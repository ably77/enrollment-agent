# Multi-Mode Install Script Design

**Date:** 2026-04-20
**Status:** Approved

## Summary

Refactor install.sh to support two modes selected via an interactive prompt: full end-to-end install (current behavior) and demo-only mode that deploys enrollment-agent workloads onto existing infrastructure provisioned by a solo-field-installer profile.

## Motivation

The current install.sh always installs everything from scratch (Istio, multi-cluster linking, agentgateway, observability). When presenting the demo on infrastructure already provisioned by a solo-field-installer profile (e.g., `2-cluster/enterprise-agentgateway-istio-helm-ambient.env`), the install script should be able to skip infra and deploy only the enrollment-agent workloads.

## Mode Selection

On startup, install.sh presents an interactive menu:

```
=== WGU Demo Workshop Installer ===

Select install mode:
  1) Full install    — Istio, AgentGateway, observability, and demo workloads (two clusters required)
  2) Demo only       — Deploy enrollment-agent workloads onto existing infrastructure

Choice [1/2]:
```

Default is 1 if the user just presses Enter. Invalid input re-prompts.

## Mode 1: Full Install

Identical to the current install.sh behavior. Requires two clusters. Installs Istio on both, multi-cluster linking, agentgateway (controller + proxy + shared extensions), observability stack (Gloo UI, Prometheus/Grafana), then deploys workloads.

Validation: `KUBECONTEXT_CLUSTER1`, `KUBECONTEXT_CLUSTER2` reachable; `SOLO_TRIAL_LICENSE_KEY` and `OPENAI_API_KEY` set.

## Mode 2: Demo Only

### Validation

Only `KUBECONTEXT_CLUSTER1` reachable; `OPENAI_API_KEY` set. Does NOT require `KUBECONTEXT_CLUSTER2` or `SOLO_TRIAL_LICENSE_KEY` (infra already licensed).

### Prerequisite Checks

Run before deploying anything. All checks target `$KUBECONTEXT_CLUSTER1`. Fail with a clear message if any check fails.

| Check | Command | Error |
|-------|---------|-------|
| Istio control plane | `kubectl get pods -n istio-system -l app=istiod` has running pods | "Istio not found in istio-system" |
| ztunnel | `kubectl get pods -n istio-system -l app=ztunnel` has running pods | "ztunnel not found — ambient mesh required" |
| AgentGateway controller | `kubectl get pods -n agentgateway-system -l app.kubernetes.io/name=enterprise-agentgateway` has running pods | "Enterprise AgentGateway controller not found" |
| AgentGateway proxy | `kubectl get gateway agentgateway-proxy -n agentgateway-system` exists | "agentgateway-proxy gateway not found" |
| Monitoring namespace | `kubectl get ns monitoring` exists | "monitoring namespace not found — observability stack required" |

### What Demo-Only Deploys

All on `$KUBECONTEXT_CLUSTER1`:

1. Namespaces (`k8s/namespaces.yaml`)
2. Backend services — graph-db-mock, data-product-api (wait for rollout)
3. Mesh policies + waypoint (`k8s/mesh/`), label namespace for waypoint
4. LLM secret (openai-secret) + gateway config (backend.yaml, route.yaml, guardrails.yaml, rate-limit.yaml — attached to existing `agentgateway-proxy`)
5. Enrollment chatbot (wait for rollout)
6. Ingress gateway (`k8s/gateway/ingress.yaml`) + wait for ready
7. Ingress routes (`k8s/gateway/ingress-routes.yaml`)
8. Grafana dashboard configmap (if JSON file exists)

### What Demo-Only Skips

- solo-istioctl installation
- Shared root CA generation
- Istio installation (istio-base, istio-cni, istiod, ztunnel) on both clusters
- Multi-cluster linking (east-west gateways, `multicluster expose/link`)
- Gateway API CRDs (already installed by profile)
- Enterprise AgentGateway helm installs (CRDs, controller)
- `agentgateway-proxy` Gateway + EnterpriseAgentgatewayParameters creation
- Observability stack (Gloo UI helm, Prometheus/Grafana helm)
- PodMonitor for gateway metrics
- Access logging + tracing policies (already configured by profile)

## Script Structure

Refactor install.sh into functions. One file, no external dependencies.

```
install.sh
  ├── prompt_mode()            — interactive menu, returns "full" or "demo"
  ├── validate_full()          — both clusters reachable, all env vars set
  ├── validate_demo()          — cluster1 reachable, OPENAI_API_KEY set
  ├── check_infra()            — prerequisite pod/resource checks (demo-only)
  ├── install_infra()          — Istio, multi-cluster, agentgateway, observability (full only)
  ├── deploy_workloads()       — namespaces, services, mesh, gateway config, chatbot, ingress
  └── print_access_info()      — completion output
```

**Full mode flow:** `prompt_mode` → `validate_full` → `install_infra` → `deploy_workloads` → `print_access_info`

**Demo mode flow:** `prompt_mode` → `validate_demo` → `check_infra` → `deploy_workloads` → `print_access_info`

The `deploy_workloads()` function is shared by both modes — identical steps for deploying the enrollment-agent-specific resources.

## What Does NOT Change

- All YAML files in `k8s/` (no changes)
- cleanup.sh (already deletes both infra and workload resources)
- workshop.md, CLAUDE.md, sidebar.py
- Docker images or application code
- The ingress proxy work (separate spec, already implemented)
