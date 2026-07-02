# 03 — Реализация

- `.claude/hooks/shared/sonar_rescan_state.py`: + `_owning_tree` (main/сабмодуль по префиксу),
  `parse_hunk_new_ranges` (парс @@-хедеров, new-сторона), `changed_line_ranges`
  (diff -w -U0 HEAD; untracked/ошибка → None = fail-closed «все строки мои»).
- `scripts/sonar_rescan_verify.py`: mode=changed-lines; `file_issue_lines` (per-file, точный) →
  ленивый fallback `project_issue_lines` (project-wide paged, severity-split, ES-cap 20 стр.);
  `baseline_degenerate` (информационный); state += `mode`/`baseline_degenerate`/`issues_truncated`
  (контракт evaluate() в Stop-гейте не изменён).
- `scripts/bsl_lint.py`: `_git_head_bytes`, `_selective_format` (построчный difflib-мердж:
  equal→before; равновеликий replace→per-line по edited-набору; структурные блоки→по пересечению),
  `_dominant_crlf`/`_apply_eol`; `_do_format` пишет merged, при «только чужие строки» — не пишет.
- `.claude/hooks/shared/gate_policy.py`: `_LOG_PATH` заякорен на корень проекта.
- `TransportManagementDevelop_SVETLY/Конфигурация/.gitattributes`: `* -text` + text eol=crlf
  для .bsl/.xml/.mdo.
- SonarQube: branch main → `SPECIFIC_ANALYSIS 8877ef63`; вступает со следующего анализа.
- SKILL `implement-1c-task`: Sonar-нота (changed-lines + один скан), Этап 3 (батч + док-комменты),
  Этап 4 шаг 0 (селективный формат), чеклист (+Sonar-дельта).
- Память: `feedback_bsl_batch_edit_format_hook`, `reference_sonar_changed_lines_gate`;
  обновлены `reference_sonar_cyrillic_component_api`, MEMORY.md (компактизация 21.4→<17KB).
- Чистка: 4 мусорных `gate-decisions.jsonl` слиты в `data/gate-decisions.jsonl`, удалены из
  деревьев сабмодулей.
