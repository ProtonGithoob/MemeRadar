import json

from memeradar_mcp import server


def test_mcp_lists_only_requested_read_tools() -> None:
    response = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

    assert response is not None
    names = {tool["name"] for tool in response["result"]["tools"]}
    assert names == {
        "list_opportunities",
        "get_opportunity",
        "get_token_analysis",
        "get_alpha_evidence",
        "get_security_evidence",
        "get_wallet_profile",
        "get_wallet_cluster",
        "get_creator_profile",
        "get_chain_health",
        "get_provider_health",
        "get_stream_gaps",
        "get_forward_outcomes",
        "get_replay_report",
        "get_ablation_report",
        "get_telegram_status",
        "get_positions",
        "get_paper_performance",
    }


def test_unexposed_research_projection_is_explicit() -> None:
    result = server.call_tool("get_stream_gaps")
    payload = json.loads(result["content"][0]["text"])

    assert result["isError"] is False
    assert payload == {
        "status": "NOT_EXPOSED",
        "reason": "STREAM_GAP_API_PROJECTION_NOT_EXPOSED",
    }


def test_mcp_api_calls_are_get_only_and_delegate_to_existing_api(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, limit: int) -> bytes:
            captured["limit"] = limit
            return b'{"items": [], "limit": 1, "has_more": false}'

    def fake_urlopen(request, timeout: int):
        captured["method"] = request.method
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(server, "urlopen", fake_urlopen)
    result = server.call_tool("list_opportunities", {"chain": "base", "limit": 1})
    payload = json.loads(result["content"][0]["text"])

    assert payload["items"] == []
    assert captured == {
        "method": "GET",
        "url": "http://127.0.0.1:18000/v1/chain-opportunities?chain=base&limit=1",
        "timeout": 10,
        "limit": 2_000_001,
    }


def test_mcp_rejects_unknown_tool_and_mutating_argument_shapes() -> None:
    unknown = server.call_tool("submit_transaction")
    invalid = server.call_tool("list_opportunities", {"method": "POST"})

    assert unknown["isError"] is True
    assert "UNKNOWN_TOOL" in unknown["content"][0]["text"]
    assert invalid["isError"] is True
    assert "unknown tool argument" in invalid["content"][0]["text"]
