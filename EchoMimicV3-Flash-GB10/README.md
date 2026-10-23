# Getac EchoMimicV3-Flash for NVIDIA GB10 · v1.0.1.0

**Experimental ARM64/CUDA compatibility package**; verified as Python/Bash source, **not yet tested on an actual GB10**. It does not stop or modify the existing Getac WhisperX, Qwen3-TTS, OCR or Image API containers.

- Dedicated Docker image: `getac-echomimicv3-flash:1.0.1.0`
- Container: `getac-echomimicv3-flash`
- Local-only API: `http://127.0.0.1:8300`
- NVIDIA official DGX Spark PyTorch base: `nvcr.io/nvidia/pytorch:25.11-py3`
- Offline inference after a one-time model download
- API generation: **1–3.2 seconds of audio per job**, queued for one GPU

## Copy directly to GB10; no ZIP or WinSCP

```bash
cd ~
git clone -b echomimicv3-flash-gb10-v1 --single-branch https://github.com/ChiuChiaChang/SAGE-Live-Caption.git
cd SAGE-Live-Caption/EchoMimicV3-Flash-GB10
bash setup.sh
```

**Requirements:** GB10 ARM64, NVIDIA Container Toolkit, Docker Compose v2, internet for first install, at least ~50GB free disk space. The base model, Flash checkpoint and Wav2Vec2 encoder are downloaded at setup time and are **not committed to GitHub**. Validate available RAM; on a 128GB unified-memory GB10 other running GPU processes can cause OOM.

### Basic check

```bash
sudo docker ps --filter name=getac-echomimicv3-flash
curl http://127.0.0.1:8300/health
```

A healthy API does **not** mean a complete GPU generation has been validated. Use the short-clip test below.

## First MP4 (offline)

Place **authorized** presenter portrait as `input/avatar.jpg` and a **2-second** WAV as `input/speech.wav`. Re-encode a sample, if necessary:

```bash
ffmpeg -y -i my-voice.wav -t 2 -ac 1 -ar 16000 -c:a pcm_s16le input/speech.wav
```

Then:

```bash
sudo docker run --rm --gpus all --ipc=host \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  -v "$PWD/models:/data/models:ro" \
  -v "$PWD/input:/data/input:ro" \
  -v "$PWD/output:/data/output" \
  getac-echomimicv3-flash:1.0.1.0 bash /opt/tools/run_test.sh
```

The output is `output/avatar_output.mp4`; move an earlier result before rerunning, because upstream inference skips existing files.

## API (already started by setup.sh)

- `GET /health`
- `GET /docs` (Swagger API test page)
- `POST /api/presenter/create` — form fields `avatar` and `audio`
- `GET /api/presenter/status/{job_id}`
- `GET /api/presenter/result/{job_id}`

Example:

```bash
curl -X POST http://127.0.0.1:8300/api/presenter/create \
  -F "avatar=@input/avatar.jpg" -F "audio=@input/speech.wav"
```

Jobs run one at a time to avoid competing GPU work. For Windows Voice Studio clients, create an SSH tunnel `ssh -L 8300:127.0.0.1:8300 corin@YOUR_GB10_IP` and use `http://127.0.0.1:8300/docs`. Do not expose this prototype API on the public Internet without authentication and network access controls.

## Troubleshooting / limits

```bash
sudo docker compose logs --tail=100
free -h
sudo docker ps
```

- The upstream `infer_flash.py` is designed for short clip generation and is currently invoked separately for each job. Joining many clips into a single 20–30 second PowerPoint narration **is not yet implemented**.
- FlashAttn is replaced with PyTorch SDPA to avoid prebuilt x86-only CUDA wheels.
- The upstream `requirements.txt` contains older TensorFlow and optional packages; this deployment installs the inference dependencies separately.
- Official upstream lists A100, RTX4090D and V100 as tested GPUs; **GB10 is not officially verified**. Build or runtime adjustments may still be required.

Sources: https://github.com/antgroup/echomimic_v3 · https://github.com/antgroup/echomimic_v3/blob/main/run_flash.sh · https://github.com/NVIDIA/dgx-spark-playbooks
