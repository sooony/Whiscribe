import ctypes
from ctypes import wintypes
import logging
import os
import queue
import threading
import time

logger = logging.getLogger("whiscribe.focus")
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class _PulaUIA:
    """
    Pojedynczy watek inspekcji UI Automation, uzywany ponownie przy kazdym zapytaniu.

    GetFocusedControl() na zawieszonym oknie nie wraca nigdy. Przy watku na zapytanie
    kazde dyktowanie w takiej sytuacji zostawialo jeden watek z apartamentem COM.
    Teraz zawieszone zapytanie blokuje jeden watek: kolejne zapytania od razu dostaja
    None (czyli sciezke awaryjna po nazwie procesu), a dopiero po PROG_PORZUCENIA
    startuje nowy watek, zeby bramka pola tekstowego wrocila do zycia, gdy zawieszone
    okno sie odblokuje.
    """

    PROG_PORZUCENIA = 15.0
    MAKS_PORZUCONYCH = 3

    def __init__(self):
        self._lock = threading.Lock()
        self._zadania = None
        self._watek = None
        self._zajety_od = None
        self._porzucone = 0

    def _wystartuj_watek(self) -> bool:
        """Uruchamia watek roboczy, jesli go nie ma. Wolane z zajetym lockiem."""
        if self._watek is not None and self._watek.is_alive():
            return True
        if self._porzucone > self.MAKS_PORZUCONYCH:
            return False
        self._zadania = queue.Queue()
        self._watek = threading.Thread(target=self._petla, args=(self._zadania,),
                                       daemon=True, name="uia-inspektor")
        self._watek.start()
        return True

    def _petla(self, zadania):
        try:
            ctypes.windll.ole32.CoInitialize(None)
        except Exception as e:
            logger.debug(f"CoInitialize w watku UIA nieudane: {e}")
        try:
            while True:
                zadanie, gotowe = zadania.get()
                if zadanie is None:
                    return
                try:
                    zadanie()
                except Exception as e:
                    logger.debug(f"Blad watku inspekcji UIA: {e}")
                finally:
                    with self._lock:
                        if self._zadania is zadania:
                            self._zajety_od = None
                    gotowe.set()
        finally:
            try:
                ctypes.windll.ole32.CoUninitialize()
            except Exception:
                pass

    def wykonaj(self, zadanie, timeout: float) -> bool:
        """
        Oddaje `zadanie` watkowi roboczemu i czeka na nie najdluzej `timeout` sekund.

        Zwraca True, gdy zadanie zdazylo sie wykonac.
        """
        gotowe = threading.Event()
        with self._lock:
            if self._zajety_od is not None:
                czeka = time.time() - self._zajety_od
                if czeka < self.PROG_PORZUCENIA:
                    return False
                # Watek wisi od kilkunastu sekund - porzucamy go i bierzemy nowy
                self._porzucone += 1
                if self._porzucone <= self.MAKS_PORZUCONYCH:
                    logger.warning(f"Watek inspekcji UIA wisi od {czeka:.0f} s - porzucam go "
                                   f"({self._porzucone}/{self.MAKS_PORZUCONYCH}).")
                self._watek = None
                self._zadania = None
                self._zajety_od = None
            if not self._wystartuj_watek():
                return False
            self._zajety_od = time.time()
            self._zadania.put((zadanie, gotowe))
        return gotowe.wait(timeout)


_PULA_UIA = _PulaUIA()

# Klasy okien nieedytowalnych (pulpit, pasek zadan, widzet aplikacji)
NON_EDITABLE_WINDOW_CLASSES = {
    '#32769',                     # Pulpit Windows (tło)
    'Progman',                    # Menedżer programu (Pulpit)
    'WorkerW',                    # Powłoka pulpitu Windows
    'Shell_TrayWnd',              # Główny pasek zadań
    'Shell_SecondaryTrayWnd',     # Pasek zadań na dodatkowym monitorze
    'SHELLDLL_DefView',           # Widok folderu / pulpit
    'SysListView32',              # Lista ikon pulpitu
    'Win11VoiceTypingOverlayClass', # Własny widżet aplikacji
    'VoiceWavePillGlassMainClass',  # Poprzednia klasa widżetu
    'VoiceUI250x90Class'            # Nowy widżet Compact Voice UI
}

# Typy kontrolek UI Automation, które nie są polami tekstowymi
NON_EDITABLE_CONTROL_TYPES = {
    'ListControl', 'ListItemControl', 'TreeControl', 'TreeItemControl',
    'ButtonControl', 'ScrollBarControl', 'HeaderControl', 'ToolBarControl',
    'MenuControl', 'MenuItemControl', 'TabItemControl', 'ImageControl',
    'ProgressBarControl', 'SliderControl', 'HyperlinkControl', 'AppBarControl',
    'TitleBarControl', 'MenuBarControl', 'SeparatorControl',
    'CheckBoxControl', 'RadioButtonControl'
}

# Środowiska programistyczne, edytory kodu i czaty (zawsze edytowalne okna robocze)
IDE_AND_EDITOR_PROCESSES = {
    'code.exe', 'cursor.exe', 'devenv.exe', 'antigravity.exe', 'windsurf.exe', 'zed.exe',
    'notepad.exe', 'wordpad.exe', 'winword.exe', 'excel.exe',
    'powerpnt.exe', 'slack.exe', 'discord.exe', 'teams.exe',
    'sublime_text.exe', 'pycharm64.exe', 'idea64.exe', 'clion64.exe',
    'webstorm64.exe', 'rider64.exe', 'obsidian.exe', 'notion.exe'
}

# Przeglądarki internetowe (obszar roboczy stron www i aplikacji webowych)
BROWSER_PROCESSES = {
    'chrome.exe', 'msedge.exe', 'firefox.exe', 'brave.exe', 'opera.exe', 'vivaldi.exe',
    'arc.exe', 'chromium.exe'
}

# Terminale i konsole (zawsze przyjmują wprowadzanie tekstu)
TERMINAL_CLASSES = {
    'ConsoleWindowClass',           # cmd.exe, powershell w starym oknie
    'CASCADIA_HOSTING_WINDOW_CLASS',# Windows Terminal
    'VirtualConsoleClass',          # ConEmu / Cmder
    'mintty'                        # Git Bash
}

# Natywne kontrolki edycyjne Win32 (klasyczny Notatnik, WordPad, okna dialogowe)
NATIVE_EDIT_CLASSES = {
    'edit', 'richedit', 'richedit20w', 'richedit20a', 'richedit50w',
    'richedit60w', 'scintilla'
}

class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]

def get_proc_name_from_hwnd(hwnd: int) -> str:
    """Zwraca nazwę procesu (np. chrome.exe, code.exe) dla danego HWND."""
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    h_proc = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h_proc:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(h_proc)
    return ""

def is_valid_target_window(hwnd: int, overlay_hwnd: int = 0) -> bool:
    """Sprawdza, czy okno jest poprawnym oknem docelowym dla tekstu."""
    if not hwnd or not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
        return False
    if overlay_hwnd and hwnd == overlay_hwnd:
        return False
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    cls_name = buf.value
    if cls_name in NON_EDITABLE_WINDOW_CLASSES or cls_name.startswith("VoiceUIClass"):
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value == os.getpid():
        return False
    return True

def _check_win32_caret(target_hwnd: int = None) -> tuple[bool, str]:
    """Weryfikuje obecność natywnego kursora tekstowego (caret) lub kontrolki Edit w Win32."""
    try:
        tid = 0
        if target_hwnd and user32.IsWindow(target_hwnd):
            tid = user32.GetWindowThreadProcessId(target_hwnd, None)
        gti = GUITHREADINFO()
        gti.cbSize = ctypes.sizeof(GUITHREADINFO)
        if user32.GetGUIThreadInfo(tid, ctypes.byref(gti)):
            # Aktywny kursor tekstowy Win32 (Caret)
            if gti.hwndCaret and gti.hwndCaret != 0:
                return True, "Natywny kursor tekstowy Win32 (Caret)"

            # Weryfikacja klasy kontrolki z fokusem
            if gti.hwndFocus and gti.hwndFocus != 0:
                cbuf = ctypes.create_unicode_buffer(128)
                user32.GetClassNameW(gti.hwndFocus, cbuf, 128)
                c_name = cbuf.value.lower()
                for edit_cls in NATIVE_EDIT_CLASSES:
                    if edit_cls in c_name:
                        return True, f"Natywna kontrolka edycyjna Win32 ({cbuf.value})"
    except Exception as e:
        logger.debug(f"Błąd Win32 GUIThreadInfo: {e}")
    return False, ""

def is_text_field_focused(target_hwnd: int = None) -> tuple[bool, str]:
    """
    Sprawdza, czy aktywne okno lub kontrolka to edytowalne pole tekstowe.
    Zapobiega wprowadzaniu tekstu w nieprawidłowe kontrolki systemowe.
    """
    hwnd_fg = target_hwnd if (target_hwnd and user32.IsWindow(target_hwnd)) else user32.GetForegroundWindow()
    if not hwnd_fg:
        return False, "Brak aktywnego okna na pierwszym planie"

    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd_fg, buf, 256)
    fg_class = buf.value

    # 1. Wykluczenie pulpitu, paska zadan i okna aplikacji
    if fg_class in NON_EDITABLE_WINDOW_CLASSES or fg_class.startswith("VoiceUIClass"):
        return False, f"Pulpit lub pasek zadań ({fg_class})"

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd_fg, ctypes.byref(pid))
    if pid.value == os.getpid():
        return False, "Własny widżet aplikacji Whiscribe"

    # 2. Terminale / konsole tekstowe (zawsze edytowalne)
    if fg_class in TERMINAL_CLASSES:
        return True, f"Terminal ({fg_class})"

    # 3. Sprawdzenie natywnego kursora Win32 (błyskawiczne i niezawodne w programach Win32)
    has_caret, caret_reason = _check_win32_caret(hwnd_fg)
    if has_caret:
        return True, caret_reason

    # 4. Identyfikacja procesu okna na pierwszym planie
    proc_name = get_proc_name_from_hwnd(hwnd_fg)

    # 5. Sprawdzenie przez Windows UI Automation z twardym limitem czasu (wątek roboczy)
    uia_result = []

    def _uia_worker():
        # CoInitialize/CoUninitialize robi watek puli, raz na swoje zycie
        try:
            import uiautomation as auto
            el = auto.GetFocusedControl()
            if not el:
                if proc_name in IDE_AND_EDITOR_PROCESSES:
                    uia_result.append((True, f"Środowisko programistyczne ({proc_name})"))
                elif proc_name in BROWSER_PROCESSES:
                    uia_result.append((True, f"Przeglądarka internetowa ({proc_name})"))
                else:
                    uia_result.append((False, f"Brak aktywnej kontrolki w oknie ({fg_class})"))
                return

            c_type = el.ControlTypeName
            c_class = el.ClassName or ""
            c_name = el.Name or ""

            # 5a. Przeglądarki internetowe:
            if proc_name in BROWSER_PROCESSES:
                if c_type in ('TitleBarControl', 'TabItemControl', 'MenuControl', 'MenuItemControl', 'ToolBarControl'):
                    uia_result.append((False, f"Element nawigacyjny przeglądarki ({c_type})"))
                    return
                if c_type in ('ButtonControl',) and ('caption' in c_class.lower() or 'close' in c_name.lower()):
                    uia_result.append((False, f"Pasek tytułowy przeglądarki ({c_type})"))
                    return
                if c_type == 'EditControl':
                    try:
                        if hasattr(el, 'IsEnabled') and not el.IsEnabled:
                            uia_result.append((False, "Pole EditControl jest wyłączone (IsEnabled=False)"))
                            return
                        val = el.GetPattern(auto.PatternId.ValuePattern)
                        if val and val.IsReadOnly:
                            uia_result.append((False, "Pole EditControl jest tylko do odczytu (IsReadOnly=True)"))
                            return
                    except Exception:
                        pass
                    uia_result.append((True, f"Pole edycyjne przeglądarki ({c_type})"))
                    return
                uia_result.append((True, f"Przeglądarka internetowa – obszar strony ({c_type})"))
                return

            # 5b. Kontrolki nieedytowalne (drzewa plików, listy, paski przewijania itp.)
            if c_type in NON_EDITABLE_CONTROL_TYPES:
                uia_result.append((False, f"Kontrolka nieedytowalna ({c_type})"))
                return

            # 5c. EditControl (pole edycji tekstu)
            if c_type == 'EditControl':
                try:
                    if hasattr(el, 'IsEnabled') and not el.IsEnabled:
                        uia_result.append((False, "Pole EditControl jest wyłączone (IsEnabled=False)"))
                        return
                    val = el.GetPattern(auto.PatternId.ValuePattern)
                    if val and val.IsReadOnly:
                        uia_result.append((False, "Pole EditControl jest tylko do odczytu (IsReadOnly=True)"))
                        return
                except Exception:
                    pass
                uia_result.append((True, f"Pole edycyjne ({c_type})"))
                return

            # 5d. ComboBoxControl (pole wyboru / prompt)
            if c_type == 'ComboBoxControl':
                uia_result.append((True, f"Pole wyboru/wprowadzania ({c_name or c_type})"))
                return

            # 5e. DocumentControl (Word, Windows 11 Notatnik, WordPad, edytory Electron)
            if c_type == 'DocumentControl':
                uia_result.append((True, f"Dokument tekstowy ({c_type})"))
                return

            # 5f. Uniwersalne wzorce edycji tekstu (Monaco w VS Code, kontrolki webowe z TextEditPattern/ValuePattern)
            try:
                te = el.GetPattern(auto.PatternId.TextEditPattern)
                if te is not None:
                    uia_result.append((True, f"Kontrolka wspiera TextEditPattern ({c_type})"))
                    return
            except Exception:
                pass

            try:
                val = el.GetPattern(auto.PatternId.ValuePattern)
                if val and not val.IsReadOnly:
                    uia_result.append((True, f"Kontrolka edytowalna ValuePattern ({c_type})"))
                    return
            except Exception:
                pass

            # 5g. Środowiska programistyczne i narzędzia robocze (VS Code, Cursor, edytory itp.)
            if proc_name in IDE_AND_EDITOR_PROCESSES:
                if c_type in ('ButtonControl', 'TitleBarControl') and ('caption' in c_class.lower() or 'close' in c_name.lower()):
                    uia_result.append((False, f"Pasek tytułowy aplikacji ({c_type})"))
                    return
                uia_result.append((True, f"Środowisko programistyczne / Czat ({proc_name})"))
                return

            # 5h. Dla pozostałych ogólnych aplikacji: brak wzorca edycji oznacza kontrolkę nieedytowalną
            uia_result.append((False, f"Kontrolka bez możliwości wprowadzania tekstu ({c_type} / {fg_class})"))
        except Exception as e:
            logger.debug(f"Błąd wątku inspekcji UIA: {e}")

    _PULA_UIA.wykonaj(_uia_worker, 0.18)

    if uia_result:
        return uia_result[0]

    # Timeout wątku UIA (COM zawisł lub zajął >180ms)
    logger.debug(f"Timeout inspekcji UIA dla procesu {proc_name} ({fg_class})")
    if proc_name in IDE_AND_EDITOR_PROCESSES:
        return True, f"Środowisko programistyczne ({proc_name}) [timeout UIA]"
    if proc_name in BROWSER_PROCESSES:
        return True, f"Przeglądarka internetowa ({proc_name}) [timeout UIA]"
    return False, f"Przekroczono limit czasu inspekcji kontrolki ({fg_class})"
