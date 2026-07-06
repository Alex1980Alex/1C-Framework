# Локальный прогон SonarQube-анализа BSL (ADR-021). Зеркалит CI-шаг bsl-analysis.
# Требует: поднятый SonarQube CB 26.6 (docker-compose.sonarqube.yml) на :9000 + $env:SONAR_TOKEN.
# Verified 2026-06-15: scanner-cli + server-JRE-provisioning (сенсор bsl = JDK 21).
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# Auto-root: якорь = расположение скрипта (scripts/..) — cwd-НЕзависимо (P0.2 roadmap 260706:
# `git rev-parse --show-toplevel` из каталога сабмодуля возвращал корень САБМОДУЛЯ →
# .env/скрипты не находились → «SONAR_TOKEN не задан» → тихий exit 0 БЕЗ скана).
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not (Test-Path (Join-Path $ProjectRoot "scripts\sonar_sources.py"))) {
    Write-Host "FATAL: scripts/sonar_sources.py не найден от корня '$ProjectRoot'" -ForegroundColor Red
    exit 2
}

# .env (gitignored) -> $env:* для не-заданных ключей (env > .env). ADR-041 follow-up.
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
        $l = $line.Trim()
        if ($l -and -not $l.StartsWith('#') -and $l.Contains('=')) {
            $k, $v = $l -split '=', 2
            $k = $k.Trim(); $v = $v.Trim().Trim('"').Trim("'")
            if ($k -and $v -and -not [Environment]::GetEnvironmentVariable($k, 'Process')) { Set-Item "env:$k" $v }
        }
    }
}
$Host_ = if ($env:SONAR_HOST_URL) { $env:SONAR_HOST_URL } else { "http://localhost:9000" }

# 1. reachability-gate — нет сервера → чистый выход (не падаем)
try { $st = (Invoke-RestMethod -Uri "$Host_/api/system/status" -TimeoutSec 5).status } catch { $st = "DOWN" }
if ($st -ne "UP") {
    Write-Host "SCAN-SKIPPED (server down) — анализ НЕ выполнялся" -ForegroundColor Yellow
    Write-Host "SonarQube недоступен на $Host_ ($st). Подними: docker compose -f docker/docker-compose.sonarqube.yml up -d" -ForegroundColor Yellow
    exit 0
}

# venv-python для helper-скриптов (P1.4: голый `python` = риск Store-alias/чужого окружения)
$py = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

# 2. quality gate «1C BSL Way» (идемпотентно; G18)
Write-Host "`n[1/3] Quality gate setup..." -ForegroundColor Cyan
& $py "$ProjectRoot\scripts\sonar_setup_quality_gate.py" --host $Host_
if ($LASTEXITCODE -ne 0) { Write-Host "FATAL: QG setup failed (exit $LASTEXITCODE)" -ForegroundColor Red; exit 2 }

# 3. динамический список источников (скоуп = живые конфигурации: ИБ+SVETLY; ADR-048)
Write-Host "`n[2/3] Discover BSL sources..." -ForegroundColor Cyan
$sources = (& $py "$ProjectRoot\scripts\sonar_sources.py") -join ","
if ($LASTEXITCODE -ne 0 -or -not $sources) {
    Write-Host "FATAL: sonar_sources.py не вернул источники (exit $LASTEXITCODE) — скан отменён" -ForegroundColor Red
    exit 2
}
Write-Host "  sources: $sources"

# 4. scanner-cli + server-JRE-provisioning (bundled scanner-JRE = битый LFS-указатель)
Write-Host "`n[3/3] Sonar Scanner..." -ForegroundColor Cyan
if (-not $env:SONAR_TOKEN) {
    # P0.2: раньше exit 0 маскировал no-op под успех (тихий пропуск скана из-за cwd-бага)
    Write-Host "FATAL: SONAR_TOKEN не задан (`$env:SONAR_TOKEN = '<token>' или .env) — скан отменён" -ForegroundColor Red
    exit 2
}
$cli = "$ProjectRoot\tools\sonar-scanner-6.2.1.4610-windows-x64\lib\sonar-scanner-cli-6.2.1.4610.jar"
if (-not (Test-Path $cli)) { Write-Host "scanner-cli не найден: $cli" -ForegroundColor Red; exit 1 }
$java = (Get-ChildItem "C:\Program Files\1C\1CE\components\axiom-jdk-full-17*\bin\java.exe" -EA SilentlyContinue | Select-Object -First 1).FullName
if (-not $java) { $java = "java" }   # fallback: system java для CLI-bootstrap

# Куча JVM движка анализа. bsl-language-server-диагностики на больших конфигах (3 корня
# ИБ+SVETLY+260304, ~33k символов) исчерпывают дефолтную кучу (~1 ГБ) → плагин communitybsl
# валит каждую диагностику ("Diagnostic computation error") и движок падает ДО старта
# (прошлый "config-wide краш" = ранний OOM, не дефект кода). -Xmx6g верифицирован 2026-06-30
# (полный прогон 3 конфигов → EXECUTION SUCCESS, ANALYSIS SUCCESSFUL). Tunable: задать
# $env:SONAR_SCANNER_JAVA_OPTS / SONAR_SCANNER_OPTS заранее (напр. меньше на CI с малой RAM).
if (-not $env:SONAR_SCANNER_JAVA_OPTS) { $env:SONAR_SCANNER_JAVA_OPTS = "-Xmx6g" }  # JVM движка (bsl-сенсор)
if (-not $env:SONAR_SCANNER_OPTS) { $env:SONAR_SCANNER_OPTS = "-Xmx6g" }            # JVM bootstrap CLI

& $java -jar $cli `
    "-Dsonar.host.url=$Host_" `
    "-Dsonar.token=$env:SONAR_TOKEN" `
    "-Dsonar.projectBaseDir=$ProjectRoot" `
    "-Dsonar.sources=$sources"
if ($LASTEXITCODE -ne 0) { Write-Host "Sonar Scanner failed!" -ForegroundColor Red; exit 1 }

# R6 (ADR-034): Quality Gate gate — Clean-as-You-Code (условия new-code; легаси не блокирует).
# Hard под $env:SONAR_QG_HARD=1 (валит билд на QG=ERROR), иначе soft (только warn).
$qgArgs = if ($env:SONAR_QG_HARD -eq "1") { @() } else { @("--soft") }
# Нативной команде передаём $qgArgs (array-expansion), НЕ @qgArgs: splat-оператор в PS 5.1
# рвёт строку "--soft" на отдельные символы ("- - s o f t" → argparse: unrecognized arguments).
& $py "$ProjectRoot\scripts\sonar_quality_gate_check.py" --host $Host_ $qgArgs
if ($LASTEXITCODE -ne 0) { Write-Host "Quality Gate FAILED (hard, new-code)" -ForegroundColor Red; exit $LASTEXITCODE }

Write-Host "`nDone! Dashboard: $Host_/dashboard?id=upravlenie-transportom-plk" -ForegroundColor Green
