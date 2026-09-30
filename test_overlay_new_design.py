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

        # Domyślnie streaming jest wyłączony
        self.assertFalse(ov.stream_realtime)

        # Test recording
        ov.show_recording()
        self.assertEqual(ov.mode, "recording")

        # Przełączenie trybu streamingu
        ov.stream_realtime = True
        self.assertTrue(ov.stream_realtime)

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

        # Test wyłączenia streamingu
        ov.stream_realtime = False
        self.assertFalse(ov.stream_realtime)

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

    def test_streaming_mode_toggle_and_render(self):
        """Weryfikacja przełączania trybu streamingu (ikona błyskawicy po lewej stronie belki)."""
        ov = FloatingOverlay(theme='dark')
        toggle_called = []
        ov.set_callbacks(on_stream_toggle=lambda: toggle_called.append(True))

        self.assertFalse(ov.stream_realtime)

        # Symulacja kliknięcia lewym przyciskiem myszy w przycisk streamingu
        click_x = int(ov.bar_stream_cx)
        click_y = int(ov.bar_stream_cy)
        lparam = (click_y << 16) | (click_x & 0xFFFF)

        # WM_LBUTTONDOWN i WM_LBUTTONUP
        ov._wnd_proc(ov.hwnd, 0x0201, 0, lparam)
        ov._wnd_proc(ov.hwnd, 0x0202, 0, lparam)
        time.sleep(0.05)

        self.assertTrue(ov.stream_realtime)
        self.assertTrue(len(toggle_called) > 0)

        # Renderuj klatkę z aktywnym streamingiem
        ov._render_frame(time.time())

        # Drugie kliknięcie - wyłączenie streamingu
        ov._wnd_proc(ov.hwnd, 0x0201, 0, lparam)
        ov._wnd_proc(ov.hwnd, 0x0202, 0, lparam)
        time.sleep(0.05)

        self.assertFalse(ov.stream_realtime)
        self.assertEqual(len(toggle_called), 2)

        # Renderuj klatkę z wyłączonym streamingiem
        ov._render_frame(time.time())

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
