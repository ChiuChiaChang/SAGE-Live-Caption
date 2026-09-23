# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

project_root = Path(SPECPATH).parent
model_name = "sherpa-onnx-streaming-zipformer-en-2023-06-26"
model_dir = project_root / "models" / model_name

if not model_dir.exists():
    raise SystemExit(f"Missing ASR model folder: {model_dir}")

sherpa_datas, sherpa_bins, sherpa_hidden = collect_all("sherpa_onnx")
pa_datas, pa_bins, pa_hidden = collect_all("pyaudiowpatch")

model_files = [
    "tokens.txt",
    "encoder-epoch-99-avg-1-chunk-16-left-128.onnx",
    "decoder-epoch-99-avg-1-chunk-16-left-128.onnx",
    "joiner-epoch-99-avg-1-chunk-16-left-128.onnx",
]

datas = list(sherpa_datas) + list(pa_datas)
for filename in model_files:
    src = model_dir / filename
    if not src.exists():
        raise SystemExit(f"Missing ASR model file: {src}")
    datas.append((str(src), f"models/{model_name}"))

binaries = list(sherpa_bins) + list(pa_bins)
hiddenimports = list(dict.fromkeys(sherpa_hidden + pa_hidden + ["numpy"]))

a = Analysis(
    [str(project_root / "src" / "sage_live_caption.py")],
    pathex=[str(project_root / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SAGE-Live-Caption",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
