# MCP-серверы транскрибации видео/аудио (Whisper/STT) — факты 2026

**Дата:** 2026-06-29
**Статус:** актуально (★/версии — снимок, сверять кликом перед фиксацией)
**Теги:** [mcp, transcription, whisper, faster-whisper, whisper.cpp, groq, speech-to-text, stt, russian, local, windows, gpu, video]

> Объективные факты из `ecosystem_scan` + WebFetch (GitHub README + реестры glama.ai/pulsemcp), US-регион.
> Решение/выбор — в ответе. Контекст-фильтр (наш профиль): Windows 11, CUDA-GPU (~24GB), RU-контент,
> приватность (внутренние 1С-встречи), бесплатно/self-host, Python-стек (.venv + stdio в `.mcp.json`).
> ⚠ Экосистема транскрибации-MCP **молодая и фрагментированная** — нет доминирующего канона; ★ низкие у всех.
> `ecosystem_scan` (окно 30 дн.) видит только свежак → канонические искал через реестры (freshness-gap memory).

## Кандидаты (verified WebFetch)

| Сервер | Бэкенд | Модели / RU | Local? | GPU | OS | Установка | Локальный файл |
|---|---|---|---|---|---|---|---|
| **ZahiriNatZuke/whisper-transcribe-mcp** | **faster-whisper** (local) + OpenAI API fallback | tiny…**large-v3**; все языки Whisper (RU ок) | да (100% офлайн при `[local]`) | faster-whisper native (CUDA если есть; **device-select не документирован**) | **Windows ок** (Py 3.12, ctranslate2 wheel) | `pip install "whisper-transcribe-mcp[local]"`; **ffmpeg/компилятор НЕ нужны (bundled)**; stdio через `uvx`/pip | `transcribe_file` (mp3/wav/m4a/ogg/flac/**webm**), `transcribe_base64`, `list_models` — абс. путь |
| **eviscerations/whisper-windows-mcp** | **whisper.cpp** (local) | **large-v3** (2.9GB) + **large-v3-turbo** (1.6GB, ~6× быстрее); RU да | да | **Vulkan** (NVIDIA/AMD/Intel, prebuilt `ggml-vulkan.dll`, без CUDA SDK); Vega56 ~14мин→3м22с | **Windows-native** | Node 18+, whisper.cpp бинарь (prebuilt `whisper-vulkan-win-x64.zip`→`C:\whisper\`), модель, **ffmpeg**; `npx whisper-windows-mcp` | mp3/wav нативно; **видео (.webm/.mp4…) авто-конверт через ffmpeg**; 12 tools (batch, субтитры SRT/VTT, progress, download/switch_model) |
| **bis-code/groq-whisper-mcp** | **Groq cloud** Whisper | large-v3-turbo (деф.) / large-v3 / distil; RU да | **нет (cloud)** | n/a (cloud, очень быстро) | Windows не тестир., кроссплатф. | clone+venv, `mcp`+`openai`; **нужен Groq API key** | `transcribe_video` (ffmpeg извлекает аудио 128/64kbps, fallback >25MB), `estimate_transcription_cost`; ~**$0.04/час** (9× дешевле OpenAI) |
| woosal1337/media-mcp | whisper.cpp (`whisper-cli`) | tiny…large-v3/turbo; RU да | да | — | mac/lin (win путь есть) | Node20+, ffmpeg, whisper-cli, yt-dlp | **только URL/соцсети** (нет локального пути) — дисквалиф. для .webm |
| vishalguptax/media-context-mcp | openai-whisper (local) | tiny…large, **деф. `small`** (слабо для RU) | да | не докум. | Win/mac/lin | `npx media-context-mcp setup`, ffmpeg | локальный путь (video/audio); tools `analyze_media`, `check_media_deps` |
| ZZtopBR/video-tools-mcp | openai-whisper (local) | не докум. | да | не докум. | Windows ок (venv) | Py 3.10+, ffmpeg, requirements | `vt_transcribe`+ffmpeg-нарезка; вход через `VT_VIDEOS_DIR` |

Реестровые (popularity, glama/pulsemcp, для полноты): `whisper.cpp` jwulff (~56★), arcaputo3 MCP Server Whisper (~55★, OpenAI+GPT-4o cloud), MacWhisper (mac-only). Все — те же 3 бэкенда (faster-whisper / whisper.cpp / cloud).

## Движки (суть выбора)
- **faster-whisper** (CTranslate2): лучший локальный — быстрее openai-whisper ~4×, ниже VRAM, large-v3, CUDA. На Windows GPU требует CUDA-runtime/cuDNN DLL (CPU — из коробки).
- **whisper.cpp**: C++ бинарь, large-v3/turbo, **Vulkan GPU prebuilt** (без CUDA SDK) — самый беспроблемный GPU на Windows; нужен ffmpeg для видео.
- **cloud (Groq)**: large-v3 качество + max скорость + ~бесплатно, НО аудио уходит в облако (приватность) + API key.

## Вывод для нашего профиля
1. **whisper-transcribe-mcp (faster-whisper, local)** — лучший баланс: топ-движок + large-v3 (RU) + 100% локально (приватность) + бесплатно + **pip без ffmpeg/компилятора** (идеально ложится в .venv + stdio как все наши MCP). Минус: GPU-ускорение на Windows может потребовать cuDNN (CPU работает сразу; 5-мин файл = минуты на CPU / секунды на GPU).
2. **whisper-windows-mcp (whisper.cpp)** — если нужен гарантированный GPU без возни с CUDA (**Vulkan prebuilt**), батч, авто-субтитры, прогресс, авто-конверт видео. Тяжелее (Node+бинарь+модель+ffmpeg), но самый активный/feature-rich, Windows-native.
3. **groq-whisper-mcp (cloud)** — если запись НЕ чувствительна и нужен max-скорость/zero-setup; нужен Groq key (есть free tier).

Практика: у записи Телемоста есть и `.webm`, и **`.mp3` (аудиодорожка уже извлечена)** → можно скармливать `.mp3` напрямую в любой аудио-MCP, шаг ffmpeg-извлечения не нужен.
