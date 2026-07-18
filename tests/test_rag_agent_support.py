import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
from agents import Agent
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.tool import ToolOrigin, ToolOriginType
from agents.tool_context import ToolContext
from openai.types.responses import ResponseFunctionToolCall

from rag_agent_support import (
    AGENT_MCP_TOOL_NAMES,
    AgentLoggingRunHooks,
    DomainRAGRunHooks,
    allowed_agent_tools,
    build_agent_mcp_server,
    build_agent_run_config,
    classify_agent_error,
    extract_called_tool_names,
    extract_trusted_evidence,
    log_agent_runtime_failure,
    validate_document_page_call,
    validate_search_knowledge_call,
)
import rag_agent_support


ORIGIN = ToolOrigin(type=ToolOriginType.MCP, mcp_server_name="agent-bank-tools")
EVIDENCE = {
    "source_id": "source-1",
    "file_name": "policy.pdf",
    "page": "1",
    "excerpt": "Policy evidence",
}


def tool_items(name, arguments, output, call_id):
    agent = Agent(name="Test Agent")
    return [
        ToolCallItem(
            agent=agent,
            raw_item=ResponseFunctionToolCall(
                arguments=json.dumps(arguments),
                call_id=call_id,
                name=name,
                type="function_call",
            ),
            tool_origin=ORIGIN,
        ),
        ToolCallOutputItem(
            agent=agent,
            raw_item={"type": "function_call_output", "call_id": call_id},
            output=output,
            tool_origin=ORIGIN,
        ),
    ]


@pytest.mark.parametrize("domain", ["credit", "compliance", "operations"])
def test_rag_contract_accepts_each_agent_domain(domain):
    assert validate_search_knowledge_call(
        "search_knowledge",
        json.dumps({"domain": domain, "query": "policy", "top_k": 5}),
        domain=domain,
    )["domain"] == domain
    assert validate_document_page_call(
        "get_document_page",
        json.dumps({"domain": domain, "source_id": "source-1"}),
        domain=domain,
    )["domain"] == domain


def test_rag_contract_rejects_another_agent_domain():
    with pytest.raises(ValueError, match="must be compliance"):
        validate_search_knowledge_call(
            "search_knowledge",
            json.dumps({"domain": "credit", "query": "policy", "top_k": 5}),
            domain="compliance",
        )


def test_agent_hooks_log_safe_structured_events(monkeypatch, caplog):
    monkeypatch.setattr(
        rag_agent_support,
        "get_current_trace",
        lambda: SimpleNamespace(trace_id="trace-test"),
    )
    hooks = AgentLoggingRunHooks("compliance")
    context = ToolContext(
        None,
        tool_name="search_knowledge",
        tool_call_id="call-search",
        tool_arguments=json.dumps(
            {"domain": "compliance", "query": "secret question", "top_k": 5}
        ),
    )
    agent = Agent(name="Compliance Knowledge Agent")

    with caplog.at_level(logging.INFO, logger="agent_trace"):
        asyncio.run(hooks.on_agent_start(context, agent))
        asyncio.run(hooks.on_tool_start(context, agent, object()))
        asyncio.run(
            hooks.on_tool_end(
                context,
                agent,
                object(),
                {"evidence": [EVIDENCE, EVIDENCE]},
            )
        )
        asyncio.run(hooks.on_agent_end(context, agent, {}))

    events = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "agent_trace"
    ]
    assert [event["event"] for event in events] == [
        "agent.started",
        "agent.tool.started",
        "agent.tool.completed",
        "agent.completed",
    ]
    assert events[1]["top_k"] == 5
    assert events[2]["evidence_count"] == 2
    assert all(event["trace_id"] == "trace-test" for event in events)
    assert "secret question" not in caplog.text


def test_agent_trace_sensitive_data_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA", raising=False)
    assert build_agent_run_config("test").trace_include_sensitive_data is False

    monkeypatch.setenv("OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA", "true")
    assert build_agent_run_config("test").trace_include_sensitive_data is True


def test_runtime_failure_is_classified_without_logging_error_details(caplog):
    model_error = type("ModelFailure", (Exception,), {"__module__": "openai.client"})
    tool_error = type("MCPFailure", (Exception,), {"__module__": "mcp.client"})

    assert classify_agent_error(model_error()) == "model"
    assert classify_agent_error(tool_error()) == "tool"
    assert classify_agent_error(ValueError("invalid evidence")) == "rag"
    assert classify_agent_error(ValueError("invalid deterministic output")) == (
        "deterministic_validation"
    )

    with caplog.at_level(logging.INFO, logger="agent_trace"):
        log_agent_runtime_failure("credit", ValueError("CCCD 001234567890"))

    event = json.loads(caplog.records[-1].getMessage())
    assert event["error_category"] == "deterministic_validation"
    assert event["error_type"] == "ValueError"
    assert "001234567890" not in caplog.text


def test_shared_mcp_client_has_five_read_only_tools():
    server = build_agent_mcp_server("http://mcp.test/mcp")

    assert server.name == "agent-bank-tools"
    assert server.tool_filter == {"allowed_tool_names": list(AGENT_MCP_TOOL_NAMES)}


def test_assess_mode_only_adds_read_only_domain_tools():
    assert allowed_agent_tools("credit", "assess") == (
        *AGENT_MCP_TOOL_NAMES,
        "search_customer",
    )
    assert allowed_agent_tools("compliance", "assess") == AGENT_MCP_TOOL_NAMES
    assert allowed_agent_tools("operations", "assess") == AGENT_MCP_TOOL_NAMES


def test_execute_mode_adds_only_the_selected_domain_tools():
    credit_tools = allowed_agent_tools("credit", "execute")
    operations_tools = allowed_agent_tools("operations", "execute")

    assert "create_customer" in credit_tools
    assert "create_task" not in credit_tools
    assert "create_task" in operations_tools
    assert "create_customer" not in operations_tools


def test_mutating_tool_is_rejected_in_assess_mode_before_execution():
    context = ToolContext(
        None,
        tool_name="create_customer",
        tool_call_id="call-create",
        tool_arguments=json.dumps({"full_name": "Demo"}),
    )

    with pytest.raises(ValueError, match="execution_mode=execute"):
        asyncio.run(
            DomainRAGRunHooks("credit", execution_mode="assess").on_tool_start(
                context,
                Agent(name="test"),
                object(),
            )
        )


def test_called_tool_names_preserve_mutation_order():
    items = tool_items(
        "create_task",
        {"loan_profile_id": "profile-1", "title": "Review", "priority": "P2"},
        {"id": "task-1", "loan_profile_id": "profile-1"},
        "call-task",
    )
    items += tool_items(
        "update_case_status",
        {"loan_profile_id": "profile-1", "status": "S08"},
        {"loan_profile_id": "profile-1", "status": "S08"},
        "call-status",
    )

    assert extract_called_tool_names(items) == ["create_task", "update_case_status"]


def test_loan_data_tool_requires_profile_id_in_agent_input():
    context = ToolContext(
        None,
        tool_name="get_loan_profile",
        tool_call_id="call-profile",
        tool_arguments=json.dumps({"loan_profile_id": "profile-1"}),
    )

    with pytest.raises(ValueError, match="require loan_profile_id"):
        asyncio.run(
            DomainRAGRunHooks("compliance").on_tool_start(
                context,
                Agent(name="test"),
                object(),
            )
        )


def test_loan_context_is_validated_but_not_returned_as_policy_evidence():
    items = []
    items += tool_items(
        "get_loan_profile",
        {"loan_profile_id": "profile-1"},
        {"id": "profile-1", "customer_id": "customer-1"},
        "call-profile",
    )
    items += tool_items(
        "get_customer",
        {"customer_id": "customer-1"},
        {"id": "customer-1", "full_name": "Demo"},
        "call-customer",
    )
    items += tool_items(
        "list_reports",
        {"loan_profile_id": "profile-1"},
        {
            "total_count": 1,
            "reports": [{"id": "report-1", "loan_profile_id": "profile-1"}],
        },
        "call-reports",
    )
    items += tool_items(
        "search_knowledge",
        {"domain": "operations", "query": "workflow", "top_k": 5},
        {"evidence": [EVIDENCE]},
        "call-search",
    )

    evidence = extract_trusted_evidence(
        items,
        domain="operations",
        loan_profile_id="profile-1",
    )

    assert [item.source_id for item in evidence] == ["source-1"]


def test_customer_tool_requires_customer_from_prior_profile_result():
    items = tool_items(
        "get_customer",
        {"customer_id": "customer-1"},
        {"id": "customer-1"},
        "call-customer",
    )
    items += tool_items(
        "search_knowledge",
        {"domain": "compliance", "query": "KYC", "top_k": 5},
        {"evidence": [EVIDENCE]},
        "call-search",
    )

    with pytest.raises(ValueError, match="prior loan profile"):
        extract_trusted_evidence(
            items,
            domain="compliance",
            loan_profile_id="profile-1",
        )
