"""Automat podlewania: odczyt sondy → decyzja → ewentualne podlanie.

Klasa Automat nie zna Flaska ani GPIO — sonda, pompka i zegar są wstrzykiwane,
więc logikę testujemy na atrapach z fałszywym zegarem.

Uruchomienie (z katalogu projektu):
    Pi:      uv run python -m app.controller
    Windows: $env:HARDWARE_MODE="simulation"; uv run python -m app.controller
"""

import logging
import os
import signal
import sys
import time
from collections import deque
from enum import StrEnum

from hardware.fake import wlacz_symulacje
from hardware.pump import Pompka
from hardware.sensor import Sonda

log = logging.getLogger("automat")

DOBA_S = 24 * 60 * 60


class Decyzja(StrEnum):
    MOKRO = "mokro"
    PRZERWA = "przerwa"  # sucho, ale za krótko od ostatniego podlania (woda wsiąka)
    LIMIT = "limit"  # sucho, ale wyczerpany limit podlań na dobę
    PODLANO = "podlano"


class Automat:
    def __init__(
        self,
        sonda,
        pompka,
        czas_podlewania_s: float = 3.0,
        przerwa_s: float = 15 * 60,
        limit_dobowy: int = 5,
        zegar=time.monotonic,
    ):
        self.sonda = sonda
        self.pompka = pompka
        self.czas_podlewania_s = czas_podlewania_s
        self.przerwa_s = przerwa_s
        self.limit_dobowy = limit_dobowy
        # Zegar monotoniczny: Pi nie ma zegara RTC, czas systemowy skacze po synchronizacji NTP.
        self._zegar = zegar
        # Start liczy się jak podlanie — po restarcie (np. pętla awarii usługi) najpierw przerwa.
        # shortcut: stan tylko w pamięci, restart zeruje limit dobowy; etap 5 zapisze go w SQLite.
        self._ostatnie_podlanie = zegar()
        self._podlania = deque()  # czasy podlań z ostatnich 24 h

    def krok(self) -> Decyzja:
        if not self.sonda.jest_sucho():
            return Decyzja.MOKRO
        teraz = self._zegar()
        while self._podlania and teraz - self._podlania[0] >= DOBA_S:
            self._podlania.popleft()
        if teraz - self._ostatnie_podlanie < self.przerwa_s:
            return Decyzja.PRZERWA
        if len(self._podlania) >= self.limit_dobowy:
            return Decyzja.LIMIT
        # Zapis przed podlaniem: nieudana próba też liczy się do przerwy i limitu,
        # więc awaria pompki nie powoduje ponawiania co krok.
        self._ostatnie_podlanie = teraz
        self._podlania.append(teraz)
        self.pompka.podlej(self.czas_podlewania_s)
        return Decyzja.PODLANO


def petla(automat: Automat, odstep_s: float = 60) -> None:
    while True:
        try:
            log.info("Decyzja: %s", automat.krok())
        except Exception:
            # Pompka jest już wyłączona przez finally w Pompka.podlej().
            log.exception("Błąd w kroku automatu")
        time.sleep(odstep_s)


def _zakoncz(signum, _frame):
    # SIGTERM (systemctl stop) / SIGHUP (zerwane SSH) → SystemExit, żeby zadziałały bloki finally.
    sys.exit(f"Zatrzymano sygnałem {signum}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler("automat.log", encoding="utf-8"), logging.StreamHandler()],
    )
    tryb = os.environ.get("HARDWARE_MODE", "real")
    if tryb == "simulation":
        wlacz_symulacje()
    elif tryb != "real":
        sys.exit(f"Nieznany HARDWARE_MODE={tryb!r} (dozwolone: real, simulation)")

    signal.signal(signal.SIGTERM, _zakoncz)
    if hasattr(signal, "SIGHUP"):  # brak na Windowsie
        signal.signal(signal.SIGHUP, _zakoncz)

    sonda, pompka = Sonda(), Pompka()
    automat = Automat(sonda, pompka)
    log.info(
        "Start (tryb=%s): podlanie %s s, przerwa %s s, limit %s/dobę",
        tryb,
        automat.czas_podlewania_s,
        automat.przerwa_s,
        automat.limit_dobowy,
    )
    try:
        petla(automat)
    finally:
        pompka.close()
        sonda.close()
        log.info("Koniec pracy automatu")


if __name__ == "__main__":
    main()
