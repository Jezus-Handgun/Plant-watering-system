import pytest
from gpiozero import Device

from hardware import pump
from hardware.pump import MAKS_CZAS_S, PIN_PRZEKAZNIKA, Pompka


@pytest.fixture
def pompka():
    p = Pompka()
    yield p
    p.close()


def stan_pinu():
    return Device.pin_factory.pin(PIN_PRZEKAZNIKA).state


def test_po_utworzeniu_wylaczona_pin_wysoki(pompka):
    # Przekaźnik sterowany stanem niskim: wyłączony = HIGH.
    assert not pompka.pracuje
    assert stan_pinu() is True


def test_podlej_wlacza_stanem_niskim_i_wylacza(pompka, monkeypatch):
    stany = []
    monkeypatch.setattr(pump.time, "sleep", lambda _s: stany.append(stan_pinu()))
    pompka.podlej(3)
    assert stany == [False]  # w trakcie: LOW = pompka włączona
    assert stan_pinu() is True  # po: HIGH = wyłączona


def test_przerwanie_w_trakcie_wylacza_pompke(pompka, monkeypatch):
    def przerwij(_s):
        raise KeyboardInterrupt

    monkeypatch.setattr(pump.time, "sleep", przerwij)
    with pytest.raises(KeyboardInterrupt):
        pompka.podlej(3)
    assert not pompka.pracuje


@pytest.mark.parametrize("sekundy", [0, -1, MAKS_CZAS_S + 0.1])
def test_czas_poza_limitem_odrzucony(pompka, sekundy):
    with pytest.raises(ValueError):
        pompka.podlej(sekundy)
    assert not pompka.pracuje
