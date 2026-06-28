# Scene-Detect MCP

MCP-сервер: извлечение кадров **при смене сцены** (PySceneDetect `ContentDetector`) — один
репрезентативный кадр на каждую сцену (сегмент между склейками). Точнее ffmpeg-фильтра
`select=gt(scene,X)`; не по таймкоду и не по I-frame'ам.

## Установка
```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Инструмент
`extract_scene_frames(video_path, threshold=27.0, output_dir="", num_images=1) -> dict`

- `threshold` — чувствительность `ContentDetector` (НИЖЕ = больше склеек; типично 20–35).
- `output_dir` — куда писать кадры (дефолт `<папка видео>/scene_frames`).
- `num_images` — кадров на сцену.
- Возврат: `{ok, count, scenes:[{n,start,end,start_sec,end_sec}], images:[пути], output_dir}`.
- `count=0` → склейки не обнаружены (один непрерывный план).

## Регистрация (`.mcp.json`)
```json
"scene-detect": {
  "command": "C:\\1С-Framework\\tools\\scene-detect-mcp\\.venv\\Scripts\\python.exe",
  "args": ["C:\\1С-Framework\\tools\\scene-detect-mcp\\scene_detect_mcp.py"],
  "timeout": 120000
}
```
После правки `.mcp.json` — полный рестарт Claude Code (не `/mcp reconnect`).
