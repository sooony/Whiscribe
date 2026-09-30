import time
import pyperclip
from pynput.keyboard import Controller, Key

kb = Controller()

def send_backspaces(count: int):
    """Wysyła naciśnięcia klawisza Backspace za pomocą pynput."""
    if count <= 0:
        return
    for _ in range(count):
        kb.tap(Key.backspace)

def send_unicode_string(text: str):
    """Wpisuje tekst (z polskimi znakami) bezpośrednio do aktywnego pola."""
    if not text:
        return
    kb.type(text)

def normalize_word(w: str) -> str:
    """Usuwa znaki interpunkcyjne do bezpiecznego porównywania tożsamości słów."""
    import re
    return re.sub(r'[^\w]', '', w).lower()

class ForwardStreamCommitter:
    """
    Zarządza płynnym wpisywaniem tekstu w czasie rzeczywistym w stylu Windows 11 Voice Typing.
    ZASADA: Wyłącznie wpisywanie w przód (Forward-Only).
    Nigdy nie wysyła naciśnięć Backspace do aktywnego dokumentu użytkownika.
    Zapobiega powielaniu słów, połykaniu tekstu i skakaniu wstecz dzięki dopasowywaniu kotwicowemu (anchor alignment).
    """
    def __init__(self, type_callback=None, safe_margin: int = 2):
        self.type_callback = type_callback or send_unicode_string
        self.safe_margin = max(1, safe_margin)
        self.typed_raw_words = []         # Wszystkie słowa wpisane w całej sesji
        self.typed_norm_words = []        # Znormalizowane słowa z całej sesji
        self.segment_typed_words = []     # Słowa wpisane w bieżącym, niezatwierdzonym segmencie audio
        self.segment_typed_norm = []      # Znormalizowane słowa w bieżącym segmencie audio
        self.last_hypothesis_words = []   # Ostatnia pełna hipoteza Whisper
        self.typed_text = ""              # Całkowity tekst wpisany w całej sesji

    def reset_for_new_segment(self):
        """Resetuje stan dopasowania dla nowego segmentu audio (gdy poprzedni został zatwierdzony w offset)."""
        self.segment_typed_words = []
        self.segment_typed_norm = []
        self.last_hypothesis_words = []

    def _find_continuation_index(self, hyp_norm: list) -> int:
        """
        Znajduje indeks w nowej hipotezie hyp_norm, od którego należy kontynuować wpisywanie.
        Wykorzystuje sekwencyjne dopasowanie kotwic (anchor matching), dzięki czemu drobne korekty
        fonetyczne Whispera na początku zdania (np. 'OK' -> 'Okej' -> 'Ok') nigdy nie powodują
        powielenia i ponownego wpisania już wyemitowanych słów.
        """
        if not self.segment_typed_norm:
            return 0
        M = len(self.segment_typed_norm)
        if not hyp_norm:
            return 0

        # 1. Kotwiczenie dopasowania (anchor matching): badamy sufiksy z offsetem 0, 1, 2
        for offset in range(min(3, M)):
            ref = self.segment_typed_norm[:M - offset] if offset > 0 else self.segment_typed_norm
            for k in range(min(4, len(ref)), 0, -1):
                anchor = ref[-k:]
                matches = []
                for i in range(len(hyp_norm) - k + 1):
                    if hyp_norm[i:i + k] == anchor:
                        matches.append(i + k)
                if matches:
                    best_match = min(matches, key=lambda m: abs(m - (M - offset)))
                    if best_match >= M - offset - 1:
                        return best_match

        # 2. Monotoniczny fallback: nigdy nie cofamy się poniżej liczby już wpisanych słów
        return min(M, len(hyp_norm))

    def _emit_words(self, words_to_type: list):
        if not words_to_type:
            return
        chunk = " ".join(words_to_type) + " "
        self.typed_raw_words.extend(words_to_type)
        norm = [normalize_word(w) for w in words_to_type]
        self.typed_norm_words.extend(norm)
        self.segment_typed_words.extend(words_to_type)
        self.segment_typed_norm.extend(norm)
        self.typed_text += chunk
        self.type_callback(chunk)

    def _feed_words(self, words: list):
        """Pomocnicze wywołanie dla zachowania kompatybilności."""
        if not words:
            return
        norm_words = [normalize_word(w) for w in words]
        cont_idx = self._find_continuation_index(norm_words)
        new_words = words[cont_idx:]
        self._emit_words(new_words)

    def process_hypothesis(self, hyp_text: str):
        """
        Analizuje bieżącą hipotezę Whisper i wpisuje nowo ustabilizowane słowa w przód.
        """
        if not hyp_text or not hyp_text.strip():
            return

        try:
            from transcriber import clean_hallucinations
            hyp_text = clean_hallucinations(hyp_text)
        except Exception:
            pass

        if not hyp_text or not hyp_text.strip():
            return

        current_words = hyp_text.strip().split()
        if not current_words:
            return

        self.last_hypothesis_words = current_words

        # Słowa stabilne to słowa sprzed ogona (ostatnie 1-2 słowa w locie mogą być jeszcze niepewne fonetycznie)
        safe_margin = getattr(self, "safe_margin", 2)
        if len(current_words) > safe_margin:
            stable_words = current_words[:-safe_margin]
            norm_stable = [normalize_word(w) for w in stable_words]
            cont_idx = self._find_continuation_index(norm_stable)
            new_words = stable_words[cont_idx:]
            self._emit_words(new_words)

    def commit_segment(self, segment_text: str):
        """
        Definitywnie zatwierdza cały zakończony segment zdania.
        Wypisuje pozostałe słowa (z zerowym marginesem) i resetuje wskaźnik segmentu.
        """
        if not segment_text or not segment_text.strip():
            return

        try:
            from transcriber import clean_hallucinations
            segment_text = clean_hallucinations(segment_text)
        except Exception:
            pass

        if not segment_text or not segment_text.strip():
            return

        words = segment_text.strip().split()
        norm_words = [normalize_word(w) for w in words]
        cont_idx = self._find_continuation_index(norm_words)
        new_words = words[cont_idx:]
        self._emit_words(new_words)
        self.reset_for_new_segment()

    def finalize(self, final_text: str = ""):
        """
        Kończy dyktowanie – dopisuje pozostałe słowa z ogona wypowiedzi.
        """
        try:
            from transcriber import clean_hallucinations
            if final_text:
                final_text = clean_hallucinations(final_text)
        except Exception:
            pass

        words = final_text.strip().split() if final_text else self.last_hypothesis_words
        if words:
            norm_words = [normalize_word(w) for w in words]
            cont_idx = self._find_continuation_index(norm_words)
            new_words = words[cont_idx:]
            self._emit_words(new_words)
        self.reset_for_new_segment()


def sync_text(old_text: str, new_text: str) -> str:
    """
    Zachowane dla kompatybilności wstecznej.
    """
    if old_text == new_text:
        return old_text

    min_len = min(len(old_text), len(new_text))
    prefix_len = 0
    while prefix_len < min_len and old_text[prefix_len] == new_text[prefix_len]:
        prefix_len += 1

    backspaces = len(old_text) - prefix_len
    to_type = new_text[prefix_len:]

    if backspaces > 30:
        backspaces = 30

    if backspaces > 0:
        send_backspaces(backspaces)
        time.sleep(0.004)

    if to_type:
        send_unicode_string(to_type)

    return new_text

def inject_text(text: str, restore_clipboard: bool = False):
    """
    Wkleja tekst do aktywnego okna przez schowek (Ctrl + V).
    Zawiera pętlę odporności na zablokowanie schowka i zwalnianie klawisza Alt.
    """
    if not text or not text.strip():
        return

    text = text.strip() + " "
    old_clipboard = None
    if restore_clipboard:
        for _ in range(3):
            try:
                old_clipboard = pyperclip.paste()
                break
            except Exception:
                time.sleep(0.02)

    # Kopiowanie do schowka z ponawianiem przy kolizji z menedżerem schowka Windows
    copied = False
    for _ in range(5):
        try:
            pyperclip.copy(text)
            copied = True
            break
        except Exception:
            time.sleep(0.02)

    if not copied:
        # Fallback: bezpośrednie wpisanie znaków jeśli schowek systemowy jest zablokowany
        send_unicode_string(text)
        return

    time.sleep(0.05)

    # Upewnij się, że klawisz Alt nie wisi w systemie (np. po skrócie Ctrl+Alt+D)
    try:
        kb.release(Key.alt)
        kb.release(Key.alt_l)
        kb.release(Key.alt_r)
    except Exception:
        pass

    # Symuluj Ctrl + V za pomocą pynput
    with kb.pressed(Key.ctrl):
        kb.tap('v')

    if restore_clipboard and old_clipboard is not None:
        time.sleep(0.35)
        try:
            pyperclip.copy(old_clipboard)
        except Exception:
            pass
