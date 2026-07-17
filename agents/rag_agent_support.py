from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal

from agents.items import ToolCallItem, ToolCallOutputItem
from agents.lifecycle import RunHooksBase
from agents.mcp import MCPServerStreamableHttp
from agents.tool import FunctionTool, ToolOriginType, get_function_tool_origin
from agents.tool_context import ToolContext
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


RAGDomain = Literal["credit", "compliance", "operations"]
AGENT_MCP_NAME = "agent-bank-tools"
AGENT_MCP_TOOL_NAMES = (
    "search_knowledge",
    "get_document_page",
    "get_loan_profile",
    "get_customer",
    "list_reports",
)
LOAN_DATA_ID_FIELDS = {
    "get_loan_profile": "loan_profile_id",
    "get_customer": "customer_id",
    "list_reports": "loan_profile_id",
}


class KnowledgeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    page: str | None = None
    excerpt: str = Field(min_length=1)


def evidence_by_id(
    evidence: list[KnowledgeEvidence],
) -> dict[str, KnowledgeEvidence]:
    by_id: dict[str, KnowledgeEvidence] = {}
    for item in evidence:
        if item.source_id in by_id:
            raise ValueError(f"Duplicate evidence source_id: {item.source_id}")
        by_id[item.source_id] = item
    return by_id


def _json_arguments(tool_name: str, raw_arguments: str) -> dict[str, Any]:
    try:
        arguments = json.loads(raw_arguments)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"{tool_name} arguments must be valid JSON") from error
    if not isinstance(arguments, dict):
        raise ValueError(f"{tool_name} arguments must be an object")
    return arguments


def validate_search_knowledge_call(
    tool_name: str,
    raw_arguments: str,
    *,
    domain: RAGDomain,
) -> dict[str, Any]:
    if tool_name != "search_knowledge":
        raise ValueError("Only search_knowledge may use the search contract")
    arguments = _json_arguments(tool_name, raw_arguments)
    if set(arguments) != {"domain", "query", "top_k"}:
        raise ValueError("search_knowledge requires exactly domain, query, and top_k")
    if arguments["domain"] != domain:
        raise ValueError(f"search_knowledge domain must be {domain}")
    if not isinstance(arguments["query"], str) or not arguments["query"].strip():
        raise ValueError("search_knowledge query must be a non-empty string")
    if type(arguments["top_k"]) is not int or arguments["top_k"] != 5:
        raise ValueError("search_knowledge top_k must be 5")
    return arguments


def validate_document_page_call(
    tool_name: str,
    raw_arguments: str,
    *,
    domain: RAGDomain,
) -> dict[str, Any]:
    if tool_name != "get_document_page":
        raise ValueError("Only get_document_page may use the page contract")
    arguments = _json_arguments(tool_name, raw_arguments)
    if set(arguments) != {"domain", "source_id"}:
        raise ValueError("get_document_page requires exactly domain and source_id")
    if arguments["domain"] != domain:
        raise ValueError(f"get_document_page domain must be {domain}")
    if not isinstance(arguments["source_id"], str) or not arguments["source_id"].strip():
        raise ValueError("get_document_page source_id must be a non-empty string")
    return arguments


def validate_loan_data_call(tool_name: str, raw_arguments: str) -> dict[str, Any]:
    field_name = LOAN_DATA_ID_FIELDS.get(tool_name)
    if field_name is None:
        raise ValueError("Unsupported loan data tool")
    arguments = _json_arguments(tool_name, raw_arguments)
    if set(arguments) != {field_name}:
        raise ValueError(f"{tool_name} requires exactly {field_name}")
    if not isinstance(arguments[field_name], str) or not arguments[field_name].strip():
        raise ValueError(f"{tool_name} {field_name} must be a non-empty string")
    return arguments


def validate_agent_tool_call(
    tool_name: str,
    raw_arguments: str,
    *,
    domain: RAGDomain,
) -> dict[str, Any]:
    if tool_name == "search_knowledge":
        return validate_search_knowledge_call(tool_name, raw_arguments, domain=domain)
    if tool_name == "get_document_page":
        return validate_document_page_call(tool_name, raw_arguments, domain=domain)
    return validate_loan_data_call(tool_name, raw_arguments)


def _validate_loan_scope(
    tool_name: str,
    arguments: dict[str, Any],
    loan_profile_id: str | None,
) -> None:
    if tool_name not in LOAN_DATA_ID_FIELDS:
        return
    if not loan_profile_id:
        raise ValueError("Loan data tools require loan_profile_id in agent input")
    if tool_name in {"get_loan_profile", "list_reports"} and (
        arguments["loan_profile_id"] != loan_profile_id
    ):
        raise ValueError(f"{tool_name} must use the input loan_profile_id")


class DomainRAGRunHooks(RunHooksBase):
    def __init__(self, domain: RAGDomain, loan_profile_id: str | None = None):
        self.domain = domain
        self.loan_profile_id = loan_profile_id

    async def on_tool_start(self, context, agent, tool) -> None:
        if not isinstance(context, ToolContext):
            raise ValueError("Agent tool calls require ToolContext")
        arguments = validate_agent_tool_call(
            context.tool_name,
            context.tool_arguments,
            domain=self.domain,
        )
        _validate_loan_scope(context.tool_name, arguments, self.loan_profile_id)
        if not isinstance(tool, FunctionTool):
            raise ValueError(f"Agent may only invoke the {AGENT_MCP_NAME} MCP server")
        origin = get_function_tool_origin(tool)
        if (
            origin is None
            or origin.type != ToolOriginType.MCP
            or origin.mcp_server_name != AGENT_MCP_NAME
        ):
            raise ValueError(f"Agent may only invoke the {AGENT_MCP_NAME} MCP server")


def _unwrap_output(output: Any) -> Any:
    payload = output
    if isinstance(payload, dict) and payload.get("type") == "text":
        payload = payload.get("text")
    elif (
        isinstance(payload, list)
        and len(payload) == 1
        and isinstance(payload[0], dict)
        and payload[0].get("type") == "text"
    ):
        payload = payload[0].get("text")
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("MCP tool returned invalid JSON") from error
    return payload


def _parse_evidence_output(output: Any) -> list[KnowledgeEvidence]:
    payload = _unwrap_output(output)
    if isinstance(payload, dict):
        if set(payload) != {"evidence"}:
            raise ValueError("RAG output envelope must contain only evidence")
        payload = payload["evidence"]
    if not isinstance(payload, list):
        raise ValueError("RAG output must be an evidence list")
    evidence = TypeAdapter(list[KnowledgeEvidence]).validate_python(payload)
    evidence_by_id(evidence)
    return evidence


def _require_agent_mcp_origin(item: ToolCallItem | ToolCallOutputItem) -> None:
    origin = item.tool_origin
    if (
        origin is None
        or origin.type != ToolOriginType.MCP
        or origin.mcp_server_name != AGENT_MCP_NAME
    ):
        raise ValueError(f"Tool item did not originate from {AGENT_MCP_NAME} MCP")


def _validate_loan_output(
    tool_name: str,
    arguments: dict[str, Any],
    output: Any,
    customer_ids: set[str],
) -> None:
    payload = _unwrap_output(output)
    if not isinstance(payload, Mapping):
        raise ValueError(f"{tool_name} returned an invalid object")
    if tool_name == "get_loan_profile":
        if payload.get("id") != arguments["loan_profile_id"]:
            raise ValueError("get_loan_profile returned a different loan profile")
        customer_id = payload.get("customer_id")
        if not isinstance(customer_id, str) or not customer_id.strip():
            raise ValueError("get_loan_profile returned an invalid customer_id")
        customer_ids.add(customer_id)
    elif tool_name == "get_customer":
        if payload.get("id") != arguments["customer_id"]:
            raise ValueError("get_customer returned a different customer")
        if arguments["customer_id"] not in customer_ids:
            raise ValueError("get_customer requires a prior loan profile result")
    else:
        reports = payload.get("reports")
        if not isinstance(reports, list) or any(
            not isinstance(report, Mapping)
            or report.get("loan_profile_id") != arguments["loan_profile_id"]
            for report in reports
        ):
            raise ValueError("list_reports returned a different loan profile")


def extract_trusted_evidence(
    new_items: list[Any],
    *,
    domain: RAGDomain,
    loan_profile_id: str | None = None,
) -> list[KnowledgeEvidence]:
    calls: dict[str, tuple[ToolCallItem, dict[str, Any]]] = {}
    outputs: dict[str, ToolCallOutputItem] = {}
    for item in new_items:
        if isinstance(item, ToolCallItem):
            _require_agent_mcp_origin(item)
            call_id = item.call_id
            raw_arguments = (
                item.raw_item.get("arguments")
                if isinstance(item.raw_item, dict)
                else getattr(item.raw_item, "arguments", None)
            )
            if not call_id or not isinstance(raw_arguments, str):
                raise ValueError("MCP tool call is missing its call ID or arguments")
            if call_id in calls:
                raise ValueError(f"Duplicate MCP call ID: {call_id}")
            arguments = validate_agent_tool_call(
                item.tool_name or "",
                raw_arguments,
                domain=domain,
            )
            _validate_loan_scope(item.tool_name or "", arguments, loan_profile_id)
            calls[call_id] = (item, arguments)
        elif isinstance(item, ToolCallOutputItem):
            _require_agent_mcp_origin(item)
            if not item.call_id:
                raise ValueError("MCP tool output is missing its call ID")
            if item.call_id in outputs:
                raise ValueError(f"Duplicate MCP output ID: {item.call_id}")
            outputs[item.call_id] = item

    trusted_evidence: list[KnowledgeEvidence] = []
    search_evidence: list[KnowledgeEvidence] = []
    customer_ids: set[str] = set()
    for call_id, (call, arguments) in calls.items():
        output = outputs.get(call_id)
        if output is None:
            raise ValueError(f"Missing MCP output for call: {call_id}")
        if call.tool_name in LOAN_DATA_ID_FIELDS:
            _validate_loan_output(call.tool_name, arguments, output.output, customer_ids)
            continue
        tool_evidence = _parse_evidence_output(output.output)
        if call.tool_name == "search_knowledge":
            search_evidence.extend(tool_evidence)
        else:
            search_item = next(
                (
                    item
                    for item in search_evidence
                    if item.source_id == arguments["source_id"]
                ),
                None,
            )
            if search_item is None:
                raise ValueError("get_document_page requires prior search evidence")
            if len(tool_evidence) != 1:
                raise ValueError("get_document_page must return exactly one evidence item")
            page_evidence = tool_evidence[0]
            if (
                page_evidence.file_name,
                page_evidence.page,
                page_evidence.source_id,
            ) != (
                search_item.file_name,
                search_item.page,
                f"page:{arguments['source_id']}",
            ):
                raise ValueError("get_document_page returned a different requested document page")
        trusted_evidence.extend(tool_evidence)

    if set(outputs) != set(calls):
        raise ValueError("MCP output does not match a tool call")
    if not search_evidence:
        raise ValueError("No search_knowledge call found")
    if not trusted_evidence:
        raise ValueError("RAG returned no evidence")
    evidence_by_id(trusted_evidence)
    return trusted_evidence


def build_agent_mcp_server(mcp_url: str) -> MCPServerStreamableHttp:
    return MCPServerStreamableHttp(
        params={"url": mcp_url, "timeout": 30, "sse_read_timeout": 30},
        name=AGENT_MCP_NAME,
        cache_tools_list=True,
        client_session_timeout_seconds=30,
        tool_filter={"allowed_tool_names": list(AGENT_MCP_TOOL_NAMES)},
        use_structured_content=True,
    )


def assert_expected_agent_tools(tools: list[Any]) -> None:
    if {tool.name for tool in tools} != set(AGENT_MCP_TOOL_NAMES):
        raise RuntimeError("Agent MCP server exposes an unexpected tool set")
