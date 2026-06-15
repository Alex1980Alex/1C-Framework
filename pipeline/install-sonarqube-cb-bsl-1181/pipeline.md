# Install SonarQube CB 26.x + BSL plugin 1.18.1

Задача: «установи sonar установи плагин» (свежак, выбор пользователя 2026-06-15).
Slug: `install-sonarqube-cb-bsl-1181`

## 1. Планирование (архитектура)

Развилка версий вынесена пользователю (AskUserQuestion) → выбран **свежак**:
SonarQube Community Build 26.x + sonar-bsl-plugin-community **1.18.1** (вместо
репо-дефолта 9.9 LTS + bundled 1.16.1). Обоснование: плагин 1.18.1 требует ядро
≥ 25.4.0.105899 → нужен сервер CB 26.x, не 9.9. Снимает прежний DEFER (ADR-020).

Pre-flight (живьём): docker-демон 29.4.0 up, 206 ГБ свободно, образа sonarqube
локально нет (нужен pull), `tools/sonar-bsl-plugin.jar` = 1.16.1 под Git LFS.

## 2. Дизайн реализации

Декларативный путь (минимум императива, переживает `down/up`):
1. Скачать плагин 1.18.1 с GitHub releases → заменить LFS-jar `tools/sonar-bsl-plugin.jar`
   (diff = указатель LFS, не 100 МБ в истории).
2. `docker/docker-compose.sonarqube.yml`: образ `lts-community` → `community` (CB 26.x);
   bind-mount jar в `/opt/sonarqube/extensions/plugins/` (`:ro`, путь `../tools/…`
   относителен каталогу compose).
3. `docker compose up -d` (pull + старт за один шаг).
4. Sync метаданных: `config_manager.py` `bsl_plugin_version` 1.16.1 → 1.18.1.

Альтернатива (docker cp в named-volume) отклонена — недекларативна.

## 3. Реализация

- Скачан `sonar-communitybsl-plugin-1.18.1.jar` (118 327 474 байт); манифест проверен:
  `Plugin-Version: 1.18.1`, `Plugin-Key: communitybsl`.
- Заменён `tools/sonar-bsl-plugin.jar` (LFS, git: `M`).
- compose: образ → `sonarqube:community` + bind-mount плагина (2 правки).
- `docker compose up -d` → образ CB подтянут, контейнер `sonarqube-1c` Up/healthy.
- `config_manager.py:29` `bsl_plugin_version = "1.18.1"`.

## 4. Тестирование (верификация — живьём)

- `GET /api/system/status` → **UP**, healthcheck **healthy**.
- `GET /api/server/version` → **26.6.0.123539** (CB, июнь 2026).
- `GET /api/plugins/installed` → **communitybsl 1.18.1** (`name: 1C (BSL) Community Plugin`,
  `filename: sonar-communitybsl-plugin-1.18.1.jar`) — сервер реально ЗАГРУЗИЛ плагин.
- `GET /api/languages/list` → язык **bsl** зарегистрирован.
- `GET /api/rules/search?languages=bsl` → **180** BSL-правил активно.
- `config_manager.SonarQubeConfig().bsl_plugin_version == "1.18.1"` (import OK).
- `docker compose config` → OK.

Итог: SonarQube CB 26.6 + BSL-плагин 1.18.1 подняты и проверены end-to-end.
UI: http://localhost:9000 (admin/admin — сменить пароль при первом входе).

Follow-up (не делал без запроса): закоммитить (jar LFS + compose + config_manager),
обновить ADR-020/roadmap (DEFER 1.18.1 → RESOLVED).
