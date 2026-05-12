$ErrorActionPreference = "Stop"

Write-Host "`n[JARVIS] Starting Unified Build Process..." -ForegroundColor Cyan

Write-Host "`n[1/3] Building Frontend UI..." -ForegroundColor Yellow
cd ui
npm install
npm run build
if ($LASTEXITCODE -ne 0) { throw "Frontend build failed" }
cd ..

Write-Host "`n[2/3] Freezing Python Backend..." -ForegroundColor Yellow
# Ensure pyinstaller is installed
venv\Scripts\python.exe -m pip install pyinstaller
if (Test-Path "dist-python") { Remove-Item -Recurse -Force "dist-python" }
venv\Scripts\python.exe -m PyInstaller --noconsole --onedir --name jarvis_backend --distpath dist-python api.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Write-Host "`n[3/3] Packaging Desktop Application with Electron Builder..." -ForegroundColor Yellow
cd ui
npx electron-builder
if ($LASTEXITCODE -ne 0) { throw "Electron Builder failed" }
cd ..

Write-Host "`n[JARVIS] Build Complete! Check the ui/dist-electron folder for your installer executable." -ForegroundColor Green
