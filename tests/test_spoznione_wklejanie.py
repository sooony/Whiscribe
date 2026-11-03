"""Testy regresyjne dla zgłoszenia Filipa z 3.11.2026 (wersja 2.2.21).

Objawy: "jak zatrzymam, to w danym momencie powieli się" i "po czasie, mimo że nie było
nic, to i tak mi wkleja to samo co było wcześniej", przy włączonym streamingu i korekcie AI.

Przyczyna z jego pliku błędów: Gemini zwracało 503 i ReadTimeout na trzech modelach pod
rząd, więc finalizacja trwała ~14 s. Kod sprawdzał tylko, czy okno docelowe jest aktywne,
i wklejał tekst, który przestał być aktualny. Każdy test pilnuje jednego ogniwa:

1. Wynik starszy niż próg nie jest wklejany, tylko odkładany do pamięci wklejek.
2. Świeży wynik wchodzi normalnie, bez zmiany dotychczasowego zachowania.
3. Porzucenie zadania w trakcie przywracania fokusu nie kończy się drugim wklejeniem.
4. Gdy wszystkie modele Gemini świeżo padały, próba jest krótsza.
5. Główny plik logu przyjmuje zapis, a gdy nie przyjmuje, aplikacja to zgłasza.
"""
import logging
import os
import threading
import time
import unittest
from unittest.mock import MagicMock, patch


class TestSpoznionyWynikNieWchodziDoOkna(unittest.TestCase):
    """Tekst sprzed kilkunastu sekund wpadał w środek pracy użytkownika."""

    def _app(self, prog=8.0, minelo=0.0):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app.config = {"max_paste_delay_seconds": prog}
        app._processing_started = time.time() - minelo if minelo else time.time()
        return app, app_mod

    def test_wynik_po_progu_jest_uznany_za_spozniony(self):
        app, _ = self._app(prog=8.0, minelo=14.0)
        self.assertGreater(app._wynik_za_stary(), 0.0,
                           "wynik po 14 s przy progu 8 s musi być uznany za spóźniony")

    def test_swiezy_wynik_przechodzi(self):
        app, _ = self._app(prog=8.0, minelo=2.0)
        self.assertEqual(app._wynik_za_stary(), 0.0)

    def test_prog_rosnie_z_dlugoscia_nagrania(self):
        # 60 s mowy: finalizacja wolno potrwać dłużej, bo użytkownik na nią czeka
        app, _ = self._app(prog=8.0, minelo=15.0)
        self.assertEqual(app._wynik_za_stary(audio_s=60.0), 0.0,
                         "przy minucie nagrania 15 s finalizacji to normalny czas")
        self.assertGreater(app._wynik_za_stary(audio_s=5.0), 0.0,
                           "przy 5 s nagrania 15 s finalizacji to już spóźnienie")

    def test_zero_w_configu_przywraca_stare_zachowanie(self):
        app, _ = self._app(prog=0, minelo=600.0)
        self.assertEqual(app._wynik_za_stary(), 0.0,
                         "0 w configu ma znaczyć: wklejaj zawsze, jak dotąd")

    def test_bledna_wartosc_w_configu_nie_wywraca_dyktowania(self):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app.config = {"max_paste_delay_seconds": "osiem"}
        app._processing_started = time.time() - 2.0
        self.assertEqual(app._wynik_za_stary(), 0.0)

    def test_spozniony_tekst_trafia_do_pamieci_wklejek_z_dymkiem(self):
        import app as app_mod
        from paste_memory import PasteMemory, STATUS_SPOZNIONY

        app = object.__new__(app_mod.DictationApp)
        app.paste_memory = PasteMemory(1)
        app.overlay = MagicMock()
        app.target_proc = 'notepad.exe'
        app._odswiez_pamiec_w_widzecie = lambda: None

        with patch.object(app_mod, "logger"):
            app._odloz_spozniony("tekst po czasie", 14.0, "Transkrypcja")

        wpis = app.paste_memory.ostatni()
        self.assertIsNotNone(wpis, "spóźniony tekst musi zostać w pamięci wklejek")
        self.assertEqual(wpis.text, "tekst po czasie")
        self.assertEqual(wpis.status, STATUS_SPOZNIONY)
        self.assertTrue(app.overlay.show_balloon.called, "użytkownik musi wiedzieć, że tekst czeka")
        tresc = app.overlay.show_balloon.call_args[0][1]
        self.assertIn("Ctrl+Alt+V", tresc, "dymek musi mówić, czym odzyskać tekst")
        self.assertEqual(app.overlay.show_balloon.call_args[1].get("duration_s"), 0,
                         "ten dymek nie może zgasnąć sam, bo niesie jedyną informację o tekście")


class TestPorzuconeZadanieNieWklejaDrugiRaz(unittest.TestCase):
    """Przywracanie fokusu trwa do 0,3 s; w tym czasie użytkownik zaczynał nowe dyktowanie."""

    def test_kontrola_zadania_jest_tuz_przed_wklejeniem(self):
        import app as app_mod
        import inspect

        zrodlo = inspect.getsource(app_mod.DictationApp._process_audio_worker)
        # Kontrola musi stać między przywróceniem fokusu a wklejeniem, nie tylko przed korektą
        # rindex, nie index: pierwsze "focus_ok = (...)" jest w galezi streamingu, a chodzi
        # o to bezposrednio przed wklejeniem w galezi wsadowej. Z index test przechodzil
        # takze na starym kodzie, bo lapal kontrole zadania sprzed korekty AI.
        pozycja_inject = zrodlo.index("wynik = inject_text(final_text")
        pozycja_focus = zrodlo.rindex("focus_ok = (user32.GetForegroundWindow() == self.target_hwnd)",
                                      0, pozycja_inject)
        fragment = zrodlo[pozycja_focus:pozycja_inject]
        self.assertIn("_is_current_job(job)", fragment,
                      "między przywróceniem fokusu a wklejeniem brakuje kontroli, czy zadanie "
                      "nadal jest aktualne – stary wątek wkleja do nowej sesji")

    def test_streaming_tez_sprawdza_zadanie_przed_wpisaniem(self):
        import app as app_mod
        import inspect

        zrodlo = inspect.getsource(app_mod.DictationApp._process_audio_worker)
        pozycja = zrodlo.index("Streaming: zadanie porzucone")
        self.assertGreater(pozycja, 0)


class TestKorektaOdpuszczaPoAwarii(unittest.TestCase):
    """Trzy ReadTimeouty po 12 s to 14 s czekania na wynik, który i tak wejdzie surowy."""

    def _transcriber(self):
        import transcriber as tr_mod

        tr = object.__new__(tr_mod.Transcriber)
        tr.config = {"llm_provider": "gemini", "llm_api_key": "x", "llm_model": "m1"}
        tr.last_llm_status = None
        tr._dead_llm_models = set()
        tr._slow_llm_models = {}
        return tr, tr_mod

    def test_wszystkie_modele_swiezo_padle_skracaja_probe(self):
        tr, tr_mod = self._transcriber()
        modele = ["m1", "m2", "m3"]
        teraz = time.monotonic()
        tr._slow_llm_models = {m: teraz + 200.0 for m in modele}

        limity = []

        def fake_timeout(deadline, cap=None):
            limity.append(cap)
            return None          # zero zapytań, interesuje nas sam limit

        with patch.object(tr_mod, "_request_timeout", side_effect=fake_timeout), \
             patch.object(tr_mod, "logger"):
            tr._gemini_correct_hedged(modele, {}, {}, time.monotonic() + 30.0, 30.0)

        self.assertTrue(limity, "nie policzono limitu próby")
        self.assertLessEqual(limity[0], tr_mod.GEMINI_PROBA_PO_AWARII_S,
                             f"limit próby {limity[0]} s, a wszystkie modele świeżo padały")

    def test_zdrowe_modele_maja_pelny_limit(self):
        tr, tr_mod = self._transcriber()
        limity = []

        def fake_timeout(deadline, cap=None):
            limity.append(cap)
            return None

        with patch.object(tr_mod, "_request_timeout", side_effect=fake_timeout), \
             patch.object(tr_mod, "logger"):
            tr._gemini_correct_hedged(["m1", "m2"], {}, {}, time.monotonic() + 30.0, 30.0)

        self.assertGreaterEqual(limity[0], 12.0,
                                "zdrowy model musi mieć pełne 12 s, bo w szczytach odpowiada po 7-10 s")

    def test_jeden_zdrowy_model_wystarcza_do_pelnego_limitu(self):
        tr, tr_mod = self._transcriber()
        teraz = time.monotonic()
        tr._slow_llm_models = {"m1": teraz + 200.0}      # m2 zdrowy
        limity = []

        with patch.object(tr_mod, "_request_timeout", side_effect=lambda d, cap=None: limity.append(cap)), \
             patch.object(tr_mod, "logger"):
            tr._gemini_correct_hedged(["m1", "m2"], {}, {}, time.monotonic() + 30.0, 30.0)

        self.assertGreaterEqual(limity[0], 12.0)


class TestGlownyLogPrzyjmujeZapis(unittest.TestCase):
    """U Filipa główny log nie dostał ani jednej linii, a ostrzeżenia szły do pliku błędów."""

    def setUp(self):
        # setup_logging() robi basicConfig(force=True), które zamyka i usuwa handlery roota.
        # Bez przywrócenia reszta zestawu logowałaby do zamkniętych plików.
        root = logging.getLogger()
        self._handlery = list(root.handlers)
        self._poziom_roota = root.level
        self._poziom_galezi = logging.getLogger("whiscribe").level

    def tearDown(self):
        root = logging.getLogger()
        for h in list(root.handlers):
            if h not in self._handlery:
                root.removeHandler(h)
                try:
                    h.close()
                except Exception:
                    pass
        root.handlers[:] = self._handlery
        root.setLevel(self._poziom_roota)
        logging.getLogger("whiscribe").setLevel(self._poziom_galezi)

    def test_log_powstaje_i_ma_wiersz_kontrolny(self):
        import importlib
        import tempfile

        katalog = tempfile.mkdtemp(prefix="whiscribe-log-test-")
        with patch.dict(os.environ, {"WHISCRIBE_LOG_DIR": katalog}):
            import logging_setup
            importlib.reload(logging_setup)
            info = logging_setup.setup_logging()
            logging.getLogger("whiscribe.app").info("wiersz po konfiguracji")
            for h in logging.getLogger().handlers:
                h.flush()

            self.assertTrue(os.path.exists(info["path"]), "główny plik logu nie powstał")
            tresc = open(info["path"], encoding="utf-8").read()
            self.assertIn("Log gotowy", tresc,
                          "brak wiersza kontrolnego, czyli nic nie potwierdza, że log działa")
            self.assertIn("wiersz po konfiguracji", tresc)
            self.assertFalse(os.path.exists(info["errors_path"]),
                             "plik błędów nie powinien powstawać, gdy nic się nie wysypało")

    def test_niedzialajacy_glowny_log_jest_zglaszany(self):
        import importlib
        import tempfile

        katalog = tempfile.mkdtemp(prefix="whiscribe-log-test-")
        with patch.dict(os.environ, {"WHISCRIBE_LOG_DIR": katalog}):
            import logging_setup
            importlib.reload(logging_setup)

            ostrzezenia = []

            class GluchyHandler(logging.Handler):
                """Udaje handler, który przyjmuje rekordy, ale nic nie zapisuje do pliku."""

                def __init__(self, sciezka):
                    super().__init__()
                    self.baseFilename = sciezka
                    self.stream = None

                def emit(self, record):
                    pass

                def flush(self):
                    pass

            sciezka = os.path.join(katalog, "nieistniejacy.log")
            with patch.object(logging_setup.logging.getLogger("whiscribe.logi"), "warning",
                              side_effect=lambda msg, *a, **k: ostrzezenia.append(msg)):
                logging_setup._sprawdz_zapis(GluchyHandler(sciezka), sciezka)

            self.assertTrue(ostrzezenia, "brak zapisu do głównego logu musi być zgłoszony")
            self.assertIn("nie przyjmuje zapisu", ostrzezenia[0])
            self.assertIn("handlery", ostrzezenia[0], "ostrzeżenie musi nieść diagnozę, nie tylko fakt")

    def test_brak_glownego_handlera_jest_zglaszany(self):
        import importlib
        import tempfile

        katalog = tempfile.mkdtemp(prefix="whiscribe-log-test-")
        with patch.dict(os.environ, {"WHISCRIBE_LOG_DIR": katalog}):
            import logging_setup
            importlib.reload(logging_setup)
            ostrzezenia = []
            with patch.object(logging_setup.logging.getLogger("whiscribe.logi"), "warning",
                              side_effect=lambda msg, *a, **k: ostrzezenia.append(msg)):
                logging_setup._sprawdz_zapis(None, os.path.join(katalog, "x.log"))
            self.assertTrue(ostrzezenia)
            self.assertIn("nie powstał", ostrzezenia[0])


if __name__ == "__main__":
    unittest.main()
