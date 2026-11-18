
"""Generic MCP Streamable HTTP client for discovering server operations."""

from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

_PROTOCOL_VERSION = "2025-03-26"
_TIMEOUT_SECONDS = 30
_MAX_PAGES = 20


class MCPDiscoveryError(Exception):
    pass


def _post(
    url: str,
    payload: dict[str, Any],
    session_id: str | None = None,
    auth_headers: dict[str, str] | None = None,
) -> requests.Response:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": _PROTOCOL_VERSION,
    }
    if auth_headers:
        headers.update(auth_headers)

    if session_id:
        headers["Mcp-Session-Id"] = session_id

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise MCPDiscoveryError(f"Could not reach MCP server: {exc}") from exc

    if response.status_code in (401, 403):
        raise PermissionError(
            f"MCP server requires authentication (HTTP {response.status_code})"
        )

    if not response.ok:
        raise MCPDiscoveryError(
            f"MCP server returned HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return response


def _extract_message(response: requests.Response) -> dict[str, Any]:
    content_type = response.headers.get("Content-Type", "").lower()

    if "application/json" in content_type:
        try:
            return response.json()
        except ValueError as exc:
            raise MCPDiscoveryError("MCP server returned invalid JSON") from exc

    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data:
                    try:
                        message = __import__("json").loads(data)
                    except ValueError:
                        continue
                    if isinstance(message, dict) and (
                        "result" in message or "error" in message
                    ):
                        return message

    raise MCPDiscoveryError(
        f"Unsupported MCP response content type: {content_type or 'missing'}"
    )


def _rpc_result(message: dict[str, Any]) -> dict[str, Any]:
    if message.get("error"):
        error = message["error"]
        raise MCPDiscoveryError(
            f"MCP error {error.get('code')}: {error.get('message', 'Unknown error')}"
        )

    result = message.get("result")
    if not isinstance(result, dict):
        raise MCPDiscoveryError("MCP response did not contain a result object")

    return result


def discover_tools(
    server_url: str,
    auth_headers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Initialize an MCP session and retrieve all tools, including paginated tools.

    auth_headers are merged into every request to this server — e.g. the
    admin's shared `x-functions-key` header (api_center_catalog.py) or the
    headers built from a user's just-submitted connection values
    (tool_connections.py) for an individually-authenticated server. Never
    logged, never cached, never persisted by this module.
    """

    initialize_response = _post(
        server_url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "credo-agent-factory",
                    "version": "1.0.0",
                },
            },
        },
        auth_headers=auth_headers,
    )

    session_id = initialize_response.headers.get("Mcp-Session-Id")
    initialize_message = _extract_message(initialize_response)
    initialize_result = _rpc_result(initialize_message)

    negotiated_version = initialize_result.get("protocolVersion")
    if negotiated_version:
        logger.info("MCP server negotiated protocol version %s", negotiated_version)

    # Complete the MCP initialization handshake.
    notification_headers = {
        "Content-Type": "application/json",
        "MCP-Protocol-Version": negotiated_version or _PROTOCOL_VERSION,
    }
    if session_id:
        notification_headers["Mcp-Session-Id"] = session_id
    if auth_headers:
        notification_headers.update(auth_headers)

    notification = requests.post(
        server_url,
        json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        },
        headers=notification_headers,
        timeout=_TIMEOUT_SECONDS,
    )

    if notification.status_code not in (200, 202, 204):
        raise MCPDiscoveryError(
            f"MCP initialization notification failed: HTTP {notification.status_code}"
        )

    tools: list[dict[str, Any]] = []
    cursor = None

    for page in range(_MAX_PAGES):
        params = {}
        if cursor:
            params["cursor"] = cursor

        response = _post(
            server_url,
            {
                "jsonrpc": "2.0",
                "id": page + 2,
                "method": "tools/list",
                "params": params,
            },
            session_id=session_id,
            auth_headers=auth_headers,
        )

        result = _rpc_result(_extract_message(response))
        page_tools = result.get("tools", [])

        if not isinstance(page_tools, list):
            raise MCPDiscoveryError("MCP tools/list returned an invalid tools collection")

        for tool in page_tools:
            if not isinstance(tool, dict) or not tool.get("name"):
                continue

            tools.append({
                "name": tool["name"],
                "description": tool.get("description", ""),
                "inputSchema": tool.get("inputSchema", {}),
            })

        cursor = result.get("nextCursor")
        if not cursor:
            return tools

    raise MCPDiscoveryError(
        f"MCP server exceeded the maximum of {_MAX_PAGES} tools/list pages"
    )
