# 01 - Архитектура: W2 B5 (autonomous 1C debugging - portability + cache)

Полная архитектура и декомпозиция - в roadmap [260708 §7](../../docs/roadmap/260708_ROADMAP_AUTONOMOUS_1C_DEBUGGING.md) (Эпик B, пункт B5).

Scope этого прогона: **B5.a** (portability) + **B5.b** (recursive cache-invalidation) в git-сабмодуле `tools/bsl-debug-server` (`uuid_index.py`).

Проблема (roadmap §3 B5): `uuid_index.py` `DEFAULT_CONFIG_SRC` захардкожен на `ИБTransportManagementDevelop` -> блокер отладки других ИБ (SVETLY/MFM); cache-invalidation по coarse top-dir `stat().st_mtime` отдаёт stale-кэш при вложенных `.mdo`-правках (правка модуля не бампает mtime корня `src/`).

Отложено в этом прогоне: B5.c/B5.d (file-cleanup: `test_rdbg*`/.log, Java-артефакты); W2 B1 (persistent JOB, env-heavy) + B3 (long-poll).
