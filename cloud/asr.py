import base64
import io
import os
import time
from functools import lru_cache
from typing import Dict, List, Tuple, Optional

import numpy as np

try:
    import webrtcvad  # type: ignore
except Exception:  # pragma: no cover
    webrtcvad = None  # type: ignore


STREAM_SR = 16000
SAMPLE_WIDTH = 2  # 16-bit PCM
FRAME_MS = 20  # 20ms frames for VAD
FRAME_BYTES = int(STREAM_SR * (FRAME_MS / 1000.0)) * SAMPLE_WIDTH
MIN_BUFFER_SEC = float(os.getenv("VC_STREAM_MIN_SEC", "0.8"))


@lru_cache(maxsize=1)
def _get_stream_model():
    from faster_whisper import WhisperModel  # lazy import

    model_name = os.getenv("VC_STREAM_MODEL", "tiny.en")
    compute_type = os.getenv("VC_STREAM_COMPUTE", "int8")
    device = os.getenv("VC_STREAM_DEVICE", "cpu")
    return WhisperModel(model_name, device=device, compute_type=compute_type)


@lru_cache(maxsize=1)
def _get_batch_model():
    from faster_whisper import WhisperModel  # lazy import

    model_name = os.getenv("VC_BATCH_MODEL", "large-v3")
    compute_type = os.getenv("VC_BATCH_COMPUTE", "int8")
    device = os.getenv("VC_BATCH_DEVICE", "cpu")
    return WhisperModel(model_name, device=device, compute_type=compute_type)


def b64_pcm16_to_bytes(b64: str) -> bytes:
    return base64.b64decode(b64)


def pcm16_to_float32(sig: bytes, sample_rate: int = STREAM_SR) -> np.ndarray:
    arr = np.frombuffer(sig, dtype=np.int16).astype(np.float32) / 32768.0
    return arr


class StreamSession:
    def __init__(self, vad_aggressiveness: int = 2):
        self.buffer = bytearray()
        self.last_voice_ts = time.time()
        self.vad = webrtcvad.Vad(vad_aggressiveness) if webrtcvad else None

    def add_frame(self, pcm16_bytes: bytes) -> None:
        self.buffer.extend(pcm16_bytes)

    def _is_voiced(self, frame: bytes) -> bool:
        if not self.vad or len(frame) < FRAME_BYTES:
            # If VAD not available, assume voiced
            return True
        return self.vad.is_speech(frame, STREAM_SR)

    def should_process(self) -> bool:
        # Process if buffer exceeds threshold seconds
        total_sec = len(self.buffer) / (STREAM_SR * SAMPLE_WIDTH)
        return total_sec >= MIN_BUFFER_SEC

    def read_and_reset(self) -> bytes:
        data = bytes(self.buffer)
        self.buffer.clear()
        return data


def transcribe_stream_segment(pcm16_bytes: bytes) -> Tuple[str, float]:
    """Transcribe a short PCM16 segment and return (text, avg_prob)."""
    model = _get_stream_model()
    audio = pcm16_to_float32(pcm16_bytes)
    # Small segments: enable vad filter in model and beam size low
    segments, info = model.transcribe(
        audio,
        language="en",
        vad_filter=True,
        beam_size=1,
        best_of=1,
        condition_on_previous_text=False,
    )
    text_parts: List[str] = []
    probs: List[float] = []
    for seg in segments:
        if seg.text:
            text_parts.append(seg.text.strip())
        if seg.avg_logprob is not None:
            probs.append(float(seg.avg_logprob))
    text = " ".join([t for t in text_parts if t])
    avg_prob = float(np.exp(np.mean(probs))) if probs else 0.5
    return text, avg_prob


def transcribe_file_bytes(data: bytes, filename: Optional[str] = None) -> Tuple[str, List[Dict]]:
    """Transcribe full file; return (text, words[]). words have word,start,end,prob.

    Handles both raw PCM16 and containerized audio (WAV/FLAC/MP3/...). For containerized formats,
    writes to a temporary file (preserving extension when available) and passes the path to faster-whisper.
    """
    model = _get_batch_model()

    # Try raw PCM16 path first if it looks like bare PCM16
    if len(data) % SAMPLE_WIDTH == 0 and filename is None:
        try:
            audio = pcm16_to_float32(data)
            segments, info = model.transcribe(
                audio,
                language="en",
                vad_filter=True,
                word_timestamps=True,
                beam_size=5,
                best_of=5,
            )
        except Exception:
            segments = []  # fall through to temp-file path
    else:
        segments = []

    if not segments:
        import tempfile
        import pathlib

        suffix = ""
        if filename:
            ext = pathlib.Path(filename).suffix
            if ext:
                suffix = ext
        # default to .wav if unknown
        if not suffix:
            suffix = ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(data)
            tmp.flush()
            segments, info = model.transcribe(
                tmp.name,
                language="en",
                vad_filter=True,
                word_timestamps=True,
                beam_size=5,
                best_of=5,
            )
    all_text: List[str] = []
    words_out: List[Dict] = []
    for seg in segments:
        if seg.text:
            all_text.append(seg.text.strip())
        if getattr(seg, "words", None):
            for w in seg.words:
                words_out.append(
                    {
                        "word": w.word.strip(),
                        "start": float(w.start) if w.start is not None else None,
                        "end": float(w.end) if w.end is not None else None,
                        "prob": float(w.probability) if getattr(w, "probability", None) is not None else None,
                    }
                )
    text = " ".join(all_text)
    return text, words_out
