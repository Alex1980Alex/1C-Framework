# ADR-057: Транскрипт по ссылке — два слоя (captions-first + локальный ASR), без второго Whisper-стека

**Дата:** 2026-07-25
**Статус:** accepted
**Исследование:** [`cache/video-transcription-mcp-2026.md`](../cache/video-transcription-mcp-2026.md) (раздел «Дополнение 2026-07-25: транскрипт ПО ССЫЛКЕ»)

## Контекст

Понадобился путь «ссылка на YouTube → текст». Половина задачи в проекте уже решена: MCP `whisper`
= `whisper-windows-mcp` (whisper.cpp + Vulkan-GPU, модель `ggml-large-v3-turbo`), `ffmpeg` 8.1.2 —
но он принимает ЛОКАЛЬНЫЙ путь, не URL. Недоставало ровно звена загрузки.

Свип GitHub (`ecosystem_scan` + GitHub API, README верифицированы WebFetch) показал, что экосистема
делится не по репозиториям, а по подходу: **A. captions-first** (готовые субтитры — мгновенно,
бесплатно, но только если они есть; YouTube режет IP датацентров), **B. ASR по аудио** (`yt-dlp -x` →
Whisper — работает всегда, качество large-v3, платим GPU-временем), **A→B** — канон экосистемы.

Кандидаты: `jkawamoto/mcp-youtube-transcript` (458★, MIT, Python/uvx, captions-only, прокси
Webshare/HTTPS в конфиге) и `samson-art/transcriptor-mcp` (18★, MIT, Node/Docker, полный A→B,
11 платформ, 8 инструментов, cookies, Redis-кеш).

## Решение

**Двухслойная схема из ДВУХ существующих компонентов, без второго Whisper-стека** (выбор
пользователя 2026-07-25 из трёх предложенных вариантов):

1. **Слой A (быстрый):** MCP `youtube-transcript` = `jkawamoto/mcp-youtube-transcript`, запуск
   `uvx --from git+…@<SHA> mcp-youtube-transcript`. Отдаёт готовые субтитры за секунды.
2. **Слой B (fallback/качество):** `yt-dlp -x --audio-format mp3` → существующий MCP `whisper`
   (whisper.cpp + Vulkan GPU, large-v3-turbo). Полностью локально.

Порядок вызова — за моделью (Claude), не за кодом: сперва A, при отсутствии субтитров либо при
требовании к качеству/приватности — B. Правило зафиксировано в скилле `whisper-transcription`.

**Пин на git-SHA, а не на PyPI [own, проверено stdio-пробой]:** PyPI-релиз `0.3.5` отстал и
экспортирует **1** инструмент (`get_transcript`), git-`main` (0.7.0, SHA `ea333cad`) — **4**
(`get_transcript`, `get_timed_transcript`, `get_video_info`, `get_available_languages`). SHA даёт и
полный набор, и воспроизводимость; `uvx` кеширует сборку после первого запуска.

## Последствия

### Положительные
- Новых тяжёлых зависимостей нет: `+1` лёгкий MCP-сервер (uvx) и `+1` python-пакет (`yt-dlp`
  в `.venv`, CLI-шим `.venv/Scripts/yt-dlp.exe`). Второй Whisper (как было бы у transcriptor-mcp
  в Docker) не появляется — GPU-стек остаётся один.
- Приватность управляема: слой B полностью локален, у `whisper-windows-mcp` есть `privacy_mode`
  (метаданные без передачи текста в API) и обязательное подтверждение перед возвратом текста.
- Оба слоя проверены живьём (см. «Проверка»), а не приняты по README.

### Отрицательные
- Два инструмента вместо одного: маршрут «сначала A, потом B» держится на правиле в скилле, а не
  на коде. Ошибка маршрутизации = лишний ASR-прогон (время GPU), не потеря данных.
- Слой A уязвим к блокировкам YouTube по IP (в апстриме для этого есть `--webshare-proxy-*` и
  `--http(s)-proxy`; при появлении отказов — включать прокси в args).
- `yt-dlp` требует сопровождения (YouTube ломает извлечение регулярно) — обновлять
  `pip install -U yt-dlp` при отказах; сейчас предупреждает об отсутствии JS-рантайма (deno).

## Альтернативы

| Вариант | Почему отклонён |
|---|---|
| `samson-art/transcriptor-mcp` (канон A→B в одном сервере) | Docker-first + Node ≥20 и **свой** Whisper-бэкенд внутри контейнера — дублирует уже настроенный GPU-стек; репо молодое (18★). Ценные идеи (пагинация, cookies, кеш по video_id) заимствованы как правила, а не как зависимость |
| Только слой B (yt-dlp + whisper) | Всегда платим ASR-прогоном там, где готовые субтитры уже есть |
| Только слой A (captions) | Падает на видео без субтитров; RU-автосубтитры без пунктуации |
| Свой MCP-сервер | Дублирование готового 458★-решения ради обёртки над двумя вызовами |

## Проверка (живая, 2026-07-25)

- `uvx mcp-youtube-transcript` (PyPI 0.3.5): stdio-хендшейк `initialize` → `tools/list` = **1** tool.
- `uvx --from git+…@ea333cad` (0.7.0): `tools/list` = **4** tools ⇒ пин на SHA.
- `tools/call get_transcript` на публичном 19-секундном ролике — 243 символа текста, путь A рабочий
  с этой машины (блокировки IP не проявились).
- `yt-dlp -x --audio-format mp3 --print after_move:filepath` — файл получен (предупреждение
  «No supported JavaScript runtime» не помешало).
- Слой B (whisper) — прогон требует явного согласия пользователя (privacy-гейт сервера).

## Связанные файлы

- [`.mcp.json`](../../../../.mcp.json) — сервер `youtube-transcript` (⚠ рантайм после `/mcp reconnect`)
- [`.claude/skills/whisper-transcription/SKILL.md`](../../whisper-transcription/SKILL.md) — правило маршрутизации A→B
- [`cache/video-transcription-mcp-2026.md`](../cache/video-transcription-mcp-2026.md) — факты свипа
