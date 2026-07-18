from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
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


MONEY_QUANTUM = Decimal("0.01")
DEFAULT_RAG_MCP_URL = "http://127.0.0.1:8766/mcp"
DEFAULT_MODEL = "gpt-5.4-mini"
OperationStatus = Literal["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10", "S11"]
OperationsResult = Literal["READY", "CONDITIONAL", "WAITING", "BLOCKED", "UNDETERMINED"]
TicketPriority = Literal["P1", "P2", "P3"]
logger = logging.getLogger(__name__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class OperationsDocument(StrictModel):
    document_type: str = Field(min_length=1)
    status: Literal["provided", "missing", "not_applicable"] = "missing"


class CreditUpstreamResult(StrictModel):
    legal_score: int = Field(ge=0, le=100)
    result: Literal["PASSED", "CONDITIONAL", "FAILED"]
    hard_stop_reasons: list[str] = Field(default_factory=list)


class ComplianceUpstreamResult(StrictModel):
    total_score: int = Field(ge=0, le=100)
    risk_rating: Literal["Low Risk", "Medium Risk", "High Risk", "Very High Risk"]
    result: Literal["PASSED", "CONDITIONAL", "FAILED"]
    dscr: Decimal = Field(ge=0)
    collateral_type: Literal["land_house", "car", "machinery", "inventory", "receivables"]
    collateral_value: Decimal = Field(gt=0)
    ltv_ratio: Decimal = Field(gt=0, le=1)
    hard_stop_reasons: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    recommended_limit: Decimal | None = Field(default=None, ge=0)


class OperationsApplication(StrictModel):
    case_id: str = Field(min_length=1)
    loan_profile_id: str = Field(min_length=1)
    execution_mode: ExecutionMode = "assess"
    customer_type: Literal["individual", "household_business", "enterprise"]
    current_status: OperationStatus = "S01"
    as_of_at: datetime
    stage_started_at: datetime
    requested_amount: Decimal = Field(gt=0)
    total_capital_need: Decimal = Field(gt=0)
    own_capital: Decimal = Field(ge=0)
    term_months: int = Field(gt=0, le=360)
    purpose: str = Field(min_length=1)
    repayment_method: str | None = None
    collateral_based: bool = True
    documents: list[OperationsDocument] = Field(default_factory=list)
    credit_result: CreditUpstreamResult
    compliance_result: ComplianceUpstreamResult
    human_approved: bool = False
    disbursement_conditions_complete: bool = False

    @model_validator(mode="after")
    def validate_case(self):
        names = [item.document_type.casefold() for item in self.documents]
        if len(names) != len(set(names)):
            raise ValueError("document_type values must be unique")
        if self.as_of_at.tzinfo is None or self.stage_started_at.tzinfo is None:
            raise ValueError("Operations timestamps must include timezone information")
        if self.current_status == "S11" and not (
            self.human_approved and self.disbursement_conditions_complete
        ):
            raise ValueError("S11 input requires human approval and completed conditions")
        return self


class OperationsFacts(StrictModel):
    checklist_breakdown: dict[str, int]
    checklist_score: int = Field(ge=0, le=100)
    result: OperationsResult
    hard_stop_reasons: list[str]
    missing_required_documents: list[str]
    conditions: list[str]
    requested_amount: Decimal
    capital_need_limit: Decimal
    collateral_limit: Decimal
    dscr_factor: str
    checklist_factor: str
    final_factor: str
    recommended_limit: Decimal | None
    proposed_status: OperationStatus
    sla_deadline: datetime
    sla_breached: bool
    ticket_priority: TicketPriority
    next_action_codes: list[str]


class OperationsAction(StrictModel):
    sequence: int = Field(ge=1)
    code: str = Field(min_length=1)
    action: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class OperationsDecisionDraft(StrictModel):
    next_actions: list[OperationsAction] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    executed_actions: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)


class OperationsDecisionExecution(StrictModel):
    draft: OperationsDecisionDraft
    trusted_evidence: list[KnowledgeEvidence]


class OperationsAssessment(StrictModel):
    case_id: str
    loan_profile_id: str
    current_status: OperationStatus
    facts: OperationsFacts
    next_actions: list[OperationsAction]
    conditions: list[str]
    executed_actions: list[str]
    missing_data: list[str]
    evidence: list[KnowledgeEvidence]


DOCUMENT_RULES = {
    "business_registration": ("legal", 7),
    "legal_representative_id": ("legal", 5),
    "company_charter": ("legal", 5),
    "appointment_decision": ("legal", 3),
    "authorization_letter": ("legal", 3),
    "signature_sample": ("legal", 2),
    "credit_request": ("loan_request", 5),
    "loan_signature": ("loan_request", 2),
    "latest_financial_statement": ("financial", 8),
    "previous_financial_statement": ("financial", 4),
    "balance_sheet": ("financial", 3),
    "income_statement": ("financial", 3),
    "cash_flow_statement": ("financial", 2),
    "use_of_funds_plan": ("repayment", 4),
    "repayment_plan": ("repayment", 4),
    "cash_flow_evidence": ("repayment", 3),
    "collateral_ownership": ("collateral", 6),
    "collateral_valuation": ("collateral", 5),
    "collateral_inspection": ("collateral", 3),
    "collateral_clear": ("collateral", 3),
    "third_party_collateral_documents": ("collateral", 3),
    "loan_summary": ("internal", 2),
    "missing_document_checklist": ("internal", 1),
    "proposed_limit": ("internal", 1),
    "processing_ticket": ("internal", 1),
}


def _document_map(application: OperationsApplication) -> dict[str, OperationsDocument]:
    return {item.document_type.casefold(): item for item in application.documents}


def _available(documents: dict[str, OperationsDocument], document_type: str) -> bool:
    item = documents.get(document_type)
    return bool(item and item.status in {"provided", "not_applicable"})


def calculate_checklist(application: OperationsApplication) -> tuple[dict[str, int], list[str]]:
    documents = _document_map(application)
    scores = {"legal": 0, "loan_request": 0, "financial": 0, "repayment": 0, "collateral": 0, "internal": 0}
    for document_type, (group, points) in DOCUMENT_RULES.items():
        if not application.collateral_based and group == "collateral":
            scores[group] += points
        elif application.customer_type != "enterprise" and document_type in {
            "business_registration",
            "legal_representative_id",
            "company_charter",
            "appointment_decision",
            "authorization_letter",
            "signature_sample",
        }:
            scores[group] += points
        elif _available(documents, document_type):
            scores[group] += points

    scores["loan_request"] += 2 if application.requested_amount > 0 else 0
    scores["loan_request"] += 2 if application.term_months > 0 else 0
    scores["loan_request"] += 2 if application.purpose else 0
    scores["loan_request"] += 2 if application.repayment_method else 0
    scores["repayment"] += 2 if application.total_capital_need > 0 else 0
    scores["repayment"] += 2 if application.own_capital >= 0 else 0

    required = ["credit_request", "latest_financial_statement", "repayment_plan"]
    if application.customer_type == "enterprise":
        required.extend(["business_registration", "legal_representative_id"])
    if application.collateral_based:
        required.extend(["collateral_ownership", "collateral_valuation", "collateral_clear"])
    missing_required = sorted(item for item in required if not _available(documents, item))
    return scores, missing_required


def _factor_for_dscr(dscr: Decimal) -> Decimal:
    return Decimal("1.00") if dscr >= Decimal("1.30") else Decimal("0.90") if dscr >= Decimal("1.10") else Decimal("0.70") if dscr >= Decimal("1.00") else Decimal("0")


def _factor_for_checklist(score: int) -> Decimal:
    return Decimal("1.00") if score >= 90 else Decimal("0.90") if score >= 75 else Decimal("0.70") if score >= 50 else Decimal("0")


def calculate_loan_limit(
    application: OperationsApplication,
    checklist_score: int,
    hard_stop: bool,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal]:
    capital_limit = (application.total_capital_need * Decimal("0.80")).quantize(MONEY_QUANTUM)
    collateral_limit = (
        application.compliance_result.collateral_value * application.compliance_result.ltv_ratio
    ).quantize(MONEY_QUANTUM)
    base_limit = min(application.requested_amount, capital_limit, collateral_limit)
    dscr_factor = _factor_for_dscr(application.compliance_result.dscr)
    checklist_factor = _factor_for_checklist(checklist_score)
    final_factor = min(dscr_factor, checklist_factor)
    recommended = Decimal("0.00") if hard_stop else (base_limit * final_factor).quantize(MONEY_QUANTUM)
    if application.compliance_result.recommended_limit is not None:
        recommended = min(recommended, application.compliance_result.recommended_limit)
    return capital_limit, collateral_limit, dscr_factor, checklist_factor, final_factor, recommended


def _missing_group(missing: list[str]) -> str | None:
    for group in ("legal", "loan_request", "financial", "repayment", "collateral"):
        if any(DOCUMENT_RULES[item][0] == group for item in missing):
            return group
    return None


def determine_case_status(
    application: OperationsApplication,
    checklist_score: int,
    hard_stop_reasons: list[str],
    missing_required: list[str],
    conditions: list[str],
) -> OperationStatus:
    if application.human_approved and application.disbursement_conditions_complete and not hard_stop_reasons:
        return "S11"
    document_only_hard_stops = all(reason.startswith("missing_document:") for reason in hard_stop_reasons)
    if hard_stop_reasons and not document_only_hard_stops:
        return "S10"
    missing_group = _missing_group(missing_required)
    if missing_group:
        return {
            "legal": "S02",
            "loan_request": "S03",
            "financial": "S04",
            "repayment": "S05",
            "collateral": "S06",
        }[missing_group]
    if checklist_score < 50:
        return "S10"
    if checklist_score < 75:
        return "S07"
    if checklist_score < 90:
        return "S08"
    return "S09"


def validate_status_transition(
    application: OperationsApplication,
    proposed_status: OperationStatus,
) -> None:
    if application.current_status == "S11" and proposed_status != "S11":
        raise ValueError("S11 is terminal")
    if proposed_status == "S11" and not (
        application.human_approved and application.disbursement_conditions_complete
    ):
        raise ValueError("S11 requires human approval and completed disbursement conditions")


def calculate_sla(application: OperationsApplication) -> tuple[datetime, bool]:
    # ponytail: demo uses elapsed hours; add a banking holiday calendar for production SLA.
    hours = {
        "S01": 4,
        "S02": 48,
        "S03": 24,
        "S04": 48,
        "S05": 24,
        "S06": 120 if application.requested_amount > Decimal("10000000000") else 48,
        "S07": 24,
        "S08": 72,
        "S09": 24,
        "S10": 48,
        "S11": 24,
    }[application.current_status]
    deadline = application.stage_started_at + timedelta(hours=hours)
    return deadline, application.as_of_at > deadline


def determine_ticket_priority(
    application: OperationsApplication,
    hard_stop_reasons: list[str],
    missing_required: list[str],
    conditions: list[str],
    sla_breached: bool,
) -> TicketPriority:
    serious = any(
        token in reason
        for reason in hard_stop_reasons
        for token in ("signer", "dispute", "purpose", "sanctions", "dscr")
    )
    if serious or (application.requested_amount > Decimal("10000000000") and sla_breached):
        return "P1"
    if (
        application.requested_amount >= Decimal("2000000000")
        and (missing_required or conditions)
    ):
        return "P2"
    return "P3"


def calculate_operations_facts(application: OperationsApplication) -> OperationsFacts:
    breakdown, missing_required = calculate_checklist(application)
    checklist_score = sum(breakdown.values())
    hard_stops = [f"missing_document:{item}" for item in missing_required]
    hard_stops.extend(application.credit_result.hard_stop_reasons)
    hard_stops.extend(application.compliance_result.hard_stop_reasons)
    if application.credit_result.result == "FAILED":
        hard_stops.append("credit_failed")
    if application.compliance_result.result == "FAILED":
        hard_stops.append("compliance_failed")
    if application.compliance_result.dscr < Decimal("1.00"):
        hard_stops.append("dscr_below_1")
    if checklist_score < 50:
        hard_stops.append("checklist_below_50")
    hard_stops = sorted(set(hard_stops))

    documents = _document_map(application)
    missing_all = sorted(item for item, doc in documents.items() if doc.status == "missing")
    conditions = [*application.compliance_result.conditions]
    conditions.extend(f"provide:{item}" for item in missing_all if item not in missing_required)
    if application.own_capital / application.total_capital_need < Decimal("0.20"):
        conditions.append("increase_own_capital")
    if application.requested_amount / application.total_capital_need > Decimal("0.80"):
        conditions.append("reduce_requested_amount")
    conditions = sorted(set(conditions))

    capital_limit, collateral_limit, dscr_factor, checklist_factor, final_factor, recommended = calculate_loan_limit(
        application,
        checklist_score,
        bool(hard_stops),
    )
    proposed_status = determine_case_status(
        application,
        checklist_score,
        hard_stops,
        missing_required,
        conditions,
    )
    validate_status_transition(application, proposed_status)
    sla_deadline, sla_breached = calculate_sla(application)
    priority = determine_ticket_priority(
        application,
        hard_stops,
        missing_required,
        conditions,
        sla_breached,
    )
    next_actions = [f"resolve:{reason}" for reason in hard_stops]
    next_actions.extend(f"provide:{item}" for item in missing_all)
    if proposed_status == "S08":
        next_actions.append("complete_conditions")
    elif proposed_status == "S09":
        next_actions.append("prepare_approval_package")
    elif proposed_status == "S11":
        next_actions.append("create_disbursement_task")
    elif not next_actions:
        next_actions.append("continue_specialist_review")

    if hard_stops:
        result: OperationsResult = "BLOCKED"
    elif proposed_status in {"S09", "S11"}:
        result = "READY"
    elif proposed_status == "S08":
        result = "CONDITIONAL"
    else:
        result = "WAITING"
    return OperationsFacts(
        checklist_breakdown=breakdown,
        checklist_score=checklist_score,
        result=result,
        hard_stop_reasons=hard_stops,
        missing_required_documents=missing_required,
        conditions=conditions,
        requested_amount=application.requested_amount,
        capital_need_limit=capital_limit,
        collateral_limit=collateral_limit,
        dscr_factor=str(dscr_factor),
        checklist_factor=str(checklist_factor),
        final_factor=str(final_factor),
        recommended_limit=recommended,
        proposed_status=proposed_status,
        sla_deadline=sla_deadline,
        sla_breached=sla_breached,
        ticket_priority=priority,
        next_action_codes=sorted(set(next_actions)),
    )


def fail_closed_assessment(
    application: OperationsApplication,
    facts: OperationsFacts,
    missing_data: list[str],
) -> OperationsAssessment:
    closed_facts = facts.model_copy(
        update={
            "result": "UNDETERMINED",
            "recommended_limit": None,
            "proposed_status": application.current_status,
        }
    )
    return OperationsAssessment(
        case_id=application.case_id,
        loan_profile_id=application.loan_profile_id,
        current_status=application.current_status,
        facts=closed_facts,
        next_actions=[],
        conditions=facts.conditions,
        executed_actions=[],
        missing_data=sorted(set(missing_data)),
        evidence=[],
    )


def assemble_operations_assessment(
    application: OperationsApplication,
    facts: OperationsFacts,
    draft: OperationsDecisionDraft,
    trusted_evidence: list[KnowledgeEvidence],
) -> OperationsAssessment:
    if not trusted_evidence:
        return fail_closed_assessment(application, facts, ["rag_evidence"])
    trusted_by_id = evidence_by_id(trusted_evidence)
    for source_id, item in evidence_by_id(draft.evidence).items():
        if trusted_by_id.get(source_id) != item:
            raise ValueError(f"Untrusted model evidence: {source_id}")
    referenced_ids = {evidence_id for action in draft.next_actions for evidence_id in action.evidence_ids}
    unknown_ids = sorted(referenced_ids - trusted_by_id.keys())
    if unknown_ids:
        raise ValueError(f"Unknown evidence ids: {', '.join(unknown_ids)}")
    if draft.missing_data:
        return fail_closed_assessment(application, facts, draft.missing_data)
    expected_sequence = list(range(1, len(draft.next_actions) + 1))
    if [item.sequence for item in draft.next_actions] != expected_sequence:
        raise ValueError("Operations action sequence must be continuous from 1")
    missing_codes = sorted(set(facts.next_action_codes) - {item.code for item in draft.next_actions})
    if missing_codes:
        raise ValueError(f"Operations actions omit required codes: {', '.join(missing_codes)}")
    if application.execution_mode == "assess" and draft.executed_actions:
        raise ValueError("Assess mode cannot execute actions")
    return OperationsAssessment(
        case_id=application.case_id,
        loan_profile_id=application.loan_profile_id,
        current_status=application.current_status,
        facts=facts,
        next_actions=draft.next_actions,
        conditions=sorted(set([*facts.conditions, *draft.conditions])),
        executed_actions=draft.executed_actions,
        missing_data=[],
        evidence=trusted_evidence,
    )


OperationsExecutor: TypeAlias = Callable[
    [OperationsApplication, OperationsFacts, str, str],
    Awaitable[OperationsDecisionExecution],
]


def build_operations_agent(server: MCPServerStreamableHttp, model: str) -> Agent:
    return Agent(
        name="Operations Agent",
        instructions=(
            "Operate one loan case using immutable Credit and Compliance results. Treat the "
            "deterministic checklist, limit, status, SLA, priority, and action codes as "
            "immutable. Before every policy-derived action call search_knowledge with "
            "domain='operations' and top_k=5; read a full page only from a returned source_id. "
            "Cite every action. In assess mode propose actions only. In execute mode persist "
            "checklist and limit first, then task/report, and update status last. Never move a "
            "case to S11 without the supplied human approval flags. executed_actions must list "
            "the exact mutating tool names in call order. Never approve or disburse."
        ),
        model=model,
        mcp_servers=[server],
        output_type=OperationsDecisionDraft,
    )


def build_agent_input(application: OperationsApplication, facts: OperationsFacts) -> str:
    return json.dumps(
        {
            "application": application.model_dump(mode="json"),
            "deterministic_facts": facts.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )


async def execute_operations_decision(
    application: OperationsApplication,
    facts: OperationsFacts,
    mcp_url: str,
    model: str,
) -> OperationsDecisionExecution:
    async with build_agent_mcp_server(mcp_url, "operations", application.execution_mode) as server:
        assert_expected_agent_tools(await server.list_tools(), "operations", application.execution_mode)
        result = await Runner.run(
            build_operations_agent(server, model),
            build_agent_input(application, facts),
            hooks=DomainRAGRunHooks(
                "operations",
                application.loan_profile_id,
                application.execution_mode,
            ),
            run_config=build_agent_run_config(
                "MediaX Operations Agent",
                metadata={"domain": "operations", "execution_mode": application.execution_mode},
            ),
        )
    if not isinstance(result.final_output, OperationsDecisionDraft):
        raise TypeError("Operations Agent returned invalid structured output")
    trusted_evidence = extract_trusted_evidence(
        result.new_items,
        domain="operations",
        loan_profile_id=application.loan_profile_id,
        execution_mode=application.execution_mode,
    )
    called_tools = extract_called_tool_names(result.new_items)
    mutations = mutating_tool_names(called_tools)
    if result.final_output.executed_actions != mutations:
        raise ValueError("Operations executed_actions do not match completed MCP mutations")
    ranks = {
        "create_checklist": 1,
        "calculate_loan_limit": 1,
        "create_task": 2,
        "create_report": 2,
        "update_case_status": 3,
    }
    if [ranks[item] for item in mutations] != sorted(ranks[item] for item in mutations):
        raise ValueError("Operations mutations were executed out of order")
    return OperationsDecisionExecution(
        draft=result.final_output,
        trusted_evidence=trusted_evidence,
    )


async def run_operations_assessment(
    application: OperationsApplication,
    *,
    mcp_url: str = DEFAULT_RAG_MCP_URL,
    model: str = DEFAULT_MODEL,
    decision_executor: OperationsExecutor | None = None,
) -> OperationsAssessment:
    facts = calculate_operations_facts(application)
    try:
        execution = await (decision_executor or execute_operations_decision)(
            application,
            facts,
            mcp_url,
            model,
        )
        return assemble_operations_assessment(
            application,
            facts,
            execution.draft,
            execution.trusted_evidence,
        )
    except Exception as error:
        logger.error("Operations assessment runtime/provenance failure [%s]", type(error).__name__)
        return fail_closed_assessment(application, facts, ["rag_or_agent_runtime"])


def load_application(path: str) -> OperationsApplication:
    return OperationsApplication.model_validate_json(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MediaX Operations Agent.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--mcp-url", default=os.getenv("RAG_MCP_URL", DEFAULT_RAG_MCP_URL))
    parser.add_argument("--model", default=os.getenv("OPENAI_AGENT_MODEL", DEFAULT_MODEL))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required.")
    assessment = asyncio.run(
        run_operations_assessment(
            load_application(args.input),
            mcp_url=args.mcp_url,
            model=args.model,
        )
    )
    print(assessment.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
