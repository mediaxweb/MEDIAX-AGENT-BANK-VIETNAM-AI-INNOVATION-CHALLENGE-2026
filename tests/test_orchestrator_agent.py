from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import orchestrator_agent
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
    assemble_question_answer,
    execute_question,
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


def test_partial_answer_can_cite_trusted_evidence():
    source = KnowledgeEvidence(
        source_id="source-1",
        file_name="policy.pdf",
        page="2",
        excerpt="Hồ sơ phải có giấy chứng nhận quyền sở hữu.",
    )
    execution = QuestionExecution(
        draft=QuestionAnswerDraft(
            domain="credit",
            answer="Tài liệu xác nhận một giấy tờ bắt buộc nhưng chưa đủ danh sách đầy đủ.",
            evidence_ids=[source.source_id],
            insufficient_information=True,
        ),
        trusted_evidence=[source],
    )

    result = assemble_question_answer("Cần giấy tờ gì?", execution)

    assert result.insufficient_information is True
    assert result.sources == [source]


def test_general_question_preserves_orchestrator_answer():
    execution = QuestionExecution(
        draft=QuestionAnswerDraft(
            domain="general",
            answer="Chào anh/chị, em có thể hỗ trợ gì ạ?",
            evidence_ids=[],
            insufficient_information=True,
        ),
        trusted_evidence=[],
    )

    result = assemble_question_answer("alo", execution)

    assert result.domain == "general"
    assert result.answer == "Chào anh/chị, em có thể hỗ trợ gì ạ?"
    assert result.insufficient_information is True
    assert result.sources == []


def test_chat_agents_require_vietnamese_plain_text_answers():
    specialist = orchestrator_agent.build_question_agent(
        "credit",
        SimpleNamespace(),
        "test-model",
    )
    orchestrator = orchestrator_agent.build_chat_orchestrator([], "test-model")

    assert "Always write the user-facing answer in Vietnamese" in specialist.instructions
    assert "Every user-facing answer must be in Vietnamese" in orchestrator.instructions
    for agent in (specialist, orchestrator):
        assert "plain text only" in agent.instructions
        assert "Do not use Markdown syntax" in agent.instructions


def test_collect_specialist_output_logs_raw_answer(monkeypatch):
    seen_events: list[tuple[str, dict]] = []
    draft = QuestionAnswerDraft(
        domain="credit",
        answer="Cần bổ sung hồ sơ pháp lý.",
        evidence_ids=[],
        insufficient_information=True,
    )
    executions: list[QuestionExecution] = []

    monkeypatch.setattr(
        orchestrator_agent,
        "log_agent_event",
        lambda event, **fields: seen_events.append((event, fields)),
    )
    monkeypatch.setattr(
        orchestrator_agent,
        "extract_trusted_evidence",
        lambda *_args, **_kwargs: [],
    )

    raw_result = asyncio.run(
        orchestrator_agent._collect_specialist_output(
            SimpleNamespace(final_output=draft, new_items=[]),
            domain="credit",
            executions=executions,
        )
    )

    assert json.loads(raw_result)["answer"] == "Cần bổ sung hồ sơ pháp lý."
    assert executions[0].draft == draft
    assert seen_events[0][0] == "agent.raw_answer"
    assert seen_events[0][1]["agent"] == "Credit Knowledge Agent"
    assert seen_events[0][1]["raw_output"]["answer"] == "Cần bổ sung hồ sơ pháp lý."


def test_execute_question_preserves_orchestrator_answer_when_no_specialist(monkeypatch):
    seen_events: list[tuple[str, dict]] = []

    class FakeTool:
        def __init__(self, name):
            self.name = name

    class FakeServer:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def list_tools(self):
            return [FakeTool("search_knowledge"), FakeTool("get_document_page")]

    class FakeRunResult:
        final_output = QuestionAnswerDraft(
            domain="general",
            answer="Tôi có thể hỗ trợ nghiệp vụ tín dụng.",
            evidence_ids=[],
            insufficient_information=True,
        )

    async def fake_run(*_args, **_kwargs):
        return FakeRunResult()

    monkeypatch.setattr(
        orchestrator_agent,
        "build_question_mcp_server",
        lambda _mcp_url: FakeServer(),
    )
    monkeypatch.setattr(orchestrator_agent.Runner, "run", fake_run)
    monkeypatch.setattr(
        orchestrator_agent,
        "log_agent_event",
        lambda event, **fields: seen_events.append((event, fields)),
    )

    execution = asyncio.run(
        execute_question("alo", "http://mcp.test/mcp", "test-model")
    )

    assert execution.draft.domain == "general"
    assert execution.draft.answer == "Tôi có thể hỗ trợ nghiệp vụ tín dụng."
    assert execution.draft.insufficient_information is True
    assert execution.trusted_evidence == []
    assert [
        fields["raw_output"]["answer"]
        for event, fields in seen_events
        if event == "agent.raw_answer" and fields["agent"] == "Orchestrator"
    ] == ["Tôi có thể hỗ trợ nghiệp vụ tín dụng."]


def test_execute_question_returns_specialist_answer_when_orchestrator_rewrites(monkeypatch):
    seen_events: list[tuple[str, dict]] = []
    captured_extractors = {}
    source = KnowledgeEvidence(
        source_id="page:source-1",
        file_name="policy.pdf",
        page="4",
        excerpt="CCCD hết hạn là hard stop.",
    )
    specialist_draft = QuestionAnswerDraft(
        domain="compliance",
        answer=(
            "Hồ sơ pháp lý hiện không đủ điều kiện PASSED vì CCCD đã hết hạn. "
            "Cần bổ sung CCCD còn hiệu lực."
        ),
        evidence_ids=[source.source_id],
        insufficient_information=True,
    )
    rewritten_draft = QuestionAnswerDraft(
        domain="compliance",
        answer="Hồ sơ không đủ điều kiện PASSED. Cần bổ sung CCCD còn hiệu lực.",
        evidence_ids=[source.source_id],
        insufficient_information=True,
    )

    class FakeTool:
        def __init__(self, name):
            self.name = name

    class FakeServer:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def list_tools(self):
            return [FakeTool("search_knowledge"), FakeTool("get_document_page")]

    class FakeQuestionAgent:
        def as_tool(self, *, tool_name, custom_output_extractor, **_kwargs):
            captured_extractors[tool_name] = custom_output_extractor
            return SimpleNamespace(name=tool_name)

    class FakeRunResult:
        final_output = rewritten_draft

    async def fake_run(*_args, **_kwargs):
        await captured_extractors["ask_compliance_agent"](
            SimpleNamespace(final_output=specialist_draft, new_items=[])
        )
        return FakeRunResult()

    monkeypatch.setattr(
        orchestrator_agent,
        "build_question_mcp_server",
        lambda _mcp_url: FakeServer(),
    )
    monkeypatch.setattr(
        orchestrator_agent,
        "build_question_agent",
        lambda *_args, **_kwargs: FakeQuestionAgent(),
    )
    monkeypatch.setattr(orchestrator_agent.Runner, "run", fake_run)
    monkeypatch.setattr(
        orchestrator_agent,
        "extract_trusted_evidence",
        lambda *_args, **_kwargs: [source],
    )
    monkeypatch.setattr(
        orchestrator_agent,
        "log_agent_event",
        lambda event, **fields: seen_events.append((event, fields)),
    )

    execution = asyncio.run(
        execute_question("CCCD hết hạn thì sao?", "http://mcp.test/mcp", "test-model")
    )

    assert execution.draft == specialist_draft
    assert execution.trusted_evidence == [source]
    changed_events = [
        fields for event, fields in seen_events if event == "agent.routing.output_changed"
    ]
    assert changed_events
    assert changed_events[0]["specialist_raw_output"]["answer"] == specialist_draft.answer
    assert changed_events[0]["orchestrator_raw_output"]["answer"] == rewritten_draft.answer
