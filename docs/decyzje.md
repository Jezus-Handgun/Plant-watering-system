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

## Etap 4 — automat podlewania

### 16. Automat jako klasa z metodą `krok()` i osobna pętla

`app/controller.py`: `Automat.krok()` podejmuje **jedną** decyzję (`MOKRO`, `PRZERWA`, `LIMIT`, `PODLANO`), a `petla()` tylko wywołuje ją co 60 s i loguje wynik. Sonda, pompka i zegar są wstrzykiwane (*dependency injection*).

- **Alternatywa:** jedna funkcja z `while True`, odczytem GPIO i `time.sleep()` w środku.
- **Dlaczego odrzucona:** nie da się jej przetestować bez czekania (przerwa 15 min, limit na 24 h) ani bez sprzętu. Z fałszywym zegarem testy sprawdzają całą dobę w ułamku sekundy. W etapie 5 Flask użyje tej samej klasy, np. do pokazania ostatniej decyzji w panelu.

### 17. Zabezpieczenia wzięte ze starego projektu

| Zabezpieczenie | Wartość domyślna | Po co |
|---|---|---|
| Limit czasu jednego podlania | 10 s (twardy, w `Pompka`), automat używa 3 s | pompka nie pracuje bez końca przy błędzie programu |
| Przerwa między podlaniami (wsiąkanie) | 15 min | sonda nie zdąży wykryć wody tuż po podlaniu — bez przerwy automat podlewałby co minutę |
| Limit dobowy | 5 podlań w oknie 24 h | ochrona przed zalaniem, gdy sonda „utknie” na SUCHO (korozja, wyjęta z gleby) |

**Pominięto histerezę** ze starego projektu: tam sonda była analogowa (%), więc potrzebne były dwa progi. U nas odczyt jest binarny, próg ustawia potencjometr, a migotanie przy progu eliminuje decyzja większościowa (decyzja 12) i przerwa między podlaniami.

Limit dobowy liczony jest w **oknie kroczącym 24 h**, a nie od północy — prostsza implementacja (kolejka czasów podlań) i brak zależności od daty, której Pi bez sieci może nie znać (patrz decyzja 18).

### 18. Zegar monotoniczny (`time.monotonic`) zamiast czasu systemowego

Raspberry Pi nie ma zegara czasu rzeczywistego (RTC). Po starcie czas systemowy może być błędny i przeskoczyć o godziny po synchronizacji NTP — przerwa liczona z `time.time()` mogłaby wtedy trwać wieki albo zniknąć. Zegar monotoniczny tylko rośnie, więc nadaje się do odmierzania odstępów. Czas „z kalendarza” jest używany wyłącznie w logach.

### 19. Bezpieczne zachowanie przy awariach

- **Start automatu liczy się jak podlanie** — po uruchomieniu najpierw mija przerwa. Gdyby usługa systemd wpadła w pętlę restartów, każdy restart nie kończy się podlaniem.
- **Podlanie zapisywane przed włączeniem pompki** — nieudana próba też liczy się do przerwy i limitu, więc awaria nie powoduje ponawiania co minutę.
- **Wyjątek w kroku jest logowany, a pętla działa dalej** — pompkę i tak wyłącza `finally` w `Pompka.podlej()`, a chwilowy błąd odczytu nie zatrzymuje automatu.
- **SIGTERM / SIGHUP → `SystemExit`** (jak w decyzji 14) — `systemctl stop` lub zerwane SSH wyłącza pompkę natychmiast, nawet w trakcie podlewania.

**Ograniczenie:** stan (czas ostatniego podlania, limit dobowy) jest tylko w pamięci — restart zeruje limit dobowy. Zapis w SQLite w etapie 5.

### 20. Logowanie do pliku `automat.log`

Moduł `logging` z biblioteki standardowej: każda decyzja z datą i godziną, błędy z pełnym śladem stosu. Poza diagnostyką to dane do rozdziału z badaniami (jak często gleba wysycha, ile podlań na dobę). Bez rotacji pliku: przy jednym wpisie na minutę to ok. 100 kB na dobę.

## Etap 2 — zasilanie pompki

### 21. Moduł z gniazdem USB-A zamiast przeciętego przedłużacza USB

Pompka ma wtyk USB-A i nie chcemy przecinać jej kabla. Zasilanie musi przechodzić przez styk NO przekaźnika.

| Rozwiązanie | Ocena |
|---|---|
| Przecięty przedłużacz USB-A m–ż (czerwona żyła przez COM/NO), zasilanie z portu USB Pi | pierwotny plan; wymaga cięcia i łączenia cienkich żył, połączenie trudne do sprawdzenia i mało trwałe |
| Przecięcie kabla pompki | niszczy pompkę jako element wymienny |
| **Moduł z gniazdem USB-A i goldpinami (wybrane)** | gniazdo dla nietkniętego wtyku pompki, połączenia przewodami dupont jak reszta układu, bez lutowania i cięcia; łatwo pokazać na obronie |

Połączenie: Pi pin 4 (5 V) → COM, NO → VBUS modułu, GND modułu → Pi pin 9. Linie D+/D- niepodłączone.

**Konsekwencja:** pompka jest zasilana z pinu 5 V złącza GPIO, a nie z portu USB — omija ogranicznik prądu portów USB Pi. Mini pompka pobiera ułamek ampera, więc przy zasilaczu 3 A to bezpieczne; spadki napięcia kontrolujemy `vcgencmd get_throttled` po każdym teście pompki. Goldpiny modułu trzeba zaizolować (zwarcie VBUS–GND = zwarcie zasilania Pi).

## Etap 5 — backend (Flask + SQLite)

### 22. Automat jako czysta logika, `Sterownik` jako jedyny właściciel sprzętu

Zmiana względem decyzji 16. W etapie 4 `Automat.krok()` sam czytał sondę i włączał pompkę. Po dodaniu ręcznego podlewania z API pompkę uruchamiałyby dwa miejsca, więc podzielono odpowiedzialność:

- `Automat.decyduj(sucho)` — **czysta funkcja decyzji** (przerwa, limit, start), bez sprzętu i bazy; testy nie potrzebują nawet atrapy pinów,
- `Sterownik` — jedyny obiekt, który dotyka sondy i pompki: wątek automatu, ręczne podlewanie, blokada pompki, zapis do bazy.

Samodzielna pętla `python -m app.controller` z etapu 4 została usunięta — automat działa teraz jako wątek aplikacji uruchamianej przez `run.py`.

### 23. Jeden proces: automat jako wątek w aplikacji Flask

- **Alternatywa:** automat i serwer WWW jako dwa osobne procesy (np. dwie usługi systemd).
- **Dlaczego odrzucona:** pin GPIO może mieć tylko jednego właściciela, więc procesy musiałyby się komunikować (kolejka, plik, gniazdo), żeby przycisk „Podlej” mógł użyć pompki. W jednym procesie wystarczy wspólny obiekt `Sterownik`.
- **Konsekwencja:** aplikacji nie wolno uruchamiać w kilku procesach (np. gunicorn z wieloma workerami) — tylko jeden proces z wątkami.
- **Blokada pompki** (`threading.Lock`, próba bez czekania): automat i ręczne podlewanie nigdy nie pracują jednocześnie; drugie żądanie `POST /api/water` dostaje `409 Conflict`.

### 24. Ręczne podlewanie — decyzja człowieka

Ustalone z właścicielem: przycisk „Podlej” działa niezależnie od automatu.

| Reguła | Automat | Ręczne |
|---|---|---|
| Twardy limit 10 s | tak | tak |
| Przerwa 15 min | tak | **nie** (człowiek widzi roślinę) |
| Limit dobowy | tak | **nie** (nie wlicza się do limitu automatu) |
| Po podlaniu | — | automat odczekuje przerwę, żeby nie dolać przed wsiąknięciem |

Automat można wyłączyć w ustawieniach (`automat_wlaczony`) — pomiary są nadal zapisywane.

`POST /api/water` odpowiada od razu `202 Accepted`, a pompka pracuje w osobnym wątku (wzór ze starego projektu). `POST /api/stop` przerywa podlewanie: `Pompka.podlej()` czeka na `threading.Event` zamiast `time.sleep`, więc inny wątek może przerwać oczekiwanie (`Pompka.zatrzymaj()`).

### 25. SQLite przez moduł `sqlite3` z biblioteki standardowej

- **Alternatywa:** ORM (SQLAlchemy / Flask-SQLAlchemy).
- **Dlaczego odrzucona:** trzy proste tabele (`pomiary`, `podlania`, `ustawienia`); SQL jest krótki i widać dokładnie, co trafia do bazy. Mniej zależności na Pi.

Rozwiązania **wzięte ze starego projektu** (klasa `Store`):
- krótkie połączenie na każdą operację — połączenia `sqlite3` nie wolno współdzielić między wątkami (automat + żądania HTTP),
- tryb WAL — odczyt historii przez panel nie blokuje zapisu pomiaru,
- wersja schematu w `PRAGMA user_version` i migracje krokami,
- historia stronicowana po `id` (`przed_id`, odpowiednik `before`), a nie przez `OFFSET`: nowe pomiary dopisywane w trakcie przeglądania nie przesuwają stron.

**Uproszczono:** brak importu danych ze starych tabel, tabel zdarzeń, kanałów czujników i danych przepływomierza. Migracja wykonuje się w jednej transakcji z ustawieniem `user_version` — awaria w połowie nie zostawia bazy w stanie pośrednim.

Czas zapisywany jako liczba sekund od 1970 r. (UTC, `time.time()`): proste porównania w SQL i łatwe formatowanie w przeglądarce.

### 26. Limit dobowy przetrwa restart

Usunięte ograniczenie z decyzji 19. Przy starcie `Sterownik` czyta z bazy podlania automatu z ostatnich 24 h. Baza zapisuje czas ścienny, a automat liczy na zegarze monotonicznym (decyzja 18), więc przeliczany jest **wiek** podlania: `teraz_monotoniczny − (teraz_ścienny − czas_podlania)`.

Pi bez sieci startuje z czasem z chwili ostatniego wyłączenia (cofniętym). Wtedy wiek wychodzi **zaniżony**, podlania wyglądają na świeższe, a automat jest ostrożniejszy — błąd zegara nie powoduje dodatkowego podlewania.

### 27. Walidacja danych na granicy zaufania (`app/api.py`)

Każde wejście z sieci jest sprawdzane przed przekazaniem dalej:
- **ścisłe typy:** `True` nie przechodzi jako `1` (w Pythonie `bool` jest podklasą `int`), `"3"` i `2.5` nie przechodzą jako liczba całkowita,
- **zakresy:** czas podlewania 1–10 s, przerwa 15–1440 min (zasada bezpieczeństwa nr 3), limit 1–20,
- **nieznane klucze odrzucane**, a błąd w jednym polu odrzuca całe żądanie — ustawienia nie zmieniają się częściowo,
- nazwa tabeli historii z listy dozwolonych (nie da się jej przekazać jako parametru SQL).

### 28. Panel bez logowania

Ustalone z właścicielem. Panel działa w sieci lokalnej albo na hotspocie Pi (obrona). **Świadome ograniczenie:** każdy w tej sieci może podlać roślinę lub zmienić ustawienia. Skutki ogranicza sprzęt i backend: maks. 10 s na podlanie, jedno podlewanie naraz, ustawienia tylko w bezpiecznych zakresach. Rozszerzenie (np. hasło w panelu) — poza zakresem pracy.

### 29. Serwer WWW — na razie wbudowany serwer Flaska

`run.py` uruchamia wbudowany serwer (Werkzeug) w trybie wielowątkowym, w jednym procesie (decyzja 23). Wystarcza dla jednego użytkownika w sieci lokalnej. Wybór serwera dla usługi systemd (np. `waitress`) — w etapie 7.

## Etap 6 — panel webowy

### 30. Panel bez zasobów z internetu

Stary panel ładował czcionki z Google Fonts. Na obronie Pi może działać jako hotspot **bez dostępu do internetu** — wtedy strona czekałaby na niedostępne zasoby. Nowy panel korzysta wyłącznie z plików serwowanych przez Flask (`app/templates/index.html`, `app/static/panel.css`, `app/static/panel.js`) i czcionek systemowych. Test `test_panel_i_pliki_statyczne` pilnuje, żeby w HTML nie pojawił się adres zewnętrzny.

**Wzięto ze starego projektu:** ciemny turkusowy motyw, układ kart (stan / podlewanie / automat, pod spodem historia i ustawienia), kolory akcji, wykres w SVG rysowany bez biblioteki. **Pominięto:** sekcje sprzętu, którego nie mamy (zawór, przepływomierz, kalibracja objętości, kanały czujników).

### 31. Czysty JavaScript zamiast frameworka (React, Vue) i bez bibliotek wykresów

Panel to jedna strona z kilkoma kartami i jednym wykresem. Framework wymagałby kroku budowania (Node.js, bundler) i większej liczby plików do utrzymania — bez korzyści przy tej skali. Biblioteka wykresów (np. Chart.js) musiałaby być dołączona lokalnie (decyzja 30), a wykres binarny jest prosty do narysowania w SVG.

### 32. Wykres jako oś czasu (pasy sucho/mokro), nie wykres liniowy

Sonda daje odczyt binarny, więc klasyczny wykres liniowy wilgotności w % nie ma sensu. Wykres pokazuje 24 h jako dwa pasy (**sucho** / **mokro**) i znaczniki podlań (automat / ręczne, różne kolory i opis w dymku). Kolejne pomiary o tym samym stanie są łączone w jeden odcinek; luka dłuższa niż 5 min między pomiarami zostaje pusta — widać, kiedy aplikacja nie działała. Informacja nie jest przekazywana wyłącznie kolorem: wiersze mają podpisy, a nad wykresem jest tekstowe podsumowanie (procent czasu sucho, liczba podlań).

### 33. Odświeżanie przez cykliczne odpytywanie (polling)

Panel co 2 s pobiera `/api/status` (pompka pracuje / stoi), a co 60 s historię — oraz od razu po nowym podlaniu.

- **Alternatywa:** WebSocket lub Server-Sent Events (serwer sam wysyła zmiany).
- **Dlaczego odrzucona:** wymaga dodatkowej biblioteki albo trwałych połączeń, a przy jednym użytkowniku w sieci lokalnej zapytanie co 2 s to znikome obciążenie Pi. Odpowiedzi API mają `Cache-Control: no-store`, więc przeglądarka zawsze pokazuje aktualny stan.

### 34. Bezpieczeństwo panelu: dane z serwera tylko przez `textContent`

Wszystkie dane z API (np. komunikat błędu zapisany w bazie) trafiają do strony przez `textContent` / `createElement`, nigdy przez `innerHTML`. Tekst z bazy nie może więc wstrzyknąć kodu HTML/JS do panelu (atak XSS).

## Etap 7 — wdrożenie

### 35. Serwer WWW: `waitress` (rozstrzygnięcie decyzji 29)

- **Alternatywy:** wbudowany serwer Flaska (Werkzeug), gunicorn.
- **Werkzeug** sam ostrzega, że nie jest przeznaczony do pracy produkcyjnej, i loguje każde żądanie (panel pyta co 2 s → zaśmiecony dziennik).
- **gunicorn** typowo uruchamia kilka procesów (workerów) — sprzeczne z decyzją 23 (jeden właściciel GPIO).
- **waitress** — serwer produkcyjny w czystym Pythonie (bez kompilacji na Pi), **jeden proces z pulą wątków** (4), działa też na Windowsie (symulacja). Na `SIGTERM` kończy pracę normalnie (przechwytuje `SystemExit`), więc `finally` w `run.py` zawsze wyłącza pompkę — sprawdzone na Pi.

### 36. Usługa systemd

[`systemd/podlewanie.service`](../systemd/podlewanie.service):

- `User=raspi` — bez uprawnień roota; użytkownik należy do grupy `gpio`, więc ma dostęp do pinów.
- `ExecStart` wskazuje Pythona z `.venv` projektu zamiast `uv run` — start nie potrzebuje sieci ani synchronizacji zależności (na obronie Pi może nie mieć internetu); po zmianie zależności ręcznie `uv sync`.
- `After=network.target` bez czekania na sieć — automat ma działać także bez Wi-Fi.
- `Restart=on-failure`, `RestartSec=10` — samoczynny powrót po awarii; pętla restartów nie oznacza wielokrotnego podlewania, bo automat po starcie najpierw odczekuje przerwę (decyzja 19), a limit dobowy jest w bazie (decyzja 26).
- `KillSignal=SIGTERM`, `TimeoutStopSec=30` — czas na wyłączenie pompki i zamknięcie GPIO.

### 37. Wyłączenie starej usługi `usb-off.service` (zalecenie)

Na Pi znaleziono włączoną usługę z wcześniejszych prób, która przy starcie wyłącza zasilanie wszystkich portów USB przez `uhubctl` — rozwiązanie odrzucone w decyzji 4. Pompka będzie zasilana z pinu 5 V złącza GPIO przez przekaźnik (decyzja 21), więc usługa nie pełni już żadnej roli, a odcina inne urządzenia USB. Zalecane `sudo systemctl disable usb-off.service` (instrukcja: `docs/obrona.md`). Konsekwencja: pompki nie wolno wpinać bezpośrednio do portu USB Pi.

### 38. Sieć na obronie: hotspot z telefonu, zapasowo hotspot na Pi

| Wariant | Ocena |
|---|---|
| **Hotspot z telefonu (główny)** | profil już zapisany na Pi; Pi ma internet, więc poprawny czas; wymaga sprawnego telefonu |
| **Hotspot na Pi (zapasowy)** | NetworkManager, `ipv4.method shared`, niski priorytet autopołączenia — włącza się sam, gdy żadna znana sieć nie jest w zasięgu; Pi bez internetu |
| Kabel Ethernet | wymaga portu w laptopie i osobnej konfiguracji adresów — tylko awaryjnie |
| Sieć uczelni | zwykle izoluje urządzenia i wymaga logowania — odrzucone |

### 39. Panel liczy czas według zegara Pi

Zaobserwowane 2026-11-09 (`docs/testy.md`): Pi bez RTC startuje z czasem z chwili ostatniego wyłączenia, a poprawia go dopiero synchronizacja NTP (przez internet). Na hotspocie Pi internetu nie ma, więc zegar Pi i laptopa mogą się różnić o godziny — panel pokazywałby świeży pomiar jako „5 h temu”, a wykres 24 h byłby pusty. `/api/status` zwraca `czas_serwera`, panel wylicza przesunięcie zegarów i liczy „X min temu” oraz okno wykresu według zegara Pi. Godziny w panelu pozostają godzinami Pi (mogą być przesunięte), ale zależności czasowe są poprawne.

### 40. Raport z testów długoterminowych (`scripts/raport.py`)

Podsumowanie każdego dnia jednym zapytaniem SQL na tabelę (`GROUP BY` po dacie lokalnej, funkcja okna `LAG` do wykrywania przerw w pracy > 5 min). Baza otwierana tylko do odczytu (`mode=ro`), więc raport nie koliduje z działającą usługą (tryb WAL). Wynik jako tabela Markdown — bezpośrednio do `docs/testy.md`.
