import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _izolowana_konfiguracja(monkeypatch, tmp_path):
    """Testy nigdy nie zapisują prawdziwego config.json ani %APPDATA%\\Whiscribe\\secrets.json.

    Wcześniej test zapisujący konfigurację bez klucza czyścił klucz API działającej aplikacji.
    """
    import config

    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(config, "get_config_path", lambda: str(tmp_path / "config.json"))
    monkeypatch.delenv("WHISCRIBE_LLM_API_KEY", raising=False)
