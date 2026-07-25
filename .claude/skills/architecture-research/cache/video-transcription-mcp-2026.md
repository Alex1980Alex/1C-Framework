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

---

## Дополнение 2026-07-25: транскрипт ПО ССЫЛКЕ (YouTube и др.)

Отдельный подкласс: вход = URL, а не локальный файл. В экосистеме два архитектурно разных подхода
(и это главный водораздел, а не выбор конкретного репо).

| Подход | Как работает | Плюсы | Минусы |
|---|---|---|---|
| **A. Captions-first** | тянет ГОТОВЫЕ субтитры (`youtube-transcript-api` либо `yt-dlp --write-subs`) | мгновенно, бесплатно, без GPU и ffmpeg | только если субтитры ЕСТЬ; YouTube блокирует IP датацентров (отсюда прокси-параметры в канонических репо); авто-субтитры RU — качество среднее, без пунктуации |
| **B. ASR по аудио** | `yt-dlp -x` → аудио → Whisper | работает ВСЕГДА, качество large-v3 (RU хорошо), приватно при локальном движке | считает время/GPU, нужен ffmpeg |
| **A→B (канон)** | субтитры, при отсутствии — ASR-fallback | покрывает оба случая | сложнее конфигурация (два бэкенда) |

### Верифицированные кандидаты (WebFetch README, 2026-07-25)

| Репо | ★ / лиц. | Стек | Как получает | Инструменты | Обход блокировок |
|---|---|---|---|---|---|
| **jkawamoto/mcp-youtube-transcript** | **458★**, MIT, upd. 2026-07-14 (252 коммита, 69 форков) | Python, запуск `uvx --from git+…` | **только captions** (`youtube-transcript-api`); ASR-fallback'а НЕТ | `get_transcript`, `get_timed_transcript`, `get_video_info`, `get_available_languages`; пагинация `next_cursor`; `lang` (деф. `en`) | **Webshare-прокси** (`WEBSHARE_PROXY_USERNAME/PASSWORD`) + `HTTP(S)_PROXY`; cookies не упомянуты |
| **samson-art/transcriptor-mcp** | 18★, MIT (2025) | Node ≥20, Docker-first (`artsamsonov/transcriptor-mcp`), stdio + HTTP/SSE | **yt-dlp субтитры → Whisper fallback** (`WHISPER_MODE`: локальный faster-whisper/whisper.cpp ЛИБО OpenAI-совместимый API `WHISPER_API_KEY`/`WHISPER_BASE_URL`) | 8 tools: `get_transcript`, `get_raw_subtitles` (SRT/VTT + пагинация, `response_limit` 1000…200000, деф. 50000), `get_available_subtitles`, `get_video_info`, `get_video_chapters`, `get_video_frame`, `get_playlist_transcripts`, `search_videos` | `COOKIES_FILE_PATH`; опц. Redis-кеш (`CACHE_MODE=redis`); `YT_DLP_TIMEOUT` |
| sinco-lab/mcp-youtube-transcript | 34★, TS, upd. 2026-06-13 | TypeScript | captions | — | — |
| woosal1337/media-mcp | (из свипа 06-29) | Node20 + ffmpeg + whisper-cli + **yt-dlp** | URL/соцсети, whisper.cpp | — | — |

Прочие `mcp-youtube-transcript`-одноимённые форки: 0-6★ (шум; `ProjectViventium` — пустой placeholder-миррор канона).

11 платформ у transcriptor-mcp: YouTube, Twitter/X, Instagram, TikTok, Twitch, Vimeo, Facebook, Bilibili, VK, Dailymotion, Reddit (поиск — только YouTube).

### Повторяющиеся приёмы (best practices экосистемы)
1. **Captions-first, ASR-fallback** — не транскрибировать то, что уже есть текстом.
2. **Пагинация ответа** (`next_cursor` + лимит символов) — часовое видео не влезает в один tool-result.
3. **Прокси/cookies как first-class конфиг** — YouTube режет IP датацентров; у канонического репо это вынесено в CLI-флаги и env.
4. **Кеш по video_id** (Redis у transcriptor) — повторный вопрос по тому же видео не платит второй раз.
5. **Разделение tool'ов «текст» / «с таймкодами» / «языки» / «метаданные»** вместо одного мега-tool.

### Локальный контекст (проверено на машине 2026-07-25)
- MCP `whisper` в [`.mcp.json`](../../../../.mcp.json) = **`whisper-windows-mcp`** (npx) с `WHISPER_CLI_PATH=C:\whisper\Release\whisper-cli.exe` и моделью `ggml-large-v3-turbo.bin` (1.6 ГБ) — оба файла на месте; ASR-половина задачи уже решена и ускорена GPU (Vulkan, без CUDA SDK). Принимает **локальный путь**, не URL.
- `ffmpeg` **есть** (8.1.2 full build, gyan.dev).
- **`yt-dlp` отсутствует** — ни CLI, ни python-пакет в `.venv`. Это единственное недостающее звено для пути «по ссылке».
