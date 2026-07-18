from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from app.core.database import Database


class ChatHistoryService:
    """Persist orchestrator chat exchanges for future history/audit features."""

    def __init__(self, database: Database = Database) -> None:
        self.database = database

    async def record_chat_exchange(
        self,
        *,
        session_id: str,
        user_id: str | None,
        user_message: str,
        assistant_answer: str,
        domain: str,
        trace_id: str,
        insufficient_information: bool,
        sources: Sequence[Any],
    ) -> None:
        now = self._now()
        normalized_session_id = self._normalize_text(session_id)
        normalized_user_id = self._normalize_optional_text(user_id)
        serialized_sources = [self._serialize_source(source) for source in sources]

        await self.database.get_chat_messages_collection().insert_many(
            [
                {
                    "session_id": normalized_session_id,
                    "user_id": normalized_user_id,
                    "role": "user",
                    "content": self._normalize_text(user_message),
                    "created_at": now,
                },
                {
                    "session_id": normalized_session_id,
                    "user_id": normalized_user_id,
                    "role": "assistant",
                    "content": self._normalize_text(assistant_answer),
                    "domain": self._normalize_text(domain),
                    "trace_id": self._normalize_text(trace_id),
                    "insufficient_information": bool(insufficient_information),
                    "sources": serialized_sources,
                    "created_at": now,
                },
            ]
        )

        await self.database.get_chat_sessions_collection().update_one(
            {"session_id": normalized_session_id},
            {
                "$setOnInsert": {
                    "session_id": normalized_session_id,
                    "title": self._build_title(user_message),
                    "created_at": now,
                    "message_count": 0,
                },
                "$set": {
                    "user_id": normalized_user_id,
                    "updated_at": now,
                    "last_domain": self._normalize_text(domain),
                    "last_trace_id": self._normalize_text(trace_id),
                    "last_message": self._normalize_text(user_message),
                    "last_answer": self._normalize_text(assistant_answer),
                    "insufficient_information": bool(insufficient_information),
                    "source_count": len(serialized_sources),
                },
                "$inc": {"message_count": 2},
            },
            upsert=True,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip()

    @classmethod
    def _normalize_optional_text(cls, value: Any) -> str | None:
        normalized = cls._normalize_text(value)
        return normalized or None

    @classmethod
    def _build_title(cls, value: Any) -> str:
        normalized = cls._normalize_text(value)
        if len(normalized) <= 120:
            return normalized or "Untitled chat"
        return f"{normalized[:117].rstrip()}..."

    @staticmethod
    def _serialize_source(source: Any) -> dict[str, Any]:
        if hasattr(source, "model_dump"):
            return source.model_dump(mode="json")
        if isinstance(source, dict):
            return dict(source)
        return {"value": str(source)}
