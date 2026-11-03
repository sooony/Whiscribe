# Whiscribe 2.2.18 - review kodu, plan logow i pamieci wklejek

Data: 3.11.2026. Material: review stabilnosci (specjalista Python/Windows 11), projekt rozwiazania (projektant systemu), krytyka wykonalnosci (deweloper), runda odpowiedzi projektanta na krytyke. Wszystkie ustalenia faktograficzne sprawdzone w kodzie.

---

## 1. Dlaczego tekst ci ginie - prawdziwa przyczyna

Nie chodzi o schowek. Chodzi o to, ze widzet, do ktorego aplikacja obiecuje tekst odlozyc, nie istnieje.

Panel transkrypcji w widzecie jest martwym kodem. `transcript_lines` jest tylko zapisywane (overlay.py:1822), nigdzie nie rysowane. `panel_open` jest na stale `False` (overlay.py:688) i ma jedno odwolanie, w obsludze kolka myszy. To samo z podgladem na zywo: `live_tail` jest zapisywany (overlay.py:1813) i nigdy nie renderowany. Osiem wywolan w app.py pisze w pustke: 936, 944, 1050, 1076, 1089, 1108, 1127, 1294.

Skutek: cztery dymki klamia.

| Miejsce | Co mowi dymek | Co sie faktycznie dzieje |
|---|---|---|
| app.py:1027 | "Przetwarzanie przerwane - jesli tekst dojdzie pozniej, bedzie w widzecie" | tekst nie trafia nigdzie |
| app.py:1091 | "Fokus okna utracony - koncowka tekstu zachowana w widzecie" | koncowka przepada |
| app.py:1108 | "Spozniony tekst jest w widzecie (nie wklejono)" | tekst przepada |
| app.py:1148 | "Fokus okna utracony - tekst zachowano w widzecie" | tekst przepada |

Do tego dymki gasna po 10 s (`BALLOON_DEFAULT_S`, overlay.py:22), wiec komunikat o utracie tekstu znika razem z tekstem.

Drugi, osobny mechanizm utraty: `inject_text` po wklejeniu przywraca poprzedni schowek, a gdy poprzedni byl pusty, czysci schowek do `""` (injector.py:317-324). To jest dzialanie zamierzone (ochrona prywatnosci), ale razem z martwym panelem oznacza, ze podyktowany tekst nie zostaje nigdzie.

**Wniosek: pamiec wklejek nie jest dodatkiem. Jest zamiennikiem martwego panelu i docelowa odpowiedzia na "tekst nie ginie".**

---

## 2. Logi - 70 procent to szum bibliotek

W app.log jest 18 999 wierszy. 13 054 z nich (69 procent) to dwa komunikaty z `faster_whisper`: "Processing audio with duration" (6909 razy) i "VAD filter removed" (6145 razy). Dalej ok. 300 wierszy z `httpx`, plus comtypes. W streamingu faster-whisper pisze 2 wiersze co 0,32 s, czyli ok. 370 wierszy na minute dyktowania.

Przyczyna: root logger ma poziom INFO (app.py:331), wiec kazda biblioteka pisze do pliku. Przy `maxBytes=2_000_000, backupCount=2` kilka godzin dyktowania wypycha z historii wszystkie wlasne komunikaty. Po awarii nie ma z czego czytac.

Dwa dodatkowe problemy, ktore wyszly po drodze:
- Format (app.py:332) nie zawiera `%(name)s` ani nazwy watku, wiec po logu nie da sie powiedziec, co zalogowalo dana linie ani z ktorego watku.
- Log lezy w katalogu aplikacji (`get_app_dir()`, app.py:325), czyli dla exe w `dist\Whiscribe-Portable`. Build PyInstallera czysci `dist`, wiec log z awarii ginie przy pierwszym przebudowaniu - ten sam mechanizm, ktory kasuje twoj config.json.
- Trzy miejsca wyciekaja tresc do logu: `meeting_manager.py:109` zapisuje caly transkrypt spotkania segment po segmencie na INFO, `meeting_manager.py:102` dwa pelne teksty przy odrzuceniu echa, `app.py:839` pelny tytul okna docelowego (nazwy dokumentow, klientow, tematy maili). Log nie wychodzi nigdzie poza ten komputer, ale tresc dyktowania i spotkan nie ma powodu w nim lezec.

### Decyzja po dyskusji

Deweloper chcial dwoch linijek (`faster_whisper` i `httpx` na WARNING), projektant obronil swoje rozwiazanie jednym argumentem: po zmianie nazw loggerow na prefiks `whiscribe.` w 12 plikach wystarczy root na WARNING i `whiscribe` na INFO, a lista wyciszen ma **zero** pozycji, bo biblioteki milkna przez dziedziczenie poziomu. Kazda nastepna gadatliwa zaleznosc jest cicha z automatu. Przyjete.

Z projektu wylecialo, jako przerost formy dla jednego uzytkownika:
- flaga `log_text_content` (nie ma czego bramkowac, tresc dyktowania jest juz na DEBUG w app.py:1092 i 1100, a DEBUG jest wylaczony),
- przelacznik diagnostyki w menu kontekstowym (UI do zdarzenia kilka razy w roku; zostaje klucz `log_level` w config.json bez UI, nadpisywany zmienna `WHISCRIBE_LOG_DIR`/`WHISCRIBE_LOG_LEVEL`),
- lista dziewieciu wyciszen bibliotek (siedem z nich nie generuje dzis ani jednego wiersza).

### Jedyne miejsce, gdzie plan mogl pogorszyc stan obecny

Dzis wersja deweloperska i portable pisza do dwoch roznych plikow, przez przypadek sciezki. Po przeniesieniu do `%LOCALAPPDATA%\Whiscribe\logs` zlalyby sie w jeden, a rotacja robi `os.rename`, ktory na Windows leci `PermissionError`, gdy plik trzyma drugi proces. Blad idzie na `sys.stderr`, ktory w buildzie windowed jest `None`, czyli awaria rotacji byla by **calkowicie cicha**. To samo z pytest, ktory importuje app.py i dzis pisze do loga w repo (w app.log jest 172 wiersze z MagicMockami).

Rozwiazanie: nazwa pliku z `sys.frozen` (`whiscribe.log` dla exe, `whiscribe-dev.log` dla wersji deweloperskiej), katalog nadpisywalny zmienna `WHISCRIBE_LOG_DIR` ustawiana w `tests/conftest.py`, handler z `delay=True` i podklasa z `doRollover` odpornym na `PermissionError` (nie rotuje, pisze dalej, jeden WARNING). Konfiguracja logowania zostaje przy imporcie, niezaleznie od mutexa, bo bledy startu leca przed mutexem (mutex jest w app.py:2214, logowanie w app.py:324-336).

---

## 3. Pamiec wklejek - rozstrzygniecie twojej niepewnosci

Pytales, czy ma to byc jeden wpis czy dwa-trzy. Projektant najpierw chcial trzech, deweloper jednego, i projektant ustapil, rozbierajac wlasny argument: deduplikacja nie ratuje scenariusza "podyktowalem drugi raz", bo powtorne dyktowanie tej samej mysli nigdy nie daje identycznego ciagu znakow. A jesli drugie dyktowanie weszlo, pierwsze jest niepotrzebne; jesli nie weszlo, masz swiezsza wersje tej samej mysli.

**Decyzja: magazyn to `deque(maxlen=...)` z wartoscia z configu, domyslnie 1.** Przejscie na 3 to zmiana jednej liczby w config.json plus pozycja podmenu, nie przepisanie modulu. Wyzwalacz jest konkretny: pierwszy raz, gdy wcisniesz skrot i dostaniesz nowszy tekst niz ten, ktorego chciales.

### Co wchodzi

- Nowy modul `paste_memory.py`, instancja w `DictationApp`. Wpis: czas, tekst, liczba znakow, status, nazwa procesu docelowego. Tylko RAM, zero plikow.
- **Karmienie przy powstaniu tekstu, nie przy wklejeniu.** Tekst, ktorego nie udalo sie wkleic, jest dokladnie tym, ktory najbardziej chcesz odzyskac. Piec punktow: app.py:1098 (przed sprawdzeniem `_is_current_job` w 1103, bo galaz porzuconego zadania wychodzi returnem - to lapie takze spozniony wynik z 1103-1110), app.py:1086-1091 jako `typed_text + final_tail`, app.py:1041-1050, app.py:1027, oraz status po probie wklejenia z app.py:1143.
- Do pamieci idzie tekst **przed** normalizacja. `inject_text` robi `text.strip() + " "` (injector.py:242), wiec zapisanie tego, co dostal injector, dawaloby przy przywracaniu druga spacje.
- Spotkania nie wchodza. Maja wlasny plik (notepad_manager.py:58) i inny cykl zycia.
- `inject_text` zaczyna zwracac wynik (udalo sie, tryb paste czy typed). Dzis zwraca `None` i cicho przechodzi na wpisywanie znak po znaku przy zablokowanym schowku (injector.py:293-296), wiec status wpisu bylby zgadywany.

### Dostep

- **Skrot globalny Ctrl+Alt+V**, przez istniejace `register_system_hotkey(103, ...)` plus galaz w app.py:1367. Z wierszem WARNING, gdy `RegisterHotKey` zwroci False, bo Ctrl+Alt+V bywa zajete (np. przez Visual Studio) i dzis wynik rejestracji nigdzie nie jest sprawdzany. Odrejestrowanie 103 trzeba dopisac do `overlay.close()` (overlay.py:1948).
- **Pigulka "Przywroc" w linii statusu widzetu.** Pomysl czwartej ikonki w naglowku upadl na geometrii: oba specjalisci przeliczyli szerokosc karty (jeden 140 px, drugi 151 px) i niezaleznie wyszlo im, ze czwarta ikonka laduje na napisie "Whiscribe", a hitboxy juz dzis na siebie nachodza, wiec zostaloby jej 16 px klikalnych. Zamiast tego: w stanie idle linia statusu pokazuje `Gotowe 00:00`, gdzie `00:00` jest zawsze zerami (martwe piksele), i to miejsce zajmuje klikalna pigulka - bursztynowa, gdy ostatni tekst nie zostal wklejony, neutralna, gdy zostal. Hitbox 52 x 16 px, bez przebudowy karty.
- **Jedna plaska pozycja w menu widzetu i w trayu** ("Przywroc ostatnia wklejke (14:32, nie wklejono)"), bez podmenu. Tray to pystray bez numerycznych ID, wiec pozycja o zmiennej etykiecie wymaga `text` jako callable.

### Co robi przywracanie

Wkleja do okna aktywnego **teraz**, nie do zapamietanego `target_hwnd`. Przez te sama sciezke `inject_text` z dzisiejszym `restore_clipboard`, czyli ochrona schowka i wykluczenie z historii Win+V zostaja nietkniete - pamiec **zastepuje** schowek jako magazyn, nie oslabia go. Bez auto-Entera (`_send_auto_enter`, app.py:1433): przywracanie to naprawa, a ponowne wyslanie wiadomosci jest jedyna rzecza w tym przeplywie, ktorej nie da sie cofnac. Bez zuzywania wpisu, wiec ten sam tekst mozna wkleic w dwa miejsca. Odmowa z dymkiem w stanach recording, processing i meeting.

### Piec min w sciezce przywracania, znalezionych w dyskusji

1. **Ctrl+V nad Explorerem wkleja pliki.** Bramka `is_text_field_focused` jest tylko w `start_recording` (app.py:814), `inject_text` nie sprawdza niczego. W sciezce przywracania bramka musi byc **zawsze wlaczona, niezaleznie od opcji "Wymagaj aktywnego pola tekstowego"**: przy starcie dyktowania ta opcja jest wygoda, przy przywracaniu zablakany Ctrl+V nad pulpitem albo Explorerem robi destrukcyjny skutek uboczny w cudzym katalogu.
2. **Fizycznie trzymany Ctrl.** Wciskasz skrot, wiec Ctrl i Alt sa wcisniete, gdy leci `inject_text`, a ten zwalnia tylko Alt (injector.py:283-288). `kb.release` nie zmienia stanu fizycznego klawiatury. Potrzebna petla na `GetAsyncKeyState` dla VK_CONTROL, VK_MENU i VK_SHIFT (wzor w app.py:317) z twardym limitem 500 ms, bo zawieszony klawisz sprzetowy zablokowalby funkcje na zawsze. Poprawia tez zwykle dyktowanie skrotem.
3. **Wyscig o schowek.** Jesli skrot wystrzeli, gdy finalizacja wlasnie wkleja (app.py:1143), dwa watki nadpisza sobie `old_clipboard` i twoj schowek zostanie z dyktowanym tekstem albo pusty. `self._type_lock` chroni wpisywanie, nie schowek. Potrzebny jeden lock na kazde wejscie do `inject_text`.
4. **Powtarzanie skrotu.** `WM_HOTKEY` powtarza sie przy przytrzymaniu klawisza, a `_safe_dispatch` (overlay.py:226-235) odpala nowy watek na kazde zdarzenie, czyli przytrzymany Ctrl+Alt+V to kolejka rownoleglych wklejen. Potrzebny debounce 0,35 s plus flaga "w toku".
5. **Normalizacja tekstu** - opisana wyzej, podwojna spacja.

### Co swiadomie odrzucone

Trwalosc na dysku i DPAPI w pierwszym podejsciu. Projektant sam sie wycofal: realne tryby awarii, ktore bola (utracony fokus, spozniony wynik, porzucone przetwarzanie), zdarzaja sie przy zywej aplikacji, a restart jako punkt utraty to hipoteza, nie obserwacja. Do tego szyfrowanie jednego dyktowania jest niespojne, dopoki klucz API Gemini lezy jawnym tekstem w `%APPDATA%\Whiscribe\secrets.json` (config.py:103-112). Dokladamy, jak zglosisz, ze straciles tekst na restarcie, i wtedy od razu z DPAPI.

Odrzucone takze: oparcie sie o historie schowka Windows (sam to wykluczyles, a aplikacja celowo sie z niej wypisuje), wylaczenie ochrony schowka jako obejscie (menu ID 107), cyklowanie wpisow podwojnym nacisnieciem skrotu, automatyczne wklejanie po powrocie fokusu (wklejenie w okno, ktorego nie wybrales, w momencie, ktorego nie wybrales, jest gorsze niz utrata tekstu), reanimacja panelu transkrypcji.

---

## 4. Review stabilnosci - co znalazl specjalista

Ocena ogolna: aplikacja jest uzywalna i widac, ze wiekszosc ostrych krawedzi zostala przepracowana (porzucanie zadan, lock na ikonie traya, watchdogi, odcinanie spoznionych wynikow). Nie jest natomiast stabilna w sensie "dziala bez niespodzianek przez caly dzien".

Ponizej posortowane. Pozycje oznaczone **[sprawdzone]** zweryfikowalem sam w kodzie.

### Ryzyko crasha albo zawieszki

1. **[sprawdzone] overlay.py:1873 - rysowanie do tego samego DIB-a z dwoch watkow naraz.** `restore()` wola `self._render_frame(time.time())` w watku wywolujacego, a nie w watku UI. Leci z przywracania widzetu z paska, ze skrotu i z menu, wiec dwa watki jednoczesnie robia `memmove` do `self.p_bits` i `UpdateLayeredWindow` na tym samym `mem_dc`. Od pocietej klatki po twardy crash w gdi32. Naprawa to jedna linia: zamiast `_render_frame` ustawic `self._dirty = True` i zostawic rysowanie w `_run_ui`. Kasuje przy okazji wyciek obiektu COM ITaskbarList, ktory `restore()` tworzy przy kazdym przywroceniu bez `Release` (overlay.py:599-631).
2. **app.py:1898, 1953, 1998 - tkinter w watkach pobocznych bez gwarantowanego destroy.** Kazde okienko (klucz API, adres serwera, O programie) robi `tk.Tk()` w swiezym watku daemon, a `root.destroy()` jest tylko na sciezce szczesliwej. Dwa okienka naraz to dwa interpretery Tcl w dwoch watkach - klasyczne zrodlo twardego wyjscia procesu w paczce PyInstaller. Naprawa: `destroy()` w `finally` plus lock na jedno okienko.

### Tekst trafia tam, gdzie nie powinien

3. **[sprawdzone] app.py:630 - tekst wpisywany do obcego okna, gdy okno docelowe zniknelo.** Warunek `target_inactive` wymaga `IsWindow(self.target_hwnd)`. Gdy okno docelowe zostalo zamkniete w trakcie dyktowania, `IsWindow` daje False, wiec `target_inactive` wychodzi False i dalsze slowa leca do dowolnego okna, ktore ma teraz fokus. Scenariusz: dyktujesz w streamingu do zakladki Chrome, zamykasz ja w polowie zdania, reszta laduje w terminalu albo w komunikatorze. Naprawa: wpisuj tylko gdy `cur_fg == self.target_hwnd`, a nieistniejacy `target_hwnd` traktuj jako brak celu.
4. **[sprawdzone] app.py:1146 - TypeError gubi tekst, ktory mial byc uratowany.** `user32.GetForegroundWindow.restype = wintypes.HWND` (app.py:236), czyli ctypes zwraca `None`, gdy nie ma okna pierwszego planu, a linia 1146 formatuje to przez `:#x`. Dokladnie w tej galezi (nie udalo sie przywrocic fokusu: ekran blokady, UAC) foreground bywa NULL, wiec format rzuca TypeError, leci do `except` i nie wykonuje sie ani dymek, ani zapis - tracisz cala wypowiedz. Linia 625 ma juz poprawne `or 0`, w 1146 go brakuje.
5. **[sprawdzone] injector.py:274-291 - wykluczenie z historii schowka nigdy nie dziala.** Po `pyperclip.copy(text)` kod robi `OpenClipboard(None)` i `SetClipboardData(cf_history, ...)`, ale `SetClipboardData` wymaga, zeby okno bylo wlascicielem schowka (po `EmptyClipboard`), a tu wlascicielem jest juz zniszczone okno pyperclipa. Efekt: kazda dyktowana wypowiedz trafia do Win+V i do Cloud Clipboard, mimo ze docstring obiecuje cos innego. Wycieku pamieci nie ma (nieudane `SetClipboardData` zwraca None i blok jest zwalniany), ale cala ochrona prywatnosci jest martwa. Naprawa: cala operacja w jednej sesji schowka (`OpenClipboard(hwnd widzetu)`, `EmptyClipboard`, `SetClipboardData(CF_UNICODETEXT, ...)` i oba znaczniki), albo uczciwa zmiana opisu. **To warto najpierw potwierdzic testem na zywej aplikacji**, bo wniosek opiera sie na dokumentacji Win32, nie na obserwacji.

### Stan aplikacji rozjezdza sie z rzeczywistoscia

6. **app.py:827 i 842 - stan "recording" zostaje po nieudanym starcie mikrofonu.** Stan jest ustawiany w 827, a `recorder.start()` leci w 842 i tworzy `sd.InputStream` bez try/except (recorder.py:72-80). Gdy mikrofon jest zajety albo wlasnie odlaczony, wyjatek zostaje tylko zalogowany, a aplikacja siedzi w stanie "recording" bez nagrywania: widzet pokazuje nagrywanie, skrot przestaje dzialac jak start, wychodzi z tego dopiero auto-stop po ciszy.
7. **[sprawdzone] config.py:209-211 - rownolegle, nieatomowe zapisy config.json.** `save_config` otwiera plik w trybie `"w"` (czyli obcina) bez locka, a wolaja go rownolegle menu kontekstowe, przelaczniki z traya i okienka dialogowe. Dwa klikniecia naraz albo zamkniecie aplikacji w trakcie zapisu daja obcięty JSON, a wtedy `load_config` cicho wraca do DEFAULT_CONFIG - tracisz motyw, presety dzwiekow, providera LLM i ustawienia widzetu. Naprawa: modulowy lock plus zapis atomowy (plik tymczasowy i `os.replace`).
8. **app.py:1138-1150 - okno wyscigu miedzy sprawdzeniem zadania a wklejeniem.** `_is_current_job(job)` jest sprawdzane raz (1103), a potem leci przywracanie fokusu do 300 ms i `inject_text`. Jesli w tym czasie porzucisz przetwarzanie skrotem i zaczniesz nowe dyktowanie w innym oknie, stary watek dokonczy wklejanie do nowego celu.

### Wycieki przy dlugiej pracy

9. **[sprawdzone] app.py:1374, app.py:2202, overlay.py:1206 - wyciek uchwytu HDESK co 3 sekundy.** `OpenDesktopW("Default", ...)` nigdy nie jest zamykane przez `CloseDesktop`, a `setup_hotkey()` wola to takze z watchdoga, ktory sprawdza co 3 s bez zadnego backoffu (app.py:1218-1228). Jesli pynput nie potrafi sie wznowic (zajety hook, powrot z ekranu blokady), zostaje 1200 uchwytow na godzine i co 3 s nowy watek listenera.
10. **focus_detector.py:165-275 - porzucone watki UIA.** `is_text_field_focused` startuje watek z `CoInitialize` i `GetFocusedControl()`, czeka `join(timeout=0.18)` i idzie dalej. Przy zawieszonym oknie docelowym (typowe dla Electrona i Office pod obciazeniem) watek nigdy sie nie konczy i zostaje z zainicjowanym apartamentem COM. Kazdy start dyktowania w takiej sytuacji doklada jeden watek na stale.
11. **app.py:1550-1738 - menu kontekstowe: uchwyty i NameError na sciezce bledu.** Siedem `CreatePopupMenu` powstaje przed wewnetrznym `try`, a `DestroyMenu` jest tylko w jego `finally`. Dodatkowo gdy `TrackPopupMenuEx` rzuci, zmienna `cmd` nie istnieje i linia 1740 rzuca NameError - dostajesz menu, ktore nic nie robi. Naprawa: `cmd = 0` przed `try` i tworzenie menu w tym samym `try`.

### Wydajnosc tam, gdzie boli

12. **app.py:657-676 - animacja ikony w zasobniku to 12 plikow tymczasowych na sekunde.** Petla chodzi z `sleep(0.08)` i za kazdym razem przerysowuje ikone 256x256 z LANCZOS, a pystray dla kazdej podmiany robi `tempfile.mkstemp`, zapis ICO, `LoadImage` i `DestroyIcon`. Przez caly czas dyktowania i przetwarzania. Stad zreszta historyczne OSError 1401, obsluzone w app.py:2176. Naprawa: zwolnic do 0,2-0,25 s i nie animowac stanu "processing".
13. **overlay.py:1629 - `_glow_sprite` liczony od zera w kazdej klatce.** Bez cache (w przeciwienstwie do `_ICON_CACHE` i `_FONT_CACHE`), czyli obraz ok. 250x250 RGBA z `GaussianBlur(18)` 33 razy na sekunde, obok pelnego renderu karty w 3x. W stanie "processing" zabiera CPU dokladnie wtedy, gdy jest potrzebny, i opoznia wpisywanie w streamingu.
14. **app.py:970-1001 - finalizacja czeka na GPU streamingu.** `_begin_finalization` robi `join(timeout=0.4)`, a krok streamingu trzyma `Transcriber._lock` przez caly przebieg `model.transcribe`. Po 0,4 s finalizacja idzie dalej i blokuje sie na tym samym locku, wiec stan "processing" wisi dluzej, niz pokazuje licznik.
15. **overlay.py:1946-1952 - `close()` zeruje `_running` przed blokujacym SendMessage**, wiec zamykanie aplikacji zacina sie na chwile (ratuje je `os._exit(0)`). Naprawa: najpierw odrejestrowac skroty, potem `_running = False`, albo `PostMessageW`.
16. **transcriber.py:666 - `httpx.Client(timeout=None)`** przy budzecie ponizej 1 s oznacza zadanie bez limitu. Dzis nieosiagalne, ale kazda zmiana kolejnosci obliczen daje zawieszenie finalizacji na lokalnym Ollamie.

### Co jest zrobione dobrze

DIB i mem DC powstaja raz i sa zwalniane w `finally` watku UI, `_ICON_CACHE` i `_FONT_CACHE` maja ograniczone klucze, `GlobalAlloc` w injectorze jest zwalniany na sciezce bledu, `threading.excepthook` jest ustawiony, `_tray_icon_lock`, `_job_seq` i `_stream_session` sensownie odcinaja spoznione zadania, `sys.stdout is None` i `sys._MEIPASS` sa obsluzone.

---

## 5. Plan pracy

### Krok 1: cisza w logu i jedno miejsce na log (3-4 h)

Prefiks `whiscribe.` w 12 loggerach, root na WARNING, `whiscribe` na INFO. Format z `%(name)s` i `%(threadName)s`. Katalog `%LOCALAPPDATA%\Whiscribe\logs` z nazwa z `sys.frozen`, zmienna `WHISCRIBE_LOG_DIR`, `delay=True`, rotacja odporna na `PermissionError`, przekierowanie w `tests/conftest.py` na poziomie modulu. Jednolinijkowy odcisk startu (wersja, frozen, device, model, dostawca LLM, zrodlo klucza bez klucza). `meeting_manager.py:102` i `:109` na DEBUG, tytul okna wyciety z app.py:839. Pozycja menu "Otworz folder z logami" (ID 110). Poprawka komunikatu w app.py:2282, ktory na sztywno mowi "app.log". Usuniecie smieciowych logow z repo (`build_2215..2218.log`, `out.log`, `err.log`, `pw_err.log`, `start_err.log`, `test_pw.log`, `test_pythonw.log`).

Opcjonalnie w tym samym kroku: drugi plik `app-errors.log` (tylko WARNING i wyzej, z `exc_info`) - to on bylby pierwszym plikiem do otwarcia po awarii.

### Krok 2: cztery uczciwe dymki, usuniecie martwego panelu, `inject_text` zwracajacy wynik (2-3 h)

Dymki w app.py:1027, 1091, 1108, 1148 dostaja tresc wskazujaca skrot i `duration_s=0`, czyli stoja do klikniecia "Rozumiem". Usuniecie `panel_open`, `show_live_preview`, `transcript_lines`, `live_tail`, `scroll_line`, `_user_scrolled`, `_max_visible_lines`, obslugi kolka, `add_transcript_entry`, `clear_transcript`, `update_live_text` i osmiu wywolan w app.py. W opisie commita zdanie, ze pamiec wklejek jest docelowym miejscem, w ktorym tekst nie ginie, zeby panel nie wrocil rownolegle.

Uwaga: dymek w app.py:1119 ("Korekta AI nieudana") jest prawdziwy i nie wolno go ruszac.

### Krok 3: pamiec wklejek, jeden wpis, Ctrl+Alt+V (4-6 h)

`paste_memory.py`, karmienie w pieciu punktach, skrot 103 z odrejestrowaniem w `close()`, pigulka w linii statusu, jedna pozycja w menu widzetu i w trayu. Bramka pola tekstowego zawsze, oczekiwanie na puszczenie modyfikatorow, lock na `inject_text`, debounce, bez auto-Entera. Wiekszosc czasu idzie na modyfikatory i fokus, nie na sama pamiec.

### Krok 4: krytyczne poprawki stabilnosci (2-3 h)

Pozycje 1, 3, 4, 6 i 7 z sekcji 4: `restore()` bez `_render_frame`, warunek wpisywania w app.py:630, `or 0` w app.py:1146, `recorder.start()` w try/except z powrotem do idle, atomowy zapis configu z lockiem. Male zmiany, duzy efekt - to te, ktore odczuwasz najmocniej.

Mozna je zrobic przed krokiem 1, jesli wolisz najpierw przestac tracic tekst w cudzych oknach.

### Krok 5: reszta, osobno

Wyciek HDESK z backoffem w watchdogu, watki UIA, tkinter w `finally`, animacja traya, cache `_glow_sprite`, uchwyty menu, `close()` z `PostMessageW`, timeout w transcriberze. Plus potwierdzenie i naprawa wykluczenia z Win+V (pozycja 5), bo to jedyna rzecz z calego review, ktora dotyczy obietnicy prywatnosci danej w docstringu.

### Na polke

Ring 3 wpisow z podmenu (zmiana jednej liczby w configu, gdy okaze sie potrzebny), trwalosc pamieci na dysku z DPAPI, przelacznik diagnostyki w menu, `crash.log` przez `faulthandler`.

### Osobne zadanie poza tym zakresem

Klucz API Gemini lezy jawnym tekstem w `%APPDATA%\Whiscribe\secrets.json` (config.py:103-112). Wart wspolnego helpera DPAPI, bo jest cenniejszym celem niz jedno dyktowanie.

---

## 6. Czego plan dotyka poza kodem

- `config.example.json` **jest juz nieaktualny**: brakuje `widget_mode`, `max_recording_seconds`, `auto_enter_after_dictation` i `config_rev` z DEFAULT_CONFIG (config.py:19-55). Kazdy nowy klucz (`log_level`, `paste_memory_size`) musi wejsc i do DEFAULT_CONFIG, i tam, bo `whiscribe.spec` wozi ten plik w `datas` i `load_config` zasiewa z niego pierwsze uruchomienie.
- README nie wspomina o app.log ani jednym slowem. Potrzebna sekcja "gdzie sa logi", nowe klucze i Ctrl+Alt+V w liscie skrotow.
- `tests/conftest.py` izoluje config.json i APPDATA, ale nie LOCALAPPDATA i nie plik logu. Warte nowych testow: `paste_memory` (ring, limit znakow) jako czysty Python bez Win32, oraz test, ze `inject_text` zwraca poprawny wynik przy zablokowanym schowku.
- `whiscribe.spec` dla logow nie wymaga zmian (`faulthandler` to stdlib, `crypt32` laduje sie przez `WinDLL` po nazwie). COLLECT dalej czysci `dist`, wiec config.json trzeba odkladac przed kazdym buildem; przeniesienie logu zalatwia polowe tego problemu.
- Pojemnosc dymka: render lamie tekst do `pw - 36` przy czcionce 9 px i ucina do 3 wierszy, czyli ok. 75 znakow. Dymek nie pokaze przywracanej tresci, tylko komunikat w stylu "Tekst nie zostal wklejony. Ctrl+Alt+V wkleja go do aktywnego okna."

---

## 7. Wynik kroku 5 (3.11.2026, wersja 2.2.20)

Zrobione:

- **Wyciek HDESK.** Trzy miejsca otwieraly wlasny uchwyt pulpitu, w tym `setup_hotkey()`, wolane przez watchdoga co 3 s. Teraz jeden uchwyt na caly proces (`win32_desktop.py`), bo `CloseDesktop` i tak odmawia zamkniecia pulpitu przypisanego do zywego watku. Przy okazji poprawne `argtypes`/`restype`: bez nich ctypes obcinal 64-bitowy uchwyt do 32 bitow.
- **Watchdog skrotow.** Odstep rosnie 3, 6, 12, 24, 48, 60 s, a ostrzezenie leci raz, nie przy kazdej probie. Dotad zajety hook pynput dawal 1200 prob i 1200 wierszy w logu na godzine, czyli dokladnie to, czego nie chcesz w logach.
- **Okienka tkinter.** Jedno naraz (lock) i `destroy()` w `finally`. Przy okazji okno "O programie" bierze skroty z configu, wiec nie klamie o Ctrl+Alt+M i pokazuje tez Ctrl+Alt+V.
- **Animacja ikony w zasobniku.** Z 12 klatek na sekunde na 5 przy nagrywaniu i 2 przy przetwarzaniu, z zachowanym tempem pulsowania (krok licznika klatek rosnie proporcjonalnie do odstepu). Tyle samo mniej plikow tymczasowych, zapisow ICO i `DestroyIcon`.
- **Cache blasku.** `_glow_sprite` liczyl `GaussianBlur` na obrazie ok. 250x250 dwa razy na klatke. Klucz jest zaokraglony (promien i alfa w 16 krokach), bo plynnie zmieniaja sie z glosnoscia. Pomiar: 44 ms na 120 wywolan bez cache, 3,4 ms z cache, 8 kluczy dla realnej animacji.
- **Uchwyty menu.** Sprzatanie przenioslo sie do zewnetrznego `finally`, ktore niszczy glowne menu i te podmenu, ktore nie zdazyly sie dolaczyc (dolaczone niszczy kaskadowo rodzic).
- **Timeout korekty AI.** Sciezka OpenAI/Groq/Ollama podawala `timeout=None` do `httpx`, gdy z budzetu zostalo mniej niz sekunde, czyli zadanie bez limitu. Teraz zwraca surowy tekst ze statusem `timeout`, a dymek mowi "zabraklo czasu".
- **Watki UIA.** Jeden watek roboczy zamiast nowego na kazde zapytanie. Zawieszona inspekcja blokuje ten jeden watek (kolejne zapytania od razu ida sciezka awaryjna po nazwie procesu), a po 15 s watek jest porzucany i startuje nowy, najwyzej trzy razy. Sprawdzone: 40 zapytan do zawieszonej inspekcji to 1 watek zamiast 40.

Nie bylo do zrobienia:

- **`close()` z `PostMessageW`** (pozycja 15) jest juz w kodzie, prawdopodobnie z wczesniejszej zmiany. Kolejnosc `_running = False` przed odrejestrowaniem skrotow nie szkodzi, bo odrejestrowanie nieistniejacego skrotu tylko zwraca False.

Co sie nie potwierdzilo:

- **Wykluczenie z Win+V (pozycja 5) nie bylo martwe.** Review twierdzilo, ze `SetClipboardData` musi zawiesc, bo wlascicielem schowka jest zniszczone okno pyperclipa. Sprawdzone na zywym systemie: `SetClipboardData` zwraca uchwyt, a `IsClipboardFormatAvailable` potwierdza oba znaczniki w schowku razem z tekstem. Wniosek z dokumentacji Win32 byl falszywy, bo przy NULL jako wlascicielu Windows na to pozwala.
- Prawdziwy problem byl inny i cichszy: **kolejnosc**. Pyperclip zamykal schowek, Windows rozsylal `WM_CLIPBOARDUPDATE`, i tylko potem dopisywalismy znaczniki, wiec menedzer historii mogl zdazyc przeczytac wpis bez nich. Teraz tekst i oba znaczniki ida w jednej sesji (`OpenClipboard`, `EmptyClipboard`, `SetClipboardData`), a pyperclip zostaje jako sciezka awaryjna. Sprawdzone na tekstach 48 i 5000 znakow: tekst zgodny, oba znaczniki na miejscu.
- Przy okazji: **historia schowka jest u ciebie wylaczona** (brak `EnableClipboardHistory` w `HKCU\Software\Microsoft\Clipboard`), wiec dzisiaj Win+V i tak nic nie zapisuje. Poprawka ma znaczenie, gdy ja wlaczysz albo przeniesiesz aplikacje na inny komputer.
- Pozycja 11 mowila tez o `NameError` na `cmd`, gdy `TrackPopupMenuEx` rzuci. W tej strukturze to niemozliwe: metoda nie ma `except`, wiec wyjatek przerywa przeplyw przed `if cmd == ...`. Wyciek uchwytow byl prawdziwy, `NameError` nie.

Co nadal czeka:

- Pozycje 8 i 14 z sekcji 4 (okno wyscigu miedzy sprawdzeniem zadania a wklejeniem, finalizacja czekajaca na GPU streamingu) - obie dotykaja kolejnosci w finalizacji, wiec warte osobnego podejscia z testami na zywej aplikacji.
- Rzeczy "na polce" bez zmian.
- Wspolny helper DPAPI dla `secrets.json` nadal poza zakresem.

### Znalezione po drodze w logu z zywej pracy

Cichy log z 2.2.19 od razu pokazal blad, ktorego review nie znalazlo, bo nie wynika z samego czytania kodu. Plik `whiscribe-errors.log` z twojej sesji 3.11.2026:

```
15:21:37,992 W Nagranie osiagnelo limit 20 min - automatyczne zatrzymanie.
15:21:37,993 I Rozpoczeto dyktowanie...
15:21:38,116 I Zatrzymano nagrywanie, finalizowanie...
```

To nie bylo zapomniane nagranie. Stan `recording` wchodzil pod lockiem, a `_recording_start_time` dopiero po otwarciu mikrofonu, czyli kilkadziesiat milisekund pozniej. `_monitor_silence` chodzi co 0,1 s i sprawdza "stan recording i czas od startu ponad limit", wiec trafiajac w to okno widzial stan `recording` ze starym czasem startu. Przy pierwszym dyktowaniu po starcie aplikacji ten czas to 0.0 z inicjalizacji, czyli roznica rzedu 56 lat: limit przekroczony natychmiast. Twoje swieze dyktowanie zostalo ubite 124 ms po rozpoczeciu i musialo byc powtorzone (15:21:39).

Trafia to kazde dyktowanie rozpoczete ponad 20 minut po poprzednim, nie tylko pierwsze. Blad jest swiezy, bo `max_recording_seconds` to nowy klucz.

Naprawa: czas startu wchodzi w tym samym bloku z lockiem co stan. Test regresyjny odtwarza wyscig i na starym ukladzie lapie watchdoga 5 razy w ciagu 0,3 s, czyli okno bylo szerokie, a nie teoretyczne.

Wniosek ogolniejszy: pozycje 8 i 14 z sekcji 4 (okno wyscigu w finalizacji, czekanie na GPU streamingu) dotykaja tej samej rodziny bledow, czyli stanu sprawdzanego w jednym momencie i uzywanego w innym. Warto je wziac razem, z testami tego samego rodzaju.

