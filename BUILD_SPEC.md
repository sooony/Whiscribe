# Specyfikacja wdrożenia wersji wykonywalnej (Portable .EXE) dla Whiscribe

> **HASŁO AKTYWUJĄCE WDROŻENIE DLA ASYSTENTA AI:**
> `robimy z tego egzeka` (lub `robimy egzeka`)

Gdy użytkownik wyda to polecenie, asystent natychmiast przystępuje do budowy wersji binarnej ściśle według poniższych założeń.

---

## 1. Format wydania: Wersja Portable (ZIP / Folder autonomiczny)
- **Typ**: Autonomiczny pakiet portable (nie wymaga uprawnień administratora ani instalatora Windows).
- **Struktura folderu**:
  - `Whiscribe.exe` (główny plik wykonywalny z wbudowaną jednolitą ikoną mikrofonu `icon.ico`).
  - `config.json` (plik konfiguracyjny tworzony/odczytywany lokalnie).
  - `models/` (lokalny cache pobranych wag modeli Whisper).
  - `transkrypcje/` (folder na generowane notatki ze spotkań).
- **Zalety wersji Portable**:
  - Działa od razu po rozpakowaniu na dowolnym komputerze Windows 10/11 (np. z pendrive'a).
  - Brak śmieci w rejestrze systemowym; usunięcie aplikacji to po prostu usunięcie folderu.
  - Opcjonalny autostart z systemem realizowany przez dodanie skrótu do `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`.

---

## 2. Kreator pierwszego uruchomienia i pobieranie modeli (Hardware Profiler)
Podczas pierwszego uruchomienia (gdy w folderze `models/` brak wag) Whiscribe uruchamia lekki graficzny kreator wyboru silnika z automatyczną detekcją sprzętu:

| Kategoria sprzętu | Wykryta konfiguracja | Rekomendowany model Whisper | Rozmiar / Pobieranie | Tryb przetwarzania |
|---|---|---|---|---|
| **Klasa PRO (Mocne GPU)** | Dedykowane NVIDIA RTX (RTX 3060, 4060+ z $\ge$ 6GB VRAM) | **`large-v3-turbo`** | ~1.5 GB | Lokalnie CUDA `float16` (błyskawiczny, bezbłędny) |
| **Klasa Średnia (GPU standard)** | Karty GTX (1660, 1060) lub RTX z mniejszą pamięcią | **`small`** lub **`medium`** | ~500 MB – 1.5 GB | Lokalnie CUDA `float16` / `int8` |
| **Zwykły komputer / Laptop** | Zintegrowana grafika Intel Iris / AMD Radeon, CPU | **`base`** lub **`small.en/pl`** | ~150 – 450 MB | Lokalnie CPU `int8` (zoptymalizowany dla x86_64) |
| **Tryb Chmurowy (Brak mocnego CPU)** | Bardzo słaby laptop biurowy, netbook | **Whisper API / Groq Cloud** | 0 MB (Brak modelu lokalnie) | Online API (zerowe obciążenie komputera) |

Kreator wyświetla czytelne opisy w języku polskim, wskaźnik postępu pobierania z Hugging Face i zapisuje wybrany model w `models/`.

---

## 3. Zunifikowanie ikony (`icon.ico`)
- Oficjalna ikona mikrofonu Whiscribe (`icon.ico`) zostaje zunifikowana we wszystkich miejscach:
  1. Ikona pliku binarnego `Whiscribe.exe` (zasób PE VERSIONINFO i ICON).
  2. Ikona okna paska zadań Windows (`WM_SETICON`).
  3. Ikona animowanego zasobnika systemowego Tray obok zegara.
  4. Ikona skrótów na Pulpicie i w Menu Start.

---

## 4. Narzędzia budowania
- `PyInstaller` z konfiguracją `.spec` dołączającą biblioteki CTranslate2, onnxruntime, sounddevice, PyAudioWPatch oraz zasoby graficzne.
- Skrypt automatyzujący: `build_portable.bat`.
