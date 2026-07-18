from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from agents import Agent, Runner, Session
from agents.mcp import MCPServerStreamableHttp
from pydantic import BaseModel, ConfigDict, model_validator

from compliance_agent import (
    ComplianceApplication,
    ComplianceAssessment,
    run_compliance_assessment,
)
from credit_agent import CreditApplication, CreditAssessment, run_credit_assessment
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
QuestionAnswerer = Callable[
    [str, str, str, Session | None], Awaitable[QuestionExecution]
]


def _raw_question_answer_output(output: QuestionAnswerDraft) -> dict[str, Any]:
    return output.model_dump(mode="json")


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
    if dscr is None:
        raise ValueError("Compliance result does not contain DSCR")
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
                "ltv_ratio": compliance.facts.max_loan_by_collateral / collateral.value,
                "hard_stop_reasons": compliance.facts.hard_stop_reasons,
                "conditions": compliance.conditions,
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
    if not credit.facts.can_forward_to_compliance:
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
    if compliance.facts.result == "UNDETERMINED" or compliance.facts.metrics.dscr is None:
        return OrchestratorAssessment(
            case_id=application.credit.case_id,
            loan_profile_id=loan_profile_id,
            overall_result=(
                "BLOCKED" if compliance.facts.result == "FAILED" else "UNDETERMINED"
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
