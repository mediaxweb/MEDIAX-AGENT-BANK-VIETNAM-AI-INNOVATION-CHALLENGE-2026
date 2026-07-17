from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal, TypeAlias

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp
from pydantic import BaseModel, ConfigDict, Field, model_validator

from rag_agent_support import (
    DomainRAGRunHooks,
    KnowledgeEvidence,
    assert_expected_agent_tools,
    build_agent_mcp_server,
    evidence_by_id,
    extract_trusted_evidence,
)


DEFAULT_RAG_MCP_URL = "http://127.0.0.1:8766/mcp"
DEFAULT_MODEL = "gpt-5.4-mini"
LoanStage = Literal[
    "intake",
    "credit_review",
    "compliance_review",
    "operations_review",
    "decision_preparation",
]
GateOutcome = Literal["ready", "needs_information", "escalated", "undetermined"]
Readiness = Literal[
    "ready_for_next_step",
    "needs_documents",
    "needs_specialist_review",
    "undetermined",
]
logger = logging.getLogger(__name__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OperationsDocument(StrictModel):
    document_type: str = Field(min_length=1)
    status: Literal["provided", "missing", "pending_verification"]


class UpstreamGate(StrictModel):
    agent: Literal["credit", "compliance"]
    outcome: GateOutcome
    blocking_items: list[str] = Field(default_factory=list)


class OperationsApplication(StrictModel):
    case_id: str = Field(min_length=1)
    loan_profile_id: str | None = Field(default=None, min_length=1)
    loan_type: Literal["personal", "sme"]
    current_stage: LoanStage
    documents: list[OperationsDocument] = Field(default_factory=list)
    upstream_gates: list[UpstreamGate]

    @model_validator(mode="after")
    def validate_case_shape(self):
        agents = [gate.agent for gate in self.upstream_gates]
        if len(agents) != 2 or set(agents) != {"credit", "compliance"}:
            raise ValueError("upstream_gates require one credit and one compliance gate")
        document_types = [item.document_type.casefold() for item in self.documents]
        if len(document_types) != len(set(document_types)):
            raise ValueError("document_type values must be unique")
        return self


class OperationsFacts(StrictModel):
    missing_documents: list[str] = Field(default_factory=list)
    pending_documents: list[str] = Field(default_factory=list)
    upstream_blockers: list[str] = Field(default_factory=list)
    stage_inconsistencies: list[str] = Field(default_factory=list)

    @property
    def has_blockers(self) -> bool:
        return any(
            (
                self.missing_documents,
                self.pending_documents,
                self.upstream_blockers,
                self.stage_inconsistencies,
            )
        )


def calculate_operations_facts(
    application: OperationsApplication,
) -> OperationsFacts:
    gates = {gate.agent: gate for gate in application.upstream_gates}
    blockers = sorted(
        f"{gate.agent}:{gate.outcome}"
        for gate in application.upstream_gates
        if gate.outcome != "ready"
    )
    stage_inconsistencies: list[str] = []
    if (
        application.current_stage == "compliance_review"
        and gates["credit"].outcome != "ready"
    ):
        stage_inconsistencies.append("compliance_review_requires_credit_ready")
    if application.current_stage in {"operations_review", "decision_preparation"} and blockers:
        stage_inconsistencies.append("current_stage_requires_ready_upstream_gates")
    return OperationsFacts(
        missing_documents=sorted(
            item.document_type
            for item in application.documents
            if item.status == "missing"
        ),
        pending_documents=sorted(
            item.document_type
            for item in application.documents
            if item.status == "pending_verification"
        ),
        upstream_blockers=blockers,
        stage_inconsistencies=stage_inconsistencies,
    )


class MissingOperationsDocument(StrictModel):
    document_type: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class OperationsAction(StrictModel):
    sequence: int = Field(ge=1)
    action: str = Field(min_length=1)
    owner_role: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class OperationsDecisionDraft(StrictModel):
    readiness: Readiness
    missing_documents: list[MissingOperationsDocument] = Field(default_factory=list)
    next_actions: list[OperationsAction] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)


class OperationsDecisionExecution(StrictModel):
    draft: OperationsDecisionDraft
    trusted_evidence: list[KnowledgeEvidence]


class OperationsAssessment(StrictModel):
    case_id: str
    loan_type: Literal["personal", "sme"]
    current_stage: LoanStage
    readiness: Readiness
    facts: OperationsFacts
    missing_documents: list[MissingOperationsDocument]
    next_actions: list[OperationsAction]
    missing_data: list[str]
    evidence: list[KnowledgeEvidence]


def fail_closed_operations_assessment(
    application: OperationsApplication,
    facts: OperationsFacts,
    missing_data: list[str],
) -> OperationsAssessment:
    return OperationsAssessment(
        case_id=application.case_id,
        loan_type=application.loan_type,
        current_stage=application.current_stage,
        readiness="undetermined",
        facts=facts,
        missing_documents=[],
        next_actions=[],
        missing_data=sorted(set(missing_data)),
        evidence=[],
    )


def _referenced_evidence_ids(draft: OperationsDecisionDraft) -> set[str]:
    return {
        evidence_id
        for item in [*draft.missing_documents, *draft.next_actions]
        for evidence_id in item.evidence_ids
    }


def assemble_operations_assessment(
    application: OperationsApplication,
    facts: OperationsFacts,
    draft: OperationsDecisionDraft,
    trusted_evidence: list[KnowledgeEvidence],
) -> OperationsAssessment:
    if not trusted_evidence:
        return fail_closed_operations_assessment(application, facts, ["rag_evidence"])

    trusted_by_id = evidence_by_id(trusted_evidence)
    for source_id, item in evidence_by_id(draft.evidence).items():
        if trusted_by_id.get(source_id) != item:
            raise ValueError(f"Untrusted model evidence: {source_id}")
    unknown_ids = sorted(_referenced_evidence_ids(draft) - trusted_by_id.keys())
    if unknown_ids:
        raise ValueError(f"Unknown evidence ids: {', '.join(unknown_ids)}")
    if draft.missing_data:
        return fail_closed_operations_assessment(
            application,
            facts,
            draft.missing_data,
        )
    if draft.readiness == "undetermined":
        if draft.next_actions or draft.missing_documents:
            raise ValueError("Contradictory undetermined operations assessment")
        return fail_closed_operations_assessment(
            application,
            facts,
            ["agent_undetermined"],
        )
    if not draft.next_actions:
        raise ValueError("Determinate operations assessment requires a next action")
    expected_sequence = list(range(1, len(draft.next_actions) + 1))
    if [item.sequence for item in draft.next_actions] != expected_sequence:
        raise ValueError("Operations action sequence must be continuous from 1")
    if draft.readiness == "ready_for_next_step" and (
        facts.has_blockers or draft.missing_documents
    ):
        raise ValueError("Operations blockers cannot be ready for the next step")
    if draft.readiness == "needs_documents":
        if not draft.missing_documents:
            raise ValueError("needs_documents requires a missing document")
        documented_types = {
            item.document_type.casefold() for item in draft.missing_documents
        }
        known_missing_types = {
            item.casefold()
            for item in [*facts.missing_documents, *facts.pending_documents]
        }
        if not known_missing_types.issubset(documented_types):
            raise ValueError("Operations assessment must include every missing document")
    escalated_gate = any(
        blocker.endswith(("escalated", "undetermined"))
        for blocker in facts.upstream_blockers
    )
    if escalated_gate and draft.readiness != "needs_specialist_review":
        raise ValueError("Escalated upstream gates require specialist review")

    return OperationsAssessment(
        case_id=application.case_id,
        loan_type=application.loan_type,
        current_stage=application.current_stage,
        readiness=draft.readiness,
        facts=facts,
        missing_documents=draft.missing_documents,
        next_actions=draft.next_actions,
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
            "Plan the next operational steps for one loan application. "
            "If loan_profile_id is present, you may call get_loan_profile, then use only "
            "its customer_id with get_customer, and may call list_reports with that same "
            "loan_profile_id. Never call loan-data tools when loan_profile_id is absent. "
            "Before proposing a policy-derived action, call search_knowledge with "
            "domain='operations' and top_k=5. If a chunk is insufficient, call "
            "get_document_page only with a source_id returned by that search. Use loan-data "
            "results only as case facts; only RAG results are policy evidence. Treat supplied "
            "facts as immutable. Propose actions only: never create tasks, reports, checklists, "
            "or update case status. Return undetermined when evidence is insufficient and cite "
            "every missing document and next action."
        ),
        model=model,
        mcp_servers=[server],
        output_type=OperationsDecisionDraft,
    )


def build_agent_input(
    application: OperationsApplication,
    facts: OperationsFacts,
) -> str:
    return json.dumps(
        {
            "application": application.model_dump(mode="json"),
            "facts": facts.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )


async def execute_operations_decision(
    application: OperationsApplication,
    facts: OperationsFacts,
    mcp_url: str,
    model: str,
) -> OperationsDecisionExecution:
    async with build_agent_mcp_server(mcp_url) as server:
        assert_expected_agent_tools(await server.list_tools())
        result = await Runner.run(
            build_operations_agent(server, model),
            build_agent_input(application, facts),
            hooks=DomainRAGRunHooks("operations", application.loan_profile_id),
        )
    if not isinstance(result.final_output, OperationsDecisionDraft):
        raise TypeError("Operations Agent returned invalid structured output")
    return OperationsDecisionExecution(
        draft=result.final_output,
        trusted_evidence=extract_trusted_evidence(
            result.new_items,
            domain="operations",
            loan_profile_id=application.loan_profile_id,
        ),
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
        logger.error(
            "Operations assessment runtime/provenance failure [%s]",
            type(error).__name__,
        )
        return fail_closed_operations_assessment(
            application,
            facts,
            ["rag_or_agent_runtime"],
        )


def load_application(path: str) -> OperationsApplication:
    return OperationsApplication.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MediaX Operations Agent.")
    parser.add_argument("--input", required=True)
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
