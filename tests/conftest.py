import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Na poziomie modułu, nie w fixture: app.py konfiguruje logowanie przy imporcie, a import
# modułów testowych leci przed fixture'ami. Bez tego pytest pisałby do żywego logu
# aplikacji i biłby się z nią o rotację pliku.
os.environ["WHISCRIBE_LOG_DIR"] = os.path.join(tempfile.gettempdir(), "whiscribe-testy")


@pytest.fixture(autouse=True)
def _izolowana_konfiguracja(monkeypatch, tmp_path):
    """Testy nigdy nie zapisują prawdziwego config.json ani %APPDATA%\\Whiscribe\\secrets.json.

    Wcześniej test zapisujący konfigurację bez klucza czyścił klucz API działającej aplikacji.
    """
    import config

    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(config, "get_config_path", lambda: str(tmp_path / "config.json"))
    monkeypatch.delenv("WHISCRIBE_LLM_API_KEY", raising=False)
