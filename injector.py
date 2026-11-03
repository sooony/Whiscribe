import threading
import time
import ctypes
from ctypes import wintypes
import pyperclip
from pynput.keyboard import Controller, Key

kb = Controller()

# Wyniki inject_text: bez nich wywołujący nie wie, czy tekst naprawdę wszedł
WYNIK_WKLEJONY = "pasted"
WYNIK_WPISANY = "typed"
WYNIK_PUSTY = "empty"

# Każde wejście do inject_text po kolei: funkcja zapisuje i odtwarza zawartość schowka
# użytkownika, więc dwa równoległe wklejenia (finalizacja dyktowania i przywrócenie
# z pamięci wklejek) nadpisywałyby sobie kopię starego schowka.
_inject_lock = threading.RLock()

_mod_user32 = ctypes.WinDLL("user32", use_last_error=True)
_mod_user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
_mod_user32.GetAsyncKeyState.restype = ctypes.c_short

VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12


def modyfikatory_wcisniete() -> bool:
    """True, gdy Ctrl, Alt albo Shift jest FIZYCZNIE wciśnięty."""
    for vk in (VK_CONTROL, VK_MENU, VK_SHIFT):
        if (_mod_user32.GetAsyncKeyState(vk) & 0x8000) != 0:
            return True
    return False


def zwolnij_modyfikatory(czekaj_s: float = 0.5) -> bool:
    """Zwalnia Ctrl, Alt i Shift i czeka na ich fizyczne puszczenie.

    kb.release() nie zmienia stanu fizycznego klawiatury: gdy tekst wkleja się w reakcji
    na skrót (Ctrl+Alt+D, Ctrl+Alt+V), klawisze są jeszcze wciśnięte i aplikacja docelowa
    zamiast Ctrl+V widzi Ctrl+Alt+V albo zawieszony Ctrl. Limit jest twardy, bo zawieszony
    klawisz sprzętowy zablokowałby wklejanie na zawsze.

    Zwraca True, jeśli klawisze faktycznie puszczono w ramach limitu.
    """
    for mod in (Key.ctrl, Key.ctrl_l, Key.ctrl_r, Key.alt, Key.alt_l, Key.alt_r,
                Key.shift, Key.shift_l, Key.shift_r):
        try:
            kb.release(mod)
        except Exception:
            pass

    deadline = time.time() + max(0.0, czekaj_s)
    while time.time() < deadline:
        if not modyfikatory_wcisniete():
            return True
        time.sleep(0.01)
    return not modyfikatory_wcisniete()

# Własne instancje bibliotek z pełnymi sygnaturami: bez argtypes/restype ctypes obcina
# 64-bitowe uchwyty i wskaźniki do 32 bitów (zapis pod błędny adres = crash procesu).
_cb_user32 = ctypes.WinDLL("user32", use_last_error=True)
_cb_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_cb_user32.OpenClipboard.argtypes = [wintypes.HWND]
_cb_user32.OpenClipboard.restype = wintypes.BOOL
_cb_user32.CloseClipboard.argtypes = []
_cb_user32.CloseClipboard.restype = wintypes.BOOL
_cb_user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
_cb_user32.SetClipboardData.restype = wintypes.HANDLE
_cb_user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
_cb_user32.RegisterClipboardFormatW.restype = wintypes.UINT
_cb_kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
_cb_kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
_cb_kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_cb_kernel32.GlobalLock.restype = wintypes.LPVOID
_cb_kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
_cb_kernel32.GlobalUnlock.restype = wintypes.BOOL
_cb_kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
_cb_kernel32.GlobalFree.restype = wintypes.HGLOBAL

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

def send_enter():
    """
    Zatwierdza wpisany tekst klawiszem Enter (wysyła wiadomość w czacie, zatwierdza pole).
    Modyfikatory ze skrótu (Ctrl + Alt + D) muszą być zwolnione, bo inaczej aplikacja
    docelowa dostaje Ctrl + Enter albo Alt + Enter, czyli zupełnie co innego.
    """
    for mod in (Key.ctrl, Key.ctrl_l, Key.ctrl_r, Key.alt, Key.alt_l, Key.alt_r, Key.shift, Key.shift_l, Key.shift_r):
        try:
            kb.release(mod)
        except Exception:
            pass
    kb.tap(Key.enter)


def normalize_word(w: str) -> str:
    """Usuwa znaki interpunkcyjne do bezpiecznego porównywania tożsamości słów."""
    import re
    return re.sub(r'[^\w]', '', w).lower()

class ForwardStreamCommitter:
    """
    Zarządza płynnym wpisywaniem tekstu w trybie strumieniowym.
    Wpisywanie wyłącznie w przód (Forward-Only) z dopasowaniem kotwicowym.
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

        # Wyznaczenie stabilnego prefiksu słów (z pominięciem marginesu ogona)
        safe_margin = getattr(self, "safe_margin", 2)
        if len(current_words) > safe_margin:
            stable_words = current_words[:-safe_margin]
            norm_stable = [normalize_word(w) for w in stable_words]
            cont_idx = self._find_continuation_index(norm_stable)
            new_words = stable_words[cont_idx:]
            self._emit_words(new_words)

    def commit_segment(self, segment_text: str):
        """Zatwierdza segment tekstu i wypisuje pozostałe słowa."""
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

def inject_text(text: str, restore_clipboard: bool = True) -> str:
    """
    Wkleja tekst do aktywnego okna przez schowek (Ctrl + V).
    Zabezpiecza przed pozostawianiem dyktowanego tekstu w schowku systemowym:
    - Przywraca poprzednią zawartość schowka użytkownika (jeśli istniała).
    - Jeśli schowek był pusty, czyści go całkowicie po wklejeniu.
    - Zapobiega zapisywaniu tymczasowego tekstu w historii schowka Windows 10/11 (Win+V).

    Zwraca WYNIK_WKLEJONY, WYNIK_WPISANY (schowek zablokowany, znaki wpisane po kolei)
    albo WYNIK_PUSTY. Bez tego wywołujący nie wie, czy tekst naprawdę wszedł, i status
    w pamięci wklejek byłby zgadywany.
    """
    if not text or not text.strip():
        return WYNIK_PUSTY

    with _inject_lock:
        return _inject_text_locked(text, restore_clipboard)


def _inject_text_locked(text: str, restore_clipboard: bool) -> str:
    text = text.strip() + " "
    old_clipboard = None
    for _ in range(3):
        try:
            old_clipboard = pyperclip.paste()
            break
        except Exception:
            time.sleep(0.02)

    # Rejestracja formatów wykluczających ze schowka Windows 10/11 (Win+V / Cloud Clipboard)
    user32, kernel32 = _cb_user32, _cb_kernel32
    GMEM_MOVEABLE = 0x0002
    GMEM_ZEROINIT = 0x0040
    try:
        cf_exclude = user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
        cf_history = user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
    except Exception:
        cf_exclude = cf_history = 0

    # Kopiowanie do schowka z ponawianiem przy kolizji z menedżerem schowka Windows
    copied = False
    for _ in range(5):
        try:
            pyperclip.copy(text)
            copied = True
            break
        except Exception:
            time.sleep(0.02)

    # Oznaczenie wpisu jako wykluczonego z historii schowka (Win+V)
    if copied and cf_history:
        try:
            if user32.OpenClipboard(None):
                try:
                    # GMEM_ZEROINIT: blok ma już wartość 0 (= "nie zapisuj w historii"), nie trzeba go blokować
                    for cf in (cf_history, cf_exclude):
                        if not cf:
                            continue
                        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, 4)
                        if h_mem and not user32.SetClipboardData(cf, h_mem):
                            kernel32.GlobalFree(h_mem)
                finally:
                    user32.CloseClipboard()
        except Exception:
            try:
                user32.CloseClipboard()
            except Exception:
                pass

    if not copied:
        # Fallback: bezpośrednie wpisanie znaków jeśli schowek systemowy jest zablokowany
        zwolnij_modyfikatory()
        send_unicode_string(text)
        return WYNIK_WPISANY

    time.sleep(0.05)

    # Ctrl, Alt i Shift ze skrótu (Ctrl+Alt+D, Ctrl+Alt+V) muszą być fizycznie puszczone,
    # inaczej aplikacja docelowa dostaje Ctrl+Alt+V zamiast Ctrl+V.
    zwolnij_modyfikatory()

    # Symuluj Ctrl + V za pomocą pynput
    with kb.pressed(Key.ctrl):
        kb.tap('v')

    # Odczekaj na odczytanie schowka przez docelową aplikację (np. Antigravity/Chrome/Word)
    time.sleep(0.30)

    # Przywrócenie lub wyczyszczenie schowka
    try:
        if restore_clipboard:
            if old_clipboard and old_clipboard.strip() and old_clipboard != text:
                pyperclip.copy(old_clipboard)
            else:
                pyperclip.copy("")
        # Gdy restore_clipboard jest False, tekst pozostaje w schowku
    except Exception:
        pass

    return WYNIK_WKLEJONY

