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
            # flush: przez SSH bez -t wydruk jest buforowany; po zerwaniu połączenia
            # zapis od razu rzuca BrokenPipeError, więc skrypt nie zostaje z zajętym pinem.
            surowy, wiekszosc = opis(sonda.odczyt_surowy()), opis(sonda.jest_sucho())
            print(f"surowy: {surowy} | większość: {wiekszosc}", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        sonda.close()


if __name__ == "__main__":
    main()
