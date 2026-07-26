#!/usr/bin/env python3
"""Скан транскрипта сессии на фактические вызовы Skill — единый источник факта активации.

Зачем: запись активации скилла в `session-skills.json` может ПОТЕРЯТЬСЯ (гонка ~4 хуков на
`PreToolUse:Skill`, `os.replace` PermissionError на Windows, мутация, чей результат перезаписан)
— тогда state врёт, а скилл был реально активирован, и энфорсер блокирует правку, требуя того,
что уже сделано. Транскрипт — независимый источник ФАКТА вызова.

Двое потребителей задают скану разные вопросы:
  - `code-skill-enforcer` — «был ли вызван КОНКРЕТНЫЙ скилл в этой сессии»
    (`skill_in_transcript`, 2026-07-17);
  - `task-protocol-enforcer` — «был ли вызван ХОТЬ КАКОЙ-ТО скилл для ТЕКУЩЕЙ задачи»
    (`skill_checked_after_last_prompt`, 2026-07-26).
Определения «запись = настоящий промпт пользователя» и «запись = вызов инструмента Skill»
живут здесь в одном экземпляре, чтобы слои не разъехались.

stdlib-only, наружу не кидает: любая проблема чтения/парсинга → False.
"""

from __future__ import annotations

import json
import os

TAIL_BYTES = 2_000_000  # хвост транскрипта: в типичном случае это сессия целиком


def read_tail(path: str, cap: int = TAIL_BYTES) -> list[str]:
    """Последние `cap` байт транскрипта построчно ([] при любой проблеме чтения)."""
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - cap))
            return f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _blocks(entry: dict) -> list:
    content = (entry.get("message") or {}).get("content")
    return content if isinstance(content, list) else []


def is_skill_call(entry: dict, name: str | None = None) -> bool:
    """Запись содержит `tool_use` инструмента Skill (опционально — с конкретным именем)."""
    for block in _blocks(entry):
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue
        if block.get("name") != "Skill":
            continue
        if name is None:
            return True
        if (block.get("input") or {}).get("skill") == name:
            return True
    return False


def is_user_prompt(entry: dict) -> bool:
    """Запись = НАСТОЯЩИЙ промпт пользователя (не результат инструмента, не инъекция).

    Форма проверена на живом транскрипте (2026-07-26): промпт — `type="user"` с
    content-**строкой**; результаты инструментов приходят той же ролью, но content —
    СПИСОК блоков `tool_result`; системные инъекции (feedback Stop-хуков,
    `local-command-caveat`) помечены `isMeta: true`. `role` не требуем: в живых записях он
    есть, в тест-фикстурах опускается — предикат должен принимать обе формы.
    """
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    message = entry.get("message") or {}
    if message.get("role") not in (None, "user"):
        return False
    return isinstance(message.get("content"), str)


def skill_in_transcript(path: str, name: str) -> bool:
    """Был ли в сессии вызов Skill с данным именем (хвост ≤`TAIL_BYTES`)."""
    if not name:
        return False
    for line in read_tail(path):
        # дешёвый префильтр перед JSON-парсом
        if '"Skill"' not in line or name not in line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(entry, dict) and is_skill_call(entry, name):
            return True
    return False


def skill_checked_after_last_prompt(path: str) -> bool:
    """Был ли вызов Skill ПОСЛЕ последнего настоящего промпта пользователя.

    Якорь обязателен: без него скилл, активированный в прошлой задаче той же сессии,
    навсегда открывал бы гейт протокола — это уже не фолбэк, а обход. Поэтому
    **fail-closed**: якорь не найден в хвосте (транскрипт срезан/нечитаем) → False и
    остаётся обычный блок. Лишняя блокировка восстановима повторной активацией, тихий
    обход протокола — нет.
    """
    last_prompt = -1
    skill_calls: list[int] = []
    for idx, line in enumerate(read_tail(path)):
        # префильтр: интересны только записи-промпты и записи с вызовом Skill
        if '"Skill"' not in line and '"user"' not in line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(entry, dict):
            continue
        if is_user_prompt(entry):
            last_prompt = idx
        elif is_skill_call(entry):
            skill_calls.append(idx)
    if last_prompt < 0:
        return False
    return any(i > last_prompt for i in skill_calls)
