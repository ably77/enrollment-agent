import json
import requests
import streamlit as st

from utils.kubectl import run_kubectl


def get_gateway_ip() -> str:
    """Auto-discover the Agentgateway proxy LoadBalancer address (cached)."""
    if "_gateway_ip_auto" in st.session_state:
        return st.session_state["_gateway_ip_auto"]
    rc, out, _ = run_kubectl(
        "kubectl get svc -n agentgateway-system "
        "--selector=gateway.networking.k8s.io/gateway-name=agentgateway-proxy "
        "-o jsonpath='{.items[*].status.loadBalancer.ingress[0].ip}"
        "{.items[*].status.loadBalancer.ingress[0].hostname}'"
    )
    ip = out.strip().strip("'") if rc == 0 else ""
    if ip:
        st.session_state["_gateway_ip_auto"] = ip
    return ip


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
    include_response_headers: bool = False,
) -> tuple[int, dict] | tuple[int, dict, dict]:
    """Send a chat completion request through the agent gateway.

    Returns (status_code, parsed_json_body), or
    (status_code, parsed_json_body, response_headers) if include_response_headers.
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
        if include_response_headers:
            return resp.status_code, body, dict(resp.headers)
        return resp.status_code, body
    except requests.RequestException as exc:
        if include_response_headers:
            return 0, {"error": str(exc)}, {}
        return 0, {"error": str(exc)}
