"""Uruchomienie aplikacji (z katalogu projektu):

    Pi:      uv run python run.py
    Windows: $env:HARDWARE_MODE="simulation"; uv run python run.py

Panel/API: http://raspi.local:5000 (z Windowsa w symulacji: http://localhost:5000)
"""

import logging
import signal
import sys

from app import create_app


def _zakoncz(signum, _frame):
    # SIGTERM (systemctl stop) / SIGHUP (zerwane SSH) → SystemExit, żeby zadziałało finally.
    sys.exit(f"Zatrzymano sygnałem {signum}")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler("automat.log", encoding="utf-8"), logging.StreamHandler()],
    )
    signal.signal(signal.SIGTERM, _zakoncz)
    if hasattr(signal, "SIGHUP"):  # brak na Windowsie
        signal.signal(signal.SIGHUP, _zakoncz)

    app = create_app()
    try:
        # Jeden proces (GPIO może mieć tylko jednego właściciela), wątki dla żądań.
        # shortcut: serwer deweloperski Werkzeuga; wybór serwera dla usługi systemd w etapie 7.
        app.run(host="0.0.0.0", port=5000, threaded=True, use_reloader=False)
    finally:
        app.extensions["sterownik"].zamknij()
        logging.getLogger("automat").info("Koniec pracy aplikacji")


if __name__ == "__main__":
    main()
