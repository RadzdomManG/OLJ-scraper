$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$pythonCmd = "python"
if (Test-Path ".\\.venv\\Scripts\\python.exe") {
    $pythonCmd = ".\\.venv\\Scripts\\python.exe"
}

if (-not $env:ENABLE_UI) {
    $env:ENABLE_UI = "true"
}
if (-not $env:DESKTOP_APP) {
    $env:DESKTOP_APP = "true"
}
if (-not $env:UI_HOST) {
    $env:UI_HOST = "127.0.0.1"
}
if (-not $env:UI_PORT) {
    $env:UI_PORT = "8080"
}

Write-Host "Starting RADZ OLJ SCRAPER (legacy-style dashboard)..." -ForegroundColor Cyan
Write-Host "Host: $($env:UI_HOST)  Port: $($env:UI_PORT)  Desktop App: $($env:DESKTOP_APP)" -ForegroundColor DarkCyan
& $pythonCmd watcher.py
