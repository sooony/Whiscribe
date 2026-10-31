import sys
import os
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from overlay import FloatingOverlay
import app

class TestMicCycle(unittest.TestCase):
    def test_overlay_state_mode_sync(self):
        overlay = FloatingOverlay(theme="light")
        overlay.show_idle()
        self.assertEqual(overlay.mode, "idle")
        self.assertEqual(overlay.state, "idle")
        self.assertEqual(overlay._start_time, 0.0)

        # Transition to recording
        overlay.show_recording()
        self.assertEqual(overlay.mode, "recording")
        self.assertEqual(overlay.state, "recording")
        self.assertGreater(overlay._start_time, 0.0)

        # Transition to processing
        overlay.show_processing()
        self.assertEqual(overlay.mode, "processing")
        self.assertEqual(overlay.state, "processing")

        # Transition back to idle
        overlay.show_idle()
        self.assertEqual(overlay.mode, "idle")
        self.assertEqual(overlay.state, "idle")
        self.assertEqual(overlay._start_time, 0.0)

        # Directly setting .state
        overlay.state = "recording"
        self.assertEqual(overlay.mode, "recording")
        self.assertGreater(overlay._start_time, 0.0)

        overlay.state = "idle"
        self.assertEqual(overlay.mode, "idle")
        self.assertEqual(overlay._start_time, 0.0)

        overlay.close()

    def test_overlay_mic_click_routing(self):
        overlay = FloatingOverlay(theme="light")
        toggled = []
        stopped = []

        overlay.set_callbacks(
            on_stop=lambda: stopped.append(True),
            on_close=lambda: None,
            on_toggle=lambda: toggled.append(True),
            on_meeting_toggle=lambda: None,
            on_minimize=lambda: None
        )

        overlay.show_idle()
        # Simulate click on mic button via WM_LBUTTONDOWN and WM_LBUTTONUP
        lparam = (int(overlay.mic_cy) << 16) | int(overlay.mic_cx)
        overlay._wnd_proc(overlay.hwnd, 0x0201, 1, lparam)
        overlay._wnd_proc(overlay.hwnd, 0x0202, 0, lparam)
        time.sleep(0.1)
        self.assertEqual(len(toggled), 1)
        self.assertEqual(len(stopped), 0)

        # Switch to recording
        overlay.show_recording()
        # Click mic when recording -> should stop
        overlay._wnd_proc(overlay.hwnd, 0x0201, 1, lparam)
        overlay._wnd_proc(overlay.hwnd, 0x0202, 0, lparam)
        time.sleep(0.1)
        self.assertEqual(len(stopped), 1)

        # Switch back to idle
        overlay.show_idle()
        overlay._wnd_proc(overlay.hwnd, 0x0201, 1, lparam)
        overlay._wnd_proc(overlay.hwnd, 0x0202, 0, lparam)
        time.sleep(0.1)
        self.assertEqual(len(toggled), 2)

        overlay.close()

    def test_app_lifecycle_recording_and_stop(self):
        # Instantiate DictationApp
        dict_app = app.DictationApp()
        dict_app.config["require_text_field"] = False
        dict_app.config["sound_feedback"] = False
        self.assertEqual(dict_app.state, "idle")
        self.assertEqual(dict_app.overlay.mode, "idle")

        # 1st cycle: Start dictation
        dict_app.start_recording()
        self.assertEqual(dict_app.state, "recording")
        self.assertEqual(dict_app.overlay.mode, "recording")
        self.assertGreater(dict_app.overlay._start_time, 0.0)

        # 1st cycle: Stop dictation
        dict_app.stop_and_transcribe()
        time.sleep(0.8)
        self.assertEqual(dict_app.state, "idle")
        self.assertEqual(dict_app.overlay.mode, "idle")
        self.assertEqual(dict_app.overlay._start_time, 0.0)

        # 2nd cycle: Start dictation again
        dict_app.start_recording()
        self.assertEqual(dict_app.state, "recording")
        self.assertEqual(dict_app.overlay.mode, "recording")
        self.assertGreater(dict_app.overlay._start_time, 0.0)

        # 2nd cycle: Stop dictation again
        dict_app.stop_and_transcribe()
        time.sleep(0.8)
        self.assertEqual(dict_app.state, "idle")
        self.assertEqual(dict_app.overlay.mode, "idle")
        self.assertEqual(dict_app.overlay._start_time, 0.0)

        # 3rd test: Minimize to taskbar and restore
        dict_app.minimize_to_taskbar()
        time.sleep(0.2)
        self.assertTrue(dict_app.is_minimized_to_tray)
        self.assertTrue(dict_app.overlay.is_minimized())

        # Restore from taskbar
        dict_app.restore_from_taskbar()
        time.sleep(0.2)
        self.assertFalse(dict_app.is_minimized_to_tray)
        self.assertFalse(dict_app.overlay.is_minimized())
        self.assertEqual(dict_app.overlay.mode, "idle")
        self.assertEqual(dict_app.overlay._start_time, 0.0)

        # 4th cycle: Start dictation after restore
        dict_app.start_recording()
        self.assertEqual(dict_app.state, "recording")
        self.assertEqual(dict_app.overlay.mode, "recording")
        dict_app.stop_and_transcribe()
        time.sleep(0.8)
        self.assertEqual(dict_app.state, "idle")
        self.assertEqual(dict_app.overlay.mode, "idle")
        self.assertEqual(dict_app.overlay._start_time, 0.0)

        # Cleanup
        dict_app._running = False
        if dict_app.overlay:
            dict_app.overlay.close()

if __name__ == "__main__":
    unittest.main()
