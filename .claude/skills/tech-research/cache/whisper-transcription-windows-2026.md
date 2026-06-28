---
topic: whisper-transcription-windows-2026
domain: tools
category: setup
created: 2026-06-29
last_verified: 2026-06-29
version: faster-whisper 1.2.1 / ctranslate2 4.8.0 / whisper-windows-mcp 2.3.0 / whisper.cpp Vulkan v1.4.0
sources: faster-whisper README (SYSTRAN), whisper-windows-mcp (eviscerations), live setup on RTX 3090
keywords: [whisper, transcription, faster-whisper, whisper.cpp, vulkan, cuda, cudnn, cublas, ggml, mcp, windows, gpu, ffmpeg, ru, mp3]
---

# Транскрибация аудио/видео на Windows — faster-whisper (CUDA) vs whisper.cpp (Vulkan MCP)

> Заземлено на живой установке (RTX 3090 24GB, Windows 11). Два рабочих пути; оба дают large-v3.

## 1. Идентификация
Локальная транскрибация (ASR) RU/multi. Два движка:
- **faster-whisper** (CTranslate2) — Python, GPU=CUDA. Лучший движок на NVIDIA, ставится в venv.
- **whisper.cpp** (`whisper-windows-mcp`) — C++ бинарь, GPU=**Vulkan** (NVIDIA/AMD/Intel, без CUDA SDK), ставится как **MCP-сервер** (звать из Claude Code).
Выбор: NVIDIA + скрипт/скорость → faster-whisper; постоянный MCP-инструмент / не-NVIDIA GPU → whisper.cpp-Vulkan.

## 2. Установка / настройка

### A. faster-whisper на GPU (CUDA, Windows)
Драйвер NVIDIA НЕ содержит cuBLAS/cuDNN (отсюда `cublas64_12.dll not found`). Toolkit ставить не нужно — хватает pip-колёс (ct2 4.8 = CUDA 12 / cuDNN 9):
```
<venv>\Scripts\python.exe -m pip install faster-whisper nvidia-cublas-cu12 "nvidia-cudnn-cu12==9.*"
```
**Windows-нюанс:** Python 3.8+ НЕ ищет зависимые DLL в PATH → перед `from faster_whisper import WhisperModel`:
```python
import os, glob, sys
for d in glob.glob(os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "*", "bin")):
    os.add_dll_directory(d)
```
Затем `WhisperModel("large-v3", device="cuda", compute_type="float16")`. CPU-fallback: `device="cpu", compute_type="int8"`.

### B. whisper.cpp Vulkan как MCP (`whisper-windows-mcp`)
1. `npm install -g whisper-windows-mcp` (Node ≥18). Пакет НЕ несёт бинарь.
2. Бинарь Vulkan отдельно: release-asset `whisper-vulkan-win-x64.zip` (v1.4.0) → распаковать в `C:\whisper\Release\` (`whisper-cli.exe`, `ggml-vulkan.dll` 57MB, `whisper.dll`, `ggml*.dll`).
3. GGML-модель: `ggml-large-v3.bin` (~3.1GB, макс. качество) или `ggml-large-v3-turbo.bin` (~1.6GB, ~6× быстрее, мин. потеря) → `C:\whisper\models\`. Источник: `huggingface.co/ggerganov/whisper.cpp`.
4. `.mcp.json` (Claude Code; в Claude Desktop — `claude_desktop_config.json`), пути с `\\`:
```json
"whisper": {
  "command": "npx",
  "args": ["-y", "whisper-windows-mcp"],
  "env": {
    "WHISPER_CLI_PATH": "C:\\whisper\\Release\\whisper-cli.exe",
    "WHISPER_MODEL": "C:\\whisper\\models\\ggml-large-v3.bin"
  },
  "timeout": 120000
}
```
5. **Полный рестарт Claude Code** (не `/mcp reconnect`). Проверка — tool `check_system` (GPU/Vulkan).
- **ffmpeg** нужен только для видео/не-(wav/mp3/flac/ogg). `winget install ffmpeg` (+ опц. env `FFMPEG_PATH`). MP3 идёт нативно.

## 3. Core API / CLI
- whisper-cli ключи: `-m model -f audio -l ru -osrt -otxt -oj --device 0 -fa` (flash-attn вкл по умолч.), VAD: `--vad`. Форматы: flac/mp3/ogg/wav.
- faster-whisper: `model.transcribe(path, language="ru", beam_size=5, vad_filter=True)` → `(segments_generator, info)`; `info.duration/language/language_probability`.

## 4. Паттерны
- Модель: large-v3 = макс. качество RU; turbo = GPU-скорость при near-quality (1-строчная замена `WHISPER_MODEL`).
- Видео-встреча: если рядом есть `.mp3`-дорожка — скармливать её (форматы wav/mp3/flac/ogg идут без ffmpeg).
- На 3090 Vulkan видит `NV_coopmat2` matrix cores, fp16 — быстрый GPU без CUDA.

## 5. Архитектура / trade-offs
- Форматы моделей НЕ взаимозаменяемы: faster-whisper = **CTranslate2** (Systran/faster-whisper-large-v3), whisper.cpp = **GGML** (ggerganov/whisper.cpp). Качать под свой движок.
- Vulkan (whisper.cpp): vendor-agnostic, prebuilt, без cuDNN. CUDA (faster-whisper): обычно быстрее на NVIDIA, но требует cuBLAS+cuDNN.

## 6. Диагностика (живые грабли)
- **HF python-загрузчик (huggingface_hub) виснет на 0 байт** на большом blob (Xet/hf_transfer); мелкие конфиги качаются. Фикс: качать модель через **curl** (`-L -C - --retry`), сеть при этом здорова (~4 MB/s). `HF_HUB_DISABLE_XET=1`/`HF_HUB_ENABLE_HF_TRANSFER=0` НЕ помогли — именно curl-bypass.
- **`cublas64_12.dll not found`** при device=cuda = нет cuBLAS/cuDNN (не в драйвере). См. §2.A. `nvidia-smi` «CUDA Version 13.2» = max драйвера, НЕ установленный toolkit.
- `cuda device count: 1` у ctranslate2 ≠ готовность счёта (driver API видит GPU, но нужны compute-либы).
- venv python на Windows = шим → один прогон = 2 процесса (шим+real); kill по `CommandLine -like '*whisper-venv*'`.

## 7. Источники
- **[GitHub]** github.com/SYSTRAN/faster-whisper — README GPU (cuBLAS CUDA12 + cuDNN9, `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12==9.*`)
- **[GitHub]** github.com/eviscerations/whisper-windows-mcp — install/config, releases v1.4.0 (whisper-vulkan-win-x64.zip), tools `download_model`/`check_system`
- **[HF]** huggingface.co/ggerganov/whisper.cpp — GGML модели; huggingface.co/Systran/faster-whisper-large-v3 — CT2 модель
- **[наш опыт, 2026-06-29]** RTX 3090: Vulkan видит NV_coopmat2; HF-hub hang → curl bypass; CPU int8 = 5-мин аудио за ~3.5 мин
- **[arch cache]** [[video-transcription-mcp-2026]] — сравнение MCP-серверов транскрибации
