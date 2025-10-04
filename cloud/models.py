from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class IntentMessage(BaseModel):
    ts: float
    source: Literal["cloud"] = "cloud"
    mode: Literal["command", "transcription"]
    intent: str
    text: Optional[str] = None
    confidence: Optional[float] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None


class Health(BaseModel):
    ok: bool = True
