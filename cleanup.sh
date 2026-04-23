#!/bin/bash
set -e

# Enrollment Agent Demo — Cleanup Script
# Tears down resources installed by install.sh
# Usage: ./cleanup.sh        (interactive prompt)
#        ./cleanup.sh full    (tear down everything)
#        ./cleanup.sh demo    (tear down workloads only, keep infra)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export KUBECONTEXT_CLUSTER1=${KUBECONTEXT_CLUSTER1:-cluster1}
export KUBECONTEXT_CLUSTER2=${KUBECONTEXT_CLUSTER2:-cluster2}

# =============================================================================
# prompt_mode — Interactive menu if no argument given
# =============================================================================
prompt_mode() {
  if [ -n "$1" ]; then
    echo "$1"
    return
  fi
  echo "" >&2
  echo "Select cleanup mode:" >&2
  echo "  1) full      — Tear down everything (workloads, infra, Istio)" >&2
  echo "  2) demo-only — Remove workloads only, keep Istio and infrastructure" >&2
  echo "" >&2
  read -rp "Choice [1]: " choice
  case "${choice:-1}" in
    1|full)
      echo "full"
      ;;
    2|demo|demo-only)
      echo "demo"
      ;;
    *)
      echo "Invalid choice: $choice" >&2
      exit 1
      ;;
  esac
}

# =============================================================================
# cleanup_workloads — Remove demo workloads and gateway config (shared by both modes)
# =============================================================================
cleanup_workloads() {
  echo "--- Killing port-forwards ---"
  kill $(lsof -ti:8501) 2>/dev/null || true
  kill $(lsof -ti:4000) 2>/dev/null || true
  kill $(lsof -ti:3000) 2>/dev/null || true

  echo "--- Deleting WGU demo resources on cluster1 ---"
  kubectl delete -f k8s/services/ --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
  kubectl delete -f k8s/mesh/ --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
  kubectl delete -f k8s/gateway/ --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true

  echo "--- Deleting agent gateway resources ---"
  kubectl delete gateway agentgateway-proxy -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
  kubectl delete enterpriseagentgatewayparameters agentgateway-config -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
  kubectl delete gateway ingress -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
  kubectl delete enterpriseagentgatewayparameters ingress-agentgateway-config -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
  kubectl delete enterpriseagentgatewaypolicy --all -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
  kubectl delete secret enrollment-openai-secret -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true

  echo "--- Deleting WGU demo resources on cluster2 ---"
  kubectl delete -f k8s/services/data-product-api.yaml --context $KUBECONTEXT_CLUSTER2 --ignore-not-found 2>/dev/null || true
  kubectl delete -f k8s/services/graph-db-mock.yaml --context $KUBECONTEXT_CLUSTER2 --ignore-not-found 2>/dev/null || true
  kubectl delete -f k8s/services/financial-aid-mcp.yaml --context $KUBECONTEXT_CLUSTER2 --ignore-not-found 2>/dev/null || true
  kubectl delete -f k8s/mesh/ --context $KUBECONTEXT_CLUSTER2 --ignore-not-found 2>/dev/null || true

  echo "--- Deleting demo namespaces ---"
  kubectl delete -f k8s/namespaces.yaml --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
  kubectl delete -f k8s/namespaces.yaml --context $KUBECONTEXT_CLUSTER2 --ignore-not-found 2>/dev/null || true
}

# =============================================================================
# cleanup_infra — Remove Istio, agent gateway helm releases, monitoring, namespaces
# =============================================================================
cleanup_infra() {
  echo "--- Uninstalling Enterprise Agentgateway ---"
  helm uninstall enterprise-agentgateway -n agentgateway-system --kube-context $KUBECONTEXT_CLUSTER1 2>/dev/null || true
  helm uninstall enterprise-agentgateway-crds -n agentgateway-system --kube-context $KUBECONTEXT_CLUSTER1 2>/dev/null || true
  helm uninstall management -n kagent --kube-context $KUBECONTEXT_CLUSTER1 2>/dev/null || true
  helm uninstall relay -n solo-enterprise --kube-context $KUBECONTEXT_CLUSTER2 2>/dev/null || true

  echo "--- Uninstalling monitoring ---"
  helm uninstall grafana-prometheus -n monitoring --kube-context $KUBECONTEXT_CLUSTER1 2>/dev/null || true

  echo "--- Removing multi-cluster linking ---"
  for CTX in $KUBECONTEXT_CLUSTER1 $KUBECONTEXT_CLUSTER2; do
    kubectl delete ns istio-gateways --context $CTX --ignore-not-found 2>/dev/null || true
  done

  echo "--- Uninstalling Istio ---"
  for CTX in $KUBECONTEXT_CLUSTER1 $KUBECONTEXT_CLUSTER2; do
    echo "  Cleaning up $CTX..."
    helm uninstall ztunnel -n istio-system --kube-context $CTX 2>/dev/null || true
    helm uninstall istiod -n istio-system --kube-context $CTX 2>/dev/null || true
    helm uninstall istio-cni -n istio-system --kube-context $CTX 2>/dev/null || true
    helm uninstall istio-base -n istio-system --kube-context $CTX 2>/dev/null || true
    kubectl delete namespace istio-system --context $CTX --ignore-not-found 2>/dev/null || true
  done

  echo "--- Deleting infrastructure namespaces ---"
  kubectl delete namespace agentgateway-system kagent monitoring --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
  kubectl delete namespace solo-enterprise --context $KUBECONTEXT_CLUSTER2 --ignore-not-found 2>/dev/null || true

  echo "--- Cleaning up generated files ---"
  rm -f shared-root-trust-secret.yaml
}

# =============================================================================
# Main
# =============================================================================
CLEANUP_MODE=$(prompt_mode "$1")

echo "=== Cleaning up Enrollment Agent Demo ($CLEANUP_MODE) ==="
echo "Clusters: $KUBECONTEXT_CLUSTER1, $KUBECONTEXT_CLUSTER2"
echo ""

case "$CLEANUP_MODE" in
  full)
    cleanup_workloads
    cleanup_infra
    ;;
  demo)
    cleanup_workloads
    ;;
esac

echo ""
echo "============================================"
echo "  Enrollment Agent Demo — Cleanup Complete ($CLEANUP_MODE)"
echo "============================================"
echo ""
if [ "$CLEANUP_MODE" = "demo" ]; then
  echo "Infrastructure (Istio, agent gateway, monitoring) is still running."
  echo "Run './cleanup.sh full' to tear down everything."
else
  echo "Clusters are still running. Stop or delete them as needed for your environment."
fi
echo ""
