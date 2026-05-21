# Start backend only
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
