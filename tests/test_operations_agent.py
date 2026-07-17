import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from operations_agent import (
    DOCUMENT_RULES,
    OperationsAction,
    OperationsApplication,
    OperationsDecisionDraft,
    OperationsDecisionExecution,
    assemble_operations_assessment,
    calculate_operations_facts,
    run_operations_assessment,
)
from rag_agent_support import KnowledgeEvidence


def operations_application(*, missing=(), **overrides):
    payload = {
        "case_id": "OPERATIONS-001",
        "loan_profile_id": "507f1f77bcf86cd799439011",
        "customer_type": "enterprise",
        "current_status": "S07",
        "as_of_at": "2026-07-18T01:00:00+07:00",
        "stage_started_at": "2026-07-17T00:00:00+07:00",
        "requested_amount": "8000000000",
        "total_capital_need": "10000000000",
        "own_capital": "2000000000",
        "term_months": 12,
        "purpose": "Bổ sung vốn lưu động",
        "repayment_method": "Trả gốc cuối kỳ",
        "documents": [
            {
                "document_type": document_type,
                "status": "missing" if document_type in missing else "provided",
            }
            for document_type in DOCUMENT_RULES
        ],
        "credit_result": {
            "legal_score": 92,
            "result": "CONDITIONAL",
            "hard_stop_reasons": [],
        },
        "compliance_result": {
            "total_score": 94,
            "risk_rating": "Low Risk",
            "result": "PASSED",
            "dscr": "1.35",
            "collateral_type": "land_house",
            "collateral_value": "10000000000",
            "ltv_ratio": "0.80",
            "hard_stop_reasons": [],
            "conditions": [],
        },
    }
    payload.update(overrides)
    return OperationsApplication.model_validate(payload)


def evidence():
    return KnowledgeEvidence(
        source_id="operations-policy-1",
        file_name="operations-policy.pdf",
        page="5",
        excerpt="A checklist score of at least 90 uses a 100 percent factor.",
    )


def draft_for(facts, **overrides):
    item = evidence()
    actions = [
        OperationsAction(
            sequence=index,
            code=code,
            action=code.replace(":", " "),
            owner_role="loan_operations",
            reason="Required by the demo operations policy.",
            evidence_ids=[item.source_id],
        )
        for index, code in enumerate(facts.next_action_codes, start=1)
    ]
    payload = {"next_actions": actions, "evidence": [item]}
    payload.update(overrides)
    return OperationsDecisionDraft.model_validate(payload)


def test_eight_billion_example_uses_full_limit():
    application = operations_application(
        missing=("company_charter", "missing_document_checklist"),
    )

    facts = calculate_operations_facts(application)

    assert facts.checklist_score == 94
    assert facts.capital_need_limit == Decimal("8000000000.00")
    assert facts.collateral_limit == Decimal("8000000000.00")
    assert facts.dscr_factor == "1.00"
    assert facts.checklist_factor == "1.00"
    assert facts.recommended_limit == Decimal("8000000000.00")
    assert facts.proposed_status == "S09"


def test_medium_cash_flow_and_84_checklist_produce_7_2_billion():
    application = operations_application(
        missing=(
            "company_charter",
            "previous_financial_statement",
            "collateral_inspection",
            "cash_flow_statement",
            "missing_document_checklist",
            "processing_ticket",
        )
    )
    application.compliance_result.dscr = Decimal("1.15")

    facts = calculate_operations_facts(application)

    assert facts.checklist_score == 84
    assert facts.dscr_factor == "0.90"
    assert facts.checklist_factor == "0.90"
    assert facts.final_factor == "0.90"
    assert facts.recommended_limit == Decimal("7200000000.00")
    assert facts.proposed_status == "S08"


def test_dscr_below_one_produces_zero_and_blocks_case():
    application = operations_application(
        missing=("company_charter", "missing_document_checklist"),
    )
    application.compliance_result.dscr = Decimal("0.95")
    application.compliance_result.result = "FAILED"
    application.compliance_result.hard_stop_reasons = ["dscr_below_1"]

    facts = calculate_operations_facts(application)

    assert facts.dscr_factor == "0"
    assert facts.recommended_limit == Decimal("0.00")
    assert facts.result == "BLOCKED"
    assert facts.proposed_status == "S10"


def test_car_collateral_caps_limit_at_1_3_billion():
    application = operations_application(
        missing=("company_charter", "missing_document_checklist"),
    )
    application.compliance_result.collateral_type = "car"
    application.compliance_result.collateral_value = Decimal("2000000000")
    application.compliance_result.ltv_ratio = Decimal("0.65")

    facts = calculate_operations_facts(application)

    assert facts.collateral_limit == Decimal("1300000000.00")
    assert facts.recommended_limit == Decimal("1300000000.00")


def test_missing_latest_financial_statement_routes_to_s04():
    application = operations_application(missing=("latest_financial_statement",))

    facts = calculate_operations_facts(application)

    assert facts.proposed_status == "S04"
    assert "latest_financial_statement" in facts.missing_required_documents
    assert facts.result == "BLOCKED"


def test_s11_requires_human_approval_and_completed_conditions():
    with pytest.raises(ValidationError, match="S11"):
        operations_application(current_status="S11")

    application = operations_application(
        current_status="S09",
        human_approved=True,
        disbursement_conditions_complete=True,
    )

    facts = calculate_operations_facts(application)

    assert facts.proposed_status == "S11"
    assert "create_disbursement_task" in facts.next_action_codes


def test_sla_breach_and_large_conditional_case_gets_p2():
    application = operations_application(missing=("company_charter",))

    facts = calculate_operations_facts(application)

    assert facts.sla_breached is True
    assert facts.ticket_priority == "P2"


def test_serious_hard_stop_gets_p1():
    application = operations_application()
    application.compliance_result.result = "FAILED"
    application.compliance_result.hard_stop_reasons = ["collateral_disputed"]

    facts = calculate_operations_facts(application)

    assert facts.ticket_priority == "P1"


def test_duplicate_document_types_are_rejected():
    with pytest.raises(ValidationError, match="unique"):
        operations_application(
            documents=[
                {"document_type": "credit_request", "status": "provided"},
                {"document_type": "Credit_Request", "status": "provided"},
            ]
        )


def test_assessment_keeps_required_actions_and_evidence():
    application = operations_application(
        missing=("company_charter", "missing_document_checklist"),
    )
    facts = calculate_operations_facts(application)

    result = assemble_operations_assessment(
        application,
        facts,
        draft_for(facts),
        [evidence()],
    )

    assert result.facts.recommended_limit == Decimal("8000000000.00")
    assert {item.code for item in result.next_actions} == set(facts.next_action_codes)
    assert result.evidence == [evidence()]


def test_action_sequence_must_be_continuous():
    application = operations_application()
    facts = calculate_operations_facts(application)
    invalid = draft_for(facts)
    invalid.next_actions[0].sequence = 2

    with pytest.raises(ValueError, match="sequence"):
        assemble_operations_assessment(application, facts, invalid, [evidence()])


def test_assess_mode_rejects_executed_actions():
    application = operations_application()
    facts = calculate_operations_facts(application)

    with pytest.raises(ValueError, match="Assess mode"):
        assemble_operations_assessment(
            application,
            facts,
            draft_for(facts, executed_actions=["create_report"]),
            [evidence()],
        )


def test_runner_uses_executor_and_returns_structured_assessment():
    application = operations_application()

    async def executor(received_application, facts, mcp_url, model):
        assert received_application == application
        assert facts.checklist_score == 100
        assert mcp_url == "http://mcp.test/mcp"
        assert model == "test-model"
        return OperationsDecisionExecution(
            draft=draft_for(facts),
            trusted_evidence=[evidence()],
        )

    result = asyncio.run(
        run_operations_assessment(
            application,
            mcp_url="http://mcp.test/mcp",
            model="test-model",
            decision_executor=executor,
        )
    )

    assert result.facts.proposed_status == "S09"


def test_runtime_failure_is_redacted_and_fails_closed(caplog):
    sentinel = "OPERATIONS_SECRET"

    async def executor(*args):
        raise RuntimeError(sentinel)

    result = asyncio.run(
        run_operations_assessment(operations_application(), decision_executor=executor)
    )

    assert result.facts.result == "UNDETERMINED"
    assert result.missing_data == ["rag_or_agent_runtime"]
    assert sentinel not in caplog.text
    assert "[RuntimeError]" in caplog.text
