import json
import streamlit as st


def render_assistant_message(content: str):
    """Render an assistant chat message."""
    with st.chat_message("assistant"):
        st.markdown(content)


def render_tool_call(function_name: str, arguments: dict, result: dict):
    """Render a tool/function call and its result in an expander."""
    with st.expander(f"Called: {function_name}", expanded=False):
        st.markdown("**Arguments:**")
        st.json(arguments)
        st.markdown("**Result:**")
        st.json(result)


def render_tool_call_with_type(
    function_name: str,
    arguments: dict,
    result: dict,
    tool_type: str = "function",
    gateway_path: str = "",
):
    """Render a tool call with a protocol type badge.

    tool_type: "function" for OpenAI function calling, "mcp" for MCP tools.
    """
    if tool_type == "mcp":
        badge = ":green[MCP Tool]"
        icon = ":material/cable:"
    else:
        badge = ":blue[Function Call]"
        icon = ":material/function:"

    with st.expander(f"{icon} {badge}  **{function_name}**", expanded=False):
        if gateway_path:
            st.caption(f"Gateway path: `{gateway_path}`")
        st.markdown("**Arguments:**")
        st.json(arguments)
        st.markdown("**Result:**")
        st.json(result)


def render_error(status_code: int, body: dict):
    """Render an error response."""
    if status_code == 0:
        st.error(f"Connection failed: {body.get('error', 'Unknown error')}")
    elif status_code == 403:
        msg = body.get("message") or body.get("error") or str(body)
        if "denied by ABAC" in msg:
            st.error(f"Access denied (ABAC): {msg}")
        else:
            st.error(f"Blocked by guardrail: {msg}")
    elif status_code == 422:
        st.error(f"PII detected: {body.get('message', body)}")
    elif status_code == 429:
        st.warning(f"Rate limited: {body.get('message', body)}")
    else:
        st.warning(f"Status {status_code}: {json.dumps(body, indent=2)}")


def render_request_chain(chain: list[dict]):
    """Render a visual request chain in the sidebar."""
    for i, hop in enumerate(chain):
        icon = hop.get("icon", "-->")
        label = hop.get("label", "")
        status = hop.get("status", "pending")
        if status == "active":
            st.markdown(f"**{icon} {label}**")
        elif status == "done":
            st.markdown(f"~~{icon} {label}~~")
        else:
            st.caption(f"{icon} {label}")
        if i < len(chain) - 1:
            st.caption("  |")
