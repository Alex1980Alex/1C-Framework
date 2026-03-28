# Дорожная карта: CI/CD для 1С с Docker — от коммита до продуктива

## Полная техническая документация для разработчика 1С на Windows

---

## Часть 1. Архитектура конвейера

### 1.1. Общая схема: что происходит от нажатия git push до обновления рабочей базы

Весь конвейер непрерывной интеграции и доставки (CI/CD) для 1С можно описать как цепочку автоматических действий, которые запускаются каждый раз, когда разработчик фиксирует изменения в системе контроля версий.

**Полный жизненный цикл изменения:**

```
Разработчик (EDT/Конфигуратор)
    │
    ▼
Git-репозиторий (GitLab/GitHub)
    │ ← триггер: push / merge request
    ▼
CI-сервер (GitLab CI / Jenkins)
    │ ← читает .gitlab-ci.yml / Jenkinsfile
    ▼
Docker Runner (поднимает контейнер из образа)
    │
    ╔══════════════════════════════════════════════════╗
    ║  Docker-контейнер (изолированная среда)          ║
    ║                                                  ║
    ║  ┌─────────────────────────────────────────┐     ║
    ║  │ Платформа 1С 8.3.x                      │     ║
    ║  │ OneScript + opm                          │     ║
    ║  │ vanessa-runner                           │     ║
    ║  │ BSL Language Server                      │     ║
    ║  │ PostgreSQL (для временных ИБ)            │     ║
    ║  │ Xvfb (виртуальный дисплей для тестов)    │     ║
    ║  └─────────────────────────────────────────┘     ║
    ║                                                  ║
    ║  Этап 1: Конвертация исходников (EDT → XML)      ║
    ║  Этап 2: Сборка информационной базы (XML → CF)   ║
    ║  Этап 3: Синтаксическая проверка платформой      ║
    ║  Этап 4: Статический анализ (BSL LS → SonarQube) ║
    ║  Этап 5: Модульные тесты (xUnit / YAxUnit)       ║
    ║  Этап 6: Дымовые тесты (Vanessa ADD)             ║
    ║  Этап 7: Сценарные BDD-тесты (Vanessa Automation)║
    ║  Этап 8: Замер покрытия кода (Coverage41C)        ║
    ╚══════════════════════════════════════════════════╝
    │
    ▼ Артефакты: CF-файл, отчёты SonarQube, Allure, покрытие
    │
    ▼
Деплой на тестовую базу (автоматический)
    │ ← проверка: тесты на тестовой базе прошли?
    ▼
Деплой на продуктивную базу (по кнопке или автоматический)
```

### 1.2. Что находится внутри Docker-образа

Docker-образ — это «снимок» файловой системы Linux со всем установленным ПО. Он описывается текстовым файлом Dockerfile. Для конвейера 1С типичный образ содержит следующие компоненты:

**Базовый слой** — Ubuntu 22.04 или Debian 11 (легковесная Linux-система).

**Платформа 1С** — сервер и/или клиент 1С:Предприятия нужной версии, установленные из DEB-пакетов. Файлы скачиваются с releases.1c.ru по учётным данным партнёра/клиента. Ключевые пакеты: `1c-enterprise-8.3.x.y-common`, `1c-enterprise-8.3.x.y-server`, `1c-enterprise-8.3.x.y-client`. Клиент нужен для запуска тестов с GUI.

**PostgreSQL** — СУБД для создания временных информационных баз. Используется сборка от PostgresPro с патчами для 1С (поддержка кластерного индекса, коллаций и т.д.). Может быть в том же контейнере или в отдельном.

**OneScript** — скриптовый движок с синтаксисом 1С. Устанавливается из DEB-пакета или через скрипт установки. После установки через пакетный менеджер `opm` доводятся библиотеки: `vanessa-runner`, `gitsync`, `deployka` и другие.

**BSL Language Server** — Java-приложение (JAR-файл) для статического анализа кода 1С. Требует JRE 11+.

**EDT (опционально)** — среда разработки 1С, нужна если проект хранится в формате EDT (а не конфигуратора). Используется headless-режим для конвертации исходников.

**Xvfb** — виртуальный фреймбуфер (эмулятор дисплея). Обязателен для сценарных тестов, потому что Vanessa Automation работает с GUI 1С — ей нужен «экран», даже если физического монитора нет.

### 1.3. Системные требования для Windows-машины разработчика

Для полноценной работы конвейера на локальном ПК с Windows 10/11:

**Оперативная память.** Минимум 16 ГБ, рекомендуется 32 ГБ. Распределение при полной нагрузке: WSL2 (подсистема Linux для Docker) — 4–6 ГБ; контейнер с 1С и PostgreSQL — 2–4 ГБ на каждый; SonarQube — 2–3 ГБ; сама Windows и IDE — 4–6 ГБ. При 32 ГБ можно комфортно запускать 2–3 контейнера параллельно.

**Диск.** SSD обязателен — образы 1С весят 3–8 ГБ каждый, а сборка конфигурации активно работает с диском. На HDD процесс сборки может занять в 5–10 раз больше времени. Свободного места нужно минимум 50 ГБ (образы + временные базы + кэш Docker).

**Процессор.** 4+ ядра. Виртуализация (VT-x/AMD-V) должна быть включена в BIOS — без неё WSL2 не запустится.

**Версия Windows.** Windows 10 версии 2004+ или Windows 11. Необходима поддержка WSL2.

---

## Часть 2. Пошаговая установка и настройка

### 2.1. Этап 1: Установка Docker Desktop и WSL2

Docker на Windows работает через WSL2 (Windows Subsystem for Linux) — легковесную виртуальную машину с ядром Linux, встроенную в Windows. Docker Desktop при установке сам предложит включить WSL2.

**Шаг 1.** Включите компоненты Windows. Откройте PowerShell от администратора:

```powershell
wsl --install
```

Эта команда включит WSL2 и установит Ubuntu. После перезагрузки создайте пользователя Linux (логин и пароль).

**Шаг 2.** Скачайте и установите Docker Desktop с docker.com. При установке убедитесь, что опция «Use WSL 2 based engine» включена. После установки Docker Desktop появится в системном трее.

**Шаг 3.** Проверьте установку. Откройте PowerShell (обычный, не от администратора):

```powershell
docker --version
docker run hello-world
```

Если вы увидели сообщение «Hello from Docker!» — всё работает.

**Шаг 4.** Настройте ресурсы. В Docker Desktop: Settings → Resources → WSL Integration — убедитесь, что ваш дистрибутив Ubuntu включён. В разделе Resources → Advanced можно ограничить потребление памяти (рекомендуется выделить 8–12 ГБ из ваших 32 ГБ).

**Шаг 5.** Установите Portainer для визуального управления контейнерами:

```powershell
docker volume create portainer_data
docker run -d -p 9443:9443 --name portainer --restart=always ^
  -v /var/run/docker.sock:/var/run/docker.sock ^
  -v portainer_data:/data portainer/portainer-ce:latest
```

Откройте https://localhost:9443 — появится веб-интерфейс для управления контейнерами.

### 2.2. Этап 2: Установка Git и базовые навыки

**Шаг 1.** Скачайте и установите Git for Windows с git-scm.com. При установке оставьте настройки по умолчанию.

**Шаг 2.** Настройте Git (PowerShell):

```powershell
git config --global user.name "Ваше Имя"
git config --global user.email "your@email.com"
```

**Шаг 3.** Создайте тестовый репозиторий на GitHub (github.com → New repository). Склонируйте его:

```powershell
git clone https://github.com/ваш-логин/test-repo.git
cd test-repo
```

**Шаг 4.** Освойте базовый цикл работы:

```powershell
# Создайте файл
echo "Hello" > test.txt

# Добавьте в отслеживание
git add test.txt

# Зафиксируйте изменение
git commit -m "Первый коммит"

# Отправьте на сервер
git push
```

**Шаг 5.** Базовые команды Linux через WSL2. Откройте терминал Ubuntu (из меню Пуск):

```bash
# Навигация
cd /home           # перейти в папку
ls -la             # список файлов с подробностями
pwd                # текущая директория

# Работа с файлами
cat file.txt       # показать содержимое файла
mkdir mydir        # создать папку
cp file1 file2     # копировать файл
rm file.txt        # удалить файл

# Установка пакетов
sudo apt update              # обновить список пакетов
sudo apt install -y curl     # установить программу
```

### 2.3. Этап 3: Сборка Docker-образа с платформой 1С

Это ключевой этап — вы создадите образ, содержащий платформу 1С, пригодный для использования в CI/CD.

**Шаг 1.** Скачайте дистрибутив платформы 1С для Linux (DEB-пакеты) с https://releases.1c.ru. Вам нужны файлы: `1c-enterprise-8.3.x.y-common_amd64.deb`, `1c-enterprise-8.3.x.y-server_amd64.deb`, `1c-enterprise-8.3.x.y-client_amd64.deb`.

**Шаг 2.** Склонируйте репозиторий с Dockerfile:

```powershell
# Вариант А: репозиторий от Первого Бита (более полная коллекция образов)
git clone https://github.com/firstBitMarksistskaya/onec-docker.git

# Вариант Б: экосистема thedemoncat (модульные образы, публикуются в ghcr.io)
git clone https://github.com/thedemoncat/onec-base.git
```

**Шаг 3.** Поместите скачанные DEB-пакеты в папку `distr/` (для onec-docker) и запустите сборку:

```powershell
# Пример для onec-docker (Первый Бит)
cd onec-docker
docker build -t onec-server:8.3.25 -f server/Dockerfile .
docker build -t onec-client:8.3.25 -f client/Dockerfile .
```

Сборка займёт 5–15 минут. На выходе вы получите Docker-образы с установленной платформой.

**Шаг 4.** Проверьте, что образ работает:

```powershell
docker run --rm onec-client:8.3.25 /opt/1cv8/x86_64/8.3.25.1257/1cv8 --version
```

Если отобразилась версия платформы — образ собран корректно.

### 2.4. Этап 4: Статический анализ кода (SonarQube + BSL Language Server)

Статический анализ — это проверка кода без его запуска. BSL Language Server анализирует код 1С по 150+ правилам и находит типичные ошибки: запросы в цикле, избыточную вложенность, высокую цикломатическую сложность, неиспользуемые переменные и многое другое.

**Шаг 1.** Запустите SonarQube с предустановленными плагинами для 1С. Создайте файл `docker-compose.yml`:

```yaml
version: '3.8'

services:
  sonarqube:
    image: sonarqube:lts-community
    container_name: sonarqube
    ports:
      - "9000:9000"
    environment:
      - SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true
    volumes:
      - sonarqube_data:/opt/sonarqube/data
      - sonarqube_logs:/opt/sonarqube/logs
      - sonarqube_extensions:/opt/sonarqube/extensions

volumes:
  sonarqube_data:
  sonarqube_logs:
  sonarqube_extensions:
```

Запустите:

```powershell
docker compose up -d
```

Откройте http://localhost:9000 (логин: admin, пароль: admin).

**Шаг 2.** Установите плагин для 1С. Скачайте JAR-файл sonar-bsl-plugin-community из релизов https://github.com/1c-syntax/sonar-bsl-plugin-community/releases и поместите в папку extensions/plugins контейнера:

```powershell
docker cp sonar-bsl-plugin-community-0.x.x.jar sonarqube:/opt/sonarqube/extensions/plugins/
docker restart sonarqube
```

**Шаг 3.** Скачайте BSL Language Server (JAR-файл) из https://github.com/1c-syntax/bsl-language-server/releases.

**Шаг 4.** Запустите анализ вашего кода 1С (исходники в формате XML или BSL-файлы):

```powershell
java -jar bsl-language-server.jar --analyze ^
  --srcDir "C:\path\to\your\1c\sources" ^
  --reporter json
```

На выходе — JSON-файл с результатами, который загружается в SonarQube.

**Что вы увидите в SonarQube.** Дашборд с метриками: количество багов, code smells, дублирование кода, покрытие тестами, цикломатическая сложность. Каждая проблема с описанием, указанием файла и строки, рекомендацией по исправлению.

### 2.5. Этап 5: Автоматическая сборка релиза (CI/CD)

На этом этапе вы настраиваете полноценный конвейер: при каждом push в Git автоматически собирается CF-файл, прогоняется анализ и формируются артефакты.

**Вариант А: GitLab CI (рекомендуется для начала).**

Зарегистрируйтесь на gitlab.com (бесплатный аккаунт включает 400 минут CI/CD в месяц) или разверните GitLab CE локально в Docker:

```powershell
docker run -d --name gitlab ^
  -p 8443:443 -p 8080:80 -p 2222:22 ^
  -v gitlab_config:/etc/gitlab ^
  -v gitlab_logs:/var/log/gitlab ^
  -v gitlab_data:/var/opt/gitlab ^
  gitlab/gitlab-ce:latest
```

**Шаг 1.** Установите и зарегистрируйте GitLab Runner:

```powershell
docker run -d --name gitlab-runner --restart always ^
  -v /var/run/docker.sock:/var/run/docker.sock ^
  -v gitlab-runner-config:/etc/gitlab-runner ^
  gitlab/gitlab-runner:latest
```

Зарегистрируйте раннер с Docker executor:

```powershell
docker exec -it gitlab-runner gitlab-runner register ^
  --url "https://gitlab.com" ^
  --token "ваш-токен-из-настроек-проекта" ^
  --executor "docker" ^
  --docker-image "onec-client:8.3.25"
```

**Шаг 2.** Создайте файл `.gitlab-ci.yml` в корне вашего репозитория:

```yaml
stages:
  - build
  - analyze
  - test
  - deploy

variables:
  ONEC_VERSION: "8.3.25.1257"

# ────────────────────────────────────────────
# Этап 1: Сборка CF из исходников
# ────────────────────────────────────────────
build_cf:
  stage: build
  image: onec-client:${ONEC_VERSION}
  script:
    # Конвертация из формата EDT в формат конфигуратора (если проект на EDT)
    - ring edt workspace export
        --workspace-location "$CI_PROJECT_DIR"
        --project "$CI_PROJECT_DIR"
        --configuration-files "$CI_PROJECT_DIR/build/cf"

    # Создание временной ИБ
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 CREATEINFOBASE
        File="$CI_PROJECT_DIR/build/ib"

    # Загрузка конфигурации из файлов
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /F "$CI_PROJECT_DIR/build/ib"
        /LoadConfigFromFiles "$CI_PROJECT_DIR/build/cf"
        /UpdateDBCfg

    # Выгрузка CF-файла
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /F "$CI_PROJECT_DIR/build/ib"
        /DumpCfg "$CI_PROJECT_DIR/build/1cv8.cf"
  artifacts:
    paths:
      - build/1cv8.cf
    expire_in: 7 days

# ────────────────────────────────────────────
# Этап 2: Синтаксическая проверка
# ────────────────────────────────────────────
syntax_check:
  stage: analyze
  image: onec-client:${ONEC_VERSION}
  needs: ["build_cf"]
  script:
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /F "$CI_PROJECT_DIR/build/ib"
        /CheckConfig
        -Server -ThinClient -WebClient
        -ExternalConnection -ExternalConnectionServer
        -ThickClientOrdinaryApplication
  allow_failure: true

# ────────────────────────────────────────────
# Этап 3: Статический анализ BSL Language Server
# ────────────────────────────────────────────
static_analysis:
  stage: analyze
  image: openjdk:17-slim
  script:
    - java -jar /tools/bsl-language-server.jar
        --analyze
        --srcDir "$CI_PROJECT_DIR/src"
        --reporter sonarGenericIssue
        --outputDir "$CI_PROJECT_DIR/build/bsl-reports"
  artifacts:
    paths:
      - build/bsl-reports/
    expire_in: 7 days

# ────────────────────────────────────────────
# Этап 4: Отправка результатов в SonarQube
# ────────────────────────────────────────────
sonarqube:
  stage: analyze
  image: sonarsource/sonar-scanner-cli:latest
  needs: ["static_analysis"]
  script:
    - sonar-scanner
        -Dsonar.projectKey=my-1c-project
        -Dsonar.sources=src
        -Dsonar.host.url=$SONAR_HOST_URL
        -Dsonar.token=$SONAR_TOKEN
        -Dsonar.externalIssuesReportPaths=build/bsl-reports/genericIssue.json

# ────────────────────────────────────────────
# Этап 5: Деплой на тестовую базу
# ────────────────────────────────────────────
deploy_test:
  stage: deploy
  needs: ["build_cf", "syntax_check"]
  script:
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /S "test-server\test_db"
        /N "Администратор" /P ""
        /LoadCfg "$CI_PROJECT_DIR/build/1cv8.cf"
        /UpdateDBCfg -Dynamic+
  when: manual  # запускается по кнопке

# ────────────────────────────────────────────
# Этап 6: Деплой на продуктивную базу
# ────────────────────────────────────────────
deploy_prod:
  stage: deploy
  needs: ["deploy_test"]
  script:
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /S "prod-server\prod_db"
        /N "Администратор" /P "$PROD_PASSWORD"
        /LoadCfg "$CI_PROJECT_DIR/build/1cv8.cf"
        /UpdateDBCfg
  when: manual
  only:
    - main
```

**Как это работает на практике.** Вы пишете код в EDT, коммитите в Git, нажимаете push. GitLab видит коммит, читает `.gitlab-ci.yml`, обращается к раннеру. Раннер поднимает Docker-контейнер из вашего образа с 1С. Внутри контейнера последовательно выполняются все этапы. Если этап завершился ошибкой — пайплайн останавливается, вы получаете уведомление (email, Telegram-бот, Slack). Готовый CF-файл сохраняется как артефакт сборки — его можно скачать из интерфейса GitLab.

---

## Часть 3. Тестирование — полная автоматизация

Это самая объёмная и технически сложная часть конвейера. Тестирование в 1С включает несколько уровней, каждый из которых решает свою задачу.

### 3.1. Уровни тестирования: что проверяет каждый

**Модульные тесты (Unit tests)** проверяют отдельные функции и процедуры в изоляции. Например: правильно ли рассчитывается скидка? Корректно ли работает алгоритм распределения оплаты по заказам? Инструменты: YAxUnit (современный, рекомендуемый), xUnitFor1C (устаревший, но ещё используется).

**Дымовые тесты (Smoke tests)** проверяют, что приложение в принципе работоспособно после обновления: все формы открываются, все документы проводятся, основные отчёты формируются. Это автоматическая проверка — система сама перебирает все метаданные и пытается открыть каждую форму, создать и провести каждый документ. Инструмент: Vanessa ADD (модуль smoke-тестов).

**Сценарные BDD-тесты (Behavior-Driven Development)** проверяют бизнес-логику по сценариям. Пишутся на языке Gherkin (русскоязычный, понятный бизнес-аналитику). Например: «Когда пользователь создаёт заказ покупателя с двумя товарами и нажимает Провести, тогда должны сформироваться движения по регистру Остатки товаров.» Инструмент: Vanessa Automation.

**Замер покрытия кода (Code Coverage)** показывает, какой процент кода 1С выполнялся во время тестов. Позволяет увидеть «мёртвый код» и непротестированные ветки. Инструмент: Coverage41C.

### 3.2. Модульное тестирование с YAxUnit

YAxUnit — это современный фреймворк модульного тестирования для 1С, созданный как расширение конфигурации. Он работает внутри платформы 1С и не требует внешних инструментов для написания тестов.

**Установка.** YAxUnit поставляется как расширение конфигурации (CFE-файл). Его нужно установить в вашу конфигурацию через конфигуратор или программно (vanessa-runner умеет это автоматизировать). Репозиторий: https://github.com/bia-technologies/yaxunit.

**Принцип работы.** Вы создаёте модули с тестами прямо в расширении конфигурации. Каждый тест — это процедура, которая вызывает тестируемый код и проверяет результат через утверждения (assertions).

**Пример теста:**

```bsl
// Модуль: ТестыРасчётаСкидок

Процедура ТестСкидкаДляОптовогоКлиента() Экспорт

    // Подготовка
    Клиент = ЮТест.Данные().СоздатьЭлемент(Справочники.Контрагенты);
    Клиент.ВидЦенообразования = Перечисления.ВидыЦенообразования.Оптовый;
    Клиент.Записать();

    Товар = ЮТест.Данные().СоздатьЭлемент(Справочники.Номенклатура);
    Товар.Цена = 1000;
    Товар.Записать();

    // Действие
    РезультатСкидки = МодульРасчётаСкидок.РассчитатьСкидку(Клиент, Товар, 100);

    // Проверка
    ЮТест.ОжидаетЧто(РезультатСкидки)
        .Равно(10)  // ожидаем 10% скидку для оптовиков
        .Описание("Скидка для оптового клиента должна быть 10%");

КонецПроцедуры

Процедура ТестНетСкидкиДляРозничногоКлиента() Экспорт

    Клиент = ЮТест.Данные().СоздатьЭлемент(Справочники.Контрагенты);
    Клиент.ВидЦенообразования = Перечисления.ВидыЦенообразования.Розничный;
    Клиент.Записать();

    Товар = ЮТест.Данные().СоздатьЭлемент(Справочники.Номенклатура);
    Товар.Цена = 1000;
    Товар.Записать();

    РезультатСкидки = МодульРасчётаСкидок.РассчитатьСкидку(Клиент, Товар, 1);

    ЮТест.ОжидаетЧто(РезультатСкидки)
        .Равно(0)
        .Описание("Розничный клиент не должен получать скидку");

КонецПроцедуры
```

**Запуск в Docker.** YAxUnit запускается через vanessa-runner или напрямую через 1С в пакетном режиме:

```bash
# Внутри Docker-контейнера
/opt/1cv8/x86_64/$ONEC_VERSION/1cv8 ENTERPRISE \
    /F "/workspace/build/ib" \
    /Execute "/workspace/tools/yaxunit-launcher.epf" \
    /C "RunTests;ExitAfter" \
    /Out "/workspace/build/test-results/yaxunit.log"
```

**Этап в .gitlab-ci.yml:**

```yaml
unit_tests:
  stage: test
  image: onec-client:${ONEC_VERSION}
  needs: ["build_cf"]
  services:
    - postgres:15-1c  # PostgreSQL с патчами для 1С в отдельном контейнере
  variables:
    POSTGRES_DB: test_db
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
  script:
    # Создание ИБ на PostgreSQL
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 CREATEINFOBASE
        Srvr="postgres";Ref="test_db";DBMS="PostgreSQL";
        DBSrvr="postgres";DB="test_db";
        DBUID="postgres";DBPwd="postgres"

    # Загрузка конфигурации
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /S "postgres\test_db"
        /LoadCfg "$CI_PROJECT_DIR/build/1cv8.cf"
        /UpdateDBCfg

    # Установка расширения YAxUnit
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /S "postgres\test_db"
        /LoadCfg "$CI_PROJECT_DIR/tools/yaxunit.cfe"
        /UpdateDBCfg

    # Запуск тестов
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 ENTERPRISE
        /S "postgres\test_db"
        /Execute "$CI_PROJECT_DIR/tools/yaxunit-launcher.epf"
        /C "RunTests;JUnitReport=$CI_PROJECT_DIR/build/reports/junit.xml"
        /DisableStartupMessages
        /DisableStartupDialogs
  artifacts:
    reports:
      junit: build/reports/junit.xml
    expire_in: 7 days
```

### 3.3. Дымовые тесты с Vanessa ADD

Дымовые тесты — это «автопилот», который автоматически обходит все метаданные вашей конфигурации и проверяет базовую работоспособность без написания тестовых сценариев вручную.

**Что проверяют дымовые тесты:**

Открытие всех форм — система перебирает каждый справочник, документ, отчёт, обработку и пытается открыть их основную форму. Если форма падает с ошибкой — тест фиксирует проблему.

Создание и проведение документов — для каждого вида документов система создаёт новый документ с минимальным заполнением обязательных реквизитов и пытается его провести.

Формирование отчётов — открытие и формирование каждого отчёта с настройками по умолчанию.

Проверка макетов печатных форм — открытие каждого макета.

**Установка Vanessa ADD.** Vanessa ADD (Automation Driven Development) устанавливается через opm:

```bash
opm install add
```

Репозиторий: https://github.com/vanessa-opensource/add

**Настройка.** Vanessa ADD использует файл конфигурации `env.json`:

```json
{
    "Открытие формы объектов тестовыми данными": true,
    "Открытие форм ролями": false,
    "Формирование отчетов": true,
    "ТипБазы": "File",
    "КаталогИБ": "/workspace/build/ib",
    "КаталогОтчетовJUnit": "/workspace/build/reports/smoke",
    "ЗагружатьФикстуры": true,
    "КаталогФикстур": "/workspace/tests/fixtures"
}
```

**Запуск в Docker:**

```bash
# Запуск виртуального дисплея (обязателен для GUI-тестов)
export DISPLAY=:1
Xvfb :1 -screen 0 1920x1080x24 &

# Запуск дымовых тестов через vanessa-runner
vanessa-runner run \
    --ibconnection "File=/workspace/build/ib" \
    --command "RunSmokeTests" \
    --execute "/workspace/tools/vanessa-add.epf" \
    --settings "/workspace/tests/smoke-settings.json" \
    --reportjunit "/workspace/build/reports/smoke-junit.xml"
```

**Этап в .gitlab-ci.yml:**

```yaml
smoke_tests:
  stage: test
  image: onec-client-vnc:${ONEC_VERSION}  # образ с Xvfb и VNC
  needs: ["build_cf"]
  script:
    # Запуск виртуального дисплея
    - export DISPLAY=:1
    - Xvfb :1 -screen 0 1920x1080x24 -ac &
    - sleep 2

    # Создание ИБ и загрузка конфигурации
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 CREATEINFOBASE
        File="/workspace/build/ib"
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /F "/workspace/build/ib"
        /LoadCfg "$CI_PROJECT_DIR/build/1cv8.cf"
        /UpdateDBCfg

    # Загрузка тестовых данных (фикстуры)
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /F "/workspace/build/ib"
        /RestoreIB "$CI_PROJECT_DIR/tests/fixtures/test-data.dt"

    # Запуск дымовых тестов
    - vanessa-runner run
        --ibconnection "File=/workspace/build/ib"
        --command "RunSmokeTests"
        --execute "$CI_PROJECT_DIR/tools/vanessa-add.epf"
        --settings "$CI_PROJECT_DIR/tests/smoke-settings.json"
        --reportjunit "$CI_PROJECT_DIR/build/reports/smoke-junit.xml"
        --reportallure "$CI_PROJECT_DIR/build/reports/allure"
  artifacts:
    reports:
      junit: build/reports/smoke-junit.xml
    paths:
      - build/reports/allure/
    when: always  # сохранять отчёты даже если тесты упали
    expire_in: 7 days
```

### 3.4. Сценарное BDD-тестирование с Vanessa Automation

Vanessa Automation — самый мощный и самый сложный инструмент тестирования в экосистеме 1С. Он позволяет описывать тесты на языке Gherkin (русскоязычный), записывать действия пользователя и воспроизводить их автоматически.

**Архитектура.** Vanessa Automation работает как внешняя обработка (EPF), которая запускается внутри клиента 1С. Она управляет интерфейсом 1С программно — нажимает кнопки, заполняет поля, читает табличные части. Для этого ей нужен работающий GUI, что в Docker обеспечивается через Xvfb (виртуальный дисплей).

**Установка:**

```bash
# Через opm (пакетный менеджер OneScript)
opm install vanessa-automation

# Или скачать EPF-файл из релизов
# https://github.com/Pr-Mex/vanessa-automation/releases
```

**Язык сценариев (Gherkin).** Тесты пишутся в файлах с расширением `.feature` на естественном языке:

```gherkin
# language: ru

Функциональность: Создание заказа покупателя
    Как менеджер по продажам
    Я хочу создавать заказы покупателей
    Чтобы фиксировать потребности клиентов

    Контекст:
        Допустим я подключаю TestClient "Тонкий клиент" логин "Менеджер" пароль ""

    Сценарий: Создание заказа с двумя товарами и проведение
        # Открытие формы нового документа
        Когда я открываю навигационную ссылку "e1cib/command/Документ.ЗаказПокупателя.Создать"
        Тогда открылась форма "Заказ покупателя (создание)"

        # Заполнение шапки
        И я нажимаю на гиперссылку "Контрагент"
        И в поле "Контрагент" я выбираю по строке "ООО Альфа"
        И я нажимаю кнопку выбора у поля "Договор"
        И в таблице "СписокДоговоров" я выбираю текущую строку

        # Добавление товаров в табличную часть
        И в табличном документе "Товары" я нажимаю на кнопку "Добавить"
        И в поле "Номенклатура" текущей строки я выбираю по строке "Кирпич красный"
        И в поле "Количество" текущей строки я ввожу текст "100"
        И в поле "Цена" текущей строки я ввожу текст "15.50"

        И в табличном документе "Товары" я нажимаю на кнопку "Добавить"
        И в поле "Номенклатура" текущей строки я выбираю по строке "Цемент М500"
        И в поле "Количество" текущей строки я ввожу текст "50"
        И в поле "Цена" текущей строки я ввожу текст "320.00"

        # Проведение документа
        И я нажимаю на кнопку "Провести и закрыть"
        Тогда у меня нет ошибок в журнале регистрации

    Сценарий: Проверка запрета проведения без товаров
        Когда я открываю навигационную ссылку "e1cib/command/Документ.ЗаказПокупателя.Создать"
        И в поле "Контрагент" я выбираю по строке "ООО Альфа"
        И я нажимаю на кнопку "Провести"
        Тогда я вижу предупреждение с текстом "Табличная часть Товары не заполнена"
        И я нажимаю кнопку "OK"
```

**Запись сценариев.** Vanessa Automation имеет режим записи — вы запускаете её в интерактивном режиме, выполняете действия в 1С руками, а она записывает каждый шаг в формате Gherkin. Потом записанный сценарий можно отредактировать и использовать для автоматического тестирования.

**Файл настроек Vanessa Automation (VanessaAutomation.json):**

```json
{
    "feature-files-paths": [
        "/workspace/tests/features"
    ],
    "report-path": "/workspace/build/reports/allure",
    "report-format": "Allure",
    "junit-report-path": "/workspace/build/reports/bdd-junit.xml",
    "screenshots-path": "/workspace/build/reports/screenshots",
    "make-screenshots-on-error": true,
    "stop-on-first-error": false,
    "testclient": {
        "additional-launch-parameters": "/DisableStartupMessages /DisableStartupDialogs"
    }
}
```

**Запуск в Docker — полный скрипт:**

```bash
#!/bin/bash
# run-bdd-tests.sh — запуск BDD-тестов в Docker-контейнере

set -e

# ═══════════════════════════════════════════════
# 1. Запуск виртуального дисплея
# ═══════════════════════════════════════════════
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
sleep 3

# Опционально: запуск VNC-сервера для отладки
# x11vnc -display :99 -forever -nopw &

# ═══════════════════════════════════════════════
# 2. Запуск сервера 1С и создание ИБ
# ═══════════════════════════════════════════════
# Запуск PostgreSQL (если в том же контейнере)
pg_ctlcluster 15 main start

# Создание информационной базы
/opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 CREATEINFOBASE \
    Srvr="localhost";Ref="test_bdd";DBMS="PostgreSQL"; \
    DBSrvr="localhost";DB="test_bdd"; \
    DBUID="postgres";DBPwd="postgres"

# Загрузка конфигурации
/opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER \
    /S "localhost\test_bdd" \
    /LoadCfg "/workspace/build/1cv8.cf" \
    /UpdateDBCfg

# Загрузка тестовых данных
/opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER \
    /S "localhost\test_bdd" \
    /RestoreIB "/workspace/tests/fixtures/bdd-data.dt"

# ═══════════════════════════════════════════════
# 3. Запуск тестового клиента 1С
# ═══════════════════════════════════════════════
# 1С должна быть запущена как клиент, к которому подключится Vanessa
/opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 ENTERPRISE \
    /S "localhost\test_bdd" \
    /N "Администратор" /P "" \
    /TestClient -TPort 48050 \
    /DisableStartupMessages \
    /DisableStartupDialogs &
CLIENT_PID=$!
sleep 10  # ждём запуска клиента

# ═══════════════════════════════════════════════
# 4. Запуск Vanessa Automation
# ═══════════════════════════════════════════════
/opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 ENTERPRISE \
    /S "localhost\test_bdd" \
    /N "Администратор" /P "" \
    /Execute "/workspace/tools/vanessa-automation.epf" \
    /C "StartFeaturePlayer;Settings=/workspace/tests/VanessaAutomation.json" \
    /TestManager -TPort 48051 \
    /DisableStartupMessages \
    /DisableStartupDialogs

EXIT_CODE=$?

# ═══════════════════════════════════════════════
# 5. Остановка процессов
# ═══════════════════════════════════════════════
kill $CLIENT_PID 2>/dev/null || true
kill $XVFB_PID 2>/dev/null || true

exit $EXIT_CODE
```

**Этап в .gitlab-ci.yml:**

```yaml
bdd_tests:
  stage: test
  image: onec-client-vnc:${ONEC_VERSION}
  needs: ["build_cf"]
  services:
    - name: postgres:15-1c
      alias: postgres
  variables:
    POSTGRES_DB: test_bdd
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: postgres
    DISPLAY: ":99"
  before_script:
    # Запуск виртуального дисплея
    - Xvfb :99 -screen 0 1920x1080x24 -ac &
    - sleep 3
  script:
    - chmod +x tests/run-bdd-tests.sh
    - tests/run-bdd-tests.sh
  after_script:
    # Сохранение скриншотов и видео при ошибках
    - cp -r /workspace/build/reports/screenshots $CI_PROJECT_DIR/build/ || true
  artifacts:
    reports:
      junit: build/reports/bdd-junit.xml
    paths:
      - build/reports/allure/
      - build/reports/screenshots/
    when: always
    expire_in: 14 days
```

### 3.5. Замер покрытия кода (Coverage41C)

Coverage41C — инструмент, который показывает, какие строки кода 1С были выполнены во время тестов. Это даёт объективную метрику: «из 10 000 строк кода тестами покрыто 3 500 (35%)».

**Принцип работы.** Coverage41C подключается к отладочному серверу 1С (dbgs) и отслеживает, какие строки кода выполнялись. После завершения тестов формирует отчёт в формате GenericCoverage (совместим с SonarQube).

**Репозиторий:** https://github.com/1c-syntax/Coverage41C

**Интеграция с тестами:**

```bash
# 1. Запуск сервера отладки 1С
/opt/1cv8/x86_64/${ONEC_VERSION}/dbgs --addr=localhost --port=1550 &
sleep 5

# 2. Запуск Coverage41C — он подключится к серверу отладки
java -jar coverage41c.jar start \
    --debugger "localhost:1550" \
    --output "/workspace/build/reports/coverage.xml" \
    --format "genericCoverage" \
    --projectDir "/workspace/src" &

# 3. Запуск тестов (модульных, дымовых, BDD — любых)
# ... (тесты выполняются, Coverage41C собирает данные) ...

# 4. Остановка Coverage41C — генерация отчёта
java -jar coverage41c.jar stop
```

**Загрузка отчёта в SonarQube** (добавляется к шагу sonarqube в пайплайне):

```bash
sonar-scanner \
    -Dsonar.coverageReportPaths=build/reports/coverage.xml
```

### 3.6. Отладка упавших тестов: VNC-доступ к контейнеру

Когда сценарные тесты падают, бывает сложно понять причину по логам — нужно увидеть, что происходит на «экране» 1С. Для этого используется VNC-доступ к работающему контейнеру.

**Настройка VNC в Docker-образе.** Добавьте в Dockerfile:

```dockerfile
RUN apt-get update && apt-get install -y \
    x11vnc \
    xvfb \
    novnc \
    websockify

# Запуск noVNC (доступ через браузер)
EXPOSE 6080
CMD ["bash", "-c", "Xvfb :1 -screen 0 1920x1080x24 & \
     x11vnc -display :1 -forever -nopw & \
     websockify --web /usr/share/novnc/ 6080 localhost:5900"]
```

**Использование.** При запуске контейнера пробросьте порт 6080:

```powershell
docker run -d -p 6080:6080 onec-client-vnc:8.3.25
```

Откройте http://localhost:6080 в браузере — вы увидите рабочий стол Linux с запущенным клиентом 1С. Можно наблюдать за выполнением тестов в реальном времени.

Образы от thedemoncat (onec-client) уже включают NoVNC на порту 6080.

### 3.7. Allure-отчёты: визуализация результатов тестирования

Allure — система отчётности, которая собирает результаты всех видов тестов в единый красивый HTML-отчёт с графиками, скриншотами и историей.

**Генерация отчёта** (после выполнения тестов):

```bash
# Установка Allure CLI
npm install -g allure-commandline

# Генерация HTML-отчёта
allure generate build/reports/allure -o build/reports/allure-html --clean

# Открытие отчёта
allure open build/reports/allure-html
```

**Публикация в GitLab Pages** (добавьте этап в .gitlab-ci.yml):

```yaml
pages:
  stage: deploy
  needs: ["smoke_tests", "bdd_tests"]
  script:
    - allure generate build/reports/allure -o public --clean
  artifacts:
    paths:
      - public
  only:
    - main
```

После этого отчёт доступен по адресу `https://ваш-логин.gitlab.io/ваш-проект/`.

---

## Часть 4. Полная автоматизация: от коммита до продуктива

### 4.1. Итоговый .gitlab-ci.yml — полный конвейер

```yaml
# ═══════════════════════════════════════════════════════
# CI/CD конвейер для 1С:Предприятие
# Полный цикл: сборка → анализ → тесты → деплой
# ═══════════════════════════════════════════════════════

stages:
  - build
  - analyze
  - test
  - report
  - deploy

variables:
  ONEC_VERSION: "8.3.25.1257"
  POSTGRES_DB: "ci_test_db"
  POSTGRES_USER: "postgres"
  POSTGRES_PASSWORD: "postgres"

# ─── Общие настройки ───────────────────────────
default:
  before_script:
    - export DISPLAY=:99
    - Xvfb :99 -screen 0 1920x1080x24 -ac &>/dev/null &
    - sleep 2

# ═══════════════════════════════════════════════
# ЭТАП 1: СБОРКА
# ═══════════════════════════════════════════════
build:
  stage: build
  image: onec-client:${ONEC_VERSION}
  script:
    # Конвертация EDT → формат конфигуратора
    - ring edt workspace export
        --workspace-location .
        --project .
        --configuration-files build/cf-xml

    # Создание ИБ и загрузка
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 CREATEINFOBASE
        File="build/ib"
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /F build/ib
        /LoadConfigFromFiles build/cf-xml
        /UpdateDBCfg
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /F build/ib
        /DumpCfg build/1cv8.cf
  artifacts:
    paths: [build/1cv8.cf, build/ib/]
    expire_in: 3 days

# ═══════════════════════════════════════════════
# ЭТАП 2: АНАЛИЗ КОДА
# ═══════════════════════════════════════════════
syntax_check:
  stage: analyze
  image: onec-client:${ONEC_VERSION}
  needs: [build]
  script:
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /F build/ib
        /CheckConfig -Server -ThinClient -WebClient
        -ExternalConnection -ExternalConnectionServer

bsl_analysis:
  stage: analyze
  image: openjdk:17-slim
  script:
    - java -jar /tools/bsl-ls.jar --analyze
        --srcDir src --reporter sonarGenericIssue
        --outputDir build/bsl-reports
  artifacts:
    paths: [build/bsl-reports/]

sonarqube:
  stage: analyze
  image: sonarsource/sonar-scanner-cli
  needs: [bsl_analysis]
  script:
    - sonar-scanner
        -Dsonar.projectKey=${CI_PROJECT_NAME}
        -Dsonar.sources=src
        -Dsonar.host.url=${SONAR_HOST_URL}
        -Dsonar.token=${SONAR_TOKEN}
        -Dsonar.externalIssuesReportPaths=build/bsl-reports/genericIssue.json

# ═══════════════════════════════════════════════
# ЭТАП 3: ТЕСТИРОВАНИЕ
# ═══════════════════════════════════════════════
unit_tests:
  stage: test
  image: onec-client:${ONEC_VERSION}
  needs: [build]
  services:
    - postgres:15-1c
  script:
    - vanessa-runner init-ib
        --db-server postgres --db-name $POSTGRES_DB
        --db-user $POSTGRES_USER --db-pwd $POSTGRES_PASSWORD
    - vanessa-runner load-cf --cf build/1cv8.cf
    - vanessa-runner load-ext --ext tools/yaxunit.cfe --name YAxUnit
    - vanessa-runner run-yaxunit
        --reportjunit build/reports/unit-junit.xml
  artifacts:
    reports: { junit: build/reports/unit-junit.xml }
    when: always

smoke_tests:
  stage: test
  image: onec-client-vnc:${ONEC_VERSION}
  needs: [build]
  services:
    - postgres:15-1c
  script:
    - vanessa-runner init-ib
        --db-server postgres --db-name "${POSTGRES_DB}_smoke"
        --db-user $POSTGRES_USER --db-pwd $POSTGRES_PASSWORD
    - vanessa-runner load-cf --cf build/1cv8.cf
    - vanessa-runner load-dt --dt tests/fixtures/smoke-data.dt
    - vanessa-runner run-smoke
        --settings tests/smoke-settings.json
        --reportjunit build/reports/smoke-junit.xml
        --reportallure build/reports/allure-smoke
  artifacts:
    reports: { junit: build/reports/smoke-junit.xml }
    paths: [build/reports/allure-smoke/]
    when: always

bdd_tests:
  stage: test
  image: onec-client-vnc:${ONEC_VERSION}
  needs: [build]
  services:
    - postgres:15-1c
  script:
    - vanessa-runner init-ib
        --db-server postgres --db-name "${POSTGRES_DB}_bdd"
        --db-user $POSTGRES_USER --db-pwd $POSTGRES_PASSWORD
    - vanessa-runner load-cf --cf build/1cv8.cf
    - vanessa-runner load-dt --dt tests/fixtures/bdd-data.dt
    - vanessa-runner run-vanessa
        --settings tests/VanessaAutomation.json
        --reportjunit build/reports/bdd-junit.xml
        --reportallure build/reports/allure-bdd
  artifacts:
    reports: { junit: build/reports/bdd-junit.xml }
    paths: [build/reports/allure-bdd/, build/reports/screenshots/]
    when: always

# ═══════════════════════════════════════════════
# ЭТАП 4: ОТЧЁТНОСТЬ
# ═══════════════════════════════════════════════
allure_report:
  stage: report
  image: node:18-slim
  needs: [unit_tests, smoke_tests, bdd_tests]
  script:
    - npm install -g allure-commandline
    - mkdir -p build/allure-combined
    - cp -r build/reports/allure-smoke/* build/allure-combined/ || true
    - cp -r build/reports/allure-bdd/* build/allure-combined/ || true
    - allure generate build/allure-combined -o public --clean
  artifacts:
    paths: [public/]
  when: always

# ═══════════════════════════════════════════════
# ЭТАП 5: ДЕПЛОЙ
# ═══════════════════════════════════════════════
deploy_test:
  stage: deploy
  image: onec-client:${ONEC_VERSION}
  needs: [unit_tests, smoke_tests, bdd_tests]
  script:
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /S "${TEST_SERVER}\${TEST_DB}"
        /N "Администратор" /P "${TEST_PASSWORD}"
        /LoadCfg build/1cv8.cf
        /UpdateDBCfg -Dynamic+
  environment:
    name: testing
  when: manual

deploy_prod:
  stage: deploy
  image: onec-client:${ONEC_VERSION}
  needs: [deploy_test]
  script:
    # Блокировка начала сеансов
    - vanessa-runner session-lock
        --server "${PROD_SERVER}" --db "${PROD_DB}"
        --admin-user "Администратор" --admin-pwd "${PROD_PASSWORD}"
        --lock-message "Обновление конфигурации"
        --lock-uc "UpdateCode123"

    # Завершение активных сеансов
    - vanessa-runner session-kill
        --server "${PROD_SERVER}" --db "${PROD_DB}"
        --uc "UpdateCode123"

    # Загрузка конфигурации
    - /opt/1cv8/x86_64/${ONEC_VERSION}/1cv8 DESIGNER
        /S "${PROD_SERVER}\${PROD_DB}"
        /N "Администратор" /P "${PROD_PASSWORD}"
        /UC "UpdateCode123"
        /LoadCfg build/1cv8.cf
        /UpdateDBCfg

    # Снятие блокировки
    - vanessa-runner session-unlock
        --server "${PROD_SERVER}" --db "${PROD_DB}"
        --admin-user "Администратор" --admin-pwd "${PROD_PASSWORD}"
  environment:
    name: production
  when: manual
  only:
    - main
```

### 4.2. Логика автоматического деплоя

Полностью автоматический деплой без ручного вмешательства (то, к чему стремился Иосиф в подкасте) выглядит следующим образом.

**Правило двух успешных раскаток.** Конфигурация автоматически деплоится на тестовую базу. Если на тестовой базе после двух последовательных успешных обновлений не зафиксировано ошибок (через мониторинг журнала регистрации), конфигурация автоматически раскатывается на продуктив.

Для этого `when: manual` заменяется на `when: on_success` с добавлением условий:

```yaml
deploy_prod:
  stage: deploy
  needs: [deploy_test]
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
      when: on_success  # автоматически, если все предыдущие этапы прошли
  script:
    # ... деплой на продуктив ...
```

**Технологическое окно.** Деплой на продуктив можно привязать к расписанию через GitLab Schedules — например, запускать только по будням с 23:00 до 01:00, когда нагрузка минимальна.

### 4.3. Мониторинг после деплоя

После автоматического обновления продуктивной базы рекомендуется настроить мониторинг:

**Проверка журнала регистрации** — скрипт на OneScript, который через 10–15 минут после деплоя проверяет журнал регистрации на наличие ошибок. Если ошибки обнаружены — отправляет уведомление в Telegram и откатывает конфигурацию.

**Проверка доступности** — простой HTTP-запрос к веб-публикации 1С. Если публикация не отвечает — алерт.

**Пример скрипта мониторинга (OneScript):**

```bsl
// monitoring.os — проверка после деплоя

ЧтениеЖР = Новый ЧтениеЖурналаРегистрации();
ЧтениеЖР.УстановитьФильтр(
    Новый Структура("НачалоПериода, Уровень",
        ТекущаяДата() - 900,  // последние 15 минут
        "Ошибка"
    )
);

КоличествоОшибок = 0;
Пока ЧтениеЖР.Прочитать() Цикл
    КоличествоОшибок = КоличествоОшибок + 1;
КонецЦикла;

Если КоличествоОшибок > 0 Тогда
    // Отправка уведомления в Telegram
    Телеграм = Новый HTTPСоединение("api.telegram.org");
    Телеграм.ОтправитьСообщение(
        "ВНИМАНИЕ: после деплоя обнаружено " + КоличествоОшибок + " ошибок!"
    );
КонецЕсли;
```

---

## Часть 5. Типичные проблемы и их решение

### 5.1. Docker на Windows — специфические проблемы

**Проблема:** Docker Desktop не запускается, ошибка «WSL 2 requires an update».
**Решение:** Скачайте обновление ядра WSL2 с https://aka.ms/wsl2kernel и установите. Затем выполните `wsl --set-default-version 2`.

**Проблема:** Низкая скорость работы с файлами.
**Причина:** Файлы, расположенные на NTFS-разделе Windows, работают через WSL2 медленно (операции ввода-вывода проходят через прослойку). Решение — хранить проектные файлы внутри файловой системы WSL2 (в `/home/`), а не в `/mnt/c/`.

**Проблема:** Контейнер с 1С не запускается, ошибка «shared memory».
**Решение:** Увеличьте shared memory: `docker run --shm-size=512m ...`

### 5.2. Проблемы с тестированием

**Проблема:** Сценарные тесты падают с ошибкой «Не удалось подключить TestClient».
**Причина:** 1С-клиент не успел запуститься до подключения Vanessa Automation. Решение — увеличьте `sleep` перед подключением или используйте скрипт с проверкой готовности.

**Проблема:** Тесты проходят локально, но падают в Docker.
**Причина:** Разрешение виртуального дисплея отличается от реального монитора. Элементы интерфейса могут быть расположены иначе. Решение — используйте Xvfb с разрешением 1920x1080 и проверяйте через VNC.

**Проблема:** Дымовые тесты падают на формах, требующих заполнения обязательных реквизитов.
**Решение:** Подготовьте файл фикстур (DT-файл) с минимальным набором данных: организация, контрагент, склад, номенклатура. Загружайте его перед запуском тестов.

---

## Часть 6. Ресурсы для изучения

### Репозитории на GitHub

Docker-образы: `firstBitMarksistskaya/onec-docker`, `thedemoncat/onec-base`, `alexanderfefelov/docker-1c-server`. OneScript: `EvilBeaver/OneScript` (oscript.io). Тестирование: `Pr-Mex/vanessa-automation`, `vanessa-opensource/add`, `bia-technologies/yaxunit`. CI/CD: `firstBitMarksistskaya/jenkins-lib`, `oscript-library/vanessa-ci-scripts`. Анализ: `1c-syntax/bsl-language-server`, `1c-syntax/sonar-bsl-plugin-community`. SonarQube для 1С: `Daabramov/Sonarqube-for-1c-docker`. Покрытие: `1c-syntax/Coverage41C`.

### Обучающие материалы

Статья «Docker для 1Сника» на Infostart (infostart.ru/1c/articles/1454888/). Руководство от 1С-Рарус «Docker для 1С» в двух частях (2025–2026). Курс OTUS «DevOps 1C» — полный курс по автоматизации. Доклады Владимира Кирбабы (BIA Technologies) на Infostart Event.

### Telegram-каналы

`@pravets_it` — Иосиф Правец: ИТ-дневник (автор подкаста). `@sergsyp` — подкаст «Мир 1С». «Менеджер Хранилищ, DevOps 1C и около» — профильный чат по DevOps в 1С. «OneScript и библиотеки» — сообщество разработчиков OneScript. Полный реестр: `SeiOkami/links-one-s` на GitHub.
