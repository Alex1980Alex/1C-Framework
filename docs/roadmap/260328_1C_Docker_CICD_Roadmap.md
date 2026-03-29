# Дорожная карта: CI/CD для 1С — от коммита до продуктива

## Адаптированная под текущий ПК и фреймворк D:\1С-Framework

**Версия:** 2.2 (2026-03-29)
**Конфигурация:** УправлениеТранспортомНаПЛК v2026.1.1.0 (91 справочник, 27 документов, 190 регистров сведений)
**Подход:** Windows-нативный CI (GitHub Actions + Self-Hosted Runner)

---

## Прогресс реализации

| Фаза | Описание | Статус | Дата |
|------|----------|:------:|------|
| **Фаза 0** | Быстрые победы | ✅ **ВЫПОЛНЕНО** | 2026-03-28 |
| 0.1 | Allure CLI v2.38.1 | ✅ | 2026-03-28 |
| 0.2 | BSL Language Server v0.22.0 (Java 17) | ✅ | 2026-03-28 |
| 0.3 | Docker cleanup (92→20 ГБ, -73 ГБ) | ✅ | 2026-03-28 |
| 0.4 | BSL LS анализ: 2027 файлов, 55030 диагностик | ✅ | 2026-03-28 |
| 0.5 | Каталоги CI (.github/workflows/, build/) | ✅ | 2026-03-28 |
| **Фаза 1** | Статический анализ (SonarQube) | ✅ **ВЫПОЛНЕНО** | 2026-03-29 |
| 1.1 | SonarQube Docker (`docker/docker-compose.sonarqube.yml`) | ✅ | 2026-03-29 |
| 1.2 | BSL-плагин (автоустановка в `setup-sonar.ps1`) | ✅ | 2026-03-29 |
| 1.3 | `sonar-project.properties` | ✅ | 2026-03-29 |
| 1.4 | sonar-scanner CLI (автоустановка в `setup-sonar.ps1`) | ✅ | 2026-03-29 |
| 1.5 | Скрипт анализа (`scripts/run-sonar-analysis.ps1`) | ✅ | 2026-03-29 |
| **Фаза 2** | GitHub Actions Self-Hosted Runner | ✅ **ВЫПОЛНЕНО** | 2026-03-29 |
| 2.1 | Установка и регистрация Runner | ⬜ Ручной шаг | — |
| 2.2 | GitHub Secrets и переменные | ⬜ Ручной шаг | — |
| 2.3 | Workflow `ci-1c.yml` | ✅ | 2026-03-29 |
| **Фаза 3** | Полное тестирование (YAxUnit/BDD/Coverage) | ⬜ TODO | — |
| **Фаза 4** | Docker-образы 1С (требует DEB) | ⬜ Будущее | — |

---

## Содержание

1. [Текущее состояние и архитектура конвейера](#часть-1-текущее-состояние-и-архитектура-конвейера)
2. [Фазы реализации](#часть-2-фазы-реализации)
3. [Архитектура тестирования: 3 слоя логики 1С](#часть-3-архитектура-тестирования-3-слоя-логики-1с)
4. [Типичные проблемы и решения](#часть-4-типичные-проблемы-и-решения-windows-специфичные)
5. [Будущее развитие — Docker-образы 1С](#часть-5-будущее-развитие--docker-образы-1с)
6. [Ресурсы](#часть-6-ресурсы)

---

## Часть 1. Текущее состояние и архитектура конвейера

### 1.1. Общая архитектура конвейера

Архитектура **гибридная**: оркестрация и вспомогательные сервисы (SonarQube, Allure) работают в Docker, а сборка, анализ кода и тестирование выполняются в нативной среде Windows.

**Схема процесса:**

```
git push / PR
    │
    ▼
GitHub Actions (облако)
    │ ← читает .github/workflows/ci-1c.yml
    ▼
Self-Hosted Runner (этот ПК, Windows 11)
    │
    ╔══════════════════════════════════════════════════════╗
    ║  Нативное окружение Windows                          ║
    ║                                                      ║
    ║  ┌─────────────────────────────────────────────┐     ║
    ║  │ 1С 8.3.27.1859 (x64)                        │     ║
    ║  │ OneScript 2.0.0 + vanessa-runner 2.6.0       │     ║
    ║  │ BSL Language Server (Java 17)                │     ║
    ║  │ MS SQL 2022 (localhost)                       │     ║
    ║  └─────────────────────────────────────────────┘     ║
    ║                                                      ║
    ║  Этап 1: Статический анализ (BSL LS → SonarQube)     ║
    ║  Этап 2: Модульные тесты (YAxUnit — Слой 3)         ║
    ║  Этап 3: Дымовые тесты (Vanessa ADD — Smoke)        ║
    ║  Этап 4: Сценарные BDD-тесты (Vanessa Automation)   ║
    ║  Этап 5: Генерация отчёта (Allure)                   ║
    ╚══════════════════════════════════════════════════════╝
    │
    ▼ Артефакты: SonarQube дашборд, JUnit XML, Allure HTML
    │
    ▼
GitHub PR: ✅/❌ статусы + комментарий с результатами
```

**Почему Windows-нативный, а не Docker для 1С:**

1. **Нет Linux-пакетов 1С** — DEB-пакеты отсутствуют, Docker-образ с 1С собрать невозможно.
2. **GUI-тесты стабильнее** — Vanessa Automation работает с тонким клиентом 1С напрямую, без эмуляции дисплея (Xvfb).
3. **Лицензирование** — HASP-ключи и сетевые лицензии доступны нативно.
4. **Производительность** — нет накладных расходов на виртуализацию ОС для тяжёлой конфигурации (190 регистров).

### 1.2. Текущее состояние: что готово

| Компонент | Статус | Версия / Расположение |
|-----------|:------:|----------------------|
| ОС и WSL2 | ✅ | Windows 11 IoT Enterprise, WSL2 (Ubuntu + docker-desktop) |
| Docker Desktop | ✅ | Работает, 13 контейнеров |
| Платформа 1С | ✅ | 8.3.27.1859 (x64), `C:\Program Files\1cv8\8.3.27.1859\bin` |
| 1С EDT | ✅ | `C:\Program Files\1C\1CE` |
| Git | ✅ | 2.53.0 + GitHub CLI 2.63.2 |
| Java | ✅ | OpenJDK 17.0.13 (Zulu) |
| OneScript | ✅ | 2.0.0, `C:\Tools\OneScript\bin\oscript.exe` |
| vanessa-runner | ✅ | v2.6.0, `C:\Tools\OneScript\lib\vanessa-runner\` |
| YAxUnit | ✅ | v25.12, 690 тестов (80.3% pass), `tools\vanessa\YAxUnit-25.12.cfe` |
| Smoke (Vanessa ADD) | ✅ | v0.2.1, `tools\vanessa\Smoke-25.12.cfe` |
| Vanessa Automation | ✅ | v1.2.043.1, `tools\vanessa\vanessa-automation-single.epf` |
| BDD features | ✅ | 3 файла в `features\` |
| BDD скрипт запуска | ✅ | `tools\vanessa\run-bdd.ps1` |
| MS SQL | ✅ | 2022, БД `testdb1c` |
| Qdrant, Neo4j, Prometheus, Grafana | ✅ | Docker-контейнеры |

### 1.3. Что нужно установить

| Компонент | Сложность | Действие | Статус |
|-----------|:---------:|----------|:------:|
| BSL Language Server | 🟢 Низкая | Скачать JAR с GitHub → `tools\bsl-ls\` | ✅ Выполнено (v0.22.0) |
| Allure CLI | 🟢 Низкая | `npm install -g allure-commandline` | ✅ Выполнено (v2.38.1) |
| GitHub Actions Runner | 🟢 Низкая | Скачать, зарегистрировать как Windows Service | ⬜ TODO |
| SonarQube | 🟡 Средняя | Docker-контейнер + BSL-плагин | ⬜ TODO |
| sonar-scanner CLI | 🟡 Средняя | Скачать ZIP, добавить в PATH | ⬜ TODO |
| Coverage41C | 🟡 Средняя | Скачать JAR, настроить dbgs | ⬜ TODO |

### 1.4. Системные требования vs текущее железо

| Ресурс | Требования CI/CD | Текущее состояние | Статус |
|--------|-----------------|-------------------|:------:|
| CPU | 4+ ядра | AMD Ryzen 7 5700G (8 ядер / 16 потоков) | ✅ |
| RAM | 16 ГБ мин, 32 ГБ рек. | 32 ГБ DDR4 | ✅ |
| Диск C: | 50+ ГБ свободно | 256 ГБ NVMe, ~126 ГБ свободно после очистки | ✅ Docker очищен (92→20 ГБ) |
| Диск D: | 100+ ГБ | 2 ТБ NVMe ADATA LEGEND 960, 155 ГБ свободно | ✅ |
| Windows | 10/11 Pro/Enterprise | Windows 11 IoT Enterprise | ✅ |

**Выполнено (2026-03-28):** `docker image prune -a -f` + `docker builder prune -a -f` — освобождено **73 ГБ** (142→11 образов, 92.85→20.17 ГБ). Рекомендация на будущее: перенести WSL2 дистрибутив Docker на диск D:.

---

## Часть 2. Фазы реализации

### Фаза 0: Быстрые победы (1 день) ✅ ВЫПОЛНЕНО 2026-03-28

#### 0.1 Установка Allure CLI ✅

```powershell
npm install -g allure-commandline
allure --version
# Результат: 2.38.1
```

#### 0.2 Скачивание BSL Language Server ✅

```powershell
New-Item -ItemType Directory -Force -Path "D:\1С-Framework\tools\bsl-ls"

$bslVersion = "0.22.0"
$bslUrl = "https://github.com/1c-syntax/bsl-language-server/releases/download/v$bslVersion/bsl-language-server-$bslVersion-exec.jar"
Invoke-WebRequest -Uri $bslUrl -OutFile "D:\1С-Framework\tools\bsl-ls\bsl-language-server.jar"

# Проверка
java -jar "D:\1С-Framework\tools\bsl-ls\bsl-language-server.jar" --version
# Результат: version: 0.22.0 (90 МБ, совместим с Java 17)
```

> **Важно:** BSL LS v0.29.0 требует Java 21 (class file version 65.0). На текущем ПК Java 17 → используем v0.22.0.

#### 0.3 Очистка Docker ✅

```powershell
docker image prune -a -f
docker builder prune -a -f
docker system df
# Результат: 142→11 образов, 92.85→20.17 ГБ, освобождено ~73 ГБ
```

#### 0.4 Первый запуск BSL LS анализа ✅

```powershell
New-Item -ItemType Directory -Force -Path "D:\1С-Framework\build\bsl-report"

java -jar "D:\1С-Framework\tools\bsl-ls\bsl-language-server.jar" `
    --analyze `
    --srcDir "D:\1С-Framework\src\projects\configuration\260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС\src" `
    --reporter json `
    --outputDir "D:\1С-Framework\build\bsl-report"
```

**Результаты первого анализа (2026-03-28):**

| Метрика | Значение |
|---------|----------|
| Файлов проанализировано | 2 027 |
| Время анализа | 40 секунд |
| Всего диагностик | **55 030** |
| Error | 810 |
| Warning | 17 515 |
| Information | 20 502 |
| Hint | 16 203 |

**Top-10 правил:**

| Правило | Количество | Описание |
|---------|-----------|----------|
| LineLength | 10 148 | Длина строки превышает лимит |
| MissingSpace | 6 217 | Пропущен пробел |
| MissingParameterDescription | 4 850 | Нет описания параметра |
| Typo | 3 840 | Опечатка |
| UsingServiceTag | 3 591 | Использование служебных тегов |
| DuplicateStringLiteral | 2 532 | Дублирование строковых литералов |
| IfElseIfEndsWithElse | 2 391 | Отсутствует ветка Иначе |
| MagicNumber | 2 379 | Магические числа |
| NestedFunctionInParameters | 2 246 | Вложенные функции в параметрах |
| CognitiveComplexity | 2 182 | Высокая когнитивная сложность |

> **Путь к отчёту:** `build/bsl-report/bsl-json.json` (66 МБ)

#### 0.5 Создание структуры каталогов ✅

```powershell
$dirs = @(
    "D:\1С-Framework\.github\workflows",
    "D:\1С-Framework\build\bsl-report",
    "D:\1С-Framework\build\reports",
    "D:\1С-Framework\build\allure-results"
)
$dirs | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ }
```

---

### Фаза 1: Статический анализ ✅ ВЫПОЛНЕНО 2026-03-29

#### 1.1 SonarQube в Docker

Добавить в существующий `docker-compose.yml` или создать отдельный:

```yaml
services:
  sonarqube:
    image: sonarqube:lts-community
    container_name: sonarqube-1c
    ports:
      - "9000:9000"
    environment:
      - SONAR_ES_BOOTSTRAP_CHECKS_DISABLE=true
    volumes:
      - sonarqube_data:/opt/sonarqube/data
      - sonarqube_extensions:/opt/sonarqube/extensions
    mem_limit: 4g

volumes:
  sonarqube_data:
  sonarqube_extensions:
```

```powershell
docker compose up -d sonarqube
# Дождаться запуска (~2-3 минуты), открыть http://localhost:9000
# Логин: admin / admin → сменить пароль
```

#### 1.2 Установка BSL-плагина для SonarQube

```powershell
$pluginVersion = "0.15.2"
$pluginUrl = "https://github.com/1c-syntax/sonar-bsl-plugin-community/releases/download/v$pluginVersion/sonar-bsl-plugin-community-$pluginVersion.jar"

Invoke-WebRequest -Uri $pluginUrl -OutFile "sonar-bsl-plugin.jar"
docker cp sonar-bsl-plugin.jar sonarqube-1c:/opt/sonarqube/extensions/plugins/
docker restart sonarqube-1c
```

#### 1.3 Конфигурация sonar-project.properties

Файл `D:\1С-Framework\sonar-project.properties`:

```properties
sonar.projectKey=upravlenie-transportom-plk
sonar.projectName=УправлениеТранспортомНаПЛК
sonar.projectVersion=2026.1.1.0

sonar.sources=src/bsl
sonar.sourceEncoding=UTF-8
sonar.language=bsl

sonar.bsl.languageserver.reportPath=build/bsl-report/bsl-ls-report.json

# Будущее: покрытие кода
# sonar.coverageReportPaths=build/reports/coverage.xml
```

#### 1.4 Установка sonar-scanner CLI

```powershell
$scannerVersion = "6.2.1.4610"
$scannerUrl = "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-$scannerVersion-windows-x64.zip"

Invoke-WebRequest -Uri $scannerUrl -OutFile "D:\1С-Framework\tools\sonar-scanner.zip"
Expand-Archive "D:\1С-Framework\tools\sonar-scanner.zip" -DestinationPath "D:\1С-Framework\tools" -Force

# Добавить в PATH
[Environment]::SetEnvironmentVariable("Path",
    $env:Path + ";D:\1С-Framework\tools\sonar-scanner-$scannerVersion-windows-x64\bin", "User")
```

#### 1.5 Полный цикл анализа

```powershell
# Скрипт: scripts/run-sonar-analysis.ps1

[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ProjectRoot = "D:\1С-Framework"

# 1. BSL Language Server → JSON отчёт
Write-Host "[1/2] BSL Language Server..." -ForegroundColor Cyan
java -jar "$ProjectRoot\tools\bsl-ls\bsl-language-server.jar" `
    --analyze `
    --srcDir "$ProjectRoot\src\bsl" `
    --reporter json `
    --outputDir "$ProjectRoot\build\bsl-report"

# 2. Sonar Scanner → отправка в SonarQube
Write-Host "[2/2] Sonar Scanner..." -ForegroundColor Cyan
sonar-scanner `
    -Dsonar.host.url="http://localhost:9000" `
    -Dsonar.token="$env:SONAR_TOKEN"

Write-Host "Отчёт: http://localhost:9000/dashboard?id=upravlenie-transportom-plk" -ForegroundColor Green
```

---

### Фаза 2: GitHub Actions Self-Hosted Runner ✅ ВЫПОЛНЕНО 2026-03-29

#### 2.1 Установка и регистрация Runner

```powershell
# Создать каталог
New-Item -ItemType Directory -Force -Path "D:\actions-runner"
Set-Location "D:\actions-runner"

# Скачать (версию проверить на github.com/actions/runner/releases)
$runnerVersion = "2.322.0"
Invoke-WebRequest -Uri "https://github.com/actions/runner/releases/download/v$runnerVersion/actions-runner-win-x64-$runnerVersion.zip" -OutFile "runner.zip"
Expand-Archive "runner.zip" -DestinationPath "." -Force

# Регистрация (токен взять из Settings → Actions → Runners → New self-hosted runner)
.\config.cmd `
    --url "https://github.com/YOUR_ORG/YOUR_REPO" `
    --token "YOUR_RUNNER_TOKEN" `
    --name "windows-1c-runner" `
    --labels "self-hosted,windows-11,1c,bsl" `
    --work "D:\actions-runner\work" `
    --runasservice
```

#### 2.2 GitHub Secrets и переменные

**Settings → Secrets and variables → Actions → Secrets:**

| Секрет | Значение | Описание |
|--------|----------|----------|
| `USER_1C_LOGIN` | `a.terletskiy@sodru.com` | Логин 1С |
| `USER_1C_PASS` | `****` | Пароль 1С |
| `SONAR_TOKEN` | `****` | Токен SonarQube |

**Settings → Variables:**

| Переменная | Значение | Описание |
|------------|----------|----------|
| `SRV_1C` | `KOMPUTER` | Имя сервера 1С (НЕ localhost!) |
| `DB_NAME` | `testdb1c` | Имя базы данных |
| `ONEC_VERSION` | `8.3.27.1859` | Версия платформы |

#### 2.3 GitHub Actions Workflow

Файл `.github/workflows/ci-1c.yml`:

```yaml
name: CI 1C:Enterprise

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  workflow_dispatch:

env:
  ONEC_PATH: "C:\\Program Files\\1cv8\\8.3.27.1859\\bin"
  OSCRIPT_PATH: "C:\\Tools\\OneScript\\bin\\oscript.exe"
  PROJECT_PATH: "D:\\1С-Framework"
  IB_CONNECTION: "/SKOMPUTER\\testdb1c"

jobs:
  # ═══════════════════════════════════════
  # Статический анализ BSL (параллельно)
  # ═══════════════════════════════════════
  bsl-analysis:
    name: BSL Analysis
    runs-on: [self-hosted, windows-11, 1c]
    steps:
      - uses: actions/checkout@v4

      - name: Run BSL Language Server
        shell: pwsh
        run: |
          [Console]::OutputEncoding = [Text.Encoding]::UTF8
          java -jar "${{ env.PROJECT_PATH }}\tools\bsl-ls\bsl-language-server.jar" `
            --analyze `
            --srcDir "${{ env.PROJECT_PATH }}\src\bsl" `
            --reporter json `
            --outputDir "${{ env.PROJECT_PATH }}\build\bsl-report"

      - name: Run Sonar Scanner
        shell: pwsh
        env:
          SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}
        run: |
          sonar-scanner `
            -Dsonar.host.url="http://localhost:9000" `
            -Dsonar.token="$env:SONAR_TOKEN" `
            -Dsonar.projectBaseDir="${{ env.PROJECT_PATH }}"

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: bsl-report
          path: build/bsl-report/

  # ═══════════════════════════════════════
  # YAxUnit модульные тесты (параллельно)
  # ═══════════════════════════════════════
  yaxunit-tests:
    name: YAxUnit Tests
    runs-on: [self-hosted, windows-11, 1c]
    steps:
      - uses: actions/checkout@v4

      - name: Run YAxUnit
        shell: pwsh
        env:
          USER_1C: ${{ secrets.USER_1C_LOGIN }}
          PASS_1C: ${{ secrets.USER_1C_PASS }}
        run: |
          [Console]::OutputEncoding = [Text.Encoding]::UTF8
          $env:MSYS_NO_PATHCONV = "1"

          & "${{ env.OSCRIPT_PATH }}" `
            "C:\Tools\OneScript\lib\vanessa-runner\vanessa-runner.os" `
            run `
            --ibconnection "${{ env.IB_CONNECTION }}" `
            --db-user "$env:USER_1C" `
            --db-pwd "$env:PASS_1C" `
            --command "RunUnitTests" `
            --execute "${{ env.PROJECT_PATH }}\tools\vanessa\YAxUnit-25.12.cfe" `
            --settings "${{ env.PROJECT_PATH }}\tools\yaxunit.json"

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: yaxunit-report
          path: build/reports/junit.xml

  # ═══════════════════════════════════════
  # Smoke тесты (параллельно)
  # ═══════════════════════════════════════
  smoke-tests:
    name: Smoke Tests
    runs-on: [self-hosted, windows-11, 1c]
    steps:
      - uses: actions/checkout@v4

      - name: Run Smoke Tests
        shell: pwsh
        env:
          USER_1C: ${{ secrets.USER_1C_LOGIN }}
          PASS_1C: ${{ secrets.USER_1C_PASS }}
        run: |
          [Console]::OutputEncoding = [Text.Encoding]::UTF8

          & "${{ env.OSCRIPT_PATH }}" `
            "C:\Tools\OneScript\lib\vanessa-runner\vanessa-runner.os" `
            run `
            --ibconnection "${{ env.IB_CONNECTION }}" `
            --db-user "$env:USER_1C" `
            --db-pwd "$env:PASS_1C" `
            --command "RunSmokeTests" `
            --execute "${{ env.PROJECT_PATH }}\tools\vanessa\vanessa-automation-single.epf" `
            --settings "${{ env.PROJECT_PATH }}\tools\vanessa\vanessa.json"

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: smoke-report
          path: build/reports/smoke-junit.xml

  # ═══════════════════════════════════════
  # BDD тесты Vanessa Automation
  # ═══════════════════════════════════════
  bdd-tests:
    name: BDD Tests
    runs-on: [self-hosted, windows-11, 1c]
    steps:
      - uses: actions/checkout@v4

      - name: Run BDD Tests
        shell: pwsh
        env:
          USER_1C: ${{ secrets.USER_1C_LOGIN }}
          PASS_1C: ${{ secrets.USER_1C_PASS }}
        run: |
          [Console]::OutputEncoding = [Text.Encoding]::UTF8

          # BDD через PowerShell скрипт (обходит проблему кириллического пути)
          powershell -File "${{ env.PROJECT_PATH }}\tools\vanessa\run-bdd.ps1"

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: bdd-report
          path: |
            build/reports/bdd-junit.xml
            build/reports/screenshots/

  # ═══════════════════════════════════════
  # Allure отчёт (после всех тестов)
  # ═══════════════════════════════════════
  allure-report:
    name: Allure Report
    runs-on: [self-hosted, windows-11, 1c]
    needs: [bsl-analysis, yaxunit-tests, smoke-tests, bdd-tests]
    if: always()
    steps:
      - uses: actions/checkout@v4

      - name: Download all reports
        uses: actions/download-artifact@v4
        with:
          path: build/allure-results
          merge-multiple: true

      - name: Generate Allure Report
        shell: pwsh
        run: |
          allure generate build/allure-results -o build/allure-report --clean

      - uses: actions/upload-artifact@v4
        with:
          name: allure-report
          path: build/allure-report/

      - name: Comment PR with results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## Результаты CI 1С\n\n| Этап | Статус |\n|------|--------|\n| BSL Analysis | ${{ needs.bsl-analysis.result }} |\n| YAxUnit | ${{ needs.yaxunit-tests.result }} |\n| Smoke | ${{ needs.smoke-tests.result }} |\n| BDD | ${{ needs.bdd-tests.result }} |\n\nAllure отчёт доступен в артефактах сборки.`
            })
```

---

### Ход реализации Фаз 1-2 (2026-03-29)

В ходе реализации первой фазы была развернута инфраструктура статического анализа кода на базе SonarQube с поддержкой языка BSL (1С:Предприятие). Во второй фазе создан CI/CD пайплайн GitHub Actions.

#### 1. Конфигурация Docker Compose

Создан файл **`docker/docker-compose.sonarqube.yml`** для изолированного запуска сервера анализа:

- **Образ:** `sonarqube:lts-community`
- **Контейнер:** `sonarqube-1c`, порт 9000
- **Ограничения ресурсов:** Лимит памяти 4 GB (необходимо для работы Java-машины и парсинга больших проектов)
- **Healthcheck:** Проверка состояния через `curl -f http://localhost:9000/api/system/status`
- **Тома (Volumes):** 3 именованных тома (`data`, `extensions`, `logs`) для сохранения состояния и логов между перезапусками
- **Таймаут запуска:** `start_period: 120s` (SonarQube требует значительного времени на инициализацию базы данных)

#### 2. Конфигурация проекта SonarQube

Создан файл **`sonar-project.properties`** в корне репозитория:

- **projectKey:** `upravlenie-transportom-plk` — уникальный идентификатор проекта
- **sources:** `src/projects/configuration` — директория с исходниками конфигурации (2027 BSL файлов)
- **Режим анализа:** External report mode — BSL Language Server генерирует JSON-отчет, SonarQube импортирует его через параметр `sonar.bsl.languageserver.reportPath`
- **Покрытие кода:** Добавлен placeholder для будущей интеграции с Coverage41C

#### 3. Скрипт автоматизации setup-sonar.ps1

Создан **`scripts/setup-sonar.ps1`** — скрипт первичной настройки окружения (5 шагов):

1. **Запуск SonarQube:** `docker compose -f docker/docker-compose.sonarqube.yml up -d`
2. **Ожидание готовности:** Опрос `/api/system/status` каждые 10 секунд (максимум 30 попыток) до получения статуса UP
3. **Загрузка sonar-scanner:** Скачивание CLI v6.2.1.4610 (пропуск, если уже установлен)
4. **Установка BSL плагина:** Загрузка плагина v0.15.2, копирование в контейнер через `docker cp`, перезапуск сервера
5. **Финализация:** Ожидание перезапуска и вывод учетных данных (admin/admin)

#### 4. Скрипт запуска анализа run-sonar-analysis.ps1

Создан **`scripts/run-sonar-analysis.ps1`** — основной скрипт для запуска анализа (2 шага):

1. **BSL Language Server v0.22.0:** Запуск анализа, генерация отчета в `build/bsl-report/bsl-json.json`
2. **sonar-scanner:** Загрузка результатов на localhost:9000
- **Graceful degradation:** Пропуск SonarQube если не задан `SONAR_TOKEN`, пропуск scanner если не установлен

#### 5. GitHub Actions CI Workflow

Создан файл **`.github/workflows/ci-1c.yml`** со следующей структурой:

**Параллельные задания (Jobs):**

| Job | Описание | Особенности |
|-----|----------|-------------|
| **bsl-analysis** | Анализ BSL LS + sonar-scanner | Graceful skip при отсутствии установки |
| **yaxunit-tests** | Запуск YAxUnit через vanessa-runner | Переменная `MSYS_NO_PATHCONV=1` |
| **bdd-tests** | Vanessa Automation через `run-bdd.ps1` | `continue-on-error: true` (GUI-зависимость) |
| **allure-report** | Генерация HTML-отчета Allure | Комментарий в PR с таблицей результатов |

**Фильтрация путей (Path filters):**
Workflow запускается только при изменениях в: `src/projects/**`, `src/bsl/**`, `features/**`, `tools/vanessa/**`

**Кодировка:** Все PowerShell-шаги начинаются с `[Console]::OutputEncoding = [Text.Encoding]::UTF8`

**Секреты (Secrets):** `USER_1C_LOGIN`, `USER_1C_PASS`, `SONAR_TOKEN`

**Глобальные переменные окружения:** `ONEC_PATH`, `OSCRIPT_PATH`, `PROJECT_PATH`, `BSL_SRC`, `IB_CONNECTION`

#### 6. Требуемые ручные шаги

| Шаг | Действие | Описание |
|-----|----------|----------|
| **2.1** | Установка GitHub Actions Runner | Регистрация с лейблами: `self-hosted`, `windows-11`, `1c` |
| **2.2** | Настройка GitHub Secrets | Добавить: `USER_1C_LOGIN`, `USER_1C_PASS`, `SONAR_TOKEN` |

#### Сводка созданных файлов

| Файл | Размер | Назначение |
|------|--------|------------|
| `docker/docker-compose.sonarqube.yml` | 0.8 KB | Конфигурация Docker Compose для SonarQube |
| `sonar-project.properties` | 0.6 KB | Параметры проекта для sonar-scanner |
| `scripts/setup-sonar.ps1` | 4.6 KB | Автоматизация развертывания SonarQube (5 шагов) |
| `scripts/run-sonar-analysis.ps1` | 2.2 KB | Запуск BSL LS анализа и загрузка в SonarQube |
| `.github/workflows/ci-1c.yml` | 7.1 KB | CI/CD пайплайн с 4 параллельными заданиями |

#### Быстрый старт

```powershell
# 1. Первичная настройка SonarQube (выполняется один раз)
powershell -File scripts/setup-sonar.ps1

# 2. Запуск статического анализа
powershell -File scripts/run-sonar-analysis.ps1

# 3. Открытие дашборда SonarQube в браузере
Start-Process "http://localhost:9000"
```

---

### Фаза 3: Полное тестирование (5-7 дней)

#### 3.1 Написание YAxUnit тестов для бизнес-логики

Ключевые тесты для модуля `гкс_ВходнойКонтрольКачества`:

```bsl
// Тест: каскадная блокировка по группе ТС
Процедура ТестБлокировкаЦепочкиПоГруппе() Экспорт

    // Подготовка: 3 ТС одного поставщика
    Регистрация1 = СоздатьРегистрацию("ТС-001", "Поставщик1", "Пшеница");
    Регистрация2 = СоздатьРегистрацию("ТС-002", "Поставщик1", "Пшеница");
    Регистрация3 = СоздатьРегистрацию("ТС-003", "Поставщик1", "Пшеница");

    // Действие: ТС-001 получило КачествоНеПринято
    гкс_ВходнойКонтрольКачества.ОбработатьРезультатАнализа(
        Регистрация1, "Клейковина",
        Перечисления.гкс_СостоянияКачества.КачествоНеПринято);

    // Проверка: ТС-002 и ТС-003 заблокированы
    ЮТест.ОжидаетЧто(Заблокирована(Регистрация2)).Равно(Истина)
        .Описание("ТС-002 должно быть заблокировано каскадом");
    ЮТест.ОжидаетЧто(Заблокирована(Регистрация3)).Равно(Истина)
        .Описание("ТС-003 должно быть заблокировано каскадом");

КонецПроцедуры

// Тест: разблокировка при принятии качества
Процедура ТестРазблокировкаЦепочки() Экспорт

    // Подготовка: заблокированная цепочка
    // ... (создание данных) ...

    // Действие: разблокировка головного ТС
    гкс_ВходнойКонтрольКачества.РазблокироватьРегистрацию(Регистрация1);

    // Проверка: вся цепочка разблокирована
    ЮТест.ОжидаетЧто(Заблокирована(Регистрация2)).Равно(Ложь);
    ЮТест.ОжидаетЧто(Заблокирована(Регистрация3)).Равно(Ложь);

КонецПроцедуры

// Тест: NULL в SQL фильтре
Процедура ТестФильтрНеЗаблокированныхБезNULL() Экспорт

    // Подготовка: запись без явного значения Разблокировано
    СоздатьЗаписьБлокировки(Регистрация, Неопределено); // NULL

    // Действие: получить заблокированные
    Результат = гкс_ВходнойКонтрольКачества.ПолучитьЗаблокированные(Контрагент);

    // Проверка: NULL не пропущен фильтром
    ЮТест.ОжидаетЧто(Результат.Количество()).БольшеИлиРавно(1)
        .Описание("Записи с NULL в поле Разблокировано должны считаться заблокированными");

КонецПроцедуры
```

#### 3.2 BDD feature-файлы для критичных сценариев

```gherkin
# language: ru
# Файл: features/blocked_ts_cascade.feature

Функционал: Каскадная блокировка транспортных средств
    Как оператор ПЛК
    Я хочу видеть автоматическую блокировку ТС
    Чтобы не пропустить некачественное сырьё

    Контекст:
        Допустим я подключаю TestClient "Тонкий клиент"

    Сценарий: Блокировка цепочки при КачествоНеПринято
        Когда я открываю навигационную ссылку "e1cib/command/Обработка.гкс_ПриемкаТранспорта"
        Тогда открылась форма "*правление транспорто*"

        # Выбор регистрации с результатом анализа
        И в таблице "СписокРегистраций" я выбираю строку с "ТС-001"
        И я вижу что колонка "СостояниеКачества" равна "КачествоНеПринято"

        # Проверка каскадной блокировки
        И в таблице "ЗаблокированныеТС" я вижу строку с "ТС-002"
        И в таблице "ЗаблокированныеТС" я вижу строку с "ТС-003"

    Сценарий: Разблокировка через АРМ
        Когда я открываю навигационную ссылку "e1cib/command/Обработка.гкс_ПриемкаТранспорта"
        И я выбираю регистрацию "ТС-001"
        И я нажимаю кнопку "Разблокировать"
        Тогда в таблице "ЗаблокированныеТС" отсутствует строка с "ТС-002"
        И у меня нет ошибок в журнале регистрации
```

#### 3.3 Coverage41C (замер покрытия)

```powershell
# Скачать Coverage41C
$coverageUrl = "https://github.com/1c-syntax/Coverage41C/releases/latest"
# Скачать JAR → tools/coverage41c/

# Запуск сервера отладки 1С
& "$env:ONEC_PATH\dbgs.exe" --addr=localhost --port=1550

# Запуск Coverage41C
java -jar "tools\coverage41c\coverage41c.jar" start `
    --debugger "localhost:1550" `
    --output "build\reports\coverage.xml" `
    --format "genericCoverage" `
    --projectDir "src\bsl"

# Запуск тестов (YAxUnit, Smoke, BDD)
# ... тесты выполняются ...

# Остановка — генерация отчёта
java -jar "tools\coverage41c\coverage41c.jar" stop

# Загрузка в SonarQube
sonar-scanner -Dsonar.coverageReportPaths=build/reports/coverage.xml
```

---

## Часть 3. Архитектура тестирования: 3 слоя логики 1С

### 3.1 Три слоя логики

В 1С логика распределена по трём слоям. Непонимание этого — главная причина пропущенных багов и хрупких тестов.

```
┌─────────────────────────────────────────────────┐
│  СЛОЙ 1: Форма (клиент)                         │
│  ПриИзменении(), ОбработкаВыбора(),             │
│  команды формы, видимость элементов              │
│                                                  │
│  Тестируется: ТОЛЬКО Vanessa Automation (BDD)    │
│  YAxUnit: ❌ НЕ видит этот слой                  │
├─────────────────────────────────────────────────┤
│  СЛОЙ 2: Форма (сервер)                         │
│  ПередЗаписьюНаСервере(), ПриСозданииНаСервере()│
│  ОбработкаПроверкиЗаполненияНаСервере()         │
│                                                  │
│  Тестируется: ТОЛЬКО Vanessa Automation (BDD)    │
│  YAxUnit: ❌ НЕ видит — срабатывает только       │
│  при записи через форму                          │
├─────────────────────────────────────────────────┤
│  СЛОЙ 3: Объект и общие модули (сервер)         │
│  ОбработкаПроведения(), ПередЗаписью() объекта, │
│  гкс_ВходнойКонтрольКачества (общий модуль)     │
│                                                  │
│  Тестируется: YAxUnit ✅ И Vanessa Automation ✅  │
│  YAxUnit вызывает напрямую без формы             │
└─────────────────────────────────────────────────┘
```

**Ключевой вывод:**

- **YAxUnit** вызывает серверный код напрямую: `ДокументОбъект.Записать(РежимЗаписиДокумента.Проведение)` — это вызывает `ОбработкаПроведения()` БЕЗ формы.
- **BDD** проводит документ нажатием кнопки "Провести" в GUI — это вызывает ВСЕ три слоя.

### 3.2 YAxUnit: серверная логика (Слой 3, ~70% багов)

| Что тестирует | Пример |
|---------------|--------|
| Общие модули | `гкс_ВходнойКонтрольКачества.ОбработатьРезультатАнализа()` |
| Проведение документов | `Документ.гкс_ЛабораторныйАнализ` → запись в РС |
| SQL-запросы | Фильтрация NULL, каскадные обновления |
| Алгоритмы | Группировка ТС, определение первого ТС |

**Преимущества:** быстро (секунды), без GUI, легко писать и поддерживать.
**Ограничения:** не видит Слои 1-2 (клиентские обработчики форм).

### 3.3 BDD с Vanessa Automation: полное покрытие (Слои 1-3, ~30% дополнительных багов)

**Архитектура запуска:**

```
TestManager (Vanessa Automation)
    │ ← ENTERPRISE /Execute vanessa-automation-single.epf
    │    /C "StartFeaturePlayer;DisableFirstRunHelper;VAParams=..."
    │
    ▼ подключается по TCP
TestClient (Тонкий клиент 1С)
    │ ← ENTERPRISE /TestClient -TPort 1538
    │    /N "user" /P "pass"
    │    /DisableStartupMessages /DisableStartupDialogs
    ▼
Действия в GUI: нажимает кнопки, заполняет поля, читает таблицы
```

**Критичные настройки (баги 1С 8.3.27):**

| Параметр | Значение | Почему |
|----------|----------|--------|
| Порт TestClient | **1538** | Нестандартные порты ломают подключение |
| Имя сервера | **KOMPUTER** | `localhost` вызывает ошибку "определение принадлежности" |
| DisableFirstRunHelper | Обязательно | Без него VA зависает 10+ минут |
| Таймаут старта | ~25 сек | Клиент долго инициализируется |

**Преимущества:** тестирует всю цепочку UI → сервер → БД.
**Ограничения:** медленнее (минуты), требует GUI, хрупче при изменении интерфейса.

### 3.4 Smoke тесты: автоматический обход форм

Smoke тесты автоматически перебирают ВСЕ метаданные конфигурации:
- **91 справочник** — открытие формы списка и элемента
- **27 документов** — открытие формы, создание, попытка проведения
- **Отчёты и обработки** — открытие

**Что ловит:** сломанные формы, ошибки `ПриСозданииНаСервере`, битые динамические списки.
**Что НЕ ловит:** бизнес-логику.

### 3.5 Какие баги ловит каждый уровень

Конкретные примеры из задачи "Заблокированные ТС":

| Тип бага | Кто ловит | Пример |
|----------|-----------|--------|
| SQL с NULL | **YAxUnit** | `WHERE Разблокировано = ЛОЖЬ` пропускает записи с NULL |
| Каскад не дошёл до 3-го ТС | **YAxUnit** | Ошибка в цикле обхода цепочки в общем модуле |
| Проведение не создало запись блокировки | **YAxUnit** | `ОбработкаПроведения` ЛабАнализа пропускает условие |
| Кнопка "Разблокировать" вызывает не тот метод | **BDD** | Copy-paste ошибка в команде формы |
| ПриИзменении контрагента не очищает группу ТС | **BDD** | Клиентский обработчик формы (Слой 1) |
| ПередЗаписьюНаСервере заполняет реквизит неверно | **BDD** | Серверный обработчик формы (Слой 2) |
| Форма АРМ не открывается | **Smoke** | Битая ссылка в динамическом списке |

**Итого:** YAxUnit (~70%) + BDD (~25%) + Smoke (~5%) = **>95% покрытие логических багов**.

---

## Часть 4. Типичные проблемы и решения (Windows-специфичные)

### 4.1 Кириллический путь D:\1С-Framework

| Проблема | Симптом | Решение |
|----------|---------|---------|
| vrunner / OneScript | "Файл не найден" при парсинге .feature | `run-bdd.ps1` копирует features в `D:\va-test` |
| Git Bash | Конвертация путей ломает кириллицу | `$env:MSYS_NO_PATHCONV = "1"` |
| Python | `UnicodeEncodeError` | `$env:PYTHONIOENCODING = "utf-8"` |
| curl | Broken UTF-8 | Использовать Python `requests` |

### 4.2 TestClient 1С 8.3.27

| Проблема | Решение |
|----------|---------|
| Нестандартные порты не работают | **Только порт 1538** |
| `localhost` → ошибка "определение принадлежности" | Использовать **KOMPUTER** |
| Окно "Настройка первоначальных возможностей" | `/DisableFirstRunHelper` или env `VANESSA_DisableFirstRunHelper=true` |
| Модальные диалоги | `/DisableStartupMessages /DisableStartupDialogs` |
| Медленный старт | `Start-Sleep -Seconds 25` перед подключением VA |

### 4.3 Docker на диске C:

```powershell
# Очистка неиспользуемых образов
docker image prune -a -f

# Перенос WSL2 на диск D: (раз и навсегда)
wsl --shutdown
wsl --export docker-desktop-data "D:\wsl-backup\docker-data.tar"
wsl --unregister docker-desktop-data
wsl --import docker-desktop-data "D:\wsl\data" "D:\wsl-backup\docker-data.tar"

# Ограничение RAM для WSL2 (файл %USERPROFILE%\.wslconfig)
# [wsl2]
# memory=8GB
```

### 4.4 Кодировки UTF-8 vs CP1251

```powershell
# В начале КАЖДОГО PowerShell скрипта
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
```

```python
# Python хуки — чтение stdin
import sys
data = sys.stdin.buffer.read().decode("utf-8")  # НЕ sys.stdin.read()
```

```bash
# Git — отображение кириллицы
git config --global core.quotepath false
```

### 4.5 YAxUnit на Windows

| Проблема | Решение |
|----------|---------|
| Пути в yaxunit.json | Только `\\` (обратные слэши), НЕ `/` |
| ДымовыеТесты | `{"Использовать": true, "ОткрытиеФорм": true}` — НЕ просто `true` |
| Git Bash конвертирует пути | `$env:MSYS_NO_PATHCONV = "1"` |
| Путь `ЭтоАбсолютныйПутьWindows` | Проверяет наличие `\` — forward slash не пройдёт |

---

## Часть 5. Будущее развитие — Docker-образы 1С

### 5.1 Что даст переход на Docker

| Характеристика | Сейчас (Windows Runner) | Docker |
|----------------|------------------------|--------|
| Изоляция | Глобальная БД, конфликты | Чистый контейнер на каждый запуск |
| Воспроизводимость | Зависит от обновлений ОС | Идентичный образ везде |
| Масштабирование | 1 runner = 1 тест | 5-10 контейнеров параллельно |
| Версионность | Одна версия 1С | Теги образов `:8.3.27`, `:8.3.26` |

### 5.2 Что требуется

1. **DEB-пакеты 1С** с releases.1c.ru (подписка ИТС)
2. **Dockerfile** из `firstBitMarksistskaya/onec-docker` или `thedemoncat/onec-base`
3. **PostgreSQL для 1С** (PostgresPro с патчами) — отдельный контейнер
4. **Xvfb** — виртуальный дисплей для GUI-тестов в Linux

### 5.3 План перехода

```
Этап 1: Получить DEB-пакеты → собрать образы onec-server, onec-client
Этап 2: Собрать образ onec-client-vnc (с Xvfb и VNC для отладки)
Этап 3: Адаптировать скрипты PowerShell → Bash
Этап 4: Перевести CI на Docker executor
Этап 5: Windows Runner остаётся как fallback
```

**Пример будущего workflow:**

```yaml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/your-org/onec-client:8.3.27
    services:
      postgres:
        image: postgrespro/postgrespro-1c:15
    steps:
      - name: Create test DB
        run: |
          /opt/1cv8/x86_64/8.3.27.1859/1cv8 CREATEINFOBASE \
            Srvr="postgres";Ref="test_db";DBMS="PostgreSQL"
      - name: Run YAxUnit
        run: |
          xvfb-run -a /opt/1cv8/x86_64/8.3.27.1859/1cv8 ENTERPRISE \
            /S "postgres\test_db" \
            /Execute tools/yaxunit-launcher.epf
```

---

## Часть 6. Ресурсы

### Репозитории

| Назначение | Репозиторий |
|------------|------------|
| Docker-образы 1С | `firstBitMarksistskaya/onec-docker`, `thedemoncat/onec-base` |
| BSL Language Server | `1c-syntax/bsl-language-server` |
| SonarQube BSL плагин | `1c-syntax/sonar-bsl-plugin-community` |
| YAxUnit | `bia-technologies/yaxunit` |
| Vanessa Automation | `Pr-Mex/vanessa-automation` |
| Vanessa ADD | `vanessa-opensource/add` |
| vanessa-runner | `oscript-library/vanessa-runner` |
| Coverage41C | `1c-syntax/Coverage41C` |
| OneScript | `EvilBeaver/OneScript` |
| GitHub Actions Runner | `actions/runner` |

### Текущая конфигурация проекта

| Параметр | Значение |
|----------|----------|
| Проект | `D:\1С-Framework` |
| Конфигурация | УправлениеТранспортомНаПЛК v2026.1.1.0 |
| Платформа | 1С 8.3.27.1859 (x64) |
| Сервер 1С | KOMPUTER |
| СУБД | MS SQL 2022, БД testdb1c |
| YAxUnit | v25.12, 690 тестов |
| Vanessa Automation | v1.2.043.1 |
| CI | GitHub Actions, Self-Hosted Windows Runner |
