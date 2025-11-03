#!/usr/bin/env bash
# Build the three per-language sandbox images.
#
# The backend looks for these tags at runtime; if they are missing it falls
# back to running submissions on the host under rlimits (see sandbox.py).
set -euo pipefail

cd "$(dirname "$0")"

TAG="${SANDBOX_TAG:-latest}"

for lang in python cpp java; do
  echo "==> building algobattle-sandbox-${lang}:${TAG}"
  docker build -f "${lang}.Dockerfile" -t "algobattle-sandbox-${lang}:${TAG}" .
done

echo
echo "Done. Images:"
docker images --filter "reference=algobattle-sandbox-*" \
  --format "  {{.Repository}}:{{.Tag}}  {{.Size}}"
