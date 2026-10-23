# Getac EchoMimicV3-Flash on NVIDIA GB10 (ARM64) - v1.0.1.0
# Experimental compatibility layer, not an official validated GB10 build.
FROM nvcr.io/nvidia/pytorch:25.11-py3
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_DISABLE_TELEMETRY=1 TOKENIZERS_PARALLELISM=false \
    ECHOMIMIC_FORCE_SDPA=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl ca-certificates libglib2.0-0 libgl1 libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/echomimic_v3
RUN git clone --depth 1 https://github.com/antgroup/echomimic_v3.git . \
    && git rev-parse HEAD > /opt/echomimic-upstream-commit.txt
# Keep NVIDIA-provided ARM64/CUDA PyTorch. Do not install upstream requirements.txt:
# it includes an older TensorFlow and optional dependencies incompatible with ARM64.
RUN python -m pip install --no-cache-dir \
    'huggingface_hub>=0.30,<1.0' 'transformers==4.51.3' \
    'diffusers==0.34.0' 'accelerate>=1.4,<2' \
    'Pillow' 'einops' 'safetensors' 'timm' 'tomesd' 'torchdiffeq' \
    'torchsde' 'numpy' 'scipy' 'scikit-image' 'opencv-python-headless' \
    'omegaconf' 'sentencepiece' 'imageio[ffmpeg]' 'ftfy' \
    'moviepy==2.2.1' 'librosa>=0.10.2' 'pyloudnorm' 'soundfile' \
    'fastapi>=0.115,<1' 'uvicorn>=0.32,<1' 'python-multipart'
# Use PyTorch SDPA instead of arch-specific flash-attn wheels. decord is not
# referenced in the infer_flash.py inference path except as an unused import.
RUN python - <<'PY'
from pathlib import Path
p=Path('/opt/echomimic_v3/infer_flash.py')
s=p.read_text()
if 'import decord' in s:
    p.write_text(s.replace('import decord', '# GB10: unused decord import'))
for name in ('src/wan_transformer3d_audio_2512.py','src/wan_transformer3d_audio.py'):
    q=Path(name)
    if not q.is_file():
        continue
    s=q.read_text()
    s=s.replace('    import flash_attn_interface\n', '    raise ModuleNotFoundError("GB10: use PyTorch SDPA")\n    import flash_attn_interface\n')
    s=s.replace('    import flash_attn\n', '    raise ModuleNotFoundError("GB10: use PyTorch SDPA")\n    import flash_attn\n')
    q.write_text(s)
print('ARM64/SDPA compatibility changes applied')
PY
COPY api.py download_models.py run_test.sh /opt/tools/
RUN chmod +x /opt/tools/run_test.sh
EXPOSE 8300
CMD ["uvicorn", "api:app", "--app-dir", "/opt/tools", "--host", "0.0.0.0", "--port", "8300", "--workers", "1"]
