"""Getac LivePortrait GB10 API v1.0.0.0.

Upload source image + driving VIDEO (not WAV) => asynchronous LivePortrait job.
Single queued worker ensures only one GPU inference process runs at a time.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError

VERSION = "1.0.0.0"
DATA = Path(os.getenv("LIVEPORTRAIT_DATA", "/data")).resolve()
JOBS = DATA / "jobs"
MODELS = DATA / "models"
JOBS.mkdir(parents=True, exist_ok=True)
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="liveportrait-gpu")
queue_lock = threading.Lock()
queued_count = 0
MAX_QUEUED = 4
MAX_IMAGE = 12 * 1024 * 1024
MAX_VIDEO = 80 * 1024 * 1024
MAX_VIDEO_SECONDS = 35.0
REQUIRED = [
    "liveportrait/base_models/appearance_feature_extractor.pth",
    "liveportrait/base_models/motion_extractor.pth",
    "liveportrait/base_models/spade_generator.pth",
    "liveportrait/base_models/warping_module.pth",
    "liveportrait/retargeting_models/stitching_retargeting_module.pth",
    "liveportrait/landmark.onnx",
    "insightface/models/buffalo_l/det_10g.onnx",
    "insightface/models/buffalo_l/2d106det.onnx",
]

app = FastAPI(
    title="Getac LivePortrait GB10 API",
    description="Source portrait image + driving MP4 => retargeted portrait MP4. "
                "Not an audio-to-video service. Optional original-alpha postprocessing is not yet included.",
    version=VERSION,
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def model_missing() -> list[str]:
    return [p for p in REQUIRED if not (MODELS / p).is_file() or (MODELS / p).stat().st_size < 100000]


def metadata_path(job_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(400, "Invalid job ID.")
    return JOBS / job_id / "job.json"


def read_job(job_id: str) -> dict:
    path = metadata_path(job_id)
    if not path.is_file():
        raise HTTPException(404, "Unknown job ID.")
    return json.loads(path.read_text(encoding="utf-8"))


def write_job(job_id: str, meta: dict) -> None:
    path = metadata_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    meta["updated_at"] = now()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


@app.on_event("startup")
def restart_recovery() -> None:
    # A running subprocess does not survive docker recreate. Mark old unfinished jobs.
    for file in JOBS.glob("*/job.json"):
        try:
            meta = json.loads(file.read_text(encoding="utf-8"))
            if meta.get("status") in ("queued", "running"):
                meta["status"] = "failed"
                meta["error"] = "Interrupted by API/Docker restart. Resubmit the job."
                write_job(meta["job_id"], meta)
        except Exception:
            pass


@app.get("/health")
def health() -> dict:
    missing = model_missing()
    return {
        "status": "ready" if not missing else "models_missing",
        "version": VERSION,
        "gpu_runtime": "NVIDIA GB10 / ARM64",
        "model_files_ready": not missing,
        "missing_model_files": missing,
        "jobs_pending_in_this_process": queued_count,
        "note": "HTTP health is not proof of successful GPU inference. POST a sample job.",
    }


@app.get("/api/portrait/status/{job_id}")
def status(job_id: str) -> dict:
    return read_job(job_id)


@app.get("/api/portrait/result/{job_id}")
def result(job_id: str):
    meta = read_job(job_id)
    if meta["status"] != "completed":
        raise HTTPException(409, f"Job not completed: {meta['status']}")
    file = JOBS / job_id / "result.mp4"
    if not file.is_file() or file.stat().st_size == 0:
        raise HTTPException(500, "Job completed, but output MP4 is missing.")
    return FileResponse(file, media_type="video/mp4", filename=f"liveportrait_{job_id}.mp4")


@app.get("/api/portrait/log/{job_id}")
def log_file(job_id: str):
    _ = read_job(job_id)
    file = JOBS / job_id / "inference.log"
    if not file.is_file():
        raise HTTPException(404, "No inference log is available yet.")
    return FileResponse(file, media_type="text/plain", filename=f"{job_id}_inference.log")


async def save_upload(upload: UploadFile, dest: Path, limit: int) -> None:
    written = 0
    with dest.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            written += len(chunk)
            if written > limit:
                raise HTTPException(413, "Uploaded file is too large.")
            out.write(chunk)
    if not written:
        raise HTTPException(400, "Uploaded file is empty.")


def video_seconds(path: Path) -> float:
    cp = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        text=True, capture_output=True, timeout=15, check=False
    )
    if cp.returncode:
        raise HTTPException(400, "Invalid driving video (ffprobe failed).")
    try:
        duration = float(cp.stdout.strip())
    except ValueError as exc:
        raise HTTPException(400, "Could not determine driving video duration.") from exc
    if not 0.1 <= duration <= MAX_VIDEO_SECONDS:
        raise HTTPException(400, f"Driving video must be 0.1 to {MAX_VIDEO_SECONDS} seconds.")
    return duration


def do_job(job_id: str, region: str, multiplier: float) -> None:
    global queued_count
    folder = JOBS / job_id
    meta = read_job(job_id)
    meta["status"] = "running"
    write_job(job_id, meta)
    cmd = [
        "python", "-u", "/opt/liveportrait/inference.py",
        "-s", str(folder / "source.png"),
        "-d", str(folder / "driving.mp4"),
        "-o", str(folder / "animation"),
        "--animation-region", region,
        "--driving-option", "expression-friendly",
        "--driving-multiplier", str(multiplier),
        "--flag-crop-driving-video",
    ]
    try:
        with (folder / "inference.log").open("w", encoding="utf-8") as output:
            output.write("Command: " + " ".join(cmd) + "\n\n")
            output.flush()
            cp = subprocess.run(
                cmd, cwd="/opt/liveportrait", stdout=output, stderr=subprocess.STDOUT,
                timeout=1200, check=False, env=os.environ.copy(),
            )
        if cp.returncode != 0:
            raise RuntimeError(f"LivePortrait inference failed (exit={cp.returncode}); see inference.log.")
        choices = [
            p for p in (folder / "animation").glob("*.mp4")
            if "_concat" not in p.name and "_with_audio" not in p.name
        ]
        if not choices:
            raise RuntimeError("Inference exited successfully but no generated MP4 was found.")
        shutil.copy2(max(choices, key=lambda p: p.stat().st_mtime), folder / "result.mp4")
        if (folder / "result.mp4").stat().st_size == 0:
            raise RuntimeError("Output MP4 is empty.")
        meta = read_job(job_id)
        meta["status"] = "completed"
        meta["result_url"] = f"/api/portrait/result/{job_id}"
        write_job(job_id, meta)
    except Exception as exc:
        meta = read_job(job_id)
        meta["status"] = "failed"
        meta["error"] = str(exc)
        write_job(job_id, meta)
        with (folder / "inference.log").open("a", encoding="utf-8") as output:
            output.write("\n\nSERVER ERROR:\n" + traceback.format_exc())
    finally:
        with queue_lock:
            queued_count -= 1


@app.post("/api/portrait/create", status_code=202)
async def create(
    source: UploadFile = File(..., description="Source portrait PNG or JPG"),
    driving: UploadFile = File(..., description="Driving MP4 video with face movement (NOT WAV)"),
    animation_region: Literal["exp", "lip", "eyes", "all"] = Form("exp"),
    driving_multiplier: float = Form(0.7),
):
    global queued_count
    if model_missing():
        raise HTTPException(503, "Model weights are missing; run the deploy installer again.")
    if not 0.1 <= driving_multiplier <= 1.5:
        raise HTTPException(400, "driving_multiplier must be 0.1 to 1.5.")
    if not source.filename or not driving.filename:
        raise HTTPException(400, "Both source and driving must have filenames.")
    if Path(source.filename).suffix.lower() not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(400, "Source must be PNG or JPEG.")
    if Path(driving.filename).suffix.lower() not in (".mp4", ".mov"):
        raise HTTPException(400, "Driving must be MP4 or MOV (not audio).")
    with queue_lock:
        if queued_count >= MAX_QUEUED:
            raise HTTPException(429, "GPU job queue is full. Try again later.")
        queued_count += 1
    job_id = uuid.uuid4().hex
    folder = JOBS / job_id
    folder.mkdir(parents=True, exist_ok=False)
    try:
        raw_img = folder / "source_upload"
        await save_upload(source, raw_img, MAX_IMAGE)
        try:
            with Image.open(raw_img) as im:
                im.verify()
            with Image.open(raw_img) as im:
                rgb = Image.new("RGB", im.size, (255, 255, 255))
                if im.mode == "RGBA":
                    rgb.paste(im, mask=im.getchannel("A"))
                else:
                    rgb.paste(im.convert("RGB"))
                if max(rgb.size) > 2048:
                    rgb.thumbnail((2048, 2048))
                rgb.save(folder / "source.png")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise HTTPException(400, "Uploaded source is not a readable image.") from exc
        raw_img.unlink(missing_ok=True)
        await save_upload(driving, folder / "driving.mp4", MAX_VIDEO)
        duration = video_seconds(folder / "driving.mp4")
        meta = {
            "job_id": job_id, "status": "queued", "created_at": now(),
            "driver_duration_seconds": round(duration, 3),
            "animation_region": animation_region,
            "driving_multiplier": driving_multiplier,
            "note": "Generated MP4 is RGB, not a transparent-alpha file.",
        }
        write_job(job_id, meta)
        executor.submit(do_job, job_id, animation_region, driving_multiplier)
        return {"job_id": job_id, "status": "queued",
                "status_url": f"/api/portrait/status/{job_id}",
                "result_url": f"/api/portrait/result/{job_id}"}
    except Exception:
        with queue_lock:
            queued_count -= 1
        shutil.rmtree(folder, ignore_errors=True)
        raise
