---
name: its-research
description: "Дословный deep-fetch стандартов/методик с ИТС (its.1c.ru, под подпиской) — v8std-стандарты, расширения, руководства для 1С-архитектуры/разработки. Дополняет 1c-doc-research (ИТС = приоритет 2). Триггеры: 'ИТС стандарт', 'its.1c.ru', 'v8std', 'дословный текст стандарта разработки 1С'. НЕ для документации платформы 8.3.27 (приоритет 1) — используй 1c-doc-research."
---

# its-research — дословные стандарты/методики с ИТС (its.1c.ru, под подпиской)

Получение **дословного** контента из-за пейвола ИТS (v8std-стандарты, расширения, руководства) для
1С-архитектуры/разработки. Дополняет `1c-doc-research` (Фаза 2, ИТС = приоритет 2 вендор) рабочим
deep-fetch. Эталон 8.3.27 (`/search/`) остаётся приоритетом 1.

## Предусловие: сессия ИТС
- Креды в **`.env.its`** (gitignored): `ITS_LOGIN=...` / `ITS_PASSWORD=...`. **Никогда не в чат.**
- Вход: `python scripts/its_fetch.py --login` (видимый браузер) ИЛИ `--auto-login` (headless по env-кредам).
- Сессия → `playwright/.auth/its.json` (gitignored), живёт недели; истекла → `--auto-login` (могу сам).

## Процедура (повторяемая)
1. **FIND страницы** — `WebSearch: "site:its.1c.ru <тема>"` (или `site:its.1c.ru/db/v8std <тема>`) → даёт URL `/db/<db>/content/N/hdoc`. JS-дерево ИТС напрямую НЕ парсится — поиск через `site:`.
2. **FETCH** — `python scripts/its_fetch.py "<URL>"` → **чистый markdown**. Контент лежит в iframe `w_metadata_doc_frame`; его HTML гонится через **trafilatura → markdown** (сохраняет нумерованные правила, таблицы, код «Правильно/Неправильно»), graceful fallback на текст фрейма.
3. **ATTRIBUTE** — каждый факт: `[its.1c.ru, content/N, #stdNNN]` (ID `#std` есть в тексте стандарта).
4. **VERIFY** (как `1c-doc-research` Фаза 3) — вендор = приоритет 2; сверить с эталоном 8.3.27; неофиц. термины → к терминологии документации; пометить версию (8.2/8.3).
5. **CACHE** (Фаза 5) — URL + положения → `1c-doc-research/cache/`.

## Ключевые БД ИТС (db-коды)
| db | Что |
|---|---|
| `v8std` | **Система стандартов и методик разработки** (для архитектора — главное) |
| `pubextensions` | «Расширения конфигураций. Как адаптировать при внедрении» |
| `metod8dev` | Методическая поддержка (платформа, механизмы) |
| `pubdevguide83` | Практическое пособие разработчика 8.3 |
| `v8313doc`/`v8std` | Руководство разработчика / стандарты |

## Инструменты
- `scripts/its_fetch.py` (`--login`/`--auto-login`/`--check`/`<URL>`/`--out`) — Playwright storageState + trafilatura.
- `WebSearch` (`site:its.1c.ru`) — поиск URL. **GitHub-поиск — через `ecosystem_scan` (гл.44), не WebSearch** [[feedback-github-search-via-ecosystem-scan]].
- `trafilatura` (markdown-извлечение).

## Безопасность (хард)
Креды только в `.env.its`/env (gitignored) или в окне браузера — **не в чат/код/git** ([[project-secret-leak-remediation-260614]]). Сессия gitignored. Low-volume self-use под своей подпиской (не массовый скрейп).

## Связано
- Дополняет [`1c-doc-research`](../1c-doc-research/SKILL.md) (Фаза 2 ИТС). Питает [`1c-solution-architecture`](../1c-solution-architecture/SKILL.md) (арх-стандарты). Кеши: [[1c-architect-its-standards]], [[its-authenticated-access]].