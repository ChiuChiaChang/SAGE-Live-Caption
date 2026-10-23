"""Getac EchoMimicV3-Flash GB10 - FastAPI v1.0.1.0.
Single GPU worker, offline model inference, short clips only.
Prototype must not be exposed directly to the public Internet.
"""
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue, Full
from threading import Thread
from uuid import uuid4
import json
import os
import subprocess
import traceback

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, ImageOps

VERSION = "1.0.1.0"
ROOT = Path("/data/jobs")
ROOT.mkdir(parents=True, exist_ok=True)
REPO = Path("/opt/echomimic_v3")
MODELS = Path("/data/models/flash")
QUEUE = Queue(maxsize=16)
app = FastAPI(title="Getac EchoMimicV3-Flash GB10", version=VERSION)

def job_path(job_id: str) -> Path:
    if len(job_id) != 32 or any(c not in "0123456789abcdef" for c in job_id):
        raise HTTPException(status_code=404, detail="Unknown job ID")
    return ROOT / job_id

def update_state(job_id: str, status: str, **fields):
    path = job_path(job_id) / "status.json"
    data = json.loads(path.read_text()) if path.exists() else {"job_id": job_id}
    data.update(status=status, updated_at=datetime.now(timezone.utc).isoformat(), **fields)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return data

def make_cmd(folder: Path):
    return [
        "python", "infer_flash.py",
        "--image_path", str(folder / "avatar.jpg"),
        "--audio_path", str(folder / "speech.wav"),
        "--prompt", "A professional presenter speaks naturally, with subtle blinking and head movements.",
        "--num_inference_steps", "8",
        "--config_path", "config/config.yaml",
        "--model_name", str(MODELS / "Wan2.1-Fun-V1.1-1.3B-InP"),
        "--transformer_path", str(MODELS / "transformer/diffusion_pytorch_model.safetensors"),
        "--wav2vec_model_dir", str(MODELS / "chinese-wav2vec2-base"),
        "--save_path", str(folder),
        "--sampler_name", "Flow_Unipc",
        "--video_length", "81", "--guidance_scale", "5.0",
        "--audio_guidance_scale", "2.0", "--weight_dtype", "bfloat16",
        "--sample_size", "384", "384", "--fps", "25", "--seed", "43"
    ]

def gpu_worker():
    while True:
        job_id = QUEUE.get()
        folder = job_path(job_id)
        try:
            update_state(job_id, "running")
            env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                       HF_HUB_DISABLE_TELEMETRY="1")
            with (folder / "inference.log").open("w") as logfile:
                process = subprocess.run(make_cmd(folder), cwd=REPO, env=env,
                                         stdout=logfile, stderr=subprocess.STDOUT)
            video = folder / "avatar_output.mp4"
            if process.returncode != 0 or not video.is_file():
                raise RuntimeError(f"Model generation failed (exit={process.returncode}); see inference.log")
            update_state(job_id, "completed", result_url=f"/api/presenter/result/{job_id}")
        except Exception as exc:
            (folder / "error.log").write_text(traceback.format_exc())
            update_state(job_id, "failed", error=str(exc))
        finally:
            QUEUE.task_done()

@app.on_event("startup")
def start():
    Thread(target=gpu_worker, daemon=True, name="getac-echo-gpu").start()

@app.get("/health")
def health():
    return {"status": "ok", "version": VERSION, "offline": True,
            "model_downloaded": (MODELS / "transformer/diffusion_pytorch_model.safetensors").is_file(),
            "queue_depth": QUEUE.qsize()}

@app.post("/api/presenter/create", status_code=202)
def create(avatar: UploadFile = File(...), audio: UploadFile = File(...)):
    if QUEUE.full():
        raise HTTPException(status_code=503, detail="GPU job queue is full")
    photo = avatar.file.read(20 * 1024 * 1024 + 1)
    sound = audio.file.read(30 * 1024 * 1024 + 1)
    if len(photo) > 20 * 1024 * 1024 or len(sound) > 30 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Input too large")
    jid = uuid4().hex
    folder = job_path(jid)
    folder.mkdir(parents=True)
    rawimage = folder / "uploaded_image"
    rawimage.write_bytes(photo)
    try:
        with Image.open(rawimage) as img:
            ImageOps.fit(img.convert("RGB"), (384, 384),
                         method=Image.Resampling.LANCZOS).save(folder / "avatar.jpg", quality=95)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid portrait image")
    original = folder / "uploaded_audio"
    original.write_bytes(sound)
    conversion = subprocess.run(
        ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
         "-i", str(original), "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
         str(folder / "speech.wav")],
        capture_output=True, text=True)
    if conversion.returncode:
        raise HTTPException(status_code=400, detail="Invalid audio")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1",
         str(folder / "speech.wav")], capture_output=True, text=True)
    try:
        length = float(probe.stdout.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Audio duration unavailable")
    if not (1.0 <= length <= 3.2):
        raise HTTPException(status_code=400,
                            detail="Prototype accepts only 1.0–3.2 seconds of audio. Longer PPT segments are not yet supported.")
    update_state(jid, "queued", audio_seconds=round(length, 2))
    try:
        QUEUE.put_nowait(jid)
    except Full:
        update_state(jid, "rejected")
        raise HTTPException(status_code=503, detail="Queue full")
    return {"job_id": jid, "status": "queued",
            "status_url": f"/api/presenter/status/{jid}"}

@app.get("/api/presenter/status/{job_id}")
def status(job_id: str):
    p = job_path(job_id) / "status.json"
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Unknown job ID")
    return json.loads(p.read_text())

@app.get("/api/presenter/result/{job_id}")
def result(job_id: str):
    p = job_path(job_id) / "status.json"
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Unknown job ID")
    if json.loads(p.read_text()).get("status") != "completed":
        raise HTTPException(status_code=409, detail="Job not completed")
    video = job_path(job_id) / "avatar_output.mp4"
    if not video.is_file():
        raise HTTPException(status_code=404, detail="Video missing")
    return FileResponse(video, media_type="video/mp4",
                        filename=f"presenter_{job_id}.mp4")
