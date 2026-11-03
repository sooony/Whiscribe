import math
import sounddevice as sd
import numpy as np
import threading
import time
import logging

logger = logging.getLogger("whiscribe.recorder")

# Zakres dynamiki fali w widżecie (dB RMS): ok. -56 dB to mowa z daleka / półgłosem,
# -14 dB to głośna mowa tuż przy mikrofonie. Skala logarytmiczna, tak jak słyszy ucho.
VOLUME_DB_FLOOR = -56.0
VOLUME_DB_CEIL = -14.0

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
        # Aktualizacja szumu tła przy niskiej energii
        if rms < 0.015:
            if rms < self.noise_floor:
                self.noise_floor = self.noise_floor * 0.95 + rms * 0.05
            else:
                self.noise_floor = min(0.008, self.noise_floor * 0.99 + rms * 0.01)

        # Próg detekcji mowy
        voice_threshold = max(0.0035, self.noise_floor * 1.5)
        if rms > voice_threshold:
            self._last_voice_time = time.time()

    def get_volume_level(self) -> float:
        """
        Zwraca poziom głośności (0.0 - 1.0) do animacji fali.
        Wcześniej skala liniowa x28 nasycała się już przy zwykłej mowie, przez co fala
        była zawsze pełna; teraz cichsza/odległa mowa daje małą falę, a głośna – pełną.
        """
        if not self.is_recording:
            return 0.0
        effective_vol = self.current_volume - self.noise_floor
        if effective_vol <= 1e-6:
            return 0.0
        db = 20.0 * math.log10(effective_vol)
        return max(0.0, min(1.0, (db - VOLUME_DB_FLOOR) / (VOLUME_DB_CEIL - VOLUME_DB_FLOOR)))

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
        Usuwa ciszę z początku i końca nagrania z zachowaniem marginesu.
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

        # Normalizacja amplitudy (bez ucinania ciszy, co zapobiega rozjeżdżaniu się indeksów streamingu)
        max_val = np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0.0
        if max_val >= 0.020 and max_val < 0.75:
            gain = min(3.5, 0.80 / max_val)
            audio_data = np.clip(audio_data * gain, -1.0, 1.0)

        return audio_data

    def get_current_audio(self, start_sample: int = 0) -> np.ndarray:
        """Zwraca nagranie od próbki start_sample (domyślnie całe), bez sklejania wcześniejszych bloków."""
        with self._lock:
            chunks = self._audio_chunks
            cut = 0
            if start_sample > 0:
                skipped, idx = 0, 0
                while idx < len(chunks) and skipped + len(chunks[idx]) <= start_sample:
                    skipped += len(chunks[idx])
                    idx += 1
                chunks = chunks[idx:]
                cut = start_sample - skipped
            if not chunks:
                return np.array([], dtype=np.float32)
            audio_data = np.concatenate(chunks)[cut:]

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
