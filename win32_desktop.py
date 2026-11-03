"""
Przypinanie wątku do pulpitu "Default".

Globalne skróty i okno widżetu działają tylko wtedy, gdy wątek, który je zakłada,
siedzi na tym samym pulpicie co sesja użytkownika. Po Ctrl+Alt+Delete albo ekranie
blokady Windows przełącza pulpit, więc wątek nasłuchu trzeba przypiąć ponownie.

Uchwyt pulpitu (HDESK) jest jeden na cały proces i celowo nigdy nie jest zamykany:
`SetThreadDesktop` wiąże go z wątkiem, a `CloseDesktop` odmawia zamknięcia pulpitu,
który jest pulpitem jakiegokolwiek żywego wątku. Wcześniej każde wywołanie otwierało
nowy uchwyt, a watchdog skrótów robi to co 3 s, czyli 1200 uchwytów na godzinę.
"""

import ctypes
import logging
import threading
from ctypes import wintypes

logger = logging.getLogger("whiscribe.pulpit")

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_user32.OpenDesktopW.restype = wintypes.HANDLE
_user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
_user32.SetThreadDesktop.restype = wintypes.BOOL

# DESKTOP_READOBJECTS | ... | DESKTOP_SWITCHDESKTOP – pełny dostęp jak w dotychczasowym kodzie
DESKTOP_ALL_ACCESS = 0x01FF

_lock = threading.Lock()
_hdesk = None
_ostrzezenie_zglaszane = False


def przypnij_watek_do_pulpitu() -> bool:
    """
    Przypina wywołujący wątek do pulpitu "Default". Zwraca True, gdy się udało.

    Wywołanie jest tanie i idempotentne, więc można je powtarzać przy każdym
    wznowieniu nasłuchu skrótów bez żadnego stanu po stronie wołającego.
    """
    global _hdesk, _ostrzezenie_zglaszane
    try:
        with _lock:
            if _hdesk is None:
                uchwyt = _user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL_ACCESS)
                if not uchwyt:
                    if not _ostrzezenie_zglaszane:
                        _ostrzezenie_zglaszane = True
                        logger.warning(f"Nie udało się otworzyć pulpitu Default (błąd {ctypes.get_last_error()}).")
                    return False
                _hdesk = uchwyt
            return bool(_user32.SetThreadDesktop(_hdesk))
    except Exception as e:
        if not _ostrzezenie_zglaszane:
            _ostrzezenie_zglaszane = True
            logger.warning(f"Przypięcie wątku do pulpitu nieudane: {e}")
        return False


def uchwyt_pulpitu():
    """Zwraca uchwyt pulpitu albo None, gdy jeszcze go nie otwarto (do testów)."""
    with _lock:
        return _hdesk
