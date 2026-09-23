# SAGE Live Caption

**版本：1.0.0.1**  
**Windows 即時英文字幕・繁體中文 AI 翻譯・會議報告產生工具**

> **Listen → Translate → Report**  
> 聽取 Windows 播放聲音 → 即時產生英文字幕 → AI 翻譯繁中 → 自動整理會議報告

SAGE Live Caption 的介面設計方向與 **SAGE / GetacPatentAI Studio** 相同：主畫面保持簡單，進階設定集中在 **Settings**。一般使用者不需要安裝 Python，也不需要使用 CMD、PowerShell 或輸入任何指令。

---

## 主要功能

- **Windows Speaker Live Caption**：透過 WASAPI Loopback 直接擷取目前 Windows 播放的聲音。
- **Sherpa-ONNX Streaming ASR**：在本機即時辨識英文語音。
- **繁體中文 AI 翻譯**：Final Caption 才送到 AI Server，減少不必要的 API 呼叫。
- **OpenAI-Compatible AI Server**：支援 vLLM 等 `/v1/chat/completions` 相容服務。
- **Environment Check**：一鍵檢查語音模型、Windows Audio、Output Folder、AI Server。
- **AI Meeting Report**：會議結束後自動清洗逐字稿並產生雙語 HTML 報告。
- **Single EXE**：正式使用者只需要執行 `SAGE-Live-Caption.exe`。

---

# 一般使用者：如何使用

## 1. 下載 EXE

到本專案的 **Releases** 頁面下載：

```text
SAGE-Live-Caption.exe
```

下載後直接雙擊執行即可，不需要另外安裝 Python、Sherpa-ONNX 或 PyAudio。

> 如果目前 Releases 尚未放出 EXE，也可以到 GitHub 的 **Actions → Build Windows EXE → Artifacts** 下載最新 Windows x64 建置版本。

---

## 2. 第一次使用：設定 AI Server

程式啟動後，按右上角：

```text
Settings
```

在 **AI Server** 區域設定：

| 項目 | 說明 |
|---|---|
| Server URL | OpenAI-compatible API URL |
| Model | AI Server 上實際載入的模型名稱 |
| API Key | 如果 Server 有設定 API Key 就填入；沒有可留白 |
| Enable Traditional Chinese translation and AI report | 啟用繁中翻譯與 AI Meeting Report |

### vLLM 範例

如果 vLLM Server 在本機：

```text
Server URL:
http://127.0.0.1:8000/v1/chat/completions
```

如果 vLLM Server 在公司內網，例如：

```text
http://YOUR-AI-SERVER:8000/v1/chat/completions
```

Model 必須與 AI Server 實際提供的 model name 相同，例如：

```text
google/gemma-4-31B-it
```

設定完成後可先按：

```text
Test AI Server
```

成功時會顯示：

```text
Connection successful
```

最後按 **Save** 儲存。

設定檔會儲存在目前 Windows 使用者的 Local AppData，不會寫進 EXE。

---

## 3. 執行 Environment Check

在 **Settings** 中按：

```text
Run Check
```

程式會自動檢查：

| 檢查項目 | 內容 |
|---|---|
| Windows | 是否為 Windows 環境 |
| Speech Engine | Sherpa-ONNX 與內建 ASR model 是否正常 |
| Windows Audio | WASAPI Loopback 是否能抓到目前播放裝置 |
| Output Folder | 報告資料夾是否可寫入 |
| AI Server | API URL、Model、API Key 與 Server 回應是否正常 |

正常會看到：

```text
✓ Ready
```

有問題則會看到：

```text
✕ Error — 原因
```

如果關閉 AI 翻譯功能，AI Server 檢查會自動顯示 Skip，不會影響純英文 Live Caption。

---

# 4. 開始使用 Live Caption

SAGE Live Caption 會自動抓目前的 **Windows Default Output Device**，例如：

- Notebook Speaker
- Realtek Audio
- AirPods
- USB Headset
- HDMI Audio

因此它主要聽的是「Windows 正在播放的聲音」，不是只聽麥克風。

適合使用：

- Microsoft Teams Meeting
- Zoom Meeting
- YouTube / Training Video
- 錄音檔播放
- 任何從 Windows Speaker / Headset 播放的英文聲音

主畫面流程很簡單：

```text
1  Listen
   ↓
2  Translate
   ↓
3  Report
```

### English Live Caption

上方會即時顯示 Sherpa-ONNX 辨識中的英文字幕。

### 繁體中文翻譯

一句英文判定完成後，程式會將 Final Caption 送到設定的 AI Server，再顯示繁體中文翻譯。

### Final Transcript

下方保留已確認的英文與繁中內容，方便會議中即時查看。

---

# 5. 會議完成後產生 AI Report

按：

```text
Finish & Report
```

程式會：

```text
停止 Live Caption
      ↓
等待最後的翻譯完成
      ↓
整理 Raw Transcript
      ↓
AI 清洗 ASR 內容
      ↓
產生繁體中文逐字稿
      ↓
產生 Summary / Key Points / Action Items
      ↓
輸出 HTML Meeting Report
```

完成後按：

```text
Open Report
```

即可用預設瀏覽器開啟報告。

---

# 6. Restart

如果要結束目前會議並立即開始新的 Session，按：

```text
Restart
```

目前 Session 會先完成儲存與報告處理，再開始新的 Live Caption Session。

---

# 7. 報告儲存位置

預設輸出到：

```text
Documents\SAGE Live Caption\Output
```

每次 Session 會依時間建立檔案，例如：

```text
sherpa_speaker_caption_raw_20260923_093000.txt
sherpa_speaker_caption_report_20260923_093000.html
```

HTML Report 內容包含：

- Meeting Topic / 會議主題
- Key Summary / 重點摘要
- Overall Summary / 會議總結
- Cleaned English Transcript / 清洗後英文逐字稿
- 繁體中文逐字稿
- Key Points / 重點
- Action Items / 待辦事項
- Unclear Parts / 不確定內容
- LLM Reflection Report / LLM 心得報告
- Raw Transcript / 原始逐字稿

---

# 架構

```text
Windows Speaker / Teams / Zoom / Video
                 │
                 ▼
          WASAPI Loopback
                 │
                 ▼
      Sherpa-ONNX Streaming ASR
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
 English Live        Final Caption
 Caption                  │
                          ▼
                 OpenAI-compatible
                    AI Server
                    / vLLM
                          │
                          ▼
                   繁中翻譯
                          │
                          ▼
                  Final Transcript
                          │
                          ▼
                   Finish & Report
                          │
                          ▼
                   AI Cleanup
                          │
                          ▼
                HTML Meeting Report
```

---

# 隱私與資料流

Sherpa-ONNX 語音辨識是在 **Windows 本機** 執行。

只有在啟用 AI 翻譯 / AI Report 時，Final Caption 與逐字稿內容才會傳送到使用者在 **Settings → AI Server** 指定的 Server。

因此如果 AI Server 是公司內部的 vLLM Server，SAGE Live Caption 本身不需要使用公有雲 LLM。

> 使用前仍應依公司資訊安全政策確認會議內容是否允許傳送到所設定的 AI Server。

---

# GitHub 自動產生 Windows EXE

專案內含：

```text
.github/workflows/build-windows-exe.yml
```

GitHub Actions 會在 Windows x64 環境：

1. 安裝 Python build dependencies。
2. 下載 Sherpa-ONNX 官方英文 Streaming Zipformer model。
3. 驗證 model files。
4. 使用 PyInstaller 打包。
5. 產生單一：

```text
SAGE-Live-Caption.exe
```

因此一般使用者不需要自己 Build，也不需要輸入任何安裝指令。

---

# Source Code

主要程式：

```text
src/sage_live_caption.py
```

PyInstaller 設定：

```text
build/SAGE-Live-Caption.spec
```

Build dependencies：

```text
requirements-build.txt
```

Runtime dependencies：

```text
requirements.txt
```

---

# 版本

## 1.0.0.1

- SAGE / GetacPatentAI Studio 風格簡潔主畫面。
- Settings 加入 AI Server 設定。
- 支援 Server URL / Model / API Key。
- 加入 Test AI Server。
- 加入 Environment Check。
- 檢查 Windows、Sherpa model、WASAPI Loopback、Output Folder、AI Server。
- Sherpa-ONNX 英文 Streaming ASR。
- Final Caption 繁體中文 AI 翻譯。
- 自動產生雙語 HTML Meeting Report。
- 支援 GitHub Actions 自動建置 Windows Single EXE。

---

## 專案定位

**SAGE Live Caption** 不只是字幕工具，而是一個簡單的本機 AI Meeting Assistant：

> **即時聽取 → 即時字幕 → AI 翻譯 → 逐字稿 → AI 會議報告**
