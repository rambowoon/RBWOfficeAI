$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"

Write-Host "Starting RBWOfficeAI Backend on http://127.0.0.1:8787 ..." -ForegroundColor Cyan
$BackendCmd = "Set-Location '$BackendDir'; & '.\.venv\Scripts\python' -m uvicorn app.main:app --host 127.0.0.1 --port 8787 --reload"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $BackendCmd

Write-Host "Starting RBWOfficeAI Frontend on http://127.0.0.1:5173 ..." -ForegroundColor Green
$FrontendCmd = "Set-Location '$FrontendDir'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $FrontendCmd

Write-Host "Open http://127.0.0.1:5173 in your browser." -ForegroundColor Yellow
