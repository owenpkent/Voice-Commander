param(
  [ValidateSet("gaming", "transcription")][string]$Mode = "gaming",
  [string]$Server = "ws://localhost:8000/ws/stream",
  [string]$Profile = ""
)
$ErrorActionPreference = "Stop"

# Repo root is the parent of this scripts directory
$repoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "[1/3] Ensuring virtual environments and dependencies..." -ForegroundColor Cyan
python "$repoRoot\launcher.py" setup

Write-Host "[2/3] Launching Cloud, Agent, and Client in separate windows..." -ForegroundColor Cyan

# Cloud window
Start-Process -FilePath powershell -WorkingDirectory $repoRoot -ArgumentList @(
  "-NoExit",
  "-Command",
  ". .\.venv-cloud\Scripts\Activate.ps1; ./scripts/run-cloud.ps1"
) | Out-Null

# Agent window (Admin for global input)
Start-Process -Verb RunAs -FilePath powershell -WorkingDirectory $repoRoot -ArgumentList @(
  "-NoExit",
  "-Command",
  ". .\.venv-agent\Scripts\Activate.ps1; ./scripts/run-agent.ps1"
) | Out-Null

# Client window
$clientCmd = ". .\.venv-client\Scripts\Activate.ps1; ./scripts/run-stream-client.ps1 -Mode `"$Mode`" -Server `"$Server`""
if ($Profile) { $clientCmd += " -GrammarProfile `"$Profile`"" }
Start-Process -FilePath powershell -WorkingDirectory $repoRoot -ArgumentList @(
  "-NoExit",
  "-Command",
  $clientCmd
) | Out-Null

Write-Host "[3/3] Launched. Windows opened for Cloud, Agent (Admin), and Client." -ForegroundColor Green
Write-Host "- Cloud: http://localhost:8000/" -ForegroundColor DarkGray
Write-Host "- Agent: Requires Administrator for global input" -ForegroundColor DarkGray
Write-Host "- Client: Mode=$Mode Server=$Server Profile=$Profile" -ForegroundColor DarkGray
