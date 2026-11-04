"""
test_dostawcy_spojnosc.py - Jedna lista dostawców dla korekty, menu i podsumowań spotkań.

Powód: 4.11.2026. Groq wycofał llama-3.3-70b-versatile (404 na żywym koncie), a nazwa
modelu stała na sztywno w trzech miejscach. Poprawka kolejności weszła tylko do korekty
dyktowania, więc podsumowanie spotkania przez Groqa nie powstałoby wcale, a wybór Groqa
w menu wpisywał martwy model do config.json. Przy tej samej okazji wyszła regresja z
2.2.24: llm_endpoint (domyślnie Ollama na localhost) nadpisywał adres API także dla
dostawców chmurowych, więc główny Groq pytałby localhost:11434 zamiast api.groq.com.

Sprawdzane:
- główny Groq pyta api.groq.com, choć w configu stoi domyślny adres Ollamy,
- główny Groq zaczyna od modelu, który żyje, a nie od wycofanego,
- adres z configu dalej działa tam, gdzie był po to wpisany: na serwerze lokalnym,
- wybór dostawcy w menu nie wpisuje żadnej nazwy modelu do konfiguracji,
- podsumowanie spotkania przechodzi na kolejny model po 404 i pyta adres dostawcy,
- żaden plik poza transcriber.py nie trzyma własnej listy modeli.
"""

import os
import sys
import threading

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _transcriber(monkeypatch, handler, **cfg):
    import transcriber as tr

    t = tr.Transcriber.__new__(tr.Transcriber)
    t.config = {
        "llm_provider": "groq",
        "llm_api_key": "atrapa-klucza-groqa",
        "llm_model": "",
        "llm_system_prompt": "popraw",
        # Tak wygląda świeży config: adres lokalnego serwera jest wypełniony domyślnie,
        # choć dostawcą jest chmura. To właśnie przewróciło główny Groq w 2.2.24.
        "llm_endpoint": "http://localhost:11434/v1",
        "llm_fallback_provider": "",
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


def _openai_ok(text):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def test_glowny_groq_pyta_api_groqa_nie_localhost(monkeypatch):
    trafienia = []

    def handler(request):
        trafienia.append(str(request.url))
        return _openai_ok("Poprawione.")

    _, t = _transcriber(monkeypatch, handler)

    assert t._post_process_with_llm("tekst surowy") == "Poprawione."
    assert trafienia, "korekta nie wysłała żadnego żądania"
    assert all("api.groq.com" in u for u in trafienia), trafienia
    assert not any("localhost" in u for u in trafienia), trafienia


def test_glowny_groq_zaczyna_od_zywego_modelu(monkeypatch):
    pytane = []

    def handler(request):
        pytane.append(request.content.decode("utf-8"))
        return _openai_ok("Poprawione.")

    _, t = _transcriber(monkeypatch, handler)
    t._post_process_with_llm("tekst surowy")

    assert "openai/gpt-oss-20b" in pytane[0], pytane[0]
    assert "llama-3.3-70b-versatile" not in pytane[0], "pierwszy strzał poszedł w model wycofany"


def test_lokalny_dostawca_nadal_slucha_adresu_z_configu(monkeypatch):
    """Adres z configu ma dalej działać tam, gdzie był po to wpisany: na serwerze lokalnym."""
    trafienia = []

    def handler(request):
        trafienia.append(str(request.url))
        return _openai_ok("Poprawione.")

    _, t = _transcriber(monkeypatch, handler, llm_provider="local", llm_api_key="",
                        llm_endpoint="http://localhost:4567/v1")
    t._post_process_with_llm("tekst surowy")

    assert trafienia and all("localhost:4567" in u for u in trafienia), trafienia


def test_wybor_dostawcy_nie_wpisuje_nazwy_modelu(monkeypatch):
    """Puste pole modelu = domyślna kolejka dostawcy, która sama omija wycofane nazwy."""
    import app

    zapisane = {}
    monkeypatch.setattr(app, "save_config", lambda cfg: zapisane.update(cfg))

    a = app.DictationApp.__new__(app.DictationApp)
    a.config = {"llm_provider": "gemini", "llm_model": "gemini-flash-lite-latest"}
    a.overlay = None
    a.transcriber = None

    app.DictationApp.set_llm_provider(a, "groq")
    assert a.config["llm_provider"] == "groq"
    assert a.config["llm_model"] == "", "w configu wylądowała nazwa modelu"
    assert zapisane.get("llm_model") == ""

    # Powrót na Gemini też nie wpisuje nazwy na sztywno
    app.DictationApp.set_llm_provider(a, "gemini")
    assert a.config["llm_model"] == ""


def test_model_wlasciwego_dostawcy_zostaje(monkeypatch):
    import app

    monkeypatch.setattr(app, "save_config", lambda cfg: None)

    a = app.DictationApp.__new__(app.DictationApp)
    a.config = {"llm_provider": "gemini", "llm_model": "gemini-3.5-flash-lite"}
    a.overlay = None
    a.transcriber = None

    app.DictationApp.set_llm_provider(a, "gemini")
    assert a.config["llm_model"] == "gemini-3.5-flash-lite", "wybór tego samego dostawcy skasował model"


class _Notatnik:
    """Minimalny notatnik spotkania: tyle, ile dotyka podsumowanie LLM."""

    def __init__(self):
        self._all_text = ""
        self.filepath = None
        self._lock = threading.Lock()

    def get_full_text(self):
        return "x" * 200          # próg długości w metodzie to 100 znaków

    def _update_notepad_display(self):
        pass


def _meeting(monkeypatch, handler, **cfg):
    import meeting_manager as mm

    m = mm.MeetingManager.__new__(mm.MeetingManager)
    m.config = {
        "llm_provider": "groq",
        "llm_api_key": "atrapa-klucza-groqa",
        "llm_model": "",
        "llm_endpoint": "http://localhost:11434/v1",
    }
    m.config.update(cfg)
    m.notepad = _Notatnik()

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client",
                        lambda *a, **k: real_client(*a, transport=httpx.MockTransport(handler), **k))
    return mm, m


def test_podsumowanie_spotkania_przechodzi_na_kolejny_model(monkeypatch):
    """Wycofany model nie może kasować całego podsumowania: pytamy kolejny z listy."""
    pytane = []

    def handler(request):
        pytane.append(str(request.url))
        if "openai/gpt-oss-20b" in request.content.decode("utf-8"):
            return httpx.Response(404, json={"error": {"message": "model_not_found"}})
        return _openai_ok("Ustalenia: wdrażamy zapas.")

    _, m = _meeting(monkeypatch, handler)
    m._generate_llm_meeting_summary()

    assert len(pytane) >= 2, "po 404 nie poszło pytanie do kolejnego modelu"
    assert all("api.groq.com" in u for u in pytane), pytane
    assert "Ustalenia: wdrażamy zapas." in m.notepad._all_text


def test_zaden_plik_nie_trzyma_wlasnej_listy_modeli():
    """Nazwy modeli żyją tylko w transcriber.ZAPASOWI_DOSTAWCY, żeby nie rozjechały się znowu."""
    import transcriber

    nazwy = set()
    for _, modele in transcriber.ZAPASOWI_DOSTAWCY.values():
        nazwy.update(modele)

    katalog = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for plik in ("app.py", "meeting_manager.py"):
        with open(os.path.join(katalog, plik), encoding="utf-8") as f:
            zrodlo = f.read()
        for nazwa in nazwy:
            # gemini-flash-lite-latest zostaje w config.py jako cel migracji wycofanych
            # modeli Google; tu pilnujemy tylko app.py i meeting_manager.py
            assert nazwa not in zrodlo, f"{plik} trzyma nazwe modelu {nazwa} na sztywno"


def test_etykiety_menu_nie_obiecuja_konkretnego_modelu():
    """Etykieta z nazwą modelu kłamie w dniu, w którym dostawca ten model wycofa.

    Tak było z "Groq Cloud (Llama 3.3)": Groq zdjął Llamę z oferty, a menu nadal ją
    obiecywało. Nazwa modelu należy do listy w transcriber.py, nie do napisu w menu.
    """
    katalog = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(katalog, "app.py"), encoding="utf-8") as f:
        linie = f.readlines()

    zakazane = ("Llama 3", "GPT-4", "Llama-3", "gpt-oss")
    trafienia = [(nr, tekst.strip()) for nr, tekst in enumerate(linie, 1)
                 if "MenuItem" in tekst or "AppendMenuW" in tekst or ", 71" in tekst or ", 72" in tekst
                 for slowo in zakazane if slowo in tekst]
    assert not trafienia, f"etykieta menu obiecuje konkretny model: {trafienia}"
