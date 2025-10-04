# Voice Commander — Deployment Guide

This guide covers local development, EC2 (Ubuntu) deployment, systemd, SSL, environment configuration, S3 integration, scaling, and troubleshooting.

## 1) Components overview
- **Cloud service** (`cloud/main.py`)
  - FastAPI server with:
    - `GET /`: banner
    - `GET /healthz`: healthcheck
    - `WS /ws/stream`: 16kHz PCM16 audio → transcripts → intents (regex grammar)
    - `WS /ws/commands`: broadcasts intents to connected clients (e.g., Windows agent)
    - `POST /batch`: batch transcription (returns `{ text, words[] }`, optionally uploads JSON to S3)
- **Windows Agent** (`agent/agent.py`)
  - Subscribes to `WS /ws/commands`, injects keyboard/mouse events.
- **Streaming Client** (`client/stream_client.py`)
  - Captures microphone audio and streams to `WS /ws/stream`.

## 2) Environment variables
- ASR models and behavior
  - `VC_STREAM_MODEL` (default: `tiny.en`)
  - `VC_STREAM_DEVICE` (default: `cpu`)
  - `VC_STREAM_COMPUTE` (default: `int8`)
  - `VC_STREAM_MIN_SEC` (default: `0.8`) — stream buffer length
  - `VC_BATCH_MODEL` (default: `small`)
  - `VC_BATCH_DEVICE` (default: `cpu`)
  - `VC_BATCH_COMPUTE` (default: `int8`)
- S3 export
  - `VC_S3_BUCKET` (default: `voice-commander-data-opk`)
- General
  - `PYTHONUNBUFFERED=1` recommended for logs

## 3) Local development (Windows)
- Cloud server
  - `python -m venv .venv-cloud`
  - `. .venv-cloud/Scripts/Activate.ps1`
  - `pip install -r cloud/requirements.txt`
  - `./scripts/run-cloud.ps1` (http://localhost:8000)
- Agent (Admin PowerShell recommended for global input)
  - `python -m venv .venv-agent`
  - `. .venv-agent/Scripts/Activate.ps1`
  - `pip install -r agent/requirements.txt`
  - `./scripts/run-agent.ps1`
- Streaming Client (mic → server)
  - `python -m venv .venv-client`
  - `. .venv-client/Scripts/Activate.ps1`
  - `pip install -r client/requirements.txt`
  - `./scripts/run-stream-client.ps1 -Server "ws://localhost:8000/ws/stream" -GrammarProfile "premiere"`

## 4) EC2 (Ubuntu) deployment
- Instance: Ubuntu LTS, open ports 22 (SSH) and 8000 (app). Restrict 8000 to your IP.
- System packages
  - `sudo apt-get update`
  - `sudo apt-get install -y python3-venv python3-pip ffmpeg`
- Clone code (example)
  - `cd /home/ubuntu`
  - `git clone https://github.com/.../Voice-Commander.git`
- Python env
  - `python3 -m venv /home/ubuntu/Voice-Commander/.venv-cloud`
  - `source /home/ubuntu/Voice-Commander/.venv-cloud/bin/activate`
  - `pip install -r /home/ubuntu/Voice-Commander/cloud/requirements.txt`
- Run once to verify
  - `python -m uvicorn cloud.main:app --host 0.0.0.0 --port 8000`
  - Check `http://<EC2-IP>:8000/` and `/healthz`

### 4.1) Systemd service
- Edit the unit file `deploy/voice-commander.service` with your paths (WorkingDirectory, ExecStart, env vars).
- Install and enable:
```
sudo cp deploy/voice-commander.service /etc/systemd/system/voice-commander.service
sudo systemctl daemon-reload
sudo systemctl enable voice-commander
sudo systemctl start voice-commander
sudo systemctl status voice-commander
```
- Logs: `journalctl -u voice-commander -f`

### 4.2) Optional: Nginx reverse proxy + SSL (Let’s Encrypt)
- Install Nginx: `sudo apt-get install -y nginx`
- Create a site config (proxy 443→127.0.0.1:8000)
- Obtain certs with Certbot:
```
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
```
- Update security group to allow 443 and close 8000 from the public internet.

### 4.3) Docker quick deploy (EC2)
Use the provided PowerShell script to build and run the server in Docker on your EC2 instance in one command.

PowerShell (from repo root):
```
./scripts/deploy-docker.ps1 -KeyPath "S:\OneDrive - Rocky Mountain Inventions\Documents\AWS\voice-commander-key.pem" -Ec2Host <EC2-IP> -NoCache
```

Notes:
- The script uploads the repo via scp, builds the Docker image, force-stops any old container, starts the new one, and verifies `/`.
- Check: `http://<EC2-IP>:8000/` and `http://<EC2-IP>:8000/healthz`.
- You can override environment defaults with flags (see the script header for options).

## 5) S3 integration (batch results)
- Set `VC_S3_BUCKET` env var (default `voice-commander-data-opk`).
- Ensure the EC2 instance role or AWS credentials allow `s3:PutObject` in that bucket.
- `/batch` returns `s3_key` when upload succeeds.

## 6) Scaling & performance
- **Models**: Use `tiny.en` or `base.en` for streaming. Batch can use `small` on CPU; for high throughput/accuracy, deploy a GPU worker or an external ASR API.
- **Processes**: Run multiple Uvicorn workers behind Nginx for more concurrency (note: streaming websockets are long-lived; scale vertically or shard clients).
- **Observability**: Add structured logging, metrics (Prometheus exporter), and traces if needed.
- **Security**: Add a token to `WS /ws/stream` and `WS /ws/commands`. Move behind HTTPS. Lock SGs to your IPs.

## 7) API summary
- `WS /ws/stream`
  - Client → Server frames: `{ "pcm16": "<base64 PCM16 16kHz mono>" }`
  - Control: `{ "cmd": "set_profile", "value": "premiere" }`
  - Server → Client intents: `{ "intent": "Key|Chord|FirePrimary|FlapsSet|ThrottleAdjust|MouseHold|MouseRelease", "entities": [...] }`
  - Intents are also broadcast to `WS /ws/commands`.
- `WS /ws/commands` — broadcast-only channel for agents.
- `POST /batch` — returns `{ text, words[] }` and optionally `s3_key`.
- `GET /`, `GET /healthz`.

## 8) Troubleshooting
- **No audio intents on /ws/stream**: verify client is sending 16kHz mono PCM16 LE. Confirm server logs and `VC_STREAM_MIN_SEC` buffering.
- **Batch decoding errors**: ensure `ffmpeg` installed; use WAV/FLAC; check logs and bucket permissions.
- **Agent not injecting input**: run PowerShell as Administrator; some games/anti-cheat may block synthetic input.
- **High latency**: reduce `VC_STREAM_MIN_SEC` (e.g., 0.5) and choose a smaller streaming model.
- **Memory/CPU limits**: t3.micro is minimal; consider larger instance for faster-whisper.
- **/healthz returns 404 in Docker**: rebuild without cache to ensure the container includes the latest code:
  - `./scripts/deploy-docker.ps1 -KeyPath <PEM> -Ec2Host <EC2-IP> -NoCache`
- **Port 8000 already in use**: force-remove the old container and start the new one:
  - `ssh ... "sudo docker rm -f voice-commander; sleep 1; sudo docker run -d --name voice-commander -p 8000:8000 ... voice-commander:latest"`

## 9) Backups & rollback (suggested)
- Keep systemd logs rotated (`/etc/logrotate.d/journal`) and back up configuration.
- Tag S3 objects with metadata to track runs. Use versioned S3 bucket for rollback of transcripts.

---
For questions or operational changes (auth, GPU deployment, YAML profiles), see `TODO.md` for the roadmap.
