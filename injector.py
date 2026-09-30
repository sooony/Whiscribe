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
    Zapobiega powielaniu słów, połykaniu tekstu i skakaniu wstecz dzięki dopasowywaniu sufiksowemu.
    """
    def __init__(self, type_callback=None):
        self.type_callback = type_callback or send_unicode_string
        self.typed_raw_words = []        # Wszystkie słowa wpisane w tej sesji
        self.typed_norm_words = []       # Znormalizowane słowa (lowercase, bez interpunkcji) do porównań
        self.last_hypothesis_words = []  # Słowa z poprzedniego przebiegu Whisper
        self.typed_text = ""             # Całkowity tekst wpisany w całej sesji

    def reset_for_new_segment(self):
        """Resetuje stan bieżącej hipotezy dla nowego segmentu audio (zachowując historię wpisanych słów)."""
        self.last_hypothesis_words = []

    def _feed_words(self, words: list):
        if not words:
            return
        norm = [normalize_word(w) for w in words]
        
        # Znajdź maksymalny overlap z końcem wpisanego dotąd tekstu (do 20 słów wstecz)
        max_lookback = min(len(self.typed_norm_words), 20, len(norm))
        overlap_len = 0
        for k in range(max_lookback, 0, -1):
            if self.typed_norm_words[-k:] == norm[:k]:
                overlap_len = k
                break

        new_words = words[overlap_len:]
        if new_words:
            chunk = " ".join(new_words) + " "
            self.typed_raw_words.extend(new_words)
            self.typed_norm_words.extend(norm[overlap_len:])
            self.typed_text += chunk
            self.type_callback(chunk)

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

        # Słowa stabilne to słowa sprzed ogona (ostatnie 1 słowo może się jeszcze zmienić w mowie)
        safe_margin = 1
        if len(current_words) > safe_margin:
            stable_words = current_words[:-safe_margin]
            self._feed_words(stable_words)

        self.last_hypothesis_words = current_words

    def commit_segment(self, segment_text: str):
        """
        Definitywnie zatwierdza cały zakończony segment zdania.
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
        self._feed_words(words)
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
            self._feed_words(words)
        self.last_hypothesis_words = []

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
