from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

from compliance_agent import (
    ComplianceAssessment,
    calculate_compliance_facts,
)
from credit_agent import CreditAssessment, calculate_credit_facts
from operations_agent import OperationsAssessment, calculate_operations_facts
from orchestrator_agent import (
    QuestionAnswerDraft,
    QuestionExecution,
    answer_question,
    load_application,
    run_orchestrator,
)
from rag_agent_support import KnowledgeEvidence


ROOT = Path(__file__).resolve().parents[1]


def test_orchestrator_runs_specialists_in_order_with_authoritative_upstream_results():
    application = load_application(
        str(ROOT / "examples" / "credit_sme.json"),
        str(ROOT / "examples" / "compliance_sme.json"),
        str(ROOT / "examples" / "operations_sme.json"),
    )
    calls: list[str] = []

    async def run_credit(item, **_):
        calls.append("credit")
        facts = calculate_credit_facts(item)
        return CreditAssessment(
            case_id=item.case_id,
            customer_type=item.customer.customer_type,
            loan_profile_id=item.loan_profile_id,
            facts=facts,
            findings=[],
            required_actions=facts.required_actions,
            executed_actions=[],
            missing_data=[],
            evidence=[],
        )

    async def run_compliance(item, **_):
        calls.append("compliance")
        assert item.credit_result.legal_score == 92
        assert item.credit_result.result == "CONDITIONAL"
        facts = calculate_compliance_facts(item)
        return ComplianceAssessment(
            case_id=item.case_id,
            loan_profile_id=item.loan_profile_id,
            facts=facts,
            findings=[],
            conditions=facts.conditions,
            executed_actions=[],
            missing_data=[],
            evidence=[],
        )

    async def run_operations(item, **_):
        calls.append("operations")
        assert item.credit_result.legal_score == 92
        assert item.compliance_result.dscr == Decimal("1.2222")
        assert item.compliance_result.ltv_ratio == Decimal("0.8")
        facts = calculate_operations_facts(item)
        return OperationsAssessment(
            case_id=item.case_id,
            loan_profile_id=item.loan_profile_id,
            current_status=item.current_status,
            facts=facts,
            next_actions=[],
            conditions=facts.conditions,
            executed_actions=[],
            missing_data=[],
            evidence=[],
        )

    result = asyncio.run(
        run_orchestrator(
            application,
            credit_runner=run_credit,
            compliance_runner=run_compliance,
            operations_runner=run_operations,
        )
    )

    assert calls == ["credit", "compliance", "operations"]
    assert result.overall_result == "READY"
    assert result.stopped_after is None
    assert result.operations is not None
    assert result.operations.facts.recommended_limit == Decimal("7200000000.00")


def test_orchestrator_stops_when_credit_is_undetermined():
    application = load_application(
        str(ROOT / "examples" / "credit_sme.json"),
        str(ROOT / "examples" / "compliance_sme.json"),
        str(ROOT / "examples" / "operations_sme.json"),
    )

    async def run_credit(item, **_):
        facts = calculate_credit_facts(item).model_copy(
            update={
                "result": "UNDETERMINED",
                "can_create_loan_profile": False,
                "can_forward_to_compliance": False,
            }
        )
        return CreditAssessment(
            case_id=item.case_id,
            customer_type=item.customer.customer_type,
            loan_profile_id=item.loan_profile_id,
            facts=facts,
            findings=[],
            required_actions=facts.required_actions,
            executed_actions=[],
            missing_data=["rag_evidence"],
            evidence=[],
        )

    async def must_not_run(*_, **__):
        raise AssertionError("Downstream agent must not run")

    result = asyncio.run(
        run_orchestrator(
            application,
            credit_runner=run_credit,
            compliance_runner=must_not_run,
            operations_runner=must_not_run,
        )
    )

    assert result.overall_result == "UNDETERMINED"
    assert result.stopped_after == "credit"
    assert result.compliance is None
    assert result.operations is None


def test_question_answer_routes_and_returns_only_cited_trusted_evidence():
    source = KnowledgeEvidence(
        source_id="source-1",
        file_name="policy.pdf",
        page="2",
        excerpt="Tỷ lệ tối đa là 80%.",
    )

    session = object()

    async def answer(question, mcp_url, model, received_session):
        assert question == "Tỷ lệ cho vay tối đa là bao nhiêu?"
        assert (mcp_url, model, received_session) == (
            "http://mcp.test/mcp",
            "test-model",
            session,
        )
        return QuestionExecution(
            draft=QuestionAnswerDraft(
                domain="compliance",
                answer="Tỷ lệ tối đa là 80%.",
                evidence_ids=["source-1"],
            ),
            trusted_evidence=[source],
        )

    result = asyncio.run(
        answer_question(
            "Tỷ lệ cho vay tối đa là bao nhiêu?",
            mcp_url="http://mcp.test/mcp",
            model="test-model",
            session=session,
            question_answerer=answer,
        )
    )

    assert result.domain == "compliance"
    assert result.answer == "Tỷ lệ tối đa là 80%."
    assert result.sources == [source]
