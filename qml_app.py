import os
import threading
import time
import wave
from typing import Optional, List

import numpy as np
import sounddevice as sd
import torch
import re
try:
    import keyboard  # for keystroke injection
except Exception:
    keyboard = None

from PySide6.QtCore import QObject, Signal, Slot, Property, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine


class RecordingSession:
    def __init__(self, samplerate: int = 16000, channels: int = 1, dtype: str = "int16"):
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self._frames = []
        self._recording = False
        self._thread: Optional[threading.Thread] = None
        self._stream = None
        self._level = 0.0
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(f"Audio status: {status}")
        self._frames.append(indata.copy())
        # Compute RMS level normalized
        try:
            if indata.dtype == np.int16:
                data = indata.astype(np.float32) / 32768.0
            else:
                data = indata.astype(np.float32)
            rms = float(np.sqrt(np.mean(np.square(data))))
            level = max(0.0, min(1.0, rms * 2.5))  # scale up a bit for visibility
            with self._lock:
                self._level = level
        except Exception:
            pass

    def start(self):
        if self._recording:
            return
        self._frames = []
        self._recording = True

        def _run():
            try:
                with sd.InputStream(
                    channels=self.channels,
                    samplerate=self.samplerate,
                    dtype=self.dtype,
                    callback=self._callback,
                ) as stream:
                    self._stream = stream
                    while self._recording:
                        sd.sleep(50)
            except Exception as e:
                print(f"Recording error: {e}")
                self._recording = False

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self):
        if not self._recording:
            return None
        self._recording = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._stream = None
        if not self._frames:
            return None
        audio = np.concatenate(self._frames, axis=0)
        return audio

    def write_wav(self, path: str, audio: np.ndarray):
        sampwidth = 2 if self.dtype == "int16" else 2
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(self.samplerate)
            wf.writeframes(audio.tobytes())

    def get_level(self) -> float:
        with self._lock:
            return float(self._level)


class Controller(QObject):
    statusChanged = Signal()
    transcriptChanged = Signal()
    backendChanged = Signal()
    localModelChanged = Signal()
    levelChanged = Signal()
    recordingChanged = Signal()
    transcriptReady = Signal(str)
    commandModeChanged = Signal()
    lastCommandChanged = Signal()
    logTextChanged = Signal()
    logReady = Signal(str)
    requireWakeWordChanged = Signal()

    def __init__(self):
        super().__init__()
        self._status = "Ready"
        self._transcript = ""
        self._backend = "API"  # or Local
        self._local_model = "base.en"
        self._level = 0.0
        self._recording = False
        self._command_mode = False
        self._last_command = ""
        self._resume_command_after_recording = False
        self._log_text = ""
        self._require_wake_word = True

        self.audio_path = os.path.join(os.getcwd(), "latest.wav")
        self.session = RecordingSession()
        self._cmd_listener: Optional[_CommandListener] = None

        # Poll audio level from session in UI thread
        self._level_timer = QTimer(self)
        self._level_timer.timeout.connect(self._update_level)
        self._level_timer.start(50)

        # Connect cross-thread signal for transcript updates
        self.transcriptReady.connect(self.setTranscript)
        # Cross-thread logging
        self.logReady.connect(self._appendLog)

    # Properties
    def getStatus(self):
        return self._status

    def setStatus(self, v):
        if self._status != v:
            self._status = v
            self.statusChanged.emit()

    status = Property(str, fget=getStatus, fset=setStatus, notify=statusChanged)

    def getTranscript(self):
        return self._transcript

    def setTranscript(self, v):
        if self._transcript != v:
            self._transcript = v
            self.transcriptChanged.emit()

    transcript = Property(str, fget=getTranscript, fset=setTranscript, notify=transcriptChanged)

    def getBackend(self):
        return self._backend

    def setBackend(self, v):
        v = (v or "API").strip()
        if v not in ("API", "Local"):
            v = "API"
        if self._backend != v:
            self._backend = v
            self.backendChanged.emit()

    backend = Property(str, fget=getBackend, fset=setBackend, notify=backendChanged)

    def getLocalModel(self):
        return self._local_model

    def setLocalModel(self, v):
        v = (v or "base.en").strip()
        if self._local_model != v:
            self._local_model = v
            self.localModelChanged.emit()

    localModel = Property(str, fget=getLocalModel, fset=setLocalModel, notify=localModelChanged)

    def getLevel(self):
        return float(self._level)

    def _setLevel(self, v: float):
        v = max(0.0, min(1.0, float(v)))
        if abs(self._level - v) > 1e-3:
            self._level = v
            self.levelChanged.emit()

    level = Property(float, fget=getLevel, notify=levelChanged)

    def isRecording(self):
        return self._recording

    def _setRecording(self, val: bool):
        if self._recording != val:
            self._recording = val
            self.recordingChanged.emit()

    recording = Property(bool, fget=isRecording, notify=recordingChanged)

    # Command Mode properties
    def getCommandMode(self) -> bool:
        return self._command_mode

    def setCommandMode(self, v: bool):
        v = bool(v)
        if self._command_mode != v:
            self._command_mode = v
            self.commandModeChanged.emit()
            if v:
                self._start_command_listener()
                self.setStatus("Command Mode: listening...")
            else:
                self._stop_command_listener()
                self.setStatus("Command Mode: off")

    commandMode = Property(bool, fget=getCommandMode, fset=setCommandMode, notify=commandModeChanged)

    def getLastCommand(self) -> str:
        return self._last_command

    def setLastCommand(self, v: str):
        if self._last_command != v:
            self._last_command = v
            self.lastCommandChanged.emit()

    lastCommand = Property(str, fget=getLastCommand, notify=lastCommandChanged)

    # Log property and helpers
    def getLogText(self) -> str:
        return self._log_text

    def _setLogText(self, v: str):
        if self._log_text != v:
            self._log_text = v
            self.logTextChanged.emit()

    logText = Property(str, fget=getLogText, notify=logTextChanged)

    def _appendLog(self, msg: str):
        try:
            from datetime import datetime
            ts = datetime.now().strftime('%H:%M:%S')
            line = f"[{ts}] {msg}\n"
        except Exception:
            line = msg + "\n"
        # Keep last ~5000 chars
        new_text = (self._log_text + line)[-5000:]
        self._setLogText(new_text)

    @Slot()
    def clearLog(self):
        self._setLogText("")

    # Require wake word property
    def getRequireWakeWord(self) -> bool:
        return self._require_wake_word

    def setRequireWakeWord(self, v: bool):
        v = bool(v)
        if self._require_wake_word != v:
            self._require_wake_word = v
            self.requireWakeWordChanged.emit()

    requireWakeWord = Property(bool, fget=getRequireWakeWord, fset=setRequireWakeWord, notify=requireWakeWordChanged)

    def _update_level(self):
        level = self.session.get_level()
        if hasattr(self, "_cmd_listener") and self._cmd_listener is not None:
            try:
                level = max(level, self._cmd_listener.get_level())
            except Exception:
                pass
        self._setLevel(level)

    # Slots
    @Slot()
    def startRecording(self):
        if self._recording:
            return
        try:
            self.setTranscript("")
            # Temporarily pause Command Mode to avoid device conflicts
            if self.getCommandMode():
                self._resume_command_after_recording = True
                self._stop_command_listener()
                self.setStatus("Command Mode paused for recording...")
                self.logReady.emit("Command Mode paused (recording started)")
            self._setRecording(True)
            self.setStatus("Recording... Press Stop when done.")
            self.logReady.emit("Recording started")
            self.session.start()
        except Exception as e:
            self._setRecording(False)
            self.setStatus(f"Error starting recording: {e}")
            self.logReady.emit(f"Recording error: {e}")

    @Slot()
    def stopRecording(self):
        if not self._recording:
            return
        try:
            audio = self.session.stop()
            self._setRecording(False)
            self.logReady.emit("Recording stopped")
            if audio is None or len(audio) == 0:
                self.setStatus("No audio captured. Try again.")
                # Resume Command Mode if it was paused
                if self._resume_command_after_recording:
                    self._start_command_listener()
                    self._resume_command_after_recording = False
                    self.logReady.emit("Command Mode resumed (no audio captured)")
                return
            self.session.write_wav(self.audio_path, audio)
            self.setStatus(f"Saved: {self.audio_path}")
            self.logReady.emit(f"Saved WAV: {self.audio_path} ({len(audio)} samples)")
            # Resume Command Mode if it was paused
            if self._resume_command_after_recording:
                self._start_command_listener()
                self._resume_command_after_recording = False
                self.logReady.emit("Command Mode resumed (after recording)")
        except Exception as e:
            self.setStatus(f"Error stopping/saving: {e}")
            # Ensure resume attempt even on error
            if self._resume_command_after_recording:
                try:
                    self._start_command_listener()
                finally:
                    self._resume_command_after_recording = False
            self.logReady.emit(f"Stop/save error: {e}")

    @Slot()
    def transcribe(self):
        if not os.path.exists(self.audio_path):
            self.setStatus("No audio: record first.")
            self.logReady.emit("Transcribe requested but no audio file present")
            return

        backend = self.getBackend()
        self.setStatus("Transcribing (" + backend + ") ...")
        self.logReady.emit(f"Transcribe using backend={backend}")

        def _work():
            try:
                if backend == "API":
                    # Ensure openai
                    from openai import OpenAI  # noqa: F401
                    client = OpenAI()
                    with open(self.audio_path, "rb") as f:
                        result = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                        )
                    text = getattr(result, "text", None) or str(result)
                else:
                    from faster_whisper import WhisperModel
                    model = WhisperModel(self.getLocalModel(), device="cpu", compute_type="int8")
                    segments, info = model.transcribe(self.audio_path, language="en")
                    text = " ".join([seg.text for seg in segments]).strip()
                # Emit to UI thread
                self.transcriptReady.emit(text)
                self.setStatus("Transcription complete.")
                self.logReady.emit(f"Transcription done: {text[:120]}")
            except Exception as e:
                self.setStatus(f"Transcription error: {e}")
                self.logReady.emit(f"Transcription error: {e}")

        threading.Thread(target=_work, daemon=True).start()

    @Slot()
    def copyText(self):
        text = self.getTranscript()
        if not text:
            return
        cb = QGuiApplication.clipboard()
        cb.setText(text)
        self.setStatus("Copied to clipboard.")

    # Command Mode internals
    def _start_command_listener(self):
        if self._cmd_listener and self._cmd_listener.is_running:
            return
        self._cmd_listener = _CommandListener(self)
        self._cmd_listener.start()
        self.logReady.emit("Command Mode listener started")

    def _stop_command_listener(self):
        if self._cmd_listener:
            self._cmd_listener.stop()
            self._cmd_listener = None
            self.logReady.emit("Command Mode listener stopped")

    def _on_command_text(self, text: str):
        # Called from listener thread; route to UI thread via signals
        # Parse and possibly execute keystroke
        self.logReady.emit(f"Heard: {text}")
        ks = parse_command_to_keystroke(text, require_wake=self.getRequireWakeWord())
        if ks:
            self.setLastCommand(ks)
            # Attempt keystroke injection
            try:
                if keyboard is None:
                    raise RuntimeError("keyboard package not available")
                keyboard.send(ks)
                self.setStatus(f"Command executed: {ks}")
                self.logReady.emit(f"Executed keystroke: {ks}")
            except Exception as e:
                self.setStatus(f"Command parse ok but keystroke failed: {ks} ({e})")
                self.logReady.emit(f"Keystroke failed: {ks} ({e})")
        else:
            # Not a command phrase; ignore silently or set status briefly
            self.setStatus("Command Mode: awaiting 'command-...' trigger")
            self.logReady.emit("No command parsed from text")


class _CommandListener:
    """Always-listening VAD-based segmenter (Silero VAD) that calls controller on speech end."""
    def __init__(self, controller: "Controller", samplerate: int = 16000, frame_ms: int = 40):
        self.controller = controller
        self.samplerate = samplerate
        self.channels = 1
        self.dtype = "int16"
        self.frame_ms = frame_ms
        self.frame_bytes = int(samplerate * (frame_ms / 1000.0)) * 2  # bytes for int16 mono
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._stream = None
        self._buf = bytearray()
        self._segment = bytearray()
        self._speech = False
        self._silence_frames = 0
        self._min_speech_frames = int(0.2 / (frame_ms / 1000.0))  # 200ms
        self._max_silence_frames = int(0.5 / (frame_ms / 1000.0))  # 500ms trailing silence
        # Silero VAD thresholds (more sensitive)
        self._th_start = 0.30
        self._th_end = 0.10
        self._level = 0.0
        self._lock = threading.Lock()
        self._vad_model = None
        self._last_state_logged = False
        self._prob_log_counter = 0
        self._vad_window = bytearray()
        self._min_vad_samples = 512  # updated to match sample rate below

    def _update_min_vad_samples(self):
        try:
            self._min_vad_samples = max(512, int(self.samplerate * 0.032))  # at least 32 ms
        except Exception:
            self._min_vad_samples = 512

    def get_level(self) -> float:
        with self._lock:
            return float(self._level)

    def _ensure_model(self):
        if self._vad_model is None:
            # Load Silero VAD model via torch hub (CPU). Requires internet on first run.
            try:
                self._vad_model, _ = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    trust_repo=True,
                )
                self._vad_model.eval()
                self.controller.logReady.emit("Silero VAD model loaded (CPU)")
            except Exception as e:
                self.controller.setStatus(f"Command Mode VAD load error: {e}")
                raise

    def _frame_speech_prob(self, frame_bytes: bytes) -> float:
        # Convert int16 mono bytes to float32 tensor [-1, 1]
        data = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        # Light DC offset removal
        data = data - float(np.mean(data))
        # Clamp to [-1, 1]
        np.clip(data, -1.0, 1.0, out=data)
        wav = torch.from_numpy(data)
        # Apply a small gain and clamp (helps low input levels)
        wav = torch.clamp(wav * 2.0, -1.0, 1.0)
        with torch.no_grad():
            prob = float(self._vad_model(wav, self.samplerate).item())
        return prob

    def _process_frames(self):
        self._ensure_model()
        while len(self._buf) >= self.frame_bytes:
            frame = bytes(self._buf[:self.frame_bytes])
            del self._buf[:self.frame_bytes]
            # grow VAD analysis window and keep only the last min_vad_samples
            self._vad_window.extend(frame)
            min_bytes = self._min_vad_samples * 2
            if len(self._vad_window) > min_bytes:
                # keep tail
                self._vad_window = self._vad_window[-min_bytes:]
            # Speech probability using Silero
            try:
                if len(self._vad_window) < min_bytes:
                    # Not enough audio for VAD yet
                    self.controller.logReady.emit(f"VAD waiting window: {len(self._vad_window)} < {min_bytes} bytes")
                    is_speech = False
                else:
                    speech_prob = self._frame_speech_prob(bytes(self._vad_window))
                is_speech = speech_prob >= (self._th_start if not self._speech else self._th_end)
                # Log every frame until first speech is detected, then every 10 frames
                self._prob_log_counter = (self._prob_log_counter + 1) % 10
                if not self._speech or self._prob_log_counter == 0:
                    if len(self._vad_window) >= min_bytes:
                        self.controller.logReady.emit(f"VAD prob={speech_prob:.2f} speech={self._speech}")
            except Exception as e:
                self.controller.logReady.emit(f"VAD prob error: {e}")
                is_speech = False

            # level from frame
            try:
                data = np.frombuffer(frame, dtype=np.int16).astype(np.float32) / 32768.0
                rms = float(np.sqrt(np.mean(np.square(data))))
                with self._lock:
                    self._level = max(0.0, min(1.0, rms * 2.5))
            except Exception:
                pass

            if is_speech:
                self._segment.extend(frame)
                self._silence_frames = 0
                if not self._speech and len(self._segment) >= self._min_speech_frames * self.frame_bytes:
                    self._speech = True
                    self.controller.logReady.emit("VAD: speech started")
            else:
                if self._speech:
                    self._silence_frames += 1
                    if self._silence_frames >= self._max_silence_frames:
                        # end of utterance
                        seg = bytes(self._segment)
                        self._segment.clear()
                        self._speech = False
                        self._silence_frames = 0
                        if seg:
                            ms = int(len(seg) / 2 / self.samplerate * 1000)
                            self.controller.logReady.emit(f"VAD: speech ended (segment ~{ms} ms)")
                            self._on_segment(seg)
                else:
                    # reset small noise
                    if len(self._segment) > 0 and len(self._segment) < self._min_speech_frames * self.frame_bytes:
                        self._segment.clear()

    def _on_segment(self, pcm_bytes: bytes):
        # Write to temp wav and transcribe with faster-whisper
        try:
            import tempfile
            from faster_whisper import WhisperModel

            # Build wav
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                path = tmp.name
            with wave.open(path, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.samplerate)
                wf.writeframes(pcm_bytes)

        except Exception as e:
            self.controller.setStatus(f"Command Mode error (prepare): {e}")
            return

        # Transcribe
        text = None
        try:
            # Reuse static model on the instance across segments for speed
            if not hasattr(self, "_whisper_model") or self._whisper_model is None:
                model_name = self.controller.getLocalModel()
                self._whisper_model = WhisperModel(model_name, device="cpu", compute_type="int8")
            segments, info = self._whisper_model.transcribe(path, language="en")
            text = " ".join([seg.text for seg in segments]).strip()
        except Exception as e:
            self.controller.setStatus(f"Command Mode error (transcribe): {e}")
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        if text:
            # UI hint about what was heard
            self.controller.setStatus(f"Command heard: {text[:80]}")
            # Lowercase and route
            self.controller._on_command_text(text.lower())

    def _callback(self, indata, frames, time_info, status):
        # Keep callback extremely light to avoid input overflows
        if status:
            print(f"VAD stream status: {status}")
        try:
            self._buf.extend(indata.tobytes())
            # Occasional buffer size log (every ~15 callbacks)
            cnt = getattr(self, "_cb_cnt", 0) + 1
            self._cb_cnt = cnt
            if cnt % 15 == 0:
                self.controller.logReady.emit(f"VAD cb frames={frames} buf_bytes={len(self._buf)}")
        except Exception:
            pass

    def start(self):
        if self.is_running:
            return
        self.is_running = True

        def _run():
            try:
                # Log default device
                try:
                    dev_idx = sd.default.device[0]
                    dev_info = sd.query_devices(dev_idx, 'input') if dev_idx is not None else sd.query_devices(kind='input')
                    self.controller.logReady.emit(
                        f"VAD default input device: {dev_info.get('name','?')} (default_sr={dev_info.get('default_samplerate','?')})"
                    )
                except Exception:
                    pass

                # Try multiple sample rates for broader device compatibility
                tried = []
                last_err = None
                for sr in [self.samplerate, 16000, 48000, 44100]:
                    try:
                        frames_per_buffer = int(sr * (self.frame_ms / 1000.0))  # match frame_ms
                        if frames_per_buffer <= 0:
                            frames_per_buffer = int(sr * 0.03)
                        stream = sd.InputStream(
                            channels=1,
                            samplerate=sr,
                            dtype=self.dtype,
                            blocksize=frames_per_buffer,
                            callback=self._callback,
                            latency='low',
                        )
                        # Opened successfully; adopt this sample rate
                        self.samplerate = sr
                        self.frame_bytes = int(sr * (self.frame_ms / 1000.0)) * 2
                        self._update_min_vad_samples()
                        with stream:
                            self._stream = stream
                            self.controller.logReady.emit(
                                f"VAD stream opened (sr={sr}, block={frames_per_buffer} frames)"
                            )
                            # Main processing loop
                            idle_cnt = 0
                            while self.is_running:
                                # Process accumulated frames outside of the audio callback
                                try:
                                    self._process_frames()
                                except Exception:
                                    pass
                                idle_cnt = (idle_cnt + 1) % 200
                                if idle_cnt == 0:
                                    self.controller.logReady.emit("VAD loop alive")
                                sd.sleep(5)
                        return
                    except Exception as e:
                        last_err = e
                        tried.append(str(sr))
                        self.controller.logReady.emit(f"VAD open failed at sr={sr}: {e}")
                        continue

                # If we get here, all attempts failed
                raise RuntimeError(f"VAD failed to open input stream at tried rates: {', '.join(tried)}; last error: {last_err}")
            except Exception as e:
                self.controller.setStatus(f"Command Mode stream error: {e}")
            finally:
                self.is_running = False
                self._stream = None

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self):
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None


def parse_command_to_keystroke(text: str, require_wake: bool = True) -> Optional[str]:
    """Return a keyboard string like 'ctrl+c' or 'ctrl+alt+delete' from phrases like
    'command control charlie' or 'command alt x-ray'. Returns None if not matched."""
    if not text:
        return None
    t = text.strip().lower().replace("\n", " ")
    # Normalize hyphens and separators then strip punctuation
    for sep in [" - ", "-", "‑", "–", "—", "/", ","]:
        t = t.replace(sep, " ")
    # Remove remaining punctuation
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    # Collapse spaces
    t = re.sub(r"\s+", " ", t).strip()
    parts = [p for p in t.split(" ") if p]
    if not parts:
        return None
    # Allow 'command' anywhere; ignore any words before it unless disabled
    if require_wake:
        if "command" in parts:
            idx = parts.index("command")
            parts = parts[idx + 1 :]
        else:
            return None
    if not parts:
        return None

    # Maps
    nato = {
        "alpha": "a", "bravo": "b", "charlie": "c", "delta": "d", "echo": "e", "foxtrot": "f",
        "golf": "g", "hotel": "h", "india": "i", "juliett": "j", "kilo": "k", "lima": "l",
        "mike": "m", "november": "n", "oscar": "o", "papa": "p", "quebec": "q", "romeo": "r",
        "sierra": "s", "tango": "t", "uniform": "u", "victor": "v", "whiskey": "w",
        "x-ray": "x", "xray": "x", "yankee": "y", "zulu": "z",
    }
    modifiers = {
        "control": "ctrl", "ctrl": "ctrl", "command": "meta", "win": "windows", "windows": "windows",
        "alt": "alt", "option": "alt", "shift": "shift",
    }
    special = {
        "enter": "enter", "return": "enter", "space": "space", "tab": "tab", "escape": "esc", "esc": "esc",
        "backspace": "backspace", "delete": "delete", "home": "home", "end": "end",
        "pageup": "page up", "page": "page", "up": "up", "down": "down", "left": "left", "right": "right",
        "pagedown": "page down",
    }

    # Common letter pronunciations (helps ASR variants)
    letter_pron = {
        "ay": "a", "bee": "b", "be": "b", "cee": "c", "see": "c", "sea": "c", "dee": "d", "de": "d",
        "ee": "e", "e": "e", "ef": "f", "eff": "f", "gee": "g", "g": "g", "aitch": "h", "h": "h",
        "eye": "i", "i": "i", "jay": "j", "j": "j", "kay": "k", "k": "k", "ell": "l", "el": "l",
        "em": "m", "en": "n", "oh": "o", "o": "o", "pee": "p", "pea": "p", "cue": "q", "queue": "q",
        "ar": "r", "are": "r", "ess": "s", "es": "s", "tee": "t", "tea": "t", "you": "u", "u": "u",
        "vee": "v", "we": "w", "double": "w", "w": "w", "ex": "x", "eks": "x", "why": "y", "zed": "z", "zee": "z",
    }

    mods: List[str] = []
    key: Optional[str] = None
    i = 0
    while i < len(parts):
        p = parts[i]
        # Skip filler words
        if p in ("and", "then", "please", "to", "the", "a", "an"):
            i += 1
            continue
        if p in modifiers:
            m = modifiers[p]
            if m == "windows":
                m = "windows"
            if m not in mods:
                mods.append(m)
            i += 1
            continue
        # Two-word tokens like 'page up' or hyphen versions already normalized
        if i + 1 < len(parts) and f"{parts[i]} {parts[i+1]}" in ("page up", "page down"):
            key = f"page {'up' if parts[i+1]=='up' else 'down'}"
            i += 2
            break
        if p in special:
            key = special[p]
            i += 1
            break
        if p in nato:
            key = nato[p]
            i += 1
            break
        # Two-word pronunciation 'double you' -> w
        if i + 1 < len(parts) and parts[i] == "double" and parts[i+1] == "you":
            key = "w"
            i += 2
            break
        if p in letter_pron:
            key = letter_pron[p]
            i += 1
            break
        if len(p) == 1 and p.isalpha():
            key = p
            i += 1
            break
        i += 1

    if key is None:
        return None
    # Build combination string for keyboard library
    combo = "+".join(mods + [key]) if mods else key
    # Normalize meta/windows on Windows -> 'windows'
    combo = combo.replace("meta+", "windows+")
    return combo


def main():
    import sys
    # Ensure Material style for Qt Quick Controls 2
    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Material")
    app = QGuiApplication(sys.argv)

    # Create engine first so we can parent the controller to it,
    # ensuring Python keeps a strong reference and QML sees a valid object.
    engine = QQmlApplicationEngine()

    controller = Controller()
    controller.setParent(engine)
    engine.rootContext().setContextProperty("controller", controller)

    qml_path = os.path.join(os.path.dirname(__file__), "qml", "Main.qml")
    engine.load(QUrl.fromLocalFile(qml_path))

    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
