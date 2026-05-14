$ErrorActionPreference = "Stop"

Write-Host "`n[JARVIS] Initializing Unified Dev Environment..." -ForegroundColor Cyan
Write-Host "[SYSTEM] Port 8000: Backend (FastAPI)" -ForegroundColor Gray
Write-Host "[SYSTEM] Port 8080: Frontend (Vite)" -ForegroundColor Gray
Write-Host "[SYSTEM] Port 11434: Ollama LLM Runtime" -ForegroundColor Gray

# ── Auto-start Ollama if not already running ─────────────────────────────────
$ollamaRunning = $false
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:11434" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    $ollamaRunning = $true
} catch {}

if ($ollamaRunning) {
    Write-Host "[OLLAMA] Already running on port 11434" -ForegroundColor Green
} else {
    Write-Host "[OLLAMA] Starting Ollama server..." -ForegroundColor Yellow
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Write-Host "[OLLAMA] Started in background" -ForegroundColor Green
}

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
