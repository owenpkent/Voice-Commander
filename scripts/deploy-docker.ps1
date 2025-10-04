param(
  [Parameter(Mandatory=$true)][string]$KeyPath,
  [Parameter(Mandatory=$true)][string]$Ec2Host,
  [string]$User = "ubuntu",
  [string]$RemoteDir = "/home/ubuntu/Voice-Commander",
  [string]$ImageTag = "voice-commander:latest",
  [int]$Port = 8000,
  [string]$S3Bucket = "voice-commander-data-opk",
  [string]$StreamModel = "tiny.en",
  [string]$BatchModel = "small",
  [switch]$NoCache
)

$ErrorActionPreference = "Stop"

function Invoke-SSH {
  param([string]$Cmd)
  ssh -o StrictHostKeyChecking=accept-new -i "$KeyPath" "$User@$Ec2Host" $Cmd
}

Write-Host "[1/6] Ensuring remote directory exists..." -ForegroundColor Cyan
Invoke-SSH "mkdir -p $RemoteDir"

Write-Host "[2/6] Installing Docker if missing..." -ForegroundColor Cyan
Invoke-SSH "bash -lc 'if ! command -v docker >/dev/null 2>&1; then sudo apt-get update && sudo apt-get install -y docker.io; fi'"

Write-Host "[3/6] Uploading repository via scp..." -ForegroundColor Cyan
# Repo root is two directories up from scripts
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
# Use scp -r to copy the entire directory (more reliable on Windows)
scp -o StrictHostKeyChecking=accept-new -i "$KeyPath" -r "$repoRoot\*" "$User@$Ec2Host`:$RemoteDir/"

Write-Host "[4/6] Building Docker image on EC2..." -ForegroundColor Cyan
$buildFlags = ""
if ($NoCache.IsPresent) { $buildFlags = "--no-cache" }
Invoke-SSH "bash -lc 'cd $RemoteDir && sudo docker build $buildFlags -t $ImageTag .'"

Write-Host "[5/6] Running container (port $Port) ..." -ForegroundColor Cyan
# Stop and remove old container forcefully, with wait
Invoke-SSH "bash -lc 'sudo docker stop voice-commander >/dev/null 2>&1 || true; sudo docker rm -f voice-commander >/dev/null 2>&1 || true; sleep 1'"
# Build docker run command with proper escaping
$dockerRunCmd = "sudo docker run -d --name voice-commander --restart unless-stopped -p ${Port}:8000 " +
  "-e PYTHONUNBUFFERED=1 " +
  "-e VC_S3_BUCKET=${S3Bucket} " +
  "-e VC_STREAM_MODEL=${StreamModel} -e VC_STREAM_DEVICE=cpu -e VC_STREAM_COMPUTE=int8 -e VC_STREAM_MIN_SEC=0.8 " +
  "-e VC_BATCH_MODEL=${BatchModel} -e VC_BATCH_DEVICE=cpu -e VC_BATCH_COMPUTE=int8 " +
  "${ImageTag}"
Invoke-SSH "bash -lc 'cd $RemoteDir && $dockerRunCmd'"

Write-Host "[6/6] Verifying endpoints..." -ForegroundColor Cyan
# Wait up to ~20s for / to become available, then print it
$verifyTemplate = @'
for i in {1..10}; do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:PORT/);
  if [ "$code" = "200" ]; then curl -s http://localhost:PORT/; break; fi;
  sleep 2;
done
'@
$verifyCmd = $verifyTemplate.Replace('PORT', $Port.ToString())
Invoke-SSH "bash -lc '$verifyCmd'"

Write-Host "Done. Try: http://${Ec2Host}:${Port}/ and ws://${Ec2Host}:${Port}/ws/stream" -ForegroundColor Green
