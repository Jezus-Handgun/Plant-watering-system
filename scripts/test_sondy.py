"""Test sondy na Pi: co sekundę odczyt surowy i decyzja większościowa. Ctrl+C kończy.

Uruchomienie (z katalogu projektu):
    uv run python -m scripts.test_sondy
"""

import time

from hardware.sensor import Sonda


def opis(sucho: bool) -> str:
    return "SUCHO" if sucho else "MOKRO"


def main() -> None:
    sonda = Sonda()
    try:
        while True:
            print(f"surowy: {opis(sonda.odczyt_surowy())} | większość: {opis(sonda.jest_sucho())}")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sonda.close()


if __name__ == "__main__":
    main()
