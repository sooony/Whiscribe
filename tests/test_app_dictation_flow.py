"""
tests/test_app_dictation_flow.py
Test integracyjny symulujący pełny cykl aplikacji Whiscribe:
1. start_recording() na oknie przeglądarki (DocumentControl) -> brak dymka błędu, brak dźwięku błędu.
2. start_recording() na pulpicie (Progman) -> dymek błędu i dźwięk błędu wywołane prawidłowo.
3. toggle_dictation() - przełączanie stanów.
4. _type_stream_chunk() i buforowanie podczas przełączania okien.
"""

import unittest
from unittest.mock import MagicMock, patch
import time
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockOverlay:
    def __init__(self):
        self.hwnd = 0x9999
        self.mode = "idle"
        self.balloon_shown = False
        self.balloon_hidden = False
        self.shown = False

    def is_minimized(self):
        return False

    def show(self):
        self.shown = True

    def show_recording(self):
        self.mode = "recording"

    def show_processing(self):
        self.mode = "processing"

    def show_idle(self):
        self.mode = "idle"

    def show_error_balloon(self, duration_s=7.0):
        self.balloon_shown = True

    def hide_balloon(self):
        self.balloon_hidden = True

    def add_transcript_entry(self, text):
        pass

    def update_live_text(self, text):
        pass

    def clear_transcript(self):
        pass


class TestAppDictationFlow(unittest.TestCase):
    """Testy przepływu start/stop nagrywania w aplikacji."""

    @patch('app.AudioRecorder')
    @patch('app.Transcriber')
    @patch('app.FloatingOverlay')
    @patch('app.pystray')
    @patch('app.keyboard')
    @patch('app._play_chime_file')
    @patch('focus_detector.user32')
    @patch('app.user32')
    @patch('app.get_proc_name_from_hwnd')
    @patch('focus_detector.get_proc_name_from_hwnd')
    @patch('uiautomation.GetFocusedControl')
    def test_01_browser_start_recording_no_error_balloon(
        self, mock_get_focused, mock_foc_proc, mock_get_proc, mock_user32, mock_foc_user32, mock_play_chime,
        mock_kb, mock_tray, mock_overlay_cls, mock_trans_cls, mock_rec_cls
    ):
        """
        Główny przypadek użycia:
        Użytkownik znajduje się na stronie w Chrome/Edge (DocumentControl).
        Wywołanie start_recording() NIE MOŻE wywoływać _play_error_chime() ani show_error_balloon()!
        Musi wejść w stan 'recording'.
        """
        from app import DictationApp

        # Konfiguracja środowiska
        mock_user32.GetForegroundWindow.return_value = 0x1234
        mock_user32.IsWindow.return_value = True
        mock_user32.IsWindowVisible.return_value = True
        mock_user32.GetWindowThreadProcessId.return_value = 1
        mock_user32.GetWindowTextLengthW.return_value = 0

        mock_foc_user32.GetForegroundWindow.return_value = 0x1234
        mock_foc_user32.IsWindow.return_value = True
        mock_foc_user32.IsWindowVisible.return_value = True
        mock_foc_user32.GetWindowThreadProcessId.return_value = 1

        def fake_get_class(hwnd, buf, max_count):
            buf.value = "Chrome_WidgetWin_1"
            return len("Chrome_WidgetWin_1")

        mock_user32.GetClassNameW.side_effect = fake_get_class
        mock_foc_user32.GetClassNameW.side_effect = fake_get_class
        mock_get_proc.return_value = "chrome.exe"
        mock_foc_proc.return_value = "chrome.exe"

        mock_el = MagicMock()
        mock_el.ControlTypeName = "DocumentControl"
        mock_el.ClassName = "Chrome_RenderWidgetHostHWND"
        mock_el.Name = "Web Page"
        mock_get_focused.return_value = mock_el

        # Tworzenie instancji aplikacji z zamockowanymi wątkami
        with patch.object(DictationApp, '_monitor_silence', return_value=None), \
             patch.object(DictationApp, '_listen_for_show_event', return_value=None), \
             patch.object(DictationApp, '_watchdog_hotkey', return_value=None), \
             patch.object(DictationApp, '_tray_anim_worker', return_value=None):
            
            app = DictationApp()
            app.overlay = MockOverlay()
            app.config["require_text_field"] = True
            app.config["sound_feedback"] = True

            # Uruchom start_recording
            app.start_recording()

            # Asercje:
            self.assertFalse(app.overlay.balloon_shown, "BŁĄD: Dymek błędu (show_error_balloon) został bezpodstawnie wyświetlony na stronie www!")
            self.assertEqual(app.state, "recording", f"Stan aplikacji powinien być 'recording', a jest {app.state}")
            self.assertEqual(app.target_hwnd, 0x1234)

            # Sprawdź odtworzone dźwięki - nie powinien być odtworzony dźwięk 'error'
            chime_calls = [call.args[0] for call in mock_play_chime.call_args_list]
            self.assertNotIn('error', chime_calls, f"Dźwięk błędu 'error' został bezpodstawnie odtworzony! Wywołania: {chime_calls}")
            self.assertTrue(any('start' in c for c in chime_calls), f"Dźwięk startu powinien zostać odtworzony! Wywołania: {chime_calls}")

            print("\n[PASSED] start_recording na stronie www w Chrome uruchamia się bez błędów i bez dymka!")

    @patch('app.AudioRecorder')
    @patch('app.Transcriber')
    @patch('app.FloatingOverlay')
    @patch('app.pystray')
    @patch('app.keyboard')
    @patch('app._play_chime_file')
    @patch('focus_detector.user32')
    @patch('app.user32')
    @patch('app.get_proc_name_from_hwnd')
    @patch('focus_detector.get_proc_name_from_hwnd')
    @patch('uiautomation.GetFocusedControl')
    def test_02_desktop_start_recording_shows_error_balloon(
        self, mock_get_focused, mock_foc_proc, mock_get_proc, mock_user32, mock_foc_user32, mock_play_chime,
        mock_kb, mock_tray, mock_overlay_cls, mock_trans_cls, mock_rec_cls
    ):
        """
        Ochrona pulpitu:
        Gdy użytkownik kliknie na pulpit Windows (Progman / Shell_TrayWnd),
        aplikacja MUSI zablokować start, odtworzyć dźwięk błędu i pokazać dymek.
        """
        from app import DictationApp

        mock_user32.GetForegroundWindow.return_value = 0x5678
        mock_user32.IsWindow.return_value = True
        mock_user32.IsWindowVisible.return_value = True

        mock_foc_user32.GetForegroundWindow.return_value = 0x5678
        mock_foc_user32.IsWindow.return_value = True
        mock_foc_user32.IsWindowVisible.return_value = True

        def fake_get_class(hwnd, buf, max_count):
            buf.value = "Progman"
            return len("Progman")

        mock_user32.GetClassNameW.side_effect = fake_get_class
        mock_foc_user32.GetClassNameW.side_effect = fake_get_class
        mock_get_proc.return_value = "explorer.exe"
        mock_foc_proc.return_value = "explorer.exe"

        with patch.object(DictationApp, '_monitor_silence', return_value=None), \
             patch.object(DictationApp, '_listen_for_show_event', return_value=None), \
             patch.object(DictationApp, '_watchdog_hotkey', return_value=None), \
             patch.object(DictationApp, '_tray_anim_worker', return_value=None):
            
            app = DictationApp()
            app.overlay = MockOverlay()
            app.config["require_text_field"] = True
            app.config["sound_feedback"] = True

            app.start_recording()

            self.assertTrue(app.overlay.balloon_shown, "Dymek błędu powinien pojawić się po kliknięciu na Pulpit!")
            self.assertEqual(app.state, "idle", "Stan aplikacji nie powinien zmienić się na 'recording'")

            chime_calls = [call.args[0] for call in mock_play_chime.call_args_list]
            self.assertIn('error', chime_calls, "Dźwięk błędu 'error' powinien zostać odtworzony dla Pulpitu")

            print("[PASSED] start_recording na Pulpicie Windows prawidłowo blokuje start i wyświetla ostrzeżenie.")

    @patch('app.AudioRecorder')
    @patch('app.Transcriber')
    @patch('app.FloatingOverlay')
    @patch('app.pystray')
    @patch('app.keyboard')
    @patch('app._play_chime_file')
    @patch('focus_detector.user32')
    @patch('app.user32')
    @patch('app.get_proc_name_from_hwnd')
    @patch('focus_detector.get_proc_name_from_hwnd')
    @patch('uiautomation.GetFocusedControl')
    def test_03_toggle_dictation_flow(
        self, mock_get_focused, mock_foc_proc, mock_get_proc, mock_user32, mock_foc_user32, mock_play_chime,
        mock_kb, mock_tray, mock_overlay_cls, mock_trans_cls, mock_rec_cls
    ):
        """Test naciśnięcia skrótu w trybie toggle (start -> stop)."""
        from app import DictationApp

        mock_user32.GetForegroundWindow.return_value = 0x1234
        mock_user32.IsWindow.return_value = True
        mock_user32.IsWindowVisible.return_value = True
        mock_user32.GetWindowThreadProcessId.return_value = 1
        mock_user32.GetWindowTextLengthW.return_value = 0

        mock_foc_user32.GetForegroundWindow.return_value = 0x1234
        mock_foc_user32.IsWindow.return_value = True
        mock_foc_user32.IsWindowVisible.return_value = True
        mock_foc_user32.GetWindowThreadProcessId.return_value = 1

        def fake_get_class(hwnd, buf, max_count):
            buf.value = "Chrome_WidgetWin_1"
            return len("Chrome_WidgetWin_1")

        mock_user32.GetClassNameW.side_effect = fake_get_class
        mock_foc_user32.GetClassNameW.side_effect = fake_get_class
        mock_get_proc.return_value = "chrome.exe"
        mock_foc_proc.return_value = "chrome.exe"

        mock_el = MagicMock()
        mock_el.ControlTypeName = "DocumentControl"
        mock_el.ClassName = "Chrome_RenderWidgetHostHWND"
        mock_el.Name = "Web Page"
        mock_get_focused.return_value = mock_el

        with patch.object(DictationApp, '_monitor_silence', return_value=None), \
             patch.object(DictationApp, '_listen_for_show_event', return_value=None), \
             patch.object(DictationApp, '_watchdog_hotkey', return_value=None), \
             patch.object(DictationApp, '_tray_anim_worker', return_value=None):
            
            app = DictationApp()
            app.overlay = MockOverlay()
            app._last_toggle_time = 0.0

            # Pierwsze naciśnięcie: start dyktowania
            app.toggle_dictation()
            self.assertEqual(app.state, "recording")

            # Drugie naciśnięcie: stop dyktowania
            app._last_toggle_time = 0.0
            with patch.object(app, '_process_audio_worker'):
                app.toggle_dictation()
                self.assertEqual(app.state, "processing")

            print("[PASSED] toggle_dictation prawidłowo przełącza ze stanu idle do recording i następnie processing.")

    @patch('app.AudioRecorder')
    @patch('app.Transcriber')
    @patch('app.FloatingOverlay')
    @patch('app.pystray')
    @patch('app.keyboard')
    @patch('app.send_unicode_string')
    @patch('app.user32')
    @patch('app.is_mouse_down')
    def test_04_type_stream_chunk_buffering_behavior(
        self, mock_mouse_down, mock_user32, mock_send_unicode,
        mock_kb, mock_tray, mock_overlay_cls, mock_trans_cls, mock_rec_cls
    ):
        """Weryfikacja czy _type_stream_chunk buforuje znaki, gdy inne okno jest aktywne lub mysz jest wciśnięta."""
        from app import DictationApp

        with patch.object(DictationApp, '_monitor_silence', return_value=None), \
             patch.object(DictationApp, '_listen_for_show_event', return_value=None), \
             patch.object(DictationApp, '_watchdog_hotkey', return_value=None), \
             patch.object(DictationApp, '_tray_anim_worker', return_value=None):
            
            app = DictationApp()
            app.target_hwnd = 0x1111
            mock_user32.IsWindow.return_value = True

            # 1. Okno docelowe aktywne, mysz nie jest wciśnięta -> natychmiastowe wpisanie
            mock_user32.GetForegroundWindow.return_value = 0x1111
            mock_mouse_down.return_value = False

            app._type_stream_chunk("Pierwszy fragment ")
            mock_send_unicode.assert_called_with("Pierwszy fragment ")
            self.assertEqual(app.buffered_untyped_text, "")

            # 2. Użytkownik przełączył okno na inne (0x2222) -> buforowanie
            mock_send_unicode.reset_mock()
            mock_user32.GetForegroundWindow.return_value = 0x2222
            app._type_stream_chunk("Drugi fragment ")
            mock_send_unicode.assert_not_called()
            self.assertEqual(app.buffered_untyped_text, "Drugi fragment ")

            # 3. Użytkownik wraca do okna docelowego (0x1111) -> opróżnienie bufora + nowy fragment
            mock_user32.GetForegroundWindow.return_value = 0x1111
            app._type_stream_chunk("Trzeci fragment ")
            mock_send_unicode.assert_called_with("Drugi fragment Trzeci fragment ")
            self.assertEqual(app.buffered_untyped_text, "")

            # 4. Mysz jest wciśnięta (przeciąganie suwaka) -> buforowanie
            mock_send_unicode.reset_mock()
            mock_mouse_down.return_value = True
            app._type_stream_chunk("Czwarty fragment ")
            mock_send_unicode.assert_not_called()
            self.assertEqual(app.buffered_untyped_text, "Czwarty fragment ")

            print("[PASSED] _type_stream_chunk prawidłowo buforuje tekst przy braku fokusu docelowego oraz podczas przeciągania myszą.")


if __name__ == '__main__':
    unittest.main()
