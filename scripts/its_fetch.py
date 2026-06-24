#!/usr/bin/env python3
"""its_fetch — авторизованный fetch its.1c.ru через Playwright storageState (ADR-040 deep-fetch).

БЕЗОПАСНОСТЬ: пароль НИКОГДА не в чате/коде/git.
  Креды берутся из env (ITS_LOGIN/ITS_PASSWORD) ИЛИ из .env.its (gitignored), либо
  вводятся вручную в окне браузера на шаге --login. Сессия -> playwright/.auth/its.json (gitignored).

Использование:
  python scripts/its_fetch.py --login            # разовый вход (видимый браузер) -> сохранить сессию
  python scripts/its_fetch.py <URL_ИТС>          # fetch под сессией -> markdown/текст в stdout
  python scripts/its_fetch.py <URL> --out f.md   # в файл
  python scripts/its_fetch.py --check            # проверить, жива ли сессия

Env: ITS_LOGIN, ITS_PASSWORD (опц., авто-заполнение), ITS_LOGIN_URL (default https://its.1c.ru/user/auth).
"""

import argparse
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_AUTH = _ROOT / "playwright" / ".auth" / "its.json"
_DEFAULT_LOGIN_URL = "https://its.1c.ru/user/auth"
_CHECK_URL = "https://its.1c.ru/db/v8std"
_LOGIN_FIELD_SELECTORS = ("input[name='login']", "input[name='username']", "input[type='email']", "#username", "#login")
_PWD_FIELD_SELECTORS = ("input[name='password']", "input[type='password']", "#password")
_SUBMIT_SELECTORS = ("button[type='submit']", "input[type='submit']", "button:has-text('Войти')")


def _load_env_its() -> None:
    """Подхватить .env.its (gitignored), не перетирая уже заданные env-переменные."""
    p = _ROOT / ".env.its"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _try_fill(page, selectors, value) -> bool:
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                el.fill(value)
                return True
        except Exception:
            continue
    return False


def do_login() -> int:
    from playwright.sync_api import sync_playwright

    _load_env_its()
    login = os.environ.get("ITS_LOGIN")
    pwd = os.environ.get("ITS_PASSWORD")
    login_url = os.environ.get("ITS_LOGIN_URL", _DEFAULT_LOGIN_URL)
    _AUTH.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(login_url, wait_until="domcontentloaded")
        if login and pwd:
            _try_fill(page, _LOGIN_FIELD_SELECTORS, login)
            _try_fill(page, _PWD_FIELD_SELECTORS, pwd)
            for sel in _SUBMIT_SELECTORS:
                try:
                    btn = page.query_selector(sel)
                    if btn:
                        btn.click()
                        break
                except Exception:
                    continue
        sys.stderr.write(
            "\n[its_fetch] Заверши вход в ОТКРЫТОМ окне браузера (логин/пароль/капча если есть).\n"
            "Когда увидишь, что залогинен — нажми ENTER здесь...\n"
        )
        sys.stderr.flush()
        try:
            input()
        except EOFError:
            # нет TTY — ждём ухода с auth-страницы
            try:
                page.wait_for_url(re.compile(r"its\.1c\.ru/(?!user/auth|login)"), timeout=180000)
            except Exception:
                pass
        if not ctx.cookies():
            sys.stderr.write("[its_fetch] ВНИМАНИЕ: cookies не найдены — вход не выполнен? Сессия может быть пустой.\n")
        ctx.storage_state(path=str(_AUTH))
        browser.close()
    sys.stderr.write(f"[its_fetch] Сессия сохранена: {_AUTH}\n")
    return 0


def do_fetch(url: str, out: str | None) -> int:
    from playwright.sync_api import sync_playwright

    if not _AUTH.exists():
        sys.stderr.write("[its_fetch] Нет сессии. Сначала: python scripts/its_fetch.py --login\n")
        return 2
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=str(_AUTH))
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        final_url = page.url
        text = page.inner_text("body")
        browser.close()

    if re.search(r"/(user/auth|login)(\?|/|$)", final_url):
        sys.stderr.write("[its_fetch] Сессия истекла (редирект на вход). Повтори --login.\n")
        return 3

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    if out:
        Path(out).write_text(text, encoding="utf-8")
        sys.stderr.write(f"[its_fetch] -> {out} ({len(text)} симв)\n")
    else:
        print(text)
    return 0


def do_check() -> int:
    return do_fetch(_CHECK_URL, out=None)


def main() -> int:
    ap = argparse.ArgumentParser(description="Авторизованный fetch its.1c.ru (Playwright storageState)")
    ap.add_argument("url", nargs="?", help="URL страницы ИТС")
    ap.add_argument("--login", action="store_true", help="разовый вход -> сохранить сессию")
    ap.add_argument("--check", action="store_true", help="проверить живость сессии")
    ap.add_argument("--out", default=None, help="сохранить в файл")
    a = ap.parse_args()
    if a.login:
        return do_login()
    if a.check:
        return do_check()
    if not a.url:
        ap.error("нужен URL или --login/--check")
    return do_fetch(a.url, a.out)


if __name__ == "__main__":
    sys.exit(main())
