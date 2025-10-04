#!/usr/bin/env python3
"""
Voice Commander Launcher
Automatically sets up virtual environments and launches components.
"""
import os
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent
VENV_CLOUD = REPO_ROOT / ".venv-cloud"
VENV_AGENT = REPO_ROOT / ".venv-agent"
VENV_CLIENT = REPO_ROOT / ".venv-client"


def run_cmd(cmd: list, cwd=None, check=True):
    """Run a command and print output."""
    print(f"→ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd or REPO_ROOT, check=check)
    return result.returncode == 0


def venv_exists(venv_path: Path) -> bool:
    """Check if venv exists and has Python."""
    if os.name == "nt":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"
    return python_exe.exists()


def get_venv_python(venv_path: Path) -> str:
    """Get the path to the venv's Python executable."""
    if os.name == "nt":
        return str(venv_path / "Scripts" / "python.exe")
    return str(venv_path / "bin" / "python")


def setup_venv(venv_path: Path, requirements: Path):
    """Create venv if needed and install requirements."""
    if not venv_exists(venv_path):
        print(f"\n[Setup] Creating virtual environment: {venv_path.name}")
        run_cmd([sys.executable, "-m", "venv", str(venv_path)])
    else:
        print(f"\n[Setup] Virtual environment exists: {venv_path.name}")

    python_exe = get_venv_python(venv_path)
    print(f"[Setup] Installing requirements: {requirements}")
    run_cmd([python_exe, "-m", "pip", "install", "--upgrade", "pip", "-q"])
    run_cmd([python_exe, "-m", "pip", "install", "-r", str(requirements)])


def launch_cloud():
    """Launch the cloud service."""
    print("\n" + "="*60)
    print("LAUNCHING CLOUD SERVICE")
    print("="*60)
    setup_venv(VENV_CLOUD, REPO_ROOT / "cloud" / "requirements.txt")
    python_exe = get_venv_python(VENV_CLOUD)
    print("\n[Cloud] Starting FastAPI server on http://localhost:8000")
    print("[Cloud] Press Ctrl+C to stop\n")
    os.environ["PYTHONUNBUFFERED"] = "1"
    run_cmd([python_exe, "-m", "uvicorn", "cloud.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"], check=False)


def launch_agent():
    """Launch the Windows agent."""
    print("\n" + "="*60)
    print("LAUNCHING AGENT")
    print("="*60)
    if os.name == "nt":
        print("[Agent] NOTE: For global input injection, run this script as Administrator.")
    setup_venv(VENV_AGENT, REPO_ROOT / "agent" / "requirements.txt")
    python_exe = get_venv_python(VENV_AGENT)
    print("\n[Agent] Connecting to cloud server...")
    print("[Agent] Press Ctrl+C to stop\n")
    os.environ["PYTHONUNBUFFERED"] = "1"
    run_cmd([python_exe, "-m", "agent.agent"], check=False)


def launch_client(mode="gaming", server=None, profile=None):
    """Launch the streaming client."""
    print("\n" + "="*60)
    print(f"LAUNCHING STREAMING CLIENT ({mode.upper()} MODE)")
    print("="*60)
    setup_venv(VENV_CLIENT, REPO_ROOT / "client" / "requirements.txt")
    python_exe = get_venv_python(VENV_CLIENT)
    
    args = [python_exe, "-m", "client.stream_client", "--mode", mode]
    if server:
        args.extend(["--server", server])
    if profile:
        args.extend(["--profile", profile])
    
    print(f"\n[Client] Mode: {mode}")
    print(f"[Client] Server: {server or 'ws://localhost:8000/ws/stream'}")
    print("[Client] Speak commands into your microphone. Press Ctrl+C to stop\n")
    os.environ["PYTHONUNBUFFERED"] = "1"
    run_cmd(args, check=False)


def setup_all():
    """Set up all virtual environments and dependencies."""
    print("\n" + "="*60)
    print("SETTING UP ALL COMPONENTS")
    print("="*60)
    setup_venv(VENV_CLOUD, REPO_ROOT / "cloud" / "requirements.txt")
    setup_venv(VENV_AGENT, REPO_ROOT / "agent" / "requirements.txt")
    setup_venv(VENV_CLIENT, REPO_ROOT / "client" / "requirements.txt")
    print("\n✅ All virtual environments and dependencies are ready!")


def print_menu():
    """Print the main menu."""
    print("\n" + "="*60)
    print("VOICE COMMANDER LAUNCHER")
    print("="*60)
    print("1. Launch Cloud Service (FastAPI server)")
    print("2. Launch Agent (keyboard/mouse injector)")
    print("3. Launch Streaming Client (mic → intents)")
    print("4. Setup All (create venvs + install dependencies)")
    print("5. Quick Start (setup + instructions)")
    print("0. Exit")
    print("="*60)


def quick_start():
    """Setup and show quick start instructions."""
    setup_all()
    print("\n" + "="*60)
    print("QUICK START INSTRUCTIONS")
    print("="*60)
    print("\nTo run Voice Commander locally, open 3 terminals:\n")
    print("Terminal 1 (Cloud):")
    print("  python launcher.py")
    print("  Choose option 1\n")
    print("Terminal 2 (Agent - run as Administrator):")
    print("  python launcher.py")
    print("  Choose option 2\n")
    print("Terminal 3 (Streaming Client):")
    print("  python launcher.py")
    print("  Choose option 3\n")
    print("Then speak: 'spacebar', 'cut', 'copy', 'paste', etc.")
    print("\nOr for EC2 deployment, see DEPLOY.md")
    print("="*60)


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Command-line mode
        cmd = sys.argv[1].lower()
        if cmd == "cloud":
            launch_cloud()
        elif cmd == "agent":
            launch_agent()
        elif cmd == "client":
            mode = sys.argv[2] if len(sys.argv) > 2 else "gaming"
            server = sys.argv[3] if len(sys.argv) > 3 else None
            profile = sys.argv[4] if len(sys.argv) > 4 else None
            launch_client(mode, server, profile)
        elif cmd == "setup":
            setup_all()
        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python launcher.py [cloud|agent|client|setup]")
            sys.exit(1)
        return

    # Interactive mode
    while True:
        print_menu()
        try:
            choice = input("\nChoose an option: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nExiting...")
            break

        if choice == "1":
            launch_cloud()
        elif choice == "2":
            launch_agent()
        elif choice == "3":
            print("\nStreaming Client Options:")
            mode = input("  Mode (gaming/transcription) [gaming]: ").strip() or "gaming"
            server = input("  Server URL [ws://localhost:8000/ws/stream]: ").strip() or None
            profile = input("  Profile (e.g., 'premiere') [default]: ").strip() or None
            launch_client(mode, server, profile)
        elif choice == "4":
            setup_all()
        elif choice == "5":
            quick_start()
        elif choice == "0":
            print("\nExiting...")
            break
        else:
            print("\n❌ Invalid choice. Please try again.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted. Exiting...")
        sys.exit(0)
