# Локальный прогон SonarQube-анализа BSL (ADR-021). Зеркалит CI-шаг bsl-analysis.
# Требует: поднятый SonarQube CB 26.6 (docker-compose.sonarqube.yml) на :9000 + $env:SONAR_TOKEN.
# Verified 2026-06-15: scanner-cli + server-JRE-provisioning (сенсор bsl = JDK 21).
# -LogFile <path>: писать UTF-8-лог сканера в файл (P1.2, native-safe; внешний *>&1 НЕ нужен).
# -Project <key|all>: split-режим — скан per-project по реестру sonar_projects.py (P3.A wiring;
#   иначе legacy mono. Активен также при $env:SONAR_SPLIT_PROJECTS=1).
param([string]$LogFile = "", [string]$Project = "")
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

# 3. динамический список источников (скоуп = живые конфигурации: ИБ+SVETLY+MFM; ADR-048/A7)
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
# ИБ+SVETLY+MFM, ~33k+ символов) исчерпывают дефолтную кучу (~1 ГБ) → плагин communitybsl
# валит каждую диагностику ("Diagnostic computation error") и движок падает ДО старта
# (прошлый "config-wide краш" = ранний OOM, не дефект кода). -Xmx6g верифицирован 2026-06-30
# (полный прогон 3 конфигов → EXECUTION SUCCESS, ANALYSIS SUCCESSFUL). Tunable: задать
# $env:SONAR_SCANNER_JAVA_OPTS / SONAR_SCANNER_OPTS заранее (напр. меньше на CI с малой RAM).
if (-not $env:SONAR_SCANNER_JAVA_OPTS) { $env:SONAR_SCANNER_JAVA_OPTS = "-Xmx6g" }  # JVM движка (bsl-сенсор)
if (-not $env:SONAR_SCANNER_OPTS) { $env:SONAR_SCANNER_OPTS = "-Xmx6g" }            # JVM bootstrap CLI

# P1.1 (I4): CE-handoff — дождаться финализации Compute Engine по .scannerwork/report-task.txt
# (verify после скана никогда не увидит in-progress). Осознанно НЕ sonar.qualitygate.wait=true
# (связал бы exit сканера с QG, у нас QG сознательно soft — R6). FAILED → exit 1.
function Wait-CeHandoff {
    param([string]$BaseDir = $ProjectRoot)  # split: .scannerwork в корне КОНФИГА (projectBaseDir), не репо
    $reportTask = Join-Path $BaseDir ".scannerwork\report-task.txt"
    if (-not (Test-Path $reportTask)) { return }
    $ceTaskId = (((Get-Content $reportTask) | Where-Object { $_ -like "ceTaskId=*" } | Select-Object -First 1) -replace "^ceTaskId=", "").Trim()
    if (-not $ceTaskId) { return }
    $ceAuth = @{ Authorization = "Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$($env:SONAR_TOKEN):")) }
    $deadline = (Get-Date).AddMinutes(10)
    $ceStatus = "PENDING"; $ce = $null
    Write-Host "  CE task $ceTaskId — жду финализации анализа..."
    while ((Get-Date) -lt $deadline) {
        try {
            $ce = Invoke-RestMethod -Uri "$Host_/api/ce/task?id=$ceTaskId" -Headers $ceAuth -TimeoutSec 15
            $ceStatus = $ce.task.status
        }
        catch { $ceStatus = "PENDING" }  # транзиент (индексация/404) → продолжаем до дедлайна
        if ($ceStatus -in @("SUCCESS", "FAILED", "CANCELED")) { break }
        Start-Sleep -Seconds 5
    }
    if ($ceStatus -eq "SUCCESS") {
        Write-Host "  CE analysis SUCCESS (analysisId=$($ce.task.analysisId))" -ForegroundColor Green
    }
    elseif ($ceStatus -eq "FAILED") {
        Write-Host "  CE analysis FAILED — анализ не загружен на сервер" -ForegroundColor Red; exit 1
    }
    else {
        Write-Host "  CE analysis статус=$ceStatus (таймаут/отменён) — verify может увидеть устаревший анализ" -ForegroundColor Yellow
    }
}

function Invoke-SonarScan {
    param([string[]]$ScanArgs, [string]$Label = "", [string]$BaseDir = $ProjectRoot)
    $lbl = if ($Label) { " [$Label]" } else { "" }
    if ($LogFile) {
        # P1.2 (I1+I2): свой UTF-8-лог. Локальный EAP=Continue — иначе stderr сенсора под EAP=Stop
        # роняет скрипт (NativeCommandError). -Append: в split проекты пишут в один лог по очереди.
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $java $ScanArgs *>&1 | Out-File -FilePath $LogFile -Encoding utf8 -Append
        $exit = $LASTEXITCODE
        $ErrorActionPreference = $prevEAP
        Write-Host "  scanner log$lbl -> $LogFile (UTF-8)"
    }
    else {
        & $java $ScanArgs
        $exit = $LASTEXITCODE
    }
    if ($exit -ne 0) { Write-Host "Sonar Scanner failed$lbl (exit $exit)!" -ForegroundColor Red; exit 1 }
    Wait-CeHandoff -BaseDir $BaseDir  # каждый проект пишет свой report-task.txt → handoff сразу после скана
}

# Скан: mono (legacy, default) или split (P3.A). ПОЛНЫЙ split = $env:SONAR_SPLIT_PROJECTS=1 —
# его читают И этот скрипт, И verify (sonar_projects.split_enabled). `-Project <key>` — точечный
# скан ОДНОГО проекта (verify без env останется mono → задай env для сквозного split).
# Аргументы массивом (array-expansion `& $java $arr`, НЕ splat @ — рвёт строки в PS 5.1).
if ($LogFile) { [System.IO.File]::WriteAllText($LogFile, "") }  # усечь лог на старте (split пишет -Append)
$splitOn = ((("$env:SONAR_SPLIT_PROJECTS").Trim()) -in @("1", "true", "yes", "on")) -or ($Project -ne "")
if ($splitOn) {
    $regJson = & $py "$ProjectRoot\scripts\sonar_projects.py" --list-json
    if ($LASTEXITCODE -ne 0 -or -not $regJson) {
        Write-Host "FATAL: sonar_projects.py --list-json не вернул реестр" -ForegroundColor Red; exit 2
    }
    # PS 5.1: ConvertFrom-Json отдаёт JSON-массив как ОДИН Object[] → НЕ оборачивать @()
    # (иначе $registry = [Object[3]], $proj в foreach = весь массив → $proj.root = Object[]).
    $registry = $regJson | ConvertFrom-Json
    if ($Project -and $Project -ne "all") {
        $registry = @($registry | Where-Object { $_.key -eq $Project })
        if (-not $registry) { Write-Host "FATAL: проект '$Project' не в реестре" -ForegroundColor Red; exit 2 }
    }
    Write-Host "  SPLIT-режим: проектов = $($registry.Count)" -ForegroundColor Cyan
    foreach ($proj in $registry) {
        $baseDir = Join-Path $ProjectRoot $proj.root
        Write-Host "`n  -> скан проекта $($proj.key) ($($proj.root))" -ForegroundColor Cyan
        # projectBaseDir = корень конфигурации (один git work-tree → SCM blame оживает; ADR-048).
        # sonar-project.properties НЕ читается вне корня репо → exclusions/encoding явно (зеркало properties).
        $pArgs = @(
            "-jar", $cli,
            "-Dsonar.host.url=$Host_",
            "-Dsonar.token=$env:SONAR_TOKEN",
            "-Dsonar.projectKey=$($proj.key)",
            "-Dsonar.projectName=$($proj.name)",
            "-Dsonar.projectBaseDir=$baseDir",
            "-Dsonar.sources=.",
            "-Dsonar.exclusions=**/docs/**,**/*.md,**/*.xml,**/*.json,**/*.cf,**/*.cfe,**/*.pkl",
            "-Dsonar.sourceEncoding=UTF-8"
        )
        Invoke-SonarScan -ScanArgs $pArgs -Label $proj.key -BaseDir $baseDir
    }
    Write-Host "`nDone (SPLIT)! Дашборды per-project: $Host_/projects" -ForegroundColor Green
}
else {
    # mono (legacy): монопроект upravlenie-transportom-plk, projectBaseDir=репо, sources=comma-list
    $scanArgs = @(
        "-jar", $cli,
        "-Dsonar.host.url=$Host_",
        "-Dsonar.token=$env:SONAR_TOKEN",
        "-Dsonar.projectBaseDir=$ProjectRoot",
        "-Dsonar.sources=$sources"
    )
    Invoke-SonarScan -ScanArgs $scanArgs

    # R6 (ADR-034): Quality Gate gate — Clean-as-You-Code (условия new-code; легаси не блокирует).
    # Hard под $env:SONAR_QG_HARD=1 (валит билд на QG=ERROR), иначе soft (только warn).
    $qgArgs = if ($env:SONAR_QG_HARD -eq "1") { @() } else { @("--soft") }
    # Нативной команде передаём $qgArgs (array-expansion), НЕ @qgArgs: splat-оператор в PS 5.1
    # рвёт строку "--soft" на отдельные символы ("- - s o f t" → argparse: unrecognized arguments).
    & $py "$ProjectRoot\scripts\sonar_quality_gate_check.py" --host $Host_ $qgArgs
    if ($LASTEXITCODE -ne 0) { Write-Host "Quality Gate FAILED (hard, new-code)" -ForegroundColor Red; exit $LASTEXITCODE }

    Write-Host "`nDone! Dashboard: $Host_/dashboard?id=upravlenie-transportom-plk" -ForegroundColor Green
}
