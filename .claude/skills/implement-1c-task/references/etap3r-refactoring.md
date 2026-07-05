# Этап 3R: Рефакторинг через bsl-semantic-search refactor (условный)

**Применяется только если decision gate (SKILL.md) определил операцию как рефакторинг.**

1. **Классифицировать символ** (routing matrix v2 — `src/bsl/semantic_search/refactor/routing_matrix.yaml`):
   - `local_variable` / `parameter` / `module_local_proc` → ast-grep in-file (confidence 0.95)
   - `module_export_proc` → ast-grep cross-file через Neo4j граф (confidence 0.85)
   - `form_handler` → ast-grep + XML (confidence 0.95 после R5.5 calibration)
   - `unknown` / динамические вызовы (`Выполнить()`) → **manual tier**

2. **Вызвать нужный инструмент** (ВСЕГДА сначала `dry_run: true`):
   ```
   mcp__bsl-semantic-search__bsl_rename_symbol(
       uri: "file:///path/to/Module.bsl",
       line: N, character: M,
       new_name: "НовоеИмя",
       dry_run: true
   )
   ```
   Или `bsl_replace_method_body` / `bsl_insert_after_method` — см. [bsl-symbol-editing](../../bsl-symbol-editing/SKILL.md).

3. **Проверить план** (dry_run response):
   - `status: "plan"` → показать `files_affected` + `edits`
   - `status: "manual_required"` → переключиться на manual tier (Grep + Edit)

4. **Подтвердить изменения** (`dry_run: false` с `confirm_token` из plan).

5. **Верифицировать через EDT-MCP:**
   ```
   EDT-MCP: get_project_errors(project, severity="ERROR") → 0 ошибок
   ```

6. **Логировать в IMPLEMENTATION-PROGRESS.md:** backend (ast-grep/multilspy/manual), confidence, N файлов изменено.

Полный workflow: [bsl-refactoring-workflow/SKILL.md](../../bsl-refactoring-workflow/SKILL.md).
