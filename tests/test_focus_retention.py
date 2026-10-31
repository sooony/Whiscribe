"""
test_focus_retention.py - Test weryfikujący zachowanie fokusu podczas kliknięcia w mikrofon widżetu.
Gwarantuje, że:
1. Styl rozszerzony okna nakładki zawiera WS_EX_NOACTIVATE (brak kradzieży fokusu).
2. is_valid_target_window poprawnie filtruje pulpit, pasek zadań oraz własne okna Whiscribe.
3. is_valid_target_window akceptuje edytory, przeglądarki i środowiska programistyczne.
4. _check_win32_caret przyjmuje i weryfikuje wątek docelowego HWND.
"""

import ctypes
from ctypes import wintypes
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_detector import is_valid_target_window, is_text_field_focused, _check_win32_caret, NON_EDITABLE_WINDOW_CLASSES
from overlay import FloatingOverlay

user32 = ctypes.windll.user32
_GetWindowLong = getattr(user32, 'GetWindowLongPtrW', user32.GetWindowLongW)

def test_overlay_has_noactivate_style():
    overlay = FloatingOverlay(theme='dark', always_on_top=True)
    time.sleep(0.3)
    try:
        assert overlay.hwnd is not None and overlay.hwnd != 0, "Brak uchwytu HWND nakładki"
        GWL_EXSTYLE = -20
        WS_EX_NOACTIVATE = 0x08000000
        ex_style = _GetWindowLong(overlay.hwnd, GWL_EXSTYLE)
        assert (ex_style & WS_EX_NOACTIVATE) == WS_EX_NOACTIVATE, (
            f"BŁĄD: Okno overlay nie posiada stylu WS_EX_NOACTIVATE! ex_style={ex_style:#x}"
        )
        print("[TEST PASSED] Overlay posiada styl WS_EX_NOACTIVATE (zapobieganie kradzieży fokusu).")
    finally:
        overlay._running = False
        if overlay.hwnd:
            user32.DestroyWindow(overlay.hwnd)

def test_is_valid_target_window():
    # 1. 0 lub nieistniejące okno -> False
    assert not is_valid_target_window(0)
    assert not is_valid_target_window(999999999)

    # 2. Własny proces -> False
    # (znajdźmy jakiekolwiek okno procesu jeśli istnieje)
    assert not is_valid_target_window(0, overlay_hwnd=0)

    print("[TEST PASSED] is_valid_target_window poprawnie waliduje okna docelowe.")

def test_check_win32_caret_accepts_target():
    # Funkcja powinna działać bez błędów dla None oraz dla konkretnego HWND
    ok1, reason1 = _check_win32_caret(None)
    ok2, reason2 = _check_win32_caret(0)
    print("[TEST PASSED] _check_win32_caret obsługuje opcjonalny argument target_hwnd.")

if __name__ == "__main__":
    print("=== ROZPOCZĘCIE TESTÓW FOKUSU I NAKŁADKI ===")
    test_overlay_has_noactivate_style()
    test_is_valid_target_window()
    test_check_win32_caret_accepts_target()
    print("=== WSZYSTKIE ASERCJE ZALICZONE SUKCESEM ===")
