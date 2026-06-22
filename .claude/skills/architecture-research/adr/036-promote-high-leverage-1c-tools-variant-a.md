# ADR-036: Промоут high-leverage 1С-инструментов в обязательные (вариант A)

**Дата:** 2026-06-23
**Статус:** accepted
**Исследование:** [035-mandatory-high-leverage-1c-tools.md](035-mandatory-high-leverage-1c-tools.md) (advisory→hard лестница), [43.7](../../../../docs/framework%20documentation/43_ПАЙПЛАЙН_1С/43.7_АНАЛИЗ_ВСЕЙ_КОНФИГУРАЦИИ.md), [43.9](../../../../docs/framework%20documentation/43_ПАЙПЛАЙН_1С/43.9_ИНСТРУМЕНТЫ_ПО_ТИПАМ.md)

## Контекст
ADR-035 ввёл high-leverage 1С-инструменты как **advisory** (`•`, не блок) в `onec-task-completion-stop`
с измерением follow_rate (окно 06-22→07-06) перед промоутом в hard. Владелец решил **промоутить раньше окна**
(owner-override) выбранный набор. Промоут в hard у task-completion Stop-гейта = блок завершения 1С-задачи,
поэтому делается **условно** (по сигналу правки) и **обратимо** (env-флаги), иначе ложные блоки.

Эмпирика (2 реальные 1С-задачи этой же сессии — валюта-в-примечании-ТТН, права-Валюты): обе правили `.bsl`,
но **не запускали** impact_analysis/BP-trace и завершились корректно → безусловный hard ложно заблокировал бы
обе; в частности мандат **live BP-trace на каждую правку непрактичен** (не всякая правка — runtime/bugfix).

## Решение (вариант A)
Промоут [own]:
1. **`bsl_lint.py --format` → авто (mandatory-by-construction).** PostToolUse:Write|Edit на `.bsl` запускает
   `bsl_lint.py --format` **детачено** (Popen без wait — bsl-ls = JVM, cold-start >5s timeout хука).
   Вендорные деревья (`/external/`, `/tools/`) пропускаются. Никогда не блокирует
   ([`posttooluse-quality-feedback.py`](../../../hooks/posttooluse-quality-feedback.py)).
2. **`bsl_impact_analysis` → conditional-hard.** В `onec-task-completion-stop`: при `ONEC_TOOLGATE_HARD=1`
   И правке 1С-кода в сессии (`config_edit`) impact входит в hard-условие блока.
3. **`1c-debug-hmr` (live BP-trace) → conditional-hard, отдельный opt-in.** Дополнительно к (2) при
   `ONEC_TOOLGATE_DEBUG_HARD=1` (мандат BP-trace на каждую правку непрактичен → не включён в `ONEC_TOOLGATE_HARD`).
4. **`find_callers`/`bsl_call_graph` → advisory** (`•`, перед `[REFACTOR]`/удалением символа) — надёжного
   сигнала «есть рефактор» из транскрипта нет → hard дал бы высокий FP.

**Инварианты безопасности:**
- **Default OFF** (`ONEC_TOOLGATE_HARD` не задан) → поведение гейта **побитово прежнее** (блок строго по
  recall/capture/research). Нулевой риск на rollout + не самоблокирует текущую сессию.
- Per-task escape: `ONEC_TOOLGATE_HARD_DISABLE=1` (trivial-правка). Полный opt-out: `ONEC_TASK_GATE_DISABLE=1`.
- Ядро блока (recall/capture/research) НЕ изменено; impact/debug — аддитивные hard-ключи под условием.
- Активация: `ONEC_TOOLGATE_HARD=1` (impact), `+ONEC_TOOLGATE_DEBUG_HARD=1` (BP-trace).

## Последствия
**Положительные:** impact-анализ перед правкой и BP-trace становятся принуждаемыми (когда флаг включён) —
предотвращение регрессий; bsl_lint авто-применяется → CI-чистый BSL без ручного шага; find_callers сюрфейсится.
**Отрицательные:** при включённом `ONEC_TOOLGATE_HARD` FP-хвост на тривиальных code-правках (закрыт
`ONEC_TOOLGATE_HARD_DISABLE`); auto-bsl_lint спавнит JVM на каждый `.bsl`-edit (детачено, best-effort).

## Альтернативы
- **Безусловный hard всегда** — отклонён (ложно блокирует, эмпирика 2/2 задач сессии).
- **Точный детект «правка экспортного метода» через git-diff hunk + `Экспорт`** — отклонён сейчас: фрагильно в
  8s Stop-хуке (правки уже закоммичены auto-save, сабмодули); `config_edit` — устойчивый прокси + opt-out.
- **Ждать окно валидации (ADR-035, до 07-06)** — отклонён владельцем (owner-override); механизм поставлен
  default-off, активация по решению владельца.

## Связанные файлы
- [`posttooluse-quality-feedback.py`](../../../hooks/posttooluse-quality-feedback.py) — авто bsl_lint
- [`onec-task-completion-stop.py`](../../../hooks/onec-task-completion-stop.py) — conditional-hard + advisory
- [43.9.4](../../../../docs/framework%20documentation/43_ПАЙПЛАЙН_1С/43.9.4_ГРАФ_И_IMPACT.md) / [43.9.7](../../../../docs/framework%20documentation/43_ПАЙПЛАЙН_1С/43.9.7_ОТЛАДКА.md) / [43.9.9](../../../../docs/framework%20documentation/43_ПАЙПЛАЙН_1С/43.9.9_СТАТАНАЛИЗ_И_КАЧЕСТВО.md) · [43.4](../../../../docs/framework%20documentation/43_ПАЙПЛАЙН_1С/43.4_СПРАВОЧНИК_ИНСТРУМЕНТОВ.md)
