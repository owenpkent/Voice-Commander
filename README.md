# Whisper Desktop Transcriber

A minimal local desktop app (Tkinter) to record audio and transcribe it using OpenAI Whisper, returning text you can copy/paste anywhere.

## Requirements
- Python 3.10+
- Microphone
- OpenAI API key (`OPENAI_API_KEY`)
  - Only required for the API backend. The Local backend (faster-whisper) does not need an API key.

## Setup
1. Create and activate a virtual environment (recommended)
   - PowerShell:
     ```powershell
     .\.venv\Scripts\Activate.ps1
     ```
2. Install dependencies
   ```powershell
   pip install -r requirements.txt
   ```
3. Set your OpenAI API key
   - For current PowerShell session:
     ```powershell
     $env:OPENAI_API_KEY = "YOUR_API_KEY"
     ```
   - To persist (new shells only):
     ```powershell
     setx OPENAI_API_KEY "YOUR_API_KEY"
     ```
   - Or create a local `.env` file:
     ```
     copy .env.example .env
     # then edit .env and set OPENAI_API_KEY=...
     ```
     - `.env` is git-ignored by default (see `.gitignore`). Use `.env.example` as a template.

## Run
```powershell
python run.py
```
Transcribe an audio file and print the text to stdout:
```powershell
python run.py --transcribe latest.wav
```
Optional flags:
```powershell
# API backend (default):
python run.py --transcribe latest.wav --backend api --model whisper-1

# Local backend (faster-whisper) with English-only model:
python run.py --transcribe latest.wav --backend local --local-model base.en
```
## Usage
- Click "Record" to start. Speak.
- Click "Stop" to save `latest.wav`.
- Choose a backend at the top: `API` (OpenAI Whisper) or `Local` (faster-whisper).
- If `Local`, pick a local model (e.g., `base.en`).
- Click "Transcribe" to run with the selected backend.
- The text appears in the main box. Click "Copy Text" to place it on the clipboard.

## Notes
- The app uses `sounddevice` to capture audio at 16 kHz mono, 16-bit.
- `OPENAI_API_KEY` must be set only when using the API backend.
- `latest.wav` is written in the repo folder and is git-ignored.
- Local backend uses `faster-whisper`. The first run will download model weights (size varies by model). CPU `int8` is used by default.
 - `.env` is git-ignored by default (see `.gitignore`). Use `.env.example` as a template.
## Troubleshooting
- No input device found: ensure a microphone is connected and enabled in Windows Sound settings.
- PortAudio errors: try updating audio drivers; ensure only one app uses the mic.
- OpenAI errors: verify your API key and that your account has access and credits.
