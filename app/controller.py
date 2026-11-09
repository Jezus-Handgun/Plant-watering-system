"""Logika podlewania.

- Automat  — czysta logika decyzji (sucho? przerwa? limit?), bez sprzętu i bazy.
- Sterownik — jedyny właściciel sprzętu w procesie: wątek automatu, ręczne podlewanie z API,
              blokada pompki i zapis do bazy.
"""

import logging
import threading
import time
from collections import deque
from enum import StrEnum

log = logging.getLogger("automat")

DOBA_S = 24 * 60 * 60


class Decyzja(StrEnum):
    WYLACZONY = "automat wyłączony"
    MOKRO = "mokro"
    PRZERWA = "przerwa"  # sucho, ale za krótko od ostatniego podlania (woda wsiąka)
    LIMIT = "limit"  # sucho, ale wyczerpany limit podlań automatu na dobę
    PODLANO = "podlano"


class Automat:
    def __init__(self, przerwa_s: float, limit_dobowy: int, zegar=time.monotonic, podlania=()):
        self.przerwa_s = przerwa_s
        self.limit_dobowy = limit_dobowy
        # Zegar monotoniczny: Pi nie ma zegara RTC, czas systemowy skacze po synchronizacji NTP.
        self._zegar = zegar
        # Start liczy się jak podlanie — po restarcie (np. pętla awarii usługi) najpierw przerwa.
        self._ostatnie_podlanie = zegar()
        self._podlania = deque(sorted(podlania))  # czasy podlań automatu z ostatnich 24 h

    def podlania_w_dobie(self) -> int:
        teraz = self._zegar()
        while self._podlania and teraz - self._podlania[0] >= DOBA_S:
            self._podlania.popleft()
        return len(self._podlania)

    def decyduj(self, sucho: bool) -> Decyzja:
        """Decyzja PODLANO od razu się zapisuje (przed włączeniem pompki): nieudana próba
        też liczy się do przerwy i limitu, więc awaria nie powoduje ponawiania co krok."""
        if not sucho:
            return Decyzja.MOKRO
        teraz = self._zegar()
        if teraz - self._ostatnie_podlanie < self.przerwa_s:
            return Decyzja.PRZERWA
        if self.podlania_w_dobie() >= self.limit_dobowy:
            return Decyzja.LIMIT
        self._ostatnie_podlanie = teraz
        self._podlania.append(teraz)
        return Decyzja.PODLANO

    def po_podlaniu_recznym(self) -> None:
        # Ręczne podlanie nie wlicza się do limitu automatu, ale woda musi wsiąknąć.
        self._ostatnie_podlanie = self._zegar()


class Sterownik:
    def __init__(self, sonda, pompka, baza, zegar=time.monotonic, zegar_scienny=time.time):
        self.sonda = sonda
        self.pompka = pompka
        self.baza = baza
        self.ustawienia = baza.ustawienia()
        self._blokada_pompki = threading.Lock()  # jedno podlewanie naraz (automat albo ręczne)
        self._koniec = threading.Event()
        self._watek = None
        self.ostatni_pomiar = None  # {"sucho": bool, "czas": float}
        self.ostatnia_decyzja = None

        # Podlania automatu z ostatniej doby (z bazy, więc restart nie zeruje limitu).
        # Baza ma czas ścienny, automat monotoniczny — przeliczamy przez „wiek” podlania.
        # Gdy zegar Pi po starcie jest cofnięty, wiek wychodzi zaniżony → automat ostrożniejszy.
        teraz_m, teraz_s = zegar(), zegar_scienny()
        podlania = [
            teraz_m - max(0.0, teraz_s - t) for t in baza.czasy_podlan_automatu(od=teraz_s - DOBA_S)
        ]
        self.automat = Automat(
            self.ustawienia["przerwa_min"] * 60, self.ustawienia["limit_dobowy"], zegar, podlania
        )

    # --- automat ---

    def krok(self) -> Decyzja:
        """Jeden cykl: pomiar → zapis → decyzja → ewentualne podlanie."""
        sucho = self.sonda.jest_sucho()
        self.baza.zapisz_pomiar(sucho)
        self.ostatni_pomiar = {"sucho": sucho, "czas": time.time()}
        if not self.ustawienia["automat_wlaczony"]:
            decyzja = Decyzja.WYLACZONY
        else:
            decyzja = self.automat.decyduj(sucho)
        self.ostatnia_decyzja = decyzja
        log.info("Pomiar: %s, decyzja: %s", "sucho" if sucho else "mokro", decyzja)
        if decyzja is Decyzja.PODLANO:
            # Ręczne podlewanie właśnie trwa → pomijamy (i tak ustawiło przerwę automatu).
            if self._blokada_pompki.acquire(blocking=False):
                self._podlewanie("automat", self.ustawienia["czas_podlewania_s"])
        return decyzja

    def start(self, odstep_s: float = 60) -> None:
        self._watek = threading.Thread(
            target=self._petla, args=(odstep_s,), name="automat", daemon=True
        )
        self._watek.start()

    def _petla(self, odstep_s: float) -> None:
        while not self._koniec.is_set():
            try:
                self.krok()
            except Exception:
                # Pompka jest już wyłączona przez finally w Pompka.podlej().
                log.exception("Błąd w kroku automatu")
            self._koniec.wait(odstep_s)

    # --- podlewanie ---

    def podlej_recznie(self, sekundy: float) -> bool:
        """Startuje podlewanie w tle. False, gdy pompka już pracuje."""
        if not self._blokada_pompki.acquire(blocking=False):
            return False
        self.automat.po_podlaniu_recznym()
        threading.Thread(
            target=self._podlewanie, args=("reczne", sekundy), name="podlewanie", daemon=True
        ).start()
        return True

    def _podlewanie(self, zrodlo: str, sekundy: float) -> None:
        """Wywoływać z zajętą blokadą pompki — zwalnia ją na końcu."""
        try:
            id_ = self.baza.zacznij_podlanie(zrodlo, sekundy)
            czas_pracy, blad = 0.0, None
            try:
                czas_pracy = self.pompka.podlej(sekundy)
            except Exception as e:
                blad = repr(e)
                log.exception("Błąd podlewania (%s)", zrodlo)
            finally:
                self.baza.zakoncz_podlanie(id_, czas_pracy, blad)
            log.info("Podlanie (%s): %.2f s z %s s", zrodlo, czas_pracy, sekundy)
        finally:
            self._blokada_pompki.release()

    def zatrzymaj_pompke(self) -> None:
        self.pompka.zatrzymaj()

    # --- ustawienia i stan ---

    def zmien_ustawienia(self, zmiany: dict) -> dict:
        """`zmiany` muszą być już sprawdzone (api.py)."""
        self.baza.zapisz_ustawienia(zmiany)
        self.ustawienia = self.ustawienia | zmiany
        self.automat.przerwa_s = self.ustawienia["przerwa_min"] * 60
        self.automat.limit_dobowy = self.ustawienia["limit_dobowy"]
        return self.ustawienia

    def status(self) -> dict:
        return {
            # Zegar Pi: bez internetu (hotspot na obronie) może być cofnięty — panel liczy
            # „X min temu” i okno wykresu względem niego, a nie zegara laptopa.
            "czas_serwera": time.time(),
            "pomiar": self.ostatni_pomiar,
            "pompka_pracuje": self.pompka.pracuje,
            "automat_wlaczony": self.ustawienia["automat_wlaczony"],
            "ostatnia_decyzja": self.ostatnia_decyzja,
            "ostatnie_podlanie": self.baza.ostatnie_podlanie(),
            "podlania_automatu_24h": self.automat.podlania_w_dobie(),
            "limit_dobowy": self.ustawienia["limit_dobowy"],
        }

    def zamknij(self) -> None:
        self._koniec.set()
        self.pompka.zatrzymaj()
        if self._watek is not None:
            self._watek.join(timeout=15)
        self._blokada_pompki.acquire(timeout=15)  # poczekaj na koniec ręcznego podlewania
        self.pompka.close()
        self.sonda.close()
