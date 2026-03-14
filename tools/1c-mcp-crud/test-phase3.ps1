# Phase 3: Test Script
# Tests all Phase 3 components: IIS, HTTP service, Python proxy, OData
# Usage: powershell -ExecutionPolicy Bypass -File test-phase3.ps1

param(
    [string]$BaseUrl = "http://localhost/TestDB",
    [string]$User = "a.terletskiy@sodru.com",
    [string]$Pass = "Alex80Alex",
    [switch]$TestOData,
    [switch]$TestProxy
)

$ErrorActionPreference = "Continue"

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [hashtable]$Headers = @{},
        [string]$ExpectedContent = ""
    )

    Write-Host "  Testing $Name..." -NoNewline
    try {
        $cred = [System.Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes("${User}:${Pass}"))
        $h = @{ "Authorization" = "Basic $cred" }
        foreach ($k in $Headers.Keys) { $h[$k] = $Headers[$k] }

        $response = Invoke-WebRequest -Uri $Url -Headers $h -UseBasicParsing -TimeoutSec 15
        $body = $response.Content

        if ($ExpectedContent -and $body -notmatch $ExpectedContent) {
            Write-Host " WARN (HTTP $($response.StatusCode), unexpected body)" -ForegroundColor Yellow
            return $false
        }

        Write-Host " OK (HTTP $($response.StatusCode))" -ForegroundColor Green
        return $true
    }
    catch {
        $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { "N/A" }
        Write-Host " FAIL (HTTP $code - $($_.Exception.Message))" -ForegroundColor Red
        return $false
    }
}

Write-Host "=" * 60
Write-Host "  Phase 3: Integration Test" -ForegroundColor Cyan
Write-Host "=" * 60
Write-Host ""

$results = @{}

# Test 1: IIS running
Write-Host "[1] IIS Service" -ForegroundColor Cyan
$svc = Get-Service W3SVC -ErrorAction SilentlyContinue
if ($svc -and $svc.Status -eq "Running") {
    Write-Host "  IIS: Running" -ForegroundColor Green
    $results["IIS"] = $true
}
else {
    Write-Host "  IIS: Not running" -ForegroundColor Red
    $results["IIS"] = $false
}

# Test 2: Health endpoint
Write-Host "[2] MCP Health Endpoint" -ForegroundColor Cyan
$results["Health"] = Test-Endpoint "health" "$BaseUrl/hs/mcp/health" -ExpectedContent '"status"\s*:\s*"ok"'

# Test 3: MCP tools/list via JSON-RPC
Write-Host "[3] MCP Tools List (JSON-RPC)" -ForegroundColor Cyan
Write-Host "  Testing tools/list..." -NoNewline
try {
    $cred = [System.Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes("${User}:${Pass}"))
    $headers = @{
        "Authorization" = "Basic $cred"
        "Content-Type"  = "application/json"
    }
    $body = '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
    $response = Invoke-WebRequest -Uri "$BaseUrl/hs/mcp/rpc" -Headers $headers -Method POST -Body $body -UseBasicParsing -TimeoutSec 15
    $json = $response.Content | ConvertFrom-Json

    if ($json.result.tools) {
        $count = $json.result.tools.Count
        Write-Host " OK ($count tools found)" -ForegroundColor Green
        Write-Host "    Tools: $($json.result.tools.name -join ', ')" -ForegroundColor Gray
        $results["Tools"] = $true
    }
    else {
        Write-Host " WARN (no tools in response)" -ForegroundColor Yellow
        $results["Tools"] = $false
    }
}
catch {
    Write-Host " FAIL ($($_.Exception.Message))" -ForegroundColor Red
    $results["Tools"] = $false
}

# Test 4: MCP tool call (get metadata summary)
Write-Host "[4] MCP Tool Call (get_metadata_summary)" -ForegroundColor Cyan
Write-Host "  Testing tool call..." -NoNewline
try {
    $body = '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_metadata_summary","arguments":{}}}'
    $response = Invoke-WebRequest -Uri "$BaseUrl/hs/mcp/rpc" -Headers $headers -Method POST -Body $body -UseBasicParsing -TimeoutSec 30
    $json = $response.Content | ConvertFrom-Json

    if ($json.result -and -not $json.result.isError) {
        Write-Host " OK" -ForegroundColor Green
        $results["ToolCall"] = $true
    }
    else {
        Write-Host " WARN (tool returned error)" -ForegroundColor Yellow
        $results["ToolCall"] = $false
    }
}
catch {
    Write-Host " FAIL ($($_.Exception.Message))" -ForegroundColor Red
    $results["ToolCall"] = $false
}

# Test 5: OData (optional)
if ($TestOData) {
    Write-Host "[5] OData Endpoint" -ForegroundColor Cyan
    $results["OData"] = Test-Endpoint "OData" "$BaseUrl/odata/standard.odata/" -ExpectedContent "xml|json"
}

# Test 6: Python Proxy (optional)
if ($TestProxy) {
    Write-Host "[6] Python Proxy (stdio)" -ForegroundColor Cyan
    Write-Host "  Testing proxy startup..." -NoNewline
    $proxyDir = "D:\1C-Enterprise_Framework\src\external\1c_mcp"
    $python = "$proxyDir\venv\Scripts\python.exe"
    if (Test-Path $python) {
        Write-Host " Python found" -ForegroundColor Green
        $results["Proxy"] = $true
    }
    else {
        Write-Host " FAIL (python not found at $python)" -ForegroundColor Red
        $results["Proxy"] = $false
    }
}

# Summary
Write-Host ""
Write-Host "=" * 60
Write-Host "  Results" -ForegroundColor Cyan
Write-Host "=" * 60

$passed = 0
$failed = 0
foreach ($k in $results.Keys) {
    $status = if ($results[$k]) { "PASS"; $passed++ } else { "FAIL"; $failed++ }
    $color = if ($results[$k]) { "Green" } else { "Red" }
    Write-Host "  [$status] $k" -ForegroundColor $color
}

Write-Host ""
Write-Host "  Total: $passed passed, $failed failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Yellow" })

if ($failed -gt 0) {
    Write-Host ""
    Write-Host "  Troubleshooting:" -ForegroundColor Yellow
    if (-not $results["IIS"]) {
        Write-Host "    - Run setup-phase3-iis.ps1 as Administrator"
    }
    if ($results["IIS"] -and -not $results["Health"]) {
        Write-Host "    - Check: extension MCP_Server.cfe installed in TestDB?"
        Write-Host "    - Check: HTTP service mcp_APIBackend enabled?"
        Write-Host "    - Check: default.vrd at $PublishPath"
    }
}
