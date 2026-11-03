"""
Konfiguracja logowania Whiscribe.

Zasada: root logger milczy na INFO, a gada tylko gałąź "whiscribe.*". Dzięki temu
biblioteki (faster_whisper, httpx, comtypes, huggingface_hub...) są ciche przez
dziedziczenie poziomu i nie trzeba ich wyciszać pojedynczo. Wcześniej root miał INFO
i 69% app.log stanowiły dwa komunikaty faster-whisper ("Processing audio with duration",
"VAD filter removed"), czyli ok. 370 wierszy na minutę dyktowania w streamingu.

Logi leżą poza katalogiem aplikacji, bo build PyInstallera czyści dist/ razem z logiem
z awarii, którą chcielibyśmy przeczytać.
"""
import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler

LOG_FORMAT = '%(asctime)s %(levelname).1s [%(name)s/%(threadName)s] %(message)s'

# Biblioteki, które sypią komunikatami na WARNING, mimo że nic nie wnoszą do diagnozy.
# Lista jest krótka celowo: root na WARNING wycisza wszystko inne sam.
HALASLIWE_BIBLIOTEKI = ()

_handlers = []


class RotacjaOdpornaNaBlokade(RotatingFileHandler):
    """RotatingFileHandler, dla którego nieudana rotacja nie jest utratą wpisu.

    doRollover robi os.rename, a na Windows leci PermissionError, gdy plik trzyma
    drugi proces (druga instancja aplikacji, antywirus, otwarty podgląd). Domyślny
    handler zgłasza to przez handleError na sys.stderr, który w buildzie windowed
    jest None, więc awaria rotacji była całkowicie cicha i gubiła rekord, który ją
    wywołał. Tutaj zamiast tego piszemy dalej do bieżącego pliku i próbujemy znowu
    przy następnym przekroczeniu progu.
    """

    def doRollover(self):
        try:
            super().doRollover()
            self._rotacja_zglaszana = False
        except OSError as e:
            if self.stream is None:
                try:
                    self.stream = self._open()
                except OSError:
                    return
            if not getattr(self, "_rotacja_zglaszana", False):
                self._rotacja_zglaszana = True
                logging.getLogger("whiscribe.logi").warning(
                    f"Nie udało się obrócić pliku logu ({e}); piszę dalej do bieżącego. "
                    "Zwykle oznacza to drugi proces trzymający ten plik."
                )


def get_log_dir() -> str:
    """Katalog logów: zmienna WHISCRIBE_LOG_DIR, inaczej %LOCALAPPDATA%\\Whiscribe\\logs."""
    wskazany = os.environ.get("WHISCRIBE_LOG_DIR", "").strip()
    if wskazany:
        return wskazany

    # Testy importują app.py, więc bez tego pytest pisałby do żywego logu aplikacji
    # i biłby się z nią o rotację (w starym app.log zostało po tym 172 wiersze z MagicMockami).
    if "pytest" in sys.modules:
        return os.path.join(tempfile.gettempdir(), "whiscribe-testy")

    local = os.environ.get("LOCALAPPDATA")
    if local:
        return os.path.join(local, "Whiscribe", "logs")

    from config import get_app_dir
    return get_app_dir()


def get_log_path() -> str:
    """Główny plik logu. Osobna nazwa dla wersji portable i deweloperskiej.

    Dotąd rozdzielała je ścieżka (katalog exe kontra katalog projektu); po przeniesieniu
    do jednego katalogu trzeba to zrobić świadomie, inaczej dwa procesy piszą do jednego
    pliku i rotacja nie przechodzi.
    """
    nazwa = "whiscribe.log" if getattr(sys, "frozen", False) else "whiscribe-dev.log"
    return os.path.join(get_log_dir(), nazwa)


def get_error_log_path() -> str:
    """Plik z samymi ostrzeżeniami i błędami: to jego otwiera się pierwszego po awarii."""
    nazwa = "whiscribe-errors.log" if getattr(sys, "frozen", False) else "whiscribe-dev-errors.log"
    return os.path.join(get_log_dir(), nazwa)


def setup_logging(level_name: str = "normal") -> dict:
    """Konfiguruje logowanie i zwraca słownik ze ścieżkami oraz ustalonym poziomem.

    level_name: "normal" (INFO w gałęzi whiscribe) albo "diag" (DEBUG, czyli także
    treść dyktowania). Zmienna WHISCRIBE_LOG_LEVEL ma priorytet nad configiem, bo
    jest jedynym sposobem włączenia diagnostyki, gdy aplikacja nie startuje.
    """
    global _handlers

    z_env = os.environ.get("WHISCRIBE_LOG_LEVEL", "").strip().lower()
    if z_env in ("diag", "debug"):
        level_name = "diag"
    elif z_env in ("normal", "info"):
        level_name = "normal"

    poziom_apki = logging.DEBUG if level_name == "diag" else logging.INFO

    log_dir = get_log_dir()
    sciezka = get_log_path()
    sciezka_bledow = get_error_log_path()
    blad_katalogu = None
    try:
        os.makedirs(log_dir, exist_ok=True)
    except OSError as e:
        blad_katalogu = e
        from config import get_app_dir
        log_dir = get_app_dir()
        sciezka = os.path.join(log_dir, os.path.basename(sciezka))
        sciezka_bledow = os.path.join(log_dir, os.path.basename(sciezka_bledow))

    formatter = logging.Formatter(LOG_FORMAT)
    handlers = []

    # delay=True: sam import app.py (np. przy zbieraniu testów) nie tworzy pliku,
    # dopóki nic nie zaloguje.
    try:
        glowny = RotacjaOdpornaNaBlokade(
            sciezka, maxBytes=1_000_000, backupCount=3, encoding='utf-8', delay=True
        )
        glowny.setFormatter(formatter)
        handlers.append(glowny)
    except OSError as e:
        blad_katalogu = blad_katalogu or e

    try:
        bledy = RotacjaOdpornaNaBlokade(
            sciezka_bledow, maxBytes=512_000, backupCount=1, encoding='utf-8', delay=True
        )
        bledy.setFormatter(formatter)
        bledy.setLevel(logging.WARNING)
        handlers.append(bledy)
    except OSError:
        pass

    if sys.stdout is not None:
        konsola = logging.StreamHandler(sys.stdout)
        konsola.setFormatter(formatter)
        handlers.append(konsola)

    logging.basicConfig(level=logging.WARNING, handlers=handlers, force=True)
    logging.getLogger("whiscribe").setLevel(poziom_apki)
    for nazwa in HALASLIWE_BIBLIOTEKI:
        logging.getLogger(nazwa).setLevel(logging.WARNING)

    _handlers = handlers

    if blad_katalogu is not None:
        logging.getLogger("whiscribe.logi").warning(
            f"Docelowy katalog logów był niedostępny ({blad_katalogu}); loguję do {log_dir}."
        )

    return {
        "dir": log_dir,
        "path": sciezka,
        "errors_path": sciezka_bledow,
        "level": level_name,
    }


def apply_log_level(level_name: str) -> str:
    """Ustawia poziom gałęzi "whiscribe" po wczytaniu configu.

    Logowanie konfiguruje się przy imporcie, czyli przed wczytaniem config.json
    (błędy startu muszą być widoczne), więc klucz log_level dociąga poziom dopiero
    tutaj. Zmienna środowiskowa zostaje nadrzędna.
    """
    z_env = os.environ.get("WHISCRIBE_LOG_LEVEL", "").strip().lower()
    if z_env in ("diag", "debug", "normal", "info"):
        return "diag" if z_env in ("diag", "debug") else "normal"

    level_name = (level_name or "normal").strip().lower()
    poziom = logging.DEBUG if level_name == "diag" else logging.INFO
    logging.getLogger("whiscribe").setLevel(poziom)
    return "diag" if poziom == logging.DEBUG else "normal"


def log_fingerprint(logger: logging.Logger, pola: dict):
    """Jedna linia odcisku sesji, bez której log nie wystarcza do diagnozy.

    Dotąd linie startowe były rozsypane, a po 338 powtórzeniach "Inicjalizacja modułu
    rozpoznawania mowy Whisper..." nie było jak poznać, który przebieg się wywrócił.
    """
    czesci = [f"{k}={v}" for k, v in pola.items() if v not in (None, "")]
    logger.info("START | " + " | ".join(czesci))
