$ErrorActionPreference = "Stop"

Write-Host "`n[JARVIS] Initializing Unified Dev Environment..." -ForegroundColor Cyan
Write-Host "[SYSTEM] Port 8000: Backend (FastAPI)" -ForegroundColor Gray
Write-Host "[SYSTEM] Port 8080: Frontend (Vite)" -ForegroundColor Gray

# Ensure node_modules exist
if (-not (Test-Path "node_modules")) {
    Write-Host "[JARVIS] Installing root dependencies..." -ForegroundColor Yellow
    npm install
}

if (-not (Test-Path "ui\node_modules")) {
    Write-Host "[JARVIS] Installing UI dependencies..." -ForegroundColor Yellow
    cd ui; npm install; cd ..
}

Write-Host "[JARVIS] Launching parallel streams...`n" -ForegroundColor Green
npm run dev
