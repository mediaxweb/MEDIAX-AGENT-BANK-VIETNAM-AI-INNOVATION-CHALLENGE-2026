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


def _completed_assessment_result():
    return {
        "status": "completed",
        "trace_id": "trace-dossier-test",
        "dossier_id": "DOSSIER-TEST",
        "overall_result": "READY",
        "stopped_after": None,
        "stop_reason": None,
        "credit": {"facts": {"result": "PASSED"}, "missing_data": []},
        "compliance": {"facts": {"result": "PASSED"}, "missing_data": []},
        "operations": {"facts": {"result": "READY"}, "missing_data": []},
        "dossier_evidence": [],
        "issues": [],
        "report": {"answer": "Hồ sơ đủ điều kiện trình phê duyệt."},
    }


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
    assessment_calls: list[tuple[dict, dict]] = []

    async def run_assessment(payload, **kwargs):
        assessment_calls.append((payload, kwargs))
        return _completed_assessment_result()

    service = LoanAgentService(
        FakeDatabase({"loan_dossier_bundles": bundles}),
        dossier_assessment_runner=run_assessment,
    )
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
    assert len(assessment_calls) == 1
    assert len(bundles.found["dispatch_runs"]) == 1
    assert len(bundles.updated) == 1
    completed_dispatches = [
        dispatch for dispatch in dispatched.agent_dispatches if dispatch.status == "completed"
    ]
    assert {dispatch.agent_name for dispatch in completed_dispatches} == {
        "credit",
        "compliance",
        "operations",
    }
    assert all(dispatch.payload is not None for dispatch in completed_dispatches)
    assert all(
        file.file_ref and not hasattr(file, "content")
        for dispatch in completed_dispatches
        for file in dispatch.payload.files
    )
    assessment_payload, assessment_kwargs = assessment_calls[0]
    assert assessment_payload["dossier_id"] == routed.dossier_id
    assert len({file["file_id"] for file in assessment_payload["files"]}) == 3
    assert all(file["checksum_sha256"] for file in assessment_payload["files"])
    assert assessment_kwargs["allowed_root"] == tmp_path.resolve()
    assert dispatched.assessment is not None
    assert dispatched.assessment.status == "completed"
    assert dispatched.assessment.trace_id == "trace-dossier-test"
    assert bundles.found["latest_assessment"]["overall_result"] == "READY"
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
        trace.stage == "agent_assessment" and trace.decision == "multi_agent_files"
        for trace in dispatched.routing_trace
    )


def test_dispatch_dossier_bundle_blocks_when_files_need_review(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()
    assessment_calls: list[dict] = []

    async def must_not_run(payload, **_kwargs):
        assessment_calls.append(payload)
        raise AssertionError("Assessment must not run while routing needs review")

    service = LoanAgentService(
        FakeDatabase({"loan_dossier_bundles": bundles}),
        dossier_assessment_runner=must_not_run,
    )
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
    assert assessment_calls == []
    assert dispatched.assessment is None
    assert bundles.found["routing_status"] == "blocked_needs_review"


def test_dispatch_dossier_bundle_marks_agent_input_and_gate_skips(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()

    async def input_not_ready(*_args, **_kwargs):
        return {
            "status": "input_not_ready",
            "trace_id": "trace-input-not-ready",
            "overall_result": "UNDETERMINED",
            "stopped_after": "input",
            "stop_reason": "credit_input_incomplete",
            "credit": None,
            "compliance": None,
            "operations": None,
        }

    service = LoanAgentService(
        FakeDatabase({"loan_dossier_bundles": bundles}),
        dossier_assessment_runner=input_not_ready,
    )
    routed = asyncio.run(
        service.route_dossier_bundle(
            user_id="loan-user",
            files=[
                _upload_file("cccd.pdf", b"%PDF-1.4\nidentity", "application/pdf")
            ],
        )
    )
    bundles.found = bundles.inserted[0]

    dispatched = asyncio.run(
        service.dispatch_dossier_bundle(
            user_id="loan-user",
            dossier_id=routed.dossier_id,
            idempotency_key="input-not-ready-1",
        )
    )

    statuses = {
        dispatch.agent_name: dispatch.status for dispatch in dispatched.agent_dispatches
    }
    assert statuses == {
        "credit": "input_not_ready",
        "compliance": "skipped_by_gate",
        "operations": "skipped_by_gate",
    }
    assert dispatched.assessment is not None
    assert dispatched.assessment.status == "input_not_ready"
    assert dispatched.assessment.overall_result == "UNDETERMINED"


def test_dispatch_dossier_bundle_marks_specialist_runtime_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()

    async def runtime_failure(*_args, **_kwargs):
        result = _completed_assessment_result()
        result.update(
            {
                "overall_result": "UNDETERMINED",
                "stopped_after": "credit",
                "stop_reason": "credit_not_ready_for_compliance",
                "credit": {
                    "facts": {"result": "UNDETERMINED"},
                    "missing_data": ["rag_or_agent_runtime"],
                },
                "compliance": None,
                "operations": None,
            }
        )
        return result

    service = LoanAgentService(
        FakeDatabase({"loan_dossier_bundles": bundles}),
        dossier_assessment_runner=runtime_failure,
    )
    routed = asyncio.run(
        service.route_dossier_bundle(
            user_id="loan-user",
            files=[_upload_file("cccd.pdf", b"%PDF-1.4\nidentity", "application/pdf")],
        )
    )
    bundles.found = bundles.inserted[0]

    dispatched = asyncio.run(
        service.dispatch_dossier_bundle(
            user_id="loan-user",
            dossier_id=routed.dossier_id,
            idempotency_key="runtime-failure-1",
        )
    )

    statuses = {
        dispatch.agent_name: dispatch.status for dispatch in dispatched.agent_dispatches
    }
    assert statuses == {
        "credit": "failed",
        "compliance": "skipped_by_gate",
        "operations": "skipped_by_gate",
    }
    assert dispatched.routing_status == "dispatch_failed"
    assert dispatched.assessment is not None
    assert dispatched.assessment.status == "failed"
    assert dispatched.assessment.error_type == "AgentRuntimeFailure"


def test_dispatch_dossier_bundle_does_not_report_completed_when_assessment_fails(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(configs, "loan_upload_dir", str(tmp_path))
    bundles = FakeCollection()

    async def fail_assessment(*_args, **_kwargs):
        raise RuntimeError("specialist failure detail")

    service = LoanAgentService(
        FakeDatabase({"loan_dossier_bundles": bundles}),
        dossier_assessment_runner=fail_assessment,
    )
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

    assert dispatched.routing_status == "dispatch_failed"
    assert {dispatch.status for dispatch in dispatched.agent_dispatches} == {"failed"}
    assert dispatched.assessment is not None
    assert dispatched.assessment.status == "failed"
    assert dispatched.assessment.error_type == "RuntimeError"
    assert "specialist failure detail" not in dispatched.model_dump_json()
    assert bundles.found["routing_status"] == "dispatch_failed"
