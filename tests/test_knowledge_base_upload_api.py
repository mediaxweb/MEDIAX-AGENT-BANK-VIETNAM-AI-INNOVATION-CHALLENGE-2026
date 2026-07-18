from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.schemas.auth import UserResponse
from app.api.v1 import knowledge_base
from app.core.config import configs
from app.services.knowledge_base_service import (
    KnowledgeBaseIndexedFileResult,
    KnowledgeBaseProcessResult,
)


class _FakeKnowledgeBaseService:
    def __init__(self):
        self.indexing_records = []
        self.indexed_records = []
        self.failed_records = []
        self.processed_path = None
        self.processed_path_existed_during_ingest = False
        self.processed_bytes = None
        self.metadata_overrides = None
        self.listed_user_ids = []

    async def record_user_file_indexing(self, *, user_id, document_path):
        self.indexing_records.append((user_id, document_path))

    async def record_user_indexed_file(self, *, user_id, document_path, result):
        self.indexed_records.append((user_id, document_path, result.collection_name))

    async def record_user_indexed_file_failed(self, *, user_id, document_path, error):
        self.failed_records.append((user_id, document_path, error))

    async def list_indexed_files(self, *, user_id):
        self.listed_user_ids.append(user_id)
        return [
            KnowledgeBaseIndexedFileResult(
                file_name="Policy Handbook.pdf",
                file_path="Policy Handbook.pdf",
                document_id=None,
                index_status="indexed",
                chunk_count=2,
                page_count=1,
                last_error=None,
            )
        ]

    def process_document_for_collection(self, request, *, collection_name, metadata_overrides=None):
        self.processed_path = Path(request.document_path)
        self.processed_path_existed_during_ingest = self.processed_path.exists()
        self.processed_bytes = self.processed_path.read_bytes()
        self.metadata_overrides = metadata_overrides
        return KnowledgeBaseProcessResult(
            document_count=1,
            node_count=2,
            collection_name=collection_name,
            message="ok",
        )


def _build_client(fake_service):
    app = FastAPI()
    app.include_router(knowledge_base.router, prefix="/api/v1/knowledge-base")

    async def fake_current_user():
        return UserResponse(
            id="user-123",
            email="user@example.com",
            full_name=None,
            is_active=True,
        )

    app.dependency_overrides[knowledge_base.get_current_user] = fake_current_user
    app.dependency_overrides[knowledge_base.get_knowledge_base_service] = lambda: fake_service
    return TestClient(app)


def test_process_document_accepts_pdf_upload_and_removes_temp_file(monkeypatch, tmp_path):
    upload_dir = tmp_path / "knowledge_base_uploads"
    monkeypatch.setattr(configs, "temp_kb_dir", str(upload_dir))
    fake_service = _FakeKnowledgeBaseService()
    client = _build_client(fake_service)

    response = client.post(
        "/api/v1/knowledge-base/process-document",
        files={
            "file": (
                "Policy Handbook.pdf",
                b"%PDF-1.4\ntext pdf payload",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "document_count": 1,
        "node_count": 2,
        "collection_name": "qa_collection__user__user-123",
        "message": "ok",
    }
    assert fake_service.indexing_records == [("user-123", "Policy Handbook.pdf")]
    assert fake_service.indexed_records == [
        ("user-123", "Policy Handbook.pdf", "qa_collection__user__user-123")
    ]
    assert fake_service.failed_records == []
    assert fake_service.processed_path_existed_during_ingest
    assert fake_service.processed_bytes == b"%PDF-1.4\ntext pdf payload"
    assert fake_service.metadata_overrides == {
        "file_name": "Policy Handbook.pdf",
        "file_path": "Policy Handbook.pdf",
    }
    assert upload_dir in fake_service.processed_path.parents
    assert not fake_service.processed_path.exists()


def test_process_document_can_target_user_when_enabled(monkeypatch, tmp_path):
    upload_dir = tmp_path / "knowledge_base_uploads"
    monkeypatch.setattr(configs, "temp_kb_dir", str(upload_dir))
    monkeypatch.setattr(configs, "allow_kb_target_user_upload", True)
    fake_service = _FakeKnowledgeBaseService()
    client = _build_client(fake_service)

    response = client.post(
        "/api/v1/knowledge-base/process-document",
        data={"user_id": "target-user-456"},
        files={
            "file": (
                "Policy Handbook.pdf",
                b"%PDF-1.4\ntext pdf payload",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["collection_name"] == "qa_collection__user__target-user-456"
    assert fake_service.indexing_records == [("target-user-456", "Policy Handbook.pdf")]
    assert fake_service.indexed_records == [
        ("target-user-456", "Policy Handbook.pdf", "qa_collection__user__target-user-456")
    ]


def test_process_document_rejects_target_user_when_disabled(monkeypatch, tmp_path):
    upload_dir = tmp_path / "knowledge_base_uploads"
    monkeypatch.setattr(configs, "temp_kb_dir", str(upload_dir))
    monkeypatch.setattr(configs, "allow_kb_target_user_upload", False)
    fake_service = _FakeKnowledgeBaseService()
    client = _build_client(fake_service)

    response = client.post(
        "/api/v1/knowledge-base/process-document",
        data={"user_id": "target-user-456"},
        files={
            "file": (
                "Policy Handbook.pdf",
                b"%PDF-1.4\ntext pdf payload",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Target user knowledge-base access is disabled."}
    assert fake_service.indexing_records == []
    assert fake_service.indexed_records == []
    assert fake_service.failed_records == []
    assert not upload_dir.exists()


def test_list_files_uses_current_user_by_default(monkeypatch):
    monkeypatch.setattr(configs, "allow_kb_target_user_upload", False)
    fake_service = _FakeKnowledgeBaseService()
    client = _build_client(fake_service)

    response = client.get("/api/v1/knowledge-base/files")

    assert response.status_code == 200
    assert response.json()["total_count"] == 1
    assert fake_service.listed_user_ids == ["user-123"]


def test_list_files_can_target_user_when_enabled(monkeypatch):
    monkeypatch.setattr(configs, "allow_kb_target_user_upload", True)
    fake_service = _FakeKnowledgeBaseService()
    client = _build_client(fake_service)

    response = client.get("/api/v1/knowledge-base/files?user_id=target-user-456")

    assert response.status_code == 200
    assert response.json()["files"][0]["file_name"] == "Policy Handbook.pdf"
    assert fake_service.listed_user_ids == ["target-user-456"]


def test_list_files_rejects_target_user_when_disabled(monkeypatch):
    monkeypatch.setattr(configs, "allow_kb_target_user_upload", False)
    fake_service = _FakeKnowledgeBaseService()
    client = _build_client(fake_service)

    response = client.get("/api/v1/knowledge-base/files?user_id=target-user-456")

    assert response.status_code == 403
    assert response.json() == {"detail": "Target user knowledge-base access is disabled."}
    assert fake_service.listed_user_ids == []
