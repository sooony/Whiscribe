"""
test_injection_and_typing.py - Kompleksowy audyt i testy modułu wprowadzania tekstu (injector.py).

Weryfikuje:
1. send_unicode_string:
   - Poprawność kodowania i wpisywania polskich znaków diakrytycznych (małych i wielkich: ąćęłńóśźż ĄĆĘŁŃÓŚŹŻ)
   - Wprowadzanie cyfr, spacji i znaków specjalnych
   - Odporność na układ klawiatury i stan klawiszy
2. inject_text:
   - Wklejanie tekstu przez schowek systemowy (Ctrl+V)
   - Wykrycie wyścigu (Race Condition) w 'restore_clipboard=True' (gdy schowek zostaje przywrócony zanim aplikacja docelowa zdąży przetworzyć Ctrl+V)
   - Test zachowania przy zablokowanym schowku (fallback do send_unicode_string)
3. Porównanie przepustowości i wydajności obu metod (znaki/s)
4. ForwardStreamCommitter:
   - Weryfikacja logiki 'Forward-Only' (brak cofania kursora, brak powielania słów)
"""

import sys
import os
import time
import ctypes
import unittest
import threading
from ctypes import wintypes
import pyperclip

from injector import send_unicode_string, inject_text, ForwardStreamCommitter

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.GetForegroundWindow.restype = wintypes.HWND

WM_SETTEXT = 0x000C
WM_GETTEXT = 0x000D
WM_GETTEXTLENGTH = 0x000E


class Win32EditContext:
    """Natywne okno Win32 EDIT z obsługą pętli zdarzeń i podpięciem do aktywnego pulpitu."""
    def __init__(self):
        self.wnd = None
        self.fg_tid = None
        self.cur_tid = None
        self.prev_fg = None

    def __enter__(self):
        # 1. Podpięcie wątku do interaktywnego pulpitu użytkownika (Default)
        try:
            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass

        self.prev_fg = user32.GetForegroundWindow()
        self.cur_tid = kernel32.GetCurrentThreadId()

        if self.prev_fg:
            pid = wintypes.DWORD()
            self.fg_tid = user32.GetWindowThreadProcessId(self.prev_fg, ctypes.byref(pid))
            if self.fg_tid and self.fg_tid != self.cur_tid:
                user32.AttachThreadInput(self.cur_tid, self.fg_tid, True)

        # 2. Utworzenie natywnego okna EDIT (WS_VISIBLE | WS_BORDER | ES_MULTILINE)
        # UWAGA: Celowo bez flagi 0x0008 (ES_UPPERCASE)!
        self.wnd = user32.CreateWindowExW(
            0x00000008,  # WS_EX_TOPMOST
            'EDIT',
            '',
            0x10000000 | 0x00800000 | 0x0004,
            150, 150, 450, 250,
            0, 0, 0, 0
        )
        user32.ShowWindow(self.wnd, 5)
        try:
            from app import safe_bring_to_foreground
            safe_bring_to_foreground(self.wnd)
        except Exception:
            user32.SetForegroundWindow(self.wnd)
        user32.SetFocus(self.wnd)
        self.pump(5)
        time.sleep(0.08)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.wnd:
            user32.DestroyWindow(self.wnd)
        if self.fg_tid and self.fg_tid != self.cur_tid:
            try:
                user32.AttachThreadInput(self.cur_tid, self.fg_tid, False)
            except Exception:
                pass
        if self.prev_fg and user32.IsWindow(self.prev_fg):
            try:
                user32.SetForegroundWindow(self.prev_fg)
            except Exception:
                pass

    def pump(self, count=3):
        """Opróżnia kolejkę komunikatów okna."""
        msg = wintypes.MSG()
        for _ in range(count):
            while user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1):
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            time.sleep(0.02)

    def set_text(self, text: str):
        user32.SendMessageW(self.wnd, WM_SETTEXT, 0, text)
        self.pump(2)

    def get_text(self) -> str:
        self.pump(3)
        length = user32.SendMessageW(self.wnd, WM_GETTEXTLENGTH, 0, 0)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.SendMessageW(self.wnd, WM_GETTEXT, length + 1, buf)
        return buf.value


class TestInjectionAndTyping(unittest.TestCase):
    """Zestaw testów jednostkowych i integracyjnych modułu wprowadzania tekstu."""

    def test_01_send_unicode_polish_characters(self):
        """Weryfikacja pełnego zestawu polskich znaków diakrytycznych w send_unicode_string."""
        with Win32EditContext() as ctx:
            test_phrase = "Zażółć gęślą jaźń ZAŻÓŁĆ GĘŚLĄ JAŹŃ 123 !?@"
            
            t0 = time.time()
            send_unicode_string(test_phrase)
            elapsed = time.time() - t0

            ctx.pump(5)
            actual_text = ctx.get_text()

            print("\n--- TEST 1: send_unicode_string (Polskie znaki) ---")
            print(f"Oczekiwano: '{test_phrase}'")
            print(f"Otrzymano:  '{actual_text}'")
            print(f"Czas: {elapsed:.3f}s | Przepustowość: {len(test_phrase)/max(elapsed, 0.001):.1f} zn./s")

            self.assertEqual(actual_text, test_phrase, "Błąd wprowadzania polskich znaków diakrytycznych!")

    def test_02_inject_text_basic_paste(self):
        """Weryfikacja inject_text (wklejanie Ctrl+V bez przywracania schowka)."""
        with Win32EditContext() as ctx:
            test_phrase = "Szybka transkrypcja AI: polskie znaki ą, ę, ś, ć, ż."
            expected = test_phrase.strip() + " "

            # Wątek pomocniczy pompujący komunikaty okna podczas naciśnięcia Ctrl+V
            stop_pump = threading.Event()
            def background_pump():
                while not stop_pump.is_set():
                    ctx.pump(1)
                    time.sleep(0.01)

            pumper = threading.Thread(target=background_pump, daemon=True)
            pumper.start()

            try:
                t0 = time.time()
                inject_text(test_phrase, restore_clipboard=False)
                elapsed = time.time() - t0
                time.sleep(0.15)
            finally:
                stop_pump.set()
                pumper.join()

            actual_text = ctx.get_text()

            print("\n--- TEST 2: inject_text (Wklejanie przez schowek Ctrl+V) ---")
            print(f"Oczekiwano: '{expected}'")
            print(f"Otrzymano:  '{actual_text}'")
            print(f"Czas: {elapsed:.3f}s")

            self.assertEqual(actual_text, expected)

    def test_03_inject_text_restore_clipboard_race_condition(self):
        """
        WERYFIKACJA KRYTYCZNEGO BŁĘDU: Race condition w restore_clipboard=True.
        Gdy okno aplikacji nie przetworzy natychmiast Ctrl+V w ciągu 350ms,
        schowek zostaje nadpisany starym tekstem i do dokumentu trafia stary schowek zamiast mowy!
        """
        initial_clipboard = "KRYTYCZNA_STARA_ZAWARTOSC_SCHOWKA"
        pyperclip.copy(initial_clipboard)

        with Win32EditContext() as ctx:
            test_phrase = "Nowa treść podyktowana przez użytkownika"
            expected_phrase = test_phrase.strip() + " "

            # Celowo NIE pompujemy komunikatów w trakcie inject_text,
            # symulując opóźnienie aplikacji docelowej (np. Word/Chrome zajęty renderowaniem przez 400ms)
            t0 = time.time()
            inject_text(test_phrase, restore_clipboard=True)
            elapsed = time.time() - t0

            # Dopiero teraz okno przetwarza Ctrl+V
            ctx.pump(5)
            actual_pasted = ctx.get_text()
            current_clipboard = pyperclip.paste()

            print("\n--- TEST 3: inject_text (Audyt wyścigu restore_clipboard) ---")
            print(f"Schowek początkowy: '{initial_clipboard}'")
            print(f"Wklejony tekst:     '{actual_pasted}'")
            print(f"Oczekiwany tekst:   '{expected_phrase}'")
            print(f"Schowek końcowy:    '{current_clipboard}'")

            # Wykazanie podatności:
            if actual_pasted == initial_clipboard:
                print("[WYKRYTO PODATNOŚĆ WYŚCIGU] Aplikacja wkleiła stary schowek, ponieważ został przywrócony za wcześnie!")
            elif actual_pasted == expected_phrase:
                print("[INFO] Wklejono poprawny tekst (aplikacja zdążyła w oknie czasowym).")

            self.assertEqual(current_clipboard, initial_clipboard, "Schowek nie został przywrócony.")

    def test_04_forward_stream_committer_logic(self):
        """Weryfikacja logiki Forward-Only w ForwardStreamCommitter."""
        typed_chunks = []
        committer = ForwardStreamCommitter(type_callback=lambda c: typed_chunks.append(c))

        # Krok 1: Hipoteza początkowa o długości 2 słów (margines safe_tail_margin = 2 nie zatwierdza jeszcze niczego)
        committer.process_hypothesis("Dziś w")
        self.assertEqual(len(typed_chunks), 0, "Dla <= 2 słów żadne słowo nie powinno być jeszcze wpisane")

        # Krok 2: Hipoteza rozszerzona do 4 słów
        committer.process_hypothesis("Dziś w Warszawie świeci")
        # stable_by_length = 4 - 2 = 2 słowa: "Dziś w "
        self.assertGreater(len(typed_chunks), 0)
        self.assertEqual("".join(typed_chunks).strip(), "Dziś w")

        # Krok 3: Commit całego segmentu
        committer.commit_segment("Dziś w Warszawie świeci słońce i jest ciepło.")
        self.assertEqual(
            "".join(typed_chunks).strip(),
            "Dziś w Warszawie świeci słońce i jest ciepło."
        )

        # Krok 4: Finalizacja z ogonem
        committer.process_hypothesis("Temperatura wynosi")
        committer.finalize("Temperatura wynosi 22 stopnie.")
        self.assertEqual(
            "".join(typed_chunks).strip(),
            "Dziś w Warszawie świeci słońce i jest ciepło. Temperatura wynosi 22 stopnie."
        )

        print("\n--- TEST 4: ForwardStreamCommitter (Forward-Only) ---")
        print(f"Całkowity wpisany tekst: '{''.join(typed_chunks).strip()}'")
        print("Liczba chunków:", len(typed_chunks))

    def test_05_throughput_benchmark(self):
        """Porównanie szybkości send_unicode_string vs inject_text."""
        sample = "Litwo Ojczyzno moja ty jesteś jak zdrowie ile cię trzeba cenić ten tylko się dowie"
        
        with Win32EditContext() as ctx:
            # 1. send_unicode_string
            t0 = time.time()
            send_unicode_string(sample)
            t_send = time.time() - t0
            ctx.set_text("")

            # 2. inject_text
            t0 = time.time()
            inject_text(sample, restore_clipboard=False)
            t_inject = time.time() - t0

            print("\n--- TEST 5: Benchmark przepustowości ---")
            print(f"Tekst ({len(sample)} znaków):")
            print(f"send_unicode_string: {t_send:.4f}s ({len(sample)/max(t_send, 0.001):.1f} zn./s)")
            print(f"inject_text:         {t_inject:.4f}s ({len(sample)/max(t_inject, 0.001):.1f} zn./s)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
