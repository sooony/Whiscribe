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
        self.assertEqual(target, "btn_minimize", "Target at minimize coords must be 'btn_minimize'")
        
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

if __name__ == "__main__":
    unittest.main()
