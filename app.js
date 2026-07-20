const STATUS_LABEL = { up: "Operational", degraded: "Degraded", down: "Down" };
const HISTORY_BARS = 40;

function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function worstStatus(statuses) {
  if (statuses.includes("down")) return "down";
  if (statuses.includes("degraded")) return "degraded";
  return "up";
}

function renderService(service) {
  const status = service.current_status || "down";
  const history = (service.history || []).slice(-HISTORY_BARS);
  const bars = history
    .map((h) => `<div class="history-bar history-bar--${h.status}" title="${formatTime(h.timestamp)} · ${h.status}"></div>`)
    .join("");

  return `
    <div class="service">
      <div class="service-top">
        <div>
          <div class="service-name">${service.name}</div>
          <div class="service-url">${service.url}</div>
        </div>
        <span class="pill pill--${status}">${STATUS_LABEL[status] ?? status}</span>
      </div>
      <div class="service-meta">
        <span>Response: <strong>${service.last_response_ms ?? "—"}ms</strong></span>
        <span>Uptime (24h): <strong>${service.uptime_24h_pct ?? "—"}%</strong></span>
        <span>Uptime (7d): <strong>${service.uptime_7d_pct ?? "—"}%</strong></span>
        <span>Checked: <strong>${formatTime(service.last_checked)}</strong></span>
      </div>
      <div class="history">${bars || "<span style='color:var(--muted);font-size:0.8rem;'>No history yet</span>"}</div>
    </div>
  `;
}

async function main() {
  const banner = document.getElementById("overall-banner");
  const container = document.getElementById("services");
  const lastRunEl = document.getElementById("last-run");

  try {
    const res = await fetch("status.json", { cache: "no-store" });
    if (!res.ok) throw new Error(`status.json ${res.status}`);
    const data = await res.json();
    const services = Object.values(data.services || {});

    if (services.length === 0) {
      banner.textContent = "No checks recorded yet.";
      banner.className = "banner banner--loading";
      return;
    }

    const overall = worstStatus(services.map((s) => s.current_status));
    banner.className = `banner banner--${overall}`;
    banner.textContent =
      overall === "up" ? "All systems operational" :
      overall === "degraded" ? "Some services are degraded" :
      "Some services are down";

    container.innerHTML = services.map(renderService).join("");
    lastRunEl.textContent = `Last checked: ${formatTime(data.last_run)}`;
  } catch (err) {
    banner.className = "banner banner--down";
    banner.textContent = "Couldn't load status data.";
    console.error(err);
  }
}

main();
