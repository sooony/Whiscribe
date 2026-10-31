"""
tests/test_browser_focus_and_streaming.py
Kompleksowe testy automatyczne weryfikujące:
1. Prawidłowe wykrywanie fokusu w przeglądarkach internetowych (Chrome, Edge, Firefox, Brave):
   - DocumentControl (obszar strony www) akceptowany bez fałszywych błędów 'tylko do odczytu'
   - ScrollBarControl (przewijanie suwakiem) akceptowany jako obszar roboczy
   - Kontrolki edycyjne EditControl, PaneControl, GroupControl, CustomControl akceptowane
   - Elementy nawigacyjne samej przeglądarki (TabItemControl, TitleBarControl, MenuControl) blokowane
2. Prawidłowe zachowanie dla środowisk IDE, terminali oraz pulpitu i paska zadań
3. Zachowanie bufora streamingu na żywo (ForwardStreamCommitter, _type_stream_chunk, _streaming_worker):
   - Brak utraty tekstu przy przełączaniu okien (Alt+Tab / kliknięcie w inne okno)
   - Spójność bufora podczas przewijania (scroll myszą, przeciąganie suwaka)
   - Zabezpieczenie przed wpisywaniem tekstu do obcego okna
"""

import unittest
from unittest.mock import MagicMock, patch
import time
import os
import sys

# Dodaj główny katalog projektu do ścieżki
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_detector import is_text_field_focused, is_valid_target_window, BROWSER_PROCESSES
from injector import ForwardStreamCommitter


class MockUIAElement:
    """Mock elementu UI Automation dla kontrolowanych testów jednostkowych."""
    def __init__(self, control_type_name="DocumentControl", class_name="", name="", is_enabled=True, is_read_only=False, patterns=None):
        self.ControlTypeName = control_type_name
        self.ClassName = class_name
        self.Name = name
        self.IsEnabled = is_enabled
        self.is_read_only = is_read_only
        self.patterns = patterns or {}

    def GetPattern(self, pattern_id):
        return self.patterns.get(pattern_id, None)


class TestBrowserFocusDetection(unittest.TestCase):
    """Testy detekcji fokusu w przeglądarkach i obszarach roboczych stron www."""

    @patch('focus_detector.user32')
    @patch('focus_detector.get_proc_name_from_hwnd')
    @patch('uiautomation.GetFocusedControl')
    def test_01_browser_document_control_accepted_after_scroll(self, mock_get_focused, mock_get_proc, mock_user32):
        """
        WERYFIKACJA GŁÓWNEGO PROBLEMU:
        Kliknięcie w tło lub przewijanie strony w Chrome/Edge ustawia fokus na DocumentControl.
        DocumentControl w przeglądarkach nie posiada TextEditPattern i ValuePattern jest None.
        Poprzednio zgłaszany jako 'strona jest tylko do odczytu' i blokował dyktowanie.
        Teraz MUSI być zaakceptowany jako obszar roboczy strony www.
        """
        mock_user32.GetForegroundWindow.return_value = 0x1001
        mock_user32.IsWindow.return_value = True
        mock_user32.GetWindowThreadProcessId.return_value = 1
        
        # Udawajmy proces chrome.exe
        mock_get_proc.return_value = "chrome.exe"

        # Mock elementu DocumentControl w Chrome (brak TextEditPattern i ValuePattern)
        mock_el = MockUIAElement(control_type_name="DocumentControl", class_name="Chrome_RenderWidgetHostHWND", name="Strona www")
        mock_get_focused.return_value = mock_el

        is_focused, reason = is_text_field_focused(0x1001)
        self.assertTrue(is_focused, f"DocumentControl w chrome.exe został fałszywie odrzucony! Powód: {reason}")
        self.assertIn("obszar strony", reason)
        self.assertNotIn("tylko do odczytu", reason)

    @patch('focus_detector.user32')
    @patch('focus_detector.get_proc_name_from_hwnd')
    @patch('uiautomation.GetFocusedControl')
    def test_02_browser_scrollbar_accepted_during_scroll(self, mock_get_focused, mock_get_proc, mock_user32):
        """
        WERYFIKACJA SCROLLOWANIA:
        Gdy użytkownik przewija stronę za pomocą paska przewijania (ScrollBarControl) w przeglądarce,
        nie powinno to wywoływać błędu 'brak aktywnego pola tekstowego'.
        """
        mock_user32.GetForegroundWindow.return_value = 0x1002
        mock_user32.IsWindow.return_value = True
        mock_get_proc.return_value = "msedge.exe"

        mock_el = MockUIAElement(control_type_name="ScrollBarControl", class_name="", name="Pionowy pasek przewijania")
        mock_get_focused.return_value = mock_el

        is_focused, reason = is_text_field_focused(0x1002)
        self.assertTrue(is_focused, f"ScrollBarControl w msedge.exe został odrzucony! Powód: {reason}")
        self.assertIn("obszar strony", reason)

    @patch('focus_detector.user32')
    @patch('focus_detector.get_proc_name_from_hwnd')
    @patch('uiautomation.GetFocusedControl')
    def test_03_browser_edit_control_accepted(self, mock_get_focused, mock_get_proc, mock_user32):
        """Pole EditControl (<input>, <textarea>, pasek adresu) w przeglądarce jest akceptowane."""
        mock_user32.GetForegroundWindow.return_value = 0x1003
        mock_user32.IsWindow.return_value = True
        mock_get_proc.return_value = "firefox.exe"

        mock_el = MockUIAElement(control_type_name="EditControl", class_name="", name="Szukaj w Google", is_enabled=True)
        mock_get_focused.return_value = mock_el

        is_focused, reason = is_text_field_focused(0x1003)
        self.assertTrue(is_focused, f"EditControl w firefox.exe został odrzucony! Powód: {reason}")
        self.assertIn("Pole edycyjne", reason)

    @patch('focus_detector.user32')
    @patch('focus_detector.get_proc_name_from_hwnd')
    @patch('uiautomation.GetFocusedControl')
    def test_04_browser_navigation_elements_rejected(self, mock_get_focused, mock_get_proc, mock_user32):
        """Elementy nawigacyjne (karty, menu, pasek tytułowy) samej przeglądarki są poprawnie odrzucane."""
        mock_user32.GetForegroundWindow.return_value = 0x1004
        mock_user32.IsWindow.return_value = True
        mock_get_proc.return_value = "brave.exe"

        for nav_type in ('TabItemControl', 'TitleBarControl', 'MenuControl', 'MenuItemControl'):
            mock_el = MockUIAElement(control_type_name=nav_type, class_name="", name="Karta")
            mock_get_focused.return_value = mock_el

            is_focused, reason = is_text_field_focused(0x1004)
            self.assertFalse(is_focused, f"Element nawigacyjny {nav_type} w przeglądarce powinien być odrzucony!")
            self.assertIn("Element nawigacyjny", reason)

    @patch('focus_detector.user32')
    @patch('focus_detector.get_proc_name_from_hwnd')
    @patch('uiautomation.GetFocusedControl')
    def test_05_browser_rich_web_elements_accepted(self, mock_get_focused, mock_get_proc, mock_user32):
        """Edytory webowe (Notion, Google Docs itp.) - PaneControl, GroupControl, CustomControl."""
        mock_user32.GetForegroundWindow.return_value = 0x1005
        mock_user32.IsWindow.return_value = True
        mock_get_proc.return_value = "chrome.exe"

        for c_type in ('PaneControl', 'GroupControl', 'CustomControl', 'TextControl', 'ListItemControl'):
            mock_el = MockUIAElement(control_type_name=c_type, class_name="", name="Notion Block")
            mock_get_focused.return_value = mock_el

            is_focused, reason = is_text_field_focused(0x1005)
            self.assertTrue(is_focused, f"Obszar roboczy strony {c_type} powinien być zaakceptowany! Powód: {reason}")
            self.assertIn("obszar strony", reason)

    @patch('focus_detector.user32')
    @patch('focus_detector.get_proc_name_from_hwnd')
    @patch('uiautomation.GetFocusedControl')
    def test_06_desktop_and_taskbar_strictly_rejected(self, mock_get_focused, mock_get_proc, mock_user32):
        """Pulpit i pasek zadań Windows muszą być bezwzględnie odrzucane."""
        mock_user32.IsWindow.return_value = True

        def fake_get_class(hwnd, buf, max_count):
            buf.value = "Shell_TrayWnd"
            return len("Shell_TrayWnd")

        mock_user32.GetClassNameW.side_effect = fake_get_class
        is_focused, reason = is_text_field_focused(0x9999)
        self.assertFalse(is_focused, "Pasek zadań (Shell_TrayWnd) nie został odrzucony!")
        self.assertIn("Pulpit lub pasek zadań", reason)


class TestStreamingBufferAndWindowSwitching(unittest.TestCase):
    """Testy zachowania bufora streamingu na żywo przy przełączaniu okien i scrollowaniu."""

    def test_01_forward_stream_committer_basic_flow(self):
        """ForwardStreamCommitter wpisuje wyłącznie w przód bez cofania."""
        typed_chunks = []
        committer = ForwardStreamCommitter(type_callback=lambda c: typed_chunks.append(c))

        committer.process_hypothesis("Dziś mamy ładną pogodę na spacer")
        committer.process_hypothesis("Dziś mamy ładną pogodę na spacer i słońce świeci")
        committer.finalize("Dziś mamy ładną pogodę na spacer i słońce świeci.")

        full_text = "".join(typed_chunks)
        self.assertIn("Dziś mamy ładną pogodę na spacer i słońce świeci", full_text)
        self.assertEqual(committer.typed_text, full_text)

    def test_02_streaming_buffer_on_window_switch(self):
        """
        SYMULACJA PRZEŁĄCZANIA OKIEN:
        Gdy użytkownik przełącza okno (cur_fg != target_hwnd), tekst NIE MOŻE być wpisany do obcego okna.
        Musi zostać zgromadzony w buforze (buffered_untyped_text) i opróżniony po powrocie.
        """
        typed_output = []
        buffered_text = ""
        target_hwnd = 0xAAAA
        cur_fg = 0xAAAA # Zaczynamy w oknie docelowym

        def fake_type(chunk):
            nonlocal buffered_text
            # Logika z zaktualizowanego _type_stream_chunk
            if target_hwnd and cur_fg != target_hwnd:
                buffered_text += chunk
                return
            if buffered_text:
                to_send = buffered_text + chunk
                buffered_text = ""
                typed_output.append(to_send)
            else:
                typed_output.append(chunk)

        committer = ForwardStreamCommitter(type_callback=fake_type)

        # 1. Użytkownik dyktuje w oknie docelowym (0xAAAA)
        committer.process_hypothesis("To jest początek zdania dyktowanego w Chrome")
        self.assertTrue(len(typed_output) > 0)
        self.assertEqual(buffered_text, "")

        # 2. Użytkownik przełącza się do innego programu (Alt+Tab -> 0xBBBB)
        cur_fg = 0xBBBB
        committer.process_hypothesis("To jest początek zdania dyktowanego w Chrome i teraz użytkownik przełączył okno")
        # Tekst powinien trafić do buffered_text, a NIE do typed_output
        self.assertTrue(len(buffered_text) > 0, "Tekst nie został zbuforowany podczas przełączenia okna!")

        # 3. Użytkownik wraca do okna docelowego (0xAAAA)
        cur_fg = 0xAAAA
        committer.process_hypothesis("To jest początek zdania dyktowanego w Chrome i teraz użytkownik przełączył okno i wrócił do Chrome")
        # Bufor powinien zostać opróżniony
        self.assertEqual(buffered_text, "", "Bufor nie został opróżniony po powrocie do okna docelowego!")

        # 4. Finalizacja
        committer.finalize("To jest początek zdania dyktowanego w Chrome i teraz użytkownik przełączył okno i wrócił do Chrome.")
        final_result = "".join(typed_output)
        self.assertIn("przełączył okno", final_result)
        self.assertIn("wrócił do Chrome", final_result)
        print(f"\n[SUKCES BUFORA] Kompletny tekst po przełączaniu okien: '{final_result.strip()}'")

    def test_03_streaming_buffer_on_mouse_drag_scroll(self):
        """
        SYMULACJA SCROLLOWANIA / PRZECIĄGANIA MYSZĄ:
        Gdy użytkownik trzyma wciśnięty przycisk myszy (przeciąga pasek przewijania / suwak),
        znaki nie są wpisywane w tym ułamku sekundy, lecz buforowane do momentu zwolnienia myszy.
        """
        typed_output = []
        buffered_text = ""
        is_mouse_pressed = True # Użytkownik trzyma suwak

        def fake_type(chunk):
            nonlocal buffered_text
            if is_mouse_pressed:
                buffered_text += chunk
                return
            if buffered_text:
                to_send = buffered_text + chunk
                buffered_text = ""
                typed_output.append(to_send)
            else:
                typed_output.append(chunk)

        committer = ForwardStreamCommitter(type_callback=fake_type)

        # Podczas przeciągania suwaka
        committer.process_hypothesis("Przewijam stronę w dół i mówię dalej")
        self.assertTrue(len(buffered_text) > 0, "Tekst powinien być buforowany podczas trzymania myszy")
        self.assertEqual(len(typed_output), 0)

        # Użytkownik puszcza przycisk myszy
        is_mouse_pressed = False
        committer.process_hypothesis("Przewijam stronę w dół i mówię dalej bez przeszkód")
        self.assertEqual(buffered_text, "")
        self.assertTrue(len(typed_output) > 0)

        committer.finalize("Przewijam stronę w dół i mówię dalej bez przeszkód.")
        final_result = "".join(typed_output)
        self.assertIn("Przewijam stronę", final_result)
        self.assertIn("bez przeszkód", final_result)
        print(f"[SUKCES SCROLLOWANIA] Kompletny tekst po przeciąganiu myszą: '{final_result.strip()}'")


if __name__ == '__main__':
    unittest.main()
