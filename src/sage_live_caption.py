import os
import sys
import time
import re
import json
import html as html_lib
import threading
import queue
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

import numpy as np
import pyaudiowpatch as pyaudio
import sherpa_onnx
import tkinter as tk
from tkinter import ttk, messagebox


# ============================================================
# Application / Packaged Resource Settings
# ============================================================

APP_NAME = "SAGE Live Caption"
APP_VERSION = "1.0.0.1"
MODEL_FOLDER_NAME = "sherpa-onnx-streaming-zipformer-en-2023-06-26"

def resource_path(relative_path):
    """Return a path that works both from source and from PyInstaller one-file EXE."""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    return os.path.join(base_path, relative_path)

def get_local_appdata_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "SAGE-Live-Caption")
    os.makedirs(path, exist_ok=True)
    return path

def get_documents_output_dir():
    documents = os.path.join(os.path.expanduser("~"), "Documents")
    path = os.path.join(documents, "SAGE Live Caption", "Output")
    os.makedirs(path, exist_ok=True)
    return path

CONFIG_FILE = os.path.join(get_local_appdata_dir(), "settings.json")

DEFAULT_CONFIG = {
    "enable_zh_translation": True,
    "vllm_api_base": "http://127.0.0.1:8000/v1/chat/completions",
    "vllm_model_name": "google/gemma-4-31B-it",
    "vllm_api_key": "",
}

def load_app_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                cfg.update(saved)
    except Exception as e:
        print(f"[WARNING] Cannot load settings: {e}")
    return cfg

def save_app_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

APP_CONFIG = load_app_config()

# ============================================================
# Sherpa ONNX ASR Model Settings
# ============================================================

MODEL_DIR = resource_path(os.path.join("models", MODEL_FOLDER_NAME))

TOKENS = os.path.join(MODEL_DIR, "tokens.txt")
ENCODER = os.path.join(MODEL_DIR, "encoder-epoch-99-avg-1-chunk-16-left-128.onnx")
DECODER = os.path.join(MODEL_DIR, "decoder-epoch-99-avg-1-chunk-16-left-128.onnx")
JOINER = os.path.join(MODEL_DIR, "joiner-epoch-99-avg-1-chunk-16-left-128.onnx")


# ============================================================
# vLLM Local LLM Settings
# ============================================================

ENABLE_ZH_TRANSLATION = bool(APP_CONFIG.get("enable_zh_translation", True))

VLLM_API_BASE = str(APP_CONFIG.get("vllm_api_base", DEFAULT_CONFIG["vllm_api_base"]))
VLLM_MODEL_NAME = str(APP_CONFIG.get("vllm_model_name", DEFAULT_CONFIG["vllm_model_name"]))
VLLM_API_KEY = str(APP_CONFIG.get("vllm_api_key", ""))

VLLM_TIMEOUT_SECONDS = 60
VLLM_CLEANUP_TIMEOUT_SECONDS = 300

TRANSLATE_LIVE_TEXT = False
TRANSLATE_FINAL_TEXT = True

CLEANUP_AFTER_CLOSE = True
FINAL_CLEANUP_WAIT_SECONDS = 10


# ============================================================
# Audio Capture Settings
# ============================================================

# 空白 = 自動抓目前 Windows Default Output Device
# 例如 AirPods / Realtek / HDMI
FORCE_OUTPUT_NAME = ""

CHUNK_SECONDS = 0.1
SHOW_AUDIO_LEVEL = False

# 數字越小，Final 越快出現；數字越大，句子越完整
RULE1_MIN_TRAILING_SILENCE = 1.2
RULE2_MIN_TRAILING_SILENCE = 0.6

PROVIDER = "cpu"
NUM_THREADS = 2


# ============================================================
# Window Settings
# ============================================================

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 680
MIN_WINDOW_WIDTH = 900
MIN_WINDOW_HEIGHT = 520

FONT_NAME = "Segoe UI"

LIVE_EN_FONT_SIZE = 18
LIVE_ZH_FONT_SIZE = 18
FINAL_FONT_SIZE = 13
STATUS_FONT_SIZE = 10

WINDOW_ALPHA = 0.97


# ============================================================
# Output Settings
# ============================================================

OUTPUT_DIR = get_documents_output_dir()
SAVE_FINAL_TEXT = True
CONSOLE_LOG_FINAL = True

os.makedirs(OUTPUT_DIR, exist_ok=True)

display_queue = queue.Queue()


# ============================================================
# UI Colors
# ============================================================

COLOR_BG = "#0F172A"
COLOR_PANEL = "#111827"
COLOR_PANEL_2 = "#1F2937"
COLOR_CARD = "#0B1220"
COLOR_EN = "#FFFFFF"
COLOR_ZH = "#E5F9EF"
COLOR_MUTED = "#9CA3AF"
COLOR_ACCENT = "#38BDF8"
COLOR_GREEN = "#22C55E"
COLOR_WARN = "#FBBF24"
COLOR_BORDER = "#334155"


# ============================================================
# Text Formatter
# ============================================================

def format_caption_text(text):
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text).strip()
    text = text.lower()

    result = []
    capitalize_next = True

    for ch in text:
        if capitalize_next and ch.isalpha():
            result.append(ch.upper())
            capitalize_next = False
        else:
            result.append(ch)

        if ch in ".?!":
            capitalize_next = True

    text = "".join(result)

    replacements = {
        r"\bi\b": "I",
        r"\bit\b": "IT",
        r"\bai\b": "AI",
        r"\bbios\b": "BIOS",
        r"\bec\b": "EC",
        r"\bgps\b": "GPS",
        r"\busb\b": "USB",
        r"\bcpu\b": "CPU",
        r"\bgpu\b": "GPU",
        r"\basr\b": "ASR",
        r"\bonnx\b": "ONNX",
        r"\bllm\b": "LLM",
        r"\brag\b": "RAG",
        r"\bsage\b": "SAGE",
        r"\bgetac\b": "Getac",
        r"\bwindows\b": "Windows",
        r"\bteams\b": "Teams",
        r"\bzoom\b": "Zoom",
        r"\boutlook\b": "Outlook",
        r"\bexcel\b": "Excel",
        r"\bairpods\b": "AirPods",
        r"\bpython\b": "Python",
        r"\bwhisper\b": "Whisper",
        r"\bsherpa\b": "Sherpa",
        r"\brobotics\b": "robotics",
        r"\bvllm\b": "vLLM",
        r"\bgemma\b": "Gemma",
    }

    for pattern, value in replacements.items():
        text = re.sub(pattern, value, text, flags=re.IGNORECASE)

    return text.strip()


def clean_llm_text(text):
    if not text:
        return ""

    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    text = text.replace("```markdown", "")
    text = text.replace("```html", "")
    text = text.replace("```繁體中文", "")
    text = text.replace("```zh-tw", "")
    text = text.replace("```zh", "")
    text = text.replace("```", "")
    text = text.strip()

    return text


def clean_translation_text(text):
    text = clean_llm_text(text)

    prefixes = [
        "繁體中文翻譯：",
        "繁中翻譯：",
        "翻譯：",
        "中文：",
    ]

    for p in prefixes:
        if text.startswith(p):
            text = text[len(p):].strip()

    return text


# ============================================================
# vLLM API
# ============================================================

def call_vllm_chat(system_prompt, user_prompt, max_tokens=4096, temperature=0.1, timeout=None):
    if timeout is None:
        timeout = VLLM_TIMEOUT_SECONDS

    payload = {
        "model": VLLM_MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        "temperature": temperature,
        "top_p": 0.9,
        "max_tokens": max_tokens,
        "stream": False
    }

    headers = {
        "Content-Type": "application/json"
    }

    if VLLM_API_KEY.strip():
        headers["Authorization"] = "Bearer " + VLLM_API_KEY.strip()

    req = urllib.request.Request(
        VLLM_API_BASE,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    content = result["choices"][0]["message"]["content"].strip()
    return clean_llm_text(content)


def translate_to_zh_tw(text):
    if not ENABLE_ZH_TRANSLATION:
        return ""

    if not text:
        return ""

    system_prompt = (
        "You are a professional real-time meeting subtitle translator. "
        "Translate English subtitles into Traditional Chinese. "
        "Only output the Traditional Chinese translation. "
        "Do not explain. Do not add extra notes. "
        "Keep technical terms such as Windows, BIOS, EC, AI, SAGE, Getac, GPS, USB, "
        "Python, Teams, Zoom, Outlook, Excel, vLLM, Gemma, and model names in English when appropriate."
    )

    user_prompt = f"""
Please translate the following English subtitle into Traditional Chinese.

English subtitle:
{text}
"""

    try:
        zh = call_vllm_chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=512,
            temperature=0.1,
            timeout=VLLM_TIMEOUT_SECONDS
        )
        return clean_translation_text(zh)

    except Exception as e:
        return f"[Translation failed: {e}]"


# ============================================================
# HTML Report Helpers
# ============================================================

def markdown_to_basic_html(markdown_text):
    lines = markdown_text.splitlines()
    html_lines = []
    in_ul = False
    in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            html_lines.append("</ul>")
            in_ul = False
        if in_ol:
            html_lines.append("</ol>")
            in_ol = False

    for raw_line in lines:
        line = raw_line.rstrip()

        if not line.strip():
            close_lists()
            continue

        esc = html_lib.escape(line.strip())

        if line.startswith("# "):
            close_lists()
            html_lines.append(f"<h1>{esc[2:]}</h1>")

        elif line.startswith("## "):
            close_lists()
            html_lines.append(f"<h2>{esc[3:]}</h2>")

        elif line.startswith("### "):
            close_lists()
            html_lines.append(f"<h3>{esc[4:]}</h3>")

        elif line.lstrip().startswith("- "):
            if not in_ul:
                close_lists()
                html_lines.append("<ul>")
                in_ul = True
            item = html_lib.escape(line.lstrip()[2:].strip())
            html_lines.append(f"<li>{item}</li>")

        elif re.match(r"^\d+\.\s+", line.strip()):
            if not in_ol:
                close_lists()
                html_lines.append("<ol>")
                in_ol = True
            item = re.sub(r"^\d+\.\s+", "", line.strip())
            html_lines.append(f"<li>{html_lib.escape(item)}</li>")

        else:
            close_lists()
            html_lines.append(f"<p>{esc}</p>")

    close_lists()
    return "\n".join(html_lines)


def build_html_report(session, report_markdown, raw_transcript):
    report_body_html = markdown_to_basic_html(report_markdown)

    raw_html = html_lib.escape(raw_transcript)
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAGE Live Caption Meeting Report</title>
<style>
:root {{
    --font-size: 18px;
    --line-height: 1.75;
}}
body {{
    margin: 0;
    padding: 0;
    background: #0f172a;
    color: #e5e7eb;
    font-family: "Segoe UI", "Microsoft JhengHei", Arial, sans-serif;
}}
.header {{
    position: sticky;
    top: 0;
    z-index: 10;
    background: linear-gradient(90deg, #0f172a, #111827);
    border-bottom: 1px solid #334155;
    padding: 18px 28px;
}}
.header h1 {{
    margin: 0;
    font-size: 26px;
    color: #ffffff;
}}
.header .meta {{
    margin-top: 8px;
    color: #9ca3af;
    font-size: 13px;
}}
.toolbar {{
    margin-top: 14px;
}}
button {{
    background: #1f2937;
    color: white;
    border: 1px solid #475569;
    border-radius: 8px;
    padding: 8px 12px;
    margin-right: 8px;
    cursor: pointer;
}}
button:hover {{
    background: #334155;
}}
.container {{
    max-width: 1180px;
    margin: 22px auto;
    padding: 0 20px 40px 20px;
}}
.card {{
    background: #111827;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 20px;
    box-shadow: 0 10px 24px rgba(0,0,0,0.22);
}}
.report-content {{
    font-size: var(--font-size);
    line-height: var(--line-height);
}}
.report-content h1 {{
    color: #38bdf8;
    border-bottom: 1px solid #334155;
    padding-bottom: 8px;
    margin-top: 28px;
}}
.report-content h2 {{
    color: #22c55e;
    margin-top: 24px;
}}
.report-content h3 {{
    color: #fbbf24;
}}
.report-content p {{
    margin: 10px 0;
}}
.report-content li {{
    margin: 7px 0;
}}
.raw-block {{
    white-space: pre-wrap;
    background: #0b1220;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 16px;
    font-size: calc(var(--font-size) - 2px);
    line-height: 1.6;
    color: #d1d5db;
    max-height: 620px;
    overflow: auto;
}}
.badge {{
    display: inline-block;
    background: #082f49;
    color: #7dd3fc;
    border: 1px solid #075985;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 12px;
    margin-right: 8px;
}}
.footer {{
    color: #9ca3af;
    font-size: 12px;
    text-align: center;
    padding: 24px;
}}
</style>
<script>
let currentSize = 18;

function applyFontSize() {{
    document.documentElement.style.setProperty("--font-size", currentSize + "px");
    document.getElementById("fontSizeLabel").innerText = currentSize + "px";
}}

function increaseFont() {{
    currentSize += 2;
    applyFontSize();
}}

function decreaseFont() {{
    if (currentSize > 12) {{
        currentSize -= 2;
        applyFontSize();
    }}
}}

function resetFont() {{
    currentSize = 18;
    applyFontSize();
}}

window.onload = applyFontSize;
</script>
</head>
<body>
<div class="header">
    <h1>SAGE Live Caption Meeting Report</h1>
    <div class="meta">
        <span class="badge">Raw Transcript</span>{html_lib.escape(session.raw_txt_file)}
        <br>
        <span class="badge">HTML Report</span>{html_lib.escape(session.report_html_file)}
        <br>
        <span class="badge">Generated</span>{html_lib.escape(report_time)}
        <span class="badge">Model</span>{html_lib.escape(VLLM_MODEL_NAME)}
    </div>
    <div class="toolbar">
        <button onclick="increaseFont()">A+ 放大</button>
        <button onclick="decreaseFont()">A- 縮小</button>
        <button onclick="resetFont()">Reset</button>
        <span style="color:#9ca3af;">Current font size: <span id="fontSizeLabel">18px</span></span>
    </div>
</div>

<div class="container">
    <div class="card report-content">
        {report_body_html}
    </div>

    <div class="card">
        <h1 style="color:#38bdf8;">Raw Transcript / 原始逐字稿</h1>
        <div class="raw-block">{raw_html}</div>
    </div>
</div>

<div class="footer">
    Generated by SAGE Live Caption using sherpa-onnx and vLLM.
</div>
</body>
</html>
"""

    with open(session.report_html_file, "w", encoding="utf-8") as f:
        f.write(html)


# ============================================================
# Final Cleanup / Meeting Summary
# ============================================================

def split_text_for_llm(text, max_chars=12000):
    chunks = []
    text = text.strip()

    while len(text) > max_chars:
        split_pos = text.rfind("\n", 0, max_chars)

        if split_pos <= 0:
            split_pos = max_chars

        chunks.append(text[:split_pos].strip())
        text = text[split_pos:].strip()

    if text:
        chunks.append(text)

    return chunks


def cleanup_transcript_chunk(chunk_text, chunk_index, total_chunks):
    system_prompt = """
You are a professional bilingual meeting transcript editor.

Your task:
1. Clean and correct raw ASR transcript content.
2. Remove repeated phrases, duplicated captions, obvious ASR errors, and broken fragments.
3. Keep the original meaning.
4. Do not invent facts.
5. Keep technical terms such as Windows, BIOS, EC, AI, SAGE, Getac, GPS, USB, vLLM, Gemma, Python, Teams, Zoom, Outlook, Excel in English when appropriate.
"""

    user_prompt = f"""
This is chunk {chunk_index} of {total_chunks} from a raw live caption transcript.

Please clean this chunk and output:

# Cleaned English
Cleaned English transcript for this chunk.

# 繁體中文
Traditional Chinese translation for this chunk.

Raw chunk:
{chunk_text}
"""

    return call_vllm_chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=8192,
        temperature=0.1,
        timeout=VLLM_CLEANUP_TIMEOUT_SECONDS
    )


def cleanup_full_meeting_transcript(session):
    if not CLEANUP_AFTER_CLOSE:
        return False

    if session.report_generated:
        print("Report already generated:")
        print(session.report_html_file)
        return True

    if not os.path.isfile(session.raw_txt_file):
        print("No transcript file found. Skip cleanup.")
        return False

    with open(session.raw_txt_file, "r", encoding="utf-8") as f:
        raw_transcript = f.read().strip()

    if not raw_transcript:
        print("Transcript is empty. Skip cleanup.")
        return False

    print("\nRunning final meeting cleanup with vLLM...")
    print("Raw transcript:")
    print(session.raw_txt_file)

    chunks = split_text_for_llm(raw_transcript, max_chars=12000)
    cleaned_chunks = []

    try:
        for i, chunk in enumerate(chunks, start=1):
            print(f"Cleaning chunk {i}/{len(chunks)}...")
            cleaned = cleanup_transcript_chunk(chunk, i, len(chunks))
            cleaned_chunks.append(cleaned)

        combined_cleaned_text = "\n\n".join(cleaned_chunks)

        system_prompt = """
You are a professional bilingual meeting report editor.

Create a final clean meeting report from the cleaned transcript chunks.

Important rules:
- Do not invent facts.
- If the meeting topic or action items are unclear, clearly say they are unclear.
- Keep technical terms such as Windows, BIOS, EC, AI, SAGE, Getac, GPS, USB, vLLM, Gemma, Python, Teams, Zoom, Outlook, Excel in English when appropriate.
- Output should be clear, professional, and useful as a formal meeting record.
- The final report must include both English and Traditional Chinese content.
- The LLM reflection section should be around 1000 Traditional Chinese characters.
"""

        user_prompt = f"""
Please create the final meeting report in Markdown format using exactly these sections:

# Meeting Topic / 會議主題
Give one short topic in English and Traditional Chinese.

# Key Summary / 重點摘要
Use bullet points. Summarize the most important points clearly.

# Overall Summary / 會議總結
Provide a concise bilingual summary explaining what the meeting is mainly about.

# Cleaned English Transcript / 清洗後英文逐字稿
Merge and clean all English transcript content. Remove duplicates and broken fragments. Keep the original meaning.

# 繁體中文逐字稿
Translate the cleaned English transcript into Traditional Chinese.

# Key Points / 重點
List the important technical or business points.

# Action Items / 待辦事項
List action items. If there are none, write "No clear action items identified / 未辨識出明確待辦事項."

# Unclear Parts / 不確定內容
List unclear ASR parts or uncertain terms.

# LLM Reflection Report / LLM 心得報告
Write around 1000 Traditional Chinese characters.
Please provide your professional reflection on:
- what this meeting is mainly discussing
- why the topic may be important
- possible technical or business implications
- possible risks or unclear areas
- suggested follow-up direction
Do not invent facts. Base the reflection only on the transcript.

Cleaned chunks:
{combined_cleaned_text}
"""

        final_report_markdown = call_vllm_chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=16000,
            temperature=0.1,
            timeout=VLLM_CLEANUP_TIMEOUT_SECONDS
        )

        build_html_report(session, final_report_markdown, raw_transcript)

        session.report_generated = True

        print("\nFinal HTML meeting report saved to:")
        print(session.report_html_file)

        return True

    except Exception as e:
        print("\n[ERROR] Final cleanup failed:")
        print(e)
        return False


# ============================================================
# Audio Helpers
# ============================================================

def clean_device_name(name):
    if not name:
        return ""

    return name.replace("[Loopback]", "").strip().lower()


def get_rms(audio):
    if audio is None or len(audio) == 0:
        return 0.0

    return float(np.sqrt(np.mean(audio ** 2)))


def find_loopback_device(pa):
    wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
    default_output_index = wasapi_info["defaultOutputDevice"]
    default_output = pa.get_device_info_by_index(default_output_index)

    default_output_name = default_output["name"]
    default_output_clean = clean_device_name(default_output_name)

    print("Current Windows default output:", default_output_name, flush=True)

    loopback_devices = list(pa.get_loopback_device_info_generator())

    print("\n===== Loopback Devices =====", flush=True)
    for dev in loopback_devices:
        print(
            f"[{dev['index']}] {dev['name']} | in={dev['maxInputChannels']} | rate={dev['defaultSampleRate']}",
            flush=True
        )
    print("============================\n", flush=True)

    if FORCE_OUTPUT_NAME.strip():
        key = FORCE_OUTPUT_NAME.lower()

        for dev in loopback_devices:
            if key in dev["name"].lower():
                print("Selected loopback device by FORCE_OUTPUT_NAME:", dev["name"], flush=True)
                return dev

        raise RuntimeError("Cannot find loopback device containing name: " + FORCE_OUTPUT_NAME)

    for dev in loopback_devices:
        loopback_name_clean = clean_device_name(dev["name"])

        if default_output_clean == loopback_name_clean:
            print("Selected current default loopback:", dev["name"], flush=True)
            return dev

    for dev in loopback_devices:
        loopback_name_clean = clean_device_name(dev["name"])

        if default_output_clean in loopback_name_clean or loopback_name_clean in default_output_clean:
            print("Selected current default loopback by partial match:", dev["name"], flush=True)
            return dev

    if loopback_devices:
        print(
            "[WARNING] Cannot match current default output. Use first loopback:",
            loopback_devices[0]["name"],
            flush=True
        )
        return loopback_devices[0]

    raise RuntimeError("No WASAPI loopback device found.")


# ============================================================
# Sherpa ONNX Recognizer
# ============================================================

def assert_file_exists(filename):
    if not Path(filename).is_file():
        raise FileNotFoundError(filename)


def create_recognizer():
    assert_file_exists(TOKENS)
    assert_file_exists(ENCODER)
    assert_file_exists(DECODER)
    assert_file_exists(JOINER)

    recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
        tokens=TOKENS,
        encoder=ENCODER,
        decoder=DECODER,
        joiner=JOINER,

        num_threads=NUM_THREADS,
        sample_rate=16000,
        feature_dim=80,

        enable_endpoint_detection=True,
        rule1_min_trailing_silence=RULE1_MIN_TRAILING_SILENCE,
        rule2_min_trailing_silence=RULE2_MIN_TRAILING_SILENCE,
        rule3_min_utterance_length=300,

        decoding_method="greedy_search",
        provider=PROVIDER,
    )

    return recognizer


def get_text_from_result(result):
    if result is None:
        return ""

    if isinstance(result, str):
        return result.strip()

    if hasattr(result, "text"):
        return result.text.strip()

    return str(result).strip()


# ============================================================
# Live Caption Session
# ============================================================

class LiveCaptionSession:
    def __init__(self, session_id):
        self.session_id = session_id
        self.run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.raw_txt_file = os.path.join(
            OUTPUT_DIR,
            f"sherpa_speaker_caption_raw_{self.run_ts}.txt"
        )

        self.report_html_file = os.path.join(
            OUTPUT_DIR,
            f"sherpa_speaker_caption_report_{self.run_ts}.html"
        )

        self.stop_event = threading.Event()
        self.asr_done_event = threading.Event()
        self.translate_queue = queue.Queue()

        self.asr_thread = None
        self.translation_thread = None

        self.is_running = False
        self.report_generated = False

    def save_text(self, line):
        with open(self.raw_txt_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def start(self):
        self.is_running = True

        self.asr_thread = threading.Thread(target=self.asr_worker)
        self.asr_thread.daemon = True
        self.asr_thread.start()

        self.translation_thread = threading.Thread(target=self.translation_worker)
        self.translation_thread.daemon = True
        self.translation_thread.start()

        display_queue.put(("session_started", {
            "session_id": self.session_id,
            "raw_file": self.raw_txt_file,
            "report_file": self.report_html_file
        }))

    def request_stop(self):
        self.stop_event.set()
        self.is_running = False

    def wait_asr(self, timeout=5):
        if self.asr_thread is not None:
            self.asr_thread.join(timeout=timeout)

    def get_unfinished_translation_tasks(self):
        return getattr(self.translate_queue, "unfinished_tasks", 0)

    def wait_translation_queue(self, timeout=10):
        wait_start = time.time()

        while self.get_unfinished_translation_tasks() > 0:
            if time.time() - wait_start > timeout:
                print("Translation queue wait timeout.")
                break

            time.sleep(0.2)

    def submit_translation(self, item_type, english_text):
        if not ENABLE_ZH_TRANSLATION:
            return

        if not english_text:
            return

        if item_type == "live" and not TRANSLATE_LIVE_TEXT:
            return

        if item_type == "final" and not TRANSLATE_FINAL_TEXT:
            return

        try:
            if item_type == "live":
                kept_items = []

                while not self.translate_queue.empty():
                    try:
                        old = self.translate_queue.get_nowait()
                        if old.get("type") != "live":
                            kept_items.append(old)
                        self.translate_queue.task_done()
                    except queue.Empty:
                        break

                for old in kept_items:
                    self.translate_queue.put_nowait(old)

            self.translate_queue.put_nowait({
                "type": item_type,
                "english": english_text
            })

        except queue.Full:
            pass

    def translation_worker(self):
        while (
            not self.asr_done_event.is_set()
            or not self.translate_queue.empty()
            or self.get_unfinished_translation_tasks() > 0
        ):
            try:
                item = self.translate_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                item_type = item.get("type")
                english_text = item.get("english", "")

                zh_text = translate_to_zh_tw(english_text)

                if item_type == "live":
                    display_queue.put(("live_zh", {
                        "session_id": self.session_id,
                        "text": zh_text
                    }))

                elif item_type == "final":
                    display_queue.put(("final_bilingual", {
                        "session_id": self.session_id,
                        "english": english_text,
                        "zh": zh_text
                    }))

                    if SAVE_FINAL_TEXT:
                        now = datetime.now().strftime("%H:%M:%S")
                        self.save_text(f"[{now}] 繁中: {zh_text}")

            finally:
                self.translate_queue.task_done()

    def asr_worker(self):
        recognizer = None
        stream_asr = None
        pa = None
        audio_stream = None

        last_partial = ""
        last_final = ""
        last_level_time = 0

        try:
            display_queue.put(("status", {
                "session_id": self.session_id,
                "text": "Loading sherpa-onnx recognizer..."
            }))

            print("Loading sherpa-onnx streaming recognizer...", flush=True)
            recognizer = create_recognizer()
            stream_asr = recognizer.create_stream()
            print("Recognizer loaded.", flush=True)

            display_queue.put(("status", {
                "session_id": self.session_id,
                "text": "Recognizer loaded. Starting audio capture..."
            }))

            pa = pyaudio.PyAudio()
            loopback_dev = find_loopback_device(pa)

            input_rate = int(loopback_dev["defaultSampleRate"])
            channels = int(loopback_dev.get("maxInputChannels", 2))

            if channels <= 0:
                channels = 2

            channels = min(channels, 2)
            frames_per_buffer = int(input_rate * CHUNK_SECONDS)

            print("Using loopback:", loopback_dev["name"], flush=True)
            print("Input rate:", input_rate, flush=True)
            print("Channels:", channels, flush=True)
            print("Frames per buffer:", frames_per_buffer, flush=True)

            display_queue.put(("status", {
                "session_id": self.session_id,
                "text": f"Capturing: {loopback_dev['name']}"
            }))

            audio_stream = pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=input_rate,
                input=True,
                input_device_index=loopback_dev["index"],
                frames_per_buffer=frames_per_buffer
            )

            print("\nStart sherpa speaker live caption with vLLM translation.", flush=True)
            print("Click Finish, Restart, or X to stop.\n", flush=True)

            while not self.stop_event.is_set():
                raw = audio_stream.read(
                    frames_per_buffer,
                    exception_on_overflow=False
                )

                audio = np.frombuffer(raw, dtype=np.int16)

                if len(audio) == 0:
                    continue

                if channels > 1:
                    audio = audio.reshape(-1, channels)
                    audio = np.mean(audio, axis=1)

                samples = audio.astype(np.float32) / 32768.0

                if SHOW_AUDIO_LEVEL:
                    now_t = time.time()
                    if now_t - last_level_time >= 2:
                        rms = get_rms(samples)
                        print(f"[Audio Level] RMS={rms:.5f}", flush=True)
                        last_level_time = now_t

                stream_asr.accept_waveform(input_rate, samples)

                while recognizer.is_ready(stream_asr):
                    recognizer.decode_stream(stream_asr)

                partial_raw = get_text_from_result(recognizer.get_result(stream_asr))
                partial_text = format_caption_text(partial_raw)

                if partial_text and partial_text != last_partial:
                    display_queue.put(("live_en", {
                        "session_id": self.session_id,
                        "text": partial_text
                    }))

                    if TRANSLATE_LIVE_TEXT:
                        self.submit_translation("live", partial_text)

                    last_partial = partial_text

                if recognizer.is_endpoint(stream_asr):
                    final_raw = get_text_from_result(recognizer.get_result(stream_asr))
                    final_text = format_caption_text(final_raw)

                    if final_text and final_text != last_final:
                        now = datetime.now().strftime("%H:%M:%S")
                        line = f"[{now}] English: {final_text}"

                        display_queue.put(("final_en", {
                            "session_id": self.session_id,
                            "text": final_text
                        }))

                        if CONSOLE_LOG_FINAL:
                            print(line, flush=True)

                        if SAVE_FINAL_TEXT:
                            self.save_text(line)

                        self.submit_translation("final", final_text)

                        last_final = final_text

                    recognizer.reset(stream_asr)
                    last_partial = ""

        except Exception as e:
            import traceback
            traceback.print_exc()

            display_queue.put(("error", {
                "session_id": self.session_id,
                "text": "Error: " + str(e)
            }))

            self.stop_event.set()

        finally:
            try:
                if last_partial and last_partial != last_final:
                    now = datetime.now().strftime("%H:%M:%S")
                    line = f"[{now}] English: {last_partial}"

                    if SAVE_FINAL_TEXT:
                        self.save_text(line)

                    self.submit_translation("final", last_partial)
                    print(line, flush=True)

            except Exception:
                pass

            try:
                if audio_stream is not None:
                    audio_stream.stop_stream()
                    audio_stream.close()
            except Exception:
                pass

            try:
                if pa is not None:
                    pa.terminate()
            except Exception:
                pass

            self.asr_done_event.set()

            print("Transcript saved to:", flush=True)
            print(self.raw_txt_file, flush=True)


# ============================================================
# Environment Check
# ============================================================

def _probe_loopback_device():
    """Return (ok, detail) for Windows WASAPI loopback without changing app state."""
    pa = None
    try:
        pa = pyaudio.PyAudio()
        wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_output_index = wasapi_info["defaultOutputDevice"]
        default_output = pa.get_device_info_by_index(default_output_index)
        default_output_name = default_output.get("name", "Unknown")
        default_output_clean = clean_device_name(default_output_name)
        loopback_devices = list(pa.get_loopback_device_info_generator())

        if not loopback_devices:
            return False, "No WASAPI loopback device was found."

        for dev in loopback_devices:
            if clean_device_name(dev.get("name", "")) == default_output_clean:
                return True, f"{default_output_name} → {dev.get('name', 'Loopback')}"

        for dev in loopback_devices:
            loop_name = clean_device_name(dev.get("name", ""))
            if default_output_clean in loop_name or loop_name in default_output_clean:
                return True, f"{default_output_name} → {dev.get('name', 'Loopback')}"

        return True, f"Default: {default_output_name}; loopback devices available: {len(loopback_devices)}"
    except Exception as e:
        return False, str(e)
    finally:
        try:
            if pa is not None:
                pa.terminate()
        except Exception:
            pass


def _probe_output_folder():
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        probe = os.path.join(OUTPUT_DIR, ".sage_write_test.tmp")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True, OUTPUT_DIR
    except Exception as e:
        return False, str(e)


def _probe_ai_server(api_url, model_name, api_key, timeout=10):
    api_url = (api_url or "").strip()
    model_name = (model_name or "").strip()
    api_key = (api_key or "").strip()

    if not api_url:
        return False, "AI Server URL is empty."
    if not model_name:
        return False, "Model name is empty."

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "Connectivity test. Reply with exactly OK."},
            {"role": "user", "content": "OK"},
        ],
        "temperature": 0.0,
        "max_tokens": 8,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        content = body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return True, f"Connected to {model_name}" + (f" ({content[:40]})" if content else "")
    except Exception as e:
        return False, str(e)


def run_environment_checks(api_url=None, model_name=None, api_key=None, include_ai=True):
    results = {}

    results["Windows"] = (
        os.name == "nt",
        "Windows detected" if os.name == "nt" else "This application is designed for Windows 10/11.",
    )

    model_files = (TOKENS, ENCODER, DECODER, JOINER)
    missing = [os.path.basename(x) for x in model_files if not os.path.isfile(x)]
    results["Speech Engine"] = (
        not missing,
        f"Sherpa-ONNX model ready: {MODEL_FOLDER_NAME}" if not missing else "Missing: " + ", ".join(missing),
    )

    audio_ok, audio_detail = _probe_loopback_device()
    results["Windows Audio"] = (audio_ok, audio_detail)

    output_ok, output_detail = _probe_output_folder()
    results["Output Folder"] = (output_ok, output_detail)

    if include_ai:
        ai_ok, ai_detail = _probe_ai_server(
            api_url if api_url is not None else VLLM_API_BASE,
            model_name if model_name is not None else VLLM_MODEL_NAME,
            api_key if api_key is not None else VLLM_API_KEY,
        )
        results["AI Server"] = (ai_ok, ai_detail)
    else:
        results["AI Server"] = (True, "Skipped (translation is disabled).")

    return results


# ============================================================
# Settings Dialog
# ============================================================

class SettingsDialog:
    def __init__(self, parent, caption_window=None):
        self.parent = parent
        self.caption_window = caption_window
        self.win = tk.Toplevel(parent)
        self.win.title(f"SAGE Live Caption Settings {APP_VERSION}")
        self.win.configure(bg=COLOR_BG)
        self.win.transient(parent)
        self.win.grab_set()
        self.win.resizable(False, False)

        width, height = 820, 680
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        self.win.geometry(f"{width}x{height}+{max(20,(sw-width)//2)}+{max(20,(sh-height)//2)}")

        self.api_var = tk.StringVar(value=VLLM_API_BASE)
        self.model_var = tk.StringVar(value=VLLM_MODEL_NAME)
        self.key_var = tk.StringVar(value=VLLM_API_KEY)
        self.translation_var = tk.BooleanVar(value=ENABLE_ZH_TRANSLATION)
        self.check_busy = False
        self.check_result = None
        self.env_vars = {}

        outer = tk.Frame(self.win, bg=COLOR_BG, padx=22, pady=18)
        outer.pack(fill="both", expand=True)

        tk.Label(
            outer,
            text="Settings",
            fg="white",
            bg=COLOR_BG,
            font=(FONT_NAME, 18, "bold"),
        ).pack(anchor="w")
        tk.Label(
            outer,
            text="AI Server and environment setup. Keep it simple: configure, test, and start.",
            fg=COLOR_MUTED,
            bg=COLOR_BG,
            font=(FONT_NAME, 10),
        ).pack(anchor="w", pady=(4, 14))

        ai_outer, ai_card = self._make_card(outer)
        ai_outer.pack(fill="x", pady=(0, 12))
        tk.Label(ai_card, text="AI Server", fg=COLOR_ACCENT, bg=COLOR_PANEL,
                 font=(FONT_NAME, 12, "bold")).pack(anchor="w")
        tk.Label(ai_card, text="OpenAI-compatible vLLM endpoint used for translation and meeting reports.",
                 fg=COLOR_MUTED, bg=COLOR_PANEL, font=(FONT_NAME, 9)).pack(anchor="w", pady=(2, 10))

        self._field(ai_card, "Server URL", self.api_var)
        self._field(ai_card, "Model", self.model_var)
        self._field(ai_card, "API Key (optional)", self.key_var, show="*")

        chk = tk.Checkbutton(
            ai_card,
            text="Enable Traditional Chinese translation and AI report",
            variable=self.translation_var,
            bg=COLOR_PANEL,
            fg="white",
            selectcolor=COLOR_PANEL_2,
            activebackground=COLOR_PANEL,
            activeforeground="white",
            font=(FONT_NAME, 10),
        )
        chk.pack(anchor="w", pady=(2, 2))

        env_outer, env_card = self._make_card(outer)
        env_outer.pack(fill="both", expand=True, pady=(0, 12))
        title_row = tk.Frame(env_card, bg=COLOR_PANEL)
        title_row.pack(fill="x")
        tk.Label(title_row, text="Environment Check", fg=COLOR_GREEN, bg=COLOR_PANEL,
                 font=(FONT_NAME, 12, "bold")).pack(side="left")
        self.check_button = ttk.Button(
            title_row,
            text="Run Check",
            style="Accent.TButton",
            command=self.run_check,
        )
        self.check_button.pack(side="right")

        tk.Label(
            env_card,
            text="Checks Windows audio loopback, Sherpa speech model, output folder, and AI Server.",
            fg=COLOR_MUTED,
            bg=COLOR_PANEL,
            font=(FONT_NAME, 9),
        ).pack(anchor="w", pady=(2, 10))

        for name in ("Windows", "Speech Engine", "Windows Audio", "Output Folder", "AI Server"):
            row = tk.Frame(env_card, bg=COLOR_PANEL)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=name, width=16, anchor="w", fg="white", bg=COLOR_PANEL,
                     font=(FONT_NAME, 9, "bold")).pack(side="left")
            var = tk.StringVar(value="○ Not checked")
            self.env_vars[name] = var
            tk.Label(row, textvariable=var, anchor="w", fg=COLOR_MUTED, bg=COLOR_PANEL,
                     font=(FONT_NAME, 9)).pack(side="left", fill="x", expand=True)

        tk.Label(
            outer,
            text=f"Settings: {CONFIG_FILE}",
            fg=COLOR_MUTED,
            bg=COLOR_BG,
            font=(FONT_NAME, 8),
        ).pack(anchor="w")

        buttons = tk.Frame(outer, bg=COLOR_BG)
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", style="Dark.TButton", command=self.win.destroy).pack(side="right")
        ttk.Button(buttons, text="Save", style="Green.TButton", command=self.save).pack(side="right", padx=(0, 8))
        ttk.Button(buttons, text="Test AI Server", style="Dark.TButton", command=self.test_vllm).pack(side="left")

    def _make_card(self, parent):
        outer = tk.Frame(parent, bg=COLOR_BORDER)
        inner = tk.Frame(outer, bg=COLOR_PANEL, padx=14, pady=12)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return outer, inner

    def _field(self, parent, label, variable, show=None):
        tk.Label(parent, text=label, fg=COLOR_MUTED, bg=COLOR_PANEL,
                 font=(FONT_NAME, 9)).pack(anchor="w")
        entry = tk.Entry(parent, textvariable=variable, show=show or "", bg=COLOR_CARD,
                         fg="white", insertbackground="white", relief="flat",
                         font=(FONT_NAME, 10))
        entry.pack(fill="x", ipady=7, pady=(3, 8))

    def _apply_globals(self):
        global ENABLE_ZH_TRANSLATION, VLLM_API_BASE, VLLM_MODEL_NAME, VLLM_API_KEY, APP_CONFIG
        ENABLE_ZH_TRANSLATION = bool(self.translation_var.get())
        VLLM_API_BASE = self.api_var.get().strip()
        VLLM_MODEL_NAME = self.model_var.get().strip()
        VLLM_API_KEY = self.key_var.get().strip()
        APP_CONFIG = {
            "enable_zh_translation": ENABLE_ZH_TRANSLATION,
            "vllm_api_base": VLLM_API_BASE,
            "vllm_model_name": VLLM_MODEL_NAME,
            "vllm_api_key": VLLM_API_KEY,
        }

    def save(self):
        if self.translation_var.get() and not self.api_var.get().strip():
            messagebox.showwarning("SAGE Live Caption", "AI Server URL cannot be empty when AI features are enabled.", parent=self.win)
            return
        if self.translation_var.get() and not self.model_var.get().strip():
            messagebox.showwarning("SAGE Live Caption", "Model cannot be empty when AI features are enabled.", parent=self.win)
            return

        self._apply_globals()
        try:
            save_app_config(APP_CONFIG)
        except Exception as e:
            messagebox.showerror("SAGE Live Caption", f"Cannot save settings:\n{e}", parent=self.win)
            return

        if self.caption_window is not None:
            self.caption_window.safe_config(
                self.caption_window.status_label,
                text="Status: Settings saved. Ready to use.",
            )
        self.win.destroy()

    def test_vllm(self):
        if not self.translation_var.get():
            messagebox.showinfo("AI Server", "AI translation is currently disabled.", parent=self.win)
            return
        ok, detail = _probe_ai_server(self.api_var.get(), self.model_var.get(), self.key_var.get(), timeout=10)
        if ok:
            messagebox.showinfo("AI Server", "Connection successful.\n\n" + detail, parent=self.win)
        else:
            messagebox.showerror("AI Server", "Connection failed.\n\n" + detail, parent=self.win)

    def run_check(self):
        if self.check_busy:
            return
        self.check_busy = True
        self.check_result = None
        self.check_button.config(state="disabled", text="Checking...")
        for var in self.env_vars.values():
            var.set("… Checking")

        api = self.api_var.get().strip()
        model = self.model_var.get().strip()
        key = self.key_var.get().strip()
        include_ai = bool(self.translation_var.get())

        def worker():
            try:
                self.check_result = run_environment_checks(api, model, key, include_ai=include_ai)
            except Exception as e:
                self.check_result = {"Windows": (False, f"Environment check failed: {e}")}

        threading.Thread(target=worker, daemon=True).start()
        self.win.after(120, self._poll_check)

    def _poll_check(self):
        if self.check_result is None:
            try:
                self.win.after(120, self._poll_check)
            except tk.TclError:
                pass
            return

        results = self.check_result
        all_ok = True
        for name, var in self.env_vars.items():
            ok, detail = results.get(name, (False, "No result"))
            all_ok = all_ok and ok
            var.set(("✓ Ready — " if ok else "✕ Error — ") + detail)

        self.check_busy = False
        self.check_button.config(state="normal", text="Run Check")

        if self.caption_window is not None:
            text = "Status: Environment ready." if all_ok else "Status: Environment check found an issue. Open Settings for details."
            self.caption_window.safe_config(self.caption_window.status_label, text=text)


# ============================================================
# App Controller
# ============================================================

class AppController:
    def __init__(self):
        self.current_session = None
        self.session_count = 0
        self.busy = False
        self.lock = threading.Lock()

    def start_new_session(self):
        with self.lock:
            self.session_count += 1
            session = LiveCaptionSession(self.session_count)
            self.current_session = session

        session.start()

    def finish_and_generate_report(self, close_after=False, restart_after=False):
        with self.lock:
            if self.busy:
                return

            self.busy = True

        t = threading.Thread(
            target=self._finish_flow,
            args=(close_after, restart_after)
        )
        t.daemon = True
        t.start()

    def _finish_flow(self, close_after=False, restart_after=False):
        session = None

        try:
            display_queue.put(("busy", {
                "busy": True,
                "text": "Stopping caption and generating HTML report..."
            }))

            with self.lock:
                session = self.current_session

            if session is not None:
                session.request_stop()
                session.wait_asr(timeout=5)
                session.wait_translation_queue(timeout=FINAL_CLEANUP_WAIT_SECONDS)

                display_queue.put(("status", {
                    "session_id": session.session_id,
                    "text": "Generating HTML report with vLLM..."
                }))

                report_ok = cleanup_full_meeting_transcript(session)

                display_queue.put(("report_done", {
                    "session_id": session.session_id,
                    "ok": report_ok,
                    "raw_file": session.raw_txt_file,
                    "report_file": session.report_html_file
                }))

            if restart_after and not close_after:
                self.start_new_session()

            if close_after:
                display_queue.put(("close_window", {}))

        finally:
            with self.lock:
                self.busy = False

            if not close_after:
                display_queue.put(("busy", {
                    "busy": False,
                    "text": "Ready"
                }))


# ============================================================
# Caption Window
# ============================================================

class CaptionWindow:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller

        self.current_session_id = None
        self.last_report_file = ""
        self.is_window_closing = False

        self.live_en_font_size = LIVE_EN_FONT_SIZE
        self.live_zh_font_size = LIVE_ZH_FONT_SIZE
        self.final_font_size = FINAL_FONT_SIZE

        self.root.title(f"SAGE Live Caption {APP_VERSION} - sherpa-onnx + vLLM")
        self.root.configure(bg=COLOR_BG)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", WINDOW_ALPHA)

        self.root.resizable(True, True)
        self.root.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        x = int((screen_w - WINDOW_WIDTH) / 2)
        y = max(20, int((screen_h - WINDOW_HEIGHT) / 2))

        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
        self.root.protocol("WM_DELETE_WINDOW", self.finish_and_close)

        self.setup_style()

        self.main_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.main_frame.pack(fill="both", expand=True)

        self.build_header()
        self.build_intro_bar()
        self.build_top_controls()
        self.build_live_cards()
        self.build_transcript_area()

        # ESC 不做任何事，也不顯示訊息
        self.root.bind("<Escape>", lambda event: "break")

        self.root.bind("<Control-plus>", lambda e: self.increase_live_font())
        self.root.bind("<Control-equal>", lambda e: self.increase_live_font())
        self.root.bind("<Control-minus>", lambda e: self.decrease_live_font())

        self.root.bind("<Control-Shift-plus>", lambda e: self.increase_final_font())
        self.root.bind("<Control-Shift-equal>", lambda e: self.increase_final_font())
        self.root.bind("<Control-Shift-minus>", lambda e: self.decrease_final_font())

        self.root.bind("<Configure>", self.on_resize)

        self.update_loop()

    def setup_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Accent.TButton",
            font=(FONT_NAME, 10),
            padding=(10, 6),
            background=COLOR_ACCENT,
            foreground="#00111F"
        )

        style.configure(
            "Green.TButton",
            font=(FONT_NAME, 10),
            padding=(10, 6),
            background=COLOR_GREEN,
            foreground="#06220F"
        )

        style.configure(
            "Warn.TButton",
            font=(FONT_NAME, 10),
            padding=(10, 6),
            background=COLOR_WARN,
            foreground="#271A00"
        )

        style.configure(
            "Dark.TButton",
            font=(FONT_NAME, 10),
            padding=(10, 6),
            background=COLOR_PANEL_2,
            foreground="white"
        )

        style.map("Accent.TButton", background=[("active", "#7DD3FC")])
        style.map("Green.TButton", background=[("active", "#86EFAC")])
        style.map("Warn.TButton", background=[("active", "#FDE68A")])
        style.map("Dark.TButton", background=[("active", "#374151")])

    def safe_config(self, widget, **kwargs):
        if self.is_window_closing:
            return False

        try:
            if widget is not None and widget.winfo_exists():
                widget.config(**kwargs)
                return True
        except tk.TclError:
            return False

        return False

    def destroy_window_safely(self):
        self.is_window_closing = True

        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except tk.TclError:
            pass

    def make_card(self, parent):
        outer = tk.Frame(parent, bg=COLOR_BORDER)
        inner = tk.Frame(outer, bg=COLOR_PANEL, padx=12, pady=10)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return outer, inner

    def build_header(self):
        header = tk.Frame(self.main_frame, bg=COLOR_BG)
        header.pack(fill="x", padx=14, pady=(12, 8))

        left = tk.Frame(header, bg=COLOR_BG)
        left.pack(side="left", fill="x", expand=True)

        title = tk.Label(
            left,
            text=f"SAGE Live Caption  {APP_VERSION}",
            fg="white",
            bg=COLOR_BG,
            font=(FONT_NAME, 18, "bold"),
            anchor="w"
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            left,
            text="Real-time meeting captions, Traditional Chinese translation, and AI meeting reports.",
            fg=COLOR_MUTED,
            bg=COLOR_BG,
            font=(FONT_NAME, 10),
            anchor="w"
        )
        subtitle.pack(anchor="w", pady=(4, 0))

        right = tk.Frame(header, bg=COLOR_BG)
        right.pack(side="right")

        self.finish_button = ttk.Button(
            right,
            text="Finish & Report",
            style="Green.TButton",
            command=self.finish_report
        )
        self.finish_button.pack(side="left", padx=(0, 8))

        self.restart_button = ttk.Button(
            right,
            text="Restart",
            style="Warn.TButton",
            command=self.restart_session
        )
        self.restart_button.pack(side="left", padx=(0, 8))

        self.settings_button = ttk.Button(
            right,
            text="Settings",
            style="Dark.TButton",
            command=self.open_settings
        )
        self.settings_button.pack(side="left", padx=(0, 8))

        self.open_report_button = ttk.Button(
            right,
            text="Open Report",
            style="Dark.TButton",
            command=self.open_report
        )
        self.open_report_button.pack(side="left")

        self.status_label = tk.Label(
            self.main_frame,
            text="Status: Loading...",
            fg=COLOR_MUTED,
            bg=COLOR_BG,
            font=(FONT_NAME, STATUS_FONT_SIZE),
            anchor="w"
        )
        self.status_label.pack(fill="x", padx=16, pady=(0, 8))

    def build_intro_bar(self):
        outer = tk.Frame(self.main_frame, bg=COLOR_BORDER)
        outer.pack(fill="x", padx=14, pady=(0, 10))
        card = tk.Frame(outer, bg=COLOR_PANEL, padx=14, pady=10)
        card.pack(fill="x", padx=1, pady=1)

        steps = [
            ("1  Listen", "Windows audio"),
            ("2  Translate", "English → 繁中"),
            ("3  Report", "AI meeting summary"),
        ]
        for i, (title, detail) in enumerate(steps):
            cell = tk.Frame(card, bg=COLOR_PANEL)
            cell.pack(side="left", fill="x", expand=True)
            tk.Label(cell, text=title, fg="white", bg=COLOR_PANEL,
                     font=(FONT_NAME, 10, "bold")).pack(anchor="w")
            tk.Label(cell, text=detail, fg=COLOR_MUTED, bg=COLOR_PANEL,
                     font=(FONT_NAME, 9)).pack(anchor="w", pady=(2, 0))
            if i < len(steps) - 1:
                tk.Label(card, text="  →  ", fg=COLOR_ACCENT, bg=COLOR_PANEL,
                         font=(FONT_NAME, 12, "bold")).pack(side="left")

    def build_top_controls(self):
        toolbar = tk.Frame(self.main_frame, bg=COLOR_BG)
        toolbar.pack(fill="x", padx=14, pady=(0, 10))

        file_row = tk.Frame(toolbar, bg=COLOR_BG)
        file_row.pack(fill="x", pady=(0, 6))

        self.output_label = tk.Label(
            file_row,
            text="Raw: -    |    HTML Report: -",
            fg=COLOR_MUTED,
            bg=COLOR_BG,
            font=(FONT_NAME, 9),
            anchor="w"
        )
        self.output_label.pack(side="left", fill="x", expand=True)

        control_row = tk.Frame(toolbar, bg=COLOR_BG)
        control_row.pack(fill="x")

        self.live_up_button = ttk.Button(
            control_row,
            text="Live A+",
            style="Dark.TButton",
            command=self.increase_live_font
        )
        self.live_up_button.pack(side="left", padx=(0, 6))

        self.live_down_button = ttk.Button(
            control_row,
            text="Live A-",
            style="Dark.TButton",
            command=self.decrease_live_font
        )
        self.live_down_button.pack(side="left", padx=(0, 6))

        self.final_up_button = ttk.Button(
            control_row,
            text="Final A+",
            style="Dark.TButton",
            command=self.increase_final_font
        )
        self.final_up_button.pack(side="left", padx=(0, 6))

        self.final_down_button = ttk.Button(
            control_row,
            text="Final A-",
            style="Dark.TButton",
            command=self.decrease_final_font
        )
        self.final_down_button.pack(side="left", padx=(0, 6))

        self.close_button = ttk.Button(
            control_row,
            text="Close, Save & Report",
            style="Accent.TButton",
            command=self.finish_and_close
        )
        self.close_button.pack(side="right", padx=(8, 0))

    def build_live_cards(self):
        live_area = tk.Frame(self.main_frame, bg=COLOR_BG)
        live_area.pack(fill="x", padx=14, pady=(0, 10))

        en_outer, en_card = self.make_card(live_area)
        en_outer.pack(fill="x", pady=(0, 8))

        en_title = tk.Label(
            en_card,
            text="English Live Caption",
            fg=COLOR_ACCENT,
            bg=COLOR_PANEL,
            font=(FONT_NAME, 10, "bold"),
            anchor="w"
        )
        en_title.pack(fill="x")

        self.live_en_label = tk.Label(
            en_card,
            text="Listening...",
            fg=COLOR_EN,
            bg=COLOR_PANEL,
            font=(FONT_NAME, self.live_en_font_size),
            wraplength=WINDOW_WIDTH - 80,
            justify="left",
            anchor="w",
            padx=4,
            pady=8
        )
        self.live_en_label.pack(fill="x")

        zh_outer, zh_card = self.make_card(live_area)
        zh_outer.pack(fill="x")

        zh_title = tk.Label(
            zh_card,
            text="繁體中文翻譯",
            fg=COLOR_GREEN,
            bg=COLOR_PANEL,
            font=(FONT_NAME, 10, "bold"),
            anchor="w"
        )
        zh_title.pack(fill="x")

        self.live_zh_label = tk.Label(
            zh_card,
            text="等待翻譯...",
            fg=COLOR_ZH,
            bg=COLOR_PANEL,
            font=(FONT_NAME, self.live_zh_font_size),
            wraplength=WINDOW_WIDTH - 80,
            justify="left",
            anchor="w",
            padx=4,
            pady=8
        )
        self.live_zh_label.pack(fill="x")

    def build_transcript_area(self):
        transcript_outer, transcript_card = self.make_card(self.main_frame)
        transcript_outer.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        title_row = tk.Frame(transcript_card, bg=COLOR_PANEL)
        title_row.pack(fill="x")

        title = tk.Label(
            title_row,
            text="Final Transcript",
            fg="white",
            bg=COLOR_PANEL,
            font=(FONT_NAME, 11, "bold"),
            anchor="w"
        )
        title.pack(side="left")

        hint = tk.Label(
            title_row,
            text="Final English + 繁中 will be saved. HTML report runs after Finish / X / Restart.",
            fg=COLOR_MUTED,
            bg=COLOR_PANEL,
            font=(FONT_NAME, 9),
            anchor="e"
        )
        hint.pack(side="right")

        text_frame = tk.Frame(transcript_card, bg=COLOR_PANEL)
        text_frame.pack(fill="both", expand=True, pady=(8, 0))

        self.scrollbar = tk.Scrollbar(text_frame)
        self.scrollbar.pack(side="right", fill="y")

        self.transcript_text = tk.Text(
            text_frame,
            bg=COLOR_CARD,
            fg="white",
            insertbackground="white",
            font=(FONT_NAME, self.final_font_size),
            wrap="word",
            yscrollcommand=self.scrollbar.set,
            relief="flat",
            padx=12,
            pady=12
        )
        self.transcript_text.pack(side="left", fill="both", expand=True)

        self.scrollbar.config(command=self.transcript_text.yview)

        self.transcript_text.insert("end", "Waiting for final captions...\n")
        self.transcript_text.config(state="disabled")

    def on_resize(self, event=None):
        if self.is_window_closing:
            return

        try:
            width = self.root.winfo_width()
            wrap = max(width - 100, 360)
            self.live_en_label.config(wraplength=wrap)
            self.live_zh_label.config(wraplength=wrap)
        except tk.TclError:
            pass

    def apply_font_size(self):
        self.safe_config(self.live_en_label, font=(FONT_NAME, self.live_en_font_size))
        self.safe_config(self.live_zh_label, font=(FONT_NAME, self.live_zh_font_size))
        self.safe_config(self.transcript_text, font=(FONT_NAME, self.final_font_size))

    def increase_live_font(self):
        self.live_en_font_size += 2
        self.live_zh_font_size += 2
        self.apply_font_size()

    def decrease_live_font(self):
        if self.live_en_font_size > 10:
            self.live_en_font_size -= 2
        if self.live_zh_font_size > 10:
            self.live_zh_font_size -= 2
        self.apply_font_size()

    def increase_final_font(self):
        self.final_font_size += 2
        self.apply_font_size()

    def decrease_final_font(self):
        if self.final_font_size > 9:
            self.final_font_size -= 2
        self.apply_font_size()

    def clear_for_new_session(self, raw_file, report_file):
        if self.is_window_closing:
            return

        try:
            self.transcript_text.config(state="normal")
            self.transcript_text.delete("1.0", "end")
            self.transcript_text.insert("end", "Waiting for final captions...\n")
            self.transcript_text.config(state="disabled")

            self.live_en_label.config(text="Listening...")
            self.live_zh_label.config(text="等待翻譯...")

            self.output_label.config(
                text=f"Raw: {raw_file}    |    HTML Report: {report_file}"
            )
        except tk.TclError:
            pass

    def append_final_caption(self, english_text, zh_text=""):
        if self.is_window_closing:
            return

        if not english_text:
            return

        now = datetime.now().strftime("%H:%M:%S")

        try:
            self.transcript_text.config(state="normal")

            current = self.transcript_text.get("1.0", "end").strip()
            if current == "Waiting for final captions...":
                self.transcript_text.delete("1.0", "end")

            self.transcript_text.insert("end", f"[{now}] English:\n{english_text}\n")

            if zh_text:
                self.transcript_text.insert("end", f"繁中:\n{zh_text}\n")

            self.transcript_text.insert("end", "\n")
            self.transcript_text.see("end")
            self.transcript_text.config(state="disabled")

        except tk.TclError:
            pass

    def set_buttons_state(self, state):
        if self.is_window_closing:
            return

        buttons = [
            self.finish_button,
            self.restart_button,
            self.close_button,
            self.live_up_button,
            self.live_down_button,
            self.final_up_button,
            self.final_down_button,
            self.settings_button
        ]

        for b in buttons:
            try:
                if b is not None and b.winfo_exists():
                    b.config(state=state)
            except tk.TclError:
                pass

    def finish_report(self):
        if self.is_window_closing:
            return
        self.controller.finish_and_generate_report(close_after=False, restart_after=False)

    def restart_session(self):
        if self.is_window_closing:
            return
        self.controller.finish_and_generate_report(close_after=False, restart_after=True)

    def finish_and_close(self, event=None):
        if self.is_window_closing:
            return "break"

        self.controller.finish_and_generate_report(close_after=True, restart_after=False)
        return "break"

    def open_settings(self):
        if self.is_window_closing:
            return
        SettingsDialog(self.root, self)

    def open_report(self):
        if self.last_report_file and os.path.isfile(self.last_report_file):
            webbrowser.open(Path(self.last_report_file).resolve().as_uri())

    def update_loop(self):
        if self.is_window_closing:
            return

        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return

        try:
            while True:
                msg_type, data = display_queue.get_nowait()

                if self.is_window_closing:
                    return

                if msg_type == "session_started":
                    self.current_session_id = data.get("session_id")
                    raw_file = data.get("raw_file", "")
                    report_file = data.get("report_file", "")

                    self.clear_for_new_session(raw_file, report_file)
                    self.safe_config(
                        self.status_label,
                        text=f"Status: New session started. Session ID: {self.current_session_id}"
                    )

                elif msg_type == "busy":
                    busy = data.get("busy", False)
                    text = data.get("text", "")

                    if busy:
                        self.set_buttons_state("disabled")
                    else:
                        self.set_buttons_state("normal")

                    self.safe_config(self.status_label, text="Status: " + text)

                elif msg_type == "report_done":
                    ok = data.get("ok", False)
                    report_file = data.get("report_file", "")

                    if ok:
                        self.last_report_file = report_file
                        self.safe_config(
                            self.status_label,
                            text=f"Status: HTML report generated: {report_file}"
                        )
                    else:
                        self.safe_config(
                            self.status_label,
                            text="Status: Report generation failed or transcript is empty."
                        )

                elif msg_type == "close_window":
                    self.is_window_closing = True

                    try:
                        self.root.after(100, self.destroy_window_safely)
                    except tk.TclError:
                        pass

                    return

                else:
                    session_id = None

                    if isinstance(data, dict):
                        session_id = data.get("session_id")

                    if session_id is not None and session_id != self.current_session_id:
                        continue

                    if msg_type == "live_en":
                        self.safe_config(self.live_en_label, text=data.get("text", ""))

                    elif msg_type == "live_zh":
                        self.safe_config(self.live_zh_label, text=data.get("text", ""))

                    elif msg_type == "final_en":
                        english_text = data.get("text", "")
                        self.safe_config(self.live_en_label, text=english_text)

                        if not ENABLE_ZH_TRANSLATION or not TRANSLATE_FINAL_TEXT:
                            self.append_final_caption(english_text)

                    elif msg_type == "final_bilingual":
                        english_text = data.get("english", "")
                        zh_text = data.get("zh", "")

                        self.safe_config(self.live_en_label, text=english_text)
                        self.safe_config(self.live_zh_label, text=zh_text)
                        self.append_final_caption(english_text, zh_text)

                    elif msg_type == "status":
                        self.safe_config(
                            self.status_label,
                            text="Status: " + data.get("text", "")
                        )

                    elif msg_type == "error":
                        self.safe_config(self.live_en_label, text=data.get("text", ""))

        except queue.Empty:
            pass

        if not self.is_window_closing:
            try:
                self.root.after(50, self.update_loop)
            except tk.TclError:
                pass


# ============================================================
# Main
# ============================================================

def main():
    missing = [p for p in (TOKENS, ENCODER, DECODER, JOINER) if not os.path.isfile(p)]
    if missing:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "SAGE Live Caption",
            "Bundled Sherpa-ONNX model files are missing.\n\n"
            "Please use the official SAGE-Live-Caption.exe built by the GitHub Actions workflow.\n\n"
            + "\n".join(missing),
            parent=root
        )
        root.destroy()
        return

    controller = AppController()

    root = tk.Tk()
    app = CaptionWindow(root, controller)

    controller.start_new_session()

    root.mainloop()

    print("\nApplication closed.")


if __name__ == "__main__":
    main()