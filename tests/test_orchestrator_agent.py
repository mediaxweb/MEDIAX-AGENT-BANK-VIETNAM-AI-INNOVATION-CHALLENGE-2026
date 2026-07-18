from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import orchestrator_agent
from compliance_agent import (
    ComplianceAssessment,
    calculate_compliance_facts,
)
from credit_agent import CreditAssessment, calculate_credit_facts
from dossier_normalizer import (
    DossierEvidence,
    DossierExtractionDraft,
    DossierFileReference,
    DossierInputBoundaryResult,
    DossierNormalizationResult,
)
from operations_agent import DOCUMENT_RULES, OperationsAssessment, calculate_operations_facts
from orchestrator_agent import (
    QuestionAnswerDraft,
    QuestionExecution,
    answer_question,
    assemble_question_answer,
    build_final_report,
    DossierWorkflowResult,
    execute_question,
    load_application,
    run_credit_slice,
    run_dossier_assessment,
    run_orchestrator,
)
from rag_agent_support import KnowledgeEvidence


ROOT = Path(__file__).resolve().parents[1]


def normalized_credit_dossier(*, customer_type="enterprise"):
    return DossierNormalizationResult(
        dossier_id="DOSSIER-CREDIT-001",
        routing_batch_id="BATCH-001",
        files=[],
        page_count=1,
        facts=DossierExtractionDraft.model_validate(
            {
                "customer": {
                    "customer_type": customer_type,
                    "full_name": "Công ty TNHH Minh An",
                    "phone": "0901234567",
                    "tax_code": "0101234567",
                    "address": "Hà Nội",
                    "industry": "Phân phối hàng hóa",
                    "years_operating": 5,
                    "legal_representative_name": "Nguyễn Văn An",
                    "legal_representative_id": "001234567890",
                },
                "signer": {
                    "name": "Nguyễn Văn An",
                    "signed": True,
                    "is_customer_or_legal_representative": True,
                },
                "loan": {
                    "requested_amount": "8000000000",
                    "term_months": 12,
                    "purpose": "Bổ sung vốn lưu động",
                    "repayment_method": "Trả gốc cuối kỳ",
                    "total_capital_need": "10000000000",
                    "own_capital": "2000000000",
                    "supporting_document_value": "8000000000",
                    "repayment_source": "Doanh thu bán hàng",
                },
                "documents": [
                    {
                        "document_type": name,
                        "status": "provided",
                        "valid": True,
                        "readable": True,
                        "complete": True,
                        "format_valid": True,
                        "suspicious_alteration": False,
                    }
                    for name in DOCUMENT_RULES
                ],
                "consistency": {
                    "customer_name_matches": True,
                    "tax_code_matches": True,
                    "representative_matches": True,
                    "industry_matches_purpose": True,
                },
                "financials": [
                    {
                        "period": "2025",
                        "revenue": "13500000000",
                        "net_profit": "720000000",
                        "total_debt": "5000000000",
                        "equity": "5000000000",
                        "operating_cash_flow": "1500000000",
                    },
                    {
                        "period": "2024",
                        "revenue": "12000000000",
                        "net_profit": "600000000",
                        "total_debt": "4500000000",
                        "equity": "4500000000",
                    },
                ],
                "funding_plan": {
                    "total_capital_need": "10000000000",
                    "own_capital": "2000000000",
                    "supporting_document_value": "8000000000",
                    "purpose_fit": "fit",
                },
                "repayment_plan": {
                    "available_cash_flow": "1500000000",
                    "annual_debt_service": "1000000000",
                    "source_status": "documented",
                    "cash_flow_timing_aligned": True,
                },
                "collateral": {
                    "collateral_type": "land_house",
                    "value": "12000000000",
                    "ownership_status": "valid",
                    "valuation_date": "2026-06-20",
                    "dispute_status": "clear",
                    "liquidity": "high",
                    "third_party_documents_complete": True,
                },
                "compliance_documents": {
                    "latest_financial_statement_present": True,
                    "signer_authority": "valid",
                    "legal_documents": "complete",
                    "consistency": "consistent",
                    "anomaly": "none",
                },
                "screening": {
                    "pep": "clear",
                    "sanctions": "clear",
                    "beneficial_owner": "clear",
                },
            }
        ),
    )


def credit_assessment(application, **updates):
    facts = calculate_credit_facts(application).model_copy(update=updates)
    return CreditAssessment(
        case_id=application.case_id,
        customer_type=application.customer.customer_type,
        loan_profile_id=None,
        facts=facts,
        findings=[],
        required_actions=facts.required_actions,
        executed_actions=[],
        missing_data=[],
        evidence=[],
    )


def compliance_assessment(application, **updates):
    facts = calculate_compliance_facts(application).model_copy(update=updates)
    return ComplianceAssessment(
        case_id=application.case_id,
        loan_profile_id=application.loan_profile_id,
        facts=facts,
        findings=[],
        conditions=facts.conditions,
        executed_actions=[],
        missing_data=[],
        evidence=[],
    )


def operations_assessment(application):
    facts = calculate_operations_facts(application)
    return OperationsAssessment(
        case_id=application.case_id,
        loan_profile_id=application.loan_profile_id,
        current_status=application.current_status,
        facts=facts,
        next_actions=[],
        conditions=facts.conditions,
        executed_actions=[],
        missing_data=[],
        evidence=[],
    )


def test_credit_slice_maps_normalized_dossier_and_runs_only_credit():
    normalized = normalized_credit_dossier()

    async def prepare(*_, **__):
        return DossierInputBoundaryResult(
            status="ready",
            dossier_id=normalized.dossier_id,
            routing_batch_id=normalized.routing_batch_id,
            normalized=normalized,
        )

    async def run_credit(application, **_):
        assert application.case_id == normalized.dossier_id
        assert application.execution_mode == "assess"
        assert application.loan.requested_amount == Decimal("8000000000")
        return credit_assessment(application)

    result = asyncio.run(
        run_credit_slice(
            {},
            allowed_root=ROOT,
            input_preparer=prepare,
            credit_runner=run_credit,
        )
    )

    assert result.status == "completed"
    assert result.can_continue_to_compliance is True
    assert result.credit is not None
    assert result.credit.facts.result == "PASSED"


def test_credit_slice_does_not_run_credit_when_required_input_is_unknown():
    normalized = normalized_credit_dossier(customer_type=None)

    async def prepare(*_, **__):
        return DossierInputBoundaryResult(
            status="ready", dossier_id=normalized.dossier_id, normalized=normalized
        )

    async def must_not_run(*_, **__):
        raise AssertionError("Credit Agent must not run with unsafe defaults")

    result = asyncio.run(
        run_credit_slice(
            {},
            allowed_root=ROOT,
            input_preparer=prepare,
            credit_runner=must_not_run,
        )
    )

    assert result.status == "input_not_ready"
    assert result.stop_reason == "credit_input_incomplete"
    assert result.issues[0].fields == ["customer.customer_type"]


def test_credit_slice_stops_after_undetermined_credit_result():
    normalized = normalized_credit_dossier()

    async def prepare(*_, **__):
        return DossierInputBoundaryResult(
            status="ready", dossier_id=normalized.dossier_id, normalized=normalized
        )

    async def run_credit(application, **_):
        return credit_assessment(
            application,
            result="UNDETERMINED",
            can_create_loan_profile=True,
            can_forward_to_compliance=True,
        )

    result = asyncio.run(
        run_credit_slice(
            {},
            allowed_root=ROOT,
            input_preparer=prepare,
            credit_runner=run_credit,
        )
    )

    assert result.status == "completed"
    assert result.can_continue_to_compliance is False
    assert result.stop_reason == "credit_not_ready_for_compliance"
    assert result.credit is not None
    assert result.credit.facts.result == "UNDETERMINED"


def test_dossier_assessment_stops_when_compliance_fails():
    normalized = normalized_credit_dossier()
    calls: list[str] = []

    async def prepare(*_, **__):
        return DossierInputBoundaryResult(
            status="ready", dossier_id=normalized.dossier_id, normalized=normalized
        )

    async def run_credit(application, **_):
        calls.append("credit")
        return credit_assessment(application)

    async def run_compliance(application, **_):
        calls.append("compliance")
        assert application.credit_result.result == "PASSED"
        return compliance_assessment(
            application,
            result="FAILED",
            hard_stop_reasons=["policy_block"],
            recommended_limit=None,
        )

    async def must_not_run(*_, **__):
        raise AssertionError("Operations must not run after Compliance FAILED")

    result = asyncio.run(
        run_dossier_assessment(
            {},
            allowed_root=ROOT,
            assessment_date=date(2026, 7, 19),
            input_preparer=prepare,
            credit_runner=run_credit,
            compliance_runner=run_compliance,
            operations_runner=must_not_run,
        )
    )

    assert calls == ["credit", "compliance"]
    assert result.overall_result == "BLOCKED"
    assert result.stopped_after == "compliance"
    assert result.operations is None
    assert result.report is not None
    assert result.report.operations is None
    assert "Hồ sơ đang bị chặn" in result.report.answer


def test_dossier_assessment_runs_three_agents_and_caps_operations_limit():
    dossier_source = DossierEvidence(
        field="loan.requested_amount",
        file_id="FILE-001",
        page=2,
        excerpt="Số tiền đề nghị vay: 8.000.000.000 đồng",
        confidence=0.99,
    )
    normalized = normalized_credit_dossier()
    normalized = normalized.model_copy(
        update={
            "files": [
                DossierFileReference(
                    file_id="FILE-001",
                    file_ref="/tmp/ho_so.pdf",
                    original_filename="02_giay_de_nghi_cap_tin_dung.pdf",
                    source_path="02_giay_de_nghi_cap_tin_dung.pdf",
                )
            ],
            "facts": normalized.facts.model_copy(update={"evidence": [dossier_source]}),
        }
    )
    policy_source = KnowledgeEvidence(
        source_id="policy-001",
        file_name="quy_dinh_tin_dung.pdf",
        page="3",
        excerpt="Hạn mức phải nằm trong giới hạn chính sách.",
    )
    calls: list[str] = []

    async def prepare(*_, **__):
        return DossierInputBoundaryResult(
            status="ready", dossier_id=normalized.dossier_id, normalized=normalized
        )

    async def run_credit(application, **_):
        calls.append("credit")
        return credit_assessment(application)

    async def run_compliance(application, **_):
        calls.append("compliance")
        assert application.credit_result.result == "PASSED"
        return compliance_assessment(
            application,
            recommended_limit=Decimal("7000000000"),
        ).model_copy(update={"evidence": [policy_source]})

    async def run_operations(application, **_):
        calls.append("operations")
        assert application.credit_result.result == "PASSED"
        assert application.compliance_result.result == "PASSED"
        assert application.compliance_result.recommended_limit == Decimal("7000000000")
        return operations_assessment(application)

    result = asyncio.run(
        run_dossier_assessment(
            {},
            allowed_root=ROOT,
            assessment_date=date(2026, 7, 19),
            assessment_at=datetime(2026, 7, 19, 9, tzinfo=timezone.utc),
            input_preparer=prepare,
            credit_runner=run_credit,
            compliance_runner=run_compliance,
            operations_runner=run_operations,
        )
    )

    assert calls == ["credit", "compliance", "operations"]
    assert result.overall_result == "READY"
    assert result.operations is not None
    assert result.operations.facts.recommended_limit == Decimal("7000000000.00")
    assert result.report is not None
    assert result.report.credit is not None
    assert result.report.compliance is not None
    assert result.report.operations is not None
    assert "Hồ sơ đủ điều kiện trình phê duyệt" in result.report.answer
    assert "đã phê duyệt" not in result.report.answer
    assert result.report.dossier_sources[0].file_name == "02_giay_de_nghi_cap_tin_dung.pdf"
    assert result.report.policy_sources == [policy_source]


def test_final_report_maps_incomplete_and_review_results_without_fake_specialists():
    for overall_result, expected in (
        ("UNDETERMINED", "Chưa đủ thông tin để kết luận hồ sơ"),
        ("REVIEW_REQUIRED", "Hồ sơ cần rà soát hoặc bổ sung điều kiện"),
    ):
        report = build_final_report(
            DossierWorkflowResult(
                status="input_not_ready",
                overall_result=overall_result,
            ),
            None,
        )

        assert expected in report.answer
        assert report.credit is None
        assert report.compliance is None
        assert report.operations is None
        assert report.disclaimer in report.answer


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
