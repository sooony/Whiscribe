# Whiscribe v2.2.0 — brief naprawczy dla agenta wykonawczego

Dokument powstał z audytu kodu i artefaktów build/release z 01.10.2026.
Odbiorca: agent, który będzie wprowadzał poprawki. Autor zmian: Filip (właściciel repo `sooony/Whiscribe`).

Wszystkie odniesienia mają format `plik:linia` względem katalogu głównego projektu.

---

## 0. Czego NIE ruszać — ślepe uliczki

Zweryfikowane, **nie są problemem**. Nie trać na to czasu i nie "naprawiaj" tego:

1. **Repozytorium git jest czyste.** Przeskanowano 247 obiektów, `git grep` po wszystkich commitach,
   wszystkie 34 historyczne wersje `config.json` mają `"llm_api_key": ""`. Potwierdzone też
   bezpośrednio z `raw.githubusercontent.com`. **Nie rób rewrite'u historii, nie używaj `filter-repo`,
   nie forsuj push-ów.** Historia jest w porządku.
2. **Folder projektu nie jest synchronizowany do OneDrive**, mimo ścieżki `C:\Users\filkn\OneDrive\...`.
   Pliki mają tylko atrybut `Archive`, brak `ReparsePoint`/`Pinned`/`RecallOnDataAccess`,
   proces OneDrive nie działa, brak wpisu autostartu. Nic z tego katalogu nie wychodzi do chmury.
   Nie przenoś projektu i nie buduj wokół tego żadnych zabezpieczeń.
3. **`Whiscribe-Dev` jest repozytorium prywatnym** (API GitHuba zwraca 404 bez autoryzacji). Nie wyciekło.
4. **Backend lokalnego LLM działa poprawnie** — `transcriber.py:350-353` prawidłowo przepuszcza
   `ollama`/`local`/`lmstudio` bez klucza API. Logika korekty jest OK. Problem jest wyłącznie w UI (p. B1).

---

## A. KLUCZE API — jedyne realne zagrożenie, priorytet bezwzględny

### A1. Klucz Gemini wyciekł w publicznym Release v2.1.9

**Status: potwierdzone dowodowo, nie podejrzenie.**

Klucz `AQ.Ab8R… (zamaskowany, klucz wycofany)` (provider: gemini, `use_llm: true`)
znajduje się w pliku `Whiscribe-Portable/_internal/config.json` **wewnątrz obu assetów**
publicznego release'u:

```
https://github.com/sooony/Whiscribe/releases/download/v2.1.9/Whiscribe-Portable-v2.1.9-Lite.zip
https://github.com/sooony/Whiscribe/releases/download/v2.1.9/Whiscribe-Portable-v2.1.9-Full.zip
```

Zweryfikowane przez pobranie tego wpisu z archiwum na GitHubie range-requestami (nie z kopii lokalnej).
Rozmiary assetów (141 626 704 B i 1 633 959 966 B) zgadzają się co do bajtu z `dist/`.

**Okoliczność łagodząca:** `download_count` = **0** dla obu assetów. Nikt ich nie pobrał.
Release ma jeden dzień. Klucz jest z darmowego tieru. Ryzyko faktycznego nadużycia jest niskie —
ale URL-e release'ów są publiczne i indeksowalne, więc traktujemy to jako wyciek do usunięcia.

### A2. Dlaczego to przeszło niezauważone — przyczyna źródłowa

`config.json` jest pakowany do builda **dwukrotnie**, z `whiscribe.spec`:

- `whiscribe.spec:9` → `datas = [('config.json', '.')]` → ląduje w `_internal/config.json`
- `whiscribe.spec` (koniec pliku) → `shutil.copy('config.json', out_dir)` → ląduje w katalogu głównym paczki

Ktoś wyczyścił **tylko** kopię widoczną w katalogu głównym:

```
dist/Whiscribe-Portable-Dist/config.json            -> "llm_api_key": ""      (wyczyszczone)
dist/Whiscribe-Portable-Dist/_internal/config.json  -> "llm_api_key": "AQ..." (przeoczone)
dist/Whiscribe-Portable/config.json                 -> "llm_api_key": "AQ..." (najnowszy build, brudny)
dist/Whiscribe-Portable/_internal/config.json       -> "llm_api_key": "AQ..." (najnowszy build, brudny)
```

Kopia z `_internal/` jest tą, którą `config.py:69-82` faktycznie czyta jako szablon przy
pierwszym uruchomieniu — czyli dokładnie tą, która trafia do użytkownika.

### A3. Co zrobić — kolejność

**Krok 1 — unieważnić klucz (robi Filip, nie agent).**
`aistudio.google.com` → usunąć klucz `AQ.Ab8R… (zamaskowany, klucz wycofany)` → wygenerować nowy.
Reszta kroków zakłada, że stary klucz jest już martwy.

**Krok 2 — usunąć skażone assety z GitHuba.**
Nie da się "poprawić" pliku w release — asset trzeba usunąć i wgrać ponownie.

```bash
gh release delete-asset v2.1.9 Whiscribe-Portable-v2.1.9-Lite.zip --yes
gh release delete-asset v2.1.9 Whiscribe-Portable-v2.1.9-Full.zip --yes
```

Nie usuwaj samego release'u ani tagu `v2.1.9` (tag jest w historii i jest czysty).
Po przebudowaniu (krok 4) wgraj nowe paczki pod tymi samymi nazwami przez `gh release upload v2.1.9 ...`.

**Krok 3 — rozdzielić konfigurację od sekretu.** To jest właściwa naprawa, nie kosmetyka.

Wymagania, które muszą być spełnione jednocześnie:
- klucz **nigdy** nie trafia do repo ani do builda,
- klucz **działa lokalnie podczas testów bez żadnej gimnastyki** (wymaganie Filipa),
- użytkownik końcowy wpisuje własny klucz w aplikacji i to się zapisuje lokalnie.

Projekt rozwiązania:

1. `config.json` → wypisać z repo i dodać do `.gitignore`:
   ```bash
   git rm --cached config.json
   printf '\n# Local user config (may contain API keys)\nconfig.json\n' >> .gitignore
   ```
2. Dodać do repo `config.example.json` — identyczny z `DEFAULT_CONFIG` z `config.py`,
   z `"llm_api_key": ""` i `"use_llm": false`.
3. W `whiscribe.spec`: `datas` ma pakować **`config.example.json`**, nigdy `config.json`.
   Usunąć `shutil.copy('config.json', out_dir)` na końcu spec-a — niech `load_config()`
   tworzy świeży `config.json` z `DEFAULT_CONFIG` przy pierwszym starcie
   (ta ścieżka już istnieje w `config.py:84-85`, wystarczy jej nie obchodzić).
4. W `config.py` — hierarchia źródeł klucza, od najwyższego priorytetu:
   ```
   1. zmienna środowiskowa  WHISCRIBE_LLM_API_KEY
   2. %APPDATA%\Whiscribe\secrets.json   -> {"llm_api_key": "..."}
   3. config.json (llm_api_key)          -> zachowane dla wstecznej kompatybilności
   ```
   Do testów lokalnych wystarczy wtedy `set WHISCRIBE_LLM_API_KEY=...` albo plik `secrets.json`
   poza drzewem projektu — nic nie może przypadkiem wejść do commita ani do paczki.
   `save_config()` **nie może** zapisywać klucza do `config.json`, jeśli pochodzi on z (1) lub (2).
5. **Bezpiecznik w buildzie** — bez tego problem wróci przy następnym release. Na końcu
   `whiscribe.spec`, po `COLLECT`, dodać twardy fail:
   ```python
   import json, glob, sys
   for p in glob.glob(os.path.join('dist', 'Whiscribe-Portable', '**', 'config*.json'), recursive=True):
       if 'models' in p:            # pomiń config.json modelu Whisper
           continue
       try:
           if json.load(open(p, encoding='utf-8')).get('llm_api_key'):
               sys.exit(f'BUILD ABORTED: klucz API w {p}')
       except (json.JSONDecodeError, OSError):
           pass
   ```

**Krok 4 — przebudować i zweryfikować przed uploadem.** Kryterium odbioru:

```bash
# musi zwrócić wyłącznie puste wartości, dla każdego config.json w paczce
find dist/Whiscribe-Portable -name "config.json" -not -path "*/models/*" \
  -exec grep -o '"llm_api_key": "[^"]*"' {} +
```

### A4. Klucz w query stringu URL-a — poprawić przy okazji

`transcriber.py:393` i `meeting_manager.py:247` wysyłają klucz jako parametr URL:

```python
url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
```

Parametry URL trafiają do logów proxy, a komunikaty wyjątków httpx potrafią zawierać pełny URL —
a `transcriber.py:437` i `meeting_manager.py:312` logują treść wyjątku do `app.log`.
Zamienić na nagłówek, który Gemini obsługuje równorzędnie:

```python
url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
headers = {"x-goog-api-key": api_key}
```

Dodatkowo: upewnić się, że żaden `logger.*` nigdy nie formatuje `api_key` ani URL-a z kluczem.

---

## B. Pozostałe zagrożenia bezpieczeństwa i prywatności

### B1. Dyktowany tekst może zostać wklejony do niewłaściwego okna  ⚠ najpoważniejsze po kluczu

`app.py:910-921` próbuje przywrócić fokus do okna docelowego, czeka max 300 ms w pętli —
a potem **bezwarunkowo** woła `inject_text(final_text, ...)`, nie sprawdzając, czy fokus faktycznie wrócił:

```python
for _ in range(15):
    if user32.GetForegroundWindow() == self.target_hwnd:
        break
    time.sleep(0.02)

inject_text(final_text, restore_clipboard=...)   # <- brak warunku
```

Jeśli przywrócenie fokusu się nie uda (okno UAC, ekran blokady, pełnoekranowa gra, inna aplikacja
kradnąca fokus), `inject_text` robi `Ctrl+V` do **tego okna, które jest aktywne**. Dyktowana treść
może wylądować w polu hasła, na czacie, w terminalu albo w pasku adresu.

Ścieżka streamingowa ma już poprawną ochronę — `app.py:553-561` (`_type_stream_chunk`) buforuje tekst,
gdy `target_inactive`. Ścieżka batch tej ochrony nie ma. Ujednolicić:

- jeśli po pętli `GetForegroundWindow() != target_hwnd` → **nie wklejać**;
  pokazać dymek z informacją i zostawić tekst w panelu transkrypcji widżetu (albo w buforze do ponowienia),
- ta sama poprawka dotyczy ścieżki streamingu w `app.py:875-895` (dopychanie `buffered_untyped_text`).

### B2. Każdy proces użytkownika może zdalnie włączyć mikrofon

`app.py:643-644` tworzy nazwane obiekty zdarzeń bez własnego DACL-a:

```python
EVENT_SHOW   = r"Local\Whiscribe_ShowOverlay_Event"
EVENT_TOGGLE = r"Local\Whiscribe_Toggle_Event"
```

Dowolny inny proces w tej samej sesji może zrobić `OpenEventW` + `SetEvent` na
`Whiscribe_Toggle_Event` i uruchomić nagrywanie mikrofonu bez wiedzy użytkownika.
Dla aplikacji sprzedawanej na prywatności to istotne.

Minimum: przekazać do `CreateEventW` `SECURITY_ATTRIBUTES` z DACL-em ograniczonym do właściciela
procesu. Dodatkowo logować każde wyzwolenie przez IPC (już jest, `app.py:650`) i rozważyć
sygnalizację dźwiękową startu nagrywania jako nieusuwalną, gdy start przyszedł z IPC.

### B3. `SPI_SETFOREGROUNDLOCKTIMEOUT` ustawiany globalnie i nieprzywracany

`app.py:524`:

```python
user32.SystemParametersInfoW(0x2001, 0, ctypes.c_void_p(0), 2)   # SPI_SETFOREGROUNDLOCKTIMEOUT = 0
```

Wyłącza systemową ochronę przed kradzieżą fokusu — **dla całej sesji użytkownika, nie tylko dla
Whiscribe** — i nigdy nie przywraca poprzedniej wartości. Po zamknięciu aplikacji ustawienie zostaje
do wylogowania. Od tego momentu dowolna aplikacja w systemie może swobodnie przechwytywać fokus.

`fWinIni=2` to `SPIF_SENDCHANGE` bez `SPIF_UPDATEINIFILE`, więc nie zapisuje się do profilu — to jedyne,
co ratuje sytuację. Naprawa: odczytać starą wartość przez `SPI_GETFOREGROUNDLOCKTIMEOUT` (0x2000),
zapamiętać, przywrócić w `exit_app()`. Albo zrezygnować z tego całkowicie — `safe_bring_to_foreground`
(`app.py:255-310`) używa już `AttachThreadInput` + `AllowSetForegroundWindow`, co w praktyce wystarcza.

### B4. `Stop-Process` po wildcardzie

`app.py:1757`:

```python
f"Get-Process -Name '*Whiscribe*' | Where-Object {{ $_.Id -ne {my_pid} }} | Stop-Process -Force"
```

Zabija **każdy** proces, którego nazwa zawiera „Whiscribe" — niezależnie od tego, czy to ta aplikacja,
czy np. otwarty w edytorze plik o takiej nazwie, czy inny build użytkownika. Dopasować nazwę dokładnie
i dodatkowo zweryfikować ścieżkę pliku wykonywalnego (`$_.Path -eq ...`) przed ubiciem.

### B5. Interpolacja ścieżek do polecenia PowerShell

`app.py:426-450` (`set_autostart`) buduje jeden długi string `-Command` z wstawionymi ścieżkami:

```python
ps_cmd = (f'$sh=New-Object -ComObject WScript.Shell; '
          f'$s=$sh.CreateShortcut(\"{lnk}\"); '
          f'$s.TargetPath=\"{exe_path}\"; ...')
```

Ścieżka zawierająca `"`, `$` lub backtick rozwali polecenie albo wstrzyknie dodatkowy kod.
Dla aplikacji portable, którą użytkownik rozpakowuje gdzie chce, to realny scenariusz.
Przekazać ścieżki jako argumenty (`-File` ze skryptem + parametry) albo tworzyć skrót przez COM
bezpośrednio z Pythona (`pywin32` / `ctypes` + `IShellLink`), bez pośrednictwa shella.

### B6. Transkrypcje dyktowania w `app.log`, bez rotacji

`app.py:902` i `app.py:866` logują pełną treść:

```
Finalny czas: 1.84s | Tekst: 'No dobrze, to zróbmy teraz kilka testów...'
Wpisano łącznie: '...'
```

Obecny `app.log` ma 1,2 MB i 206 linii z treścią. Brak `RotatingFileHandler`, plik rośnie bez końca.
Lokalnie to nie wyciek (p. 0.2), ale wysłanie logu przy zgłoszeniu buga oznacza wysłanie wszystkiego,
co użytkownik podyktował.

- treść dyktowania → `logger.debug`, nigdy `info`,
- `RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=2, encoding='utf-8')` w `app.py:330`,
- rozważyć przeniesienie `app.log` i folderu `transkrypcje/` do `%LOCALAPPDATA%\Whiscribe\`
  (dla wersji portable to też naprawia zapis w `Program Files`).

### B7. Tryb spotkania nadpisuje treść otwartego Notatnika użytkownika

`notepad_manager.py:151-172`. `_connect_ui_automation()` nie jest wołane **nigdzie** — sprawdzone
w całym projekcie. Zatem `self._val_pattern` jest zawsze `None`, więc `_update_notepad_display()`
przy **każdej wypowiedzi** wchodzi w fallback: szuka dowolnego okna klasy `Notepad` i robi
`val.SetValue(self._all_text)`.

Jeśli użytkownik ma otwarty Notatnik z niezapisaną pracą, jej zawartość zostaje podmieniona
na transkrypcję spotkania. To utrata danych. Dodatkowo to blokujące zapytanie COM na wątku
transkrypcji przy każdej wypowiedzi.

Naprawa: usunąć fallback w całości (plik `.txt` jest i tak zapisywany synchronicznie w
`notepad_manager.py:99-106`), albo wiązać się z Notatnikiem tylko wtedy, gdy aplikacja sama
go uruchomiła i zapamiętała jego PID.
Przy okazji: `open_notepad_on_meeting` z `config.json` to martwa opcja — Notatnik nie jest już
uruchamiany. Albo przywrócić funkcję, albo usunąć opcję i poprawić `hotkey_meeting_description`,
które obiecuje „transkrypcję do Notatnika".

### B8. Łańcuch dostaw

- `requirements.txt` — wszystkie zależności z `>=`, zero pinów. Build nie jest odtwarzalny,
  a kolejny `pip install` może wciągnąć nową wersję `pynput`/`uiautomation` i rozwalić wpisywanie.
  Przypiąć (`==`) i wygenerować `requirements.lock` z hashami.
- `transcriber.py:154` — model `turbo` ciągnięty z `mobiuslabsgmbh/faster-whisper-large-v3-turbo`,
  czyli repozytorium społecznościowego, bez przypiętej rewizji. Dla aplikacji z obietnicą
  prywatności warto przypiąć `revision=` konkretnym commitem i zweryfikować sumy kontrolne.
- `hardware_profiler.py:52` używa `wmic`, usuniętego z nowszych buildów Windows 11.
  Zamienić na `Get-CimInstance Win32_VideoController` przez PowerShell.

---

## C. Błędy funkcjonalne

### C1. `overlay.show_balloon` nie istnieje — przycisk korekty AI rzuca wyjątek

`app.py:1484` i `app.py:1519` wołają `self.overlay.show_balloon(...)`.
W `overlay.py` są wyłącznie `show_error_balloon` (1755) i `hide_balloon` (1761). **Metody nie ma.**

Wywołanie leci z `overlay.py:1091` w surowym `threading.Thread`, więc traceback idzie na stderr —
a aplikacja chodzi pod `pythonw`/`run_silent.vbs` bez konsoli, więc w `app.log` nie ma **żadnego** śladu
(zweryfikowane: 0 trafień). Objaw dla użytkownika: ustawienie się zapisuje, ale potwierdzenie nie
pojawia się nigdy i wygląda to na „nie działa".

Dodatkowo `_render_frame` obsługuje tylko `_balloon_type == "error"` (`overlay.py:1306` i dalej),
więc dymek `"info"` i tak nie zostałby narysowany.

Naprawa: dopisać `show_balloon(kind, text)` + obsługę `"info"` w `_render_frame`.
Niezależnie od tego **owinąć wszystkie callbacki z `overlay.py` w try/except z `logger.exception`** —
obecnie każdy wyjątek w callbacku widżetu przepada bezgłośnie. To jest przyczyna, dla której ten
błąd żył tak długo.

### C2. Tryb streamingu gubi końcówkę wypowiedzi

`committed_sample_offset` jest liczony w przestrzeni próbek bufora z `recorder.get_current_audio()`,
który **nie obcina ciszy**. Natomiast `app.py:869`:

```python
remaining_audio = audio_data[self.committed_sample_offset:]
```

operuje na `audio_data` z `recorder.stop()` — a `stop()` woła `trim_silence()` (`recorder.py:131`)
i ucina ciszę wiodącą. Indeksy rozjeżdżają się o długość uciętego fragmentu.

Skutek: jeśli użytkownik zacznie mówić np. 3 s po wciśnięciu skrótu, ogon wypowiedzi jest przycięty
o ~2,8 s i ostatnie słowa nie zostają wpisane.

Naprawa: `stop()` zwraca surowy, nieobcięty bufor; `trim_silence()` stosować wyłącznie w ścieżce batch
(`transcriber.transcribe()` i tak robi to u siebie, `transcriber.py:300-302`).
Alternatywnie: zwracać z `stop()` offset obcięcia i korygować nim `committed_sample_offset`.

### C3. Lokalny LLM — brak UI i aktywne niszczenie konfiguracji

Backend jest poprawny (p. 0.4). Problem jest w warstwie UI:

- `app.py:1469` i `app.py:1508` — `toggle_gemini_correction()` i `prompt_and_set_gemini_api_key()`
  **na twardo** ustawiają `self.config["llm_provider"] = "gemini"`. Użytkownik ze skonfigurowaną
  Ollamą traci konfigurację po jednym kliknięciu przycisku AI w widżecie.
- `app.py:1464-1466` — przy braku klucza API przycisk otwiera okno „Wprowadź klucz Gemini"
  i robi `return` bez włączenia czegokolwiek. Dla trybu lokalnego klucz jest zbędny,
  więc lokalnego LLM **nie da się włączyć z interfejsu w ogóle**.
- W całym `app.py`, `overlay.py` i `hardware_profiler.py` ciągi `ollama`, `lmstudio`, `llm_endpoint`
  nie występują ani razu. Jedyna droga do trybu lokalnego to ręczna edycja `config.json`.
- `meeting_manager.py:198` — `if ... and self.config.get("llm_api_key"):` blokuje podsumowanie
  spotkania, mimo że `_generate_llm_meeting_summary()` (`meeting_manager.py:222`) obsługuje tryb lokalny.
  Z Ollamą podsumowania spotkań nie powstaną nigdy.

Naprawa:
- podmenu „Korekta AI" z wyborem dostawcy: Gemini / Groq / OpenAI / Ollama / LM Studio,
  plus pozycja „Adres lokalnego serwera..." zapisująca `llm_endpoint`,
- `toggle_*` przełącza **tylko** `use_llm`, nigdy nie nadpisuje `llm_provider`,
- warunek na włączenie i na podsumowanie: `api_key or provider in ("ollama","local","lmstudio")`
  — w obu miejscach,
- przemianować `toggle_gemini_correction` → `toggle_llm_correction`, etykiety z „Gemini Flash"
  na „Korekta AI" z aktywnym dostawcą w nawiasie.

### C4. Korekta LLM nie działa w trybie streamingu

Post-processing LLM jest wołany wyłącznie w `Transcriber.transcribe()` (`transcriber.py:352`),
czyli tylko w ścieżce batch. W streamingu nie ma go wcale — a oba przełączniki
(„Pisanie na żywo" i „Korekta AI") można włączyć jednocześnie bez żadnego ostrzeżenia.

Decyzja projektowa do podjęcia: albo korekta per zatwierdzony segment (ryzyko opóźnień i migotania
tekstu), albo wzajemne wykluczenie obu trybów w UI z jasnym komunikatem. Druga opcja jest uczciwsza.

### C5. Aliasing audio w trybie spotkania

`meeting_recorder.py:183-186`:

```python
if orig_sr % self.target_sample_rate == 0:
    dec = orig_sr // self.target_sample_rate
    return audio[::dec]
```

Goła decymacja bez filtra antyaliasingowego. WASAPI domyślnie pracuje na 48 kHz → `dec=3` →
wszystko powyżej 8 kHz zawija się w pasmo mowy. Pogarsza Whispera, a przede wszystkim **rozwala
centroid widmowy**, na którym stoi cała diaryzacja (`diarizer.py:122-127`).

Druga ścieżka (`resample_poly`, 44,1 kHz) jest wołana osobno na każdym bloku 1024 próbek bez
przenoszenia stanu filtra → nieciągłości co ~21 ms.

Naprawa: `scipy.signal.decimate(audio, dec, ftype='fir', zero_phase=True)` dla całkowitych
krotności, a dla pozostałych utrzymywać stan filtra między blokami (`lfilter_zi`) albo
resamplować dopiero na całym zebranym segmencie mowy, nie na pojedynczych blokach.

### C6. Kolejki bez ograniczenia rozmiaru

`meeting_recorder.py:35,46,47` — `speech_queue`, `_mic_raw_queue`, `_loop_raw_queue` są nieograniczone.
Jeśli transkrypcja jest wolniejsza niż czas rzeczywisty (fallback na CPU, długie spotkanie),
zużycie RAM rośnie liniowo, a opóźnienie narasta bez końca.
Dać `maxsize`, politykę odrzucania najstarszych segmentów i `logger.warning` przy przepełnieniu.

---

## D. Jakość i wydajność

### D1. Overlay przepala CPU — najlepszy stosunek zysku do pracy w całym projekcie

`overlay.py:1299-1307` ładuje **6–7 fontów TrueType w każdej klatce**:

```python
fnt_tab    = ImageFont.truetype(FONT_SEMI_PATH, int(8.2 * scale))
fnt_text   = ImageFont.truetype(FONT_REG_PATH,  int(8.8 * scale))
...
```

`_render_frame` to 432 linie: pełny redraw PIL w skali 2×, `resize(LANCZOS)`, konwersja BGRA w numpy —
przy ~33 fps, nieprzerwanie podczas nagrywania, czyli równolegle z Whisperem na tym samym procesorze.

- cache fontów w słowniku na poziomie modułu (kilka minut pracy, natychmiastowy efekt),
- cache statycznych warstw (tło, ramka, ikony) i przerysowywanie tylko fali i licznika,
- spadek do ~20 fps, gdy nie ma animacji.

### D2. `require_text_field` praktycznie nic nie blokuje

`focus_detector.py:144-259` — **każda** ścieżka kończy się akceptacją:
`"Przeglądarka – obszar roboczy strony"` (196), `"Aktywne okno robocze"` (256),
`"Domyślna akceptacja okna"` (265). Zabezpieczenie jest w praktyce dekoracyjne,
a użytkownik ma w menu checkbox sugerujący ochronę, której nie ma.

Osobno: synchroniczne `uiautomation.GetFocusedControl()` (`focus_detector.py:172`) siedzi na ścieżce
skrót → start nagrywania. To wywołanie COM potrafi trwać setki ms albo zawisnąć, co opóźnia start
dyktowania. Przenieść do wątku z twardym timeoutem i decyzją domyślną przy jego przekroczeniu.

### D3. Diaryzacja rozdzieli tylko wyraźnie różne głosy

`diarizer.py:183-199`: `dist = sqrt(0.70*(Δpitch/35)² + 0.30*(Δcentroid/600)²)` przy progu `1.25`
wymaga różnicy F0 rzędu **~52 Hz**, żeby uznać kogoś za nowego mówcę. Dwóch mężczyzn o podobnym
tonie zawsze zostanie zlany w jednego „Uczestnika 1". Lista `self.clusters` rośnie bez ograniczenia,
decyzja jest podejmowana online i nie da się jej skorygować po fakcie.

To nie jest poprawka, to osobny projekt — **nie bierz tego razem z resztą.**
Kierunek: embeddingi głosu (`resemblyzer`, ~15 MB, działa offline) albo przynajmniej MFCC + jitter/shimmer
i re-clustering całego spotkania po jego zakończeniu, zamiast klasyfikacji na bieżąco.

### D4. Dług strukturalny

- `app.py` 1805 linii, `overlay.py` 1903 — oba robią po pięć rzeczy. Wydzielić: generatory dźwięków
  (`app.py:17-190`, wykonują się przy imporcie i zapisują 10 plików WAV do temp przy każdym starcie),
  budowanie menu Win32 (`app.py:1230-1450`), menu tray (`app.py:1580-1700`).
- `os._exit(0)` w `exit_app` (`app.py:1452`) ucina flush logów.
- Skrót rejestrowany **dwukrotnie** — Win32 `RegisterHotKey` (`app.py:1140`) i `UniversalGlobalHotKeys`
  (`app.py:1160`). Przed podwójnym wywołaniem chroni wyłącznie debounce 0,35 s (`app.py:941`).
  Działa, ale jest kruche; docelowo jedna ścieżka z fallbackiem wybieranym raz przy starcie.
- Lista modeli fallback dla Gemini zawiera `gemini-3.1-flash-lite` i `gemini-flash-lite-latest`
  (`transcriber.py:364`, `meeting_manager.py:241`). Zweryfikować, czy te nazwy w ogóle istnieją —
  jeśli nie, pętla po nich to czysty narzut i opóźnienie.
- `transcriber.py:396-404` — `except Exception: continue` w pętli po modelach zjada błędy 401/403,
  a odpowiedzi `status_code != 200` nie są nigdzie logowane. Zły klucz objawia się jako
  „korekta po prostu nie działa", bez żadnej diagnostyki. Logować status i treść błędu,
  pokazać użytkownikowi dymek przy błędzie autoryzacji.
- Timeout 4,5 s (`transcriber.py:390`) na korektę całego dyktowania jest za krótki dla dłuższych tekstów.

### D5. Testy

`tests/` jest w `.gitignore` (linia 20), więc publiczne repo nie ma **żadnych** testów.
Pliki w środku to skrypty ad-hoc z `print`, bez pytest i bez CI.
Brak `.gitattributes` przy mieszanych końcach linii — stąd ostrzeżenia CRLF przy każdym `git diff`
i dlatego `git status` potrafi nie pokazać zmiany w `config.json`.

- przenieść sensowne testy do `tests/` **w repo**, przepisać na pytest, zamockować `WhisperModel`,
- dodać `.gitattributes` z `* text=auto eol=crlf`,
- GitHub Actions: `py_compile` wszystkich modułów + testy jednostkowe + **bramka z kroku A3.5**
  (fail, jeśli jakikolwiek `config*.json` w repo lub w buildzie ma niepusty `llm_api_key`).

---

## Kolejność wykonania

**Natychmiast (bezpieczeństwo):**
1. A1–A3 — rotacja klucza (Filip), usunięcie assetów, rozdzielenie sekretu od configu, bezpiecznik w buildzie
2. B1 — warunek przed `inject_text`, żeby tekst nie trafiał do obcego okna
3. B7 — wyłączyć nadpisywanie Notatnika
4. A4 — klucz do nagłówka, audyt logowania

**Dzień drugi (błędy widoczne dla użytkownika):**
5. C1 — `show_balloon` + try/except na callbackach widżetu
6. C2 — offset w finalizacji streamingu
7. D1 — cache fontów
8. C3 — UI lokalnego LLM i warunki `api_key or is_local` (priorytet biznesowy właściciela)

**Dalej:**
9. B3, B4, B5, B6 — ustawienia systemowe, kill procesów, autostart, rotacja logów
10. C5, C6 — resampling i limity kolejek
11. B8, D5 — piny zależności, `.gitattributes`, CI z bramką na sekrety
12. D2, D4 — detekcja pola tekstowego, refaktor
13. D3 — diaryzacja, osobno i na końcu

## Kryteria odbioru

- `find dist/Whiscribe-Portable -name "config.json" -not -path "*/models/*" -exec grep -o '"llm_api_key": "[^"]*"' {} +` → tylko puste wartości
- `git ls-files | grep -x config.json` → brak wyniku
- build przerywa się z błędem, gdy w paczce jest niepusty `llm_api_key`
- `set WHISCRIBE_LLM_API_KEY=...` wystarcza, żeby korekta AI działała lokalnie, a `git status` jest czysty
- klikanie „Włącz korektę AI" nie rzuca wyjątku i pokazuje dymek potwierdzenia
- przy `llm_provider: "ollama"` i pustym kluczu: korekta działa, podsumowanie spotkania powstaje, a kliknięcie przycisku AI nie przestawia providera na `gemini`
- dyktowanie w trybie streamingu nie gubi ostatnich słów, gdy mowa zaczyna się kilka sekund po wciśnięciu skrótu
- uruchomiony Notatnik z niezapisaną treścią nie zostaje nadpisany po rozpoczęciu trybu spotkania
- nieudane przywrócenie fokusu nie powoduje wklejenia tekstu do obcego okna
