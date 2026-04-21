# Multicluster Failover Demo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a multicluster failover demo that showcases Istio ambient mesh cross-cluster service routing — scale down `data-product-api` on cluster1 and prove the chatbot still works because the mesh transparently routes to cluster2.

**Architecture:** Install script deploys backend services to cluster2 and labels them as global. A new Streamlit page (`2_Multi_Cluster.py`) lets the presenter label the cluster1 services as global live, simulate failover by scaling down `data-product-api`, verify the API still responds (served from cluster2), and restore. The chatbot pod only needs in-cluster kubectl access to cluster1.

**Tech Stack:** Bash (install script), Python/Streamlit (demo page), kubectl, Istio ambient mesh multicluster

**Spec:** `docs/superpowers/specs/2026-04-20-multicluster-failover-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `install.sh:479-589` | Add `deploy_workloads_cluster2` and `configure_global_services` functions, call them in `full` mode |
| Modify | `cleanup.sh:23-28` | Add cluster2 workload cleanup |
| Modify | `k8s/services/enrollment-chatbot.yaml:10-16` | Extend ClusterRole with RBAC for services, deployments, scale, serviceentries |
| Create | `demo-ui/pages/2_Multi_Cluster.py` | New multicluster failover demo page |

---

### Task 1: Extend RBAC for the chatbot service account

The demo page needs to label services, scale deployments, and read serviceentries. Extend the existing ClusterRole.

**Files:**
- Modify: `k8s/services/enrollment-chatbot.yaml:10-16`

- [ ] **Step 1: Add RBAC rules to the ClusterRole**

In `k8s/services/enrollment-chatbot.yaml`, the existing `enrollment-chatbot-mesh-demo` ClusterRole (lines 10-16) has rules for `authorizationpolicies` and `pods`. Add the new rules after the existing ones:

```yaml
# RBAC for the demo UI to read/manage mesh policies
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: enrollment-chatbot-mesh-demo
rules:
- apiGroups: ["security.istio.io"]
  resources: ["authorizationpolicies"]
  verbs: ["get", "list", "create", "update", "patch", "delete"]
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["services"]
  verbs: ["get", "list", "patch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "patch"]
- apiGroups: ["apps"]
  resources: ["deployments/scale"]
  verbs: ["get", "update"]
- apiGroups: ["networking.istio.io"]
  resources: ["serviceentries"]
  verbs: ["get", "list"]
```

Replace the entire ClusterRole block (lines 9-16 of the file) with the above.

- [ ] **Step 2: Verify YAML is valid**

Run: `kubectl apply --dry-run=client -f k8s/services/enrollment-chatbot.yaml`
Expected: resources listed with `(dry run)` — no errors.

- [ ] **Step 3: Commit**

```bash
git add k8s/services/enrollment-chatbot.yaml
git commit -m "feat: extend chatbot RBAC for multicluster demo (services, deployments, serviceentries)"
```

---

### Task 2: Add cluster2 workload deployment to install script

Add two new functions to `install.sh`: `deploy_workloads_cluster2` deploys backend services to cluster2, and `configure_global_services` labels services as global on cluster2 only.

**Files:**
- Modify: `install.sh`

- [ ] **Step 1: Add `deploy_workloads_cluster2` function**

Add this function after the `deploy_workloads` function (after line 589) and before `print_access_info`:

```bash
# =============================================================================
# deploy_workloads_cluster2 — Deploy backend services to cluster2 for multicluster failover.
# =============================================================================
deploy_workloads_cluster2() {
  local ctx=$KUBECONTEXT_CLUSTER2

  echo "=== Deploying backend services to cluster2 ==="
  kubectl apply -f k8s/namespaces.yaml --context $ctx
  kubectl apply -f k8s/services/graph-db-mock.yaml --context $ctx
  kubectl apply -f k8s/services/data-product-api.yaml --context $ctx
  kubectl rollout status deploy/graph-db-mock -n wgu-demo --watch --timeout=120s --context $ctx
  kubectl rollout status deploy/data-product-api -n wgu-demo --watch --timeout=120s --context $ctx

  echo "=== Applying mesh policies on cluster2 ==="
  kubectl apply -f k8s/mesh/ --context $ctx
  kubectl label namespace wgu-demo istio.io/use-waypoint=wgu-demo-waypoint --context $ctx --overwrite
  kubectl rollout status deploy/wgu-demo-waypoint -n wgu-demo --watch --timeout=120s --context $ctx

  echo "Backend services deployed to cluster2."
}
```

- [ ] **Step 2: Add `configure_global_services` function**

Add this function immediately after `deploy_workloads_cluster2`:

```bash
# =============================================================================
# configure_global_services — Label services as global on cluster2.
# Cluster1 labeling is done by the demo UI page (live teaching moment).
# =============================================================================
configure_global_services() {
  local ctx=$KUBECONTEXT_CLUSTER2

  echo "=== Configuring global services on cluster2 ==="
  for svc in data-product-api graph-db-mock; do
    kubectl --context $ctx -n wgu-demo \
      label service $svc solo.io/service-scope=global --overwrite
    kubectl --context $ctx -n wgu-demo \
      annotate service $svc networking.istio.io/traffic-distribution=PreferNetwork --overwrite
  done

  echo "Services labeled as global on cluster2."
}
```

- [ ] **Step 3: Wire the new functions into the `full` mode flow**

In the `Main` section (around line 628), update the `full` case to call the new functions after `deploy_workloads`:

```bash
case "$INSTALL_MODE" in
  full)
    validate_full
    install_infra
    deploy_workloads
    deploy_workloads_cluster2
    configure_global_services
    ;;
  demo)
    validate_demo
    check_infra
    deploy_workloads
    ;;
esac
```

- [ ] **Step 4: Verify script syntax**

Run: `bash -n install.sh`
Expected: no output (no syntax errors).

- [ ] **Step 5: Commit**

```bash
git add install.sh
git commit -m "feat: deploy backend services to cluster2 and label as global in install script"
```

---

### Task 3: Add cluster2 cleanup to cleanup script

The cleanup script should tear down workloads on cluster2.

**Files:**
- Modify: `cleanup.sh`

- [ ] **Step 1: Add cluster2 workload cleanup**

In `cleanup.sh`, after the existing cluster1 resource deletion block (line 28), add cluster2 cleanup:

```bash
# --- Delete WGU demo resources on cluster2 ---
echo "--- Deleting WGU demo resources on cluster2 ---"
kubectl delete -f k8s/services/data-product-api.yaml --context $KUBECONTEXT_CLUSTER2 --ignore-not-found 2>/dev/null || true
kubectl delete -f k8s/services/graph-db-mock.yaml --context $KUBECONTEXT_CLUSTER2 --ignore-not-found 2>/dev/null || true
kubectl delete -f k8s/mesh/ --context $KUBECONTEXT_CLUSTER2 --ignore-not-found 2>/dev/null || true
kubectl delete -f k8s/namespaces.yaml --context $KUBECONTEXT_CLUSTER2 --ignore-not-found 2>/dev/null || true
```

Insert this after line 28 (`kubectl delete -f k8s/namespaces.yaml --context $KUBECONTEXT_CLUSTER1 ...`) and before the agent gateway deletion block.

- [ ] **Step 2: Verify script syntax**

Run: `bash -n cleanup.sh`
Expected: no output (no syntax errors).

- [ ] **Step 3: Commit**

```bash
git add cleanup.sh
git commit -m "feat: add cluster2 workload cleanup to cleanup script"
```

---

### Task 4: Create the Multi-Cluster demo page

Create `demo-ui/pages/2_Multi_Cluster.py` — a 4-step tabbed demo page for multicluster failover.

**Files:**
- Create: `demo-ui/pages/2_Multi_Cluster.py`

- [ ] **Step 1: Create the page file**

Create `demo-ui/pages/2_Multi_Cluster.py` with this content:

```python
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
```

- [ ] **Step 2: Verify Python syntax**

Run: `python3 -c "import ast; ast.parse(open('demo-ui/pages/2_Multi_Cluster.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add demo-ui/pages/2_Multi_Cluster.py
git commit -m "feat: add multicluster failover demo page"
```

---

### Task 5: Verify everything integrates

Smoke-test the full set of changes together.

**Files:**
- All modified files from Tasks 1-4

- [ ] **Step 1: Verify all YAML is valid**

Run: `kubectl apply --dry-run=client -f k8s/services/enrollment-chatbot.yaml`
Expected: resources listed with `(dry run)` — no errors.

- [ ] **Step 2: Verify both scripts parse**

Run: `bash -n install.sh && bash -n cleanup.sh && echo "OK"`
Expected: `OK`

- [ ] **Step 3: Verify Python page parses**

Run: `python3 -c "import ast; ast.parse(open('demo-ui/pages/2_Multi_Cluster.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Verify all imports resolve**

Run from project root:
```bash
cd demo-ui && python3 -c "
from utils.theme import inject_theme
from utils.kubectl import run_kubectl
from utils.config import DATA_PRODUCT_URL, NS_BACKEND, DEFAULT_STUDENT_ID
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 5: Final commit if any fixups were needed**

Only if changes were made during verification:
```bash
git add -A
git commit -m "fix: address integration issues from multicluster failover review"
```
