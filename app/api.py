"""Endpointy /api/... — granica zaufania: każde wejście z sieci jest tu sprawdzane."""

from flask import Blueprint, current_app, request

from app.db import TABELE_HISTORII
from hardware.pump import MAKS_CZAS_S

api = Blueprint("api", __name__, url_prefix="/api")

# klucz → (typ, min, max); bool bez zakresu
ZAKRESY_USTAWIEN = {
    "automat_wlaczony": (bool, None, None),
    "czas_podlewania_s": (int, 1, MAKS_CZAS_S),
    "przerwa_min": (int, 15, 24 * 60),  # zasada bezpieczeństwa nr 3: min. 15 min
    "limit_dobowy": (int, 1, 20),
}


def sterownik():
    return current_app.extensions["sterownik"]


def blad(komunikat: str, kod: int = 400):
    return {"blad": komunikat}, kod


def liczba_calkowita(wartosc, od: int, do: int) -> bool:
    # bool jest podklasą int w Pythonie — True nie może przejść jako 1.
    return type(wartosc) is int and od <= wartosc <= do


@api.after_request
def bez_cache(odpowiedz):
    odpowiedz.headers["Cache-Control"] = "no-store"  # stan ma być zawsze aktualny
    return odpowiedz


@api.get("/status")
def status():
    return sterownik().status()


@api.post("/water")
def water():
    dane = request.get_json(silent=True)
    if not isinstance(dane, dict) or not liczba_calkowita(dane.get("sekundy"), 1, MAKS_CZAS_S):
        return blad(f'Podaj JSON {{"sekundy": liczba całkowita 1–{MAKS_CZAS_S}}}')
    if not sterownik().podlej_recznie(dane["sekundy"]):
        return blad("Pompka już pracuje", 409)
    return {"status": "rozpoczęto", "sekundy": dane["sekundy"]}, 202


@api.post("/stop")
def stop():
    sterownik().zatrzymaj_pompke()
    return {"pompka_pracuje": False}


@api.get("/settings")
def get_settings():
    return sterownik().ustawienia


@api.put("/settings")
def put_settings():
    dane = request.get_json(silent=True)
    if not isinstance(dane, dict) or not dane:
        return blad("Podaj JSON z co najmniej jednym ustawieniem")
    for klucz, wartosc in dane.items():
        if klucz not in ZAKRESY_USTAWIEN:
            return blad(f"Nieznane ustawienie: {klucz}")
        typ, od, do = ZAKRESY_USTAWIEN[klucz]
        poprawne = type(wartosc) is bool if typ is bool else liczba_calkowita(wartosc, od, do)
        if not poprawne:
            opis = "true/false" if typ is bool else f"liczba całkowita {od}–{do}"
            return blad(f"{klucz}: oczekiwano {opis}")
    return sterownik().zmien_ustawienia(dane)


@api.get("/history/<rodzaj>")
def history(rodzaj):
    if rodzaj not in TABELE_HISTORII:
        return blad(f"Nieznana historia: {rodzaj} (dostępne: {', '.join(TABELE_HISTORII)})", 404)
    try:
        limit = int(request.args.get("limit", 50))
        przed = request.args.get("przed_id")
        przed = int(przed) if przed is not None else None
    except ValueError:
        return blad("limit i przed_id muszą być liczbami całkowitymi")
    if not 1 <= limit <= 500 or (przed is not None and przed < 1):
        return blad("limit: 1–500, przed_id: ≥ 1")
    return current_app.extensions["baza"].historia(rodzaj, limit, przed)
