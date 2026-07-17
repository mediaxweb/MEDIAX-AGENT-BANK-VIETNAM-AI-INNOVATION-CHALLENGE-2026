import asyncio

import pytest
from pydantic import ValidationError

from operations_agent import (
    MissingOperationsDocument,
    OperationsAction,
    OperationsApplication,
    OperationsDecisionDraft,
    OperationsDecisionExecution,
    assemble_operations_assessment,
    calculate_operations_facts,
    run_operations_assessment,
)
from rag_agent_support import KnowledgeEvidence


def operations_application(**overrides):
    payload = {
        "case_id": "CASE-O-001",
        "loan_type": "personal",
        "current_stage": "operations_review",
        "documents": [
            {"document_type": "identity", "status": "provided"},
            {"document_type": "income", "status": "provided"},
        ],
        "upstream_gates": [
            {"agent": "credit", "outcome": "ready"},
            {"agent": "compliance", "outcome": "ready"},
        ],
    }
    payload.update(overrides)
    return OperationsApplication.model_validate(payload)


def evidence():
    return KnowledgeEvidence(
        source_id="operations-policy-1",
        file_name="operations-policy.pdf",
        page="6",
        excerpt="Move a complete case to decision preparation.",
    )


def ready_draft():
    item = evidence()
    return OperationsDecisionDraft(
        readiness="ready_for_next_step",
        next_actions=[
            OperationsAction(
                sequence=1,
                action="Prepare the case for decision review.",
                owner_role="loan_operations",
                reason="The case and upstream gates are complete.",
                evidence_ids=[item.source_id],
            )
        ],
        evidence=[item],
    )


def test_operations_facts_include_documents_gates_and_stage_conflicts():
    application = operations_application(
        current_stage="decision_preparation",
        documents=[
            {"document_type": "identity", "status": "missing"},
            {"document_type": "income", "status": "pending_verification"},
        ],
        upstream_gates=[
            {
                "agent": "credit",
                "outcome": "needs_information",
                "blocking_items": ["income"],
            },
            {"agent": "compliance", "outcome": "ready"},
        ],
    )

    facts = calculate_operations_facts(application)

    assert facts.missing_documents == ["identity"]
    assert facts.pending_documents == ["income"]
    assert facts.upstream_blockers == ["credit:needs_information"]
    assert facts.stage_inconsistencies == [
        "current_stage_requires_ready_upstream_gates"
    ]


@pytest.mark.parametrize(
    "overrides",
    [
        {"upstream_gates": [{"agent": "credit", "outcome": "ready"}]},
        {
            "upstream_gates": [
                {"agent": "credit", "outcome": "ready"},
                {"agent": "credit", "outcome": "ready"},
            ]
        },
        {
            "documents": [
                {"document_type": "identity", "status": "provided"},
                {"document_type": "Identity", "status": "provided"},
            ]
        },
        {"loan_profile_id": "  "},
    ],
)
def test_invalid_operations_case_shapes_are_rejected(overrides):
    with pytest.raises(ValidationError):
        operations_application(**overrides)


def test_ready_assessment_keeps_only_trusted_policy_evidence():
    application = operations_application()

    result = assemble_operations_assessment(
        application,
        calculate_operations_facts(application),
        ready_draft(),
        [evidence()],
    )

    assert result.readiness == "ready_for_next_step"
    assert result.evidence == [evidence()]


def test_blockers_cannot_produce_ready_assessment():
    application = operations_application(
        documents=[{"document_type": "identity", "status": "missing"}]
    )

    with pytest.raises(ValueError, match="blockers"):
        assemble_operations_assessment(
            application,
            calculate_operations_facts(application),
            ready_draft(),
            [evidence()],
        )


def test_action_sequence_must_be_continuous_from_one():
    application = operations_application()
    draft = ready_draft()
    draft.next_actions[0].sequence = 2

    with pytest.raises(ValueError, match="sequence"):
        assemble_operations_assessment(
            application,
            calculate_operations_facts(application),
            draft,
            [evidence()],
        )


def test_needs_documents_requires_a_cited_missing_document():
    application = operations_application()
    draft = ready_draft()
    draft.readiness = "needs_documents"

    with pytest.raises(ValueError, match="requires a missing document"):
        assemble_operations_assessment(
            application,
            calculate_operations_facts(application),
            draft,
            [evidence()],
        )


def test_needs_documents_includes_every_known_missing_document():
    application = operations_application(
        documents=[
            {"document_type": "identity", "status": "missing"},
            {"document_type": "income", "status": "pending_verification"},
        ]
    )
    draft = ready_draft()
    draft.readiness = "needs_documents"
    draft.missing_documents = [
        MissingOperationsDocument(
            document_type="identity",
            reason="Required by policy.",
            evidence_ids=[evidence().source_id],
        )
    ]

    with pytest.raises(ValueError, match="every missing document"):
        assemble_operations_assessment(
            application,
            calculate_operations_facts(application),
            draft,
            [evidence()],
        )


def test_policy_missing_document_requires_trusted_evidence():
    application = operations_application()
    draft = OperationsDecisionDraft(
        readiness="needs_documents",
        missing_documents=[
            MissingOperationsDocument(
                document_type="residence",
                reason="Required by policy.",
                evidence_ids=["fabricated"],
            )
        ],
        next_actions=[
            OperationsAction(
                sequence=1,
                action="Request the residence document.",
                owner_role="loan_operations",
                reason="Required by policy.",
                evidence_ids=["fabricated"],
            )
        ],
        evidence=[evidence()],
    )

    with pytest.raises(ValueError, match="Unknown evidence ids"):
        assemble_operations_assessment(
            application,
            calculate_operations_facts(application),
            draft,
            [evidence()],
        )


def test_escalated_upstream_gate_requires_specialist_review():
    application = operations_application(
        current_stage="credit_review",
        upstream_gates=[
            {"agent": "credit", "outcome": "escalated"},
            {"agent": "compliance", "outcome": "ready"},
        ],
    )
    draft = ready_draft()
    draft.readiness = "needs_documents"
    draft.missing_documents = [
        MissingOperationsDocument(
            document_type="income",
            reason="Required by policy.",
            evidence_ids=[evidence().source_id],
        )
    ]

    with pytest.raises(ValueError, match="specialist review"):
        assemble_operations_assessment(
            application,
            calculate_operations_facts(application),
            draft,
            [evidence()],
        )


def test_model_missing_data_fails_closed():
    application = operations_application()
    draft = OperationsDecisionDraft(
        readiness="undetermined",
        missing_data=["operations_policy"],
    )

    result = assemble_operations_assessment(
        application,
        calculate_operations_facts(application),
        draft,
        [evidence()],
    )

    assert result.readiness == "undetermined"
    assert result.missing_data == ["operations_policy"]
    assert result.evidence == []


def test_runner_uses_executor_and_returns_structured_assessment():
    application = operations_application()

    async def executor(received_application, facts, mcp_url, model):
        assert received_application == application
        assert not facts.has_blockers
        assert mcp_url == "http://mcp.test/mcp"
        assert model == "test-model"
        return OperationsDecisionExecution(
            draft=ready_draft(),
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

    assert result.readiness == "ready_for_next_step"


def test_runner_redacts_runtime_failure(caplog):
    sentinel = "OPERATIONS_SECRET"

    async def executor(*args):
        raise RuntimeError(sentinel)

    result = asyncio.run(
        run_operations_assessment(
            operations_application(),
            decision_executor=executor,
        )
    )

    assert result.readiness == "undetermined"
    assert result.missing_data == ["rag_or_agent_runtime"]
    assert sentinel not in caplog.text
    assert "[RuntimeError]" in caplog.text
