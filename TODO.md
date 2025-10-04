# Voice Commander — Project TODO

Use this document to track backlog, in-progress items, and completed work. Checkboxes indicate status and help coordinate across modules (cloud, agent, client, ops).

## Status legend
- [ ] Not started
- [~] In progress
- [x] Done

## Backlog
- [ ] Security
  - [ ] WebSocket auth tokens for `/ws/stream` and `/ws/commands`
  - [ ] HTTPS via Nginx/ALB + certs
  - [ ] Signed intents (HMAC) between cloud and agent
- [ ] Profiles (YAML)
  - [ ] Move rules from `cloud/grammar.py` into `configs/` YAML per app (Premiere/Resolve/Sim)
  - [ ] Hot-reload or admin API to switch/update profiles
- [ ] Streaming ASR improvements
  - [ ] VAD tuning and adaptive buffer (`VC_STREAM_MIN_SEC` per profile)
  - [ ] Partial hypothesis emission for sub-0.5s latency
  - [ ] GPU-accelerated streaming worker option
- [ ] Batch ASR improvements
  - [ ] GPU path for large models; autoscale batch workers
  - [ ] Alternative ASR API integration option
  - [ ] SRT/VTT export endpoints and signed S3 URLs
- [ ] Agent outputs
  - [ ] ViGEm/vJoy virtual controller output (gaming)
  - [ ] App-aware key mapping (detect active window)
  - [ ] Safety mode (disable in full-screen anti-cheat contexts)
  - [ ] Configurable key repeat/hold durations
- [ ] Observability
  - [ ] Structured logs + request IDs
  - [ ] Metrics (Prometheus) for stream/batch
  - [ ] Basic tracing

## In progress
- [~] Security hardening
  - [ ] Token auth for WebSockets
  - [ ] Lock down SG + HTTPS fronting (Nginx/ALB)
- [~] Advanced agent features
  - [ ] Windows service wrapper (runs at boot)
  - [ ] System tray app with pause/resume

## Completed
- [x] Scaffolding: cloud + agent + scripts + README
- [x] `WS /ws/commands` broadcast + `/simulate`
- [x] Minimal NLU for legacy simulate mode
- [x] Streaming ASR endpoint: `WS /ws/stream` (buffer, VAD optional, intents)
- [x] Batch transcription endpoint: `POST /batch` (text + words + S3)
- [x] Grammar: regex-based mapping to new intent schema
- [x] Agent compatibility with new intent schema
- [x] Streaming client (microphone) + Windows runner
- [x] EC2 systemd service template
- [x] Docker support (Dockerfile, .dockerignore, docker-compose.yml)
- [x] One-command EC2 Docker deploy script (`scripts/deploy-docker.ps1`)
- [x] Documentation updates: README (Docker quick deploy), DEPLOY (Docker section, troubleshooting)
- [x] Gaming vs transcription mode toggle in streaming client
- [x] End-to-end testing guide (TESTING.md)

## Nice to have
- [ ] Admin dashboard (web UI) for testing & monitoring
- [ ] Public demo with restricted auth
- [ ] Automated installers for Windows agent
- [ ] Cross-platform agent (macOS, Linux)
