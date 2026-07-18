from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import orchestrator
from orchestrator_agent import OrchestratorQuestionAnswer
from rag_agent_support import KnowledgeEvidence


def test_anonymous_chat_creates_and_reuses_session_id(monkeypatch, tmp_path):
    seen_session_ids: list[str] = []
    seen_history_sizes: list[int] = []
    seen_traces: list[tuple[str, str]] = []

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
    app = FastAPI()
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
