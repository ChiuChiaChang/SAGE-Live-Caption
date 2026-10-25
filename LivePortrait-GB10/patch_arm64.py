#!/usr/bin/env python3
"""Safely adapt official LivePortrait's face detection to available ONNX Runtime providers.

NVIDIA PyTorch still runs on CUDA. For GB10/aarch64 we install ORT CPU and must
use CPUExecutionProvider for both bundled InsightFace and landmark detectors.
"""
from pathlib import Path
p = Path("/opt/liveportrait/src/utils/cropper.py")
text = p.read_text(encoding="utf-8")
needle = "        self.face_analysis_wrapper = FaceAnalysisDIY("
add = (
    "        # Getac GB10 ARM64: ONNX Runtime CPU for detection only; PyTorch stays CUDA.\n"
    "        import onnxruntime as ort\n"
    "        if 'CUDAExecutionProvider' not in ort.get_available_providers():\n"
    "            face_analysis_wrapper_provider = ['CPUExecutionProvider']\n"
    "            device = 'cpu'\n\n"
)
if text.count(needle) != 1:
    raise SystemExit(f"ABORT: unexpected cropper.py upstream structure. Found {text.count(needle)} matching anchors.")
if "Getac GB10 ARM64: ONNX Runtime CPU" not in text:
    text = text.replace(needle, add + needle)
    compile(text, str(p), "exec")
    p.write_text(text, encoding="utf-8")
    print("Applied GB10 CPU ONNX detection provider fallback.")
else:
    print("CPU ONNX detection provider fallback already present.")
