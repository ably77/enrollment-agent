#!/bin/bash
set -e

# WGU Demo Workshop — Full Install Script
# Prerequisites: cluster1 and cluster2 contexts available, SOLO_TRIAL_LICENSE_KEY and OPENAI_API_KEY set

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Config ---
export KUBECONTEXT_CLUSTER1=${KUBECONTEXT_CLUSTER1:-cluster1}
export KUBECONTEXT_CLUSTER2=${KUBECONTEXT_CLUSTER2:-cluster2}
export MESH_NAME_CLUSTER1=${MESH_NAME_CLUSTER1:-cluster1}
export MESH_NAME_CLUSTER2=${MESH_NAME_CLUSTER2:-cluster2}
export ISTIO_VERSION=${ISTIO_VERSION:-1.29.0}
export ENTERPRISE_AGW_VERSION=${ENTERPRISE_AGW_VERSION:-v2.3.0}
export SOLO_MGMT_UI_VERSION=${SOLO_MGMT_UI_VERSION:-0.3.15-nightly-2026-04-20-680d5f97}
export SOLO_MGMT_UI_OCI_REPO=${SOLO_MGMT_UI_OCI_REPO:-us-docker.pkg.dev/developers-369321/solo-enterprise-public-nonprod}

# --- EKS detection ---
# Auto-detect if cluster1 is EKS by checking the server URL for ".eks.amazonaws.com"
detect_platform() {
  local ctx=$1
  local server
  server=$(kubectl config view -o jsonpath="{.clusters[?(@.name==\"$(kubectl config view -o jsonpath="{.contexts[?(@.name==\"$ctx\")].context.cluster}")\")].cluster.server}" 2>/dev/null)
  if [[ "$server" == *".eks.amazonaws.com"* ]]; then
    echo "eks"
  else
    echo ""
  fi
}

# Resolve LoadBalancer address (IP on GKE/kind, hostname on EKS NLB)
get_lb_address() {
  local svc=$1 ns=$2 ctx=$3
  local ip hostname
  ip=$(kubectl get svc "$svc" -n "$ns" --context "$ctx" -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
  if [ -n "$ip" ]; then
    echo "$ip"
    return
  fi
  hostname=$(kubectl get svc "$svc" -n "$ns" --context "$ctx" -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
  if [ -n "$hostname" ]; then
    echo "$hostname"
    return
  fi
  echo "<pending>"
}

# =============================================================================
# prompt_mode — Interactive menu, returns "full" or "demo". Default=1 on empty Enter.
# =============================================================================
prompt_mode() {
  echo "" >&2
  echo "Select install mode:" >&2
  echo "  1) full      — Install everything end-to-end (Istio, AgentGateway, workloads)" >&2
  echo "  2) demo-only — Deploy enrollment-agent workloads onto existing infrastructure" >&2
  echo "" >&2
  while true; do
    printf "Enter selection [1]: " >&2
    read -r selection
    # Default to 1 on empty Enter
    selection="${selection:-1}"
    case "$selection" in
      1|full)
        echo "full"
        return
        ;;
      2|demo|demo-only)
        echo "demo"
        return
        ;;
      *)
        echo "Invalid selection: '$selection'. Please enter 1 or 2." >&2
        ;;
    esac
  done
}

# =============================================================================
# validate_full — Check both clusters reachable, SOLO_TRIAL_LICENSE_KEY and OPENAI_API_KEY set.
# =============================================================================
validate_full() {
  echo "=== Validating prerequisites ==="
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

# =============================================================================
# validate_demo — Check only cluster1 reachable and OPENAI_API_KEY set.
# No SOLO_TRIAL_LICENSE_KEY or cluster2 needed.
# =============================================================================
validate_demo() {
  echo "=== Validating prerequisites (demo-only mode) ==="
  if [ -z "${OPENAI_API_KEY}" ]; then
    echo "ERROR: OPENAI_API_KEY is not set"
    exit 1
  fi
  kubectl cluster-info --context $KUBECONTEXT_CLUSTER1 > /dev/null 2>&1 || { echo "ERROR: Cannot reach $KUBECONTEXT_CLUSTER1"; exit 1; }
  echo "Cluster1 reachable, credentials set."

  # Check if cluster2 is reachable for multicluster failover demo
  if kubectl cluster-info --context $KUBECONTEXT_CLUSTER2 > /dev/null 2>&1; then
    CLUSTER2_REACHABLE=true
    echo "Cluster2 reachable — multicluster failover demo will be configured."
  else
    CLUSTER2_REACHABLE=false
    echo "Cluster2 not reachable — skipping multicluster setup (single-cluster mode)."
  fi
}

# =============================================================================
# check_infra — Demo-only prerequisite checks.
# Collects all failures and reports them all at once, then exits if any failed.
# =============================================================================
check_infra() {
  echo "=== Checking existing infrastructure ==="
  local failures=()

  # Istio control plane: istiod Running pods
  if ! kubectl get pods -n istio-system -l app=istiod --context $KUBECONTEXT_CLUSTER1 \
      --field-selector=status.phase=Running --no-headers 2>/dev/null | grep -q .; then
    failures+=("Istio control plane (istiod) not found or not Running in istio-system")
  fi

  # ztunnel: Running pods
  if ! kubectl get pods -n istio-system -l app=ztunnel --context $KUBECONTEXT_CLUSTER1 \
      --field-selector=status.phase=Running --no-headers 2>/dev/null | grep -q .; then
    failures+=("ztunnel not found or not Running in istio-system")
  fi

  # AgentGateway controller: Running pods
  if ! kubectl get pods -n agentgateway-system \
      -l app.kubernetes.io/name=enterprise-agentgateway --context $KUBECONTEXT_CLUSTER1 \
      --field-selector=status.phase=Running --no-headers 2>/dev/null | grep -q .; then
    failures+=("AgentGateway controller not found or not Running in agentgateway-system")
  fi

  # AgentGateway proxy Gateway resource exists
  if ! kubectl get gateway agentgateway-proxy -n agentgateway-system \
      --context $KUBECONTEXT_CLUSTER1 > /dev/null 2>&1; then
    failures+=("Gateway 'agentgateway-proxy' not found in agentgateway-system")
  fi

  # Monitoring namespace exists
  if ! kubectl get ns monitoring --context $KUBECONTEXT_CLUSTER1 > /dev/null 2>&1; then
    failures+=("Namespace 'monitoring' not found")
  fi

  if [ ${#failures[@]} -gt 0 ]; then
    echo ""
    echo "ERROR: Infrastructure prerequisites not met:"
    for f in "${failures[@]}"; do
      echo "  - $f"
    done
    echo ""
    echo "Run in 'full' mode to install all infrastructure first."
    exit 1
  fi

  echo "Infrastructure checks passed."
}

# =============================================================================
# install_infra — All infrastructure-only code.
# =============================================================================
install_infra() {
  # --- solo-istioctl ---
  if ! command -v solo-istioctl &> /dev/null; then
    echo "=== Installing solo-istioctl ==="
    OS=$(uname | tr '[:upper:]' '[:lower:]' | sed -E 's/darwin/osx/')
    ARCH=$(uname -m | sed -E 's/aarch/arm/; s/x86_64/amd64/; s/armv7l/armv7/')
    curl -sSL "https://storage.googleapis.com/soloio-istio-binaries/release/${ISTIO_VERSION}-solo/istioctl-${ISTIO_VERSION}-solo-${OS}-${ARCH}.tar.gz" | tar xzf - -C /tmp/
    sudo mv /tmp/istioctl /usr/local/bin/solo-istioctl
    chmod +x /usr/local/bin/solo-istioctl
  fi

  # --- Shared root CA ---
  echo "=== Generating shared root CA ==="
  openssl req -new -newkey rsa:4096 -x509 -sha256 \
    -days 3650 -nodes -subj "/O=Solo.io/CN=Root CA" \
    -keyout /tmp/wgu-root-key.pem -out /tmp/wgu-root-cert.pem 2>/dev/null

  # --- Install Istio on both clusters ---
  install_istio() {
    local CTX=$1 MESH_NAME=$2
    echo "=== Installing Istio ambient mesh on $CTX ==="

    kubectl create namespace istio-system --context $CTX 2>/dev/null || true
    kubectl create secret generic cacerts -n istio-system \
      --from-file=ca-cert.pem=/tmp/wgu-root-cert.pem \
      --from-file=ca-key.pem=/tmp/wgu-root-key.pem \
      --from-file=root-cert.pem=/tmp/wgu-root-cert.pem \
      --from-file=cert-chain.pem=/tmp/wgu-root-cert.pem \
      --context $CTX --dry-run=client -oyaml | kubectl apply --context $CTX -f -

    helm upgrade --kube-context $CTX --install istio-base \
      oci://us-docker.pkg.dev/soloio-img/istio-helm/base \
      -n istio-system --version $ISTIO_VERSION-solo --create-namespace --wait

    kubectl label namespace istio-system topology.istio.io/network=$MESH_NAME --context $CTX --overwrite

    # Gateway API CRDs (experimental for TLSRoute support, server-side apply for large CRDs)
    kubectl get crd gateways.gateway.networking.k8s.io --context $CTX &> /dev/null || \
      kubectl --context $CTX apply --server-side -f \
        https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.0/experimental-install.yaml

    helm upgrade --kube-context $CTX --install istio-cni \
      oci://us-docker.pkg.dev/soloio-img/istio-helm/cni \
      -n istio-system --version=$ISTIO_VERSION-solo --wait \
      -f -<<EOF
profile: ambient
ambient:
  dnsCapture: true
excludeNamespaces:
  - istio-system
  - kube-system
global:
  hub: us-docker.pkg.dev/soloio-img/istio
  tag: $ISTIO_VERSION-solo
  variant: distroless
EOF

    helm upgrade --kube-context $CTX --install istiod \
      oci://us-docker.pkg.dev/soloio-img/istio-helm/istiod \
      -n istio-system --version=$ISTIO_VERSION-solo --wait \
      -f -<<EOF
profile: ambient
global:
  hub: us-docker.pkg.dev/soloio-img/istio
  tag: $ISTIO_VERSION-solo
  variant: distroless
  multiCluster:
    clusterName: $MESH_NAME
  network: $MESH_NAME
meshConfig:
  trustDomain: $MESH_NAME.local
env:
  PILOT_ENABLE_IP_AUTOALLOCATE: "true"
  PILOT_ENABLE_K8S_SELECT_WORKLOAD_ENTRIES: "false"
  PILOT_SKIP_VALIDATE_TRUST_DOMAIN: "true"
platforms:
  peering:
    enabled: true
license:
  value: $SOLO_TRIAL_LICENSE_KEY
EOF

    helm upgrade --kube-context $CTX --install ztunnel \
      oci://us-docker.pkg.dev/soloio-img/istio-helm/ztunnel \
      -n istio-system --version=$ISTIO_VERSION-solo --wait \
      -f -<<EOF
profile: ambient
logLevel: info
global:
  hub: us-docker.pkg.dev/soloio-img/istio
  tag: $ISTIO_VERSION-solo
  variant: distroless
resources:
  requests:
    cpu: 500m
    memory: 2048Mi
istioNamespace: istio-system
env:
  L7_ENABLED: "true"
  SKIP_VALIDATE_TRUST_DOMAIN: "true"
network: $MESH_NAME
multiCluster:
  clusterName: $MESH_NAME
EOF

    echo "Istio ambient mesh installed on $CTX"
  }

  install_istio $KUBECONTEXT_CLUSTER1 $MESH_NAME_CLUSTER1
  install_istio $KUBECONTEXT_CLUSTER2 $MESH_NAME_CLUSTER2

  # --- Multi-cluster linking ---
  echo "=== Linking clusters ==="
  kubectl create ns istio-gateways --context $KUBECONTEXT_CLUSTER1 2>/dev/null || true
  kubectl create ns istio-gateways --context $KUBECONTEXT_CLUSTER2 2>/dev/null || true
  solo-istioctl multicluster expose --namespace istio-gateways --context $KUBECONTEXT_CLUSTER1
  solo-istioctl multicluster expose --namespace istio-gateways --context $KUBECONTEXT_CLUSTER2

  # On EKS, add NLB annotation via the Gateway spec.infrastructure.annotations field.
  # This propagates to the generated Service and tells the in-tree cloud controller
  # to manage NodePort security group rules on the node SGs automatically.
  if [ "$(detect_platform $KUBECONTEXT_CLUSTER1)" = "eks" ]; then
    echo "EKS detected — patching east-west Gateways with NLB annotations..."
    for ctx in $KUBECONTEXT_CLUSTER1 $KUBECONTEXT_CLUSTER2; do
      kubectl patch gateway istio-eastwest -n istio-gateways --context "$ctx" --type=merge -p '
spec:
  infrastructure:
    annotations:
      service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
'
    done
  fi

  kubectl rollout status deploy -n istio-gateways --watch --timeout=120s --context $KUBECONTEXT_CLUSTER1
  kubectl rollout status deploy -n istio-gateways --watch --timeout=120s --context $KUBECONTEXT_CLUSTER2

  # Wait for east-west gateway LoadBalancers to get external addresses (EKS NLBs can take 30-60s)
  echo "Waiting for east-west gateway LoadBalancers..."
  for ctx in $KUBECONTEXT_CLUSTER1 $KUBECONTEXT_CLUSTER2; do
    for i in $(seq 1 30); do
      local addr
      addr=$(get_lb_address istio-eastwest istio-gateways "$ctx")
      if [ "$addr" != "<pending>" ]; then
        echo "  $ctx east-west LB: $addr"
        break
      fi
      if [ $i -eq 30 ]; then
        echo "WARNING: $ctx east-west LB still pending after 60s — multicluster link may fail"
      fi
      sleep 2
    done
  done

  solo-istioctl multicluster link --contexts=$KUBECONTEXT_CLUSTER1,$KUBECONTEXT_CLUSTER2 --namespace istio-gateways

  # --- Enterprise Agentgateway ---
  echo "=== Installing Enterprise Agentgateway ==="

  # Upgrade to experimental Gateway API CRDs v1.5.0
  kubectl delete validatingadmissionpolicybinding safe-upgrades.gateway.networking.k8s.io --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null
  kubectl delete validatingadmissionpolicy safe-upgrades.gateway.networking.k8s.io --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null
  kubectl apply --server-side -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.5.0/experimental-install.yaml --context $KUBECONTEXT_CLUSTER1

  kubectl create namespace agentgateway-system --context $KUBECONTEXT_CLUSTER1 2>/dev/null || true

  helm upgrade -i --create-namespace --namespace agentgateway-system \
    --version $ENTERPRISE_AGW_VERSION enterprise-agentgateway-crds \
    oci://us-docker.pkg.dev/solo-public/enterprise-agentgateway/charts/enterprise-agentgateway-crds \
    --kube-context $KUBECONTEXT_CLUSTER1

  helm upgrade -i -n agentgateway-system enterprise-agentgateway \
    oci://us-docker.pkg.dev/solo-public/enterprise-agentgateway/charts/enterprise-agentgateway \
    --create-namespace --version $ENTERPRISE_AGW_VERSION \
    --set-string licensing.licenseKey=$SOLO_TRIAL_LICENSE_KEY \
    --kube-context $KUBECONTEXT_CLUSTER1 --wait \
    -f -<<EOF
gatewayClassParametersRefs:
  enterprise-agentgateway:
    group: enterpriseagentgateway.solo.io
    kind: EnterpriseAgentgatewayParameters
    name: agentgateway-config
    namespace: agentgateway-system
EOF

  # Deploy gateway config
  kubectl apply --context $KUBECONTEXT_CLUSTER1 -f -<<'EOF'
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayParameters
metadata:
  name: agentgateway-config
  namespace: agentgateway-system
spec:
  sharedExtensions:
    extauth:
      enabled: true
      deployment:
        spec:
          replicas: 1
    ratelimiter:
      enabled: true
      deployment:
        spec:
          replicas: 1
    extCache:
      enabled: true
      deployment:
        spec:
          replicas: 1
  logging:
    level: info
  service:
    spec:
      type: ClusterIP
  deployment:
    spec:
      replicas: 1
---
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: agentgateway-proxy
  namespace: agentgateway-system
spec:
  gatewayClassName: enterprise-agentgateway
  listeners:
    - name: http
      port: 8080
      protocol: HTTP
      allowedRoutes:
        namespaces:
          from: All
EOF

  echo "Waiting for agentgateway controller..."
  kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=enterprise-agentgateway \
    -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --timeout=180s

  echo "Waiting for agentgateway proxy..."
  kubectl wait --for=condition=programmed gateway agentgateway-proxy \
    -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --timeout=120s
  kubectl wait --for=condition=ready pod -l gateway.networking.k8s.io/gateway-name=agentgateway-proxy \
    -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --timeout=120s

  # --- Observability: Solo Management UI + Prometheus/Grafana ---
  echo "=== Installing observability stack ==="

  # Solo Management UI with both Mesh and AgentGateway product views
  kubectl create namespace kagent --context $KUBECONTEXT_CLUSTER1 2>/dev/null || true
  kubectl label namespace kagent istio.io/dataplane-mode=ambient --context $KUBECONTEXT_CLUSTER1 --overwrite

  helm upgrade -i management \
    "oci://${SOLO_MGMT_UI_OCI_REPO}/charts/management" \
    --namespace kagent --create-namespace \
    --version "$SOLO_MGMT_UI_VERSION" \
    --kube-context $KUBECONTEXT_CLUSTER1 --wait --no-hooks \
    -f -<<EOF
cluster: "${KUBECONTEXT_CLUSTER1}"
service:
  type: ClusterIP
products:
  agentgateway:
    enabled: true
    namespace: agentgateway-system
  mesh:
    enabled: true
  kagent:
    enabled: false
  agentregistry:
    enabled: false
clickhouse:
  enabled: true
tracing:
  verbose: true
licensing:
  licenseKey: "${SOLO_TRIAL_LICENSE_KEY}"
EOF

  # Label Solo Enterprise services as global for cross-cluster mesh visibility
  kubectl label svc solo-enterprise-ui -n kagent solo.io/service-scope=global \
    --context $KUBECONTEXT_CLUSTER1 --overwrite 2>/dev/null || true
  kubectl label svc solo-enterprise-telemetry-gateway -n kagent solo.io/service-scope=global \
    --context $KUBECONTEXT_CLUSTER1 --overwrite 2>/dev/null || true

  # Prometheus + Grafana
  helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
  helm repo update prometheus-community
  helm upgrade --install grafana-prometheus \
    prometheus-community/kube-prometheus-stack \
    --version 80.4.2 --namespace monitoring --create-namespace \
    --kube-context $KUBECONTEXT_CLUSTER1 --wait \
    --values -<<EOF
alertmanager:
  enabled: false
grafana:
  adminPassword: "prom-operator"
  service:
    type: ClusterIP
    port: 3000
  sidecar:
    dashboards:
      enabled: true
      label: grafana_dashboard
      labelValue: "1"
      searchNamespace: monitoring
nodeExporter:
  enabled: false
prometheus:
  prometheusSpec:
    ruleSelectorNilUsesHelmValues: false
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false
EOF

  # PodMonitor for gateway metrics
  kubectl apply --context $KUBECONTEXT_CLUSTER1 -f -<<'EOF'
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: agentgateway-metrics
  namespace: agentgateway-system
spec:
  namespaceSelector:
    matchNames:
      - agentgateway-system
  podMetricsEndpoints:
    - port: metrics
  selector:
    matchLabels:
      app.kubernetes.io/name: agentgateway-proxy
EOF

  # Access logging
  kubectl apply --context $KUBECONTEXT_CLUSTER1 -f -<<'EOF'
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: access-logs
  namespace: agentgateway-system
spec:
  targetRefs:
  - group: gateway.networking.k8s.io
    kind: Gateway
    name: agentgateway-proxy
  frontend:
    accessLog:
      attributes:
        add:
        - name: llm.prompt
          expression: llm.prompt
        - name: llm.completion
          expression: 'llm.completion[0]'
        - name: llm.streaming
          expression: llm.streaming
EOF

  # Tracing — send traces to OTEL collector for Gloo UI
  kubectl apply --context $KUBECONTEXT_CLUSTER1 -f -<<'EOF'
apiVersion: enterpriseagentgateway.solo.io/v1alpha1
kind: EnterpriseAgentgatewayPolicy
metadata:
  name: tracing
  namespace: agentgateway-system
spec:
  targetRefs:
  - group: gateway.networking.k8s.io
    kind: Gateway
    name: agentgateway-proxy
  frontend:
    tracing:
      backendRef:
        name: solo-enterprise-telemetry-collector
        namespace: agentgateway-system
        port: 4317
      protocol: GRPC
      randomSampling: "true"
      attributes:
        add:
        - name: jwt
          expression: jwt
        - name: response.body
          expression: json(response.body)
EOF

  echo "Observability stack installed."
}

# =============================================================================
# deploy_workloads — Shared by BOTH modes.
# =============================================================================
deploy_workloads() {
  local ctx=$KUBECONTEXT_CLUSTER1

  # --- Deploy WGU workloads ---
  echo "=== Deploying WGU demo workloads ==="
  kubectl apply -f k8s/namespaces.yaml --context $ctx
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
    -f k8s/gateway/abac-ext-authz.yaml \
    --context $ctx

  kubectl rollout status deploy/abac-ext-authz -n agentgateway-system --watch --timeout=60s --context $ctx

  # Note: agentgateway-system is NOT enrolled in the ambient mesh.
  # Enrolling it breaks internal traffic (proxy -> OTEL collector, proxy -> rate limiter)
  # because ALLOW policies on the proxy deny internal pod-to-pod communication.
  # The agent gateway is still governed through its own policies (guardrails, rate limits, access logs).

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

  # Detect which namespace solo-enterprise-ui is in (agentgateway-system or kagent)
  local ui_ns=""
  if kubectl get svc solo-enterprise-ui -n agentgateway-system --context $ctx &>/dev/null; then
    ui_ns="agentgateway-system"
  elif kubectl get svc solo-enterprise-ui -n kagent --context $ctx &>/dev/null; then
    ui_ns="kagent"
  fi

  if [ -n "$ui_ns" ]; then
    # Clean up stale ui-ingress-route from the other namespace if it exists
    if [ "$ui_ns" = "kagent" ]; then
      kubectl delete httproute ui-ingress-route -n agentgateway-system --context $ctx --ignore-not-found 2>/dev/null || true
    else
      kubectl delete httproute ui-ingress-route -n kagent --context $ctx --ignore-not-found 2>/dev/null || true
    fi
    echo "Found solo-enterprise-ui in $ui_ns — applying UI ingress route"
    kubectl apply --context $ctx -f -<<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: ui-ingress-route
  namespace: $ui_ns
spec:
  hostnames:
  - "ui.glootest.com"
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
EOF
    # Patch to ClusterIP if LoadBalancer (avoids port 80 conflict with ingress)
    local svc_type=$(kubectl get svc solo-enterprise-ui -n $ui_ns --context $ctx -o jsonpath='{.spec.type}')
    if [ "$svc_type" = "LoadBalancer" ]; then
      kubectl patch svc solo-enterprise-ui -n $ui_ns --context $ctx \
        --type=merge -p '{"spec":{"type":"ClusterIP"}}' 2>/dev/null || true
    fi
  else
    echo "WARNING: solo-enterprise-ui not found in agentgateway-system or kagent — skipping UI route"
  fi

  # Import Agentgateway Grafana dashboard
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

  # --- Solo Enterprise relay for Mesh UI multi-cluster visibility ---
  echo "=== Installing Solo Enterprise relay on cluster2 ==="
  helm upgrade -i relay \
    "oci://${SOLO_MGMT_UI_OCI_REPO}/charts/relay" \
    --version "$SOLO_MGMT_UI_VERSION" \
    --namespace solo-enterprise --create-namespace \
    --kube-context $ctx --wait \
    -f -<<EOF
cluster: ${ctx}
tunnel:
  fqdn: solo-enterprise-ui.kagent.mesh.internal
  port: 9000
telemetry:
  fqdn: solo-enterprise-telemetry-gateway.kagent.mesh.internal
EOF

  kubectl label namespace solo-enterprise istio.io/dataplane-mode=ambient --context $ctx --overwrite

  echo "Backend services and relay deployed to cluster2."
}

# =============================================================================
# configure_global_services — Ensure cluster2 services have global labels.
# Cluster1 labels are already in the manifests (data-product-api.yaml).
# DATA_PRODUCT_URL defaults to mesh.internal in the chatbot manifest.
# =============================================================================
configure_global_services() {
  local ctx=$KUBECONTEXT_CLUSTER2

  echo "=== Configuring global services on cluster2 ==="
  # The manifest already has the global label and annotation for cluster1.
  # Cluster2's apply also picks them up, but label/annotate explicitly
  # in case the manifest was applied before the labels were added.
  for svc in data-product-api graph-db-mock; do
    kubectl --context $ctx -n wgu-demo \
      label service $svc solo.io/service-scope=global --overwrite
    kubectl --context $ctx -n wgu-demo \
      annotate service $svc networking.istio.io/traffic-distribution=PreferNetwork --overwrite
  done

  echo "Global services configured on cluster2."
}

# =============================================================================
# print_access_info — Completion output block.
# =============================================================================
print_access_info() {
  # --- Done ---
  local LB_ADDR
  LB_ADDR=$(get_lb_address ingress agentgateway-system "$KUBECONTEXT_CLUSTER1")

  echo ""
  echo "============================================"
  echo "  WGU Demo Workshop — Install Complete"
  echo "============================================"
  echo ""
  echo "Access via ingress gateway (requires /etc/hosts or DNS):"
  echo "  http://enroll.glootest.com    — Enrollment chatbot"
  echo "  http://grafana.glootest.com    — Grafana (admin / prom-operator)"
  echo "  http://ui.glootest.com         — Gloo UI (traces)"
  echo ""
  echo "Ingress LoadBalancer address: $LB_ADDR"

  # Detect if it's a hostname (EKS NLB) vs an IP
  if [[ "$LB_ADDR" == *".elb."* || "$LB_ADDR" == *".amazonaws.com"* ]]; then
    echo ""
    echo "EKS NLB detected — resolve hostname to IP for /etc/hosts:"
    echo "  nslookup $LB_ADDR"
    echo ""
    echo "Add to /etc/hosts (use one of the resolved IPs):"
    # Try to resolve automatically
    local RESOLVED_IP
    RESOLVED_IP=$(dig +short "$LB_ADDR" 2>/dev/null | head -1)
    if [ -n "$RESOLVED_IP" ]; then
      echo "  $RESOLVED_IP enroll.glootest.com grafana.glootest.com ui.glootest.com"
    else
      echo "  <RESOLVED_IP> enroll.glootest.com grafana.glootest.com ui.glootest.com"
    fi
    echo ""
    echo "NOTE: EKS NLB IPs can change. For production, use Route 53 CNAME records instead."
  else
    echo ""
    echo "Add to /etc/hosts:"
    echo "  $LB_ADDR enroll.glootest.com grafana.glootest.com ui.glootest.com"
  fi

  # Detect where solo-enterprise-ui is deployed
  local ui_pf_ns=""
  if kubectl get svc solo-enterprise-ui -n kagent --context "$KUBECONTEXT_CLUSTER1" &>/dev/null; then
    ui_pf_ns="kagent"
  elif kubectl get svc solo-enterprise-ui -n agentgateway-system --context "$KUBECONTEXT_CLUSTER1" &>/dev/null; then
    ui_pf_ns="agentgateway-system"
  fi

  echo ""
  echo "Fallback (port-forward):"
  echo "  kubectl port-forward svc/enrollment-chatbot -n wgu-demo-frontend 8501:8501 --context $KUBECONTEXT_CLUSTER1"
  if [ -n "$ui_pf_ns" ]; then
    echo "  kubectl port-forward -n $ui_pf_ns svc/solo-enterprise-ui 4000:80 --context $KUBECONTEXT_CLUSTER1"
  fi
  echo "  kubectl port-forward -n monitoring svc/grafana-prometheus 3000:3000 --context $KUBECONTEXT_CLUSTER1"
  echo ""
  echo "Verify mesh enrollment:"
  echo "  solo-istioctl ztunnel-config workloads --context $KUBECONTEXT_CLUSTER1 | grep -E 'wgu-demo|ingress'"
  echo ""
}

# =============================================================================
# Main
# =============================================================================
INSTALL_MODE=$(prompt_mode)

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
    if [ "$CLUSTER2_REACHABLE" = "true" ]; then
      deploy_workloads_cluster2
      configure_global_services
    fi
    ;;
esac

print_access_info
