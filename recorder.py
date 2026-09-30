import sounddevice as sd
import numpy as np
import threading
import time
import logging

logger = logging.getLogger("AudioRecorder")

class AudioRecorder:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.is_recording = False
        self._audio_chunks = []
        self._lock = threading.Lock()
        self._stream = None
        self._last_voice_time = time.time()
        self._start_time = time.time()
        self.current_volume = 0.0
        self.noise_floor = 0.002

    def _audio_callback(self, indata, frames, time_info, status):
        if not self.is_recording:
            return
        
        # indata to tablica numpy (frames, 1) float32
        chunk = indata[:, 0].copy()
        with self._lock:
            self._audio_chunks.append(chunk)
            
        # Obliczenie energii/głośności (RMS) z wygładzaniem
        rms = float(np.sqrt(np.mean(chunk**2))) if len(chunk) > 0 else 0.0
        self.current_volume = self.current_volume * 0.35 + rms * 0.65

        # Adaptacyjny poziom szumu tła:
        # WAŻNE: Aktualizujemy szum tła TYLKO przy niskiej energii (cisza otoczenia poniżej 0.015),
        # aby mowa ludzka nie zawyżała progu szumu i nie wyłączała syntezatora w trakcie mówienia!
        if rms < 0.015:
            if rms < self.noise_floor:
                self.noise_floor = self.noise_floor * 0.95 + rms * 0.05
            else:
                self.noise_floor = min(0.008, self.noise_floor * 0.99 + rms * 0.01)

        # Czuła detekcja mowy człowieka (nie przerywa przy cichszej mowie lub oddechach):
        voice_threshold = max(0.0035, self.noise_floor * 1.5)
        if rms > voice_threshold:
            self._last_voice_time = time.time()

    def get_volume_level(self) -> float:
        """Zwraca znormalizowany poziom głośności (0.0 - 1.0) do animacji syntezatora."""
        if not self.is_recording:
            return 0.0
        effective_vol = max(0.0, self.current_volume - self.noise_floor)
        vol = max(0.0, min(1.0, effective_vol * 28.0))
        return vol

    def start(self):
        with self._lock:
            self._audio_chunks = []
            self.is_recording = True
            now = time.time()
            self._last_voice_time = now
            self._start_time = now
            self.current_volume = 0.0
            self.noise_floor = 0.002

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            callback=self._audio_callback,
            blocksize=int(self.sample_rate * 0.05)  # bloki 50ms
        )
        self._stream.start()

    @staticmethod
    def trim_silence(audio: np.ndarray, sample_rate: int = 16000, keep_lead_s: float = 0.20, keep_tail_s: float = 0.35) -> np.ndarray:
        """
        Odcina zbędną ciszę i szum tła z początku i z końca nagrania (pozostawiając margines na oddech/początek mowy),
        co zapobiega wstępnym i końcowym halucynacjom modelu Whisper.
        """
        if audio is None or len(audio) < sample_rate * 0.5:
            return audio

        frame_len = int(sample_rate * 0.05)  # okna 50ms
        n_frames = len(audio) // frame_len
        if n_frames < 4:
            return audio

        frames = audio[:n_frames * frame_len].reshape(n_frames, frame_len)
        rms = np.sqrt(np.mean(frames**2, axis=1))

        noise_level = np.percentile(rms, 25)
        speech_thresh = max(0.006, noise_level * 1.8)

        active_indices = np.where(rms > speech_thresh)[0]
        if len(active_indices) == 0:
            return np.array([], dtype=np.float32)

        first_active_frame = active_indices[0]
        last_active_frame = active_indices[-1]

        lead_samples = int(keep_lead_s * sample_rate)
        start_point = max(0, first_active_frame * frame_len - lead_samples)

        tail_samples = int(keep_tail_s * sample_rate)
        end_point = min(len(audio), (last_active_frame + 1) * frame_len + tail_samples)

        return audio[start_point:end_point]

    trim_trailing_silence = trim_silence

    def stop(self) -> np.ndarray:
        self.is_recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        with self._lock:
            if not self._audio_chunks:
                return np.array([], dtype=np.float32)
            audio_data = np.concatenate(self._audio_chunks)
            self._audio_chunks = []

        # 1. Obcięcie wstępnej i końcowej ciszy przed wzmocnieniem
        audio_data = self.trim_silence(audio_data, sample_rate=self.sample_rate, keep_lead_s=0.20, keep_tail_s=0.35)

        # 2. Inteligentna normalizacja głośności
        max_val = np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0.0
        if max_val >= 0.020 and max_val < 0.75:
            gain = min(3.5, 0.80 / max_val)
            audio_data = np.clip(audio_data * gain, -1.0, 1.0)

        return audio_data

    def get_current_audio(self) -> np.ndarray:
        with self._lock:
            if not self._audio_chunks:
                return np.array([], dtype=np.float32)
            audio_data = np.concatenate(self._audio_chunks).copy()

        max_val = np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0.0
        if max_val >= 0.020 and max_val < 0.75:
            gain = min(3.5, 0.80 / max_val)
            audio_data = np.clip(audio_data * gain, -1.0, 1.0)
        return audio_data

    def reset_buffer(self):
        with self._lock:
            self._audio_chunks = []

    @property
    def seconds_since_last_voice(self) -> float:
        return time.time() - self._last_voice_time
