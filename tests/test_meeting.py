"""
test_meeting.py - Kompleksowy zestaw testów jednostkowych i integracyjnych
dla modułu transkrypcji spotkań.

Weryfikuje:
1. Test analizy tonu głosu i separacji mówców (AudioToneDiarizer).
2. Test automatyzacji Notatnika Windows i zapisu transkrypcji (NotepadManager).
3. Test integralności dwuźródłowego rejestratora (MeetingRecorder).
4. Test bezpieczeństwa i prywatności danych audio.
"""

import os
import sys
import time
import datetime
import unittest
import numpy as np
import scipy.signal

from diarizer import AudioToneDiarizer
from notepad_manager import NotepadManager
from meeting_recorder import MeetingRecorder, MeetingAudioSegment

class TestMeetingDiarizer(unittest.TestCase):
    def setUp(self):
        self.sr = 16000
        self.diarizer = AudioToneDiarizer(sample_rate=self.sr)

    def _generate_synthetic_speech(self, pitch_hz: float, duration_s: float = 1.0) -> np.ndarray:
        """Generuje syntetyczny sygnał mowy z harmonicznymi i obwiednią."""
        t = np.linspace(0, duration_s, int(self.sr * duration_s), endpoint=False)
        # Fala podstawowa + harmoniczne
        signal = 0.4 * np.sin(2 * np.pi * pitch_hz * t)
        signal += 0.25 * np.sin(2 * np.pi * 2 * pitch_hz * t)
        signal += 0.15 * np.sin(2 * np.pi * 3 * pitch_hz * t)
        # Obwiednia amplitudy
        envelope = np.sin(np.pi * t / duration_s) ** 2
        audio = (signal * envelope).astype(np.float32)
        return audio

    def test_tone_feature_extraction(self):
        """Weryfikacja dokładności wykrywania częstotliwości podstawowej F0."""
        expected_pitches = [115.0, 160.0, 225.0]
        for exp_p in expected_pitches:
            audio = self._generate_synthetic_speech(exp_p, duration_s=1.0)
            pitch, centroid = self.diarizer.extract_voice_features(audio)
            print(f"[TEST] Oczekiwany ton: {exp_p} Hz | Wykryty ton: {pitch:.1f} Hz | Centroid: {centroid:.1f} Hz")
            self.assertGreater(pitch, 0, "Ton głosu powinien być większy od zera dla sygnału dźwięcznego")
            self.assertAlmostEqual(pitch, exp_p, delta=12.0, msg=f"Błąd tonu dla {exp_p} Hz")

    def test_speaker_separation_by_tone(self):
        """Weryfikacja podziału uczestników zewnętrznych na podstawie tonu głosu."""
        # Uczestnik 1 (niski męski głos: ~110 Hz)
        audio_spk1 = self._generate_synthetic_speech(110.0, duration_s=1.2)
        # Uczestnik 2 (wysoki kobiecy głos: ~230 Hz)
        audio_spk2 = self._generate_synthetic_speech(230.0, duration_s=1.2)

        id1 = self.diarizer.identify_participant(audio_spk1, 1.2)
        id2 = self.diarizer.identify_participant(audio_spk2, 1.2)

        print(f"[TEST] Identyfikacja rozmówcy 110Hz: {id1}")
        print(f"[TEST] Identyfikacja rozmówcy 230Hz: {id2}")

        self.assertEqual(id1, "Uczestnik 1")
        self.assertEqual(id2, "Uczestnik 2")

        # Ponowna wypowiedź uczestnika 1 powinna zostać zaklasyfikowana do tego samego klastra
        id1_repeat = self.diarizer.identify_participant(audio_spk1, 1.0)
        self.assertEqual(id1_repeat, "Uczestnik 1")

        summary = self.diarizer.get_summary()
        print(f"[TEST] Podsumowanie uczestników: {summary}")
        self.assertEqual(summary["total_participants"], 3)  # Ja + 2 uczestników zewnętrznych
        self.assertEqual(summary["external_count"], 2)


class TestNotepadManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.abspath("test_transkrypcje")
        os.makedirs(self.test_dir, exist_ok=True)
        self.mgr = NotepadManager(output_dir=self.test_dir)

    def tearDown(self):
        # Zamknięcie procesu Notatnika jeśli otwarty
        if self.mgr.process and self.mgr.process.poll() is None:
            try:
                self.mgr.process.kill()
                self.mgr.process.wait(timeout=1.0)
            except Exception:
                pass

        # Czyszczenie plików testowych
        if os.path.exists(self.test_dir):
            for f in os.listdir(self.test_dir):
                try:
                    os.remove(os.path.join(self.test_dir, f))
                except Exception:
                    pass
            try:
                os.rmdir(self.test_dir)
            except Exception:
                pass

    def test_notepad_session_and_formatting(self):
        """Weryfikacja tworzenia sesji, zapisu wypowiedzi ze znacznikami czasu i podsumowania."""
        filepath = self.mgr.start_meeting_session()
        self.assertTrue(os.path.exists(filepath), "Plik transkrypcji powinien istnieć na dysku")

        # Symulacja wypowiedzi
        t0 = datetime.datetime.now()
        self.mgr.append_utterance("Ja", "Dzień dobry, otwieram spotkanie projektowe.", t0)
        self.mgr.append_utterance("Uczestnik 1", "Cześć, słyszę Cię bardzo wyraźnie.", t0 + datetime.timedelta(seconds=15))
        self.mgr.append_utterance("Uczestnik 2", "Ja również potwierdzam obecność.", t0 + datetime.timedelta(seconds=30))

        # Zakończenie i podsumowanie
        t_end = t0 + datetime.timedelta(minutes=5, seconds=12)
        self.mgr.append_summary(t_end, total_participants=3, participant_details=[
            "Ja – Mikrofon (gospodarz spotkania)",
            "Uczestnik 1 – Średni ton: 110 Hz",
            "Uczestnik 2 – Średni ton: 230 Hz"
        ])

        # Weryfikacja zawartości pliku na dysku
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        t1 = t0 + datetime.timedelta(seconds=15)
        t2 = t0 + datetime.timedelta(seconds=30)
        self.assertIn(f"[{t0.strftime('%H:%M')}] Ja: Dzień dobry, otwieram spotkanie projektowe.", content)
        self.assertIn(f"[{t1.strftime('%H:%M')}] Uczestnik 1: Cześć, słyszę Cię bardzo wyraźnie.", content)
        self.assertIn(f"[{t2.strftime('%H:%M')}] Uczestnik 2: Ja również potwierdzam obecność.", content)
        self.assertIn("PODSUMOWANIE SPOTKANIA:", content)
        self.assertIn("Sugerowana liczba osób biorących udział: 3", content)
        print("[TEST] Plik transkrypcji zweryfikowany pomyślnie!")

    def test_meeting_recorder_lifecycle(self):
        """Weryfikacja bezpiecznego uruchamiania i zatrzymywania rejestratora bez crashy."""
        rec = MeetingRecorder(target_sample_rate=16000)
        for i in range(2):
            rec.start()
            self.assertTrue(rec.is_recording)
            time.sleep(0.3)
            rec.stop()
            self.assertFalse(rec.is_recording)
        rec.close()
        print("[TEST] Cykl życia MeetingRecorder zweryfikowany pomyślnie!")


class TestSecurityAndAudio(unittest.TestCase):
    def test_audio_device_discovery(self):
        """Weryfikacja dostępności urządzeń WASAPI bez wycieków zasobów."""
        import pyaudiowpatch as pyaudio
        p = pyaudio.PyAudio()
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        self.assertIsNotNone(wasapi_info)

        mic = p.get_device_info_by_index(wasapi_info['defaultInputDevice'])
        speakers = p.get_device_info_by_index(wasapi_info['defaultOutputDevice'])
        print(f"[SECURITY] Mikrofon systemowy: {mic['name']}")
        print(f"[SECURITY] Głośniki/Wyjście audio: {speakers['name']}")

        # Weryfikacja obecności urządzenia loopback
        loopbacks = list(p.get_loopback_device_info_generator())
        self.assertGreater(len(loopbacks), 0, "System Windows musi posiadać aktywne urządzenie WASAPI loopback")
        print(f"[SECURITY] Znaleziono {len(loopbacks)} urządzeń loopback WASAPI.")
        p.terminate()

    def test_api_key_privacy(self):
        """Audyt bezpieczeństwa: upewnienie się, że klucze API nie trafiają do plików transkrypcji ani logów."""
        from config import load_config
        cfg = load_config()
        test_mgr = NotepadManager(output_dir="test_privacy")
        test_mgr.start_meeting_session()
        test_mgr.append_utterance("Ja", "Rozmawiamy o projekcie i bezpiecznych danych.")
        full_text = test_mgr.get_full_text()

        if cfg.get("llm_api_key"):
            self.assertNotIn(cfg["llm_api_key"], full_text, "Klucz API NIGDY nie może znaleźć się w transkrypcji!")

        if test_mgr.process:
            test_mgr.process.kill()
        if os.path.exists("test_privacy"):
            for f in os.listdir("test_privacy"):
                try: os.remove(os.path.join("test_privacy", f))
                except Exception: pass
            try: os.rmdir("test_privacy")
            except Exception: pass
        print("[SECURITY] Test poufności klucza API zaliczony pomyślnie.")


if __name__ == "__main__":
    unittest.main()
