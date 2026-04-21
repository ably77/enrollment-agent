import os
import streamlit as st
from utils.theme import inject_theme
from utils.config import APP_TITLE


def render_sidebar():
    """Render the sidebar with gateway config and observability info."""
    inject_theme()

    if "gateway_ip" not in st.session_state:
        st.session_state["gateway_ip"] = os.environ.get("GATEWAY_IP", "localhost")
    if "protocol" not in st.session_state:
        st.session_state["protocol"] = os.environ.get("GATEWAY_PROTOCOL", "http")
    if "port" not in st.session_state:
        st.session_state["port"] = os.environ.get("GATEWAY_PORT", "8080")

    with st.sidebar:
        st.title(APP_TITLE)
        st.caption("Solo.io Ambient Mesh + Agent Gateway")

        st.divider()
        st.markdown("**Gateway Configuration**")

        protocol = st.selectbox(
            "Protocol",
            ["http", "https"],
            index=0 if st.session_state["protocol"] == "http" else 1,
        )
        st.session_state["protocol"] = protocol

        port = st.text_input("Port", value=st.session_state["port"])
        st.session_state["port"] = port

        st.text_input(
            "Gateway IP",
            value=st.session_state["gateway_ip"],
            key="sidebar_gw_ip",
            on_change=lambda: st.session_state.update(
                gateway_ip=st.session_state["sidebar_gw_ip"]
            ),
        )

        st.divider()
        st.markdown("**Observability**")
        st.caption("Gloo UI: [ui.glootest.com](http://ui.glootest.com)")
        st.caption("Grafana: [grafana.glootest.com](http://grafana.glootest.com)")
