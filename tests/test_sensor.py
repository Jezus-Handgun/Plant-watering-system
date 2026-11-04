import pytest

from hardware import sensor
from hardware.fake import ustaw_sonde
from hardware.sensor import Sonda


@pytest.fixture
def sonda():
    s = Sonda()
    yield s
    s.close()


def symuluj_odczyty(monkeypatch, odczyty):
    """Kolejne odczyty sondy: pierwszy od razu, następne po każdym sleep()."""
    kolejne = iter(odczyty[1:])
    ustaw_sonde(odczyty[0])
    monkeypatch.setattr(sensor.time, "sleep", lambda _s: ustaw_sonde(next(kolejne)))


def test_odlaczona_sonda_czyta_mokro(sonda):
    # Pull-down: brak sygnału = MOKRO = brak podlewania.
    assert sonda.odczyt_surowy() is False
    assert sonda.jest_sucho() is False


@pytest.mark.parametrize(
    ("odczyty", "oczekiwane"),
    [
        ([1, 1, 1, 1, 1], True),
        ([0, 0, 0, 0, 0], False),
        ([1, 0, 1, 0, 1], True),  # przeskakiwanie przy progu: 3/5 sucho
        ([0, 1, 0, 1, 0], False),  # 2/5 sucho
    ],
)
def test_decyzja_wiekszosciowa(sonda, monkeypatch, odczyty, oczekiwane):
    symuluj_odczyty(monkeypatch, odczyty)
    assert sonda.jest_sucho() is oczekiwane


def test_remis_daje_mokro(monkeypatch):
    s = Sonda(liczba_odczytow=4)
    symuluj_odczyty(monkeypatch, [1, 0, 1, 0])
    assert s.jest_sucho() is False
    s.close()
