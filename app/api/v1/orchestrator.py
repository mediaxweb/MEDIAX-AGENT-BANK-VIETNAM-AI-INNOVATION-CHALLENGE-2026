from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from agents import SQLiteSession
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
from rag_agent_support import KnowledgeEvidence, RAGDomain  # noqa: E402


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
    try:
        result: OrchestratorQuestionAnswer = await answer_question(
            request.message,
            mcp_url=os.getenv("RAG_MCP_URL", DEFAULT_RAG_MCP_URL),
            model=os.getenv("OPENAI_AGENT_MODEL", DEFAULT_MODEL),
            session=session,
        )
    finally:
        session.close()
    return ChatResponse(
        session_id=session_id,
        answer=result.answer,
        domain=result.domain,
        insufficient_information=result.insufficient_information,
        sources=result.sources,
    )
