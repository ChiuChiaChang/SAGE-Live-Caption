#!/usr/bin/env bash
# Getac LivePortrait GB10 one-line installer v1.0.0.0
set -Eeuo pipefail
SOURCE="${HOME}/.local/share/getac-liveportrait-github"
URL="https://github.com/ChiuChiaChang/SAGE-Live-Caption.git"
command -v git >/dev/null || { echo "ERROR: install git first (sudo apt install git)"; exit 1; }
if [[ -d "${SOURCE}/.git" ]]; then
  echo "[1/2] Updating from GitHub..."
  git -C "${SOURCE}" pull --ff-only origin main
else
  echo "[1/2] Cloning from GitHub with sparse checkout..."
  mkdir -p "$(dirname "${SOURCE}")"
  git clone --depth=1 --filter=blob:none --sparse --branch main "${URL}" "${SOURCE}"
fi
git -C "${SOURCE}" sparse-checkout set LivePortrait-GB10
echo "[2/2] Deploying on GB10..."
exec bash "${SOURCE}/LivePortrait-GB10/deploy.sh"
