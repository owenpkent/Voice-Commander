import argparse
import asyncio
import base64
import json
import signal
import time
import math
from array import array
from typing import Optional

import websockets

try:
    import sounddevice as sd  # type: ignore
except Exception as e:
    raise RuntimeError("sounddevice is required. Install with: pip install sounddevice") from e


STREAM_SR = 16000
SAMPLE_WIDTH = 2  # 16-bit
CHUNK_MS_DEFAULT = 20


async def producer(ws: websockets.WebSocketClientProtocol, q: asyncio.Queue, show_levels: bool, show_stats: bool):
    last_ts = time.monotonic()
    sent = 0
    while True:
        chunk = await q.get()
        if chunk is None:
            break
        if show_levels:
            # Compute RMS in dBFS for 16-bit PCM
            samples = array('h')
            samples.frombytes(chunk)
            if len(samples):
                rms = math.sqrt(sum(s*s for s in samples) / len(samples))
                db = 20 * math.log10(max(rms, 1e-9) / 32767.0 + 1e-12)
                # Simple VU meter
                level = max(min(int((db + 60) / 3), 20), 0)  # map roughly -60..0 dB to 0..20
                bar = '#' * level + '-' * (20 - level)
                print(f"\rMic: [{bar}] {db:6.1f} dBFS", end="", flush=True)
        if show_stats:
            sent += 1
            now = time.monotonic()
            if now - last_ts >= 1.0:
                print(f"\n[client] chunks/sec: {sent}")
                sent = 0
                last_ts = now
        b64 = base64.b64encode(chunk).decode("ascii")
        await ws.send(json.dumps({"pcm16": b64}))


def start_audio_capture(q: asyncio.Queue, device: Optional[int], chunk_ms: int):
    blocksize = int(STREAM_SR * (chunk_ms / 1000.0))
    loop = asyncio.get_event_loop()

    def callback(indata, frames, time_info, status):  # type: ignore
        if status:
            # Non-fatal warnings
            pass
        # RawInputStream provides bytes-like object already; ensure copy
        chunk = bytes(indata)

        # Enqueue on the event loop thread with backpressure handling.
        def _enqueue():
            try:
                q.put_nowait(chunk)
            except asyncio.QueueFull:
                # Drop oldest and try again to keep the stream responsive
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(chunk)
                except asyncio.QueueFull:
                    # If still full, drop this chunk
                    pass

        loop.call_soon_threadsafe(_enqueue)

    stream = sd.RawInputStream(
        samplerate=STREAM_SR,
        channels=1,
        dtype="int16",
        blocksize=blocksize,
        callback=callback,
        device=device,
    )
    return stream


async def run(server: str, profile: Optional[str], device: Optional[int], chunk_ms: int, mode: str, show_levels: bool, show_stats: bool):
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    stream = None

    mode_label = "GAMING" if mode == "gaming" else "TRANSCRIPTION"
    print(f"[Voice Commander] Mode: {mode_label} | Profile: {profile or 'default'} | Server: {server}")
    print("Speak commands now. Press Ctrl+C to exit.\n")

    try:
        async with websockets.connect(server, ping_interval=20, ping_timeout=20) as ws:
            if profile:
                await ws.send(json.dumps({"cmd": "set_profile", "value": profile}))

            # Start capturing only after the WebSocket is established to prevent backlog
            stream = start_audio_capture(q, device, chunk_ms)
            stream.start()
            prod = asyncio.create_task(producer(ws, q, show_levels, show_stats))

            async for message in ws:
                # Print intents for visibility
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue
                intent_type = data.get("intent", "unknown")
                if mode == "gaming":
                    # Gaming mode: minimal output, focus on responsiveness
                    print(f"→ {intent_type}")
                else:
                    # Transcription mode: full detail
                    print(f"intent: {data}")

            await q.put(None)
            await prod
    finally:
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Voice Commander streaming client")
    parser.add_argument("--server", default="ws://localhost:8000/ws/stream", help="WebSocket server URL")
    parser.add_argument("--profile", default=None, help="Grammar profile, e.g., 'premiere'")
    parser.add_argument("--device", type=int, default=None, help="Input device index (sounddevice)")
    parser.add_argument("--chunk-ms", type=int, default=CHUNK_MS_DEFAULT, help="Chunk size in milliseconds (default 20ms)")
    parser.add_argument("--mode", choices=["gaming", "transcription"], default="gaming", help="Mode: 'gaming' (minimal output, fast) or 'transcription' (full detail)")
    parser.add_argument("--show-levels", action="store_true", help="Show live microphone level VU meter")
    parser.add_argument("--stats", action="store_true", help="Show send rate statistics (chunks/sec)")
    parser.add_argument("--list-devices", action="store_true", help="List audio input devices and exit")
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, loop.stop)
        except NotImplementedError:
            # Windows may not support signal handlers the same way
            pass

    if args.list_devices:
        print("Available audio devices:")
        try:
            import sounddevice as sd  # type: ignore
            print(sd.query_devices())
        except Exception as e:
            print(f"Failed to list devices: {e}")
        return

    try:
        loop.run_until_complete(run(args.server, args.profile, args.device, args.chunk_ms, args.mode, args.show_levels, args.stats))
    finally:
        if not loop.is_closed():
            loop.close()


if __name__ == "__main__":
    main()
