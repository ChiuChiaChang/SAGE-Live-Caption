# NVIDIA DGX Spark / GB10 ARM64 PyTorch base
FROM nvcr.io/nvidia/pytorch:25.11-py3
ARG LIVEPORTRAIT_COMMIT=9b294b3d0536135442ea73cb01e6cb3ca7029dd3
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_XET=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git ca-certificates libgl1 libglib2.0-0 libsm6 libxext6 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt
RUN git clone --filter=blob:none https://github.com/KlingAIResearch/LivePortrait.git liveportrait \
 && cd liveportrait && git checkout "$LIVEPORTRAIT_COMMIT"
# Weights live on persistent host storage. Upstream config expects pretrained_weights under its repo.
RUN rm -rf /opt/liveportrait/pretrained_weights && ln -s /data/models /opt/liveportrait/pretrained_weights
COPY requirements-gb10.txt /opt/getac/requirements-gb10.txt
# Keep NGC's preinstalled CUDA-enabled torch; do not install upstream's x86-era onnxruntime-gpu pin.
RUN python -m pip install --no-cache-dir -r /opt/getac/requirements-gb10.txt
COPY server.py download_models.py patch_arm64.py /opt/getac/
RUN python /opt/getac/patch_arm64.py
WORKDIR /opt/liveportrait
EXPOSE 8400
CMD ["python", "-m", "uvicorn", "server:app", "--app-dir", "/opt/getac", "--host", "0.0.0.0", "--port", "8400", "--workers", "1"]
