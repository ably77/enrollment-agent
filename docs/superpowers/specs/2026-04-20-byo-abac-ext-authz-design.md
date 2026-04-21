# BYO ABAC gRPC Ext-Authz for Agent Gateway

## Summary

Add a purpose-built ABAC (Attribute-Based Access Control) gRPC ext-authz server to the enrollment-agent repo, integrated into the existing Homepage as an opt-in demo feature, with a companion workshop document. Demonstrates how BYO ext-authz enforces fine-grained agent-to-LLM access control at the agent gateway based on caller attributes (role, tier) and requested resource (model).

## Motivation

The audience is interested in ABAC for service-to-service and agent-to-service communication. The existing mesh layer provides identity-based auth (binary allow/deny per service account), but ABAC decisions are richer — combining multiple attributes to make fine-grained decisions. This demo shows how a custom ext-authz server plugs into the Enterprise Agentgateway to enforce policies like "enrollment-advisor agents can use gpt-4o-mini but not gpt-4o."

## Delivery Format

- **Workshop document** — step-by-step markdown with curl-based verification
- **Demo page integration** — ABAC controls integrated into the existing Homepage (not a separate page)

## Architecture

```
Student User
  -> Enrollment Chatbot (Homepage, with ABAC persona selector)
    -> Agent Gateway Proxy
      -> ABAC Ext-Authz Server (gRPC check)
        -> Allow/Deny based on (role + tier + model)
      -> (if allowed) OpenAI Backend
```

The ext-authz server is deployed in `agentgateway-system`. An `EnterpriseAgentgatewayPolicy` targets the existing `openai` HTTPRoute, so only LLM traffic goes through ABAC — other routes are unaffected.

## Component 1: ABAC Ext-Authz Server

### Location

```
services/abac-ext-authz/
  main.go
  go.mod
  go.sum
  Dockerfile
  build-and-push.sh
```

### Policy Model

A static policy table loaded from an `ABAC_POLICIES` env var. Each entry maps a `(role:tier)` pair to a list of allowed models:

```
ABAC_POLICIES="enrollment-advisor:standard=gpt-4o-mini,analytics-agent:premium=gpt-4o|gpt-4o-mini"
```

### Decision Flow

1. Extract `x-agent-role` and `x-agent-tier` from request headers
2. If either missing -> deny ("missing agent identity attributes")
3. Look up `role:tier` in policy table -> if not found, deny ("unrecognized agent")
4. Parse `model` from JSON request body (requires `includeRequestBody` in gateway policy)
5. Check if requested model is in allowed list -> allow or deny with specific reason

### Response Headers (on allow)

- `x-abac-decision: allowed`
- `x-abac-agent: {role}`
- `x-abac-reason: agent "{role}" ({tier}) authorized for model {model}`

### Response (on deny, 403)

- Body: `denied by ABAC: agent "{role}" ({tier}) not authorized for model "{model}" (allowed: {allowed_models})`
- Header: `x-abac-decision: denied`

### Implementation

Go, using `envoyproxy/go-control-plane` for the gRPC ext-authz proto. Same dependencies and Dockerfile pattern as the existing `grpc-ext-authz` server. Multi-stage build, distroless final image. Published as `ably7/abac-ext-authz:latest` via `ly-builder` buildx (amd64/arm64).

## Component 2: Kubernetes Resources

### File: `k8s/gateway/abac-ext-authz.yaml`

Three resources in one file:

1. **Deployment** (`abac-ext-authz`) — namespace `agentgateway-system`, 1 replica, port 9000. Env vars: `ABAC_POLICIES` (policy table), `PORT=9000`.

2. **Service** (`abac-ext-authz`) — ClusterIP, port 4444 -> targetPort 9000, `appProtocol: kubernetes.io/h2c` for gRPC.

3. **EnterpriseAgentgatewayPolicy** (`abac-ext-auth-policy`) — targets `openai` HTTPRoute. References abac-ext-authz service on port 4444. Uses `grpc` with `includeRequestBody: true` for model parsing.

### Not in default install

The ABAC resources are NOT applied by `install.sh`. They are applied:
- Manually via the workshop doc
- Or described in the workshop for the presenter to apply before demoing the UI

This keeps the base install clean and the demo shows before/after.

## Component 3: Homepage Integration

### Sidebar Changes

New "Agent Identity (ABAC)" section below the student selector:

- **Checkbox**: "Enable ABAC Simulation" (default: off)
- **Role dropdown**: `enrollment-advisor` / `analytics-agent` / `unauthorized-agent` (visible when enabled)
- **Tier dropdown**: `standard` / `premium` (visible when enabled)
- **Model dropdown**: `gpt-4o-mini` / `gpt-4o` (visible when enabled; without ABAC, model stays `gpt-4o-mini`)
- **Reset to defaults button**: snaps back to ABAC disabled, role=enrollment-advisor, tier=standard, model=gpt-4o-mini

### Policy Matrix (displayed in sidebar when ABAC enabled)

| Role | Tier | gpt-4o-mini | gpt-4o |
|---|---|---|---|
| enrollment-advisor | standard | allow | deny |
| analytics-agent | premium | allow | allow |
| unauthorized-agent | — | deny | deny |

### `utils/gateway.py` Change

`chat_completion()` gains an optional `extra_headers: dict | None = None` parameter. When provided, headers are merged into the request. No change to existing callers.

### `Homepage.py` Change

When ABAC is enabled, the `chat_completion()` call passes:
- `extra_headers={"x-agent-role": role, "x-agent-tier": tier}`
- `model=selected_model` (from dropdown instead of hardcoded `gpt-4o-mini`)

### Error Display

403 responses from ext-authz flow through the existing `render_error()` path. The deny body displays naturally as a styled error in the chat. No changes to `utils/display.py`.

### What Doesn't Change

- Chat logic, tool calling, message history
- Mesh Policies page
- Sidebar gateway config, observability links
- Student selector, system prompt, data product API calls

## Component 4: Workshop Document

### File: `workshop-byo-abac-ext-authz.md` (project root)

### Structure

1. **Objectives** — deploy ABAC ext-authz, apply policy, demonstrate attribute-based decisions
2. **About ABAC Ext-Auth** — ABAC vs simple header checks, the policy model, decision flow diagram
3. **Deploy the ABAC ext-authz server** — `kubectl apply` deployment + service
4. **Verify route works without ABAC** — curl to `/openai` without agent headers, confirm 200
5. **Apply the ABAC policy** — `kubectl apply` the EnterpriseAgentgatewayPolicy
6. **Test: no agent identity -> denied** — curl without headers, 403
7. **Test: enrollment-advisor + gpt-4o-mini -> allowed** — curl with headers, 200
8. **Test: enrollment-advisor + gpt-4o -> denied** — same agent, premium model, 403 with reason
9. **Test: analytics-agent + gpt-4o -> allowed** — premium tier, 200
10. **View ext-authz logs** — ABAC decisions in server logs
11. **Demo UI integration** — point to Homepage ABAC toggle, same scenarios through chatbot
12. **Cleanup** — delete policy, deployment, service

Each step includes exact `kubectl`/`curl` commands and expected output.

## Component 5: Build & Install Integration

### No changes to `install.sh`

ABAC ext-authz is opt-in, not part of the default install.

### No changes to `build-and-redeploy.sh`

Only rebuilds the chatbot image. ABAC server is a separate image.

### New: `services/abac-ext-authz/build-and-push.sh`

Builds and pushes `ably7/abac-ext-authz:latest` via `ly-builder` buildx (amd64/arm64).

### Chatbot image rebuild

Required once to pick up Homepage sidebar changes and `gateway.py` `extra_headers` parameter. Done via existing `./build-and-redeploy.sh`.

### `cleanup.sh`

Add three `kubectl delete --ignore-not-found` lines for ABAC resources (deployment, service, policy in agentgateway-system).

### `CLAUDE.md`

Add brief entry to the project structure and "Adding a new..." sections documenting the ABAC ext-authz service.

## Demo Personas

| Persona | Role Header | Tier Header | gpt-4o-mini | gpt-4o | Use Case |
|---|---|---|---|---|---|
| Enrollment Advisor | `enrollment-advisor` | `standard` | allowed | denied | Day-to-day student support agent |
| Analytics Agent | `analytics-agent` | `premium` | allowed | allowed | Data analysis, needs powerful models |
| Unauthorized Agent | `unauthorized-agent` | (any) | denied | denied | Rogue/unknown caller — denied because no policy entry matches this role |

## Files Changed

| File | Change |
|---|---|
| `services/abac-ext-authz/main.go` | New — ABAC gRPC ext-authz server |
| `services/abac-ext-authz/go.mod` | New — Go module |
| `services/abac-ext-authz/go.sum` | New — Go dependencies |
| `services/abac-ext-authz/Dockerfile` | New — multi-stage distroless build |
| `services/abac-ext-authz/build-and-push.sh` | New — buildx push script |
| `k8s/gateway/abac-ext-authz.yaml` | New — Deployment + Service + Policy |
| `demo-ui/Homepage.py` | Modified — ABAC sidebar section, model selector, reset button |
| `demo-ui/utils/gateway.py` | Modified — `extra_headers` parameter on `chat_completion()` |
| `workshop-byo-abac-ext-authz.md` | New — workshop document |
| `cleanup.sh` | Modified — delete ABAC resources |
| `CLAUDE.md` | Modified — document ABAC ext-authz |
