# Agentgateway Ingress Proxy Design

**Date:** 2026-04-20
**Status:** Approved

## Summary

Add a second agentgateway instance named `ingress` to expose user-facing services (enrollment chatbot, Grafana, Gloo UI) through a LoadBalancer on port 80 with hostname-based routing. The ingress proxy is enrolled in the ambient mesh, demonstrating agentgateway operating inside the mesh with mTLS on the ingress-to-service hop.

## Motivation

Currently, workshop attendees access services via `kubectl port-forward`. An ingress proxy provides:
- A realistic production-like access pattern for demos
- Demonstrates agentgateway as an ingress controller (not just an LLM proxy)
- Shows agentgateway participating in the ambient mesh with mTLS telemetry
- Matches the pattern established in solo-field-installer (`lib/ingress.sh`)

## Architecture

```
Student browser
  -> ingress (agentgateway-system, LoadBalancer:80, IN mesh)
    -> chatbot.glootest.local  -> enrollment-chatbot:8501 (wgu-demo-frontend, in mesh)
    -> grafana.glootest.local  -> grafana-prometheus-grafana:3000 (monitoring, not in mesh)
    -> ui.glootest.local       -> solo-enterprise-ui:80 (agentgateway-system, not in mesh)

Enrollment chatbot (internal, unchanged)
  -> agentgateway-proxy (ClusterIP:8080, NOT in mesh)
    -> LLM provider (guardrails, rate limits)
  -> data-product-api (mTLS via mesh)
    -> graph-db-mock (mTLS via mesh)
```

Two agentgateway instances coexist:
- **`ingress`** — LoadBalancer:80, mesh-enrolled, HTTP routing to user-facing services, no shared extensions
- **`agentgateway-proxy`** — ClusterIP:8080, NOT mesh-enrolled, LLM routing with guardrails/rate-limits/tracing

## New Resources

### 1. Ingress Gateway (`k8s/gateway/ingress.yaml`)

**EnterpriseAgentgatewayParameters** (`ingress-agentgateway-config`):
- `service.spec.type: LoadBalancer` with AWS NLB annotation
- `deployment.spec.replicas: 2`
- Pod template label: `istio.io/dataplane-mode: ambient` (mesh enrollment)
- Logging level: info
- No shared extensions (no extauth, ratelimiter, extCache)

**Gateway** (`ingress`):
- `gatewayClassName: enterprise-agentgateway`
- `infrastructure.parametersRef` -> `ingress-agentgateway-config`
- Single HTTP listener on port 80
- `allowedRoutes.namespaces.from: All`

### 2. HTTPRoutes (`k8s/gateway/ingress-routes.yaml`)

Three HTTPRoutes, all with `parentRefs` pointing to `ingress` in `agentgateway-system`:

| Route Name | Namespace | Hostname | Backend Service | Port |
|-----------|-----------|----------|----------------|------|
| `chatbot-ingress-route` | `wgu-demo-frontend` | `chatbot.glootest.local` | `enrollment-chatbot` | 8501 |
| `grafana-ingress-route` | `monitoring` | `grafana.glootest.local` | `grafana-prometheus-grafana` | 3000 |
| `ui-ingress-route` | `agentgateway-system` | `ui.glootest.local` | `solo-enterprise-ui` | 80 |

Routes live in their backend's namespace following the field-installer convention.

### 3. Mesh AuthorizationPolicy (`k8s/mesh/ingress-to-chatbot.yaml`)

The `wgu-demo-frontend` namespace has a deny-all policy. The ingress proxy (in the mesh) needs an explicit ALLOW to reach the chatbot.

- **Type:** AuthorizationPolicy (ALLOW)
- **Namespace:** `wgu-demo-frontend`
- **Principal:** `*/ns/agentgateway-system/sa/ingress` (the ingress proxy's service account)
- **Target:** `enrollment-chatbot` service on port 8501

Grafana (`monitoring`) and Gloo UI (`agentgateway-system`) are not in the mesh, so no policies are needed for those routes.

## Modified Files

### `install.sh`

Two additions:
1. After the `agentgateway-proxy` gateway is deployed and ready, apply `k8s/gateway/ingress.yaml` and wait for the `ingress` deployment rollout
2. After observability stack and chatbot are deployed, apply `k8s/gateway/ingress-routes.yaml` (routes reference services that must exist)

The ingress routes are applied last because they reference services across multiple namespaces that are deployed at different stages.

### `k8s/mesh/` (picked up by existing `kubectl apply -f k8s/mesh/`)

The new `ingress-to-chatbot.yaml` is automatically included by the existing `kubectl apply -f k8s/mesh/` command in `install.sh`.

### `workshop.md`

Replace `kubectl port-forward` access instructions with:
- `http://chatbot.glootest.local` for the enrollment chatbot
- `http://grafana.glootest.local` for Grafana (admin / prom-operator)
- `http://ui.glootest.local` for Gloo UI

Add a prerequisite note about `/etc/hosts` entries pointing to the ingress LoadBalancer IP.

### `CLAUDE.md`

Update the architecture diagram to show the ingress proxy and update the Quick Start access section.

## What Does NOT Change

- `agentgateway-proxy` configuration (ClusterIP, not in mesh, LLM routing)
- Guardrails, rate limits, tracing on `agentgateway-proxy`
- Existing mesh policies (deny-all, chatbot-to-data-product, data-product-to-graphdb, waypoint-to-backends)
- Service deployments, namespaces, RBAC
- Docker images or application code

## Verification

After deployment:
1. `kubectl get gateway ingress -n agentgateway-system` — should show `Programmed: True`
2. `curl -H "Host: chatbot.glootest.local" http://<INGRESS_LB_IP>/` — returns Streamlit HTML
3. `curl -H "Host: grafana.glootest.local" http://<INGRESS_LB_IP>/` — returns Grafana login
4. `curl -H "Host: ui.glootest.local" http://<INGRESS_LB_IP>/` — returns Gloo UI
5. `solo-istioctl ztunnel-config workloads | grep ingress` — shows ingress proxy enrolled in mesh
