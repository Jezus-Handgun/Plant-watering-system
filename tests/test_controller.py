"""Testy automatu: prawdziwe klasy Sonda/Pompka na atrapie pinów + fałszywy zegar."""

import time

import pytest

from app.controller import DOBA_S, Automat, Decyzja
from hardware.fake import ustaw_sonde
from hardware.pump import Pompka
from hardware.sensor import Sonda

PRZERWA = 15 * 60


class Zegar:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def podlania(monkeypatch):
    """Zamiast czekać w podlej() — zapisuje, ile razy pompka faktycznie ruszyła."""
    lista = []
    monkeypatch.setattr(time, "sleep", lambda s: lista.append(s))
    return lista


@pytest.fixture
def zegar():
    return Zegar()


@pytest.fixture
def automat(zegar, podlania):
    sonda, pompka = Sonda(liczba_odczytow=1), Pompka()
    yield Automat(sonda, pompka, przerwa_s=PRZERWA, limit_dobowy=2, zegar=zegar)
    pompka.close()
    sonda.close()


def test_mokro_nie_podlewa(automat, zegar, podlania):
    ustaw_sonde(sucho=False)
    zegar.t = PRZERWA
    assert automat.krok() is Decyzja.MOKRO
    assert podlania == []


def test_po_starcie_najpierw_przerwa(automat, zegar, podlania):
    ustaw_sonde(sucho=True)
    zegar.t = PRZERWA - 1
    assert automat.krok() is Decyzja.PRZERWA
    assert podlania == []


def test_sucho_po_przerwie_podlewa_i_wylacza(automat, zegar, podlania):
    ustaw_sonde(sucho=True)
    zegar.t = PRZERWA
    assert automat.krok() is Decyzja.PODLANO
    assert podlania == [3.0]
    assert not automat.pompka.pracuje


def test_przerwa_miedzy_podlaniami(automat, zegar, podlania):
    ustaw_sonde(sucho=True)
    zegar.t = PRZERWA
    automat.krok()
    zegar.t += PRZERWA - 1
    assert automat.krok() is Decyzja.PRZERWA
    zegar.t += 1
    assert automat.krok() is Decyzja.PODLANO
    assert len(podlania) == 2


def test_limit_dobowy_i_odnowienie_po_dobie(automat, zegar, podlania):
    ustaw_sonde(sucho=True)
    for _ in range(2):
        zegar.t += PRZERWA
        assert automat.krok() is Decyzja.PODLANO
    pierwsze = PRZERWA
    zegar.t += PRZERWA
    assert automat.krok() is Decyzja.LIMIT
    zegar.t = pierwsze + DOBA_S  # pierwsze podlanie wypada z okna 24 h
    assert automat.krok() is Decyzja.PODLANO
    assert len(podlania) == 3


def test_awaria_pompki_liczy_sie_jako_proba(automat, zegar, monkeypatch):
    ustaw_sonde(sucho=True)
    zegar.t = PRZERWA

    def awaria(_s):
        raise RuntimeError("awaria")

    monkeypatch.setattr(time, "sleep", awaria)
    with pytest.raises(RuntimeError):
        automat.krok()
    assert not automat.pompka.pracuje
    assert automat.krok() is Decyzja.PRZERWA  # bez natychmiastowego ponawiania
