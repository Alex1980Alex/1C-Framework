# Switch Claude Code backend between Anthropic and Z.AI GLM
# Usage: .\switch-claude-backend.ps1 -Backend [anthropic|zai]

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("anthropic", "zai")]
    [string]$Backend
)

$ErrorActionPreference = "Stop"

# Paths
$claudeConfigDir = "$env:USERPROFILE\.claude"
$settingsFile = "$claudeConfigDir\settings.json"
$backupDir = "$claudeConfigDir\backups"
$zaiConfigFile = "$PSScriptRoot\zai-config.json"

Write-Host ""
Write-Host "=== Claude Backend Switcher ===" -ForegroundColor Cyan
Write-Host ""

# Create backup directory
if (-not (Test-Path $backupDir)) {
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

# Check if settings.json exists
if (-not (Test-Path $settingsFile)) {
    Write-Host "[ERROR] Settings file not found: $settingsFile" -ForegroundColor Red
    exit 1
}

# Read current settings
$settings = Get-Content $settingsFile -Raw | ConvertFrom-Json

# Backup current settings
$backupFile = "$backupDir\settings_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
Copy-Item $settingsFile $backupFile
Write-Host "[OK] Backup created: $backupFile" -ForegroundColor Green

# Z.AI environment keys to manage
$zaiKeys = @(
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL"
)

switch ($Backend) {
    "anthropic" {
        Write-Host "[INFO] Switching to Anthropic (original)..." -ForegroundColor Yellow

        # Save Z.AI config before removing
        if ($settings.env -and $settings.env.ANTHROPIC_BASE_URL) {
            $zaiConfig = @{}
            foreach ($key in $zaiKeys) {
                if ($settings.env.$key) {
                    $zaiConfig[$key] = $settings.env.$key
                }
            }
            $jsonContent = $zaiConfig | ConvertTo-Json
            [System.IO.File]::WriteAllText($zaiConfigFile, $jsonContent)
            Write-Host "[OK] Z.AI config saved to: $zaiConfigFile" -ForegroundColor Green
        }

        # Remove Z.AI keys from settings
        if ($settings.env) {
            foreach ($key in $zaiKeys) {
                if ($settings.env.$key) {
                    $settings.env.PSObject.Properties.Remove($key)
                }
            }
        }

        # Clear environment variables
        foreach ($key in $zaiKeys) {
            Remove-Item "Env:$key" -ErrorAction SilentlyContinue
        }

        Write-Host ""
        Write-Host "=== Switched to ANTHROPIC ===" -ForegroundColor Green
        Write-Host ""
        Write-Host "Claude Code will now use:" -ForegroundColor Cyan
        Write-Host "  - Original Anthropic API"
        Write-Host "  - Your Anthropic API key (from ANTHROPIC_API_KEY)"
        Write-Host "  - Models: Claude Haiku, Sonnet, Opus"
    }

    "zai" {
        Write-Host "[INFO] Switching to Z.AI GLM-5..." -ForegroundColor Yellow

        # Check if we have saved Z.AI config
        if (-not (Test-Path $zaiConfigFile)) {
            Write-Host "[ERROR] Z.AI config not found!" -ForegroundColor Red
            Write-Host ""
            Write-Host "Run setup first:" -ForegroundColor Yellow
            Write-Host "  .\setup-zai.ps1 -ApiKey 'YOUR_ZAI_API_KEY'"
            exit 1
        }

        # Load Z.AI config
        $zaiConfig = Get-Content $zaiConfigFile -Raw | ConvertFrom-Json

        # Ensure env section exists as PSCustomObject
        if (-not $settings.env) {
            $settings | Add-Member -NotePropertyName "env" -NotePropertyValue ([PSCustomObject]@{})
        }

        # Apply Z.AI config
        foreach ($key in $zaiConfig.PSObject.Properties.Name) {
            $value = $zaiConfig.$key
            $existingProp = $settings.env.PSObject.Properties[$key]
            if ($existingProp) {
                $settings.env.$key = $value
            } else {
                $settings.env | Add-Member -NotePropertyName $key -NotePropertyValue $value -Force
            }
            Set-Item "Env:$key" $value
        }

        # Get actual model names from config
        $opusModel = $zaiConfig.ANTHROPIC_DEFAULT_OPUS_MODEL
        $sonnetModel = $zaiConfig.ANTHROPIC_DEFAULT_SONNET_MODEL
        $haikuModel = $zaiConfig.ANTHROPIC_DEFAULT_HAIKU_MODEL

        Write-Host ""
        Write-Host "=============================================" -ForegroundColor Green
        Write-Host "   Switched to Z.AI GLM-5 (Zhipu AI)" -ForegroundColor Green
        Write-Host "=============================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Claude Code will now use Z.AI API as backend:" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  API Endpoint: https://api.z.ai/api/anthropic" -ForegroundColor White
        Write-Host ""
        Write-Host "  Model Mapping:" -ForegroundColor Yellow
        Write-Host "  +----------------+------------------+" -ForegroundColor DarkGray
        Write-Host "  | Claude Model   | Z.AI Model       |" -ForegroundColor DarkGray
        Write-Host "  +----------------+------------------+" -ForegroundColor DarkGray
        Write-Host "  | Opus           | $opusModel" -ForegroundColor White
        Write-Host "  | Sonnet         | $sonnetModel" -ForegroundColor White
        Write-Host "  | Haiku          | $haikuModel" -ForegroundColor White
        Write-Host "  +----------------+------------------+" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  GLM-5 = Zhipu AI latest model" -ForegroundColor DarkCyan
        Write-Host "  - Large context window" -ForegroundColor DarkGray
        Write-Host "  - High quality for coding tasks" -ForegroundColor DarkGray
    }
}

# Save updated settings (UTF-8 without BOM for Node.js compatibility)
$jsonContent = $settings | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($settingsFile, $jsonContent)
Write-Host "[OK] Settings updated: $settingsFile" -ForegroundColor Green

Write-Host ""
Write-Host "Now run: claude" -ForegroundColor Cyan
Write-Host ""
