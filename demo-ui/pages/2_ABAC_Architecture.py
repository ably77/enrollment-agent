"""ABAC Ext-Authz Flow — Architecture diagram for the BYO gRPC ext-authz demo."""

import streamlit as st

st.set_page_config(
    page_title="ABAC Ext-Authz Flow",
    page_icon=":material/security:",
    layout="wide",
)

from utils.theme import inject_theme

inject_theme()

st.title("ABAC Ext-Authz Flow")
st.caption("How the Agentgateway enforces attribute-based access control on LLM requests")

with open("assets/abac-architecture.html", "r") as f:
    st.components.v1.html(f.read(), height=620, scrolling=False)
