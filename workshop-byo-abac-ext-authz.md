# BYO ABAC gRPC External Authorization (ext-authz)

## Pre-requisites

This lab assumes you have completed the enrollment-agent installation via `./install.sh` and the chatbot is accessible at `http://enroll.glootest.com`. The `wgu-enrollment` HTTPRoute and the `agentgateway-proxy` gateway are already running.

## Lab Objectives

- Deploy the ABAC ext-authz server to the cluster
- Apply an `EnterpriseAgentgatewayPolicy` that enforces ABAC on the `wgu-enrollment` route
- Validate that requests without agent identity headers are denied with 403
- Validate that `enrollment-advisor` (standard tier) is allowed to use `gpt-4o-mini` and denied for `gpt-4o`
- Validate that `analytics-agent` (premium tier) is allowed to use both models
- Observe ALLOWED/DENIED decisions in the ext-authz server logs
- Walk through the same scenarios using the ABAC toggle in the chatbot Demo UI

## About ABAC External Auth

Identity-based authorization asks *who are you?* — it grants access based on a verified identity (a certificate, a JWT claim, a Kubernetes ServiceAccount). That is what Istio AuthorizationPolicy does at the mesh layer.

Attribute-Based Access Control (ABAC) asks *what are you allowed to do, given the combination of attributes you carry?* — access is granted or denied based on a policy that evaluates multiple attributes simultaneously. This lets you express fine-grained rules such as "this agent, at this service tier, may call this model" without coupling the policy to any single identity.

In this lab the ABAC server evaluates three attributes sent as request headers:

| Header | Description | Example values |
|---|---|---|
| `x-agent-role` | The role of the calling agent | `enrollment-advisor`, `analytics-agent` |
| `x-agent-tier` | The service tier of the agent | `standard`, `premium` |
| `x-agent-model` | The LLM model being requested | `gpt-4o-mini`, `gpt-4o` |

The policy matrix the server enforces:

| Role | Tier | gpt-4o-mini | gpt-4o |
|---|---|---|---|
| enrollment-advisor | standard | allowed | denied |
| analytics-agent | premium | allowed | allowed |
| unauthorized-agent | any | denied | denied |

Request flow with ABAC ext-authz in place:

```
Client / Demo UI
  → Agentgateway Proxy (agentgateway-system)
      → gRPC Check(x-agent-role, x-agent-tier, x-agent-model)
          → ABAC ext-authz server
              → DENIED (403)  ← if policy check fails
              → ALLOWED       ← if policy check passes
                  → Backend LLM (OpenAI via wgu-enrollment route)
```

## Deploy the ABAC ext-authz server

Deploy the ABAC gRPC ext-authz server. The `ABAC_POLICIES` environment variable defines the policy matrix in the format `role:tier=model1|model2` with entries separated by commas.

```bash
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  namespace: agentgateway-system
  name: abac-ext-authz
  labels:
    app: abac-ext-authz
spec:
  replicas: 1
  selector:
    matchLabels:
      app: abac-ext-authz
  template:
    metadata:
      labels:
        app: abac-ext-authz
        app.kubernetes.io/name: abac-ext-authz
    spec:
      containers:
      - image: ably7/abac-ext-authz:latest
        name: abac-ext-authz
        ports:
        - containerPort: 9000
        env:
        - name: PORT
          value: "9000"
        - name: ABAC_POLICIES
          value: "enrollment-advisor:standard=gpt-4o-mini,analytics-agent:premium=gpt-4o|gpt-4o-mini"
EOF
```

Wait for the ext-authz pod to be ready:
```bash
kubectl rollout status deployment/abac-ext-authz -n agentgateway-system --timeout=60s
```

Create the Service for the ext-authz Deployment. The `appProtocol: kubernetes.io/h2c` annotation tells the gateway that this backend speaks gRPC (HTTP/2 cleartext).
```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Service
metadata:
  namespace: agentgateway-system
  name: abac-ext-authz
  labels:
    app: abac-ext-authz
spec:
  ports:
  - port: 4444
    targetPort: 9000
    protocol: TCP
    appProtocol: kubernetes.io/h2c
  selector:
    app: abac-ext-authz
EOF
```

## Verify the route works without ABAC

Confirm the `wgu-enrollment` route is healthy before locking it down. Requests should pass through to OpenAI without any ABAC headers.

```bash
export GATEWAY_IP=$(kubectl get svc -n agentgateway-system --selector=gateway.networking.k8s.io/gateway-name=agentgateway-proxy -o jsonpath='{.items[*].status.loadBalancer.ingress[0].ip}{.items[*].status.loadBalancer.ingress[0].hostname}')

curl -i "$GATEWAY_IP:8080/openai" \
  -H "content-type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {
        "role": "user",
        "content": "Say hello in one sentence."
      }
    ]
  }'
```

You should get a 200 response with a completion from OpenAI.

## Apply the ABAC ext-authz policy

Create an `EnterpriseAgentgatewayPolicy` that applies ABAC ext-authz to the `wgu-enrollment` HTTPRoute. By targeting the HTTPRoute rather than the Gateway, only traffic to this route requires ABAC — other routes are unaffected.

```bash
kubectl apply -f - <<EOF
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  namespace: agentgateway-system
  name: abac-ext-auth-policy
  labels:
    app: abac-ext-authz
spec:
  targetRefs:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: wgu-enrollment
  traffic:
    extAuth:
      backendRef:
        name: abac-ext-authz
        namespace: agentgateway-system
        port: 4444
      grpc: {}
EOF
```

## Test: request denied without agent identity

Send the same request as before. Now that the ABAC policy is active, the request is missing the required identity headers and should be denied.

```bash
curl -i "$GATEWAY_IP:8080/openai" \
  -H "content-type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {
        "role": "user",
        "content": "Say hello in one sentence."
      }
    ]
  }'
```

Expected output:
```
HTTP/1.1 403 Forbidden
content-type: text/plain
x-abac-decision: denied

denied by ABAC: missing required header: x-agent-role
```

## Test: enrollment-advisor + gpt-4o-mini → allowed

Send a request with the `enrollment-advisor` role at `standard` tier requesting `gpt-4o-mini`. This combination is in the policy matrix and should be allowed.

```bash
curl -i "$GATEWAY_IP:8080/openai" \
  -H "content-type: application/json" \
  -H "x-agent-role: enrollment-advisor" \
  -H "x-agent-tier: standard" \
  -H "x-agent-model: gpt-4o-mini" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {
        "role": "user",
        "content": "Say hello in one sentence."
      }
    ]
  }'
```

You should see a 200 response with a completion from OpenAI. The response will include the `x-abac-decision: allowed` and `x-abac-agent: enrollment-advisor` headers injected by the ext-authz server.

## Test: enrollment-advisor + gpt-4o → denied

Send the same request but request `gpt-4o`. Standard-tier `enrollment-advisor` agents are not authorized for `gpt-4o`.

```bash
curl -i "$GATEWAY_IP:8080/openai" \
  -H "content-type: application/json" \
  -H "x-agent-role: enrollment-advisor" \
  -H "x-agent-tier: standard" \
  -H "x-agent-model: gpt-4o" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {
        "role": "user",
        "content": "Say hello in one sentence."
      }
    ]
  }'
```

Expected output:
```
HTTP/1.1 403 Forbidden
content-type: text/plain
x-abac-decision: denied

denied by ABAC: agent "enrollment-advisor" (standard) not authorized for model "gpt-4o" (allowed: gpt-4o-mini)
```

## Test: analytics-agent + gpt-4o → allowed

Send a request as `analytics-agent` at `premium` tier requesting `gpt-4o`. Premium-tier analytics agents are authorized for both models.

```bash
curl -i "$GATEWAY_IP:8080/openai" \
  -H "content-type: application/json" \
  -H "x-agent-role: analytics-agent" \
  -H "x-agent-tier: premium" \
  -H "x-agent-model: gpt-4o" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {
        "role": "user",
        "content": "Say hello in one sentence."
      }
    ]
  }'
```

You should see a 200 response with a completion from OpenAI.

## Test: unauthorized-agent → denied

Send a request as an unknown agent role. Any role not in the ABAC policy table is denied by default:

```bash
curl -i "$GATEWAY_IP:8080/openai" \
  -H "content-type: application/json" \
  -H "x-agent-role: unauthorized-agent" \
  -H "x-agent-tier: standard" \
  -H "x-agent-model: gpt-4o-mini" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {
        "role": "user",
        "content": "Say hello in one sentence."
      }
    ]
  }'
```

Expected output:
```
HTTP/1.1 403 Forbidden
x-abac-decision: denied

denied by ABAC: no ABAC policy for agent "unauthorized-agent" (standard)
```

## View ext-authz logs

Check the ABAC ext-authz server logs to see the ALLOWED and DENIED decisions recorded for each request:

```bash
kubectl logs -n agentgateway-system -l app=abac-ext-authz --tail=20
```

Each log line shows the HTTP method, path, and the three ABAC header values that were evaluated, followed by an ALLOWED or DENIED line with the policy reason. For example:

```
[abac-ext-authz] POST /openai | role=enrollment-advisor tier=standard model=gpt-4o-mini
[abac-ext-authz] ALLOWED: agent "enrollment-advisor" (standard) authorized for model gpt-4o-mini
[abac-ext-authz] POST /openai | role=enrollment-advisor tier=standard model=gpt-4o
[abac-ext-authz] DENIED: agent "enrollment-advisor" (standard) not authorized for model "gpt-4o" (allowed: gpt-4o-mini)
[abac-ext-authz] POST /openai | role=analytics-agent tier=premium model=gpt-4o
[abac-ext-authz] ALLOWED: agent "analytics-agent" (premium) authorized for model gpt-4o
```

## Demo UI integration

The enrollment chatbot at `http://enroll.glootest.com` has an ABAC simulation toggle built into the sidebar. Once the ABAC policy is applied, you can use it to walk through all four scenarios interactively without writing any curl commands.

**How to use the toggle:**

1. Open `http://enroll.glootest.com` in a browser
2. In the left sidebar, locate the **Agent Identity (ABAC)** section
3. Check the **Enable ABAC Simulation** checkbox — three dropdowns appear:
   - **Agent Role**: `enrollment-advisor`, `analytics-agent`, or `unauthorized-agent`
   - **Agent Tier**: `standard` or `premium`
   - **LLM Model**: `gpt-4o-mini` or `gpt-4o`
4. When ABAC Simulation is enabled, every chat request sends `x-agent-role`, `x-agent-tier`, and `x-agent-model` headers to the gateway

**Walk through the scenarios:**

| Scenario | Role | Tier | Model | Expected result |
|---|---|---|---|---|
| No ABAC headers (toggle off) | — | — | gpt-4o-mini | 403 — missing x-agent-role |
| Authorized combination | enrollment-advisor | standard | gpt-4o-mini | 200 — chatbot responds |
| Unauthorized model | enrollment-advisor | standard | gpt-4o | 403 — model not authorized |
| Premium tier | analytics-agent | premium | gpt-4o | 200 — chatbot responds |

When a request is denied the chatbot displays the 403 error body returned by the ABAC server. Denied messages are not saved to the chat history — this prevents the blocked content from being replayed on subsequent requests.

Use the **Reset to defaults** button in the sidebar to restore default settings.

## Cleanup

Remove the ABAC policy, deployment, and service when you are done with this lab:

```bash
kubectl delete enterpriseagentgatewaypolicy -n agentgateway-system abac-ext-auth-policy
kubectl delete deployment -n agentgateway-system abac-ext-authz
kubectl delete service -n agentgateway-system abac-ext-authz
```

The `wgu-enrollment` route will continue to work without ABAC once the policy is removed.
