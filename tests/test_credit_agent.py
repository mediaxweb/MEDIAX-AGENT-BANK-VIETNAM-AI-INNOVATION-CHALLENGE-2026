import asyncio

import pytest
from pydantic import ValidationError

from credit_agent import (
    CreditApplication,
    CreditDecisionDraft,
    CreditDecisionExecution,
    CreditFinding,
    CustomerMatch,
    assemble_credit_assessment,
    calculate_credit_facts,
    run_credit_assessment,
)
from rag_agent_support import KnowledgeEvidence


def enterprise_application(**overrides):
    payload = {
        "case_id": "CREDIT-001",
        "customer": {
            "customer_type": "enterprise",
            "full_name": "Công ty TNHH Minh An",
            "phone": "0901234567",
            "email": "demo@example.com",
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
            "purpose": "Bổ sung vốn nhập hàng",
            "repayment_method": "Trả gốc cuối kỳ",
            "total_capital_need": "10000000000",
            "own_capital": "2000000000",
            "supporting_document_value": "8000000000",
            "repayment_source": "Doanh thu bán hàng",
            "capital_needed_at": "2026-08",
            "purchase_description": "Nhập hàng phân phối",
        },
        "documents": [
            {"document_type": "business_registration", "status": "provided"},
            {"document_type": "company_charter", "status": "missing"},
            {"document_type": "appointment_decision", "status": "provided"},
            {"document_type": "shareholders_information", "status": "provided"},
            {"document_type": "signature_sample", "status": "provided"},
            {"document_type": "legal_representative_id", "status": "provided"},
        ],
    }
    payload.update(overrides)
    return CreditApplication.model_validate(payload)


def evidence():
    return KnowledgeEvidence(
        source_id="credit-policy-1",
        file_name="credit-policy.pdf",
        page="1",
        excerpt="A legal score of 75 or more may open a conditional profile.",
    )


def draft(**overrides):
    item = evidence()
    payload = {
        "customer_match": CustomerMatch(
            customer_id="507f1f77bcf86cd799439011",
            score=100,
            action="reuse",
        ),
        "findings": [
            CreditFinding(
                summary="The company charter is missing.",
                severity="warning",
                evidence_ids=[item.source_id],
            )
        ],
        "required_actions": ["provide:company_charter"],
        "evidence": [item],
    }
    payload.update(overrides)
    return CreditDecisionDraft.model_validate(payload)


def test_enterprise_example_scores_92_and_remains_eligible():
    facts = calculate_credit_facts(enterprise_application())

    assert facts.legal_score == 92
    assert facts.score_breakdown == {
        "customer_identity": 25,
        "legal_status": 22,
        "signer_authority": 25,
        "consistency": 10,
        "file_quality": 10,
    }
    assert facts.result == "CONDITIONAL"
    assert facts.hard_stop_reasons == []
    assert facts.missing_documents == ["company_charter"]
    assert facts.can_create_loan_profile is True
    assert facts.can_forward_to_compliance is True


def test_unauthorized_signer_is_a_hard_stop():
    application = enterprise_application()
    application.signer.is_customer_or_legal_representative = False

    facts = calculate_credit_facts(application)

    assert facts.result == "FAILED"
    assert "unauthorized_signer" in facts.hard_stop_reasons
    assert facts.can_create_loan_profile is False


def test_loan_above_80_percent_is_conditional_with_eight_billion_cap():
    application = enterprise_application()
    application.loan.requested_amount = 9_000_000_000
    application.loan.own_capital = 1_000_000_000

    facts = calculate_credit_facts(application)

    assert facts.loan_to_capital_need_ratio == "0.9000"
    assert facts.max_amount_by_capital_need == 8_000_000_000
    assert facts.result == "CONDITIONAL"
    assert "reduce_requested_amount_to_80_percent_of_capital_need" in facts.required_actions


@pytest.mark.parametrize(
    "customer_type,customer,documents",
    [
        (
            "household_business",
            {
                "full_name": "Hộ kinh doanh Lan Phương",
                "national_id": "001234567890",
                "address": "Hà Nội",
                "industry": "Bán lẻ",
                "phone": "0901234567",
            },
            [
                "household_registration",
                "owner_identity",
                "business_activity_evidence",
                "bank_statements",
            ],
        ),
        (
            "individual",
            {
                "full_name": "Nguyễn Văn A",
                "national_id": "001234567890",
                "address": "Hà Nội",
                "occupation": "Kỹ sư",
                "phone": "0901234567",
            },
            ["identity", "income_evidence", "collateral_documents"],
        ),
    ],
)
def test_other_customer_types_can_reach_100_points(customer_type, customer, documents):
    application = CreditApplication.model_validate(
        {
            "case_id": "OTHER-001",
            "customer": {"customer_type": customer_type, **customer},
            "signer": {
                "signed": True,
                "is_customer_or_legal_representative": True,
            },
            "loan": {
                "requested_amount": 100_000_000,
                "term_months": 12,
                "purpose": "Vốn kinh doanh",
                "repayment_source": "Thu nhập",
            },
            "documents": [
                {"document_type": name, "status": "provided"} for name in documents
            ],
        }
    )

    facts = calculate_credit_facts(application)

    assert facts.legal_score == 100
    assert facts.result == "PASSED"


def test_duplicate_document_types_are_rejected():
    with pytest.raises(ValidationError, match="unique"):
        enterprise_application(
            documents=[
                {"document_type": "identity", "status": "provided"},
                {"document_type": "Identity", "status": "provided"},
            ]
        )


def test_assessment_keeps_deterministic_facts_and_trusted_evidence():
    application = enterprise_application()
    facts = calculate_credit_facts(application)

    result = assemble_credit_assessment(application, facts, draft(), [evidence()])

    assert result.facts.legal_score == 92
    assert result.customer_match.score == 100
    assert result.evidence == [evidence()]


def test_ambiguous_customer_match_blocks_profile_creation():
    application = enterprise_application()
    facts = calculate_credit_facts(application)
    ambiguous = draft(
        customer_match={"score": 90, "action": "verify"},
    )

    result = assemble_credit_assessment(application, facts, ambiguous, [evidence()])

    assert result.facts.result == "CONDITIONAL"
    assert result.facts.can_create_loan_profile is False
    assert "verify_possible_duplicate_customer" in result.required_actions


def test_assess_mode_rejects_executed_actions():
    application = enterprise_application()

    with pytest.raises(ValueError, match="Assess mode"):
        assemble_credit_assessment(
            application,
            calculate_credit_facts(application),
            draft(executed_actions=["create_loan_profile"]),
            [evidence()],
        )


def test_runner_uses_executor_and_returns_structured_assessment():
    application = enterprise_application()

    async def executor(received_application, facts, mcp_url, model):
        assert received_application == application
        assert facts.legal_score == 92
        assert mcp_url == "http://mcp.test/mcp"
        assert model == "test-model"
        return CreditDecisionExecution(draft=draft(), trusted_evidence=[evidence()])

    result = asyncio.run(
        run_credit_assessment(
            application,
            mcp_url="http://mcp.test/mcp",
            model="test-model",
            decision_executor=executor,
        )
    )

    assert result.facts.result == "CONDITIONAL"


def test_runtime_failure_is_redacted_and_fails_closed(caplog):
    sentinel = "CREDIT_SECRET"

    async def executor(*args):
        raise RuntimeError(sentinel)

    result = asyncio.run(
        run_credit_assessment(enterprise_application(), decision_executor=executor)
    )

    assert result.facts.result == "UNDETERMINED"
    assert result.missing_data == ["rag_or_agent_runtime"]
    assert sentinel not in caplog.text
    assert "[RuntimeError]" in caplog.text
