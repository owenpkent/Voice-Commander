import os
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext
import time
import wave

import numpy as np
import sounddevice as sd

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # We'll check at runtime and show a helpful message


class Recorder:
    def __init__(self, samplerate: int = 16000, channels: int = 1, dtype: str = "int16"):
        self.samplerate = samplerate
        self.channels = channels
        self.dtype = dtype
        self._frames = []
        self._recording = False
        self._thread = None
        self._stream = None

    def _callback(self, indata, frames, time_info, status):
        if status:
            # You could surface this in the UI if desired
            print(f"Audio status: {status}")
        # Append a copy to avoid referencing the memory after callback returns
        self._frames.append(indata.copy())

    def start(self):
        if self._recording:
            return
        # Clear previous frames
        self._frames = []
        # Try to determine a reasonable default samplerate
        if not self.samplerate:
            try:
                default_sr = int(sd.query_devices(kind='input')['default_samplerate'])
                self.samplerate = default_sr
            except Exception:
                self.samplerate = 16000
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
                        sd.sleep(100)
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
        # Concatenate frames into one numpy array
        audio = np.concatenate(self._frames, axis=0)
        return audio

    def write_wav(self, path: str, audio: np.ndarray):
        # Ensure int16 samples if dtype is int16
        sampwidth = 2 if self.dtype == "int16" else 2
        with wave.open(path, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(sampwidth)
            wf.setframerate(self.samplerate)
            wf.writeframes(audio.tobytes())


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Whisper Transcriber")
        self.root.geometry("640x480")

        self.recorder = Recorder()
        self.audio_path = os.path.join(os.getcwd(), "latest.wav")

        # UI Elements
        self.btn_frame = tk.Frame(root)
        self.btn_frame.pack(fill=tk.X, padx=10, pady=10)

        self.record_btn = tk.Button(self.btn_frame, text="● Record", fg="#b00000", command=self.start_recording)
        self.record_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(self.btn_frame, text="■ Stop", state=tk.DISABLED, command=self.stop_recording)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.transcribe_btn = tk.Button(self.btn_frame, text="Transcribe", state=tk.DISABLED, command=self.transcribe)
        self.transcribe_btn.pack(side=tk.LEFT, padx=5)

        self.copy_btn = tk.Button(self.btn_frame, text="Copy Text", state=tk.DISABLED, command=self.copy_text)
        self.copy_btn.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="Ready")
        self.status_lbl = tk.Label(root, textvariable=self.status_var, anchor="w")
        self.status_lbl.pack(fill=tk.X, padx=10)

        self.text = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=20)
        self.text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def set_status(self, msg: str):
        self.status_var.set(msg)
        self.root.update_idletasks()

    def start_recording(self):
        try:
            self.text.delete("1.0", tk.END)
            self.copy_btn.config(state=tk.DISABLED)
            self.transcribe_btn.config(state=tk.DISABLED)
            self.record_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.set_status("Recording... Press Stop when done.")
            self.recorder.start()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start recording:\n{e}")
            self.record_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.set_status("Ready")

    def stop_recording(self):
        try:
            audio = self.recorder.stop()
            self.stop_btn.config(state=tk.DISABLED)
            self.record_btn.config(state=tk.NORMAL)
            if audio is None or len(audio) == 0:
                self.set_status("No audio captured. Try again.")
                return
            # Write WAV
            self.recorder.write_wav(self.audio_path, audio)
            self.set_status(f"Saved: {self.audio_path}")
            self.transcribe_btn.config(state=tk.NORMAL)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop/save recording:\n{e}")
            self.set_status("Ready")

    def _ensure_openai(self):
        if OpenAI is None:
            raise RuntimeError(
                "The 'openai' package is not installed. Run: pip install -r requirements.txt"
            )
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Set it in your environment before transcribing."
            )

    def transcribe(self):
        try:
            self._ensure_openai()
            if not os.path.exists(self.audio_path):
                messagebox.showwarning("No audio", "Record audio first.")
                return
            self.transcribe_btn.config(state=tk.DISABLED)
            self.set_status("Transcribing with OpenAI Whisper...")

            def _do_transcribe():
                try:
                    client = OpenAI()
                    with open(self.audio_path, "rb") as f:
                        result = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=f,
                        )
                    text = getattr(result, "text", None) or str(result)
                    self.text.delete("1.0", tk.END)
                    self.text.insert(tk.END, text)
                    self.copy_btn.config(state=tk.NORMAL)
                    self.set_status("Transcription complete.")
                except Exception as e:
                    messagebox.showerror("Transcription Error", str(e))
                    self.set_status("Ready")
                finally:
                    self.transcribe_btn.config(state=tk.NORMAL)

            threading.Thread(target=_do_transcribe, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.set_status("Ready")
            self.transcribe_btn.config(state=tk.NORMAL)

    def copy_text(self):
        try:
            content = self.text.get("1.0", tk.END).strip()
            if not content:
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.set_status("Copied to clipboard.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy text:\n{e}")


def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
