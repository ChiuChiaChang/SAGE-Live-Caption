#!/usr/bin/env bash
# Getac LivePortrait GB10 deploy/update, v1.0.0.0
set -Eeuo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${LIVEPORTRAIT_DATA_DIR:-$HOME/getac-liveportrait-data}"
PORT="${LIVEPORTRAIT_PORT:-8400}"
mkdir -p "$DATA/models" "$DATA/jobs" "$DATA/hf-cache"
if [[ "$(uname -m)" != "aarch64" ]]; then
  echo "WARNING: Designed for NVIDIA GB10 ARM64; detected $(uname -m)." >&2
fi
if docker info >/dev/null 2>&1; then DOCKER=(docker); else DOCKER=(sudo docker); fi
"${DOCKER[@]}" info >/dev/null || { echo "ERROR: Docker unavailable."; exit 1; }
"${DOCKER[@]}" compose version >/dev/null || { echo "ERROR: Docker Compose v2 required."; exit 1; }
nvidia-smi >/dev/null 2>&1 || echo "WARNING: nvidia-smi unavailable: verify NVIDIA runtime."
printf 'LIVEPORTRAIT_DATA_DIR=%s\nLIVEPORTRAIT_PORT=%s\n' "$DATA" "$PORT" > "$HERE/.env"
cd "$HERE"
COMPOSE=("${DOCKER[@]}" compose -p getac-liveportrait -f docker-compose.yml --env-file .env)
echo "[1/4] Building LivePortrait ARM64 Docker image..."
"${COMPOSE[@]}" build liveportrait
echo "[2/4] Checking/downloading official models..."
"${COMPOSE[@]}" run --rm --no-deps --entrypoint python liveportrait /opt/getac/download_models.py
echo "[3/4] Starting ONLY getac-liveportrait..."
"${COMPOSE[@]}" up -d --no-deps liveportrait
echo "[4/4] Checking port $PORT..."
READY=0
for i in $(seq 1 60); do
  if curl --noproxy '*' -fsS --max-time 3 "http://127.0.0.1:$PORT/health" >/dev/null; then READY=1; break; fi
  sleep 2
done
if [[ "$READY" != "1" ]]; then
  echo "ERROR: /health did not respond; container logs:" >&2
  "${COMPOSE[@]}" logs --tail 120 liveportrait
  exit 1
fi
curl --noproxy '*' -fsS "http://127.0.0.1:$PORT/health"
printf '\nSUCCESS: Open http://<GB10-IP>:%s/docs\nData directory: %s\n' "$PORT" "$DATA"
printf 'Other Docker services (EchoMimic, TTS, WhisperX, OCR, Qwen-Image) are untouched.\n'
printf 'The health endpoint alone does not prove successful GPU inference. See test_api.sh.\n'
