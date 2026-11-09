import sqlite3
from datetime import datetime

from app.db import Baza
from scripts.raport import jako_markdown, raport


def t(dzien: int, godzina: int, minuta: int = 0) -> float:
    return datetime(2026, 11, dzien, godzina, minuta).timestamp()  # czas lokalny


def test_raport_dzienny(tmp_path):
    sciezka = str(tmp_path / "test.db")
    Baza(sciezka)
    with sqlite3.connect(sciezka) as db:
        # 1.11: 4 pomiary co minutę, 3 sucho, potem luka 2 h (aplikacja nie działała)
        pomiary = [(t(1, 10, m), m < 3) for m in range(4)] + [(t(1, 12), False)]
        # 2.11: jeden pomiar
        pomiary.append((t(2, 9), True))
        db.executemany("INSERT INTO pomiary (czas, sucho) VALUES (?, ?)", pomiary)
        db.executemany(
            "INSERT INTO podlania (czas, zrodlo, sekundy, czas_pracy_s, blad) VALUES (?,?,?,?,?)",
            [
                (t(1, 10, 1), "automat", 3, 3.0, None),
                (t(1, 11), "reczne", 5, 2.5, None),
                (t(3, 8), "automat", 3, 0.0, "RuntimeError('awaria')"),  # dzień bez pomiarów
            ],
        )

    wiersze = raport(sciezka)

    assert [w["dzien"] for w in wiersze] == ["2026-11-01", "2026-11-02", "2026-11-03"]
    d1, d2, d3 = wiersze
    assert d1 == {
        "dzien": "2026-11-01",
        "pomiary": 5,
        "sucho_proc": 60,
        "przerwy": 1,
        "automat": 1,
        "reczne": 1,
        "czas_pompy": 5.5,
        "bledy": 0,
    }
    assert d2["pomiary"] == 1 and d2["automat"] == 0  # dzień bez podlań: zera, nie brak klucza
    assert d2["przerwy"] == 1  # odstęp od ostatniego pomiaru poprzedniego dnia
    assert d3["pomiary"] == 0 and d3["bledy"] == 1
    assert jako_markdown(wiersze).count("\n") == 4  # nagłówek + separator + 3 dni


def test_raport_pustej_bazy(tmp_path):
    sciezka = str(tmp_path / "test.db")
    Baza(sciezka)
    assert raport(sciezka) == []
