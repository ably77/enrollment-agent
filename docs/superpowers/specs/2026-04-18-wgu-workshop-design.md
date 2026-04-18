# WGU Demo Workshop — Design Spec

## Overview

A linear, self-contained workshop document (`workshop.md`) that the WGU team can follow start-to-finish to set up, run, and test a full Solo.io demo covering Istio Ambient Mesh, Enterprise Agentgateway, security/governance, and an end-to-end AI enrollment scenario.

**Target audiences:**
- Platform/infra engineers (know Kubernetes, IAM, VPC networking, Terraform)
- Architecture/leadership (care about governance, compliance, TCO, outcomes)

**Delivery format:** Single markdown file at `/Users/alexly-solo/Desktop/customer/wgu/workshop.md` with step-by-step commands, verification steps, and business context callouts.

**Runnable on:** Two local Colima clusters (primary dev/test path), with AWS/EKS annotations throughout for production deployment.

---

## Section 1: Prerequisites & Environment Setup

### Purpose
Get two Kubernetes clusters running with all necessary tools and credentials.

### Content

**Local dev path (primary):**
- Two Colima clusters with named Kubernetes contexts (`cluster1`, `cluster2`)
- Specific `colima start` commands with appropriate CPU/memory/k8s-version flags
- Kubeconfig setup with named contexts

**AWS production path (noted via callouts):**
- EKS cluster requirements: us-east-1 (primary), us-west-2 (secondary)
- AWS-specific annotations (LoadBalancer configs, IRSA for IAM roles) shown as `> **AWS/EKS:** ...` callout boxes where configs differ from local

**CLI tools:**
- `kubectl`, `helm`, `istioctl`, `meshctl`, `jq`
- Version requirements for each

**Credentials:**
- API key for OpenAI or Anthropic (workshop supports either)
- Namespace creation for demo workloads

**Verification:**
- Commands to confirm cluster connectivity, tool versions, and context naming

### Design Decisions
- Workshop assumes clusters already exist on the AWS path (WGU provisions their own). We provide requirements but not Terraform/IaC for cluster creation.
- Colima is the primary path so anyone can test locally. AWS annotations ensure smooth transition to EKS.
- Where configs differ (e.g., Service type ClusterIP vs LoadBalancer), the main flow shows the local version with an AWS callout showing the variant.

---

## Section 2: Istio Ambient Mesh

### Purpose
Install ambient mesh on both clusters, deploy WGU-themed workloads, demonstrate mTLS, cross-cluster connectivity, and zero-trust authorization.

### Content (in order)

1. **Install Solo Istio ambient mesh on both clusters**
   - Helm charts: `istio-base`, `istiod`, `ztunnel`, `istio-cni`
   - Adapted from existing multi-cluster ambient workshop install labs
   - AWS callout: EKS-specific CNI considerations, node security groups

2. **Deploy WGU-themed demo workloads**
   - Data product API service (student academic data)
   - Graph DB mock service
   - Deployed early so mesh enrollment steps feel relevant to WGU's story (not generic Bookinfo)

3. **Enroll workloads in the mesh**
   - Label namespaces with `istio.io/dataplane-mode=ambient`
   - Show pods going from unencrypted to mTLS with zero restarts, no sidecars
   - Verification: confirm ztunnel is proxying traffic

4. **Demonstrate mTLS**
   - Exec into a pod, show traffic is encrypted
   - `istioctl ztunnel-config` to verify HBONE tunnels
   - Business callout: "This replaces VPC peering, PrivateLink, and manual certificate rotation"

5. **Multi-cluster connectivity**
   - Link the two clusters (Colima locally, EKS on AWS)
   - Cross-cluster service discovery via `mesh.internal` DNS
   - Verification: call a service on cluster2 from cluster1

6. **AuthorizationPolicy**
   - Apply deny-all baseline
   - Explicitly allow only the paths needed for the enrollment scenario:
     - Data product API can talk to graph DB
     - Nothing else can reach student data
   - Business callout: "This is your FERPA boundary — only explicitly authorized services can reach student data"

7. **Waypoint for L7 policy**
   - Deploy a waypoint proxy for the data product API namespace
   - Enable L7 traffic management (header-based routing, retries)

### Source Material
Adapted from: `solo-enterprise-for-istio-workshops/istio-ambient-multicluster/` labs, with WGU-specific workloads replacing Bookinfo.

---

## Section 3: Agent Gateway & Agent Mesh

### Purpose
Install the agent gateway, configure LLM routing with guardrails and rate limiting, show observability, and demonstrate that agent traffic inherits mesh security.

### Content (in order)

1. **Install Enterprise Agentgateway**
   - Helm chart deployment into the mesh-enrolled cluster
   - Gateway API CRDs, agentgateway proxy, Gloo UI
   - Adapted from existing agent gateway workshop install lab

2. **Configure an LLM backend**
   - Route to OpenAI or Anthropic (workshop supports either)
   - Create: API key secret, Backend resource, HTTPRoute
   - Verification: simple curl chat completion through the gateway

3. **Add guardrails**
   - Built-in prompt guards: PII detection (critical for FERPA — student SSNs, IDs), prompt injection protection, harmful content filtering
   - Test: send a request containing fake PII, show it gets blocked
   - Business callout: "PII filtering means a misconfigured agent can't accidentally exfiltrate student data to an LLM provider"

4. **Token-level rate limiting**
   - Per-consumer token budgets
   - Demonstrate a burst of requests hitting the limit
   - Business callout: "This is your AI cost governance — per-team or per-agent budgets enforced at the gateway"

5. **Observability**
   - Gloo UI: request logs, token counts, latency metrics
   - Every LLM call is auditable: who called what model, tokens consumed, guardrails fired
   - Business callout: "Every LLM call is logged with token counts and latency — this is your AI cost governance and FERPA/PCI-DSS audit trail"

6. **Agent mesh integration**
   - The key bridge between sections 2 and 3
   - Show the agent gateway sits inside the ambient mesh
   - All agent-to-LLM and agent-to-service traffic inherits mTLS, AuthorizationPolicy, and observability from the mesh
   - No additional security config needed — one unified governance plane

### Source Material
Adapted from: `fe-enterprise-agentgateway-workshop/` labs for routing, security, rate limiting, guardrails, and observability.

---

## Section 4: Security & Governance (Deep Dive)

### Purpose
Show the unified governance posture across mesh and gateway, demonstrate compliance-relevant audit capabilities, and intentionally violate policies to prove enforcement.

### Content (in order)

1. **Centralized policy view**
   - Walk through policies from sections 2 and 3 holistically
   - AuthorizationPolicy (mesh) + guardrails (gateway) + rate limits = unified governance
   - Gloo UI: full topology visualization — what's talking to what, what's allowed, what's blocked
   - Business callout: "This single policy view replaces CloudTrail + IAM policy analysis + VPC flow logs + custom authorization middleware"

2. **RBAC for service-to-service**
   - Expand AuthorizationPolicy to principal-based access control
   - Only enrollment chatbot's service account can reach the agent gateway
   - Only data product API's service account can reach the graph DB
   - Business callout: "Student data access is identity-scoped, not network-scoped — this is your FERPA boundary"

3. **Audit logging and compliance reporting**
   - Mesh access logs: who called what, when, mTLS identity verified
   - Gateway logs: which model, what prompt, what guardrails fired
   - Together: complete audit trail
   - Business callout: "This is what you'd show an auditor for FERPA or PCI-DSS — cryptographic identity at every hop"

4. **Policy enforcement demonstration**
   - Intentionally violate three policies:
     - Call data product API from unauthorized service → blocked
     - Send PII through agent gateway → blocked
     - Exceed rate limit → blocked
   - Show clear error responses and audit log entries for each
   - Business callout: "An auditor can see the full request chain from student chatbot to student data — with cryptographic identity at every hop"

5. **Forward reference to section 6**
   - Brief setup: "Next we'll deploy the full enrollment scenario. In the final section, we'll show what building this same governance posture looks like with native AWS services."

---

## Section 5: The Home Run — End-to-End Enrollment Scenario

### Purpose
Deploy a realistic AI enrollment chatbot scenario and trace a student request through the entire secured, governed chain.

### Components Deployed

1. **Enrollment Chatbot (Streamlit app)**
   - Forked from existing demo UI patterns (theme, wizard utils, gateway helpers)
   - Single-page chat interface — student types enrollment questions
   - Sends messages to LLM (OpenAI or Anthropic) via the agent gateway
   - System prompt: enrollment advisor with access to a student data tool/function call
   - Sidebar shows real-time observability (request chain, guardrail status, token count)
   - NOT the full 11-page demo app — purpose-built for this scenario

2. **Data Product API**
   - Small Python service deployed in the mesh
   - REST API for student academic data: enrollment status, program, courses completed, GPA, term dates
   - Returns realistic WGU-style data
   - Called via OpenAI-compatible function calling (tool use): the LLM returns a `tool_calls` response requesting student data, the chatbot executes the function call against this API, then sends the result back to the LLM for the final response

3. **Graph DB Mock**
   - Lightweight in-cluster service
   - Data product API calls it for graph-style queries
   - Returns canned responses: student → enrolled_in → program, student → completed → course
   - Represents Neptune without needing an actual graph database
   - Simple enough to run on Colima

### Demo Flow (workshop steps)

1. Deploy all three services into the mesh-enrolled namespace
2. Verify they inherit mTLS and AuthorizationPolicies from section 2
3. Open the Streamlit UI (port-forward or LoadBalancer)
4. Send a message: "What courses do I have left to complete my BS in Computer Science?"
5. Trace the chain:
   - Chatbot → agent gateway (guardrails check, token counting)
   - → LLM (generates response, invokes function call for student data)
   - → data product API (through the mesh, mTLS verified)
   - → graph DB mock
   - → response back up the chain to the chat UI
6. Show observability:
   - Gloo UI: LLM call with token count and latency
   - Mesh: service-to-service calls with mTLS identities
   - Audit log: complete request chain
7. Test governance: send a message containing a fake SSN — guardrail catches it before it reaches the LLM

### Streamlit App Design

**Forked from:** `/Users/alexly-solo/Desktop/solo/solo-github/solo-field-installer/demos/enterprise-agentgateway/demo-ui`

**What gets forked:**
- Dark enterprise theme (`utils/theme.py`)
- Gateway HTTP utilities (`utils/gateway.py`)
- Log parsing and rendering (`utils/logs.py`)
- Display helpers (`utils/display.py`)
- Sidebar config pattern (`utils/sidebar.py`)

**What gets built new:**
- `Homepage.py` — single-page enrollment chatbot
- Chat interface with message history
- System prompt for WGU enrollment advisor persona
- Function calling integration for student data lookup
- Sidebar: real-time request chain visualization, guardrail status, token count
- Kubernetes manifests for in-cluster deployment

**Data shapes (realistic WGU-style):**
```json
{
  "student_id": "WGU-2024-00142",
  "name": "Jordan Rivera",
  "program": "BS Computer Science",
  "enrollment_status": "active",
  "term": "April 2026",
  "courses_completed": 28,
  "courses_remaining": 11,
  "gpa": 3.42,
  "competency_units_earned": 89,
  "competency_units_remaining": 32,
  "courses": [
    {"code": "C949", "name": "Data Structures and Algorithms I", "status": "completed", "grade": "B+"},
    {"code": "C950", "name": "Data Structures and Algorithms II", "status": "in_progress"},
    {"code": "C951", "name": "Introduction to Artificial Intelligence", "status": "not_started"}
  ]
}
```

---

## Section 6: Without Solo — The AWS-Native Alternative

### Purpose
Show what the same enrollment chatbot chain would require using only native AWS services. Documentation only — nothing built or deployed.

### Part 1: Side-by-Side Comparison Table

| Capability | With Solo | Without Solo (AWS Native) | Complexity Delta |
|---|---|---|---|
| Service-to-service mTLS | Ambient mesh — automatic, zero config per service | ACM Private CA + custom certificate distribution + rotation automation | Weeks of setup, ongoing rotation maintenance |
| Cross-cluster service discovery | Mesh linking + `mesh.internal` DNS | VPC Peering + PrivateLink endpoints + Route53 private hosted zones + custom DNS | Per-service endpoint management, VPC CIDR planning |
| Zero-trust authorization | AuthorizationPolicy (declarative YAML) | Security Groups + NACLs + IAM policies per service + custom authorization middleware | N policies per service pair, no unified view |
| LLM gateway routing | Agent Gateway HTTPRoute | API Gateway + custom Lambda authorizers + manual provider integration | Per-provider custom integration |
| PII / prompt injection guardrails | Built-in prompt guards (one policy) | Custom Lambda middleware + Comprehend/Macie integration + manual pipeline | Custom code to build and maintain |
| Token rate limiting | RateLimitConfig (declarative) | API Gateway usage plans + custom DynamoDB-backed token counters | Custom counter logic, no token-level granularity |
| Unified observability | Gloo UI + mesh metrics (single pane) | CloudWatch + CloudTrail + X-Ray + custom correlation across all three | Three systems, manual correlation |
| Audit trail for compliance | Mesh access logs + gateway logs (unified) | CloudTrail + Config Rules + custom aggregation + manual report generation | Manual aggregation, no agent-aware logging |
| Agent-to-service governance | Same mesh policies apply to agents | No native equivalent — entirely custom build | Greenfield custom development |

### Part 2: Narrative Walkthrough

Traces the same enrollment chatbot request path, describing every AWS component needed at each hop:

1. **Student sends message**
   - API Gateway with WAF rules
   - Lambda authorizer checking JWT from Entra/Ping
   - Custom rate limiting via DynamoDB (API Gateway usage plans don't support token-level limits)
   - No equivalent to agent gateway guardrails at this layer

2. **LLM call**
   - Lambda function with IAM role scoped to Bedrock
   - No native guardrail equivalent for prompt injection (Bedrock Guardrails is limited in scope)
   - Custom PII scrubbing via Comprehend before the call
   - No token-level observability without custom instrumentation

3. **Data product API call**
   - Cross-service communication requires VPC endpoint or PrivateLink
   - Security group rules per service pair (no declarative policy language)
   - No mTLS — TLS termination at ALB only, no cryptographic service identity
   - IAM role chaining for authorization (complex, hard to audit)

4. **Graph DB query**
   - Neptune in private subnet, VPC endpoint required
   - Cross-region access requires additional networking (Transit Gateway or peering)
   - No unified audit trail linking the LLM call to the data query

### Part 3: WGU-Specific Pain Points

Each pain point directly references real issues from WGU's environment, with a Solo counterpoint:

1. **Orphaned VPC endpoint that can't be deleted due to IAM policy conflicts**
   - With Solo: no VPC endpoints needed. Mesh handles cross-service connectivity declaratively. Remove a service from the mesh by removing a label — no orphaned infrastructure.

2. **Neptune private graph endpoint required `hashicorp/awscc` provider instead of `hashicorp/aws`**
   - With Solo: graph DB access goes through the mesh like any other service. No special provider, no per-service networking config. One Terraform module for the mesh, standard manifests for services.

3. **Cross-region Lambda-to-Neptune connectivity took weeks to solve**
   - With Solo: multi-cluster mesh linking handles cross-region connectivity. A service in us-east-1 calls a service in us-west-2 the same way it calls a service in the same cluster — mesh routing, automatic mTLS, no VPC peering or Transit Gateway config.

4. **ServiceNow and AWS Control Tower evaluated and found lacking**
   - With Solo: unified governance plane purpose-built for service mesh + AI agent governance. Not a general-purpose IT management tool retrofitted for this use case.

---

## What Gets Built (Implementation Scope)

### Code artifacts

1. **Streamlit enrollment chatbot app**
   - Forked from existing demo UI (theme, utils, patterns)
   - Single-page chat interface with sidebar observability
   - System prompt for WGU enrollment advisor
   - Function calling for student data lookup
   - Kubernetes deployment manifests

2. **Data product API service**
   - Small Python service (Flask or FastAPI)
   - REST endpoints: `GET /students/{id}`, `GET /students/{id}/courses`
   - Returns canned realistic WGU data
   - Kubernetes deployment + service manifests

3. **Graph DB mock service**
   - Lightweight Python service
   - Called by data product API
   - Returns canned graph-style responses
   - Kubernetes deployment + service manifests

4. **Kubernetes manifests for all mesh/gateway config**
   - Namespace definitions
   - AuthorizationPolicies
   - Gateway, HTTPRoute, Backend resources
   - Guardrail and rate limit policies
   - Waypoint configuration

### Documentation artifacts

5. **`workshop.md`** — The full linear workshop document with all 6 sections

### What is NOT built

- No actual Neptune database
- No actual Lambda functions
- No Terraform for cluster provisioning
- No CI/CD pipeline
- No AWS-native comparison environment (section 6 is documentation only)
- No multi-page Streamlit app (single page only)
