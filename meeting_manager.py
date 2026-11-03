"""
meeting_manager.py - Koordynator sesji transkrypcji spotkań.
Zarządza nagrywaniem (mikrofon + loopback), diarizacją, transkrypcją i zapisem.
"""

import threading
import queue
import time
import datetime
import os
import re
import logging
import numpy as np
from meeting_recorder import MeetingRecorder, MeetingAudioSegment
from diarizer import AudioToneDiarizer
from notepad_manager import NotepadManager
from config import get_app_dir

logger = logging.getLogger("whiscribe.meeting")

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
        self.recent_utterances = []  # Bufor ostatnich wypowiedzi do deduplikacji echa akustycznego

    def start_meeting(self, on_utterance=None) -> str:
        """Rozpoczyna sesję spotkania: uruchamia Notatnik, nagrywanie i wątek transkrypcji."""
        if self.is_active:
            return self.notepad.filepath

        logger.info("Inicjalizacja nowej sesji spotkania...")
        self.is_active = True
        self.start_dt = datetime.datetime.now()
        self.diarizer.reset()
        self.utterance_count = 0
        self.recent_utterances.clear()
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
                    if hasattr(self.diarizer, "update_user_voice"):
                        self.diarizer.update_user_voice(segment.audio)
                else:
                    if self.config.get("diarization_enabled", True):
                        speaker = self.diarizer.identify_participant(segment.audio, segment.duration_s)
                    else:
                        speaker = "Uczestnik"

                # 2. Transkrypcja fragmentu mowy za pomocą modelu Whisper
                text = self._transcribe_segment(segment.audio)

                if text and text.strip():
                    norm_text = re.sub(r'[^\w\s]', '', text).lower().strip()

                    # Sprawdzenie czy segment z mikrofonu nie jest echem akustycznym wypowiedzi z głośników (loopback)
                    if segment.source == "mic":
                        is_echo = False
                        now_ts = segment.timestamp
                        for past_src, past_spk, past_text, past_norm, past_ts in reversed(self.recent_utterances[-8:]):
                            if past_src == "loopback" and abs((now_ts - past_ts).total_seconds()) < 4.0:
                                words_mic = set(norm_text.split())
                                words_loop = set(past_norm.split())
                                if words_mic and words_loop:
                                    intersection = words_mic.intersection(words_loop)
                                    overlap_ratio = len(intersection) / min(len(words_mic), len(words_loop))
                                    if overlap_ratio >= 0.45 or norm_text in past_norm or past_norm in norm_text:
                                        # Bez treści: log spotkania nie jest kopią transkryptu, ten leci do pliku.
                                        logger.info(f"Odrzucono echo akustyczne z mikrofonu ({len(text)} znaków, oryginał od {past_spk}: {len(past_text)} znaków)")
                                        is_echo = True
                                        break
                        if is_echo:
                            continue

                    self.utterance_count += 1
                    # Treść wypowiedzi tylko na DEBUG: transkrypt i tak zapisujemy do pliku
                    # spotkania, a log ma służyć diagnozie, nie być drugą kopią rozmowy.
                    logger.info(f"[{segment.timestamp.strftime('%H:%M:%S')}] {speaker}: {len(text)} znaków")
                    logger.debug(f"[{segment.timestamp.strftime('%H:%M:%S')}] {speaker}: {text}")

                    self.recent_utterances.append((segment.source, speaker, text, norm_text, segment.timestamp))
                    if len(self.recent_utterances) > 30:
                        self.recent_utterances.pop(0)

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
        """Transkrybuje segment audio."""
        if audio is None or len(audio) < 16000 * 0.25:
            return ""

        # Normalizacja amplitudy (loopback / WebRTC)
        max_val = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        if max_val < 0.004:
            return ""
        if max_val < 0.7:
            audio = audio * (0.85 / max_val)
        else:
            audio = audio / max_val * 0.95

        raw_lang = self.config.get("language", "pl")
        language = None if (not raw_lang or str(raw_lang).lower() in ("auto", "none")) else raw_lang

        try:
            from transcriber import clean_hallucinations, is_valid_segment
            with self.transcriber._lock:
                prompt = getattr(self.transcriber, "initial_prompt", None)
                segments, _ = self.transcriber.model.transcribe(
                    audio,
                    language=language,
                    beam_size=3,
                    without_timestamps=True,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=350, threshold=0.30, speech_pad_ms=200),
                    no_speech_threshold=0.60,
                    log_prob_threshold=-1.1,
                    condition_on_previous_text=False,
                    initial_prompt=prompt
                )
                texts = [s.text.strip() for s in segments if s.text and is_valid_segment(s, s.text, audio)]
                raw_text = " ".join(texts).strip()
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

        # 5. Opcjonalne podsumowanie przez LLM (chmura z kluczem API lub serwer lokalny Ollama/LM Studio)
        llm_prov = self.config.get("llm_provider", "gemini").lower()
        is_local_llm = llm_prov in ("ollama", "local", "lmstudio")
        if self.config.get("meeting_summary_llm", False) and (self.config.get("llm_api_key") or is_local_llm):
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
        """Generuje podsumowanie spotkania za pomocą LLM."""
        full_text = self.notepad.get_full_text()
        if not full_text or len(full_text) < 100:
            return

        provider = self.config.get("llm_provider", "gemini").lower()
        api_key = self.config.get("llm_api_key", "").strip()
        is_local = provider in ("ollama", "local", "lmstudio")
        if not api_key and not is_local:
            return

        try:
            import httpx
            prompt = (
                "Jesteś asystentem biznesowym. Przeanalizuj poniższą transkrypcję spotkania i sporządź zwięzłe podsumowanie:\n"
                "1. Główne tematy rozmowy\n"
                "2. Kluczowe ustalenia i decyzje\n"
                "3. Zadania do wykonania (Action Items)\n\n"
                f"Transkrypcja:\n{full_text}"
            )
            summary_text = ""

            if provider == "gemini":
                primary_model = self.config.get('llm_model', 'gemini-flash-latest')
                candidate_models = [primary_model]
                for fb in ("gemini-flash-latest", "gemini-3.8-flash", "gemini-flash-lite-latest"):
                    if fb not in candidate_models:
                        candidate_models.append(fb)
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1000}
                }
                headers = {"x-goog-api-key": api_key}
                with httpx.Client(timeout=12.0) as client:
                    for model_name in candidate_models:
                        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                        try:
                            resp = client.post(url, headers=headers, json=payload)
                            if resp.status_code == 200:
                                data = resp.json()
                                candidates = data.get("candidates", [])
                                if candidates:
                                    summary_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                                    if summary_text:
                                        break
                            elif resp.status_code in (401, 403):
                                logger.error(f"Błąd autoryzacji Gemini API dla podsumowania (kod {resp.status_code})")
                                break
                            else:
                                logger.warning(f"Gemini API ({model_name}) zwróciło kod {resp.status_code}")
                        except Exception as req_err:
                            logger.debug(f"Błąd połączenia Gemini ({model_name}): {req_err}")
                            continue
            else:
                if provider == "groq":
                    base_url = "https://api.groq.com/openai/v1"
                    default_model = "llama-3.3-70b-versatile"
                elif provider == "openai":
                    base_url = "https://api.openai.com/v1"
                    default_model = "gpt-4o-mini"
                elif provider == "ollama":
                    base_url = self.config.get("llm_endpoint", "http://localhost:11434/v1").rstrip("/")
                    default_model = "llama3.2"
                else:
                    base_url = self.config.get("llm_endpoint", "http://localhost:1234/v1").rstrip("/")
                    default_model = "local-model"

                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                elif is_local:
                    headers["Authorization"] = "Bearer ollama"

                payload = {
                    "model": self.config.get("llm_model", default_model),
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2
                }
                with httpx.Client(timeout=12.0 if is_local else 8.0) as client:
                    resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            summary_text = choices[0].get("message", {}).get("content", "")

            if summary_text:
                provider_tag = "LOKALNE AI (OLLAMA)" if provider == "ollama" else ("LOKALNE AI" if is_local else f"AI ({provider.upper()})")
                llm_block = (
                    "\n"
                    "----------------------------------------------------------------------\n"
                    f" SYNTETYCZNE PODSUMOWANIE {provider_tag}:\n"
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
            logger.warning(f"Błąd generowania podsumowania LLM dla spotkania ({provider}): {e}")

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

