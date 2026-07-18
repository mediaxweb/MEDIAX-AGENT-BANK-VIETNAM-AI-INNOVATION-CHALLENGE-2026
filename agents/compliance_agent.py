from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from pathlib import Path
from typing import Literal, TypeAlias

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from pydantic import BaseModel, ConfigDict, Field

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
    log_agent_runtime_failure,
    mutating_tool_names,
)


RATIO_QUANTUM = Decimal("0.0001")
MONEY_QUANTUM = Decimal("0.01")
DEFAULT_RAG_MCP_URL = "http://127.0.0.1:8766/mcp"
DEFAULT_MODEL = "gpt-5.4-mini"
ComplianceResult = Literal["PASSED", "CONDITIONAL", "FAILED", "UNDETERMINED"]
RiskRating = Literal["Low Risk", "Medium Risk", "High Risk", "Very High Risk", "Undetermined"]
logger = logging.getLogger(__name__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class CreditUpstreamResult(StrictModel):
    legal_score: int = Field(ge=0, le=100)
    result: Literal["PASSED", "CONDITIONAL", "FAILED"]
    hard_stop: bool = False
    missing_documents: list[str] = Field(default_factory=list)


class FinancialPeriod(StrictModel):
    period: str = Field(min_length=1)
    revenue: Decimal = Field(ge=0)
    net_profit: Decimal
    total_debt: Decimal = Field(ge=0)
    equity: Decimal
    operating_cash_flow: Decimal | None = None


class FundingPlan(StrictModel):
    total_capital_need: Decimal = Field(gt=0)
    own_capital: Decimal = Field(ge=0)
    supporting_document_value: Decimal = Field(ge=0)
    purpose_fit: Literal["fit", "needs_explanation", "not_allowed"]


class RepaymentPlan(StrictModel):
    available_cash_flow: Decimal | None = None
    annual_debt_service: Decimal | None = Field(default=None, ge=0)
    source_status: Literal["documented", "described", "missing"]
    cash_flow_timing_aligned: bool = True


class CollateralFacts(StrictModel):
    collateral_type: Literal["land_house", "car", "machinery", "inventory", "receivables"]
    value: Decimal = Field(gt=0)
    ownership_status: Literal["valid", "verify", "missing"]
    valuation_date: date | None = None
    dispute_status: Literal["clear", "verify", "disputed"]
    liquidity: Literal["high", "medium", "low"]
    third_party_documents_complete: bool = True


class ComplianceDocuments(StrictModel):
    latest_financial_statement_present: bool = True
    signer_authority: Literal["valid", "verify", "invalid"] = "valid"
    legal_documents: Literal["complete", "minor_missing", "mandatory_missing"] = "complete"
    consistency: Literal["consistent", "minor_mismatch", "major_mismatch"] = "consistent"
    anomaly: Literal["none", "review", "serious"] = "none"


class ScreeningFacts(StrictModel):
    pep: Literal["clear", "pending", "match"] = "clear"
    sanctions: Literal["clear", "pending", "match"] = "clear"
    beneficial_owner: Literal["clear", "pending", "match"] = "clear"


class ComplianceApplication(StrictModel):
    case_id: str = Field(min_length=1)
    loan_profile_id: str = Field(min_length=1)
    execution_mode: ExecutionMode = "assess"
    customer_type: Literal["individual", "household_business", "enterprise"]
    as_of_date: date
    requested_amount: Decimal = Field(gt=0)
    term_months: int = Field(gt=0, le=360)
    purpose: str = Field(min_length=1)
    credit_result: CreditUpstreamResult
    current_financials: FinancialPeriod | None = None
    previous_financials: FinancialPeriod | None = None
    funding_plan: FundingPlan
    repayment_plan: RepaymentPlan
    collateral: CollateralFacts
    documents: ComplianceDocuments = Field(default_factory=ComplianceDocuments)
    screening: ScreeningFacts = Field(default_factory=ScreeningFacts)


class ComplianceMetrics(StrictModel):
    revenue_growth: str | None = None
    net_profit_margin: str | None = None
    debt_to_equity: str | None = None
    dscr: str | None = None
    own_capital_ratio: str
    loan_to_capital_need_ratio: str
    supporting_document_ratio: str
    ltv: str


class ComplianceFacts(StrictModel):
    metrics: ComplianceMetrics
    score_breakdown: dict[str, int]
    total_score: int = Field(ge=0, le=100)
    risk_rating: RiskRating
    result: ComplianceResult
    hard_stop_reasons: list[str]
    conditions: list[str]
    max_loan_by_collateral: Decimal
    dscr_adjusted_limit: Decimal | None = None
    recommended_limit: Decimal | None = None
    final_recommendation: Literal[
        "consider_credit",
        "conditional_review",
        "reduce_limit_or_request_information",
        "not_recommended",
        "undetermined",
    ]


class ComplianceFinding(StrictModel):
    summary: str = Field(min_length=1)
    severity: Literal["info", "warning", "critical"]
    evidence_ids: list[str] = Field(min_length=1)


class ComplianceDecisionDraft(StrictModel):
    findings: list[ComplianceFinding] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    executed_actions: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)


class ComplianceDecisionExecution(StrictModel):
    draft: ComplianceDecisionDraft
    trusted_evidence: list[KnowledgeEvidence]


class ComplianceAssessment(StrictModel):
    case_id: str
    loan_profile_id: str
    facts: ComplianceFacts
    findings: list[ComplianceFinding]
    conditions: list[str]
    executed_actions: list[str]
    missing_data: list[str]
    evidence: list[KnowledgeEvidence]


def _ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    try:
        return (numerator / denominator).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)
    except DecimalException:
        return None


def _financial_scores(
    revenue_growth: Decimal | None,
    margin: Decimal | None,
    debt_to_equity: Decimal | None,
    dscr: Decimal | None,
) -> int:
    growth_score = 0 if revenue_growth is None else 10 if revenue_growth >= Decimal("0.10") else 8 if revenue_growth >= 0 else 5 if revenue_growth >= Decimal("-0.10") else 0
    margin_score = 0 if margin is None or margin < 0 else 10 if margin >= Decimal("0.08") else 8 if margin >= Decimal("0.05") else 5 if margin >= Decimal("0.02") else 2
    leverage_score = 0 if debt_to_equity is None else 10 if debt_to_equity <= Decimal("1.50") else 7 if debt_to_equity <= Decimal("2.50") else 3 if debt_to_equity <= Decimal("3.50") else 0
    dscr_score = 0 if dscr is None else 10 if dscr >= Decimal("1.30") else 7 if dscr >= Decimal("1.10") else 3 if dscr >= Decimal("1.00") else 0
    return growth_score + margin_score + leverage_score + dscr_score


def _funding_score(
    application: ComplianceApplication,
    own_capital_ratio: Decimal,
    loan_ratio: Decimal,
    supporting_ratio: Decimal,
) -> int:
    purpose_score = {"fit": 5, "needs_explanation": 3, "not_allowed": 0}[application.funding_plan.purpose_fit]
    own_score = 5 if own_capital_ratio >= Decimal("0.30") else 4 if own_capital_ratio >= Decimal("0.20") else 2 if own_capital_ratio >= Decimal("0.10") else 0
    loan_score = 5 if loan_ratio <= Decimal("0.80") else 2 if loan_ratio <= Decimal("0.90") else 0
    support_score = 5 if supporting_ratio >= Decimal("0.70") else 3 if supporting_ratio >= Decimal("0.40") else 0
    source_score = {"documented": 5, "described": 3, "missing": 0}[application.repayment_plan.source_status]
    return purpose_score + own_score + loan_score + support_score + source_score


def _valuation_age_months(as_of_date: date, valuation_date: date | None) -> int | None:
    if valuation_date is None:
        return None
    months = (as_of_date.year - valuation_date.year) * 12 + as_of_date.month - valuation_date.month
    if as_of_date.day < valuation_date.day:
        months -= 1
    return months


def _collateral_score(
    application: ComplianceApplication,
    ltv: Decimal,
    ltv_limit: Decimal,
) -> int:
    collateral = application.collateral
    ownership_score = {"valid": 5, "verify": 2, "missing": 0}[collateral.ownership_status]
    age = _valuation_age_months(application.as_of_date, collateral.valuation_date)
    valuation_score = 0 if age is None or age < 0 or age > 12 else 5 if age <= 6 else 2
    ltv_score = 5 if ltv <= ltv_limit else 2 if ltv <= ltv_limit + Decimal("0.10") else 0
    dispute_score = {"clear": 5, "verify": 2, "disputed": 0}[collateral.dispute_status]
    liquidity_score = {"high": 5, "medium": 3, "low": 1}[collateral.liquidity]
    return ownership_score + valuation_score + ltv_score + dispute_score + liquidity_score


def _document_score(documents: ComplianceDocuments) -> int:
    return (
        {"valid": 3, "verify": 1, "invalid": 0}[documents.signer_authority]
        + {"complete": 3, "minor_missing": 1, "mandatory_missing": 0}[documents.legal_documents]
        + {"consistent": 2, "minor_mismatch": 1, "major_mismatch": 0}[documents.consistency]
        + {"none": 2, "review": 1, "serious": 0}[documents.anomaly]
    )


def calculate_compliance_facts(application: ComplianceApplication) -> ComplianceFacts:
    current = application.current_financials
    previous = application.previous_financials
    growth = _ratio(
        current.revenue - previous.revenue if current and previous else None,
        previous.revenue if previous else None,
    )
    margin = _ratio(current.net_profit if current else None, current.revenue if current else None)
    leverage = _ratio(current.total_debt if current else None, current.equity if current else None)
    dscr = _ratio(
        application.repayment_plan.available_cash_flow,
        application.repayment_plan.annual_debt_service,
    )
    own_ratio = _ratio(application.funding_plan.own_capital, application.funding_plan.total_capital_need)
    loan_ratio = _ratio(application.requested_amount, application.funding_plan.total_capital_need)
    support_ratio = _ratio(application.funding_plan.supporting_document_value, application.requested_amount)
    ltv = _ratio(application.requested_amount, application.collateral.value)
    assert own_ratio is not None and loan_ratio is not None and support_ratio is not None and ltv is not None

    ltv_limits = {
        "land_house": Decimal("0.80"),
        "car": Decimal("0.65"),
        "machinery": Decimal("0.50"),
        "inventory": Decimal("0.40"),
        "receivables": Decimal("0.30"),
    }
    ltv_limit = ltv_limits[application.collateral.collateral_type]
    max_by_collateral = (application.collateral.value * ltv_limit).quantize(MONEY_QUANTUM)
    breakdown = {
        "financial_capacity": _financial_scores(growth, margin, leverage, dscr),
        "funding_and_repayment": _funding_score(application, own_ratio, loan_ratio, support_ratio),
        "collateral": _collateral_score(application, ltv, ltv_limit),
        "document_compliance": _document_score(application.documents),
    }
    total_score = sum(breakdown.values())

    hard_stops: list[str] = []
    if application.credit_result.hard_stop or application.credit_result.result == "FAILED":
        hard_stops.append("credit_hard_stop")
    if not application.documents.latest_financial_statement_present or current is None:
        hard_stops.append("missing_latest_financial_statement")
    if application.documents.signer_authority == "invalid":
        hard_stops.append("invalid_signer_authority")
    if application.collateral.dispute_status == "disputed":
        hard_stops.append("collateral_disputed")
    if application.collateral.ownership_status == "missing":
        hard_stops.append("missing_collateral_ownership")
    if application.repayment_plan.source_status == "missing":
        hard_stops.append("missing_repayment_source")
    if dscr is None:
        hard_stops.append("missing_dscr_data")
    elif dscr < Decimal("1.00"):
        hard_stops.append("dscr_below_1")
    if application.funding_plan.purpose_fit == "not_allowed":
        hard_stops.append("loan_purpose_not_allowed")
    if application.documents.anomaly == "serious":
        hard_stops.append("serious_document_anomaly")
    if application.screening.sanctions == "match":
        hard_stops.append("sanctions_match")

    conditions: list[str] = []
    if previous is None:
        conditions.append("provide_previous_financial_period")
    if application.repayment_plan.source_status == "described":
        conditions.append("provide_repayment_evidence")
    if not application.repayment_plan.cash_flow_timing_aligned:
        conditions.append("align_cash_flow_with_repayment_schedule")
    if own_ratio < Decimal("0.20"):
        conditions.append("increase_or_verify_own_capital")
    if loan_ratio > Decimal("0.80"):
        conditions.append("reduce_requested_amount_or_increase_own_capital")
    if support_ratio < Decimal("0.70"):
        conditions.append("provide_more_supporting_documents")
    valuation_age = _valuation_age_months(application.as_of_date, application.collateral.valuation_date)
    if valuation_age is None or valuation_age > 6:
        conditions.append("refresh_or_verify_collateral_valuation")
    if application.collateral.ownership_status == "verify" or application.collateral.dispute_status == "verify":
        conditions.append("verify_collateral_legal_status")
    if not application.collateral.third_party_documents_complete:
        conditions.append("provide_third_party_collateral_documents")
    if application.screening.pep != "clear" or application.screening.beneficial_owner != "clear":
        conditions.append("complete_enhanced_due_diligence")
    if application.screening.sanctions == "pending":
        conditions.append("complete_sanctions_screening")

    capital_limit = (application.funding_plan.total_capital_need * Decimal("0.80")).quantize(MONEY_QUANTUM)
    base_limit = min(application.requested_amount, capital_limit, max_by_collateral)
    dscr_factor = None if dscr is None else Decimal("1.00") if dscr >= Decimal("1.30") else Decimal("0.90") if dscr >= Decimal("1.10") else Decimal("0.70") if dscr >= Decimal("1.00") else Decimal("0")
    adjusted_limit = None if dscr_factor is None else (base_limit * dscr_factor).quantize(MONEY_QUANTUM)
    recommended_limit = None if hard_stops else adjusted_limit

    if total_score >= 80:
        rating: RiskRating = "Low Risk"
    elif total_score >= 65:
        rating = "Medium Risk"
    elif total_score >= 50:
        rating = "High Risk"
    else:
        rating = "Very High Risk"
    if hard_stops:
        rating = "Very High Risk"
        result: ComplianceResult = "FAILED"
        recommendation = "not_recommended"
    elif total_score >= 80 and not conditions:
        result = "PASSED"
        recommendation = "consider_credit"
    elif total_score >= 50:
        result = "CONDITIONAL"
        recommendation = "conditional_review" if total_score >= 65 else "reduce_limit_or_request_information"
    else:
        result = "FAILED"
        recommendation = "not_recommended"
    return ComplianceFacts(
        metrics=ComplianceMetrics(
            revenue_growth=str(growth) if growth is not None else None,
            net_profit_margin=str(margin) if margin is not None else None,
            debt_to_equity=str(leverage) if leverage is not None else None,
            dscr=str(dscr) if dscr is not None else None,
            own_capital_ratio=str(own_ratio),
            loan_to_capital_need_ratio=str(loan_ratio),
            supporting_document_ratio=str(support_ratio),
            ltv=str(ltv),
        ),
        score_breakdown=breakdown,
        total_score=total_score,
        risk_rating=rating,
        result=result,
        hard_stop_reasons=sorted(set(hard_stops)),
        conditions=sorted(set(conditions)),
        max_loan_by_collateral=max_by_collateral,
        dscr_adjusted_limit=adjusted_limit,
        recommended_limit=recommended_limit,
        final_recommendation=recommendation,
    )


def fail_closed_assessment(
    application: ComplianceApplication,
    facts: ComplianceFacts,
    missing_data: list[str],
) -> ComplianceAssessment:
    closed_facts = facts.model_copy(
        update={
            "risk_rating": "Undetermined",
            "result": "UNDETERMINED",
            "recommended_limit": None,
            "final_recommendation": "undetermined",
        }
    )
    return ComplianceAssessment(
        case_id=application.case_id,
        loan_profile_id=application.loan_profile_id,
        facts=closed_facts,
        findings=[],
        conditions=facts.conditions,
        executed_actions=[],
        missing_data=sorted(set(missing_data)),
        evidence=[],
    )


def assemble_compliance_assessment(
    application: ComplianceApplication,
    facts: ComplianceFacts,
    draft: ComplianceDecisionDraft,
    trusted_evidence: list[KnowledgeEvidence],
) -> ComplianceAssessment:
    if not trusted_evidence:
        return fail_closed_assessment(application, facts, ["rag_evidence"])
    trusted_by_id = evidence_by_id(trusted_evidence)
    for source_id, item in evidence_by_id(draft.evidence).items():
        if trusted_by_id.get(source_id) != item:
            raise ValueError(f"Untrusted model evidence: {source_id}")
    referenced_ids = {evidence_id for finding in draft.findings for evidence_id in finding.evidence_ids}
    unknown_ids = sorted(referenced_ids - trusted_by_id.keys())
    if unknown_ids:
        raise ValueError(f"Unknown evidence ids: {', '.join(unknown_ids)}")
    if draft.missing_data:
        return fail_closed_assessment(application, facts, draft.missing_data)
    if application.execution_mode == "assess" and draft.executed_actions:
        raise ValueError("Assess mode cannot execute actions")
    return ComplianceAssessment(
        case_id=application.case_id,
        loan_profile_id=application.loan_profile_id,
        facts=facts,
        findings=draft.findings,
        conditions=sorted(set([*facts.conditions, *draft.conditions])),
        executed_actions=draft.executed_actions,
        missing_data=[],
        evidence=trusted_evidence,
    )


ComplianceExecutor: TypeAlias = Callable[
    [ComplianceApplication, ComplianceFacts, str, str],
    Awaitable[ComplianceDecisionExecution],
]


def build_compliance_agent(server: MCPServerStreamableHttp, model: str) -> Agent:
    return Agent(
        name="Compliance Agent",
        instructions=(
            "Assess financial, repayment, collateral, legal, and compliance risk for one loan "
            "application. Treat deterministic facts, scores, ratios, hard stops, and limits as "
            "immutable. Before every policy finding call search_knowledge with "
            "domain='compliance' and top_k=5. If a chunk is insufficient, call "
            "get_document_page only with its returned source_id. Cite every finding. In assess "
            "mode do not write data. In execute mode persist checks and the compliance result "
            "only for the supplied loan_profile_id. executed_actions must list the exact "
            "mutating tool names in call order. Never approve or disburse a loan."
        ),
        model=model,
        mcp_servers=[server],
        output_type=ComplianceDecisionDraft,
    )


def build_agent_input(application: ComplianceApplication, facts: ComplianceFacts) -> str:
    return json.dumps(
        {
            "application": application.model_dump(mode="json"),
            "deterministic_facts": facts.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )


async def execute_compliance_decision(
    application: ComplianceApplication,
    facts: ComplianceFacts,
    mcp_url: str,
    model: str,
) -> ComplianceDecisionExecution:
    async with build_agent_mcp_server(mcp_url, "compliance", application.execution_mode) as server:
        assert_expected_agent_tools(await server.list_tools(), "compliance", application.execution_mode)
        result = await Runner.run(
            build_compliance_agent(server, model),
            build_agent_input(application, facts),
            hooks=DomainRAGRunHooks(
                "compliance",
                application.loan_profile_id,
                application.execution_mode,
            ),
            run_config=build_agent_run_config(
                "MediaX Compliance Agent",
                metadata={"domain": "compliance", "execution_mode": application.execution_mode},
            ),
        )
    if not isinstance(result.final_output, ComplianceDecisionDraft):
        raise TypeError("Compliance Agent returned invalid structured output")
    trusted_evidence = extract_trusted_evidence(
        result.new_items,
        domain="compliance",
        loan_profile_id=application.loan_profile_id,
        execution_mode=application.execution_mode,
    )
    called_tools = extract_called_tool_names(result.new_items)
    mutations = mutating_tool_names(called_tools)
    if result.final_output.executed_actions != mutations:
        raise ValueError("Compliance executed_actions do not match completed MCP mutations")
    if "save_compliance_result" in mutations and mutations[-1] != "save_compliance_result":
        raise ValueError("save_compliance_result must be the final compliance mutation")
    return ComplianceDecisionExecution(
        draft=result.final_output,
        trusted_evidence=trusted_evidence,
    )


async def run_compliance_assessment(
    application: ComplianceApplication,
    *,
    mcp_url: str = DEFAULT_RAG_MCP_URL,
    model: str = DEFAULT_MODEL,
    decision_executor: ComplianceExecutor | None = None,
) -> ComplianceAssessment:
    facts = calculate_compliance_facts(application)
    try:
        execution = await (decision_executor or execute_compliance_decision)(
            application,
            facts,
            mcp_url,
            model,
        )
        return assemble_compliance_assessment(
            application,
            facts,
            execution.draft,
            execution.trusted_evidence,
        )
    except Exception as error:
        logger.error("Compliance assessment runtime/provenance failure [%s]", type(error).__name__)
        log_agent_runtime_failure("compliance", error)
        return fail_closed_assessment(application, facts, ["rag_or_agent_runtime"])


def load_application(path: str) -> ComplianceApplication:
    return ComplianceApplication.model_validate_json(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MediaX Compliance Agent.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--mcp-url", default=os.getenv("RAG_MCP_URL", DEFAULT_RAG_MCP_URL))
    parser.add_argument("--model", default=os.getenv("OPENAI_AGENT_MODEL", DEFAULT_MODEL))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required.")
    assessment = asyncio.run(
        run_compliance_assessment(
            load_application(args.input),
            mcp_url=args.mcp_url,
            model=args.model,
        )
    )
    print(assessment.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
