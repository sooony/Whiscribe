"""
test_balloon_and_auto_enter.py - Czytelność komunikatów i Enter po dyktowaniu.

Sprawdzane:
- dymek nie gaśnie w chwili powrotu widżetu do stanu bezczynności (komunikat był nie do przeczytania),
- dymek znika sam po upływie swojego czasu,
- kliknięcie "Rozumiem" zamyka dymek od razu,
- Enter po zakończeniu dyktowania leci tylko przy włączonej opcji.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_dymek_przezywa_powrot_do_bezczynnosci():
    from overlay import FloatingOverlay, BALLOON_DEFAULT_S

    assert BALLOON_DEFAULT_S >= 10.0, "komunikat musi stać na ekranie na tyle długo, żeby dało się go przeczytać"

    ov = FloatingOverlay(theme="dark")
    ov.show_balloon("info", "Korekta AI nieudana — tekst surowy")
    ov.show_idle()

    assert ov._balloon_type == "info"
    assert ov._balloon_text.startswith("Korekta AI nieudana")


def test_dymek_gasnie_po_swoim_czasie():
    from overlay import FloatingOverlay

    ov = FloatingOverlay(theme="dark")
    ov.show_balloon("info", "krótki komunikat", duration_s=0.2)
    time.sleep(0.3)
    ov.show_idle()

    assert ov._balloon_type is None


def test_rozumiem_zamyka_dymek_od_razu():
    from overlay import FloatingOverlay

    ov = FloatingOverlay(theme="dark")
    ov.show_balloon("info", "komunikat do zamknięcia")
    assert ov._get_target(ov.px + ov.pw / 2, ov.py + ov.ph - 16) == 'btn_rozumiem'

    ov.hide_balloon()
    assert ov._balloon_type is None


@pytest.mark.parametrize("wlaczone, oczekiwane_entery", [(False, 0), (True, 1)])
def test_auto_enter_tylko_przy_wlaczonej_opcji(monkeypatch, wlaczone, oczekiwane_entery):
    import app

    entery = []
    monkeypatch.setattr(app, "send_enter", lambda: entery.append(1))

    class _Atrapa:
        config = {"auto_enter_after_dictation": wlaczone}

    app.DictationApp._send_auto_enter(_Atrapa())
    assert len(entery) == oczekiwane_entery
