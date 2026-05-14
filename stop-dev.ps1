Write-Host "`n[JARVIS] Shutting down all servers..." -ForegroundColor Cyan
Stop-Process -Name "python","node" -Force -ErrorAction SilentlyContinue
Write-Host "[SYSTEM] Backend (Python) stopped." -ForegroundColor Gray
Write-Host "[SYSTEM] Frontend (Node/Vite) stopped." -ForegroundColor Gray
Write-Host "[JARVIS] All systems offline.`n" -ForegroundColor Green
