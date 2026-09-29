import sys
import os
import unittest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from overlay import FloatingOverlay, THEMES
from config import DEFAULT_CONFIG
import app

class TestV2Features(unittest.TestCase):
    def test_themes_edge_alphas(self):
        """Weryfikacja czy w każdym z 5 motywów ramka zewnętrzna ma ściśle alpha = 0 (brak uciętego bluru)."""
        for theme_name in THEMES.keys():
            overlay = FloatingOverlay(theme=theme_name)
            # Renderujemy idle
            overlay.show_idle()
            import ctypes
            overlay._render_frame(1.0)
            arr = np.ctypeslib.as_array(ctypes.cast(overlay.p_bits, ctypes.POINTER(ctypes.c_uint8)), shape=(overlay.h, overlay.w, 4))
            top_max = np.max(arr[0, :, 3])
            bottom_max = np.max(arr[-1, :, 3])
            left_max = np.max(arr[:, 0, 3])
            right_max = np.max(arr[:, -1, 3])
            self.assertEqual(top_max, 0, f"Theme {theme_name} has non-zero top edge alpha: {top_max}")
            self.assertEqual(bottom_max, 0, f"Theme {theme_name} has non-zero bottom edge alpha: {bottom_max}")
            self.assertEqual(left_max, 0, f"Theme {theme_name} has non-zero left edge alpha: {left_max}")
            self.assertEqual(right_max, 0, f"Theme {theme_name} has non-zero right edge alpha: {right_max}")
            overlay.close()

    def test_minimize_button_hit_test(self):
        """Weryfikacja czy przycisk minimalizacji prawidłowo reaguje na kliknięcie."""
        minimized = []
        overlay = FloatingOverlay(theme="light")
        overlay.set_callbacks(
            on_stop=lambda: None,
            on_close=lambda: None,
            on_toggle=lambda: None,
            on_meeting_toggle=lambda: None,
            on_minimize=lambda: minimized.append(True)
        )
        # min_cx to self.mx + 14, min_cy to self.my + 12
        target = overlay._get_target(overlay.min_cx, overlay.min_cy)
        self.assertIn(target, ("btn_bar_minimize", "btn_minimize"), "Target at minimize coords must be 'btn_bar_minimize'")
        
        # Test wywołania callbacku
        overlay.on_minimize_callback()
        self.assertTrue(len(minimized) > 0 and minimized[0], "Minimize callback must be executed")
        overlay.close()

    def test_sound_preset_synthesis(self):
        """Weryfikacja syntezy wszystkich 4 presetów dźwięków startu i stopu."""
        generators = [
            ("start_1", app._make_sound_start_1),
            ("start_2", app._make_sound_start_2),
            ("start_3", app._make_sound_start_3),
            ("start_4", app._make_sound_start_4),
            ("stop_1", app._make_sound_stop_1),
            ("stop_2", app._make_sound_stop_2),
            ("stop_3", app._make_sound_stop_3),
            ("stop_4", app._make_sound_stop_4),
            ("ready", app._make_sound_ready),
            ("error", app._make_sound_error)
        ]
        for name, fn in generators:
            data = fn()
            self.assertGreater(len(data), 100, f"Sound {name} generated too few bytes")
            # Sprawdź czy to poprawny nagłówek RIFF/WAVE
            self.assertEqual(data[:4], b"RIFF", f"Sound {name} missing RIFF header")
            self.assertEqual(data[8:12], b"WAVE", f"Sound {name} missing WAVE tag")

    def test_tray_icon_generation(self):
        """Weryfikacja dynamicznego generowania ikon system tray dla wszystkich stanów i klatek animacji."""
        states = ["idle", "recording", "meeting", "processing"]
        for st in states:
            for frame in range(5):
                img = app.create_tray_icon_image(state=st, frame_idx=frame, vol=0.7)
                self.assertEqual(img.size, (64, 64))
                self.assertEqual(img.mode, "RGBA")

    def test_taskbar_minimize_and_restore(self):
        """Weryfikacja minimalizacji do dolnego paska zadań Windows i przywracania."""
        import time
        overlay = FloatingOverlay(theme="light")
        overlay.show()
        time.sleep(0.1)
        self.assertFalse(overlay.is_minimized())
        overlay.minimize()
        time.sleep(0.1)
        self.assertTrue(overlay.is_minimized())
        overlay.restore()
        time.sleep(0.1)
        self.assertFalse(overlay.is_minimized())
        overlay.close()

    def test_hover_and_active_no_alpha_punching(self):
        """Weryfikacja czy stany hover i aktywny we wszystkich 5 motywach nie dziurawią kanału alpha (brak białych plam)."""
        import ctypes
        for theme in THEMES.keys():
            overlay = FloatingOverlay(theme=theme)
            targets = [
                ('btn_bar_menu', int(overlay.bar_menu_cx), int(overlay.bar_menu_cy)),
                ('btn_bar_minimize', int(overlay.bar_min_cx), int(overlay.bar_min_cy)),
                ('btn_bar_close', int(overlay.bar_close_cx), int(overlay.bar_close_cy)),
                ('btn_toggle_transcript', int(overlay.tgl_btn_x + overlay.tgl_btn_w/2), int(overlay.tgl_btn_y + overlay.tgl_btn_h/2))
            ]
            for t_name, cx, cy in targets:
                overlay._hover_target = t_name
                overlay._render_frame(1.0)
                arr = np.ctypeslib.as_array(ctypes.cast(overlay.p_bits, ctypes.POINTER(ctypes.c_uint8)), shape=(overlay.h, overlay.w, 4))
                dib_y = overlay.h - 1 - cy
                patch = arr[dib_y-4:dib_y+5, cx-4:cx+5, 3]
                min_a = np.min(patch)
                self.assertGreaterEqual(min_a, 200, f"Theme {theme} {t_name} min_alpha={min_a} (musi być kryjący >= 200)")

            # Aktywny przycisk transkrypcji (Zwiń transkrypcję)
            overlay.panel_open = True
            overlay._hover_target = None
            overlay._render_frame(1.0)
            arr = np.ctypeslib.as_array(ctypes.cast(overlay.p_bits, ctypes.POINTER(ctypes.c_uint8)), shape=(overlay.h, overlay.w, 4))
            cy = int(overlay.tgl_btn_y + overlay.tgl_btn_h/2)
            cx = int(overlay.tgl_btn_x + 25)
            dib_y = overlay.h - 1 - cy
            patch = arr[dib_y-4:dib_y+5, cx-4:cx+5, 3]
            min_a = np.min(patch)
            self.assertGreaterEqual(min_a, 200, f"Theme {theme} panel_open min_alpha={min_a}")

            overlay.close()

    def test_three_dots_menu_integration(self):
        """Weryfikacja podłączenia menu trzech kropek do menu tray_icon bez błędów Win32."""
        import pystray, time, threading, ctypes
        from PIL import Image

        handler_called = []
        menu = pystray.Menu(
            pystray.MenuItem("Opcja Testowa", lambda icon, item: handler_called.append(True))
        )
        icon = pystray.Icon("TestWhiscribe", Image.new("RGB", (16, 16)), "Test", menu)
        icon.run_detached()
        time.sleep(0.2)

        icon.update_menu()
        self.assertIsNotNone(icon._menu_handle)
        hmenu, descriptors = icon._menu_handle
        self.assertGreaterEqual(len(descriptors), 1)

        # Wywołanie deskryptora (dokładnie tak jak w _show_settings_menu)
        descriptors[0](icon)
        self.assertTrue(len(handler_called) > 0 and handler_called[0])

        # Test wywołania _show_settings_menu z wątku roboczego z własnym oknem hosta
        class MockApp:
            def __init__(self):
                self.config = {"theme": "dark", "stream_realtime": False, "require_text_field": True}
                self.state = "idle"
                self.overlay = None
                self.tray_icon = icon

            _show_settings_menu = app.DictationApp._show_settings_menu
            _show_fallback_win32_menu = app.DictationApp._show_fallback_win32_menu

        mock = MockApp()
        user32 = ctypes.windll.user32
        def cancel_tray():
            time.sleep(0.1)
            h = user32.FindWindowW("STATIC", "WhiscribeMenuHost")
            if h:
                user32.PostMessageW(h, 0x001F, 0, 0)

        t = threading.Thread(target=cancel_tray)
        t.start()
        ctypes.set_last_error(0)
        mock._show_settings_menu(200, 200)
        self.assertEqual(ctypes.GetLastError(), 0, "Menu nie może zwracać błędu Win32 (np. ERROR_INVALID_PARAMETER 87)")
        t.join()

        icon.stop()

if __name__ == "__main__":
    unittest.main()

