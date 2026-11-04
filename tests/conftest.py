import pytest
from gpiozero import Device

from hardware.fake import wlacz_symulacje


@pytest.fixture(autouse=True)
def atrapa_gpio():
    """Każdy test dostaje świeżą atrapę pinów — bez Raspberry Pi."""
    wlacz_symulacje()
    yield
    Device.pin_factory.reset()
