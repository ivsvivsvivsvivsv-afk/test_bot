# Admin API smoke checks for bot backend.
# Usage:
#   .\deploy\smoke_admin_api.ps1
#   .\deploy\smoke_admin_api.ps1 -BaseUrl https://bot.neurounit.fun -AdminSecret <secret>

param(
    [string]$BaseUrl = "",
    [string]$AdminSecret = "",
    [int]$Retries = 3
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    $BaseUrl = $env:BOT_API_URL
}
if ([string]::IsNullOrWhiteSpace($AdminSecret)) {
    $AdminSecret = $env:ADMIN_API_SECRET
}
if ([string]::IsNullOrWhiteSpace($BaseUrl)) {
    throw "[FAIL] BaseUrl is required. Pass -BaseUrl or set BOT_API_URL."
}
if ([string]::IsNullOrWhiteSpace($AdminSecret)) {
    throw "[FAIL] AdminSecret is required. Pass -AdminSecret or set ADMIN_API_SECRET."
}

function Invoke-WithRetries {
    param(
        [string]$Name,
        [scriptblock]$Call
    )

    $lastError = $null
    for ($i = 1; $i -le $Retries; $i++) {
        try {
            $result = & $Call
            Write-Host "[OK]   $Name (attempt $i/$Retries)"
            return $result
        } catch {
            $lastError = $_
            Write-Host "[WARN] $Name failed (attempt $i/$Retries): $($_.Exception.Message)"
            Start-Sleep -Seconds 1
        }
    }
    throw "[FAIL] $Name failed after $Retries retries. Last error: $($lastError.Exception.Message)"
}

$headers = @{ "X-Admin-Secret" = $AdminSecret }

Write-Host "[STEP] GET /api/admin/stats"
$stats = Invoke-WithRetries "GET admin stats" {
    Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/admin/stats" -Headers $headers -TimeoutSec 10
}
$stats | ConvertTo-Json -Compress

Write-Host "[STEP] GET /api/admin/leads?limit=5"
$leads = Invoke-WithRetries "GET admin leads" {
    Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/admin/leads?limit=5" -Headers $headers -TimeoutSec 10
}
if (-not $leads.ok) {
    throw "[FAIL] /api/admin/leads returned ok=false"
}

Write-Host "[STEP] GET /api/admin/leads?client_type=web&limit=5"
$leadsWeb = Invoke-WithRetries "GET admin leads filtered by client_type" {
    Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/admin/leads?client_type=web&limit=5" -Headers $headers -TimeoutSec 10
}
if (-not $leadsWeb.filters) {
    throw "[FAIL] /api/admin/leads response has no filters block"
}
if ($leadsWeb.filters.client_type -ne "web") {
    throw "[FAIL] /api/admin/leads did not echo client_type=web filter"
}

Write-Host "[STEP] GET /api/admin/funnel?days=7&client_type=telegram"
$funnel = Invoke-WithRetries "GET admin funnel filtered by client_type" {
    Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/admin/funnel?days=7&client_type=telegram" -Headers $headers -TimeoutSec 10
}
if (-not $funnel.ok) {
    throw "[FAIL] /api/admin/funnel returned ok=false"
}
if (-not $funnel.filters) {
    throw "[FAIL] /api/admin/funnel response has no filters block"
}
if ($funnel.filters.client_type -ne "telegram") {
    throw "[FAIL] /api/admin/funnel did not echo client_type=telegram filter"
}

Write-Host "[STEP] GET /api/admin/bundles"
$bundles = Invoke-WithRetries "GET admin bundles" {
    Invoke-RestMethod -Method GET -Uri "$BaseUrl/api/admin/bundles" -Headers $headers -TimeoutSec 10
}
if (-not $bundles.ok -or -not $bundles.bundles) {
    throw "[FAIL] /api/admin/bundles returned ok=false or no bundles"
}
Write-Host "       bundles: $($bundles.bundles -join ', ')"

Write-Host "[PASS] Admin API smoke checks passed"

