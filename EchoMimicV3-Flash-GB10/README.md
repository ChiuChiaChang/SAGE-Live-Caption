# Getac EchoMimicV3-Flash GB10 — one-command update (v1.0.2.0)

Maintained as a targeted GB10 hotfix by Getac ES SW Team.

## One command on your GB10

Run from any directory on the GB10 Linux host:

    curl -fL --retry 3 https://raw.githubusercontent.com/ChiuChiaChang/SAGE-Live-Caption/main/EchoMimicV3-Flash-GB10/update-and-restart.sh -o /tmp/getac-echomimic-update.sh && bash /tmp/getac-echomimic-update.sh

The command downloads the script from your GitHub before executing it. You may review the downloaded script beforehand.

## What it does

1. Locates the existing container named getac-echomimicv3-flash.
2. Copies the container's /opt/echomimic_v3/infer_flash.py to a timestamped backup at ~/.local/share/getac-echomimic-backups/.
3. Applies one exact, repeatable PyTorch fix: transformer.load_state_dict(state_dict, strict=False) to transformer.load_state_dict(state_dict, strict=False, assign=True).
4. Parses and Python-compiles the patched source.
5. Restarts ONLY getac-echomimicv3-flash. Qwen3-TTS, WhisperX, OCR and other Docker services are untouched.
6. Checks http://127.0.0.1:8300/health and attempts rollback on a failed health check.

## Why

The failing GB10 inference job hit this exception in infer_flash.py when moving the model to GPU:

    NotImplementedError: Cannot copy out of meta tensor; no data!
    pipeline.to(device=device)

Earlier warnings report checkpoint weights copying to meta parameters as a no-op.
Passing assign=True is an appropriate initial fix in this checkpoint-loading path; it does not guarantee there are no additional model problems.

## Important limitations

- This hotfix does NOT build a new Docker image or recreate the container.
- A hotfix to the writable container layer **survives docker restart** but does NOT survive removal, docker compose up --force-recreate, or an image rebuild from an unpatched source.
- /health HTTP 200 checks the web service, not model generation. Create a NEW 3-second Presenter test in Windows Studio and check that the job succeeds.
- The current SAGE-Live-Caption GitHub main branch does not yet contain your full local EchoMimic GB10 Dockerfile/build context. Committing those sources to GitHub and rebuilding an immutable image is a separate, future step.

## Verify

    sudo docker ps --filter name=getac-echomimicv3-flash
    sudo docker exec getac-echomimicv3-flash grep -n transformer.load_state_dict /opt/echomimic_v3/infer_flash.py
    curl -f http://127.0.0.1:8300/health

Static design review only: cannot reach the user's private 10.61.*.* GB10 server.
