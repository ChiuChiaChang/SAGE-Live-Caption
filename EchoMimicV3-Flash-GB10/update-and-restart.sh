#!/usr/bin/env bash
# Getac ES SW Team - EchoMimicV3-Flash GB10 one-command hotfix
# Version 1.0.2.0 (2026-10-24)
# Only patches infer_flash.py inside the named container; no other containers touched.
# Docker restart keeps mounts/ports/volumes. Recreated containers need this fix reapplied.
set -Eeuo pipefail

CONTAINER="${ECHOMIMIC_CONTAINER:-getac-echomimicv3-flash}"
INFER_PATH="/opt/echomimic_v3/infer_flash.py"
HEALTH_URL="http://127.0.0.1:8300/health"
STAMP="$(date -u +%Y%m%d_%H%M%S_UTC)"
BACKUP_DIR="${HOME}/.local/share/getac-echomimic-backups/${STAMP}"
WORK_DIR="$(mktemp -d)"
COPIED=0
SUCCESS=0

cleanup() { rm -rf "${WORK_DIR}"; }
trap cleanup EXIT
log() { printf '\n[Getac EchoMimic 1.0.2.0] %s\n' "$*"; }
die() { printf '\n[ERROR] %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null || die "python3 is required on the GB10 host."
command -v curl >/dev/null || die "curl is required on the GB10 host."
command -v docker >/dev/null || die "Docker CLI is required on the GB10 host."
if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
else
  DOCKER=(sudo docker)
  "${DOCKER[@]}" info >/dev/null || die "Docker access failed (try sudo)."
fi
"${DOCKER[@]}" inspect "${CONTAINER}" >/dev/null 2>&1 ||
  die "Container not found: ${CONTAINER}"
RUNNING="$("${DOCKER[@]}" inspect -f '{{.State.Running}}' "${CONTAINER}")"
[[ "${RUNNING}" == "true" ]] || die "Container ${CONTAINER} is not running."

mkdir -p "${BACKUP_DIR}"
log "Step 1/5: backup ${CONTAINER}:${INFER_PATH}"
"${DOCKER[@]}" cp "${CONTAINER}:${INFER_PATH}" "${BACKUP_DIR}/infer_flash.py" ||
  die "Cannot read inference source from container."
cp "${BACKUP_DIR}/infer_flash.py" "${WORK_DIR}/infer_flash.py"

log "Step 2/5: patch checkpoint loading with assign=True (idempotent)"
python3 - "${WORK_DIR}/infer_flash.py" <<'PY'
import ast
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
original = re.compile(
    r"\btransformer\.load_state_dict\(\s*state_dict\s*,\s*strict\s*=\s*False\s*\)"
)
already = re.compile(
    r"\btransformer\.load_state_dict\(\s*state_dict\s*,\s*strict\s*=\s*False\s*,\s*assign\s*=\s*True\s*\)"
)
a = len(original.findall(source))
b = len(already.findall(source))
if a == 1 and b == 0:
    patched = original.sub(
        "transformer.load_state_dict(state_dict, strict=False, assign=True)",
        source, count=1
    )
    ast.parse(patched, filename=str(path))
    path.write_text(patched, encoding="utf-8")
    print("OK: changed transformer.load_state_dict(..., assign=True)")
elif a == 0 and b == 1:
    ast.parse(source, filename=str(path))
    print("OK: assign=True already present; patch is idempotent")
else:
    raise SystemExit(
        f"STOP: expected one exact load_state_dict statement; found original={a}, patched={b}. "
        "File unchanged. Review the version of infer_flash.py."
    )
PY

restore() {
  log "Attempting rollback to unmodified infer_flash.py"
  "${DOCKER[@]}" cp "${BACKUP_DIR}/infer_flash.py" "${CONTAINER}:${INFER_PATH}" || true
  "${DOCKER[@]}" restart "${CONTAINER}" >/dev/null || true
  printf '[Rollback] Original backup: %s\n' "${BACKUP_DIR}/infer_flash.py"
}
on_error() {
  local status=$?
  trap - ERR
  if [[ "${COPIED}" == "1" && "${SUCCESS}" != "1" ]]; then restore; fi
  exit "${status}"
}
trap on_error ERR

log "Step 3/5: copy verified Python file back to container"
"${DOCKER[@]}" cp "${WORK_DIR}/infer_flash.py" "${CONTAINER}:${INFER_PATH}" ||
  die "Could not copy patched source into container."
COPIED=1
if ! "${DOCKER[@]}" exec "${CONTAINER}" python3 -m py_compile "${INFER_PATH}"; then
  restore
  die "Python compile failed; original backed up at ${BACKUP_DIR}/infer_flash.py"
fi

log "Step 4/5: restart ONLY ${CONTAINER}"
"${DOCKER[@]}" restart "${CONTAINER}" >/dev/null
log "Step 5/5: verify /health on Port 8300"
READY=0
for attempt in $(seq 1 30); do
  if curl --noproxy '*' --silent --fail --max-time 3 "${HEALTH_URL}" >/dev/null; then
    READY=1
    break
  fi
  sleep 2
done
if [[ "${READY}" -ne 1 ]]; then
  restore
  die "EchoMimic failed health check after restart; rollback attempted."
fi
SUCCESS=1
log "SUCCESS: patched, container restarted and /health OK."
printf 'Container: %s\nBackup: %s\n' "${CONTAINER}" "${BACKUP_DIR}/infer_flash.py"
printf '\nNext: run a NEW 3-second presenter job in Windows Studio.\n'
printf 'If inference still fails, inspect the NEW job inference.log; /health does not prove GPU inference.\n'
printf '\nNOTE: Hotfix survives docker restart, NOT image rebuild/container recreation.\n'
printf '      Re-run this GitHub updater after recreating the container.\n'
