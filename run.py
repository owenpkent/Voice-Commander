import argparse
import os
import sys
import subprocess


def load_env_from_dotenv(path: str = ".env"):
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)
    except Exception:
        pass


def _pip_install(requirement: str) -> bool:
    try:
        print(f"Installing dependency: {requirement}...")
        res = subprocess.run([sys.executable, "-m", "pip", "install", requirement], capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout)
            print(res.stderr, file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"pip install failed for {requirement}: {e}", file=sys.stderr)
        return False


def _upgrade_build_tools() -> None:
    try:
        print("Upgrading pip/setuptools/wheel...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], check=False)
    except Exception:
        pass


def ensure_openai(interactive: bool = False):
    try:
        from openai import OpenAI  # noqa: F401
    except Exception:
        if not _pip_install("openai>=1.30.0,<2.0.0"):
            _upgrade_build_tools()
            if not _pip_install("openai>=1.30.0,<2.0.0"):
                print("Error: failed to install 'openai'.", file=sys.stderr)
                sys.exit(1)
        # re-import after install
        try:
            from openai import OpenAI  # noqa: F401
        except Exception as e:  # pragma: no cover
            print(f"Error importing openai after install: {e}", file=sys.stderr)
            sys.exit(1)

    # Load .env if present to pick up OPENAI_API_KEY
    load_env_from_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        if interactive:
            try:
                print("OPENAI_API_KEY not set. Enter key (input hidden not supported here):")
                key = input().strip()
                if key:
                    os.environ["OPENAI_API_KEY"] = key
                else:
                    print("Error: OPENAI_API_KEY not provided.", file=sys.stderr)
                    sys.exit(1)
            except Exception:
                print("Error: OPENAI_API_KEY not set in environment.", file=sys.stderr)
                sys.exit(1)
        else:
            print("Error: OPENAI_API_KEY not set in environment.", file=sys.stderr)
            sys.exit(1)


def ensure_faster_whisper():
    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except Exception:
        if not _pip_install("faster-whisper>=1.0.0"):
            _upgrade_build_tools()
            if not _pip_install("faster-whisper>=1.0.0"):
                print("Error: failed to install 'faster-whisper'.", file=sys.stderr)
                sys.exit(1)
        # re-import after install
        try:
            from faster_whisper import WhisperModel  # noqa: F401
        except Exception as e:  # pragma: no cover
            print(f"Error importing faster-whisper after install: {e}", file=sys.stderr)
            sys.exit(1)


def ensure_torch():
    # Ensure torch is importable; install CPU wheel if missing
    try:
        import torch  # noqa: F401
        return
    except Exception:
        pass
    # Try install from PyPI
    if not _pip_install("torch>=2.1.0"):
        _upgrade_build_tools()
        if not _pip_install("torch>=2.1.0"):
            # Fallback to PyTorch CPU wheels index
            print("Retrying torch install from PyTorch CPU wheels index...")
            res = subprocess.run([
                sys.executable, "-m", "pip", "install",
                "--index-url", "https://download.pytorch.org/whl/cpu",
                "torch>=2.1.0"
            ], capture_output=True, text=True)
            if res.returncode != 0:
                print(res.stdout)
                print(res.stderr, file=sys.stderr)
                print("Error: failed to install 'torch'.", file=sys.stderr)
                sys.exit(1)
    try:
        import torch  # noqa: F401
    except Exception as e:
        print(f"Error importing torch after install: {e}", file=sys.stderr)
        sys.exit(1)


def ensure_keyboard():
    # Best-effort install; not fatal if missing
    try:
        import keyboard  # noqa: F401
        return
    except Exception:
        pass
    if not _pip_install("keyboard>=0.13.5"):
        _upgrade_build_tools()
        if not _pip_install("keyboard>=0.13.5"):
            print("Warning: failed to install 'keyboard'. Command Mode keystrokes may be unavailable.", file=sys.stderr)
            return
    try:
        import keyboard  # noqa: F401
    except Exception as e:
        print(f"Warning: importing 'keyboard' after install failed: {e}", file=sys.stderr)
        # Non-fatal
        return


def ensure_torchaudio():
    try:
        import torchaudio  # noqa: F401
        return
    except Exception:
        pass
    # Try to match torchaudio to the installed torch version
    torch_version = None
    try:
        import torch  # noqa: F401
        torch_version = getattr(torch, "__version__", None)
        if torch_version:
            torch_version = torch_version.split("+")[0]
    except Exception:
        torch_version = None

    def install_torchaudio_spec(spec: str) -> bool:
        if _pip_install(spec):
            try:
                import torchaudio  # noqa: F401
                return True
            except Exception:
                return False
        return False

    # 1) Try exact match with CPU index if version known
    if torch_version:
        print(f"Attempting torchaudio=={torch_version} from PyTorch CPU index...")
        res = subprocess.run([
            sys.executable, "-m", "pip", "install",
            "--index-url", "https://download.pytorch.org/whl/cpu",
            f"torchaudio=={torch_version}"
        ], capture_output=True, text=True)
        if res.returncode == 0:
            try:
                import torchaudio  # noqa: F401
                return
            except Exception:
                pass
        else:
            print(res.stdout)
            print(res.stderr, file=sys.stderr)

    # 2) Try generic from PyPI
    if install_torchaudio_spec("torchaudio>=2.1.0"):
        return

    # 3) Fallback to CPU index with generic spec
    print("Retrying torchaudio install from PyTorch CPU wheels index...")
    res = subprocess.run([
        sys.executable, "-m", "pip", "install",
        "--index-url", "https://download.pytorch.org/whl/cpu",
        "torchaudio>=2.1.0"
    ], capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        print("Warning: failed to install 'torchaudio'. Silero VAD may not load.", file=sys.stderr)
        return
    try:
        import torchaudio  # noqa: F401
    except Exception as e:
        print(f"Warning: importing torchaudio after install failed: {e}", file=sys.stderr)
        return


def run_ui():
    return run_ui_with_preference(prefer="qml")


def ensure_pyside6():
    try:
        import PySide6  # noqa: F401
    except Exception:
        if not _pip_install("PySide6>=6.6"):
            _upgrade_build_tools()
            if not _pip_install("PySide6>=6.6"):
                print("Error: failed to install 'PySide6'.", file=sys.stderr)
                sys.exit(1)
        try:
            import PySide6  # noqa: F401
        except Exception as e:
            print(f"Error importing PySide6 after install: {e}", file=sys.stderr)
            sys.exit(1)


def run_ui_with_preference(prefer: str = "qml"):
    # Load .env in case API key is needed and proactively ensure local backend
    load_env_from_dotenv()
    try:
        from faster_whisper import WhisperModel  # noqa: F401
    except Exception:
        ensure_faster_whisper()
    # Ensure Command Mode dependencies so qml_app can import successfully
    ensure_torch()
    ensure_torchaudio()
    ensure_keyboard()

    ui_order = [prefer, "qml", "tk"] if prefer == "qml" else [prefer, "tk", "qml"]
    for ui in ui_order:
        if ui == "qml":
            try:
                ensure_pyside6()
                import qml_app
                return sys.exit(qml_app.main())
            except SystemExit as se:
                raise se
            except Exception as e:
                print(f"QML UI failed: {e}. Falling back...", file=sys.stderr)
                continue
        elif ui == "tk":
            try:
                from app import main as app_main
                return app_main()
            except Exception as e:
                print(f"Tkinter UI failed: {e}", file=sys.stderr)
                continue
    print("No UI could be launched.", file=sys.stderr)
    sys.exit(1)


def transcribe_file(path: str, backend: str = "api", api_model: str = "whisper-1", local_model: str = "base.en"):
    if not os.path.exists(path):
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    backend = (backend or "api").lower()
    if backend == "api":
        ensure_openai(interactive=True)
        from openai import OpenAI

        client = OpenAI()
        try:
            with open(path, "rb") as f:
                result = client.audio.transcriptions.create(
                    model=api_model,
                    file=f,
                )
            text = getattr(result, "text", None) or str(result)
            print(text)
        except Exception as e:
            print(f"Transcription error (API): {e}", file=sys.stderr)
            sys.exit(2)
    else:
        ensure_faster_whisper()
        from faster_whisper import WhisperModel

        try:
            model = WhisperModel(local_model, device="cpu", compute_type="int8")
            segments, info = model.transcribe(path, language="en")
            text_parts = [seg.text for seg in segments]
            print(" ".join(text_parts).strip())
        except Exception as e:
            print(f"Transcription error (Local): {e}", file=sys.stderr)
            sys.exit(2)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run Whisper Desktop Transcriber (QML by default) or transcribe a file via CLI.")
    parser.add_argument("--transcribe", "-t", metavar="FILE", help="Transcribe an audio file (wav/mp3/m4a) and print text")
    parser.add_argument("--backend", choices=["api", "local"], help="Select transcription backend for CLI (api or local)")
    parser.add_argument("--model", default="whisper-1", help="OpenAI Whisper model when --backend api (default: whisper-1)")
    parser.add_argument("--local-model", default="base.en", help="Local faster-whisper model when --backend local (e.g., base.en)")
    parser.add_argument("--ui", choices=["qml", "tk"], default="qml", help="Which UI to launch when not using --transcribe (default: qml)")

    args = parser.parse_args(argv)

    if args.transcribe:
        transcribe_file(
            args.transcribe,
            backend=args.backend or "api",
            api_model=args.model,
            local_model=args.local_model,
        )
    else:
        run_ui_with_preference(prefer=args.ui)


if __name__ == "__main__":
    main()
