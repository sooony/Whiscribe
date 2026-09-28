import re
import threading
import numpy as np
from faster_whisper import WhisperModel
import httpx
import logging

logger = logging.getLogger("Transcriber")

# Predefiniowane wyrażenia regularne do usuwania artefaktów i halucynacji Whisper (np. z filmów YouTube)
HALLUCINATION_PATTERNS = [
    r'\s*\[?[Dd]zięki\s+(bardzo\s+)?za\s+(oglądanie|uwagę|obejrzenie|wysłuchanie)[!\. ]*\]?',
    r'\s*\[?[Dd]ziękuję\s+(bardzo\s+)?za\s+(oglądanie|uwagę|obejrzenie|wysłuchanie)[!\. ]*\]?',
    r'\s*\[?[Dd]ziękujemy\s+(bardzo\s+)?za\s+(oglądanie|uwagę|obejrzenie|wysłuchanie)[!\. ]*\]?',
    r'\s*\[?[Nn]apisy\s+(stworzone|przygotowane|wykonane|tłumaczenie).*?\]?',
    r'\s*\[?[Ss]ubskrybuj(cie)?(\s+mój)?\s+(kanał|profil)[!\. ]*\]?',
    r'\s*\[?[Zz]ostaw\s+(suba|lajka|łapkę\s+w\s+górę)[!\. ]*\]?',
    r'\s*\[?[Dd]o\s+zobaczenia(\s+w\s+(następnym|kolejnym)\s+(filmie|odcinku|materiale|wideo))?[!\. ]*\]?',
    r'\s*\[?[Ii]\s+to\s+by\s+było\s+na\s+tyle[!\. ]*\]?',
    r'\s*\[?[Tt]o\s+wszystko\s+na\s+(dziś|dzisiaj)[!\. ]*\]?',
    r'\s*\[?[Tt]o\s+tyle\s+na\s+(dziś|dzisiaj)[!\. ]*\]?',
    r'\s*\[?[Tt]hank\s+you\s+for\s+watching[!\. ]*\]?',
    r'\s*\[?[Tt]hanks\s+for\s+watching[!\. ]*\]?',
    r'\s*\[?[Ss]ubscribe\s+(to\s+my\s+channel)?[!\. ]*\]?',
    r'\s*\[?[Ss]ee\s+you\s+next\s+time[!\. ]*\]?',
]

def clean_hallucinations(text: str) -> str:
    """
    Oczyszcza transkrybowany tekst z typowych halucynacji modelu Whisper na ciszy/końcówkach:
    - Usuwa outro z YouTube ('Dzięki za oglądanie!', 'Dziękuję za uwagę', 'Subskrybuj kanał').
    - Usuwa doczepione na końcu samotne słowa-halucynacje po kropkach ('...tekst. Koniec.', '...tekst. Dziękuję.').
    - Jeśli całe rozpoznanie to wyłącznie halucynacja, zwraca pusty ciąg.
    """
    if not text:
        return ""
    cleaned = text.strip()

    # 1. Usunięcie znanych fraz outro
    for pat in HALLUCINATION_PATTERNS:
        cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE).strip()

    # 2. Usunięcie doczepionych na końcu samotnych słów-widm i powitań po znakach interpunkcyjnych:
    cleaned = re.sub(
        r'([.!?]\s*)(dzień dobry|cześć|witam|witajcie|dziękuję|dzięki|koniec(\s+filmu|\s+transmisji)?|do widzenia)[.!?\s]*$',
        r'\1',
        cleaned,
        flags=re.IGNORECASE
    ).strip()

    # 3. Jeśli cały tekst był wyłącznie słowem "Koniec" lub outro
    cleaned = re.sub(r'^(koniec(\s+filmu|\s+transmisji)?|dziękuję za oglądanie|dzięki za oglądanie|dziękuję za uwagę|dzięki za uwagę)[.!?\s]*$', '', cleaned, flags=re.IGNORECASE).strip()

    # 4. Usunięcie nadmiarowych spacji
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()

    return cleaned

class Transcriber:
    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self._lock = threading.Lock()
        self.initial_prompt = "Dyktowanie tekstu roboczego, notatek i wiadomości."
        self._init_model()

    def _init_model(self):
        model_size = self.config.get("model_size", "turbo")
        device = self.config.get("device", "cuda")
        compute_type = self.config.get("compute_type", "float16")

        logger.info(f"Ładowanie modelu Whisper: {model_size} na {device} ({compute_type})...")
        try:
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            logger.info("Model Whisper załadowany pomyślnie!")
        except Exception as e:
            logger.error(f"Nie udało się załadować na {device}: {e}. Próbuję fallback na CPU...")
            self.model = WhisperModel(model_size, device="cpu", compute_type="int8")
            logger.info("Model Whisper załadowany na CPU.")

    def transcribe_stream_chunk(self, audio: np.ndarray) -> tuple[list[tuple[str, float]], str]:
        """
        Transkrypcja strumieniowa dla ciągłego dyktowania (greedy decoding z timestampami).
        Działa na buforze bieżącej wypowiedzi (od ostatniego zatwierdzonego segmentu).
        Zwraca:
            completed_segments: lista definitywnie zakończonych zdań/fraz [(tekst, end_time_s)]
            tail_text: bieżący, nadal mówiony fragment zdania
        """
        if audio is None or len(audio) < 16000 * 0.4:
            return [], ""

        max_val = np.max(np.abs(audio)) if len(audio) > 0 else 0.0
        if max_val < 0.025:
            return [], ""

        raw_lang = self.config.get("language", "pl")
        language = None if (not raw_lang or str(raw_lang).lower() in ("auto", "none")) else raw_lang
        chunk_duration = len(audio) / 16000.0

        try:
            with self._lock:
                segments_gen, _ = self.model.transcribe(
                    audio,
                    language=language,
                    beam_size=1,
                    without_timestamps=False,
                    condition_on_previous_text=False,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=250, threshold=0.40, speech_pad_ms=200),
                    no_speech_threshold=0.5,
                    log_prob_threshold=-0.9,
                    compression_ratio_threshold=2.4,
                    initial_prompt=self.initial_prompt
                )
                segments = [s for s in segments_gen if s.no_speech_prob <= 0.45 and s.avg_logprob >= -1.2]
        except Exception as e:
            logger.warning(f"Błąd transkrypcji strumieniowej: {e}")
            return [], ""

        if not segments:
            return [], ""

        completed = []
        tail_text = ""

        # Jeśli model wykrył 2 lub więcej segmentów rozdzielonych pauzami:
        # wszystkie wcześniejsze segmenty są zakończone i gotowe do zatwierdzenia (commit)!
        if len(segments) >= 2:
            for s in segments[:-1]:
                t = clean_hallucinations(s.text.strip())
                if t:
                    completed.append((t, s.end))
            last_seg = segments[-1]
            tail_text = clean_hallucinations(last_seg.text.strip())
            is_ended_by_punct = (chunk_duration - last_seg.end >= 0.30) and any(tail_text.endswith(p) for p in ('.', '!', '?', '...'))
            is_ended_by_silence = (chunk_duration - last_seg.end >= 0.50)
            if is_ended_by_punct or is_ended_by_silence:
                if tail_text:
                    completed.append((tail_text, last_seg.end))
                tail_text = ""
        else:
            s = segments[0]
            text = clean_hallucinations(s.text.strip())
            is_ended_by_punct = (chunk_duration - s.end >= 0.30) and any(text.endswith(p) for p in ('.', '!', '?', '...'))
            is_ended_by_silence = (chunk_duration - s.end >= 0.50)
            if is_ended_by_punct or is_ended_by_silence:
                if text:
                    completed.append((text, s.end))
                tail_text = ""
            else:
                tail_text = text

        return completed, tail_text

    def transcribe_fast(self, audio: np.ndarray) -> str:
        """Błyskawiczna transkrypcja do podglądu na żywo (greedy decoding, beam_size=1)."""
        if audio is None or len(audio) < 16000 * 0.4:
            return ""

        # Odrzuć ciszę/szum otoczenia bez obciążania GPU i bez ryzyka halucynacji
        max_val = np.max(np.abs(audio)) if len(audio) > 0 else 0.0
        if max_val < 0.03:
            return ""

        raw_lang = self.config.get("language", "pl")
        language = None if (not raw_lang or str(raw_lang).lower() in ("auto", "none")) else raw_lang
        try:
            with self._lock:
                segments, _ = self.model.transcribe(
                    audio,
                    language=language,
                    beam_size=1,
                    without_timestamps=True,
                    condition_on_previous_text=False,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=300, threshold=0.5),
                    no_speech_threshold=0.5,
                    log_prob_threshold=-0.9,
                    compression_ratio_threshold=2.4,
                    initial_prompt=self.initial_prompt
                )
                texts = [segment.text for segment in segments if segment.no_speech_prob <= 0.45]
                raw_fast = " ".join(texts).strip()
                return clean_hallucinations(raw_fast)
        except Exception as e:
            logger.warning(f"Błąd szybkiej transkrypcji: {e}")
            return ""

    def transcribe(self, audio: np.ndarray) -> str:
        """Transkrybuje tablicę audio float32 (16kHz) na tekst z pełną dokładnością i filtrem halucynacji."""
        if audio is None or len(audio) < 16000 * 0.3:  # poniżej 0.3s ignorujemy
            return ""

        # Odetnij zbędny ogon ciszy przed transkrypcją (eliminuje halucynacje Whisper na wygasaniu głosu)
        from recorder import AudioRecorder
        audio = AudioRecorder.trim_trailing_silence(audio, sample_rate=16000, keep_tail_s=0.35)

        # Jeśli nagranie zawiera wyłącznie ciszę poniżej progu słyszalności mowy
        max_val = np.max(np.abs(audio)) if len(audio) > 0 else 0.0
        if max_val < 0.012:
            logger.info("Pominięto transkrypcję – brak energii mowy w buforze audio.")
            return ""

        raw_lang = self.config.get("language", "pl")
        language = None if (not raw_lang or str(raw_lang).lower() in ("auto", "none")) else raw_lang
        
        try:
            with self._lock:
                segments, info = self.model.transcribe(
                    audio,
                    language=language,
                    beam_size=5,
                    without_timestamps=True,
                    vad_filter=True,  # automatyczne odfiltrowanie ciszy (Silero VAD)
                    vad_parameters=dict(min_silence_duration_ms=600, threshold=0.35, speech_pad_ms=250),
                    no_speech_threshold=0.5,
                    log_prob_threshold=-0.9,
                    compression_ratio_threshold=2.4,
                    condition_on_previous_text=False,
                    initial_prompt=self.initial_prompt
                )
                valid_texts = []
                for s in segments:
                    t = s.text.strip()
                    if not t:
                        continue
                    if s.no_speech_prob > 0.45 or s.avg_logprob < -1.1:
                        logger.debug(f"Odrzucono podejrzany segment (no_speech={s.no_speech_prob:.2f}): '{t}'")
                        continue
                    valid_texts.append(t)
                raw_text = " ".join(valid_texts).strip()



        except Exception as e:
            logger.error(f"Błąd głównej transkrypcji: {e}", exc_info=True)
            return ""

        # Oczyszczenie tekstu z typowych halucynacji (outro YouTube, samotne 'Koniec', 'Dziękuję' na końcu)
        raw_text = clean_hallucinations(raw_text)

        if not raw_text:
            return ""

        # Opcjonalny post-processing przez LLM
        if self.config.get("use_llm", False) and self.config.get("llm_api_key"):
            cleaned_text = self._post_process_with_llm(raw_text)
            return clean_hallucinations(cleaned_text) if cleaned_text else raw_text

        return raw_text

    def _post_process_with_llm(self, text: str) -> str:
        """Opcjonalna korekta językowa przez LLM (Gemini, Groq lub inny)."""
        provider = self.config.get("llm_provider", "gemini").lower()
        api_key = self.config.get("llm_api_key", "").strip()
        system_prompt = self.config.get("llm_system_prompt", "")

        if not api_key:
            return text

        try:
            if provider == "gemini":
                # Google Gemini API
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.config.get('llm_model', 'gemini-2.0-flash')}:generateContent?key={api_key}"
                payload = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": f"{system_prompt}\n\nTekst do poprawy:\n{text}"}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 1000
                    }
                }
                with httpx.Client(timeout=4.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "").strip()
            
            elif provider in ("groq", "openai"):
                # OpenAI-compatible API (Groq, OpenAI, etc.)
                base_url = "https://api.groq.com/openai/v1" if provider == "groq" else "https://api.openai.com/v1"
                headers = {"Authorization": f"Bearer {api_key}"}
                payload = {
                    "model": self.config.get("llm_model", "llama-3.3-70b-versatile" if provider == "groq" else "gpt-4o-mini"),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.1
                }
                with httpx.Client(timeout=4.0) as client:
                    resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            return choices[0].get("message", {}).get("content", "").strip()

        except Exception as e:
            logger.warning(f"Błąd korekty LLM: {e}. Zwracam surowy tekst.")

        return text
