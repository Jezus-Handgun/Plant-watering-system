"""Sonda wilgotności HW-080 + komparator HW-103, wyjście cyfrowe DO na GPIO17."""

import time

from gpiozero import DigitalInputDevice

PIN_SONDY = 17


class Sonda:
    def __init__(self, pin: int = PIN_SONDY, liczba_odczytow: int = 5, odstep_s: float = 0.1):
        # DO: 1 = sucho, 0 = mokro (sprawdzone testem). Pull-down: odłączony przewód DO
        # czyta się jako MOKRO, więc awaria sondy nie powoduje podlewania.
        self._wejscie = DigitalInputDevice(pin, pull_up=False)
        self.liczba_odczytow = liczba_odczytow
        self.odstep_s = odstep_s

    def odczyt_surowy(self) -> bool:
        """Pojedynczy odczyt: True = sucho."""
        return self._wejscie.is_active

    def jest_sucho(self) -> bool:
        """Decyzja większościowa z kilku odczytów (blisko progu odczyt przeskakuje).

        Wymaga ścisłej większości odczytów SUCHO — remis daje MOKRO (bez podlewania).
        """
        suche = 0
        for i in range(self.liczba_odczytow):
            if i:
                time.sleep(self.odstep_s)
            suche += self.odczyt_surowy()
        return suche > self.liczba_odczytow / 2

    def close(self) -> None:
        self._wejscie.close()
