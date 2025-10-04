param(
  [string]$Server = "ws://localhost:8000/ws/stream",
  [string]$GrammarProfile = "",
  [int]$Device = -1,
  [int]$ChunkMs = 20,
  [ValidateSet("gaming", "transcription")][string]$Mode = "gaming",
  [switch]$ShowLevels,
  [switch]$Stats,
  [switch]$ListDevices
)
$env:PYTHONUNBUFFERED = "1"
$argvList = @()
if ($Server) { $argvList += @("--server", $Server) }
if ($GrammarProfile) { $argvList += @("--profile", $GrammarProfile) }
if ($Device -ge 0) { $argvList += @("--device", $Device) }
if ($ChunkMs -ne 20) { $argvList += @("--chunk-ms", $ChunkMs) }
if ($Mode) { $argvList += @("--mode", $Mode) }
if ($ShowLevels) { $argvList += @("--show-levels") }
if ($Stats) { $argvList += @("--stats") }
if ($ListDevices) { $argvList += @("--list-devices") }
python -m client.stream_client @argvList
