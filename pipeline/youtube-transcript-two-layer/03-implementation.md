# Транскрипт по ссылке: два слоя (captions-first + локальный ASR)

Решение — [ADR-057](../../.claude/skills/architecture-research/adr/057-youtube-transcript-two-layer.md),
факты свипа — [cache/video-transcription-mcp-2026.md](../../.claude/skills/architecture-research/cache/video-transcription-mcp-2026.md).

## Этап 1-2. Исследование и выбор

`ecosystem_scan` (окно 30 дн.) дал один свежий кандидат — `samson-art/transcriptor-mcp`;
канонические репо окно не видит, поэтому добраны через GitHub API по звёздам
(`jkawamoto/mcp-youtube-transcript` 458★). README обоих верифицированы WebFetch.

Водораздел экосистемы — не репозиторий, а подход: captions-first (быстро, но только при наличии
субтитров) vs ASR по аудио (всегда, но платим GPU) vs канон A→B. Локальный контекст: ASR-половина
уже развёрнута (`whisper-windows-mcp` + Vulkan GPU + `large-v3-turbo`, `ffmpeg` 8.1.2), не хватало
только `yt-dlp`. Выбор пользователя — оба слоя из существующих компонентов, без второго Whisper.

## Этап 3. Реализация

- `pip install yt-dlp` в `.venv` → **2026.07.04**, CLI-шим `.venv/Scripts/yt-dlp.exe`.
- `.mcp.json` += сервер `youtube-transcript` (31-й), запуск `uvx --from git+…@ea333cad… mcp-youtube-transcript`.
- Скилл `whisper-transcription`: раздел «Транскрипт ПО ССЫЛКЕ» (правило A→B, таблица «когда какой
  слой», операционные ноты), обновлён `description` под новые триггеры.
- ADR-057 + запись в `adr/_index.json`.

## Этап 4. Проверка (живая)

| Что | Результат |
|---|---|
| stdio-хендшейк PyPI 0.3.5 | `initialize` OK, `tools/list` = **1** инструмент |
| stdio-хендшейк git 0.7.0 (`ea333cad`) | `tools/list` = **4** инструмента ⇒ пин на SHA |
| `tools/call get_transcript` (публичный 19-сек ролик) | 243 символа текста — слой A рабочий, блокировки IP не проявились |
| `yt-dlp -x --audio-format mp3 --print after_move:filepath` | файл получен; предупреждение «No supported JavaScript runtime» не помешало |
| слой B (`transcribe_audio`) | **ожидает явного согласия пользователя** — privacy-гейт сервера whisper |
| `lint_skills --strict` | 0 errors (4 warning'а — преджние BODY500 чужих скиллов) |

⚠ Рантайм нового MCP-сервера — после `/mcp reconnect`.
