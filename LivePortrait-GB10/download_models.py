#!/usr/bin/env python3
"""Fetch official model weights into persistent /data/models."""
from pathlib import Path
import os
import sys
from huggingface_hub import snapshot_download

root = Path(os.environ.get("LIVEPORTRAIT_DATA", "/data")) / "models"
root.mkdir(parents=True, exist_ok=True)
paths = [
    "liveportrait/base_models/appearance_feature_extractor.pth",
    "liveportrait/base_models/motion_extractor.pth",
    "liveportrait/base_models/spade_generator.pth",
    "liveportrait/base_models/warping_module.pth",
    "liveportrait/retargeting_models/stitching_retargeting_module.pth",
    "liveportrait/landmark.onnx",
    "insightface/models/buffalo_l/det_10g.onnx",
    "insightface/models/buffalo_l/2d106det.onnx",
]
if not all((root / p).is_file() and (root / p).stat().st_size > 100_000 for p in paths):
    print("Downloading https://huggingface.co/KwaiVGI/LivePortrait ...", flush=True)
    snapshot_download(repo_id="KwaiVGI/LivePortrait", repo_type="model", local_dir=str(root), allow_patterns=["liveportrait/**", "insightface/**"])
missing = [p for p in paths if not (root / p).is_file() or (root / p).stat().st_size <= 100_000]
if missing:
    print("ERROR: missing weights: " + ", ".join(missing), file=sys.stderr)
    sys.exit(1)
print(f"Verified {len(paths)} official model files under {root}", flush=True)
