import os
import re
import queue
import threading
import time
import numpy as np
from faster_whisper import WhisperModel
import httpx
import logging
from config import get_app_dir, DEPRECATED_GEMINI_MODELS

logger = logging.getLogger("whiscribe.transcriber")

# Kolejność zapasowa: same lekkie modele (zwykle < 1 s); pełne modele flash "myślą"
# i bywają przeciążone (503/timeout po 25 s), więc nie nadają się do korekty dyktowania.
GEMINI_FALLBACK_MODELS = ("gemini-flash-lite-latest", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite")
# Model, który się przyciął lub był przeciążony, idzie na koniec kolejki na tyle sekund
LLM_SLOW_MODEL_COOLDOWN_S = 300.0
# Po tylu sekundach milczenia pierwszego modelu dosyłamy pozostałe równolegle.
# Przy pytaniu po kolei każdy zawieszony model wypalał cały swój limit (12-14 s),
# więc jedno dyktowanie czekało 30 s, żeby na końcu dostać surowy tekst Whispera.
GEMINI_HEDGE_AFTER_S = 2.0


def llm_time_budget(text: str, is_local: bool) -> float:
    """
    Łączny limit czasu na całą korektę (wszystkie próby i modele zapasowe razem).
    Rośnie z długością tekstu, ale ma twardy sufit – po nim wklejamy surową transkrypcję.
    """
    n = len(text or "")
    if is_local:
        return max(30.0, min(90.0, 30.0 + n / 80.0))
    return max(30.0, min(60.0, 30.0 + n / 200.0))


def _request_timeout(deadline: float, max_attempt_s: float = None):
    """
    Timeout pojedynczego żądania: to, co zostało z budżetu, ale nie więcej niż max_attempt_s,
    żeby jeden zawieszony model nie zjadł całego czasu na modele zapasowe (None = budżet wyczerpany).
    """
    remaining = deadline - time.monotonic()
    if remaining < 1.0:
        return None
    if max_attempt_s:
        remaining = min(remaining, max_attempt_s)
    return httpx.Timeout(connect=min(5.0, remaining), read=remaining, write=min(10.0, remaining), pool=min(5.0, remaining))

# Wyrażenia regularne do usuwania artefaktów i halucynacji modelu Whisper
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
    # 4. Prawa autorskie / zastrzeżone
    r'\b((wszystkie|wielkie)\s+)?prawa\s+zastrzeżone[.!,]?\s*',
    r'\ball\s+rights\s+reserved[.!,]?\s*',
]

def is_valid_segment(s, text: str, audio: np.ndarray = None) -> bool:
    """Sprawdza, czy segment nie jest szumem lub halucynacją."""
    if not text:
        return False
    t = text.strip().lower()
    if not t:
        return False

    # 1. Sprawdzenie pewności modelu akustycznego
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
    max_no_speech = 0.65 if any(cw in t for cw in COMMON_WORDS) else 0.60
    min_logprob = -1.5 if any(cw in t for cw in COMMON_WORDS) else -1.4

    if s.no_speech_prob > max_no_speech or s.avg_logprob < min_logprob:
        return False

    # 2. Fizyczna weryfikacja energii mowy w przedziale czasowym segmentu [s.start : s.end]
    if audio is not None and len(audio) > 0 and hasattr(s, 'start') and hasattr(s, 'end') and s.end > s.start:
        sample_rate = 16000
        start_idx = max(0, int(s.start * sample_rate))
        end_idx = min(len(audio), int(s.end * sample_rate))
        seg_audio = audio[start_idx:end_idx]
        if len(seg_audio) >= int(sample_rate * 0.10):
            frame_len = int(sample_rate * 0.05)
            n_frames = len(seg_audio) // frame_len
            if n_frames > 0:
                frames = seg_audio[:n_frames * frame_len].reshape(n_frames, frame_len)
                rms = np.sqrt(np.mean(frames**2, axis=1))
                active_speech_frames = np.sum(rms > 0.008)
                # Jeśli segment ma tekst (dłuższy niż 2 znaki), ale mniej niż 3 klatki mowy (150ms),
                # to jest to fizycznie niemożliwa halucynacja na kliknięciu/oddechu
                if len(t) > 2 and active_speech_frames < 3:
                    return False

    return True

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

    # 7. Napraw sztuczne wielkie litery w spójnikach wewnątrz zdania (np. 'test I zobaczmy' -> 'test i zobaczmy')
    cleaned = re.sub(r'([^\.\!\?\n])\s+([IAWZOU])\s+', lambda m: m.group(1) + ' ' + m.group(2).lower() + ' ', cleaned)

    # 8. Upewnij się, że pierwszy znak tekstu zaczyna się wielką literą
    cleaned = cleaned.strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]

    return cleaned

class Transcriber:
    def __init__(self, config: dict):
        self.config = config
        self.model = None
        self._lock = threading.Lock()
        self.initial_prompt = None
        # Status ostatniej korekty LLM: None (nie zadano) / 'ok' / 'failed' / 'rejected'
        self.last_llm_status = None
        # Modele, które w tej sesji zwróciły 404 – nie pytamy o nie przy każdym dyktowaniu
        self._dead_llm_models = set()
        # Modele chwilowo przeciążone: {nazwa: time.monotonic() do kiedy omijać}
        self._slow_llm_models = {}
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

        model_revision = "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf" if model_size == "turbo" else None
        model_kwargs = {}
        if model_revision and not (os.path.exists(target) and os.path.isdir(target)):
            model_kwargs["revision"] = model_revision

        logger.info(f"Ładowanie modelu Whisper: {target} (root: {dl_root}) na {device} ({compute_type})...")
        try:
            self.model = WhisperModel(target, device=device, compute_type=compute_type, download_root=dl_root, **model_kwargs)
            logger.info("Model Whisper załadowany pomyślnie!")
        except Exception as e:
            logger.error(f"Nie udało się załadować na {device}: {e}. Próbuję fallback na CPU...")
            self.model = WhisperModel(target, device="cpu", compute_type="int8", download_root=dl_root, **model_kwargs)
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
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=300, speech_pad_ms=200, threshold=0.35),
                    no_speech_threshold=0.6,
                    log_prob_threshold=-1.0,
                    compression_ratio_threshold=2.4,
                    hallucination_silence_threshold=2.0,
                    repetition_penalty=1.15,
                    no_repeat_ngram_size=3,
                    suppress_blank=True,
                    initial_prompt=self.initial_prompt
                )
                segments = [s for s in segments_gen if is_valid_segment(s, s.text, audio)]
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
                    completed.append((tail_text, chunk_duration))
                tail_text = ""
        else:
            s = segments[0]
            text = clean_hallucinations(s.text.strip())
            is_ended_by_punct = (chunk_duration - s.end >= 0.30) and any(text.endswith(p) for p in ('.', '!', '?', '...'))
            is_ended_by_silence = (chunk_duration - s.end >= 0.50)
            if is_ended_by_punct or is_ended_by_silence:
                if text:
                    completed.append((text, chunk_duration))
                tail_text = ""
            else:
                tail_text = text

        return completed, tail_text

    def transcribe_fast(self, audio: np.ndarray) -> str:
        """Szybka transkrypcja do podglądu na żywo (greedy decoding, beam_size=1)."""
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

        # Odetnij zbędną ciszę przed i po mowie (eliminuje wstępne i końcowe halucynacje Whisper)
        from recorder import AudioRecorder
        audio = AudioRecorder.trim_silence(audio, sample_rate=16000, keep_lead_s=0.20, keep_tail_s=0.35)

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
                    if not is_valid_segment(s, t, audio):
                        logger.debug(f"Odrzucono podejrzany segment (no_speech={s.no_speech_prob:.2f}): '{t}'")
                        continue
                    valid_texts.append(t)
                raw_text = " ".join(valid_texts).strip()



        except Exception as e:
            logger.error(f"Błąd głównej transkrypcji: {e}", exc_info=True)
            return ""

        # Oczyszczenie tekstu z typowych halucynacji
        raw_text = clean_hallucinations(raw_text)

        if not raw_text:
            return ""

        # Opcjonalny post-processing przez LLM (chmurowy lub 100% lokalny)
        use_llm = self.config.get("use_llm", False)
        provider = self.config.get("llm_provider", "gemini").lower()
        api_key = self.config.get("llm_api_key", "").strip()
        is_local_llm = provider in ("ollama", "local", "lmstudio")

        if use_llm and (api_key or is_local_llm):
            self.last_llm_status = None
            cleaned_text = self._post_process_with_llm(raw_text)
            if not cleaned_text:
                return raw_text

            cleaned_text = clean_hallucinations(cleaned_text)
            if not self._is_plausible_correction(raw_text, cleaned_text):
                self.last_llm_status = 'rejected'
                return raw_text
            return cleaned_text

        return raw_text

    @staticmethod
    def _is_plausible_correction(raw_text: str, corrected: str) -> bool:
        """
        Zabezpieczenie przed utratą treści przy korekcie LLM.

        Korekta zastępuje tekst, który trafia do okna użytkownika, więc odpowiedź modelu
        musi mieć porównywalną objętość. Odrzucamy wynik, gdy model uciął wypowiedź
        (limit tokenów), streścił ją albo odpowiedział na jej treść zamiast ją poprawić.
        """
        if not corrected:
            return False

        raw_words = len(raw_text.split())
        new_words = len(corrected.split())

        # Kontrola skrócenia ma sens tylko dla dłuższych wypowiedzi – tam grozi ucięcie
        # przez limit tokenów lub streszczenie. W krótkich zdaniach usunięcie samych
        # wypełniaczy ("yyy eee no tak" -> "Tak.") to poprawny, duży skok proporcji.
        if raw_words >= 12 and new_words < raw_words * 0.60:
            logger.warning(
                f"Odrzucono korektę LLM – podejrzana utrata treści "
                f"({raw_words} -> {new_words} słów). Używam surowej transkrypcji."
            )
            return False

        # Model nie powinien rozbudowywać wypowiedzi (dopisywanie, komentarze, odpowiadanie).
        if raw_words >= 4 and new_words > raw_words * 1.8 + 10:
            logger.warning(
                f"Odrzucono korektę LLM – model rozbudował wypowiedź "
                f"({raw_words} -> {new_words} słów). Używam surowej transkrypcji."
            )
            return False

        return True

    def _order_gemini_models(self, models: list) -> list:
        """
        Kolejność pytania: najpierw model, który ostatnio poprawnie odpowiedział, potem te,
        które najdawniej się wysypały. Samo "przeciążony na koniec" nie działało, bo gdy
        wszystkie trzy modele były oznaczone, kolejność nie zmieniała się wcale i ten
        zawieszony dostawał pierwszeństwo przy każdym kolejnym dyktowaniu.
        """
        slow = getattr(self, "_slow_llm_models", None)
        if slow is None:
            slow = self._slow_llm_models = {}
        last_good = getattr(self, "_last_good_llm_model", None)
        now = time.monotonic()

        def klucz(model_name):
            if model_name == last_good and slow.get(model_name, 0.0) <= now:
                return (0, 0.0)
            return (1, slow.get(model_name, 0.0))

        return sorted(models, key=klucz)

    def _gemini_attempt(self, model_name: str, payload: dict, headers: dict, timeout):
        """
        Jedno zapytanie do modelu. Zwraca (status, wartość) i niczego nie loguje ani nie
        zmienia w obiekcie, bo leci z osobnego wątku – stan zmienia tylko wątek główny.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return 'empty', f"brak kandydatów: {str(data.get('promptFeedback', ''))[:200]}"
            parts = candidates[0].get("content", {}).get("parts", [])
            # Modele "myślące" mogą zwrócić kilka części – pomijamy części z myśleniem
            cleaned = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if cleaned:
                return 'ok', cleaned
            return 'empty', f"finishReason={candidates[0].get('finishReason')}"
        if resp.status_code in (401, 403):
            return 'auth', resp.status_code
        if resp.status_code == 404:
            return '404', resp.status_code
        return 'http', (resp.status_code, resp.text[:200])

    def _gemini_correct_hedged(self, models: list, payload: dict, headers: dict, deadline: float, budget: float):
        """
        Pyta pierwszy model, a jeśli ten milczy dłużej niż GEMINI_HEDGE_AFTER_S albo odpada
        od razu, dosyła pozostałe równolegle i bierze pierwszą dobrą odpowiedź. W normalnym
        przypadku (odpowiedź w ~1 s) leci dokładnie jedno zapytanie, jak dotąd.
        Zwraca poprawiony tekst albo None.
        """
        slow = getattr(self, "_slow_llm_models", None)
        if slow is None:
            slow = self._slow_llm_models = {}
        # 12 s na próbę: w szczytach Gemini odpowiada po 7-10 s, przy krótszym limicie
        # korekta odpadała, mimo że model zdążyłby odpowiedzieć.
        attempt_cap = max(12.0, budget * 0.4)
        wyniki = queue.Queue()

        def probuj(model_name, timeout):
            try:
                status, wartosc = self._gemini_attempt(model_name, payload, headers, timeout)
            except Exception as err:
                status, wartosc = 'conn', err
            wyniki.put((model_name, status, wartosc))

        def odpal(model_name) -> bool:
            timeout = _request_timeout(deadline, attempt_cap)
            if timeout is None:
                return False
            threading.Thread(target=probuj, args=(model_name, timeout), daemon=True,
                             name=f"gemini-{model_name}").start()
            return True

        oczekujace = list(models)
        if not oczekujace or not odpal(oczekujace.pop(0)):
            logger.warning("Korekta Gemini: budżet czasu wyczerpany przed pierwszym zapytaniem.")
            return None
        pierwszy = models[0]
        uruchomione = 1
        odpowiedzi = 0
        rozeslane = False

        def rozeslij(powod: str):
            nonlocal rozeslane
            rozeslane = True
            logger.info(f"Korekta Gemini: {powod} – pytam równolegle {', '.join(oczekujace)}.")
            dosylane = 0
            for m in oczekujace:
                if odpal(m):
                    dosylane += 1
            oczekujace.clear()
            return dosylane

        while odpowiedzi < uruchomione:
            pozostalo = deadline - time.monotonic()
            if pozostalo <= 0:
                logger.warning("Korekta Gemini przekroczyła łączny limit czasu.")
                break
            czekaj = pozostalo if rozeslane else min(pozostalo, GEMINI_HEDGE_AFTER_S)
            try:
                model_name, status, wartosc = wyniki.get(timeout=czekaj)
            except queue.Empty:
                if not rozeslane and oczekujace:
                    uruchomione += rozeslij(f"{pierwszy} milczy ponad {GEMINI_HEDGE_AFTER_S:.0f} s")
                continue

            odpowiedzi += 1
            if status == 'ok':
                self._last_good_llm_model = model_name
                return wartosc
            if status == 'auth':
                logger.error(f"Błąd autoryzacji Gemini API (kod {wartosc}): Niepoprawny klucz API!")
                break
            if status == '404':
                self._dead_llm_models.add(model_name)
                logger.warning(f"Model Gemini {model_name} jest niedostępny (404) – pomijam go do końca sesji.")
            elif status == 'empty':
                logger.warning(f"Gemini ({model_name}) zwrócił pustą odpowiedź ({wartosc}).")
            elif status == 'http':
                kod, tresc = wartosc
                if kod == 429 or kod >= 500:
                    slow[model_name] = time.monotonic() + LLM_SLOW_MODEL_COOLDOWN_S
                logger.warning(f"Gemini API ({model_name}) zwróciło kod {kod}: {tresc}")
            else:
                slow[model_name] = time.monotonic() + LLM_SLOW_MODEL_COOLDOWN_S
                logger.warning(f"Błąd połączenia z modelem {model_name}: {type(wartosc).__name__}: {wartosc}")

            if oczekujace and not rozeslane:
                uruchomione += rozeslij(f"{model_name} odpadł")

        return None

    def _post_process_with_llm(self, text: str) -> str:
        """Opcjonalna korekta językowa przez LLM (Gemini, Groq, OpenAI lub lokalną Ollama/LM Studio)."""
        provider = self.config.get("llm_provider", "gemini").lower()
        api_key = self.config.get("llm_api_key", "").strip()
        system_prompt = self.config.get("llm_system_prompt", "")
        is_local = provider in ("ollama", "local", "lmstudio")

        if not api_key and not is_local:
            return text

        try:
            # Jeden budżet czasu na całą korektę: po jego przekroczeniu wklejamy surowy tekst,
            # zamiast wisieć w "przetwarzaniu" przez kolejne próby i modele zapasowe.
            budget = llm_time_budget(text, is_local)
            deadline = time.monotonic() + budget

            if provider == "gemini":
                # Google Gemini API
                primary_model = self.config.get('llm_model', 'gemini-flash-lite-latest')
                candidate_models = [] if primary_model in DEPRECATED_GEMINI_MODELS else [primary_model]
                for fallback_m in GEMINI_FALLBACK_MODELS:
                    if fallback_m not in candidate_models:
                        candidate_models.append(fallback_m)
                candidate_models = [m for m in candidate_models if m not in self._dead_llm_models] or list(GEMINI_FALLBACK_MODELS)
                candidate_models = self._order_gemini_models(candidate_models)

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
                        # Limit musi pomieścić całą wypowiedź z marginesem – przy zbyt niskiej
                        # wartości model ucina tekst, a w trybie podglądu to jego wynik jest wklejany.
                        "maxOutputTokens": max(2048, len(text) // 2 + 1024)
                    }
                }
                headers = {"x-goog-api-key": api_key}
                poprawiony = self._gemini_correct_hedged(candidate_models, payload, headers, deadline, budget)
                if poprawiony:
                    self.last_llm_status = 'ok'
                    return poprawiony

            elif provider in ("groq", "openai", "ollama", "local", "lmstudio"):
                # OpenAI-compatible API (Chmura lub 100% lokalna Ollama / LM Studio)
                if provider == "groq":
                    base_url = "https://api.groq.com/openai/v1"
                    default_model = "llama-3.3-70b-versatile"
                elif provider == "openai":
                    base_url = "https://api.openai.com/v1"
                    default_model = "gpt-4o-mini"
                elif provider == "ollama":
                    base_url = self.config.get("llm_endpoint", "http://localhost:11434/v1").rstrip("/")
                    default_model = "llama3.2"
                else:  # local / lmstudio
                    base_url = self.config.get("llm_endpoint", "http://localhost:1234/v1").rstrip("/")
                    default_model = "local-model"

                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                elif is_local:
                    headers["Authorization"] = "Bearer ollama"

                # Ollama domyślnie ogranicza odpowiedź do ~128 tokenów (num_predict), co ucinałoby
                # dłuższe wypowiedzi. Limit wyliczamy z długości tekstu wejściowego.
                out_tokens = max(2048, len(text) // 2 + 1024)
                payload = {
                    "model": self.config.get("llm_model", default_model),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": text}
                    ],
                    "temperature": 0.1,
                    "max_tokens": out_tokens
                }
                if provider == "ollama":
                    payload["options"] = {"num_predict": out_tokens}

                with httpx.Client(timeout=_request_timeout(deadline)) as client:
                    resp = client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
                    if resp.status_code == 200:
                        data = resp.json()
                        choices = data.get("choices", [])
                        if choices:
                            out = choices[0].get("message", {}).get("content", "").strip()
                            if out:
                                self.last_llm_status = 'ok'
                                return out
                    elif resp.status_code in (401, 403):
                        logger.error(f"Błąd autoryzacji {provider} (kod {resp.status_code}): niepoprawny klucz API!")
                    else:
                        logger.warning(f"{provider} zwrócił kod {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            logger.warning(f"Błąd korekty LLM ({provider}): {e}. Zwracam surowy tekst.")

        self.last_llm_status = 'failed'
        logger.warning("Korekta LLM nie powiodła się – zwracam surową transkrypcję Whispera.")
        return text
