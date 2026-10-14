"use strict";

const $ = (selector) => document.querySelector(selector);
const POLL_MS = 30000;
const PAGE = 25;
const GIB = 1024 ** 3;
const state = { csrf: null, busy: false, timer: null, clock: null, pendingConfirm: null, items: [], shown: 0, selected: -1 };

const formatBytes = (value) => {
  if (!Number.isFinite(value)) return "?";
  const units = ["B", "K", "M", "G", "T"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) { amount /= 1024; index += 1; }
  return `${amount >= 10 || index === 0 ? amount.toFixed(0) : amount.toFixed(1)}${units[index]}`;
};

const formatDuration = (seconds) => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return [days ? `${days}d` : "", hours ? `${hours}h` : "", `${minutes}m`].filter(Boolean).join("");
};

const pad = (value) => String(value).padStart(2, "0");
const hms = (date) => `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
const ymd = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const plural = (count, word) => `${count} ${word}${count === 1 ? "" : "s"}`;
// Text-mode usage bar, e.g. ██████░░░░
const bar = (fraction, width = 10) => {
  const filled = Math.round(Math.min(Math.max(fraction, 0), 1) * width);
  return `<span class="bar">${"█".repeat(filled)}<i>${"░".repeat(width - filled)}</i></span>`;
};

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.csrf && options.method === "POST") headers["X-CSRF-Token"] = state.csrf;
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  let payload;
  try { payload = await response.json(); } catch { payload = { error: `HTTP ${response.status}` }; }
  if (response.status === 401 && path !== "/api/login") {
    showLogin();
    throw new Error("session ended; sign in again");
  }
  if (!response.ok || payload.ok === false) throw new Error(payload.error || `request failed (${response.status})`);
  return payload;
}

const appVisible = () => !$("#app-view").hidden;

function tick() { $("#clock").textContent = hms(new Date()); }

function stopTimers() {
  clearInterval(state.timer);
  clearInterval(state.clock);
  state.timer = state.clock = null;
}

// Polling and the clock stop while the tab is in the background so idle tabs cost the Pi nothing.
function startTimers() {
  stopTimers();
  if (document.hidden || !appVisible()) return;
  tick();
  state.clock = setInterval(tick, 1000);
  state.timer = setInterval(refreshStatus, POLL_MS);
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) stopTimers();
  else if (appVisible()) { refreshStatus(); startTimers(); }
});

function showLogin() {
  stopTimers();
  $("#app-view").hidden = true;
  $("#login-view").hidden = false;
  $("#password").value = "";
  $("#username").focus();
}

function showApp() {
  $("#login-view").hidden = true;
  $("#app-view").hidden = false;
  refreshAll();
  startTimers();
}

function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = `${error ? "ERR" : "OK "} ${message}`;
  element.classList.toggle("err", error);
  element.hidden = false;
  clearTimeout(element.hideTimer);
  element.hideTimer = setTimeout(() => { element.hidden = true; }, 4000);
}

function setBusy(busy, label = "working") {
  state.busy = busy;
  document.body.classList.toggle("busy", busy);
  ["#power-button", "#restart-button", "#retention-button", "#refresh-button", "#delete-all-button", "#restore-all-button"].forEach((id) => { $(id).disabled = busy; });
  if (busy) $("#service-detail").textContent = `${label}…`;
}

function metric(id, html, tone = "") {
  const element = $(id);
  element.className = `${element.classList.contains("span") ? "span " : ""}${tone ? `is-${tone}` : ""}`;
  element.querySelector("dd").innerHTML = html;
}

function renderStatus(data) {
  const live = data.service.active === "active";
  const healthy = live && data.camera && data.dashboard;
  const mode = healthy ? "live" : live ? "degraded" : "stopped";
  $("#header-state").className = `tag ${mode}`;
  $("#header-state").textContent = healthy ? "● REC" : live ? "▲ WARN" : "■ OFF";
  $("#state-dot").className = `lamp ${mode}`;
  $("#state-label").className = `state-label ${mode}`;
  $("#state-label").textContent = healthy ? "RECORDING" : live ? "DEGRADED" : "STOPPED";
  $("#service-detail").textContent = healthy
    ? "camera online · recorder responding"
    : live ? "recorder running · a health check failed" : "recording stopped · pi still powered";

  const power = $("#power-button");
  power.disabled = state.busy;
  power.dataset.mode = live ? "stop" : "start";
  power.className = `cmd power ${live ? "stop" : "start"}`;
  power.querySelector("span").textContent = live ? "stop recording" : "start recording";

  const diskUsed = 1 - data.disk.free / (data.disk.total || 1);
  const memTotal = data.memory.MemTotal || 0;
  const memUsed = memTotal ? 1 - (data.memory.MemAvailable || 0) / memTotal : 0;
  const storageOk = data.disk.free >= 8 * GIB;
  const timerValues = Object.values(data.timers);
  const timersUp = timerValues.filter((value) => value === "active").length;
  const timersOk = timersUp === timerValues.length;
  const powerOk = data.power === "throttled=0x0";

  metric("#m-camera", data.camera ? "online" : "MISSING", data.camera ? "" : "bad");
  metric("#m-power", powerOk ? "ok" : escapeHtml(data.power.replace("throttled=", "")), powerOk ? "" : "warn");
  metric("#m-temp", escapeHtml(data.temperature));
  metric("#m-timers", `${timersUp}/${timerValues.length}`, timersOk ? "" : "bad");
  metric("#m-disk", `${bar(diskUsed)} ${formatBytes(data.disk.free)} free / ${formatBytes(data.disk.total)}`, storageOk ? "" : "bad");
  metric("#m-mem", `${bar(memUsed)} ${formatBytes(data.memory.MemAvailable || 0)} free / ${formatBytes(memTotal)}`, memUsed > .9 ? "warn" : "");
  metric("#m-uptime", formatDuration(data.uptime));
  metric("#m-restarts", escapeHtml(data.service.restarts || "0"), Number(data.service.restarts) > 0 ? "warn" : "");
  metric("#m-quarantine", `${plural(data.quarantine.count, "file")} · ${formatBytes(data.quarantine.bytes)}`);

  const warnings = [];
  if (!data.camera) warnings.push(["bad", "CAM", "camera not detected: check the USB cable, then restart"]);
  if (!storageOk) warnings.push(["bad", "DISK", "under 8G free: run cleanup or move recordings off the card"]);
  if (!timersOk) warnings.push(["bad", "TIMERS", "a health, cleanup, or quarantine timer is not active"]);
  if (!powerOk) warnings.push(["", "PWR", `${data.power}: undervoltage can corrupt recordings; check the supply`]);
  const alerts = $("#alerts");
  alerts.textContent = "";
  warnings.forEach(([tone, title, copy]) => {
    const row = document.createElement("div");
    row.className = `alert ${tone}`;
    const label = document.createElement("b");
    label.textContent = `!! ${title}`;
    const text = document.createElement("span");
    text.textContent = copy;
    row.append(label, text);
    alerts.append(row);
  });

  $("#quarantine-banner").hidden = data.quarantine.count === 0;
  $("#quarantine-count").textContent = `${plural(data.quarantine.count, "file")} in quarantine · auto-erased after 24h`;
  $("#last-updated").textContent = `sync ${hms(new Date())}`;
}

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = String(value);
  return element.innerHTML;
}

async function refreshStatus() {
  if (state.busy || !appVisible()) return;
  try { renderStatus(await api("/api/status")); }
  catch (error) {
    $("#header-state").className = "tag degraded";
    $("#header-state").textContent = "▲ LINK";
    toast(error.message, true);
  }
}

function cell(className, content) {
  const td = document.createElement("td");
  td.className = className;
  if (typeof content === "string") td.textContent = content;
  else td.append(...content);
  return td;
}

function glyphButton(tag, cls, glyph, label) {
  const element = document.createElement(tag);
  element.className = `ib ${cls}`;
  element.title = label;
  element.setAttribute("aria-label", label);
  element.textContent = `${glyph}︎`;
  return element;
}

function renderMore() {
  const fragment = document.createDocumentFragment();
  state.items.slice(state.shown, state.shown + PAGE).forEach((item, offset) => {
    const index = state.shown + offset;
    const when = new Date(item.modified * 1000);
    const row = document.createElement("tr");
    row.dataset.index = index;
    const file = cell("f", item.name);
    file.title = item.relative;
    const play = glyphButton("button", "", "▶", "Play");
    play.type = "button";
    play.dataset.play = index;
    const download = glyphButton("a", "", "↓", "Download");
    download.href = `/media/${encodeURIComponent(item.id)}`;
    download.download = item.name;
    const remove = glyphButton("button", "del", "✕", "Move to quarantine");
    remove.type = "button";
    remove.dataset.remove = index;
    row.append(cell("d", ymd(when)), cell("t", hms(when)), file, cell("n", formatBytes(item.bytes)), cell("n a", [play, download, remove]));
    fragment.append(row);
  });
  $("#recording-list").append(fragment);
  state.shown = Math.min(state.shown + PAGE, state.items.length);
  $("#more-button").hidden = state.shown >= state.items.length;
  $("#more-count").textContent = state.items.length ? `showing ${state.shown}/${state.items.length}` : "";
}

async function refreshRecordings() {
  try {
    const data = await api("/api/recordings");
    $("#recording-summary").textContent = `${plural(data.total, "file")} · ${formatBytes(data.bytes)}${data.limited ? ` · newest ${data.items.length}` : ""}`;
    state.items = data.items;
    state.shown = 0;
    state.selected = -1;
    $("#recording-list").textContent = "";
    renderMore();
    $("#empty-recordings").hidden = data.items.length !== 0;
    $("#recording-table").hidden = data.items.length === 0;
  } catch (error) { toast(error.message, true); }
}

async function refreshAll() { await Promise.all([refreshStatus(), refreshRecordings()]); }

async function run(label, request, settleMs = 800) {
  setBusy(true, label);
  try {
    const result = await request();
    toast(result.message);
    await new Promise((resolve) => setTimeout(resolve, settleMs));
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); await refreshAll(); }
}

const post = (path, body = {}) => () => api(path, { method: "POST", body: JSON.stringify(body) });
const action = (name, label) => run(label, post("/api/action", { action: name }), name === "restart" || name === "start" ? 12000 : 1200);

function askConfirm({ title, copy, phrase = "", confirmLabel = "confirm", callback }) {
  $("#confirm-title").textContent = title;
  $("#confirm-copy").textContent = copy;
  $("#confirm-input").value = "";
  $("#confirm-label").hidden = !phrase;
  $("#confirm-label span").textContent = phrase ? `type "${phrase}" to continue` : "";
  $("#confirm-submit").textContent = confirmLabel;
  state.pendingConfirm = { phrase, callback };
  $("#confirm-dialog").showModal();
  (phrase ? $("#confirm-input") : $("#confirm-submit")).focus();
}

$("#confirm-form").addEventListener("submit", (event) => {
  if (event.submitter?.value !== "confirm") { state.pendingConfirm = null; return; }
  const pending = state.pendingConfirm;
  if (!pending) return;
  if (pending.phrase && $("#confirm-input").value !== pending.phrase) {
    event.preventDefault();
    toast("confirmation phrase does not match", true);
    return;
  }
  state.pendingConfirm = null;
  queueMicrotask(pending.callback);
});

// The player element is created on open and destroyed on close so no video stays buffered in memory.
function openPlayer(item) {
  if (!item) return;
  const media = document.createElement(item.kind === "image" ? "img" : "video");
  media.src = `/media/${encodeURIComponent(item.id)}`;
  if (item.kind === "image") media.alt = item.name;
  else { media.controls = true; media.autoplay = true; media.preload = "metadata"; }
  $("#player-body").replaceChildren(media);
  const when = new Date(item.modified * 1000);
  $("#player-title").textContent = `${ymd(when)} ${hms(when)} · ${item.name}`;
  $("#player-dialog").showModal();
}

$("#player-dialog").addEventListener("close", () => {
  const video = $("#player-body video");
  if (video) { video.pause(); video.removeAttribute("src"); video.load(); }
  $("#player-body").replaceChildren();
});
$("#player-close").addEventListener("click", () => $("#player-dialog").close());

function confirmQuarantine(item) {
  if (!item) return;
  askConfirm({
    title: "move to quarantine?",
    copy: `${item.name} can be restored for 24h before it is erased.`,
    confirmLabel: "move",
    callback: () => run("moving to quarantine", post("/api/recordings/quarantine", { id: item.id }), 0),
  });
}

function select(index) {
  const rows = $("#recording-list").children;
  if (!rows.length) return;
  rows[state.selected]?.classList.remove("selected");
  state.selected = Math.min(Math.max(index, 0), rows.length - 1);
  rows[state.selected].classList.add("selected");
  rows[state.selected].scrollIntoView({ block: "nearest" });
}

$("#recording-list").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  const row = event.target.closest("tr");
  if (row) select(Number(row.dataset.index));
  if (!button) return;
  if (button.dataset.play !== undefined) openPlayer(state.items[Number(button.dataset.play)]);
  else confirmQuarantine(state.items[Number(button.dataset.remove)]);
});

$("#more-button").addEventListener("click", renderMore);

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  $("#login-error").textContent = "";
  try {
    const result = await api("/api/login", { method: "POST", body: JSON.stringify({ username: $("#username").value, password: $("#password").value }) });
    state.csrf = result.csrf;
    showApp();
  } catch (error) { $("#login-error").textContent = `! ${error.message}`; }
  finally { submit.disabled = false; }
});

async function logout() {
  try { await api("/api/logout", { method: "POST", body: "{}" }); } catch { /* session is closed locally */ }
  state.csrf = null;
  showLogin();
}

function togglePower() {
  if ($("#power-button").disabled) return;
  if ($("#power-button").dataset.mode === "start") { action("start", "starting recorder"); return; }
  askConfirm({
    title: "stop recording?",
    copy: "The camera and motion recorder stop. The Raspberry Pi and this panel stay on.",
    confirmLabel: "stop recording",
    callback: () => action("stop", "stopping recorder"),
  });
}

function quarantineAll() {
  askConfirm({
    title: "quarantine every recording?",
    copy: "Recording pauses briefly while files are moved. They can be restored for 24h.",
    phrase: "QUARANTINE ALL RECORDINGS",
    confirmLabel: "quarantine all",
    callback: () => run("quarantining all recordings", post("/api/recordings/quarantine-all", { confirmation: "QUARANTINE ALL RECORDINGS" }), 0),
  });
}

async function toggleLogs() {
  const panel = $("#log-panel");
  if (!panel.hidden) { panel.hidden = true; $("#logs").textContent = ""; return; }
  panel.hidden = false;
  $("#logs").textContent = "loading…";
  try {
    const result = await api("/api/logs");
    $("#logs").textContent = result.lines.join("\n") || "-- no recent log entries --";
  } catch (error) { $("#logs").textContent = `! ${error.message}`; }
}

$("#logout-button").addEventListener("click", logout);
$("#power-button").addEventListener("click", togglePower);
$("#restart-button").addEventListener("click", () => action("restart", "restarting recorder"));
$("#retention-button").addEventListener("click", () => action("retention", "running cleanup"));
$("#refresh-button").addEventListener("click", refreshAll);
$("#delete-all-button").addEventListener("click", quarantineAll);
$("#restore-all-button").addEventListener("click", () => run("restoring quarantine", post("/api/quarantine/restore-all"), 0));
$("#load-logs-button").addEventListener("click", toggleLogs);
$("#hide-logs-button").addEventListener("click", toggleLogs);

const keys = {
  s: togglePower,
  r: () => !state.busy && action("restart", "restarting recorder"),
  c: () => !state.busy && action("retention", "running cleanup"),
  f: refreshAll,
  l: toggleLogs,
  q: logout,
  Q: () => !state.busy && quarantineAll(),
  j: () => select(state.selected + 1),
  k: () => select(state.selected - 1),
  ArrowDown: () => select(state.selected + 1),
  ArrowUp: () => select(state.selected - 1),
  Enter: () => openPlayer(state.items[state.selected]),
  x: () => !state.busy && confirmQuarantine(state.items[state.selected]),
};

document.addEventListener("keydown", (event) => {
  if (!appVisible() || event.ctrlKey || event.metaKey || event.altKey) return;
  if (document.querySelector("dialog[open]") || event.target.closest("input, textarea")) return;
  if (event.key === "Enter" && event.target.closest("button, a")) return;
  const handler = keys[event.key];
  if (!handler) return;
  event.preventDefault();
  handler();
});

(async () => {
  try {
    const session = await api("/api/session");
    if (session.authenticated) { state.csrf = session.csrf; showApp(); }
    else showLogin();
  } catch { showLogin(); }
})();
