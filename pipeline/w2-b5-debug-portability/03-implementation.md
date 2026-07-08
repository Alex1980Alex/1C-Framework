# 03 - Реализация

Сабмодуль `tools/bsl-debug-server` commit **91e89a8**; parent **834f1f277** (gitlink-bump + roadmap §статус).

Файлы:
- `uuid_index.py` (+124/-19): alias-машинерия (`_parse_config_src_map`/`_cache_path_for`/`set_active_config`/`get_index_for_alias`/`_indexes_by_alias`/`_active_alias`), `_src_fingerprint` вместо `_src_mtime`, `_load_cache`/`_save_cache`/`_ensure_index` прокидывают fingerprint, alias-aware `resolve_uuid`/`get_source_info`. Удалён мёртвый `_index_mtime`.
- `mcp_debug_server.py` (+7): `uuid_index.set_active_config(infobase_alias)` в `RDBGClient.__init__`; `alias=self.infobase_alias` в `eval_locals_auto`.
- `tests/test_uuid_index.py` (+151): 12 новых тестов.
