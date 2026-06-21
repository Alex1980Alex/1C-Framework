# Пайплайн: Фикс segfault reindex_bsl_qwen3.py (torch 2.10 stack)

Корневой фикс инфра-бага (пункт 3 из сессии индексации ERP reference). Code-change в
общий скрипт `scripts/reindex_bsl_qwen3.py`. code-verify PASS.

## План
`reindex_bsl_qwen3.py --embedder qwen3-st` (FULL) падал segfault'ом (exit 139) на `model_load`
на стеке transformers 5.6.2 / sentence-transformers 5.4.1 / torch 2.10.0+cu128. Нужно устранить
в самом скрипте (а не обходным runpy-лаунчером), т.к. скрипт общий.

## Дизайн
Root cause (bisect + faulthandler): daemon-треды `ProgressTracker` (heartbeat + nvidia-smi
telemetry subprocess) гоняются с нативной загрузкой DLL при `from sentence_transformers import`
→ Windows loader-lock crash. Решение: pre-import torch+ST в `main()` ДО `make_tracker().start()`
(gate на in-process эмбеддеры e5/qwen3-st). Доп.: `_fa2_preflight_ok()` — изолированный
subprocess-probe FA2 с graceful-деградацией (защита от будущего flash-attn/torch ABI-дрейфа;
override BSL_FORCE_FA2). Установлено по ходу: FA2 сам по себе ИСПРАВЕН — ранние FA2-segfault'ы
были той же гонкой трекера.

## Реализация
4 правки `scripts/reindex_bsl_qwen3.py`: (1) `import subprocess`; (2) функция
`_fa2_preflight_ok()`; (3) pre-import block до старта трекера; (4) FA2-preflight block →
авто-деградация. ruff clean, py_compile OK. Прод git-hook (qwen3-tei/httpx) и reindex_bsl_parallel
не затронуты.

## Тест
code-verify (bug-fix-validation, reviewer-субагент) → **PASS** (обе root cause устранены,
минимально, без регрессии; 3 некритичные рекомендации). Эмпирика: отредактированный скрипт
запущен ТОЧНОЙ исходной падавшей командой (`qwen3-st --enable-fa2 --enable-sparse --limit 64` +
трекер) → `model_load DONE 25.7s` (VRAM 19 ГБ), 64 точки в Qdrant, segfault'а НЕТ. `_fa2_preflight_ok()`
→ True за 3.8с (FA2 работает). Полный ERP reindex перезапущен с FA2 (`bb201r5k6`).
Паттерн зафиксирован в skill-learning (pending). Память `feedback-bsl-reindex-segfault-torch210`
обновлена.
