"""
Multi-Cluster Failover — Live Demo
Demonstrates cross-cluster service routing with Istio ambient mesh global services.
Scale down data-product-api on this cluster, prove the chatbot still works via cluster2.
"""

import streamlit as st
import requests

st.set_page_config(
    page_title="Multi-Cluster",
    page_icon=":material/language:",
    layout="wide",
)

from utils.theme import inject_theme
from utils.kubectl import run_kubectl
from utils.config import DATA_PRODUCT_URL, NS_BACKEND, DEFAULT_STUDENT_ID

inject_theme()

st.title("Multi-Cluster Failover")
st.caption("Cross-cluster service routing demo | Istio Ambient Mesh")

st.info(
    "This demo showcases **multicluster failover** with Istio ambient mesh. "
    "When `data-product-api` is scaled to zero on this cluster, the mesh "
    "transparently routes requests to cluster2 — the chatbot keeps working "
    "with no application changes."
)

GLOBAL_LABEL_YAML = """\
# Label a service as globally available across the mesh
apiVersion: v1
kind: Service
metadata:
  name: data-product-api
  namespace: wgu-demo
  labels:
    solo.io/service-scope: global        # Makes service discoverable across clusters
  annotations:
    networking.istio.io/traffic-distribution: PreferNetwork  # Prefer local, failover to remote
"""


def kubectl(cmd: str) -> tuple[int, str, str]:
    """Run kubectl without --context (uses in-cluster config)."""
    return run_kubectl(cmd)


# ──────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "1. Enable Global Service",
    "2. Simulate Failover",
    "3. Verify Failover",
    "4. Restore",
])

# ──────────────────────────────────────────────
# Step 1: Enable Global Service
# ──────────────────────────────────────────────
with tab1:
    st.header("Step 1: Enable Global Service", divider=True)
    st.markdown(
        "Label `data-product-api` and `graph-db-mock` as **global** so Istio creates "
        "cross-cluster `ServiceEntry` resources. The `PreferNetwork` annotation ensures "
        "traffic stays local when healthy, failing over to the remote cluster only when needed."
    )

    with st.expander("What do these labels do?"):
        st.code(GLOBAL_LABEL_YAML, language="yaml")
        st.markdown(
            "- **`solo.io/service-scope=global`** — Istio's multicluster controller detects this "
            "and generates a `ServiceEntry` in each cluster with hostname "
            "`<service>.<namespace>.mesh.internal`\n"
            "- **`networking.istio.io/traffic-distribution=PreferNetwork`** — Prefer routing to "
            "instances in the same network (local cluster) before failing over to remote"
        )

    if st.button("Enable Global Service", key="mc_btn_enable_global", type="primary"):
        results = []
        with st.spinner("Labeling services as global..."):
            for svc in ["data-product-api", "graph-db-mock"]:
                results.append(kubectl(
                    f"kubectl label service {svc} -n {NS_BACKEND} "
                    f"solo.io/service-scope=global --overwrite"
                ))
                results.append(kubectl(
                    f"kubectl annotate service {svc} -n {NS_BACKEND} "
                    f"networking.istio.io/traffic-distribution=PreferNetwork --overwrite"
                ))
        st.session_state["mc_step1_results"] = results
        st.session_state["mc_step1_done"] = True

    if st.session_state.get("mc_step1_done"):
        for rc, out, err in st.session_state.get("mc_step1_results", []):
            if rc == 0:
                st.success(out.strip() if out.strip() else "Applied successfully")
            else:
                st.error(err.strip())

        st.markdown("---")
        st.markdown("**Auto-generated ServiceEntries** (may take a few seconds to appear):")
        if st.button("Check ServiceEntries", key="mc_btn_check_se"):
            rc, out, err = kubectl("kubectl get serviceentry -n istio-system")
            if rc == 0 and out.strip():
                st.code(out, language="text")
            elif rc == 0:
                st.warning("No ServiceEntries found yet — wait a few seconds and try again.")
            else:
                st.error(err.strip())

        st.markdown("**Current deployments:**")
        rc, out, err = kubectl(f"kubectl get deploy -n {NS_BACKEND}")
        if rc == 0:
            st.code(out, language="text")

# ──────────────────────────────────────────────
# Step 2: Simulate Failover
# ──────────────────────────────────────────────
with tab2:
    st.header("Step 2: Simulate Failover", divider=True)
    st.markdown(
        "Scale `data-product-api` to **zero replicas** on this cluster. "
        "The mesh will detect no healthy local endpoints and route traffic "
        "to cluster2 transparently."
    )

    if st.button(
        "Scale Down data-product-api (this cluster)",
        key="mc_btn_scaledown",
        type="primary",
    ):
        results = []
        with st.spinner("Scaling down..."):
            results.append(kubectl(
                f"kubectl scale deploy/data-product-api -n {NS_BACKEND} --replicas 0"
            ))
            results.append(kubectl(
                f"kubectl get deploy -n {NS_BACKEND}"
            ))
        st.session_state["mc_step2_results"] = results
        st.session_state["mc_step2_done"] = True

    if st.session_state.get("mc_step2_done"):
        st.warning("data-product-api scaled to 0 replicas on this cluster.")
        for rc, out, err in st.session_state.get("mc_step2_results", []):
            if rc == 0:
                st.code(out, language="text")
            else:
                st.error(err.strip())
        st.info(
            "The mesh will now route `data-product-api` traffic to cluster2. "
            "Go to the **Verify Failover** tab to confirm."
        )

# ──────────────────────────────────────────────
# Step 3: Verify Failover
# ──────────────────────────────────────────────
with tab3:
    st.header("Step 3: Verify Failover", divider=True)
    st.markdown(
        "Test that the data product API is still reachable even though it has "
        "zero replicas on this cluster. If the mesh is routing to cluster2, "
        "these requests will succeed."
    )

    if st.button("Test Data Product API", key="mc_btn_verify", type="primary"):
        test_results = []
        with st.spinner("Testing API endpoints..."):
            # Health check
            try:
                resp = requests.get(f"{DATA_PRODUCT_URL}/health", timeout=10)
                test_results.append(("Health Check", resp.status_code, resp.text))
            except requests.exceptions.ConnectionError:
                test_results.append(("Health Check", None, "Connection refused"))
            except requests.RequestException as exc:
                test_results.append(("Health Check", None, str(exc)))

            # Student data lookup
            try:
                resp = requests.get(
                    f"{DATA_PRODUCT_URL}/students/{DEFAULT_STUDENT_ID}", timeout=10,
                )
                test_results.append(("Student Lookup", resp.status_code, resp.text))
            except requests.exceptions.ConnectionError:
                test_results.append(("Student Lookup", None, "Connection refused"))
            except requests.RequestException as exc:
                test_results.append(("Student Lookup", None, str(exc)))

        st.session_state["mc_step3_results"] = test_results

    for name, status_code, body in st.session_state.get("mc_step3_results", []):
        if status_code == 200:
            st.success(f"**{name}**: HTTP {status_code} — served from cluster2!")
            if name == "Student Lookup":
                with st.expander("Response data"):
                    st.code(body, language="json")
        elif status_code is not None:
            st.error(f"**{name}**: HTTP {status_code} — {body[:200]}")
        else:
            st.error(
                f"**{name}**: {body} — failover may not be working. "
                "Check that cluster2 has data-product-api running and "
                "services are labeled `solo.io/service-scope=global`."
            )

    if any(
        sc == 200
        for _, sc, _ in st.session_state.get("mc_step3_results", [])
    ):
        st.markdown("---")
        st.info(
            "**Try it end-to-end:** Go to the **Homepage** and ask the chatbot a question "
            "(e.g., *What courses do I have left?*). The chatbot will call the data product API "
            "through the mesh — served transparently from cluster2."
        )

# ──────────────────────────────────────────────
# Step 4: Restore
# ──────────────────────────────────────────────
with tab4:
    st.header("Step 4: Restore", divider=True)
    st.markdown(
        "Scale `data-product-api` back up on this cluster. The `PreferNetwork` annotation "
        "ensures traffic returns to the local instance once it's healthy again."
    )

    if st.button(
        "Scale Up data-product-api (this cluster)",
        key="mc_btn_scaleup",
        type="primary",
    ):
        results = []
        with st.spinner("Scaling up and waiting for pod to be ready..."):
            results.append(kubectl(
                f"kubectl scale deploy/data-product-api -n {NS_BACKEND} --replicas 1"
            ))
            results.append(kubectl(
                f"kubectl rollout status deploy/data-product-api -n {NS_BACKEND} --timeout=60s"
            ))
            results.append(kubectl(
                f"kubectl get deploy -n {NS_BACKEND}"
            ))
        st.session_state["mc_step4_results"] = results
        st.session_state["mc_step4_done"] = True

    if st.session_state.get("mc_step4_done"):
        for rc, out, err in st.session_state.get("mc_step4_results", []):
            if rc == 0:
                st.code(out, language="text")
            else:
                st.error(err.strip())

        st.success("data-product-api restored on this cluster.")

        st.markdown("---")
        st.markdown("**Verify local is serving again:**")
        if st.button("Test Data Product API", key="mc_btn_verify_restored"):
            try:
                resp = requests.get(f"{DATA_PRODUCT_URL}/health", timeout=10)
                if resp.status_code == 200:
                    st.success(f"Health check: HTTP {resp.status_code} — local instance is serving")
                else:
                    st.warning(f"Health check: HTTP {resp.status_code}")
            except requests.RequestException as exc:
                st.error(f"Health check failed: {exc}")


# ──────────────────────────────────────────────
# Demo Walkthrough
# ──────────────────────────────────────────────
st.header("Demo Walkthrough", divider=True)
st.markdown("""
**Recommended demo flow:**

1. **Enable global service** — Walk through what the `solo.io/service-scope=global` label does. Show the auto-generated ServiceEntry.
2. **Baseline test** — On the Homepage, ask the chatbot a question to show it working normally with the local data-product-api.
3. **Simulate failover** — Scale data-product-api to 0 on this cluster. Point out there are zero replicas locally.
4. **Verify failover** — Test the API from this tab (HTTP 200 = served from cluster2). Then go to the Homepage and ask the chatbot the same question — it still works.
5. **Key message:** Zero code changes. Zero config changes in the app. The mesh handles cross-cluster routing transparently with mTLS preserved end-to-end.
6. **Restore** — Scale back up. Traffic returns to local because of `PreferNetwork`.
""")
