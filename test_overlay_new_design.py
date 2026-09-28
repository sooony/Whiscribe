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

        # Test meeting recording (powinno wyczyścić poprzednią transkrypcję)
        ov.show_meeting_recording()
        self.assertEqual(ov.mode, "transcribing")
        self.assertEqual(len(ov.transcript_lines), 0)
        ov.add_transcript_entry("Rozmówca: Cześć wszystkim", timestamp_s=10.0)
        self.assertEqual(len(ov.transcript_lines), 1)

        # Test closing panel
        ov.panel_open = False
        self.assertFalse(ov.panel_open)

        # Test idle (powinno wyczyścić transkrypcję po zakończeniu sesji)
        ov.show_idle()
        self.assertEqual(ov.mode, "idle")
        self.assertEqual(len(ov.transcript_lines), 0)

        # Test ponownego nagrywania (czyszczenie na starcie)
        ov.add_transcript_entry("Pozostałość")
        ov.show_recording()
        self.assertEqual(len(ov.transcript_lines), 0)

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

    def test_waveform_dynamics_and_stabilization(self):
        ov = FloatingOverlay(theme='dark')
        test_vol = 0.0
        ov.set_volume_getter(lambda: test_vol)
        
        # 1. Spoczynek (idle): głośność 0, brak ruchu
        ov.show_idle()
        ov._render_frame(time.time())
        self.assertEqual(ov._smooth_vol, 0.0)
        
        # 2. Start nagrywania w ciszy: głośność 0, fala ustabilizowana bez ruchu
        ov.show_recording()
        ov._render_frame(time.time())
        self.assertEqual(ov._smooth_vol, 0.0)
        
        # 3. Głos użytkownika (mówienie): fala dynamicznie rośnie
        test_vol = 0.85
        ov._render_frame(time.time())
        self.assertGreater(ov._smooth_vol, 0.4)
        
        # 4. Zakończenie mówienia (cisza): fala stabilizuje się i wraca do 0.0
        test_vol = 0.0
        for _ in range(25):
            ov._render_frame(time.time())
        self.assertEqual(ov._smooth_vol, 0.0)
        
        ov.close()
        time.sleep(0.1)

if __name__ == '__main__':
    unittest.main()
