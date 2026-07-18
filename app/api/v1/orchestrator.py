from __future__ import annotations

import os
import sys
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import UUID, uuid4

from agents import SQLiteSession, trace
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints


ROOT = Path(__file__).resolve().parents[3]
AGENT_SCRIPTS_DIR = ROOT / "agents"
if str(AGENT_SCRIPTS_DIR) not in sys.path:
    # ponytail: scripts stay outside a package to avoid shadowing the OpenAI `agents` SDK.
    sys.path.insert(0, str(AGENT_SCRIPTS_DIR))

from orchestrator_agent import (  # noqa: E402
    DEFAULT_MODEL,
    DEFAULT_RAG_MCP_URL,
    OrchestratorQuestionAnswer,
    answer_question,
)
from rag_agent_support import KnowledgeEvidence, RAGDomain, log_agent_event  # noqa: E402


router = APIRouter()
SESSION_DB_PATH = ROOT / ".local_storage" / "orchestrator_sessions.db"
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Message
    session_id: UUID | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    trace_id: str
    answer: str
    domain: RAGDomain
    insufficient_information: bool
    sources: list[KnowledgeEvidence]


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
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
            try:
                result: OrchestratorQuestionAnswer = await answer_question(
                    request.message,
                    mcp_url=os.getenv("RAG_MCP_URL", DEFAULT_RAG_MCP_URL),
                    model=os.getenv("OPENAI_AGENT_MODEL", DEFAULT_MODEL),
                    session=session,
                )
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
    return ChatResponse(
        session_id=session_id,
        trace_id=trace_id,
        answer=result.answer,
        domain=result.domain,
        insufficient_information=result.insufficient_information,
        sources=result.sources,
    )
