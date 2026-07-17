from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from decimal import Decimal, DecimalException, ROUND_HALF_UP
from pathlib import Path
from typing import Annotated, Literal, TypeAlias

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from pydantic import BaseModel, Field, TypeAdapter

from rag_agent_support import (
    DomainRAGRunHooks,
    KnowledgeEvidence,
    assert_expected_agent_tools,
    build_agent_mcp_server,
    evidence_by_id,
    extract_trusted_evidence,
)


RATIO_QUANTUM = Decimal("0.0001")
DEFAULT_RAG_MCP_URL = "http://127.0.0.1:8766/mcp"
DEFAULT_MODEL = "gpt-5.4-mini"
MetricName = Literal["dti", "ltv", "dscr", "debt_to_equity", "current_ratio"]
logger = logging.getLogger(__name__)


class PersonalLoanApplication(BaseModel):
    case_id: str = Field(min_length=1)
    loan_profile_id: str | None = Field(default=None, min_length=1)
    loan_type: Literal["personal"]
    requested_amount: Decimal = Field(gt=0)
    term_months: int = Field(gt=0)
    purpose: str = Field(min_length=1)
    monthly_income: Decimal | None = Field(default=None, ge=0)
    monthly_debt_payment: Decimal | None = Field(default=None, ge=0)
    collateral_value: Decimal | None = Field(default=None, gt=0)


class SMELoanApplication(BaseModel):
    case_id: str = Field(min_length=1)
    loan_profile_id: str | None = Field(default=None, min_length=1)
    loan_type: Literal["sme"]
    requested_amount: Decimal = Field(gt=0)
    term_months: int = Field(gt=0)
    purpose: str = Field(min_length=1)
    annual_net_operating_income: Decimal | None = None
    annual_debt_service: Decimal | None = Field(default=None, ge=0)
    total_debt: Decimal | None = Field(default=None, ge=0)
    equity: Decimal | None = None
    current_assets: Decimal | None = Field(default=None, ge=0)
    current_liabilities: Decimal | None = Field(default=None, ge=0)
    collateral_value: Decimal | None = Field(default=None, gt=0)


LoanApplication = Annotated[
    PersonalLoanApplication | SMELoanApplication,
    Field(discriminator="loan_type"),
]
LOAN_APPLICATION_ADAPTER = TypeAdapter(LoanApplication)


class MetricResult(BaseModel):
    name: MetricName
    value: str | None
    reason: str | None = None


def _ratio(
    name: MetricName,
    numerator: Decimal | None,
    numerator_field: str,
    denominator: Decimal | None,
    denominator_field: str,
) -> tuple[MetricResult, list[str]]:
    missing = [
        field_name
        for value, field_name in (
            (numerator, numerator_field),
            (denominator, denominator_field),
        )
        if value is None
    ]
    if missing:
        return MetricResult(name=name, value=None, reason=f"Missing: {', '.join(missing)}"), missing
    assert numerator is not None
    assert denominator is not None
    try:
        if denominator <= 0:
            return (
                MetricResult(
                    name=name,
                    value=None,
                    reason=f"{denominator_field} must be greater than 0",
                ),
                [],
            )
        value = (numerator / denominator).quantize(RATIO_QUANTUM, rounding=ROUND_HALF_UP)
    except DecimalException:
        return MetricResult(name=name, value=None, reason="Calculation failed"), []
    return MetricResult(name=name, value=str(value)), []


def calculate_credit_metrics(
    application: LoanApplication,
) -> tuple[list[MetricResult], list[str]]:
    metrics: list[MetricResult] = []
    missing_data: list[str] = []

    if isinstance(application, PersonalLoanApplication):
        metric, missing = _ratio(
            "dti",
            application.monthly_debt_payment,
            "monthly_debt_payment",
            application.monthly_income,
            "monthly_income",
        )
        metrics.append(metric)
        missing_data.extend(missing)
    else:
        for arguments in (
            (
                "dscr",
                application.annual_net_operating_income,
                "annual_net_operating_income",
                application.annual_debt_service,
                "annual_debt_service",
            ),
            (
                "debt_to_equity",
                application.total_debt,
                "total_debt",
                application.equity,
                "equity",
            ),
            (
                "current_ratio",
                application.current_assets,
                "current_assets",
                application.current_liabilities,
                "current_liabilities",
            ),
        ):
            metric, missing = _ratio(*arguments)
            metrics.append(metric)
            missing_data.extend(missing)

    if application.collateral_value is not None:
        metric, missing = _ratio(
            "ltv",
            application.requested_amount,
            "requested_amount",
            application.collateral_value,
            "collateral_value",
        )
        metrics.append(metric)
        missing_data.extend(missing)

    return metrics, sorted(set(missing_data))


RiskLevel = Literal["low", "medium", "high", "undetermined"]
Recommendation = Literal[
    "proceed_to_manual_review",
    "request_more_information",
    "escalate_high_risk_review",
]


class CreditFinding(BaseModel):
    summary: str = Field(min_length=1)
    severity: Literal["info", "warning", "critical"]
    evidence_ids: list[str] = Field(min_length=1)


class CreditDecisionDraft(BaseModel):
    risk_level: RiskLevel
    recommendation: Recommendation
    findings: list[CreditFinding] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)


class CreditDecisionExecution(BaseModel):
    draft: CreditDecisionDraft
    trusted_evidence: list[KnowledgeEvidence]


class CreditAssessment(BaseModel):
    case_id: str
    loan_type: Literal["personal", "sme"]
    risk_level: RiskLevel
    recommendation: Recommendation
    metrics: list[MetricResult]
    findings: list[CreditFinding]
    missing_data: list[str]
    evidence: list[KnowledgeEvidence]


def fail_closed_assessment(
    application: LoanApplication,
    metrics: list[MetricResult],
    missing_data: list[str],
) -> CreditAssessment:
    return CreditAssessment(
        case_id=application.case_id,
        loan_type=application.loan_type,
        risk_level="undetermined",
        recommendation="request_more_information",
        metrics=metrics,
        findings=[],
        missing_data=sorted(set(missing_data)),
        evidence=[],
    )


def assemble_credit_assessment(
    application: LoanApplication,
    metrics: list[MetricResult],
    missing_data: list[str],
    draft: CreditDecisionDraft,
    trusted_evidence: list[KnowledgeEvidence],
) -> CreditAssessment:
    if not trusted_evidence:
        return fail_closed_assessment(application, metrics, ["rag_evidence"])

    trusted_by_id = evidence_by_id(trusted_evidence)
    draft_by_id = evidence_by_id(draft.evidence)
    for source_id, item in draft_by_id.items():
        if trusted_by_id.get(source_id) != item:
            raise ValueError(f"Untrusted model evidence: {source_id}")

    referenced_ids = {
        evidence_id
        for finding in draft.findings
        for evidence_id in finding.evidence_ids
    }
    unknown_ids = sorted(referenced_ids - trusted_by_id.keys())
    if unknown_ids:
        raise ValueError(f"Unknown evidence ids: {', '.join(unknown_ids)}")

    if draft.risk_level == "undetermined":
        if draft.recommendation != "request_more_information" or draft.findings:
            raise ValueError("Contradictory undetermined credit decision")
    elif draft.recommendation == "request_more_information" or not draft.findings:
        raise ValueError("Contradictory determinate credit decision")

    combined_missing_data = sorted(set([*missing_data, *draft.missing_data]))
    if combined_missing_data:
        return fail_closed_assessment(application, metrics, combined_missing_data)
    if draft.risk_level == "undetermined":
        return fail_closed_assessment(application, metrics, ["agent_undetermined"])

    return CreditAssessment(
        case_id=application.case_id,
        loan_type=application.loan_type,
        risk_level=draft.risk_level,
        recommendation=draft.recommendation,
        metrics=metrics,
        findings=draft.findings,
        missing_data=[],
        evidence=trusted_evidence,
    )


DecisionExecutor: TypeAlias = Callable[
    [LoanApplication, list[MetricResult], str, str],
    Awaitable[CreditDecisionExecution],
]


def build_credit_agent(server: MCPServerStreamableHttp, model: str) -> Agent:
    return Agent(
        name="Credit Agent",
        instructions=(
            "Assess one personal or SME loan application. "
            "When loan_profile_id is supplied, use get_loan_profile to read the persisted "
            "case; you may then use its customer_id with get_customer and use list_reports "
            "for existing case history. Treat loan data tool results as supplemental context "
            "and never create or update records. "
            "Before making any policy finding, call search_knowledge with "
            "domain='credit' and top_k=5. If a returned excerpt lacks enough context, "
            "call get_document_page with the exact source_id from that search evidence. "
            "Never read a page for a source_id not returned by search_knowledge. "
            "Use only evidence returned by these tools. "
            "Copy source_id, file_name, page, and excerpt into evidence, and make every "
            "finding reference existing evidence_ids. Treat supplied metrics as immutable. "
            "Never approve, reject, or update a loan. Return undetermined and request more "
            "information when data or evidence is insufficient."
        ),
        model=model,
        mcp_servers=[server],
        output_type=CreditDecisionDraft,
    )


def build_agent_input(
    application: LoanApplication,
    metrics: list[MetricResult],
) -> str:
    return json.dumps(
        {
            "application": application.model_dump(mode="json"),
            "metrics": [metric.model_dump(mode="json") for metric in metrics],
        },
        ensure_ascii=False,
    )


async def execute_credit_decision(
    application: LoanApplication,
    metrics: list[MetricResult],
    mcp_url: str,
    model: str,
) -> CreditDecisionExecution:
    async with build_agent_mcp_server(mcp_url) as server:
        tools = await server.list_tools()
        assert_expected_agent_tools(tools)
        agent = build_credit_agent(server, model)
        result = await Runner.run(
            agent,
            build_agent_input(application, metrics),
            hooks=DomainRAGRunHooks("credit", application.loan_profile_id),
        )

    if not isinstance(result.final_output, CreditDecisionDraft):
        raise TypeError("Credit Agent returned an invalid structured output")
    return CreditDecisionExecution(
        draft=result.final_output,
        trusted_evidence=extract_trusted_evidence(
            result.new_items,
            domain="credit",
            loan_profile_id=application.loan_profile_id,
        ),
    )


async def run_credit_assessment(
    application: LoanApplication,
    *,
    mcp_url: str = DEFAULT_RAG_MCP_URL,
    model: str = DEFAULT_MODEL,
    decision_executor: DecisionExecutor | None = None,
) -> CreditAssessment:
    metrics, missing_data = calculate_credit_metrics(application)
    if missing_data:
        return fail_closed_assessment(application, metrics, missing_data)
    if any(metric.value is None for metric in metrics):
        logger.warning("Credit assessment failed closed: invalid_financial_metrics")
        return fail_closed_assessment(
            application,
            metrics,
            ["invalid_financial_metrics"],
        )

    executor = decision_executor or execute_credit_decision
    try:
        execution = await executor(application, metrics, mcp_url, model)
        return assemble_credit_assessment(
            application,
            metrics,
            [],
            execution.draft,
            execution.trusted_evidence,
        )
    except Exception as error:
        logger.error(
            "Credit assessment runtime/provenance failure [%s]",
            type(error).__name__,
        )
        return fail_closed_assessment(
            application,
            metrics,
            ["rag_or_agent_runtime"],
        )


def load_application(path: str) -> LoanApplication:
    raw_json = Path(path).read_text(encoding="utf-8")
    return LOAN_APPLICATION_ADAPTER.validate_json(raw_json)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MediaX Credit Agent.")
    parser.add_argument("--input", required=True, help="Path to a normalized loan JSON file.")
    parser.add_argument(
        "--mcp-url",
        default=os.getenv("RAG_MCP_URL", DEFAULT_RAG_MCP_URL),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("OPENAI_AGENT_MODEL", DEFAULT_MODEL),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required.")
    application = load_application(args.input)
    assessment = asyncio.run(
        run_credit_assessment(
            application,
            mcp_url=args.mcp_url,
            model=args.model,
        )
    )
    print(assessment.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
