#!/usr/bin/env python3
"""Download official EchoMimicV3 Flash-Pro components for fully offline use.
Version: 1.0.1.0. Online only during installation.
"""
from pathlib import Path
from huggingface_hub import snapshot_download

root = Path("/data/models/flash")
root.mkdir(parents=True, exist_ok=True)

def fetch(repo_id, directory, allow_patterns=None):
    dest = root / directory
    dest.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {repo_id} => {dest}", flush=True)
    snapshot_download(repo_id=repo_id, local_dir=str(dest), allow_patterns=allow_patterns)
    return dest

base = fetch("alibaba-pai/Wan2.1-Fun-V1.1-1.3B-InP", "Wan2.1-Fun-V1.1-1.3B-InP")
audio = fetch("TencentGameMate/chinese-wav2vec2-base", "chinese-wav2vec2-base",
              ["config.json", "preprocessor_config.json", "pytorch_model.bin", "*.safetensors"])
flash = fetch("BadToBest/EchoMimicV3", "echomimicv3_repository",
              ["echomimicv3-flash-pro/*"])
source = flash / "echomimicv3-flash-pro/diffusion_pytorch_model.safetensors"
target = root / "transformer/diffusion_pytorch_model.safetensors"
target.parent.mkdir(parents=True, exist_ok=True)
if not source.is_file():
    raise FileNotFoundError(f"Flash checkpoint not found: {source}")
# Avoid storing a second 3.7GB copy.
relative_source = Path("../echomimicv3_repository/echomimicv3-flash-pro/diffusion_pytorch_model.safetensors")
if target.is_symlink() or target.exists():
    target.unlink()
target.symlink_to(relative_source)

required = [
    base / "config.json",
    base / "diffusion_pytorch_model.safetensors",
    base / "Wan2.1_VAE.pth",
    base / "models_t5_umt5-xxl-enc-bf16.pth",
    base / "models_clip_open-clip-xlm-roberta-large-vit-huge-14.pth",
    base / "google/umt5-xxl/tokenizer_config.json",
    audio / "config.json",
    audio / "preprocessor_config.json",
    target,
]
missing = [str(p) for p in required if not p.is_file()]
if not ((audio / "pytorch_model.bin").is_file() or
        (audio / "model.safetensors").is_file()):
    missing.append(str(audio / "pytorch_model.bin or model.safetensors"))
if missing:
    raise RuntimeError("Missing downloaded model files:\n" + "\n".join(missing))
print("Model files ready. Inference can now run offline.")
