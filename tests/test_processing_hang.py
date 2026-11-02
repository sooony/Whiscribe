"""
test_processing_hang.py - Zawieszanie się w stanie "przetwarzanie".

Sprawdzane:
- wyjątek z ikony w zasobniku (wyścig w pystray) nie zostawia stanu "processing",
- ponowny skrót / X na widżecie przerywa zawieszone przetwarzanie,
- spóźniony wynik porzuconego zadania nie jest wklejany i nie zmienia stanu,
- korekta AI ma łączny limit czasu, a modele z 404 są pomijane do końca sesji,
- wycofany model Gemini w config.json jest podmieniany przy starcie,
- bufor streamingu jest pobierany od zadanej próbki.
"""

import os
import sys
import threading
import time

import httpx
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class _BrokenTray:
    """Ikona, której zmiana rzuca OSError – tak jak DestroyIcon w pystray przy wyścigu wątków."""
    @property
    def icon(self):
        return None

    @icon.setter
    def icon(self, value):
        raise OSError("DestroyIcon: Nieprawidłowy uchwyt kursora.")


class _FakeRecorder:
    def __init__(self, audio=None):
        self.audio = audio if audio is not None else np.zeros(16000, dtype=np.float32)
        self.stopped = 0

    def stop(self):
        self.stopped += 1
        return self.audio


def _app(**cfg):
    from app import DictationApp

    app = DictationApp.__new__(DictationApp)
    app.config = {"stream_realtime": False, "use_llm": False, "llm_provider": "gemini", "llm_api_key": ""}
    app.config.update(cfg)
    app.state = "recording"
    app._lock = threading.RLock()
    app._type_lock = threading.RLock()
    app._stream_stop_event = threading.Event()
    app._streaming_thread = None
    app._job_seq = 0
    app._processing_started = 0.0
    app._processing_deadline = 0.0
    app.overlay = None
    app.tray_icon = None
    app.recorder = _FakeRecorder()
    app.committed_text = ""
    app.committed_sample_offset = 0
    app.buffered_untyped_text = ""
    app._play_stop_chime = lambda: None
    return app


def test_tray_icon_error_does_not_leave_processing():
    app = _app()
    app.tray_icon = _BrokenTray()
    started = threading.Event()
    app._process_audio_worker = lambda audio, job: started.set()

    app.stop_and_transcribe()

    assert started.wait(2.0), "finalizacja nie wystartowała po błędzie ikony"
    assert app.recorder.stopped == 1
    assert app._processing_deadline > time.time()


def test_failure_before_worker_returns_to_idle():
    app = _app()

    def _boom():
        raise RuntimeError("PortAudio padł")
    app.recorder.stop = _boom

    app.stop_and_transcribe()

    assert app.state == "idle"


def test_hotkey_abandons_long_processing():
    app = _app()
    app.state = "processing"
    app._job_seq = 3
    app._processing_started = time.time() - 30
    app._last_toggle_time = 0.0

    app.toggle_dictation()

    assert app.state == "idle"
    assert app._job_seq == 4


def test_hotkey_does_not_abandon_fresh_processing():
    app = _app()
    app.state = "processing"
    app._processing_started = time.time() - 2
    app._last_toggle_time = 0.0

    app.toggle_dictation()

    assert app.state == "processing"


def test_cancel_abandons_processing():
    app = _app()
    app.state = "processing"
    app._processing_started = time.time() - 1

    app.cancel_dictation()

    assert app.state == "idle"


def test_late_result_is_not_pasted(monkeypatch):
    import app as app_module

    app = _app()
    app.state = "processing"
    app._job_seq = 1
    pasted = []
    monkeypatch.setattr(app_module, "inject_text", lambda *a, **k: pasted.append(a))

    class _SlowTranscriber:
        last_llm_status = None

        def transcribe(self, audio):
            # W trakcie korekty użytkownik przerwał i zaczął nowe dyktowanie
            app._abandon_processing("test")
            app.state = "recording"
            return "Spóźniony tekst."

    app.transcriber = _SlowTranscriber()

    app._process_audio_worker(np.zeros(16000, dtype=np.float32), 1)

    assert pasted == []
    assert app.state == "recording", "porzucone zadanie nadpisało stan nowej sesji"


# --- korekta AI: limit czasu i martwe modele ----------------------------------

def _transcriber(monkeypatch, handler, **cfg):
    import transcriber as tr

    t = tr.Transcriber.__new__(tr.Transcriber)
    t.config = {"llm_provider": "gemini", "llm_api_key": "k", "llm_model": "gemini-flash-latest",
                "llm_system_prompt": "popraw"}
    t.config.update(cfg)
    t.last_llm_status = None
    t._dead_llm_models = set()
    t._slow_llm_models = {}

    real_client = httpx.Client
    monkeypatch.setattr(tr.httpx, "Client",
                        lambda *a, **k: real_client(*a, transport=httpx.MockTransport(handler), **k))
    return tr, t


def _gemini_ok(text):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def test_llm_correction_respects_total_budget(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        time.sleep(0.8)
        return httpx.Response(503, json={"error": "przeciążony"})

    tr, t = _transcriber(monkeypatch, handler)
    monkeypatch.setattr(tr, "llm_time_budget", lambda text, is_local: 2.0)

    t0 = time.monotonic()
    out = t._post_process_with_llm("jakiś tekst")

    assert time.monotonic() - t0 < 3.0
    assert out == "jakiś tekst"
    assert t.last_llm_status == "failed"
    assert len(calls) == 2, "po wyczerpaniu budżetu nie powinno być kolejnych prób"


def test_dead_model_is_skipped_next_time(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if "gemini-flash-latest" in request.url.path:
            return httpx.Response(404, json={"error": "no longer available"})
        return _gemini_ok("Poprawiony tekst.")

    _, t = _transcriber(monkeypatch, handler)

    assert t._post_process_with_llm("poprawiony tekst") == "Poprawiony tekst."
    calls.clear()
    assert t._post_process_with_llm("poprawiony tekst") == "Poprawiony tekst."
    assert not any("gemini-flash-latest" in c for c in calls)


def test_deprecated_configured_model_is_not_called(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return _gemini_ok("Ok.")

    _, t = _transcriber(monkeypatch, handler, llm_model="gemini-2.0-flash")

    assert t._post_process_with_llm("ok") == "Ok."
    assert "gemini-2.0-flash" not in calls[0]


def test_overloaded_model_moves_to_end_of_queue(monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if "gemini-flash-latest" in request.url.path:
            return httpx.Response(503, json={"error": "high demand"})
        return _gemini_ok("Ok.")

    _, t = _transcriber(monkeypatch, handler)

    assert t._post_process_with_llm("ok") == "Ok."
    assert "gemini-flash-latest" in calls[0]
    calls.clear()
    assert t._post_process_with_llm("ok") == "Ok."
    assert len(calls) == 1 and "gemini-flash-latest" not in calls[0], "przeciążony model nadal pytany jako pierwszy"


def test_thinking_parts_are_skipped(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"text": "Najpierw przeanalizuję zdanie...", "thought": True},
            {"text": "Gotowy tekst."},
        ]}}]})

    _, t = _transcriber(monkeypatch, handler)
    assert t._post_process_with_llm("gotowy tekst") == "Gotowy tekst."


def test_llm_budget_grows_with_text_but_is_capped():
    from transcriber import llm_time_budget
    assert llm_time_budget("a" * 100, False) == pytest.approx(30.5)
    assert llm_time_budget("a" * 100000, False) == 60.0
    assert llm_time_budget("a" * 100000, True) == 90.0


def test_deprecated_gemini_model_is_migrated():
    from config import migrate_config
    assert migrate_config({"llm_provider": "gemini", "llm_model": "gemini-2.0-flash"})["llm_model"] == "gemini-flash-lite-latest"
    assert migrate_config({"llm_provider": "ollama", "llm_model": "llama3.2"})["llm_model"] == "llama3.2"


def test_old_default_flash_latest_moves_to_lite_once():
    from config import migrate_config
    cfg = migrate_config({"llm_provider": "gemini", "llm_model": "gemini-flash-latest"})
    assert cfg["llm_model"] == "gemini-flash-lite-latest"
    # Świadomy wybór pełnego modelu po migracji (config_rev zapisany) zostaje
    cfg["llm_model"] = "gemini-flash-latest"
    assert migrate_config(cfg)["llm_model"] == "gemini-flash-latest"


# --- bufor streamingu ---------------------------------------------------------

@pytest.mark.parametrize("offset", [0, 1, 799, 800, 801, 2400, 3999, 4000, 5000])
def test_recorder_returns_audio_from_offset(offset):
    from recorder import AudioRecorder

    rec = AudioRecorder()
    rng = np.random.default_rng(0)
    chunks = [rng.uniform(-0.9, 0.9, 800).astype(np.float32) for _ in range(5)]
    for c in chunks:
        c[0] = c[-1] = 0.9  # pik >= 0.75 w każdym wycinku -> bez normalizacji, porównujemy surowe próbki
    rec._audio_chunks = list(chunks)

    full = np.concatenate(chunks)
    np.testing.assert_array_equal(rec.get_current_audio(offset), full[offset:])
