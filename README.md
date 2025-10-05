# Whisper Desktop Transcriber

A minimal local desktop app (Tkinter) to record audio and transcribe it using OpenAI Whisper, returning text you can copy/paste anywhere.

## Requirements
- Python 3.10+
- Microphone
- OpenAI API key (`OPENAI_API_KEY`)

## Setup
1. Create and activate a virtual environment (recommended)
   - PowerShell:
     ```powershell
     python -m venv .venv
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

## Run
```powershell
python app.py
```

## Usage
- Click "Record" to start. Speak.
- Click "Stop" to save `latest.wav`.
- Click "Transcribe" to send audio to OpenAI Whisper (`whisper-1`).
- The text appears in the main box. Click "Copy Text" to place it on the clipboard.

## Notes
- The app uses `sounddevice` to capture audio at 16 kHz mono, 16-bit.
- `OPENAI_API_KEY` must be set before transcribing.
- `latest.wav` is written in the repo folder and is git-ignored.

## Troubleshooting
- No input device found: ensure a microphone is connected and enabled in Windows Sound settings.
- PortAudio errors: try updating audio drivers; ensure only one app uses the mic.
- OpenAI errors: verify your API key and that your account has access and credits.
