# Wyniki testów i kalibracji

Materiał do rozdziału z badaniami. Każdy wpis: data, co testowano, jak, wynik.

## 2026-11-04 — Etap 1: sonda wilgotności (HW-080 + HW-103)

- **Podłączenie:** VCC → pin 1 (3,3 V), GND → pin 6, DO → pin 11 (GPIO17). AO niepodłączone.
- **Wynik:** działa. Logika wyjścia DO:
  - **0 = mokro** (zapala się druga dioda na HW-103),
  - **1 = sucho**.
- **Obserwacja:** przy wilgotności blisko progu odczyt przeskakuje między SUCHO a MOKRO. Wniosek: w kodzie kilka odczytów i decyzja większościowa.

## 2026-11-04 — Etap 1b: przekaźnik HW-307

### Próba 1: IN bezpośrednio do GPIO27

- **Wynik:** niepoprawny. Stan niski włącza przekaźnik, ale stan wysoki 3,3 V **nie wyłącza** go — wyłączał się dopiero po zwolnieniu pinu (pin jako wejście).
- **Przyczyna:** moduł sterowany stanem niskim, zaprojektowany pod logikę 5 V.

### Próba 2: IN przez czerwoną LED (katoda do GPIO27, anoda do IN)

- **Kod:** `OutputDevice(27, active_high=False, initial_value=False)`.
- **Wynik:** działa.
  - `on()` → przekaźnik klika, świeci zielona dioda modułu i czerwona LED,
  - `off()` → wszystko gaśnie.

## 2026-11-04 — Etap 1c: zachowanie przekaźnika podczas restartu Pi

- **Cel:** sprawdzić, czy przekaźnik nie włącza się samoczynnie podczas startu systemu (zanim program przejmie GPIO27). Gdyby się włączał, pompka ruszałaby przy każdym starcie Pi.
- **Metoda:** `sudo reboot`, obserwacja zielonej diody modułu HW-307 i czerwonej LED w torze IN przez cały czas startu.
- **Wynik:** poprawny — żadna z diod się nie zapaliła, przekaźnik nie kliknął.
- **Wyjaśnienie:** podczas startu GPIO27 jest wejściem (stan wysokiej impedancji), więc przez LED nie płynie prąd i przekaźnik pozostaje wyłączony. Potwierdza to założenie z decyzji 4 i 5 (`docs/decyzje.md`).

## 2026-11-04 — Etap 3: moduły `hardware/` na Pi

- **Testy jednostkowe na atrapach** (`uv run pytest`): 12/12 zaliczonych na komputerze (Windows) i na Pi.
- **Sonda przez nowy moduł** (`uv run python -m scripts.test_sondy`, 5 s): odczyt surowy i decyzja większościowa zgodne — SUCHO przez cały czas trwania testu.

## 2026-11-09 — Etap 4: automat podlewania

- **Testy jednostkowe** (`uv run pytest`): 18/18 na komputerze i na Pi. Fałszywy zegar sprawdza przerwę 15 min, limit 5 podlań/24 h i jego odnowienie oraz zachowanie przy awarii pompki.
- **Uruchomienie na Pi** (`uv run python -m app.controller`, tryb `real`, 5 s, pompka niepodłączona):
  - sonda: SUCHO → decyzja `przerwa` (zgodnie z założeniem: po starcie automat najpierw odczekuje przerwę),
  - po przerwaniu (SIGINT) wykonało się `finally` — wpis „Koniec pracy automatu” w `automat.log`.

## 2026-11-09 — Etap 2 (częściowo): sterowanie przekaźnikiem skryptem kalibracji

- **Polecenie:** `scripts/kalibracja_pompki.py 2` (po potwierdzeniu: pompka w wodzie, wąż w naczyniu).
- **Wynik:** przekaźnik włączony przez **2,00 s**, czerwona LED świeciła i zgasła; `vcgencmd get_throttled` przed i po = `0x0` (brak spadków napięcia).
- **Ograniczenie:** pompka była wpięta bezpośrednio do portu USB Pi, poza torem przekaźnika — **nie** sprawdzono sterowania pompką ani wydajności (ml/s). Zalecono odłączenie pompki od USB; etap czeka na moduł z gniazdem USB-A (decyzja 21).

## 2026-11-09 — Etap 5: backend Flask + SQLite

- **Testy jednostkowe** (`uv run pytest`): 50/50 na komputerze i na Pi — logika automatu, sterownik z bazą, migracje i stronicowanie bazy, API (walidacja danych, `202`/`409`, przerwanie podlewania przez `/api/stop`).
- **Symulacja na Windowsie** (`HARDWARE_MODE=simulation`, prawdziwy serwer HTTP): `POST /api/water` 2 s → pompka pracuje, `POST /api/stop` → zatrzymana po **0,76 s**, w historii `czas_pracy_s = 0,76`; `PUT /api/settings` z przerwą 5 min odrzucone (`400`).
- **Pi, tryb `real`** (`uv run python run.py`, pompka niepodłączona, bez `/api/water`):
  - zapytania z komputera przez sieć (`http://raspi.local:5000`): `/api/status`, `/api/settings`, `/api/history/pomiary` → `200`, w historii pomiary z sondy zapisane w SQLite na Pi,
  - automat: pomiar co 60 s, sucho → decyzja `przerwa` (przerwa po starcie),
  - `SIGTERM` (jak `systemctl stop`) → czyste zamknięcie, wpis „Koniec pracy aplikacji”.

## 2026-11-09 — Etap 6: panel webowy

- **Testy jednostkowe:** 51/51 (nowy: strona `/` i pliki statyczne, brak zasobów z internetu).
- **Podgląd w przeglądarce** (Chrome bez okna, symulacja, baza z 24 h przykładowych danych):
  - szerokość 1280 px: trzy karty w rzędzie, wykres 24 h z pasami sucho/mokro, luka 30 min w danych widoczna jako przerwa, 5 podlań w tabeli,
  - szerokość 390 px (telefon): karty jedna pod drugą, wykres przewijany w poziomie z czytelnymi napisami, tabela mieści się.
- **Pi, tryb `real`:** panel otwarty z komputera pod `http://raspi.local:5000` — plakietka „Połączono z Pi”, stan SUCHO z prawdziwej sondy, decyzja „trwa przerwa na wsiąknięcie”, na wykresie pomiary zapisane w SQLite na Pi; aplikacja zatrzymana sygnałem SIGTERM.
- **Nie sprawdzono w przeglądarce:** kliknięć „Podlej”/„Zatrzymaj”/„Zapisz” (te same endpointy są pokryte testami API).

## 2026-11-09 — Obserwacja: przeskok zegara Pi po starcie

- Pi uruchomione 2026-11-09 ok. 18:10 (po kilku dniach wyłączenia).
- Do 18:11:23 zegar systemowy pokazywał **2026-11-04 23:14** (czas zapisany przy poprzednim wyłączeniu — Pi nie ma zegara RTC). Usługi startujące w tym czasie mają w dzienniku datę 4 listopada.
- O 18:11:23 `systemd-timesyncd` zsynchronizował czas z serwerem NTP — **przeskok o ok. 4 dni i 19 h** do przodu.
- Wniosek: odmierzanie przerw zegarem systemowym byłoby błędne; potwierdza decyzje 18, 26 i 39.

## 2026-11-09 — Etap 7: serwer, usługa, raport

- **Testy jednostkowe:** 53/53 (nowe: raport dzienny, `czas_serwera` w statusie).
- **Pi, `run.py` z serwerem `waitress`:** panel `200` z komputera, status z prawdziwą sondą; `SIGTERM` → wpis „Koniec pracy aplikacji” w mniej niż 1 s, proces zakończony.
- **Raport** (`python -m scripts.raport`) na bazie z Pi — dotychczasowe krótkie uruchomienia testowe:

| Dzień | Pomiary | Sucho [%] | Przerwy w pracy | Podlania automatu | Podlania ręczne | Praca pompy [s] | Błędy |
|---|---|---|---|---|---|---|---|
| 2026-11-09 | 5 | 100 | 1 | 0 | 0 | 0 | 0 |

## 2026-11-12 — Etap 2 (bez pompki): HW-766 podłączony, usługa systemd

Okablowanie: Pi pin 4 (5 V) → COM, NO → VBUS HW-766, GND HW-766 → Pi pin 9 (decyzja 41). **Pompka niewpięta.**

- **Usługa `podlewanie`** startuje razem z Pi (start 20:17:56, usługa od pierwszych sekund); w dzienniku brak błędów, ostrzeżeń i restartów po awarii; `usb-off.service` wyłączona.
- **Ponownie przeskok zegara po starcie:** pierwsze wpisy usługi mają datę 2026-11-09 19:10 (czas z poprzedniego wyłączenia), poprawny czas po synchronizacji NTP — automat (zegar monotoniczny) działał poprawnie.
- **„GPIO busy” przy uruchamianiu skryptów** — przyczyna: GPIO17 i GPIO27 trzyma działająca usługa (`gpioinfo`: oba piny z `consumer="lg"`, jedyny proces z otwartym `/dev/gpiochip` = `run.py` usługi). Zachowanie poprawne (jeden właściciel GPIO, decyzja 23).
- **Pełna ścieżka automatu na sprzęcie** (bez pompki): sonda SUCHO, przerwa po starcie 15 min → o 20:33:17 decyzja `podlano` → przekaźnik włączony **3,00 s** → wpis w bazie (`zrodlo = automat`); `vcgencmd get_throttled` = `0x0`.
- **Ręczne podlewanie przez API:** `POST /api/water` 10 s → `202`; drugie żądanie w trakcie → `409 Pompka już pracuje`; `POST /api/stop` po ok. 1,5 s → przekaźnik wyłączony, w historii `czas_pracy_s = 2,07` z zadanych 10 s; `throttled = 0x0`.
- 53/53 testów jednostkowych na Pi.

## 2026-11-12 — Etap 2: pompka przez przekaźnik i HW-766

Pompka zanurzona w naczyniu z wodą, wąż skierowany do drugiego (pustego) naczynia. Sterowanie przez działającą usługę (`POST /api/water` — ta sama ścieżka co przycisk „Podlej” w panelu).

- **Po wpięciu pompki do HW-766 pompka nie ruszyła** (drugie naczynie puste) — tor przez styk NO jest poprawny.
- **2 s:** przekaźnik 2,00 s, woda popłynęła wyraźnym strumieniem i zatrzymała się po wyłączeniu przekaźnika (obserwacja właściciela); `throttled = 0x0`, brak komunikatów jądra o napięciu.
- **5 s:** przekaźnik 5,00 s, `throttled = 0x0` — zasilanie pompki z pinu 5 V nie powoduje spadków napięcia Pi.
- **Kalibracja ml/s — przełożona** (pomiar 5 s wykonany, ale bez ważenia).

## Do zrobienia

- Etap 2: ile ml wody daje 1 s pracy pompki (waga, 3 × 5 s) — pompka już działa przez przekaźnik.
- Pełna ścieżka z pompką: sucho → automat podlewa → woda w doniczce (przekaźnik w tej ścieżce sprawdzony 2026-11-12).
- Test długoterminowy (min. 7 dni, po etapie 2) — raport `scripts.raport`.
- Próba generalna na laptopie z obrony (wybrana sieć).
