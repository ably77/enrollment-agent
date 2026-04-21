# Agentgateway Ingress Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mesh-enrolled agentgateway ingress proxy to expose the enrollment chatbot, Grafana, and Gloo UI via hostname-based routing on a LoadBalancer.

**Architecture:** A second agentgateway instance named `ingress` (LoadBalancer:80, ambient mesh enrolled) sits alongside the existing `agentgateway-proxy` (ClusterIP:8080, not in mesh). Three HTTPRoutes map `chatbot.glootest.local`, `grafana.glootest.local`, and `ui.glootest.local` to their backend services. A new AuthorizationPolicy allows the ingress SA to reach the chatbot through the mesh's deny-all baseline.

**Tech Stack:** Kubernetes Gateway API, Enterprise Agentgateway CRDs, Istio AuthorizationPolicy

**Spec:** `docs/superpowers/specs/2026-04-20-ingress-proxy-design.md`

---

### Task 1: Create Ingress Gateway Resources

**Files:**
- Create: `k8s/gateway/ingress.yaml`

This creates the `EnterpriseAgentgatewayParameters` and `Gateway` resources for the ingress proxy, following the pattern from `solo-field-installer/lib/ingress.sh`.

- [ ] **Step 1: Create `k8s/gateway/ingress.yaml`**

```yaml
# Ingress gateway — exposes user-facing services (chatbot, Grafana, Gloo UI)
# via hostname-based routing on a LoadBalancer. Enrolled in the ambient mesh
# for mTLS on the ingress-to-service hop.
#
# This is separate from agentgateway-proxy (ClusterIP:8080), which handles
# LLM routing with guardrails/rate-limits and is NOT in the mesh.
---
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayParameters
metadata:
  name: ingress-agentgateway-config
  namespace: agentgateway-system
spec:
  logging:
    level: info
  service:
    metadata:
      annotations:
        service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
    spec:
      type: LoadBalancer
  deployment:
    spec:
      replicas: 2
      template:
        metadata:
          labels:
            istio.io/dataplane-mode: ambient
        spec:
          containers:
          - name: agentgateway
            resources:
              requests:
                cpu: 50m
                memory: 64Mi
---
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: ingress
  namespace: agentgateway-system
spec:
  gatewayClassName: enterprise-agentgateway
  infrastructure:
    parametersRef:
      group: enterpriseagentgateway.solo.io
      kind: EnterpriseAgentgatewayParameters
      name: ingress-agentgateway-config
  listeners:
  - allowedRoutes:
      namespaces:
        from: All
    name: http
    port: 80
    protocol: HTTP
```

- [ ] **Step 2: Commit**

```bash
git add k8s/gateway/ingress.yaml
git commit -m "feat: add agentgateway ingress gateway resources"
```

---

### Task 2: Create HTTPRoutes for Ingress

**Files:**
- Create: `k8s/gateway/ingress-routes.yaml`

Three HTTPRoutes routing `*.glootest.local` hostnames to backend Kubernetes services through the `ingress` gateway. Each route lives in the same file for simplicity since they're all managed together.

**Note on Grafana service name:** The kube-prometheus-stack chart with helm release name `grafana-prometheus` creates a Grafana service named `grafana-prometheus-grafana` in the `monitoring` namespace. The existing `workshop.md` and `install.sh` reference `svc/grafana-prometheus` in port-forward commands — this is likely wrong (the real service is `grafana-prometheus-grafana`). The HTTPRoute below uses the correct chart-generated name. Verify with `kubectl get svc -n monitoring --context $KUBECONTEXT_CLUSTER1` after install.

- [ ] **Step 1: Create `k8s/gateway/ingress-routes.yaml`**

```yaml
# HTTPRoutes for the ingress gateway — hostname-based routing to user-facing services.
# All routes reference the 'ingress' gateway in agentgateway-system.
#
# /etc/hosts (pointing to the ingress LoadBalancer IP):
#   <INGRESS_LB_IP> chatbot.glootest.local grafana.glootest.local ui.glootest.local
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: chatbot-ingress-route
  namespace: wgu-demo-frontend
spec:
  hostnames:
  - "chatbot.glootest.local"
  parentRefs:
  - name: ingress
    namespace: agentgateway-system
  rules:
  - backendRefs:
    - name: enrollment-chatbot
      port: 8501
    matches:
    - path:
        type: PathPrefix
        value: /
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: grafana-ingress-route
  namespace: monitoring
spec:
  hostnames:
  - "grafana.glootest.local"
  parentRefs:
  - name: ingress
    namespace: agentgateway-system
  rules:
  - backendRefs:
    - name: grafana-prometheus-grafana
      port: 3000
    matches:
    - path:
        type: PathPrefix
        value: /
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: ui-ingress-route
  namespace: agentgateway-system
spec:
  hostnames:
  - "ui.glootest.local"
  parentRefs:
  - name: ingress
    namespace: agentgateway-system
  rules:
  - backendRefs:
    - name: solo-enterprise-ui
      port: 80
    matches:
    - path:
        type: PathPrefix
        value: /
```

- [ ] **Step 2: Commit**

```bash
git add k8s/gateway/ingress-routes.yaml
git commit -m "feat: add HTTPRoutes for ingress (chatbot, grafana, gloo UI)"
```

---

### Task 3: Create Mesh AuthorizationPolicy for Ingress

**Files:**
- Create: `k8s/mesh/ingress-to-chatbot.yaml`

The `wgu-demo-frontend` namespace has a deny-all policy (`k8s/mesh/deny-all.yaml`). The ingress proxy is mesh-enrolled, so its traffic to the chatbot is subject to mesh policy. This ALLOW policy permits the ingress SA to reach the chatbot.

Grafana (`monitoring`) and Gloo UI (`agentgateway-system`) are not in the mesh, so no policies are needed for those.

- [ ] **Step 1: Create `k8s/mesh/ingress-to-chatbot.yaml`**

```yaml
# Allow the ingress gateway to reach the enrollment chatbot.
# Required because wgu-demo-frontend has a deny-all baseline and
# the ingress proxy is enrolled in the ambient mesh.
apiVersion: security.istio.io/v1
kind: AuthorizationPolicy
metadata:
  name: ingress-to-chatbot
  namespace: wgu-demo-frontend
spec:
  action: ALLOW
  rules:
  - from:
    - source:
        principals:
        - "*/ns/agentgateway-system/sa/ingress"
    to:
    - operation:
        ports: ["8501"]
```

- [ ] **Step 2: Commit**

```bash
git add k8s/mesh/ingress-to-chatbot.yaml
git commit -m "feat: add mesh policy allowing ingress to reach chatbot"
```

---

### Task 4: Update install.sh

**Files:**
- Modify: `install.sh:241-251` (after agentgateway-proxy is ready, add ingress gateway deployment)
- Modify: `install.sh:400-410` (after LLM backend config, apply ingress routes)
- Modify: `install.sh:412-432` (update completion output with new URLs)

The ingress gateway is deployed right after the `agentgateway-proxy` is ready (same controller handles both). The ingress routes are applied at the end after all backend services (chatbot, Grafana, Gloo UI) exist.

- [ ] **Step 1: Add ingress gateway deployment after agentgateway-proxy is ready**

After line 251 (`kubectl wait --for=condition=ready pod ... agentgateway-proxy`), add:

```bash

# --- Deploy ingress gateway ---
echo "=== Deploying ingress gateway ==="
kubectl apply -f k8s/gateway/ingress.yaml --context $KUBECONTEXT_CLUSTER1

echo "Waiting for ingress gateway..."
kubectl wait --for=condition=programmed gateway ingress \
  -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --timeout=120s
kubectl wait --for=condition=ready pod -l gateway.networking.k8s.io/gateway-name=ingress \
  -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --timeout=120s
```

- [ ] **Step 2: Add ingress routes after chatbot deployment**

After line 410 (`kubectl rollout status deploy/enrollment-chatbot`), add:

```bash

# --- Apply ingress routes ---
echo "=== Applying ingress routes ==="
kubectl apply -f k8s/gateway/ingress-routes.yaml --context $KUBECONTEXT_CLUSTER1
```

- [ ] **Step 3: Update the completion output**

Replace the existing completion output block (lines 412-432) with:

```bash
# --- Done ---
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
```

- [ ] **Step 4: Commit**

```bash
git add install.sh
git commit -m "feat: deploy ingress gateway and routes in install script"
```

---

### Task 5: Update cleanup.sh

**Files:**
- Modify: `cleanup.sh:32-33` (add ingress gateway resource deletion alongside agentgateway-proxy)

The cleanup script already deletes everything in `k8s/gateway/` (line 27), which covers the new `ingress.yaml` and `ingress-routes.yaml`. But the inline resources (Gateway, EnterpriseAgentgatewayParameters) need explicit deletion too, matching the existing pattern for `agentgateway-proxy`.

- [ ] **Step 1: Add ingress gateway cleanup**

After line 33 (`kubectl delete enterpriseagentgatewayparameters agentgateway-config ...`), add:

```bash
kubectl delete gateway ingress -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
kubectl delete enterpriseagentgatewayparameters ingress-agentgateway-config -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
```

- [ ] **Step 2: Commit**

```bash
git add cleanup.sh
git commit -m "feat: add ingress gateway cleanup"
```

---

### Task 6: Update workshop.md

**Files:**
- Modify: `workshop.md:878-901` (Section 3.6 Observability — replace port-forward with ingress URLs)
- Modify: `workshop.md:1092-1103` (Section 5.3 — replace chatbot port-forward with ingress URL)

Replace `kubectl port-forward` instructions with ingress URLs. Keep port-forward as a fallback note.

- [ ] **Step 1: Update Section 3.6 (Observability)**

Replace the Gloo UI and Grafana access blocks at lines 878-901 with:

```markdown
**Access the Gloo UI:**

Open http://ui.glootest.local — you'll see:
- Request traces for each LLM call
- Token counts per request
- Guardrail evaluations (blocked/allowed)
- Latency metrics

**Access Grafana:**

Open http://grafana.glootest.local (admin / prom-operator):
- `agentgateway_gen_ai_client_token_usage` — tokens consumed
- `agentgateway_requests_total` — request counts by status
- `agentgateway_guardrail_checks` — guardrail evaluations

> **Fallback:** If the ingress gateway is not available, use port-forward:
> ```bash
> kubectl port-forward -n agentgateway-system svc/solo-enterprise-ui 4000:80 --context $KUBECONTEXT_CLUSTER1
> kubectl port-forward -n monitoring svc/grafana-prometheus-grafana 3000:3000 --context $KUBECONTEXT_CLUSTER1
> ```
```

- [ ] **Step 2: Update Section 5.3 (Open the Enrollment Chatbot)**

Replace the chatbot access block at lines 1092-1103 with:

```markdown
### 5.3 Open the Enrollment Chatbot

Open http://chatbot.glootest.local

> **Fallback:** If the ingress gateway is not available:
> ```bash
> kubectl port-forward svc/enrollment-chatbot -n wgu-demo-frontend 8501:8501 --context $KUBECONTEXT_CLUSTER1
> ```
> Open http://localhost:8501
```

- [ ] **Step 3: Commit**

```bash
git add workshop.md
git commit -m "docs: replace port-forward with ingress URLs in workshop"
```

---

### Task 7: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md:10-16` (architecture diagram)
- Modify: `CLAUDE.md:55-64` (Quick Start access section)

- [ ] **Step 1: Update architecture diagram**

Replace the architecture block at lines 10-16 with:

```markdown
## Architecture

```
Student User
  → Ingress Gateway (agentgateway-system, LoadBalancer:80, in mesh)
    → Enrollment Chatbot (Streamlit, wgu-demo-frontend namespace)
      → Agent Gateway (agentgateway-system, ClusterIP:8080) → LLM Provider (OpenAI/Anthropic)
      → Data Product API (wgu-demo namespace, through mesh with mTLS)
        → Graph DB Mock (wgu-demo namespace, through waypoint)
  → Grafana (monitoring namespace)
  → Gloo UI (agentgateway-system namespace)
```
```

- [ ] **Step 2: Update Quick Start access section**

Replace the access block at lines 55-64 with:

```markdown
## Quick Start

```bash
# Prerequisites: two k8s clusters (cluster1, cluster2), Solo license, OpenAI key
export SOLO_TRIAL_LICENSE_KEY=<key>
export OPENAI_API_KEY=<key>
./install.sh

# /etc/hosts (point to ingress LoadBalancer IP):
# <INGRESS_IP> chatbot.glootest.local grafana.glootest.local ui.glootest.local

# Access
# http://chatbot.glootest.local    — Enrollment chatbot
# http://grafana.glootest.local    — Grafana (admin / prom-operator)
# http://ui.glootest.local         — Gloo UI (traces)
```
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md architecture and access for ingress"
```

---

### Task 8: Update sidebar.py observability links

**Files:**
- Modify: `demo-ui/utils/sidebar.py:46-47` (replace port-forward captions with ingress URLs)

- [ ] **Step 1: Update observability captions**

Replace lines 46-47 in `demo-ui/utils/sidebar.py`:

```python
        st.caption("Gloo UI: `kubectl port-forward -n agentgateway-system svc/solo-enterprise-ui 4000:80`")
        st.caption("Grafana: `kubectl port-forward -n monitoring svc/grafana-prometheus 3000:3000`")
```

with:

```python
        st.caption("Gloo UI: [ui.glootest.local](http://ui.glootest.local)")
        st.caption("Grafana: [grafana.glootest.local](http://grafana.glootest.local)")
```

- [ ] **Step 2: Commit**

```bash
git add demo-ui/utils/sidebar.py
git commit -m "feat: update sidebar observability links to use ingress URLs"
```

---

### Task 9: Verify (manual, post-deploy)

These are manual verification steps to run after deploying to a cluster.

- [ ] **Step 1: Verify ingress gateway is programmed**

```bash
kubectl get gateway ingress -n agentgateway-system --context $KUBECONTEXT_CLUSTER1
```

Expected: `Programmed: True` in conditions.

- [ ] **Step 2: Verify ingress is mesh-enrolled**

```bash
solo-istioctl ztunnel-config workloads --context $KUBECONTEXT_CLUSTER1 | grep ingress
```

Expected: ingress pods show with HBONE protocol.

- [ ] **Step 3: Verify Grafana service name**

```bash
kubectl get svc -n monitoring --context $KUBECONTEXT_CLUSTER1
```

Verify the Grafana service is named `grafana-prometheus-grafana`. If it's different, update `k8s/gateway/ingress-routes.yaml` accordingly.

- [ ] **Step 4: Test each route**

```bash
INGRESS_IP=$(kubectl get svc ingress -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

curl -s -o /dev/null -w "%{http_code}" -H "Host: chatbot.glootest.local" http://$INGRESS_IP/
# Expected: 200

curl -s -o /dev/null -w "%{http_code}" -H "Host: grafana.glootest.local" http://$INGRESS_IP/
# Expected: 302 (Grafana login redirect)

curl -s -o /dev/null -w "%{http_code}" -H "Host: ui.glootest.local" http://$INGRESS_IP/
# Expected: 200
```

- [ ] **Step 5: Verify mesh policy allows ingress to chatbot**

```bash
# This should work (ingress SA is allowed)
curl -H "Host: chatbot.glootest.local" http://$INGRESS_IP/

# Check ztunnel logs for the allowed connection
kubectl logs -n istio-system -l app=ztunnel --context $KUBECONTEXT_CLUSTER1 --tail=20 | grep -i "inbound.*8501"
```
