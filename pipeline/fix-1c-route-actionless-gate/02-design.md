# 02 · Дизайн — гейт `actionless` (Находка 3, 2026-06-18)

## Условие гейта
В `route_1c_task`, внутри confident-ветки (после `if not confident: return`), перед simple→auto:

```
actionless = (
    comp == "simple"
    and not _TASK_VERB.search(prompt)      # нет таск-глагола
    and not eff.get("signals")             # нет work-сигналов (modify/develop/heavy/cross/multi/folder/light)
)
```

`actionless == True` → `flow = "ask_flow"` (понижение `auto → ask_flow`, как просил пользователь).

### Почему только в полосе `simple`
verb-less ∧ zero-signal ⇒ `estimate_effort` даёт `points = base(1) + ttype(0|1) ≤ 2` ⇒ **всегда
`simple`**. То есть гейт по построению срабатывает исключительно там, где сейчас стоит `auto`.
medium/complex недостижимы без work-сигнала ⇒ ветки `gated`/`ask_flow`(medium) не затронуты.

### Почему конъюнкция (verb AND signal), а не дизъюнкция
Максимально консервативно: гейт ловит только «чистый 1С-контекст/вопрос без действия». Если есть
хоть глагол ИЛИ хоть work-сигнал — это уже названная работа, маршрутизируем по сложности как раньше.

## Наблюдаемость
Ключ `out["actionless"]` проставляется во ВСЕХ возвратах `route_1c_task` (по образцу
`non_1c_context`): `False` в none-ветке, в ask_1c-ветке и в неактуальных confident-подветках.

## Потребитель (`onec-task-input.py`)
`flow == "ask_flow"` уже обрабатывается. Добавляем подветку: если `r.get("actionless")` —
сообщение «действие НЕ названо → СПРОСИ, что сделать (не запускай AUTO)» вместо общего
«средней сложности → AUTO или гейт» (иначе текст врал бы про сложность).

## Blast-radius (существующие unit-тесты)
- `test_route_simple_auto`, `test_route_truly_cosmetic_still_auto`: глагол «исправить» ⇒
  `no_verb=False` ⇒ гейт НЕ срабатывает ⇒ остаются `auto`. ✅
- `test_code_path_bsp_call_confident_route`: ассертит `flow != "ask_1c"`; гейт даёт `ask_flow`
  (≠ ask_1c) ⇒ тест проходит (и поведение лучше — «замени» не в словаре, спросить безопаснее). ✅
- `test_code_path_manager_call_no_verb`, `*_event_handler_no_verb`: flow не ассертят ⇒ ок. ✅
- Все confident+medium/complex (`test_route_complex_gated`, `*_develop_printform_not_auto`,
  `*_exchange_setup_not_auto`, `*_medium_ask_flow`): work-сигнал есть ⇒ не simple ⇒ не затронуты. ✅
- ask_1c/none-ветки: гейт за `if not confident: return` ⇒ не достигаются. ✅

## Тест-план (новые)
1. **Headline — ровно пример пользователя**: путь+BSL+предупреждение+«Это 1С задача?» →
   `is_1c=True`, `confident_1c=True`, `actionless=True`, `flow="ask_flow"`. (Промпт собран в тесте
   из точных кусков; tests/ exempt от code-skill-enforcer, но дублируем стиль безопасно.)
2. **Инвариант auto сохранён**: confident+simple С глаголом → `actionless=False`, `flow="auto"`.
3. **Ключ присутствует**: `actionless` в возврате none-ветки и confident-ветки (наблюдаемость).
4. **Code-dump без глагола** (`РегистрыСведений.…СрезПоследних`) → `actionless=True`, `flow="ask_flow"`.

## Риск / робастность
Эвристика — память [[feedback-deterministic-test-robustness]]: гейт детерминирован (regex + пустота
списка), без обращения к окружению. Худший случай (verb-less code-dump) закодирован в headline-тесте
→ откат фикса = красный тест в любом порядке прогона.

## Доп-объём (решение пользователя 2026-06-18): укрепить `_TASK_VERB`
Добавить частые глаголы-действия, которых не было в словаре, **со start-`\b`** против substring-FP
(существующие основы — substring, новые — `\b`-anchored). Набор (start-anchored основы):
`замен` (заменить/замени, не «взамен») · `помен` (поменять) · `переписа`/`перепиш` (переписать/перепиши,
не «переписка») · `передела` (переделать, не «переделка») · `обнов` (обновить) · `переимен`
(переименовать) · `поправ` (поправить). НЕ добавляем сверх-общие (`напиш`/`сдела`) — они тянут
не-1С кодинг. Эффект на гейт: меньше ложных «actionless» (напр. «замени X на Y» теперь = названное
действие → маршрут по сложности, а не вопрос). Регресс: новые позитивы + negatives на substring-FP
(«взамен»/«переписка»/«переделка» → НЕ глагол).

**Одобрение:** делегировано пользователем («сделай»). Approve by=claude-delegated.
