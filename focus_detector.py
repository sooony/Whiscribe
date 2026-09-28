import ctypes
from ctypes import wintypes
import logging
import os

logger = logging.getLogger("FocusDetector")
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Klasy okien, które pod żadnym pozorem nie są polami tekstowymi (Pulpit, Pasek Zadań i Widżet Aplikacji)
NON_EDITABLE_WINDOW_CLASSES = {
    '#32769',                     # Pulpit Windows (tło)
    'Progman',                    # Menedżer programu (Pulpit)
    'WorkerW',                    # Powłoka pulpitu Windows
    'Shell_TrayWnd',              # Główny pasek zadań
    'Shell_SecondaryTrayWnd',     # Pasek zadań na dodatkowym monitorze
    'SHELLDLL_DefView',           # Widok folderu / pulpit
    'SysListView32',              # Lista ikon pulpitu
    'Win11VoiceTypingOverlayClass', # Własny widżet aplikacji
    'VoiceWavePillGlassMainClass'   # Poprzednia klasa widżetu
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
    'antigravity.exe', 'code.exe', 'cursor.exe', 'devenv.exe',
    'notepad.exe', 'wordpad.exe', 'winword.exe', 'excel.exe',
    'powerpnt.exe', 'slack.exe', 'discord.exe', 'teams.exe',
    'sublime_text.exe', 'pycharm64.exe', 'idea64.exe', 'clion64.exe',
    'webstorm64.exe', 'rider64.exe', 'obsidian.exe', 'notion.exe'
}

# Przeglądarki internetowe (wymagają rzeczywistego fokusowania pola wprowadzania tekstu)
BROWSER_PROCESSES = {
    'chrome.exe', 'msedge.exe', 'firefox.exe', 'brave.exe', 'opera.exe', 'vivaldi.exe'
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
    """Zwraca nazwę procesu (np. antigravity.exe, chrome.exe) dla danego HWND."""
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

def _check_win32_caret() -> tuple[bool, str]:
    """Weryfikuje obecność natywnego kursora tekstowego (caret) lub kontrolki Edit w Win32."""
    try:
        gti = GUITHREADINFO()
        gti.cbSize = ctypes.sizeof(GUITHREADINFO)
        if user32.GetGUIThreadInfo(0, ctypes.byref(gti)):
            # Jeśli system zgłasza aktywny kursor tekstowy (migająca pionowa kreska)
            if gti.hwndCaret and gti.hwndCaret != 0:
                return True, "Natywny kursor tekstowy Win32 (Caret)"

            # Sprawdź klasę kontrolki z fokusem
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

def is_text_field_focused() -> tuple[bool, str]:
    """
    Rygorystycznie sprawdza przed rozpoczęciem dyktowania, czy aktywne okno lub kontrolka
    to edytowalne pole tekstowe.
    Zapobiega uruchomieniu syntezatora i przypadkowemu wędrowaniu po ikonach
    pulpitu lub wywoływaniu skrótów klawiszowych w nieodpowiednich aplikacjach.
    """
    hwnd_fg = user32.GetForegroundWindow()
    if not hwnd_fg:
        return False, "Brak aktywnego okna na pierwszym planie"

    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd_fg, buf, 256)
    fg_class = buf.value

    # 1. Bezwzględne zablokowanie pulpitu, paska zadań i widżetu aplikacji
    if fg_class in NON_EDITABLE_WINDOW_CLASSES:
        return False, f"Pulpit lub pasek zadań ({fg_class})"

    # 2. Terminale / konsole tekstowe (zawsze edytowalne)
    if fg_class in TERMINAL_CLASSES:
        return True, f"Terminal ({fg_class})"

    # 3. Sprawdzenie natywnego kursora Win32 (błyskawiczne i niezawodne w programach Win32)
    has_caret, caret_reason = _check_win32_caret()
    if has_caret:
        return True, caret_reason

    # 4. Identyfikacja procesu okna na pierwszym planie
    proc_name = get_proc_name_from_hwnd(hwnd_fg)

    # 5. Sprawdzenie przez Windows UI Automation (dla Chrome, Edge, Notatnika Win11, Antigravity, VS Code, Word itp.)
    try:
        import uiautomation as auto
        el = auto.GetFocusedControl()
        if not el:
            if proc_name in IDE_AND_EDITOR_PROCESSES:
                return True, f"Środowisko programistyczne ({proc_name})"
            return True, f"Aktywne okno aplikacji ({fg_class})"

        c_type = el.ControlTypeName
        c_class = el.ClassName or ""
        c_name = el.Name or ""

        # 5a. Jawnie zakazane kontrolki interfejsu (drzewa plików, listy, przyciski, paski przewijania itp.)
        # Odrzucamy je natychmiast, nawet w środowiskach programistycznych (np. kliknięcie w drzewo plików w VS Code/Antigravity)
        if c_type in NON_EDITABLE_CONTROL_TYPES:
            return False, f"Kontrolka nieedytowalna ({c_type})"

        # 5b. EditControl (<input>, <textarea>, pole czatu, edytor)
        if c_type == 'EditControl':
            try:
                if hasattr(el, 'IsEnabled') and not el.IsEnabled:
                    return False, "Pole EditControl jest wyłączone (IsEnabled=False)"
                val = el.GetPattern(auto.PatternId.ValuePattern)
                if val and val.IsReadOnly:
                    return False, "Pole EditControl jest tylko do odczytu (IsReadOnly=True)"
            except Exception:
                pass
            return True, f"Pole edycyjne ({c_type})"

        # 5c. ComboBoxControl (np. pole Message input w Antigravity / Monaco prompt)
        if c_type == 'ComboBoxControl':
            return True, f"Pole wyboru/wprowadzania ({c_name or c_type})"

        # 5d. DocumentControl (Windows 11 Notatnik RichEditD2DPT, Word, WordPad, Dokumenty Google, edytory Electron)
        if c_type == 'DocumentControl':
            if proc_name in BROWSER_PROCESSES:
                try:
                    te = el.GetPattern(auto.PatternId.TextEditPattern)
                    val = el.GetPattern(auto.PatternId.ValuePattern)
                    if te is None and (val is None or val.IsReadOnly):
                        return False, "Przeglądarka internetowa – strona jest tylko do odczytu"
                except Exception:
                    return False, "Przeglądarka internetowa – strona nieedytowalna"
            return True, f"Dokument tekstowy ({c_type})"

        # 5e. Uniwersalne wzorce edycji tekstu dla kontrolek niestandardowych (np. Monaco w VS Code, contenteditable)
        try:
            te = el.GetPattern(auto.PatternId.TextEditPattern)
            if te is not None:
                return True, f"Kontrolka wspiera TextEditPattern ({c_type})"
        except Exception:
            pass

        try:
            val = el.GetPattern(auto.PatternId.ValuePattern)
            if val and not val.IsReadOnly:
                return True, f"Kontrolka edytowalna ValuePattern ({c_type})"
        except Exception:
            pass

        # 5f. Środowiska programistyczne i narzędzia robocze (Antigravity, VS Code, Cursor, itp.)
        if proc_name in IDE_AND_EDITOR_PROCESSES:
            # W Antigravity/VS Code kontrolki to często PaneControl/GroupControl reprezentujące czat lub edytor
            # Blokujemy tylko jawne przyciski paska tytułowego (zamknij, minimalizuj)
            if c_type in ('ButtonControl', 'TitleBarControl') and ('caption' in c_class.lower() or 'close' in c_name.lower()):
                return False, f"Pasek tytułowy aplikacji ({c_type})"
            return True, f"Środowisko programistyczne / Czat ({proc_name})"

        # 5g. W zwykłej przeglądarce internetowej (Chrome, Edge, Firefox):
        # kliknięcie w puste tło, link lub przycisk nie jest polem tekstowym
        if proc_name in BROWSER_PROCESSES:
            return False, f"Przeglądarka internetowa – brak aktywnego pola tekstowego ({c_type})"

        # 5h. Zezwalamy dla normalnych kontrolek aplikacji roboczych (PaneControl, CustomControl itp.)
        return True, f"Aktywne okno robocze ({c_type} / {fg_class})"

    except Exception as e:
        logger.debug(f"Info inspekcji UI Automation: {e}")
        if proc_name in IDE_AND_EDITOR_PROCESSES:
            return True, f"Środowisko programistyczne ({proc_name})"
        return True, f"Domyślna akceptacja okna ({fg_class})"
