import os
import threading
import time
import wave
from typing import Optional

import numpy as np
import sounddevice as sd

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

    def __init__(self):
        super().__init__()
        self._status = "Ready"
        self._transcript = ""
        self._backend = "API"  # or Local
        self._local_model = "base.en"
        self._level = 0.0
        self._recording = False

        self.audio_path = os.path.join(os.getcwd(), "latest.wav")
        self.session = RecordingSession()

        # Poll audio level from session in UI thread
        self._level_timer = QTimer(self)
        self._level_timer.timeout.connect(self._update_level)
        self._level_timer.start(50)

        # Connect cross-thread signal for transcript updates
        self.transcriptReady.connect(self.setTranscript)

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

    def _update_level(self):
        self._setLevel(self.session.get_level())

    # Slots
    @Slot()
    def startRecording(self):
        if self._recording:
            return
        try:
            self.setTranscript("")
            self._setRecording(True)
            self.setStatus("Recording... Press Stop when done.")
            self.session.start()
        except Exception as e:
            self._setRecording(False)
            self.setStatus(f"Error starting recording: {e}")

    @Slot()
    def stopRecording(self):
        if not self._recording:
            return
        try:
            audio = self.session.stop()
            self._setRecording(False)
            if audio is None or len(audio) == 0:
                self.setStatus("No audio captured. Try again.")
                return
            self.session.write_wav(self.audio_path, audio)
            self.setStatus(f"Saved: {self.audio_path}")
        except Exception as e:
            self.setStatus(f"Error stopping/saving: {e}")

    @Slot()
    def transcribe(self):
        if not os.path.exists(self.audio_path):
            self.setStatus("No audio: record first.")
            return

        backend = self.getBackend()
        self.setStatus("Transcribing (" + backend + ") ...")

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
            except Exception as e:
                self.setStatus(f"Transcription error: {e}")

        threading.Thread(target=_work, daemon=True).start()

    @Slot()
    def copyText(self):
        text = self.getTranscript()
        if not text:
            return
        cb = QGuiApplication.clipboard()
        cb.setText(text)
        self.setStatus("Copied to clipboard.")


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
