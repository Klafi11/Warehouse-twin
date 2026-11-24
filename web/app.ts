// Vanilla Canvas client. Compile with `npx -p typescript tsc -p web`; the compiled
// app.js is committed, so running the app needs no Node.

type StationKind = "packing" | "inbound_dock" | "back_room" | "charger" | "repair_bay";

interface Config {
  width: number;
  height: number;
  products: { sku: string; name: string }[];
  aisles: { aisle_id: string; x: number; y: number; width: number; height: number }[];
  shelf_slots: { slot_id: string; x: number; y: number; sku: string }[];
  stations: { station_id: string; kind: StationKind; x: number; y: number }[];
  robots: { robot_id: string; x: number; y: number }[];
}

interface State {
  speed: number;
  snapshot: {
    run_id: string;
    seed: number;
    tick: number;
    simulated_time: string;
    status: "running" | "paused" | "ended";
    config: Config;
  };
}

const STATION_STYLE: Record<StationKind, { color: string; label: string }> = {
  packing: { color: "#2f9e44", label: "Packing station" },
  inbound_dock: { color: "#1c7ed6", label: "Inbound dock" },
  back_room: { color: "#7048e8", label: "Back room" },
  charger: { color: "#f59f00", label: "Charger" },
  repair_bay: { color: "#e03131", label: "Repair bay" },
};
const AISLE_COLOR = "#dee2e6";
const SHELF_COLOR = "#868e96";
const ROBOT_COLOR = "#212529";

const el = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;
const canvas = el<HTMLCanvasElement>("map");
const ctx = canvas.getContext("2d")!;
let state: State | null = null;

function draw(): void {
  if (!state) return;
  const { config } = state.snapshot;
  const cell = Math.floor(Math.min(canvas.width / config.width, canvas.height / config.height));
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  ctx.strokeStyle = "#0001";
  for (let x = 0; x <= config.width; x++) line(x * cell, 0, x * cell, config.height * cell);
  for (let y = 0; y <= config.height; y++) line(0, y * cell, config.width * cell, y * cell);

  ctx.fillStyle = AISLE_COLOR;
  for (const a of config.aisles) ctx.fillRect(a.x * cell, a.y * cell, a.width * cell, a.height * cell);

  ctx.font = `${Math.floor(cell / 4)}px system-ui`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  for (const s of config.shelf_slots) box(s.x, s.y, SHELF_COLOR, s.sku.replace("SKU-", "#"), cell);
  for (const s of config.stations) box(s.x, s.y, STATION_STYLE[s.kind].color, s.station_id, cell);

  for (const r of config.robots) {
    ctx.fillStyle = ROBOT_COLOR;
    ctx.beginPath();
    ctx.arc((r.x + 0.5) * cell, (r.y + 0.5) * cell, cell * 0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.fillText(r.robot_id, (r.x + 0.5) * cell, (r.y + 0.5) * cell);
  }
}

function line(x1: number, y1: number, x2: number, y2: number): void {
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

function box(x: number, y: number, color: string, label: string, cell: number): void {
  ctx.fillStyle = color;
  ctx.fillRect(x * cell + 3, y * cell + 3, cell - 6, cell - 6);
  ctx.fillStyle = "#fff";
  ctx.fillText(label, (x + 0.5) * cell, (y + 0.5) * cell);
}

function render(next: State): void {
  const first = state === null;
  state = next;
  const s = next.snapshot;
  el("status").textContent = s.status;
  el<HTMLButtonElement>("toggle").textContent = s.status === "paused" ? "Resume" : "Pause";
  el<HTMLButtonElement>("toggle").disabled = s.status === "ended";
  const speedSelect = el<HTMLSelectElement>("speed");
  if (![...speedSelect.options].some((o) => Number(o.value) === next.speed)) {
    speedSelect.add(new Option(`${next.speed}×`, String(next.speed)));
  }
  speedSelect.value = String(next.speed);
  el("info").innerHTML =
    `<dt>Run</dt><dd>${s.run_id.slice(0, 8)}</dd><dt>Seed</dt><dd>${s.seed}</dd>` +
    `<dt>Tick</dt><dd>${s.tick}</dd><dt>Sim time</dt><dd>${s.simulated_time.slice(11, 19)}</dd>`;
  if (first) {
    el<HTMLInputElement>("seed").value = String(s.seed);
    el("legend").innerHTML = Object.values(STATION_STYLE)
      .concat([{ color: SHELF_COLOR, label: "Shelf slot" }, { color: AISLE_COLOR, label: "Aisle" }])
      .map((v) => `<li><i style="background:${v.color}"></i>${v.label}</li>`)
      .join("");
  }
  draw();
}

async function control(body: Record<string, unknown>): Promise<void> {
  const res = await fetch("/api/control", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.ok) render(await res.json());
  else el("status").textContent = `request rejected (${res.status})`;
}

el("toggle").addEventListener("click", () =>
  control({ action: state?.snapshot.status === "paused" ? "resume" : "pause" }),
);
el("speed").addEventListener("change", (e) =>
  control({ action: "speed", speed: Number((e.target as HTMLSelectElement).value) }),
);
el("reset").addEventListener("click", () =>
  {
    const seed = Number(el<HTMLInputElement>("seed").value);
    if (Number.isSafeInteger(seed)) control({ action: "reset", seed });
    else el("status").textContent = "seed must be a whole number";
  },
);

function connect(): void {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onmessage = (m) => render(JSON.parse(m.data));
  ws.onclose = () => {
    el("status").textContent = "disconnected, retrying…";
    setTimeout(connect, 1000);
  };
}
connect();
