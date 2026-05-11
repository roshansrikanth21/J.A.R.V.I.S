$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ui = Join-Path $root "ui"

Write-Host "[JARVIS] Building desktop UI..." -ForegroundColor Yellow
Push-Location $ui
try {
    npm run build
    Write-Host "[JARVIS] Launching desktop app. Backend will start automatically..." -ForegroundColor Green
    npm run desktop:fast
}
finally {
    Pop-Location
}
