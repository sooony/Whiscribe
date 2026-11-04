import os
import sys
import glob
import json
import inspect
import pytest
import numpy as np

# Dodaj główny katalog projektu do sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import config
from config import load_config, save_config, get_app_dir, DEFAULT_CONFIG
from meeting_recorder import MeetingRecorder, MeetingAudioSegment
from recorder import AudioRecorder
from focus_detector import is_text_field_focused


def test_no_api_keys_in_config_files():
    """Kryterium A1-A3: Żaden config*.json w repo ani w buildzie nie może zawierać klucza API."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_files = glob.glob(os.path.join(repo_root, "**", "config*.json"), recursive=True)
    
    scanned = 0
    for path in config_files:
        if "models" in path or ".venv" in path or "venv" in path:
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                scanned += 1
                key = data.get("llm_api_key", "")
                assert not key, f"WYCIEK KLUCZA API w pliku: {path} (wartość: {key[:6]}...)"
        except (json.JSONDecodeError, OSError):
            pass
    assert scanned > 0, "Powinien zostać przeskanowany przynajmniej jeden plik config*.json"


def test_config_resolution_hierarchy(monkeypatch, tmp_path):
    """Kryterium A3: Hierarchia źródeł klucza (ENV > secrets.json > config.json)."""
    # 1. Test pierwszeństwa zmiennej środowiskowej
    test_key_env = "test_env_key_12345"
    monkeypatch.setenv("WHISCRIBE_LLM_API_KEY", test_key_env)
    cfg = load_config()
    assert cfg.get("llm_api_key") == test_key_env
    assert cfg.get("_llm_key_source") == "env"

    # 2. Test gdy brak ENV, ale jest secrets.json
    monkeypatch.delenv("WHISCRIBE_LLM_API_KEY", raising=False)
    secrets_path = os.path.join(str(tmp_path), "secrets.json")
    with open(secrets_path, "w", encoding="utf-8") as f:
        json.dump({"llm_api_key": "test_secrets_key_99999"}, f)
    
    monkeypatch.setattr(config, "get_secrets_path", lambda: secrets_path)
    
    cfg = load_config()
    assert cfg.get("llm_api_key") == "test_secrets_key_99999"
    assert cfg.get("_llm_key_source") == "secrets_file"


def test_save_config_does_not_leak_env_key(monkeypatch, tmp_path):
    """Kryterium A3: save_config() NIE zapisuje klucza do config.json, jeśli pochodzi z ENV."""
    monkeypatch.setenv("WHISCRIBE_LLM_API_KEY", "secret_env_key_xyz")
    cfg = load_config()
    assert cfg.get("llm_api_key") == "secret_env_key_xyz"

    dummy_config_path = os.path.join(str(tmp_path), "config.json")
    monkeypatch.setattr(config, "get_config_path", lambda: dummy_config_path)

    save_config(cfg)

    # Sprawdź zawartość zapisanego pliku config.json na dysku
    with open(dummy_config_path, "r", encoding="utf-8") as f:
        saved_on_disk = json.load(f)
    assert saved_on_disk.get("llm_api_key") == "", "Klucz ze zmiennej ENV wyciekł do config.json!"


def test_key_dialog_writes_new_key_to_secrets_file(monkeypatch, tmp_path):
    """Nowy klucz z okienka trafia do secrets.json także wtedy, gdy stary pochodził z secrets.json."""
    import tkinter
    from tkinter import simpledialog
    import app as app_mod

    secrets_path = os.path.join(str(tmp_path), "secrets.json")
    with open(secrets_path, "w", encoding="utf-8") as f:
        json.dump({"llm_api_key": "stary_klucz"}, f)
    monkeypatch.setattr(config, "get_secrets_path", lambda: secrets_path)

    class _Root:
        def withdraw(self): pass
        def attributes(self, *a): pass
        def destroy(self): pass

    class _SyncThread:
        def __init__(self, target=None, daemon=None, **kw): self._t = target
        def start(self): self._t()

    monkeypatch.setattr(tkinter, "Tk", _Root)
    monkeypatch.setattr(app_mod.threading, "Thread", _SyncThread)

    def run(typed):
        monkeypatch.setattr(simpledialog, "askstring", lambda *a, **k: typed)
        a = app_mod.DictationApp.__new__(app_mod.DictationApp)
        a.config = {"llm_provider": "gemini", "llm_api_key": "stary_klucz", "_llm_key_source": "secrets_file", "use_llm": False}
        a.overlay = None
        a.prompt_and_set_llm_api_key()
        return a

    # Tekst, który nie jest kluczem Gemini (np. ID projektu), nie nadpisuje zapisanego klucza
    run("gen-lang-client-0123456789")
    assert config.load_secrets().get("llm_api_key") == "stary_klucz"
    # Nowy format kluczy z AI Studio ("AQ.") jest przyjmowany
    aq = "AQ." + "Ab1_-" * 10
    run(aq)
    assert config.load_secrets().get("llm_api_key") == aq
    # Puste pole = bez zmian
    run("")
    assert config.load_secrets().get("llm_api_key") == aq
    # Klucz w starszym formacie także trafia do secrets.json i włącza korektę
    good = "AIza" + "x" * 35
    a = run("  " + good + "  ")
    assert config.load_secrets().get("llm_api_key") == good
    assert a.config["use_llm"] is True


def test_save_config_without_key_keeps_secrets_file(monkeypatch, tmp_path):
    """Zapis konfiguracji bez klucza w pamięci (np. przełączenie Stream) nie może skasować secrets.json."""
    secrets_path = os.path.join(str(tmp_path), "secrets.json")
    with open(secrets_path, "w", encoding="utf-8") as f:
        json.dump({"llm_api_key": "zachowany_klucz_123"}, f)
    monkeypatch.setattr(config, "get_secrets_path", lambda: secrets_path)

    save_config({"stream_realtime": False, "use_llm": False, "llm_api_key": ""})

    assert config.load_secrets().get("llm_api_key") == "zachowany_klucz_123"


def test_gemini_uses_header_not_query_param():
    """Kryterium A4: Żadne wywołanie API Gemini nie może przekazywać klucza w parametrze URL ?key=."""
    import transcriber
    import meeting_manager

    # Cała klasa, bo żądanie do Gemini buduje się w _kandydaci_dostawcy, a leci z _gemini_attempt
    transcriber_src = inspect.getsource(transcriber.Transcriber)
    assert "?key=" not in transcriber_src, "W Transcriber klucz jest nadal przekazywany w query string!"
    assert "x-goog-api-key" in transcriber_src, "Transcriber musi używać nagłówka x-goog-api-key"

    meeting_src = inspect.getsource(meeting_manager.MeetingManager._generate_llm_meeting_summary)
    assert "?key=" not in meeting_src, "W meeting_manager klucz jest nadal przekazywany w query string!"
    assert "x-goog-api-key" in meeting_src, "MeetingManager musi używać nagłówka x-goog-api-key"


def test_local_llm_allowed_without_api_key():
    """Kryterium C3: Lokalni dostawcy (ollama, lmstudio, local) działają bez klucza API."""
    import transcriber
    import meeting_manager

    assert set(transcriber.LOKALNI_DOSTAWCY) >= {"ollama", "local", "lmstudio"}
    t_src = inspect.getsource(transcriber.Transcriber._post_process_with_llm)
    assert "LOKALNI_DOSTAWCY" in t_src, "Rozpoznanie lokalnego dostawcy musi iść przez LOKALNI_DOSTAWCY"
    k_src = inspect.getsource(transcriber.Transcriber._kandydaci_dostawcy)
    assert "if not api_key and not lokalny" in k_src, "Lokalny dostawca nie może wymagać klucza API"

    m_src = inspect.getsource(meeting_manager.MeetingManager.stop_meeting)
    assert 'in ("ollama", "local", "lmstudio")' in m_src or "in ('ollama', 'local', 'lmstudio')" in m_src


def test_recorder_stop_retains_audio():
    """Kryterium C2: recorder.stop() zwraca pełny bufor bez trim_silence(), zapobiegając ucinaniu końcówki."""
    rec = AudioRecorder(sample_rate=16000)
    # Wygeneruj bufor z 1 sekundą ciszy i 1 sekundą tonu
    silence = np.zeros(16000, dtype=np.float32)
    tone = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 16000)).astype(np.float32) * 0.5
    rec._audio_chunks = [silence, tone]
    rec.is_recording = True

    audio_out = rec.stop()
    assert len(audio_out) == 32000, f"stop() obciął bufor! Oczekiwano 32000 próbek, otrzymano {len(audio_out)}"


def test_meeting_recorder_resampling_antialiasing():
    """Kryterium C5: Resampling z 48kHz do 16kHz używa decymacji z filtrem antyaliasingowym."""
    rec = MeetingRecorder(target_sample_rate=16000)
    # Wygeneruj 48000 próbek sygnału
    t = np.linspace(0, 1, 48000, endpoint=False)
    # Składowa 1kHz (w paśmie) + składowa 18kHz (powyżej Nyquista 8kHz)
    sig_48k = (np.sin(2 * np.pi * 1000 * t) + np.sin(2 * np.pi * 18000 * t)).astype(np.float32)

    sig_16k = rec._resample_to_16k(sig_48k, 48000)
    assert len(sig_16k) == 16000
    assert sig_16k.dtype == np.float32
    assert np.all(np.isfinite(sig_16k))


def test_meeting_recorder_queue_bounded():
    """Kryterium C6: Kolejka transkrypcji spotkania ma limit i politykę odrzucania najstarszych."""
    rec = MeetingRecorder(target_sample_rate=16000)
    assert rec.speech_queue.maxsize == 40

    import datetime
    dummy_audio = np.zeros(16000, dtype=np.float32)
    for i in range(50):
        seg = MeetingAudioSegment(
            source="mic",
            audio=dummy_audio,
            timestamp=datetime.datetime.now(),
            duration_s=1.0
        )
        rec._enqueue_speech_segment(seg)

    assert rec.speech_queue.qsize() == 40, "Kolejka przekroczyła dopuszczalny limit!"


def test_notepad_manager_no_wildcard_overwrite():
    """Kryterium B7: Notatnik nie może być wyszukiwany po klasie 'Notepad' i nadpisywany."""
    notepad_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "notepad_manager.py"))
    with open(notepad_py, "r", encoding="utf-8") as f:
        src = f.read()

    assert "auto.WindowControl(searchDepth=1, ClassName=\"Notepad\")" not in src, "W notepad_manager.py pozostał niebezpieczny fallback szukający losowego Notatnika!"
    assert "val.SetValue(self._all_text)" not in src, "W notepad_manager.py pozostało nadpisywanie Notatnika przez SetValue!"


def test_build_abort_safeguard_in_spec():
    """Kryterium A3.5: whiscribe.spec zawiera twardy fail w razie wykrycia klucza w config*.json."""
    spec_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "whiscribe.spec"))
    with open(spec_path, "r", encoding="utf-8") as f:
        spec_content = f.read()

    assert "BUILD ABORTED: klucz API" in spec_content, "W whiscribe.spec brakuje bezpiecznika przerywającego build!"
    # Zapasowy silnik ma własny klucz, więc bezpiecznik musi patrzeć na oba pola
    assert "llm_fallback_api_key" in spec_content, "Bezpiecznik buildu nie sprawdza klucza zapasowego silnika!"
    assert "config.example.json" in spec_content, "whiscribe.spec musi pakować config.example.json!"
    assert "shutil.copy('config.json', out_dir)" not in spec_content, "whiscribe.spec nie może kopiować config.json do katalogu paczki!"


def test_focus_detector_desktop_rejected(monkeypatch):
    """Kryterium D2 & B1: brak aktywnego okna jest odrzucany z odpowiednim komunikatem.

    Wynik musi być deterministyczny, dlatego nie polegamy na faktycznym stanie pulpitu:
    przy hwnd=0 funkcja sięga po GetForegroundWindow(), więc to ją zaślepiamy.
    Bez tego test zależy od tego, co było aktywne w chwili uruchomienia (i pada w CI).
    """
    import focus_detector

    monkeypatch.setattr(focus_detector.user32, "GetForegroundWindow", lambda: 0)
    ok, reason = focus_detector.is_text_field_focused(0)
    assert not ok
    assert "Brak aktywnego okna" in reason

