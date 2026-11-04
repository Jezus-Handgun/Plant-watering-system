"""Pompka sterowana przekaźnikiem HW-307 na GPIO27 (przez diodę LED, stan niski = włączona)."""

import time

from gpiozero import OutputDevice

PIN_PRZEKAZNIKA = 27
MAKS_CZAS_S = 10  # twardy limit jednego podlewania (zasada bezpieczeństwa nr 2)


class Pompka:
    def __init__(self, pin: int = PIN_PRZEKAZNIKA):
        # HW-307 przez LED: sterowany stanem niskim. on() = LOW = pompka włączona.
        # Nigdy active_high=True — pompka by się nie wyłączała.
        self._przekaznik = OutputDevice(pin, active_high=False, initial_value=False)

    @property
    def pracuje(self) -> bool:
        return self._przekaznik.is_active

    def podlej(self, sekundy: float) -> float:
        """Włącza pompkę na `sekundy` (0 < s <= MAKS_CZAS_S). Zwraca faktyczny czas pracy."""
        if not 0 < sekundy <= MAKS_CZAS_S:
            raise ValueError(f"Czas podlewania musi być w zakresie (0, {MAKS_CZAS_S}] s")
        start = time.monotonic()
        try:
            self._przekaznik.on()
            time.sleep(sekundy)
        finally:
            # Wyłączenie także przy wyjątku i Ctrl+C.
            self._przekaznik.off()
        return time.monotonic() - start

    def close(self) -> None:
        self._przekaznik.off()
        self._przekaznik.close()
