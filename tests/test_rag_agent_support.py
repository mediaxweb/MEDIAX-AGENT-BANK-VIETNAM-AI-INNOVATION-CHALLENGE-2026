import asyncio
import json

import pytest
from agents import Agent
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.tool import ToolOrigin, ToolOriginType
from agents.tool_context import ToolContext
from openai.types.responses import ResponseFunctionToolCall

from rag_agent_support import (
    AGENT_MCP_TOOL_NAMES,
    DomainRAGRunHooks,
    build_agent_mcp_server,
    extract_trusted_evidence,
    validate_document_page_call,
    validate_search_knowledge_call,
)


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


def test_shared_mcp_client_has_five_read_only_tools():
    server = build_agent_mcp_server("http://mcp.test/mcp")

    assert server.name == "agent-bank-tools"
    assert server.tool_filter == {"allowed_tool_names": list(AGENT_MCP_TOOL_NAMES)}


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
