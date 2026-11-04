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

## Do zrobienia

- Etap 2: ile ml wody daje 1 s pracy pompki.
