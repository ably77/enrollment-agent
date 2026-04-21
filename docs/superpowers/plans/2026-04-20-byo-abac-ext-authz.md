# BYO ABAC gRPC Ext-Authz Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a purpose-built ABAC gRPC ext-authz server to the enrollment-agent repo, integrated into the Homepage sidebar, with a workshop companion doc.

**Architecture:** A Go gRPC ext-authz server enforces ABAC at the agent gateway. The chatbot sends agent identity headers (`x-agent-role`, `x-agent-tier`, `x-agent-model`) with each LLM request. The ext-authz checks a `(role:tier) -> [allowed models]` policy table and returns allow/deny. An `EnterpriseAgentgatewayPolicy` wires it to the `wgu-enrollment` HTTPRoute.

**Tech Stack:** Go 1.25, envoyproxy/go-control-plane, gRPC, Streamlit (Python), Kubernetes/Gateway API, Enterprise Agentgateway CRDs

**Design spec:** `docs/superpowers/specs/2026-04-20-byo-abac-ext-authz-design.md`

---

### Task 1: ABAC Ext-Authz Server — Go Implementation

**Files:**
- Create: `services/abac-ext-authz/main.go`
- Create: `services/abac-ext-authz/main_test.go`
- Create: `services/abac-ext-authz/go.mod`

**Context:** This server implements the Envoy gRPC ext-authz proto. It reads three headers (`x-agent-role`, `x-agent-tier`, `x-agent-model`) and checks a policy table loaded from the `ABAC_POLICIES` env var. The policy table format is: `role:tier=model1|model2,role:tier=model3`. Use the existing `grpc-ext-authz` server at `/Users/alexly-solo/Desktop/solo/solo-github/grpc-ext-authz/main.go` as the reference for gRPC boilerplate and response construction.

- [ ] **Step 1: Write the ABAC policy parsing test**

Create `services/abac-ext-authz/main_test.go`:

```go
package main

import (
	"os"
	"testing"
)

func TestParsePolicies(t *testing.T) {
	os.Setenv("ABAC_POLICIES", "enrollment-advisor:standard=gpt-4o-mini,analytics-agent:premium=gpt-4o|gpt-4o-mini")
	defer os.Unsetenv("ABAC_POLICIES")

	initPolicies()

	tests := []struct {
		key      string
		expected []string
	}{
		{"enrollment-advisor:standard", []string{"gpt-4o-mini"}},
		{"analytics-agent:premium", []string{"gpt-4o", "gpt-4o-mini"}},
	}

	for _, tt := range tests {
		models, ok := policies[tt.key]
		if !ok {
			t.Errorf("policy key %q not found", tt.key)
			continue
		}
		if len(models) != len(tt.expected) {
			t.Errorf("key %q: got %d models, want %d", tt.key, len(models), len(tt.expected))
			continue
		}
		for i, m := range models {
			if m != tt.expected[i] {
				t.Errorf("key %q model[%d]: got %q, want %q", tt.key, i, m, tt.expected[i])
			}
		}
	}
}

func TestParsePoliciesDefault(t *testing.T) {
	os.Unsetenv("ABAC_POLICIES")
	initPolicies()

	if _, ok := policies["enrollment-advisor:standard"]; !ok {
		t.Error("default policy for enrollment-advisor:standard not found")
	}
	if _, ok := policies["analytics-agent:premium"]; !ok {
		t.Error("default policy for analytics-agent:premium not found")
	}
}
```

- [ ] **Step 2: Write the ABAC check logic test**

Append to `services/abac-ext-authz/main_test.go`:

```go
func TestCheckABAC(t *testing.T) {
	os.Setenv("ABAC_POLICIES", "enrollment-advisor:standard=gpt-4o-mini,analytics-agent:premium=gpt-4o|gpt-4o-mini")
	defer os.Unsetenv("ABAC_POLICIES")
	initPolicies()

	tests := []struct {
		name    string
		headers map[string]string
		allowed bool
		reason  string
	}{
		{
			name:    "enrollment-advisor allowed for gpt-4o-mini",
			headers: map[string]string{"x-agent-role": "enrollment-advisor", "x-agent-tier": "standard", "x-agent-model": "gpt-4o-mini"},
			allowed: true,
		},
		{
			name:    "enrollment-advisor denied for gpt-4o",
			headers: map[string]string{"x-agent-role": "enrollment-advisor", "x-agent-tier": "standard", "x-agent-model": "gpt-4o"},
			allowed: false,
		},
		{
			name:    "analytics-agent allowed for gpt-4o",
			headers: map[string]string{"x-agent-role": "analytics-agent", "x-agent-tier": "premium", "x-agent-model": "gpt-4o"},
			allowed: true,
		},
		{
			name:    "analytics-agent allowed for gpt-4o-mini",
			headers: map[string]string{"x-agent-role": "analytics-agent", "x-agent-tier": "premium", "x-agent-model": "gpt-4o-mini"},
			allowed: true,
		},
		{
			name:    "missing role header",
			headers: map[string]string{"x-agent-tier": "standard", "x-agent-model": "gpt-4o-mini"},
			allowed: false,
		},
		{
			name:    "missing tier header",
			headers: map[string]string{"x-agent-role": "enrollment-advisor", "x-agent-model": "gpt-4o-mini"},
			allowed: false,
		},
		{
			name:    "missing model header",
			headers: map[string]string{"x-agent-role": "enrollment-advisor", "x-agent-tier": "standard"},
			allowed: false,
		},
		{
			name:    "unknown role",
			headers: map[string]string{"x-agent-role": "unauthorized-agent", "x-agent-tier": "standard", "x-agent-model": "gpt-4o-mini"},
			allowed: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			allowed, reason, _ := checkABAC(tt.headers)
			if allowed != tt.allowed {
				t.Errorf("got allowed=%v, want %v (reason: %s)", allowed, tt.allowed, reason)
			}
		})
	}
}
```

- [ ] **Step 3: Write `main.go` — policy parsing, ABAC check, and gRPC server**

Create `services/abac-ext-authz/main.go`:

```go
package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"os"
	"strings"

	corev3 "github.com/envoyproxy/go-control-plane/envoy/config/core/v3"
	authv3 "github.com/envoyproxy/go-control-plane/envoy/service/auth/v3"
	typev3 "github.com/envoyproxy/go-control-plane/envoy/type/v3"
	"google.golang.org/genproto/googleapis/rpc/status"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
)

// policies maps "role:tier" to a list of allowed model names.
var policies map[string][]string

func initPolicies() {
	policies = make(map[string][]string)
	raw := os.Getenv("ABAC_POLICIES")
	if raw == "" {
		// Defaults for the enrollment-agent demo
		policies["enrollment-advisor:standard"] = []string{"gpt-4o-mini"}
		policies["analytics-agent:premium"] = []string{"gpt-4o", "gpt-4o-mini"}
		return
	}
	for _, entry := range strings.Split(raw, ",") {
		parts := strings.SplitN(entry, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.TrimSpace(parts[0])
		models := strings.Split(parts[1], "|")
		for i := range models {
			models[i] = strings.TrimSpace(models[i])
		}
		policies[key] = models
	}
}

func checkABAC(headers map[string]string) (bool, string, map[string]string) {
	role := headers["x-agent-role"]
	tier := headers["x-agent-tier"]
	model := headers["x-agent-model"]

	if role == "" {
		return false, "missing required header: x-agent-role", nil
	}
	if tier == "" {
		return false, "missing required header: x-agent-tier", nil
	}
	if model == "" {
		return false, "missing required header: x-agent-model", nil
	}

	key := role + ":" + tier
	allowed, exists := policies[key]
	if !exists {
		return false, fmt.Sprintf("no ABAC policy for agent %q (%s)", role, tier), nil
	}

	for _, m := range allowed {
		if m == model {
			reason := fmt.Sprintf("agent %q (%s) authorized for model %s", role, tier, model)
			extra := map[string]string{
				"x-abac-decision": "allowed",
				"x-abac-agent":    role,
				"x-abac-reason":   reason,
			}
			return true, reason, extra
		}
	}

	return false, fmt.Sprintf("agent %q (%s) not authorized for model %q (allowed: %s)", role, tier, model, strings.Join(allowed, ", ")), nil
}

// --- gRPC server ---

type extAuthzServer struct{}

func (s *extAuthzServer) Check(ctx context.Context, req *authv3.CheckRequest) (*authv3.CheckResponse, error) {
	httpReq := req.GetAttributes().GetRequest().GetHttp()
	headers := httpReq.GetHeaders()
	path := httpReq.GetPath()
	method := httpReq.GetMethod()

	log.Printf("[abac-ext-authz] %s %s | role=%s tier=%s model=%s",
		method, path,
		headers["x-agent-role"], headers["x-agent-tier"], headers["x-agent-model"])

	allowed, reason, extraHeaders := checkABAC(headers)

	if allowed {
		log.Printf("[abac-ext-authz] ALLOWED: %s", reason)
		okHeaders := []*corev3.HeaderValueOption{}
		for k, v := range extraHeaders {
			okHeaders = append(okHeaders, &corev3.HeaderValueOption{
				Header: &corev3.HeaderValue{Key: k, Value: v},
			})
		}
		return &authv3.CheckResponse{
			Status: &status.Status{Code: int32(codes.OK)},
			HttpResponse: &authv3.CheckResponse_OkResponse{
				OkResponse: &authv3.OkHttpResponse{
					Headers: okHeaders,
				},
			},
		}, nil
	}

	log.Printf("[abac-ext-authz] DENIED: %s", reason)
	return &authv3.CheckResponse{
		Status: &status.Status{Code: int32(codes.PermissionDenied)},
		HttpResponse: &authv3.CheckResponse_DeniedResponse{
			DeniedResponse: &authv3.DeniedHttpResponse{
				Status: &typev3.HttpStatus{
					Code: typev3.StatusCode_Forbidden,
				},
				Body: fmt.Sprintf("denied by ABAC: %s", reason),
				Headers: []*corev3.HeaderValueOption{
					{
						Header: &corev3.HeaderValue{
							Key:   "x-abac-decision",
							Value: "denied",
						},
					},
				},
			},
		},
	}, nil
}

func main() {
	port := os.Getenv("PORT")
	if port == "" {
		port = "9000"
	}

	initPolicies()

	log.Printf("Loaded ABAC policies:")
	for key, models := range policies {
		log.Printf("  %s -> [%s]", key, strings.Join(models, ", "))
	}

	lis, err := net.Listen("tcp", ":"+port)
	if err != nil {
		log.Fatalf("Failed to listen on port %s: %v", port, err)
	}

	s := grpc.NewServer()
	authv3.RegisterAuthorizationServer(s, &extAuthzServer{})

	log.Printf("ABAC ext-authz server listening on :%s", port)
	if err := s.Serve(lis); err != nil {
		log.Fatalf("Failed to serve: %v", err)
	}
}
```

- [ ] **Step 4: Create `go.mod`**

Create `services/abac-ext-authz/go.mod`. Copy the module definition and dependencies from the reference server at `/Users/alexly-solo/Desktop/solo/solo-github/grpc-ext-authz/go.mod`, changing only the module name:

```
module github.com/alexly-solo/abac-ext-authz

go 1.25.6

require (
	github.com/envoyproxy/go-control-plane/envoy v1.37.0
	google.golang.org/genproto/googleapis/rpc v0.0.0-20260414002931-afd174a4e478
	google.golang.org/grpc v1.80.0
)

require (
	github.com/cncf/xds/go v0.0.0-20251210132809-ee656c7534f5 // indirect
	github.com/envoyproxy/protoc-gen-validate v1.3.0 // indirect
	github.com/planetscale/vtprotobuf v0.6.1-0.20240319094008-0393e58bdf10 // indirect
	golang.org/x/net v0.49.0 // indirect
	golang.org/x/sys v0.40.0 // indirect
	golang.org/x/text v0.33.0 // indirect
	google.golang.org/protobuf v1.36.11 // indirect
)
```

Copy `go.sum` from `/Users/alexly-solo/Desktop/solo/solo-github/grpc-ext-authz/go.sum` as-is (identical dependencies).

- [ ] **Step 5: Run tests**

```bash
cd services/abac-ext-authz && go test -v ./...
```

Expected: All tests pass (TestParsePolicies, TestParsePoliciesDefault, TestCheckABAC — 8 subtests).

- [ ] **Step 6: Commit**

```bash
git add services/abac-ext-authz/main.go services/abac-ext-authz/main_test.go services/abac-ext-authz/go.mod services/abac-ext-authz/go.sum
git commit -m "feat: add ABAC gRPC ext-authz server with policy engine and tests"
```

---

### Task 2: Docker Build Infrastructure

**Files:**
- Create: `services/abac-ext-authz/Dockerfile`
- Create: `services/abac-ext-authz/build-and-push.sh`

**Context:** Same multi-stage distroless pattern as the reference server at `/Users/alexly-solo/Desktop/solo/solo-github/grpc-ext-authz/Dockerfile`. Uses `ly-builder` buildx builder for multi-arch (amd64/arm64).

- [ ] **Step 1: Create Dockerfile**

Create `services/abac-ext-authz/Dockerfile`:

```dockerfile
FROM --platform=$BUILDPLATFORM golang:1.25-alpine AS builder
ARG TARGETARCH
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY main.go .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=$TARGETARCH go build -o /abac-ext-authz .

FROM gcr.io/distroless/static-debian12
COPY --from=builder /abac-ext-authz /abac-ext-authz
EXPOSE 9000
ENTRYPOINT ["/abac-ext-authz"]
```

- [ ] **Step 2: Create build-and-push.sh**

Create `services/abac-ext-authz/build-and-push.sh`:

```bash
#!/bin/bash
set -e

# Build and push the ABAC ext-authz server to DockerHub.
# Usage: ./build-and-push.sh [version]
# Example: ./build-and-push.sh 0.0.2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

IMAGE_NAME="ably7/abac-ext-authz"
DEFAULT_VERSION="0.0.1"

if [ -n "$1" ]; then
  VERSION="$1"
else
  VERSION="$DEFAULT_VERSION"
fi

IMAGE="${IMAGE_NAME}:${VERSION}"
echo "=== Building and pushing ${IMAGE} ==="

# Build and push multi-arch image
docker buildx build --builder ly-builder \
  --platform linux/amd64,linux/arm64 \
  -t "$IMAGE" \
  -t "${IMAGE_NAME}:latest" \
  --push .

echo ""
echo "=== Pushed ${IMAGE} ==="
echo "=== Pushed ${IMAGE_NAME}:latest ==="
```

- [ ] **Step 3: Make build script executable**

```bash
chmod +x services/abac-ext-authz/build-and-push.sh
```

- [ ] **Step 4: Commit**

```bash
git add services/abac-ext-authz/Dockerfile services/abac-ext-authz/build-and-push.sh
git commit -m "feat: add Dockerfile and build script for ABAC ext-authz"
```

---

### Task 3: Kubernetes Resources

**Files:**
- Create: `k8s/gateway/abac-ext-authz.yaml`

**Context:** Three resources in one file: Deployment, Service, and EnterpriseAgentgatewayPolicy. The policy targets the `wgu-enrollment` HTTPRoute (see `k8s/gateway/route.yaml:4`). The ext-authz service uses `appProtocol: kubernetes.io/h2c` for gRPC. All resources go in `agentgateway-system` namespace.

- [ ] **Step 1: Create the K8s manifest**

Create `k8s/gateway/abac-ext-authz.yaml`:

```yaml
# ABAC ext-authz server for agent-to-LLM access control.
# NOT applied by install.sh — this is an opt-in demo feature.
# Apply manually: kubectl apply -f k8s/gateway/abac-ext-authz.yaml
# Workshop: workshop-byo-abac-ext-authz.md
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
---
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
---
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
```

- [ ] **Step 2: Commit**

```bash
git add k8s/gateway/abac-ext-authz.yaml
git commit -m "feat: add K8s resources for ABAC ext-authz (deployment, service, policy)"
```

---

### Task 4: Modify `gateway.py` — Add `extra_headers` Support

**Files:**
- Modify: `demo-ui/utils/gateway.py:14-39`

**Context:** Add an optional `extra_headers` parameter to `chat_completion()`. When provided, these headers are merged into the request. No change to existing callers that don't pass the parameter.

- [ ] **Step 1: Update `chat_completion()` function**

In `demo-ui/utils/gateway.py`, change the function signature and header construction. The current function at lines 14-39 becomes:

```python
def chat_completion(
    messages: list[dict],
    model: str = "gpt-4o-mini",
    tools: list[dict] | None = None,
    path: str = "/openai",
    extra_headers: dict | None = None,
) -> tuple[int, dict]:
    """Send a chat completion request through the agent gateway.

    Returns (status_code, parsed_json_body).
    """
    url = f"{get_gateway_url()}{path}"
    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools

    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        try:
            body = resp.json()
        except (json.JSONDecodeError, TypeError):
            body = {"error": resp.text}
        return resp.status_code, body
    except requests.RequestException as exc:
        return 0, {"error": str(exc)}
```

The only changes from the original:
1. Added `extra_headers: dict | None = None` parameter
2. Added `if extra_headers: headers.update(extra_headers)` after the base headers dict

- [ ] **Step 2: Commit**

```bash
git add demo-ui/utils/gateway.py
git commit -m "feat: add extra_headers parameter to chat_completion()"
```

---

### Task 5: Homepage ABAC Sidebar Integration

**Files:**
- Modify: `demo-ui/Homepage.py:34-52` (sidebar section) and `demo-ui/Homepage.py:139-141` (chat_completion calls)

**Context:** Add an ABAC simulation section to the sidebar, below the student selector. When enabled, role/tier/model dropdowns appear, and the `chat_completion()` calls pass the selected values as extra headers and model. Add a reset-to-defaults button. Display the policy matrix when enabled. The existing chat logic, tool calling, and error handling are untouched.

- [ ] **Step 1: Add ABAC session state defaults and sidebar section**

In `demo-ui/Homepage.py`, after the student selector block (line 49, after the `st.selectbox` for student), add the ABAC sidebar section. Insert before the line `SELECTED_STUDENT = st.session_state["selected_student"]` (line 51):

```python
    # --- ABAC Simulation ---
    st.divider()
    st.markdown("**Agent Identity (ABAC)**")

    abac_enabled = st.checkbox("Enable ABAC Simulation", key="abac_enabled")

    if abac_enabled:
        abac_role = st.selectbox(
            "Agent Role",
            ["enrollment-advisor", "analytics-agent", "unauthorized-agent"],
            key="abac_role",
        )
        abac_tier = st.selectbox(
            "Agent Tier",
            ["standard", "premium"],
            key="abac_tier",
        )
        abac_model = st.selectbox(
            "LLM Model",
            ["gpt-4o-mini", "gpt-4o"],
            key="abac_model",
        )

        if st.button("Reset to defaults"):
            st.session_state["abac_enabled"] = False
            st.session_state["abac_role"] = "enrollment-advisor"
            st.session_state["abac_tier"] = "standard"
            st.session_state["abac_model"] = "gpt-4o-mini"
            st.rerun()

        st.caption("**Policy Matrix**")
        st.markdown(
            "| Role | Tier | 4o-mini | 4o |\n"
            "|---|---|---|---|\n"
            "| enrollment-advisor | standard | :material/check: | :material/close: |\n"
            "| analytics-agent | premium | :material/check: | :material/check: |\n"
            "| unauthorized-agent | any | :material/close: | :material/close: |"
        )
```

This block goes inside the existing `with st.sidebar:` block that starts at line 41.

- [ ] **Step 2: Build ABAC headers helper**

After the ABAC sidebar section and after `SELECTED_STUDENT` / `SYSTEM_PROMPT` are set (around line 52), add a helper to build the ABAC state:

```python
# --- ABAC state ---
def _get_abac_config():
    """Return (model, extra_headers) based on ABAC toggle state."""
    if st.session_state.get("abac_enabled"):
        role = st.session_state.get("abac_role", "enrollment-advisor")
        tier = st.session_state.get("abac_tier", "standard")
        model = st.session_state.get("abac_model", "gpt-4o-mini")
        extra_headers = {
            "x-agent-role": role,
            "x-agent-tier": tier,
            "x-agent-model": model,
        }
        return model, extra_headers
    return "gpt-4o-mini", None
```

- [ ] **Step 3: Update the `chat_completion()` calls to use ABAC config**

There are two calls to `chat_completion()` in Homepage.py:

1. First call at line 140 (inside `with st.spinner("Thinking...")`):

Change from:
```python
            status, body = chat_completion(api_messages, tools=TOOLS)
```
To:
```python
            _model, _extra = _get_abac_config()
            status, body = chat_completion(api_messages, model=_model, tools=TOOLS, extra_headers=_extra)
```

2. Second call at line 155 (inside `with st.spinner("Analyzing your data...")`):

Change from:
```python
                    status2, body2 = chat_completion(api_messages, tools=TOOLS)
```
To:
```python
                    status2, body2 = chat_completion(api_messages, model=_model, tools=TOOLS, extra_headers=_extra)
```

Note: `_model` and `_extra` are already set from the first call above, so they can be reused for the second call in the same request cycle.

- [ ] **Step 4: Commit**

```bash
git add demo-ui/Homepage.py
git commit -m "feat: add ABAC simulation toggle to Homepage sidebar"
```

---

### Task 6: Update `cleanup.sh`

**Files:**
- Modify: `cleanup.sh:23-27`

**Context:** The ABAC resources (deployment, service, policy) are in `agentgateway-system`. The cleanup script already deletes `k8s/gateway/` resources with `kubectl delete -f k8s/gateway/` at line 27, which will automatically pick up the new `abac-ext-authz.yaml` file. However, if someone applied the resources directly (without the file), we should also ensure they're cleaned up. The existing line 43 already does `kubectl delete enterpriseagentgatewaypolicy --all -n agentgateway-system` which covers the policy.

No changes needed — the existing cleanup script already handles this:
- Line 27: `kubectl delete -f k8s/gateway/ --context $KUBECONTEXT_CLUSTER1 --ignore-not-found` deletes all resources defined in `k8s/gateway/`, including the new `abac-ext-authz.yaml`
- Line 43: `kubectl delete enterpriseagentgatewaypolicy --all -n agentgateway-system` catches any stray policies

- [ ] **Step 1: Verify no cleanup.sh changes needed**

Read `cleanup.sh` lines 25-27 and 43 to confirm the existing delete commands cover the ABAC resources. No edit needed.

- [ ] **Step 2: Skip commit (no changes)**

No changes to commit.

---

### Task 7: Workshop Document

**Files:**
- Create: `workshop-byo-abac-ext-authz.md`

**Context:** Step-by-step workshop document in the project root. Mirrors the structure of the existing workshop lab at `/Users/alexly-solo/Desktop/solo/solo-github/fe-enterprise-agentgateway-workshop/llm-byo-grpc-ext-authz.md`. Uses the existing `wgu-enrollment` HTTPRoute and `agentgateway-proxy` gateway from the enrollment-agent install. All `kubectl` commands use no `--context` flag (assumes current context is cluster1).

- [ ] **Step 1: Write the workshop document**

Create `workshop-byo-abac-ext-authz.md` in the project root with the following content:

```markdown
# BYO ABAC gRPC External Authorization (ext-authz)

## Pre-requisites
This lab assumes you have completed the enrollment-agent install (`./install.sh`) and the chatbot is working at `http://enroll.glootest.com`.

## Lab Objectives
- Deploy a custom ABAC gRPC ext-authz server to the cluster
- Create an `EnterpriseAgentgatewayPolicy` to enforce attribute-based access control on the LLM route
- Validate that requests without agent identity are denied with 403
- Validate that different agent personas get different access levels based on role, tier, and model
- Observe ABAC decisions in the ext-authz server logs

## About ABAC External Auth

The existing enrollment-agent uses Istio AuthorizationPolicies for **identity-based** access control — binary allow/deny based on service account. ABAC (Attribute-Based Access Control) is richer: it combines multiple attributes of the caller to make fine-grained decisions.

This lab deploys a custom ext-authz server that checks three attributes on every request to the LLM:

| Attribute | Header | Description |
|-----------|--------|-------------|
| Role | `x-agent-role` | The agent's purpose (enrollment-advisor, analytics-agent) |
| Tier | `x-agent-tier` | The agent's access level (standard, premium) |
| Model | `x-agent-model` | The LLM model being requested (gpt-4o-mini, gpt-4o) |

The ABAC policy table:

| Role | Tier | gpt-4o-mini | gpt-4o |
|------|------|-------------|--------|
| enrollment-advisor | standard | ALLOW | DENY |
| analytics-agent | premium | ALLOW | ALLOW |
| (unknown) | any | DENY | DENY |

```
Client → Agentgateway Proxy → ABAC ext-authz server → Allow/Deny
                              ↓ (if allowed)
                         OpenAI Backend (LLM)
```

## Deploy the ABAC ext-authz server

Deploy the Deployment and Service for the ABAC ext-authz server:

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

Wait for the pod to be ready:
```bash
kubectl rollout status deployment/abac-ext-authz -n agentgateway-system --timeout=60s
```

Create the Service:
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

Send a test request to confirm the OpenAI route works before applying the ABAC policy:
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

Create an `EnterpriseAgentgatewayPolicy` that applies ABAC ext-authz to the `wgu-enrollment` HTTPRoute:

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

Send a request without any agent headers. The ABAC server denies it because the required attributes are missing:

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
x-abac-decision: denied

denied by ABAC: missing required header: x-agent-role
```

## Test: enrollment-advisor + gpt-4o-mini → allowed

The enrollment-advisor agent with standard tier is authorized for gpt-4o-mini:

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

You should get a 200 response with `x-abac-decision: allowed` and `x-abac-agent: enrollment-advisor` headers.

## Test: enrollment-advisor + gpt-4o → denied

The same enrollment-advisor tries to use the premium gpt-4o model — denied:

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
x-abac-decision: denied

denied by ABAC: agent "enrollment-advisor" (standard) not authorized for model "gpt-4o" (allowed: gpt-4o-mini)
```

## Test: analytics-agent + gpt-4o → allowed

The analytics-agent with premium tier can use gpt-4o:

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

You should get a 200 response with `x-abac-decision: allowed` and `x-abac-agent: analytics-agent` headers.

## View ext-authz logs

Check the ABAC server logs to see the decisions:
```bash
kubectl logs -n agentgateway-system -l app=abac-ext-authz --tail=20
```

You should see entries like:
```
[abac-ext-authz] POST /openai | role=enrollment-advisor tier=standard model=gpt-4o-mini
[abac-ext-authz] ALLOWED: agent "enrollment-advisor" (standard) authorized for model gpt-4o-mini
[abac-ext-authz] POST /openai | role=enrollment-advisor tier=standard model=gpt-4o
[abac-ext-authz] DENIED: agent "enrollment-advisor" (standard) not authorized for model "gpt-4o" (allowed: gpt-4o-mini)
```

## Demo UI integration

The enrollment chatbot Homepage includes an ABAC simulation toggle. In the sidebar:

1. Check **"Enable ABAC Simulation"**
2. Select an **Agent Role** and **Tier** from the dropdowns
3. Select an **LLM Model**
4. Chat normally — the chatbot sends the selected agent identity headers with each LLM request

Try these scenarios through the chatbot:
- `enrollment-advisor` / `standard` / `gpt-4o-mini` — chat works normally
- `enrollment-advisor` / `standard` / `gpt-4o` — blocked with ABAC deny message
- `analytics-agent` / `premium` / `gpt-4o` — chat works with the premium model
- `unauthorized-agent` / any tier / any model — blocked

The policy matrix is displayed in the sidebar for reference.

## Cleanup

```bash
kubectl delete enterpriseagentgatewaypolicy -n agentgateway-system abac-ext-auth-policy
kubectl delete deployment -n agentgateway-system abac-ext-authz
kubectl delete service -n agentgateway-system abac-ext-authz
```
```

- [ ] **Step 2: Commit**

```bash
git add workshop-byo-abac-ext-authz.md
git commit -m "docs: add BYO ABAC ext-authz workshop document"
```

---

### Task 8: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Context:** Add the ABAC ext-authz service to the project structure tree and mention it in the relevant sections. Keep it brief — this is a reference entry, not documentation.

- [ ] **Step 1: Add to project structure**

In `CLAUDE.md`, in the project structure tree under `├── services/`, add the new service:

```
│   ├── abac-ext-authz/         # ABAC gRPC ext-authz server (Go) — BYO ext-auth demo
```

Add the workshop doc to the root-level entries:

```
├── workshop-byo-abac-ext-authz.md  # ABAC ext-authz workshop (BYO ext-auth demo)
```

- [ ] **Step 2: Add to the K8s gateway section**

In the project structure tree under `├── k8s/` > `│   ├── gateway/`, add:

```
│   │   ├── abac-ext-authz.yaml  # ABAC ext-authz (Deployment, Service, Policy) — opt-in
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add ABAC ext-authz to CLAUDE.md project structure"
```

---

### Task 9: Build Docker Image and Verify

**Files:** None (build and deploy steps)

**Context:** Build the ABAC ext-authz Docker image and push to DockerHub. Then rebuild the chatbot image to pick up the Homepage and gateway.py changes. This task requires Docker buildx with the `ly-builder` builder configured.

- [ ] **Step 1: Build and push the ABAC ext-authz image**

```bash
cd services/abac-ext-authz && ./build-and-push.sh
```

Expected: Image `ably7/abac-ext-authz:0.0.1` and `ably7/abac-ext-authz:latest` pushed to DockerHub.

- [ ] **Step 2: Rebuild the chatbot image**

```bash
cd /Users/alexly-solo/Desktop/solo/solo-github/enrollment-agent && ./build-and-redeploy.sh
```

Expected: New chatbot image built and deployed with the ABAC sidebar changes.

- [ ] **Step 3: Deploy the ABAC ext-authz to the cluster**

```bash
kubectl apply -f k8s/gateway/abac-ext-authz.yaml
kubectl rollout status deployment/abac-ext-authz -n agentgateway-system --timeout=60s
```

- [ ] **Step 4: Verify with curl**

Run the workshop test cases:

```bash
export GATEWAY_IP=$(kubectl get svc -n agentgateway-system --selector=gateway.networking.k8s.io/gateway-name=agentgateway-proxy -o jsonpath='{.items[*].status.loadBalancer.ingress[0].ip}{.items[*].status.loadBalancer.ingress[0].hostname}')

# Should be denied (no agent headers)
curl -i "$GATEWAY_IP:8080/openai" \
  -H "content-type: application/json" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'

# Should be allowed
curl -i "$GATEWAY_IP:8080/openai" \
  -H "content-type: application/json" \
  -H "x-agent-role: enrollment-advisor" \
  -H "x-agent-tier: standard" \
  -H "x-agent-model: gpt-4o-mini" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hello"}]}'

# Should be denied (wrong model for tier)
curl -i "$GATEWAY_IP:8080/openai" \
  -H "content-type: application/json" \
  -H "x-agent-role: enrollment-advisor" \
  -H "x-agent-tier: standard" \
  -H "x-agent-model: gpt-4o" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"hello"}]}'
```

- [ ] **Step 5: Verify the chatbot UI**

Open `http://enroll.glootest.com` and:
1. Enable ABAC Simulation in the sidebar
2. With enrollment-advisor / standard / gpt-4o-mini — send a chat message, verify it works
3. Switch to gpt-4o — send a chat message, verify 403 error appears
4. Switch to analytics-agent / premium / gpt-4o — send a chat message, verify it works
5. Switch to unauthorized-agent — send a chat message, verify 403 error appears
6. Click "Reset to defaults" — verify everything snaps back

- [ ] **Step 6: Check ext-authz logs**

```bash
kubectl logs -n agentgateway-system -l app=abac-ext-authz --tail=20
```

Verify ALLOWED and DENIED entries match the test scenarios.
