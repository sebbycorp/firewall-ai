const TOKEN_KEY = "firewall_ai_admin_token";

const gate = document.getElementById("gate");
const dash = document.getElementById("dash");
const rows = document.getElementById("rows");
const login = document.getElementById("login");
const loginError = document.getElementById("login-error");
const logout = document.getElementById("logout");
const clock = document.getElementById("clock");
const count = document.getElementById("count");
const threshold = document.getElementById("threshold");

function token() {
  return sessionStorage.getItem(TOKEN_KEY) || "";
}

function setSignedIn(on) {
  gate.hidden = on;
  dash.hidden = !on;
  logout.hidden = !on;
}

function fmtTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString();
}

function statusCell(lab) {
  if (!lab.online) {
    return `<span class="badge offline"><span class="dot"></span>offline</span>`;
  }
  if (lab.ok === false) {
    return `<span class="badge degraded"><span class="dot"></span>online / fw error</span>`;
  }
  return `<span class="badge online"><span class="dot"></span>online</span>`;
}

async function api(path, options = {}) {
  const headers = Object.assign({ Authorization: `Bearer ${token()}` }, options.headers || {});
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    sessionStorage.removeItem(TOKEN_KEY);
    setSignedIn(false);
    throw new Error("Invalid admin token");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

function renderLabs(payload) {
  const labs = payload.labs || [];
  count.textContent = `${labs.length} lab${labs.length === 1 ? "" : "s"}`;
  if (payload.offline_after_sec) {
    const mins = Math.round(payload.offline_after_sec / 60);
    threshold.textContent = mins === 1 ? "1 minute" : `${mins} minutes`;
  }
  clock.textContent = `Updated ${fmtTime(payload.generated_at)}`;
  if (!labs.length) {
    rows.innerHTML = `<tr><td colspan="8" class="empty">No agents enrolled yet.</td></tr>`;
    return;
  }
  rows.innerHTML = labs
    .map(
      (lab) => `
      <tr>
        <td>${escapeHtml(lab.student_id)}</td>
        <td>${statusCell(lab)}</td>
        <td>${escapeHtml(fmtTime(lab.last_seen))}</td>
        <td>${escapeHtml(lab.hostname || "—")}</td>
        <td>${escapeHtml(lab.sw_version || "—")}</td>
        <td>${escapeHtml(lab.mgmt_ip || "—")}</td>
        <td>${escapeHtml(lab.last_error || "—")}</td>
        <td><button class="ghost" data-probe="${escapeHtml(lab.student_id)}">Probe</button></td>
      </tr>`
    )
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function refresh() {
  if (!token()) return;
  const payload = await api("/v1/labs");
  renderLabs(payload);
}

login.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.hidden = true;
  sessionStorage.setItem(TOKEN_KEY, document.getElementById("token").value.trim());
  try {
    await refresh();
    setSignedIn(true);
  } catch (err) {
    loginError.textContent = err.message;
    loginError.hidden = false;
  }
});

logout.addEventListener("click", () => {
  sessionStorage.removeItem(TOKEN_KEY);
  setSignedIn(false);
});

rows.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-probe]");
  if (!button) return;
  button.disabled = true;
  try {
    await api(`/v1/labs/${encodeURIComponent(button.dataset.probe)}/probe`, { method: "POST" });
    button.textContent = "Queued";
  } catch (err) {
    button.textContent = "Failed";
    alert(err.message);
  } finally {
    setTimeout(() => {
      button.disabled = false;
      button.textContent = "Probe";
    }, 2500);
  }
});

if (token()) {
  refresh()
    .then(() => setSignedIn(true))
    .catch(() => setSignedIn(false));
}

setInterval(() => {
  refresh().catch(() => {});
}, 10000);
