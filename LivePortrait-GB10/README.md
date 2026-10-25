# Getac LivePortrait GB10 API v1.0.0.0

Target: NVIDIA GB10 / DGX Spark, Linux ARM64, API port 8400.

## One-command GB10 installation/update

Run on GB10 Linux terminal:

    curl -fL --retry 3 https://raw.githubusercontent.com/ChiuChiaChang/SAGE-Live-Caption/main/LivePortrait-GB10/install.sh -o /tmp/getac-liveportrait-install.sh && bash /tmp/getac-liveportrait-install.sh

The installer downloads only the LivePortrait-GB10 source folder from your GitHub, builds a GB10 PyTorch Docker image, downloads official weights to persistent host storage, starts only the getac-liveportrait container and checks /health.

Requirements: Docker and Docker Compose v2, NVIDIA GPU container integration, Git, curl, access to NVIDIA NGC, GitHub, PyPI, and Hugging Face, and space for the Docker image and models.

## API

- GET http://GB10-IP:8400/health -- reports model file readiness, NOT inference success.
- GET http://GB10-IP:8400/docs -- Swagger interface.
- POST /api/portrait/create -- multipart fields source (PNG/JPEG, <=12 MB), driving (MP4/MOV, <=80 MB, <=35 s), animation_region (exp default, lip, eyes, all), driving_multiplier (0.7 default).
- GET /api/portrait/status/{job_id} -- queued, running, completed or failed.
- GET /api/portrait/result/{job_id} -- binary result MP4.
- GET /api/portrait/log/{job_id} -- inference.log.

Only ONE GPU inference subprocess runs at a time. Max four queued/running jobs. Each subprocess exits after inference to release memory.

## First actual GPU test

Copy a source portrait photo and a short driving MP4 (for example, 3-second EchoMimic output) to GB10:

    bash "$HOME/.local/share/getac-liveportrait-github/LivePortrait-GB10/test_api.sh" "/path/presenter.png" "/path/echomimic_3s.mp4"

The script uploads both files, polls progress and downloads liveportrait_JOBID.mp4.

IMPORTANT: LivePortrait uses a driving VIDEO, not WAV. Intended future pipeline: Qwen3-TTS 8100 -> EchoMimic 8300 -> LivePortrait 8400 -> PPT Studio.

IMPORTANT: LivePortrait generates RGB MP4, not transparent-alpha MP4. Your Studio still needs alpha matting or a suitable mask to composite a transparent presenter. The exp region helps limit motion but does not guarantee fixed shoulders.

## Data and operations

Checkout: ~/.local/share/getac-liveportrait-github/LivePortrait-GB10
Persistent weights: ~/getac-liveportrait-data/models/
Jobs/results/logs: ~/getac-liveportrait-data/jobs/

    sudo docker ps --filter name=getac-liveportrait
    sudo docker logs --tail 100 getac-liveportrait
    curl -fsS http://127.0.0.1:8400/health

Rerun the same one-line installer to update. It does not stop, rebuild or restart EchoMimic, Qwen3-TTS, WhisperX, Qwen-Image or OCR.

## Sources and compatibility

- Base image: nvcr.io/nvidia/pytorch:25.11-py3, recommended for DGX Spark by NVIDIA.
- LivePortrait source pinned to KlingAIResearch/LivePortrait commit 9b294b3d0536135442ea73cb01e6cb3ca7029dd3.
- Official HF models: KwaiVGI/LivePortrait. Stored under /data/models and linked into upstream pretrained_weights.
- ARM64 compatible CPU face detector: onnxruntime==1.23.2; NVIDIA image retains CUDA PyTorch.

## License and security warnings

- LivePortrait code is MIT. Official LICENSE says the bundled InsightFace pretrained models are NON-COMMERCIAL research only. Replace or license these for commercial/customer use.
- Models are not automatically licensed for commercial use merely because downloading is free.
- Current prototype binds 0.0.0.0:8400 without API authentication. Trusted internal LAN/VPN and firewall ONLY. Never expose to public Internet.

## Verification status

Only repository and static syntax checks; no actual run on your physical GB10 yet. GET /health is NOT proof of successful GPU inference. Check /api/portrait/log/{job_id} on job failure.
