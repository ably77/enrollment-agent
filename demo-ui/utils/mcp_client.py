"""MCP client helper — discovers and calls MCP tools through the agent gateway."""

import asyncio
import json
import logging

logger = logging.getLogger(__name__)


def _mcp_tool_to_openai(tool) -> dict:
    """Convert an MCP tool definition to OpenAI function calling format."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema if tool.inputSchema else {"type": "object", "properties": {}},
        },
    }


async def _discover_tools(url: str) -> list[dict]:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [_mcp_tool_to_openai(t) for t in result.tools]


async def _call_tool(url: str, name: str, arguments: dict) -> str:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            if result.content:
                return result.content[0].text
            return json.dumps({"error": "Empty response from MCP tool"})


def discover_mcp_tools(url: str) -> list[dict]:
    """Discover MCP tools from the gateway endpoint. Returns OpenAI-format tool defs."""
    try:
        return asyncio.run(_discover_tools(url))
    except Exception as exc:
        logger.warning("MCP tool discovery failed: %s", exc)
        return []


def call_mcp_tool(url: str, name: str, arguments: dict) -> dict:
    """Call an MCP tool through the gateway endpoint. Returns parsed JSON result."""
    try:
        raw = asyncio.run(_call_tool(url, name, arguments))
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"result": raw}
    except Exception as exc:
        return {"error": f"MCP tool call failed: {exc}"}
