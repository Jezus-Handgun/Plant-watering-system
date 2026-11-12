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
  `ssh -t raspi@raspi.local "cd ~/plant-watering-system && git pull && ~/.local/bin/uv run python -m scripts.test_sondy"`
  (skrypty uruchamiać jako moduły `-m`, żeby był widoczny pakiet `hardware`;
  w poleceniach `ssh ... "..."` pełna ścieżka `~/.local/bin/uv` — nieinteraktywna powłoka
  nie wczytuje końca `~/.bashrc`, gdzie instalator uv dopisał `PATH`;
  `-t` tworzy terminal: Ctrl+C trafia do skryptu na Pi, działa `input()`. Bez `-t` Ctrl+C
  zamyka tylko klienta SSH, a skrypt na Pi działa dalej i trzyma GPIO — „GPIO busy”)
- **Usługa `podlewanie` jest zainstalowana i działa od startu Pi (od 2026-11-09) — to ona trzyma GPIO17 i GPIO27.**
- **Pompka jest wpięta na stałe (od 2026-11-12):** przy włączonym automacie i suchej sondzie usługa sama ją
  uruchamia (co ≥ 15 min, maks. 5 ×/dobę). Przed pracą przy pompce wyłączyć automat w panelu albo zatrzymać usługę. Przed skryptami testowymi
  `sudo systemctl stop podlewanie`, po nich `sudo systemctl start podlewanie` (szczegóły: `docs/obrona.md`).
- Na Pi była włączona stara usługa `usb-off.service` (wyłącza zasilanie wszystkich portów USB przy starcie,
  pozostałość po odrzuconym `uhubctl`) — **wyłączona** (decyzja 37).
- W katalogu domowym Pi (`~`) leżą stare skrypty spoza repozytorium (`test_sondy.py`, `test_led.py`,
  `test_przekaznika.py`). **`test_przekaznika.py` steruje przekaźnikiem odrzuconą metodą** (LOW = wł.,
  zwolnienie pinu = wył., 5 × 2 s) — nie uruchamiać przy wpiętej pompce. Używać skryptów z `scripts/`.
- Logowanie SSH kluczem `id_ed25519` (bez hasła). Jeśli SSH pyta o hasło — powiedz właścicielowi, nie próbuj obchodzić.
- Przed każdym poleceniem, które może włączyć pompkę, obowiązuje zasada bezpieczeństwa nr 1 (pytanie o wodę).

## Prezentacja na obronie

Na obronie Pi z elektroniką i **osobny laptop**. VS Code ani Claude Code nie są wtedy potrzebne:
- aplikacja Flask startuje sama przy uruchomieniu Pi (usługa systemd),
- laptop otwiera panel w przeglądarce: `http://raspi.local:5000`,
- SSH tylko awaryjnie.

Na sali może nie być wspólnej sieci — **wybrano hotspot z iPhone'a** (profil Wi-Fi `iPhone` zapisany na Pi, autopołączenie; instrukcja: `docs/obrona.md`, plan A). Zapasowo hotspot na Pi (plan B). Przećwiczyć całą prezentację na tym laptopie przed obroną.

## Sprzęt

| Element | Model | Rola | Status |
|---|---|---|---|
| Sonda wilgotności (widelec) | **HW-080** (rezystancyjna) | Elektrody w glebie | ✅ działa |
| Moduł komparatora | **HW-103** (LM393, potencjometr) | Wyjście DO (cyfrowe) | ✅ działa |
| Przekaźnik | **HW-307** (JQC3F-05VDC-C, 1 kanał, cewka 5 V) | Włącza pompkę | ✅ działa (przez diodę LED) |
| Dioda LED | czerwona 5 mm | Dopasowanie poziomów 3,3 V → przekaźnik + wskaźnik pracy pompki | ✅ działa |
| Pompka zanurzeniowa | mini pompa 5 V z wtykiem **USB-A** | Podlewanie | ✅ działa przez przekaźnik i HW-766 (2026-11-12); kalibracja ml/s do zrobienia |
| Moduł z gniazdem USB-A | **HW-766**: gniazdo USB-A żeńskie, 4 piny 2,54 mm opisane na płytce (VBUS, D-, D+, GND), bez innych elementów (zamiast planowanego Botland MOD-16154 — ten sam układ, decyzja 41) | Gniazdo dla wtyku pompki, zasilane przez przekaźnik | ✅ podłączony (2026-11-12) |
| Czujnik poziomu wody | **HW-038** (S, +, −; analogowy) | — | ❌ nieużywany (wymaga ADC) |

Brak przetwornika ADC (np. ADS1115) — dlatego sonda działa w **trybie cyfrowym** (DO), próg ustawiany potencjometrem na HW-103.

## Połączenia (aktualne, sprawdzone 2026-11-04)

Numeracja **fizyczna** pinów złącza 40-pin (sprawdzona komendą `pinout`). Pin 1 jest w rzędzie wewnętrznym (bliżej środka płytki), na końcu złącza najdalej od portów USB. Rząd wewnętrzny = piny nieparzyste, rząd przy krawędzi = piny parzyste.

### Mapa zajętych pinów

```
              rząd wewnętrzny   rząd przy krawędzi
               (nieparzyste)       (parzyste)
czerwony (sonda VCC)  → [1]  [2]  ← niebieski (przekaźnik VCC)
                        [3]  [4]  ← zielony (5 V → COM przekaźnika, zasilanie pompki)
                        [5]  [6]  ← brązowy (sonda GND)
                        [7]  [8]
pomarańczowy (GND HW-766) → [9]  [10]
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

### Pompka przez HW-766 (działa, sprawdzone 2026-11-12)

Pompka wpięta wtykiem USB-A (kabel nietknięty) do **HW-766** (płytka z gniazdem USB-A); zasilanie gniazda przechodzi przez styk NO przekaźnika (decyzje 21 i 41 w `docs/decyzje.md`):

| Kolor przewodu | Skąd | Dokąd | Uwagi |
|---|---|---|---|
| zielony | Pi **pin 4** (5 V) | **COM** przekaźnika (środkowa śruba, 公共端) | pin 2 (5 V) zajęty przez VCC przekaźnika |
| biały | **NO** przekaźnika (górna śruba, 常开) | **VBUS** HW-766 | NC (常闭, dolna śruba) zostaje wolny |
| pomarańczowy | Pi **pin 9** (GND) | **GND** HW-766 | wspólna masa z Pi |
| — | D+, D- HW-766 | — | niepodłączone (pompka nie używa linii danych) |

- Piny HW-766 są opisane na płytce (VBUS, D-, D+, GND). Pomylenie VBUS z GND = odwrócona polaryzacja pompki.
- Pompka dostaje 5 V prosto z szyny zasilania Pi (bez ogranicznika prądu portów USB). Mini pompka pobiera ułamek ampera — z zasilaczem 3 A to wystarczy; po teście sprawdzić `vcgencmd get_throttled` (`0x0` = brak spadków napięcia). Zwarcie VBUS–GND na module zwiera zasilanie Pi — goldpiny zaizolować.
- Opcjonalnie: dioda (np. 1N5819/1N4007) równolegle do gniazda, zaporowo (katoda → VBUS, anoda → GND) — tłumi przepięcie z silnika pompki przy rozłączaniu styku.
- Kolejność uruchomienia: okablowanie przy wyłączonym Pi → start Pi → dopiero wtedy wpiąć pompkę do modułu. **Pompka nie może ruszyć sama.** Jeśli rusza — wyjąć wtyk, wyłączyć Pi, sprawdzić NO/NC.

**Dopóki pompka nie jest wpięta przez przekaźnik, nie wkładać jej bezpośrednio do USB Pi** — ruszyłaby od razu i pracowała bez przerwy (2026-11-09 tak się zdarzyło: test 2 s przełączył tylko przekaźnik, pompka była poza jego torem).

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
- [ ] **Etap 2 — pompka:** moduł z gniazdem USB-A (**HW-766, podłączony 2026-11-12**) przez przekaźnik (COM/NO, patrz „Pompka”), funkcja `podlej(sekundy)` z `try/finally` i limitem czasu. Zmierzyć, ile ml wody daje 1 s pracy pompki (do `docs/testy.md`). Kod gotowy (`Pompka.podlej()`, `scripts/kalibracja_pompki.py`), sterowanie przekaźnikiem i zasilanie Pi sprawdzone (2026-11-09) — **pompka działa przez przekaźnik i HW-766 (2026-11-12): nie rusza sama, 2 s i 5 s z panelu/API, zasilanie Pi bez spadków. Zostało: kalibracja ml/s.** Kalibracja: waga kuchenna (1 g = 1 ml), 3 × 5 s.
- [x] **Etap 3 — moduły sprzętowe w repozytorium:** `hardware/sensor.py`, `hardware/pump.py`, `hardware/fake.py`, skrypty w `scripts/`, testy na atrapach — **zrobione (2026-11-04)**.
- [x] **Etap 4 — automat:** pętla: odczyt sondy (decyzja większościowa) → jeśli sucho i minęła przerwa → podlej N sekund. Logowanie do pliku. — **zrobione (2026-11-09)**: `app/controller.py` (od etapu 5 automat działa jako wątek aplikacji, patrz decyzja 22).
- [x] **Etap 5 — backend:** Flask + SQLite (fabryka `create_app()`, blueprinty). Modele: pomiary, cykle podlewania, ustawienia. Endpointy wzorowane na starym projekcie: `GET /api/status`, `GET /api/history/...`, `POST /api/water` (ręczne podlanie z limitem czasu), `POST /api/stop`, `GET/PUT /api/settings`. **Zrobione (2026-11-09):** `app/db.py`, `app/api.py`, `app/controller.py` (`Automat` + `Sterownik`), `run.py`; ręczne podlewanie omija przerwę i limit automatu (decyzja 24), panel bez logowania (decyzja 28). Uruchomienie: `uv run python run.py` (Windows: `$env:HARDWARE_MODE="simulation"; uv run python run.py`); na Pi przez SSH: `~/.local/bin/uv run python run.py`.
- [x] **Etap 6 — frontend:** panel webowy serwowany przez Flask (stan rośliny, przycisk „Podlej”, wykres historii, ustawienia), wyglądem inspirowany panelem ze starego repozytorium. **Zrobione (2026-11-09):** `app/templates/index.html`, `app/static/panel.css`, `app/static/panel.js` — bez zasobów z internetu (decyzja 30), czysty JS (decyzja 31).
- [~] **Etap 7 — wdrożenie i badania:** aplikacja jako usługa systemd uruchamiana przy starcie, sieć na obronę (hotspot na Pi lub Ethernet), testy długoterminowe, opis wyników w `docs/testy.md`. **Kod gotowy (2026-11-09):** serwer `waitress` (decyzja 35), `systemd/podlewanie.service`, `scripts/raport.py`, instrukcja `docs/obrona.md`. Usługa zainstalowana i startuje z Pi, `usb-off.service` wyłączona (2026-11-12). **Zostało:** wybór i próba sieci na obronę (decyzja 38), test długoterminowy.
- [ ] **Później (opcjonalnie):** ADS1115 dla odczytu wilgotności w %, czujnik poziomu wody HW-038 (blokada pompki przy pustym zbiorniku), sonda pojemnościowa zamiast HW-080 (HW-080 koroduje).

## Co zostało do zrobienia (stan na 2026-11-09)

Cały kod systemu (etapy 0–7) jest gotowy i przetestowany. Zostały kroki zależne od sprzętu, czasu i właściciela:

1. **Etap 2 — kalibracja pompki.** Pompka działa przez przekaźnik i HW-766 (2026-11-12, sekcja „Pompka”).
   Zostało: kalibracja na wadze
   (3 × 5 s przy zatrzymanej usłudze: `scripts.kalibracja_pompki`, albo przyciskiem „Podlej” w panelu;
   zasada bezpieczeństwa nr 1) → ustawienie czasu podlewania w panelu
   na podstawie ml/s → pełna ścieżka „sucho → automat podlewa”.
2. **Etap 7 — kroki właściciela:** ~~instalacja usługi systemd~~ (zrobione, usługa startuje z Pi — sprawdzone
   2026-11-12), ~~wyłączenie `usb-off.service`~~ (zrobione); zostało: próba sieci na obronę
   (wybrany hotspot z iPhone'a — `docs/obrona.md`, plan A).
3. **Test długoterminowy** (min. 7 dni, po etapie 2) — raport `scripts.raport` do `docs/testy.md`.
4. **Próba generalna** na laptopie z obrony (lista kontrolna w `docs/obrona.md`).

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
