from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.schemas.auth import UserResponse
from app.api.schemas.loan_agent import CustomerResponse, UploadedDocumentResponse
from app.api.v1 import loan_agent


NOW = datetime(2026, 7, 17, tzinfo=timezone.utc)


class _FakeLoanAgentService:
    def __init__(self):
        self.created_customer_user_id = None
        self.uploaded_legal_doc = None
        self.routed_dossier_bundle = None
        self.dispatched_dossier_bundle = None

    async def create_customer(self, *, user_id, payload):
        self.created_customer_user_id = user_id
        return CustomerResponse(
            id="customer-1",
            full_name=payload.full_name,
            phone=payload.phone,
            email=str(payload.email) if payload.email else None,
            national_id=payload.national_id,
            date_of_birth=payload.date_of_birth,
            address=payload.address,
            metadata=payload.metadata,
            created_at=NOW,
            updated_at=NOW,
        )

    async def upload_legal_doc(self, *, user_id, loan_profile_id, file, doc_type, description):
        self.uploaded_legal_doc = {
            "user_id": user_id,
            "loan_profile_id": loan_profile_id,
            "file_name": file.filename,
            "doc_type": doc_type,
            "description": description,
        }
        return UploadedDocumentResponse(
            id="doc-1",
            loan_profile_id=loan_profile_id,
            category="legal_doc",
            file_name=file.filename,
            file_path="/tmp/doc-1.pdf",
            content_type=file.content_type,
            size_bytes=10,
            doc_type=doc_type,
            description=description,
            status="uploaded",
            created_at=NOW,
        )

    async def route_dossier_bundle(self, *, user_id, files):
        self.routed_dossier_bundle = {
            "user_id": user_id,
            "file_names": [file.filename for file in files],
        }
        return {
            "dossier_id": "DOSSIER-20260718-DEMO0001",
            "routing_status": "ready_to_dispatch",
            "received_files_count": len(files),
            "accepted_files_count": len(files),
            "ignored_files_count": 0,
            "needs_review_count": 0,
            "document_registry": [],
            "agent_packages": [
                {
                    "agent_name": "credit",
                    "file_count": 0,
                    "package_reason": "Files routed to Credit Agent.",
                    "files": [],
                },
                {
                    "agent_name": "compliance",
                    "file_count": 0,
                    "package_reason": "Files routed to Compliance Agent.",
                    "files": [],
                },
                {
                    "agent_name": "operations",
                    "file_count": 0,
                    "package_reason": "Files routed to Operations Agent.",
                    "files": [],
                },
            ],
            "needs_review_files": [],
            "ignored_files": [],
            "routing_trace": [],
            "created_at": NOW,
            "updated_at": NOW,
        }

    async def get_dossier_routing(self, *, user_id, dossier_id):
        return {
            "dossier_id": dossier_id,
            "routing_status": "ready_to_dispatch",
            "received_files_count": 0,
            "accepted_files_count": 0,
            "ignored_files_count": 0,
            "needs_review_count": 0,
            "document_registry": [],
            "agent_packages": [],
            "needs_review_files": [],
            "ignored_files": [],
            "routing_trace": [],
            "created_at": NOW,
            "updated_at": NOW,
        }

    async def dispatch_dossier_bundle(self, *, user_id, dossier_id, idempotency_key):
        self.dispatched_dossier_bundle = {
            "user_id": user_id,
            "dossier_id": dossier_id,
            "idempotency_key": idempotency_key,
        }
        return {
            "dossier_id": dossier_id,
            "routing_status": "dispatched",
            "routing_batch_id": "ROUTING-BATCH-20260718-DEMO0001",
            "message": "Planner dispatched file references.",
            "agent_dispatches": [
                {
                    "agent_name": "credit",
                    "status": "completed",
                    "file_count": 1,
                    "routing_batch_id": "ROUTING-BATCH-20260718-DEMO0001",
                    "dispatched_at": NOW,
                    "message": "Credit assessment completed.",
                    "payload": {
                        "dossier_id": dossier_id,
                        "routing_batch_id": "ROUTING-BATCH-20260718-DEMO0001",
                        "agent_name": "credit",
                        "file_count": 1,
                        "package_reason": "Files routed to Credit Agent.",
                        "files": [],
                        "scope_note": ["File references only."],
                        "created_at": NOW,
                    },
                }
            ],
            "assessment": {
                "status": "completed",
                "trace_id": "trace-dossier-api-test",
                "overall_result": "READY",
                "result": {"report": {"answer": "Đủ điều kiện trình phê duyệt."}},
                "created_at": NOW,
                "updated_at": NOW,
            },
            "agent_packages": [],
            "needs_review_count": 0,
            "needs_review_files": [],
            "ignored_files_count": 0,
            "ignored_files": [],
            "routing_trace": [],
            "created_at": NOW,
            "updated_at": NOW,
        }


def _build_client(fake_service):
    app = FastAPI()
    app.include_router(loan_agent.router, prefix="/api/v1/loan")

    async def fake_current_user():
        return UserResponse(
            id="user-123",
            email="user@example.com",
            full_name=None,
            is_active=True,
        )

    app.dependency_overrides[loan_agent.get_current_user] = fake_current_user
    app.dependency_overrides[loan_agent.get_loan_agent_service] = lambda: fake_service
    return TestClient(app)


def test_loan_agent_openapi_exposes_mvp_endpoints():
    app = FastAPI()
    app.include_router(loan_agent.router, prefix="/api/v1/loan")
    openapi = app.openapi()
    paths = openapi["paths"]

    expected_routes = {
        ("post", "/api/v1/loan/customers"),
        ("get", "/api/v1/loan/customers/{customer_id}"),
        ("patch", "/api/v1/loan/customers/{customer_id}"),
        ("post", "/api/v1/loan/loan-profiles"),
        ("get", "/api/v1/loan/loan-profiles/{loan_profile_id}"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/legal-docs"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/check-legal-docs"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/financial-reports"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/collaterals"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/check-financials"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/check-collateral"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/check-credit-rule"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/compliance-result"),
        ("patch", "/api/v1/loan/loan-profiles/{loan_profile_id}/status"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/checklist"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/calculate-limit"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/tasks"),
        ("post", "/api/v1/loan/loan-profiles/{loan_profile_id}/reports"),
        ("get", "/api/v1/loan/loan-profiles/{loan_profile_id}/reports"),
        ("post", "/api/v1/loan/dossiers/route-bundle"),
        ("get", "/api/v1/loan/dossiers/{dossier_id}/routing"),
        ("post", "/api/v1/loan/dossiers/{dossier_id}/dispatch"),
    }
    discovered_routes = {
        (method, path)
        for path, operations in paths.items()
        for method in operations
        if method in {"get", "post", "patch", "delete"}
    }

    assert expected_routes <= discovered_routes
    assert len(expected_routes) == 22
    assert "multipart/form-data" in paths[
        "/api/v1/loan/loan-profiles/{loan_profile_id}/legal-docs"
    ]["post"]["requestBody"]["content"]
    assert "multipart/form-data" in paths[
        "/api/v1/loan/loan-profiles/{loan_profile_id}/financial-reports"
    ]["post"]["requestBody"]["content"]
    assert "multipart/form-data" in paths[
        "/api/v1/loan/loan-profiles/{loan_profile_id}/collaterals"
    ]["post"]["requestBody"]["content"]
    assert "multipart/form-data" in paths[
        "/api/v1/loan/dossiers/route-bundle"
    ]["post"]["requestBody"]["content"]


def test_create_customer_uses_authenticated_user_scope():
    fake_service = _FakeLoanAgentService()
    client = _build_client(fake_service)

    response = client.post(
        "/api/v1/loan/customers",
        json={
            "full_name": "Nguyen Van A",
            "phone": "0900000000",
            "email": "customer@example.com",
        },
    )

    assert response.status_code == 201
    assert response.json()["full_name"] == "Nguyen Van A"
    assert fake_service.created_customer_user_id == "user-123"


def test_upload_legal_doc_accepts_multipart_file():
    fake_service = _FakeLoanAgentService()
    client = _build_client(fake_service)

    response = client.post(
        "/api/v1/loan/loan-profiles/profile-1/legal-docs",
        data={
            "doc_type": "identity",
            "description": "Citizen identity card",
        },
        files={
            "file": (
                "identity.pdf",
                b"%PDF-1.4\nidentity",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["file_name"] == "identity.pdf"
    assert fake_service.uploaded_legal_doc == {
        "user_id": "user-123",
        "loan_profile_id": "profile-1",
        "file_name": "identity.pdf",
        "doc_type": "identity",
        "description": "Citizen identity card",
    }


def test_route_dossier_bundle_accepts_multipart_files():
    fake_service = _FakeLoanAgentService()
    client = _build_client(fake_service)

    response = client.post(
        "/api/v1/loan/dossiers/route-bundle",
        files=[
            (
                "files",
                (
                    "bctc.pdf",
                    b"%PDF-1.4\nfinancial",
                    "application/pdf",
                ),
            ),
            (
                "files",
                (
                    "cccd.pdf",
                    b"%PDF-1.4\nidentity",
                    "application/pdf",
                ),
            ),
        ],
    )

    assert response.status_code == 201
    assert response.json()["dossier_id"] == "DOSSIER-20260718-DEMO0001"
    assert fake_service.routed_dossier_bundle == {
        "user_id": "user-123",
        "file_names": ["bctc.pdf", "cccd.pdf"],
    }


def test_dispatch_dossier_bundle_accepts_idempotency_key():
    fake_service = _FakeLoanAgentService()
    client = _build_client(fake_service)

    response = client.post(
        "/api/v1/loan/dossiers/DOSSIER-20260718-DEMO0001/dispatch",
        json={"idempotency_key": "dispatch-demo-1"},
    )

    assert response.status_code == 200
    assert response.json()["routing_status"] == "dispatched"
    assert response.json()["routing_batch_id"] == "ROUTING-BATCH-20260718-DEMO0001"
    assert response.json()["assessment"]["status"] == "completed"
    assert response.json()["assessment"]["trace_id"] == "trace-dossier-api-test"
    assert fake_service.dispatched_dossier_bundle == {
        "user_id": "user-123",
        "dossier_id": "DOSSIER-20260718-DEMO0001",
        "idempotency_key": "dispatch-demo-1",
    }
