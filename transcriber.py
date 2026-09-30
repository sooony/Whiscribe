import os
import re
import threading
import numpy as np
from faster_whisper import WhisperModel
import httpx
import logging
from config import get_app_dir

logger = logging.getLogger("Transcriber")

# Predefiniowane wyrażenia regularne do usuwania artefaktów i halucynacji Whisper (filmy YouTube, TikTok, Reels)
# ZACHOWUJĄC wszystkie naturalne powitania, zwroty grzecznościowe i codzienne słowa (np. Cześć, Dzień dobry, Dziękuję, Pozdrawiam, Słuchaj, Na razie).
HALLUCINATION_PATTERNS = [
    # 1. Dziękuję / Dzięki za uwagę / za oglądanie / za wysłuchanie / za obejrzenie (WYŁĄCZNIE z frazą 'za uwagę/oglądanie/itp.')
    r'\b[Dd]ziękuj(emy|[eę])(\s+bardzo|\s+państwu|\s+serdecznie)*\s+za\s+(uwagę|oglądanie|obejrzenie|wysłuchanie)[.!,]?\s*',
    r'\b([Ww]ielkie\s+)?[Dd]zięki(\s+bardzo|\s+serdecznie)*\s+za\s+(uwagę|oglądanie|obejrzenie|wysłuchanie)[.!,]?\s*',

    # 2. Obserwacje / zaobserwujcie / TikTok / Instagram / YouTube
    r'\b((wielkie\s+)?dzięki|(bardzo\s+)?dziękuj[eę])?\s*za\s+obserwac[ji][eęia][.!,]?\s*',
    r'\bzaobserwuj(cie)?(\s+(mój|nasz)?\s*(profil|kanał|konto|tiktoka|tik\s*tok|instagrama?))?(\s+po\s+więcej)?[.!,]?\s*',
    r'\bobserwuj(cie)?\s+(nas|mój\s+profil|nasz\s+profil)(\s+po\s+więcej)?[.!,]?\s*',
    r'\b(zostaw|daj)\s+(suba|lajka|obserwację|łapkę|komentarz)[.!,]?\s*',
    r'\bkliknij\s+(w\s+)?dzwoneczek[.!,]?\s*',
    r'\blink\s+w\s+opis(ie)?[.!,]?\s*',
    r'\budostępnij(cie)?(\s+(ten\s+film|rolkę|materiał))?[.!,]?\s*',
    r'\bwpadajcie\s+na\s+(mojego|naszego)?\s*(tiktoka|tik\s*toka|instagrama|yt|youtube)[.!,]?\s*',
    r'\b(obejrzyj|zobacz)\s+(kolejny|następny)\s+(film|odcinek|materiał)[.!,]?\s*',

    # 3. Outra YouTube i napisy
    r'\b[Nn]apisy\s+(stworzone|przygotowane|wykonane|tłumaczenie).*?([.!?]|$)',
    r'\b[Ss]ubskrybuj(cie)?(\s+mój)?\s+(kanał|profil)[.!,]?\s*',
    r'\b[Zz]ostaw\s+(suba|lajka|łapkę\s+w\s+górę)[.!,]?\s*',
    r'\b[Dd]o\s+zobaczenia\s+w\s+(następnym|kolejnym)\s+(filmie|odcinku|materiale|wideo)[.!,]?\s*',
    r'\b[Mm]iłego\s+oglądania[.!,]?\s*',
    r'\b[Tt]hank\s+you\s+(very\s+much\s+)?for\s+watching[.!,]?\s*',
    r'\b[Tt]hanks\s+for\s+watching[.!,]?\s*',
    r'\b[Ss]ubscribe\s+(to\s+my\s+channel)?[.!,]?\s*',
    r'\b[Ss]ee\s+you\s+next\s+time[.!,]?\s*',
]

def is_valid_segment(s, text: str) -> bool:
    """Sprawdza, czy segment nie jest czystym szumem/halucynacją."""
    if not text:
        return False
    t = text.strip().lower()
    if not t:
        return False

    # Zaufane słowa i zwroty konwersacyjne (np. powitania, pożegnania, krótkie odpowiedzi)
    # Whisper może przypisać im wyższe no_speech_prob z powodu krótkiego czasu trwania w oknie analizy
    COMMON_WORDS = (
        "cześć", "czesc", "hej", "hejka", "siema", "siemanko", "halo",
        "słuchaj", "sluchaj", "słuchajcie", "sluchajcie", "jak się macie", "jak sie macie", "jak się masz", "jak sie masz",
        "witaj", "witajcie", "dzień dobry", "dzien dobry", "dobry wieczór", "dobry wieczor",
        "na razie", "narazie", "do zobaczenia", "do widzenia", "było fajnie", "bylo fajnie",
        "spotkamy się", "spotkamy sie", "będzie okej", "bedzie okej", "trzymaj się", "trzymaj sie",
        "dzięki", "dzieki", "dzięki za informację", "dzieki za informacje", "dzięki za info", "dzieki za info",
        "dziękuję", "dziekuje", "dziękuję bardzo", "dziekuje bardzo", "proszę", "prosze",
        "pozdrawiam", "miłego dnia", "milego dnia", "miłego wieczoru", "milego wieczoru",
        "tak", "nie", "jasne", "dobrze", "super", "dokładnie", "oczywiście"
    )
    if any(cw in t for cw in COMMON_WORDS):
        return s.no_speech_prob < 0.85 and s.avg_logprob > -1.8

    return s.no_speech_prob <= 0.65 and s.avg_logprob >= -1.4

def clean_hallucinations(text: str) -> str:
    """
    Oczyszcza transkrybowany tekst z typowych halucynacji modelu Whisper:
    - Usuwa wtrącenia YouTube/TikTok: 'Zaobserwujcie', 'Dzięki za obserwację', 'Dziękuję za uwagę', 'Subskrybuj kanał'.
    - ZACHOWUJE wszystkie naturalne powitania i zwroty: Cześć, Dzień dobry, Hej, Słuchaj, Na razie, Dziękuję, Pozdrawiam, Miłego dnia.
    - Normalizuje interpunkcję, wielkie litery na początku i spacje.
    """
    if not text:
        return ""
    cleaned = text.strip()

    # 1. Usunięcie znanych fraz halucynacji ze środka i z końca tekstu
    for pat in HALLUCINATION_PATTERNS:
        cleaned = re.sub(pat, ' ', cleaned, flags=re.IGNORECASE)

    # 2. Jeśli cały tekst był wyłącznie artefaktem outro filmu ("Koniec filmu", "I to by było na tyle")
    cleaned = re.sub(r'^(koniec(\s+filmu|\s+transmisji)?)[.!?\s]*$', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'^(i\s+to\s+by\s+było\s+na\s+tyle|to\s+wszystko\s+na\s+(dziś|dzisiaj))[.!?\s]*$', '', cleaned, flags=re.IGNORECASE).strip()

    # 3. Usunięcie nadmiarowych spacji i wiszącej interpunkcji
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    cleaned = re.sub(r'\s+([,.\?!])', r'\1', cleaned)
    cleaned = re.sub(r'([,.\?!])\1+', r'\1', cleaned)

    # 4. Usunięcie samotnych spójników pozostałych po złożonych halucynacjach (np. 'i', 'oraz')
    cleaned = re.sub(r'^(i|a|oraz|więc|ale|lub|albo)[.!?\s]*$', '', cleaned, flags=re.IGNORECASE).strip()

    # 5. Upewnij się, że początek zdania po kropce/pytajniku zaczyna się wielką literą
    cleaned = re.sub(r'([.!?]\s+)([a-ząćęłńóśźż])', lambda m: m.group(1) + m.group(2).upper(), cleaned)

    # 6. Napraw sztuczne wielkie litery po przecinku (np. 'Cześć, Jak się masz' -> 'Cześć, jak się masz')
    cleaned = re.sub(r',\s+([A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+)', lambda m: ', ' + m.group(1).lower() if m.group(1).lower() in ("jak", "co", "gdzie", "kiedy", "dlaczego", "który", "która", "które", "że", "ponieważ", "bo", "ale", "lecz", "czyli", "mam", "masz", "trzymaj", "witam") else m.group(0), cleaned)

    # 7. Upewnij się, że pierwszy znak tekstu zaczyna się wielką literą
    cleaned = cleaned.strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned

class Transcriber:
    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self._lock = threading.Lock()
        self.initial_prompt = (
            "Ciągłe profesjonalne dyktowanie tekstu w języku polskim. "
            "Pisz poprawną polszczyzną, z pełną interpunkcją (kropki, przecinki, pytajniki) oraz wielkimi literami na początku zdań. "
            "Zapisuj dokładnie każde wypowiedziane słowo mówcy, w tym powitania (np. Cześć, Dzień dobry, Hej), "
            "pożegnania (np. Na razie, Do widzenia, Pozdrawiam), krótkie wtrącenia (np. Słuchaj, Tak, Nie) "
            "oraz zwroty grzecznościowe (np. Dziękuję bardzo, Proszę). "
            "Bezwzględnie unikaj jedynie zwrotów z filmów i mediów społecznościowych, takich jak zaobserwuj profil, subskrybuj kanał czy dziękuję za uwagę."
        )
        self._init_model()

    def _init_model(self):
        model_size = self.config.get("model_size", "turbo")
        device = self.config.get("device", "cuda")
        compute_type = self.config.get("compute_type", "float16")

        models_dir = os.path.join(get_app_dir(), "models")
        os.makedirs(models_dir, exist_ok=True)
        local_path = os.path.join(models_dir, model_size)

        if os.path.exists(local_path) and os.path.isdir(local_path):
            target = local_path
            dl_root = None
        else:
            target = model_size
            # Sprawdź czy model jest już w models/ czy w ~/.cache/huggingface/hub
            spec_repo = "mobiuslabsgmbh/faster-whisper-large-v3-turbo" if model_size == "turbo" else f"Systran/faster-whisper-{model_size}"
            hf_hub = os.path.expanduser("~/.cache/huggingface/hub")
            repo_dir = "models--" + spec_repo.replace("/", "--")
            if os.path.exists(os.path.join(hf_hub, repo_dir)):
                dl_root = None
            else:
                dl_root = models_dir

        logger.info(f"Ładowanie modelu Whisper: {target} (root: {dl_root}) na {device} ({compute_type})...")
        try:
            self.model = WhisperModel(target, device=device, compute_type=compute_type, download_root=dl_root)
            logger.info("Model Whisper załadowany pomyślnie!")
        except Exception as e:
            logger.error(f"Nie udało się załadować na {device}: {e}. Próbuję fallback na CPU...")
            self.model = WhisperModel(target, device="cpu", compute_type="int8", download_root=dl_root)
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
                    beam_size=2,
                    without_timestamps=False,
                    condition_on_previous_text=False,
                    vad_filter=False,  # W streamingu sub-segmentów VAD nie może ucinać próbek, bo rozjeżdża timestampy!
                    no_speech_threshold=0.6,
                    log_prob_threshold=-1.0,
                    compression_ratio_threshold=2.4,
                    hallucination_silence_threshold=2.0,
                    repetition_penalty=1.15,
                    no_repeat_ngram_size=3,
                    suppress_blank=True,
                    initial_prompt=self.initial_prompt
                )
                segments = [s for s in segments_gen if is_valid_segment(s, s.text)]
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
                    hallucination_silence_threshold=1.8,
                    repetition_penalty=1.15,
                    suppress_blank=True,
                    initial_prompt=self.initial_prompt
                )
                texts = [segment.text for segment in segments if is_valid_segment(segment, segment.text)]
                raw_fast = " ".join(texts).strip()
                return clean_hallucinations(raw_fast)
        except Exception as e:
            logger.warning(f"Błąd szybkiej transkrypcji: {e}")
            return ""

    def transcribe(self, audio: np.ndarray) -> str:
        """Transkrybuje tablicę audio float32 (16kHz) na tekst z pełną dokładnością i filtrem halucynacji."""
        if audio is None or len(audio) < 16000 * 0.2:  # poniżej 0.2s ignorujemy
            return ""

        # Odetnij zbędny ogon ciszy przed transkrypcją (eliminuje halucynacje Whisper na wygasaniu głosu)
        from recorder import AudioRecorder
        audio = AudioRecorder.trim_trailing_silence(audio, sample_rate=16000, keep_tail_s=0.35)

        # Jeśli nagranie zawiera wyłącznie ciszę poniżej progu słyszalności mowy
        max_val = np.max(np.abs(audio)) if len(audio) > 0 else 0.0
        if max_val < 0.008:
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
                    no_speech_threshold=0.6,
                    log_prob_threshold=-1.0,
                    compression_ratio_threshold=2.4,
                    condition_on_previous_text=False,
                    hallucination_silence_threshold=2.0,
                    repetition_penalty=1.15,
                    no_repeat_ngram_size=3,
                    suppress_blank=True,
                    initial_prompt=self.initial_prompt
                )
                valid_texts = []
                for s in segments:
                    t = s.text.strip()
                    if not t:
                        continue
                    if not is_valid_segment(s, t):
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
