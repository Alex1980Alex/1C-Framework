# Локальный прогон SonarQube-анализа BSL (ADR-021). Зеркалит CI-шаг bsl-analysis.
# Требует: поднятый SonarQube CB 26.6 (docker-compose.sonarqube.yml) на :9000 + $env:SONAR_TOKEN.
# Verified 2026-06-15: scanner-cli + server-JRE-provisioning (сенсор bsl = JDK 21).
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# Auto-root (надёжнее хардкода; устраняет до-миграционный D:\1С-Framework)
$ProjectRoot = (git rev-parse --show-toplevel).Trim()
if (-not $ProjectRoot) { $ProjectRoot = "C:\1С-Framework" }
$Host_ = if ($env:SONAR_HOST_URL) { $env:SONAR_HOST_URL } else { "http://localhost:9000" }

# 1. reachability-gate — нет сервера → чистый выход (не падаем)
try { $st = (Invoke-RestMethod -Uri "$Host_/api/system/status" -TimeoutSec 5).status } catch { $st = "DOWN" }
if ($st -ne "UP") {
    Write-Host "SonarQube недоступен на $Host_ ($st). Подними: docker compose -f docker/docker-compose.sonarqube.yml up -d" -ForegroundColor Yellow
    exit 0
}

# 2. quality gate «1C BSL Way» (идемпотентно; G18)
Write-Host "`n[1/3] Quality gate setup..." -ForegroundColor Cyan
python "$ProjectRoot\scripts\sonar_setup_quality_gate.py" --host $Host_

# 3. динамический список источников (G19; растущие configuration/<JIRA> авто-подхватываются)
Write-Host "`n[2/3] Discover BSL sources..." -ForegroundColor Cyan
$sources = & python "$ProjectRoot\scripts\sonar_sources.py"
Write-Host "  sources: $sources"

# 4. scanner-cli + server-JRE-provisioning (bundled scanner-JRE = битый LFS-указатель)
Write-Host "`n[3/3] Sonar Scanner..." -ForegroundColor Cyan
if (-not $env:SONAR_TOKEN) {
    Write-Host "SONAR_TOKEN не задан. `$env:SONAR_TOKEN = '<token>'" -ForegroundColor Yellow
    exit 0
}
$cli = "$ProjectRoot\tools\sonar-scanner-6.2.1.4610-windows-x64\lib\sonar-scanner-cli-6.2.1.4610.jar"
if (-not (Test-Path $cli)) { Write-Host "scanner-cli не найден: $cli" -ForegroundColor Red; exit 1 }
$java = (Get-ChildItem "C:\Program Files\1C\1CE\components\axiom-jdk-full-17*\bin\java.exe" -EA SilentlyContinue | Select-Object -First 1).FullName
if (-not $java) { $java = "java" }   # fallback: system java для CLI-bootstrap

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
& "$ProjectRoot\.venv\Scripts\python.exe" "$ProjectRoot\scripts\sonar_quality_gate_check.py" --host $Host_ $qgArgs
if ($LASTEXITCODE -ne 0) { Write-Host "Quality Gate FAILED (hard, new-code)" -ForegroundColor Red; exit $LASTEXITCODE }

Write-Host "`nDone! Dashboard: $Host_/dashboard?id=upravlenie-transportom-plk" -ForegroundColor Green
