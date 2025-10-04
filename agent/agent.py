import asyncio
import json
import logging
import os
from pathlib import Path
import sys

import websockets

from . import input_mapper

CONFIG_PATH = Path(__file__).with_name("config.json")


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"server_url": os.getenv("VC_SERVER_URL", "ws://localhost:8000/ws/commands")}


async def run_agent():
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s - %(message)s")
    cfg = load_config()
    server_url = cfg.get("server_url", "ws://localhost:8000/ws/commands")
    backoff = 1

    logging.info(f"Voice Commander Agent starting. Server: {server_url}")

    while True:
        try:
            async with websockets.connect(server_url, ping_interval=20, ping_timeout=20) as ws:
                logging.info("Connected to cloud server.")
                backoff = 1
                async for message in ws:
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        logging.debug("Non-JSON message received; ignoring")
                        continue
                    input_mapper.apply_intent(data)
        except Exception as e:
            logging.warning(f"Connection error: {e}. Retrying in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


if __name__ == "__main__":
    if os.name == "nt" and not os.environ.get("PYTHONIOENCODING"):
        # Hint to run as admin if needed for keyboard control
        sys.stderr.write(
            "Note: On Windows, sending global key events may require running the terminal as Administrator.\n"
        )
    asyncio.run(run_agent())
