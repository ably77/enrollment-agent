#!/bin/bash
set -e

# Quick rebuild and deploy the enrollment chatbot.
# Usage: ./deploy.sh [version]
# Example: ./deploy.sh 0.0.7

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CTX=${KUBECONTEXT_CLUSTER1:-cluster1}

# Auto-increment version from current manifest
CURRENT=$(grep 'image: ably7/enrollment-chatbot:' k8s/services/enrollment-chatbot.yaml | sed 's/.*://')
if [ -n "$1" ]; then
  VERSION="$1"
else
  # Bump patch version
  MAJOR=$(echo $CURRENT | cut -d. -f1)
  MINOR=$(echo $CURRENT | cut -d. -f2)
  PATCH=$(echo $CURRENT | cut -d. -f3)
  VERSION="${MAJOR}.${MINOR}.$((PATCH + 1))"
fi

IMAGE="ably7/enrollment-chatbot:${VERSION}"
echo "=== Building and deploying $IMAGE ==="

# Build and push
docker buildx build --builder ly-builder \
  --platform linux/amd64,linux/arm64 \
  -t "$IMAGE" --push \
  -f demo-ui/Dockerfile .

# Update manifest
sed -i '' "s|ably7/enrollment-chatbot:.*|ably7/enrollment-chatbot:${VERSION}|" k8s/services/enrollment-chatbot.yaml

# Deploy
kubectl apply -f k8s/services/enrollment-chatbot.yaml --context $CTX
kubectl rollout status deploy/enrollment-chatbot -n wgu-demo-frontend --watch --timeout=120s --context $CTX

# Restart port-forward
kill $(lsof -ti:8501) 2>/dev/null || true
kubectl port-forward svc/enrollment-chatbot -n wgu-demo-frontend 8501:8501 --context $CTX &>/dev/null &
sleep 2

echo ""
echo "=== Deployed $IMAGE ==="
echo "Open http://localhost:8501"
