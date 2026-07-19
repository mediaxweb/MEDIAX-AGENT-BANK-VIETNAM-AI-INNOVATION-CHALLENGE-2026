from __future__ import annotations

import json
import logging
import os
from collections.abc import Mapping
from time import perf_counter
from typing import Any, Literal

from agents import RunConfig
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.lifecycle import RunHooksBase
from agents.mcp import MCPServerStreamableHttp
from agents.tool import FunctionTool, ToolOriginType, get_function_tool_origin
from agents.tool_context import ToolContext
from agents.tracing import get_current_trace
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


RAGDomain = Literal["credit", "compliance", "operations"]
ExecutionMode = Literal["assess", "execute"]
AGENT_MCP_NAME = "agent-bank-tools"
AGENT_TRACE_LOGGER = logging.getLogger("agent_trace")
COMMON_MCP_TOOL_NAMES = (
    "search_knowledge",
    "get_document_page",
    "get_loan_profile",
    "get_customer",
    "list_reports",
)
DOMAIN_MCP_TOOL_NAMES = {
    "credit": (
        "search_customer",
        "create_customer",
        "update_customer",
        "create_loan_profile",
        "check_legal_docs",
    ),
    "compliance": (
        "check_financials",
        "check_collateral",
        "check_credit_rule",
        "save_compliance_result",
    ),
    "operations": (
        "update_case_status",
        "create_checklist",
        "calculate_loan_limit",
        "create_task",
        "create_report",
    ),
}
READ_ONLY_DOMAIN_TOOLS = {"search_customer"}
AGENT_MCP_TOOL_NAMES = COMMON_MCP_TOOL_NAMES
MUTATING_TOOL_NAMES = {
    tool_name
    for tool_names in DOMAIN_MCP_TOOL_NAMES.values()
    for tool_name in tool_names
    if tool_name not in READ_ONLY_DOMAIN_TOOLS
}
LOAN_DATA_ID_FIELDS = {
    "get_loan_profile": "loan_profile_id",
    "get_customer": "customer_id",
    "list_reports": "loan_profile_id",
    "check_legal_docs": "loan_profile_id",
    "check_financials": "loan_profile_id",
    "check_collateral": "loan_profile_id",
    "check_credit_rule": "loan_profile_id",
    "save_compliance_result": "loan_profile_id",
    "update_case_status": "loan_profile_id",
    "create_checklist": "loan_profile_id",
    "calculate_loan_limit": "loan_profile_id",
    "create_task": "loan_profile_id",
    "create_report": "loan_profile_id",
}

TOOL_ARGUMENT_FIELDS = {
    "search_customer": (
        set(),
        {"full_name", "phone", "email", "national_id", "tax_code", "address"},
    ),
    "create_customer": (
        {"full_name"},
        {"full_name", "phone", "email", "national_id", "address", "customer_type", "tax_code"},
    ),
    "update_customer": (
        {"customer_id"},
        {"customer_id", "full_name", "phone", "email", "national_id", "address", "customer_type", "tax_code"},
    ),
    "create_loan_profile": (
        {"customer_id", "loan_amount", "loan_purpose", "term_months"},
        {"customer_id", "loan_amount", "loan_purpose", "term_months", "product_type", "currency", "metadata"},
    ),
    "check_legal_docs": (
        {"loan_profile_id", "required_doc_types"},
        {"loan_profile_id", "required_doc_types", "notes"},
    ),
    "check_financials": (
        {"loan_profile_id"},
        {"loan_profile_id", "notes"},
    ),
    "check_collateral": (
        {"loan_profile_id"},
        {"loan_profile_id", "notes"},
    ),
    "check_credit_rule": (
        {"loan_profile_id"},
        {"loan_profile_id", "notes"},
    ),
    "save_compliance_result": (
        {"loan_profile_id", "decision"},
        {"loan_profile_id", "decision", "score", "notes", "conditions", "details"},
    ),
    "update_case_status": (
        {"loan_profile_id", "status"},
        {"loan_profile_id", "status", "notes"},
    ),
    "create_checklist": (
        {"loan_profile_id"},
        {"loan_profile_id", "items", "notes"},
    ),
    "calculate_loan_limit": (
        {"loan_profile_id", "total_capital_need", "collateral_value", "ltv_ratio", "dscr", "checklist_score", "hard_stop"},
        {"loan_profile_id", "total_capital_need", "collateral_value", "ltv_ratio", "dscr", "checklist_score", "hard_stop"},
    ),
    "create_task": (
        {"loan_profile_id", "title", "priority"},
        {"loan_profile_id", "title", "description", "assignee_agent", "priority", "due_date"},
    ),
    "create_report": (
        {"loan_profile_id"},
        {"loan_profile_id", "report_type", "title", "summary"},
    ),
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


def validate_domain_tool_call(
    tool_name: str,
    raw_arguments: str,
    *,
    domain: RAGDomain,
    execution_mode: ExecutionMode,
) -> dict[str, Any]:
    if tool_name not in DOMAIN_MCP_TOOL_NAMES[domain]:
        raise ValueError(f"{tool_name} is not available to the {domain} agent")
    if tool_name in MUTATING_TOOL_NAMES and execution_mode != "execute":
        raise ValueError(f"{tool_name} requires execution_mode=execute")
    arguments = _json_arguments(tool_name, raw_arguments)
    required, allowed = TOOL_ARGUMENT_FIELDS[tool_name]
    if not required.issubset(arguments) or not set(arguments).issubset(allowed):
        raise ValueError(f"{tool_name} received an invalid argument set")
    if tool_name == "search_customer" and not any(
        isinstance(value, str) and value.strip() for value in arguments.values()
    ):
        raise ValueError("search_customer requires at least one search field")
    return arguments


def validate_agent_tool_call(
    tool_name: str,
    raw_arguments: str,
    *,
    domain: RAGDomain,
    execution_mode: ExecutionMode = "assess",
) -> dict[str, Any]:
    if tool_name == "search_knowledge":
        return validate_search_knowledge_call(tool_name, raw_arguments, domain=domain)
    if tool_name == "get_document_page":
        return validate_document_page_call(tool_name, raw_arguments, domain=domain)
    if tool_name in COMMON_MCP_TOOL_NAMES:
        return validate_loan_data_call(tool_name, raw_arguments)
    return validate_domain_tool_call(
        tool_name,
        raw_arguments,
        domain=domain,
        execution_mode=execution_mode,
    )


def _validate_loan_scope(
    tool_name: str,
    arguments: dict[str, Any],
    loan_profile_id: str | None,
) -> None:
    if tool_name not in LOAN_DATA_ID_FIELDS:
        return
    if not loan_profile_id:
        raise ValueError("Loan data tools require loan_profile_id in agent input")
    field_name = LOAN_DATA_ID_FIELDS[tool_name]
    if field_name == "loan_profile_id" and arguments[field_name] != loan_profile_id:
        raise ValueError(f"{tool_name} must use the input loan_profile_id")


def log_agent_event(event: str, **fields: Any) -> None:
    trace = get_current_trace()
    payload = {"event": event}
    if trace is not None:
        payload["trace_id"] = trace.trace_id
        metadata = getattr(trace, "metadata", None)
        if isinstance(metadata, Mapping) and metadata.get("dossier_id"):
            payload["dossier_id"] = metadata["dossier_id"]
    payload.update({key: value for key, value in fields.items() if value is not None})
    AGENT_TRACE_LOGGER.info(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def classify_agent_error(error: Exception) -> str:
    module = type(error).__module__.casefold()
    name = type(error).__name__.casefold()
    message = str(error).casefold()
    if "openai" in module or "model" in name:
        return "model"
    if "mcp" in module or "tool" in name or "tool" in message:
        return "tool"
    if module.startswith(("httpx", "httpcore")) or any(
        token in message for token in ("rag", "evidence", "search_knowledge")
    ):
        return "rag"
    if isinstance(error, (TypeError, ValueError, AssertionError)) or module.startswith(
        "pydantic"
    ):
        return "deterministic_validation"
    return "agent_runtime"


def log_agent_runtime_failure(domain: RAGDomain, error: Exception) -> None:
    log_agent_event(
        "agent.runtime.failed",
        agent=f"{domain.title()} Agent",
        domain=domain,
        stage=domain,
        error_category=classify_agent_error(error),
        error_type=type(error).__name__,
    )


def build_agent_run_config(
    workflow_name: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> RunConfig:
    include_sensitive = os.getenv(
        "OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA",
        "false",
    ).strip().lower() in {"1", "true", "yes", "on"}
    return RunConfig(
        workflow_name=workflow_name,
        trace_include_sensitive_data=include_sensitive,
        trace_metadata=metadata,
    )


class AgentLoggingRunHooks(RunHooksBase):
    def __init__(self, domain: RAGDomain | None = None):
        self.domain = domain
        self._agent_started_at: dict[str, float] = {}
        self._tool_started_at: dict[str, float] = {}

    @staticmethod
    def _duration_ms(started_at: float | None) -> int | None:
        if started_at is None:
            return None
        return int((perf_counter() - started_at) * 1000)

    @staticmethod
    def _tool_key(context: Any, tool_name: str) -> str:
        return getattr(context, "tool_call_id", None) or tool_name

    def _tool_fields(self, context: Any, tool_name: str) -> dict[str, Any]:
        fields: dict[str, Any] = {"domain": self.domain}
        if tool_name.startswith("ask_") and tool_name.endswith("_agent"):
            routed_domain = tool_name.removeprefix("ask_").removesuffix("_agent")
            if routed_domain in {"credit", "compliance", "operations"}:
                fields["domain"] = routed_domain
        if isinstance(context, ToolContext) and tool_name == "search_knowledge":
            try:
                arguments = json.loads(context.tool_arguments)
            except (TypeError, json.JSONDecodeError):
                arguments = {}
            if type(arguments.get("top_k")) is int:
                fields["top_k"] = arguments["top_k"]
        return fields

    @staticmethod
    def _evidence_count(result: Any) -> int | None:
        payload = result
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return None
        evidence = payload.get("evidence") if isinstance(payload, Mapping) else None
        return len(evidence) if isinstance(evidence, list) else None

    async def on_agent_start(self, context, agent) -> None:
        self._agent_started_at[agent.name] = perf_counter()
        log_agent_event(
            "agent.started",
            agent=agent.name,
            domain=self.domain,
        )

    async def on_agent_end(self, context, agent, output) -> None:
        usage = context.usage
        log_agent_event(
            "agent.completed",
            agent=agent.name,
            domain=self.domain,
            requests=usage.requests,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            duration_ms=self._duration_ms(self._agent_started_at.pop(agent.name, None)),
        )

    async def on_tool_start(self, context, agent, tool) -> None:
        tool_name = getattr(context, "tool_name", None) or getattr(tool, "name", type(tool).__name__)
        self._tool_started_at[self._tool_key(context, tool_name)] = perf_counter()
        log_agent_event(
            "agent.tool.started",
            agent=agent.name,
            tool=tool_name,
            **self._tool_fields(context, tool_name),
        )

    async def on_tool_end(self, context, agent, tool, result) -> None:
        tool_name = getattr(context, "tool_name", None) or getattr(tool, "name", type(tool).__name__)
        log_agent_event(
            "agent.tool.completed",
            agent=agent.name,
            tool=tool_name,
            evidence_count=self._evidence_count(result),
            duration_ms=self._duration_ms(
                self._tool_started_at.pop(self._tool_key(context, tool_name), None)
            ),
            **self._tool_fields(context, tool_name),
        )


class DomainRAGRunHooks(AgentLoggingRunHooks):
    def __init__(
        self,
        domain: RAGDomain,
        loan_profile_id: str | None = None,
        execution_mode: ExecutionMode = "assess",
    ):
        super().__init__(domain)
        self.loan_profile_id = loan_profile_id
        self.execution_mode = execution_mode

    async def on_tool_start(self, context, agent, tool) -> None:
        if not isinstance(context, ToolContext):
            raise ValueError("Agent tool calls require ToolContext")
        arguments = validate_agent_tool_call(
            context.tool_name,
            context.tool_arguments,
            domain=self.domain,
            execution_mode=self.execution_mode,
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
        await super().on_tool_start(context, agent, tool)


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
    execution_mode: ExecutionMode = "assess",
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
                execution_mode=execution_mode,
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
        if call.tool_name in {"get_loan_profile", "get_customer", "list_reports"}:
            _validate_loan_output(call.tool_name, arguments, output.output, customer_ids)
            continue
        if call.tool_name in DOMAIN_MCP_TOOL_NAMES[domain]:
            if not isinstance(_unwrap_output(output.output), Mapping):
                raise ValueError(f"{call.tool_name} returned an invalid object")
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


def extract_called_tool_names(new_items: list[Any]) -> list[str]:
    tool_names: list[str] = []
    for item in new_items:
        if isinstance(item, ToolCallItem):
            _require_agent_mcp_origin(item)
            if not item.tool_name:
                raise ValueError("MCP tool call is missing its tool name")
            tool_names.append(item.tool_name)
    return tool_names


def mutating_tool_names(tool_names: list[str]) -> list[str]:
    return [tool_name for tool_name in tool_names if tool_name in MUTATING_TOOL_NAMES]


def allowed_agent_tools(
    domain: RAGDomain | None = None,
    execution_mode: ExecutionMode = "assess",
) -> tuple[str, ...]:
    if domain is None:
        return COMMON_MCP_TOOL_NAMES
    domain_tools = tuple(
        tool_name
        for tool_name in DOMAIN_MCP_TOOL_NAMES[domain]
        if execution_mode == "execute" or tool_name not in MUTATING_TOOL_NAMES
    )
    return (*COMMON_MCP_TOOL_NAMES, *domain_tools)


def build_agent_mcp_server(
    mcp_url: str,
    domain: RAGDomain | None = None,
    execution_mode: ExecutionMode = "assess",
) -> MCPServerStreamableHttp:
    tool_names = allowed_agent_tools(domain, execution_mode)
    return MCPServerStreamableHttp(
        params={"url": mcp_url, "timeout": 30, "sse_read_timeout": 30},
        name=AGENT_MCP_NAME,
        cache_tools_list=True,
        client_session_timeout_seconds=30,
        tool_filter={"allowed_tool_names": list(tool_names)},
        use_structured_content=True,
    )


def assert_expected_agent_tools(
    tools: list[Any],
    domain: RAGDomain | None = None,
    execution_mode: ExecutionMode = "assess",
) -> None:
    if {tool.name for tool in tools} != set(allowed_agent_tools(domain, execution_mode)):
        raise RuntimeError("Agent MCP server exposes an unexpected tool set")
