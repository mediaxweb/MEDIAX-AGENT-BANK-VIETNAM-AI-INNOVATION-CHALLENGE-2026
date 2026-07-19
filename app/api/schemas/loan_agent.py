from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


CheckStatus = Literal["passed", "warning", "failed"]
ComplianceDecision = Literal["approved", "conditional", "rejected", "needs_review"]
TaskPriority = Literal["low", "medium", "high", "urgent", "P1", "P2", "P3"]
DossierAgentName = Literal["credit", "compliance", "operations"]
DossierRoutingStatus = Literal[
    "ready_to_dispatch",
    "needs_review",
    "dispatching",
    "dispatched",
    "partial_dispatch_failed",
    "dispatch_failed",
    "blocked_needs_review",
    "failed",
]
DossierAgentDispatchStatus = Literal[
    "sent",
    "completed",
    "input_not_ready",
    "skipped_by_gate",
    "skipped_no_files",
    "blocked_needs_review",
    "failed",
]
DossierAssessmentStatus = Literal["completed", "input_not_ready", "failed"]


class CustomerCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=1)
    phone: str | None = None
    email: EmailStr | None = None
    national_id: str | None = None
    date_of_birth: str | None = None
    address: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CustomerUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1)
    phone: str | None = None
    email: EmailStr | None = None
    national_id: str | None = None
    date_of_birth: str | None = None
    address: str | None = None
    metadata: dict[str, Any] | None = None


class CustomerResponse(BaseModel):
    id: str
    full_name: str
    phone: str | None = None
    email: str | None = None
    national_id: str | None = None
    date_of_birth: str | None = None
    address: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CustomerSearchMatch(CustomerResponse):
    match_score: int = Field(..., ge=0, le=100)


class CustomerSearchResponse(BaseModel):
    matches: list[CustomerSearchMatch] = Field(default_factory=list)


class LoanProfileCreateRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    loan_amount: float = Field(..., gt=0)
    loan_purpose: str = Field(..., min_length=1)
    term_months: int = Field(..., gt=0, le=360)
    product_type: str | None = None
    currency: str = Field(default="VND", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoanProfileResponse(BaseModel):
    id: str
    customer_id: str
    loan_amount: float
    loan_purpose: str
    term_months: int
    product_type: str | None = None
    currency: str = "VND"
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class UploadedDocumentResponse(BaseModel):
    id: str
    loan_profile_id: str
    category: str
    file_name: str
    file_path: str
    content_type: str | None = None
    size_bytes: int = Field(..., ge=0)
    doc_type: str | None = None
    description: str | None = None
    status: str
    created_at: datetime


class FinancialReportResponse(UploadedDocumentResponse):
    report_period: str | None = None
    declared_revenue: float | None = None
    declared_expense: float | None = None
    declared_monthly_income: float | None = None


class CollateralResponse(UploadedDocumentResponse):
    collateral_type: str | None = None
    estimated_value: float | None = None
    currency: str = "VND"


class CheckIssue(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "critical"] = "warning"


class CheckLegalDocsRequest(BaseModel):
    required_doc_types: list[str] = Field(
        default_factory=lambda: ["identity", "income", "residence"]
    )
    notes: str | None = None


class CheckRequest(BaseModel):
    notes: str | None = None


class CheckResultResponse(BaseModel):
    id: str
    loan_profile_id: str
    check_type: str
    status: CheckStatus
    score: float = Field(..., ge=0, le=100)
    issues: list[CheckIssue] = Field(default_factory=list)
    recommendation: str
    notes: str | None = None
    created_at: datetime


class ComplianceResultRequest(BaseModel):
    decision: ComplianceDecision
    score: float | None = Field(default=None, ge=0, le=100)
    notes: str | None = None
    conditions: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ComplianceResultResponse(BaseModel):
    id: str
    loan_profile_id: str
    decision: ComplianceDecision
    score: float | None = None
    notes: str | None = None
    conditions: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class CaseStatusUpdateRequest(BaseModel):
    status: str = Field(..., min_length=1)
    notes: str | None = None


class CaseStatusResponse(BaseModel):
    loan_profile_id: str
    status: str
    notes: str | None = None
    updated_at: datetime


class ChecklistItemInput(BaseModel):
    title: str = Field(..., min_length=1)
    status: str = "pending"
    owner_agent: str | None = None
    category: str | None = None
    points: int | None = Field(default=None, ge=0)
    required: bool = False
    reason: str | None = None


class ChecklistCreateRequest(BaseModel):
    items: list[ChecklistItemInput] = Field(default_factory=list)
    notes: str | None = None


class ChecklistItemResponse(BaseModel):
    id: str
    title: str
    status: str
    owner_agent: str | None = None
    category: str | None = None
    points: int | None = None
    required: bool = False
    reason: str | None = None


class ChecklistResponse(BaseModel):
    id: str
    loan_profile_id: str
    items: list[ChecklistItemResponse]
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class LoanLimitCalculationRequest(BaseModel):
    total_capital_need: float = Field(..., gt=0)
    collateral_value: float = Field(..., gt=0)
    ltv_ratio: float = Field(..., gt=0, le=1)
    dscr: float = Field(..., ge=0)
    checklist_score: int = Field(..., ge=0, le=100)
    hard_stop: bool = False


class LoanLimitCalculationResponse(BaseModel):
    id: str
    loan_profile_id: str
    requested_amount: float
    capital_need_limit: float
    collateral_limit: float
    calculated_limit: float
    dscr_factor: float
    checklist_factor: float
    final_factor: float
    recommended_limit: float
    currency: str
    assumptions: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str | None = None
    assignee_agent: str | None = None
    priority: TaskPriority = "medium"
    due_date: str | None = None


class TaskResponse(BaseModel):
    id: str
    loan_profile_id: str
    title: str
    description: str | None = None
    assignee_agent: str | None = None
    priority: TaskPriority
    due_date: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class ReportCreateRequest(BaseModel):
    report_type: str = Field(default="case_summary", min_length=1)
    title: str | None = None
    summary: str | None = None


class ReportResponse(BaseModel):
    id: str
    loan_profile_id: str
    report_type: str
    title: str
    summary: str
    report_body: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ReportsListResponse(BaseModel):
    total_count: int = Field(..., ge=0)
    reports: list[ReportResponse] = Field(default_factory=list)


class DossierIgnoredFile(BaseModel):
    source_path: str
    original_filename: str | None = None
    file_type: str | None = None
    reason: str


class DossierDocumentRecord(BaseModel):
    file_id: str
    original_filename: str
    normalized_filename: str
    source_path: str
    file_type: str
    file_ref: str
    content_type: str | None = None
    size_bytes: int = Field(..., ge=0)
    checksum_sha256: str
    status: str
    detected_document_type: str | None = None
    business_group: str | None = None
    target_agents: list[DossierAgentName] = Field(default_factory=list)
    confidence: float = Field(default=0, ge=0, le=1)
    classification_source: str | None = None
    needs_review: bool = False
    needs_agent_confirm: bool = False
    reason: str | None = None


class DossierAgentFile(BaseModel):
    file_id: str
    file_ref: str
    original_filename: str
    source_path: str
    detected_document_type: str | None = None
    business_group: str | None = None
    confidence: float = Field(default=0, ge=0, le=1)
    needs_agent_confirm: bool = False
    reason: str | None = None


class DossierAgentPackage(BaseModel):
    agent_name: DossierAgentName
    file_count: int = Field(..., ge=0)
    package_reason: str
    files: list[DossierAgentFile] = Field(default_factory=list)


class DossierRoutingTraceEntry(BaseModel):
    file_id: str | None = None
    source_path: str
    stage: str
    decision: str
    reason: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class DossierDispatchRequest(BaseModel):
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class DossierAgentDispatchPayload(BaseModel):
    dossier_id: str
    routing_batch_id: str
    agent_name: DossierAgentName
    file_count: int = Field(..., ge=0)
    package_reason: str
    files: list[DossierAgentFile] = Field(default_factory=list)
    scope_note: list[str] = Field(default_factory=list)
    created_at: datetime


class DossierAgentDispatchResult(BaseModel):
    agent_name: DossierAgentName
    status: DossierAgentDispatchStatus
    file_count: int = Field(..., ge=0)
    routing_batch_id: str
    dispatched_at: datetime | None = None
    message: str
    payload: DossierAgentDispatchPayload | None = None


class DossierAssessmentSnapshot(BaseModel):
    status: DossierAssessmentStatus
    trace_id: str | None = None
    overall_result: Literal[
        "READY", "REVIEW_REQUIRED", "BLOCKED", "UNDETERMINED"
    ] | None = None
    stopped_after: str | None = None
    stop_reason: str | None = None
    result: dict[str, Any] | None = None
    error_type: str | None = None
    created_at: datetime
    updated_at: datetime


class DossierDispatchSnapshot(BaseModel):
    routing_batch_id: str
    idempotency_key: str | None = None
    routing_status: DossierRoutingStatus
    message: str
    agent_dispatches: list[DossierAgentDispatchResult] = Field(default_factory=list)
    assessment: DossierAssessmentSnapshot | None = None
    created_at: datetime
    updated_at: datetime


class DossierDispatchResponse(BaseModel):
    id: str | None = None
    dossier_id: str
    routing_status: DossierRoutingStatus
    routing_batch_id: str
    message: str
    agent_dispatches: list[DossierAgentDispatchResult] = Field(default_factory=list)
    assessment: DossierAssessmentSnapshot | None = None
    agent_packages: list[DossierAgentPackage] = Field(default_factory=list)
    needs_review_count: int = Field(..., ge=0)
    needs_review_files: list[DossierDocumentRecord] = Field(default_factory=list)
    ignored_files_count: int = Field(..., ge=0)
    ignored_files: list[DossierIgnoredFile] = Field(default_factory=list)
    routing_trace: list[DossierRoutingTraceEntry] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DossierRoutingResponse(BaseModel):
    id: str | None = None
    dossier_id: str
    routing_status: DossierRoutingStatus
    routing_batch_id: str | None = None
    dispatch_message: str | None = None
    received_files_count: int = Field(..., ge=0)
    accepted_files_count: int = Field(..., ge=0)
    ignored_files_count: int = Field(..., ge=0)
    needs_review_count: int = Field(..., ge=0)
    document_registry: list[DossierDocumentRecord] = Field(default_factory=list)
    agent_packages: list[DossierAgentPackage] = Field(default_factory=list)
    needs_review_files: list[DossierDocumentRecord] = Field(default_factory=list)
    ignored_files: list[DossierIgnoredFile] = Field(default_factory=list)
    routing_trace: list[DossierRoutingTraceEntry] = Field(default_factory=list)
    latest_dispatch: DossierDispatchSnapshot | None = None
    created_at: datetime
    updated_at: datetime
