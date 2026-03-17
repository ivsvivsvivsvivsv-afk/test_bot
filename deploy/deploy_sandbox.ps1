# HYDRA BOT — Deploy sandbox via SSH (PowerShell)
# Usage: .\deploy\deploy_sandbox.ps1
# Requires: deploy/.deploy.env with DEPLOY_HOST, DEPLOY_USER, and DEPLOY_KEY or DEPLOY_PASSWORD

$ErrorActionPreference = "Stop"
$DeployEnvPath = Join-Path $PSScriptRoot ".deploy.env"

if (-not (Test-Path $DeployEnvPath)) {
    Write-Host "[FAIL] Create deploy/.deploy.env from .deploy.env.example and fill credentials" -ForegroundColor Red
    Write-Host "  cp deploy/.deploy.env.example deploy/.deploy.env" -ForegroundColor Yellow
    Write-Host "  nano deploy/.deploy.env  # add DEPLOY_KEY or DEPLOY_PASSWORD" -ForegroundColor Yellow
    exit 1
}

$envContent = Get-Content $DeployEnvPath -Raw
foreach ($line in $envContent -split "`n") {
    if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+)$' -and $line -notmatch '^\s*#') {
        $name = $matches[1]
        $val = $matches[2].Trim()
        if ($val -and $val -ne '') { [Environment]::SetEnvironmentVariable($name, $val, "Process") }
    }
}

$host_addr = $env:DEPLOY_HOST
$user = $env:DEPLOY_USER
$key = $env:DEPLOY_KEY
$password = $env:DEPLOY_PASSWORD
$hostKey = $env:DEPLOY_HOSTKEY

if (-not $host_addr -or -not $user) {
    Write-Host "[FAIL] DEPLOY_HOST and DEPLOY_USER required in .deploy.env" -ForegroundColor Red
    exit 1
}

$sshTarget = "${user}@${host_addr}"

# Remote deploy script (runs on server)
$remoteScript = @'
set -e
SANDBOX_DIR="/opt/hydra_bot_sandbox"
REPO="https://github.com/ivsvivsvivsvivsv-afk/test_bot.git"

if [ -d "$SANDBOX_DIR/.git" ]; then
  cd "$SANDBOX_DIR" && git fetch --all --prune && git reset --hard origin/main && git clean -fd
else
  sudo rm -rf "$SANDBOX_DIR" 2>/dev/null || true
  sudo git clone "$REPO" "$SANDBOX_DIR"
  cd "$SANDBOX_DIR"
  echo 'TARGET_ENV=sandbox
TARGET_INSTANCE=hydra-sandbox' > .deploy-target
  [ -f .env.sandbox.example ] && [ ! -f .env ] && sudo cp .env.sandbox.example .env
fi

cd "$SANDBOX_DIR"
echo 'TARGET_ENV=sandbox
TARGET_INSTANCE=hydra-sandbox' > .deploy-target

# Apply migrations (patch4 vk_active_scenario)
if [ -f migrations/patch4_001_vk_active_scenario.sql ]; then
  source .env 2>/dev/null || true
  PGPASSWORD="${DB_PASSWORD:-}" psql -U hydra -d hydra_bot_sandbox -h localhost -f migrations/patch4_001_vk_active_scenario.sql 2>/dev/null || true
fi

if [ -f .env ]; then
  echo "sandbox:hydra-sandbox" | sudo bash deploy/guarded_deploy.sh --env sandbox --project-dir "$SANDBOX_DIR"
else
  sudo bash deploy/setup_sandbox.sh
fi
echo "[DONE] Sandbox deploy finished"
'@

Write-Host "[STEP] Connecting to $sshTarget..." -ForegroundColor Cyan

if ($key -and (Test-Path $key)) {
    Write-Host "[STEP] Using SSH key: $key" -ForegroundColor Cyan
    ssh -o StrictHostKeyChecking=accept-new -i $key $sshTarget $remoteScript
} elseif ($password -and (Get-Command plink -ErrorAction SilentlyContinue)) {
    Write-Host "[STEP] Using plink with password" -ForegroundColor Cyan
    $tmpScript = [System.IO.Path]::GetTempFileName()
    $scriptLf = $remoteScript -replace "`r`n", "`n" -replace "`r", "`n"
    [System.IO.File]::WriteAllText($tmpScript, $scriptLf, [System.Text.UTF8Encoding]::new($false))
    try {
        if ($hostKey) {
            Get-Content $tmpScript -Raw | plink -batch -hostkey $hostKey -pw $password $sshTarget "bash -s"
        } else {
            Write-Host "[WARN] DEPLOY_HOSTKEY not set; plink may fail in batch mode on first connect" -ForegroundColor Yellow
            Get-Content $tmpScript -Raw | plink -batch -pw $password $sshTarget "bash -s"
        }
    } finally {
        Remove-Item $tmpScript -Force -ErrorAction SilentlyContinue
    }
} elseif ($password) {
    Write-Host "[STEP] ssh with password (interactive) - run manually if needed" -ForegroundColor Yellow
    ssh -o StrictHostKeyChecking=accept-new $sshTarget $remoteScript
} else {
    Write-Host "[FAIL] Set DEPLOY_KEY (path to private key) or DEPLOY_PASSWORD in .deploy.env" -ForegroundColor Red
    Write-Host "  For password auth: install PuTTY/plink, add DEPLOY_PASSWORD to .deploy.env" -ForegroundColor Yellow
    exit 1
}
