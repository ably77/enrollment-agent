#!/bin/bash
set -e

# WGU Demo Workshop — Cleanup Script
# Tears down everything installed by install.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export KUBECONTEXT_CLUSTER1=${KUBECONTEXT_CLUSTER1:-cluster1}
export KUBECONTEXT_CLUSTER2=${KUBECONTEXT_CLUSTER2:-cluster2}

echo "=== Cleaning up WGU Demo Workshop ==="
echo "Clusters: $KUBECONTEXT_CLUSTER1, $KUBECONTEXT_CLUSTER2"
echo ""

# --- Kill local port-forwards ---
echo "--- Killing port-forwards ---"
kill $(lsof -ti:8501) 2>/dev/null || true
kill $(lsof -ti:4000) 2>/dev/null || true
kill $(lsof -ti:3000) 2>/dev/null || true

# --- Delete WGU demo resources ---
echo "--- Deleting WGU demo resources ---"
kubectl delete -f k8s/services/ --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
kubectl delete -f k8s/mesh/ --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
kubectl delete -f k8s/gateway/ --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
kubectl delete -f k8s/namespaces.yaml --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true

# --- Delete agent gateway ---
echo "--- Uninstalling Enterprise Agentgateway ---"
kubectl delete gateway agentgateway-proxy -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
kubectl delete enterpriseagentgatewayparameters agentgateway-config -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
kubectl delete enterpriseagentgatewaypolicy --all -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
kubectl delete secret openai-secret -n agentgateway-system --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true
helm uninstall enterprise-agentgateway -n agentgateway-system --kube-context $KUBECONTEXT_CLUSTER1 2>/dev/null || true
helm uninstall enterprise-agentgateway-crds -n agentgateway-system --kube-context $KUBECONTEXT_CLUSTER1 2>/dev/null || true
helm uninstall management -n agentgateway-system --kube-context $KUBECONTEXT_CLUSTER1 2>/dev/null || true

# --- Delete monitoring ---
echo "--- Uninstalling monitoring ---"
helm uninstall grafana-prometheus -n monitoring --kube-context $KUBECONTEXT_CLUSTER1 2>/dev/null || true

# --- Delete multi-cluster linking ---
echo "--- Removing multi-cluster linking ---"
for CTX in $KUBECONTEXT_CLUSTER1 $KUBECONTEXT_CLUSTER2; do
  kubectl delete ns istio-gateways --context $CTX --ignore-not-found 2>/dev/null || true
done

# --- Uninstall Istio from both clusters ---
echo "--- Uninstalling Istio ---"
for CTX in $KUBECONTEXT_CLUSTER1 $KUBECONTEXT_CLUSTER2; do
  echo "  Cleaning up $CTX..."
  helm uninstall ztunnel -n istio-system --kube-context $CTX 2>/dev/null || true
  helm uninstall istiod -n istio-system --kube-context $CTX 2>/dev/null || true
  helm uninstall istio-cni -n istio-system --kube-context $CTX 2>/dev/null || true
  helm uninstall istio-base -n istio-system --kube-context $CTX 2>/dev/null || true
  kubectl delete namespace istio-system --context $CTX --ignore-not-found 2>/dev/null || true
done

# --- Delete remaining namespaces ---
echo "--- Deleting namespaces ---"
kubectl delete namespace agentgateway-system monitoring --context $KUBECONTEXT_CLUSTER1 --ignore-not-found 2>/dev/null || true

# --- Clean up temp files ---
rm -f /tmp/wgu-root-key.pem /tmp/wgu-root-cert.pem

echo ""
echo "============================================"
echo "  WGU Demo Workshop — Cleanup Complete"
echo "============================================"
echo ""
echo "Clusters are still running. To stop Colima clusters:"
echo "  colima stop --profile cluster1"
echo "  colima stop --profile cluster2"
echo ""
