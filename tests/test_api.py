"""Testy API przez app.test_client() — tryb symulacji, baza w katalogu tymczasowym."""

import threading
import time

import pytest

from app import create_app
from hardware.fake import ustaw_sonde


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {"BAZA": str(tmp_path / "test.db"), "HARDWARE_MODE": "simulation", "URUCHOM_AUTOMAT": False}
    )
    yield app
    app.extensions["sterownik"].zamknij()


@pytest.fixture
def klient(app):
    return app.test_client()


@pytest.fixture
def sterownik(app):
    return app.extensions["sterownik"]


def test_panel_i_pliki_statyczne(klient):
    strona = klient.get("/")
    assert strona.status_code == 200
    html = strona.get_data(as_text=True)
    assert "Panel sterowania" in html
    assert "http" not in html.replace("http://www.w3.org", "")  # bez zasobów z internetu
    for plik in ("/static/panel.css", "/static/panel.js"):
        odp = klient.get(plik)
        assert odp.status_code == 200
        odp.close()


def test_status(klient, sterownik):
    ustaw_sonde(sucho=True)
    sterownik.krok()
    odp = klient.get("/api/status")
    assert odp.status_code == 200
    assert odp.headers["Cache-Control"] == "no-store"
    dane = odp.get_json()
    assert dane["pomiar"]["sucho"] is True
    assert dane["pompka_pracuje"] is False
    assert abs(dane["czas_serwera"] - time.time()) < 5
    assert dane["ostatnia_decyzja"] == "przerwa"


def test_status_czyta_sonde_na_zywo_bez_kroku_automatu(klient):
    """Panel pyta co 2 s — zmiana stanu sondy widoczna od razu, nie po minutowym cyklu."""
    ustaw_sonde(sucho=False)
    assert klient.get("/api/status").get_json()["pomiar"]["sucho"] is False
    ustaw_sonde(sucho=True)
    assert klient.get("/api/status").get_json()["pomiar"]["sucho"] is True


@pytest.mark.parametrize(
    "tresc",
    [
        None,
        {},
        {"sekundy": 0},
        {"sekundy": 11},
        {"sekundy": "3"},
        {"sekundy": True},
        {"sekundy": 2.5},
        [3],
    ],
)
def test_water_odrzuca_niepoprawne_dane(klient, sterownik, tresc):
    odp = klient.post("/api/water", json=tresc)
    assert odp.status_code == 400
    assert not sterownik.pompka.pracuje


def test_water_stop_i_zajeta_pompka(klient, sterownik):
    odp = klient.post("/api/water", json={"sekundy": 10})
    assert odp.status_code == 202
    while not sterownik.pompka.pracuje:  # podlewanie startuje w osobnym wątku
        pass
    assert klient.post("/api/water", json={"sekundy": 1}).status_code == 409
    assert klient.post("/api/stop").status_code == 200
    with sterownik._blokada_pompki:  # czekamy, aż wątek podlewania zapisze wynik
        pass
    assert not sterownik.pompka.pracuje
    podlanie = klient.get("/api/history/podlania").get_json()["elementy"][0]
    assert podlanie["zrodlo"] == "reczne"
    assert podlanie["czas_pracy_s"] < 1  # przerwane przez /api/stop zamiast 10 s


def test_reczne_podlanie_wstrzymuje_automat(klient, sterownik, monkeypatch):
    zakonczone = threading.Event()
    monkeypatch.setattr(sterownik.pompka._przerwij, "wait", lambda _s: zakonczone.set())
    sterownik.automat._ostatnie_podlanie = -1e9  # przerwa po starcie już minęła
    klient.post("/api/water", json={"sekundy": 2})
    zakonczone.wait(2)
    ustaw_sonde(sucho=True)
    assert sterownik.krok() == "przerwa"


def test_ustawienia_odczyt_i_zmiana(klient, sterownik):
    assert klient.get("/api/settings").get_json()["limit_dobowy"] == 5
    odp = klient.put("/api/settings", json={"limit_dobowy": 3, "automat_wlaczony": False})
    assert odp.status_code == 200
    assert odp.get_json()["limit_dobowy"] == 3
    assert sterownik.automat.limit_dobowy == 3
    assert klient.get("/api/settings").get_json()["automat_wlaczony"] is False


@pytest.mark.parametrize(
    "tresc",
    [
        None,
        {},
        {"nieznane": 1},
        {"przerwa_min": 14},
        {"czas_podlewania_s": 11},
        {"limit_dobowy": True},
        {"automat_wlaczony": 1},
        {"limit_dobowy": 3, "zle": 1},
    ],
)
def test_ustawienia_odrzuca_niepoprawne(klient, tresc):
    assert klient.put("/api/settings", json=tresc).status_code == 400
    assert klient.get("/api/settings").get_json()["limit_dobowy"] == 5  # nic nie zapisano


def test_historia_parametry(klient, sterownik):
    for _ in range(3):
        sterownik.krok()
    dane = klient.get("/api/history/pomiary?limit=2").get_json()
    assert len(dane["elementy"]) == 2
    assert klient.get("/api/history/ustawienia").status_code == 404
    assert klient.get("/api/history/pomiary?limit=0").status_code == 400
    assert klient.get("/api/history/pomiary?limit=abc").status_code == 400
