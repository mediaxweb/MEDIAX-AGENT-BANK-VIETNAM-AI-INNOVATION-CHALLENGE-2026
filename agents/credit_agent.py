from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from pathlib import Path
from typing import Literal, TypeAlias

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_agent_support import (
    DomainRAGRunHooks,
    ExecutionMode,
    KnowledgeEvidence,
    assert_expected_agent_tools,
    build_agent_mcp_server,
    build_agent_run_config,
    evidence_by_id,
    extract_called_tool_names,
    extract_trusted_evidence,
    mutating_tool_names,
)


RATIO_QUANTUM = Decimal("0.0001")
DEFAULT_RAG_MCP_URL = "http://127.0.0.1:8766/mcp"
DEFAULT_MODEL = "gpt-5.4-mini"
CustomerType = Literal["individual", "household_business", "enterprise"]
CreditResult = Literal["PASSED", "CONDITIONAL", "FAILED", "UNDETERMINED"]
logger = logging.getLogger(__name__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class CustomerInformation(StrictModel):
    customer_type: CustomerType
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    national_id: str | None = None
    tax_code: str | None = None
    address: str | None = None
    industry: str | None = None
    occupation: str | None = None
    years_operating: int | None = Field(default=None, ge=0)
    internal_customer_id: str | None = None
    legal_representative_name: str | None = None
    legal_representative_id: str | None = None


class SignerInformation(StrictModel):
    name: str | None = None
    signed: bool = False
    is_customer_or_legal_representative: bool = False
    has_valid_authorization: bool = False
    authorized_person_id_present: bool = False


class LoanRequest(StrictModel):
    requested_amount: Decimal = Field(ge=0)
    term_months: int = Field(ge=0, le=360)
    purpose: str | None = None
    repayment_method: str | None = None
    total_capital_need: Decimal | None = Field(default=None, gt=0)
    own_capital: Decimal | None = Field(default=None, ge=0)
    supporting_document_value: Decimal | None = Field(default=None, ge=0)
    repayment_source: str | None = None
    capital_needed_at: str | None = None
    purchase_description: str | None = None


class CreditDocument(StrictModel):
    document_type: str = Field(min_length=1)
    status: Literal["provided", "missing", "not_applicable"] = "missing"
    valid: bool = True
    readable: bool = True
    complete: bool = True
    format_valid: bool = True
    suspicious_alteration: bool = False


class ConsistencyChecks(StrictModel):
    customer_name_matches: bool = True
    tax_code_matches: bool = True
    representative_matches: bool = True
    industry_matches_purpose: bool = True


class CreditApplication(StrictModel):
    case_id: str = Field(min_length=1)
    loan_profile_id: str | None = Field(default=None, min_length=1)
    execution_mode: ExecutionMode = "assess"
    customer: CustomerInformation
    signer: SignerInformation
    loan: LoanRequest
    documents: list[CreditDocument] = Field(default_factory=list)
    consistency: ConsistencyChecks = Field(default_factory=ConsistencyChecks)

    @model_validator(mode="after")
    def validate_unique_documents(self):
        names = [item.document_type.casefold() for item in self.documents]
        if len(names) != len(set(names)):
            raise ValueError("document_type values must be unique")
        return self


class CreditFacts(StrictModel):
    score_breakdown: dict[str, int]
    legal_score: int = Field(ge=0, le=100)
    result: CreditResult
    hard_stop_reasons: list[str]
    missing_documents: list[str]
    required_actions: list[str]
    own_capital_ratio: str | None = None
    loan_to_capital_need_ratio: str | None = None
    supporting_document_ratio: str | None = None
    max_amount_by_capital_need: Decimal | None = None
    can_create_loan_profile: bool
    can_forward_to_compliance: bool


class CustomerMatch(StrictModel):
    customer_id: str | None = None
    score: int = Field(ge=0, le=100)
    action: Literal["reuse", "verify", "create"]


class CreditFinding(StrictModel):
    summary: str = Field(min_length=1)
    severity: Literal["info", "warning", "critical"]
    evidence_ids: list[str] = Field(min_length=1)


class CreditDecisionDraft(StrictModel):
    customer_match: CustomerMatch
    findings: list[CreditFinding] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    executed_actions: list[str] = Field(default_factory=list)
    created_customer_id: str | None = None
    created_loan_profile_id: str | None = None
    missing_data: list[str] = Field(default_factory=list)
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)


class CreditDecisionExecution(StrictModel):
    draft: CreditDecisionDraft
    trusted_evidence: list[KnowledgeEvidence]


class CreditAssessment(StrictModel):
    case_id: str
    customer_type: CustomerType
    loan_profile_id: str | None = None
    facts: CreditFacts
    customer_match: CustomerMatch | None = None
    findings: list[CreditFinding]
    required_actions: list[str]
    executed_actions: list[str]
    missing_data: list[str]
    evidence: list[KnowledgeEvidence]


def _document_map(application: CreditApplication) -> dict[str, CreditDocument]:
    return {item.document_type.casefold(): item for item in application.documents}


def _is_present(documents: dict[str, CreditDocument], document_type: str) -> bool:
    item = documents.get(document_type)
    return bool(
        item
        and item.status in {"provided", "not_applicable"}
        and item.valid
        and item.readable
        and not item.suspicious_alteration
    )


def _score_document(
    documents: dict[str, CreditDocument],
    document_type: str,
    points: int,
) -> int:
    return points if _is_present(documents, document_type) else 0


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> str | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    try:
        return str((numerator / denominator).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP))
    except DecimalException:
        return None


def _enterprise_score(
    application: CreditApplication,
    documents: dict[str, CreditDocument],
) -> dict[str, int]:
    customer = application.customer
    signer = application.signer
    identity = sum(
        (
            5 if customer.full_name else 0,
            5 if customer.tax_code else 0,
            3 if customer.address else 0,
            4 if customer.industry else 0,
            3 if customer.phone or customer.email else 0,
            5,  # Internal customer ID is conditional and therefore neutral when absent.
        )
    )
    legal = sum(
        (
            _score_document(documents, "business_registration", 12),
            _score_document(documents, "company_charter", 8),
            _score_document(documents, "appointment_decision", 5),
            _score_document(documents, "shareholders_information", 3),
            _score_document(documents, "signature_sample", 2),
        )
    )
    signer_score = _score_document(documents, "legal_representative_id", 8)
    if signer.is_customer_or_legal_representative:
        signer_score += 17
    else:
        signer_score += 7 if signer.has_valid_authorization else 0
        signer_score += 3 if signer.authorized_person_id_present else 0
    consistency = sum(
        (
            3 if application.consistency.customer_name_matches else 0,
            3 if application.consistency.tax_code_matches else 0,
            2 if application.consistency.representative_matches else 0,
            2 if application.consistency.industry_matches_purpose else 0,
        )
    )
    return {
        "customer_identity": identity,
        "legal_status": legal,
        "signer_authority": signer_score,
        "consistency": consistency,
        "file_quality": _file_quality_score(application.documents, 10),
    }


def _household_score(
    application: CreditApplication,
    documents: dict[str, CreditDocument],
) -> dict[str, int]:
    customer = application.customer
    checklist = {
        "household_registration": _score_document(documents, "household_registration", 25),
        "owner_identity": _score_document(documents, "owner_identity", 20),
        "business_address": 10 if customer.address else 0,
        "industry": 10 if customer.industry else 0,
        "contact": 5 if customer.phone or customer.email else 0,
        "business_activity_evidence": _score_document(documents, "business_activity_evidence", 15),
        "bank_statements": _score_document(documents, "bank_statements", 10),
        "file_quality": _file_quality_score(application.documents, 5),
    }
    return {"legal_checklist": sum(checklist.values())}


def _individual_score(
    application: CreditApplication,
    documents: dict[str, CreditDocument],
) -> dict[str, int]:
    customer = application.customer
    checklist = {
        "identity": _score_document(documents, "identity", 25),
        "residence": 15 if customer.address else 0,
        "occupation": 15 if customer.occupation else 0,
        "contact": 10 if customer.phone or customer.email else 0,
        "income_evidence": _score_document(documents, "income_evidence", 20),
        "collateral_documents": _score_document(documents, "collateral_documents", 10),
        "file_quality": _file_quality_score(application.documents, 5),
    }
    return {"legal_checklist": sum(checklist.values())}


def _file_quality_score(documents: list[CreditDocument], maximum: int) -> int:
    provided = [item for item in documents if item.status == "provided"]
    if not provided:
        return 0
    checks = (
        all(item.readable for item in provided),
        all(item.complete for item in provided),
        all(item.format_valid for item in provided),
        all(not item.suspicious_alteration for item in provided),
    )
    weights = (4, 3, 2, 1) if maximum == 10 else (2, 1, 1, 1)
    return sum(weight for passed, weight in zip(checks, weights) if passed)


def _hard_stops(
    application: CreditApplication,
    documents: dict[str, CreditDocument],
) -> list[str]:
    customer = application.customer
    signer = application.signer
    reasons: list[str] = []
    if not customer.full_name:
        reasons.append("missing_customer_name")
    if application.loan.requested_amount <= 0:
        reasons.append("invalid_requested_amount")
    if not signer.signed:
        reasons.append("missing_loan_request_signature")
    if not application.loan.repayment_source:
        reasons.append("missing_repayment_source")
    if not application.consistency.customer_name_matches:
        reasons.append("customer_name_mismatch")
    if not signer.is_customer_or_legal_representative and not signer.has_valid_authorization:
        reasons.append("unauthorized_signer")
    if any(
        item.status == "provided"
        and (not item.valid or not item.readable or item.suspicious_alteration)
        for item in application.documents
    ):
        reasons.append("invalid_or_suspicious_legal_document")

    if customer.customer_type == "enterprise":
        if not customer.tax_code:
            reasons.append("missing_tax_code")
        if not customer.legal_representative_name or not customer.legal_representative_id:
            reasons.append("missing_legal_representative")
        if not _is_present(documents, "business_registration"):
            reasons.append("missing_business_registration")
        if not _is_present(documents, "legal_representative_id"):
            reasons.append("missing_legal_representative_id")
        if not application.consistency.tax_code_matches:
            reasons.append("tax_code_mismatch")
    elif customer.customer_type == "household_business":
        if not customer.national_id:
            reasons.append("missing_owner_identity")
        if not _is_present(documents, "household_registration"):
            reasons.append("missing_household_registration")
        if not _is_present(documents, "owner_identity"):
            reasons.append("missing_owner_identity_document")
        if not application.consistency.industry_matches_purpose:
            reasons.append("industry_mismatch")
    else:
        if not customer.national_id:
            reasons.append("missing_identity")
        if not _is_present(documents, "identity"):
            reasons.append("missing_identity_document")
    return sorted(set(reasons))


def calculate_credit_facts(application: CreditApplication) -> CreditFacts:
    documents = _document_map(application)
    if application.customer.customer_type == "enterprise":
        score_breakdown = _enterprise_score(application, documents)
    elif application.customer.customer_type == "household_business":
        score_breakdown = _household_score(application, documents)
    else:
        score_breakdown = _individual_score(application, documents)
    legal_score = min(sum(score_breakdown.values()), 100)
    hard_stops = _hard_stops(application, documents)
    missing_documents = sorted(
        item.document_type for item in application.documents if item.status == "missing"
    )

    loan = application.loan
    own_capital_ratio = _ratio(loan.own_capital, loan.total_capital_need)
    loan_ratio = _ratio(loan.requested_amount, loan.total_capital_need)
    supporting_ratio = _ratio(loan.supporting_document_value, loan.requested_amount)
    max_by_capital = (
        (loan.total_capital_need * Decimal("0.80")).quantize(Decimal("0.01"))
        if loan.total_capital_need is not None
        else None
    )
    required_actions: list[str] = [f"resolve:{reason}" for reason in hard_stops]
    required_actions.extend(f"provide:{item}" for item in missing_documents)
    if own_capital_ratio is not None and Decimal(own_capital_ratio) < Decimal("0.20"):
        required_actions.append("increase_own_capital_or_reduce_requested_amount")
    if loan_ratio is not None and Decimal(loan_ratio) > Decimal("0.80"):
        required_actions.append("reduce_requested_amount_to_80_percent_of_capital_need")
    if supporting_ratio is not None and Decimal(supporting_ratio) < Decimal("0.70"):
        required_actions.append("provide_more_supporting_documents")
    if application.customer.years_operating is not None and application.customer.years_operating < 1:
        required_actions.append("verify_operating_history")
    if not application.consistency.industry_matches_purpose:
        required_actions.append("verify_loan_purpose_against_business_activity")
    if not loan.purpose:
        required_actions.append("provide_loan_purpose")
    if loan.term_months <= 0:
        required_actions.append("provide_valid_term")

    core_loan_ready = bool(loan.purpose and loan.term_months > 0)
    can_create = not hard_stops and legal_score >= 75 and core_loan_ready
    can_forward = can_create
    if hard_stops or legal_score < 50:
        result: CreditResult = "FAILED"
    elif required_actions or legal_score < 90:
        result = "CONDITIONAL"
    else:
        result = "PASSED"
    return CreditFacts(
        score_breakdown=score_breakdown,
        legal_score=legal_score,
        result=result,
        hard_stop_reasons=hard_stops,
        missing_documents=missing_documents,
        required_actions=sorted(set(required_actions)),
        own_capital_ratio=own_capital_ratio,
        loan_to_capital_need_ratio=loan_ratio,
        supporting_document_ratio=supporting_ratio,
        max_amount_by_capital_need=max_by_capital,
        can_create_loan_profile=can_create,
        can_forward_to_compliance=can_forward,
    )


def fail_closed_assessment(
    application: CreditApplication,
    facts: CreditFacts,
    missing_data: list[str],
) -> CreditAssessment:
    closed_facts = facts.model_copy(
        update={
            "result": "UNDETERMINED",
            "can_create_loan_profile": False,
            "can_forward_to_compliance": False,
        }
    )
    return CreditAssessment(
        case_id=application.case_id,
        customer_type=application.customer.customer_type,
        loan_profile_id=application.loan_profile_id,
        facts=closed_facts,
        findings=[],
        required_actions=facts.required_actions,
        executed_actions=[],
        missing_data=sorted(set(missing_data)),
        evidence=[],
    )


def assemble_credit_assessment(
    application: CreditApplication,
    facts: CreditFacts,
    draft: CreditDecisionDraft,
    trusted_evidence: list[KnowledgeEvidence],
) -> CreditAssessment:
    if not trusted_evidence:
        return fail_closed_assessment(application, facts, ["rag_evidence"])
    trusted_by_id = evidence_by_id(trusted_evidence)
    for source_id, item in evidence_by_id(draft.evidence).items():
        if trusted_by_id.get(source_id) != item:
            raise ValueError(f"Untrusted model evidence: {source_id}")
    referenced_ids = {
        evidence_id for finding in draft.findings for evidence_id in finding.evidence_ids
    }
    unknown_ids = sorted(referenced_ids - trusted_by_id.keys())
    if unknown_ids:
        raise ValueError(f"Unknown evidence ids: {', '.join(unknown_ids)}")
    if draft.missing_data:
        return fail_closed_assessment(application, facts, draft.missing_data)
    if draft.customer_match.score == 100 and (
        draft.customer_match.action != "reuse" or not draft.customer_match.customer_id
    ):
        raise ValueError("A 100% customer match must reuse an existing customer")
    if 50 <= draft.customer_match.score < 100 and draft.customer_match.action != "verify":
        raise ValueError("A 50-99% customer match requires verification")
    if draft.customer_match.score < 50 and draft.customer_match.action != "create":
        raise ValueError("A customer match below 50% may create a new customer")
    if application.execution_mode == "assess" and draft.executed_actions:
        raise ValueError("Assess mode cannot execute actions")
    combined_actions = sorted(set([*facts.required_actions, *draft.required_actions]))
    effective_facts = facts
    if draft.customer_match.action == "verify":
        effective_facts = facts.model_copy(
            update={
                "result": "CONDITIONAL" if facts.result != "FAILED" else "FAILED",
                "can_create_loan_profile": False,
                "can_forward_to_compliance": False,
            }
        )
        combined_actions = sorted(set([*combined_actions, "verify_possible_duplicate_customer"]))
    output_profile_id = draft.created_loan_profile_id or application.loan_profile_id
    return CreditAssessment(
        case_id=application.case_id,
        customer_type=application.customer.customer_type,
        loan_profile_id=output_profile_id,
        facts=effective_facts,
        customer_match=draft.customer_match,
        findings=draft.findings,
        required_actions=combined_actions,
        executed_actions=draft.executed_actions,
        missing_data=[],
        evidence=trusted_evidence,
    )


DecisionExecutor: TypeAlias = Callable[
    [CreditApplication, CreditFacts, str, str],
    Awaitable[CreditDecisionExecution],
]


def build_credit_agent(server: MCPServerStreamableHttp, model: str) -> Agent:
    return Agent(
        name="Credit Agent",
        instructions=(
            "Assess intake and legal readiness for one loan application. Treat supplied facts "
            "as immutable. Search for an existing customer before proposing creation. Before "
            "any policy finding, call search_knowledge with domain='credit' and top_k=5. If a "
            "chunk lacks context, call get_document_page only with its returned source_id. "
            "Use RAG only as policy evidence and cite every finding. In assess mode, only read "
            "data and propose actions. In execute mode, use write tools only when deterministic "
            "facts allow the action; never create a duplicate customer. Never approve or "
            "disburse a loan. executed_actions must list the exact mutating tool names in call "
            "order. Return missing_data when evidence or case data is insufficient."
        ),
        model=model,
        mcp_servers=[server],
        output_type=CreditDecisionDraft,
    )


def build_agent_input(application: CreditApplication, facts: CreditFacts) -> str:
    return json.dumps(
        {
            "application": application.model_dump(mode="json"),
            "deterministic_facts": facts.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )


async def execute_credit_decision(
    application: CreditApplication,
    facts: CreditFacts,
    mcp_url: str,
    model: str,
) -> CreditDecisionExecution:
    async with build_agent_mcp_server(
        mcp_url,
        "credit",
        application.execution_mode,
    ) as server:
        tools = await server.list_tools()
        assert_expected_agent_tools(tools, "credit", application.execution_mode)
        result = await Runner.run(
            build_credit_agent(server, model),
            build_agent_input(application, facts),
            hooks=DomainRAGRunHooks(
                "credit",
                application.loan_profile_id,
                application.execution_mode,
            ),
            run_config=build_agent_run_config(
                "MediaX Credit Agent",
                metadata={"domain": "credit", "execution_mode": application.execution_mode},
            ),
        )
    if not isinstance(result.final_output, CreditDecisionDraft):
        raise TypeError("Credit Agent returned invalid structured output")
    trusted_evidence = extract_trusted_evidence(
        result.new_items,
        domain="credit",
        loan_profile_id=application.loan_profile_id,
        execution_mode=application.execution_mode,
    )
    called_tools = extract_called_tool_names(result.new_items)
    mutations = mutating_tool_names(called_tools)
    if result.final_output.executed_actions != mutations:
        raise ValueError("Credit executed_actions do not match completed MCP mutations")
    if "create_customer" in called_tools and (
        "search_customer" not in called_tools
        or called_tools.index("search_customer") > called_tools.index("create_customer")
    ):
        raise ValueError("create_customer requires a prior search_customer call")
    return CreditDecisionExecution(
        draft=result.final_output,
        trusted_evidence=trusted_evidence,
    )


async def run_credit_assessment(
    application: CreditApplication,
    *,
    mcp_url: str = DEFAULT_RAG_MCP_URL,
    model: str = DEFAULT_MODEL,
    decision_executor: DecisionExecutor | None = None,
) -> CreditAssessment:
    facts = calculate_credit_facts(application)
    try:
        execution = await (decision_executor or execute_credit_decision)(
            application,
            facts,
            mcp_url,
            model,
        )
        return assemble_credit_assessment(
            application,
            facts,
            execution.draft,
            execution.trusted_evidence,
        )
    except Exception as error:
        logger.error("Credit assessment runtime/provenance failure [%s]", type(error).__name__)
        return fail_closed_assessment(application, facts, ["rag_or_agent_runtime"])


def load_application(path: str) -> CreditApplication:
    return CreditApplication.model_validate_json(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MediaX Credit Agent.")
    parser.add_argument("--input", required=True, help="Path to a normalized loan JSON file.")
    parser.add_argument("--mcp-url", default=os.getenv("RAG_MCP_URL", DEFAULT_RAG_MCP_URL))
    parser.add_argument("--model", default=os.getenv("OPENAI_AGENT_MODEL", DEFAULT_MODEL))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required.")
    assessment = asyncio.run(
        run_credit_assessment(
            load_application(args.input),
            mcp_url=args.mcp_url,
            model=args.model,
        )
    )
    print(assessment.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
