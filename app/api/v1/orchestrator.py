from __future__ import annotations

import os
import sys
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import UUID, uuid4

from agents import SQLiteSession, trace
from agents.exceptions import ModelBehaviorError, ModelRefusalError
from fastapi import APIRouter, Depends, Header, HTTPException
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.config import configs
from app.core.security import TokenError
from app.services.auth_service import AuthService, InactiveUserError, UserNotFoundError
from app.services.chat_history_service import ChatHistoryService
from logs.logging_config import logger


ROOT = Path(__file__).resolve().parents[3]
AGENT_SCRIPTS_DIR = ROOT / "agents"
if str(AGENT_SCRIPTS_DIR) not in sys.path:
    # ponytail: scripts stay outside a package to avoid shadowing the OpenAI `agents` SDK.
    sys.path.insert(0, str(AGENT_SCRIPTS_DIR))

from orchestrator_agent import (  # noqa: E402
    ChatDomain,
    DEFAULT_LLM_ERROR_CHAT_ANSWER,
    DEFAULT_MODEL,
    DEFAULT_RAG_MCP_URL,
    OrchestratorQuestionAnswer,
    answer_question,
)
from rag_agent_support import KnowledgeEvidence, log_agent_event  # noqa: E402


router = APIRouter()
SESSION_DB_PATH = ROOT / configs.resolved_orchestrator_session_db_path
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
LLM_FALLBACK_ERRORS = (OpenAIError, ModelBehaviorError, ModelRefusalError)


def get_chat_history_service() -> ChatHistoryService:
    """FastAPI dependency that instantiates the chat history service."""

    return ChatHistoryService()


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    normalized_token = token.strip()
    return normalized_token or None


async def _resolve_optional_chat_user_id(authorization: str | None) -> str | None:
    token = _extract_bearer_token(authorization)
    if not token:
        return None
    try:
        current_user = await AuthService().get_current_user_from_token(token)
    except (TokenError, UserNotFoundError, InactiveUserError) as exc:
        logger.warning("Ignoring invalid chat Authorization header for history logging: %s", exc)
        return None
    except Exception as exc:
        logger.warning("Unable to resolve chat user for history logging: %s", exc)
        return None
    return current_user.id


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Message
    session_id: UUID | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    trace_id: str
    answer: str
    domain: ChatDomain
    insufficient_information: bool
    sources: list[KnowledgeEvidence]


def _build_llm_error_answer(question: str) -> OrchestratorQuestionAnswer:
    return OrchestratorQuestionAnswer(
        question=question,
        domain="general",
        answer=DEFAULT_LLM_ERROR_CHAT_ANSWER,
        insufficient_information=True,
        sources=[],
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    authorization: str | None = Header(default=None),
    chat_history_service: ChatHistoryService = Depends(get_chat_history_service),
) -> ChatResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is required")

    session_id = request.session_id or uuid4()
    SESSION_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    session = SQLiteSession(str(session_id), db_path=SESSION_DB_PATH)
    started_at = perf_counter()
    try:
        with trace(
            "MediaX Agent Bank Chat",
            group_id=str(session_id),
            metadata={"surface": "orchestrator_chat"},
        ) as agent_trace:
            log_agent_event(
                "agent.request.started",
                session_id=str(session_id),
                workflow="chat",
            )
            log_agent_event(
                "agent.request.raw_input",
                session_id=str(session_id),
                workflow="chat",
                raw_question=request.message,
            )
            try:
                result: OrchestratorQuestionAnswer = await answer_question(
                    request.message,
                    mcp_url=os.getenv("RAG_MCP_URL", DEFAULT_RAG_MCP_URL),
                    model=os.getenv("OPENAI_AGENT_MODEL", DEFAULT_MODEL),
                    session=session,
                )
            except LLM_FALLBACK_ERRORS as error:
                log_agent_event(
                    "agent.request.llm_fallback",
                    session_id=str(session_id),
                    stage="orchestrator_chat",
                    error_type=type(error).__name__,
                    duration_ms=int((perf_counter() - started_at) * 1000),
                )
                result = _build_llm_error_answer(request.message)
            except Exception as error:
                log_agent_event(
                    "agent.request.failed",
                    session_id=str(session_id),
                    stage="orchestrator_chat",
                    error_type=type(error).__name__,
                    duration_ms=int((perf_counter() - started_at) * 1000),
                )
                raise
            log_agent_event(
                "agent.response.raw_output",
                session_id=str(session_id),
                domain=result.domain,
                raw_answer=result.answer,
                insufficient_information=result.insufficient_information,
                raw_sources=[source.model_dump(mode="json") for source in result.sources],
            )
            log_agent_event(
                "agent.request.completed",
                session_id=str(session_id),
                domain=result.domain,
                cited_sources=len(result.sources),
                insufficient_information=result.insufficient_information,
                duration_ms=int((perf_counter() - started_at) * 1000),
            )
            trace_id = agent_trace.trace_id
    finally:
        session.close()
    response = ChatResponse(
        session_id=session_id,
        trace_id=trace_id,
        answer=result.answer,
        domain=result.domain,
        insufficient_information=result.insufficient_information,
        sources=result.sources,
    )
    try:
        await chat_history_service.record_chat_exchange(
            session_id=str(response.session_id),
            user_id=await _resolve_optional_chat_user_id(authorization),
            user_message=request.message,
            assistant_answer=response.answer,
            domain=response.domain,
            trace_id=response.trace_id,
            insufficient_information=response.insufficient_information,
            sources=response.sources,
        )
    except Exception:
        logger.warning("Failed to persist orchestrator chat history.", exc_info=True)
    return response
