"""Uruchomienie aplikacji (z katalogu projektu):

    Pi:      uv run python run.py   (na stałe: usługa systemd/podlewanie.service)
    Windows: $env:HARDWARE_MODE="simulation"; uv run python run.py

Panel/API: http://raspi.local:5000 (z Windowsa w symulacji: http://localhost:5000)
"""

import logging
import signal
import sys

from waitress import serve

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
        # waitress: serwer produkcyjny w czystym Pythonie — jeden proces (GPIO może mieć
        # tylko jednego właściciela), żądania obsługiwane wątkami. Na SIGTERM kończy się
        # normalnie (łapie SystemExit), więc finally poniżej zawsze wyłączy pompkę.
        serve(app, host="0.0.0.0", port=5000, threads=4)
    finally:
        app.extensions["sterownik"].zamknij()
        logging.getLogger("automat").info("Koniec pracy aplikacji")


if __name__ == "__main__":
    main()
