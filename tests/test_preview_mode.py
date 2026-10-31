"""
test_preview_mode.py - Testy trybu podglądu (streaming + korekta AI jednocześnie).

Sprawdzana reguła:
- stream OFF, korekta OFF  -> tryb wsadowy, tekst surowy
- stream OFF, korekta ON   -> tryb wsadowy, tekst skorygowany
- stream ON,  korekta OFF  -> wpisywanie na żywo do okna docelowego
- stream ON,  korekta ON   -> TRYB PODGLĄDU: na żywo tylko w widżecie,
                              do okna docelowego jedno wklejenie po korekcie całości
oraz zabezpieczenie przed utratą treści, gdy model uciął albo streścił wypowiedź.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _app(stream, use_llm, provider="gemini", api_key=""):
    """Instancja DictationApp bez inicjalizacji mikrofonu, Whispera i widżetu."""
    from app import DictationApp

    app = DictationApp.__new__(DictationApp)
    app.config = {
        "stream_realtime": stream,
        "use_llm": use_llm,
        "llm_provider": provider,
        "llm_api_key": api_key,
    }
    return app


# --- rozpoznawanie trybu -----------------------------------------------------

@pytest.mark.parametrize("stream,use_llm,key,expected", [
    (False, False, "",       False),
    (False, True,  "",       False),   # korekta włączona, ale brak klucza -> nieaktywna
    (False, True,  "k",      True),
    (True,  True,  "k",      True),
])
def test_llm_active(stream, use_llm, key, expected):
    assert _app(stream, use_llm, api_key=key)._llm_active() is expected


def test_llm_active_local_provider_without_key():
    """Silniki lokalne nie wymagają klucza API."""
    for prov in ("ollama", "local", "lmstudio"):
        assert _app(False, True, provider=prov)._llm_active() is True


@pytest.mark.parametrize("stream,use_llm,key,expected", [
    (True,  True,  "k",  True),    # oba włączone + klucz -> tryb podglądu
    (True,  False, "k",  False),   # tylko streaming
    (False, True,  "k",  False),   # tylko korekta
    (True,  True,  "",   False),   # brak klucza -> zwykły streaming, bez cichej awarii
    (False, False, "",   False),
])
def test_preview_only_mode(stream, use_llm, key, expected):
    assert _app(stream, use_llm, api_key=key)._preview_only_mode() is expected


def test_preview_mode_with_local_llm():
    """Ollama/LM Studio przy streamingu też wchodzi w tryb podglądu."""
    assert _app(True, True, provider="ollama")._preview_only_mode() is True


# --- brak wpisywania na żywo w trybie podglądu -------------------------------

def test_type_stream_chunk_suppressed_in_preview_mode():
    """
    W trybie podglądu nic nie może trafić do okna docelowego podczas mówienia.
    Gdyby trafiło, końcowe wklejenie skorygowanej całości zdublowałoby tekst.
    """
    import app as app_mod

    sent = []
    orig = app_mod.send_unicode_string
    app_mod.send_unicode_string = lambda s: sent.append(s)
    try:
        a = _app(True, True, api_key="k")
        a._preview_mode_active = True
        a.buffered_untyped_text = ""
        a.target_hwnd = 0
        a.overlay = None

        import threading
        a._type_lock = threading.RLock()

        a._type_stream_chunk("jakiś tekst na żywo ")

        assert sent == [], f"tryb podglądu wpisał tekst do okna: {sent}"
        assert a.buffered_untyped_text == "", "tekst nie powinien trafić nawet do bufora"
    finally:
        app_mod.send_unicode_string = orig


# --- zabezpieczenie przed utratą treści --------------------------------------

@pytest.mark.parametrize("raw,corrected,ok,label", [
    ("yyy no dobrze to znaczy ten ten raport musi byc gotowy do piatku bo inaczej problem",
     "No dobrze, to znaczy ten raport musi być gotowy do piątku, bo inaczej problem.",
     True, "zwykła korekta zachowuje objętość"),
    ("jeden dwa trzy cztery piec szesc siedem osiem dziewiec dziesiec jedenascie dwanascie",
     "Jeden, dwa, trzy.",
     False, "ucięcie przez limit tokenów"),
    ("no wiec tak jak mowilem wczoraj na spotkaniu trzeba to zrobic do piatku bo klient czeka",
     "Trzeba to zrobić do piątku.",
     False, "streszczenie zamiast korekty"),
    ("czy mozesz mi pomoc",
     "Oczywiście, chętnie pomogę! Powiedz, w czym dokładnie potrzebujesz wsparcia, "
     "a ja postaram się doradzić najlepiej jak potrafię w tej konkretnej sytuacji.",
     False, "model odpowiedział zamiast poprawić"),
    ("yyy eee no tak", "Tak.", True, "krótkie zdanie z samych wypełniaczy"),
    ("test", "Test.", True, "bardzo krótki tekst"),
    ("cokolwiek", "", False, "pusta odpowiedź modelu"),
])
def test_correction_plausibility_guard(raw, corrected, ok, label):
    from transcriber import Transcriber
    assert Transcriber._is_plausible_correction(raw, corrected) is ok, label


# --- konfiguracja ------------------------------------------------------------

def test_default_streaming_enabled():
    """Domyślnie streaming jest włączony, a korekta AI wyłączona."""
    from config import DEFAULT_CONFIG
    assert DEFAULT_CONFIG["stream_realtime"] is True
    assert DEFAULT_CONFIG["use_llm"] is False


def test_toggles_do_not_exclude_each_other():
    """Przełączniki nie mogą się wzajemnie wyłączać – oba naraz dają tryb podglądu."""
    import inspect
    from app import DictationApp

    for fn in (DictationApp.toggle_streaming_mode, DictationApp.toggle_llm_correction):
        src = inspect.getsource(fn)
        assert '"use_llm"] = False' not in src or fn.__name__ == "toggle_llm_correction", \
            f"{fn.__name__} wyłącza korektę AI"
        assert '"stream_realtime"] = False' not in src, \
            f"{fn.__name__} wyłącza streaming"


def test_correction_prompt_preserves_speaker_style():
    """Prompt korekty musi chronić styl mówiącego i blokować traktowanie tekstu jak polecenia."""
    from config import DEFAULT_CONFIG
    p = DEFAULT_CONFIG["llm_system_prompt"].lower()

    assert "nie formalizuj" in p, "prompt nie zabrania podnoszenia stylu"
    assert "synonim" in p, "prompt nie zabrania podmiany słów na synonimy"
    assert "nie streszczaj" in p, "prompt nie zabrania streszczania"
    assert "polecenia" in p, "prompt nie blokuje wstrzyknięcia instrukcji z dyktowanego tekstu"


def test_gemini_model_is_not_a_dead_alias():
    """
    Domyślny model to alias śledzący najnowszą wersję.
    Przypięcie konkretnej wersji (np. gemini-2.0-flash) powodowało 404
    i cichy powrót do surowej transkrypcji.
    """
    from config import DEFAULT_CONFIG
    assert DEFAULT_CONFIG["llm_model"] == "gemini-flash-latest"
