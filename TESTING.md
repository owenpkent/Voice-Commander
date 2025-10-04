# Voice Commander — End-to-End Testing Guide

This guide walks through testing the complete flow: microphone → cloud → agent → keyboard/mouse.

## Prerequisites
- **Cloud service** running (local or EC2)
- **Agent** running (Windows, Administrator recommended)
- **Streaming client** with microphone access

## Test 1: Local end-to-end (no mic)

### Step 1: Start cloud locally
```powershell
. .venv-cloud/Scripts/Activate.ps1
./scripts/run-cloud.ps1
```
- Verify: http://localhost:8000/ and http://localhost:8000/healthz

### Step 2: Start agent (Admin PowerShell)
```powershell
. .venv-agent/Scripts/Activate.ps1
./scripts/run-agent.ps1
```
- You should see: `Voice Commander Agent starting. Server: ws://localhost:8000/ws/commands`
- Then: `Connected to cloud server.`

### Step 3: Simulate a command (no mic)
In a third terminal:
```powershell
$body = @{ text = "spacebar" } | ConvertTo-Json
Invoke-RestMethod -Uri http://localhost:8000/simulate -Method POST -ContentType 'application/json' -Body $body
```

**Expected**: Agent prints `Press key: space` and the Space key is injected globally. Open Notepad to see spaces appear.

**Other test phrases**:
- `"cut"` → Ctrl+X
- `"copy"` → Ctrl+C
- `"paste"` → Ctrl+V
- `"undo"` → Ctrl+Z

---

## Test 2: Real-time mic streaming (gaming mode)

### Setup
1. Cloud running (local or EC2)
2. Agent running (Admin PowerShell)
3. Streaming client ready

### Start streaming client (gaming mode)
```powershell
. .venv-client/Scripts/Activate.ps1
./scripts/run-stream-client.ps1 -Server "ws://localhost:8000/ws/stream" -Mode gaming
```

Or for EC2:
```powershell
./scripts/run-stream-client.ps1 -Server "ws://35.93.15.178:8000/ws/stream" -Mode gaming
```

**Expected output**:
```
[Voice Commander] Mode: GAMING | Profile: default | Server: ws://localhost:8000/ws/stream
Speak commands now. Press Ctrl+C to exit.
```

### Speak commands
Say into your mic:
- **"spacebar"** → You'll see `→ Key` printed, and Space is pressed.
- **"cut"** → `→ Chord` and Ctrl+X is pressed.
- **"copy"** → `→ Chord` and Ctrl+C is pressed.
- **"paste"** → `→ Chord` and Ctrl+V is pressed.

Open Notepad or a game to see the inputs being injected.

---

## Test 3: Transcription mode (full detail)

Start the client in transcription mode:
```powershell
./scripts/run-stream-client.ps1 -Server "ws://localhost:8000/ws/stream" -Mode transcription
```

**Expected**: Full JSON intents are printed for debugging:
```
intent: {'intent': 'Key', 'entities': [{'type': 'key', 'value': 'space'}]}
```

Use this mode to:
- Debug grammar rules
- Verify intent structure
- See confidence scores (if available)

---

## Test 4: Profile switching (e.g., Premiere)

Start with a profile:
```powershell
./scripts/run-stream-client.ps1 -Server "ws://localhost:8000/ws/stream" -GrammarProfile "premiere" -Mode gaming
```

Say **"cut"** → In Premiere profile, this maps to `Ctrl+K` (add edit at playhead) instead of `Ctrl+X`.

Edit `cloud/grammar.py` to add more profile-specific mappings.

---

## Troubleshooting

### Agent not injecting keys
- **Run PowerShell as Administrator** (required for global input on Windows).
- Check agent logs for errors.
- Some games/anti-cheat may block synthetic input.

### No audio captured
- Check microphone permissions (Windows Privacy → Microphone).
- List available devices: `python -m sounddevice` (in client venv).
- Specify device index: `./scripts/run-stream-client.ps1 -Device 1`

### Intents not arriving at agent
- Verify cloud logs show transcripts and intents.
- Check agent is connected: agent terminal should say `Connected to cloud server.`
- Test simulate endpoint first (Test 1) to isolate issue.

### High latency (>1s)
- Reduce buffer: set `VC_STREAM_MIN_SEC=0.5` in cloud env.
- Use smaller model: `VC_STREAM_MODEL=tiny.en`.
- Check network latency if using EC2.

---

## Quick reference commands

### Local (all three terminals)
```powershell
# Terminal 1: Cloud
./scripts/run-cloud.ps1

# Terminal 2: Agent (Admin)
./scripts/run-agent.ps1

# Terminal 3: Streaming client
./scripts/run-stream-client.ps1 -Mode gaming
```

### EC2 (two local terminals + Docker on EC2)
```powershell
# Cloud on EC2 (already running via Docker)

# Terminal 1: Agent (Admin)
$env:VC_SERVER_URL="ws://35.93.15.178:8000/ws/commands"; ./scripts/run-agent.ps1

# Terminal 2: Streaming client
./scripts/run-stream-client.ps1 -Server "ws://35.93.15.178:8000/ws/stream" -Mode gaming
```

---

## Next steps
- Add custom phrases to `cloud/grammar.py`
- Create per-app profiles (Premiere, Resolve, games)
- Explore batch transcription with `POST /batch` for recorded audio
