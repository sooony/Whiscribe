"""
Pamięć wklejek: własny magazyn ostatnio podyktowanego tekstu, niezależny od schowka
systemowego i od historii Win+V.

Po co: inject_text po wklejeniu przywraca poprzednią zawartość schowka albo go czyści
(ochrona prywatności), a panel transkrypcji w widżecie nigdy nie był rysowany, więc
podyktowany tekst nie zostawał nigdzie. Dotyczy to zwłaszcza sytuacji, w których tekst
w ogóle nie został wklejony: utracony fokus okna, spóźniony wynik, przerwane przetwarzanie.

Dlatego wpis powstaje w momencie, w którym tekst powstał, a nie po udanym wklejeniu,
a status dopisujemy po próbie.

Pamięć żyje tylko w pamięci procesu. Zapis na dysk byłby dopisywaniem prywatnej treści
do profilu dla scenariusza (utrata tekstu przy restarcie), którego na razie nie
zaobserwowaliśmy.
"""
import threading
import time
from collections import deque

# Jedno dyktowanie może być długie (max_recording_seconds domyślnie 1200 s), ale trzymanie
# w pamięci megabajtów tekstu nie ma sensu.
MAX_ZNAKOW = 20_000

STATUS_WKLEJONY = "wklejony"
STATUS_WPISANY = "wpisany"
STATUS_W_TOKU = "w toku"
STATUS_BRAK_FOKUSU = "nie wklejono (utracony fokus okna)"
STATUS_SPOZNIONY = "nie wklejono (spóźniony wynik)"
STATUS_PRZERWANE = "nie wklejono (przerwane przetwarzanie)"

# Statusy, przy których użytkownik ma tekst wyłącznie tutaj
STATUSY_NIEWKLEJONE = (STATUS_BRAK_FOKUSU, STATUS_SPOZNIONY, STATUS_PRZERWANE)


class WpisWklejki:
    """Jeden zapamiętany tekst. Trzyma treść PRZED normalizacją injectora.

    inject_text robi `text.strip() + " "`, więc zapisanie tego, co dostał injector,
    dawałoby przy przywracaniu drugą spację i rozjazd z oryginałem.
    """

    __slots__ = ("text", "czas", "status", "proc", "znakow")

    def __init__(self, text: str, status: str, proc: str = ""):
        self.text = text
        self.czas = time.time()
        self.status = status
        self.proc = proc or ""
        self.znakow = len(text)

    @property
    def niewklejony(self) -> bool:
        return self.status in STATUSY_NIEWKLEJONE

    def godzina(self) -> str:
        return time.strftime("%H:%M", time.localtime(self.czas))

    def podglad(self, limit: int = 40) -> str:
        jedna_linia = " ".join(self.text.split())
        if len(jedna_linia) <= limit:
            return jedna_linia
        return jedna_linia[:limit].rstrip() + "..."

    def etykieta(self) -> str:
        """Opis do pozycji w menu: godzina, status i początek treści."""
        stan = self.status if self.status != STATUS_WKLEJONY else "wklejony"
        return f"{self.godzina()} - {stan} - {self.podglad()}"


class PasteMemory:
    """Ring ostatnich dyktowań. Domyślnie jeden wpis.

    Rozmiar jest konfigurowalny (paste_memory_size), bo prawdziwa potrzeba to "odzyskaj
    ostatnie", a nie "przeszukaj historię". Jeśli kiedyś zabraknie przedostatniego, zmiana
    jednej liczby w config.json daje ring bez przepisywania czegokolwiek.
    """

    def __init__(self, rozmiar: int = 1):
        try:
            rozmiar = int(rozmiar)
        except (TypeError, ValueError):
            rozmiar = 1
        self._rozmiar = max(1, min(10, rozmiar))
        self._wpisy = deque(maxlen=self._rozmiar)
        self._lock = threading.RLock()

    @property
    def rozmiar(self) -> int:
        return self._rozmiar

    def __len__(self) -> int:
        with self._lock:
            return len(self._wpisy)

    def pusta(self) -> bool:
        return len(self) == 0

    def dodaj(self, text: str, status: str = STATUS_W_TOKU, proc: str = ""):
        """Zapamiętuje tekst i zwraca wpis, żeby wywołujący mógł później dopisać status.

        Zwraca None dla tekstu pustego. Powtórzenie dokładnie tej samej treści co
        najnowszy wpis tylko odświeża jego status: dzięki temu ponowna próba wklejenia
        tego samego tekstu nie wypycha z ringu wpisu, który chcemy zachować.
        """
        if not text or not text.strip():
            return None

        if len(text) > MAX_ZNAKOW:
            text = text[:MAX_ZNAKOW]

        with self._lock:
            if self._wpisy and self._wpisy[-1].text == text:
                wpis = self._wpisy[-1]
                wpis.status = status
                wpis.czas = time.time()
                if proc:
                    wpis.proc = proc
                return wpis

            wpis = WpisWklejki(text, status, proc)
            self._wpisy.append(wpis)
            return wpis

    def oznacz(self, wpis, status: str):
        """Dopisuje status po próbie wklejenia. Bezpieczne dla wpisu wypchniętego z ringu."""
        if wpis is None:
            return
        with self._lock:
            wpis.status = status

    def ostatni(self):
        with self._lock:
            return self._wpisy[-1] if self._wpisy else None

    def lista(self):
        """Wpisy od najnowszego do najstarszego."""
        with self._lock:
            return list(reversed(self._wpisy))

    def wyczysc(self):
        with self._lock:
            self._wpisy.clear()
