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

## Do zrobienia

- Etap 1c: test restartu (`sudo reboot`) — diody przekaźnika nie mogą się zapalić podczas startu.
- Etap 2: ile ml wody daje 1 s pracy pompki.
