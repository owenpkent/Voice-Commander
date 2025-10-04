# Voice Commander

Hybrid voice interface that combines real-time command recognition with high-accuracy transcription. Cloud service performs recognition + simple NLU and emits structured JSON intents over WebSocket; a lightweight local agent subscribes and maps intents to keystrokes, mouse events, or controller inputs.

## Architecture
- **Cloud (`cloud/`)**: FastAPI app exposing:
  - `GET /` server banner
  - `GET /healthz` health endpoint
  - `WS /ws/commands` broadcast channel for intents
  - `WS /ws/stream` real-time audio streaming to intents
  - `POST /simulate` helper to broadcast a text string through simple NLU for testing
  - `POST /batch` batch transcription with word timings; writes JSON to S3 if configured
- **Agent (`agent/`)**: Windows client that connects via WebSocket and applies intents using global input libraries (`keyboard`, `mouse`).
  - Backward compatible with the legacy intent schema and supports the new schema:
    - New: `{ "intent":"Key|Chord|FirePrimary|FlapsSet|ThrottleAdjust|MouseHold|MouseRelease", "entities": [...] }`
    - Legacy: `{ "intent":"key.press|key.combo|mouse.click", "payload": { ... } }`
- **Client (`client/`)**: Minimal microphone streaming client that captures audio and sends 16kHz PCM16 frames to `WS /ws/stream`.

## Repo structure
```
cloud/
  main.py         # FastAPI app + WebSocket
  nlu.py          # Simple rule-based NLU mapping
  models.py       # Pydantic models
  asr.py          # faster-whisper helpers (stream & batch)
  grammar.py      # Regex grammar mapping text->intent schema
  requirements.txt
agent/
  agent.py        # WebSocket client that applies intents
  input_mapper.py # Maps intents to keyboard/mouse actions
  config.json     # Server URL
  requirements.txt
client/
  stream_client.py  # Mic -> WS /ws/stream
  requirements.txt
scripts/
  run-cloud.ps1   # Start uvicorn
  run-agent.ps1   # Start agent (module mode)
  run-stream-client.ps1 # Start streaming client
  run-all.ps1      # One command: open Cloud/Agent/Client windows
deploy/
  voice-commander.service # systemd unit template (Ubuntu)
Dockerfile        # Container image for cloud service
docker-compose.yml
.dockerignore
scripts/deploy-docker.ps1 # One-command EC2 Docker deploy
```

## Quick start (Windows)
You can use separate virtual environments for cloud and agent.

1) Cloud service
```
python -m venv .venv-cloud
. .venv-cloud/Scripts/Activate.ps1
pip install -r cloud/requirements.txt
./scripts/run-cloud.ps1  # starts FastAPI at http://localhost:8000
```

2) Agent (in a second terminal)
```
python -m venv .venv-agent
. .venv-agent/Scripts/Activate.ps1
pip install -r agent/requirements.txt
# For global key injection, run PowerShell as Administrator
./scripts/run-agent.ps1
```

3) Streaming client (mic to server)
```
python -m venv .venv-client
. .venv-client/Scripts/Activate.ps1
pip install -r client/requirements.txt
# Local server:
./scripts/run-stream-client.ps1 -Server "ws://localhost:8000/ws/stream" -GrammarProfile "premiere"
# Remote EC2:
./scripts/run-stream-client.ps1 -Server "ws://<EC2-IP>:8000/ws/stream" -GrammarProfile "premiere"
```

## Launcher & one-command run

- Launcher (interactive menu):
```
python launcher.py
```
Choose:
- 1: Cloud
- 2: Agent (run in Administrator PowerShell for global input)
- 3: Streaming Client
- 4: Setup All (create venvs and install requirements)

- One-command multi-window start (local):
```
./scripts/run-all.ps1 -Mode gaming
```
- EC2 target:
```
./scripts/run-all.ps1 -Server "ws://<EC2-IP>:8000/ws/stream" -Mode gaming -Profile "premiere"
```

Note: In Administrator PowerShell, `python` may not be on PATH. Use `py -3` or call the venv python directly (e.g., `.\.venv-agent\Scripts\python.exe`).
## Test without a microphone (simulate)
With both cloud and agent running, broadcast a test command via HTTP:

PowerShell:
```
$body = @{ text = "spacebar" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/simulate -Method POST -ContentType 'application/json' -Body $body
```
Other examples:
- `"cut"` -> Ctrl+X
- `"copy"` -> Ctrl+C
- `"paste"` -> Ctrl+V
- `"gear up"` -> Page Up

Streaming intent rules live in `cloud/grammar.py`. The `/simulate` endpoint uses legacy mappings in `cloud/nlu.py`.

## Real-time streaming API
  - `{ "pcm16": "<base64 of 16kHz mono PCM16 little-endian>" }`
  - **Control (optional)**
  - `{ "cmd":"set_profile", "value":"premiere" }`
  - **Server → Client intents (JSON)**
  - Example: `{ "intent":"Key", "entities":[{ "type":"key", "value":"space" }] }`
  - Intent schema supported initially:
    - `Key|Chord|FirePrimary|FlapsSet|ThrottleAdjust|MouseHold|MouseRelease`
    - Entities include: `key`, `chord`, `step`, `delta`, `duration_ms`

## Client troubleshooting
- List devices: `./scripts/run-stream-client.ps1 -ListDevices`
- Show mic level meter: `./scripts/run-stream-client.ps1 -ShowLevels`
- Show send rate: `./scripts/run-stream-client.ps1 -Stats`
- Choose mic device: `./scripts/run-stream-client.ps1 -Device <index>` (use with `-ListDevices`)
- Reduce latency: lower server buffer `VC_STREAM_MIN_SEC=0.5` and/or use `-ChunkMs 10` on the client
- If Admin shell says "Python not installed": use `py -3` or venv python path

## ROADMAP
  - Streaming ASR (low-latency) for command mode
  - Batch Whisper for high-accuracy transcripts with timestamps
  - Configurable grammar and per-app command maps
  - Security: auth on WebSocket and signed intents
- Audio must be 16kHz, mono, PCM16 LE.
- The server buffers ~0.8s by default (override via `VC_STREAM_MIN_SEC`).
- Intents from `/ws/stream` are also broadcast to `/ws/commands` for local agents.

## Batch transcription API
- `POST /batch` with WAV/FLAC/… file upload (multipart/form-data)
  - Returns:
    ```json
    { "text":"...", "words":[ { "word":"hello", "start":0.42, "end":0.58, "prob":0.93 } ] }
    ```
  - If S3 is configured, also returns `s3_key` of the uploaded JSON results in the bucket.

### Ubuntu/EC2 prerequisites
- Install ffmpeg to support containerized audio decoding:
  - `sudo apt-get update && sudo apt-get install -y ffmpeg`
- Recommended env vars (example):
  - `VC_S3_BUCKET=voice-commander-data-opk`
  - `VC_STREAM_MODEL=tiny.en` (low-latency)
  - `VC_BATCH_MODEL=small` (or larger with GPU box)

## Configuration
- Agent server URL: `agent/config.json` or env var `VC_SERVER_URL`.
- CORS: Cloud is permissive by default for ease of testing.
- Cloud ASR models (env): `VC_STREAM_MODEL`, `VC_STREAM_DEVICE`, `VC_STREAM_COMPUTE`, `VC_STREAM_MIN_SEC`, `VC_BATCH_MODEL`, `VC_BATCH_DEVICE`, `VC_BATCH_COMPUTE`.
- S3: `VC_S3_BUCKET` (requires AWS credentials/role).

### Optional dependencies (Windows)
- `webrtcvad` is optional on Windows and requires MSVC build tools. It is commented out in `cloud/requirements.txt`. The server will run without it (silence gating disabled). To enable later, install build tools and uncomment.

## EC2 systemd (Ubuntu)
Use the provided template and adjust paths as needed:

1) Copy `deploy/voice-commander.service` to `/etc/systemd/system/voice-commander.service`.
2) Edit `WorkingDirectory` and `ExecStart` to your repo path and venv Python.
3) Reload and start:
```
sudo systemctl daemon-reload
sudo systemctl enable voice-commander
sudo systemctl start voice-commander
sudo systemctl status voice-commander
```

## Docker quick deploy (EC2)
Use the provided script to build and run the server in Docker on your EC2 instance in one command:

PowerShell (from repo root):
```
./scripts/deploy-docker.ps1 -KeyPath "S:\OneDrive - Rocky Mountain Inventions\Documents\AWS\voice-commander-key.pem" -Ec2Host <EC2-IP> -NoCache
```

- The script uploads the repo, builds the Docker image (CPU), stops any old container, starts the new one, and verifies `/`.
- Check: `http://<EC2-IP>:8000/` and `http://<EC2-IP>:8000/healthz`.
- Environment defaults can be overridden with flags; see the script for parameters.

## Notes & permissions
- On Windows, global keyboard/mouse events may require running the terminal as Administrator.
- Some anti-cheat systems may block input injection. Use responsibly.
- Lock down port 8000 to your IP in the EC2 security group; consider Nginx/ALB + HTTPS later.

## Roadmap
- Streaming ASR (low-latency) for command mode
- Batch Whisper for high-accuracy transcripts with timestamps
- Configurable grammar and per-app command maps
- Security: auth on WebSocket and signed intents

## License
See `LICENSE`.
