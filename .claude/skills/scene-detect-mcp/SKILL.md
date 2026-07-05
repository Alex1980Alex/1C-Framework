---
name: scene-detect-mcp
description: "Извлечение кадра на каждую смену сцены через PySceneDetect ContentDetector (HSV-взвешенный детект склеек), точнее ffmpeg select=gt(scene,X). Триггеры: 'раскадровка видео', 'смена сцены', 'кадр при смене сцены', 'scene detection', 'извлечь ключевые кадры', 'PySceneDetect', 'storyboard frames'. НЕ для кадров по таймкоду/интервалу — используй ffmpeg -vf fps=N. НЕ для YouTube-метаданных/транскриптов — используй youtube-mcp."
---

# scene-detect-mcp — кадры при смене сцены (PySceneDetect)

MCP-сервер `scene-detect` ([`tools/scene-detect-mcp/`](../../../tools/scene-detect-mcp/scene_detect_mcp.py)): извлечение кадра **на каждую смену сцены** через PySceneDetect `ContentDetector` (HSV-взвешенный детект склеек). Точнее ffmpeg-фильтра `select=gt(scene,X)`; не по таймкоду и не по I-frame'ам. ИСПОЛЬЗУЙ когда нужно раскадровать видео по сменам сцен.

Триггеры: 'раскадровка видео', 'смена сцены', 'кадр при смене сцены', 'scene detection', 'извлечь ключевые кадры', 'PySceneDetect', 'scene-detect MCP', 'storyboard frames', 'видео на кадры по сценам', 'detect scene changes'.

НЕ для кадров по таймкоду/интервалу (→ ffmpeg `-vf fps=N`). НЕ для YouTube-метаданных/транскриптов (→ youtube-mcp).

## Инструмент
`mcp__scene-detect__extract_scene_frames(video_path, threshold=27.0, output_dir="", num_images=1) -> dict`
- `threshold` — чувствительность `ContentDetector` (**НИЖЕ = больше склеек**; типично 20–35; дефолт 27).
- `output_dir` — куда писать кадры (дефолт `<папка видео>/scene_frames`).
- `num_images` — кадров на сцену.
- Возврат: `{ok, count, scenes:[{n,start,end,start_sec,end_sec}], images:[пути], output_dir}`.
- `count=0` → склейки не обнаружены (один непрерывный план).

## Установка / запуск
- Код + venv: `tools/scene-detect-mcp/` (`scene_detect_mcp.py`, `.venv` со `scenedetect`+`opencv-python-headless`+`mcp`; `pip install -r requirements.txt`).
- Зарегистрирован в `.mcp.json` как `scene-detect`. После правки `.mcp.json` — **полный рестарт Claude Code** (не `/mcp reconnect`).

## Под капотом (Source: PySceneDetect v0.7)
`detect(video, ContentDetector(threshold))` → сцены (пары FrameTimecode) → `save_images(scenes, open_video(video), num_images, output_dir)`. `save_images` импортируется устойчиво: `scenedetect.output` (v0.7) → fallback `scenedetect.scene_manager` (v0.6).

## Антипаттерны (из реализации)
| Плохо | Почему | Правильно |
|---|---|---|
| Кадр по таймкоду для «смены сцены» | интервал/I-frame ≠ визуальная смена | `ContentDetector` (этот MCP) |
| Тест на solid-цветах | мягкие переходы недоловлены (smoke нашёл 1 из 2 склеек) | реальное видео ИЛИ threshold↓ (20) |
| `/mcp reconnect` после правки `.mcp.json` | не перечитывает конфиг | полный рестарт CLI |
| Голый `python -m venv` | Store-alias python (exit 49) | `.venv/Scripts/python.exe -m venv …` |
