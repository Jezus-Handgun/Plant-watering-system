# Decyzje projektowe

Każda decyzja: co wybrano, jakie były alternatywy, dlaczego. Materiał do części opisowej pracy inżynierskiej.

## Decyzje podjęte przed utworzeniem repozytorium

### 1. Nowe repozytorium zamiast przerabiania starego

Stary projekt ([Automated-watering-device](https://github.com/Jezus-Handgun/Automated-watering-device)) zakładał sprzęt, którego nie ma (MCP3008, przepływomierz, zawór, pływak). Przeróbka oznaczałaby głównie wycinanie kodu. Stary projekt zostaje jako prototyp i wzorzec (API, panel, zasady bezpieczeństwa).

### 2. Flask zamiast Django

Lżejszy dla Raspberry Pi z 2 GB RAM, a stary projekt też był we Flasku, więc część rozwiązań można przenieść.

### 3. Sonda w trybie cyfrowym (DO) zamiast analogowego

Brak przetwornika ADC; próg ustawiany potencjometrem na module HW-103. Konsekwencja: odczyt binarny (sucho/mokro), bez procentów.

### 4. Sterowanie pompką: przekaźnik zamiast `uhubctl`

Rozważono odcinanie zasilania USB przez `uhubctl`. Odrzucono, bo:

- na Pi 4 wyłącza wszystkie porty USB naraz,
- pompka pracowałaby przez kilkanaście sekund przy każdym starcie Pi, zanim usługa systemd zdąży wyłączyć porty.

Przekaźnik na styku NO jest wyłączony od samego startu.

### 5. Dioda LED między GPIO27 a wejściem IN przekaźnika

Problem: HW-307 jest sterowany stanem niskim i zaprojektowany pod logikę 5 V — stan wysoki 3,3 V z GPIO nie wystarcza do jego wyłączenia. Rozważone rozwiązania:

| Rozwiązanie | Ocena |
|---|---|
| Przełączanie pinu między wyjściem LOW a wejściem | działa, ale pin dostaje napięcie powyżej 3,3 V od strony modułu |
| Tranzystor NPN jako bufor | rozwiązanie wzorcowe, brak elementu |
| Inny moduł (MOSFET / przekaźnik 3,3 V) | wymaga zakupu |
| **Czerwona LED w szeregu (wybrane)** | dostępna od ręki, przesuwa próg napięcia (~1,8 V), chroni pin i daje wizualny wskaźnik pracy pompki |

Skutek w kodzie: `OutputDevice(27, active_high=False, initial_value=False)`.

### 6. Claude Code na komputerze, nie na Pi

Claude Code oficjalnie wymaga 4 GB RAM, a Pi ma 2 GB. Kod powstaje na komputerze, Pi tylko pobiera zmiany (`git pull`) i uruchamia testy sprzętowe przez SSH.

## Etap 0 — środowisko

### 7. uv jako menedżer projektu i zależności

Wybrano `uv` zamiast `pip` + `venv` (lub Poetry): jedno narzędzie tworzy środowisko, instaluje zależności i zapisuje dokładne wersje w `uv.lock`. Dzięki plikowi blokady komputer i Pi mają identyczne wersje bibliotek (`uv sync`).

### 8. Python 3.13 (`.python-version`)

Raspberry Pi OS (Debian 13 „trixie”) ma systemowy Python 3.13.5. Ta sama wersja na komputerze eliminuje różnice między środowiskiem testowym a docelowym.

### 9. `lgpio` tylko na Linuksie

`lgpio` (backend gpiozero dla Pi 4/5) to biblioteka C działająca wyłącznie na Linuksie. Dodano ją z markerem `sys_platform == 'linux'`: na Pi jest instalowana, na Windowsie pomijana. Na komputerze testy używają atrap (`HARDWARE_MODE=simulation`, `gpiozero` z `MockFactory`), więc `lgpio` nie jest tam potrzebne.

Na PyPI nie ma gotowej paczki (wheel) `lgpio` dla Pythona 3.13 na `aarch64`, więc uv kompiluje ją ze źródeł. Wymaga to na Pi jednorazowo: `sudo apt-get install swig liblgpio-dev`. Alternatywa — systemowy `python3-lgpio` widoczny w `.venv` (`--system-site-packages`) — odrzucona, bo wersja biblioteki zależałaby od systemu, a nie od `uv.lock`.

### 10. Ruff jako linter i formatter

Jedno szybkie narzędzie zamiast kilku (flake8 + isort + black). Włączone reguły: `E`, `W` (PEP 8), `F` (błędy), `I` (kolejność importów), `B` (typowe pułapki), `UP` (nowoczesna składnia). Długość linii 100.

## Etap 3 — moduły sprzętowe

### 11. Atrapy przez `MockFactory` z gpiozero zamiast własnych klas-atrap

Tryb symulacji (`hardware/fake.py`) podmienia tylko warstwę pinów (`Device.pin_factory = MockFactory()`); klasy `Sonda` i `Pompka` są te same co na Pi.

- **Alternatywa:** osobne klasy `FakeSonda` / `FakePompka` z tym samym interfejsem (podejście ze starego projektu).
- **Dlaczego odrzucona:** testy sprawdzałyby kopię logiki, a nie prawdziwy kod. Z `MockFactory` testy weryfikują m.in., że przekaźnik jest sterowany stanem niskim (`active_high=False`) — błąd w tym miejscu oznaczałby pompkę, która się nie wyłącza.
- **Ograniczenie:** atrapa nie odwzorowuje elektryki (np. progu napięcia na diodzie LED) — to sprawdzają testy na sprzęcie (`docs/testy.md`).

### 12. Decyzja większościowa z 5 odczytów sondy

Blisko progu komparatora wyjście DO przeskakuje między SUCHO a MOKRO. `Sonda.jest_sucho()` robi 5 odczytów co 0,1 s i zwraca SUCHO tylko przy **ścisłej większości**. Remis (przy parzystej liczbie odczytów) daje MOKRO — przy niepewności system nie podlewa (nadmiar wody szkodzi roślinie bardziej niż chwilowe opóźnienie podlania).

### 13. Rezystor podciągający w dół (pull-down) na GPIO17

Moduł HW-103 ma własny rezystor podciągający wyjście DO do VCC, więc wewnętrzny pull-down Pi (~50 kΩ) nie zakłóca odczytu. Wybrano pull-down, bo przy odłączonym przewodzie DO pin czyta 0 = MOKRO → **awaria sondy nie powoduje podlewania** (zasada fail-safe). Pull-up dałby w tej sytuacji SUCHO i podlewanie co przerwę.

### 14. Sygnały SIGHUP/SIGTERM w skrypcie kalibracji pompki

Polecenia na Pi są uruchamiane przez SSH. Zerwanie połączenia wysyła SIGHUP, który domyślnie kończy proces **bez wykonania `finally`** — pompka mogłaby zostać włączona. Skrypt zamienia SIGHUP i SIGTERM na `SystemExit`, dzięki czemu `finally` w `Pompka.podlej()` zawsze wyłącza przekaźnik.

### 15. Skrypty uruchamiane jako moduły (`python -m scripts.nazwa`)

Przy `python scripts/nazwa.py` Python widzi tylko katalog `scripts/` i nie znajduje pakietu `hardware`. Uruchamianie z `-m` z katalogu projektu rozwiązuje to bez instalowania projektu jako pakietu i bez modyfikowania `sys.path` w kodzie.
