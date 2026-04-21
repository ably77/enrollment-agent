import json
import requests
import streamlit as st


def get_gateway_url() -> str:
    """Build the gateway base URL from session state."""
    protocol = st.session_state.get("protocol", "http")
    port = st.session_state.get("port", "8080")
    ip = st.session_state.get("gateway_ip", "localhost")
    return f"{protocol}://{ip}:{port}"


def chat_completion(
    messages: list[dict],
    model: str = "gpt-4o-mini",
    tools: list[dict] | None = None,
    path: str = "/openai",
    extra_headers: dict | None = None,
) -> tuple[int, dict]:
    """Send a chat completion request through the agent gateway.

    Returns (status_code, parsed_json_body).
    """
    url = f"{get_gateway_url()}{path}"
    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools

    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        try:
            body = resp.json()
        except (json.JSONDecodeError, TypeError):
            body = {"error": resp.text}
        return resp.status_code, body
    except requests.RequestException as exc:
        return 0, {"error": str(exc)}
