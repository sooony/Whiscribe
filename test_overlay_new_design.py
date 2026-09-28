import time
import unittest
from overlay import FloatingOverlay

class TestOverlayNewDesign(unittest.TestCase):
    def test_overlay_lifecycle_and_methods(self):
        ov = FloatingOverlay(theme='dark')
        self.assertTrue(ov.is_alive())
        self.assertIsNotNone(ov.hwnd)
        self.assertEqual(ov.mw, 250)
        self.assertEqual(ov.mh, 90)

        # Panel transkrypcji jest domyślnie wyłączony (zwinięty)
        self.assertFalse(ov.panel_open)

        # Test recording
        ov.show_recording()
        self.assertEqual(ov.mode, "recording")
        self.assertFalse(ov.panel_open)  # Pozostaje zwinięty, nie narzuca się użytkownikowi

        # Otwieranie na żądanie
        ov.panel_open = True
        self.assertTrue(ov.panel_open)

        # Test transcript update
        ov.update_live_text("Bieżący ogon transkrypcji")
        ov.add_transcript_entry("Zatwierdzone zdanie pierwsze", timestamp_s=2.5)
        self.assertEqual(len(ov.transcript_lines), 1)

        # Test meeting recording
        ov.show_meeting_recording()
        self.assertEqual(ov.mode, "transcribing")
        ov.add_transcript_entry("Rozmówca: Cześć wszystkim", timestamp_s=10.0)
        self.assertEqual(len(ov.transcript_lines), 2)

        # Test closing panel
        ov.panel_open = False
        self.assertFalse(ov.panel_open)

        # Test idle
        ov.show_idle()
        self.assertEqual(ov.mode, "idle")

        # Cleanup
        ov.close()
        time.sleep(0.1)

    def test_scroll_and_timestamp_free_transcript(self):
        ov = FloatingOverlay(theme='dark')
        ov.panel_open = True
        
        for i in range(12):
            ov.add_transcript_entry(f"Zdanie testowe {i+1}: weryfikacja przewijania i braku znaczników czasu.")
        
        # Renderuj klatkę
        ov._render_frame(time.time())
        self.assertGreater(ov._total_lines_count, ov._max_visible_lines)
        self.assertFalse(ov._user_scrolled)
        
        # Przewiń kółkiem myszy w górę (delta = +120)
        ov._wnd_proc(ov.hwnd, 0x020A, (120 << 16), 0)
        ov._render_frame(time.time())
        self.assertTrue(ov._user_scrolled)
        
        # Przewiń z powrotem w dół do końca
        for _ in range(10):
            ov._wnd_proc(ov.hwnd, 0x020A, ((-120 & 0xFFFF) << 16), 0)
        ov._render_frame(time.time())
        self.assertFalse(ov._user_scrolled)
        
        ov.close()
        time.sleep(0.1)

if __name__ == '__main__':
    unittest.main()
