from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.loan_agent import (
    CaseStatusResponse,
    CaseStatusUpdateRequest,
    CheckLegalDocsRequest,
    CheckRequest,
    CheckResultResponse,
    ChecklistCreateRequest,
    ChecklistItemInput,
    ChecklistResponse,
    ComplianceResultRequest,
    ComplianceResultResponse,
    CustomerCreateRequest,
    CustomerResponse,
    CustomerSearchResponse,
    CustomerUpdateRequest,
    LoanProfileCreateRequest,
    LoanProfileResponse,
    LoanLimitCalculationRequest,
    LoanLimitCalculationResponse,
    ReportCreateRequest,
    ReportResponse,
    ReportsListResponse,
    TaskCreateRequest,
    TaskResponse,
)
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.loan_agent_service import LoanAgentService


RAGDomain = Literal["credit", "compliance", "operations"]
CaseStatus = Literal["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S11"]
RAG_USER_ENV_BY_DOMAIN = {
    "credit": "RAG_MCP_CREDIT_USER_ID",
    "compliance": "RAG_MCP_COMPLIANCE_USER_ID",
    "operations": "RAG_MCP_OPERATIONS_USER_ID",
}


class KnowledgeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    page: str | None = None
    excerpt: str = Field(min_length=1)


class KnowledgeEvidenceEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence: list[KnowledgeEvidence]


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


def resolve_domain_user_id(
    domain: str,
    environ: Mapping[str, str] = os.environ,
) -> str:
    env_name = RAG_USER_ENV_BY_DOMAIN.get(domain)
    if env_name is None:
        raise ValueError("Unsupported RAG domain")
    value = environ.get(env_name, "")
    if domain == "credit" and not value.strip():
        value = environ.get("RAG_MCP_USER_ID", "")
        env_name = f"{env_name} or RAG_MCP_USER_ID"
    return _required_text(value, env_name)


def _loan_user_id() -> str:
    return _required_text(
        os.getenv("LOAN_DATA_MCP_USER_ID", ""),
        "LOAN_DATA_MCP_USER_ID",
    )


def _chunk_to_evidence(chunk: Any) -> KnowledgeEvidence:
    if not isinstance(chunk, Mapping):
        raise ValueError("Retrieved chunk must be an object")
    raw_page = chunk.get("page_label")
    page = None if raw_page is None else str(raw_page).strip() or None
    excerpt = chunk.get("window") or chunk.get("text")
    return KnowledgeEvidence(
        source_id=_required_text(chunk.get("chunk_id"), "chunk_id"),
        file_name=_required_text(chunk.get("file_name"), "file_name"),
        page=page,
        excerpt=_required_text(excerpt, "window or text"),
    )


async def retrieve_evidence(
    domain: str,
    query: str,
    top_k: int,
    *,
    user_id: str,
    service: KnowledgeBaseService,
) -> KnowledgeEvidenceEnvelope:
    if domain not in RAG_USER_ENV_BY_DOMAIN:
        raise ValueError("Unsupported RAG domain")
    normalized_query = _required_text(query, "query")
    if type(top_k) is not int or top_k != 5:
        raise ValueError("search_knowledge top_k must be 5")
    normalized_user_id = _required_text(user_id, "user_id")

    try:
        result = await asyncio.to_thread(
            service.retrieve_chunks,
            normalized_query,
            user_id=normalized_user_id,
        )
    except Exception:
        raise RuntimeError("Knowledge retrieval failed") from None

    chunks = result.get("chunks") if isinstance(result, Mapping) else None
    if not isinstance(chunks, list):
        raise ValueError("RAG retrieval returned an invalid chunk list")
    evidence = [_chunk_to_evidence(chunk) for chunk in chunks[:top_k]]
    if not evidence:
        raise ValueError("RAG retrieval returned no evidence")
    source_ids = [item.source_id for item in evidence]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Duplicate evidence source_id")
    return KnowledgeEvidenceEnvelope(evidence=evidence)


async def retrieve_document_page(
    domain: str,
    source_id: str,
    *,
    user_id: str,
    service: KnowledgeBaseService,
) -> KnowledgeEvidenceEnvelope:
    if domain not in RAG_USER_ENV_BY_DOMAIN:
        raise ValueError("Unsupported RAG domain")
    normalized_source_id = _required_text(source_id, "source_id")
    normalized_user_id = _required_text(user_id, "user_id")

    try:
        chunk = await asyncio.to_thread(
            service.get_chunk_detail,
            normalized_source_id,
            user_id=normalized_user_id,
        )
        metadata = chunk.metadata
        if not isinstance(metadata, Mapping):
            raise ValueError("Chunk metadata must be an object")
        normalized_file_name = _required_text(metadata.get("file_name"), "file_name")
        normalized_page = _required_text(metadata.get("page_label"), "page_label")
        result = await asyncio.to_thread(
            service.get_document_text,
            normalized_file_name,
            page_label=normalized_page,
            user_id=normalized_user_id,
        )
    except Exception:
        raise RuntimeError("Document page retrieval failed") from None

    result_file_name = _required_text(result.document_path, "document_path")
    result_page = _required_text(result.page_label, "page_label")
    if (result_file_name, result_page) != (normalized_file_name, normalized_page):
        raise ValueError("RAG returned a different document page")
    return KnowledgeEvidenceEnvelope(
        evidence=[
            KnowledgeEvidence(
                source_id=f"page:{normalized_source_id}",
                file_name=result_file_name,
                page=result_page,
                excerpt=_required_text(result.text, "page text"),
            )
        ]
    )


knowledge_base_service = KnowledgeBaseService()
loan_agent_service = LoanAgentService()
mcp = FastMCP(
    "agent-bank-tools",
    host=os.getenv("RAG_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("RAG_MCP_PORT", "8766")),
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
)


@mcp.tool(structured_output=True)
async def search_knowledge(
    domain: RAGDomain,
    query: str,
    top_k: int = 5,
) -> KnowledgeEvidenceEnvelope:
    """Retrieve grounded evidence from one agent policy knowledge base."""
    return await retrieve_evidence(
        domain,
        query,
        top_k,
        user_id=resolve_domain_user_id(domain),
        service=knowledge_base_service,
    )


@mcp.tool(structured_output=True)
async def get_document_page(
    domain: RAGDomain,
    source_id: str,
) -> KnowledgeEvidenceEnvelope:
    """Read the full indexed page for evidence returned by search_knowledge."""
    return await retrieve_document_page(
        domain,
        source_id,
        user_id=resolve_domain_user_id(domain),
        service=knowledge_base_service,
    )


@mcp.tool(structured_output=True)
async def get_loan_profile(loan_profile_id: str) -> LoanProfileResponse:
    """Read one persisted loan profile from the authenticated MCP user scope."""
    normalized_id = _required_text(loan_profile_id, "loan_profile_id")
    user_id = _loan_user_id()
    try:
        return await loan_agent_service.get_loan_profile(
            user_id=user_id,
            loan_profile_id=normalized_id,
        )
    except Exception:
        raise RuntimeError("Loan profile retrieval failed") from None


@mcp.tool(structured_output=True)
async def get_customer(customer_id: str) -> CustomerResponse:
    """Read one customer referenced by a persisted loan profile."""
    normalized_id = _required_text(customer_id, "customer_id")
    user_id = _loan_user_id()
    try:
        return await loan_agent_service.get_customer(
            user_id=user_id,
            customer_id=normalized_id,
        )
    except Exception:
        raise RuntimeError("Customer retrieval failed") from None


@mcp.tool(structured_output=True)
async def list_reports(loan_profile_id: str) -> ReportsListResponse:
    """List existing case reports without creating or updating case data."""
    normalized_id = _required_text(loan_profile_id, "loan_profile_id")
    user_id = _loan_user_id()
    try:
        return await loan_agent_service.list_reports(
            user_id=user_id,
            loan_profile_id=normalized_id,
        )
    except Exception:
        raise RuntimeError("Loan report retrieval failed") from None


@mcp.tool(structured_output=True)
async def search_customer(
    full_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    national_id: str | None = None,
    tax_code: str | None = None,
    address: str | None = None,
) -> CustomerSearchResponse:
    """Find possible duplicate customers in the persisted loan-data scope."""
    try:
        return await loan_agent_service.search_customers(
            user_id=_loan_user_id(),
            full_name=full_name,
            phone=phone,
            email=email,
            national_id=national_id,
            tax_code=tax_code,
            address=address,
        )
    except Exception:
        raise RuntimeError("Customer search failed") from None


@mcp.tool(structured_output=True)
async def create_customer(
    full_name: str,
    phone: str | None = None,
    email: str | None = None,
    national_id: str | None = None,
    address: str | None = None,
    customer_type: str | None = None,
    tax_code: str | None = None,
) -> CustomerResponse:
    """Create a customer after duplicate checks have completed."""
    metadata = {
        key: value
        for key, value in {"customer_type": customer_type, "tax_code": tax_code}.items()
        if value is not None
    }
    try:
        return await loan_agent_service.create_customer(
            user_id=_loan_user_id(),
            payload=CustomerCreateRequest(
                full_name=full_name,
                phone=phone,
                email=email,
                national_id=national_id,
                address=address,
                metadata=metadata,
            ),
        )
    except Exception:
        raise RuntimeError("Customer creation failed") from None


@mcp.tool(structured_output=True)
async def update_customer(
    customer_id: str,
    full_name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    national_id: str | None = None,
    address: str | None = None,
    customer_type: str | None = None,
    tax_code: str | None = None,
) -> CustomerResponse:
    """Update one confirmed customer without replacing unrelated metadata."""
    metadata = {
        key: value
        for key, value in {"customer_type": customer_type, "tax_code": tax_code}.items()
        if value is not None
    }
    try:
        return await loan_agent_service.update_customer(
            user_id=_loan_user_id(),
            customer_id=_required_text(customer_id, "customer_id"),
            payload=CustomerUpdateRequest(
                full_name=full_name,
                phone=phone,
                email=email,
                national_id=national_id,
                address=address,
                metadata=metadata or None,
            ),
        )
    except Exception:
        raise RuntimeError("Customer update failed") from None


@mcp.tool(structured_output=True)
async def create_loan_profile(
    customer_id: str,
    loan_amount: float,
    loan_purpose: str,
    term_months: int,
    product_type: str | None = None,
    currency: str = "VND",
    metadata: dict[str, Any] | None = None,
) -> LoanProfileResponse:
    """Create a draft loan profile for a confirmed customer."""
    try:
        return await loan_agent_service.create_loan_profile(
            user_id=_loan_user_id(),
            payload=LoanProfileCreateRequest(
                customer_id=customer_id,
                loan_amount=loan_amount,
                loan_purpose=loan_purpose,
                term_months=term_months,
                product_type=product_type,
                currency=currency,
                metadata=metadata or {},
            ),
        )
    except Exception:
        raise RuntimeError("Loan profile creation failed") from None


@mcp.tool(structured_output=True)
async def check_legal_docs(
    loan_profile_id: str,
    required_doc_types: list[str],
    notes: str | None = None,
) -> CheckResultResponse:
    """Persist the legal-document checklist for an existing loan profile."""
    request = CheckLegalDocsRequest(required_doc_types=required_doc_types, notes=notes)
    try:
        return await loan_agent_service.check_legal_docs(
            user_id=_loan_user_id(),
            loan_profile_id=_required_text(loan_profile_id, "loan_profile_id"),
            required_doc_types=request.required_doc_types,
            notes=request.notes,
        )
    except Exception:
        raise RuntimeError("Legal document check failed") from None


@mcp.tool(structured_output=True)
async def check_financials(
    loan_profile_id: str,
    notes: str | None = None,
) -> CheckResultResponse:
    """Persist the financial-document check for a loan profile."""
    try:
        return await loan_agent_service.check_financials(
            user_id=_loan_user_id(),
            loan_profile_id=_required_text(loan_profile_id, "loan_profile_id"),
            notes=CheckRequest(notes=notes).notes,
        )
    except Exception:
        raise RuntimeError("Financial check failed") from None


@mcp.tool(structured_output=True)
async def check_collateral(
    loan_profile_id: str,
    notes: str | None = None,
) -> CheckResultResponse:
    """Persist the collateral check for a loan profile."""
    try:
        return await loan_agent_service.check_collateral(
            user_id=_loan_user_id(),
            loan_profile_id=_required_text(loan_profile_id, "loan_profile_id"),
            notes=CheckRequest(notes=notes).notes,
        )
    except Exception:
        raise RuntimeError("Collateral check failed") from None


@mcp.tool(structured_output=True)
async def check_credit_rule(
    loan_profile_id: str,
    notes: str | None = None,
) -> CheckResultResponse:
    """Persist the credit-rule check for a loan profile."""
    try:
        return await loan_agent_service.check_credit_rule(
            user_id=_loan_user_id(),
            loan_profile_id=_required_text(loan_profile_id, "loan_profile_id"),
            notes=CheckRequest(notes=notes).notes,
        )
    except Exception:
        raise RuntimeError("Credit-rule check failed") from None


@mcp.tool(structured_output=True)
async def save_compliance_result(
    loan_profile_id: str,
    decision: Literal["approved", "conditional", "rejected", "needs_review"],
    score: float | None = None,
    notes: str | None = None,
    conditions: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> ComplianceResultResponse:
    """Save the completed Compliance Agent assessment."""
    try:
        return await loan_agent_service.save_compliance_result(
            user_id=_loan_user_id(),
            loan_profile_id=_required_text(loan_profile_id, "loan_profile_id"),
            payload=ComplianceResultRequest(
                decision=decision,
                score=score,
                notes=notes,
                conditions=conditions or [],
                details=details or {},
            ),
        )
    except Exception:
        raise RuntimeError("Compliance result save failed") from None


@mcp.tool(structured_output=True)
async def update_case_status(
    loan_profile_id: str,
    status: CaseStatus,
    notes: str | None = None,
) -> CaseStatusResponse:
    """Update one loan profile to an Operations Agent status."""
    try:
        return await loan_agent_service.update_case_status(
            user_id=_loan_user_id(),
            loan_profile_id=_required_text(loan_profile_id, "loan_profile_id"),
            payload=CaseStatusUpdateRequest(status=status, notes=notes),
        )
    except Exception:
        raise RuntimeError("Case status update failed") from None


@mcp.tool(structured_output=True)
async def create_checklist(
    loan_profile_id: str,
    items: list[dict[str, Any]] | None = None,
    notes: str | None = None,
) -> ChecklistResponse:
    """Create the scored operational checklist for a loan profile."""
    try:
        payload = ChecklistCreateRequest(
            items=[ChecklistItemInput.model_validate(item) for item in items or []],
            notes=notes,
        )
        return await loan_agent_service.create_checklist(
            user_id=_loan_user_id(),
            loan_profile_id=_required_text(loan_profile_id, "loan_profile_id"),
            payload=payload,
        )
    except Exception:
        raise RuntimeError("Checklist creation failed") from None


@mcp.tool(structured_output=True)
async def calculate_loan_limit(
    loan_profile_id: str,
    total_capital_need: float,
    collateral_value: float,
    ltv_ratio: float,
    dscr: float,
    checklist_score: int,
    hard_stop: bool,
) -> LoanLimitCalculationResponse:
    """Calculate and persist the demo Operations Agent loan limit."""
    try:
        return await loan_agent_service.calculate_loan_limit(
            user_id=_loan_user_id(),
            loan_profile_id=_required_text(loan_profile_id, "loan_profile_id"),
            payload=LoanLimitCalculationRequest(
                total_capital_need=total_capital_need,
                collateral_value=collateral_value,
                ltv_ratio=ltv_ratio,
                dscr=dscr,
                checklist_score=checklist_score,
                hard_stop=hard_stop,
            ),
        )
    except Exception:
        raise RuntimeError("Loan limit calculation failed") from None


@mcp.tool(structured_output=True)
async def create_task(
    loan_profile_id: str,
    title: str,
    priority: Literal["low", "medium", "high", "urgent", "P1", "P2", "P3"],
    description: str | None = None,
    assignee_agent: str | None = None,
    due_date: str | None = None,
) -> TaskResponse:
    """Create one operational ticket or task."""
    try:
        return await loan_agent_service.create_task(
            user_id=_loan_user_id(),
            loan_profile_id=_required_text(loan_profile_id, "loan_profile_id"),
            payload=TaskCreateRequest(
                title=title,
                description=description,
                assignee_agent=assignee_agent,
                priority=priority,
                due_date=due_date,
            ),
        )
    except Exception:
        raise RuntimeError("Task creation failed") from None


@mcp.tool(structured_output=True)
async def create_report(
    loan_profile_id: str,
    report_type: str = "case_summary",
    title: str | None = None,
    summary: str | None = None,
) -> ReportResponse:
    """Create a persisted operational case report."""
    try:
        return await loan_agent_service.create_report(
            user_id=_loan_user_id(),
            loan_profile_id=_required_text(loan_profile_id, "loan_profile_id"),
            payload=ReportCreateRequest(
                report_type=report_type,
                title=title,
                summary=summary,
            ),
        )
    except Exception:
        raise RuntimeError("Report creation failed") from None


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
