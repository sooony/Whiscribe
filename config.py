import json
import os
import sys

def get_app_dir() -> str:
    """Zwraca katalog główny aplikacji (dla środowiska deweloperskiego oraz spakowanej wersji Portable .EXE)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

APP_NAME = "Whiscribe"
APP_VERSION = "2.1.0"
__version__ = APP_VERSION

CONFIG_FILE = os.path.join(get_app_dir(), "config.json")

DEFAULT_CONFIG = {
    "hotkey": "<ctrl>+<alt>+d",
    "hotkey_description": "Skrót klawiszowy aktywujący dyktowanie (możesz przypisać ten sam skrót do przycisku myszki MX Master w Logi Options+)",
    "mode": "toggle",  # "toggle" lub "push_to_talk"
    "model_size": "turbo",  # "turbo" (large-v3-turbo), "large-v3", "medium", "small", "base"
    "device": "cuda",  # "cuda" lub "cpu"
    "compute_type": "float16",  # "float16" dla GPU, "int8" dla CPU
    "language": "pl",
    "sound_feedback": True,
    "sound_start_preset": 1,  # 1: Nowoczesny dzwonek, 2: Soft Pop, 3: Harmonia, 4: Cyber Minimal, 0: Brak
    "sound_stop_preset": 1,   # 1: Łagodny spadek, 2: Soft Pop, 3: Harmonia, 4: Cyber Minimal, 0: Brak
    "show_overlay": True,
    "require_text_field": True,  # Wymaga aktywnego pola tekstowego przed rozpoczęciem dyktowania (zapobiega chodzeniu po ikonkach)
    "stream_realtime": False,  # Domyślnie False (czyste wklejanie końcowego tekstu bez pożerania liter i cofania kursora)
    "auto_stop_silence_seconds": 4.5,  # Automatyczne zatrzymanie po ciszy (domyślnie 4.5s)
    "theme": "light",  # Styl widżetu: light, dark, glass_light, glass_dark, glass_color
    "restore_clipboard": False,
    "hotkey_meeting": "<ctrl>+<alt>+m",
    "hotkey_meeting_description": "Skrót klawiszowy uruchamiający transkrypcję spotkań z podziałem na mówców do Notatnika",
    "open_notepad_on_meeting": False,
    "meetings_folder": "transkrypcje",
    "diarization_enabled": True,
    "meeting_summary_llm": True,
    "use_llm": False,
    "llm_provider": "gemini",
    "llm_api_key": "",
    "llm_model": "gemini-2.0-flash",
    "llm_system_prompt": "Jesteś polskim korektorem tekstu dyktowanego. Popraw zająknięcia (np. yyy, eee), błędy interpunkcyjne i formatowanie. Nie zmieniaj sensu wypowiedzi. Zwróć WYŁĄCZNIE poprawiony tekst, bez żadnych dodatkowych komentarzy ani cudzysłowów."
}

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(user_cfg)
                return config
        except Exception as e:
            print(f"Błąd odczytu {CONFIG_FILE}: {e}. Używam domyślnej konfiguracji.")
            return DEFAULT_CONFIG.copy()
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

def save_config(config: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Błąd zapisu {CONFIG_FILE}: {e}")
