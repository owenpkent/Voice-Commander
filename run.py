import argparse
import os
import sys


def ensure_openai():
    try:
        from openai import OpenAI  # noqa: F401
    except Exception:
        print("Error: openai package not installed. Run 'pip install -r requirements.txt'", file=sys.stderr)
        sys.exit(1)
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set in environment.", file=sys.stderr)
        sys.exit(1)


def run_ui():
    # Lazy import so that CLI-only usage doesn't require Tk deps immediately
    from app import main as app_main
    app_main()


def transcribe_file(path: str, model: str = "whisper-1"):
    ensure_openai()
    from openai import OpenAI

    if not os.path.exists(path):
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    client = OpenAI()
    try:
        with open(path, "rb") as f:
            result = client.audio.transcriptions.create(
                model=model,
                file=f,
            )
        text = getattr(result, "text", None) or str(result)
        print(text)
    except Exception as e:
        print(f"Transcription error: {e}", file=sys.stderr)
        sys.exit(2)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Whisper Desktop Transcriber or transcribe a file via CLI.")
    parser.add_argument("--transcribe", "-t", metavar="FILE", help="Transcribe an audio file (wav/mp3/m4a) and print text")
    parser.add_argument("--model", default="whisper-1", help="OpenAI Whisper model (default: whisper-1)")

    args = parser.parse_args(argv)

    if args.transcribe:
        transcribe_file(args.transcribe, model=args.model)
    else:
        run_ui()


if __name__ == "__main__":
    main()
