"""Tryb symulacji: atrapa pinów gpiozero (MockFactory) zamiast prawdziwego GPIO.

Klasy Sonda i Pompka działają bez zmian — podmieniana jest tylko warstwa pinów,
więc testy sprawdzają prawdziwy kod (łącznie z logiką active_high=False).
"""

from gpiozero import Device
from gpiozero.pins.mock import MockFactory

from hardware.sensor import PIN_SONDY


def wlacz_symulacje() -> None:
    """Wywołać przed utworzeniem Sondy/Pompki."""
    Device.pin_factory = MockFactory()


def ustaw_sonde(sucho: bool) -> None:
    """Symuluje stan wyjścia DO sondy (1 = sucho, 0 = mokro)."""
    pin = Device.pin_factory.pin(PIN_SONDY)
    if sucho:
        pin.drive_high()
    else:
        pin.drive_low()
