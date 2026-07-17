"""Unit: SessionState v2.1 — межпроцессная гонка мутаций (pipeline fix-session-state-skill-race).

Инцидент 2026-07-17: активация Skill('1c-doc-research') потерялась — os.replace на
Windows упал PermissionError под параллельным читателем state-файла, observer глотнул
исключение. Латентный класс: read-modify-write поверх процессного кэша терял чужие
записи (lost update). Тесты детерминированные, без таймингов.
"""

import importlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "hooks"))

pytestmark = pytest.mark.unit


def _fresh(monkeypatch, tmp_path):
    monkeypatch.setenv("SESSION_STATE_PATH", str(tmp_path))
    from shared import session_state as ss

    importlib.reload(ss)
    ss.SessionState._state_cache = None
    return ss


def _read_disk(tmp_path):
    return json.loads((tmp_path / "session-skills.json").read_text(encoding="utf-8"))


def test_replace_retry_survives_permissionerror(monkeypatch, tmp_path):
    """Windows-коллизия: os.replace падает, пока читатель держит файл. Ретрай обязан
    дожать запись — до фикса первый же PermissionError терял активацию."""
    ss = _fresh(monkeypatch, tmp_path)

    real_replace = os.replace
    fails = {"left": 2}

    def flaky_replace(src, dst):
        if str(dst).endswith("session-skills.json") and fails["left"] > 0:
            fails["left"] -= 1
            raise PermissionError(13, "Access is denied (reader holds file)", str(dst))
        return real_replace(src, dst)

    monkeypatch.setattr(ss.os, "replace", flaky_replace)

    ss.SessionState.add_activated_skill("1c-doc-research")

    assert fails["left"] == 0  # ретраи реально прошли через отказы
    assert "1c-doc-research" in _read_disk(tmp_path)["activated_skills"]


def test_replace_retry_exhaustion_reraises(monkeypatch, tmp_path):
    """Исчерпание ретраев — прежний контракт: исключение наружу (вызыватели деградируют)."""
    ss = _fresh(monkeypatch, tmp_path)
    ss.SessionState.add_activated_skill("seed")  # файл создан до подмены

    def always_fail(src, dst):
        raise PermissionError(13, "Access is denied", str(dst))

    monkeypatch.setattr(ss.os, "replace", always_fail)

    with pytest.raises(PermissionError):
        ss.SessionState.add_activated_skill("never-lands")


def test_mutation_preserves_external_write(monkeypatch, tmp_path):
    """Lost-update: чужая запись (другой hook-процесс) между нашим load и mutate
    не должна затираться — мутация обязана перечитать диск, а не верить кэшу."""
    ss = _fresh(monkeypatch, tmp_path)
    ss.SessionState.add_activated_skill("a")  # прогревает процессный кэш

    # «Другой процесс»: пишет напрямую в файл, мимо нашего кэша
    state_file = tmp_path / "session-skills.json"
    data = json.loads(state_file.read_text(encoding="utf-8"))
    data["activated_skills"].append("external")
    data["current_prompt_id"] = "ext-pid"
    state_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    ss.SessionState.add_activated_skill("b")  # мутация по устаревшему кэшу = клоббер

    disk = _read_disk(tmp_path)
    assert set(disk["activated_skills"]) == {"a", "external", "b"}
    assert disk.get("current_prompt_id") == "ext-pid"


def test_stale_lock_broken_and_cleaned(monkeypatch, tmp_path):
    """Упавший процесс оставил лок: старый (> _LOCK_STALE_SEC) взламывается, мутация
    проходит, lock-файл не остаётся."""
    ss = _fresh(monkeypatch, tmp_path)
    lock_path = tmp_path / "session-skills.json.lock"
    lock_path.write_text("", encoding="utf-8")
    old = time.time() - (ss.SessionState._LOCK_STALE_SEC + 5)
    os.utime(lock_path, (old, old))

    ss.SessionState.add_activated_skill("after-stale-lock")

    assert "after-stale-lock" in _read_disk(tmp_path)["activated_skills"]
    assert not lock_path.exists()


def test_fresh_lock_fail_open(monkeypatch, tmp_path):
    """Свежий чужой лок не отдан за бюджет ожидания → fail-open: мутация всё равно
    проходит (потеря взаимного исключения лучше дедлока хука с timeout 3с)."""
    ss = _fresh(monkeypatch, tmp_path)
    monkeypatch.setattr(ss.SessionState, "_LOCK_WAIT_SEC", 0.05)
    lock_path = tmp_path / "session-skills.json.lock"
    lock_path.write_text("", encoding="utf-8")  # свежий: mtime = сейчас

    ss.SessionState.add_activated_skill("fail-open")

    assert "fail-open" in _read_disk(tmp_path)["activated_skills"]
    assert lock_path.exists()  # чужой лок не трогаем (не наш, не stale)


def test_reader_error_does_not_erase_state(monkeypatch, tmp_path):
    """Reader-side erase (review №1): битый/нечитаемый файл на ПУТИ ЧТЕНИЯ не должен
    персистить пустой state — до фикса recovery-ветка _load_state перезаписывала файл
    и стирала чужие activated_skills/task_protocol. Лечит файл только первая мутация."""
    ss = _fresh(monkeypatch, tmp_path)
    ss.SessionState.add_activated_skill("keep-me")

    state_file = tmp_path / "session-skills.json"
    state_file.write_text("{broken json", encoding="utf-8")
    ss.SessionState._state_cache = None

    assert ss.SessionState.get_already_activated() == []  # деградация чтения в памяти
    assert state_file.read_text(encoding="utf-8") == "{broken json"  # файл НЕ перезаписан

    ss.SessionState._state_cache = None
    ss.SessionState.add_activated_skill("heals")  # первая мутация лечит файл
    assert "heals" in _read_disk(tmp_path)["activated_skills"]


def test_no_tmp_or_lock_leftovers(monkeypatch, tmp_path):
    ss = _fresh(monkeypatch, tmp_path)
    for i in range(10):
        ss.SessionState.add_activated_skill(f"s{i}")
    ss.SessionState.record_skill_checked()
    ss.SessionState.set_prompt_id("p")
    ss.SessionState.clear_prompt_id()

    leftovers = [p.name for p in tmp_path.iterdir() if p.name.endswith((".tmp", ".lock"))]
    assert leftovers == []
