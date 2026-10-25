#!/usr/bin/env bash
# Test actual LivePortrait inference from GB10 or another LAN client
# Usage: bash test_api.sh SOURCE.png DRIVING.mp4 [http://GB10-IP:8400]
set -Eeuo pipefail
SRC="${1:?Usage: bash test_api.sh SOURCE.png DRIVING.mp4 [URL]}"
DRV="${2:?Usage: bash test_api.sh SOURCE.png DRIVING.mp4 [URL]}"
BASE="${3:-http://127.0.0.1:8400}"
[[ -f "$SRC" && -f "$DRV" ]] || { echo "ERROR: both source files must exist"; exit 1; }
command -v python3 >/dev/null
command -v curl >/dev/null
echo "Server: $BASE"
curl -fsS "$BASE/health" && echo
echo "Submitting SOURCE image + DRIVING video (NOT WAV)..."
RESPONSE="$(curl -fsS -X POST "$BASE/api/portrait/create" \
  -F "source=@$SRC" -F "driving=@$DRV" \
  -F "animation_region=exp" -F "driving_multiplier=0.7")"
echo "$RESPONSE"
JOB_ID="$(printf '%s' "$RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"
echo "Job: $JOB_ID"
for i in $(seq 1 240); do
  RESPONSE="$(curl -fsS "$BASE/api/portrait/status/$JOB_ID")"
  STATUS="$(printf '%s' "$RESPONSE" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
  echo "[$i] $STATUS"
  if [[ "$STATUS" == "completed" ]]; then
    OUT="liveportrait_$JOB_ID.mp4"
    curl -fsS "$BASE/api/portrait/result/$JOB_ID" -o "$OUT"
    echo "SUCCESS: $OUT"
    exit 0
  fi
  if [[ "$STATUS" == "failed" ]]; then
    echo "$RESPONSE"
    curl -fsS "$BASE/api/portrait/log/$JOB_ID" -o "liveportrait_$JOB_ID.log" || true
    echo "FAILED: see liveportrait_$JOB_ID.log"
    exit 1
  fi
  sleep 3
done
echo "Timed out waiting for job. Last status: $RESPONSE"
exit 1
