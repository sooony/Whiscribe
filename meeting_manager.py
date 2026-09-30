"""
meeting_manager.py - Główny koordynator sesji transkrypcji spotkań (Meeting Manager).

Łączy:
1. MeetingRecorder (rejestracja Mic + WASAPI Loopback)
2. AudioToneDiarizer (rozpoznawanie mówców i tonu głosu)
3. Transcriber (Whisper CUDA/CPU)
4. NotepadManager (synchronizacja z Notatnikiem Windows w czasie rzeczywistym)
5. Opcjonalną integrację z LLM (Gemini/Groq) dla podsumowania ustaleń
"""

import threading
import queue
import time
import datetime
import os
import logging
from meeting_recorder import MeetingRecorder, MeetingAudioSegment
from diarizer import AudioToneDiarizer
from notepad_manager import NotepadManager
from config import get_app_dir

logger = logging.getLogger("MeetingManager")

class MeetingManager:
    def __init__(self, transcriber, config: dict):
        self.transcriber = transcriber
        self.config = config
        self.recorder = MeetingRecorder(target_sample_rate=16000)
        self.diarizer = AudioToneDiarizer(sample_rate=16000)
        raw_folder = self.config.get("meetings_folder", "transkrypcje")
        output_folder = raw_folder if os.path.isabs(raw_folder) else os.path.join(get_app_dir(), raw_folder)
        self.notepad = NotepadManager(output_dir=output_folder)

        self.is_active = False
        self._worker_thread = None
        self.start_dt = None
        self.on_utterance_callback = None
        self.utterance_count = 0

    def start_meeting(self, on_utterance=None) -> str:
        """Rozpoczyna sesję spotkania: uruchamia Notatnik, nagrywanie i wątek transkrypcji."""
        if self.is_active:
            return self.notepad.filepath

        logger.info("Inicjalizacja nowej sesji spotkania...")
        self.is_active = True
        self.start_dt = datetime.datetime.now()
        self.diarizer.reset()
        self.utterance_count = 0
        self.on_utterance_callback = on_utterance

        # 1. Przygotuj plik i uruchom Notatnik
        filepath = self.notepad.start_meeting_session()

        # 2. Uruchom przechwytywanie audio (Mic + Loopback)
        self.recorder.start()

        # 3. Uruchom wątek przetwarzający i transkrybujący wypowiedzi
        self._worker_thread = threading.Thread(target=self._transcription_worker, daemon=True)
        self._worker_thread.start()

        logger.info(f"Sesja spotkania aktywna! Zapis do: {filepath}")
        return filepath

    def _transcription_worker(self):
        """Pobiera segmenty audio z kolejki, klasyfikuje mówcę i dopisuje do Notatnika."""
        while self.is_active or not self.recorder.speech_queue.empty():
            try:
                segment: MeetingAudioSegment = self.recorder.speech_queue.get(timeout=0.3)
            except queue.Empty:
                continue

            try:
                # 1. Określenie mówcy na podstawie źródła i analizy tonu
                if segment.source == "mic":
                    speaker = "Ja"
                else:
                    if self.config.get("diarization_enabled", True):
                        speaker = self.diarizer.identify_participant(segment.audio, segment.duration_s)
                    else:
                        speaker = "Uczestnik"

                # 2. Transkrypcja fragmentu mowy za pomocą modelu Whisper
                # Używamy transcribe_fast lub transcribe z beam_size=2 dla szybkiego i dokładnego przetwarzania
                text = self._transcribe_segment(segment.audio)

                if text and text.strip():
                    self.utterance_count += 1
                    logger.info(f"[{segment.timestamp.strftime('%H:%M:%S')}] {speaker}: {text}")
                    
                    # 3. Dopisanie do Notatnika i pliku
                    self.notepad.append_utterance(speaker, text, segment.timestamp)

                    # 4. Powiadomienie interfejsu UI (np. widżetu)
                    if self.on_utterance_callback:
                        try:
                            self.on_utterance_callback(speaker, text, segment.timestamp)
                        except Exception:
                            pass

            except Exception as e:
                logger.error(f"Błąd transkrypcji segmentu spotkania: {e}", exc_info=True)

    def _transcribe_segment(self, audio) -> str:
        """Transkrybuje segment audio bez zbędnego narzutu."""
        if audio is None or len(audio) < 16000 * 0.25:
            return ""

        raw_lang = self.config.get("language", "pl")
        language = None if (not raw_lang or str(raw_lang).lower() in ("auto", "none")) else raw_lang

        try:
            with self.transcriber._lock:
                prompt = getattr(self.transcriber, "initial_prompt", "Transkrypcja spotkania biznesowego.")
                segments, _ = self.transcriber.model.transcribe(
                    audio,
                    language=language,
                    beam_size=2,  # Optymalny kompromis szybkości i jakości (nie blokuje GPU)
                    without_timestamps=True,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=250, threshold=0.35, speech_pad_ms=200),
                    no_speech_threshold=0.5,
                    log_prob_threshold=-0.9,
                    condition_on_previous_text=False,
                    initial_prompt=prompt
                )
                texts = [s.text.strip() for s in segments if s.no_speech_prob <= 0.45]
                raw_text = " ".join(texts).strip()
                from transcriber import clean_hallucinations
                return clean_hallucinations(raw_text)
        except Exception as e:
            logger.warning(f"Błąd transkrypcji: {e}")
            return ""

    def stop_meeting(self) -> dict:
        """Zatrzymuje spotkanie, przetwarza pozostałe segmenty i generuje podsumowanie."""
        if not self.is_active:
            return {}

        logger.info("Zatrzymywanie sesji spotkania...")
        self.is_active = False

        # 1. Zatrzymanie strumieni audio
        self.recorder.stop()

        # 2. Odczekanie na przetworzenie ostatnich segmentów z kolejki
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3.0)

        end_dt = datetime.datetime.now()
        duration_s = (end_dt - self.start_dt).total_seconds() if self.start_dt else 0

        # 3. Statystyki uczestników
        diar_summary = self.diarizer.get_summary()
        total_participants = diar_summary.get("total_participants", 1)
        
        participant_details = []
        for spk, desc in diar_summary.get("breakdown", {}).items():
            participant_details.append(f"{spk} – {desc}")

        # 4. Zapis podsumowania do Notatnika
        self.notepad.append_summary(end_dt, total_participants, participant_details)

        # 5. Opcjonalne podsumowanie przez LLM (jeśli skonfigurowano API)
        if self.config.get("meeting_summary_llm", False) and self.config.get("llm_api_key"):
            self._generate_llm_meeting_summary()

        result = {
            "start_time": self.start_dt.strftime("%Y-%m-%d %H:%M:%S") if self.start_dt else "",
            "end_time": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": duration_s,
            "total_participants": total_participants,
            "utterance_count": self.utterance_count,
            "file_path": self.notepad.filepath
        }

        logger.info(f"Spotkanie zakończone. Czas trwania: {duration_s:.1f}s, Uczestnicy: {total_participants}")
        return result

    def _generate_llm_meeting_summary(self):
        """Generuje krótkie podsumowanie kluczowych wniosków ze spotkania za pomocą LLM."""
        full_text = self.notepad.get_full_text()
        if not full_text or len(full_text) < 100:
            return

        api_key = self.config.get("llm_api_key", "").strip()
        if not api_key:
            return

        try:
            import httpx
            provider = self.config.get("llm_provider", "gemini").lower()
            prompt = (
                "Jesteś asystentem biznesowym. Przeanalizuj poniższą transkrypcję spotkania i sporządź zwięzłe podsumowanie:\n"
                "1. Główne tematy rozmowy\n"
                "2. Kluczowe ustalenia i decyzje\n"
                "3. Zadania do wykonania (Action Items)\n\n"
                f"Transkrypcja:\n{full_text}"
            )

            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.get('llm_model', 'gemini-2.0-flash')}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1000}
                }
                with httpx.Client(timeout=8.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            summary_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if summary_text:
                                llm_block = (
                                    "\n"
                                    "----------------------------------------------------------------------\n"
                                    " SYNTETYCZNE PODSUMOWANIE AI (GEMINI):\n"
                                    f"{summary_text.strip()}\n"
                                    "----------------------------------------------------------------------\n"
                                )
                                with self.notepad._lock:
                                    self.notepad._all_text += llm_block
                                    if self.notepad.filepath:
                                        with open(self.notepad.filepath, "a", encoding="utf-8") as f:
                                            f.write(llm_block)
                                            f.flush()
                                    self.notepad._update_notepad_display()
        except Exception as e:
            logger.warning(f"Błąd generowania podsumowania LLM dla spotkania: {e}")

    def get_audio_levels(self) -> tuple[float, float]:
        """Zwraca poziomy głośności (mic_vol, loopback_vol) w skali 0.0 - 1.0."""
        return self.recorder.get_mic_volume(), self.recorder.get_loopback_volume()

    def close(self):
        """Zwalnia wszystkie zasoby spotkania i rejestratora przy wyjściu z aplikacji."""
        if self.is_active:
            try:
                self.stop_meeting()
            except Exception:
                pass
        self.recorder.close()

