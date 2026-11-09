"""SQLite: schemat, migracje i zapytania.

Każda operacja otwiera krótkie, własne połączenie — dzięki temu z bazy mogą korzystać
jednocześnie wątek automatu i wątki obsługujące żądania HTTP (połączenia sqlite3
nie wolno współdzielić między wątkami).

Czas zapisywany jako liczba sekund od 1970-01-01 UTC (time.time()):
proste porównania w SQL, a w podglądzie bazy: datetime(czas, 'unixepoch', 'localtime').
"""

import json
import sqlite3
import time
from contextlib import contextmanager

WERSJA_SCHEMATU = 1

SCHEMAT_V1 = """
CREATE TABLE pomiary (
    id    INTEGER PRIMARY KEY,
    czas  REAL    NOT NULL,
    sucho INTEGER NOT NULL CHECK (sucho IN (0, 1))
);
CREATE TABLE podlania (
    id           INTEGER PRIMARY KEY,
    czas         REAL    NOT NULL,
    zrodlo       TEXT    NOT NULL CHECK (zrodlo IN ('automat', 'reczne')),
    sekundy      REAL    NOT NULL,      -- zadany czas pracy
    czas_pracy_s REAL,                  -- faktyczny (krótszy po /api/stop); NULL = w trakcie
    blad         TEXT
);
CREATE INDEX podlania_czas ON podlania (czas);
CREATE TABLE ustawienia (
    klucz   TEXT PRIMARY KEY,
    wartosc TEXT NOT NULL               -- JSON
);
"""

DOMYSLNE_USTAWIENIA = {
    "automat_wlaczony": True,
    "czas_podlewania_s": 3,
    "przerwa_min": 15,
    "limit_dobowy": 5,
}

TABELE_HISTORII = ("pomiary", "podlania")


class Baza:
    def __init__(self, sciezka: str):
        self.sciezka = sciezka
        self._migruj()

    @contextmanager
    def _polaczenie(self):
        db = sqlite3.connect(self.sciezka, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:  # commit przy sukcesie, rollback przy wyjątku
                yield db
        finally:
            db.close()

    def _migruj(self) -> None:
        """Wersja schematu w PRAGMA user_version; kolejne migracje: `if wersja < N`."""
        with self._polaczenie() as db:
            # WAL: odczyty (panel) nie blokują zapisu (automat) i odwrotnie.
            db.execute("PRAGMA journal_mode=WAL")
            wersja = db.execute("PRAGMA user_version").fetchone()[0]
            if wersja > WERSJA_SCHEMATU:
                raise RuntimeError("Baza pochodzi z nowszej wersji aplikacji")
            if wersja < 1:
                # Schemat i numer wersji w jednej transakcji: awaria w połowie nic nie zmienia.
                db.executescript(f"BEGIN; {SCHEMAT_V1} PRAGMA user_version = 1; COMMIT;")

    # --- pomiary ---

    def zapisz_pomiar(self, sucho: bool) -> None:
        with self._polaczenie() as db:
            db.execute("INSERT INTO pomiary (czas, sucho) VALUES (?, ?)", (time.time(), sucho))

    # --- podlania ---

    def zacznij_podlanie(self, zrodlo: str, sekundy: float) -> int:
        with self._polaczenie() as db:
            kursor = db.execute(
                "INSERT INTO podlania (czas, zrodlo, sekundy) VALUES (?, ?, ?)",
                (time.time(), zrodlo, sekundy),
            )
            return kursor.lastrowid

    def zakoncz_podlanie(self, id_: int, czas_pracy_s: float, blad: str | None) -> None:
        with self._polaczenie() as db:
            db.execute(
                "UPDATE podlania SET czas_pracy_s = ?, blad = ? WHERE id = ?",
                (czas_pracy_s, blad, id_),
            )

    def czasy_podlan_automatu(self, od: float) -> list[float]:
        with self._polaczenie() as db:
            wiersze = db.execute(
                "SELECT czas FROM podlania WHERE zrodlo = 'automat' AND czas >= ? ORDER BY czas",
                (od,),
            )
            return [w["czas"] for w in wiersze]

    def ostatnie_podlanie(self) -> dict | None:
        with self._polaczenie() as db:
            w = db.execute("SELECT * FROM podlania ORDER BY id DESC LIMIT 1").fetchone()
            return dict(w) if w else None

    # --- historia (stronicowanie po id: stabilne, gdy w trakcie dochodzą nowe wiersze) ---

    def historia(self, tabela: str, limit: int, przed_id: int | None = None) -> dict:
        if tabela not in TABELE_HISTORII:  # nazwy tabeli nie da się przekazać parametrem SQL
            raise ValueError(f"Nieznana tabela: {tabela}")
        with self._polaczenie() as db:
            wiersze = db.execute(
                f"SELECT * FROM {tabela} WHERE id < ? ORDER BY id DESC LIMIT ?",
                (przed_id if przed_id is not None else 2**63 - 1, limit),
            ).fetchall()
        elementy = [dict(w) for w in wiersze]
        nastepna = elementy[-1]["id"] if len(elementy) == limit else None
        return {"elementy": elementy, "nastepna_strona_przed_id": nastepna}

    # --- ustawienia ---

    def ustawienia(self) -> dict:
        with self._polaczenie() as db:
            zapisane = {
                w["klucz"]: json.loads(w["wartosc"])
                for w in db.execute("SELECT klucz, wartosc FROM ustawienia")
            }
        return DOMYSLNE_USTAWIENIA | {k: v for k, v in zapisane.items() if k in DOMYSLNE_USTAWIENIA}

    def zapisz_ustawienia(self, zmiany: dict) -> None:
        with self._polaczenie() as db:
            db.executemany(
                "INSERT INTO ustawienia (klucz, wartosc) VALUES (?, ?) "
                "ON CONFLICT (klucz) DO UPDATE SET wartosc = excluded.wartosc",
                [(k, json.dumps(v)) for k, v in zmiany.items()],
            )
