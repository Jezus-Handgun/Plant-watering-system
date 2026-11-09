"""Fabryka aplikacji Flask: create_app() składa sprzęt, bazę, sterownik i endpointy."""

import os

from flask import Flask, render_template

from app.api import api
from app.controller import Sterownik
from app.db import Baza
from hardware.fake import wlacz_symulacje
from hardware.pump import Pompka
from hardware.sensor import Sonda


def create_app(konfiguracja: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        BAZA=os.path.join(app.instance_path, "podlewanie.db"),
        HARDWARE_MODE=os.environ.get("HARDWARE_MODE", "real"),
        ODSTEP_POMIARU_S=60,
        URUCHOM_AUTOMAT=True,  # testy wyłączają wątek i wołają krok() ręcznie
    )
    app.config.update(konfiguracja or {})
    app.json.ensure_ascii = False  # polskie znaki w JSON zamiast ę

    tryb = app.config["HARDWARE_MODE"]
    if tryb == "simulation":
        wlacz_symulacje()
    elif tryb != "real":
        raise ValueError(f"Nieznany HARDWARE_MODE={tryb!r} (dozwolone: real, simulation)")

    os.makedirs(os.path.dirname(app.config["BAZA"]), exist_ok=True)
    baza = Baza(app.config["BAZA"])
    sterownik = Sterownik(Sonda(), Pompka(), baza)
    app.extensions["baza"] = baza
    app.extensions["sterownik"] = sterownik
    app.register_blueprint(api)

    @app.get("/")
    def panel():
        return render_template("index.html")

    if app.config["URUCHOM_AUTOMAT"]:
        sterownik.start(app.config["ODSTEP_POMIARU_S"])
    return app
