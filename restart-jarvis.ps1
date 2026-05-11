$ErrorActionPreference = "Stop"

$ports = @(8000, 8080)
foreach ($port in $ports) {
    $listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($listener in $listeners) {
        $processId = $listener.OwningProcess
        if ($processId -and $processId -ne $PID) {
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if ($process) {
                Write-Host "[JARVIS] Stopping $($process.ProcessName) on port $port (PID $processId)..." -ForegroundColor Yellow
                Stop-Process -Id $processId -Force
            }
        }
    }
}

& (Join-Path $PSScriptRoot "start-jarvis-desktop.ps1")
