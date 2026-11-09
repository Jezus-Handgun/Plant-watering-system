"""Raport z testów długoterminowych: podsumowanie każdego dnia z bazy SQLite.

Drukuje tabelę Markdown do wklejenia w docs/testy.md. Baza otwierana tylko do odczytu,
więc raport można robić przy działającej usłudze. Uruchomienie na Pi (z katalogu projektu):
    ~/.local/bin/uv run python -m scripts.raport
"""

import sqlite3
import sys

DOMYSLNA_BAZA = "instance/podlewanie.db"
LUKA_S = 5 * 60  # dłuższy odstęp między pomiarami = aplikacja nie działała

ZAPYTANIE_POMIARY = """
WITH p AS (
    SELECT date(czas, 'unixepoch', 'localtime') AS dzien, sucho,
           czas - LAG(czas) OVER (ORDER BY czas) AS odstep
    FROM pomiary
)
SELECT dzien, COUNT(*) AS pomiary, SUM(sucho) AS suche, SUM(odstep > ?) AS przerwy
FROM p GROUP BY dzien
"""

ZAPYTANIE_PODLANIA = """
SELECT date(czas, 'unixepoch', 'localtime') AS dzien,
       SUM(zrodlo = 'automat') AS automat, SUM(zrodlo = 'reczne') AS reczne,
       SUM(COALESCE(czas_pracy_s, 0)) AS czas_pompy, SUM(blad IS NOT NULL) AS bledy
FROM podlania GROUP BY dzien
"""

KOLUMNY = [
    ("dzien", "Dzień"),
    ("pomiary", "Pomiary"),
    ("sucho_proc", "Sucho [%]"),
    ("przerwy", "Przerwy w pracy"),
    ("automat", "Podlania automatu"),
    ("reczne", "Podlania ręczne"),
    ("czas_pompy", "Praca pompy [s]"),
    ("bledy", "Błędy"),
]


def raport(sciezka: str) -> list[dict]:
    db = sqlite3.connect(f"file:{sciezka}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        dni: dict[str, dict] = {}
        for w in db.execute(ZAPYTANIE_POMIARY, (LUKA_S,)):
            dni[w["dzien"]] = {
                "pomiary": w["pomiary"],
                "sucho_proc": round(100 * w["suche"] / w["pomiary"]),
                "przerwy": w["przerwy"] or 0,
            }
        for w in db.execute(ZAPYTANIE_PODLANIA):
            dni.setdefault(w["dzien"], {}).update(
                automat=w["automat"],
                reczne=w["reczne"],
                czas_pompy=round(w["czas_pompy"], 1),
                bledy=w["bledy"],
            )
    finally:
        db.close()
    puste = {k: 0 for k, _ in KOLUMNY[1:]}
    return [{"dzien": d} | puste | dni[d] for d in sorted(dni)]


def jako_markdown(wiersze: list[dict]) -> str:
    linie = [
        "| " + " | ".join(n for _, n in KOLUMNY) + " |",
        "|" + "---|" * len(KOLUMNY),
    ]
    linie += ["| " + " | ".join(str(w[k]) for k, _ in KOLUMNY) + " |" for w in wiersze]
    return "\n".join(linie)


def main() -> None:
    sciezka = sys.argv[1] if len(sys.argv) > 1 else DOMYSLNA_BAZA
    wiersze = raport(sciezka)
    print(jako_markdown(wiersze) if wiersze else "Baza nie zawiera jeszcze danych.")


if __name__ == "__main__":
    main()
