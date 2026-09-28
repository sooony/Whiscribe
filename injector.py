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
    Zapobiega 'zjadaniu' tekstu, migotaniu i skakaniu wstecz.
    """
    def __init__(self, type_callback=None):
        self.type_callback = type_callback or send_unicode_string
        self.committed_words = []        # Słowa już fizycznie wpisane do dokumentu w bieżącym segmencie
        self.last_hypothesis_words = []  # Słowa z poprzedniego przebiegu Whisper
        self.typed_text = ""             # Całkowity tekst wpisany w całej sesji

    def reset_for_new_segment(self):
        """Resetuje stan dla nowego segmentu po przesunięciu offsetu audio."""
        self.committed_words = []
        self.last_hypothesis_words = []

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

        num_committed = len(self.committed_words)
        num_current = len(current_words)

        if num_current <= num_committed:
            self.last_hypothesis_words = current_words
            return

        # Sprawdź ile słów pokrywa się między poprzednim a bieżącym przebiegiem
        common_count = 0
        min_len = min(len(self.last_hypothesis_words), num_current)
        for i in range(min_len):
            if normalize_word(self.last_hypothesis_words[i]) == normalize_word(current_words[i]):
                common_count += 1
            else:
                break

        # Słowa stabilne:
        # - Jeśli pokrywają się w 2 kolejnych krokach -> stabilne
        # - LUB jeśli jest to długa, ciągła wypowiedź -> słowa przed marginesem 2 ostatnich słów są stabilne
        safe_tail_margin = 2
        stable_by_length = max(0, num_current - safe_tail_margin)
        stable_index = max(common_count, stable_by_length)
        stable_index = min(stable_index, num_current)

        if stable_index > num_committed:
            words_to_commit = current_words[num_committed:stable_index]
            chunk = " ".join(words_to_commit) + " "
            self.committed_words.extend(words_to_commit)
            self.typed_text += chunk
            self.type_callback(chunk)

        self.last_hypothesis_words = current_words

    def commit_segment(self, segment_text: str):
        """
        Definitywnie zatwierdza cały zakończony segment zdania i resetuje wskaźnik słów.
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
        num_committed = len(self.committed_words)
        if len(words) > num_committed:
            remaining = words[num_committed:]
            chunk = " ".join(remaining) + " "
            self.committed_words.extend(remaining)
            self.typed_text += chunk
            self.type_callback(chunk)
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
        num_committed = len(self.committed_words)
        if len(words) > num_committed:
            remaining = words[num_committed:]
            chunk = " ".join(remaining) + " "
            self.committed_words.extend(remaining)
            self.typed_text += chunk
            self.type_callback(chunk)
        elif not self.typed_text.strip() and final_text and final_text.strip():
            # Krótka jednorazowa fraza, która nie zdążyła się zmatchować w streamingu
            chunk = final_text.strip() + " "
            self.typed_text += chunk
            self.type_callback(chunk)

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
