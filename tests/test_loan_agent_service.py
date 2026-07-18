import asyncio
import io
from types import SimpleNamespace
import zipfile

import pytest
from bson import ObjectId
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.api.schemas.loan_agent import CustomerCreateRequest, LoanLimitCalculationRequest
from app.core.config import configs
from app.services.loan_agent_service import LoanAgentService, LoanAgentValidationError


class FakeCollection:
    def __init__(self, found=None):
        self.found = found
        self.inserted = []
        self.updated = []

    async def find_one(self, query):
        return self.found

    async def insert_one(self, document):
        self.inserted.append(document.copy())
        return SimpleNamespace(inserted_id=ObjectId())

    async def update_one(self, query, update):
        self.updated.append({"query": query, "update": update})
        if not self.found:
            return SimpleNamespace(matched_count=0)
        for key, expected in query.items():
            if self.found.get(key) != expected:
                return SimpleNamespace(matched_count=0)
        for key, value in (update.get("$set") or {}).items():
            self.found[key] = value
        for key, value in (update.get("$push") or {}).items():
            self.found.setdefault(key, [])
            if isinstance(value, dict) and "$each" in value:
                self.found[key].extend(value["$each"])
            else:
                self.found[key].append(value)
        return SimpleNamespace(matched_count=1)


class FakeDatabase:
    def __init__(self, collections):
        self.collections = collections

    def get_loan_collection(self, name):
        return self.collections[name]


class FailingComplianceDispatchService(LoanAgentService):
    async def _send_dossier_agent_payload(self, payload):
        if payload["agent_name"] == "compliance":
            raise RuntimeError("compliance outbox unavailable")


def test_create_customer_rejects_duplicate_identity_before_insert():
    customers = FakeCollection(found={"_id": ObjectId(), "national_id": "001"})
    service = LoanAgentService(FakeDatabase({"loan_customers": customers}))

    with pytest.raises(LoanAgentValidationError, match="same identity"):
        asyncio.run(
            service.create_customer(
                user_id="loan-user",
                payload=CustomerCreateRequest(full_name="Demo", national_id="001"),
            )
        )

    assert customers.inserted == []


def test_persisted_limit_is_zero_when_case_has_hard_stop():
    profile_id = ObjectId()
    profiles = FakeCollection(
        found={
            "_id": profile_id,
            "user_id": "loan-user",
            "loan_amount": 8_000_000_000,
            "currency": "VND",
        }
    )
    calculations = FakeCollection()
    service = LoanAgentService(
        FakeDatabase(
            {
                "loan_profiles": profiles,
                "loan_limit_calculations": calculations,
            }
        )
    )

    result = asyncio.run(
        service.calculate_loan_limit(
            user_id="loan-user",
            loan_profile_id=str(profile_id),
            payload=LoanLimitCalculationRequest(
                total_capital_need=10_000_000_000,
                collateral_value=10_000_000_000,
                ltv_ratio=0.8,
                dscr=1.35,
                checklist_score=94,
                hard_stop=True,
            ),
        )
    )

    assert result.calculated_limit == 8_000_000_000
    assert result.final_factor == 0
    assert result.recommended_limit == 0


def _upload_file(name: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename=name,
        headers=Headers({"content-type": content_type}),
    )


def _zip_upload(entries: dict[str, bytes]) -> UploadFile:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in entries.items():
            archive.writestr(path, content)
    return _upload_file("bo_ho_so.zip", buffer.getvalue(), "application/zip")


def test_route_dossier_bundle_routes_pdf_zip_and_ignores_system_junk(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()
    service = LoanAgentService(FakeDatabase({"loan_dossier_bundles": bundles}))
    upload = _zip_upload(
        {
            "01_Ho_so_phap_ly/01_Giay_chung_nhan_dang_ky_doanh_nghiep_DEMO.pdf": b"%PDF-1.4\nlegal",
            "02_Ho_so_cap_tin_dung/06_Giay_de_nghi_cap_tin_dung_DEMO.pdf": b"%PDF-1.4\ncredit",
            ".DS_Store": b"junk",
            "__MACOSX/._bo_ho_so": b"junk",
        }
    )

    result = asyncio.run(
        service.route_dossier_bundle(
            user_id="loan-user",
            files=[upload],
        )
    )

    assert result.routing_status == "ready_to_dispatch"
    assert result.accepted_files_count == 2
    assert result.ignored_files_count == 2
    assert result.needs_review_count == 0
    credit_package = next(package for package in result.agent_packages if package.agent_name == "credit")
    compliance_package = next(package for package in result.agent_packages if package.agent_name == "compliance")
    operations_package = next(package for package in result.agent_packages if package.agent_name == "operations")
    assert credit_package.file_count == 2
    assert compliance_package.file_count == 1
    assert operations_package.file_count == 0
    assert any(file.detected_document_type == "business_registration" for file in credit_package.files)
    assert any(file.detected_document_type == "credit_request_form" for file in compliance_package.files)
    assert bundles.inserted[0]["dossier_id"] == result.dossier_id


def test_route_dossier_bundle_handles_unstructured_pdf_names(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()
    service = LoanAgentService(FakeDatabase({"loan_dossier_bundles": bundles}))
    uploads = [
        _upload_file("bctc_final_new.pdf", b"%PDF-1.4\nfinancial", "application/pdf"),
        _upload_file("scan001.pdf", b"%PDF-1.4\nunknown", "application/pdf"),
    ]

    result = asyncio.run(
        service.route_dossier_bundle(
            user_id="loan-user",
            files=uploads,
        )
    )

    assert result.routing_status == "needs_review"
    assert result.accepted_files_count == 2
    assert result.needs_review_count == 1
    compliance_package = next(package for package in result.agent_packages if package.agent_name == "compliance")
    assert compliance_package.file_count == 1
    assert compliance_package.files[0].detected_document_type == "financial_statement"
    assert result.needs_review_files[0].original_filename == "scan001.pdf"


def test_route_dossier_bundle_routes_summary_index_to_operations(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()
    service = LoanAgentService(FakeDatabase({"loan_dossier_bundles": bundles}))
    upload = _zip_upload(
        {
            "HO_SO_KHACH_HANG_NAP_VAO_AGENTS/00_DANH_MUC_VA_TOM_TAT_HO_SO.pdf": b"%PDF-1.4\ncredit request summary",
        }
    )

    result = asyncio.run(
        service.route_dossier_bundle(
            user_id="loan-user",
            files=[upload],
        )
    )

    operations_package = next(package for package in result.agent_packages if package.agent_name == "operations")
    credit_package = next(package for package in result.agent_packages if package.agent_name == "credit")
    compliance_package = next(package for package in result.agent_packages if package.agent_name == "compliance")
    assert operations_package.file_count == 1
    assert operations_package.files[0].detected_document_type == "dossier_summary"
    assert credit_package.file_count == 0
    assert compliance_package.file_count == 0


def test_route_dossier_bundle_rejects_unsafe_zip_path(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()
    service = LoanAgentService(FakeDatabase({"loan_dossier_bundles": bundles}))
    upload = _zip_upload({"../evil.pdf": b"%PDF-1.4\nunsafe"})

    with pytest.raises(LoanAgentValidationError, match="đường dẫn không an toàn"):
        asyncio.run(
            service.route_dossier_bundle(
                user_id="loan-user",
                files=[upload],
            )
        )


def test_route_dossier_bundle_rejects_non_pdf_inside_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()
    service = LoanAgentService(FakeDatabase({"loan_dossier_bundles": bundles}))
    upload = _zip_upload(
        {
            "01_Ho_so_phap_ly/01_Giay_chung_nhan_dang_ky_doanh_nghiep_DEMO.pdf": b"%PDF-1.4\nlegal",
            "notes.txt": b"not supported",
        }
    )

    with pytest.raises(LoanAgentValidationError, match="chỉ được chứa PDF"):
        asyncio.run(
            service.route_dossier_bundle(
                user_id="loan-user",
                files=[upload],
            )
        )


def test_dispatch_dossier_bundle_sends_file_references_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()
    service = LoanAgentService(FakeDatabase({"loan_dossier_bundles": bundles}))
    upload = _zip_upload(
        {
            "01_Ho_so_phap_ly/01_Giay_chung_nhan_dang_ky_doanh_nghiep_DEMO.pdf": b"%PDF-1.4\nlegal",
            "03_Ho_so_tai_chinh/11_BCTC_2025_DEMO.pdf": b"%PDF-1.4\nfinancial",
            "05_Tai_san_bao_dam/21_Chung_thu_tham_dinh_gia_DEMO.pdf": b"%PDF-1.4\nvaluation",
        }
    )
    routed = asyncio.run(
        service.route_dossier_bundle(
            user_id="loan-user",
            files=[upload],
        )
    )
    bundles.found = bundles.inserted[0]

    dispatched = asyncio.run(
        service.dispatch_dossier_bundle(
            user_id="loan-user",
            dossier_id=routed.dossier_id,
            idempotency_key="dispatch-demo-1",
        )
    )
    replayed = asyncio.run(
        service.dispatch_dossier_bundle(
            user_id="loan-user",
            dossier_id=routed.dossier_id,
            idempotency_key="dispatch-demo-1",
        )
    )

    assert dispatched.routing_status == "dispatched"
    assert replayed.routing_batch_id == dispatched.routing_batch_id
    assert len(bundles.found["dispatch_runs"]) == 1
    assert len(bundles.updated) == 1
    sent_dispatches = [
        dispatch for dispatch in dispatched.agent_dispatches if dispatch.status == "sent"
    ]
    assert {dispatch.agent_name for dispatch in sent_dispatches} == {
        "credit",
        "compliance",
        "operations",
    }
    assert all(dispatch.payload is not None for dispatch in sent_dispatches)
    assert all(
        file.file_ref and not hasattr(file, "content")
        for dispatch in sent_dispatches
        for file in dispatch.payload.files
    )
    operations_dispatch = next(
        dispatch for dispatch in dispatched.agent_dispatches if dispatch.agent_name == "operations"
    )
    compliance_dispatch = next(
        dispatch for dispatch in dispatched.agent_dispatches if dispatch.agent_name == "compliance"
    )
    assert operations_dispatch.file_count == 1
    assert any(
        file.file_id == operations_dispatch.payload.files[0].file_id
        for file in compliance_dispatch.payload.files
    )
    assert any(
        trace.stage == "planner_dispatch" and trace.decision == "multi_agent_files"
        for trace in dispatched.routing_trace
    )


def test_dispatch_dossier_bundle_blocks_when_files_need_review(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()
    service = LoanAgentService(FakeDatabase({"loan_dossier_bundles": bundles}))
    routed = asyncio.run(
        service.route_dossier_bundle(
            user_id="loan-user",
            files=[
                _upload_file("scan001.pdf", b"%PDF-1.4\nunknown", "application/pdf"),
                _upload_file("bctc_2025.pdf", b"%PDF-1.4\nfinancial", "application/pdf"),
            ],
        )
    )
    bundles.found = bundles.inserted[0]

    dispatched = asyncio.run(
        service.dispatch_dossier_bundle(
            user_id="loan-user",
            dossier_id=routed.dossier_id,
            idempotency_key="blocked-1",
        )
    )

    assert dispatched.routing_status == "blocked_needs_review"
    assert dispatched.needs_review_count == 1
    assert {dispatch.status for dispatch in dispatched.agent_dispatches} == {
        "blocked_needs_review"
    }
    assert bundles.found["routing_status"] == "blocked_needs_review"


def test_dispatch_dossier_bundle_reports_partial_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()
    service = FailingComplianceDispatchService(FakeDatabase({"loan_dossier_bundles": bundles}))
    routed = asyncio.run(
        service.route_dossier_bundle(
            user_id="loan-user",
            files=[
                _upload_file("cccd.pdf", b"%PDF-1.4\nidentity", "application/pdf"),
                _upload_file("bctc_2025.pdf", b"%PDF-1.4\nfinancial", "application/pdf"),
            ],
        )
    )
    bundles.found = bundles.inserted[0]

    dispatched = asyncio.run(
        service.dispatch_dossier_bundle(
            user_id="loan-user",
            dossier_id=routed.dossier_id,
            idempotency_key="partial-1",
        )
    )

    assert dispatched.routing_status == "partial_dispatch_failed"
    dispatches_by_agent = {
        dispatch.agent_name: dispatch for dispatch in dispatched.agent_dispatches
    }
    assert dispatches_by_agent["credit"].status == "sent"
    assert dispatches_by_agent["compliance"].status == "failed"
    assert dispatches_by_agent["operations"].status == "skipped_no_files"
    assert bundles.found["routing_status"] == "partial_dispatch_failed"
