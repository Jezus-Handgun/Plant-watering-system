"""Pompka sterowana przekaźnikiem HW-307 na GPIO27 (przez diodę LED, stan niski = włączona)."""

import threading
import time

from gpiozero import OutputDevice

PIN_PRZEKAZNIKA = 27
MAKS_CZAS_S = 10  # twardy limit jednego podlewania (zasada bezpieczeństwa nr 2)


class Pompka:
    def __init__(self, pin: int = PIN_PRZEKAZNIKA):
        # HW-307 przez LED: sterowany stanem niskim. on() = LOW = pompka włączona.
        # Nigdy active_high=True — pompka by się nie wyłączała.
        self._przekaznik = OutputDevice(pin, active_high=False, initial_value=False)
        # Event zamiast time.sleep: oczekiwanie da się przerwać z innego wątku (/api/stop).
        self._przerwij = threading.Event()

    @property
    def pracuje(self) -> bool:
        return self._przekaznik.is_active

    def podlej(self, sekundy: float) -> float:
        """Włącza pompkę na `sekundy` (0 < s <= MAKS_CZAS_S). Zwraca faktyczny czas pracy."""
        if not 0 < sekundy <= MAKS_CZAS_S:
            raise ValueError(f"Czas podlewania musi być w zakresie (0, {MAKS_CZAS_S}] s")
        self._przerwij.clear()
        start = time.monotonic()
        try:
            self._przekaznik.on()
            self._przerwij.wait(sekundy)
        finally:
            # Wyłączenie także przy wyjątku i Ctrl+C.
            self._przekaznik.off()
        return time.monotonic() - start

    def zatrzymaj(self) -> None:
        """Natychmiast przerywa trwające podlewanie (bezpieczne z dowolnego wątku)."""
        self._przerwij.set()
        self._przekaznik.off()

    def close(self) -> None:
        self._przekaznik.off()
        self._przekaznik.close()
