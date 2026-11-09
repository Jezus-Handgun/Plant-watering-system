"""Automat: czysta logika z fałszywym zegarem. Sterownik: atrapa pinów + baza tymczasowa."""

import pytest

from app.controller import DOBA_S, Automat, Decyzja, Sterownik
from app.db import Baza
from hardware.fake import ustaw_sonde
from hardware.pump import Pompka
from hardware.sensor import Sonda

PRZERWA = 15 * 60


class Zegar:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def zegar():
    return Zegar()


@pytest.fixture
def automat(zegar):
    return Automat(przerwa_s=PRZERWA, limit_dobowy=2, zegar=zegar)


# --- Automat ---


def test_mokro_nie_podlewa(automat, zegar):
    zegar.t = PRZERWA
    assert automat.decyduj(sucho=False) is Decyzja.MOKRO


def test_po_starcie_najpierw_przerwa(automat, zegar):
    zegar.t = PRZERWA - 1
    assert automat.decyduj(sucho=True) is Decyzja.PRZERWA
    zegar.t = PRZERWA
    assert automat.decyduj(sucho=True) is Decyzja.PODLANO


def test_przerwa_miedzy_podlaniami(automat, zegar):
    zegar.t = PRZERWA
    automat.decyduj(sucho=True)
    zegar.t += PRZERWA - 1
    assert automat.decyduj(sucho=True) is Decyzja.PRZERWA
    zegar.t += 1
    assert automat.decyduj(sucho=True) is Decyzja.PODLANO


def test_limit_dobowy_i_odnowienie_po_dobie(automat, zegar):
    for _ in range(2):
        zegar.t += PRZERWA
        assert automat.decyduj(sucho=True) is Decyzja.PODLANO
    zegar.t += PRZERWA
    assert automat.decyduj(sucho=True) is Decyzja.LIMIT
    zegar.t = PRZERWA + DOBA_S  # pierwsze podlanie wypada z okna 24 h
    assert automat.decyduj(sucho=True) is Decyzja.PODLANO


def test_podlanie_reczne_wymusza_przerwe_ale_nie_zuzywa_limitu(automat, zegar):
    zegar.t = 10 * PRZERWA
    automat.po_podlaniu_recznym()
    assert automat.decyduj(sucho=True) is Decyzja.PRZERWA
    zegar.t += PRZERWA
    assert automat.decyduj(sucho=True) is Decyzja.PODLANO
    assert automat.podlania_w_dobie() == 1


def test_podlania_z_poprzedniego_uruchomienia_licza_sie_do_limitu(zegar):
    zegar.t = DOBA_S
    automat = Automat(PRZERWA, limit_dobowy=2, zegar=zegar, podlania=[DOBA_S - 100, DOBA_S - 50])
    zegar.t += PRZERWA
    assert automat.decyduj(sucho=True) is Decyzja.LIMIT


# --- Sterownik ---


@pytest.fixture
def baza(tmp_path):
    return Baza(str(tmp_path / "test.db"))


@pytest.fixture
def sterownik(baza, zegar):
    s = Sterownik(Sonda(liczba_odczytow=1), Pompka(), baza, zegar=zegar)
    yield s
    s.zamknij()


@pytest.fixture
def bez_czekania(sterownik, monkeypatch):
    """Pompka „pracuje” bez czekania; lista zadanych czasów."""
    czasy = []
    monkeypatch.setattr(sterownik.pompka._przerwij, "wait", czasy.append)
    return czasy


def test_krok_zapisuje_pomiar(sterownik, baza):
    ustaw_sonde(sucho=False)
    assert sterownik.krok() is Decyzja.MOKRO
    assert baza.historia("pomiary", 10)["elementy"][0]["sucho"] == 0


def test_krok_podlewa_i_zapisuje_podlanie(sterownik, baza, zegar, bez_czekania):
    ustaw_sonde(sucho=True)
    zegar.t = PRZERWA
    assert sterownik.krok() is Decyzja.PODLANO
    assert bez_czekania == [3]
    podlanie = baza.ostatnie_podlanie()
    assert podlanie["zrodlo"] == "automat" and podlanie["blad"] is None
    assert not sterownik.pompka.pracuje


def test_automat_wylaczony_nie_podlewa(sterownik, zegar, bez_czekania):
    sterownik.zmien_ustawienia({"automat_wlaczony": False})
    ustaw_sonde(sucho=True)
    zegar.t = PRZERWA
    assert sterownik.krok() is Decyzja.WYLACZONY
    assert bez_czekania == []


def test_awaria_pompki_zapisana_i_bez_ponawiania(sterownik, baza, zegar, monkeypatch):
    def awaria(_s):
        raise RuntimeError("awaria")

    monkeypatch.setattr(sterownik.pompka._przerwij, "wait", awaria)
    ustaw_sonde(sucho=True)
    zegar.t = PRZERWA
    sterownik.krok()
    assert "awaria" in baza.ostatnie_podlanie()["blad"]
    assert not sterownik.pompka.pracuje
    assert sterownik.krok() is Decyzja.PRZERWA


def test_restart_nie_zeruje_limitu(baza, zegar):
    """Podlania zapisane przez poprzedni Sterownik liczą się do limitu nowego."""
    baza.zapisz_ustawienia({"limit_dobowy": 1})
    baza.zakoncz_podlanie(baza.zacznij_podlanie("automat", 3), 3, None)
    nowy = Sterownik(Sonda(liczba_odczytow=1), Pompka(), baza, zegar=zegar)
    try:
        ustaw_sonde(sucho=True)
        zegar.t = PRZERWA
        assert nowy.krok() is Decyzja.LIMIT
    finally:
        nowy.zamknij()
