"""Small stdlib-only MCP server that delegates to MemeRadar's read API.

The MCP process is an operator interface, not a data plane.  It has no
database handle, provider adapter, signer, or mutation route.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from . import __version__

MCP_PROTOCOL_VERSION = "2025-06-18"
DEFAULT_API_BASE_URL = "http://127.0.0.1:18000"
MAX_ARGUMENT_LENGTH = 256
MAX_RESPONSE_BYTES = 2_000_000


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    properties: Mapping[str, Mapping[str, object]]
    required: tuple[str, ...] = ()
    route_template: str | None = None
    unavailable_reason: str | None = None

    def as_mcp(self) -> dict[str, object]:
        schema: dict[str, object] = {
            "type": "object",
            "properties": dict(self.properties),
            "additionalProperties": False,
        }
        if self.required:
            schema["required"] = list(self.required)
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": schema,
        }


def _string_property(description: str) -> dict[str, str]:
    return {"type": "string", "description": description}


def _integer_property(description: str) -> dict[str, object]:
    return {"type": "integer", "minimum": 1, "maximum": 100, "description": description}


_ID = _string_property("Existing MemeRadar API identifier.")
_ADDRESS = _string_property("Chain-qualified or provider-native address.")


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "list_opportunities",
        "List normalized opportunity evidence through the existing read API.",
        {
            "chain": _string_property("Optional chain filter."),
            "limit": _integer_property("Page size."),
        },
        route_template="/v1/chain-opportunities",
    ),
    ToolSpec(
        "get_opportunity",
        "Get one candidate/opportunity projection by its existing API identifier.",
        {"candidate_id": _ID},
        required=("candidate_id",),
        route_template="/v1/candidates/{candidate_id}",
    ),
    ToolSpec(
        "get_token_analysis",
        "Get the existing normalized token analysis projection.",
        {"token_id": _ID},
        required=("token_id",),
        route_template="/v1/tokens/{token_id}",
    ),
    ToolSpec(
        "get_alpha_evidence",
        "Get candidate evidence fields used by the existing read projection.",
        {"candidate_id": _ID},
        required=("candidate_id",),
        route_template="/v1/candidates/{candidate_id}",
    ),
    ToolSpec(
        "get_security_evidence",
        "Get candidate risk and security evidence from the existing read projection.",
        {"candidate_id": _ID},
        required=("candidate_id",),
        route_template="/v1/candidates/{candidate_id}",
    ),
    ToolSpec(
        "get_wallet_profile",
        "Get an existing wallet profile.",
        {"address": _ADDRESS},
        required=("address",),
        route_template="/v1/wallets/{address}",
    ),
    ToolSpec(
        "get_wallet_cluster",
        "Get an existing wallet-cluster graph projection.",
        {"cluster_id": _ID},
        required=("cluster_id",),
        route_template="/v1/wallet-graph/clusters/{cluster_id}",
    ),
    ToolSpec(
        "get_creator_profile",
        "Get an existing creator reputation projection.",
        {"address": _ADDRESS},
        required=("address",),
        route_template="/v1/creator-reputation/{address}",
    ),
    ToolSpec(
        "get_chain_health",
        "List chain-event provider health; unavailable chain filtering remains explicit.",
        {
            "provider": _string_property("Optional provider filter."),
            "limit": _integer_property("Page size."),
        },
        route_template="/v1/providers/health",
    ),
    ToolSpec(
        "get_provider_health",
        "List provider capability health through the existing read API.",
        {
            "provider": _string_property("Optional provider filter."),
            "limit": _integer_property("Page size."),
        },
        route_template="/v1/providers/health",
    ),
    ToolSpec(
        "get_stream_gaps",
        "Read stream-gap diagnostics once the API projection is exposed.",
        {},
        unavailable_reason="STREAM_GAP_API_PROJECTION_NOT_EXPOSED",
    ),
    ToolSpec(
        "get_forward_outcomes",
        "Read matured forward outcomes once the API projection is exposed.",
        {},
        unavailable_reason="FORWARD_OUTCOME_API_PROJECTION_NOT_EXPOSED",
    ),
    ToolSpec(
        "get_replay_report",
        "Read replay reports once the API projection is exposed.",
        {},
        unavailable_reason="REPLAY_REPORT_API_PROJECTION_NOT_EXPOSED",
    ),
    ToolSpec(
        "get_ablation_report",
        "Read ablation reports once the API projection is exposed.",
        {},
        unavailable_reason="ABLATION_REPORT_API_PROJECTION_NOT_EXPOSED",
    ),
    ToolSpec(
        "get_telegram_status",
        "Read Telegram delivery status once the API projection is exposed.",
        {},
        unavailable_reason="TELEGRAM_STATUS_API_PROJECTION_NOT_EXPOSED",
    ),
    ToolSpec(
        "get_positions",
        "List existing read-only paper/live position projections; no execution is exposed.",
        {"limit": _integer_property("Page size.")},
        route_template="/v1/positions",
    ),
    ToolSpec(
        "get_paper_performance",
        "Read paper-performance metrics once the API projection is exposed.",
        {},
        unavailable_reason="PAPER_PERFORMANCE_API_PROJECTION_NOT_EXPOSED",
    ),
)

_TOOLS = {spec.name: spec for spec in TOOL_SPECS}
_ARGUMENT_NAMES = {key for spec in TOOL_SPECS for key in spec.properties}


def _json_result(payload: Mapping[str, object], *, is_error: bool = False) -> dict[str, object]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(payload, sort_keys=True, separators=(",", ":")),
            }
        ],
        "isError": is_error,
    }


def _arguments(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("arguments must be an object")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or key not in _ARGUMENT_NAMES:
            raise ValueError("unknown tool argument")
        if isinstance(item, str) and len(item) > MAX_ARGUMENT_LENGTH:
            raise ValueError("tool argument is too long")
        if isinstance(item, bool) or not isinstance(item, str | int):
            raise ValueError("tool arguments must be strings or integers")
        result[key] = item
    return result


def _query(arguments: Mapping[str, object], keys: tuple[str, ...]) -> str:
    values = [(key, str(arguments[key])) for key in keys if key in arguments]
    return "" if not values else "?" + urlencode(values)


def _path(spec: ToolSpec, arguments: Mapping[str, object]) -> str:
    for required in spec.required:
        if required not in arguments:
            raise ValueError(f"missing required argument: {required}")
    if spec.route_template is None:
        raise ValueError("tool has no API route")
    path = spec.route_template
    for key in spec.required:
        path = path.replace("{" + key + "}", quote(str(arguments[key]), safe=""))
    if spec.name == "list_opportunities":
        return path + _query(arguments, ("chain", "limit", "cursor"))
    if spec.name in {"get_chain_health", "get_provider_health"}:
        return path + _query(arguments, ("provider", "limit", "cursor"))
    if spec.name == "get_positions":
        return path + _query(arguments, ("limit", "cursor"))
    return path


def _base_url() -> str:
    value = os.environ.get("MEMERADAR_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise ValueError("MEMERADAR_API_BASE_URL must be an HTTP(S) URL without credentials")
    return value


def _read_api(spec: ToolSpec, arguments: Mapping[str, object]) -> Mapping[str, object]:
    url = _base_url() + _path(spec, arguments)
    headers = {"Accept": "application/json"}
    token = os.environ.get("MEMERADAR_VIEWER_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                return {"status": "ERROR", "reason": "API_RESPONSE_TOO_LARGE"}
            parsed = json.loads(body.decode("utf-8"))
            return parsed if isinstance(parsed, Mapping) else {"data": parsed}
    except HTTPError as exc:
        return {"status": "API_ERROR", "http_status": exc.code}
    except (URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {"status": "API_UNAVAILABLE", "reason": "READ_API_REQUEST_FAILED"}


def call_tool(name: str, arguments: object = None) -> dict[str, object]:
    """Dispatch one explicitly read-only tool call."""

    spec = _TOOLS.get(name)
    if spec is None:
        return _json_result({"status": "ERROR", "reason": "UNKNOWN_TOOL"}, is_error=True)
    try:
        normalized = _arguments(arguments)
        if spec.unavailable_reason is not None:
            return _json_result(
                {"status": "NOT_EXPOSED", "reason": spec.unavailable_reason},
            )
        return _json_result(_read_api(spec, normalized))
    except (ValueError, TypeError) as exc:
        return _json_result({"status": "INVALID_ARGUMENTS", "reason": str(exc)}, is_error=True)


def _response(request_id: object, result: Mapping[str, object]) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle_message(message: Mapping[str, object]) -> dict[str, object] | None:
    """Handle one MCP JSON-RPC request; notifications intentionally have no reply."""

    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _response(
            request_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "memeradar-mcp", "version": __version__},
            },
        )
    if method == "tools/list":
        return _response(request_id, {"tools": [spec.as_mcp() for spec in TOOL_SPECS]})
    if method == "tools/call":
        params = message.get("params")
        if not isinstance(params, Mapping) or not isinstance(params.get("name"), str):
            return _response(request_id, {"error": "tools/call requires a tool name"})
        return _response(request_id, call_tool(str(params["name"]), params.get("arguments")))
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "method not found"},
    }


def main() -> None:
    """Run the line-delimited stdio MCP transport."""

    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            if not isinstance(message, Mapping):
                raise ValueError("JSON-RPC message must be an object")
            response = handle_message(message)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": str(exc)},
            }
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()


__all__ = ["TOOL_SPECS", "call_tool", "handle_message", "main"]
