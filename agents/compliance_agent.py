from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import date
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
ScreeningStatus = Literal[
    "clear",
    "potential_match",
    "confirmed_match",
    "not_checked",
]
ComplianceStatus = Literal[
    "no_blocker_identified",
    "needs_information",
    "escalate_compliance_review",
    "undetermined",
]
ComplianceRecommendation = Literal[
    "proceed_to_operations_review",
    "request_compliance_information",
    "escalate_compliance_review",
]
logger = logging.getLogger(__name__)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ComplianceDocument(StrictModel):
    document_type: str = Field(min_length=1)
    status: Literal["provided", "missing", "pending_verification"]
    document_id: str | None = Field(default=None, min_length=1)
    issuer: str | None = Field(default=None, min_length=1)
    issue_date: date | None = None
    expiry_date: date | None = None


class ComplianceApplication(StrictModel):
    case_id: str = Field(min_length=1)
    loan_profile_id: str | None = Field(default=None, min_length=1)
    loan_type: Literal["personal", "sme"]
    customer_type: Literal["individual", "business"]
    as_of_date: date
    documents: list[ComplianceDocument] = Field(default_factory=list)
    pep_status: ScreeningStatus
    sanctions_status: ScreeningStatus
    beneficial_owner_status: ScreeningStatus | None = None

    @model_validator(mode="after")
    def validate_case_shape(self):
        expected_customer_type = (
            "individual" if self.loan_type == "personal" else "business"
        )
        if self.customer_type != expected_customer_type:
            raise ValueError("customer_type does not match loan_type")
        if self.loan_type == "sme" and self.beneficial_owner_status is None:
            raise ValueError("SME applications require beneficial_owner_status")
        if self.loan_type == "personal" and self.beneficial_owner_status is not None:
            raise ValueError("Personal applications cannot have beneficial_owner_status")
        normalized_types = [item.document_type.casefold() for item in self.documents]
        if len(normalized_types) != len(set(normalized_types)):
            raise ValueError("document_type values must be unique")
        return self


class ComplianceFacts(StrictModel):
    missing_documents: list[str] = Field(default_factory=list)
    pending_documents: list[str] = Field(default_factory=list)
    expired_documents: list[str] = Field(default_factory=list)
    screening_flags: list[str] = Field(default_factory=list)

    @property
    def has_blockers(self) -> bool:
        return any(
            (
                self.missing_documents,
                self.pending_documents,
                self.expired_documents,
                self.screening_flags,
            )
        )


def calculate_compliance_facts(
    application: ComplianceApplication,
) -> ComplianceFacts:
    documents = application.documents
    screening_values = {
        "pep_status": application.pep_status,
        "sanctions_status": application.sanctions_status,
        "beneficial_owner_status": application.beneficial_owner_status,
    }
    return ComplianceFacts(
        missing_documents=sorted(
            item.document_type for item in documents if item.status == "missing"
        ),
        pending_documents=sorted(
            item.document_type
            for item in documents
            if item.status == "pending_verification"
        ),
        expired_documents=sorted(
            item.document_type
            for item in documents
            if item.expiry_date is not None
            and item.expiry_date < application.as_of_date
        ),
        screening_flags=sorted(
            f"{name}:{value}"
            for name, value in screening_values.items()
            if value not in {None, "clear"}
        ),
    )


class ComplianceFinding(StrictModel):
    summary: str = Field(min_length=1)
    severity: Literal["info", "warning", "critical"]
    evidence_ids: list[str] = Field(min_length=1)


class MissingComplianceDocument(StrictModel):
    document_type: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class ComplianceDecisionDraft(StrictModel):
    status: ComplianceStatus
    recommendation: ComplianceRecommendation
    findings: list[ComplianceFinding] = Field(default_factory=list)
    missing_documents: list[MissingComplianceDocument] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    evidence: list[KnowledgeEvidence] = Field(default_factory=list)


class ComplianceDecisionExecution(StrictModel):
    draft: ComplianceDecisionDraft
    trusted_evidence: list[KnowledgeEvidence]


class ComplianceAssessment(StrictModel):
    case_id: str
    loan_type: Literal["personal", "sme"]
    status: ComplianceStatus
    recommendation: ComplianceRecommendation
    facts: ComplianceFacts
    findings: list[ComplianceFinding]
    missing_documents: list[MissingComplianceDocument]
    missing_data: list[str]
    evidence: list[KnowledgeEvidence]


def fail_closed_compliance_assessment(
    application: ComplianceApplication,
    facts: ComplianceFacts,
    missing_data: list[str],
) -> ComplianceAssessment:
    return ComplianceAssessment(
        case_id=application.case_id,
        loan_type=application.loan_type,
        status="undetermined",
        recommendation="request_compliance_information",
        facts=facts,
        findings=[],
        missing_documents=[],
        missing_data=sorted(set(missing_data)),
        evidence=[],
    )


def _referenced_evidence_ids(draft: ComplianceDecisionDraft) -> set[str]:
    return {
        evidence_id
        for item in [*draft.findings, *draft.missing_documents]
        for evidence_id in item.evidence_ids
    }


def assemble_compliance_assessment(
    application: ComplianceApplication,
    facts: ComplianceFacts,
    draft: ComplianceDecisionDraft,
    trusted_evidence: list[KnowledgeEvidence],
) -> ComplianceAssessment:
    if not trusted_evidence:
        return fail_closed_compliance_assessment(application, facts, ["rag_evidence"])

    trusted_by_id = evidence_by_id(trusted_evidence)
    for source_id, item in evidence_by_id(draft.evidence).items():
        if trusted_by_id.get(source_id) != item:
            raise ValueError(f"Untrusted model evidence: {source_id}")
    unknown_ids = sorted(_referenced_evidence_ids(draft) - trusted_by_id.keys())
    if unknown_ids:
        raise ValueError(f"Unknown evidence ids: {', '.join(unknown_ids)}")
    if draft.missing_data:
        return fail_closed_compliance_assessment(
            application,
            facts,
            draft.missing_data,
        )

    expected_recommendations = {
        "no_blocker_identified": "proceed_to_operations_review",
        "needs_information": "request_compliance_information",
        "escalate_compliance_review": "escalate_compliance_review",
        "undetermined": "request_compliance_information",
    }
    if draft.recommendation != expected_recommendations[draft.status]:
        raise ValueError("Contradictory compliance recommendation")
    if draft.status == "undetermined":
        if draft.findings or draft.missing_documents:
            raise ValueError("Contradictory undetermined compliance assessment")
        return fail_closed_compliance_assessment(
            application,
            facts,
            ["agent_undetermined"],
        )
    if not draft.findings and not draft.missing_documents:
        raise ValueError("Determinate compliance assessment requires a finding")
    if draft.status == "no_blocker_identified" and (
        facts.has_blockers or draft.missing_documents
    ):
        raise ValueError("Compliance blockers cannot produce a clear assessment")
    if any(
        flag.endswith(("potential_match", "confirmed_match"))
        for flag in facts.screening_flags
    ) and draft.status != "escalate_compliance_review":
        raise ValueError("Screening matches require compliance escalation")

    return ComplianceAssessment(
        case_id=application.case_id,
        loan_type=application.loan_type,
        status=draft.status,
        recommendation=draft.recommendation,
        facts=facts,
        findings=draft.findings,
        missing_documents=draft.missing_documents,
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
            "Assess legal and compliance readiness for one loan application. "
            "If loan_profile_id is present, you may call get_loan_profile, then use only "
            "its customer_id with get_customer, and may call list_reports with that same "
            "loan_profile_id. Never call loan-data tools when loan_profile_id is absent. "
            "Before any policy finding, call search_knowledge with domain='compliance' "
            "and top_k=5. If a chunk is insufficient, call get_document_page only with a "
            "source_id returned by that search. Use loan-data results only as case facts; "
            "only RAG results are policy evidence. Treat supplied facts as immutable. "
            "Never approve, reject, upload, save, or update a loan. Return undetermined "
            "when evidence is insufficient and cite every finding or missing document."
        ),
        model=model,
        mcp_servers=[server],
        output_type=ComplianceDecisionDraft,
    )


def build_agent_input(
    application: ComplianceApplication,
    facts: ComplianceFacts,
) -> str:
    return json.dumps(
        {
            "application": application.model_dump(mode="json"),
            "facts": facts.model_dump(mode="json"),
        },
        ensure_ascii=False,
    )


async def execute_compliance_decision(
    application: ComplianceApplication,
    facts: ComplianceFacts,
    mcp_url: str,
    model: str,
) -> ComplianceDecisionExecution:
    async with build_agent_mcp_server(mcp_url) as server:
        assert_expected_agent_tools(await server.list_tools())
        result = await Runner.run(
            build_compliance_agent(server, model),
            build_agent_input(application, facts),
            hooks=DomainRAGRunHooks("compliance", application.loan_profile_id),
        )
    if not isinstance(result.final_output, ComplianceDecisionDraft):
        raise TypeError("Compliance Agent returned invalid structured output")
    return ComplianceDecisionExecution(
        draft=result.final_output,
        trusted_evidence=extract_trusted_evidence(
            result.new_items,
            domain="compliance",
            loan_profile_id=application.loan_profile_id,
        ),
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
        logger.error(
            "Compliance assessment runtime/provenance failure [%s]",
            type(error).__name__,
        )
        return fail_closed_compliance_assessment(
            application,
            facts,
            ["rag_or_agent_runtime"],
        )


def load_application(path: str) -> ComplianceApplication:
    return ComplianceApplication.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the MediaX Compliance Agent.")
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
        run_compliance_assessment(
            load_application(args.input),
            mcp_url=args.mcp_url,
            model=args.model,
        )
    )
    print(assessment.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
