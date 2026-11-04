# Automatyczne podlewanie roślin — Raspberry Pi 4

Ten plik opisuje projekt dla Claude Code. Przeczytaj go w całości przed pisaniem kodu lub uruchamianiem testów.

## Kontekst: praca inżynierska

Projekt jest realizowany jako **praca inżynierska** na temat: **„Automatyczny system podlewania roślin”**.

Z tego wynika:
- Budujemy **kompletny system**: warstwa sprzętowa (czujniki, pompka), backend, frontend, baza danych — wszystko działające na **Raspberry Pi 4**.
- Kod ma być na poziomie pracy dyplomowej: czytelna architektura, podział na moduły, testy, sensowne nazwy, komentarze po polsku.
- **Decyzje projektowe trzeba zapisywać** (co wybrano, jakie były alternatywy, dlaczego) — przydadzą się do części opisowej pracy. Zapisuj je w `docs/decyzje.md` (kolejne numery).
- Wyniki testów (np. kalibracja sondy, czas podlewania vs ilość wody) zapisuj w `docs/testy.md` — to materiał do rozdziału z badaniami.
- Właściciel programuje w Pythonie i interesuje go strona backendowa / implementacyjna. Wyjaśniaj decyzje, żeby mógł je obronić na egzaminie.

## Kolejność prac

1. **Najpierw elektronika** — połączenie i przetestowanie całego sprzętu (sonda, przekaźnik, pompka). Dopóki to nie działa niezawodnie, nie piszemy reszty systemu.
2. **Potem system** — backend, frontend, baza danych, automatyka podlewania.

## Cel systemu

System, który:
1. Odczytuje wilgotność gleby z sondy.
2. Włącza pompkę wody, gdy gleba jest sucha (na kilka sekund), potem ją wyłącza.
3. Udostępnia aplikację webową do podglądu stanu, historii pomiarów i ręcznego podlewania.

## Stos technologiczny (ustalony)

| Warstwa | Technologia |
|---|---|
| Backend | **Flask** (Python) |
| Baza danych | **SQLite** |
| Zarządzanie projektem i zależnościami | **uv** (`uv init`, `uv add`, `uv run`) |
| Linter i formatowanie | **Ruff** (`uv run ruff check .`, `uv run ruff format .`) |
| Sterowanie GPIO | **gpiozero** |
| Pompka | **przekaźnik HW-307 na GPIO27** (sterowany stanem niskim, przez diodę LED) |
| Frontend | inspirowany poprzednim projektem (patrz niżej) |

Zasady:
- Zależności dodawaj tylko przez `uv add` (dev: `uv add --dev`), nie przez `pip`.
- Przed każdym commitem: `uv run ruff check .` i `uv run ruff format .` muszą przechodzić.
- Testy: `uv run pytest` (aplikacja Flask testowana przez `app.test_client()`).

## Poprzedni projekt (referencja)

Repozytorium: https://github.com/Jezus-Handgun/Automated-watering-device

To wcześniejsza wersja projektu: **Flask**, SQLite, panel webowy, ADC **MCP3008**, przepływomierz Halla, zawór, czujnik pływakowy, przekaźnik, Docker. Zakłada **dużo więcej elektroniki, niż faktycznie mamy**.

Jak z niego korzystać:
- **Wzorować się** na: wyglądzie i układzie panelu (frontend), projekcie API (`/api/status`, `/api/water`, `/api/stop`, historia z paginacją), zasadach bezpieczeństwa (limit czasu, dzienny budżet podlewania, przerwa na wsiąkanie, histereza, tryb symulacji), testach z mockami.
- Stary projekt też jest we **Flasku**, więc fragmenty backendu (struktura aplikacji, `create_app()`, obsługa SQLite, migracje, endpointy, testy) można **przenosić wybiórczo**, upraszczając je.
- **Nie przenosić** kodu obsługi sprzętu, którego nie mamy (MCP3008, przepływomierz, zawór, pływak) ani ustawień z nim związanych. Uwaga: stary kod przekaźnika zakładał inną logikę niż nasz moduł — obsługę pompki piszemy od nowa według sekcji „Połączenia”. Nie kopiować całego repozytorium hurtem — każdy przeniesiony moduł ma być zrozumiały i potrzebny.
- Przy przenoszeniu pomysłu zapisz w `docs/decyzje.md`, co wzięto ze starego projektu, a co uproszczono i dlaczego.

## Środowisko

- **Raspberry Pi 4 Model B rev 1.5, 2 GB RAM**, karta microSD 32 GB, system 64-bit (`aarch64`)
- Hostname: **`raspi`**, użytkownik: **`raspi`** → `ssh raspi@raspi.local`
- Python 3, biblioteka GPIO: **gpiozero** (preferowana)
- Komputer właściciela: **Windows** (PowerShell)

## Sposób pracy (ustalony)

Claude Code oficjalnie wymaga 4 GB RAM, a Pi ma 2 GB — dlatego **Claude Code i VS Code działają na komputerze właściciela, nie na Pi**.

```
KOMPUTER (VS Code + Claude Code)              RASPBERRY PI
kod projektu (git)            ── git push → GitHub → git pull ──▶  kopia kodu
Ruff + testy z atrapami       ── ssh raspi@raspi.local "..." ──▶  testy na sprzęcie
```

- **Komputer jest jedynym źródłem kodu.** Na Pi nie edytujemy plików — tylko `git pull`.
- Repozytorium: **`plant-watering-system`** (GitHub, konto `Jezus-Handgun`).
- Logikę testuj lokalnie na atrapach (`HARDWARE_MODE=simulation`), bez sprzętu.
- Testy sprzętowe uruchamiaj na Pi jednym poleceniem przez SSH, np.:
  `ssh raspi@raspi.local "cd ~/plant-watering-system && git pull && ~/.local/bin/uv run python -m scripts.test_sondy"`
  (skrypty uruchamiać jako moduły `-m`, żeby był widoczny pakiet `hardware`;
  w poleceniach `ssh ... "..."` pełna ścieżka `~/.local/bin/uv` — nieinteraktywna powłoka
  nie wczytuje końca `~/.bashrc`, gdzie instalator uv dopisał `PATH`)
- Logowanie SSH kluczem `id_ed25519` (bez hasła). Jeśli SSH pyta o hasło — powiedz właścicielowi, nie próbuj obchodzić.
- Przed każdym poleceniem, które może włączyć pompkę, obowiązuje zasada bezpieczeństwa nr 1 (pytanie o wodę).

## Prezentacja na obronie

Na obronie Pi z elektroniką i **osobny laptop**. VS Code ani Claude Code nie są wtedy potrzebne:
- aplikacja Flask startuje sama przy uruchomieniu Pi (usługa systemd),
- laptop otwiera panel w przeglądarce: `http://raspi.local:5000`,
- SSH tylko awaryjnie.

Na sali może nie być wspólnej sieci — przygotować (etap 7): hotspot Wi-Fi na Pi albo połączenie kablem Ethernet. Przećwiczyć całą prezentację na tym laptopie przed obroną.

## Sprzęt

| Element | Model | Rola | Status |
|---|---|---|---|
| Sonda wilgotności (widelec) | **HW-080** (rezystancyjna) | Elektrody w glebie | ✅ działa |
| Moduł komparatora | **HW-103** (LM393, potencjometr) | Wyjście DO (cyfrowe) | ✅ działa |
| Przekaźnik | **HW-307** (JQC3F-05VDC-C, 1 kanał, cewka 5 V) | Włącza pompkę | ✅ działa (przez diodę LED) |
| Dioda LED | czerwona 5 mm | Dopasowanie poziomów 3,3 V → przekaźnik + wskaźnik pracy pompki | ✅ działa |
| Pompka zanurzeniowa | mini pompa 5 V z wtykiem **USB-A** | Podlewanie | ⏳ czeka na przedłużacz USB |
| Przedłużacz USB-A męski–żeński | — | Linia zasilania pompki przez przekaźnik | ⏳ do kupienia |
| Czujnik poziomu wody | **HW-038** (S, +, −; analogowy) | — | ❌ nieużywany (wymaga ADC) |

Brak przetwornika ADC (np. ADS1115) — dlatego sonda działa w **trybie cyfrowym** (DO), próg ustawiany potencjometrem na HW-103.

## Połączenia (aktualne, sprawdzone 2026-11-04)

Numeracja **fizyczna** pinów złącza 40-pin (sprawdzona komendą `pinout`). Pin 1 jest w rzędzie wewnętrznym (bliżej środka płytki), na końcu złącza najdalej od portów USB. Rząd wewnętrzny = piny nieparzyste, rząd przy krawędzi = piny parzyste.

### Mapa zajętych pinów

```
              rząd wewnętrzny   rząd przy krawędzi
               (nieparzyste)       (parzyste)
czerwony (sonda VCC)  → [1]  [2]  ← niebieski (przekaźnik VCC)
                        [3]  [4]
                        [5]  [6]  ← brązowy (sonda GND)
                        [7]  [8]
                        [9]  [10]
żółty (sonda DO)      → [11] [12]
czarny (→ LED → IN)   → [13] [14] ← fioletowy (przekaźnik GND)
```

### Sonda wilgotności (HW-080 + HW-103)

| HW-103 | Kolor przewodu | Raspberry Pi |
|---|---|---|
| VCC | czerwony | **pin 1** (3,3 V) |
| GND | brązowy | **pin 6** (GND) |
| DO | żółty | **pin 11** (GPIO17) |
| AO | — | niepodłączony |

- Sonda HW-080 podłączona do 2-pinowego gniazda HW-103 (zielony + pomarańczowy, kierunek obojętny).
- HW-103 zasilany z **3,3 V**, więc wyjście DO jest bezpieczne dla GPIO. **Nie zasilać z 5 V.**
- Logika DO **potwierdzona testem**: **0 = mokro** (zapala się druga dioda na HW-103), **1 = sucho**.
- Przy wilgotności blisko progu odczyt przeskakuje SUCHO/MOKRO — w kodzie stosować kilka odczytów i decyzję większościową.

### Przekaźnik HW-307

| Przekaźnik | Kolor przewodu | Raspberry Pi |
|---|---|---|
| VCC | niebieski | **pin 2** (5 V) |
| GND | fioletowy | **pin 14** (GND) |
| IN | czarny → **dioda LED** → czarny | **pin 13** (GPIO27) |

Tor sygnału IN (kierunek diody jest ważny):

```
pin 13 (GPIO27) ── czarny przewód ── KRÓTKA nóżka LED (katoda, –)
                                     DŁUGA nóżka LED (anoda, +) ── czarny przewód ── IN przekaźnika
```

**Dlaczego dioda:** moduł HW-307 jest **sterowany stanem niskim** i zaprojektowany pod logikę 5 V. Test bez diody pokazał, że stan wysoki 3,3 V z GPIO **nie wyłącza** przekaźnika (wyłączał się dopiero po zwolnieniu pinu). Czerwona LED (spadek ~1,8 V) działa jak próg:
- GPIO **LOW** → prąd płynie przez LED → przekaźnik **włączony**, czerwona LED świeci,
- GPIO **HIGH** (3,3 V) → za mała różnica napięć → przekaźnik **wyłączony**,
- pin jako wejście (start Pi, zakończony program) → przekaźnik **wyłączony**,
- dodatkowo LED ogranicza napięcie widziane przez pin GPIO od strony modułu 5 V.

**Obowiązkowy sposób sterowania w kodzie:**

```python
from gpiozero import OutputDevice

# HW-307 przez LED: sterowany stanem niskim. on() = LOW = pompka włączona.
przekaznik = OutputDevice(27, active_high=False, initial_value=False)
```

Nigdy nie używaj `active_high=True` dla tego przekaźnika — pompka by się nie wyłączała.

Test potwierdzony: przy `on()` klika przekaźnik, świeci zielona dioda modułu i czerwona LED; przy `off()` wszystko gaśnie.

### Pompka (do zrobienia)

Pompka przez przecięty **przedłużacz USB-A męski–żeński** (kabel pompki zostaje nietknięty):
- w przedłużaczu przecięta **tylko czerwona żyła** (+5 V); czarna, zielona i biała bez zmian,
- czerwona od strony **wtyku** (do portu USB Pi) → **COM** (środkowa śruba, 公共端),
- czerwona od strony **gniazda** (do pompki) → **NO** (śruba 常开),
- NC (常闭) zostaje wolny,
- przedłużacz wpięty w dowolny port USB Pi, pompka wpięta w przedłużacz.

**Dopóki pompka nie jest wpięta przez przekaźnik, nie wkładać jej bezpośrednio do USB Pi** — ruszyłaby od razu.

## Zasady bezpieczeństwa (OBOWIĄZKOWE dla Claude Code)

1. **Nigdy nie włączaj pompki bez potwierdzenia od użytkownika**, że pompka jest w wodzie, a wąż skierowany do naczynia/zlewu. Pompka na sucho się przegrzewa.
2. Każde włączenie pompki: **`try/finally` z wyłączeniem** w `finally`, oraz **twardy limit czasu** (domyślnie max 10 s na jedno podlewanie).
3. Między podlewaniami minimalna przerwa (np. 15 min), żeby nie zalać rośliny przy błędnym odczycie.
4. Nie proponuj zmian w okablowaniu przy włączonym Pi. Każda zmiana kabli: najpierw `sudo shutdown -h now` i odłączenie zasilania.
5. Nigdy nie sugeruj podłączenia VCC sondy do 5 V (pin 2/4) — wyjście DO uszkodziłoby GPIO.
6. Nie podłączaj IN przekaźnika do GPIO z pominięciem diody LED.
7. Nie wykonuj komend modyfikujących system (instalacja, systemd, sudoers) bez pokazania ich użytkownikowi i zgody.

## Plan prac

- [x] **Etap 0 — środowisko:** **zrobione (2026-11-04)** — na Pi dodatkowo `sudo apt-get install swig liblgpio-dev` (patrz decyzja 9). na komputerze (Windows): Git, VS Code, Claude Code, uv. Repozytorium `plant-watering-system` na GitHubie, sklonowane na komputer i na Pi. Na Pi: `uv`. `uv init`, `uv add gpiozero lgpio`, `uv add --dev ruff pytest`, konfiguracja Ruff w `pyproject.toml`. Utworzyć `docs/decyzje.md` i `docs/testy.md` i przenieść do nich decyzje i wyniki z tego pliku.
- [x] **Etap 1 — test sondy:** GPIO17, SUCHO/MOKRO — **działa (2026-11-04)**.
- [x] **Etap 1b — test przekaźnika:** GPIO27 przez diodę LED, `active_high=False` — **działa (2026-11-04)**.
- [x] **Etap 1c — test restartu:** `sudo reboot` — zielona dioda przekaźnika i czerwona LED nie mogą się zapalić podczas startu. — **działa (2026-11-04)**.
- [ ] **Etap 2 — pompka:** przedłużacz USB przez przekaźnik (COM/NO), funkcja `podlej(sekundy)` z `try/finally` i limitem czasu. Zmierzyć, ile ml wody daje 1 s pracy pompki (do `docs/testy.md`). Kod gotowy (`Pompka.podlej()`, `scripts/kalibracja_pompki.py`) — czeka na przedłużacz USB.
- [x] **Etap 3 — moduły sprzętowe w repozytorium:** `hardware/sensor.py`, `hardware/pump.py`, `hardware/fake.py`, skrypty w `scripts/`, testy na atrapach — **zrobione (2026-11-04)**.
- [ ] **Etap 4 — automat:** pętla: odczyt sondy (decyzja większościowa) → jeśli sucho i minęła przerwa → podlej N sekund. Logowanie do pliku.
- [ ] **Etap 5 — backend:** Flask + SQLite (fabryka `create_app()`, blueprinty). Modele: pomiary, cykle podlewania, ustawienia. Endpointy wzorowane na starym projekcie: `GET /api/status`, `GET /api/history/...`, `POST /api/water` (ręczne podlanie z limitem czasu), `POST /api/stop`, `GET/PUT /api/settings`.
- [ ] **Etap 6 — frontend:** panel webowy serwowany przez Flask (stan rośliny, przycisk „Podlej”, wykres historii, ustawienia), wyglądem inspirowany panelem ze starego repozytorium.
- [ ] **Etap 7 — wdrożenie i badania:** aplikacja jako usługa systemd uruchamiana przy starcie, sieć na obronę (hotspot na Pi lub Ethernet), testy długoterminowe, opis wyników w `docs/testy.md`.
- [ ] **Później (opcjonalnie):** ADS1115 dla odczytu wilgotności w %, czujnik poziomu wody HW-038 (blokada pompki przy pustym zbiorniku), sonda pojemnościowa zamiast HW-080 (HW-080 koroduje).

## Proponowana struktura

```
plant-watering-system/
├── CLAUDE.md
├── pyproject.toml         # uv + konfiguracja Ruff
├── uv.lock
├── hardware/              # warstwa sprzętowa, niezależna od Flaska
│   ├── sensor.py          # odczyt sondy (GPIO17, decyzja większościowa)
│   ├── pump.py            # pompka przez przekaźnik (GPIO27, active_high=False)
│   └── fake.py            # atrapy do testów i trybu symulacji
├── scripts/               # skrypty testowe elektroniki
├── app/                   # aplikacja Flask
│   ├── __init__.py        # create_app()
│   ├── api.py             # blueprint z endpointami /api/...
│   ├── db.py              # SQLite: połączenie, schemat, migracje
│   ├── controller.py      # logika automatu podlewania
│   ├── templates/         # frontend (etap 6)
│   └── static/
├── run.py                 # uruchomienie aplikacji
├── tests/                 # testy z mockami (bez sprzętu)
├── systemd/               # pliki usług
└── docs/
    ├── decyzje.md         # decyzje projektowe (do pracy inżynierskiej)
    └── testy.md           # wyniki testów i kalibracji
```

Warstwa `hardware/` nie zależy od Flaska, a logika podlewania nie zależy bezpośrednio od sprzętu — sonda i pompka wstrzykiwane, żeby dało się testować na atrapach (pytest) bez Raspberry Pi. Tryb pracy wybierany zmienną `HARDWARE_MODE=real|simulation` (jak w starym projekcie).

## Notatki

- HW-080 jest rezystancyjna i z czasem koroduje. Docelowo można zasilać sondę tylko na czas odczytu (VCC z pinu GPIO zamiast 3,3 V).
- Odczyt jest binarny (sucho/mokro). Próg zmienia się śrubką potencjometru na HW-103.
- Nóżki diody LED są cieńsze niż piny — w końcówkach dupont zagięte i owinięte taśmą. Przy przenoszeniu Pi (np. na obronę) sprawdzić, czy się nie poluzowały.
