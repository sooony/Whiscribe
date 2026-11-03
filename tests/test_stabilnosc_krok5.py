"""Testy regresyjne dla kroku 5 review kodu (2.2.20).

Każdy test pilnuje jednego błędu znalezionego w działającym kodzie:
1. OpenDesktopW bez CloseDesktop, wołane z watchdoga co 3 s (1200 uchwytów na godzinę).
2. Watchdog skrótów bez backoffu: próba i WARNING co 3 s, gdy nasłuch nie wstaje.
3. Okienka tkinter bez gwarantowanego destroy() i bez ograniczenia do jednego naraz.
4. Animacja ikony w zasobniku: 12 plików tymczasowych na sekundę przez całe dyktowanie.
5. _glow_sprite liczony od zera w każdej klatce (GaussianBlur na obrazie ok. 250x250).
6. Uchwyty menu kontekstowego gubione, gdy błąd poleci przed TrackPopupMenuEx.
7. timeout=None w żądaniu korekty AI przy wyczerpanym budżecie (żądanie bez limitu).
8. Nowy wątek inspekcji UIA na każde zapytanie, zostający na stałe przy zawieszonym oknie.
9. Znaczniki wykluczenia z Win+V dopisywane dopiero po opublikowaniu tekstu w schowku.
10. Watchdog limitu nagrania ubijal swieze dyktowanie (znalezione w logu z zywej pracy).
"""
import threading
import time
import unittest
from unittest.mock import MagicMock, patch


class TestUchwytPulpituNieWycieka(unittest.TestCase):
    """setup_hotkey() leci też z watchdoga co 3 s, a każde wywołanie otwierało nowy HDESK."""

    def test_wielokrotne_przypiecie_otwiera_pulpit_tylko_raz(self):
        import win32_desktop

        with patch.object(win32_desktop, "_hdesk", None), \
             patch.object(win32_desktop, "_user32") as fake_user32:
            fake_user32.OpenDesktopW.return_value = 0x1234
            fake_user32.SetThreadDesktop.return_value = 1

            for _ in range(200):
                self.assertTrue(win32_desktop.przypnij_watek_do_pulpitu())

            self.assertEqual(fake_user32.OpenDesktopW.call_count, 1,
                             "każde przypięcie otwiera nowy uchwyt pulpitu")
            self.assertEqual(fake_user32.SetThreadDesktop.call_count, 200,
                             "przypięcie wątku musi lecieć za każdym razem, uchwyt jest wspólny")

    def test_przypiecie_z_wielu_watkow_uzywa_jednego_uchwytu(self):
        import win32_desktop

        with patch.object(win32_desktop, "_hdesk", None), \
             patch.object(win32_desktop, "_user32") as fake_user32:
            fake_user32.OpenDesktopW.return_value = 0x1234
            fake_user32.SetThreadDesktop.return_value = 1

            watki = [threading.Thread(target=win32_desktop.przypnij_watek_do_pulpitu) for _ in range(12)]
            for w in watki:
                w.start()
            for w in watki:
                w.join(timeout=5)

            self.assertEqual(fake_user32.OpenDesktopW.call_count, 1)

    def test_nieudane_otwarcie_pulpitu_nie_wywraca_aplikacji(self):
        import win32_desktop

        with patch.object(win32_desktop, "_hdesk", None), \
             patch.object(win32_desktop, "_ostrzezenie_zglaszane", False), \
             patch.object(win32_desktop, "_user32") as fake_user32:
            fake_user32.OpenDesktopW.return_value = 0

            self.assertFalse(win32_desktop.przypnij_watek_do_pulpitu())
            self.assertFalse(win32_desktop.przypnij_watek_do_pulpitu())
            fake_user32.SetThreadDesktop.assert_not_called()


class TestWatchdogSkrotowZBackoffem(unittest.TestCase):
    """Przy zajętym hooku pynput watchdog próbował co 3 s: tysiąc wierszy w logu na godzinę."""

    def _app_z_watchdogiem(self):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app._running = True
        app.hotkey_listener = None
        return app, app_mod

    def test_odstep_rosnie_a_ostrzezenie_leci_raz(self):
        app, app_mod = self._app_z_watchdogiem()
        odstepy = []
        proby = []

        def fake_sleep(s):
            odstepy.append(s)
            if len(odstepy) >= 6:
                app._running = False

        app.setup_hotkey = lambda: proby.append(1)

        with patch.object(app_mod.time, "sleep", side_effect=fake_sleep), \
             patch.object(app_mod, "logger") as log:
            app._watchdog_hotkey()

        self.assertEqual(odstepy[0], 3.0)
        self.assertGreater(odstepy[-1], odstepy[0],
                           "odstęp między próbami musi rosnąć, inaczej watchdog kręci się co 3 s")
        self.assertLessEqual(max(odstepy), 60.0, "odstęp nie powinien rosnąć bez granicy")
        self.assertEqual(log.warning.call_count, 1,
                         "ostrzeżenie o martwym nasłuchu ma lecieć raz, nie przy każdej próbie")
        self.assertGreaterEqual(len(proby), 2, "watchdog nadal musi próbować wznawiać nasłuch")

    def test_po_wznowieniu_odstep_wraca_do_trzech_sekund(self):
        app, app_mod = self._app_z_watchdogiem()
        odstepy = []

        zywy = MagicMock()
        zywy.is_alive.return_value = True

        def fake_sleep(s):
            odstepy.append(s)
            if len(odstepy) == 3:
                app.hotkey_listener = zywy   # nasłuch wstał
            if len(odstepy) >= 6:
                app._running = False

        app.setup_hotkey = lambda: None

        with patch.object(app_mod.time, "sleep", side_effect=fake_sleep), \
             patch.object(app_mod, "logger"):
            app._watchdog_hotkey()

        self.assertEqual(odstepy[-1], 3.0,
                         "po powrocie nasłuchu watchdog musi wrócić do częstego sprawdzania")


class TestOkienkaTkinter(unittest.TestCase):
    """root.destroy() stało tylko na ścieżce szczęśliwej, a dwa okna naraz to dwa interpretery Tcl."""

    def _app(self):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app._tk_dialog_lock = threading.Lock()
        return app, app_mod

    def test_okno_jest_niszczone_takze_gdy_pytanie_rzuci(self):
        app, app_mod = self._app()
        root = MagicMock()

        with patch.dict("sys.modules", {"tkinter": MagicMock(Tk=MagicMock(return_value=root))}), \
             patch.object(app_mod, "logger"):
            status, wynik = app._zapytaj_w_okienku("test", lambda r: 1 / 0)

        self.assertEqual(status, "blad")
        self.assertIsNone(wynik)
        root.destroy.assert_called_once()

    def test_drugie_okno_nie_powstaje_rownolegle(self):
        app, app_mod = self._app()
        root = MagicMock()
        w_srodku = threading.Event()
        pusc = threading.Event()
        drugi_status = []

        def pierwsze_pytanie(r):
            w_srodku.set()
            pusc.wait(timeout=5)
            return "pierwszy"

        with patch.dict("sys.modules", {"tkinter": MagicMock(Tk=MagicMock(return_value=root))}), \
             patch.object(app_mod, "logger"):
            t = threading.Thread(target=lambda: app._zapytaj_w_okienku("pierwsze", pierwsze_pytanie))
            t.start()
            self.assertTrue(w_srodku.wait(timeout=5))

            status, _ = app._zapytaj_w_okienku("drugie", lambda r: "drugi")
            drugi_status.append(status)

            pusc.set()
            t.join(timeout=5)

        self.assertEqual(drugi_status, ["zajete"],
                         "drugie okno tkinter powstało, mimo że pierwsze było otwarte")

    def test_po_bledzie_lock_jest_zwalniany(self):
        app, app_mod = self._app()
        root = MagicMock()

        with patch.dict("sys.modules", {"tkinter": MagicMock(Tk=MagicMock(return_value=root))}), \
             patch.object(app_mod, "logger"):
            app._zapytaj_w_okienku("pierwsze", lambda r: 1 / 0)
            status, wynik = app._zapytaj_w_okienku("drugie", lambda r: "ok")

        self.assertEqual((status, wynik), ("ok", "ok"),
                         "po wyjątku w okienku kolejne okno musi dać się otworzyć")


class TestAnimacjaZasobnika(unittest.TestCase):
    """pystray przy każdej podmianie ikony robi plik tymczasowy, zapis ICO, LoadImage i DestroyIcon."""

    def _app(self, stan):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app._running = True
        app.state = stan
        app.tray_icon = MagicMock()
        app.recorder = MagicMock()
        app.recorder.get_volume_level.return_value = 0.4
        app._set_tray_icon = MagicMock()
        return app, app_mod

    def _ile_podmian(self, stan, sekundy=1.0):
        app, app_mod = self._app(stan)
        czas = [0.0]

        def fake_sleep(s):
            czas[0] += s
            if czas[0] >= sekundy:
                app._running = False

        with patch.object(app_mod.time, "sleep", side_effect=fake_sleep):
            app._tray_anim_worker()
        return app._set_tray_icon.call_count

    def test_nagrywanie_rysuje_ikone_najwyzej_szesc_razy_na_sekunde(self):
        ile = self._ile_podmian("recording")
        self.assertLessEqual(ile, 6, f"ikona zasobnika przerysowana {ile} razy na sekundę nagrywania")
        self.assertGreaterEqual(ile, 2, "animacja nagrywania musi być nadal widoczna")

    def test_przetwarzanie_rysuje_rzadziej_niz_nagrywanie(self):
        self.assertLess(self._ile_podmian("processing"), self._ile_podmian("recording"),
                        "przetwarzanie nie reaguje na głos, więc nie potrzebuje tempa nagrywania")

    def test_stan_bezczynny_nie_rusza_ikony(self):
        self.assertEqual(self._ile_podmian("idle"), 0)


class TestCacheBlasku(unittest.TestCase):
    """_glow_sprite liczył GaussianBlur dwa razy na klatkę, czyli 66 razy na sekundę."""

    def test_te_same_parametry_daja_ten_sam_obiekt(self):
        import overlay

        overlay._GLOW_CACHE.clear()
        a = overlay._glow_sprite(44, (120, 160, 250, 70), 6)
        b = overlay._glow_sprite(44, (120, 160, 250, 70), 6)
        self.assertIs(a[0], b[0], "blask liczony drugi raz dla tych samych parametrów")

    def test_cache_nie_rosnie_bez_granicy(self):
        import overlay

        overlay._GLOW_CACHE.clear()
        for i in range(4000):
            overlay._glow_sprite(20 + (i % 40), (120, 160, 250, i % 256), 5 + (i % 3))
        self.assertLessEqual(len(overlay._GLOW_CACHE), overlay._GLOW_CACHE_MAX,
                             "cache blasku rośnie bez ograniczenia")

    def test_blask_wyglada_tak_samo_jak_bez_cache(self):
        import overlay

        overlay._GLOW_CACHE.clear()
        z_cache = overlay._glow_sprite(30, (255, 45, 65, 80), 6)
        overlay._GLOW_CACHE.clear()
        bez_cache = overlay._glow_sprite(30, (255, 45, 65, 80), 6)
        self.assertEqual(z_cache[1], bez_cache[1])
        self.assertEqual(z_cache[0].tobytes(), bez_cache[0].tobytes())


class TestUchwytyMenuKontekstowego(unittest.TestCase):
    """Siedem CreatePopupMenu powstawało przed try, a DestroyMenu było tylko w jego finally."""

    def test_niedolaczone_podmenu_jest_zwalniane(self):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app._menu_glowne = 0xAA
        app._menu_podmenu = [0xB1, 0xB2, 0xB3]
        app._menu_dolaczone = {0xB1}

        with patch.object(app_mod.ctypes, "windll") as windll, \
             patch.object(app_mod, "logger"):
            app._zwolnij_uchwyty_menu()
            zwolnione = [c.args[0] for c in windll.user32.DestroyMenu.call_args_list]

        self.assertIn(0xAA, zwolnione, "główne menu musi zostać zwolnione")
        self.assertIn(0xB2, zwolnione, "niedołączone podmenu wycieka")
        self.assertIn(0xB3, zwolnione, "niedołączone podmenu wycieka")
        self.assertNotIn(0xB1, zwolnione,
                         "dołączone podmenu niszczy kaskadowo DestroyMenu rodzica")

    def test_powtorne_zwolnienie_nic_nie_robi(self):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app._menu_glowne = 0xAA
        app._menu_podmenu = [0xB1]
        app._menu_dolaczone = set()

        with patch.object(app_mod.ctypes, "windll") as windll, \
             patch.object(app_mod, "logger"):
            app._zwolnij_uchwyty_menu()
            windll.user32.DestroyMenu.reset_mock()
            app._zwolnij_uchwyty_menu()
            windll.user32.DestroyMenu.assert_not_called()

    def test_brak_uchwytow_nie_wywraca_sprzatania(self):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        with patch.object(app_mod.ctypes, "windll"), patch.object(app_mod, "logger"):
            app._zwolnij_uchwyty_menu()   # nie powinno rzucić


class TestBudzetKorektyAI(unittest.TestCase):
    """Przy resztce budżetu poniżej sekundy _request_timeout zwraca None, czyli brak limitu."""

    def _transcriber(self, provider="ollama"):
        import transcriber as tr_mod

        tr = object.__new__(tr_mod.Transcriber)
        tr.config = {
            "llm_provider": provider,
            "llm_endpoint": "http://localhost:11434/v1",
            "llm_model": "llama3.2",
            "use_llm": True,
        }
        tr.last_llm_status = None
        return tr, tr_mod

    def test_wyczerpany_budzet_nie_wysyla_zadania_i_zwraca_surowy_tekst(self):
        tr, tr_mod = self._transcriber()
        surowy = "tekst po whisperze"

        with patch.object(tr_mod.httpx, "Client") as klient, \
             patch.object(tr_mod, "_request_timeout", return_value=None), \
             patch.object(tr_mod, "logger"):
            wynik = tr._post_process_with_llm(surowy)

        klient.assert_not_called()
        self.assertEqual(wynik, surowy, "surowy tekst nie może zginąć przy pominiętej korekcie")
        self.assertEqual(tr.last_llm_status, "timeout")

    def test_status_timeout_daje_uczciwy_komunikat(self):
        import app as app_mod
        import inspect

        zrodlo = inspect.getsource(app_mod.DictationApp)
        self.assertIn('"timeout"', zrodlo,
                      "status timeout musi być obsłużony, inaczej użytkownik nie wie o pominiętej korekcie")


class TestPulaWatkowUIA(unittest.TestCase):
    """Wątek na zapytanie zostawał na stałe, gdy GetFocusedControl nie wracało."""

    def test_zawieszona_inspekcja_blokuje_jeden_watek_nie_kazdy(self):
        from focus_detector import _PulaUIA

        pula = _PulaUIA()
        stop = threading.Event()
        przed = threading.active_count()
        try:
            for _ in range(40):
                self.assertFalse(pula.wykonaj(lambda: stop.wait(timeout=30), 0.02))
            wzrost = threading.active_count() - przed
            self.assertLessEqual(wzrost, 1,
                                 f"40 zapytań do zawieszonej inspekcji zostawiło {wzrost} wątków")
        finally:
            stop.set()

    def test_zdrowa_inspekcja_uzywa_jednego_watku_wielokrotnie(self):
        from focus_detector import _PulaUIA

        pula = _PulaUIA()
        wyniki = []
        przed = threading.active_count()
        for _ in range(50):
            self.assertTrue(pula.wykonaj(lambda: wyniki.append(1), 2.0))
        self.assertEqual(len(wyniki), 50)
        self.assertLessEqual(threading.active_count() - przed, 1)

    def test_po_zawieszeniu_pula_wraca_do_zycia(self):
        from focus_detector import _PulaUIA

        pula = _PulaUIA()
        pula.PROG_PORZUCENIA = 0.05
        stop = threading.Event()
        try:
            self.assertFalse(pula.wykonaj(lambda: stop.wait(timeout=30), 0.02))
            time.sleep(0.1)
            wyniki = []
            self.assertTrue(pula.wykonaj(lambda: wyniki.append(1), 2.0),
                            "po porzuceniu zawieszonego wątku bramka pola tekstowego musi znów działać")
            self.assertEqual(wyniki, [1])
        finally:
            stop.set()

    def test_liczba_porzuconych_watkow_ma_granice(self):
        from focus_detector import _PulaUIA

        pula = _PulaUIA()
        pula.PROG_PORZUCENIA = 0.01
        stop = threading.Event()
        przed = threading.active_count()
        try:
            for _ in range(30):
                pula.wykonaj(lambda: stop.wait(timeout=30), 0.01)
                time.sleep(0.02)
            wzrost = threading.active_count() - przed
            self.assertLessEqual(wzrost, pula.MAKS_PORZUCONYCH + 1,
                                 f"pula urosła do {wzrost} wątków, limit porzuconych nie działa")
        finally:
            stop.set()


class TestLimitNagraniaNieUbijaSwiezegoDyktowania(unittest.TestCase):
    """Zdarzylo sie na zywo 3.11.2026 o 15:21:37, przy pierwszym dyktowaniu po starcie.

    Stan "recording" wchodzil pod lockiem, a `_recording_start_time` dopiero po otwarciu
    mikrofonu. `_monitor_silence` chodzi co 0,1 s, wiec trafiajac w to okno widzial stan
    "recording" z zerowym czasem startu i natychmiast zglaszal "limit 20 min":

        15:21:37,992 W Nagranie osiagnelo limit 20 min - automatyczne zatrzymanie.
        15:21:37,993 I Rozpoczeto dyktowanie...
        15:21:38,116 I Zatrzymano nagrywanie, finalizowanie...
    """

    def _app(self):
        import app as app_mod

        app = object.__new__(app_mod.DictationApp)
        app._lock = threading.RLock()
        app._running = True
        app.state = "idle"
        app.overlay = None
        app.tray_icon = None
        app.config = {"require_text_field": False, "max_recording_seconds": 1200,
                      "auto_stop_silence_seconds": 0}
        app._recording_start_time = 0.0
        app.last_active_hwnd = 0
        app.recorder = MagicMock()
        app.committed_text = ""
        app.committed_sample_offset = 0
        app._stream_stop_event = threading.Event()
        return app, app_mod

    def test_czas_startu_wchodzi_razem_ze_stanem(self):
        app, app_mod = self._app()

        # Mikrofon startuje wolno: to wlasnie w tym czasie watchdog budzil sie i ubijal nagranie
        widziane = []

        def wolny_start():
            widziane.append((app.state, app._recording_start_time))
            time.sleep(0.15)

        app.recorder.start.side_effect = wolny_start

        with patch.object(app_mod, "is_valid_target_window", return_value=False), \
             patch.object(app_mod.user32, "GetForegroundWindow", return_value=0), \
             patch.object(app_mod, "ForwardStreamCommitter", MagicMock()), \
             patch.object(app_mod, "logger"):
            app.start_recording()

        stan_w_trakcie, czas_w_trakcie = widziane[0]
        self.assertEqual(stan_w_trakcie, "recording")
        self.assertGreater(czas_w_trakcie, 0.0,
                           "stan recording wszedl przed czasem startu, wiec watchdog limitu "
                           "widzi zerowy czas i ubija swieze nagranie")

    def test_watchdog_nie_zatrzymuje_nagrania_rozpoczetego_przed_chwila(self):
        app, app_mod = self._app()
        zatrzymania = []
        app.stop_and_transcribe = lambda: zatrzymania.append(1)

        # Watchdog budzi sie dokladnie w chwili, gdy mikrofon jeszcze startuje
        def wolny_start():
            app._monitor_silence_jedna_runda = True
            time.sleep(0.05)

        app.recorder.start.side_effect = wolny_start

        with patch.object(app_mod, "is_valid_target_window", return_value=False), \
             patch.object(app_mod.user32, "GetForegroundWindow", return_value=0), \
             patch.object(app_mod, "ForwardStreamCommitter", MagicMock()), \
             patch.object(app_mod, "logger"):
            watek = threading.Thread(target=app.start_recording)
            watek.start()

            # Przez caly start mikrofonu sprawdzamy warunek watchdoga tak jak on
            koniec = time.time() + 0.3
            while time.time() < koniec:
                if (app.state == "recording"
                        and time.time() - app._recording_start_time >= 1200):
                    zatrzymania.append("watchdog")
                time.sleep(0.01)
            watek.join(timeout=5)

        self.assertEqual(zatrzymania, [],
                         "watchdog limitu zatrzymal nagranie rozpoczete przed chwila")


class TestWykluczenieZHistoriiSchowka(unittest.TestCase):
    """Znaczniki dopisywane po pyperclipie trafiały do schowka już po powiadomieniu słuchaczy."""

    def test_tekst_i_znaczniki_ida_w_jednej_sesji(self):
        import injector

        kolejnosc = []
        formaty = []

        class FakeUser32:
            def RegisterClipboardFormatW(self, nazwa):
                return {"CanIncludeInClipboardHistory": 49749,
                        "ExcludeClipboardContentFromMonitorProcessing": 49796}[nazwa]

            def OpenClipboard(self, hwnd):
                kolejnosc.append("open")
                return 1

            def EmptyClipboard(self):
                kolejnosc.append("empty")
                return 1

            def SetClipboardData(self, cf, h):
                kolejnosc.append(f"set:{cf}")
                formaty.append(cf)
                return h

            def CloseClipboard(self):
                kolejnosc.append("close")
                return 1

        with patch.object(injector, "_cb_user32", FakeUser32()):
            self.assertTrue(injector._zapisz_schowek_z_wykluczeniem("tekst probny"))

        self.assertEqual(kolejnosc[0], "open")
        self.assertEqual(kolejnosc[1], "empty")
        self.assertEqual(kolejnosc[-1], "close")
        self.assertEqual(kolejnosc.count("open"), 1,
                         "tekst i znaczniki muszą iść w jednej sesji schowka")
        self.assertIn(injector.CF_UNICODETEXT, formaty)
        self.assertIn(49749, formaty, "brak znacznika CanIncludeInClipboardHistory")
        self.assertIn(49796, formaty, "brak znacznika ExcludeClipboardContentFromMonitorProcessing")
        self.assertLess(formaty.index(injector.CF_UNICODETEXT), formaty.index(49749),
                        "tekst musi być w schowku przed znacznikami")

    def test_nieudane_otwarcie_schowka_nie_zostawia_sesji(self):
        import injector

        zamkniecia = []

        class FakeUser32:
            def RegisterClipboardFormatW(self, nazwa):
                return 49749

            def OpenClipboard(self, hwnd):
                return 0

            def CloseClipboard(self):
                zamkniecia.append(1)
                return 1

        with patch.object(injector, "_cb_user32", FakeUser32()):
            self.assertFalse(injector._zapisz_schowek_z_wykluczeniem("tekst"))

    def test_odrzucony_blok_pamieci_jest_zwalniany(self):
        import injector

        zwolnione = []

        class FakeUser32:
            def RegisterClipboardFormatW(self, nazwa):
                return 49749

            def OpenClipboard(self, hwnd):
                return 1

            def EmptyClipboard(self):
                return 1

            def SetClipboardData(self, cf, h):
                return 0      # schowek odrzuca blok

            def CloseClipboard(self):
                return 1

        class FakeKernel32:
            def GlobalAlloc(self, flagi, rozmiar):
                return 0xDEAD

            def GlobalLock(self, h):
                return 0x1000

            def GlobalUnlock(self, h):
                return 1

            def GlobalFree(self, h):
                zwolnione.append(h)
                return 0

        with patch.object(injector, "_cb_user32", FakeUser32()), \
             patch.object(injector, "_cb_kernel32", FakeKernel32()), \
             patch.object(injector.ctypes, "memmove"):
            self.assertFalse(injector._zapisz_schowek_z_wykluczeniem("tekst"))

        self.assertIn(0xDEAD, zwolnione,
                      "blok odrzucony przez schowek zostaje własnością procesu i musi być zwolniony")

    def test_gdy_jedna_sesja_zawiedzie_tekst_wchodzi_przez_pyperclip(self):
        import injector

        with patch.object(injector, "_zapisz_schowek_z_wykluczeniem", return_value=False), \
             patch.object(injector, "pyperclip") as pc, \
             patch.object(injector, "zwolnij_modyfikatory"), \
             patch.object(injector, "send_unicode_string"), \
             patch.object(injector, "_cb_user32"), \
             patch.object(injector.time, "sleep"), \
             patch.object(injector, "logger"):
            pc.paste.return_value = ""
            injector._inject_text_locked("awaryjny tekst", restore_clipboard=False)

        self.assertTrue(pc.copy.called,
                        "gdy jedna sesja schowka nie wyjdzie, tekst musi wejść przez pyperclip")


if __name__ == "__main__":
    unittest.main()
