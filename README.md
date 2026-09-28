# 🎙️ Dyktowanie Mowy AI (Whisper Turbo + Windows 11 Voice Typing)

Lokalna, błyskawiczna wtyczka do zamiany mowy na tekst dla systemu Windows z interfejsem wiernie odwzorowującym **natywne wpisywanie głosowe Windows 11 (Win + H)**. Wykorzystuje lokalny model **Whisper large-v3-turbo** na karcie **NVIDIA RTX 3060**, oferując bezbłędne rozpoznawanie języka polskiego, znaki interpunkcyjne, wielkie litery oraz możliwość bezpośredniego sterowania myszką **Logitech MX Master** lub skrótem klawiszowym.

---

## 🪟 Nowy interfejs Windows 11 Fluent Design

Widżet został w 100% dostosowany do natywnego programu wpisywania głosowego Windows 11:
1. **Pływający widżet Fluent Acrylic:**
   - **Górny uchwyt (Drag Handle):** Płynne przeciąganie widżetu w dowolne miejsce ekranu.
   - **Przycisk ✕ (Zamknij):** Ukrywa widżet lub anuluje bieżące nagranie.
   - **Centralny przycisk Mikrofonu:**
     - W spoczynku: Czysty biały przycisk z ikoną mikrofonu Windows 11.
     - W trakcie nagrywania: Podświetlenie w kolorze akcentu Windows 11 (błękit `#0067c0`) oraz animowane, reaktywne fale głosu pulsujące w rytm Twojej mowy.
     - Kliknięcie mikrofonu włącza lub zatrzymuje wpisywanie głosowe.
   - **Koło zębate ⚙ (Ustawienia):** Otwiera natywne menu ustawień (pisanie na żywo, czujnik pola tekstowego, dźwięki, pauzy ciszy, motyw jasny/ciemny).
   - **Przycisk Pomoc (?):** Wyświetla dymek z instrukcją obsługi i skrótami.
2. **Dymek ostrzegawczy braku pola tekstowego:**
   - Jeśli spróbujesz rozpocząć dyktowanie, gdy żadne pole tekstowe nie jest zaznaczone (np. kliknięto pulpit lub tło strony), pojawia się dymek:
     `❌ Aby używać wpisywania głosowego, zaznacz pole tekstowe i spróbuj ponownie.`
     z przyciskiem **Rozumiem** do natychmiastowego zamknięcia.
3. **Niekradnące fokusu okno (`WS_EX_NOACTIVATE`, `MA_NOACTIVATE`):**
   - Kliknięcie mikrofonu na widżecie nie odbiera fokusu z aktywnego edytora (Notatnik, przeglądarka, Word, Discord itp.).

---

## 🚀 Jak to działa?

1. Ustawiasz kursor w dowolnym polu tekstowym (np. czat w **Antigravity**, przeglądarka, notatnik, Word, Discord).
2. Naciskasz przycisk na myszce MX Master (lub skrót `Ctrl + Alt + D`, ewentualnie klikasz mikrofon na widżecie).
3. Słyszysz przyjemny rosnący dźwięk gotowości Windows 11, a mikrofon podświetla się na niebiesko z animacją fali głosu.
4. Mówisz swobodnie po polsku.
5. Naciskasz przycisk ponownie lub robisz krótką pauzę (domyślnie 4.5s ciszy automatycznie zatwierdza tekst).
6. W ułamku sekundy (~0.3 s) model **Whisper large-v3-turbo** na Twojej karcie **NVIDIA RTX 3060** przepisuje mowę i natychmiast wkleja poprawny tekst w miejsce kursora!

---

## 🖱️ Konfiguracja myszki Logitech MX Master (Logi Options+)

Aplikacja **Logi Options+** działa na Twoim komputerze w tle. Aby przypisać dyktowanie do przycisku myszki:

1. Otwórz program **Logi Options+**.
2. Kliknij na swoją myszkę **MX Master**.
3. Wybierz przycisk, którym chcesz sterować dyktowaniem – świetnie sprawdza się:
   - **Przycisk pod kciukiem (przycisk gestów / Gesture Button)**, lub
   - **Przycisk zmiany trybu kółka (za głównym scrollem)**.
4. W menu akcji po prawej stronie wybierz: **Przypisanie naciśnięcia klawisza** (Keystroke assignment).
5. Wpisz kombinację: `Ctrl + Alt + D`.
6. Gotowe! Jedno kliknięcie przycisku myszy włącza i wyłącza dyktowanie.

---

## 📁 Uruchamianie

- **`run.bat`** – Uruchamia aplikację z oknem konsoli (wygodne do testów, widzisz logi w czasie rzeczywistym).
- **`run_silent.vbs`** – Uruchamia aplikację całkowicie w tle bez żadnych okien terminala. W zasobniku systemowym pojawi się ikonka mikrofonu.

---

## ⚙️ Opcje w `config.json`

```json
{
  "hotkey": "<ctrl>+<alt>+d",
  "mode": "toggle",
  "model_size": "turbo",
  "device": "cuda",
  "compute_type": "float16",
  "language": "pl",
  "sound_feedback": true,
  "show_overlay": true,
  "require_text_field": true,
  "stream_realtime": false,
  "auto_stop_silence_seconds": 4.5,
  "theme": "light",
  "restore_clipboard": false,
  "use_llm": false,
  "llm_provider": "gemini",
  "llm_api_key": "",
  "llm_model": "gemini-2.0-flash"
}
```
