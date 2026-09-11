const SPONSOR_ADAPTERS = [
  { key: "cognee", label: "Cognee" },
  { key: "hydra", label: "HydraDB" },
  { key: "hotdata", label: "HotData" },
  { key: "rocketride", label: "RocketRide" },
  { key: "modiqo", label: "Rote" },
];

const state = {
  columns: [],
  rowCount: 0,
  sampleRows: [],
  targetSchema: [],
  mapping: [],
  mascotTimer: null,
};

const STEP_LABELS = {
  upload: "Upload", profile: "Profile", recall: "Recall", map: "Map",
  approve: "Approve", migrate: "Migrate", reconcile: "Reconcile", learn: "Learn",
};

function setStep(name, status) {
  const el = document.querySelector(`.step[data-step="${name}"]`);
  if (!el) return;
  el.classList.remove("active", "done");
  if (status) el.classList.add(status);
  el.textContent = STEP_LABELS[name];
}

function setStepProgress(name, current, total) {
  const el = document.querySelector(`.step[data-step="${name}"]`);
  if (!el) return;
  el.textContent = `${STEP_LABELS[name]} (${current}/${total})`;
}

function setMascotStatus(text) {
  document.getElementById("mascot-status").textContent = text;
}

function setMonsterMood(mood, status, speech) {
  const img = document.getElementById("monster-img");
  const bubble = document.getElementById("monster-speech");
  if (state.mascotTimer) {
    window.clearTimeout(state.mascotTimer);
    state.mascotTimer = null;
  }
  img.className = "";
  img.src = mood === "complete" ? "assets/monster-scan-complete.png" : "assets/monster-eating.png";
  if (mood) img.classList.add(`monster-${mood}`);
  if (status) setMascotStatus(status);
  if (speech) bubble.textContent = speech;
}

function show(id) {
  document.getElementById(id).hidden = false;
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

async function renderAdapters() {
  const data = await api("/api/adapters");
  const list = document.getElementById("adapter-list");
  list.innerHTML = "";
  let anyConnected = false;
  for (const { key, label } of SPONSOR_ADAPTERS) {
    const live = !!data[key]?.live;
    if (live) anyConnected = true;
    const row = document.createElement("div");
    row.className = "adapter-row";
    row.innerHTML = `<span>${label}</span><span class="pill ${live ? "connected" : "disconnected"}">${live ? "Connected" : "Disconnected"}</span>`;
    list.appendChild(row);
  }
  document.getElementById("adapter-note").textContent = anyConnected
    ? "Connected sponsor services enrich mapping memory. Everything else stays local and masked in previews."
    : "No sponsor service is active. PII remains local and masked in previews.";
}

function maskValue(column, value) {
  if (!value) return value;
  if (/e[-_]?mail/i.test(column)) {
    const at = value.indexOf("@");
    return at === -1 ? "***" : `***@${value.slice(at + 1).toUpperCase()}`;
  }
  if (/phone|tel|mobile/i.test(column)) {
    const digits = value.replace(/\D/g, "");
    return digits.length > 4 ? `***-***-${digits.slice(-4)}` : "****";
  }
  return value;
}

function renderPreviewTable() {
  const wrap = document.getElementById("preview-table");
  const head = state.columns.map((c) => `<th>${c}</th>`).join("");
  const body = state.sampleRows
    .map((row) => `<tr>${state.columns.map((c) => `<td>${maskValue(c, row[c] ?? "")}</td>`).join("")}</tr>`)
    .join("");
  wrap.innerHTML = `<table class="mini"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderFileChip(name, meta) {
  document.getElementById("file-chip-wrap").innerHTML = `
    <div class="file-chip">
      <span class="file-icon">&#128203;</span>
      <span>${name}</span>
      <span class="file-meta">${meta}</span>
    </div>
  `;
}

document.getElementById("file-input").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  setMonsterMood("eat", "Cookie accepted — uploading data…", "Nom. I got the file!");
  const form = new FormData();
  form.append("file", file);
  const data = await api("/api/upload", { method: "POST", body: form });
  renderFileChip(file.name, `${data.row_count} rows`);
  onDatasetLoaded(data);
});

document.getElementById("sample-btn").addEventListener("click", async () => {
  setMonsterMood("eat", "Cookie accepted — loading sample data…", "Nom. Sample cookie!");
  const data = await api("/api/sample", { method: "POST" });
  renderFileChip("sample_vendor_file.csv", `${data.row_count} rows`);
  onDatasetLoaded(data);
});

async function onDatasetLoaded(data) {
  state.columns = data.columns;
  state.rowCount = data.row_count;
  state.sampleRows = data.sample_rows;
  setStep("upload", "done");

  for (const id of ["preview-section", "profile-section", "recall-section", "mapping-section", "migrate-section", "reconcile-section", "ask-section"]) {
    document.getElementById(id).hidden = true;
  }
  document.getElementById("profile-panel").innerHTML = "";
  document.getElementById("recall-panel").innerHTML = "";
  document.getElementById("mapping-panel").innerHTML = "";
  document.getElementById("reconcile-panel").innerHTML = "";
  document.getElementById("ask-answer").innerHTML = "";
  document.getElementById("ask-input").value = "";
  document.getElementById("incoming-rack").innerHTML = "";
  document.getElementById("loaded-count").textContent = "0";
  document.getElementById("quarantine-count").textContent = "0";
  resetMonster();

  show("preview-section");
  renderPreviewTable();
  await runProfile();
}

async function runProfile() {
  setStep("profile", "active");
  setMonsterMood("eat", "Profiling the file for nulls, duplicates & sensitive fields…", "Crunching the upload.");
  const profile = await api("/api/profile", { method: "POST" });
  show("profile-section");
  const sensitive = Object.entries(profile.sensitive_columns);
  document.getElementById("profile-panel").innerHTML = `
    <div>${profile.row_count} rows &middot; ${profile.duplicate_rows} duplicate rows &middot; ${profile.invalid_email_count} invalid emails</div>
    <div class="muted small">engine: ${profile.engine}</div>
    ${sensitive.length ? `<div class="muted small">sensitive columns: ${sensitive.map(([c, l]) => `${c} (${l})`).join(", ")}</div>` : ""}
  `;
  setStep("profile", "done");
  await runRecall();
}

async function runRecall() {
  setStep("recall", "active");
  setMonsterMood("think", "Checking memory for mappings that worked before…", "Looking for familiar shapes.");
  const recall = await api("/api/recall");
  show("recall-section");
  const panel = document.getElementById("recall-panel");
  if (recall.hydra_previous_mapping || recall.replayable_play || recall.cognee_notes.length) {
    panel.innerHTML = `
      ${recall.replayable_play ? '<div>&#9889; A learned play matches this file shape.</div>' : ""}
      ${recall.hydra_previous_mapping ? '<div>HydraDB found a prior mapping for these exact columns.</div>' : ""}
      ${recall.cognee_notes.length ? `<div class="muted small">Cognee: ${recall.cognee_notes[0]}</div>` : ""}
    `;
  } else {
    panel.innerHTML = `<div class="muted">No prior migrations recognized — this looks like a new file shape.</div>`;
  }
  setStep("recall", "done");
  await runSuggestMappings();
}

async function runSuggestMappings() {
  setStep("map", "active");
  setMonsterMood("think", "Drafting field mappings…", "Matching fields now.");
  const [schema, mapping] = await Promise.all([
    state.targetSchema.length ? Promise.resolve(state.targetSchema) : api("/api/target-schema"),
    api("/api/suggest-mappings", { method: "POST" }),
  ]);
  state.targetSchema = schema;
  state.mapping = mapping.map((m) => ({ ...m, approved: false, rejected: false }));
  show("mapping-section");
  renderMappingTable();
  setStep("map", "done");
  setMonsterMood("hop", "Mappings are ready.", "I mapped it!");
  setStep("approve", "active");
  state.mascotTimer = window.setTimeout(() => {
    setMonsterMood("approval", "Waiting for your approval…", "Please approve the mapping.");
  }, 900);
}

function decideRow(idx, decision) {
  const m = state.mapping[idx];
  m.approved = decision === "approved";
  m.rejected = decision === "rejected";
  renderMappingTable();
}

function renderMappingTable() {
  const panel = document.getElementById("mapping-panel");
  const options = state.targetSchema.map((f) => f.field);
  const rows = state.mapping
    .map((m, i) => {
      const pct = Math.round((m.confidence || 0) * 100);
      const opts = [`<option value="">— ignore —</option>`]
        .concat(options.map((o) => `<option value="${o}" ${o === m.target_field ? "selected" : ""}>${o}</option>`))
        .join("");
      const rowClass = m.approved ? "approved" : m.rejected ? "rejected" : "";
      return `<tr class="${rowClass}">
        <td>${m.source_field}</td>
        <td><select data-idx="${i}" ${m.rejected ? "disabled" : ""}>${opts}</select></td>
        <td><span class="confidence-bar" style="width:${Math.max(pct, 6)}px"></span> ${pct}%</td>
        <td class="muted small">${m.reasoning || ""}</td>
        <td class="decision-cell">
          <button type="button" class="decision-btn approve ${m.approved ? "active" : ""}" data-idx="${i}" data-decision="approved">Approve</button>
          <button type="button" class="decision-btn reject ${m.rejected ? "active" : ""}" data-idx="${i}" data-decision="rejected">Reject</button>
        </td>
      </tr>`;
    })
    .join("");
  const allDecided = state.mapping.every((m) => m.rejected || (m.approved && m.target_field));
  const decidedCount = state.mapping.filter((m) => m.approved || m.rejected).length;
  panel.innerHTML = `
    <div class="table-wrap">
      <table class="mini">
        <thead><tr><th>Source</th><th>Target</th><th>Confidence</th><th>Reasoning</th><th>Decision</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <div class="mapping-actions">
      <button id="approve-btn" class="btn-primary" ${allDecided ? "" : "disabled"}>Start Migration</button>
      <span class="muted small">${allDecided ? "Approved fields will migrate; rejected fields will quarantine." : `${decidedCount}/${state.mapping.length} fields decided — approve with a target or reject each one.`}</span>
    </div>
  `;
  panel.querySelectorAll("select").forEach((sel) => {
    sel.addEventListener("change", (e) => {
      const idx = Number(e.target.dataset.idx);
      state.mapping[idx].target_field = e.target.value || null;
    });
  });
  panel.querySelectorAll(".decision-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => decideRow(Number(e.target.dataset.idx), e.target.dataset.decision));
  });
  if (allDecided) {
    document.getElementById("approve-btn").addEventListener("click", approveAndMigrate);
  }
}

function buildIncomingRack() {
  const rack = document.getElementById("incoming-rack");
  rack.innerHTML = "";
  for (let i = 0; i < state.rowCount; i++) {
    const chip = document.createElement("div");
    chip.className = "row-chip";
    chip.id = `chip-${i}`;
    chip.textContent = `Row ${i + 1}`;
    rack.appendChild(chip);
  }
}

function chomp() {
  const img = document.getElementById("monster-img");
  const fx = document.getElementById("chomp-fx");
  img.src = "assets/monster-eating.png";
  img.classList.add("chomp");
  fx.textContent = "\u{1F36A}";
  fx.classList.remove("show");
  void fx.offsetWidth;
  fx.classList.add("show");
  setTimeout(() => img.classList.remove("chomp"), 150);
}

function resetMonster() {
  setMonsterMood("wave", "Idle — waiting for a file", "Hi! Send me a CSV.");
}

function celebrateMonster() {
  setMonsterMood("complete", "Migration complete!", "All done!");
}

async function approveAndMigrate() {
  setStep("approve", "done");
  setMonsterMood("eat", "Decisions received — migrating approved data and quarantining rejects…", "Approved goes in. Rejected goes aside.");
  const payload = state.mapping.map((m) => ({ ...m, target_field: m.rejected ? null : m.target_field }));
  await api("/api/approve-mappings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mapping: payload }),
  });
  document.getElementById("mapping-panel").querySelector("#approve-btn").disabled = true;
  show("migrate-section");
  buildIncomingRack();
  setStep("migrate", "active");

  const es = new EventSource("/api/migrate-stream");
  es.onmessage = (evt) => {
    const result = JSON.parse(evt.data);
    handleRowResult(result);
  };
  es.addEventListener("done", async () => {
    es.close();
    setStep("migrate", "done");
    await runReconcile();
  });
  es.onerror = () => es.close();
}

function handleRowResult(result) {
  chomp();
  document.getElementById("monster-img").classList.add("monster-eat");
  const rejectedCount = result.quarantined_data?.length || 0;
  document.getElementById("monster-speech").textContent = rejectedCount
    ? `Row ${result.index + 1}: migrate approved, quarantine ${rejectedCount}.`
    : `Migrating row ${result.index + 1}.`;
  setMascotStatus(`Processing record ${result.index + 1} of ${state.rowCount}…`);
  setStepProgress("migrate", result.index + 1, state.rowCount);
  const chip = document.getElementById(`chip-${result.index}`);
  const good = result.status === "loaded";
  setTimeout(() => {
    if (chip) {
      chip.classList.add(good ? "fly-good" : "fly-bad");
      setTimeout(() => chip.remove(), 380);
    }
    if (good) {
      const loadedCounter = document.getElementById("loaded-count");
      loadedCounter.textContent = String(Number(loadedCounter.textContent) + 1);
    }
    const quarantineIncrement = (good ? 0 : 1) + rejectedCount;
    if (quarantineIncrement) {
      const quarantineCounter = document.getElementById("quarantine-count");
      quarantineCounter.textContent = String(Number(quarantineCounter.textContent) + quarantineIncrement);
    }
  }, 150);
}

async function runReconcile() {
  setStep("reconcile", "active");
  show("reconcile-section");
  const report = await api("/api/reconcile", { method: "POST" });
  const panel = document.getElementById("reconcile-panel");
  panel.innerHTML = `
    <div class="reconcile-card ${report.reconciled ? "ok" : "bad"}">
      <div><strong>${report.loaded_count}</strong> loaded / <strong>${report.quarantined_count}</strong> quarantined out of ${report.source_row_count} source rows</div>
      ${report.rejected_data_count ? `<div class="muted small">${report.rejected_data_count} rejected source values were quarantined by the approval gate.</div>` : ""}
      <div class="muted small">${report.reconciled ? "Reconciled: modern DB count matches." : "Mismatch detected between processed and loaded counts."}</div>
      ${report.quarantine_reasons.length ? `<ul class="muted small">${report.quarantine_reasons.map((q) => `<li>Row ${q.index + 1}: ${q.reasons.join("; ")}</li>`).join("")}</ul>` : ""}
      ${report.rejected_data?.length ? `<ul class="muted small">${report.rejected_data.slice(0, 6).map((q) => `<li>Row ${q.index + 1}: ${q.source_field} quarantined (${q.reason})</li>`).join("")}</ul>` : ""}
    </div>
  `;
  setStep("reconcile", "done");
  celebrateMonster();
  spawnConfetti();
  setStep("learn", "active");
  await api("/api/learn", { method: "POST" });
  setStep("learn", "done");
  renderAdapters();
  show("ask-section");
}

async function askQuestion() {
  const input = document.getElementById("ask-input");
  const question = input.value.trim();
  if (!question) return;
  const answerBox = document.getElementById("ask-answer");
  const btn = document.getElementById("ask-btn");
  btn.disabled = true;
  answerBox.innerHTML = `<div class="muted small">Asking RocketRide…</div>`;
  try {
    const { answer } = await api("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    answerBox.innerHTML = `<div class="ask-answer-card">${answer}</div>`;
  } catch (err) {
    answerBox.innerHTML = `<div class="muted small">RocketRide couldn't answer that: ${err.message}</div>`;
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("ask-btn").addEventListener("click", askQuestion);
document.getElementById("ask-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") askQuestion();
});

function spawnConfetti() {
  const layer = document.createElement("div");
  layer.className = "confetti";
  document.body.appendChild(layer);
  const colors = ["#6fe0cf", "#34d399", "#f2a2ab", "#fbbf24"];
  for (let i = 0; i < 40; i++) {
    const piece = document.createElement("div");
    piece.style.position = "absolute";
    piece.style.left = `${Math.random() * 100}%`;
    piece.style.top = "-10px";
    piece.style.width = "8px";
    piece.style.height = "8px";
    piece.style.background = colors[i % colors.length];
    piece.style.transition = `transform ${1.2 + Math.random()}s ease-in, opacity ${1.2 + Math.random()}s`;
    layer.appendChild(piece);
    requestAnimationFrame(() => {
      piece.style.transform = `translateY(${300 + Math.random() * 300}px) rotate(${Math.random() * 360}deg)`;
      piece.style.opacity = "0";
    });
  }
  setTimeout(() => layer.remove(), 2500);
}

renderAdapters();
