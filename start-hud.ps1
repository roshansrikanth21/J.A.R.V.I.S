# start-hud.ps1 — Launch the JARVIS HUD overlay
# Run this in a separate terminal while the main JARVIS engine is running.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "=== J.A.R.V.I.S HUD ===" -ForegroundColor Cyan
Write-Host "Connecting to backend at ws://localhost:8000/ws" -ForegroundColor Gray
Write-Host "Close the tray icon or press Ctrl+C to exit." -ForegroundColor Gray
Write-Host ""

& ".\venv\Scripts\python.exe" run_hud.py
