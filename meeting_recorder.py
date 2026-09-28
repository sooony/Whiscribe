"""
meeting_recorder.py - Dwuźródłowy rejestrator audio dla spotkań (Meeting Mode)
oparty na Windows WASAPI (pyaudiowpatch).

Jednocześnie przechwytuje:
1. Mikrofon użytkownika (źródło wewnętrzne -> "Ja")
2. WASAPI Loopback głośników (źródło zewnętrzne -> Teams/Zoom/Meet/System -> "Uczestnicy")

Dzieli mowę na segmenty VAD i przesyła do kolejki transkrypcji w czasie rzeczywistym.
Zastosowano architekturę bezblokującą ze stream_callback oraz kolejkami asynchronicznymi,
co zapobiega kolizjom wątków i awariom procesu przy zatrzymywaniu spotkania.
"""

import threading
import queue
import time
import datetime
import logging
from dataclasses import dataclass
import numpy as np
import scipy.signal
import pyaudiowpatch as pyaudio

logger = logging.getLogger("MeetingRecorder")

@dataclass
class MeetingAudioSegment:
    source: str  # "mic" lub "loopback"
    audio: np.ndarray  # float32, 16000 Hz, mono
    timestamp: datetime.datetime
    duration_s: float

class MeetingRecorder:
    def __init__(self, target_sample_rate: int = 16000):
        self.target_sample_rate = target_sample_rate
        self.speech_queue = queue.Queue()
        self.is_recording = False
        self._stop_event = threading.Event()

        self.mic_volume = 0.0
        self.loopback_volume = 0.0

        self._pyaudio = None
        self._mic_stream = None
        self._loop_stream = None
        self._mic_raw_queue = queue.Queue()
        self._loop_raw_queue = queue.Queue()
        self._mic_thread = None
        self._loop_thread = None

    def start(self):
        """Uruchamia rejestrację obu strumieni (Mic + Loopback) w asynchronicznym trybie WASAPI."""
        if self.is_recording:
            return

        self.is_recording = True
        self._stop_event.clear()

        # Opróżnij kolejki
        for q in (self.speech_queue, self._mic_raw_queue, self._loop_raw_queue):
            while not q.empty():
                try:
                    q.get_nowait()
                except queue.Empty:
                    break

        if self._pyaudio is None:
            self._pyaudio = pyaudio.PyAudio()

        try:
            wasapi_info = self._pyaudio.get_host_api_info_by_type(pyaudio.paWASAPI)
            mic_dev = self._pyaudio.get_device_info_by_index(wasapi_info['defaultInputDevice'])
            speakers_dev = self._pyaudio.get_device_info_by_index(wasapi_info['defaultOutputDevice'])

            # Wyszukanie urządzenia loopback powiązanego z domyślnymi głośnikami
            loopback_dev = None
            for lb in self._pyaudio.get_loopback_device_info_generator():
                if speakers_dev['name'] in lb['name']:
                    loopback_dev = lb
                    break
            if not loopback_dev:
                loopback_dev = self._pyaudio.get_default_wasapi_loopback()

            logger.info(f"MeetingRecorder: Mikrofon: '{mic_dev['name']}'")
            logger.info(f"MeetingRecorder: Loopback: '{loopback_dev['name']}'")

            # Callback dla strumienia mikrofonu (zero narzutu, czysta kolejka)
            def _mic_callback(in_data, frame_count, time_info, status):
                if in_data and self.is_recording:
                    self._mic_raw_queue.put(in_data)
                return (None, pyaudio.paContinue)

            mic_rate = int(mic_dev['defaultSampleRate'])
            mic_channels = max(1, mic_dev['maxInputChannels'])
            self._mic_stream = self._pyaudio.open(
                format=pyaudio.paFloat32,
                channels=mic_channels,
                rate=mic_rate,
                input=True,
                input_device_index=mic_dev['index'],
                stream_callback=_mic_callback,
                frames_per_buffer=1024
            )

            # Callback dla strumienia loopback
            def _loop_callback(in_data, frame_count, time_info, status):
                if in_data and self.is_recording:
                    self._loop_raw_queue.put(in_data)
                return (None, pyaudio.paContinue)

            loop_rate = int(loopback_dev['defaultSampleRate'])
            loop_channels = max(1, loopback_dev['maxInputChannels'])
            self._loop_stream = self._pyaudio.open(
                format=pyaudio.paFloat32,
                channels=loop_channels,
                rate=loop_rate,
                input=True,
                input_device_index=loopback_dev['index'],
                stream_callback=_loop_callback,
                frames_per_buffer=1024
            )

            # Uruchomienie wątków procesujących audio z kolejek (VAD i podział na wypowiedzi)
            self._mic_thread = threading.Thread(
                target=self._capture_worker,
                args=("mic", self._mic_raw_queue, mic_rate, mic_channels, 0.0045),
                daemon=True
            )
            self._loop_thread = threading.Thread(
                target=self._capture_worker,
                args=("loopback", self._loop_raw_queue, loop_rate, loop_channels, 0.0035),
                daemon=True
            )

            self._mic_thread.start()
            self._loop_thread.start()
            logger.info("MeetingRecorder uruchomiony – nasłuchiwanie obu kanałów...")

        except Exception as e:
            logger.error(f"Błąd inicjalizacji MeetingRecorder: {e}", exc_info=True)
            self.stop()
            raise

    def stop(self):
        """Zatrzymuje nagrywanie i zwalnia strumienie WASAPI bez ubijania instancji PyAudio."""
        if not self.is_recording:
            return

        self.is_recording = False
        self._stop_event.set()

        # 1. Zatrzymanie strumieni asynchronicznych PortAudio
        for stream in (self._mic_stream, self._loop_stream):
            if stream is not None:
                try:
                    if stream.is_active():
                        stream.stop_stream()
                    stream.close()
                except Exception as e:
                    logger.debug(f"Błąd zamykania strumienia: {e}")
        self._mic_stream = None
        self._loop_stream = None

        # 2. Bezpieczne odczekanie na zakończenie wątków czytających z kolejek
        if self._mic_thread and self._mic_thread.is_alive():
            self._mic_thread.join(timeout=1.0)
        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=1.0)
        self._mic_thread = None
        self._loop_thread = None

        self.mic_volume = 0.0
        self.loopback_volume = 0.0
        logger.info("MeetingRecorder zatrzymany pomyślnie.")

    def close(self):
        """Pełne zwolnienie zasobów PyAudio przy wyjściu z aplikacji."""
        self.stop()
        if self._pyaudio is not None:
            try:
                self._pyaudio.terminate()
            except Exception:
                pass
            self._pyaudio = None

    def _resample_to_16k(self, audio: np.ndarray, orig_sr: int) -> np.ndarray:
        """Szybka i precyzyjna konwersja do 16000 Hz."""
        if orig_sr == self.target_sample_rate:
            return audio
        if orig_sr % self.target_sample_rate == 0:
            dec = orig_sr // self.target_sample_rate
            return audio[::dec]

        import math
        gcd = math.gcd(self.target_sample_rate, orig_sr)
        up = self.target_sample_rate // gcd
        down = orig_sr // gcd
        return scipy.signal.resample_poly(audio, up, down).astype(np.float32)

    def _capture_worker(self, source: str, raw_queue: queue.Queue, orig_rate: int, channels: int, vad_threshold: float):
        """
        Wątek odczytujący próbki audio z kolejki asynchronicznej, analizujący VAD
        i emitujący gotowe segmenty mowy do kolejki transkrypcji.
        """
        speech_chunks = []
        is_speech_active = False
        speech_start_time = None
        last_voice_time = time.time()
        silence_timeout = 0.65  # Pauza 650ms oznacza koniec zdania/segmentu
        max_chunk_sec = 6.5     # Maksymalna długość jednego segmentu

        while not self._stop_event.is_set() or not raw_queue.empty():
            try:
                raw_bytes = raw_queue.get(timeout=0.05)
            except queue.Empty:
                if self._stop_event.is_set():
                    break
                continue

            try:
                # Konwersja na tablicę numpy
                data = np.frombuffer(raw_bytes, dtype=np.float32)
                if channels > 1:
                    data = data.reshape(-1, channels)
                    mono = np.mean(data, axis=1)
                else:
                    mono = data

                # Konwersja do 16kHz
                mono_16k = self._resample_to_16k(mono, orig_rate)

                # Obliczenie energii RMS dla VAD i wskaźnika poziomu
                rms = float(np.sqrt(np.mean(mono_16k**2))) if len(mono_16k) > 0 else 0.0

                if source == "mic":
                    self.mic_volume = self.mic_volume * 0.4 + rms * 0.6
                else:
                    self.loopback_volume = self.loopback_volume * 0.4 + rms * 0.6

                now = time.time()

                if rms > vad_threshold:
                    last_voice_time = now
                    if not is_speech_active:
                        is_speech_active = True
                        speech_start_time = datetime.datetime.now()
                        speech_chunks = []
                    speech_chunks.append(mono_16k)
                elif is_speech_active:
                    speech_chunks.append(mono_16k)

                    elapsed_silence = now - last_voice_time
                    current_duration = sum(len(c) for c in speech_chunks) / self.target_sample_rate

                    if elapsed_silence >= silence_timeout or current_duration >= max_chunk_sec:
                        # Emituj segment mowy do kolejki transkrypcji
                        audio_full = np.concatenate(speech_chunks)
                        # Odrzuć zbyt ciche lub mikroskopijne szumy (< 0.25s)
                        if len(audio_full) >= self.target_sample_rate * 0.25 and np.max(np.abs(audio_full)) >= vad_threshold * 1.5:
                            segment = MeetingAudioSegment(
                                source=source,
                                audio=audio_full,
                                timestamp=speech_start_time or datetime.datetime.now(),
                                duration_s=len(audio_full) / self.target_sample_rate
                            )
                            self.speech_queue.put(segment)

                        # Reset pod kolejną wypowiedź
                        if elapsed_silence >= silence_timeout:
                            is_speech_active = False
                            speech_chunks = []
                        else:
                            speech_start_time = datetime.datetime.now()
                            speech_chunks = []

            except Exception as e:
                logger.debug(f"Błąd przetwarzania próbki {source}: {e}")

        # Na zakończenie: emituj ewentualny pozostały fragment mowy z bufora
        if is_speech_active and speech_chunks:
            try:
                audio_full = np.concatenate(speech_chunks)
                if len(audio_full) >= self.target_sample_rate * 0.25:
                    segment = MeetingAudioSegment(
                        source=source,
                        audio=audio_full,
                        timestamp=speech_start_time or datetime.datetime.now(),
                        duration_s=len(audio_full) / self.target_sample_rate
                    )
                    self.speech_queue.put(segment)
            except Exception as e:
                logger.debug(f"Błąd emitowania końcowego segmentu {source}: {e}")

    def get_mic_volume(self) -> float:
        return min(1.0, self.mic_volume * 25.0)

    def get_loopback_volume(self) -> float:
        return min(1.0, self.loopback_volume * 25.0)

    def get_total_volume(self) -> float:
        return min(1.0, max(self.mic_volume, self.loopback_volume) * 25.0)
