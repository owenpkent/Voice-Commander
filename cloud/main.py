import asyncio
import json
import os
import time
from typing import Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .models import IntentMessage, Health
from .nlu import nlu_parse
from .asr import StreamSession, b64_pcm16_to_bytes, transcribe_stream_segment, transcribe_file_bytes
from .grammar import text_to_intents

try:
    import boto3  # type: ignore
except Exception:  # pragma: no cover
    boto3 = None  # type: ignore

app = FastAPI(title="Voice Commander Cloud")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        data = json.dumps(message)
        async with self._lock:
            conns = list(self.active_connections)
        to_remove = []
        for connection in conns:
            try:
                await connection.send_text(data)
            except Exception:
                to_remove.append(connection)
        for c in to_remove:
            await self.disconnect(c)


manager = ConnectionManager()


@app.get("/healthz", response_model=Health)
async def healthz():
    return Health(ok=True)


@app.get("/")
async def root():
    return {"message": "Voice Commander server is live!"}


class SimulateIn(BaseModel):
    text: str
    session_id: str | None = None


@app.post("/simulate", response_model=IntentMessage)
async def simulate(payload: SimulateIn):
    msg = nlu_parse(payload.text, session_id=payload.session_id)
    await manager.broadcast(msg.model_dump())
    return msg


@app.websocket("/ws/commands")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Optionally send a hello message
        hello = IntentMessage(
            ts=__import__("time").time(),
            mode="transcription",
            intent="system.hello",
            text="connected",
            payload={},
        )
        await websocket.send_text(json.dumps(hello.model_dump()))

        while True:
            try:
                msg = await websocket.receive_text()
                if msg.strip().lower() == "ping":
                    await websocket.send_text("pong")
            except Exception:
                await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    session = StreamSession()
    profile = "default"
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Control messages
            cmd = payload.get("cmd")
            if cmd == "set_profile":
                val = str(payload.get("value", "default")).strip().lower()
                profile = val or "default"
                await websocket.send_text(json.dumps({"ok": True, "profile": profile}))
                continue

            # Audio frames
            b64 = payload.get("pcm16")
            if not b64:
                continue
            pcm = b64_pcm16_to_bytes(b64)
            session.add_frame(pcm)
            if session.should_process():
                segment = session.read_and_reset()
                text, prob = transcribe_stream_segment(segment)
                intents = text_to_intents(text, profile=profile)
                for intent in intents:
                    await websocket.send_text(json.dumps(intent))
                    # Also broadcast to /ws/commands subscribers for local agents
                    try:
                        await manager.broadcast(intent)
                    except Exception:
                        pass
    except WebSocketDisconnect:
        pass
    except Exception:
        # Do not crash the server due to a single client error
        await asyncio.sleep(0.05)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.post("/batch")
async def batch(file: UploadFile = File(...)):
    data = await file.read()
    text, words = transcribe_file_bytes(data, filename=file.filename)

    # Upload results to S3 if available
    s3_key = None
    bucket = os.getenv("VC_S3_BUCKET", "voice-commander-data-opk")
    if boto3 and bucket:
        try:
            s3 = boto3.client("s3")
            ts = int(time.time())
            s3_key = f"batch/{ts}_{file.filename}.json"
            payload = {"file": file.filename, "text": text, "words": words}
            s3.put_object(Bucket=bucket, Key=s3_key, Body=json.dumps(payload).encode("utf-8"), ContentType="application/json")
        except Exception:
            s3_key = None

    return {"text": text, "words": words, "s3_key": s3_key}
