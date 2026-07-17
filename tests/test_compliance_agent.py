import asyncio

import pytest
from pydantic import ValidationError

from compliance_agent import (
    ComplianceApplication,
    ComplianceDecisionDraft,
    ComplianceDecisionExecution,
    ComplianceFinding,
    MissingComplianceDocument,
    assemble_compliance_assessment,
    calculate_compliance_facts,
    run_compliance_assessment,
)
from rag_agent_support import KnowledgeEvidence


def personal_application(**overrides):
    payload = {
        "case_id": "CASE-C-001",
        "loan_type": "personal",
        "customer_type": "individual",
        "as_of_date": "2026-07-18",
        "documents": [
            {
                "document_type": "identity",
                "status": "provided",
                "expiry_date": "2030-01-01",
            }
        ],
        "pep_status": "clear",
        "sanctions_status": "clear",
    }
    payload.update(overrides)
    return ComplianceApplication.model_validate(payload)


def evidence():
    return KnowledgeEvidence(
        source_id="compliance-policy-1",
        file_name="compliance-policy.pdf",
        page="4",
        excerpt="Required compliance controls for personal loans.",
    )


def clear_draft():
    item = evidence()
    return ComplianceDecisionDraft(
        status="no_blocker_identified",
        recommendation="proceed_to_operations_review",
        findings=[
            ComplianceFinding(
                summary="No policy blocker was identified.",
                severity="info",
                evidence_ids=[item.source_id],
            )
        ],
        evidence=[item],
    )


def test_personal_facts_are_calculated_from_dates_and_screening():
    application = personal_application(
        documents=[
            {
                "document_type": "identity",
                "status": "provided",
                "expiry_date": "2026-07-17",
            },
            {"document_type": "residence", "status": "missing"},
            {"document_type": "income", "status": "pending_verification"},
        ],
        pep_status="not_checked",
    )

    facts = calculate_compliance_facts(application)

    assert facts.expired_documents == ["identity"]
    assert facts.missing_documents == ["residence"]
    assert facts.pending_documents == ["income"]
    assert facts.screening_flags == ["pep_status:not_checked"]


def test_sme_requires_beneficial_owner_screening():
    with pytest.raises(ValidationError, match="beneficial_owner_status"):
        ComplianceApplication.model_validate(
            {
                "case_id": "CASE-SME-001",
                "loan_type": "sme",
                "customer_type": "business",
                "as_of_date": "2026-07-18",
                "pep_status": "clear",
                "sanctions_status": "clear",
            }
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"customer_type": "business"},
        {"beneficial_owner_status": "clear"},
        {
            "documents": [
                {"document_type": "identity", "status": "provided"},
                {"document_type": "Identity", "status": "provided"},
            ]
        },
        {"loan_profile_id": "  "},
    ],
)
def test_invalid_compliance_case_shapes_are_rejected(overrides):
    with pytest.raises(ValidationError):
        personal_application(**overrides)


def test_clear_assessment_keeps_only_trusted_policy_evidence():
    application = personal_application()
    facts = calculate_compliance_facts(application)
    draft = clear_draft()

    result = assemble_compliance_assessment(
        application,
        facts,
        draft,
        [evidence()],
    )

    assert result.status == "no_blocker_identified"
    assert result.evidence == [evidence()]


def test_missing_document_cannot_produce_clear_assessment():
    application = personal_application(
        documents=[{"document_type": "identity", "status": "missing"}]
    )

    with pytest.raises(ValueError, match="blockers"):
        assemble_compliance_assessment(
            application,
            calculate_compliance_facts(application),
            clear_draft(),
            [evidence()],
        )


def test_screening_match_requires_escalation():
    application = personal_application(sanctions_status="potential_match")
    draft = clear_draft()
    draft.status = "needs_information"
    draft.recommendation = "request_compliance_information"

    with pytest.raises(ValueError, match="escalation"):
        assemble_compliance_assessment(
            application,
            calculate_compliance_facts(application),
            draft,
            [evidence()],
        )


def test_policy_missing_document_requires_trusted_evidence():
    application = personal_application()
    draft = ComplianceDecisionDraft(
        status="needs_information",
        recommendation="request_compliance_information",
        missing_documents=[
            MissingComplianceDocument(
                document_type="residence",
                reason="Required by policy",
                evidence_ids=["fabricated"],
            )
        ],
        evidence=[evidence()],
    )

    with pytest.raises(ValueError, match="Unknown evidence ids"):
        assemble_compliance_assessment(
            application,
            calculate_compliance_facts(application),
            draft,
            [evidence()],
        )


def test_model_missing_data_fails_closed():
    application = personal_application()
    draft = ComplianceDecisionDraft(
        status="undetermined",
        recommendation="request_compliance_information",
        missing_data=["policy_scope"],
    )

    result = assemble_compliance_assessment(
        application,
        calculate_compliance_facts(application),
        draft,
        [evidence()],
    )

    assert result.status == "undetermined"
    assert result.missing_data == ["policy_scope"]
    assert result.evidence == []


def test_runner_uses_executor_and_returns_structured_assessment():
    application = personal_application()

    async def executor(received_application, facts, mcp_url, model):
        assert received_application == application
        assert not facts.has_blockers
        assert mcp_url == "http://mcp.test/mcp"
        assert model == "test-model"
        return ComplianceDecisionExecution(
            draft=clear_draft(),
            trusted_evidence=[evidence()],
        )

    result = asyncio.run(
        run_compliance_assessment(
            application,
            mcp_url="http://mcp.test/mcp",
            model="test-model",
            decision_executor=executor,
        )
    )

    assert result.status == "no_blocker_identified"


def test_runner_redacts_runtime_failure(caplog):
    sentinel = "COMPLIANCE_SECRET"

    async def executor(*args):
        raise RuntimeError(sentinel)

    result = asyncio.run(
        run_compliance_assessment(
            personal_application(),
            decision_executor=executor,
        )
    )

    assert result.status == "undetermined"
    assert result.missing_data == ["rag_or_agent_runtime"]
    assert sentinel not in caplog.text
    assert "[RuntimeError]" in caplog.text
