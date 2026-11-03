"""Pisanie na żywo i korekta AI wykluczają się wzajemnie (2.2.23).

Decyzja Filipa z 3.11.2026, po przetestowaniu trzech konfiguracji. Wcześniej oba dało się
włączyć naraz i wchodziły w "tryb podglądu": streaming nie wpisywał nic do okna, a tekst
wchodził raz, po korekcie całości. Podgląd miał się pokazywać w panelu widżetu, ale panel
był martwym kodem usuniętym w 2.2.19, więc ustawienie nie robiło nic, a w menu wyglądało
na aktywne. Jego log to potwierdził: stream z korektą zachowywał się identycznie jak sama
korekta, a różnicę widać dopiero przy streamingu bez korekty (finalizacja 0,00 s).
"""
import threading
import unittest
from unittest.mock import MagicMock, patch


class TestPrzelacznikiSieWykluczaja(unittest.TestCase):

    def _app(self, stream, korekta):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app.config = {
            "stream_realtime": stream,
            "use_llm": korekta,
            "llm_provider": "gemini",
            "llm_api_key": "AIza" + "x" * 35,
        }
        app.overlay = MagicMock()
        app.transcriber = MagicMock()
        return app, app_mod

    def test_wlaczenie_pisania_na_zywo_wylacza_korekte(self):
        app, app_mod = self._app(stream=False, korekta=True)
        with patch.object(app_mod, "save_config"), patch.object(app_mod, "logger"):
            app.toggle_streaming_mode()

        self.assertTrue(app.config["stream_realtime"])
        self.assertFalse(app.config["use_llm"],
                         "pisanie na żywo musi wyłączyć korektę, inaczej nic nie wpisuje na żywo")
        self.assertFalse(app.overlay.ai_enabled)

    def test_wlaczenie_korekty_wylacza_pisanie_na_zywo(self):
        app, app_mod = self._app(stream=True, korekta=False)
        with patch.object(app_mod, "save_config"), patch.object(app_mod, "logger"):
            app.toggle_llm_correction()

        self.assertTrue(app.config["use_llm"])
        self.assertFalse(app.config["stream_realtime"],
                         "korekta musi wyłączyć pisanie na żywo, bo i tak nic by nie wpisywało")
        self.assertFalse(app.overlay.stream_realtime)

    def test_wylaczenie_pisania_na_zywo_nie_rusza_korekty(self):
        app, app_mod = self._app(stream=True, korekta=False)
        with patch.object(app_mod, "save_config"), patch.object(app_mod, "logger"):
            app.toggle_streaming_mode()      # wyłączamy streaming

        self.assertFalse(app.config["stream_realtime"])
        self.assertFalse(app.config["use_llm"], "wyłączenie jednego trybu nie włącza drugiego")

    def test_wylaczenie_korekty_nie_rusza_pisania_na_zywo(self):
        app, app_mod = self._app(stream=False, korekta=True)
        with patch.object(app_mod, "save_config"), patch.object(app_mod, "logger"):
            app.toggle_llm_correction()      # wyłączamy korektę

        self.assertFalse(app.config["use_llm"])
        self.assertFalse(app.config["stream_realtime"])

    def test_uzytkownik_dowiaduje_sie_co_zostalo_wylaczone(self):
        app, app_mod = self._app(stream=False, korekta=True)
        with patch.object(app_mod, "save_config"), patch.object(app_mod, "logger"):
            app.toggle_streaming_mode()

        self.assertTrue(app.overlay.show_balloon.called,
                        "ciche wyłączenie drugiego trybu byłoby niespodzianką")
        tresc = app.overlay.show_balloon.call_args[0][1]
        self.assertIn("korekta", tresc.lower())

    def test_przelaczanie_tam_i_z_powrotem_zostawia_dokladnie_jeden_tryb(self):
        app, app_mod = self._app(stream=True, korekta=False)
        with patch.object(app_mod, "save_config"), patch.object(app_mod, "logger"):
            for _ in range(5):
                app.toggle_llm_correction()      # korekta on -> stream off
                app.toggle_streaming_mode()      # stream on -> korekta off
                self.assertFalse(app.config["stream_realtime"] and app.config["use_llm"],
                                 "oba tryby włączone naraz, a to się wyklucza")

    def test_bez_klucza_api_korekta_nie_wylacza_pisania_na_zywo(self):
        """Brak klucza otwiera okno wpisywania i nie zmienia niczego po drodze."""
        app, app_mod = self._app(stream=True, korekta=False)
        app.config["llm_api_key"] = ""
        app.prompt_and_set_llm_api_key = MagicMock()

        with patch.object(app_mod, "save_config"), patch.object(app_mod, "logger"):
            app.toggle_llm_correction()

        app.prompt_and_set_llm_api_key.assert_called_once()
        self.assertTrue(app.config["stream_realtime"],
                        "skoro korekta się nie włączyła, pisanie na żywo musi zostać")
        self.assertFalse(app.config["use_llm"])


class TestStaryConfigJestProstowanyPrzyStarcie(unittest.TestCase):
    """Config Filipa mial oba tryby naraz, wiec sama zmiana przelacznikow by nie wystarczyla."""

    def test_config_z_obydwoma_trybami_zostawia_korekte(self):
        import app as app_mod
        import inspect

        zrodlo = inspect.getsource(app_mod.DictationApp.__init__)
        self.assertIn('self.config["stream_realtime"] = False', zrodlo,
                      "stary config z obydwoma trybami musi zostać wyprostowany przy starcie")
        # Korekta wygrywa, bo to ona dzialala w tej kombinacji
        pozycja = zrodlo.index('self.config["stream_realtime"] = False')
        warunek = zrodlo[max(0, pozycja - 300):pozycja]
        self.assertIn('use_llm', warunek)

    def test_rozdzielenie_dziala_na_zywym_obiekcie(self):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app.config = {"stream_realtime": True, "use_llm": True, "llm_provider": "gemini",
                      "llm_api_key": "AIza" + "x" * 35}
        app.overlay = MagicMock()
        app.transcriber = MagicMock()

        with patch.object(app_mod, "save_config"), patch.object(app_mod, "logger"):
            zmienione = app._rozdziel_tryby("korekta")

        self.assertTrue(zmienione)
        self.assertFalse(app.config["stream_realtime"])
        self.assertTrue(app.config["use_llm"])

    def test_rozdzielenie_nic_nie_robi_gdy_tryby_sa_rozlaczne(self):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app.config = {"stream_realtime": True, "use_llm": False}
        app.overlay = MagicMock()

        with patch.object(app_mod, "save_config"), patch.object(app_mod, "logger"):
            self.assertFalse(app._rozdziel_tryby("stream"))

        self.assertTrue(app.config["stream_realtime"])
        self.assertFalse(app.overlay.show_balloon.called,
                         "nie ma o czym informować, skoro nic nie zostało wyłączone")


if __name__ == "__main__":
    unittest.main()
