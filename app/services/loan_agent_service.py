from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import unicodedata
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import UploadFile

from app.api.schemas.loan_agent import (
    CaseStatusResponse,
    CaseStatusUpdateRequest,
    ChecklistCreateRequest,
    ChecklistResponse,
    CheckResultResponse,
    CollateralResponse,
    ComplianceResultRequest,
    ComplianceResultResponse,
    CustomerCreateRequest,
    CustomerResponse,
    CustomerSearchMatch,
    CustomerSearchResponse,
    CustomerUpdateRequest,
    DossierAgentDispatchPayload,
    DossierAgentDispatchResult,
    DossierAgentFile,
    DossierAgentPackage,
    DossierDispatchResponse,
    DossierDispatchSnapshot,
    DossierDocumentRecord,
    DossierIgnoredFile,
    DossierRoutingResponse,
    DossierRoutingTraceEntry,
    FinancialReportResponse,
    LoanLimitCalculationRequest,
    LoanLimitCalculationResponse,
    LoanProfileCreateRequest,
    LoanProfileResponse,
    ReportCreateRequest,
    ReportResponse,
    ReportsListResponse,
    TaskCreateRequest,
    TaskResponse,
    UploadedDocumentResponse,
)
from app.core.config import configs
from app.core.database import Database


UPLOAD_CHUNK_SIZE_BYTES = 1024 * 1024
DOSSIER_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
DOSSIER_MAX_SINGLE_FILE_BYTES = 25 * 1024 * 1024
DOSSIER_MAX_FILES = 100
DOSSIER_DIRECT_UPLOAD_EXTENSIONS = frozenset({".pdf"})
DOSSIER_ZIP_MEMBER_EXTENSIONS = frozenset({".pdf"})
DOSSIER_METADATA_FILENAMES = frozenset({"manifest.csv", "document_checklist.csv"})
DOSSIER_SYSTEM_PATH_PARTS = frozenset({"__macosx"})
DOSSIER_SYSTEM_FILENAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini"})
DOSSIER_AGENT_NAMES = ("credit", "compliance", "operations")
DOSSIER_DISPATCH_SCOPE_NOTE = (
    "Planner chỉ gửi tham chiếu file; phân tích nghiệp vụ chuyên sâu là bước tiếp theo của agent chuyên gia.",
    "Payload không chứa nội dung nhị phân của PDF.",
    "File ở trạng thái needs_review được giữ lại cho tới khi Planner hoặc người vận hành xác nhận tuyến xử lý.",
)


class LoanAgentError(Exception):
    """Base error for loan-agent service failures."""


class LoanAgentNotFoundError(LoanAgentError):
    """Raised when a user-scoped loan-agent record cannot be found."""


class LoanAgentValidationError(LoanAgentError):
    """Raised when a loan-agent request is invalid."""


class LoanAgentService:
    """Service layer for the bank loan-agent MVP workflow."""

    DEFAULT_CHECKLIST_ITEMS = (
        {"title": "Customer profile is created", "owner_agent": "credit"},
        {"title": "Legal documents are uploaded", "owner_agent": "credit"},
        {"title": "Financials are checked", "owner_agent": "compliance"},
        {"title": "Collateral is checked", "owner_agent": "compliance"},
        {"title": "Loan limit is calculated", "owner_agent": "operations"},
        {"title": "Case report is created", "owner_agent": "operations"},
    )

    def __init__(self, database: Database = Database):
        self.database = database

    async def create_customer(self, *, user_id: str, payload: CustomerCreateRequest) -> CustomerResponse:
        customer_data = payload.model_dump(mode="json", exclude_none=True)
        if "national_id" in customer_data:
            customer_data["national_id"] = self._normalize_identity(customer_data["national_id"])
        metadata = customer_data.get("metadata") or {}
        if metadata.get("tax_code"):
            metadata["tax_code"] = self._normalize_identity(metadata["tax_code"])
            customer_data["metadata"] = metadata
        await self._ensure_unique_customer_identity(
            user_id=user_id,
            national_id=customer_data.get("national_id"),
            tax_code=metadata.get("tax_code"),
        )
        now = self._now()
        document = {
            **customer_data,
            "user_id": self._normalize_user_id(user_id),
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection("loan_customers").insert_one(document)
        document["_id"] = result.inserted_id
        return CustomerResponse.model_validate(self._serialize_record(document))

    async def get_customer(self, *, user_id: str, customer_id: str) -> CustomerResponse:
        document = await self._require_customer(user_id=user_id, customer_id=customer_id)
        return CustomerResponse.model_validate(self._serialize_record(document))

    async def search_customers(
        self,
        *,
        user_id: str,
        full_name: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        national_id: str | None = None,
        tax_code: str | None = None,
        address: str | None = None,
    ) -> CustomerSearchResponse:
        criteria = {
            key: self._normalize_optional_text(value)
            for key, value in {
                "full_name": full_name,
                "phone": phone,
                "email": email,
                "national_id": national_id,
                "tax_code": tax_code,
                "address": address,
            }.items()
        }
        if not any(criteria.values()):
            raise LoanAgentValidationError("At least one customer search field is required.")

        query_fields = {
            "full_name": "full_name",
            "phone": "phone",
            "email": "email",
            "national_id": "national_id",
            "tax_code": "metadata.tax_code",
            "address": "address",
        }
        predicates = [
            {query_fields[key]: {"$regex": f"^{re.escape(value)}$", "$options": "i"}}
            for key, value in criteria.items()
            if value
        ]
        cursor = self._collection("loan_customers").find(
            {
                "user_id": self._normalize_user_id(user_id),
                "$or": predicates,
            }
        )
        documents = await cursor.to_list(length=50)

        def normalized(value: Any) -> str:
            return str(value or "").strip().casefold()

        matches: list[CustomerSearchMatch] = []
        for document in documents:
            metadata = document.get("metadata") or {}
            same_name = bool(criteria["full_name"]) and normalized(document.get("full_name")) == normalized(criteria["full_name"])
            same_address = bool(criteria["address"]) and normalized(document.get("address")) == normalized(criteria["address"])
            if (
                criteria["tax_code"]
                and normalized(metadata.get("tax_code")) == normalized(criteria["tax_code"])
            ) or (
                criteria["national_id"]
                and normalized(document.get("national_id")) == normalized(criteria["national_id"])
            ):
                score = 100
            elif criteria["phone"] and same_name and normalized(document.get("phone")) == normalized(criteria["phone"]):
                score = 90
            elif same_name and same_address:
                score = 80
            elif same_name:
                score = 50
            else:
                score = 0
            serialized = self._serialize_record(document)
            serialized["match_score"] = score
            matches.append(CustomerSearchMatch.model_validate(serialized))

        matches.sort(key=lambda item: (-item.match_score, item.id))
        return CustomerSearchResponse(matches=matches)

    async def update_customer(
        self,
        *,
        user_id: str,
        customer_id: str,
        payload: CustomerUpdateRequest,
    ) -> CustomerResponse:
        updates = payload.model_dump(mode="json", exclude_unset=True)
        updates = {key: value for key, value in updates.items() if value is not None}
        if not updates:
            raise LoanAgentValidationError("At least one customer field is required.")

        if "national_id" in updates:
            updates["national_id"] = self._normalize_identity(updates["national_id"])
        if (updates.get("metadata") or {}).get("tax_code"):
            updates["metadata"]["tax_code"] = self._normalize_identity(
                updates["metadata"]["tax_code"]
            )

        if "metadata" in updates:
            current = await self._require_customer(user_id=user_id, customer_id=customer_id)
            updates["metadata"] = {**(current.get("metadata") or {}), **updates["metadata"]}

        if "national_id" in updates or "metadata" in updates:
            current = await self._require_customer(user_id=user_id, customer_id=customer_id)
            await self._ensure_unique_customer_identity(
                user_id=user_id,
                national_id=updates.get("national_id", current.get("national_id")),
                tax_code=(updates.get("metadata") or current.get("metadata") or {}).get("tax_code"),
                exclude_customer_id=customer_id,
            )

        now = self._now()
        updates["updated_at"] = now
        customer_object_id = self._object_id(customer_id, label="customer_id")
        result = await self._collection("loan_customers").update_one(
            {"_id": customer_object_id, "user_id": self._normalize_user_id(user_id)},
            {"$set": updates},
        )
        if result.matched_count == 0:
            raise LoanAgentNotFoundError("Customer was not found.")

        return await self.get_customer(user_id=user_id, customer_id=customer_id)

    async def create_loan_profile(
        self,
        *,
        user_id: str,
        payload: LoanProfileCreateRequest,
    ) -> LoanProfileResponse:
        normalized_user_id = self._normalize_user_id(user_id)
        await self._require_customer(user_id=normalized_user_id, customer_id=payload.customer_id)

        now = self._now()
        document = {
            **payload.model_dump(mode="json", exclude_none=True),
            "user_id": normalized_user_id,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection("loan_profiles").insert_one(document)
        document["_id"] = result.inserted_id
        return LoanProfileResponse.model_validate(self._serialize_record(document))

    async def get_loan_profile(self, *, user_id: str, loan_profile_id: str) -> LoanProfileResponse:
        document = await self._require_loan_profile(
            user_id=user_id,
            loan_profile_id=loan_profile_id,
        )
        return LoanProfileResponse.model_validate(self._serialize_record(document))

    async def upload_legal_doc(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        file: UploadFile,
        doc_type: str | None,
        description: str | None,
    ) -> UploadedDocumentResponse:
        await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        upload = await self._save_uploaded_file(
            file,
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            category="legal_doc",
        )
        document = await self._insert_uploaded_document(
            collection_name="loan_legal_docs",
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            category="legal_doc",
            upload=upload,
            extra={
                "doc_type": self._normalize_optional_text(doc_type),
                "description": self._normalize_optional_text(description),
                "status": "uploaded",
            },
        )
        return UploadedDocumentResponse.model_validate(self._serialize_record(document))

    async def check_legal_docs(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        required_doc_types: list[str],
        notes: str | None = None,
    ):
        await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        required = [item.strip().lower() for item in required_doc_types if item.strip()]
        documents = await self._find_by_profile(
            "loan_legal_docs",
            user_id=user_id,
            loan_profile_id=loan_profile_id,
        )
        uploaded_types = {
            str(document.get("doc_type") or "").strip().lower()
            for document in documents
            if document.get("doc_type")
        }
        missing = [doc_type for doc_type in required if doc_type not in uploaded_types]
        issues = [
            {
                "code": "missing_legal_doc",
                "message": f"Missing required legal document type: {doc_type}.",
                "severity": "critical",
            }
            for doc_type in missing
        ]
        if not documents:
            issues.append(
                {
                    "code": "no_legal_docs",
                    "message": "No legal documents have been uploaded.",
                    "severity": "critical",
                }
            )

        status = "passed" if not issues else "failed"
        score = 100.0 if not required else round(((len(required) - len(missing)) / len(required)) * 100, 2)
        if not documents:
            score = 0.0
        recommendation = (
            "Legal documents are sufficient for the MVP review."
            if status == "passed"
            else "Request the missing legal documents before compliance review."
        )
        return await self._record_check(
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            check_type="legal_docs",
            status=status,
            score=score,
            issues=issues,
            recommendation=recommendation,
            notes=notes,
        )

    async def upload_financial_report(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        file: UploadFile,
        report_period: str | None,
        declared_revenue: float | None,
        declared_expense: float | None,
        declared_monthly_income: float | None,
    ) -> FinancialReportResponse:
        await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        upload = await self._save_uploaded_file(
            file,
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            category="financial_report",
        )
        document = await self._insert_uploaded_document(
            collection_name="loan_financial_reports",
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            category="financial_report",
            upload=upload,
            extra={
                "report_period": self._normalize_optional_text(report_period),
                "declared_revenue": declared_revenue,
                "declared_expense": declared_expense,
                "declared_monthly_income": declared_monthly_income,
                "status": "uploaded",
            },
        )
        return FinancialReportResponse.model_validate(self._serialize_record(document))

    async def upload_collateral(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        file: UploadFile,
        collateral_type: str | None,
        estimated_value: float | None,
        currency: str,
        description: str | None,
    ) -> CollateralResponse:
        await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        upload = await self._save_uploaded_file(
            file,
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            category="collateral",
        )
        document = await self._insert_uploaded_document(
            collection_name="loan_collaterals",
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            category="collateral",
            upload=upload,
            extra={
                "collateral_type": self._normalize_optional_text(collateral_type),
                "estimated_value": estimated_value,
                "currency": currency or "VND",
                "description": self._normalize_optional_text(description),
                "status": "uploaded",
            },
        )
        return CollateralResponse.model_validate(self._serialize_record(document))

    async def check_financials(self, *, user_id: str, loan_profile_id: str, notes: str | None = None):
        await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        reports = await self._find_by_profile(
            "loan_financial_reports",
            user_id=user_id,
            loan_profile_id=loan_profile_id,
        )
        issues: list[dict[str, Any]] = []
        if not reports:
            issues.append(
                {
                    "code": "no_financial_report",
                    "message": "No financial report has been uploaded.",
                    "severity": "critical",
                }
            )

        declared_income = self._latest_number(reports, "declared_monthly_income")
        if reports and declared_income is None:
            issues.append(
                {
                    "code": "missing_income",
                    "message": "Financial reports do not include declared monthly income.",
                    "severity": "warning",
                }
            )

        status = "passed" if not issues else "warning" if reports else "failed"
        score = 100.0 if status == "passed" else 70.0 if status == "warning" else 0.0
        recommendation = (
            "Financial information is ready for credit-rule checks."
            if status == "passed"
            else "Review or supplement financial information before final approval."
        )
        return await self._record_check(
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            check_type="financials",
            status=status,
            score=score,
            issues=issues,
            recommendation=recommendation,
            notes=notes,
        )

    async def check_collateral(self, *, user_id: str, loan_profile_id: str, notes: str | None = None):
        profile = await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        collaterals = await self._find_by_profile(
            "loan_collaterals",
            user_id=user_id,
            loan_profile_id=loan_profile_id,
        )
        total_value = sum(float(item.get("estimated_value") or 0) for item in collaterals)
        requested_amount = float(profile.get("loan_amount") or 0)
        issues: list[dict[str, Any]] = []
        if not collaterals:
            issues.append(
                {
                    "code": "no_collateral",
                    "message": "No collateral has been uploaded.",
                    "severity": "critical",
                }
            )
        elif requested_amount and total_value < requested_amount:
            issues.append(
                {
                    "code": "low_collateral_value",
                    "message": "Collateral value is lower than requested loan amount.",
                    "severity": "warning",
                }
            )

        status = "passed" if not issues else "warning" if collaterals else "failed"
        score = 0.0 if requested_amount <= 0 else min(round((total_value / requested_amount) * 100, 2), 100.0)
        recommendation = (
            "Collateral is sufficient for the MVP review."
            if status == "passed"
            else "Review collateral value or request additional collateral."
        )
        return await self._record_check(
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            check_type="collateral",
            status=status,
            score=score,
            issues=issues,
            recommendation=recommendation,
            notes=notes,
        )

    async def check_credit_rule(self, *, user_id: str, loan_profile_id: str, notes: str | None = None):
        profile = await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        legal_docs = await self._find_by_profile("loan_legal_docs", user_id=user_id, loan_profile_id=loan_profile_id)
        reports = await self._find_by_profile(
            "loan_financial_reports",
            user_id=user_id,
            loan_profile_id=loan_profile_id,
        )
        collaterals = await self._find_by_profile("loan_collaterals", user_id=user_id, loan_profile_id=loan_profile_id)

        issues: list[dict[str, Any]] = []
        if not legal_docs:
            issues.append({"code": "legal_docs_required", "message": "Legal documents are required.", "severity": "critical"})
        if not reports:
            issues.append({"code": "financials_required", "message": "Financial reports are required.", "severity": "critical"})
        if not collaterals:
            issues.append({"code": "collateral_required", "message": "Collateral is required.", "severity": "warning"})
        if int(profile.get("term_months") or 0) > 360:
            issues.append({"code": "term_too_long", "message": "Loan term exceeds 360 months.", "severity": "critical"})

        critical_count = sum(1 for issue in issues if issue["severity"] == "critical")
        status = "passed" if not issues else "failed" if critical_count else "warning"
        score = max(0.0, 100.0 - critical_count * 30.0 - (len(issues) - critical_count) * 15.0)
        recommendation = (
            "Credit-rule checklist passed."
            if status == "passed"
            else "Resolve credit-rule issues before approval."
        )
        return await self._record_check(
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            check_type="credit_rule",
            status=status,
            score=score,
            issues=issues,
            recommendation=recommendation,
            notes=notes,
        )

    async def save_compliance_result(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        payload: ComplianceResultRequest,
    ) -> ComplianceResultResponse:
        await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        now = self._now()
        document = {
            **payload.model_dump(mode="json", exclude_none=True),
            "user_id": self._normalize_user_id(user_id),
            "loan_profile_id": loan_profile_id,
            "created_at": now,
        }
        result = await self._collection("loan_compliance_results").insert_one(document)
        document["_id"] = result.inserted_id
        await self._collection("loan_profiles").update_one(
            {"_id": self._object_id(loan_profile_id, label="loan_profile_id")},
            {
                "$set": {
                    "status": "compliance_completed",
                    "compliance_decision": payload.decision,
                    "updated_at": now,
                }
            },
        )
        return ComplianceResultResponse.model_validate(self._serialize_record(document))

    async def update_case_status(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        payload: CaseStatusUpdateRequest,
    ) -> CaseStatusResponse:
        await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        now = self._now()
        result = await self._collection("loan_profiles").update_one(
            {
                "_id": self._object_id(loan_profile_id, label="loan_profile_id"),
                "user_id": self._normalize_user_id(user_id),
            },
            {
                "$set": {
                    "status": payload.status,
                    "status_notes": payload.notes,
                    "updated_at": now,
                }
            },
        )
        if result.matched_count == 0:
            raise LoanAgentNotFoundError("Loan profile was not found.")
        return CaseStatusResponse(
            loan_profile_id=loan_profile_id,
            status=payload.status,
            notes=payload.notes,
            updated_at=now,
        )

    async def create_checklist(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        payload: ChecklistCreateRequest,
    ) -> ChecklistResponse:
        await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        now = self._now()
        source_items = payload.items or [
            {**item, "status": "pending"}
            for item in self.DEFAULT_CHECKLIST_ITEMS
        ]
        items = [
            {
                "id": uuid.uuid4().hex,
                **(item.model_dump(mode="json") if hasattr(item, "model_dump") else item),
            }
            for item in source_items
        ]
        document = {
            "user_id": self._normalize_user_id(user_id),
            "loan_profile_id": loan_profile_id,
            "items": items,
            "status": "open",
            "notes": payload.notes,
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection("loan_checklists").insert_one(document)
        document["_id"] = result.inserted_id
        return ChecklistResponse.model_validate(self._serialize_record(document))

    async def calculate_loan_limit(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        payload: LoanLimitCalculationRequest,
    ) -> LoanLimitCalculationResponse:
        profile = await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        requested_amount = float(profile.get("loan_amount") or 0.0)
        capital_need_limit = payload.total_capital_need * 0.8
        collateral_limit = payload.collateral_value * payload.ltv_ratio
        calculated_limit = min(requested_amount, capital_need_limit, collateral_limit)
        dscr_factor = 1.0 if payload.dscr >= 1.3 else 0.9 if payload.dscr >= 1.1 else 0.7 if payload.dscr >= 1.0 else 0.0
        checklist_factor = 1.0 if payload.checklist_score >= 90 else 0.9 if payload.checklist_score >= 75 else 0.7 if payload.checklist_score >= 50 else 0.0
        final_factor = 0.0 if payload.hard_stop else min(dscr_factor, checklist_factor)
        recommended_limit = calculated_limit * final_factor
        now = self._now()
        document = {
            "user_id": self._normalize_user_id(user_id),
            "loan_profile_id": loan_profile_id,
            "requested_amount": requested_amount,
            "capital_need_limit": round(capital_need_limit, 2),
            "collateral_limit": round(collateral_limit, 2),
            "calculated_limit": round(calculated_limit, 2),
            "dscr_factor": dscr_factor,
            "checklist_factor": checklist_factor,
            "final_factor": final_factor,
            "recommended_limit": round(recommended_limit, 2),
            "currency": profile.get("currency") or "VND",
            "assumptions": {
                **payload.model_dump(mode="json"),
            },
            "created_at": now,
        }
        result = await self._collection("loan_limit_calculations").insert_one(document)
        document["_id"] = result.inserted_id
        return LoanLimitCalculationResponse.model_validate(self._serialize_record(document))

    async def create_task(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        payload: TaskCreateRequest,
    ) -> TaskResponse:
        await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        now = self._now()
        document = {
            **payload.model_dump(mode="json", exclude_none=True),
            "user_id": self._normalize_user_id(user_id),
            "loan_profile_id": loan_profile_id,
            "status": "open",
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection("loan_tasks").insert_one(document)
        document["_id"] = result.inserted_id
        return TaskResponse.model_validate(self._serialize_record(document))

    async def create_report(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        payload: ReportCreateRequest,
    ) -> ReportResponse:
        profile = await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        customer = await self._require_customer(user_id=user_id, customer_id=str(profile["customer_id"]))
        now = self._now()
        report_body = await self._build_report_body(
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            profile=profile,
            customer=customer,
        )
        title = payload.title or f"Loan case report for {customer.get('full_name')}"
        summary = payload.summary or self._build_report_summary(profile, report_body)
        document = {
            "user_id": self._normalize_user_id(user_id),
            "loan_profile_id": loan_profile_id,
            "report_type": payload.report_type,
            "title": title,
            "summary": summary,
            "report_body": report_body,
            "created_at": now,
        }
        result = await self._collection("loan_reports").insert_one(document)
        document["_id"] = result.inserted_id
        return ReportResponse.model_validate(self._serialize_record(document))

    async def list_reports(self, *, user_id: str, loan_profile_id: str) -> ReportsListResponse:
        await self._require_loan_profile(user_id=user_id, loan_profile_id=loan_profile_id)
        documents = await self._find_by_profile(
            "loan_reports",
            user_id=user_id,
            loan_profile_id=loan_profile_id,
            sort_desc=True,
        )
        reports = [
            ReportResponse.model_validate(self._serialize_record(document))
            for document in documents
        ]
        return ReportsListResponse(total_count=len(reports), reports=reports)

    async def route_dossier_bundle(
        self,
        *,
        user_id: str,
        files: list[UploadFile],
    ) -> DossierRoutingResponse:
        normalized_user_id = self._normalize_user_id(user_id)
        upload_files = [file for file in files or [] if file is not None]
        if not upload_files:
            raise LoanAgentValidationError("Chưa chọn bộ hồ sơ để nạp.")
        if len(upload_files) > DOSSIER_MAX_FILES:
            raise LoanAgentValidationError(
                f"Bộ hồ sơ chỉ được chứa tối đa {DOSSIER_MAX_FILES} file."
            )

        uploaded_names = [self._uploaded_file_name(file) for file in upload_files]
        uploaded_extensions = [Path(file_name).suffix.lower() for file_name in uploaded_names]
        unsupported_extensions = [
            uploaded_name
            for uploaded_name, extension in zip(uploaded_names, uploaded_extensions, strict=True)
            if extension not in {".pdf", ".zip"}
        ]
        if unsupported_extensions:
            raise LoanAgentValidationError(
                "Chỉ hỗ trợ một file ZIP chứa PDF hoặc các file PDF. "
                f"File không hợp lệ: {', '.join(unsupported_extensions)}."
            )

        zip_count = sum(1 for extension in uploaded_extensions if extension == ".zip")
        if zip_count and len(upload_files) > 1:
            raise LoanAgentValidationError(
                "Chỉ chọn một file ZIP hoặc chọn nhiều file PDF. Không trộn ZIP với PDF."
            )
        if zip_count > 1:
            raise LoanAgentValidationError("Mỗi lần chỉ được gửi một file ZIP.")

        dossier_id = self._new_dossier_id()
        dossier_dir = self._dossier_upload_dir(normalized_user_id, dossier_id)
        files_dir = dossier_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        accepted_files: list[dict[str, Any]] = []
        ignored_files: list[dict[str, Any]] = []
        if zip_count:
            await self._ingest_dossier_zip(
                upload_files[0],
                files_dir=files_dir,
                accepted_files=accepted_files,
                ignored_files=ignored_files,
            )
        else:
            for file in upload_files:
                await self._ingest_direct_dossier_file(
                    file,
                    files_dir=files_dir,
                    accepted_files=accepted_files,
                    ignored_files=ignored_files,
                )
                if self._accepted_dossier_size(accepted_files) > DOSSIER_MAX_UPLOAD_BYTES:
                    raise LoanAgentValidationError("Tổng dung lượng bộ hồ sơ vượt giới hạn cho phép.")

        if not accepted_files:
            raise LoanAgentValidationError("Không tìm thấy file PDF hợp lệ trong bộ hồ sơ.")

        routed_files, agent_packages, needs_review_files, routing_trace = self._build_dossier_routing(
            accepted_files
        )
        now = self._now()
        routing_status = "needs_review" if needs_review_files else "ready_to_dispatch"
        dispatch_message = (
            "Planner đã phân loại xong; có thể gửi tham chiếu file cho các agent chuyên gia."
            if routing_status == "ready_to_dispatch"
            else "Planner tạm giữ điều phối vì có file cần kiểm tra tuyến xử lý."
        )
        document = {
            "user_id": normalized_user_id,
            "dossier_id": dossier_id,
            "routing_status": routing_status,
            "dispatch_message": dispatch_message,
            "received_files_count": len(accepted_files) + len(ignored_files),
            "accepted_files_count": len(accepted_files),
            "ignored_files_count": len(ignored_files),
            "needs_review_count": len(needs_review_files),
            "document_registry": routed_files,
            "agent_packages": agent_packages,
            "needs_review_files": needs_review_files,
            "ignored_files": ignored_files,
            "routing_trace": routing_trace,
            "created_at": now,
            "updated_at": now,
        }
        result = await self._collection("loan_dossier_bundles").insert_one(document)
        document["_id"] = result.inserted_id
        return DossierRoutingResponse.model_validate(self._serialize_record(document))

    async def get_dossier_routing(self, *, user_id: str, dossier_id: str) -> DossierRoutingResponse:
        normalized_dossier_id = self._normalize_optional_text(dossier_id)
        if not normalized_dossier_id:
            raise LoanAgentValidationError("dossier_id is required.")

        document = await self._collection("loan_dossier_bundles").find_one(
            {
                "user_id": self._normalize_user_id(user_id),
                "dossier_id": normalized_dossier_id,
            }
        )
        if not document:
            raise LoanAgentNotFoundError("Dossier routing was not found.")
        return DossierRoutingResponse.model_validate(self._serialize_record(document))

    async def dispatch_dossier_bundle(
        self,
        *,
        user_id: str,
        dossier_id: str,
        idempotency_key: str | None = None,
    ) -> DossierDispatchResponse:
        normalized_user_id = self._normalize_user_id(user_id)
        normalized_dossier_id = self._normalize_optional_text(dossier_id)
        normalized_idempotency_key = self._normalize_idempotency_key(idempotency_key)
        if not normalized_dossier_id:
            raise LoanAgentValidationError("dossier_id is required.")

        collection = self._collection("loan_dossier_bundles")
        document = await collection.find_one(
            {
                "user_id": normalized_user_id,
                "dossier_id": normalized_dossier_id,
            }
        )
        if not document:
            raise LoanAgentNotFoundError("Dossier routing was not found.")

        if normalized_idempotency_key:
            existing_dispatch = self._find_dossier_dispatch_by_idempotency_key(
                document,
                normalized_idempotency_key,
            )
            if existing_dispatch:
                return self._build_dossier_dispatch_response(document, existing_dispatch)

        now = self._now()
        routing_batch_id = self._new_routing_batch_id()
        if int(document.get("needs_review_count") or 0) > 0:
            routing_status = "blocked_needs_review"
            agent_dispatches = self._blocked_dossier_agent_dispatches(
                document=document,
                routing_batch_id=routing_batch_id,
                created_at=now,
            )
            message = "Tạm dừng gửi hồ sơ vì vẫn còn file cần kiểm tra tuyến xử lý."
        else:
            agent_dispatches = []
            for package in self._normalized_dossier_agent_packages(document):
                payload = self._build_dossier_agent_dispatch_payload(
                    dossier_id=normalized_dossier_id,
                    routing_batch_id=routing_batch_id,
                    package=package,
                    created_at=now,
                )
                if int(package.get("file_count") or 0) == 0:
                    agent_dispatches.append(
                        DossierAgentDispatchResult(
                            agent_name=package["agent_name"],
                            status="skipped_no_files",
                            file_count=0,
                            routing_batch_id=routing_batch_id,
                            dispatched_at=None,
                            message="Không có file nào được route tới agent này.",
                            payload=payload,
                        ).model_dump(mode="json")
                    )
                    continue

                try:
                    await self._send_dossier_agent_payload(payload)
                    agent_dispatches.append(
                        DossierAgentDispatchResult(
                            agent_name=package["agent_name"],
                            status="sent",
                            file_count=package["file_count"],
                            routing_batch_id=routing_batch_id,
                            dispatched_at=now,
                            message="Đã gửi tham chiếu file tới hàng đợi của agent chuyên gia.",
                            payload=payload,
                        ).model_dump(mode="json")
                    )
                except Exception as exc:
                    agent_dispatches.append(
                        DossierAgentDispatchResult(
                            agent_name=package["agent_name"],
                            status="failed",
                            file_count=package["file_count"],
                            routing_batch_id=routing_batch_id,
                            dispatched_at=None,
                            message=f"Gửi hồ sơ thất bại: {exc.__class__.__name__}.",
                            payload=payload,
                        ).model_dump(mode="json")
                    )

            routing_status = self._dossier_dispatch_status(agent_dispatches)
            message = self._dossier_dispatch_message(routing_status)

        latest_dispatch = DossierDispatchSnapshot(
            routing_batch_id=routing_batch_id,
            idempotency_key=normalized_idempotency_key,
            routing_status=routing_status,
            message=message,
            agent_dispatches=agent_dispatches,
            created_at=now,
            updated_at=now,
        ).model_dump(mode="json")
        dispatch_trace = self._build_dossier_dispatch_trace(
            document=document,
            routing_batch_id=routing_batch_id,
            routing_status=routing_status,
            agent_dispatches=agent_dispatches,
        )
        previous_dispatch_runs = list(document.get("dispatch_runs") or [])
        previous_routing_trace = list(document.get("routing_trace") or [])

        update_result = await collection.update_one(
            {
                "user_id": normalized_user_id,
                "dossier_id": normalized_dossier_id,
            },
            {
                "$set": {
                    "routing_status": routing_status,
                    "routing_batch_id": routing_batch_id,
                    "dispatch_message": message,
                    "latest_dispatch": latest_dispatch,
                    "updated_at": now,
                },
                "$push": {
                    "dispatch_runs": latest_dispatch,
                    "routing_trace": {"$each": dispatch_trace},
                },
            },
        )
        if update_result.matched_count == 0:
            raise LoanAgentNotFoundError("Dossier routing was not found.")

        document["routing_status"] = routing_status
        document["routing_batch_id"] = routing_batch_id
        document["dispatch_message"] = message
        document["latest_dispatch"] = latest_dispatch
        document["updated_at"] = now
        document["dispatch_runs"] = [*previous_dispatch_runs, latest_dispatch]
        document["routing_trace"] = [*previous_routing_trace, *dispatch_trace]
        return self._build_dossier_dispatch_response(document, latest_dispatch)

    async def _insert_uploaded_document(
        self,
        *,
        collection_name: str,
        user_id: str,
        loan_profile_id: str,
        category: str,
        upload: dict[str, Any],
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        now = self._now()
        document = {
            **upload,
            **extra,
            "user_id": self._normalize_user_id(user_id),
            "loan_profile_id": loan_profile_id,
            "category": category,
            "created_at": now,
        }
        result = await self._collection(collection_name).insert_one(document)
        document["_id"] = result.inserted_id
        return document

    async def _ingest_direct_dossier_file(
        self,
        file: UploadFile,
        *,
        files_dir: Path,
        accepted_files: list[dict[str, Any]],
        ignored_files: list[dict[str, Any]],
    ) -> None:
        file_name = self._uploaded_file_name(file)
        extension = Path(file_name).suffix.lower()
        if len(file_name) > 255:
            await file.close()
            raise LoanAgentValidationError("Tên file tải lên quá dài.")
        if extension not in DOSSIER_DIRECT_UPLOAD_EXTENSIONS:
            await file.close()
            raise LoanAgentValidationError("Chỉ hỗ trợ file PDF khi gửi nhiều file trực tiếp.")
        if not self._is_allowed_upload_content_type(
            file.content_type,
            allowed={"application/pdf", "application/octet-stream", "binary/octet-stream"},
        ):
            await file.close()
            raise LoanAgentValidationError("File PDF không đúng định dạng được hỗ trợ.")

        try:
            content = await self._read_upload_file_limited(
                file,
                limit_bytes=DOSSIER_MAX_SINGLE_FILE_BYTES,
                label=file_name,
            )
        except LoanAgentValidationError as exc:
            ignored_files.append(
                self._ignored_dossier_file(
                    source_path=file_name,
                    original_filename=file_name,
                    file_type=extension.lstrip(".") or None,
                    reason=str(exc),
                )
            )
            return

        self._store_dossier_file(
            files_dir=files_dir,
            accepted_files=accepted_files,
            source_path=file_name,
            original_filename=file_name,
            file_type=extension.lstrip("."),
            content_type=file.content_type,
            content=content,
        )

    async def _ingest_dossier_zip(
        self,
        file: UploadFile,
        *,
        files_dir: Path,
        accepted_files: list[dict[str, Any]],
        ignored_files: list[dict[str, Any]],
    ) -> None:
        file_name = self._uploaded_file_name(file)
        extension = Path(file_name).suffix.lower()
        if len(file_name) > 255:
            raise LoanAgentValidationError("Tên file ZIP tải lên quá dài.")
        if extension != ".zip":
            raise LoanAgentValidationError("File bộ hồ sơ phải là ZIP.")
        if not self._is_allowed_upload_content_type(
            file.content_type,
            allowed={
                "application/zip",
                "application/x-zip-compressed",
                "application/octet-stream",
                "binary/octet-stream",
            },
        ):
            raise LoanAgentValidationError("File ZIP không đúng định dạng được hỗ trợ.")

        zip_content = await self._read_upload_file_limited(
            file,
            limit_bytes=DOSSIER_MAX_UPLOAD_BYTES,
            label=file_name,
        )
        try:
            archive = zipfile.ZipFile(io.BytesIO(zip_content))
        except zipfile.BadZipFile as exc:
            raise LoanAgentValidationError("File ZIP không hợp lệ hoặc không thể giải nén.") from exc

        with archive:
            file_infos = [info for info in archive.infolist() if not info.is_dir()]
            if len(file_infos) > DOSSIER_MAX_FILES:
                raise LoanAgentValidationError(
                    f"File ZIP chỉ được chứa tối đa {DOSSIER_MAX_FILES} file."
                )

            total_uncompressed_bytes = 0
            for info in file_infos:
                source_path = self._normalize_zip_source_path(info.filename)
                original_filename = PurePosixPath(source_path).name
                if not self._is_safe_zip_path(source_path):
                    raise LoanAgentValidationError("File ZIP có đường dẫn không an toàn.")
                if len(original_filename) > 255:
                    raise LoanAgentValidationError("File ZIP có tên file bên trong quá dài.")
                if self._is_ignored_zip_path(source_path):
                    ignored_files.append(
                        self._ignored_dossier_file(
                            source_path=source_path,
                            original_filename=original_filename,
                            file_type=Path(source_path).suffix.lower().lstrip(".") or None,
                            reason="File hệ thống hoặc file tạm đã được bỏ qua.",
                        )
                    )
                    continue

                extension = Path(source_path).suffix.lower()
                if extension not in DOSSIER_ZIP_MEMBER_EXTENSIONS:
                    raise LoanAgentValidationError(
                        "File ZIP chỉ được chứa PDF. "
                        f"File không hợp lệ bên trong ZIP: {source_path}."
                    )

                if not self._is_allowed_dossier_metadata(source_path, extension):
                    raise LoanAgentValidationError(
                        "File ZIP chỉ được chứa PDF. "
                        f"File không hợp lệ bên trong ZIP: {source_path}."
                    )

                if info.file_size <= 0:
                    ignored_files.append(
                        self._ignored_dossier_file(
                            source_path=source_path,
                            original_filename=original_filename,
                            file_type=extension.lstrip(".") or None,
                            reason="File is empty.",
                        )
                    )
                    continue

                total_uncompressed_bytes += info.file_size
                if total_uncompressed_bytes > DOSSIER_MAX_UPLOAD_BYTES:
                    raise LoanAgentValidationError("Tổng dung lượng giải nén của ZIP vượt giới hạn cho phép.")

                try:
                    content = self._read_zip_member_limited(
                        archive,
                        info,
                        limit_bytes=DOSSIER_MAX_SINGLE_FILE_BYTES,
                    )
                except LoanAgentValidationError as exc:
                    ignored_files.append(
                        self._ignored_dossier_file(
                            source_path=source_path,
                            original_filename=original_filename,
                            file_type=extension.lstrip(".") or None,
                            reason=str(exc),
                        )
                    )
                    continue

                if extension == ".json" and not self._is_valid_json_metadata(content):
                    ignored_files.append(
                        self._ignored_dossier_file(
                            source_path=source_path,
                            original_filename=original_filename,
                            file_type=extension.lstrip(".") or None,
                            reason="Invalid JSON metadata file inside ZIP.",
                        )
                    )
                    continue

                self._store_dossier_file(
                    files_dir=files_dir,
                    accepted_files=accepted_files,
                    source_path=source_path,
                    original_filename=original_filename,
                    file_type=extension.lstrip("."),
                    content_type=self._content_type_for_extension(extension),
                    content=content,
                )

    def _build_dossier_routing(
        self,
        records: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        metadata = self._load_dossier_metadata(records)
        routing_trace: list[dict[str, Any]] = list(metadata.get("warnings") or [])

        for record in records:
            classification = self._classify_dossier_record(record, metadata)
            record.update(classification)
            record["status"] = "needs_review" if classification["needs_review"] else "classified"
            routing_trace.append(
                DossierRoutingTraceEntry(
                    file_id=record["file_id"],
                    source_path=record["source_path"],
                    stage="planner_routing",
                    decision="needs_review" if record["needs_review"] else "classified",
                    reason=record["reason"] or "Planner routing completed.",
                    confidence=record["confidence"],
                ).model_dump(mode="json")
            )

        agent_packages = self._build_dossier_agent_packages(records)
        needs_review_files = [
            DossierDocumentRecord.model_validate(record).model_dump(mode="json")
            for record in records
            if record.get("needs_review")
        ]
        routed_records = [
            DossierDocumentRecord.model_validate(record).model_dump(mode="json")
            for record in records
        ]
        return routed_records, agent_packages, needs_review_files, routing_trace

    def _build_dossier_agent_packages(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        packages: list[dict[str, Any]] = []
        package_reasons = {
            "credit": "File được gửi cho Agent Credit để kiểm tra nhận diện khách hàng, pháp lý và đề nghị cấp tín dụng.",
            "compliance": "File được gửi cho Agent Compliance để kiểm tra tài chính, phương án trả nợ, tài sản bảo đảm và chính sách.",
            "operations": "File được gửi cho Agent Operations để kiểm tra checklist, trạng thái hồ sơ và các bước vận hành tiếp theo.",
        }
        for agent_name in DOSSIER_AGENT_NAMES:
            files = [
                DossierAgentFile(
                    file_id=record["file_id"],
                    file_ref=record["file_ref"],
                    original_filename=record["original_filename"],
                    source_path=record["source_path"],
                    detected_document_type=record.get("detected_document_type"),
                    business_group=record.get("business_group"),
                    confidence=record.get("confidence") or 0,
                    needs_agent_confirm=bool(record.get("needs_agent_confirm")),
                    reason=record.get("reason"),
                ).model_dump(mode="json")
                for record in records
                if agent_name in (record.get("target_agents") or []) and not record.get("needs_review")
            ]
            packages.append(
                DossierAgentPackage(
                    agent_name=agent_name,
                    file_count=len(files),
                    package_reason=package_reasons[agent_name],
                    files=files,
                ).model_dump(mode="json")
            )
        return packages

    def _normalized_dossier_agent_packages(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        packages_by_agent = {
            str(package.get("agent_name")): DossierAgentPackage.model_validate(package).model_dump(mode="json")
            for package in document.get("agent_packages") or []
            if package.get("agent_name") in DOSSIER_AGENT_NAMES
        }
        for agent_name in DOSSIER_AGENT_NAMES:
            packages_by_agent.setdefault(
                agent_name,
                DossierAgentPackage(
                    agent_name=agent_name,
                    file_count=0,
                    package_reason=f"Không có file nào được route tới Agent {agent_name.title()}.",
                    files=[],
                ).model_dump(mode="json"),
            )
        return [packages_by_agent[agent_name] for agent_name in DOSSIER_AGENT_NAMES]

    def _build_dossier_agent_dispatch_payload(
        self,
        *,
        dossier_id: str,
        routing_batch_id: str,
        package: dict[str, Any],
        created_at: datetime,
    ) -> dict[str, Any]:
        payload = DossierAgentDispatchPayload(
            dossier_id=dossier_id,
            routing_batch_id=routing_batch_id,
            agent_name=package["agent_name"],
            file_count=package["file_count"],
            package_reason=package["package_reason"],
            files=package.get("files") or [],
            scope_note=list(DOSSIER_DISPATCH_SCOPE_NOTE),
            created_at=created_at,
        )
        return payload.model_dump(mode="json")

    def _blocked_dossier_agent_dispatches(
        self,
        *,
        document: dict[str, Any],
        routing_batch_id: str,
        created_at: datetime,
    ) -> list[dict[str, Any]]:
        dispatches: list[dict[str, Any]] = []
        for package in self._normalized_dossier_agent_packages(document):
            payload = self._build_dossier_agent_dispatch_payload(
                dossier_id=document["dossier_id"],
                routing_batch_id=routing_batch_id,
                package=package,
                created_at=created_at,
            )
            dispatches.append(
                DossierAgentDispatchResult(
                    agent_name=package["agent_name"],
                    status="blocked_needs_review",
                    file_count=package["file_count"],
                    routing_batch_id=routing_batch_id,
                    dispatched_at=None,
                    message="Chưa gửi package vì bộ hồ sơ còn file ở trạng thái needs_review.",
                    payload=payload,
                ).model_dump(mode="json")
            )
        return dispatches

    @staticmethod
    def _dossier_dispatch_status(agent_dispatches: list[dict[str, Any]]) -> str:
        sent_count = sum(1 for dispatch in agent_dispatches if dispatch.get("status") == "sent")
        failed_count = sum(1 for dispatch in agent_dispatches if dispatch.get("status") == "failed")
        if failed_count and sent_count:
            return "partial_dispatch_failed"
        if failed_count:
            return "dispatch_failed"
        return "dispatched"

    @staticmethod
    def _dossier_dispatch_message(routing_status: str) -> str:
        if routing_status == "dispatched":
            return "Planner đã gửi tham chiếu file cho tất cả agent có file được route."
        if routing_status == "partial_dispatch_failed":
            return "Planner đã gửi được một phần package, nhưng có ít nhất một agent gửi thất bại."
        if routing_status == "dispatch_failed":
            return "Planner chưa gửi được package nào có file được route."
        if routing_status == "blocked_needs_review":
            return "Planner tạm giữ điều phối vì có file cần kiểm tra tuyến xử lý."
        return "Planner đã hoàn tất điều phối."

    def _build_dossier_dispatch_trace(
        self,
        *,
        document: dict[str, Any],
        routing_batch_id: str,
        routing_status: str,
        agent_dispatches: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        trace_entries: list[dict[str, Any]] = [
            DossierRoutingTraceEntry(
                file_id=None,
                source_path=f"dossier:{document['dossier_id']}",
                stage="planner_dispatch",
                decision=routing_status,
                reason=f"routing_batch_id={routing_batch_id}; needs_review_count={document.get('needs_review_count', 0)}.",
                confidence=None,
            ).model_dump(mode="json")
        ]

        for dispatch in agent_dispatches:
            trace_entries.append(
                DossierRoutingTraceEntry(
                    file_id=None,
                    source_path=f"agent:{dispatch['agent_name']}",
                    stage="planner_dispatch",
                    decision=dispatch["status"],
                    reason=f"{dispatch['message']} file_count={dispatch['file_count']}.",
                    confidence=None,
                ).model_dump(mode="json")
            )

        multi_agent_files = self._multi_agent_dossier_file_ids(document)
        if multi_agent_files:
            trace_entries.append(
                DossierRoutingTraceEntry(
                    file_id=None,
                    source_path=f"dossier:{document['dossier_id']}",
                    stage="planner_dispatch",
                    decision="multi_agent_files",
                    reason=f"Files routed to multiple agents: {', '.join(multi_agent_files)}.",
                    confidence=None,
                ).model_dump(mode="json")
            )
        return trace_entries

    @staticmethod
    def _multi_agent_dossier_file_ids(document: dict[str, Any]) -> list[str]:
        agent_count_by_file_id: dict[str, int] = {}
        for package in document.get("agent_packages") or []:
            for file_record in package.get("files") or []:
                file_id = file_record.get("file_id")
                if file_id:
                    agent_count_by_file_id[file_id] = agent_count_by_file_id.get(file_id, 0) + 1
        return sorted(file_id for file_id, count in agent_count_by_file_id.items() if count > 1)

    @staticmethod
    def _find_dossier_dispatch_by_idempotency_key(
        document: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        for dispatch in document.get("dispatch_runs") or []:
            if dispatch.get("idempotency_key") == idempotency_key:
                return dispatch
        latest_dispatch = document.get("latest_dispatch") or {}
        if latest_dispatch.get("idempotency_key") == idempotency_key:
            return latest_dispatch
        return None

    def _build_dossier_dispatch_response(
        self,
        document: dict[str, Any],
        dispatch: dict[str, Any],
    ) -> DossierDispatchResponse:
        serialized = self._serialize_record(document)
        return DossierDispatchResponse.model_validate(
            {
                "id": serialized.get("id"),
                "dossier_id": serialized["dossier_id"],
                "routing_status": dispatch["routing_status"],
                "routing_batch_id": dispatch["routing_batch_id"],
                "message": dispatch["message"],
                "agent_dispatches": dispatch.get("agent_dispatches") or [],
                "agent_packages": serialized.get("agent_packages") or [],
                "needs_review_count": serialized.get("needs_review_count") or 0,
                "needs_review_files": serialized.get("needs_review_files") or [],
                "ignored_files_count": serialized.get("ignored_files_count") or 0,
                "ignored_files": serialized.get("ignored_files") or [],
                "routing_trace": serialized.get("routing_trace") or [],
                "created_at": serialized["created_at"],
                "updated_at": serialized["updated_at"],
            }
        )

    @staticmethod
    async def _send_dossier_agent_payload(payload: dict[str, Any]) -> None:
        return None

    def _classify_dossier_record(
        self,
        record: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if metadata_classification := self._classify_metadata_file(record):
            return metadata_classification

        if checklist_classification := self._classify_from_checklist(record, metadata):
            return checklist_classification

        search_text = self._normalized_search_text(record["source_path"], record["original_filename"])
        folder_rule = self._match_folder_rule(record["source_path"])
        filename_rule = self._match_keyword_rule(search_text)
        if filename_rule:
            source = "folder+filename" if folder_rule else "filename"
            confidence = 0.9 if folder_rule else 0.86
            rule_reason = filename_rule.pop("reason")
            return self._classification_payload(
                **filename_rule,
                confidence=confidence,
                classification_source=source,
                reason=f"Matched dossier filename rule: {rule_reason}",
            )
        if folder_rule:
            rule_reason = folder_rule.pop("reason")
            return self._classification_payload(
                **folder_rule,
                confidence=0.72,
                classification_source="folder",
                reason=f"Matched dossier folder rule: {rule_reason}",
            )

        if record["file_type"] == "pdf":
            first_page_text = self._extract_first_page_text(record["file_ref"])
            if first_page_text:
                first_page_rule = self._match_keyword_rule(self._normalized_search_text(first_page_text))
                if first_page_rule:
                    rule_reason = first_page_rule.pop("reason")
                    return self._classification_payload(
                        **first_page_rule,
                        confidence=0.67,
                        classification_source="first_page_text",
                        reason=f"Matched first-page text rule: {rule_reason}",
                    )

        return self._classification_payload(
            detected_document_type="unknown",
            business_group="unknown",
            target_agents=[],
            confidence=0,
            classification_source="none",
            reason="No confident manifest, checklist, folder, filename, or first-page text match.",
        )

    def _classify_metadata_file(self, record: dict[str, Any]) -> dict[str, Any] | None:
        file_name = record["original_filename"].casefold()
        if record["file_type"] == "csv" and file_name == "manifest.csv":
            return self._classification_payload(
                detected_document_type="planner_manifest",
                business_group="planner_metadata",
                target_agents=[],
                confidence=0.95,
                classification_source="metadata_filename",
                reason="Manifest supports dossier intake and is kept for Planner trace only.",
            )
        if record["file_type"] == "csv" and file_name == "document_checklist.csv":
            return self._classification_payload(
                detected_document_type="document_checklist",
                business_group="operations_checklist",
                target_agents=["operations"],
                confidence=0.95,
                classification_source="metadata_filename",
                reason="Document checklist is routed to Operations Agent and used by Planner.",
            )
        if record["file_type"] != "json":
            return None

        metadata_targets = {
            "credit_agent_input": ("credit_agent_input", "credit_metadata", ["credit"]),
            "compliance_agent_input": ("compliance_agent_input", "compliance_metadata", ["compliance"]),
            "operations_agent_input": ("operations_agent_input", "operations_metadata", ["operations"]),
            "customer_master": ("customer_master", "customer_metadata", ["credit"]),
        }
        normalized_name = self._normalized_search_text(file_name)
        for marker, (document_type, business_group, target_agents) in metadata_targets.items():
            if self._normalized_search_text(marker) in normalized_name:
                return self._classification_payload(
                    detected_document_type=document_type,
                    business_group=business_group,
                    target_agents=target_agents,
                    confidence=0.95,
                    classification_source="metadata_filename",
                    reason=f"Metadata file is intended for {', '.join(target_agents).title()} Agent.",
                )
        return self._classification_payload(
            detected_document_type="planner_metadata",
            business_group="planner_metadata",
            target_agents=[],
            confidence=0.7,
            classification_source="metadata_filename",
            reason="JSON metadata is kept with Planner but is not routed to a specialist.",
        )

    def _classify_from_checklist(
        self,
        record: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        checklist_by_doc_id = metadata.get("checklist_by_doc_id") or {}
        checklist_rows = metadata.get("checklist_rows") or []
        doc_id = self._document_id_from_source_path(record["source_path"])
        checklist_row = checklist_by_doc_id.get(doc_id) if doc_id else None
        search_text = self._normalized_search_text(record["source_path"], record["original_filename"])

        if not checklist_row:
            for row in checklist_rows:
                document_name = self._normalized_search_text(row.get("document_name"))
                tokens = [token for token in document_name.split() if len(token) >= 3]
                if document_name and document_name in search_text:
                    checklist_row = row
                    break
                if tokens and sum(1 for token in tokens if token in search_text) >= min(2, len(tokens)):
                    checklist_row = row
                    break

        if not checklist_row:
            return None

        target_agents = self._normalize_agent_names(checklist_row.get("primary_agent"))
        return self._classification_payload(
            detected_document_type=self._slugify_document_type(checklist_row.get("document_name") or "checklist_document"),
            business_group=self._business_group_from_checklist(checklist_row.get("group")),
            target_agents=target_agents,
            confidence=0.96,
            classification_source="document_checklist",
            reason=f"Matched document_checklist.csv row {checklist_row.get('document_id')}.",
        )

    def _classification_payload(
        self,
        *,
        detected_document_type: str,
        business_group: str,
        target_agents: list[str],
        confidence: float,
        classification_source: str,
        reason: str,
    ) -> dict[str, Any]:
        normalized_agents = [agent for agent in target_agents if agent in DOSSIER_AGENT_NAMES]
        needs_review = confidence < 0.6 and bool(normalized_agents or detected_document_type == "unknown")
        return {
            "detected_document_type": detected_document_type,
            "business_group": business_group,
            "target_agents": normalized_agents,
            "confidence": confidence,
            "classification_source": classification_source,
            "needs_review": needs_review,
            "needs_agent_confirm": bool(normalized_agents) and 0.6 <= confidence < 0.85,
            "reason": reason,
        }

    def _load_dossier_metadata(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        manifest_paths: set[str] = set()
        checklist_rows: list[dict[str, str]] = []
        checklist_by_doc_id: dict[str, dict[str, str]] = {}
        warnings: list[dict[str, Any]] = []

        for record in records:
            file_name = record["original_filename"].casefold()
            if record["file_type"] != "csv" or file_name not in DOSSIER_METADATA_FILENAMES:
                continue
            try:
                content = Path(record["file_ref"]).read_text(encoding="utf-8-sig")
            except OSError as exc:
                warnings.append(
                    DossierRoutingTraceEntry(
                        file_id=record["file_id"],
                        source_path=record["source_path"],
                        stage="metadata",
                        decision="warning",
                        reason=f"Could not read metadata file: {exc.__class__.__name__}.",
                        confidence=None,
                    ).model_dump(mode="json")
                )
                continue
            reader = csv.DictReader(io.StringIO(content))
            if not reader.fieldnames:
                warnings.append(
                    DossierRoutingTraceEntry(
                        file_id=record["file_id"],
                        source_path=record["source_path"],
                        stage="metadata",
                        decision="warning",
                        reason="Metadata CSV has no header row.",
                        confidence=None,
                    ).model_dump(mode="json")
                )
                continue
            if file_name == "manifest.csv":
                for row in reader:
                    relative_path = (row.get("relative_path") or "").strip()
                    if relative_path:
                        manifest_paths.add(self._normalized_search_text(relative_path))
                continue

            for row in reader:
                cleaned = {str(key or "").lstrip("\ufeff").strip(): str(value or "").strip() for key, value in row.items()}
                document_id = cleaned.get("document_id")
                if document_id:
                    cleaned["document_id"] = document_id.upper()
                    checklist_by_doc_id[cleaned["document_id"]] = cleaned
                checklist_rows.append(cleaned)

        return {
            "manifest_paths": manifest_paths,
            "checklist_rows": checklist_rows,
            "checklist_by_doc_id": checklist_by_doc_id,
            "warnings": warnings,
        }

    def _match_keyword_rule(self, search_text: str) -> dict[str, Any] | None:
        for keywords, document_type, business_group, target_agents, reason in self._keyword_rules():
            if any(keyword in search_text for keyword in keywords):
                return {
                    "detected_document_type": document_type,
                    "business_group": business_group,
                    "target_agents": target_agents,
                    "reason": reason,
                }
        return None

    def _match_folder_rule(self, source_path: str) -> dict[str, Any] | None:
        normalized_path = self._normalized_search_text(source_path)
        folder_rules = (
            (("01 ho so phap ly", "ho so phap ly"), "legal_bundle", "legal", ["credit"], "legal dossier folder"),
            (("02 ho so cap tin dung", "ho so cap tin dung"), "credit_request_bundle", "credit_request", ["credit"], "credit request folder"),
            (("03 ho so tai chinh", "ho so tai chinh"), "financial_bundle", "financial", ["compliance"], "financial dossier folder"),
            (("04 can cu vay", "can cu vay"), "loan_basis_bundle", "loan_basis", ["compliance"], "loan-basis folder"),
            (("05 tai san bao dam", "tai san bao dam", "tsbd"), "collateral_bundle", "collateral", ["compliance", "operations"], "collateral folder"),
            (("06 du lieu cho agent", "du lieu cho agent"), "agent_metadata_bundle", "planner_metadata", [], "agent metadata folder"),
        )
        for keywords, document_type, business_group, target_agents, reason in folder_rules:
            if any(keyword in normalized_path for keyword in keywords):
                return {
                    "detected_document_type": document_type,
                    "business_group": business_group,
                    "target_agents": target_agents,
                    "reason": reason,
                }
        return None

    def _keyword_rules(self) -> tuple[tuple[tuple[str, ...], str, str, list[str], str], ...]:
        return (
            (("danh muc va tom tat", "tom tat ho so", "danh muc ho so", "muc luc ho so"), "dossier_summary", "operations_checklist", ["operations"], "dossier summary and document index"),
            (("dang ky doanh nghiep", "giay chung nhan dang ky doanh nghiep", "giay dang ky doanh nghiep"), "business_registration", "legal", ["credit"], "business registration document"),
            (("cccd", "can cuoc", "nguoi dai dien", "identity"), "representative_identity", "legal", ["credit"], "representative identity document"),
            (("dieu le", "company charter"), "company_charter", "legal", ["credit"], "company charter document"),
            (("quyet dinh bo nhiem", "bo nhiem giam doc", "appointment"), "director_appointment", "legal", ["credit"], "director appointment document"),
            (("mau chu ky", "chu ky nguoi dai dien", "signature"), "signature_specimen", "legal", ["credit"], "signature specimen"),
            (("giay de nghi cap tin dung", "de nghi cap tin dung", "credit request"), "credit_request_form", "credit_request", ["credit", "compliance"], "credit request form"),
            (("thong tin khoan vay", "loan information", "loan info"), "loan_information", "credit_request", ["credit", "operations"], "loan information document"),
            (("phuong an su dung von", "su dung von", "muc dich vay"), "capital_use_plan", "loan_plan", ["compliance"], "capital-use plan"),
            (("phuong an tra no", "tra no", "repayment"), "repayment_plan", "loan_plan", ["compliance"], "repayment plan"),
            (("cam ket cung cap chung tu", "cam ket chung tu"), "document_supply_commitment", "credit_request", ["credit"], "document supply commitment"),
            (("bao cao tai chinh", "bctc", "financial statement"), "financial_statement", "financial", ["compliance"], "financial statement"),
            (("sao ke", "dong tien", "bank statement"), "cashflow_statement", "financial", ["compliance"], "cash-flow statement"),
            (("cong no", "phai thu", "phai tra"), "receivable_payable_report", "financial", ["compliance"], "receivable and payable report"),
            (("han muc cu", "cap han muc cu", "old credit limit"), "previous_credit_limit", "internal", ["compliance"], "previous credit-limit record"),
            (("hop dong dau ra", "output contract"), "output_contract", "loan_basis", ["compliance"], "output contract"),
            (("hop dong dau vao", "input contract"), "input_contract", "loan_basis", ["compliance"], "input contract"),
            (("don dat hang", "don hang", "purchase order"), "purchase_order", "loan_basis", ["compliance"], "purchase order"),
            (("hoa don", "invoice"), "invoice", "loan_basis", ["compliance"], "invoice"),
            (("quyen su dung dat", "nha xuong", "dat nha xuong"), "collateral_title", "collateral", ["compliance"], "collateral title document"),
            (("chung thu tham dinh", "tham dinh gia", "valuation"), "valuation_certificate", "collateral", ["compliance", "operations"], "valuation certificate"),
            (("bien ban kiem tra tai san", "kiem tra tai san"), "collateral_inspection_minutes", "collateral", ["compliance", "operations"], "collateral inspection minutes"),
            (("du thao hop dong the chap", "hop dong the chap", "mortgage"), "mortgage_contract_draft", "collateral", ["operations"], "mortgage contract draft"),
            (("checklist", "danh sach ho so"), "document_checklist", "operations_checklist", ["operations"], "document checklist"),
        )

    def _store_dossier_file(
        self,
        *,
        files_dir: Path,
        accepted_files: list[dict[str, Any]],
        source_path: str,
        original_filename: str,
        file_type: str,
        content_type: str | None,
        content: bytes,
    ) -> None:
        if not content:
            raise LoanAgentValidationError("File is empty.")
        file_id = f"FILE-{len(accepted_files) + 1:04d}"
        normalized_filename = f"{file_id}_{self._safe_file_name(original_filename)}"
        file_ref = files_dir / normalized_filename
        file_ref.write_bytes(content)
        accepted_files.append(
            {
                "file_id": file_id,
                "original_filename": original_filename,
                "normalized_filename": normalized_filename,
                "source_path": source_path,
                "file_type": file_type,
                "file_ref": str(file_ref),
                "content_type": content_type,
                "size_bytes": len(content),
                "checksum_sha256": hashlib.sha256(content).hexdigest(),
                "status": "received",
                "detected_document_type": None,
                "business_group": None,
                "target_agents": [],
                "confidence": 0,
                "classification_source": None,
                "needs_review": False,
                "needs_agent_confirm": False,
                "reason": None,
            }
        )

    async def _read_upload_file_limited(
        self,
        file: UploadFile,
        *,
        limit_bytes: int,
        label: str,
    ) -> bytes:
        chunks: list[bytes] = []
        size_bytes = 0
        try:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > limit_bytes:
                    raise LoanAgentValidationError(f"{label} exceeds the file size limit.")
                chunks.append(chunk)
        finally:
            await file.close()

        if size_bytes == 0:
            raise LoanAgentValidationError(f"{label} is empty.")
        return b"".join(chunks)

    @staticmethod
    def _read_zip_member_limited(
        archive: zipfile.ZipFile,
        info: zipfile.ZipInfo,
        *,
        limit_bytes: int,
    ) -> bytes:
        if info.file_size > limit_bytes:
            raise LoanAgentValidationError("File exceeds the per-file size limit.")
        chunks: list[bytes] = []
        size_bytes = 0
        with archive.open(info) as member:
            while True:
                chunk = member.read(UPLOAD_CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > limit_bytes:
                    raise LoanAgentValidationError("File exceeds the per-file size limit.")
                chunks.append(chunk)
        if size_bytes == 0:
            raise LoanAgentValidationError("File is empty.")
        return b"".join(chunks)

    @classmethod
    def _ignored_dossier_file(
        cls,
        *,
        source_path: str,
        original_filename: str | None,
        file_type: str | None,
        reason: str,
    ) -> dict[str, Any]:
        return DossierIgnoredFile(
            source_path=source_path,
            original_filename=original_filename,
            file_type=file_type,
            reason=reason,
        ).model_dump(mode="json")

    @staticmethod
    def _accepted_dossier_size(records: list[dict[str, Any]]) -> int:
        return sum(int(record.get("size_bytes") or 0) for record in records)

    @classmethod
    def _normalize_zip_source_path(cls, source_path: str) -> str:
        return str(source_path or "").replace("\\", "/").strip()

    @classmethod
    def _is_safe_zip_path(cls, source_path: str) -> bool:
        if not source_path:
            return False
        path = PurePosixPath(source_path)
        if path.is_absolute():
            return False
        for part in path.parts:
            if part in {"", ".", ".."} or part.endswith(":"):
                return False
        return True

    @classmethod
    def _is_ignored_zip_path(cls, source_path: str) -> bool:
        path = PurePosixPath(source_path)
        parts = [part.casefold() for part in path.parts]
        file_name = parts[-1] if parts else ""
        return (
            any(part in DOSSIER_SYSTEM_PATH_PARTS for part in parts)
            or file_name in DOSSIER_SYSTEM_FILENAMES
            or file_name.startswith("._")
            or file_name.startswith("~$")
            or file_name.endswith((".tmp", ".bak", ".swp"))
        )

    @classmethod
    def _is_allowed_dossier_metadata(cls, source_path: str, extension: str) -> bool:
        if extension == ".pdf":
            return True
        file_name = PurePosixPath(source_path).name.casefold()
        if extension == ".csv":
            return file_name in DOSSIER_METADATA_FILENAMES
        if extension == ".json":
            return file_name in {
                "credit_agent_input.json",
                "compliance_agent_input.json",
                "operations_agent_input.json",
                "customer_master.json",
            }
        return False

    @staticmethod
    def _content_type_for_extension(extension: str) -> str | None:
        return {
            ".pdf": "application/pdf",
            ".csv": "text/csv",
            ".json": "application/json",
        }.get(extension)

    @staticmethod
    def _is_valid_json_metadata(content: bytes) -> bool:
        try:
            json.loads(content.decode("utf-8-sig"))
            return True
        except (UnicodeDecodeError, json.JSONDecodeError):
            return False

    @staticmethod
    def _is_allowed_upload_content_type(content_type: str | None, *, allowed: set[str]) -> bool:
        if not content_type:
            return True
        normalized = content_type.split(";", 1)[0].strip().casefold()
        return normalized in allowed

    def _extract_first_page_text(self, file_ref: str) -> str | None:
        try:
            from pypdf import PdfReader

            reader = PdfReader(file_ref)
            if not reader.pages:
                return None
            text = reader.pages[0].extract_text() or ""
            return text[:3000] or None
        except Exception:
            return None

    @classmethod
    def _document_id_from_source_path(cls, source_path: str) -> str | None:
        file_name = PurePosixPath(source_path).name
        match = re.match(r"(?P<number>\d{1,3})[_\-\s.]", file_name)
        if not match:
            return None
        number = int(match.group("number"))
        if number <= 0:
            return None
        return f"DOC-{number:02d}"

    @classmethod
    def _normalize_agent_names(cls, raw_agents: str | None) -> list[str]:
        normalized_agents: list[str] = []
        for value in re.split(r"[/,;|]+", str(raw_agents or "")):
            agent = value.strip().casefold()
            if agent in DOSSIER_AGENT_NAMES and agent not in normalized_agents:
                normalized_agents.append(agent)
        return normalized_agents

    @classmethod
    def _business_group_from_checklist(cls, value: str | None) -> str:
        normalized = cls._normalized_search_text(value)
        if "phap ly" in normalized:
            return "legal"
        if "cap tin dung" in normalized:
            return "credit_request"
        if "phuong an" in normalized:
            return "loan_plan"
        if "tai chinh" in normalized:
            return "financial"
        if "can cu vay" in normalized:
            return "loan_basis"
        if "tsbd" in normalized or "tai san bao dam" in normalized:
            return "collateral"
        if "noi bo" in normalized:
            return "internal"
        return "unknown"

    @classmethod
    def _slugify_document_type(cls, value: str) -> str:
        normalized = cls._normalized_search_text(value)
        slug = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
        return slug or "checklist_document"

    @classmethod
    def _normalized_search_text(cls, *values: Any) -> str:
        raw = " ".join(str(value or "") for value in values)
        raw = raw.replace("Đ", "D").replace("đ", "d")
        normalized = unicodedata.normalize("NFKD", raw)
        ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
        return re.sub(r"[^a-zA-Z0-9]+", " ", ascii_text).casefold().strip()

    def _dossier_upload_dir(self, user_id: str, dossier_id: str) -> Path:
        return (
            Path(configs.resolved_loan_upload_dir)
            / self._safe_path_component(user_id)
            / "dossiers"
            / self._safe_path_component(dossier_id)
        )

    @staticmethod
    def _new_dossier_id() -> str:
        return f"DOSSIER-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"

    @staticmethod
    def _new_routing_batch_id() -> str:
        return f"ROUTING-BATCH-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"

    @classmethod
    def _normalize_idempotency_key(cls, value: str | None) -> str | None:
        normalized = cls._normalize_optional_text(value)
        if normalized and len(normalized) > 128:
            raise LoanAgentValidationError("idempotency_key must be at most 128 characters.")
        return normalized

    async def _save_uploaded_file(
        self,
        file: UploadFile,
        *,
        user_id: str,
        loan_profile_id: str,
        category: str,
    ) -> dict[str, Any]:
        file_name = self._uploaded_file_name(file)
        target_dir = (
            Path(configs.resolved_loan_upload_dir)
            / self._safe_path_component(user_id)
            / self._safe_path_component(loan_profile_id)
            / self._safe_path_component(category)
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}_{self._safe_file_name(file_name)}"
        target_path = target_dir / stored_name
        size_bytes = 0
        try:
            with target_path.open("wb") as output:
                while True:
                    chunk = await file.read(UPLOAD_CHUNK_SIZE_BYTES)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    output.write(chunk)
            if size_bytes == 0:
                target_path.unlink(missing_ok=True)
                raise LoanAgentValidationError("Uploaded file cannot be empty.")
        except Exception:
            target_path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

        return {
            "file_name": file_name,
            "file_path": str(target_path),
            "content_type": file.content_type,
            "size_bytes": size_bytes,
        }

    async def _record_check(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        check_type: str,
        status: str,
        score: float,
        issues: list[dict[str, Any]],
        recommendation: str,
        notes: str | None,
    ):
        now = self._now()
        document = {
            "user_id": self._normalize_user_id(user_id),
            "loan_profile_id": loan_profile_id,
            "check_type": check_type,
            "status": status,
            "score": score,
            "issues": issues,
            "recommendation": recommendation,
            "notes": notes,
            "created_at": now,
        }
        result = await self._collection("loan_agent_checks").insert_one(document)
        document["_id"] = result.inserted_id
        return CheckResultResponse.model_validate(self._serialize_record(document))

    async def _build_report_body(
        self,
        *,
        user_id: str,
        loan_profile_id: str,
        profile: dict[str, Any],
        customer: dict[str, Any],
    ) -> dict[str, Any]:
        collection_counts = {}
        for name, collection_name in {
            "legal_docs": "loan_legal_docs",
            "financial_reports": "loan_financial_reports",
            "collaterals": "loan_collaterals",
            "checks": "loan_agent_checks",
            "tasks": "loan_tasks",
        }.items():
            collection_counts[name] = await self._collection(collection_name).count_documents(
                {
                    "user_id": self._normalize_user_id(user_id),
                    "loan_profile_id": loan_profile_id,
                }
            )

        latest_compliance = await self._latest_by_profile(
            "loan_compliance_results",
            user_id=user_id,
            loan_profile_id=loan_profile_id,
        )
        latest_limit = await self._latest_by_profile(
            "loan_limit_calculations",
            user_id=user_id,
            loan_profile_id=loan_profile_id,
        )
        return {
            "customer": self._serialize_record(customer),
            "loan_profile": self._serialize_record(profile),
            "counts": collection_counts,
            "latest_compliance_result": self._serialize_record(latest_compliance) if latest_compliance else None,
            "latest_limit_calculation": self._serialize_record(latest_limit) if latest_limit else None,
        }

    @staticmethod
    def _build_report_summary(profile: dict[str, Any], report_body: dict[str, Any]) -> str:
        counts = report_body.get("counts") or {}
        return (
            f"Loan profile status is {profile.get('status')}. "
            f"Documents: {counts.get('legal_docs', 0)} legal, "
            f"{counts.get('financial_reports', 0)} financial, "
            f"{counts.get('collaterals', 0)} collateral. "
            f"Checks completed: {counts.get('checks', 0)}."
        )

    async def _find_by_profile(
        self,
        collection_name: str,
        *,
        user_id: str,
        loan_profile_id: str,
        sort_desc: bool = False,
    ) -> list[dict[str, Any]]:
        cursor = self._collection(collection_name).find(
            {
                "user_id": self._normalize_user_id(user_id),
                "loan_profile_id": loan_profile_id,
            }
        )
        cursor = cursor.sort("created_at", -1 if sort_desc else 1)
        return await cursor.to_list(length=None)

    async def _latest_by_profile(
        self,
        collection_name: str,
        *,
        user_id: str,
        loan_profile_id: str,
    ) -> dict[str, Any] | None:
        cursor = self._collection(collection_name).find(
            {
                "user_id": self._normalize_user_id(user_id),
                "loan_profile_id": loan_profile_id,
            }
        ).sort("created_at", -1)
        documents = await cursor.to_list(length=1)
        return documents[0] if documents else None

    async def _require_customer(self, *, user_id: str, customer_id: str) -> dict[str, Any]:
        document = await self._collection("loan_customers").find_one(
            {
                "_id": self._object_id(customer_id, label="customer_id"),
                "user_id": self._normalize_user_id(user_id),
            }
        )
        if not document:
            raise LoanAgentNotFoundError("Customer was not found.")
        return document

    async def _ensure_unique_customer_identity(
        self,
        *,
        user_id: str,
        national_id: str | None,
        tax_code: str | None,
        exclude_customer_id: str | None = None,
    ) -> None:
        predicates = []
        if normalized_national_id := self._normalize_identity(national_id):
            predicates.append({"national_id": normalized_national_id})
        if normalized_tax_code := self._normalize_identity(tax_code):
            predicates.append({"metadata.tax_code": normalized_tax_code})
        if not predicates:
            return
        query: dict[str, Any] = {
            "user_id": self._normalize_user_id(user_id),
            "$or": predicates,
        }
        if exclude_customer_id:
            query["_id"] = {"$ne": self._object_id(exclude_customer_id, label="customer_id")}
        if await self._collection("loan_customers").find_one(query):
            raise LoanAgentValidationError("A customer with the same identity already exists.")

    async def _require_loan_profile(self, *, user_id: str, loan_profile_id: str) -> dict[str, Any]:
        document = await self._collection("loan_profiles").find_one(
            {
                "_id": self._object_id(loan_profile_id, label="loan_profile_id"),
                "user_id": self._normalize_user_id(user_id),
            }
        )
        if not document:
            raise LoanAgentNotFoundError("Loan profile was not found.")
        return document

    def _collection(self, name: str):
        return self.database.get_loan_collection(name)

    @staticmethod
    def _object_id(value: str, *, label: str) -> ObjectId:
        try:
            return ObjectId(str(value))
        except (InvalidId, TypeError) as exc:
            raise LoanAgentValidationError(f"{label} must be a valid MongoDB ObjectId.") from exc

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            raise LoanAgentValidationError("user_id is required.")
        return normalized_user_id

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _normalize_identity(value: str | None) -> str | None:
        normalized = str(value or "").strip().upper()
        return normalized or None

    @classmethod
    def _uploaded_file_name(cls, file: UploadFile) -> str:
        file_name = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not file_name:
            raise LoanAgentValidationError("Uploaded file name is required.")
        return file_name

    @classmethod
    def _safe_file_name(cls, file_name: str) -> str:
        normalized_name = unicodedata.normalize("NFKD", file_name)
        ascii_name = "".join(char for char in normalized_name if not unicodedata.combining(char))
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", ascii_name).strip("._-")
        return safe_name or "upload.bin"

    @classmethod
    def _safe_path_component(cls, value: str) -> str:
        return cls._safe_file_name(value).replace(".", "_")

    @staticmethod
    def _latest_number(documents: list[dict[str, Any]], key: str) -> float | None:
        for document in reversed(documents):
            value = document.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _serialize_record(document: dict[str, Any]) -> dict[str, Any]:
        serialized: dict[str, Any] = {}
        for key, value in dict(document).items():
            if key == "_id":
                serialized["id"] = str(value)
            elif key == "user_id":
                continue
            elif isinstance(value, ObjectId):
                serialized[key] = str(value)
            else:
                serialized[key] = value
        return serialized
