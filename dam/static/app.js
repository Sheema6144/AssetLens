/* AssetLens front-end: plain JavaScript, no build step. */
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const api = async (url, opts = {}) => {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.json();
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtBytes = (n) => { if (!n) return "0 B"; const u = ["B", "KB", "MB", "GB"]; let i = 0; while (n >= 1024 && i < 3) { n /= 1024; i++; } return `${n.toFixed(i ? 1 : 0)} ${u[i]}`; };
const fmtTime = (s) => { s = Math.round(s || 0); return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; };
const fmtDate = (t) => (t ? new Date(t * 1000).toLocaleString() : "");
const toast = (msg) => { const d = document.createElement("div"); d.className = "toast"; d.textContent = msg; document.body.append(d); setTimeout(() => d.remove(), 2200); };

const EXAMPLES = [
  "a woman standing with a cat", "customer testimonial videos", "brochures related to residential projects",
  "images showing a modern living room", "videos containing construction activity", "people in a business meeting",
  "aerial view of a city at night", "food on a table",
];

/* ---------------- tabs ---------------- */
$$("nav .tab").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
function showTab(name) {
  $$("nav .tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tabpane").forEach((p) => p.classList.toggle("hidden", p.id !== `tab-${name}`));
  if (name === "index") refreshIndex();
  if (name === "eval" && !$("#evalList").children.length) runEval();
}

/* ---------------- search ---------------- */
$("#examples").innerHTML = EXAMPLES.map((e) => `<button type="button">${esc(e)}</button>`).join("");
$$("#examples button").forEach((b) => b.addEventListener("click", () => { $("#q").value = b.textContent; doSearch(); }));
$("#searchForm").addEventListener("submit", (e) => { e.preventDefault(); doSearch(); });
$$(".filters input, .filters select").forEach((el) => el.addEventListener("change", doSearch));
$("#clearFilters").addEventListener("click", () => {
  $$(".filters input[type=checkbox]").forEach((c) => (c.checked = false));
  $$(".filters input[type=number]").forEach((c) => (c.value = ""));
  $$(".filters select").forEach((s) => (s.selectedIndex = s.id === "topK" ? 1 : 0));
  doSearch();
});

function filterParams() {
  const p = new URLSearchParams();
  p.set("q", $("#q").value.trim());
  const kinds = $$("input[name=kind]:checked").map((c) => c.value);
  if (kinds.length) p.set("kinds", kinds.join(","));
  if ($("#minMb").value) p.set("min_mb", $("#minMb").value);
  if ($("#maxMb").value) p.set("max_mb", $("#maxMb").value);
  if ($("#folder").value) p.set("folder", $("#folder").value);
  if ($("#orientation").value) p.set("orientation", $("#orientation").value);
  if ($("#maxDur").value) p.set("max_duration", $("#maxDur").value);
  if ($("#hasSpeech").checked) p.set("has_speech", "true");
  if ($("#modified").value) p.set("modified_after", Date.now() / 1000 - Number($("#modified").value) * 86400);
  p.set("top_k", $("#topK").value);
  return p;
}

let lastResults = [];
let searchSeq = 0;
async function doSearch() {
  const seq = ++searchSeq;
  $("#resultInfo").textContent = "Searching…";
  try {
    const res = await api(`/api/search?${filterParams()}`);
    if (seq !== searchSeq) return; // a newer search started
    lastResults = res.results;
    renderResults(res);
  } catch (e) {
    $("#resultInfo").textContent = `Search failed: ${e.message}`;
  }
}

function whereLabel(m, kind) {
  if (!m) return "";
  if (m.source === "frame" || (kind === "video" && m.ref != null && m.source !== "transcript")) return `▶ ${fmtTime(m.ref)}`;
  if (m.source === "transcript") return "🗣 speech";
  if (["page", "pdf_text", "pdf_summary"].includes(m.source) && m.ref) return `page ${m.ref}`;
  return "";
}

function renderResults(res) {
  const n = res.results.length;
  let info = res.query
    ? `<b>${n}</b> result${n === 1 ? "" : "s"} in ${res.ms} ms`
    : `<b>Browsing</b> ${n} most recent of ${res.total_candidates} assets — type a description above to search`;
  if (res.query && res.embedded_query && res.embedded_query.toLowerCase() !== res.query.toLowerCase())
    info += ` · searched for <span class="chip">${esc(res.embedded_query)}</span>`;
  if (res.detected_type) info += ` · boosting <span class="chip">${res.detected_type}s</span>`;
  if (res.warnings?.length) info += ` · <span style="color:var(--warn)">${esc(res.warnings.join("; "))}</span>`;
  $("#resultInfo").innerHTML = info;
  if (!n) {
    $("#grid").innerHTML = `<div class="empty">No results. Try other words, clear filters, or check the Indexing tab.</div>`;
    return;
  }
  $("#grid").innerHTML = res.results.map((r, i) => {
    const best = r.match?.best;
    const thumb = best?.thumb || r.thumb;
    const where = whereLabel(best, r.kind);
    const extra = r.kind === "video" ? fmtTime(r.meta?.duration) : r.kind === "pdf" ? `${r.meta?.pages || "?"} pages` : r.meta?.width ? `${r.meta.width}×${r.meta.height}` : "";
    const rel = r.relevance ?? null;
    return `<article class="res ${r.confidence === "low" ? "low" : ""} conf-${r.confidence || ""}" data-i="${i}">
      <div class="thumb">${thumb ? `<img loading="lazy" src="/thumbs/${esc(thumb)}" alt="">` : `<span class="muted">no preview</span>`}
        <span class="kind ${r.kind}">${r.kind}</span>
        ${where ? `<span class="where">${where}</span>` : ""}
        ${r.duplicates?.length ? `<span class="dup" title="Identical copies in other folders">+${r.duplicates.length} copy</span>` : ""}
      </div>
      <div class="body">
        <div class="fname" title="${esc(r.path)}">${esc(r.filename)}</div>
        <div class="cap">${esc(r.caption || (r.tags || []).join(", ") || "")}</div>
        ${rel !== null ? `<div class="rel" title="score ${r.score} · ${r.confidence} confidence"><div class="relbar"><i style="width:${rel}%"></i></div>${Math.round(rel)}%</div>` : ""}
        <div class="muted small">${extra} · ${fmtBytes(r.size)}</div>
      </div></article>`;
  }).join("");
  $$("#grid .res").forEach((el) => el.addEventListener("click", () => openPreview(lastResults[Number(el.dataset.i)])));
}

/* ---------------- preview modal ---------------- */
async function openPreview(r) {
  const d = await api(`/api/assets/${r.hash}`);
  const fileUrl = `/api/file/${r.file_id}`;
  const best = r.match?.best;
  let pv = "";
  if (r.kind === "image") pv = `<img src="${fileUrl}" alt="">`;
  else if (r.kind === "video") {
    const t = best?.source === "frame" || best?.source === "caption" ? best.ref || 0 : 0;
    pv = `<video id="pv" src="${fileUrl}#t=${t}" controls autoplay muted playsinline></video>`;
  } else if (r.kind === "pdf") pv = `<iframe src="${fileUrl}#page=${best?.ref || 1}" title="PDF preview"></iframe>`;
  $("#preview").innerHTML = pv;

  const frames = (d.parts || []).filter((p) => p.thumb);
  const framesHtml = frames.length > 1 ? `<h4>${r.kind === "video" ? "Analysed keyframes" : "Analysed pages"}</h4>
    <div class="frames">${frames.map((f) => `<figure data-ref="${f.ref}" class="${best && best.ref === f.ref ? "hit" : ""}">
      <img src="/thumbs/${esc(f.thumb)}" alt=""><figcaption>${r.kind === "video" ? fmtTime(f.ref) : "p. " + f.ref}${f.label && !f.label.startsWith("page") ? " · " + esc(f.label) : ""}</figcaption></figure>`).join("")}</div>` : "";
  const sig = r.signals || {};
  const others = (d.files || []).filter((f) => f.id !== r.file_id && f.present);
  const transcript = (d.body || "").split("TRANSCRIPT:")[1];
  $("#details").innerHTML = `
    <h3>${esc(r.filename)}</h3>
    <div class="muted small">${esc(d.caption || "")}</div>
    <div class="btnrow">
      <button class="primary" id="openLoc">📂 Show in folder</button>
      <button id="copyPath">Copy path</button>
      <a href="${fileUrl}" target="_blank"><button>Open file</button></a>
    </div>
    <div class="kv">
      <b>Location</b><span class="path">${esc(r.path)}</span>
      <b>Type</b><span>${r.kind} (${esc(r.ext)})</span>
      <b>Size</b><span>${fmtBytes(r.size)}</span>
      <b>Modified</b><span>${fmtDate(r.mtime)}</span>
      ${r.kind === "video" ? `<b>Duration</b><span>${fmtTime(d.meta.duration)} · ${d.meta.width}×${d.meta.height} · ${d.meta.frames_sampled} keyframes${d.meta.has_speech ? " · speech" : ""}</span>` : ""}
      ${r.kind === "image" ? `<b>Dimensions</b><span>${d.meta.width}×${d.meta.height}</span>` : ""}
      ${r.kind === "pdf" ? `<b>Pages</b><span>${d.meta.pages}${d.meta.title ? " · " + esc(d.meta.title) : ""}</span>` : ""}
      ${sig.visual != null || sig.semantic != null ? `<b>Match</b><span>score ${r.score} (${r.confidence}) · visual ${sig.visual ?? "–"} · text ${sig.semantic ?? "–"} · keyword ${sig.keyword ?? 0}</span>` : ""}
      ${best?.label ? `<b>Why</b><span>${esc(best.source)}${whereLabel(best, r.kind) ? " @ " + whereLabel(best, r.kind) : ""}: “${esc(best.label.slice(0, 220))}”</span>` : ""}
    </div>
    ${d.tags?.length ? `<h4>AI tags</h4><div class="tags">${d.tags.map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div>` : ""}
    ${framesHtml}
    ${transcript ? `<h4>Transcript</h4><div class="transcript">${esc(transcript.trim())}</div>` : ""}
    ${r.kind === "pdf" && d.body ? `<h4>Extracted text</h4><div class="transcript">${esc(d.body.slice(0, 1500))}</div>` : ""}
    ${others.length ? `<h4>Identical copies</h4>${others.map((f) => `<div class="path">${esc(f.path)}</div>`).join("")}` : ""}
    ${d.warnings?.length ? `<h4>Warnings</h4><div class="small" style="color:var(--warn)">${d.warnings.map(esc).join("<br>")}</div>` : ""}`;
  $("#openLoc").onclick = async () => {
    try { await api(`/api/open/${r.file_id}`, { method: "POST" }); toast("Opened in file explorer"); }
    catch (e) { toast("Could not open folder: " + e.message); }
  };
  $("#copyPath").onclick = () => { navigator.clipboard?.writeText(r.path); toast("Path copied"); };
  $$("#details .frames figure").forEach((f) => f.addEventListener("click", () => {
    const v = $("#pv"); if (v) { v.currentTime = Number(f.dataset.ref); v.play(); }
    else if (r.kind === "pdf") $("#preview iframe").src = `${fileUrl}#page=${f.dataset.ref}`;
  }));
  $("#modal").classList.remove("hidden");
}
const closeModal = () => { $("#modal").classList.add("hidden"); $("#preview").innerHTML = ""; };
$("#closeModal").addEventListener("click", closeModal);
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

/* ---------------- indexing ---------------- */
let pollTimer = null;
$("#startBtn").addEventListener("click", async () => {
  try {
    const r = await api("/api/index/start", { method: "POST", body: JSON.stringify({ root: $("#root").value.trim() }) });
    toast(r.started ? "Indexing started" : "Indexing is already running");
    poll();
  } catch (e) { toast(e.message); }
});
$("#stopBtn").addEventListener("click", async () => { await api("/api/index/stop", { method: "POST" }); toast("Stopping after the current file…"); });
$("#retryBtn").addEventListener("click", async () => { const r = await api("/api/retry-failed", { method: "POST" }); toast(`${r.reset} failed file(s) queued — press Start`); refreshIndex(); });

function poll() { clearTimeout(pollTimer); refreshIndex().finally(() => { pollTimer = setTimeout(poll, 1500); }); }

async function refreshIndex() {
  const s = await api("/api/index/status");
  if (!$("#root").value) $("#root").value = s.job?.root || s.media_dir;
  const j = s.job;
  const badge = $("#tabBadge");
  if (j) {
    const done = (j.processed || 0) + (j.failed || 0);
    const pct = j.phase === "processing" && j.total ? (100 * done) / j.total : j.state === "finished" ? 100 : j.phase === "scanning" ? 3 : 0;
    $("#bar").style.width = `${pct}%`;
    const el = ((j.finished_at || s.now) - j.started_at);
    const eta = j.phase === "processing" && done ? (el / done) * (j.total - done) : null;
    $("#jobLine").innerHTML = s.running
      ? `${j.phase === "scanning" ? `Scanning… ${j.total} files seen` : `Processing ${done} / ${j.total}`}${eta ? ` · ETA ${Math.ceil(eta / 60)} min` : ""}${j.current ? ` · <span class="path">${esc(j.current.split(/[\\/]/).pop())}</span>` : ""}`
      : `Last run: <b>${j.state}</b> · ${j.processed} processed, ${j.failed} failed, ${j.skipped} unchanged skipped, ${j.duplicates} duplicates, ${j.unsupported} unsupported · ${Math.round(el)} s`;
    $("#jobMsg").textContent = [j.message, s.error].filter(Boolean).join(" · ");
    badge.classList.toggle("hidden", !s.running);
    badge.textContent = s.running && j.total ? `${Math.round(pct)}%` : "…";
  }
  if (!s.running) clearTimeout(pollTimer);
  const st = s.asset_status || {};
  $("#statusBox").innerHTML = `<table>${["done", "pending", "processing", "failed"].map((k) => `<tr><td class="st-${k}">${k}</td><td>${st[k] || 0}</td></tr>`).join("")}</table>`;

  const [stats, fails, folders] = await Promise.all([api("/api/stats"), api("/api/failures"), api("/api/folders")]);
  const tot = stats.by_kind.reduce((a, r) => ({ f: a.f + r.files, b: a.b + (r.bytes || 0) }), { f: 0, b: 0 });
  $("#statsBox").innerHTML = `<table><tr><th>Type</th><th>Files</th><th>Unique</th><th>Size</th></tr>
    ${stats.by_kind.map((r) => `<tr><td>${r.kind}</td><td>${r.files}</td><td>${r.unique_assets}</td><td>${fmtBytes(r.bytes)}</td></tr>`).join("")}
    <tr><td><b>Total</b></td><td><b>${tot.f}</b></td><td></td><td><b>${fmtBytes(tot.b)}</b></td></tr></table>
    <div class="muted small" style="margin-top:6px">${stats.duplicate_files} duplicate file(s) share content with another file
    ${stats.other.map((o) => ` · ${o.n} ${o.file_status}`).join("")}</div>`;
  $("#timingBox").innerHTML = stats.timing.length ? `<table>${stats.timing.map((t) => `<tr><td>${t.kind}</td><td>${(t.avg_ms / 1000).toFixed(1)} s</td><td class="muted">${t.n} files</td></tr>`).join("")}</table>` : `<span class="muted">nothing processed yet</span>`;

  const rows = [
    ...fails.failed.map((f) => `<tr><td class="st-failed">failed</td><td>${f.kind}</td><td class="path">${esc(f.path)}</td><td>${esc((f.error || "").split("\n")[0])}</td></tr>`),
    ...fails.skipped.map((f) => `<tr><td class="st-pending">${f.file_status}</td><td>${esc(f.ext)}</td><td class="path">${esc(f.path)}</td><td>${esc(f.file_error || "")}</td></tr>`),
    ...fails.warnings.slice(0, 50).map((f) => `<tr><td class="muted">warning</td><td>${f.kind}</td><td class="path">${esc(f.path || "")}</td><td>${esc(f.warnings.join("; "))}</td></tr>`),
  ];
  $("#failBox").innerHTML = rows.length ? `<table><tr><th>Status</th><th>Type</th><th>File</th><th>Reason</th></tr>${rows.join("")}</table>` : `<span class="muted">No problems 🎉</span>`;

  const sel = $("#folder"), cur = sel.value;
  sel.innerHTML = `<option value="">All folders</option>` + folders.map((f) => `<option value="${esc(f)}">${esc(f.split(/[\\/]/).slice(-2).join("/"))}</option>`).join("");
  sel.value = cur;
  if (s.running && !pollTimer) poll();
}

/* ---------------- evaluation ---------------- */
let evalData = null;
$("#evalRun").addEventListener("click", runEval);
$("#evalExport").addEventListener("click", async () => {
  const r = await api("/api/eval/export", { method: "POST" });
  toast("Written: eval/RESULTS.md");
  console.log(r);
});

async function runEval() {
  $("#evalList").innerHTML = `<div class="card muted">Running test queries…</div>`;
  evalData = await api("/api/eval");
  renderEval();
}

function renderEval() {
  const s = evalData.summary;
  const metric = (label, v) => `<div class="metric"><span class="muted small">${label}</span><b>${v ?? "–"}</b></div>`;
  $("#evalSummary").innerHTML = metric("Queries", `${s.fully_judged}/${s.queries} judged`) + metric(`Mean P@${s.k}`, s[`mean_p_at_${s.k}`]) +
    metric("MRR", s.mean_mrr) + metric(`Hit rate@${s.k}`, s[`hit_rate_at_${s.k}`]) + metric("Recall@10", s.mean_recall_at_10);
  $("#evalList").innerHTML = evalData.queries.map((q, qi) => `
    <section class="card evalq" data-qi="${qi}">
      <div class="qhead"><div><h4>${qi + 1}. “${esc(q.query)}”</h4>
        <div class="small"><b>Looking for:</b> ${esc(q.intent || "")}</div>
        <div class="small muted"><b>Expected:</b> ${esc(q.expected || "")}</div></div>
        <div class="small muted" style="text-align:right">${q.metrics ? `P@${s.k} <b>${q.metrics.p_at_k}</b> · MRR <b>${q.metrics.mrr}</b>` : "judge all top-5"}<br>${q.ms} ms${q.detected_type ? " · type: " + q.detected_type : ""}</div></div>
      <div class="evalrow">${q.results.slice(0, s.k).map((r, ri) => `
        <div class="evalitem ${r.relevant === 1 ? "yes" : r.relevant === 0 ? "no" : ""}">
          <img src="${r.thumb ? "/thumbs/" + esc(r.thumb) : ""}" data-ri="${ri}" alt="" title="${esc(r.path)}">
          <div class="eb"><div class="fname">${ri + 1}. ${esc(r.filename)}</div>
            <div class="muted">${r.kind} · ${r.score}${r.match && whereLabel(r.match, r.kind) ? " · " + whereLabel(r.match, r.kind) : ""}</div>
            <div class="judge"><button class="y ${r.relevant === 1 ? "on" : ""}" data-ri="${ri}" data-v="1">✓</button><button class="n ${r.relevant === 0 ? "on" : ""}" data-ri="${ri}" data-v="0">✗</button></div>
          </div></div>`).join("") || `<span class="muted">no results</span>`}</div>
      <textarea placeholder="Observations (e.g. where the search performs poorly and why)">${esc(q.note)}</textarea>
    </section>`).join("");
  $$("#evalList .evalq").forEach((sec) => {
    const q = evalData.queries[Number(sec.dataset.qi)];
    $$(".judge button", sec).forEach((b) => b.addEventListener("click", async () => {
      const r = q.results[Number(b.dataset.ri)];
      const v = Number(b.dataset.v);
      const newVal = r.relevant === v ? null : v;
      await api("/api/eval/judge", { method: "POST", body: JSON.stringify({ query: q.query, hash: r.hash, relevant: newVal === null ? null : !!newVal }) });
      const y = window.scrollY; evalData = await api("/api/eval"); renderEval(); window.scrollTo(0, y);
    }));
    $$("img", sec).forEach((im) => im.addEventListener("click", () => {
      const r = q.results[Number(im.dataset.ri)];
      openPreview({ ...r, ext: "", size: 0, mtime: 0, signals: {}, match: { best: r.match } });
    }));
    $("textarea", sec).addEventListener("change", (e) => api("/api/eval/notes", { method: "POST", body: JSON.stringify({ query: q.query, note: e.target.value }) }));
  });
}

/* ---------------- start ---------------- */
refreshIndex().then(() => doSearch()).catch(() => doSearch());
