# Setup Z.AI GLM for Claude Code
# Usage: .\setup-zai.ps1 -ApiKey "YOUR_API_KEY" [-Model "glm-5"]

param(
    [Parameter(Mandatory=$true)]
    [string]$ApiKey,

    [Parameter(Mandatory=$false)]
    [ValidateSet("glm-5.1", "glm-5-turbo", "glm-5", "glm-4.7", "glm-4.7-air")]
    [string]$Model = "glm-5.1"
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=== Z.AI GLM Setup ===" -ForegroundColor Cyan
Write-Host ""

# Validate API Key
if ($ApiKey.Length -lt 10) {
    Write-Host "[ERROR] API Key too short" -ForegroundColor Red
    Write-Host "Get your key at: https://z.ai/manage-apikey/apikey-list"
    exit 1
}

# Paths
$claudeConfigDir = "$env:USERPROFILE\.claude"
$settingsFile = "$claudeConfigDir\settings.json"
$zaiConfigFile = "$PSScriptRoot\zai-config.json"

# Create .claude directory
if (-not (Test-Path $claudeConfigDir)) {
    New-Item -ItemType Directory -Path $claudeConfigDir -Force | Out-Null
    Write-Host "[OK] Created: $claudeConfigDir" -ForegroundColor Green
}

# Model mapping
$haikuModel = "glm-4.5-air"
$sonnetModel = $Model
$opusModel = $Model

# Create Z.AI config
$zaiConfig = @{
    ANTHROPIC_BASE_URL = "https://api.z.ai/api/anthropic"
    ANTHROPIC_AUTH_TOKEN = $ApiKey
    ANTHROPIC_DEFAULT_HAIKU_MODEL = $haikuModel
    ANTHROPIC_DEFAULT_SONNET_MODEL = $sonnetModel
    ANTHROPIC_DEFAULT_OPUS_MODEL = $opusModel
}

# Save Z.AI config
$zaiConfig | ConvertTo-Json | Out-File $zaiConfigFile -Encoding utf8
Write-Host "[OK] Z.AI config saved: $zaiConfigFile" -ForegroundColor Green

# Load or create settings
if (Test-Path $settingsFile) {
    $settings = Get-Content $settingsFile -Raw | ConvertFrom-Json -AsHashtable
} else {
    $settings = @{}
}

# Ensure env section
if (-not $settings.ContainsKey("env")) {
    $settings["env"] = @{}
}

# Apply Z.AI config to settings
foreach ($key in $zaiConfig.Keys) {
    $settings.env[$key] = $zaiConfig[$key]
    Set-Item "Env:$key" $zaiConfig[$key]
}

# Save settings
$settings | ConvertTo-Json -Depth 10 | Out-File $settingsFile -Encoding utf8
Write-Host "[OK] Settings updated: $settingsFile" -ForegroundColor Green

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  API:    https://api.z.ai/api/anthropic"
Write-Host "  Haiku:  $haikuModel"
Write-Host "  Sonnet: $sonnetModel"
Write-Host "  Opus:   $opusModel"
Write-Host ""
Write-Host "Commands:" -ForegroundColor Yellow
Write-Host "  Run Claude:          claude"
Write-Host "  Switch to Z.AI:      .\switch-claude-backend.ps1 -Backend zai"
Write-Host "  Switch to Anthropic: .\switch-claude-backend.ps1 -Backend anthropic"
Write-Host ""
