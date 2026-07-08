# 02 - Дизайн: B5.a + B5.b

## B5.a portability
- env `BSL_DEBUG_CONFIG_SRC_MAP="Alias=path;..."` ('='-сепаратор из-за ':' в Windows-путях).
- per-alias `UUIDIndex`-реестр (`_indexes_by_alias` под `_alias_lock`; `_cache_path_for`=sha1 -> свой cache-файл на каждый config_src).
- `set_active_config(alias)` вызывается в `RDBGClient.__init__` (одно live RDBG-соединение за раз -> module-global `_active_alias` точен, не эвристика).
- `resolve_uuid`/`get_source_info`: опц. `alias`, fallback на `_active_alias`. Покрывает module-level вызовы без alias (`_enrich_stack`, `autonomy.read_source_context`/`inspect_frame`).
- **Инвариант**: незаданный env -> byte-identical маршрут на default singleton (unmapped/None alias -> `get_default_index`).

## B5.b cache-invalidation
- `_src_fingerprint` = `{max_mtime, count, total_size}` над `config_src.rglob("*.mdo")` (stat-only, без чтения) вместо `config_src.stat().st_mtime`.
- Ключ кэша `src_mtime` -> `src_fingerprint`; старые кэши инвалидируются (None != dict) и ребилдятся.

**Одобрение**: дизайн = roadmap §7.6 (roadmap-driven); подтверждён code-verify behavior-preservation PASS.
