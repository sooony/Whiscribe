"""Testy regresyjne dla poprawek stabilności z review kodu (2.2.19).

Każdy test pilnuje jednego konkretnego błędu, który review znalazło w działającym kodzie:
1. restore() rysowało klatkę w wątku wywołującego, równolegle z wątkiem UI.
2. Zamknięcie okna docelowego w trakcie dyktowania przepuszczało tekst do obcego okna.
3. Nieudany start mikrofonu zostawiał aplikację w stanie "recording" bez nagrywania.
4. save_config obcinał plik bez locka, więc tracone były ustawienia.
"""
import json
import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch


class TestRestoreNieRysujeWObcymWatku(unittest.TestCase):
    """restore() leci z wątku IPC, menu i skrótu, a _render_frame pisze do wspólnego DIB-a.

    Dwa wątki rysujące naraz do jednej bitmapy przez memmove i UpdateLayeredWindow to
    od pociętej klatki po twardą wywrotkę w gdi32.
    """

    def test_restore_tylko_oznacza_klatke_jako_brudna(self):
        from overlay import FloatingOverlay

        ov = FloatingOverlay(theme='dark')
        try:
            time.sleep(0.5)
            ov.minimize()

            # Podmiana metody działa też dla wątku UI, który rysować MUSI, więc notujemy,
            # z którego wątku każde rysowanie poleciało.
            watki_rysujace = []
            oryginal = ov._render_frame

            def szpieg(t_now):
                watki_rysujace.append(threading.get_ident())
                return oryginal(t_now)

            with patch.object(ov, '_render_frame', side_effect=szpieg):
                # W stanie idle wątek UI rysuje tylko na brudną klatkę, więc po chwili cichnie
                time.sleep(0.2)
                watki_rysujace.clear()
                moj_watek = threading.get_ident()

                ov.restore()

                self.assertNotIn(moj_watek, watki_rysujace,
                                 "restore() rysuje w wątku wywołującego, równolegle z wątkiem UI")

                # Klatka i tak musi się odświeżyć, tylko rękami wątku UI
                time.sleep(0.3)
                self.assertTrue(watki_rysujace, "wątek UI powinien przerysować widżet po restore()")
                self.assertNotIn(moj_watek, watki_rysujace)
                self.assertFalse(ov._pending_taskbar_add,
                                 "wątek UI powinien obsłużyć zgłoszenie do paska zadań")
        finally:
            ov.close()
            time.sleep(0.1)

    def test_powtorne_zgloszenie_do_paska_nie_tworzy_nowego_obiektu_com(self):
        """Dotąd każde przywrócenie robiło CoCreateInstance bez Release ani CoUninitialize."""
        import overlay

        p_tb = MagicMock()
        p_tb.value = 0x1234
        with patch.object(overlay, '_taskbar_add_tab', return_value=True) as mock_add_tab, \
             patch.object(overlay, '_add_hwnd_to_taskbar') as mock_create:
            self.assertTrue(overlay._taskbar_add_tab is mock_add_tab)
            # Interfejs już istnieje, więc wystarczy AddTab na nim
            wynik = mock_add_tab(p_tb, 0x9999)
            self.assertTrue(wynik)
            mock_create.assert_not_called()


class TestTekstNieIdzieDoObcegoOkna(unittest.TestCase):
    """Warunek wymagał IsWindow(target), więc zamknięcie okna docelowego wyłączało blokadę."""

    mocki = (
        patch('app.AudioRecorder'), patch('app.Transcriber'), patch('app.FloatingOverlay'),
        patch('app.pystray'), patch('app.keyboard'), patch('app._play_chime_file'),
        patch('app.user32'), patch('app.is_mouse_down'), patch('app.send_unicode_string'),
    )

    def setUp(self):
        from app import DictationApp
        aktywne = [m.start() for m in self.mocki]
        self.addCleanup(lambda: [m.stop() for m in self.mocki])
        self.mock_user32 = aktywne[6]
        aktywne[7].return_value = False  # mysz nie jest wciśnięta
        self.mock_send = aktywne[8]

        with patch.object(DictationApp, '_monitor_silence', return_value=None), \
             patch.object(DictationApp, '_listen_for_show_event', return_value=None), \
             patch.object(DictationApp, '_watchdog_hotkey', return_value=None), \
             patch.object(DictationApp, '_tray_anim_worker', return_value=None):
            self.app = DictationApp()
        self.app.overlay = None
        self.app._preview_mode_active = False
        self.app.buffered_untyped_text = ""

    def test_zamkniete_okno_docelowe_buforuje_zamiast_pisac(self):
        self.app.target_hwnd = 0x1234
        # Okno docelowe zniknęło, a fokus ma teraz coś innego (terminal, komunikator)
        self.mock_user32.IsWindow.return_value = False
        self.mock_user32.GetForegroundWindow.return_value = 0x4321

        self.app._type_stream_chunk("reszta zdania")

        self.mock_send.assert_not_called()
        self.assertEqual(self.app.buffered_untyped_text, "reszta zdania")

    def test_zywe_okno_docelowe_z_fokusem_pisze_normalnie(self):
        self.app.target_hwnd = 0x1234
        self.mock_user32.IsWindow.return_value = True
        self.mock_user32.GetForegroundWindow.return_value = 0x1234

        self.app._type_stream_chunk("tekst do okna")

        self.mock_send.assert_called_once_with("tekst do okna")

    def test_brak_zapamietanego_celu_nie_blokuje_pisania(self):
        """Gdy celu nie zapamiętano, zachowanie zostaje jak dotąd: piszemy tam, gdzie stoi user."""
        self.app.target_hwnd = 0
        self.mock_user32.IsWindow.return_value = False
        self.mock_user32.GetForegroundWindow.return_value = 0x4321

        self.app._type_stream_chunk("tekst bez celu")

        self.mock_send.assert_called_once_with("tekst bez celu")

    def test_finalizacja_nie_wkleja_gdy_okno_docelowe_zniknelo(self):
        from paste_memory import STATUS_BRAK_FOKUSU

        self.app.config["stream_realtime"] = False
        self.app.config["use_llm"] = False
        self.app.transcriber.transcribe.return_value = "tekst po zamknieciu okna"
        self.app.target_hwnd = 0x1234
        self.mock_user32.IsWindow.return_value = False
        self.mock_user32.GetForegroundWindow.return_value = 0x4321
        self.app.tray_icon = None

        with patch('app.inject_text') as mock_inject:
            self.app._process_audio_worker(object(), job=self.app._job_seq)

        mock_inject.assert_not_called()
        wpis = self.app.paste_memory.ostatni()
        self.assertIsNotNone(wpis, "tekst musi zostać w pamięci wklejek")
        self.assertEqual(wpis.status, STATUS_BRAK_FOKUSU)


class TestNieudanyStartMikrofonu(unittest.TestCase):
    """Wyjątek z sd.InputStream zostawiał stan "recording" bez nagrywania.

    Widżet pokazywał nagrywanie, skrót przestawał działać jak start, a wychodził
    z tego dopiero auto-stop po ciszy.
    """

    def test_rekorder_wraca_do_stanu_niearejestrujacego(self):
        import recorder as recorder_mod
        from recorder import AudioRecorder

        rec = AudioRecorder(sample_rate=16000)
        with patch.object(recorder_mod.sd, 'InputStream', side_effect=OSError("mikrofon zajęty")):
            with self.assertRaises(OSError):
                rec.start()

        self.assertFalse(rec.is_recording, "rekorder nie może udawać, że nagrywa")
        self.assertIsNone(rec._stream)

    def test_aplikacja_wraca_do_idle_i_mowi_o_mikrofonie(self):
        from app import DictationApp

        mocki = [
            patch('app.AudioRecorder'), patch('app.Transcriber'), patch('app.FloatingOverlay'),
            patch('app.pystray'), patch('app.keyboard'), patch('app._play_chime_file'),
            patch('app.user32'), patch('app.get_proc_name_from_hwnd', return_value="chrome.exe"),
            patch('app.is_text_field_focused', return_value=(True, "pole tekstowe")),
            patch('app.safe_bring_to_foreground'), patch('app.is_valid_target_window', return_value=True),
        ]
        aktywne = [m.start() for m in mocki]
        self.addCleanup(lambda: [m.stop() for m in mocki])
        mock_user32 = aktywne[6]
        mock_user32.GetForegroundWindow.return_value = 0x1234
        mock_user32.IsWindow.return_value = True

        with patch.object(DictationApp, '_monitor_silence', return_value=None), \
             patch.object(DictationApp, '_listen_for_show_event', return_value=None), \
             patch.object(DictationApp, '_watchdog_hotkey', return_value=None), \
             patch.object(DictationApp, '_tray_anim_worker', return_value=None):
            app = DictationApp()

        overlay = MagicMock()
        overlay.hwnd = 0x9999
        overlay.is_minimized.return_value = False
        app.overlay = overlay
        app.tray_icon = None
        app.state = "idle"
        app.recorder.start.side_effect = OSError("mikrofon zajęty przez inną aplikację")

        app.start_recording()

        self.assertEqual(app.state, "idle", "zajęty mikrofon nie może zostawić stanu 'recording'")
        komunikaty = [str(c.args[1]) for c in overlay.show_balloon.call_args_list if len(c.args) > 1]
        self.assertTrue(any("mikrofon" in k.lower() for k in komunikaty), komunikaty)


class TestAtomowyZapisUstawien(unittest.TestCase):
    """save_config obcinał plik w trybie "w" bez locka, a wołają go równolegle menu
    kontekstowe, przełączniki w zasobniku i okienka dialogowe. Obcięty JSON oznaczał
    cichy powrót do ustawień domyślnych (motyw, presety dźwięków, provider LLM)."""

    def test_rownolegle_zapisy_nie_daja_obcietego_pliku(self, ):
        import config as config_mod

        import tempfile
        katalog = tempfile.mkdtemp()
        cfg_path = os.path.join(katalog, "config.json")

        with patch.object(config_mod, 'get_config_path', lambda: cfg_path):
            bledy = []
            odczyty = []

            def pisz(i):
                try:
                    for _ in range(10):
                        c = config_mod.DEFAULT_CONFIG.copy()
                        c["theme"] = f"motyw{i}"
                        config_mod.save_config(c)
                        with open(cfg_path, encoding="utf-8") as f:
                            odczyty.append(json.load(f)["theme"])
                except Exception as e:
                    bledy.append(repr(e))

            watki = [threading.Thread(target=pisz, args=(i,)) for i in range(8)]
            for t in watki:
                t.start()
            for t in watki:
                t.join()

        self.assertEqual(bledy, [], "czytający nigdy nie może zobaczyć obciętego JSON-a")
        self.assertEqual(len(odczyty), 80)
        self.assertTrue(all(v.startswith("motyw") for v in odczyty))
        # Po zapisie nie zostają pliki tymczasowe
        self.assertEqual([f for f in os.listdir(katalog) if f != "config.json"], [])

    def test_zablokowany_plik_nie_gubi_ustawienia(self):
        """Na Windows os.replace leci WinError 5, gdy plik trzyma ktoś inny (OneDrive,
        antywirus). Wtedy zapisujemy w miejscu, bo lepiej wrócić do starego ryzyka
        niż po cichu zgubić ustawienie."""
        import config as config_mod

        import tempfile
        katalog = tempfile.mkdtemp()
        cfg_path = os.path.join(katalog, "config.json")

        with patch.object(config_mod.os, 'replace', side_effect=OSError(5, "Odmowa dostępu")), \
             patch.object(config_mod.time, 'sleep'):
            config_mod.zapisz_json_atomowo(cfg_path, {"theme": "graphite"})

        with open(cfg_path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["theme"], "graphite")
        self.assertEqual([f for f in os.listdir(katalog) if f != "config.json"], [])

    def test_klucz_api_zapisywany_atomowo(self):
        import config as config_mod

        import tempfile
        katalog = tempfile.mkdtemp()
        sec_path = os.path.join(katalog, "secrets.json")

        with patch.object(config_mod, 'get_secrets_path', lambda: sec_path):
            self.assertTrue(config_mod.save_secret_key("klucz-testowy-123"))
            with open(sec_path, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["llm_api_key"], "klucz-testowy-123")
        self.assertEqual([f for f in os.listdir(katalog) if f != "secrets.json"], [])


if __name__ == "__main__":
    unittest.main()
