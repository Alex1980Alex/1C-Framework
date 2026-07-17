# fix-skill-routing-dedup-tests — компактный пайплайн (trivial, 1 файл)

## 1. План / диагноз

`TestSkillRouterSessionDedup` (tests/test_skill_routing.py, 26-30) мёртв с рождения: ImportError на module-level `reset_session` (появился только 2026-07-17) прятал гниль ожиданий. После починки импорта падали 4/5 — включая test_26 (первый вызов), что исключало связь с session-state.

## 2. Дизайн (эмпирика live-прогонов роутера)

Три сгнивших допущения: (1) вывод роутера теперь **plain text** `[SKILL-ROUTER] …` на stdout, не JSON с systemMessage → `parse_hook_output` всегда None; (2) фикстура ресетила **живой** `data/session-skills.json`, и dedup давился реальной сессией (рекомендованные там скиллы глушили тестовые промпты); (3) test_30 ждал session-timeout-переоткрытие, которого в роутере НЕТ, и искал state по мёртвому пути `.claude/cache/`. Контракт проверен live: 1-й вызов FIRED / повтор EMPTY / переформулировка того же бандла EMPTY (skill-level dedup) / после reset FIRED.

## 3. Реализация

Класс переписан: фикстура `isolated_session` (SESSION_STATE_PATH → tmp, reload, teardown возвращает реальный путь — модуль не остаётся привязан к мёртвому tmp); ассерты по тексту stdout; test_30 заменён на «переформулировка того же бандла молчит» (реальный контракт вместо несуществующего таймаута). Fallback-путь `clean_session` починен `.claude/cache/` → `data/`. Роутер/сессия НЕ трогались — только тесты.

## 4. Тестирование

5/5 PASSED (~2.7с, изолированный state); коллекция файла цела (139); живой session-state прогоном не задет; ruff clean. Сабботаж-гарантия — взаимный брекет (26/28/29 FIRED ↔ 27/30 EMPTY): любой перекос роутера/dedup красит половину класса. Верификация inline (test-only дифф, контракт списан с live-прогонов дважды).
