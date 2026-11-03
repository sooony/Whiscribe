# Whiscribe - natywne wpisywanie głosowe dla Windows

Whiscribe to zaawansowana aplikacja desktopowa do dyktowania i wpisywania głosowego w systemie Windows. Wykorzystuje lokalny model Faster-Whisper large-v3-turbo akcelerowany sprzętowo przez NVIDIA CUDA (oraz zoptymalizowany pod kątem procesorów CPU), zapewniając jakość rozpoznawania mowy na poziomie rozwiązań komercyjnych przy zerowym opóźnieniu i pełnej prywatności.

Aplikacja integruje się bezpośrednio z aktywnym polem tekstowym w systemie Windows: edytorami tekstu (Word, Notatnik), arkuszami kalkulacyjnymi, przeglądarkami internetowymi (Chrome, Edge, Firefox), komunikatorami (Slack, Discord, Teams) oraz środowiskami programistycznymi (VS Code, Cursor, Visual Studio).

---

## Kluczowe możliwości

### 1. Nowoczesny widżet interfejsu (Windows 11)
- **Minimalizacja do paska zadań Windows 11:** Widżet posiada dedykowany przycisk minimalizacji oraz natywny przycisk na dolnym pasku zadań (`WS_EX_APPWINDOW`, `WS_MINIMIZEBOX`). Kliknięcie przycisku minimalizuje aplikację do paska zadań, a ponowne kliknięcie na pasku lub w zasobniku systemowym natychmiast przywraca widżet na ekran.
- **Zawsze na wierzchu (Always on Top):** W trybie domyślnym widżet unosi się ponad oknami systemu dzięki mechanizmowi pętli kontroli kolejności okien. Nie znika pod aktywnymi aplikacjami roboczymi.
- **Brak kradzieży fokusu:** Kliknięcie w dowolny element interfejsu (przycisk mikrofonu, ustawienia) nie odbiera fokusu z edytora tekstu, w którym aktualnie znajduje się kursor.
- **Swobodne przemieszczanie:** Możliwość płynnego przeciągania widżetu w dowolne miejsce ekranu oraz między wieloma monitorami.

### 2. Dwa tryby wpisywania (streaming włączony lub wyłączony)
Na belce widżetu znajduje się dedykowany przełącznik trybu wprowadzania tekstu:
- **Streaming włączony (pisanie na żywo):** Tekst pojawia się w polu edycyjnym w czasie rzeczywistym, słowo po słowie, bezpośrednio w trakcie wypowiedzi. Algorytm dopasowywania sekwencji eliminuje powtórzenia wyrazów.

  Pisanie na żywo i korekta AI wykluczają się: włączenie jednego wyłącza drugie. Tekstu, który już wszedł do cudzego okna, nie da się później poprawić, więc albo słowa lecą na bieżąco bez korekty, albo wchodzą raz, poprawione, po zakończeniu. Wcześniej dawało się zaznaczyć oba naraz i wtedy pisanie na żywo po cichu nic nie robiło.
- **Streaming wyłączony (zatwierdzanie blokowe):** Wypowiadane jest pełne zdanie lub akapit. Po zwolnieniu skrótu, kliknięciu mikrofonu lub automatycznym wykryciu pauzy ciszy, zoptymalizowany tekst z pełną interpunkcją i wielkimi literami pojawia się w miejscu kursora.

### 3. Wielowarstwowy filtr eliminacji zniekształceń i halucynacji
Whiscribe zawiera moduł filtrujący zniekształcenia charakterystyczne dla modeli Whisper (wtrącenia ze zwiastunów wideo, napisy końcowe z nagrań internetowych), jednocześnie precyzyjnie przepuszczając naturalne polskie powitania, pożegnania i zwroty grzecznościowe (np. "dzień dobry", "cześć", "do widzenia", "dzięki za informację").

### 4. Detektor aktywnego pola tekstowego
Moduł inspekcji interfejsu weryfikuje obecność kursora w edytowalnym elemencie systemu Windows:
- Zapobiega przypadkowemu wklejaniu tekstu na pulpit, do menu kontekstowego lub na paski narzędziowe.
- Wyświetla czytelny komunikat w przypadku próby dyktowania bez aktywnego pola tekstowego.

### 5. Globalne skróty klawiszowe w systemie Windows
Rejestracja skrótów na poziomie systemu operacyjnego pozwala na natychmiastowe rozpoczęcie dyktowania z dowolnego miejsca w systemie:
- Domyślny skrót dyktowania: `Ctrl + Alt + D`.
- Domyślny skrót trybu spotkania: `Ctrl + Alt + M`.
- Domyślny skrót przywracania ostatniej wklejki: `Ctrl + Alt + V` (patrz "Pamięć wklejek" niżej).
- Główny przycisk widżetu działa według trybu wybranego w menu `···`: "Dyktowanie do tekstu" (ikona mikrofonu) albo "Transkrypcja rozmowy" (ikona ludzików).
- Przyciski "Stream" i "Korekta" pod nagłówkiem włączają pisanie na żywo i korektę AI (włączony ma czerwoną diodę i obwódkę). Płynna fala po bokach głównego przycisku pokazuje głośność mowy i pojawia się tylko wtedy, gdy mówisz. Przy przetwarzaniu w przycisku pulsują trzy kropki.
- Pełna możliwość modyfikacji kombinacji klawiszy w pliku konfiguracyjnym.

### 6. Pamięć wklejek (odzyskiwanie ostatnio podyktowanego tekstu)
Po wklejeniu tekstu schowek systemowy jest przywracany do poprzedniego stanu albo czyszczony, żeby dyktowana treść nie zostawała w schowku ani w historii `Win + V`. Dlatego aplikacja trzyma ostatnio podyktowany tekst we własnej pamięci, niezależnej od schowka:
- `Ctrl + Alt + V` wkleja zapamiętany tekst do okna aktywnego w tej chwili (bez zatwierdzania Enterem).
- Wpis powstaje w momencie, w którym tekst powstał, a nie po udanym wklejeniu. Dzięki temu da się odzyskać także tekst, który nigdy nie wszedł: po utracie fokusu okna, po spóźnionym wyniku transkrypcji i po przerwanym przetwarzaniu.
- Gdy jest co przywracać, w linii statusu widżetu pojawia się klikalna pigułka "Przywróć". Bursztynowa oznacza tekst, który nie został wklejony.
- Ta sama pozycja jest w menu `···` widżetu oraz w menu ikony w zasobniku, razem z "Wyczyść pamięć wklejek".
- Przywracanie zawsze sprawdza, czy pod kursorem jest pole tekstowe, niezależnie od opcji `require_text_field`. Bez tego `Ctrl + V` nad Eksploratorem plików wklejałby pliki.
- Pamięć żyje tylko w pamięci procesu i nie jest zapisywana na dysk. Domyślnie trzyma jeden wpis; `paste_memory_size` w konfiguracji pozwala trzymać 2-3, jeśli potrzebny bywa przedostatni tekst.
- Transkrypcje spotkań nie trafiają do pamięci wklejek, bo mają własny plik w katalogu `transkrypcje`.

### 7. Architektura systemu: praca offline oraz moduł korekty językowej

Whiscribe został zbudowany z naciskiem na prywatność danych użytkownika. Model rozpoznawania mowy działa całkowicie lokalnie.

#### Tryb 1: Domyślny - praca całkowicie offline (tylko lokalny model Whisper)
Domyślnie w pliku konfiguracyjnym parametr `use_llm` ma wartość `false`. Aplikacja nie łączy się z internetem i nie przesyła żadnych danych audio ani tekstu poza komputer użytkownika. Całość obliczeń realizowana jest lokalnie przez kartę graficzną lub procesor.

```mermaid
flowchart LR
    A["Głos użytkownika"] --> B["Lokalny model Whisper GPU<br/>(wersja turbo lub large)"]
    B -->|"Rozpoznany tekst w czasie rzeczywistym"| C["Aktywne pole tekstowe<br/>(Word, Notatnik, przeglądarka)"]
```

#### Tryb 2: Praca offline z lokalnym modelem językowym (Ollama lub LM Studio)
W przypadku posiadania lokalnie uruchomionego serwera modeli językowych (np. Ollama na porcie 11434 lub LM Studio na porcie 1234), możliwa jest automatyczna korekta tekstu bez łączenia się z internetem.

```mermaid
flowchart LR
    A["Głos użytkownika"] --> B["Lokalny model Whisper GPU"]
    B -->|"Surowy tekst"| C["Lokalny model językowy<br/>(Ollama / LM Studio na localhost)"]
    C -->|"Korekta interpunkcji i usunięcie zająknięć"| D["Aktywne pole tekstowe"]
```

Przykład konfiguracji w `config.json` dla narzędzia Ollama:
```json
"use_llm": true,
"llm_provider": "ollama",
"llm_endpoint": "http://localhost:11434/v1",
"llm_model": "llama3.2",
"llm_api_key": ""
```

#### Tryb 3: Opcjonalna korekta chmurowa (Google Gemini, Groq, OpenAI)
Dla użytkowników preferujących zewnętrzną korektę stylistyczną istnieje możliwość podpięcia zewnętrznego interfejsu programistycznego:

```mermaid
flowchart LR
    A["Głos użytkownika"] --> B["Lokalny model Whisper GPU"]
    B -->|"Surowy tekst transkrypcji"| C["Zewnętrzny model językowy<br/>(Gemini, Groq lub OpenAI)"]
    C -->|"Poprawiony tekst docelowy"| D["Aktywne pole tekstowe"]
```

#### Rola i budowa promptu systemowego (llm_system_prompt)
Domyślna treść instrukcji dla modułu korekty:
```text
Jesteś polskim korektorem tekstu dyktowanego. Popraw zająknięcia (np. yyy, eee), błędy interpunkcyjne i formatowanie. Nie zmieniaj sensu wypowiedzi. Zwróć WYŁĄCZNIE poprawiony tekst, bez żadnych dodatkowych komentarzy ani cudzysłowów.
```
- Usunięcie zająknięć: eliminuje dźwięki namysłu i mimowolne powtórzenia wyrazów.
- Zachowanie sensu wypowiedzi: zapobiega dodawaniu własnych wniosków przez model.
- Format odpowiedzi: nakaz zwrotu wyłącznie czystego tekstu zapobiega dołączaniu komentarzy wstępnych. Treść można dostosować w pliku konfiguracyjnym pod kątem specyfiki redagowanych pism.

---

## Plany rozwoju: transkrypcja spotkań zespołowych i rozpoznawanie osób

Aplikacja jest rozwijana w kierunku rejestracji i protokołowania spotkań zespołowych (Microsoft Teams, Google Meet, Zoom):

1. **Równoległy nasłuch dwukanałowy:**
   - Rejestracja głosu użytkownika bezpośrednio z mikrofonu fizycznego.
   - Równoległa rejestracja głosu pozostałych rozmówców z wyjścia karty dźwiękowej za pośrednictwem pętli zwrotnej systemu Windows.
2. **Rozpoznawanie uczestników na podstawie cech głosu:**
   - Wykorzystanie analizy barwy głosu, częstotliwości podstawowej oraz parametrów widmowych dźwięku.
   - Automatyczne przypisywanie poszczególnych wypowiedzi do właściwych osób w zespole.
3. **Automatyczne protokoły i podsumowania:**
   - Zapis transkrypcji z podziałem na role do formatu tekstowego oraz Markdown.
   - Generowanie podsumowań ustaleń i listy zadań po zakończeniu spotkania.

---

## Uruchomienie aplikacji

### Wariant A: Wersja przenośna (wersja bez instalacji środowiska Python)
1. Pobierz archiwum `Whiscribe-Portable.zip` z sekcji wydań na GitHubie.
2. Rozpakuj archiwum do wybranego katalogu na dysku.
3. Uruchom plik `Whiscribe.exe`.
4. Przy pierwszym uruchomieniu nastąpi automatyczna weryfikacja konfiguracji sprzętowej i pobranie wybranego modelu mowy.

### Wariant B: Uruchomienie z kodu źródłowego
Wymagania: Python 3.10 lub nowszy, opcjonalnie karta graficzna NVIDIA z obsługą biblioteki CUDA.

```bash
# 1. Klonowanie repozytorium
git clone https://github.com/sooony/Whiscribe.git
cd Whiscribe

# 2. Utworzenie i aktywacja środowiska wirtualnego
python -m venv venv
venv\Scripts\activate

# 3. Instalacja zależności
pip install -r requirements.txt

# 4. Uruchomienie aplikacji
python app.py
```

---

## Konfiguracja (config.json)

Plik konfiguracyjny `config.json` tworzony jest automatycznie przy pierwszym uruchomieniu:

```json
{
  "hotkey": "<ctrl>+<alt>+d",
  "hotkey_meeting": "<ctrl>+<alt>+m",
  "hotkey_restore_paste": "<ctrl>+<alt>+v",
  "mode": "toggle",
  "model_size": "turbo",
  "device": "cuda",
  "compute_type": "float16",
  "language": "pl",
  "always_on_top": true,
  "stream_realtime": false,
  "require_text_field": true,
  "sound_feedback": true,
  "auto_stop_silence_seconds": 4.5,
  "theme": "dark",
  "paste_memory_size": 1,
  "max_paste_delay_seconds": 8.0,
  "gemini_hedge_after_seconds": 1.0,
  "log_level": "normal",
  "use_llm": false,
  "llm_provider": "gemini",
  "llm_api_key": "",
  "llm_model": "gemini-flash-lite-latest",
  "llm_system_prompt": "Jesteś polskim korektorem tekstu dyktowanego. Popraw zająknięcia (np. yyy, eee), błędy interpunkcyjne i formatowanie. Nie zmieniaj sensu wypowiedzi. Zwróć WYŁĄCZNIE poprawiony tekst, bez żadnych dodatkowych komentarzy ani cudzysłowów."
}
```

### Wybrane parametry:
- `always_on_top`: utrzymuje widżet na wierzchu ekranu.
- `stream_realtime`: przełącza pisanie w czasie rzeczywistym w trakcie mówienia. Wyklucza się z `use_llm`: jeśli w configu oba są ustawione na `true`, aplikacja przy starcie zostawia korektę i wyłącza pisanie na żywo.
- `require_text_field`: weryfikuje obecność aktywnego pola tekstowego przed rozpoczęciem wpisywania.
- `auto_stop_silence_seconds`: czas ciszy w sekundach, po którym nagranie zostaje automatycznie zakończone i przetworzone.
- `use_llm`: aktywuje opcjonalną korektę stylistyczną i interpunkcyjną.
- `paste_memory_size`: liczba ostatnich dyktowań trzymanych w pamięci wklejek (domyślnie 1).
- `max_paste_delay_seconds`: po ilu sekundach od zatrzymania nagrania wynik przestaje być wklejany automatycznie (domyślnie 8). Korekta AI potrafi trwać kilkanaście sekund, gdy modele są przeciążone, a tekst wklejony po takim czasie wpada w środek tego, co właśnie piszesz. Taki spóźniony tekst trafia do pamięci wklejek i czeka na `Ctrl+Alt+V`. Limit rośnie z długością nagrania (35 procent czasu mowy), bo na dłuższe dyktowanie czeka się świadomie, i jest 2,5 raza hojniejszy, gdy korekta AI się udała: tekst poprawiony po dziesięciu sekundach jest tego wart, a surowy po piętnastu, bo modele padły, już nie. `0` wyłącza kontrolę i przywraca wklejanie zawsze.
- `gemini_hedge_after_seconds`: po ilu sekundach milczenia pierwszego modelu Gemini pytane są równolegle pozostałe (domyślnie 1). Z pomiarów na żywej aplikacji pierwszy pytany model regularnie milczy dłużej, a wynik daje model dosłany, więc dłuższe czekanie było czystym kosztem: jedno dyktowanie skróciło się z 3,0 do około 1,5 sekundy. Krótszy próg oznacza częściej trzy zapytania zamiast jednego, więc przy ciasnych limitach API warto go podnieść.
- `hotkey_restore_paste`: skrót przywracania ostatniej wklejki (domyślnie `<ctrl>+<alt>+v`).
- `log_level`: `normal` (domyślnie) albo `diag`. Tryb `diag` zapisuje do logu także treść dyktowania, więc włącza się go tylko na czas diagnozy.

### Logi
Logi nie leżą w katalogu aplikacji, bo budowanie wersji przenośnej czyści katalog `dist` razem z nimi. Trafiają do `%LOCALAPPDATA%\Whiscribe\logs`:
- `whiscribe.log` (wersja przenośna) albo `whiscribe-dev.log` (uruchomienie z kodu źródłowego): przebieg pracy aplikacji.
- `whiscribe-errors.log`: tylko ostrzeżenia i błędy, ze śladami wyjątków. Ten plik otwiera się pierwszy po awarii.
- Katalog można otworzyć pozycją "Otwórz folder z logami" w menu widżetu albo w menu ikony w zasobniku, a zmienić zmienną środowiskową `WHISCRIBE_LOG_DIR`.
- Logi bibliotek (model Whisper, zapytania HTTP) są wyciszone do poziomu ostrzeżeń: wcześniej stanowiły prawie 70 procent pliku i wypychały z niego własne komunikaty aplikacji.
- Domyślnie do logu nie trafia ani jedno słowo dyktowania ani transkrypcji spotkania, ani tytuły okien. Treść zapisuje tylko tryb `diag`, włączany świadomie przez `log_level` albo zmienną `WHISCRIBE_LOG_LEVEL=diag`.

---

## Bezpieczeństwo i prywatność danych

- **Brak telemetrii:** Aplikacja nie gromadzi i nie wysyła żadnych danych telemetrycznych ani informacji diagnostycznych.
- **Lokalne przetwarzanie głosu:** Sygnał audio z mikrofonu jest przetwarzany bezpośrednio w pamięci RAM i na lokalnej karcie graficznej. Dźwięk nie opuszcza komputera użytkownika.
- **Bezpieczeństwo kluczy:** Klucze dostępu do opcjonalnych usług zewnętrznych są zapisywane wyłącznie w lokalnym pliku konfiguracyjnym.
- **Czysty schowek:** Po wklejeniu tekstu schowek jest przywracany do poprzedniego stanu albo czyszczony. Tekst i znaczniki wykluczenia z historii schowka Windows (`Win + V`) wchodzą do schowka w jednej operacji, więc menedżer historii nigdy nie widzi wpisu bez znaczników. Jeśli schowek odmówi (zajęty przez inny program), tekst wchodzi awaryjną ścieżką bez wykluczenia i trafia do `Win + V`, a w logu jest wtedy wpis na poziomie DEBUG. Ostatnio podyktowany tekst zostaje wyłącznie w pamięci procesu aplikacji (pamięć wklejek) i nie jest zapisywany na dysk.
- **Logi bez treści:** Logi domyślnie nie zawierają dyktowanej treści, transkrypcji spotkań ani tytułów okien. Zapisuje je tylko świadomie włączony tryb diagnostyczny (`log_level: diag`).

---

## Licencja

Projekt udostępniony na licencji [MIT](LICENSE).
