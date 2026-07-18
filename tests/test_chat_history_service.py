import asyncio
from types import SimpleNamespace

from app.services.chat_history_service import ChatHistoryService


class FakeMessagesCollection:
    def __init__(self, operations):
        self.inserted_batches = []
        self.operations = operations

    async def insert_many(self, documents):
        self.inserted_batches.append([document.copy() for document in documents])
        self.operations.append("insert_messages")
        return SimpleNamespace(inserted_ids=[1, 2])


class FakeSessionsCollection:
    def __init__(self, operations):
        self.updates = []
        self.operations = operations

    async def update_one(self, query, update, *, upsert):
        self.updates.append((query.copy(), update.copy(), upsert))
        self.operations.append("update_session")
        return SimpleNamespace(upserted_id="session-1")


class FakeDatabase:
    def __init__(self):
        self.operations = []
        self.messages = FakeMessagesCollection(self.operations)
        self.sessions = FakeSessionsCollection(self.operations)

    def get_chat_messages_collection(self):
        return self.messages

    def get_chat_sessions_collection(self):
        return self.sessions


def test_record_chat_exchange_persists_session_and_messages():
    database = FakeDatabase()
    service = ChatHistoryService(database)

    asyncio.run(
        service.record_chat_exchange(
            session_id="session-123",
            user_id="user-456",
            user_message="Những tài sản đảm bảo để cấp tín dụng là gì?",
            assistant_answer="Tài sản bảo đảm thường gồm bất động sản, ô tô và hàng tồn kho.",
            domain="compliance",
            trace_id="trace-test",
            insufficient_information=False,
            sources=[
                {
                    "source_id": "source-1",
                    "file_name": "policy.pdf",
                    "page": "2",
                    "excerpt": "Tài sản bảo đảm gồm...",
                }
            ],
        )
    )

    inserted = database.messages.inserted_batches[0]
    assert [message["role"] for message in inserted] == ["user", "assistant"]
    assert inserted[0]["session_id"] == "session-123"
    assert inserted[0]["user_id"] == "user-456"
    assert inserted[0]["content"].startswith("Những tài sản")
    assert inserted[1]["domain"] == "compliance"
    assert inserted[1]["trace_id"] == "trace-test"
    assert inserted[1]["sources"][0]["file_name"] == "policy.pdf"

    assert database.operations == ["update_session", "insert_messages", "update_session"]

    query, update, upsert = database.sessions.updates[0]
    assert query == {"session_id": "session-123"}
    assert upsert is True
    assert update["$setOnInsert"]["title"] == "Những tài sản đảm bảo để cấp tín dụng là gì?"
    assert update["$setOnInsert"]["message_count"] == 0
    assert "user_id" not in update["$setOnInsert"]
    assert update["$set"]["user_id"] == "user-456"
    assert "$inc" not in update

    query, update, upsert = database.sessions.updates[1]
    assert query == {"session_id": "session-123"}
    assert upsert is False
    assert "$setOnInsert" not in update
    assert update["$set"]["last_domain"] == "compliance"
    assert update["$set"]["source_count"] == 1
    assert update["$inc"] == {"message_count": 2}
