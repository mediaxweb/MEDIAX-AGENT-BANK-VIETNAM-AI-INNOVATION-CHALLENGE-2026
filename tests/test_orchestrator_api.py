from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import orchestrator
from orchestrator_agent import DEFAULT_UNROUTED_CHAT_ANSWER, OrchestratorQuestionAnswer
from rag_agent_support import KnowledgeEvidence


def test_anonymous_chat_creates_and_reuses_session_id(monkeypatch, tmp_path):
    seen_session_ids: list[str] = []
    seen_history_sizes: list[int] = []
    seen_traces: list[tuple[str, str]] = []

    class FakeChatHistoryService:
        def __init__(self):
            self.calls = []

        async def record_chat_exchange(self, **kwargs):
            self.calls.append(kwargs)

    class FakeTrace:
        def __init__(self, trace_id):
            self.trace_id = trace_id

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    def fake_trace(workflow_name, *, group_id, metadata):
        seen_traces.append((workflow_name, group_id))
        return FakeTrace(f"trace-test-{len(seen_traces)}")

    async def fake_answer(question, **kwargs):
        session = kwargs["session"]
        seen_session_ids.append(session.session_id)
        seen_history_sizes.append(len(await session.get_items()))
        await session.add_items([{"role": "user", "content": question}])
        return OrchestratorQuestionAnswer(
            question=question,
            domain="compliance",
            answer="Tỷ lệ tối đa là 80%.",
            insufficient_information=False,
            sources=[
                KnowledgeEvidence(
                    source_id="source-1",
                    file_name="policy.pdf",
                    page="2",
                    excerpt="Tỷ lệ tối đa là 80%.",
                )
            ],
        )

    monkeypatch.setattr(orchestrator, "answer_question", fake_answer)
    monkeypatch.setattr(orchestrator, "trace", fake_trace)
    monkeypatch.setattr(orchestrator, "SESSION_DB_PATH", tmp_path / "sessions.db")
    fake_history = FakeChatHistoryService()
    app = FastAPI()
    app.dependency_overrides[orchestrator.get_chat_history_service] = lambda: fake_history
    app.include_router(orchestrator.router, prefix="/api/v1/orchestrator")
    client = TestClient(app)

    first = client.post("/api/v1/orchestrator/chat", json={"message": "Tỷ lệ tối đa?"})
    assert first.status_code == 200
    session_id = first.json()["session_id"]
    assert first.json()["trace_id"] == "trace-test-1"
    assert first.json()["sources"][0]["page"] == "2"

    second = client.post(
        "/api/v1/orchestrator/chat",
        json={"session_id": session_id, "message": "Còn ô tô thì sao?"},
    )
    assert second.status_code == 200
    assert second.json()["session_id"] == session_id
    assert second.json()["trace_id"] == "trace-test-2"
    assert seen_session_ids == [session_id, session_id]
    assert seen_history_sizes == [0, 1]
    assert seen_traces == [
        ("MediaX Agent Bank Chat", session_id),
        ("MediaX Agent Bank Chat", session_id),
    ]
    assert [call["session_id"] for call in fake_history.calls] == [session_id, session_id]
    assert [call["user_message"] for call in fake_history.calls] == [
        "Tỷ lệ tối đa?",
        "Còn ô tô thì sao?",
    ]
    assert fake_history.calls[0]["assistant_answer"] == "Tỷ lệ tối đa là 80%."
    assert fake_history.calls[0]["domain"] == "compliance"
    assert fake_history.calls[0]["trace_id"] == "trace-test-1"
    assert fake_history.calls[0]["user_id"] is None
    assert fake_history.calls[0]["sources"][0].file_name == "policy.pdf"


def test_chat_returns_general_clarification_when_question_is_unrouted(monkeypatch, tmp_path):
    class FakeTrace:
        trace_id = "trace-unrouted"

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    async def fake_answer(question, **kwargs):
        return OrchestratorQuestionAnswer(
            question=question,
            domain="general",
            answer=DEFAULT_UNROUTED_CHAT_ANSWER,
            insufficient_information=True,
            sources=[],
        )

    monkeypatch.setattr(orchestrator, "answer_question", fake_answer)
    monkeypatch.setattr(orchestrator, "trace", lambda *_args, **_kwargs: FakeTrace())
    monkeypatch.setattr(orchestrator, "SESSION_DB_PATH", tmp_path / "sessions.db")
    app = FastAPI()
    app.include_router(orchestrator.router, prefix="/api/v1/orchestrator")
    client = TestClient(app)

    response = client.post("/api/v1/orchestrator/chat", json={"message": "alo"})

    assert response.status_code == 200
    assert response.json()["domain"] == "general"
    assert response.json()["answer"] == DEFAULT_UNROUTED_CHAT_ANSWER
    assert response.json()["insufficient_information"] is True
    assert response.json()["sources"] == []
