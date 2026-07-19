from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

from agents import Agent, Runner, Session, trace
from agents.mcp import MCPServerStreamableHttp
from agents.tracing import get_current_trace
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from compliance_agent import (
    ComplianceApplication,
    ComplianceAssessment,
    run_compliance_assessment,
)
from credit_agent import CreditApplication, CreditAssessment, run_credit_assessment
from dossier_normalizer import (
    DossierEvidence,
    DossierInputBoundaryResult,
    DossierInputIssue,
    DossierNormalizationResult,
    prepare_dossier_input,
)
from operations_agent import (
    OperationsApplication,
    OperationsAssessment,
    run_operations_assessment,
)
from rag_agent_support import (
    AGENT_MCP_NAME,
    AgentLoggingRunHooks,
    DomainRAGRunHooks,
    KnowledgeEvidence,
    RAGDomain,
    build_agent_run_config,
    classify_agent_error,
    evidence_by_id,
    extract_trusted_evidence,
    log_agent_event,
)


DEFAULT_RAG_MCP_URL = "http://127.0.0.1:8766/mcp"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_LLM_ERROR_CHAT_ANSWER = "Dạ anh/chị cần hỗ trợ gì ko ạ"
ChatDomain = Literal["credit", "compliance", "operations", "general"]
OverallResult = Literal["READY", "REVIEW_REQUIRED", "BLOCKED", "UNDETERMINED"]
Stage = Literal["credit", "compliance"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class OrchestratorApplication(StrictModel):
    credit: CreditApplication
    compliance: ComplianceApplication
    operations: OperationsApplication

    @model_validator(mode="after")
    def validate_same_case(self):
        if len({self.credit.case_id, self.compliance.case_id, self.operations.case_id}) != 1:
            raise ValueError("All specialist inputs must use the same case_id")
        if self.compliance.loan_profile_id != self.operations.loan_profile_id:
            raise ValueError("Compliance and Operations must use the same loan_profile_id")
        if self.credit.loan_profile_id not in {None, self.compliance.loan_profile_id}:
            raise ValueError("Credit loan_profile_id must match the downstream inputs")
        if len(
            {
                self.credit.execution_mode,
                self.compliance.execution_mode,
                self.operations.execution_mode,
            }
        ) != 1:
            raise ValueError("All specialist inputs must use the same execution_mode")
        if len(
            {
                self.credit.customer.customer_type,
                self.compliance.customer_type,
                self.operations.customer_type,
            }
        ) != 1:
            raise ValueError("All specialist inputs must use the same customer_type")
        return self


class OrchestratorAssessment(StrictModel):
    case_id: str
    loan_profile_id: str | None
    overall_result: OverallResult
    stopped_after: Stage | None = None
    stop_reason: str | None = None
    credit: CreditAssessment
    compliance: ComplianceAssessment | None = None
    operations: OperationsAssessment | None = None


class CreditSliceResult(StrictModel):
    status: Literal["completed", "input_not_ready"]
    dossier_id: str | None = None
    routing_batch_id: str | None = None
    can_continue_to_compliance: bool = False
    stop_reason: str | None = None
    credit: CreditAssessment | None = None
    dossier_evidence: list[DossierEvidence] = Field(default_factory=list)
    issues: list[DossierInputIssue] = Field(default_factory=list)


class DossierReportSource(StrictModel):
    file_id: str
    file_name: str
    page: int = Field(ge=1)
    field: str
    excerpt: str


class SpecialistConclusion(StrictModel):
    result: str
    summary: str
    policy_source_ids: list[str] = Field(default_factory=list)


class DossierFinalReport(StrictModel):
    answer: str
    customer_summary: str
    loan_summary: str
    credit: SpecialistConclusion | None = None
    compliance: SpecialistConclusion | None = None
    operations: SpecialistConclusion | None = None
    missing_information: list[str] = Field(default_factory=list)
    hard_stops: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    dossier_sources: list[DossierReportSource] = Field(default_factory=list)
    policy_sources: list[KnowledgeEvidence] = Field(default_factory=list)
    disclaimer: str


class DossierWorkflowResult(StrictModel):
    status: Literal["completed", "input_not_ready"]
    trace_id: str | None = None
    dossier_id: str | None = None
    routing_batch_id: str | None = None
    overall_result: OverallResult
    stopped_after: Literal["input", "credit", "compliance"] | None = None
    stop_reason: str | None = None
    credit: CreditAssessment | None = None
    compliance: ComplianceAssessment | None = None
    operations: OperationsAssessment | None = None
    dossier_evidence: list[DossierEvidence] = Field(default_factory=list)
    issues: list[DossierInputIssue] = Field(default_factory=list)
    report: DossierFinalReport | None = None


class QuestionAnswerDraft(StrictModel):
    domain: ChatDomain
    answer: str
    evidence_ids: list[str]
    insufficient_information: bool = False


class QuestionExecution(StrictModel):
    draft: QuestionAnswerDraft
    trusted_evidence: list[KnowledgeEvidence]


class OrchestratorQuestionAnswer(StrictModel):
    question: str
    domain: ChatDomain
    answer: str
    insufficient_information: bool
    sources: list[KnowledgeEvidence]


SpecialistRunner = Callable[..., Awaitable[Any]]
InputPreparer = Callable[..., Awaitable[DossierInputBoundaryResult]]
QuestionAnswerer = Callable[
    [str, str, str, Session | None], Awaitable[QuestionExecution]
]


def _raw_question_answer_output(output: QuestionAnswerDraft) -> dict[str, Any]:
    return output.model_dump(mode="json")


def _validation_error_fields(error: ValidationError) -> list[str]:
    return sorted(
        {".".join(str(part) for part in item["loc"]) for item in error.errors()}
    )


async def _run_specialist_stage(
    domain: RAGDomain,
    runner: SpecialistRunner,
    application: Any,
    *,
    mcp_url: str,
    model: str,
) -> Any:
    started_at = perf_counter()
    log_agent_event(
        f"agent.{domain}.started",
        dossier_id=application.case_id,
        stage=domain,
    )
    try:
        assessment = await runner(application, mcp_url=mcp_url, model=model)
    except Exception as error:
        log_agent_event(
            f"agent.{domain}.failed",
            dossier_id=application.case_id,
            stage=domain,
            error_category=classify_agent_error(error),
            error_type=type(error).__name__,
            duration_ms=int((perf_counter() - started_at) * 1000),
        )
        raise

    runtime_failed = "rag_or_agent_runtime" in assessment.missing_data
    log_agent_event(
        f"agent.{domain}.failed" if runtime_failed else f"agent.{domain}.completed",
        dossier_id=application.case_id,
        stage=domain,
        result=assessment.facts.result,
        error_category="rag_or_agent_runtime" if runtime_failed else None,
        evidence_count=len(assessment.evidence),
        missing_information_count=len(assessment.missing_data),
        hard_stop_count=len(assessment.facts.hard_stop_reasons),
        duration_ms=int((perf_counter() - started_at) * 1000),
    )
    return assessment


def build_credit_application(
    normalized: DossierNormalizationResult,
) -> tuple[CreditApplication | None, list[str]]:
    facts = normalized.facts
    missing: list[str] = []
    if facts.customer.customer_type is None:
        missing.append("customer.customer_type")
    if facts.signer.signed is None:
        missing.append("signer.signed")
    if facts.signer.is_customer_or_legal_representative is None:
        missing.append("signer.is_customer_or_legal_representative")
    elif not facts.signer.is_customer_or_legal_representative:
        if facts.signer.has_valid_authorization is None:
            missing.append("signer.has_valid_authorization")
        if facts.signer.authorized_person_id_present is None:
            missing.append("signer.authorized_person_id_present")
    if facts.loan.requested_amount is None:
        missing.append("loan.requested_amount")
    if facts.loan.term_months is None:
        missing.append("loan.term_months")

    consistency = facts.consistency.model_dump(mode="python")
    missing.extend(
        f"consistency.{field}"
        for field, value in consistency.items()
        if value is None
    )
    for index, document in enumerate(facts.documents):
        if document.status != "provided":
            continue
        for field in (
            "valid",
            "readable",
            "complete",
            "format_valid",
            "suspicious_alteration",
        ):
            if getattr(document, field) is None:
                missing.append(f"documents.{index}.{field}")
    if missing:
        return None, sorted(set(missing))

    try:
        application = CreditApplication.model_validate(
            {
                "case_id": normalized.dossier_id,
                "execution_mode": "assess",
                "customer": facts.customer.model_dump(mode="python", exclude_none=True),
                "signer": facts.signer.model_dump(mode="python", exclude_none=True),
                "loan": facts.loan.model_dump(mode="python", exclude_none=True),
                "documents": [
                    item.model_dump(mode="python", exclude_none=True)
                    for item in facts.documents
                ],
                "consistency": consistency,
            }
        )
    except ValidationError as exc:
        return None, _validation_error_fields(exc)
    return application, []


async def _run_credit_stage(
    boundary: DossierInputBoundaryResult,
    *,
    mcp_url: str,
    model: str,
    credit_runner: SpecialistRunner,
) -> CreditSliceResult:
    if boundary.status != "ready" or boundary.normalized is None:
        return CreditSliceResult(
            status="input_not_ready",
            dossier_id=boundary.dossier_id,
            routing_batch_id=boundary.routing_batch_id,
            stop_reason="dossier_input_not_ready",
            issues=boundary.issues,
        )

    application, missing = build_credit_application(boundary.normalized)
    if application is None:
        return CreditSliceResult(
            status="input_not_ready",
            dossier_id=boundary.dossier_id,
            routing_batch_id=boundary.routing_batch_id,
            stop_reason="credit_input_incomplete",
            dossier_evidence=boundary.normalized.facts.evidence,
            issues=[
                DossierInputIssue(
                    code="credit_input_incomplete",
                    message="Hồ sơ chưa đủ dữ liệu an toàn để chạy Credit Agent.",
                    fields=missing,
                )
            ],
        )

    credit = await _run_specialist_stage(
        "credit",
        credit_runner,
        application,
        mcp_url=mcp_url,
        model=model,
    )
    can_continue = _credit_can_continue(credit)
    return CreditSliceResult(
        status="completed",
        dossier_id=boundary.dossier_id,
        routing_batch_id=boundary.routing_batch_id,
        can_continue_to_compliance=can_continue,
        stop_reason=None if can_continue else "credit_not_ready_for_compliance",
        credit=credit,
        dossier_evidence=boundary.normalized.facts.evidence,
    )


async def run_credit_slice(
    payload: Any,
    *,
    allowed_root: str | Path,
    mcp_url: str = DEFAULT_RAG_MCP_URL,
    model: str = DEFAULT_MODEL,
    normalizer_runner: SpecialistRunner = Runner.run,
    credit_runner: SpecialistRunner = run_credit_assessment,
    input_preparer: InputPreparer = prepare_dossier_input,
) -> CreditSliceResult:
    boundary = await input_preparer(
        payload,
        allowed_root=allowed_root,
        model=model,
        runner=normalizer_runner,
    )
    return await _run_credit_stage(
        boundary,
        mcp_url=mcp_url,
        model=model,
        credit_runner=credit_runner,
    )


def build_compliance_application(
    normalized: DossierNormalizationResult,
    credit: CreditAssessment,
    *,
    assessment_date: date | None = None,
) -> tuple[ComplianceApplication | None, list[str]]:
    facts = normalized.facts
    documents = facts.compliance_documents.model_dump(mode="python")
    screening = facts.screening.model_dump(mode="python")
    missing = [
        *(f"compliance_documents.{field}" for field, value in documents.items() if value is None),
        *(f"screening.{field}" for field, value in screening.items() if value is None),
    ]
    if missing:
        return None, sorted(missing)

    financials = sorted(
        facts.financials,
        key=lambda item: item.period or "",
        reverse=True,
    )[:2]
    try:
        application = ComplianceApplication.model_validate(
            {
                "case_id": normalized.dossier_id,
                "loan_profile_id": credit.loan_profile_id or normalized.dossier_id,
                "execution_mode": "assess",
                "customer_type": facts.customer.customer_type,
                "as_of_date": assessment_date or date.today(),
                "requested_amount": facts.loan.requested_amount,
                "term_months": facts.loan.term_months,
                "purpose": facts.loan.purpose,
                "credit_result": {
                    "legal_score": credit.facts.legal_score,
                    "result": credit.facts.result,
                    "hard_stop": bool(credit.facts.hard_stop_reasons),
                    "missing_documents": credit.facts.missing_documents,
                },
                "current_financials": (
                    financials[0].model_dump(mode="python", exclude_none=True)
                    if financials
                    else None
                ),
                "previous_financials": (
                    financials[1].model_dump(mode="python", exclude_none=True)
                    if len(financials) > 1
                    else None
                ),
                "funding_plan": facts.funding_plan.model_dump(
                    mode="python", exclude_none=True
                ),
                "repayment_plan": facts.repayment_plan.model_dump(
                    mode="python", exclude_none=True
                ),
                "collateral": facts.collateral.model_dump(
                    mode="python", exclude_none=True
                ),
                "documents": documents,
                "screening": screening,
            }
        )
    except ValidationError as exc:
        return None, _validation_error_fields(exc)
    return application, []


def build_operations_application(
    normalized: DossierNormalizationResult,
    credit: CreditAssessment,
    compliance: ComplianceAssessment,
    *,
    assessment_at: datetime | None = None,
) -> tuple[OperationsApplication | None, list[str]]:
    facts = normalized.facts
    dscr = compliance.facts.metrics.dscr
    ltv = compliance.facts.metrics.ltv
    missing: list[str] = []
    for field, value in (
        ("customer.customer_type", facts.customer.customer_type),
        ("loan.requested_amount", facts.loan.requested_amount),
        ("loan.total_capital_need", facts.loan.total_capital_need),
        ("loan.own_capital", facts.loan.own_capital),
        ("loan.term_months", facts.loan.term_months),
        ("loan.purpose", facts.loan.purpose),
        ("collateral.collateral_type", facts.collateral.collateral_type),
        ("collateral.value", facts.collateral.value),
        ("compliance.metrics.dscr", dscr),
        ("compliance.metrics.ltv", ltv),
        ("compliance.recommended_limit", compliance.facts.recommended_limit),
    ):
        if value is None:
            missing.append(field)
    if missing:
        return None, missing

    now = assessment_at or datetime.now(timezone.utc)
    try:
        application = OperationsApplication.model_validate(
            {
                "case_id": normalized.dossier_id,
                "loan_profile_id": credit.loan_profile_id or normalized.dossier_id,
                "execution_mode": "assess",
                "customer_type": facts.customer.customer_type,
                "current_status": "S01",
                "as_of_at": now,
                "stage_started_at": now,
                "requested_amount": facts.loan.requested_amount,
                "total_capital_need": facts.loan.total_capital_need,
                "own_capital": facts.loan.own_capital,
                "term_months": facts.loan.term_months,
                "purpose": facts.loan.purpose,
                "repayment_method": facts.loan.repayment_method,
                "collateral_based": True,
                "documents": [
                    {
                        "document_type": item.document_type,
                        "status": item.status,
                    }
                    for item in facts.documents
                ],
                "credit_result": {
                    "legal_score": credit.facts.legal_score,
                    "result": credit.facts.result,
                    "hard_stop_reasons": credit.facts.hard_stop_reasons,
                },
                "compliance_result": {
                    "total_score": compliance.facts.total_score,
                    "risk_rating": compliance.facts.risk_rating,
                    "result": compliance.facts.result,
                    "dscr": Decimal(dscr),
                    "collateral_type": facts.collateral.collateral_type,
                    "collateral_value": facts.collateral.value,
                    "ltv_ratio": Decimal(ltv),
                    "hard_stop_reasons": compliance.facts.hard_stop_reasons,
                    "conditions": compliance.conditions,
                    "recommended_limit": compliance.facts.recommended_limit,
                },
                "human_approved": False,
                "disbursement_conditions_complete": False,
            }
        )
    except ValidationError as exc:
        return None, _validation_error_fields(exc)
    return application, []


def _credit_overall_result(credit: CreditAssessment) -> OverallResult:
    if credit.facts.result == "UNDETERMINED":
        return "UNDETERMINED"
    if credit.facts.result == "FAILED":
        return "BLOCKED"
    return "REVIEW_REQUIRED"


def _credit_can_continue(credit: CreditAssessment) -> bool:
    return bool(
        credit.facts.result in {"PASSED", "CONDITIONAL"}
        and not credit.facts.hard_stop_reasons
        and credit.facts.can_forward_to_compliance
    )


def _compliance_can_continue(compliance: ComplianceAssessment) -> bool:
    return bool(
        compliance.facts.result in {"PASSED", "CONDITIONAL"}
        and not compliance.facts.hard_stop_reasons
        and compliance.facts.metrics.dscr is not None
        and compliance.facts.recommended_limit is not None
    )


def _compliance_stop_result(compliance: ComplianceAssessment) -> OverallResult:
    if compliance.facts.result == "FAILED" or compliance.facts.hard_stop_reasons:
        return "BLOCKED"
    if (
        compliance.facts.result == "UNDETERMINED"
        or compliance.facts.metrics.dscr is None
        or compliance.facts.recommended_limit is None
    ):
        return "UNDETERMINED"
    return "REVIEW_REQUIRED"


_RESULT_LABELS = {
    "PASSED": "đạt",
    "CONDITIONAL": "đạt có điều kiện",
    "FAILED": "không đạt",
    "UNDETERMINED": "chưa đủ căn cứ",
    "READY": "đủ điều kiện trình phê duyệt",
    "BLOCKED": "bị chặn",
    "WAITING": "đang chờ bổ sung",
}
_CUSTOMER_TYPE_LABELS = {
    "individual": "cá nhân",
    "household_business": "hộ kinh doanh",
    "enterprise": "doanh nghiệp",
}
_DISCLAIMER = (
    "Đây là đề xuất hỗ trợ thẩm định, không phải quyết định phê duyệt cuối cùng "
    "của ngân hàng."
)


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _money(value: Decimal | None) -> str:
    return "chưa xác định" if value is None else f"{value:,.0f}".replace(",", ".") + " VND"


def _specialist_conclusions(
    result: DossierWorkflowResult,
) -> tuple[
    SpecialistConclusion | None,
    SpecialistConclusion | None,
    SpecialistConclusion | None,
]:
    credit = result.credit
    compliance = result.compliance
    operations = result.operations
    return (
        SpecialistConclusion(
            result=credit.facts.result,
            summary=(
                f"Credit Agent kết luận {_RESULT_LABELS[credit.facts.result]}, "
                f"điểm pháp lý {credit.facts.legal_score}/100."
            ),
            policy_source_ids=_unique([item.source_id for item in credit.evidence]),
        )
        if credit
        else None,
        SpecialistConclusion(
            result=compliance.facts.result,
            summary=(
                f"Compliance Agent kết luận {_RESULT_LABELS[compliance.facts.result]}, "
                f"điểm tuân thủ {compliance.facts.total_score}/100, "
                f"hạn mức đề xuất {_money(compliance.facts.recommended_limit)}."
            ),
            policy_source_ids=_unique([item.source_id for item in compliance.evidence]),
        )
        if compliance
        else None,
        SpecialistConclusion(
            result=operations.facts.result,
            summary=(
                f"Operations Agent kết luận {_RESULT_LABELS[operations.facts.result]}, "
                f"điểm checklist {operations.facts.checklist_score}/100, "
                f"hạn mức đề xuất {_money(operations.facts.recommended_limit)}."
            ),
            policy_source_ids=_unique([item.source_id for item in operations.evidence]),
        )
        if operations
        else None,
    )


def build_final_report(
    result: DossierWorkflowResult,
    normalized: DossierNormalizationResult | None,
) -> DossierFinalReport:
    facts = normalized.facts if normalized else None
    customer_summary = (
        "Khách hàng: "
        f"{facts.customer.full_name or 'chưa xác định'}; "
        "loại khách hàng "
        f"{_CUSTOMER_TYPE_LABELS.get(facts.customer.customer_type, 'chưa xác định')}."
        if facts
        else "Khách hàng: chưa đủ dữ liệu để xác định."
    )
    loan_summary = (
        "Nhu cầu vay: "
        f"{_money(facts.loan.requested_amount)}; "
        f"thời hạn {facts.loan.term_months or 'chưa xác định'} tháng; "
        f"mục đích {facts.loan.purpose or 'chưa xác định'}."
        if facts
        else "Nhu cầu vay: chưa đủ dữ liệu để xác định."
    )
    credit, compliance, operations = _specialist_conclusions(result)

    assessments = [item for item in (result.credit, result.compliance, result.operations) if item]
    missing_information = _unique(
        [
            *(
                [f"{item.field}: {item.reason}" for item in facts.missing_information]
                if facts
                else []
            ),
            *(item.message for item in result.issues),
            *(item for assessment in assessments for item in assessment.missing_data),
            *(result.credit.facts.missing_documents if result.credit else []),
        ]
    )
    hard_stops = _unique(
        [
            *(result.credit.facts.hard_stop_reasons if result.credit else []),
            *(result.compliance.facts.hard_stop_reasons if result.compliance else []),
            *(result.operations.facts.hard_stop_reasons if result.operations else []),
        ]
    )
    conditions = _unique(
        [
            *(result.compliance.conditions if result.compliance else []),
            *(result.operations.conditions if result.operations else []),
        ]
    )
    next_actions = _unique(
        [
            *(result.credit.required_actions if result.credit else []),
            *(
                [item.action for item in result.operations.next_actions]
                if result.operations
                else []
            ),
            *(result.operations.facts.next_action_codes if result.operations else []),
        ]
    )

    file_names = {
        item.file_id: item.original_filename for item in normalized.files
    } if normalized else {}
    dossier_sources = [
        DossierReportSource(
            file_id=item.file_id,
            file_name=file_names.get(item.file_id, item.file_id),
            page=item.page,
            field=item.field,
            excerpt=item.excerpt,
        )
        for item in result.dossier_evidence
    ]
    policy_by_id = {
        item.source_id: item
        for assessment in assessments
        for item in assessment.evidence
    }
    policy_sources = list(policy_by_id.values())

    overall_summary = {
        "READY": "Hồ sơ đủ điều kiện trình phê duyệt.",
        "REVIEW_REQUIRED": "Hồ sơ cần rà soát hoặc bổ sung điều kiện trước khi trình phê duyệt.",
        "BLOCKED": "Hồ sơ đang bị chặn và chưa đủ điều kiện trình phê duyệt.",
        "UNDETERMINED": "Chưa đủ thông tin để kết luận hồ sơ.",
    }[result.overall_result]
    lines = [overall_summary, customer_summary, loan_summary]
    lines.extend(item.summary for item in (credit, compliance, operations) if item)
    for label, values in (
        ("Thông tin còn thiếu", missing_information),
        ("Điểm chặn", hard_stops),
        ("Điều kiện", conditions),
        ("Hành động tiếp theo", next_actions),
    ):
        if values:
            lines.append(f"{label}: {'; '.join(values)}.")
    if dossier_sources:
        lines.append(
            "Nguồn hồ sơ: "
            + "; ".join(
                f"{item.file_name}, trang {item.page}" for item in dossier_sources
            )
            + "."
        )
    if policy_sources:
        lines.append(
            "Nguồn chính sách: "
            + "; ".join(
                f"{item.file_name}, trang {item.page or 'không xác định'}"
                for item in policy_sources
            )
            + "."
        )
    lines.append(_DISCLAIMER)
    return DossierFinalReport(
        answer="\n".join(lines),
        customer_summary=customer_summary,
        loan_summary=loan_summary,
        credit=credit,
        compliance=compliance,
        operations=operations,
        missing_information=missing_information,
        hard_stops=hard_stops,
        conditions=conditions,
        next_actions=next_actions,
        dossier_sources=dossier_sources,
        policy_sources=policy_sources,
        disclaimer=_DISCLAIMER,
    )


def _with_final_report(
    result: DossierWorkflowResult,
    normalized: DossierNormalizationResult | None,
) -> DossierWorkflowResult:
    current_trace = get_current_trace()
    if current_trace is not None:
        result.trace_id = current_trace.trace_id
    result.report = build_final_report(result, normalized)
    return result


async def _run_dossier_assessment(
    payload: Any,
    *,
    allowed_root: str | Path,
    mcp_url: str = DEFAULT_RAG_MCP_URL,
    model: str = DEFAULT_MODEL,
    assessment_date: date | None = None,
    assessment_at: datetime | None = None,
    normalizer_runner: SpecialistRunner = Runner.run,
    credit_runner: SpecialistRunner = run_credit_assessment,
    compliance_runner: SpecialistRunner = run_compliance_assessment,
    operations_runner: SpecialistRunner = run_operations_assessment,
    input_preparer: InputPreparer = prepare_dossier_input,
) -> DossierWorkflowResult:
    normalization_started_at = perf_counter()
    log_agent_event("dossier.normalization.started", stage="input")
    try:
        boundary = await input_preparer(
            payload,
            allowed_root=allowed_root,
            model=model,
            runner=normalizer_runner,
        )
    except Exception as error:
        log_agent_event(
            "dossier.normalization.failed",
            stage="input",
            error_category=classify_agent_error(error),
            error_type=type(error).__name__,
            duration_ms=int((perf_counter() - normalization_started_at) * 1000),
        )
        raise
    log_agent_event(
        "dossier.normalization.completed",
        dossier_id=boundary.dossier_id,
        stage="input",
        status=boundary.status,
        page_count=(boundary.normalized.page_count if boundary.normalized else 0),
        evidence_count=(
            len(boundary.normalized.facts.evidence) if boundary.normalized else 0
        ),
        missing_information_count=(
            len(boundary.normalized.facts.missing_information)
            if boundary.normalized
            else len(boundary.issues)
        ),
        duration_ms=int((perf_counter() - normalization_started_at) * 1000),
    )
    credit_slice = await _run_credit_stage(
        boundary,
        mcp_url=mcp_url,
        model=model,
        credit_runner=credit_runner,
    )
    if credit_slice.credit is None or boundary.normalized is None:
        log_agent_event(
            "orchestrator.credit_gate",
            dossier_id=boundary.dossier_id,
            stage="credit",
            decision="stop",
            stop_reason=credit_slice.stop_reason,
            error_category="input",
            missing_information_count=len(credit_slice.issues),
        )
        return _with_final_report(
            DossierWorkflowResult(
                status="input_not_ready",
                dossier_id=boundary.dossier_id,
                routing_batch_id=boundary.routing_batch_id,
                overall_result="UNDETERMINED",
                stopped_after="input",
                stop_reason=credit_slice.stop_reason,
                dossier_evidence=credit_slice.dossier_evidence,
                issues=credit_slice.issues,
            ),
            boundary.normalized,
        )

    credit = credit_slice.credit
    log_agent_event(
        "orchestrator.credit_gate",
        dossier_id=boundary.dossier_id,
        stage="credit",
        decision=(
            "continue_to_compliance"
            if credit_slice.can_continue_to_compliance
            else "stop"
        ),
        result=credit.facts.result,
        stop_reason=(
            None
            if credit_slice.can_continue_to_compliance
            else "credit_not_ready_for_compliance"
        ),
        missing_information_count=len(credit.missing_data),
        hard_stop_count=len(credit.facts.hard_stop_reasons),
    )
    if not credit_slice.can_continue_to_compliance:
        return _with_final_report(
            DossierWorkflowResult(
                status="completed",
                dossier_id=boundary.dossier_id,
                routing_batch_id=boundary.routing_batch_id,
                overall_result=_credit_overall_result(credit),
                stopped_after="credit",
                stop_reason="credit_not_ready_for_compliance",
                credit=credit,
                dossier_evidence=credit_slice.dossier_evidence,
            ),
            boundary.normalized,
        )

    compliance_application, missing = build_compliance_application(
        boundary.normalized,
        credit,
        assessment_date=assessment_date,
    )
    if compliance_application is None:
        log_agent_event(
            "orchestrator.compliance_gate",
            dossier_id=boundary.dossier_id,
            stage="compliance",
            decision="stop",
            stop_reason="compliance_input_incomplete",
            error_category="input",
            missing_information_count=len(missing),
        )
        return _with_final_report(
            DossierWorkflowResult(
                status="input_not_ready",
                dossier_id=boundary.dossier_id,
                routing_batch_id=boundary.routing_batch_id,
                overall_result="UNDETERMINED",
                stopped_after="credit",
                stop_reason="compliance_input_incomplete",
                credit=credit,
                dossier_evidence=credit_slice.dossier_evidence,
                issues=[
                    DossierInputIssue(
                        code="compliance_input_incomplete",
                        message="Hồ sơ chưa đủ dữ liệu an toàn để chạy Compliance Agent.",
                        fields=missing,
                    )
                ],
            ),
            boundary.normalized,
        )

    compliance = await _run_specialist_stage(
        "compliance",
        compliance_runner,
        compliance_application,
        mcp_url=mcp_url,
        model=model,
    )
    compliance_can_continue = _compliance_can_continue(compliance)
    log_agent_event(
        "orchestrator.compliance_gate",
        dossier_id=boundary.dossier_id,
        stage="compliance",
        decision="continue_to_operations" if compliance_can_continue else "stop",
        result=compliance.facts.result,
        stop_reason=(
            None if compliance_can_continue else "compliance_not_ready_for_operations"
        ),
        missing_information_count=len(compliance.missing_data),
        hard_stop_count=len(compliance.facts.hard_stop_reasons),
    )
    if not compliance_can_continue:
        return _with_final_report(
            DossierWorkflowResult(
                status="completed",
                dossier_id=boundary.dossier_id,
                routing_batch_id=boundary.routing_batch_id,
                overall_result=_compliance_stop_result(compliance),
                stopped_after="compliance",
                stop_reason="compliance_not_ready_for_operations",
                credit=credit,
                compliance=compliance,
                dossier_evidence=credit_slice.dossier_evidence,
            ),
            boundary.normalized,
        )

    operations_application, missing = build_operations_application(
        boundary.normalized,
        credit,
        compliance,
        assessment_at=assessment_at,
    )
    if operations_application is None:
        log_agent_event(
            "orchestrator.operations_input_gate",
            dossier_id=boundary.dossier_id,
            stage="operations",
            decision="stop",
            stop_reason="operations_input_incomplete",
            error_category="input",
            missing_information_count=len(missing),
        )
        return _with_final_report(
            DossierWorkflowResult(
                status="input_not_ready",
                dossier_id=boundary.dossier_id,
                routing_batch_id=boundary.routing_batch_id,
                overall_result="UNDETERMINED",
                stopped_after="compliance",
                stop_reason="operations_input_incomplete",
                credit=credit,
                compliance=compliance,
                dossier_evidence=credit_slice.dossier_evidence,
                issues=[
                    DossierInputIssue(
                        code="operations_input_incomplete",
                        message="Hồ sơ chưa đủ dữ liệu an toàn để chạy Operations Agent.",
                        fields=missing,
                    )
                ],
            ),
            boundary.normalized,
        )

    operations = await _run_specialist_stage(
        "operations",
        operations_runner,
        operations_application,
        mcp_url=mcp_url,
        model=model,
    )
    overall_result: OverallResult = {
        "READY": "READY",
        "BLOCKED": "BLOCKED",
        "UNDETERMINED": "UNDETERMINED",
        "CONDITIONAL": "REVIEW_REQUIRED",
        "WAITING": "REVIEW_REQUIRED",
    }[operations.facts.result]
    return _with_final_report(
        DossierWorkflowResult(
            status="completed",
            dossier_id=boundary.dossier_id,
            routing_batch_id=boundary.routing_batch_id,
            overall_result=overall_result,
            credit=credit,
            compliance=compliance,
            operations=operations,
            dossier_evidence=credit_slice.dossier_evidence,
        ),
        boundary.normalized,
    )


async def run_dossier_assessment(
    payload: Any,
    *,
    allowed_root: str | Path,
    mcp_url: str = DEFAULT_RAG_MCP_URL,
    model: str = DEFAULT_MODEL,
    assessment_date: date | None = None,
    assessment_at: datetime | None = None,
    normalizer_runner: SpecialistRunner = Runner.run,
    credit_runner: SpecialistRunner = run_credit_assessment,
    compliance_runner: SpecialistRunner = run_compliance_assessment,
    operations_runner: SpecialistRunner = run_operations_assessment,
    input_preparer: InputPreparer = prepare_dossier_input,
) -> DossierWorkflowResult:
    raw = payload.model_dump(mode="python") if isinstance(payload, BaseModel) else payload
    dossier_id = raw.get("dossier_id") if isinstance(raw, dict) else None
    dossier_id = dossier_id.strip() or None if isinstance(dossier_id, str) else None
    files = raw.get("files") if isinstance(raw, dict) else None
    started_at = perf_counter()

    with trace(
        "MediaX Dossier Assessment",
        group_id=dossier_id,
        metadata={"dossier_id": dossier_id} if dossier_id else None,
    ):
        log_agent_event(
            "dossier.assessment.started",
            dossier_id=dossier_id,
            stage="input",
            file_count=len(files) if isinstance(files, list) else None,
            execution_mode="assess",
        )
        try:
            result = await _run_dossier_assessment(
                payload,
                allowed_root=allowed_root,
                mcp_url=mcp_url,
                model=model,
                assessment_date=assessment_date,
                assessment_at=assessment_at,
                normalizer_runner=normalizer_runner,
                credit_runner=credit_runner,
                compliance_runner=compliance_runner,
                operations_runner=operations_runner,
                input_preparer=input_preparer,
            )
        except Exception as error:
            log_agent_event(
                "dossier.assessment.failed",
                dossier_id=dossier_id,
                stage="workflow",
                error_category=classify_agent_error(error),
                error_type=type(error).__name__,
                duration_ms=int((perf_counter() - started_at) * 1000),
            )
            raise

        runtime_failed = any(
            "rag_or_agent_runtime" in assessment.missing_data
            for assessment in (result.credit, result.compliance, result.operations)
            if assessment
        )
        report = result.report
        log_agent_event(
            "dossier.assessment.completed",
            dossier_id=result.dossier_id,
            stage=result.stopped_after or "completed",
            status=result.status,
            result=result.overall_result,
            stop_reason=result.stop_reason,
            error_category=(
                "input"
                if result.status == "input_not_ready"
                else "rag_or_agent_runtime"
                if runtime_failed
                else None
            ),
            evidence_count=(
                len(result.dossier_evidence) + len(report.policy_sources)
                if report
                else len(result.dossier_evidence)
            ),
            missing_information_count=(len(report.missing_information) if report else 0),
            hard_stop_count=(len(report.hard_stops) if report else 0),
            duration_ms=int((perf_counter() - started_at) * 1000),
        )
        return result


def _compliance_input(
    application: OrchestratorApplication,
    credit: CreditAssessment,
    loan_profile_id: str,
) -> ComplianceApplication:
    return ComplianceApplication.model_validate(
        {
            **application.compliance.model_dump(mode="python"),
            "loan_profile_id": loan_profile_id,
            "credit_result": {
                "legal_score": credit.facts.legal_score,
                "result": credit.facts.result,
                "hard_stop": bool(credit.facts.hard_stop_reasons),
                "missing_documents": credit.facts.missing_documents,
            },
        }
    )


def _operations_input(
    application: OrchestratorApplication,
    credit: CreditAssessment,
    compliance: ComplianceAssessment,
    loan_profile_id: str,
) -> OperationsApplication:
    dscr = compliance.facts.metrics.dscr
    ltv = compliance.facts.metrics.ltv
    if dscr is None or ltv is None:
        raise ValueError("Compliance result does not contain DSCR/LTV")
    collateral = application.compliance.collateral
    return OperationsApplication.model_validate(
        {
            **application.operations.model_dump(mode="python"),
            "loan_profile_id": loan_profile_id,
            "credit_result": {
                "legal_score": credit.facts.legal_score,
                "result": credit.facts.result,
                "hard_stop_reasons": credit.facts.hard_stop_reasons,
            },
            "compliance_result": {
                "total_score": compliance.facts.total_score,
                "risk_rating": compliance.facts.risk_rating,
                "result": compliance.facts.result,
                "dscr": Decimal(dscr),
                "collateral_type": collateral.collateral_type,
                "collateral_value": collateral.value,
                "ltv_ratio": Decimal(ltv),
                "hard_stop_reasons": compliance.facts.hard_stop_reasons,
                "conditions": compliance.conditions,
                "recommended_limit": compliance.facts.recommended_limit,
            },
        }
    )


async def run_orchestrator(
    application: OrchestratorApplication,
    *,
    mcp_url: str = DEFAULT_RAG_MCP_URL,
    model: str = DEFAULT_MODEL,
    credit_runner: SpecialistRunner = run_credit_assessment,
    compliance_runner: SpecialistRunner = run_compliance_assessment,
    operations_runner: SpecialistRunner = run_operations_assessment,
) -> OrchestratorAssessment:
    credit = await credit_runner(application.credit, mcp_url=mcp_url, model=model)
    loan_profile_id = credit.loan_profile_id or application.compliance.loan_profile_id
    if not _credit_can_continue(credit):
        result: OverallResult = (
            "UNDETERMINED"
            if credit.facts.result == "UNDETERMINED"
            else "BLOCKED"
            if credit.facts.result == "FAILED"
            else "REVIEW_REQUIRED"
        )
        return OrchestratorAssessment(
            case_id=application.credit.case_id,
            loan_profile_id=loan_profile_id,
            overall_result=result,
            stopped_after="credit",
            stop_reason="credit_not_ready_for_compliance",
            credit=credit,
        )

    compliance = await compliance_runner(
        _compliance_input(application, credit, loan_profile_id),
        mcp_url=mcp_url,
        model=model,
    )
    if not _compliance_can_continue(compliance):
        return OrchestratorAssessment(
            case_id=application.credit.case_id,
            loan_profile_id=loan_profile_id,
            overall_result=(
                _compliance_stop_result(compliance)
            ),
            stopped_after="compliance",
            stop_reason="compliance_not_ready_for_operations",
            credit=credit,
            compliance=compliance,
        )

    operations = await operations_runner(
        _operations_input(application, credit, compliance, loan_profile_id),
        mcp_url=mcp_url,
        model=model,
    )
    overall_result: OverallResult = {
        "READY": "READY",
        "BLOCKED": "BLOCKED",
        "UNDETERMINED": "UNDETERMINED",
        "CONDITIONAL": "REVIEW_REQUIRED",
        "WAITING": "REVIEW_REQUIRED",
    }[operations.facts.result]
    return OrchestratorAssessment(
        case_id=application.credit.case_id,
        loan_profile_id=loan_profile_id,
        overall_result=overall_result,
        credit=credit,
        compliance=compliance,
        operations=operations,
    )


def build_question_mcp_server(mcp_url: str) -> MCPServerStreamableHttp:
    return MCPServerStreamableHttp(
        params={"url": mcp_url, "timeout": 30, "sse_read_timeout": 30},
        name=AGENT_MCP_NAME,
        cache_tools_list=True,
        client_session_timeout_seconds=30,
        tool_filter={
            "allowed_tool_names": ["search_knowledge", "get_document_page"]
        },
        use_structured_content=True,
    )


def build_question_agent(
    domain: RAGDomain,
    server: MCPServerStreamableHttp,
    model: str,
) -> Agent:
    return Agent(
        name=f"{domain.title()} Knowledge Agent",
        instructions=(
            f"Answer the user's question as the {domain} banking specialist. First call "
            f"search_knowledge with domain='{domain}' and top_k=5. Set domain='{domain}' in "
            "the output. If a returned chunk lacks "
            "enough context, call get_document_page with the same domain and only a source_id "
            "returned by that search. Always write the user-facing answer in Vietnamese, "
            "regardless of the user's or source document's language, and use only MCP evidence. "
            "Return the answer as plain text only. Do not use Markdown syntax such as headings, "
            "bold or italic markers, code fences, or Markdown lists. "
            "Put every cited source_id in evidence_ids. If evidence supports only part of the "
            "answer, cite the sources used and set insufficient_information=true. Use "
            "evidence_ids=[] only when no returned evidence supports a useful answer. Never "
            "provide policy facts from memory."
        ),
        model=model,
        mcp_servers=[server],
        output_type=QuestionAnswerDraft,
    )


def build_chat_orchestrator(specialist_tools: list[Any], model: str) -> Agent:
    return Agent(
        name="Orchestrator",
        instructions=(
            "Use conversation history to understand follow-up questions, then call exactly "
            "one primary specialist: credit for customer intake, legal documents, signatures, "
            "and opening a loan case; compliance for financial capacity, repayment, collateral, "
            "legal/compliance risk, and policy ratios; operations for workflow, checklist, "
            "S01-S11 status, SLA, priority, limits, and next actions. Return the specialist's "
            "structured result without changing its answer, domain, or evidence_ids. Every "
            "user-facing answer must be in Vietnamese and plain text only. Do not use Markdown "
            "syntax such as headings, bold or italic markers, code fences, or Markdown lists."
        ),
        model=model,
        tools=specialist_tools,
        output_type=QuestionAnswerDraft,
    )


async def _collect_specialist_output(
    result: Any,
    *,
    domain: RAGDomain,
    executions: list[QuestionExecution],
) -> str:
    if not isinstance(result.final_output, QuestionAnswerDraft):
        raise TypeError("Knowledge Agent returned an invalid answer")
    if result.final_output.domain != domain:
        raise ValueError(f"{domain} agent returned a different domain")
    trusted_evidence = extract_trusted_evidence(
        result.new_items,
        domain=domain,
    )
    executions.append(
        QuestionExecution(
            draft=result.final_output,
            trusted_evidence=trusted_evidence,
        )
    )
    log_agent_event(
        "agent.raw_answer",
        agent=f"{domain.title()} Knowledge Agent",
        domain=domain,
        raw_output=_raw_question_answer_output(result.final_output),
    )
    log_agent_event(
        "agent.output.validated",
        agent=f"{domain.title()} Knowledge Agent",
        domain=domain,
        evidence_count=len(trusted_evidence),
        cited_sources=len(result.final_output.evidence_ids),
        insufficient_information=result.final_output.insufficient_information,
    )
    return result.final_output.model_dump_json()


async def execute_question(
    question: str,
    mcp_url: str,
    model: str,
    session: Session | None = None,
) -> QuestionExecution:
    async with build_question_mcp_server(mcp_url) as server:
        tools = await server.list_tools()
        if {tool.name for tool in tools} != {"search_knowledge", "get_document_page"}:
            raise RuntimeError("Question agent MCP server exposes an unexpected tool set")
        executions: list[QuestionExecution] = []
        specialist_tools = [
            build_question_agent(domain, server, model).as_tool(
                tool_name=f"ask_{domain}_agent",
                tool_description=f"Ask the {domain} banking specialist.",
                hooks=DomainRAGRunHooks(domain),
                custom_output_extractor=lambda result, domain=domain: _collect_specialist_output(
                    result,
                    domain=domain,
                    executions=executions,
                ),
            )
            for domain in ("credit", "compliance", "operations")
        ]
        result = await Runner.run(
            build_chat_orchestrator(specialist_tools, model),
            question,
            session=session,
            hooks=AgentLoggingRunHooks(),
            run_config=build_agent_run_config(
                "MediaX Agent Bank Chat",
                metadata={"surface": "orchestrator_chat"},
            ),
        )
    if not isinstance(result.final_output, QuestionAnswerDraft):
        raise TypeError("Orchestrator returned an invalid answer")
    log_agent_event(
        "agent.raw_answer",
        agent="Orchestrator",
        raw_output=_raw_question_answer_output(result.final_output),
    )
    if len(executions) == 0:
        log_agent_event(
            "agent.routing.unresolved",
            stage="orchestrator_chat",
            reason="no_specialist_called",
            orchestrator_domain=result.final_output.domain,
            insufficient_information=result.final_output.insufficient_information,
        )
        return QuestionExecution(draft=result.final_output, trusted_evidence=[])
    if len(executions) != 1:
        raise ValueError("Orchestrator must call exactly one specialist")
    if result.final_output != executions[0].draft:
        log_agent_event(
            "agent.routing.output_changed",
            stage="orchestrator_chat",
            specialist_domain=executions[0].draft.domain,
            orchestrator_domain=result.final_output.domain,
            specialist_raw_output=_raw_question_answer_output(executions[0].draft),
            orchestrator_raw_output=_raw_question_answer_output(result.final_output),
        )
    return executions[0]


def assemble_question_answer(
    question: str,
    execution: QuestionExecution,
) -> OrchestratorQuestionAnswer:
    if execution.draft.domain == "general":
        return OrchestratorQuestionAnswer(
            question=question,
            domain=execution.draft.domain,
            answer=execution.draft.answer,
            insufficient_information=True,
            sources=[],
        )
    trusted = evidence_by_id(execution.trusted_evidence)
    unknown_ids = sorted(set(execution.draft.evidence_ids) - trusted.keys())
    if unknown_ids:
        raise ValueError(f"Unknown answer evidence ids: {', '.join(unknown_ids)}")
    if not execution.draft.insufficient_information and not execution.draft.evidence_ids:
        raise ValueError("A grounded answer must cite evidence")
    return OrchestratorQuestionAnswer(
        question=question,
        domain=execution.draft.domain,
        answer=execution.draft.answer,
        insufficient_information=execution.draft.insufficient_information,
        sources=[trusted[source_id] for source_id in execution.draft.evidence_ids],
    )


async def answer_question(
    question: str,
    *,
    mcp_url: str = DEFAULT_RAG_MCP_URL,
    model: str = DEFAULT_MODEL,
    session: Session | None = None,
    question_answerer: QuestionAnswerer = execute_question,
) -> OrchestratorQuestionAnswer:
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("Question is required")
    execution = await question_answerer(
        normalized_question,
        mcp_url,
        model,
        session,
    )
    return assemble_question_answer(normalized_question, execution)


def load_application(
    credit_path: str,
    compliance_path: str,
    operations_path: str,
) -> OrchestratorApplication:
    return OrchestratorApplication(
        credit=CreditApplication.model_validate_json(
            Path(credit_path).read_text(encoding="utf-8")
        ),
        compliance=ComplianceApplication.model_validate_json(
            Path(compliance_path).read_text(encoding="utf-8")
        ),
        operations=OperationsApplication.model_validate_json(
            Path(operations_path).read_text(encoding="utf-8")
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MediaX loan Orchestrator.")
    parser.add_argument("--ask", help="Ask one natural-language banking question.")
    parser.add_argument("--credit-input")
    parser.add_argument("--compliance-input")
    parser.add_argument("--operations-input")
    parser.add_argument("--mcp-url", default=os.getenv("RAG_MCP_URL", DEFAULT_RAG_MCP_URL))
    parser.add_argument("--model", default=os.getenv("OPENAI_AGENT_MODEL", DEFAULT_MODEL))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required.")
    input_paths = [args.credit_input, args.compliance_input, args.operations_input]
    if args.ask:
        if any(input_paths):
            parser.error("--ask cannot be combined with specialist input files")
        answer = asyncio.run(
            answer_question(args.ask, mcp_url=args.mcp_url, model=args.model)
        )
        print(answer.answer)
        if answer.sources:
            print("\nSources:")
            for source in answer.sources:
                print(f"- [{source.source_id}] {source.file_name}, page {source.page or '-'}")
        return
    if not all(input_paths):
        parser.error("provide --ask or all three specialist input files")
    assessment = asyncio.run(
        run_orchestrator(
            load_application(
                args.credit_input,
                args.compliance_input,
                args.operations_input,
            ),
            mcp_url=args.mcp_url,
            model=args.model,
        )
    )
    print(json.dumps(assessment.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
