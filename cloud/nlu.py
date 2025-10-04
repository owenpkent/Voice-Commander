import time
from typing import Optional
from .models import IntentMessage


COMMAND_MAP = {
    "space": {"intent": "key.press", "payload": {"key": "space"}},
    "spacebar": {"intent": "key.press", "payload": {"key": "space"}},
    "cut": {"intent": "key.combo", "payload": {"combo": ["ctrl", "x"]}},
    "copy": {"intent": "key.combo", "payload": {"combo": ["ctrl", "c"]}},
    "paste": {"intent": "key.combo", "payload": {"combo": ["ctrl", "v"]}},
    "undo": {"intent": "key.combo", "payload": {"combo": ["ctrl", "z"]}},
    "redo": {"intent": "key.combo", "payload": {"combo": ["ctrl", "y"]}},
    "enter": {"intent": "key.press", "payload": {"key": "enter"}},
    "escape": {"intent": "key.press", "payload": {"key": "esc"}},
    "gear up": {"intent": "key.press", "payload": {"key": "page up"}},
    "gear down": {"intent": "key.press", "payload": {"key": "page down"}},
}


def nlu_parse(text: str, session_id: Optional[str] = None) -> IntentMessage:
    cleaned = (text or "").strip().lower()
    ts = time.time()

    if cleaned in COMMAND_MAP:
        mapping = COMMAND_MAP[cleaned]
        return IntentMessage(
            ts=ts,
            mode="command",
            intent=mapping["intent"],
            payload=mapping.get("payload", {}),
            text=cleaned,
            confidence=0.9,
            session_id=session_id,
        )

    # Fallback to transcription mode
    return IntentMessage(
        ts=ts,
        mode="transcription",
        intent="transcript.segment",
        payload={},
        text=cleaned,
        confidence=0.7,
        session_id=session_id,
    )
