"""Kalibracja pompki: jedno podlanie o zadanym czasie, wynik (ml) mierzysz miarką.

Uruchomienie na Pi (z katalogu projektu):
    uv run python -m scripts.kalibracja_pompki 5
"""

import signal
import sys

from hardware.pump import MAKS_CZAS_S, Pompka


def _zakoncz(signum, _frame):
    # SIGHUP (zerwane SSH) / SIGTERM domyślnie zabijają proces bez `finally`;
    # SystemExit sprawia, że `finally` w podlej() wyłączy pompkę.
    sys.exit(f"Przerwano sygnałem {signum}")


def main() -> None:
    sekundy = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
    if not 0 < sekundy <= MAKS_CZAS_S:
        sys.exit(f"Czas musi być w zakresie (0, {MAKS_CZAS_S}] s")

    odp = input("Pompka w wodzie, wąż skierowany do naczynia? [t/N] ")
    if odp.strip().lower() != "t":
        sys.exit("Przerwano — pompka nie została włączona.")

    signal.signal(signal.SIGTERM, _zakoncz)
    signal.signal(signal.SIGHUP, _zakoncz)

    pompka = Pompka()
    try:
        czas = pompka.podlej(sekundy)
        print(f"Pompka pracowała {czas:.2f} s. Zmierz ilość wody i zapisz w docs/testy.md.")
    finally:
        pompka.close()


if __name__ == "__main__":
    main()
