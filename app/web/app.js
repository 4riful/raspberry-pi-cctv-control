"use strict";

const $ = (selector) => document.querySelector(selector);
const state = { csrf: null, busy: false, timer: null, pendingConfirm: null };

const formatBytes = (value) => {
  if (!Number.isFinite(value)) return "Unknown";
  const units = ["B", "KiB", "MiB", "GiB", "TiB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) { amount /= 1024; index += 1; }
  return `${amount >= 10 || index === 0 ? amount.toFixed(0) : amount.toFixed(1)} ${units[index]}`;
};

const formatDuration = (seconds) => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return [days ? `${days}d` : "", hours ? `${hours}h` : "", `${minutes}m`].filter(Boolean).join(" ");
};

const formatDate = (epoch) => new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium", timeStyle: "medium", hour12: true,
}).format(new Date(epoch * 1000));

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.csrf && options.method === "POST") headers["X-CSRF-Token"] = state.csrf;
  const response = await fetch(path, { credentials: "same-origin", ...options, headers });
  let payload;
  try { payload = await response.json(); } catch { payload = { error: `HTTP ${response.status}` }; }
  if (response.status === 401 && path !== "/api/login") {
    showLogin();
    throw new Error("Your session ended. Sign in again.");
  }
  if (!response.ok || payload.ok === false) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function showLogin() {
  clearInterval(state.timer);
  $("#app-view").hidden = true;
  $("#login-view").hidden = false;
  $("#password").value = "";
  $("#username").focus();
}

function showApp() {
  $("#login-view").hidden = true;
  $("#app-view").hidden = false;
  refreshAll();
  clearInterval(state.timer);
  state.timer = setInterval(refreshStatus, 15000);
}

function toast(message, error = false) {
  const element = $("#toast");
  element.textContent = message;
  element.style.background = error ? "var(--red)" : "var(--ink)";
  element.hidden = false;
  clearTimeout(element.hideTimer);
  element.hideTimer = setTimeout(() => { element.hidden = true; }, 5000);
}

function setBusy(busy, label = "Dispatching command") {
  state.busy = busy;
  document.body.classList.toggle("busy", busy);
  ["#quick-power-button", "#restart-button", "#retention-button", "#refresh-button", "#delete-all-button"].forEach((id) => { $(id).disabled = busy; });
  if (busy) {
    $("#header-state").textContent = label;
    $("#primary-state").textContent = "Pending";
    $("#primary-state").className = "visually-hidden";
  }
}

function markStage(name, good, text) {
  const item = document.querySelector(`[data-stage="${name}"]`);
  item.classList.toggle("live", good);
  item.classList.toggle("problem", !good);
  const label = $(`#stage-${name}`);
  if (label) label.textContent = text;
}

function renderStatus(data) {
  const serviceLive = data.service.active === "active";
  const healthy = serviceLive && data.camera && data.dashboard;
  const degraded = serviceLive && !healthy;
  const mode = healthy ? "live" : degraded ? "degraded" : "stopped";
  const label = healthy ? "Recording on" : degraded ? "Needs attention" : "Recording off";
  $("#header-dot").className = `status-dot ${mode}`;
  $("#header-state").textContent = label;
  $("#state-lamp").className = `state-lamp ${mode}`;
  $("#primary-state").textContent = healthy ? "Recorder active" : degraded ? "Attention needed" : "Recorder stopped";
  $("#overview-title").textContent = healthy ? "Recording is on" : degraded ? "Recording needs attention" : "Recording is off";
  $("#service-detail").textContent = healthy
    ? "Camera, recorder, and local dashboard are responding."
    : serviceLive ? "The recorder is running, but one or more checks require attention." : "The CCTV service is not recording. Start it when ready.";

  markStage("camera", data.camera, data.camera ? "Connected" : "Missing");
  markStage("recorder", serviceLive && data.dashboard, serviceLive ? (data.dashboard ? "Responding" : "UI unavailable") : "Stopped");
  markStage("storage", data.disk.free >= 8 * 1024 ** 3, `${formatBytes(data.disk.free)} free`);
  const timersGood = Object.values(data.timers).every((value) => value === "active");
  markStage("retention", timersGood, timersGood ? "Timers active" : "Timer fault");
  const warnings = [];
  if (data.power !== "throttled=0x0") warnings.push(["Power warning", `${data.power}. Undervoltage can corrupt recordings or stop USB devices; software cannot repair the power supply.`]);
  if (!data.camera) warnings.push(["Camera missing", "Check the camera USB connection and power before restarting services."]);
  if (data.disk.free < 8 * 1024 ** 3) warnings.push(["Storage reserve", "Free space is below 8 GiB. Run cleanup and move recordings off the microSD."]);
  if (!timersGood) warnings.push(["Timer fault", "One or more health, retention, or quarantine timers are not active."]);
  const warningIcons = { "Power warning": "bolt", "Camera missing": "camera", "Storage reserve": "storage", "Timer fault": "clock" };
  $("#alerts").innerHTML = warnings.map(([title, copy]) => `<div class="alert"><strong>${icon(warningIcons[title] || "heartbeat")}${escapeHtml(title)}</strong><span>${escapeHtml(copy)}</span></div>`).join("");

  const power = $("#diag-power");
  power.textContent = data.power === "throttled=0x0" ? "Normal · throttled=0x0" : `Attention · ${data.power}`;
  power.className = data.power === "throttled=0x0" ? "good" : "warning";
  $("#diag-temp").textContent = data.temperature;
  $("#diag-storage").textContent = `${formatBytes(data.disk.free)} of ${formatBytes(data.disk.total)}`;
  $("#diag-memory").textContent = `${formatBytes(data.memory.MemAvailable || 0)} of ${formatBytes(data.memory.MemTotal || 0)}`;
  $("#diag-restarts").textContent = data.service.restarts || "0";
  $("#diag-uptime").textContent = formatDuration(data.uptime);
  $("#diag-health").textContent = timersGood ? "All timers active" : Object.entries(data.timers).map(([name, value]) => `${name}: ${value}`).join(" · ");
  $("#diag-quarantine").textContent = `${data.quarantine.count} files · ${formatBytes(data.quarantine.bytes)}`;
  const quickPower = $("#quick-power-button");
  quickPower.disabled = state.busy;
  quickPower.dataset.mode = serviceLive ? "stop" : "start";
  quickPower.className = `power-control ${serviceLive ? "stop" : "start"}`;
  quickPower.querySelector("span").textContent = serviceLive ? "Turn CCTV off" : "Turn CCTV on";
  $("#last-updated").textContent = `Updated ${new Date().toLocaleTimeString([], { hour12: true })}`;
  renderQuarantine(data.quarantine);
}

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = String(value);
  return element.innerHTML;
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function icon(name) {
  return `<svg class="icon" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
}

async function refreshStatus() {
  if (state.busy || $("#app-view").hidden) return;
  try { renderStatus(await api("/api/status")); }
  catch (error) {
    $("#header-dot").className = "status-dot degraded";
    $("#header-state").textContent = "Control link unavailable";
    toast(error.message, true);
  }
}

async function refreshRecordings() {
  try {
    const data = await api("/api/recordings");
    $("#recording-summary").textContent = `${data.total} recording${data.total === 1 ? "" : "s"} · ${formatBytes(data.bytes)}${data.limited ? " · showing newest 250" : ""}`;
    const list = $("#recording-list");
    list.textContent = "";
    data.items.forEach((item) => {
      const row = document.createElement("li");
      const mediaUrl = `/media/${encodeURIComponent(item.id)}`;
      row.innerHTML = `
        <time class="recording-time" datetime="${new Date(item.modified * 1000).toISOString()}">${escapeHtml(formatDate(item.modified))}</time>
        <span class="recording-name" title="${escapeAttr(item.relative)}">${escapeHtml(item.name)}</span>
        <span class="recording-size">${escapeHtml(formatBytes(item.bytes))}</span>
        <span class="recording-actions">
          <a class="recording-action primary" href="${mediaUrl}" target="_blank" rel="noopener">${icon("play")}<span>Play</span></a>
          <a class="recording-action" href="${mediaUrl}" download="${escapeAttr(item.name)}">${icon("download")}<span>Download</span></a>
          <button class="recording-action remove" type="button" data-id="${escapeAttr(item.id)}" data-name="${escapeAttr(item.name)}">${icon("quarantine")}<span>Quarantine</span></button>
        </span>`;
      list.append(row);
    });
    $("#empty-recordings").hidden = data.items.length !== 0;
  } catch (error) { toast(error.message, true); }
}

function renderQuarantine(quarantine) {
  const banner = $("#quarantine-banner");
  banner.hidden = quarantine.count === 0;
  $("#quarantine-count").textContent = `${quarantine.count} recording${quarantine.count === 1 ? "" : "s"} in quarantine · ${formatBytes(quarantine.bytes)}`;
}

async function refreshAll() { await Promise.all([refreshStatus(), refreshRecordings()]); }

async function action(name, label) {
  setBusy(true, label);
  try {
    const result = await api("/api/action", { method: "POST", body: JSON.stringify({ action: name }) });
    toast(result.message);
    await new Promise((resolve) => setTimeout(resolve, name === "restart" || name === "start" ? 12000 : 1200));
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); await refreshAll(); }
}

function askConfirm({ title, copy, phrase = "", confirmLabel = "Confirm", callback }) {
  const dialog = $("#confirm-dialog");
  $("#confirm-title").textContent = title;
  $("#confirm-copy").textContent = copy;
  $("#confirm-input").value = "";
  $("#confirm-input").hidden = !phrase;
  $("#confirm-label").hidden = !phrase;
  $("#confirm-label").textContent = phrase ? `Type “${phrase}” to continue` : "";
  $("#confirm-submit").textContent = confirmLabel;
  state.pendingConfirm = { phrase, callback };
  dialog.showModal();
  (phrase ? $("#confirm-input") : $("#confirm-submit")).focus();
}

$("#confirm-form").addEventListener("submit", (event) => {
  if (event.submitter?.value !== "confirm") { state.pendingConfirm = null; return; }
  const pending = state.pendingConfirm;
  if (!pending) return;
  if (pending.phrase && $("#confirm-input").value !== pending.phrase) {
    event.preventDefault();
    toast("The confirmation phrase does not match", true);
    return;
  }
  state.pendingConfirm = null;
  queueMicrotask(pending.callback);
});

$("#login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  $("#login-error").textContent = "";
  try {
    const result = await api("/api/login", { method: "POST", body: JSON.stringify({ username: $("#username").value, password: $("#password").value }) });
    state.csrf = result.csrf;
    showApp();
  } catch (error) { $("#login-error").textContent = error.message; }
  finally { submit.disabled = false; }
});

$("#logout-button").addEventListener("click", async () => {
  try { await api("/api/logout", { method: "POST", body: "{}" }); } catch { /* session is closed locally */ }
  state.csrf = null;
  showLogin();
});
const confirmStop = () => askConfirm({ title: "Turn CCTV off?", copy: "This stops the camera and motion recording service. The control portal and Raspberry Pi stay powered on.", confirmLabel: "Turn CCTV off", callback: () => action("stop", "Turning CCTV off") });
$("#quick-power-button").addEventListener("click", () => {
  if ($("#quick-power-button").dataset.mode === "start") action("start", "Turning CCTV on");
  else confirmStop();
});
$("#restart-button").addEventListener("click", () => action("restart", "Restarting recording line"));
$("#retention-button").addEventListener("click", () => action("retention", "Running retention cleanup"));
$("#refresh-button").addEventListener("click", refreshAll);

$("#recording-list").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-id]");
  if (!button) return;
  askConfirm({
    title: "Quarantine recording?",
    copy: `${button.dataset.name} will leave the recording board now. You can restore it for 24 hours before permanent cleanup.`,
    confirmLabel: "Move to quarantine",
    callback: async () => {
      setBusy(true, "Moving recording to quarantine");
      try {
        const result = await api("/api/recordings/quarantine", { method: "POST", body: JSON.stringify({ id: button.dataset.id }) });
        toast(result.message);
      } catch (error) { toast(error.message, true); }
      finally { setBusy(false); await refreshAll(); }
    },
  });
});

$("#delete-all-button").addEventListener("click", () => askConfirm({
  title: "Quarantine every recording?",
  copy: "Recording pauses briefly while every managed CCTV file is moved out of the archive. The service then returns to its previous state. You have 24 hours to restore the files.",
  phrase: "QUARANTINE ALL RECORDINGS",
  confirmLabel: "Quarantine everything",
  callback: async () => {
    setBusy(true, "Quarantining all recordings");
    try {
      const result = await api("/api/recordings/quarantine-all", { method: "POST", body: JSON.stringify({ confirmation: "QUARANTINE ALL RECORDINGS" }) });
      toast(result.message);
    } catch (error) { toast(error.message, true); }
    finally { setBusy(false); await refreshAll(); }
  },
}));

$("#restore-all-button").addEventListener("click", async () => {
  setBusy(true, "Restoring quarantined recordings");
  try {
    const result = await api("/api/quarantine/restore-all", { method: "POST", body: "{}" });
    toast(result.message);
  } catch (error) { toast(error.message, true); }
  finally { setBusy(false); await refreshAll(); }
});

$("#load-logs-button").addEventListener("click", async () => {
  $("#logs").textContent = "Loading…";
  try {
    const result = await api("/api/logs");
    $("#logs").textContent = result.lines.join("\n") || "No recent service log entries.";
  } catch (error) { $("#logs").textContent = error.message; }
});

(async () => {
  try {
    const session = await api("/api/session");
    if (session.authenticated) { state.csrf = session.csrf; showApp(); }
    else showLogin();
  } catch { showLogin(); }
})();
