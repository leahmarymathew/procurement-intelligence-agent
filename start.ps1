# Start the S2P Procurement Agent system
# Usage: .\start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

# Check .env
if (-not (Test-Path ".env")) {
    Write-Host "[setup] .env not found — copying from .env.example"
    Copy-Item ".env.example" ".env"
    Write-Host "[setup] Edit .env and add your OPENAI_API_KEY before continuing."
    Write-Host "        The system runs without a key but supplier scoring will use fallback scores."
}

# Start backend
Write-Host ""
Write-Host "=== Starting FastAPI backend (port 8000) ==="
$backend = Start-Process -PassThru -NoNewWindow powershell -ArgumentList @(
    "-Command",
    "Set-Location '$root'; python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
)

Start-Sleep 3

# Start frontend
Write-Host ""
Write-Host "=== Starting React dashboard (port 5173) ==="
$frontend = Start-Process -PassThru -NoNewWindow powershell -ArgumentList @(
    "-Command",
    "Set-Location '$root\frontend'; npm run dev"
)

Write-Host ""
Write-Host "System started."
Write-Host "  API:       http://localhost:8000"
Write-Host "  API docs:  http://localhost:8000/docs"
Write-Host "  Dashboard: http://localhost:5173"
Write-Host ""
Write-Host "Press Ctrl+C to stop all processes."

try {
    Wait-Process -Id $backend.Id
} finally {
    Stop-Process -Id $frontend.Id -ErrorAction SilentlyContinue
}
