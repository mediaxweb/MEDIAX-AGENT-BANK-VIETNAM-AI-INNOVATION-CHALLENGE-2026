import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from compliance_agent import (
    ComplianceApplication,
    ComplianceDecisionDraft,
    ComplianceDecisionExecution,
    ComplianceFinding,
    assemble_compliance_assessment,
    calculate_compliance_facts,
    run_compliance_assessment,
)
from rag_agent_support import KnowledgeEvidence


def compliance_application(**overrides):
    payload = {
        "case_id": "COMPLIANCE-001",
        "loan_profile_id": "507f1f77bcf86cd799439011",
        "customer_type": "enterprise",
        "as_of_date": "2026-07-18",
        "requested_amount": "8000000000",
        "term_months": 12,
        "purpose": "Bổ sung vốn lưu động",
        "credit_result": {
            "legal_score": 92,
            "result": "CONDITIONAL",
            "hard_stop": False,
            "missing_documents": ["company_charter"],
        },
        "current_financials": {
            "period": "2025",
            "revenue": "13500000000",
            "net_profit": "720000000",
            "total_debt": "5000000000",
            "equity": "5000000000",
            "operating_cash_flow": "1100000000",
        },
        "previous_financials": {
            "period": "2024",
            "revenue": "12000000000",
            "net_profit": "600000000",
            "total_debt": "4500000000",
            "equity": "4500000000",
        },
        "funding_plan": {
            "total_capital_need": "10666666666.6667",
            "own_capital": "2666666666.6667",
            "supporting_document_value": "6936000000",
            "purpose_fit": "fit",
        },
        "repayment_plan": {
            "available_cash_flow": "1100000000",
            "annual_debt_service": "900000000",
            "source_status": "documented",
            "cash_flow_timing_aligned": True,
        },
        "collateral": {
            "collateral_type": "land_house",
            "value": "10000000000",
            "ownership_status": "valid",
            "valuation_date": "2026-04-18",
            "dispute_status": "clear",
            "liquidity": "high",
        },
    }
    payload.update(overrides)
    return ComplianceApplication.model_validate(payload)


def evidence():
    return KnowledgeEvidence(
        source_id="compliance-policy-1",
        file_name="compliance-policy.pdf",
        page="6",
        excerpt="A total score of 80 or more is Low Risk.",
    )


def draft(**overrides):
    item = evidence()
    payload = {
        "findings": [
            ComplianceFinding(
                summary="The case is Low Risk under the demo policy.",
                severity="info",
                evidence_ids=[item.source_id],
            )
        ],
        "evidence": [item],
    }
    payload.update(overrides)
    return ComplianceDecisionDraft.model_validate(payload)


def test_demo_case_scores_94_low_risk():
    facts = calculate_compliance_facts(compliance_application())

    assert facts.metrics.revenue_growth == "0.1250"
    assert facts.metrics.net_profit_margin == "0.0533"
    assert facts.metrics.debt_to_equity == "1.0000"
    assert facts.metrics.dscr == "1.2222"
    assert facts.score_breakdown == {
        "financial_capacity": 35,
        "funding_and_repayment": 24,
        "collateral": 25,
        "document_compliance": 10,
    }
    assert facts.total_score == 94
    assert facts.risk_rating == "Low Risk"
    assert facts.result == "PASSED"
    assert facts.max_loan_by_collateral == Decimal("8000000000.00")
    assert facts.dscr_adjusted_limit == Decimal("7200000000.00")


def test_dscr_below_one_is_a_hard_stop():
    application = compliance_application()
    application.repayment_plan.available_cash_flow = Decimal("855000000")

    facts = calculate_compliance_facts(application)

    assert facts.metrics.dscr == "0.9500"
    assert facts.result == "FAILED"
    assert facts.risk_rating == "Very High Risk"
    assert "dscr_below_1" in facts.hard_stop_reasons
    assert facts.recommended_limit is None


@pytest.mark.parametrize(
    "valuation_date,expected_collateral_score",
    [
        ("2026-01-18", 25),
        ("2025-12-18", 22),
        ("2025-06-18", 20),
    ],
)
def test_collateral_valuation_age_buckets(valuation_date, expected_collateral_score):
    application = compliance_application()
    application.collateral.valuation_date = valuation_date

    facts = calculate_compliance_facts(application)

    assert facts.score_breakdown["collateral"] == expected_collateral_score


@pytest.mark.parametrize(
    "collateral_type,value,expected_limit",
    [
        ("land_house", "10000000000", "8000000000.00"),
        ("car", "2000000000", "1300000000.00"),
        ("machinery", "2000000000", "1000000000.00"),
        ("inventory", "2000000000", "800000000.00"),
        ("receivables", "2000000000", "600000000.00"),
    ],
)
def test_ltv_limit_by_collateral_type(collateral_type, value, expected_limit):
    application = compliance_application()
    application.collateral.collateral_type = collateral_type
    application.collateral.value = value

    facts = calculate_compliance_facts(application)

    assert facts.max_loan_by_collateral == Decimal(expected_limit)


@pytest.mark.parametrize(
    "mutator,reason",
    [
        (lambda app: setattr(app.documents, "signer_authority", "invalid"), "invalid_signer_authority"),
        (lambda app: setattr(app.collateral, "dispute_status", "disputed"), "collateral_disputed"),
        (lambda app: setattr(app.collateral, "ownership_status", "missing"), "missing_collateral_ownership"),
        (lambda app: setattr(app.documents, "anomaly", "serious"), "serious_document_anomaly"),
        (lambda app: setattr(app.screening, "sanctions", "match"), "sanctions_match"),
    ],
)
def test_policy_hard_stops(mutator, reason):
    application = compliance_application()
    mutator(application)

    facts = calculate_compliance_facts(application)

    assert facts.result == "FAILED"
    assert reason in facts.hard_stop_reasons


def test_missing_latest_financial_statement_fails_without_division():
    application = compliance_application(
        current_financials=None,
        documents={"latest_financial_statement_present": False},
    )

    facts = calculate_compliance_facts(application)

    assert facts.metrics.net_profit_margin is None
    assert facts.result == "FAILED"
    assert "missing_latest_financial_statement" in facts.hard_stop_reasons


def test_invalid_negative_requested_amount_is_rejected():
    with pytest.raises(ValidationError):
        compliance_application(requested_amount="-1")


def test_assessment_keeps_trusted_evidence_and_deterministic_score():
    application = compliance_application()

    result = assemble_compliance_assessment(
        application,
        calculate_compliance_facts(application),
        draft(),
        [evidence()],
    )

    assert result.facts.total_score == 94
    assert result.evidence == [evidence()]


def test_assess_mode_rejects_executed_actions():
    application = compliance_application()

    with pytest.raises(ValueError, match="Assess mode"):
        assemble_compliance_assessment(
            application,
            calculate_compliance_facts(application),
            draft(executed_actions=["save_compliance_result"]),
            [evidence()],
        )


def test_runner_uses_executor_and_returns_structured_assessment():
    application = compliance_application()

    async def executor(received_application, facts, mcp_url, model):
        assert received_application == application
        assert facts.total_score == 94
        assert mcp_url == "http://mcp.test/mcp"
        assert model == "test-model"
        return ComplianceDecisionExecution(draft=draft(), trusted_evidence=[evidence()])

    result = asyncio.run(
        run_compliance_assessment(
            application,
            mcp_url="http://mcp.test/mcp",
            model="test-model",
            decision_executor=executor,
        )
    )

    assert result.facts.risk_rating == "Low Risk"


def test_runtime_failure_is_redacted_and_fails_closed(caplog):
    sentinel = "COMPLIANCE_SECRET"

    async def executor(*args):
        raise RuntimeError(sentinel)

    result = asyncio.run(
        run_compliance_assessment(compliance_application(), decision_executor=executor)
    )

    assert result.facts.result == "UNDETERMINED"
    assert result.missing_data == ["rag_or_agent_runtime"]
    assert sentinel not in caplog.text
    assert "[RuntimeError]" in caplog.text
