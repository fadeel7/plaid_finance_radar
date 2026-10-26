// Dashboard: fetch the overview and render the hero readout, subscriptions table,
// and three charts. The data contract (GET /api/overview) is unchanged.
// Colors mirror the architectural palette in styles.css.

const COLORS = {
  income: "#3fae76",
  expense: "#d06a4e",
  accent: "#f0b645",
  neutralBar: "#37544a",
  ink: "#eef2ef",
  ink2: "#c3d0c9",
  muted: "#7d918a",
  line: "#1f2825",
  lineStrong: "#2c3a34",
};

const reduceMotion =
  window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const money = (n) =>
  (n < 0 ? "-" : "") +
  "$" +
  Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// Compact axis labels keep the chart chrome quiet: $1.2k, $950, -$2k.
const moneyAxis = (n) => {
  const sign = n < 0 ? "-" : "";
  const a = Math.abs(n);
  if (a >= 1000) return `${sign}$${(a / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 })}k`;
  return `${sign}$${a.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
};

const shortMonth = (ym) => {
  const [y, m] = ym.split("-");
  return new Date(y, m - 1).toLocaleString("en-US", { month: "short" });
};

const chartsReady = typeof Chart !== "undefined";
if (chartsReady) {
  Chart.defaults.color = COLORS.muted;
  Chart.defaults.font.family = "'IBM Plex Mono', ui-monospace, monospace";
  Chart.defaults.font.size = 11;
  Chart.defaults.borderColor = COLORS.line;
  Chart.defaults.animation = reduceMotion ? false : { duration: 480, easing: "easeOutQuart" };
}

// One shared chart system: faint grid, mono ticks, no box chrome, dark-first.
const gridX = { grid: { color: COLORS.line, drawTicks: false }, border: { display: false } };
const gridY = { grid: { color: COLORS.line, drawTicks: false }, border: { display: false } };
const baseTooltip = {
  backgroundColor: "#0e1411",
  borderColor: COLORS.lineStrong,
  borderWidth: 1,
  titleColor: COLORS.ink,
  bodyColor: COLORS.ink2,
  titleFont: { family: "'IBM Plex Mono', monospace", weight: "500" },
  bodyFont: { family: "'IBM Plex Mono', monospace" },
  padding: 10,
  cornerRadius: 4,
  displayColors: false,
};

async function load() {
  const modeText = document.getElementById("mode-text");
  let data;
  try {
    const res = await fetch("/api/overview");
    data = await res.json();
  } catch (e) {
    modeText.textContent = "offline";
    return;
  }

  modeText.textContent = data.mode + " mode";

  // Data-driven sections render regardless of the charting library.
  renderHero(data);
  renderSubs(data.subscriptions);

  // Charts render only if Chart.js loaded; the readout stays usable without it.
  if (chartsReady) {
    renderCategory(data.spending_by_category);
    renderCashflow(data.monthly_cashflow);
    renderProjection(data.projection);
  }
}

function renderHero(data) {
  const h = data.headline;
  const net = data.projection.monthly_net;

  // Split the hero figure so the currency mark and cents stay quiet around the
  // dominant integer — one memorable, deliberately set number.
  const s = money(h.monthly_subscription_cost); // e.g. "$1,736.29"
  const m = s.match(/^(-?\$)([\d,]+)(\.\d+)?$/);
  const hero = document.getElementById("hero-value");
  if (m) {
    hero.innerHTML =
      `<span class="cur">${m[1]}</span>${m[2]}<span class="dec">${m[3] || ""}</span>`;
  } else {
    hero.textContent = s;
  }

  document.getElementById("stat-count").textContent = h.subscription_count;

  const netEl = document.getElementById("stat-net");
  netEl.textContent = money(net);
  netEl.classList.add(net >= 0 ? "pos" : "neg");

  // Keep the hero note's count in sync with the data.
  const note = document.getElementById("hero-note");
  note.textContent =
    `Across ${h.subscription_count} recurring charges, detected automatically from raw ` +
    `bank transactions — subscriptions, bills and other charges that quietly repeat.`;
}

function renderSubs(subs) {
  const body = document.querySelector("#subs-table tbody");
  if (!subs.length) {
    body.innerHTML = `<tr><td colspan="6" class="empty">No recurring charges detected.</td></tr>`;
    return;
  }
  body.innerHTML = subs
    .map((s) => {
      const pct = Math.round(s.confidence * 100);
      const conf = pct >= 85 ? "" : "mid";
      return `<tr>
        <td class="merchant">${s.display_name}</td>
        <td><span class="cadence-tag">${s.cadence}</span></td>
        <td class="num charge">${money(s.amount)}</td>
        <td class="num per-month">${money(-s.monthly_cost)}</td>
        <td class="num next-date">${s.next_date}</td>
        <td class="num">
          <span class="conf">
            <span class="conf-val">${pct}%</span>
            <span class="conf-track" role="img" aria-label="confidence ${pct} percent">
              <i class="${conf}" style="width:${pct}%"></i>
            </span>
          </span>
        </td>
      </tr>`;
    })
    .join("");
}

function renderCategory(rows) {
  // Architectural accent: only the single largest outflow is amber; the rest recede.
  const maxTotal = Math.max(...rows.map((r) => r.total));
  const colors = rows.map((r) => (r.total === maxTotal ? COLORS.accent : COLORS.neutralBar));

  new Chart(document.getElementById("category-chart"), {
    type: "bar",
    data: {
      labels: rows.map((r) => r.category),
      datasets: [{ data: rows.map((r) => r.total), backgroundColor: colors, borderRadius: 2, borderSkipped: false, barThickness: 14 }],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { ...baseTooltip, callbacks: { label: (c) => money(c.parsed.x) } },
      },
      scales: {
        x: { ...gridX, ticks: { callback: moneyAxis } },
        y: { ...gridY, grid: { display: false }, ticks: { color: COLORS.ink2 } },
      },
    },
  });

  const top = rows.find((r) => r.total === maxTotal);
  const cap = document.getElementById("category-summary");
  if (cap) {
    cap.textContent =
      `Spending across ${rows.length} categories. Largest: ${top.category}, ${money(top.total)}.`;
  }
}

function renderCashflow(rows) {
  new Chart(document.getElementById("cashflow-chart"), {
    type: "bar",
    data: {
      labels: rows.map((r) => shortMonth(r.month)),
      datasets: [
        { label: "Income", data: rows.map((r) => r.income), backgroundColor: COLORS.income, borderRadius: 2, borderSkipped: false },
        { label: "Expenses", data: rows.map((r) => r.expense), backgroundColor: COLORS.expense, borderRadius: 2, borderSkipped: false },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { ...baseTooltip, displayColors: true, callbacks: { label: (c) => `${c.dataset.label}: ${money(c.parsed.y)}` } },
      },
      scales: {
        x: { ...gridX, grid: { display: false } },
        y: { ...gridY, ticks: { callback: moneyAxis } },
      },
    },
  });
  document.getElementById("cashflow-legend").innerHTML =
    `<span><i class="swatch" style="background:${COLORS.income}"></i>Income</span>
     <span><i class="swatch" style="background:${COLORS.expense}"></i>Expenses</span>`;
}

function renderProjection(proj) {
  const pts = proj.points;

  // Emphasise "now" (month 0) as the instrument's current reading.
  const pointColors = pts.map((p) => (p.month === 0 ? COLORS.accent : "#11161388"));
  const pointRadii = pts.map((p) => (p.month === 0 ? 5 : 3));

  new Chart(document.getElementById("projection-chart"), {
    type: "line",
    data: {
      labels: pts.map((p) => (p.month === 0 ? "now" : `+${p.month}mo`)),
      datasets: [{
        label: "Projected balance",
        data: pts.map((p) => p.balance),
        borderColor: COLORS.accent,
        backgroundColor: COLORS.accentWash || "rgba(240,182,69,0.10)",
        borderWidth: 2,
        fill: true,
        tension: 0.3,
        pointRadius: pointRadii,
        pointHoverRadius: 6,
        pointBackgroundColor: pointColors,
        pointBorderColor: COLORS.accent,
        pointBorderWidth: 1.5,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { ...baseTooltip, callbacks: { label: (c) => money(c.parsed.y) } },
      },
      scales: {
        x: { ...gridX, grid: { display: false } },
        y: { ...gridY, ticks: { callback: moneyAxis } },
      },
    },
  });

  const end = pts[pts.length - 1];
  const cap = document.getElementById("projection-summary");
  if (cap) {
    cap.textContent =
      `Projected balance from ${money(pts[0].balance)} now to ${money(end.balance)} in ` +
      `${end.month} months, at ${money(proj.monthly_net)} net per month.`;
  }
}

load();
