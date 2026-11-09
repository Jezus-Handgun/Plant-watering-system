# Wdrożenie na Raspberry Pi i przygotowanie do obrony

Polecenia z `sudo` uruchamiasz sam (SSH z opcją `-t`, bo `sudo` pyta o hasło).
Każda zmiana okablowania — wyłącznie przy wyłączonym Pi (`sudo shutdown -h now` + odłączenie zasilania).

## 1. Usługa systemd — aplikacja startuje razem z Pi

Plik usługi: [`systemd/podlewanie.service`](../systemd/podlewanie.service) — uruchamia `run.py` jako użytkownik `raspi`, w trybie `HARDWARE_MODE=real`, z restartem po awarii.

### Instalacja (jednorazowo)

```bash
ssh -t raspi@raspi.local
cd ~/plant-watering-system && git pull && ~/.local/bin/uv sync
sudo cp systemd/podlewanie.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now podlewanie.service
systemctl status podlewanie.service --no-pager
```

Panel: `http://raspi.local:5000`.

### Obsługa

| Cel | Polecenie |
|---|---|
| Stan usługi | `systemctl status podlewanie --no-pager` |
| Logi na żywo | `journalctl -u podlewanie -f` |
| Logi od ostatniego startu Pi | `journalctl -u podlewanie -b --no-pager` |
| Zatrzymanie (pompka wyłączana w `finally`) | `sudo systemctl stop podlewanie` |
| Aktualizacja kodu | `git pull && ~/.local/bin/uv sync && sudo systemctl restart podlewanie` |

**Usługa trzyma piny GPIO.** Skrypty testowe (`scripts.test_sondy`, `scripts.kalibracja_pompki`) zakończą się błędem „GPIO busy”, dopóki usługa działa — przed nimi `sudo systemctl stop podlewanie`, po nich `sudo systemctl start podlewanie`.

### Test po instalacji

1. `sudo reboot` — podczas startu zielona dioda przekaźnika i czerwona LED **nie mogą** się zapalić (jak w etapie 1c).
2. Po ok. 1 min panel `http://raspi.local:5000` działa bez logowania się na Pi.
3. `sudo systemctl stop podlewanie` → `journalctl -u podlewanie -n 5` kończy się wpisem „Koniec pracy aplikacji”.

## 2. Stara usługa `usb-off.service` (zalecane wyłączenie)

Na Pi jest włączona usługa z wcześniejszych prób: przy każdym starcie wyłącza zasilanie **wszystkich** portów USB przez `uhubctl`. To rozwiązanie odrzucono w decyzji 4 (pompka steruje przekaźnik), a pompka będzie zasilana z pinu 5 V złącza GPIO, nie z portu USB — więc usługa nie jest już potrzebna, a odłącza np. klawiaturę czy pendrive.

```bash
sudo systemctl disable usb-off.service
```

**Po jej wyłączeniu porty USB mają zasilanie** — pompki nigdy nie wpinamy bezpośrednio do portu USB Pi (pracowałaby bez przerwy), tylko do modułu USB za przekaźnikiem.

## 3. Sieć na obronie

Na sali może nie być wspólnej sieci. Laptop i Pi muszą być w tej samej sieci, żeby otworzyć panel.

| Plan | Jak | Plusy / minusy |
|---|---|---|
| **A. Hotspot z telefonu** (profil `iPhone` już zapisany na Pi) | włącz hotspot w telefonie → Pi łączy się sam; laptop łączy się z tym samym hotspotem → `http://raspi.local:5000` | zero konfiguracji Pi, Pi ma internet (poprawny czas); zależy od telefonu i baterii |
| **B. Hotspot na Pi** | Pi tworzy własną sieć Wi-Fi „Podlewanie”; laptop łączy się z nią → `http://10.42.0.1:5000` | niezależny od telefonu i sali; Pi bez internetu (czas z chwili wyłączenia) |
| **C. Kabel Ethernet** | laptop ↔ Pi kablem | tylko jeśli laptop ma port Ethernet; wymaga osobnej konfiguracji |

**Rekomendacja:** A jako główny (już skonfigurowany), B jako zapasowy.

### Plan A — sprawdzenie

Hotspot w telefonie musi mieć tę samą nazwę i hasło co przy zapisywaniu profilu na Pi. Przećwiczyć w domu: wyłączyć domowe Wi-Fi (albo odejść z Pi poza zasięg), włączyć hotspot, zrestartować Pi, połączyć laptop z hotspotem, otworzyć panel.

### Plan B — hotspot na Pi (NetworkManager)

Utworzenie profilu (hasło: min. 8 znaków):

```bash
sudo nmcli connection add type wifi ifname wlan0 con-name obrona-hotspot ssid Podlewanie \
  802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "TWOJE_HASLO" \
  connection.autoconnect yes connection.autoconnect-priority -10
```

- `autoconnect-priority -10` — niższy niż sieci domowej (`Multiplay_2280`, priorytet 0) i telefonu: gdy znana sieć jest w zasięgu, Pi łączy się z nią; gdy żadnej nie ma (sala), Pi uruchamia własny hotspot.
- **Przed obroną sprawdzić w domu kilkoma restartami (`sudo reboot`), że Pi wraca do sieci domowej.** Jeśli zamiast tego włączy hotspot: połącz komputer z siecią „Podlewanie”, `ssh raspi@10.42.0.1` i ustaw `sudo nmcli connection modify obrona-hotspot connection.autoconnect no` (wtedy hotspot tylko ręcznie: `sudo nmcli connection up obrona-hotspot` tuż przed wyjściem z domu).
- Usunięcie profilu: `sudo nmcli connection delete obrona-hotspot`.

**Czas bez internetu:** Pi nie ma zegara RTC — bez internetu startuje z czasem z chwili ostatniego wyłączenia (sprawdzone 2026-11-09: przeskok o 5 dni po synchronizacji). Bezpieczeństwo automatu to nie zmienia (decyzje 18 i 26), a panel liczy „X min temu” i wykres według zegara Pi (decyzja 39). Godziny pokazywane w panelu mogą być jednak przesunięte — warto wyłączyć Pi (`sudo shutdown -h now`) tuż przed wyjściem z domu, żeby przesunięcie było jak najmniejsze.

## 4. Testy długoterminowe

Po instalacji usługi Pi zbiera dane samo (pomiar co minutę, podlania). Raport dzienny:

```bash
ssh raspi@raspi.local "cd ~/plant-watering-system && ~/.local/bin/uv run python -m scripts.raport"
```

Drukuje tabelę Markdown (pomiary, % czasu sucho, przerwy w pracy aplikacji, podlania automatu i ręczne, czas pracy pompki, błędy) — wkleić do `docs/testy.md`. Sensowny test: **min. 7 dni** z rośliną w doniczce, po etapie 2 (pompka przez przekaźnik). Na co patrzeć:

- „Przerwy w pracy” = 0 poza restartami (stabilność usługi),
- liczba podlań automatu na dobę ≤ limit, odstępy ≥ przerwa,
- „Błędy” = 0,
- korozja sondy HW-080 (zdjęcie elektrod przed i po teście).

## 5. Lista kontrolna przed obroną

- [ ] Usługa włączona (`systemctl is-enabled podlewanie` → `enabled`).
- [ ] Generalna próba na **laptopie z obrony**: zasilanie Pi, wybrana sieć (A lub B), panel w przeglądarce, „Podlej” 2 s z pompką w wodzie, „Zatrzymaj”.
- [ ] Nóżki diody LED w końcówkach dupont dobrze owinięte (mogą się poluzować przy przenoszeniu).
- [ ] Goldpiny modułu USB zaizolowane.
- [ ] Zbiornik z wodą, wąż w doniczce lub naczyniu; ręcznik.
- [ ] Zasilacz Pi (oficjalny, 3 A) — bez niego pompka może powodować spadki napięcia.
- [ ] Zapasowo: kabel USB-C do zasilania Pi z powerbanku, telefon z hotspotem.
