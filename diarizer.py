"""
diarizer.py - Moduł rozpoznawania i separacji mówców (Speaker Diarization)
oparty na akustycznej analizie tonu głosu (częstotliwości podstawowej F0) oraz barwy (Spectral Centroid).

Rozróżnia:
1. "Ja" – ruch z mikrofonu (100% pewności, sprzętowe źródło wejściowe)
2. "Uczestnicy" – ruch z głośników (WASAPI Loopback):
   - Uczestnik 1, Uczestnik 2, Uczestnik 3... rozróżniani na podstawie tonu i tembru głosu.
"""

import numpy as np
import scipy.signal
import logging
import time

logger = logging.getLogger("SpeakerDiarizer")

class SpeakerCluster:
    def __init__(self, speaker_id: str, pitch: float, centroid: float):
        self.speaker_id = speaker_id
        self.pitch = pitch
        self.centroid = centroid
        self.samples_count = 1
        self.last_active_time = time.time()
        self.total_utterance_time = 0.0

    def update(self, pitch: float, centroid: float, duration: float):
        # Aktualizacja adaptacyjna z wygładzaniem wykładniczym (EMA)
        alpha = 0.35
        if pitch > 0:
            self.pitch = (1 - alpha) * self.pitch + alpha * pitch
        if centroid > 0:
            self.centroid = (1 - alpha) * self.centroid + alpha * centroid
        self.samples_count += 1
        self.last_active_time = time.time()
        self.total_utterance_time += duration

class AudioToneDiarizer:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.clusters: list[SpeakerCluster] = []
        self._next_participant_index = 1
        self.last_external_speaker = None
        self.last_external_time = 0.0

    def extract_voice_features(self, audio: np.ndarray) -> tuple[float, float]:
        """
        Ekstrahuje częstotliwość podstawową głosu F0 (Hz) oraz centroid widmowy (Hz).
        Działa na oknach 40-50ms z uśrednieniem po ramkach dźwięcznych (voiced frames).
        """
        if audio is None or len(audio) < self.sample_rate * 0.15:
            return 0.0, 0.0

        sr = self.sample_rate
        frame_len = int(sr * 0.04)  # 40 ms okno
        hop_len = int(sr * 0.02)    # 20 ms krok
        
        pitches = []
        centroids = []

        num_frames = (len(audio) - frame_len) // hop_len
        if num_frames <= 0:
            return 0.0, 0.0

        # Badamy zakres częstotliwości ludzkiej mowy: 75 Hz (niski męski) do 360 Hz (wysoki kobiecy/dziecięcy)
        min_lag = int(sr / 360.0)
        max_lag = int(sr / 75.0)

        for i in range(min(num_frames, 35)):  # Maksymalnie 35 ramek dla minimalnego narzutu CPU
            frame = audio[i * hop_len : i * hop_len + frame_len]
            # Sprawdzenie energii ramki (czy to mowa, a nie cisza)
            rms = np.sqrt(np.mean(frame**2))
            if rms < 0.02:
                continue

            # Okienkowanie Hamminga
            w_frame = frame * np.hamming(len(frame))

            # Autokorelacja
            corr = scipy.signal.correlate(w_frame, w_frame, mode='full')
            corr = corr[len(corr) // 2 :]

            if max_lag < len(corr):
                search_slice = corr[min_lag:max_lag]
                peak_idx = np.argmax(search_slice) + min_lag
                peak_val = corr[peak_idx]
                zero_val = corr[0] if corr[0] > 0 else 1e-6

                # Weryfikacja dźwięczności (Voiced frame)
                if (peak_val / zero_val) > 0.30:
                    pitch_hz = sr / float(peak_idx)
                    if 75 <= pitch_hz <= 360:
                        pitches.append(pitch_hz)

            # Centroid widmowy (jasność/tembr)
            fft_mag = np.abs(np.fft.rfft(w_frame))
            freqs = np.fft.rfftfreq(len(w_frame), 1.0 / sr)
            sum_mag = np.sum(fft_mag)
            if sum_mag > 1e-6:
                centroid = np.sum(freqs * fft_mag) / sum_mag
                centroids.append(centroid)

        avg_pitch = float(np.median(pitches)) if pitches else 0.0
        avg_centroid = float(np.mean(centroids)) if centroids else 0.0
        return avg_pitch, avg_centroid

    def identify_participant(self, audio: np.ndarray, duration_s: float = 1.0) -> str:
        """
        Klasyfikuje zewnętrzny segment audio (z loopbacku) do uczestnika:
        Uczestnik 1, Uczestnik 2, itd.
        """
        pitch, centroid = self.extract_voice_features(audio)
        now = time.time()

        # Jeśli segment jest zbyt krótki lub szeptany (brak wyraźnego F0)
        if pitch <= 0.0:
            # Jeśli minęło mniej niż 1.2s od ostatniej wypowiedzi zewnętrznej, kontynuujemy poprzedniego
            if self.last_external_speaker and (now - self.last_external_time < 1.2):
                return self.last_external_speaker
            # Jeśli mamy zarejestrowanego tylko jednego uczestnika
            if len(self.clusters) == 1:
                return self.clusters[0].speaker_id
            return self.last_external_speaker or "Uczestnik 1"

        # Jeśli to pierwszy uczestnik zewnętrzny
        if not self.clusters:
            spk_id = f"Uczestnik {self._next_participant_index}"
            self._next_participant_index += 1
            self.clusters.append(SpeakerCluster(spk_id, pitch, centroid))
            self.last_external_speaker = spk_id
            self.last_external_time = now
            logger.info(f"Wykryto nowego rozmówcę: {spk_id} (Pitch: {pitch:.1f}Hz, Centroid: {centroid:.1f}Hz)")
            return spk_id

        # Porównanie z istniejącymi profilami mówców (znormalizowana odległość euklidesowa)
        best_cluster = None
        best_distance = float('inf')

        for cl in self.clusters:
            # Wagi: ton głosu (pitch) jest najważniejszy (~70%), tembr (centroid) pomocniczy (~30%)
            # Normalizacja: różnica 30 Hz w pitch to istotna zmiana tonu (np. kobieta vs mężczyzna)
            pitch_diff_norm = abs(cl.pitch - pitch) / 35.0
            centroid_diff_norm = abs(cl.centroid - centroid) / 600.0 if centroid > 0 and cl.centroid > 0 else 0.0

            dist = np.sqrt(0.70 * (pitch_diff_norm ** 2) + 0.30 * (centroid_diff_norm ** 2))
            if dist < best_distance:
                best_distance = dist
                best_cluster = cl

        # Próg podziału na nowego uczestnika:
        # Odległość > 1.25 oznacza wyraźnie inny ton głosu
        THRESHOLD_NEW_SPEAKER = 1.25

        if best_distance < THRESHOLD_NEW_SPEAKER and best_cluster is not None:
            best_cluster.update(pitch, centroid, duration_s)
            self.last_external_speaker = best_cluster.speaker_id
            self.last_external_time = now
            return best_cluster.speaker_id
        else:
            # Tworzymy nowego uczestnika
            spk_id = f"Uczestnik {self._next_participant_index}"
            self._next_participant_index += 1
            self.clusters.append(SpeakerCluster(spk_id, pitch, centroid))
            self.last_external_speaker = spk_id
            self.last_external_time = now
            logger.info(f"Wykryto nowego uczestnika zewnętrznego: {spk_id} (Pitch: {pitch:.1f}Hz, Odległość: {best_distance:.2f})")
            return spk_id

    def get_summary(self) -> dict:
        """Zwraca statystyki uczestników spotkania."""
        num_external = len(self.clusters)
        total_participants = 1 + num_external  # 1 to "Ja"

        breakdown = {"Ja": "Mikrofon (gospodarz spotkania)"}
        for cl in self.clusters:
            breakdown[cl.speaker_id] = f"Średni ton: {cl.pitch:.0f} Hz (wypowiedzi: {cl.samples_count})"

        return {
            "total_participants": total_participants,
            "external_count": num_external,
            "has_user": True,
            "breakdown": breakdown
        }

    def reset(self):
        self.clusters = []
        self._next_participant_index = 1
        self.last_external_speaker = None
        self.last_external_time = 0.0
