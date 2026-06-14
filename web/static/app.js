"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let socket = null;

// --------------------------------------------------------------------------
// Tab switching
// --------------------------------------------------------------------------
$$(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    $$(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $("#tab-" + tab.dataset.tab).classList.add("active");
    if (tab.dataset.tab === "logs") loadLogs();
  });
});

// --------------------------------------------------------------------------
// Tool selection (Ansible vs Terraform)
// --------------------------------------------------------------------------
function currentTool() {
  return document.querySelector('input[name="tool"]:checked').value;
}
function syncToolGroups() {
  const tool = currentTool();
  $$(".tool-group").forEach((g) => (g.hidden = g.dataset.tool !== tool));
}
$$('input[name="tool"]').forEach((r) => r.addEventListener("change", syncToolGroups));

// --------------------------------------------------------------------------
// Discovery: populate playbooks / inventories / projects / actions
// --------------------------------------------------------------------------
async function loadInventory() {
  const res = await fetch("/api/inventory");
  const data = await res.json();

  $("#paths").textContent =
    `ansible: ${data.ansible_dir}  •  terraform: ${data.terraform_dir}`;

  fillSelect($("#ans-playbook"), data.playbooks, "(no playbooks found)");

  const inv = $("#ans-inventory");
  inv.innerHTML = '<option value="">auto / default</option>';
  data.inventories.forEach((i) => addOption(inv, i, i));

  fillSelect($("#tf-project"), data.terraform_projects, "(no projects found)");
  fillSelect($("#tf-command"), data.terraform_actions, "");
  // Default Terraform command to "plan" when present.
  const cmdSel = $("#tf-command");
  if ([...cmdSel.options].some((o) => o.value === "plan")) cmdSel.value = "plan";
}

function fillSelect(sel, items, emptyLabel) {
  sel.innerHTML = "";
  if (!items.length && emptyLabel) {
    addOption(sel, "", emptyLabel);
    return;
  }
  items.forEach((i) => addOption(sel, i, i));
}
function addOption(sel, value, label) {
  const o = document.createElement("option");
  o.value = value;
  o.textContent = label;
  sel.appendChild(o);
}

// --------------------------------------------------------------------------
// Console helpers
// --------------------------------------------------------------------------
function appendConsole(text, cls) {
  const con = $("#console");
  const atBottom = con.scrollHeight - con.scrollTop - con.clientHeight < 40;
  const span = document.createElement("span");
  if (cls) span.className = cls;
  span.textContent = text + "\n";
  con.appendChild(span);
  if (atBottom) con.scrollTop = con.scrollHeight;
}
function setStatus(text, cls) {
  const s = $("#status");
  s.textContent = text;
  s.className = "status " + (cls || "");
}

// --------------------------------------------------------------------------
// Run via WebSocket
// --------------------------------------------------------------------------
function buildPayload() {
  const tool = currentTool();
  const base = { tool, args: $("#extra-args").value };
  if (tool === "ansible") {
    return Object.assign(base, {
      target: $("#ans-playbook").value,
      inventory: $("#ans-inventory").value,
      extra_vars: $("#ans-extravars").value,
      limit: $("#ans-limit").value,
      tags: $("#ans-tags").value,
      check: $('input[name="check"]').checked,
      verbose: $('input[name="verbose"]').checked,
    });
  }
  return Object.assign(base, {
    target: $("#tf-project").value,
    command: $("#tf-command").value,
    extra_vars: $("#tf-vars").value,
  });
}

function setRunning(running) {
  $("#run-btn").disabled = running;
  $("#stop-btn").disabled = !running;
}

$("#run-form").addEventListener("submit", (e) => {
  e.preventDefault();
  if (socket) return;

  const payload = buildPayload();
  if (!payload.target) {
    setStatus("Nothing selected to run.", "fail");
    return;
  }

  const proto = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${proto}://${location.host}/ws/run`);
  setRunning(true);
  setStatus("connecting…", "running");

  socket.onopen = () => {
    setStatus("running…", "running");
    socket.send(JSON.stringify(payload));
  };

  socket.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "start") {
      appendConsole("$ " + msg.data, "cmd");
      $("#console-log").textContent = msg.log ? "log: " + msg.log : "";
    } else if (msg.type === "output") {
      const cls = msg.data.startsWith("$ ") ? "cmd" : "";
      appendConsole(msg.data, cls);
    } else if (msg.type === "end") {
      const ok = msg.returncode === 0;
      appendConsole(`\n— finished (exit ${msg.returncode}) —`, ok ? "ok" : "err");
      setStatus(ok ? "completed" : `failed (exit ${msg.returncode})`, ok ? "ok" : "fail");
    } else if (msg.type === "error") {
      appendConsole("error: " + msg.data, "err");
      setStatus("error", "fail");
    }
  };

  socket.onclose = () => {
    socket = null;
    setRunning(false);
  };
  socket.onerror = () => {
    appendConsole("websocket error", "err");
    setStatus("connection error", "fail");
  };
});

$("#stop-btn").addEventListener("click", () => {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ action: "stop" }));
    setStatus("stopping…", "running");
  }
});

$("#clear-btn").addEventListener("click", () => {
  $("#console").innerHTML = "";
  $("#console-log").textContent = "";
  setStatus("");
});

// --------------------------------------------------------------------------
// Logs viewer
// --------------------------------------------------------------------------
async function loadLogs() {
  const res = await fetch("/api/logs");
  const data = await res.json();
  const list = $("#logs-list");
  list.innerHTML = "";
  if (!data.logs.length) {
    list.innerHTML = '<li class="meta">No logs yet.</li>';
    return;
  }
  data.logs.forEach((log) => {
    const li = document.createElement("li");
    li.innerHTML =
      `<span class="name">${log.name}</span>` +
      `<span class="meta">${log.modified} · ${formatSize(log.size)}</span>`;
    li.addEventListener("click", () => {
      $$("#logs-list li").forEach((x) => x.classList.remove("active"));
      li.classList.add("active");
      viewLog(log.name);
    });
    list.appendChild(li);
  });
}

async function viewLog(name) {
  $("#log-view-title").textContent = name;
  const res = await fetch("/api/logs/" + encodeURIComponent(name));
  $("#log-view").textContent = await res.text();
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}

$("#refresh-logs").addEventListener("click", loadLogs);

// --------------------------------------------------------------------------
// Init
// --------------------------------------------------------------------------
syncToolGroups();
loadInventory().catch((e) => setStatus("failed to load: " + e, "fail"));
