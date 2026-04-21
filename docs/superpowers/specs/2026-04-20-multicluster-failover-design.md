# Multicluster Failover Demo — Design Spec

## Summary

Add a multicluster failover demo to the enrollment-agent project. The demo showcases Istio ambient mesh cross-cluster service routing by making `data-product-api` a globally available service, then simulating failover by scaling it down on cluster1. The chatbot continues to work because the mesh transparently routes requests to cluster2.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Failover target | `data-product-api` | Directly affects chatbot UX — user can ask a question during failover and it still works |
| Page layout | Stepped tabs (4 steps) | Matches reference pattern, clean guided demo flow |
| Cluster2 access from pod | None — cluster1-only | Simpler setup; proves the mesh handles it transparently |
| Global labeling | Install script labels cluster2; demo page labels cluster1 live | Teaching moment on cluster1, no cross-cluster kubeconfig needed |
| Cluster2 workload deployment | Install script | Infra setup should "just work" before the demo starts |

## Component 1: Install Script Changes

### `deploy_workloads_cluster2` function

Deploys backend services to cluster2 by reusing existing YAMLs:

- `kubectl apply -f k8s/namespaces.yaml --context $KUBECONTEXT_CLUSTER2`
- `kubectl apply -f k8s/services/graph-db-mock.yaml --context $KUBECONTEXT_CLUSTER2`
- `kubectl apply -f k8s/services/data-product-api.yaml --context $KUBECONTEXT_CLUSTER2`
- `kubectl apply -f k8s/mesh/ --context $KUBECONTEXT_CLUSTER2`
- Label namespace for waypoint: `kubectl label namespace wgu-demo istio.io/use-waypoint=wgu-demo-waypoint --context $KUBECONTEXT_CLUSTER2 --overwrite`
- Wait for rollouts on cluster2

Does NOT deploy: chatbot, agentgateway, ingress, observability stack. Those stay on cluster1 only.

### `configure_global_services` function

Runs on cluster2 only (cluster1 labeling is done by the demo page):

```bash
for svc in data-product-api graph-db-mock; do
  kubectl --context $KUBECONTEXT_CLUSTER2 -n wgu-demo \
    label service $svc solo.io/service-scope=global --overwrite
  kubectl --context $KUBECONTEXT_CLUSTER2 -n wgu-demo \
    annotate service $svc networking.istio.io/traffic-distribution=PreferNetwork --overwrite
done
```

Both `graph-db-mock` must also be global because if `data-product-api` fails over to cluster2, it needs to reach `graph-db-mock` there.

### Execution order

Called in `full` mode only, after `deploy_workloads` (cluster1):

```
install_infra → deploy_workloads (cluster1) → deploy_workloads_cluster2 → configure_global_services → print_access_info
```

## Component 2: Demo Page — `demo-ui/pages/2_Multi_Cluster.py`

New Streamlit page with 4 stepped tabs. Uses the same patterns as `1_Mesh_Policies.py`: `run_kubectl()` without `--context` (in-cluster config, cluster1 only), `requests` for HTTP verification, imports from `utils/`.

### Step 1: Enable Global Service

- Button: "Enable Global Service"
- Runs:
  - `kubectl label service data-product-api -n wgu-demo solo.io/service-scope=global --overwrite`
  - `kubectl annotate service data-product-api -n wgu-demo networking.istio.io/traffic-distribution=PreferNetwork --overwrite`
  - Same two commands for `graph-db-mock`
- Displays: `kubectl get serviceentry -n istio-system` to show the auto-generated ServiceEntry
- Displays: `kubectl get deploy -n wgu-demo` to show current replica counts
- Expandable YAML reference explaining the label and annotation

### Step 2: Simulate Failover

- Button: "Scale Down data-product-api (this cluster)"
- Runs:
  - `kubectl scale deploy/data-product-api -n wgu-demo --replicas 0`
  - `kubectl get deploy -n wgu-demo` to confirm 0/0
- Info text: "The mesh will now route data-product-api traffic to cluster2 transparently"

### Step 3: Verify Failover

- Button: "Test Data Product API"
- Makes HTTP requests from the pod:
  - `GET {DATA_PRODUCT_URL}/health`
  - `GET {DATA_PRODUCT_URL}/students/{DEFAULT_STUDENT_ID}`
- If 200: success message — "data-product-api is responding — traffic is being served from cluster2"
- If connection refused: error — "Failover not working — check that cluster2 has data-product-api running and services are labeled global"
- Suggestion to also try asking the chatbot a question on the Homepage

### Step 4: Restore

- Button: "Scale Up data-product-api (this cluster)"
- Runs:
  - `kubectl scale deploy/data-product-api -n wgu-demo --replicas 1`
  - `kubectl rollout status deploy/data-product-api -n wgu-demo --timeout=60s`
  - `kubectl get deploy -n wgu-demo` to confirm 1/1
- Button: "Test Data Product API" to verify local is serving again
- Success message when confirmed

### Bottom section: Demo Walkthrough

Recommended narrative flow for presenting this demo, similar to the walkthrough section in `1_Mesh_Policies.py`.

## Component 3: RBAC Changes

Extend the existing `enrollment-chatbot-mesh-demo` ClusterRole in `k8s/services/enrollment-chatbot.yaml` with:

```yaml
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

## What does NOT change

- `run_kubectl` — no `--context` support needed
- `config.py` — no new env vars
- `sidebar.py` — no changes
- `Homepage.py` — no changes
- `Dockerfile` — no changes (already copies `k8s/` into the image)
- No new k8s YAML files — cluster2 reuses existing manifests
