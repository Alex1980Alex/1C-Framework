#!/usr/bin/env pwsh
# autoresearch.ps1 — AutoResearch: автономный цикл улучшений через Claude Code CLI
#
# Использование:
#   .\scripts\autoresearch.ps1 -Domain skills -MaxIterations 15
#   .\scripts\autoresearch.ps1 -Domain python-quality -Target 0
#   .\scripts\autoresearch.ps1 -Domain skills -MaxIterations 20 -Target 0.85

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("skills", "skill-health", "python-quality", "bsl", "docs", "hooks", "security", "tests")]
    [string]$Domain,

    [int]$MaxIterations = 10,
    [string]$Target
)

# Настройка UTF-8
chcp 65001 > $null 2>&1
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Корень проекта
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Get-Item "$scriptDir\..").FullName
Set-Location $projectRoot

if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path "data" > $null }

$jsonlPath = "data\autoresearch.jsonl"
$mdPath = "data\autoresearch.md"
$logPath = "data\autoresearch_${Domain}_$(Get-Date -Format 'yyyyMMdd').log"

# Рецепты доменов
$recipes = @{
    "skills" = @{
        Verify = "python scripts/eval-skill-router.py"
        Metric = "F1 score skill router"
        Prompt = "Улучши description ОДНОГО скилла в .claude/skills/ для повышения F1 eval-skill-router.py. Используй pushy стиль с триггерами и негативными маркерами. Измени ТОЛЬКО description в YAML frontmatter. Один скилл за итерацию."
    }
    "skill-health" = @{
        Verify = "python scripts/eval-skill-router.py"
        Metric = "F1(All) skill router + health report"
        Prompt = "Запусти python scripts/skill-health-analyzer.py --no-eval чтобы найти проблемный скилл. Если HIGH WASTE — перепиши description (сузить триггеры). Если ROUTER MISS — добавь keywords в skill-router-config.json. Если NEVER USED — перемести в .claude/skills/_archived/. Один скилл за итерацию. Используй pushy стиль."
    }
    "python-quality" = @{
        Verify = "ruff check src/ --output-format json"
        Metric = "ruff errors count (lower is better)"
        Prompt = "Исправь ОДНУ категорию ошибок ruff в src/. Запусти ruff check src/ чтобы найти самую частую. Исправь ВСЕ файлы с этой ошибкой."
    }
    "bsl" = @{
        Verify = "echo METRIC: 0"
        Metric = "bsl_analyze errors"
        Prompt = "Проанализируй BSL код в src/bsl/ через bsl_analyze. Исправь ОДНУ категорию ошибок."
    }
    "docs" = @{
        Verify = "echo METRIC: 0"
        Metric = "audit-docs coverage score"
        Prompt = "Допиши документацию к ОДНОМУ модулю в src/pdf_framework/ используя скилл audit-docs."
    }
    "hooks" = @{
        Verify = "python scripts/eval-hooks.py"
        Metric = "eval-hooks accuracy"
        Prompt = "Улучши ОДИН хук в .claude/hooks/ для повышения accuracy eval-hooks.py."
    }
    "security" = @{
        Verify = "bandit -r src/ -f json"
        Metric = "bandit findings count (lower is better)"
        Prompt = "Исправь ОДНУ уязвимость из bandit -r src/. Не меняй логику — только безопасность."
    }
    "tests" = @{
        Verify = "pytest --cov=src -q"
        Metric = "pytest coverage %"
        Prompt = "Напиши тесты для ОДНОГО модуля в src/pdf_framework/ который ещё не покрыт тестами."
    }
}

$recipe = $recipes[$Domain]

# Состояние сессии
$bestMetric = $null
$plateauCount = 0
$startIter = 0

if (Test-Path $mdPath) {
    $md = Get-Content $mdPath -Raw -Encoding UTF8
    if ($md -match "Domain: $Domain") {
        if ($md -match 'BestMetric:\s*([\d.]+)') { $bestMetric = [double]$Matches[1] }
        if ($md -match 'Iteration:\s*(\d+)') { $startIter = [int]$Matches[1] }
        if ($md -match 'Plateau:\s*(\d+)') { $plateauCount = [int]$Matches[1] }
    }
}

Write-Host "=== AutoResearch: $Domain ===" -ForegroundColor Cyan
Write-Host "Max iterations: $MaxIterations | Target: $(if($Target){$Target}else{'none'})"
Write-Host "Verify: $($recipe.Verify)"
Write-Host ""

$lastIter = $startIter
for ($i = $startIter + 1; $i -le $MaxIterations; $i++) {
    $lastIter = $i
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
    Write-Host "`n=== Iteration $i / $MaxIterations [$ts] ===" -ForegroundColor Cyan

    # Единый вызов claude -p: EXECUTE + REVIEW в одном промпте
    $prompt = @"
AutoResearch итерация $i из $MaxIterations. Домен: $Domain.

ЗАДАЧА: $($recipe.Prompt)

ПРОТОКОЛ:
1. Проверь git log --oneline -3 для контекста предыдущих изменений.
2. Внеси ОДНО изменение.
3. git add и git commit -m "[AR] $Domain iter ${i}: описание"
4. Запусти verify: $($recipe.Verify)
5. Выведи результат СТРОГО в формате: METRIC: число (например METRIC: 0.7189). Без таблиц, без F1:, только METRIC: число.
6. Сравни с предыдущим значением и выведи VERDICT: KEEP или VERDICT: REVERT
7. Если REVERT — выполни git revert HEAD --no-edit
8. Если задача полностью завершена по ВСЕМ критериям: AUTORESEARCH_DONE
"@

    Write-Host "  Запуск Claude..." -ForegroundColor Yellow
    $env:RALPH_ENABLED = "1"
    $output = claude -p $prompt --dangerously-skip-permissions 2>&1 | Out-String
    $output | Add-Content $logPath -Encoding UTF8
    Write-Host $output

    # Маркер завершения
    if ($output -match "AUTORESEARCH_DONE") {
        Write-Host "`n  Завершено: AUTORESEARCH_DONE" -ForegroundColor Green
        break
    }

    # Парсинг метрики и вердикта
    $metric = $null
    # Парсинг метрики: METRIC: число, или F1: число, или F1 = число
    if ($output -match "METRIC:\s*([\d.]+)") { $metric = [double]$Matches[1] }
    elseif ($output -match "F1[\s:=]+([\d.]+)") { $metric = [double]$Matches[1] }
    $delta = if ($bestMetric -ne $null -and $metric -ne $null) { $metric - $bestMetric } else { 0 }

    $action = "unknown"
    if ($output -match "VERDICT:\s*KEEP") {
        $action = "keep"
        if ($metric -ne $null -and ($bestMetric -eq $null -or $metric -gt $bestMetric)) {
            $bestMetric = $metric; $plateauCount = 0
        } else { $plateauCount++ }
        Write-Host "  KEEP: metric=$metric delta=$([math]::Round($delta, 4))" -ForegroundColor Green
    }
    elseif ($output -match "VERDICT:\s*REVERT") {
        $action = "revert"; $plateauCount++
        Write-Host "  REVERT: metric=$metric delta=$([math]::Round($delta, 4))" -ForegroundColor Yellow
    }
    else { $plateauCount++ }

    # JSONL лог
    $entry = @{ ts=$ts; iter=$i; domain=$Domain; metric=$metric; delta=[math]::Round($delta,4); action=$action }
    ($entry | ConvertTo-Json -Compress) | Add-Content $jsonlPath -Encoding UTF8

    # Сохранение состояния
    @"
# AutoResearch Session
Domain: $Domain
Iteration: $i
BestMetric: $bestMetric
Plateau: $plateauCount
Target: $Target
Updated: $ts
"@ | Set-Content $mdPath -Encoding UTF8

    # Цель достигнута?
    if ($Target -and $bestMetric -ne $null -and $bestMetric -ge [double]$Target) {
        Write-Host "`nЦель достигнута: $bestMetric >= $Target" -ForegroundColor Green; break
    }

    # Плато?
    if ($plateauCount -ge 5) {
        Write-Host "`nПлато: 5 итераций без улучшений. Остановка." -ForegroundColor Yellow; break
    }

    Start-Sleep -Seconds 2
}

Write-Host "`n=== AutoResearch завершён ===" -ForegroundColor Cyan
Write-Host "Домен: $Domain | Итераций: $lastIter | Лучшая метрика: $bestMetric"
