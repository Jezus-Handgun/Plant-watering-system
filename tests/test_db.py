import sqlite3

import pytest

from app.db import DOMYSLNE_USTAWIENIA, WERSJA_SCHEMATU, Baza


@pytest.fixture
def sciezka(tmp_path):
    return str(tmp_path / "test.db")


def test_migracja_tworzy_schemat_i_jest_powtarzalna(sciezka):
    Baza(sciezka)
    Baza(sciezka)  # drugi start nie może próbować tworzyć tabel ponownie
    with sqlite3.connect(sciezka) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == WERSJA_SCHEMATU


def test_baza_z_nowszej_wersji_odrzucona(sciezka):
    with sqlite3.connect(sciezka) as db:
        db.execute(f"PRAGMA user_version = {WERSJA_SCHEMATU + 1}")
    with pytest.raises(RuntimeError):
        Baza(sciezka)


def test_ustawienia_domyslne_i_zapis(sciezka):
    baza = Baza(sciezka)
    assert baza.ustawienia() == DOMYSLNE_USTAWIENIA
    baza.zapisz_ustawienia({"limit_dobowy": 3})
    baza.zapisz_ustawienia({"limit_dobowy": 4, "automat_wlaczony": False})
    assert baza.ustawienia() == DOMYSLNE_USTAWIENIA | {"limit_dobowy": 4, "automat_wlaczony": False}


def test_historia_stronicowana_od_najnowszych(sciezka):
    baza = Baza(sciezka)
    for i in range(5):
        baza.zapisz_pomiar(i % 2 == 0)
    strona1 = baza.historia("pomiary", limit=2)
    assert [w["id"] for w in strona1["elementy"]] == [5, 4]
    strona2 = baza.historia("pomiary", limit=2, przed_id=strona1["nastepna_strona_przed_id"])
    assert [w["id"] for w in strona2["elementy"]] == [3, 2]
    strona3 = baza.historia("pomiary", limit=2, przed_id=strona2["nastepna_strona_przed_id"])
    assert [w["id"] for w in strona3["elementy"]] == [1]
    assert strona3["nastepna_strona_przed_id"] is None


def test_historia_odrzuca_nieznana_tabele(sciezka):
    with pytest.raises(ValueError):
        Baza(sciezka).historia("ustawienia; DROP TABLE pomiary", 10)
