#!/usr/bin/env bash
# Offline standalone clip generation - v1.0.1.0
set -euo pipefail
cd /opt/echomimic_v3
IMG="${IMG:-/data/input/avatar.jpg}"
AUDIO="${AUDIO:-/data/input/speech.wav}"
OUT="${OUT:-/data/output}"
FRAMES="${FRAMES:-41}"
SIZE="${SIZE:-384}"
STEPS="${STEPS:-8}"
mkdir -p "$OUT"
test -f "$IMG" || { echo "Missing image $IMG"; exit 2; }
test -f "$AUDIO" || { echo "Missing audio $AUDIO"; exit 2; }
test -f /data/models/flash/transformer/diffusion_pytorch_model.safetensors || { echo "Download models first"; exit 3; }
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
python infer_flash.py \
  --image_path "$IMG" --audio_path "$AUDIO" \
  --prompt "A professional presenter speaks naturally, gentle blinking and subtle head movements." \
  --num_inference_steps "$STEPS" \
  --config_path config/config.yaml \
  --model_name /data/models/flash/Wan2.1-Fun-V1.1-1.3B-InP \
  --transformer_path /data/models/flash/transformer/diffusion_pytorch_model.safetensors \
  --wav2vec_model_dir /data/models/flash/chinese-wav2vec2-base \
  --save_path "$OUT" --sampler_name Flow_Unipc \
  --video_length "$FRAMES" --guidance_scale 5.0 \
  --audio_guidance_scale 2.0 --weight_dtype bfloat16 \
  --sample_size "$SIZE" "$SIZE" --fps 25 --seed 43
echo "Check output: $OUT/avatar_output.mp4"
