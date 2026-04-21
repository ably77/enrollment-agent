"""
Mesh Authorization Policies — Live Enforcement Demo
Demonstrates zero-trust policies, tests enforcement, and allows toggling policies on/off.
"""

import streamlit as st
import requests

st.set_page_config(
    page_title="Mesh Policies",
    page_icon=":material/shield:",
    layout="wide",
)

from utils.theme import inject_theme
from utils.kubectl import run_kubectl
from utils.config import DATA_PRODUCT_URL, GRAPH_DB_URL, NS_BACKEND, NS_FRONTEND, DEFAULT_STUDENT_ID

inject_theme()

st.title("Mesh Authorization Policies")
st.caption("Zero-trust enforcement demo | Istio Ambient Mesh")

with open("assets/mesh-architecture.html", "r") as f:
    st.components.v1.html(f.read(), height=900, scrolling=True)

POLICY_DIR = "/app/k8s/mesh"

# YAML content for display
DENY_ALL_YAML = """\
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: deny-all
  namespace: wgu-demo
spec:
  {}    # empty spec = deny everything
---
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: deny-all
  namespace: wgu-demo-frontend
spec:
  {}"""

CHATBOT_TO_DATA_YAML = """\
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: chatbot-to-data-product
  namespace: wgu-demo
spec:
  targetRefs:            # L7 enforcement at the waypoint
  - kind: Service
    group: ""
    name: data-product-api
  action: ALLOW
  rules:
  - from:
    - source:
        principals:
        - "*/ns/wgu-demo-frontend/sa/enrollment-chatbot\""""

DATA_TO_GRAPH_YAML = """\
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: data-product-to-graphdb
  namespace: wgu-demo
spec:
  targetRefs:            # L7 enforcement at the waypoint
  - kind: Service
    group: ""
    name: graph-db-mock
  action: ALLOW
  rules:
  - from:
    - source:
        principals:
        - "*/ns/wgu-demo/sa/data-product-api\""""

WAYPOINT_TO_BACKENDS_YAML = """\
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: waypoint-to-backends
  namespace: wgu-demo
spec:
  action: ALLOW
  rules:
  - from:
    - source:
        principals:
        - "*/ns/wgu-demo/sa/wgu-demo-waypoint\""""


def kubectl(cmd: str) -> tuple[int, str, str]:
    """Run kubectl without --context (uses in-cluster config)."""
    return run_kubectl(cmd)


# ──────────────────────────────────────────────
# Section 1: Current Policy State
# ──────────────────────────────────────────────
st.header("Current Policies", divider=True)

col_demo, col_frontend = st.columns(2)

with col_demo:
    st.subheader(f"{NS_BACKEND} namespace")
    rc, out, err = kubectl(f"kubectl get authorizationpolicies -n {NS_BACKEND} -o wide")
    if rc == 0 and out.strip():
        st.code(out, language="text")
    elif err.strip():
        st.error(err.strip())
    else:
        st.info(f"No AuthorizationPolicies in {NS_BACKEND}")

with col_frontend:
    st.subheader(f"{NS_FRONTEND} namespace")
    rc, out, err = kubectl(f"kubectl get authorizationpolicies -n {NS_FRONTEND} -o wide")
    if rc == 0 and out.strip():
        st.code(out, language="text")
    elif err.strip():
        st.error(err.strip())
    else:
        st.info(f"No AuthorizationPolicies in {NS_FRONTEND}")

if st.button("Refresh policies", key="refresh_policies"):
    st.rerun()


# ──────────────────────────────────────────────
# Section 2: Live Enforcement Tests
# ──────────────────────────────────────────────
st.header("Live Enforcement Tests", divider=True)
st.caption(
    "These tests run FROM this chatbot pod. The chatbot's service account "
    f"({NS_FRONTEND}/enrollment-chatbot) determines what's allowed."
)

test_col1, test_col2 = st.columns(2)

with test_col1:
    st.subheader("Allowed paths")
    st.caption("The chatbot SA is explicitly allowed to reach these services.")

    if st.button("Test: Chatbot -> Data Product API", key="test_allowed_data"):
        with st.spinner("Testing..."):
            try:
                resp = requests.get(f"{DATA_PRODUCT_URL}/health", timeout=5)
                st.success(f"ALLOWED (HTTP {resp.status_code}): {resp.text}")
            except requests.exceptions.ConnectionError:
                st.error("BLOCKED: Connection refused (policy denied)")
            except requests.RequestException as exc:
                st.error(f"BLOCKED: {exc}")

    if st.button("Test: Chatbot -> Student Data", key="test_allowed_student"):
        with st.spinner("Testing..."):
            try:
                resp = requests.get(
                    f"{DATA_PRODUCT_URL}/students/{DEFAULT_STUDENT_ID}", timeout=5
                )
                if resp.status_code == 200:
                    st.success(f"ALLOWED (HTTP {resp.status_code})")
                    st.json(resp.json())
                else:
                    st.error(f"BLOCKED (HTTP {resp.status_code})")
            except requests.exceptions.ConnectionError:
                st.error("BLOCKED: Connection refused (policy denied)")
            except requests.RequestException as exc:
                st.error(f"BLOCKED: {exc}")

with test_col2:
    st.subheader("Blocked paths")
    st.caption("The chatbot SA is NOT allowed to reach the graph DB directly.")

    if st.button("Test: Chatbot -> Graph DB (direct)", key="test_blocked_graph"):
        with st.spinner("Testing..."):
            try:
                resp = requests.get(f"{GRAPH_DB_URL}/health", timeout=5)
                if resp.status_code == 403:
                    st.error(f"BLOCKED (HTTP 403): RBAC access denied by waypoint policy")
                elif resp.status_code == 200:
                    st.warning(f"NOT BLOCKED (HTTP 200): {resp.text} — policies may be disabled!")
                else:
                    st.warning(f"HTTP {resp.status_code}: {resp.text[:100]}")
            except requests.exceptions.ConnectionError:
                st.error("BLOCKED: Connection refused (policy denied at L4)")
            except requests.RequestException as exc:
                st.error(f"BLOCKED: {exc}")
        st.caption(
            "Only data-product-api can reach graph-db-mock. "
            "This is the FERPA boundary."
        )

    if st.button("Test: Chatbot -> Graph DB query", key="test_blocked_query"):
        with st.spinner("Testing..."):
            try:
                resp = requests.post(
                    f"{GRAPH_DB_URL}/query",
                    json={"query": "MATCH (s:Student)", "student_id": DEFAULT_STUDENT_ID},
                    timeout=5,
                )
                if resp.status_code == 403:
                    st.error(f"BLOCKED (HTTP 403): RBAC access denied by waypoint policy")
                elif resp.status_code == 200:
                    st.warning(f"NOT BLOCKED (HTTP 200) — policies may be disabled!")
                else:
                    st.warning(f"HTTP {resp.status_code}: {resp.text[:100]}")
            except requests.exceptions.ConnectionError:
                st.error("BLOCKED: Connection refused (policy denied at L4)")
            except requests.RequestException as exc:
                st.error(f"BLOCKED: {exc}")
        st.caption("Direct graph queries from the chatbot are denied by policy.")


# ──────────────────────────────────────────────
# Section 3: Policy Toggle
# ──────────────────────────────────────────────
st.header("Policy Toggle", divider=True)
st.caption(
    "Toggle between zero-trust (all policies enforced) and open access "
    "(no policies — any service can talk to any service)."
)

# Check current state by counting policies
rc, out, _ = kubectl(f"kubectl get authorizationpolicies -n {NS_BACKEND} -o name")
policy_count = len(out.strip().splitlines()) if rc == 0 and out.strip() else 0
zero_trust_active = policy_count > 0

if zero_trust_active:
    st.success(f"Zero-trust is **ACTIVE** — {policy_count} policies enforced. Only explicitly allowed paths work.")
else:
    st.warning("Zero-trust is **DISABLED** — no policies. All services can talk to each other freely.")

toggle_col1, toggle_col2 = st.columns(2)

with toggle_col1:
    if st.button(
        "Remove ALL policies (open access)",
        key="open_access",
        disabled=not zero_trust_active,
        type="primary" if zero_trust_active else "secondary",
    ):
        with st.spinner("Removing all policies..."):
            kubectl(f"kubectl delete authorizationpolicies --all -n {NS_BACKEND} --ignore-not-found")
            kubectl(f"kubectl delete authorizationpolicies --all -n {NS_FRONTEND} --ignore-not-found")
        st.session_state["last_policy_action"] = "remove"
        st.rerun()

with toggle_col2:
    if st.button(
        "Restore zero-trust (all policies)",
        key="restore_all",
        disabled=zero_trust_active,
        type="primary" if not zero_trust_active else "secondary",
    ):
        with st.spinner("Applying all policies..."):
            kubectl(f"kubectl apply -f {POLICY_DIR}/")
        st.session_state["last_policy_action"] = "restore"
        st.rerun()

# Show result of last action with YAML
last_action = st.session_state.get("last_policy_action")

if last_action == "remove":
    st.success("All policies removed — traffic is wide open")
    with st.expander("Commands executed", expanded=True):
        st.code(f"kubectl delete authorizationpolicies --all -n {NS_BACKEND}\nkubectl delete authorizationpolicies --all -n {NS_FRONTEND}", language="bash")

elif last_action == "restore":
    st.success("Zero-trust restored — all policies active")
    with st.expander("YAML applied", expanded=True):
        st.code(DENY_ALL_YAML, language="yaml")
        st.divider()
        st.code(CHATBOT_TO_DATA_YAML, language="yaml")
        st.divider()
        st.code(DATA_TO_GRAPH_YAML, language="yaml")
        st.divider()
        st.code(WAYPOINT_TO_BACKENDS_YAML, language="yaml")


# ──────────────────────────────────────────────
# Section 4: Policy YAML Reference
# ──────────────────────────────────────────────
st.header("Policy YAML Reference", divider=True)

with st.expander("deny-all.yaml — Deny all traffic by default (FERPA boundary)"):
    st.code(DENY_ALL_YAML, language="yaml")

with st.expander("chatbot-to-data-product.yaml — Allow chatbot to query student data"):
    st.code(CHATBOT_TO_DATA_YAML, language="yaml")

with st.expander("data-product-to-graphdb.yaml — Allow data product API to query graph DB"):
    st.code(DATA_TO_GRAPH_YAML, language="yaml")

with st.expander("waypoint-to-backends.yaml — Allow waypoint proxy to reach backends (L4)"):
    st.code(WAYPOINT_TO_BACKENDS_YAML, language="yaml")


# ──────────────────────────────────────────────
# Section 5: Demo Walkthrough
# ──────────────────────────────────────────────
st.header("Demo Walkthrough", divider=True)
st.markdown("""
**Recommended demo flow:**

1. **Show current state** — policies are active, zero-trust is enforced
2. **Review the YAML** — expand the policy reference to show how simple the policies are
3. **Run enforcement tests** — show allowed paths work, blocked paths are denied
4. **Disable deny-all** — click "Disable deny-all", then re-run the "Chatbot -> Graph DB" test. It now succeeds — the chatbot can access raw student data directly, bypassing the data product API
5. **Re-enable deny-all** — click "Enable deny-all", re-run the test. Blocked again.
6. **Key message:** 5 lines of YAML control the FERPA boundary. Compare to managing Security Groups, NACLs, and IAM policies per service pair in AWS.
""")
