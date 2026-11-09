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

## Do zrobienia

- Etap 2: ile ml wody daje 1 s pracy pompki.
- Pełna ścieżka na sprzęcie: sucho → automat podlewa → pompka rusza (po etapie 2).
