"""Testy pamięci wklejek i wyniku zwracanego przez inject_text.

Czysty Python, bez Win32 i bez widżetu: to jedyna część tej funkcji, którą da się
sprawdzić bez uruchamiania aplikacji.
"""
import unittest
from unittest.mock import patch

from paste_memory import (PasteMemory, MAX_ZNAKOW, STATUS_WKLEJONY, STATUS_W_TOKU,
                          STATUS_BRAK_FOKUSU, STATUS_SPOZNIONY)


class TestPasteMemory(unittest.TestCase):
    def test_domyslnie_jeden_wpis(self):
        pm = PasteMemory()
        self.assertEqual(pm.rozmiar, 1)
        self.assertTrue(pm.pusta())

        pm.dodaj("pierwszy tekst", STATUS_WKLEJONY)
        pm.dodaj("drugi tekst", STATUS_WKLEJONY)

        self.assertEqual(len(pm), 1)
        self.assertEqual(pm.ostatni().text, "drugi tekst")

    def test_ring_trzech_wpisow(self):
        pm = PasteMemory(3)
        for t in ("jeden", "dwa", "trzy", "cztery"):
            pm.dodaj(t, STATUS_WKLEJONY)

        self.assertEqual(len(pm), 3)
        # Lista od najnowszego: najstarszy ("jeden") wypadł z ringu
        self.assertEqual([w.text for w in pm.lista()], ["cztery", "trzy", "dwa"])

    def test_rozmiar_jest_pilnowany(self):
        self.assertEqual(PasteMemory(0).rozmiar, 1)
        self.assertEqual(PasteMemory(-5).rozmiar, 1)
        self.assertEqual(PasteMemory("nonsens").rozmiar, 1)
        self.assertEqual(PasteMemory(100).rozmiar, 10)

    def test_pusty_tekst_nie_tworzy_wpisu(self):
        pm = PasteMemory()
        self.assertIsNone(pm.dodaj("", STATUS_WKLEJONY))
        self.assertIsNone(pm.dodaj("   \n  ", STATUS_WKLEJONY))
        self.assertTrue(pm.pusta())

    def test_powtorzenie_tej_samej_tresci_odswieza_status(self):
        """Ponowna próba wklejenia tego samego tekstu nie może wypchnąć wpisu z ringu."""
        pm = PasteMemory(2)
        pm.dodaj("tekst do zachowania", STATUS_WKLEJONY)
        pm.dodaj("ten sam tekst", STATUS_BRAK_FOKUSU)
        pm.dodaj("ten sam tekst", STATUS_WKLEJONY)

        self.assertEqual(len(pm), 2)
        self.assertEqual(pm.ostatni().status, STATUS_WKLEJONY)
        self.assertEqual([w.text for w in pm.lista()], ["ten sam tekst", "tekst do zachowania"])

    def test_limit_dlugosci_wpisu(self):
        pm = PasteMemory()
        pm.dodaj("a" * (MAX_ZNAKOW + 500), STATUS_WKLEJONY)
        self.assertEqual(pm.ostatni().znakow, MAX_ZNAKOW)

    def test_status_dopisywany_po_probie_wklejenia(self):
        pm = PasteMemory()
        wpis = pm.dodaj("tekst w trakcie wklejania", STATUS_W_TOKU)
        self.assertEqual(wpis.status, STATUS_W_TOKU)

        pm.oznacz(wpis, STATUS_BRAK_FOKUSU)
        self.assertEqual(pm.ostatni().status, STATUS_BRAK_FOKUSU)
        self.assertTrue(pm.ostatni().niewklejony)

        pm.oznacz(wpis, STATUS_WKLEJONY)
        self.assertFalse(pm.ostatni().niewklejony)

        # Brak wpisu (np. pusty tekst) nie może wywrócić wywołującego
        pm.oznacz(None, STATUS_WKLEJONY)

    def test_niewklejone_statusy_sygnalizuja_utrate(self):
        pm = PasteMemory()
        for status in (STATUS_BRAK_FOKUSU, STATUS_SPOZNIONY):
            pm.dodaj(f"tekst {status}", status)
            self.assertTrue(pm.ostatni().niewklejony, status)

    def test_etykieta_do_menu(self):
        pm = PasteMemory()
        pm.dodaj("Cześć, w sprawie faktury za październik proszę o korektę pozycji drugiej",
                 STATUS_BRAK_FOKUSU)
        etykieta = pm.ostatni().etykieta()

        self.assertIn("nie wklejono", etykieta)
        self.assertIn("Cześć, w sprawie faktury", etykieta)
        self.assertTrue(etykieta.endswith("..."), etykieta)
        self.assertLess(len(etykieta), 110)

    def test_podglad_sklada_wiele_wierszy_w_jeden(self):
        pm = PasteMemory()
        pm.dodaj("pierwszy wiersz\n\n   drugi    wiersz", STATUS_WKLEJONY)
        self.assertEqual(pm.ostatni().podglad(), "pierwszy wiersz drugi wiersz")

    def test_wyczyszczenie(self):
        pm = PasteMemory(3)
        pm.dodaj("cokolwiek", STATUS_WKLEJONY)
        pm.wyczysc()
        self.assertTrue(pm.pusta())
        self.assertIsNone(pm.ostatni())
        self.assertEqual(pm.lista(), [])


class TestInjectTextWynik(unittest.TestCase):
    """inject_text musi mówić, czy tekst wszedł: bez tego status wpisu byłby zgadywany."""

    def test_pusty_tekst(self):
        from injector import inject_text, WYNIK_PUSTY
        self.assertEqual(inject_text(""), WYNIK_PUSTY)
        self.assertEqual(inject_text("   "), WYNIK_PUSTY)

    def test_zablokowany_schowek_zwraca_wpisany(self):
        from injector import inject_text, WYNIK_WPISANY
        import injector

        wpisane = []
        with patch.object(injector.pyperclip, "copy", side_effect=RuntimeError("schowek zajęty")), \
             patch.object(injector.pyperclip, "paste", return_value=""), \
             patch.object(injector, "send_unicode_string", side_effect=lambda t: wpisane.append(t)), \
             patch.object(injector, "zwolnij_modyfikatory", return_value=True):
            wynik = inject_text("tekst awaryjny")

        self.assertEqual(wynik, WYNIK_WPISANY)
        self.assertEqual(wpisane, ["tekst awaryjny "])

    def test_udane_wklejenie_zwraca_wklejony(self):
        from injector import inject_text, WYNIK_WKLEJONY
        import injector

        with patch.object(injector.pyperclip, "copy"), \
             patch.object(injector.pyperclip, "paste", return_value="stara zawartość"), \
             patch.object(injector, "zwolnij_modyfikatory", return_value=True), \
             patch.object(injector.kb, "tap"), \
             patch.object(injector.kb, "pressed"), \
             patch.object(injector.time, "sleep"):
            wynik = inject_text("tekst do wklejenia")

        self.assertEqual(wynik, WYNIK_WKLEJONY)


class FakeOverlay:
    """Minimalny widżet: tylko to, czego dotyka finalizacja dyktowania."""

    def __init__(self):
        self.hwnd = 0x9999
        self.mode = "idle"
        self.balony = []
        self.pamiec = None

    def is_minimized(self):
        return False

    def show(self):
        pass

    def show_idle(self):
        self.mode = "idle"

    def show_processing(self):
        self.mode = "processing"

    def show_recording(self):
        self.mode = "recording"

    def show_balloon(self, kind="info", text="", duration_s=7.0):
        self.balony.append((kind, text, duration_s))

    def show_error_balloon(self, duration_s=7.0):
        self.balony.append(("error", "", duration_s))

    def hide_balloon(self):
        pass

    def set_paste_memory(self, ma_wklejke, niewklejony=False):
        self.pamiec = (ma_wklejke, niewklejony)


def _zbuduj_app():
    """DictationApp z zamockowanym sprzętem i bez wątków w tle."""
    from app import DictationApp

    with patch.object(DictationApp, '_monitor_silence', return_value=None), \
         patch.object(DictationApp, '_listen_for_show_event', return_value=None), \
         patch.object(DictationApp, '_watchdog_hotkey', return_value=None), \
         patch.object(DictationApp, '_tray_anim_worker', return_value=None):
        app = DictationApp()
    app.overlay = FakeOverlay()
    app.config["stream_realtime"] = False
    app.config["use_llm"] = False
    app.config["auto_enter_after_dictation"] = False
    app.tray_icon = None
    return app


class TestFinalizacjaKarmiPamiec(unittest.TestCase):
    """Wpis musi powstawać PRZY POWSTANIU TEKSTU, nie po udanym wklejeniu.

    Tekst, który nie wszedł do okna, jest dokładnie tym, który trzeba móc odzyskać:
    dotąd obiecywały go cztery dymki ("tekst zachowano w widżecie"), a panel widżetu
    nigdy nie był rysowany, więc tekst przepadał.
    """

    mocki = (
        patch('app.AudioRecorder'), patch('app.Transcriber'), patch('app.FloatingOverlay'),
        patch('app.pystray'), patch('app.keyboard'), patch('app._play_chime_file'),
        patch('app.user32'),
    )

    def setUp(self):
        self._aktywne = [m.start() for m in self.mocki]
        self.addCleanup(lambda: [m.stop() for m in self.mocki])
        self.mock_user32 = self._aktywne[6]

    def test_udane_wklejenie_oznacza_wpis_jako_wklejony(self):
        from injector import WYNIK_WKLEJONY

        app = _zbuduj_app()
        app.transcriber.transcribe.return_value = "tekst do wklejenia"
        app.target_hwnd = None  # brak okna docelowego: fokusu nie trzeba przywracać

        with patch('app.inject_text', return_value=WYNIK_WKLEJONY) as mock_inject:
            app._process_audio_worker(object(), job=app._job_seq)

        mock_inject.assert_called_once()
        self.assertEqual(mock_inject.call_args.args[0], "tekst do wklejenia")
        wpis = app.paste_memory.ostatni()
        self.assertIsNotNone(wpis, "tekst nie trafił do pamięci wklejek")
        self.assertEqual(wpis.text, "tekst do wklejenia")
        self.assertEqual(wpis.status, STATUS_WKLEJONY)
        self.assertFalse(wpis.niewklejony)
        self.assertEqual(app.overlay.pamiec, (True, False))

    def test_utracony_fokus_zapisuje_tekst_i_mowi_o_skrocie(self):
        app = _zbuduj_app()
        app.transcriber.transcribe.return_value = "tekst, który nie wszedł"
        app.target_hwnd = 0x1234

        self.mock_user32.IsWindow.return_value = True
        # Fokus uparcie siedzi w innym oknie, więc wklejanie musi zostać wstrzymane
        self.mock_user32.GetForegroundWindow.return_value = 0x4321

        with patch('app.inject_text') as mock_inject, \
             patch('app.safe_bring_to_foreground'):
            app._process_audio_worker(object(), job=app._job_seq)

        mock_inject.assert_not_called()
        wpis = app.paste_memory.ostatni()
        self.assertIsNotNone(wpis, "tekst przepadł zamiast trafić do pamięci wklejek")
        self.assertEqual(wpis.status, STATUS_BRAK_FOKUSU)
        self.assertTrue(wpis.niewklejony)
        self.assertEqual(app.overlay.pamiec, (True, True))

        # Dymek musi mówić prawdę i stać do kliknięcia, a nie gasnąć po 10 s
        komunikaty = [t for _, t, _ in app.overlay.balony]
        self.assertTrue(any("Ctrl+Alt+V" in t for t in komunikaty), komunikaty)
        self.assertFalse(any("w widżecie" in t for t in komunikaty), komunikaty)
        self.assertTrue(any(d == 0 for _, _, d in app.overlay.balony), app.overlay.balony)

    def test_brak_okna_pierwszego_planu_nie_wywraca_finalizacji(self):
        """GetForegroundWindow ma restype HWND, czyli przy braku okna zwraca None.

        Formatowanie None przez :#x rzucało TypeError w gałęzi utraconego fokusu,
        czyli dokładnie tam, gdzie tekst miał być ratowany.
        """
        app = _zbuduj_app()
        app.transcriber.transcribe.return_value = "tekst przy zablokowanym ekranie"
        app.target_hwnd = 0x1234

        self.mock_user32.IsWindow.return_value = True
        self.mock_user32.GetForegroundWindow.return_value = None

        with patch('app.inject_text') as mock_inject, \
             patch('app.safe_bring_to_foreground'):
            app._process_audio_worker(object(), job=app._job_seq)

        mock_inject.assert_not_called()
        self.assertEqual(app.paste_memory.ostatni().status, STATUS_BRAK_FOKUSU)

    def test_spozniony_wynik_trafia_do_pamieci(self):
        app = _zbuduj_app()
        app.transcriber.transcribe.return_value = "spóźniona transkrypcja"
        app.target_hwnd = None

        # Zadanie porzucone (watchdog albo ponowny skrót): numer sesji już się zmienił
        app._job_seq = 7
        with patch('app.inject_text') as mock_inject:
            app._process_audio_worker(object(), job=5)

        mock_inject.assert_not_called()
        wpis = app.paste_memory.ostatni()
        self.assertIsNotNone(wpis, "spóźniony tekst przepadł")
        self.assertEqual(wpis.status, STATUS_SPOZNIONY)


class TestPigulkaPrzywrocWidzecie(unittest.TestCase):
    """Sygnał "masz co przywrócić" siedzi w linii statusu, nie w nagłówku.

    Nagłówek odpadł na geometrii: karta ma 140 px, a czwarta ikonka obok ··· — × wchodzi
    na napis "Whiscribe" i zostaje jej 16 px klikalnych. W idle timer pokazuje zawsze
    00:00, więc pigułka zajmuje te martwe piksele.
    """

    def test_pigulka_pojawia_sie_tylko_w_idle_i_jest_klikalna(self):
        import time
        from overlay import FloatingOverlay

        ov = FloatingOverlay(theme='dark')
        try:
            time.sleep(0.5)
            ov.show_idle()
            self.assertIsNone(ov._paste_pill_box, "pusta pamięć nie może pokazywać pigułki")

            ov.set_paste_memory(True, niewklejony=True)
            time.sleep(0.4)
            box = ov._paste_pill_box
            self.assertIsNotNone(box, "pigułka nie została narysowana")

            bx, by, bw, bh = box
            self.assertEqual(ov._get_target(bx + bw / 2, by + bh / 2), 'btn_restore_paste')
            # Pigułka nie może przejąć kliknięć głównego przycisku ani nagłówka
            self.assertEqual(ov._get_target(ov.mic_cx, ov.mic_cy), 'btn_mic')
            self.assertEqual(ov._get_target(ov.bar_close_cx, ov.by + ov.bh / 2), 'btn_bar_close')
            # Mieści się w karcie
            self.assertGreaterEqual(bx, ov.cx0)
            self.assertLessEqual(bx + bw, ov.cx0 + ov.cw)

            # W trakcie nagrywania timer coś znaczy, więc pigułki nie ma
            ov.show_recording()
            time.sleep(0.3)
            self.assertIsNone(ov._paste_pill_box)

            ov.show_idle()
            ov.set_paste_memory(False)
            time.sleep(0.3)
            self.assertIsNone(ov._paste_pill_box)
        finally:
            ov.close()
            time.sleep(0.1)


if __name__ == "__main__":
    unittest.main()
