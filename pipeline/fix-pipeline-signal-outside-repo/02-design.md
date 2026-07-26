# Дизайн: бит `in_repo` в canonical tool_call

## Изменения (3 файла)

### 1. `shared/invocation_logger.py` — транспорт бита
Аддитивный параметр `in_repo: bool | None = None`; в запись попадает только когда не `None`:
```python
**({"in_repo": bool(in_repo)} if in_repo is not None else {}),
```
Зеркалит `duration_ms`. Форма записи для всех прочих вызовов **бит-в-бит прежняя** (пинится тестом).

### 2. `tool-invocation-logger.py` — вычисление бита
`_target_in_repo(tool_input) -> bool | None`:
- цель = `file_path` ⟶ иначе `notebook_path`; нет ни одного ⟶ `None` (тул без файловой цели);
- относительный путь резолвится от корня проекта (Claude Code шлёт абсолютные; относительный трактуем как внутренний);
- `Path.resolve()` + `is_relative_to(PROJECT_ROOT)`; исключение ⟶ `None`.

Корень берётся от расположения самого хука (`.claude/hooks/` ⟶ два уровня вверх), не от cwd: cwd у Stop-хука не гарантирован.

### 3. `pipeline-protocol-stop.py` — потребитель
В цикле сбора, в ветке `category == "tool_call"`:
```python
if o.get("in_repo") is False:
    continue        # запись вне репозитория — не правка кода
```
Строго `is False`: `None`/отсутствие ключа/`True` ⟶ прежнее поведение (fail-closed). Стоит **до** накопления в `canonical`, поэтому block-запись не расходуется.

`gate_policies.build_context` делегирует в эту же функцию ⟶ живой хук и оркестратор чинятся одной правкой (инвариант parity-harness сохраняется).

## Тесты (`tests/unit/test_pipeline_signal_outside_repo.py`)

Обе стороны инварианта + саботаж-устойчивость:
1. `in_repo: False` ⟶ `had_write=False` (память/настройки вне репо не требуют пайплайна);
2. `in_repo: True` ⟶ `had_write=True`;
3. ключ отсутствует ⟶ `had_write=True` (fail-closed, старые записи);
4. смесь: одна запись вне репо + одна внутри ⟶ `True` (одна внешняя не «оправдывает» внутреннюю);
5. запись вне репо **не расходует** block-запись: `[outside, inside]` + один block ⟶ `False` (block гасит внутреннюю, внешняя пропущена);
6. `_target_in_repo`: файл проекта / файл вне проекта / `notebook_path` / нет пути ⟶ `True/False/·/None`;
7. форма записи `log_invocation` без `in_repo` идентична прежней (ключа нет).

## Риск и откат
Риск односторонний: гейт может **пропустить** правку, чью запись логгер пометил `in_repo: False`. Это ровно правка вне корня проекта, то есть не product-код. Откат — снять 3 строки в потребителе; бит в логе безвреден.
