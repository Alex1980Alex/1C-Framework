#!/usr/bin/env python3
"""its_fetch — авторизованный fetch its.1c.ru через Playwright storageState (ADR-040 deep-fetch).

БЕЗОПАСНОСТЬ: пароль НИКОГДА не в чате/коде/git.
  Креды — из env (ITS_LOGIN/ITS_PASSWORD) ИЛИ .env.its (gitignored), либо ручной ввод в браузере.
  Сессия -> playwright/.auth/its.json (gitignored).

Поток входа (1С SSO): its.1c.ru/user/auth -> cookie-consent -> "Войти через Портал 1С:ИТС"
  -> login.1c.ru (#username/#password/#loginButton) -> redirect обратно на its.1c.ru.

Использование:
  python scripts/its_fetch.py --login         # видимый браузер; env-креды авто-заполняются, иначе вручную
  python scripts/its_fetch.py --auto-login     # headless авто-вход по env-кредам (для re-login при истечении)
  python scripts/its_fetch.py <URL_ИТС>        # fetch под сессией -> текст в stdout
  python scripts/its_fetch.py <URL> --out f.md
  python scripts/its_fetch.py --check          # жива ли сессия

Env: ITS_LOGIN, ITS_PASSWORD (опц.), ITS_LOGIN_URL (default https://its.1c.ru/user/auth).
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
# login.1c.ru SSO форма (разведано 2026-06-24)
_LOGIN_FIELD_SELECTORS = ("#username", "input[name='username']", "input[type='email']", "input[name='login']")
_PWD_FIELD_SELECTORS = ("#password", "input[name='password']", "input[type='password']")
_SUBMIT_SELECTORS = ("#loginButton", "button[type='submit']", "input[type='submit']", "button:has-text('Войти')")
_PORTAL_SELECTORS = ("#login_portal", "button:has-text('Войти через Портал')")
_COOKIE_ACCEPT = ("button:has-text('Принимаю')", "button:has-text('Принять')")


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


def _click_first(page, selectors) -> bool:
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                el.click()
                return True
        except Exception:
            continue
    return False


def _fill_first(page, selectors, value) -> bool:
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                el.fill(value)
                return True
        except Exception:
            continue
    return False


def _is_logged_in(page, ctx) -> bool:
    url = page.url
    return ("login.1c.ru" not in url) and ("user/auth" not in url) and len(ctx.cookies()) > 3


def _login_flow(page, ctx, login: str | None, pwd: str | None) -> bool:
    """Пройти SSO-поток. С env-кредами — авто-заполнение. Возвращает True если залогинен."""
    login_url = os.environ.get("ITS_LOGIN_URL", _DEFAULT_LOGIN_URL)
    page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
    if _click_first(page, _COOKIE_ACCEPT):
        page.wait_for_timeout(400)
    # перейти на портал входа
    if _click_first(page, _PORTAL_SELECTORS):
        try:
            page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
    # форма login.1c.ru
    if login and pwd:
        if _fill_first(page, _LOGIN_FIELD_SELECTORS, login) and _fill_first(page, _PWD_FIELD_SELECTORS, pwd):
            _click_first(page, _SUBMIT_SELECTORS)
            try:
                page.wait_for_load_state("networkidle", timeout=30000)
            except Exception:
                pass
    return _is_logged_in(page, ctx)


def do_login() -> int:
    """Видимый браузер: env-креды авто-заполняются; человек завершает (капча/2FA) и жмёт Enter."""
    from playwright.sync_api import sync_playwright

    _load_env_its()
    login = os.environ.get("ITS_LOGIN")
    pwd = os.environ.get("ITS_PASSWORD")
    _AUTH.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        logged = _login_flow(page, ctx, login, pwd)
        if not logged:
            sys.stderr.write(
                "\n[its_fetch] Заверши вход в ОТКРЫТОМ браузере (логин/пароль/капча), затем нажми ENTER здесь...\n"
            )
            sys.stderr.flush()
            try:
                input()
            except EOFError:
                try:
                    page.wait_for_url(re.compile(r"its\.1c\.ru/(?!user/auth)"), timeout=180000)
                except Exception:
                    pass
        if not ctx.cookies():
            sys.stderr.write("[its_fetch] ВНИМАНИЕ: cookies не найдены — вход не выполнен? Сессия может быть пустой.\n")
        ctx.storage_state(path=str(_AUTH))
        browser.close()
    sys.stderr.write(f"[its_fetch] Сессия сохранена: {_AUTH}\n")
    return 0


def do_auto_login() -> int:
    """Headless авто-вход по env-кредам (для re-login при истечении). Без участия человека."""
    from playwright.sync_api import sync_playwright

    _load_env_its()
    login = os.environ.get("ITS_LOGIN")
    pwd = os.environ.get("ITS_PASSWORD")
    if not (login and pwd):
        sys.stderr.write("[its_fetch] Нет ITS_LOGIN/ITS_PASSWORD (env или .env.its). Для авто-входа задай их.\n")
        return 4
    _AUTH.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        logged = _login_flow(page, ctx, login, pwd)
        if logged:
            ctx.storage_state(path=str(_AUTH))
        browser.close()
    if logged:
        sys.stderr.write(f"[its_fetch] Сессия сохранена: {_AUTH}\n")
        return 0
    sys.stderr.write("[its_fetch] Авто-вход не удался (капча/2FA/изменилась форма). Запусти --login вручную.\n")
    return 4


def _extract_content(page) -> str:
    """Контент статьи ИТС лежит в iframe (w_metadata_doc_frame, about:srcdoc); fallback body."""
    for f in page.frames[1:]:
        try:
            t = f.inner_text("body")
            if len(t.strip()) > 120:
                return t
        except Exception:
            continue
    return page.inner_text("body")


def do_fetch(url: str, out: str | None) -> int:
    from playwright.sync_api import sync_playwright

    if not _AUTH.exists():
        sys.stderr.write("[its_fetch] Нет сессии. Сначала: python scripts/its_fetch.py --login (или --auto-login)\n")
        return 2
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=str(_AUTH))
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        final_url = page.url
        text = _extract_content(page)
        browser.close()

    if re.search(r"/(user/auth|login)(\?|/|$)", final_url) or "login.1c.ru" in final_url:
        sys.stderr.write("[its_fetch] Сессия истекла (редирект на вход). Повтори --auto-login или --login.\n")
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
    ap.add_argument("--login", action="store_true", help="видимый браузер -> сохранить сессию")
    ap.add_argument("--auto-login", action="store_true", help="headless авто-вход по env-кредам")
    ap.add_argument("--check", action="store_true", help="проверить живость сессии")
    ap.add_argument("--out", default=None, help="сохранить в файл")
    a = ap.parse_args()
    if a.login:
        return do_login()
    if a.auto_login:
        return do_auto_login()
    if a.check:
        return do_check()
    if not a.url:
        ap.error("нужен URL или --login/--auto-login/--check")
    return do_fetch(a.url, a.out)


if __name__ == "__main__":
    sys.exit(main())
