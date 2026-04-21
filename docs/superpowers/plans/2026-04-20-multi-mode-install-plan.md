# Multi-Mode Install Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor install.sh to support an interactive mode selection — full end-to-end install or demo-only mode that deploys workloads onto existing infrastructure.

**Architecture:** The existing linear install.sh is refactored into functions: `prompt_mode`, `validate_full`, `validate_demo`, `check_infra`, `install_infra`, `install_istio` (existing), `deploy_workloads`, and `print_access_info`. Full mode calls all of them; demo mode skips `install_infra` and runs `check_infra` instead. The `deploy_workloads` function is shared by both modes.

**Tech Stack:** Bash

**Spec:** `docs/superpowers/specs/2026-04-20-multi-mode-install-design.md`

---

## File Structure

Only one file is modified:
- **Modify:** `install.sh` — refactor from linear script into functions with mode selection

The current install.sh is 453 lines. After refactoring it will have the same content reorganized into functions with a mode prompt at the top.

---

### Task 1: Add prompt_mode function and mode dispatch

**Files:**
- Modify: `install.sh`

Replace the script header, config, and validation sections (lines 1-29) with the mode prompt, config, and a main dispatch block. The `install_istio` function (lines 48-136) stays as-is.

- [ ] **Step 1: Replace lines 1-29 with the new header, config, prompt, and dispatch**

Replace everything from line 1 through line 29 (`echo "Clusters reachable, credentials set."`) with:

```bash
#!/bin/bash
set -e

# WGU Demo Workshop — Install Script
# Supports two modes:
#   1) Full install — Istio, AgentGateway, observability, and demo workloads (two clusters)
#   2) Demo only   — Deploy enrollment-agent workloads onto existing infrastructure

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Config ---
export KUBECONTEXT_CLUSTER1=${KUBECONTEXT_CLUSTER1:-cluster1}
export KUBECONTEXT_CLUSTER2=${KUBECONTEXT_CLUSTER2:-cluster2}
export MESH_NAME_CLUSTER1=${MESH_NAME_CLUSTER1:-cluster1}
export MESH_NAME_CLUSTER2=${MESH_NAME_CLUSTER2:-cluster2}
export ISTIO_VERSION=${ISTIO_VERSION:-1.29.0}
export ENTERPRISE_AGW_VERSION=${ENTERPRISE_AGW_VERSION:-v2.3.0}
export AGW_UI_VERSION=${AGW_UI_VERSION:-0.3.12}

# --- Mode selection ---
prompt_mode() {
  echo ""
  echo "=== WGU Demo Workshop Installer ==="
  echo ""
  echo "Select install mode:"
  echo "  1) Full install    — Istio, AgentGateway, observability, and demo workloads (two clusters required)"
  echo "  2) Demo only       — Deploy enrollment-agent workloads onto existing infrastructure"
  echo ""
  while true; do
    read -rp "Choice [1/2]: " choice
    case "$choice" in
      1|"") echo "full"; return ;;
      2)    echo "demo"; return ;;
      *)    echo "Invalid choice. Enter 1 or 2." ;;
    esac
  done
}

# --- Validation ---
validate_full() {
  echo "=== Validating prerequisites (full install) ==="
  for var in SOLO_TRIAL_LICENSE_KEY OPENAI_API_KEY; do
    if [ -z "${!var}" ]; then
      echo "ERROR: $var is not set"
      exit 1
    fi
  done
  kubectl cluster-info --context $KUBECONTEXT_CLUSTER1 > /dev/null 2>&1 || { echo "ERROR: Cannot reach $KUBECONTEXT_CLUSTER1"; exit 1; }
  kubectl cluster-info --context $KUBECONTEXT_CLUSTER2 > /dev/null 2>&1 || { echo "ERROR: Cannot reach $KUBECONTEXT_CLUSTER2"; exit 1; }
  echo "Clusters reachable, credentials set."
}

validate_demo() {
  echo "=== Validating prerequisites (demo only) ==="
  if [ -z "$OPENAI_API_KEY" ]; then
    echo "ERROR: OPENAI_API_KEY is not set"
    exit 1
  fi
  kubectl cluster-info --context $KUBECONTEXT_CLUSTER1 > /dev/null 2>&1 || { echo "ERROR: Cannot reach $KUBECONTEXT_CLUSTER1"; exit 1; }
  echo "Cluster reachable, API key set."
}
```

- [ ] **Step 2: Commit**

```bash
git add install.sh
git commit -m "refactor: add mode prompt and validation functions to install.sh"
```

---

### Task 2: Add check_infra function

**Files:**
- Modify: `install.sh`

Add the `check_infra` function after `validate_demo`. This function runs prerequisite checks for demo-only mode.

- [ ] **Step 1: Add check_infra function after validate_demo**

Insert after the closing `}` of `validate_demo`:

```bash

# --- Infrastructure checks (demo-only) ---
check_infra() {
  echo "=== Checking existing infrastructure ==="
  local ctx=$KUBECONTEXT_CLUSTER1
  local failed=0

  # Istio control plane
  if ! kubectl get pods -n istio-system -l app=istiod --context $ctx 2>/dev/null | grep -q Running; then
    echo "ERROR: Istio not found in istio-system"
    failed=1
  fi

  # ztunnel (ambient mesh)
  if ! kubectl get pods -n istio-system -l app=ztunnel --context $ctx 2>/dev/null | grep -q Running; then
    echo "ERROR: ztunnel not found — ambient mesh required"
    failed=1
  fi

  # AgentGateway controller
  if ! kubectl get pods -n agentgateway-system -l app.kubernetes.io/name=enterprise-agentgateway --context $ctx 2>/dev/null | grep -q Running; then
    echo "ERROR: Enterprise AgentGateway controller not found"
    failed=1
  fi

  # AgentGateway proxy instance
  if ! kubectl get gateway agentgateway-proxy -n agentgateway-system --context $ctx &>/dev/null; then
    echo "ERROR: agentgateway-proxy gateway not found"
    failed=1
  fi

  # Monitoring namespace
  if ! kubectl get ns monitoring --context $ctx &>/dev/null; then
    echo "ERROR: monitoring namespace not found — observability stack required"
    failed=1
  fi

  if [ $failed -eq 1 ]; then
    echo ""
    echo "Prerequisites not met. Install infrastructure first (mode 1) or use a solo-field-installer profile."
    exit 1
  fi

  echo "All infrastructure prerequisites found."
}
```

- [ ] **Step 2: Commit**

```bash
git add install.sh
git commit -m "feat: add check_infra function for demo-only prerequisite checks"
```

---

### Task 3: Wrap infrastructure installation in install_infra function

**Files:**
- Modify: `install.sh`

Wrap the existing infrastructure code (solo-istioctl install, root CA, `install_istio` calls, multi-cluster linking, agentgateway helm installs, agentgateway-proxy creation, ingress gateway, observability stack, access logging, tracing, dashboard import) into a single `install_infra` function.

This is the code from the current lines starting at `# --- solo-istioctl ---` through `echo "Observability stack installed."` — everything between the validation section and the `# --- LLM backend` section.

- [ ] **Step 1: Wrap infrastructure code in install_infra function**

Find the line `# --- solo-istioctl ---` (currently around line 31 after Task 1's changes). Insert `install_infra() {` before it, and close the function with `}` after the line `echo "Observability stack installed."`.

The `install_istio` function definition (lines 48-136 in the original) stays nested inside `install_infra` — this is fine in bash and keeps it scoped.

Before `# --- solo-istioctl ---`, add:
```bash

# --- Infrastructure installation (full mode only) ---
install_infra() {
```

After `echo "Observability stack installed."`, add:
```bash
}
```

- [ ] **Step 2: Commit**

```bash
git add install.sh
git commit -m "refactor: wrap infrastructure installation in install_infra function"
```

---

### Task 4: Wrap workload deployment in deploy_workloads function

**Files:**
- Modify: `install.sh`

Wrap the workload deployment code (LLM backend config through ingress routes) into a `deploy_workloads` function. This is the code from `# --- LLM backend, route, guardrails, rate limits ---` through `kubectl apply -f k8s/gateway/ingress-routes.yaml`.

But `deploy_workloads` also needs to include the WGU workload deployment and mesh policy steps that currently live before the infra section. These steps need to move into `deploy_workloads`:
- Namespaces (`k8s/namespaces.yaml`)
- Backend services (graph-db-mock, data-product-api)
- Mesh policies + waypoint
- Ingress gateway deployment (currently inside infra — needs to move to workloads since demo-only also needs it)

- [ ] **Step 1: Move workload steps out of the linear flow and into deploy_workloads**

Find these sections currently in the linear flow (between the `install_istio` calls/multi-cluster linking and the `install_infra` start):

The current linear flow has:
1. `install_istio` calls + multi-cluster linking (stays in `install_infra`)
2. WGU workloads deployment (moves to `deploy_workloads`)
3. Mesh policies (moves to `deploy_workloads`)
4. Enterprise Agentgateway install (stays in `install_infra`)
5. Ingress gateway (moves to `deploy_workloads`)
6. Observability stack (stays in `install_infra`)
7. LLM backend + chatbot + routes (moves to `deploy_workloads`)

Create the `deploy_workloads` function after the `install_infra` closing `}`:

```bash

# --- Deploy enrollment-agent workloads (shared by both modes) ---
deploy_workloads() {
  local ctx=$KUBECONTEXT_CLUSTER1

  # --- Namespaces ---
  echo "=== Deploying WGU demo workloads ==="
  kubectl apply -f k8s/namespaces.yaml --context $ctx

  # --- Backend services ---
  kubectl apply -f k8s/services/graph-db-mock.yaml --context $ctx
  kubectl apply -f k8s/services/data-product-api.yaml --context $ctx
  kubectl rollout status deploy/graph-db-mock -n wgu-demo --watch --timeout=120s --context $ctx
  kubectl rollout status deploy/data-product-api -n wgu-demo --watch --timeout=120s --context $ctx

  # --- Mesh policies and waypoint ---
  echo "=== Applying mesh policies ==="
  kubectl apply -f k8s/mesh/ --context $ctx
  kubectl label namespace wgu-demo istio.io/use-waypoint=wgu-demo-waypoint --context $ctx --overwrite
  kubectl rollout status deploy/wgu-demo-waypoint -n wgu-demo --watch --timeout=120s --context $ctx

  # --- LLM backend, route, guardrails, rate limits ---
  echo "=== Configuring LLM backend and policies ==="
  kubectl create secret generic openai-secret -n agentgateway-system \
    --from-literal="Authorization=Bearer $OPENAI_API_KEY" \
    --dry-run=client -oyaml | kubectl apply --context $ctx -f -

  kubectl apply -f k8s/gateway/backend.yaml -f k8s/gateway/route.yaml \
    -f k8s/gateway/guardrails.yaml -f k8s/gateway/rate-limit.yaml \
    --context $ctx

  # --- Deploy enrollment chatbot ---
  echo "=== Deploying enrollment chatbot ==="
  kubectl apply -f k8s/services/enrollment-chatbot.yaml --context $ctx
  kubectl rollout status deploy/enrollment-chatbot -n wgu-demo-frontend --watch --timeout=120s --context $ctx

  # --- Deploy ingress gateway ---
  echo "=== Deploying ingress gateway ==="
  kubectl apply -f k8s/gateway/ingress.yaml --context $ctx

  echo "Waiting for ingress gateway..."
  kubectl wait --for=condition=programmed gateway ingress \
    -n agentgateway-system --context $ctx --timeout=120s
  kubectl wait --for=condition=ready pod -l gateway.networking.k8s.io/gateway-name=ingress \
    -n agentgateway-system --context $ctx --timeout=120s

  # --- Apply ingress routes ---
  echo "=== Applying ingress routes ==="
  kubectl apply -f k8s/gateway/ingress-routes.yaml --context $ctx

  # --- Grafana dashboard ---
  DASHBOARD_JSON="${SCRIPT_DIR}/k8s/observability/agentgateway-grafana-dashboard-v1.json"
  if [ -f "$DASHBOARD_JSON" ]; then
    kubectl create configmap agentgateway-dashboard \
      --from-file=agentgateway-overview.json="$DASHBOARD_JSON" \
      --namespace monitoring --context $ctx \
      --dry-run=client -o yaml | \
    kubectl label --local -f - grafana_dashboard="1" --dry-run=client -o yaml | \
    kubectl apply --context $ctx -f -
  else
    echo "WARNING: Grafana dashboard JSON not found at $DASHBOARD_JSON — skipping dashboard import"
  fi
}
```

Also remove these sections from `install_infra` since they've moved to `deploy_workloads`:
- The WGU workloads deployment block (namespaces, services, rollouts)
- The mesh policies block
- The ingress gateway block
- The Grafana dashboard import block

The `install_infra` function should end after the tracing policy apply and `echo "Observability stack installed."`.

- [ ] **Step 2: Commit**

```bash
git add install.sh
git commit -m "refactor: extract deploy_workloads function shared by both modes"
```

---

### Task 5: Wrap completion output in print_access_info and add main dispatch

**Files:**
- Modify: `install.sh`

Wrap the completion output in `print_access_info` and add the main dispatch logic at the bottom of the file.

- [ ] **Step 1: Wrap completion output in print_access_info function**

Replace the `# --- Done ---` block through end of file with:

```bash

# --- Completion output ---
print_access_info() {
  echo ""
  echo "============================================"
  echo "  WGU Demo Workshop — Install Complete"
  echo "============================================"
  echo ""
  echo "Access via ingress gateway (requires /etc/hosts entries):"
  echo "  http://chatbot.glootest.local    — Enrollment chatbot"
  echo "  http://grafana.glootest.local    — Grafana (admin / prom-operator)"
  echo "  http://ui.glootest.local         — Gloo UI (traces)"
  echo ""
  echo "Ingress LoadBalancer IP:"
  echo "  kubectl get svc ingress -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 -o jsonpath='{.status.loadBalancer.ingress[0].ip}'"
  echo ""
  echo "Add to /etc/hosts:"
  echo "  <INGRESS_IP> chatbot.glootest.local grafana.glootest.local ui.glootest.local"
  echo ""
  echo "Fallback (port-forward):"
  echo "  kubectl port-forward svc/enrollment-chatbot -n wgu-demo-frontend 8501:8501 --context $KUBECONTEXT_CLUSTER1"
  echo "  kubectl port-forward -n agentgateway-system svc/solo-enterprise-ui 4000:80 --context $KUBECONTEXT_CLUSTER1"
  echo "  kubectl port-forward -n monitoring svc/grafana-prometheus-grafana 3000:3000 --context $KUBECONTEXT_CLUSTER1"
  echo ""
  echo "Verify mesh enrollment:"
  echo "  solo-istioctl ztunnel-config workloads --context $KUBECONTEXT_CLUSTER1 | grep -E 'wgu-demo|ingress'"
  echo ""
}
```

- [ ] **Step 2: Add main dispatch at the bottom of the file**

After `print_access_info`, add:

```bash

# =============================================================================
# Main
# =============================================================================
INSTALL_MODE=$(prompt_mode)

case "$INSTALL_MODE" in
  full)
    validate_full
    install_infra
    deploy_workloads
    ;;
  demo)
    validate_demo
    check_infra
    deploy_workloads
    ;;
esac

print_access_info
```

- [ ] **Step 3: Remove any remaining linear code that's now inside functions**

At this point, all the code between the function definitions should be inside functions. The file structure should be:

1. Shebang + config (lines 1-17)
2. `prompt_mode()` function
3. `validate_full()` function
4. `validate_demo()` function
5. `check_infra()` function
6. `install_infra()` function (contains `install_istio()` nested inside)
7. `deploy_workloads()` function
8. `print_access_info()` function
9. Main dispatch block

Verify there's no code executing outside of functions (except the config block and the main dispatch at the bottom). Remove any orphaned linear code.

- [ ] **Step 4: Verify the script parses**

Run: `bash -n install.sh`
Expected: No output (clean parse)

- [ ] **Step 5: Commit**

```bash
git add install.sh
git commit -m "refactor: add print_access_info and main dispatch for mode selection"
```

---

### Task 6: Verify the complete refactored script

**Files:**
- Verify: `install.sh`

- [ ] **Step 1: Verify script structure**

Run: `bash -n install.sh`
Expected: No output (clean parse)

- [ ] **Step 2: Verify all functions exist**

Run: `grep -n '^[a-z_]*()' install.sh`
Expected output should show these functions:
```
prompt_mode()
validate_full()
validate_demo()
check_infra()
install_istio()    (nested inside install_infra)
install_infra()
deploy_workloads()
print_access_info()
```

- [ ] **Step 3: Verify the main dispatch block exists at the end**

Run: `tail -20 install.sh`
Expected: Should show the `INSTALL_MODE=$(prompt_mode)` and `case` dispatch block.

- [ ] **Step 4: Verify no code runs outside functions (except config and main)**

Skim the script to confirm:
- Lines 1-17: shebang, set -e, config vars — OK, these run at source time
- All other code is inside function bodies
- Main dispatch block at the bottom calls the functions

- [ ] **Step 5: Commit (if any fixes were needed)**

```bash
git add install.sh
git commit -m "fix: clean up install.sh refactoring"
```
