"""
test_zapasowy_llm.py - Zapasowy silnik korekty, gdy dostawca główny padnie.

Powód: log z 3.11.2026 18:05-18:09. Gemini oddało 503 "high demand" i ReadTimeout na
wszystkich trzech lekkich modelach naraz, więc pięć dyktowań pod rząd dostało surową
transkrypcję Whispera. Kolejka modeli w obrębie jednego dostawcy tego nie ratuje.

Sprawdzane:
- gdy Gemini milczy, odpowiedź zapasowego silnika wchodzi jako korekta,
- zapas nie wydłuża oczekiwania: wchodzi po progu hedge, nie po budżecie,
- gdy wszystkie modele Gemini są świeżo po awarii, zapas jest pytany PIERWSZY,
- przy zdrowym Gemini zapas nie dostaje żadnego żądania (nie palimy darmowych limitów),
- wyłączony zapas i zapas bez klucza nie zmieniają niczego,
- zły klucz dostawcy wyklucza go z sesji, ale nie przerywa wyścigu,
- klucz zapasowego silnika nie ląduje w config.json i nie kasuje klucza głównego.
"""

import os
import sys
import time

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _transcriber(monkeypatch, handler, **cfg):
    import transcriber as tr

    t = tr.Transcriber.__new__(tr.Transcriber)
    t.config = {
        "llm_provider": "gemini",
        "llm_api_key": "atrapa-klucza-glownego",
        "llm_model": "gemini-flash-lite-latest",
        "llm_system_prompt": "popraw",
        "llm_fallback_provider": "groq",
        "llm_fallback_api_key": "atrapa-klucza-zapasowego",
        "gemini_hedge_after_seconds": 0.3,
    }
    t.config.update(cfg)
    t.last_llm_status = None
    t.last_llm_engine = None
    t.last_llm_duration = 0.0
    t._dead_llm_models = set()
    t._slow_llm_models = {}
    t._dead_llm_providers = set()

    real_client = httpx.Client
    monkeypatch.setattr(tr.httpx, "Client",
                        lambda *a, **k: real_client(*a, transport=httpx.MockTransport(handler), **k))
    return tr, t


def _gemini_ok(text):
    return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]})


def _openai_ok(text):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def _jest_groq(request):
    return "api.groq.com" in str(request.url)


def test_zapas_ratuje_korekte_gdy_gemini_oddaje_503(monkeypatch):
    """Dokładnie sytuacja z logu: całe Gemini na 503, korekta i tak ma wejść."""
    trafienia = []

    def handler(request):
        trafienia.append(str(request.url))
        if _jest_groq(request):
            return _openai_ok("Tekst poprawiony przez zapas.")
        return httpx.Response(503, json={"error": {"message": "high demand"}})

    _, t = _transcriber(monkeypatch, handler)

    assert t._post_process_with_llm("tekst surowy") == "Tekst poprawiony przez zapas."
    assert t.last_llm_status == "ok"
    assert t.last_llm_engine.startswith("groq:")
    assert any("api.groq.com" in u for u in trafienia)


def test_zapas_nie_wydluza_czekania_gdy_gemini_milczy(monkeypatch):
    """Zapas wchodzi po progu hedge (0.3 s), a nie po wyczerpaniu budżetu korekty."""
    def handler(request):
        if _jest_groq(request):
            return _openai_ok("Gotowe.")
        time.sleep(5.0)          # Gemini wisi, tak jak przy ReadTimeout z logu
        return _gemini_ok("za późno")

    _, t = _transcriber(monkeypatch, handler)

    t0 = time.monotonic()
    assert t._post_process_with_llm("tekst surowy") == "Gotowe."
    czekanie = time.monotonic() - t0
    assert czekanie < 2.0, f"czekaliśmy {czekanie:.2f}s, zapas ma wchodzić po progu hedge"


def test_po_awarii_gemini_zapas_jest_pytany_pierwszy(monkeypatch):
    """Gdy wszystkie modele Gemini siedzą w cooldownie, pierwsze żądanie idzie do zapasu."""
    kolejnosc = []

    def handler(request):
        kolejnosc.append("groq" if _jest_groq(request) else "gemini")
        if _jest_groq(request):
            return _openai_ok("Gotowe.")
        return httpx.Response(503, json={"error": "high demand"})

    tr_mod, t = _transcriber(monkeypatch, handler)
    teraz = time.monotonic()
    t._slow_llm_models = {m: teraz + 200.0 for m in tr_mod.GEMINI_FALLBACK_MODELS}

    assert t._post_process_with_llm("tekst surowy") == "Gotowe."
    assert kolejnosc[0] == "groq", f"pierwsze pytanie poszło do {kolejnosc[0]}, a Gemini było świeżo po awarii"


def test_zdrowe_gemini_nie_pyta_zapasu(monkeypatch):
    """Darmowe limity zapasu są skończone: przy działającym Gemini ma nie dostać żądania."""
    trafienia = []

    def handler(request):
        trafienia.append(str(request.url))
        return _gemini_ok("Poprawione przez Gemini.")

    _, t = _transcriber(monkeypatch, handler)

    assert t._post_process_with_llm("tekst surowy") == "Poprawione przez Gemini."
    assert len(trafienia) == 1, f"poszło {len(trafienia)} żądań zamiast jednego: {trafienia}"
    assert not any("api.groq.com" in u for u in trafienia)


@pytest.mark.parametrize("zmiana", [
    {"llm_fallback_provider": ""},                      # zapas wyłączony
    {"llm_fallback_api_key": ""},                       # zapas bez klucza
    {"llm_fallback_provider": "gemini"},                # ten sam dostawca co główny
])
def test_bez_uzywalnego_zapasu_zostaje_surowy_tekst(monkeypatch, zmiana):
    trafienia = []

    def handler(request):
        trafienia.append(str(request.url))
        return httpx.Response(503, json={"error": "high demand"})

    _, t = _transcriber(monkeypatch, handler, **zmiana)

    assert t._post_process_with_llm("tekst surowy") == "tekst surowy"
    assert t.last_llm_status == "failed"
    assert not any("api.groq.com" in u for u in trafienia)


def test_zly_klucz_glownego_nie_przerywa_wyscigu(monkeypatch):
    """401 na Gemini to już nie koniec korekty: zapas kończy robotę, a Gemini wypada z sesji."""
    trafienia = []

    def handler(request):
        trafienia.append(str(request.url))
        if _jest_groq(request):
            return _openai_ok("Gotowe.")
        return httpx.Response(401, json={"error": "API key not valid"})

    _, t = _transcriber(monkeypatch, handler)

    assert t._post_process_with_llm("tekst surowy") == "Gotowe."
    assert "gemini" in t._dead_llm_providers

    # Druga próba w tej samej sesji nie pyta już Gemini: zły klucz sam się nie naprawi
    trafienia.clear()
    assert t._post_process_with_llm("tekst surowy") == "Gotowe."
    assert trafienia and all("api.groq.com" in u for u in trafienia), trafienia


def test_wycofany_model_zapasu_ustepuje_nastepnemu(monkeypatch):
    """Groq zmienia listę modeli co kwartał: 404 ma przestawić zapas na kolejny model."""
    def handler(request):
        if _jest_groq(request):
            if "openai/gpt-oss-20b" in request.content.decode("utf-8"):
                return httpx.Response(404, json={"error": {"message": "model_not_found"}})
            return _openai_ok("Gotowe.")
        return httpx.Response(503, json={"error": "high demand"})

    _, t = _transcriber(monkeypatch, handler)

    # Pierwsze dyktowanie: model z listy odpada na 404
    t._post_process_with_llm("tekst surowy")
    assert "groq:openai/gpt-oss-20b" in t._dead_llm_models

    # Drugie: zapas pyta już następny model i korekta wchodzi
    assert t._post_process_with_llm("tekst surowy") == "Gotowe."
    assert t.last_llm_engine == "groq:openai/gpt-oss-120b"


def test_klucz_zapasu_nie_laduje_w_config_json(monkeypatch, tmp_path):
    """config.json jeździ w paczce portable, więc żaden klucz nie ma prawa w nim zostać."""
    import json
    import config

    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr(config, "get_config_path", lambda: str(cfg_path))

    cfg = config.DEFAULT_CONFIG.copy()
    cfg["llm_api_key"] = "atrapa-glowna-123456789012345"
    cfg["llm_fallback_provider"] = "groq"
    cfg["llm_fallback_api_key"] = "atrapa-zapasowa-123456789012"
    config.save_config(cfg)

    zapisane = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert zapisane["llm_fallback_api_key"] == ""
    assert zapisane["llm_api_key"] == ""
    assert zapisane["llm_fallback_provider"] == "groq"

    # Oba klucze żyją w secrets.json, każdy w swoim polu
    sekrety = config.load_secrets()
    assert sekrety["llm_api_key"] == "atrapa-glowna-123456789012345"
    assert sekrety["llm_fallback_api_key"] == "atrapa-zapasowa-123456789012"

    # ...i wracają po wczytaniu konfiguracji
    wczytane = config.load_config()
    assert wczytane["llm_api_key"] == "atrapa-glowna-123456789012345"
    assert wczytane["llm_fallback_api_key"] == "atrapa-zapasowa-123456789012"


def test_zapis_klucza_zapasu_nie_rusza_klucza_glownego(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "get_config_path", lambda: str(tmp_path / "config.json"))
    assert config.save_secret_key("atrapa-glowna-987654321098765", "llm_api_key")
    assert config.save_secret_key("atrapa-zapasowa-987654321098", "llm_fallback_api_key")

    sekrety = config.load_secrets()
    assert sekrety["llm_api_key"] == "atrapa-glowna-987654321098765"
    assert sekrety["llm_fallback_api_key"] == "atrapa-zapasowa-987654321098"
    assert not config.save_secret_key("x", "cokolwiek_innego")
