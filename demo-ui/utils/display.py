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


def render_error(status_code: int, body: dict):
    """Render an error response."""
    if status_code == 0:
        st.error(f"Connection failed: {body.get('error', 'Unknown error')}")
    elif status_code == 403:
        st.error(f"Blocked by guardrail: {body.get('message', body)}")
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
