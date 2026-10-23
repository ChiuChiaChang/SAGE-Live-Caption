#!/usr/bin/env bash
# v1.0.1.0. Builds a new Docker image, fetches model files and starts port 8300.
# Does not stop or modify any pre-existing Docker containers.
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(uname -m)" != "aarch64" ]; then
  echo "WARNING: designed for GB10 ARM64; detected $(uname -m)."
fi
if ! command -v docker >/dev/null; then echo "Docker is required"; exit 1; fi
if docker info >/dev/null 2>&1; then D=(docker); else D=(sudo docker); fi
mkdir -p models input output jobs
echo "[1/5] Building isolated GB10 Docker image"
"${D[@]}" compose build
echo "[2/5] Checking GPU visibility"
"${D[@]}" run --rm --gpus all getac-echomimicv3-flash:1.0.1.0 \
  python -c 'import torch; assert torch.cuda.is_available(); print(torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))'
echo "[3/5] Checking EchoMimic import"
"${D[@]}" run --rm --gpus all getac-echomimicv3-flash:1.0.1.0 \
  python -c 'import os; os.chdir("/opt/echomimic_v3"); import infer_flash; print("EchoMimic imports OK")'
echo "[4/5] Downloading Flash-Pro model weights (once; Internet required)"
"${D[@]}" run --rm -v "$PWD/models:/data/models" \
  getac-echomimicv3-flash:1.0.1.0 python /opt/tools/download_models.py
echo "[5/5] Starting API (local port 8300)"
"${D[@]}" compose up -d --no-build
echo "Done. Check with: curl http://127.0.0.1:8300/health"
echo "API docs: http://127.0.0.1:8300/docs"
