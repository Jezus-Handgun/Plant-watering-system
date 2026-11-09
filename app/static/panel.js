"use strict";
// Panel podlewania: odpytuje API Flaska (/api/...).
// Dane z serwera trafiają do strony tylko przez textContent (nigdy innerHTML) — brak ryzyka XSS.

const $ = (id) => document.getElementById(id);
const DOBA_S = 24 * 3600;
const MAKS_LUKA_S = 5 * 60; // dłuższa przerwa między pomiarami = aplikacja nie działała
const SVG = "http://www.w3.org/2000/svg";

const OPIS_DECYZJI = {
  "mokro": "Gleba wilgotna — automat nie podlewa.",
  "przerwa": "Sucho, ale trwa przerwa na wsiąknięcie wody.",
  "limit": "Sucho, ale wyczerpany dobowy limit automatu.",
  "podlano": "Automat właśnie podlał roślinę.",
  "automat wyłączony": "Automat wyłączony — tylko pomiary.",
};
const ZRODLO = { automat: "automat", reczne: "ręczne" };

// --- komunikacja z API ---

async function api(sciezka, opcje = {}) {
  let odp;
  try {
    odp = await fetch(sciezka, { headers: { "Content-Type": "application/json" }, ...opcje });
  } catch {
    ustawPolaczenie(false);
    throw new Error("Brak połączenia z Raspberry Pi");
  }
  ustawPolaczenie(true);
  const dane = await odp.json().catch(() => ({}));
  if (!odp.ok) throw new Error(dane.blad || `Błąd serwera (${odp.status})`);
  return dane;
}

function ustawPolaczenie(ok) {
  const el = $("polaczenie");
  el.textContent = ok ? "Połączono z Pi" : "Brak połączenia z Pi";
  el.className = "status-pill " + (ok ? "ok" : "blad");
}

function nota(id, tekst, blad = false) {
  const el = $(id);
  el.textContent = tekst;
  el.classList.toggle("blad", blad);
}

// --- formatowanie czasu ---

const czas = (t) => new Date(t * 1000).toLocaleString("pl-PL");
const godzina = (t) =>
  new Date(t * 1000).toLocaleTimeString("pl-PL", { hour: "2-digit", minute: "2-digit" });

function ileTemu(t) {
  const s = Math.max(0, Date.now() / 1000 - t);
  if (s < 60) return "przed chwilą";
  if (s < 3600) return `${Math.floor(s / 60)} min temu`;
  return `${Math.floor(s / 3600)} h temu`;
}

// --- stan ---

let pompkaPracowala = false;
let ostatniePodlanieId; // undefined ≠ null → pierwszy status zawsze wczytuje historię

async function odswiezStatus() {
  const s = await api("/api/status");

  const gleba = $("gleba");
  if (s.pomiar) {
    gleba.textContent = s.pomiar.sucho ? "SUCHO" : "MOKRO";
    gleba.dataset.stan = s.pomiar.sucho ? "sucho" : "mokro";
    $("czasPomiaru").textContent = `Pomiar ${ileTemu(s.pomiar.czas)} (${godzina(s.pomiar.czas)})`;
  } else {
    gleba.textContent = "—";
    gleba.dataset.stan = "brak";
    $("czasPomiaru").textContent = "Pierwszy pomiar w ciągu minuty od startu.";
  }
  $("decyzja").textContent = OPIS_DECYZJI[s.ostatnia_decyzja] ?? "";

  const pompka = $("pompka");
  pompka.dataset.pracuje = s.pompka_pracuje;
  pompka.textContent = s.pompka_pracuje ? "Pompka: pracuje" : "Pompka: stoi";
  $("przyciskPodlej").disabled = s.pompka_pracuje;

  $("automat").textContent = s.automat_wlaczony ? "Włączony" : "Wyłączony";
  $("limit").textContent =
    `Podlania automatu w ciągu 24 h: ${s.podlania_automatu_24h} z ${s.limit_dobowy}`;

  const p = s.ostatnie_podlanie;
  $("ostatniePodlanie").textContent = p
    ? `Ostatnie podlanie: ${czas(p.czas)} (${ZRODLO[p.zrodlo]})`
    : "Jeszcze nie podlewano.";

  // Nowe podlanie albo koniec pracy pompki → odśwież historię i tabelę.
  const noweId = p ? p.id : null;
  if ((pompkaPracowala && !s.pompka_pracuje) || noweId !== ostatniePodlanieId) {
    ostatniePodlanieId = noweId;
    odswiezHistorie().catch(pokazBladHistorii);
  }
  pompkaPracowala = s.pompka_pracuje;
}

// --- podlewanie ręczne ---

$("formPodlej").addEventListener("submit", async (e) => {
  e.preventDefault();
  const sekundy = Number($("sekundy").value);
  try {
    await api("/api/water", { method: "POST", body: JSON.stringify({ sekundy }) });
    nota("notaPodlej", `Podlewanie ${sekundy} s…`);
    await odswiezStatus();
  } catch (err) {
    nota("notaPodlej", err.message, true);
  }
});

$("przyciskStop").addEventListener("click", async () => {
  try {
    await api("/api/stop", { method: "POST" });
    nota("notaPodlej", "Pompka zatrzymana.");
    await odswiezStatus();
  } catch (err) {
    nota("notaPodlej", err.message, true);
  }
});

// --- ustawienia ---

const formUst = $("formUstawienia");

async function zaladujUstawienia() {
  const u = await api("/api/settings");
  formUst.elements.automat_wlaczony.checked = u.automat_wlaczony;
  for (const klucz of ["czas_podlewania_s", "przerwa_min", "limit_dobowy"]) {
    formUst.elements[klucz].value = u[klucz];
  }
  $("sekundy").value = u.czas_podlewania_s;
}

formUst.addEventListener("submit", async (e) => {
  e.preventDefault();
  const dane = {
    automat_wlaczony: formUst.elements.automat_wlaczony.checked,
    czas_podlewania_s: Number(formUst.elements.czas_podlewania_s.value),
    przerwa_min: Number(formUst.elements.przerwa_min.value),
    limit_dobowy: Number(formUst.elements.limit_dobowy.value),
  };
  try {
    await api("/api/settings", { method: "PUT", body: JSON.stringify(dane) });
    nota("notaUstawienia", "Zapisano.");
    await odswiezStatus();
  } catch (err) {
    nota("notaUstawienia", err.message, true);
  }
});

// --- historia: wykres 24 h ---

async function pobierzDobe(rodzaj) {
  // API zwraca od najnowszych, max 500 na stronę; 24 h pomiarów co minutę = ok. 1440.
  const od = Date.now() / 1000 - DOBA_S;
  const wynik = [];
  let przed = null;
  for (let i = 0; i < 5; i++) {
    const q = przed ? `&przed_id=${przed}` : "";
    const strona = await api(`/api/history/${rodzaj}?limit=500${q}`);
    wynik.push(...strona.elementy);
    przed = strona.nastepna_strona_przed_id;
    if (!przed || strona.elementy.at(-1).czas < od) break;
  }
  return wynik.filter((e) => e.czas >= od).reverse(); // rosnąco w czasie
}

function el(nazwa, atrybuty, tekst) {
  const e = document.createElementNS(SVG, nazwa);
  for (const [k, v] of Object.entries(atrybuty)) e.setAttribute(k, v);
  if (tekst !== undefined) e.textContent = tekst;
  return e;
}

function rysujWykres(pomiary, podlania) {
  const svg = $("wykres");
  svg.replaceChildren();
  const X0 = 70, X1 = 890;
  const koniec = Date.now() / 1000, poczatek = koniec - DOBA_S;
  const x = (t) => X0 + ((t - poczatek) / DOBA_S) * (X1 - X0);
  const WIERSZE = { sucho: 20, mokro: 66 }; // y wierszy pomiarów (wysokość 36)

  // siatka co 3 h, na pełnych godzinach
  const pierwsza = Math.ceil(poczatek / 3600) * 3600;
  for (let t = pierwsza; t <= koniec; t += 3 * 3600) {
    svg.append(el("line", { x1: x(t), x2: x(t), y1: 12, y2: 160, class: "siatka" }));
    svg.append(el("text", { x: x(t), y: 185, "text-anchor": "middle" }, godzina(t)));
  }
  svg.append(el("text", { x: 8, y: 43 }, "sucho"));
  svg.append(el("text", { x: 8, y: 89 }, "mokro"));
  svg.append(el("text", { x: 8, y: 145 }, "podlania"));

  // odcinki stanu: kolejne pomiary o tym samym stanie łączone; luka > 5 min = brak danych
  let i = 0;
  while (i < pomiary.length) {
    const stan = pomiary[i].sucho ? "sucho" : "mokro";
    let j = i;
    while (
      j + 1 < pomiary.length &&
      pomiary[j + 1].sucho === pomiary[i].sucho &&
      pomiary[j + 1].czas - pomiary[j].czas <= MAKS_LUKA_S
    ) j++;
    const nast = pomiary[j + 1];
    const t1 = nast && nast.czas - pomiary[j].czas <= MAKS_LUKA_S ? nast.czas : pomiary[j].czas + 60;
    const xa = x(pomiary[i].czas);
    svg.append(el("rect", {
      x: xa, y: WIERSZE[stan], height: 36, width: Math.max(1, x(Math.min(t1, koniec)) - xa),
      class: stan,
    }));
    i = j + 1;
  }

  for (const p of podlania) {
    const linia = el("line", {
      x1: x(p.czas), x2: x(p.czas), y1: 124, y2: 160, "stroke-width": 3, class: p.zrodlo === "automat" ? "auto" : "reczne",
    });
    linia.append(el("title", {}, `${godzina(p.czas)} — ${ZRODLO[p.zrodlo]}, ${p.sekundy} s`));
    svg.append(linia);
  }

  svg.parentElement.scrollLeft = svg.parentElement.scrollWidth; // telefon: najnowsze godziny widoczne

  const suche = pomiary.filter((p) => p.sucho).length;
  const auto = podlania.filter((p) => p.zrodlo === "automat").length;
  $("podsumowanie").textContent = pomiary.length
    ? `Pomiarów: ${pomiary.length}, w tym sucho: ${Math.round((100 * suche) / pomiary.length)}%. ` +
      `Podlania: ${auto} automatycznie, ${podlania.length - auto} ręcznie.`
    : "Brak pomiarów w ostatnich 24 h.";
}

// --- historia: tabela podlań ---

let tabelaPrzedId = null;

async function zaladujTabele(dalej = false) {
  const q = dalej && tabelaPrzedId ? `&przed_id=${tabelaPrzedId}` : "";
  const strona = await api(`/api/history/podlania?limit=10${q}`);
  const tbody = $("tabelaPodlan");
  if (!dalej) tbody.replaceChildren();
  for (const p of strona.elementy) {
    const tr = document.createElement("tr");
    const faktyczny = p.czas_pracy_s === null ? "w trakcie" : `${p.czas_pracy_s.toFixed(1)} s`;
    for (const tekst of [czas(p.czas), ZRODLO[p.zrodlo], `${p.sekundy} s`, faktyczny, p.blad || "—"]) {
      const td = document.createElement("td");
      td.textContent = tekst;
      tr.append(td);
    }
    tbody.append(tr);
  }
  if (!dalej && strona.elementy.length === 0) {
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 5;
    td.textContent = "Brak podlań.";
    tr.append(td);
    tbody.append(tr);
  }
  tabelaPrzedId = strona.nastepna_strona_przed_id;
  $("starsze").hidden = !tabelaPrzedId;
}

$("starsze").addEventListener("click", () => zaladujTabele(true).catch(pokazBladHistorii));

async function odswiezHistorie() {
  const [pomiary, podlania] = await Promise.all([pobierzDobe("pomiary"), pobierzDobe("podlania")]);
  rysujWykres(pomiary, podlania);
  await zaladujTabele();
}

function pokazBladHistorii(err) {
  $("podsumowanie").textContent = `Nie udało się pobrać historii: ${err.message}`;
}

// --- start i cykliczne odświeżanie ---

const cicho = (err) => console.warn(err.message); // brak połączenia pokazuje już plakietka

zaladujUstawienia().catch((err) => nota("notaUstawienia", err.message, true));
odswiezStatus().catch(cicho);
setInterval(() => odswiezStatus().catch(cicho), 2000);
setInterval(() => odswiezHistorie().catch(pokazBladHistorii), 60000);
