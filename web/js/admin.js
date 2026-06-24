/* lumi-staff back office (D2): a cross-tenant staff console, gated on
   me.user.platform_admin. Loads AFTER submission.js + pulses.js so it can reuse
   their file-global components (InputForType, PulseReport). Authors
   definitions/metadata only — never answer data. */
/* global html, useState, useEffect, api, Icon, EmptyState, Spinner, toast, nav,
   InputForType, PulseReport */

const ADMIN_TABS = [
  { key: "orgs", label: "Organisations", icon: "table" },
  { key: "suggestions", label: "Suggestions", icon: "bulb" },
  { key: "pulses", label: "Pulses", icon: "zap" },
  { key: "pulse-reviews", label: "Pulse reviews", icon: "list-checks" },
  { key: "metrics", label: "Metrics", icon: "target" },
];

const adminSpinner = html`<div class="row" style=${{ justifyContent: "center", padding: "var(--s8)" }}><${Spinner} /></div>`;

window.AdminConsolePage = function ({ me, route }) {
  const sub = (route.replace(/^\/admin\/?/, "").split("?")[0].split("/")[0]) || "orgs";
  const active = ADMIN_TABS.some(t => t.key === sub) ? sub : "orgs";
  return html`
    <div class="admin-console">
      <div class="admin-head">
        <div class="eyebrow">lumi staff · back office</div>
        <h1 class="display-title" style=${{ margin: "2px 0 0" }}>Console</h1>
        <p class="caption" style=${{ margin: "var(--s1) 0 0" }}>Cross-tenant staff tools. Signed in as ${me.user.email}.</p>
      </div>
      <div class="admin-tabs">
        ${ADMIN_TABS.map(t => html`
          <button key=${t.key} class=${"admin-tab" + (t.key === active ? " on" : "")}
            onClick=${() => nav("/admin/" + t.key)}>
            <${Icon} name=${t.icon} size=${15} /> ${t.label}
          </button>`)}
      </div>
      <div class="admin-body">
        ${active === "orgs" && html`<${AdminOrgsTab} />`}
        ${active === "suggestions" && html`<${AdminSuggestionsTab} />`}
        ${active === "pulses" && html`<${AdminPulsesTab} />`}
        ${active === "pulse-reviews" && html`<${AdminPulseReviewsTab} />`}
        ${active === "metrics" && html`<${AdminMetricsTab} />`}
      </div>
    </div>`;
};

/* ---- module 1: organisations (cross-tenant, read-only) ---- */
function AdminOrgsTab() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [q, setQ] = useState("");
  useEffect(() => { api("/api/admin/orgs").then(setData).catch(e => setErr(e.message)); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load organisations" body=${err} />`;
  if (!data) return adminSpinner;
  const needle = q.trim().toLowerCase();
  const rows = data.orgs.filter(o => !needle
    || (o.name || "").toLowerCase().includes(needle)
    || (o.industry || "").toLowerCase().includes(needle));
  return html`
    <div>
      <div class="admin-toolbar">
        <input class="ctl" placeholder="Filter by name or industry…" value=${q}
          onInput=${e => setQ(e.target.value)} aria-label="Filter organisations" />
        <span class="caption">${rows.length} of ${data.total} organisations</span>
      </div>
      <table class="data admin-table">
        <thead><tr>
          <th>Organisation</th><th>Industry</th><th>Size</th><th>Source</th>
          <th class="num">Users</th><th>Profile</th><th>Submitted</th><th>Insights</th>
        </tr></thead>
        <tbody>
          ${rows.map(o => html`<tr key=${o.org_id}>
            <td><b>${o.name}</b></td>
            <td>${o.industry || "—"}</td>
            <td>${o.fte_band || "—"}</td>
            <td><span class="admin-pill">${o.source}</span></td>
            <td class="num">${o.n_users}</td>
            <td>${o.classified ? "✓" : "—"}</td>
            <td>${o.submission_complete ? "✓" : "—"}</td>
            <td>${o.unlocked ? html`<span class="admin-yes">Unlocked</span>` : html`<span class="caption">Locked</span>`}</td>
          </tr>`)}
        </tbody>
      </table>
    </div>`;
}

/* ---- module 2: metric-suggestions triage ---- */
function AdminSuggestionsTab() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const load = () => api("/api/admin/suggestions").then(setData).catch(e => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load suggestions" body=${err} />`;
  if (!data) return adminSpinner;
  if (!data.suggestions.length) return html`<${EmptyState} icon="bulb" title="No suggestions yet"
    body="Member 'Suggest a metric' submissions land here for triage." />`;
  return html`<div>
    <div class="admin-toolbar"><span class="caption">${data.suggestions.length} suggestion${data.suggestions.length === 1 ? "" : "s"}</span></div>
    ${data.suggestions.map(s => html`<${SuggestionCard} key=${s.id} s=${s} statuses=${data.statuses} onSaved=${load} />`)}
  </div>`;
}

function SuggestionCard({ s, statuses, onSaved }) {
  const [status, setStatus] = useState(s.status || "new");
  const [notes, setNotes] = useState(s.review_notes || "");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      const r = await api("/api/admin/suggestions/" + s.id, { method: "PUT", body: { status, review_notes: notes } });
      toast(r.promoted_to_backlog ? "Saved — added to the release backlog." : "Saved.");
      onSaved();
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  return html`
    <div class="card admin-card">
      <div class="row spread">
        <div><b>${s.metric_name}</b> <span class="admin-pill">${s.suggested_category || "uncategorised"}</span></div>
        <span class=${"admin-status admin-status-" + status}>${status}</span>
      </div>
      <div class="caption" style=${{ margin: "var(--s1) 0 var(--s2)" }}>From ${s.org_name || "—"} · ${s.user_email || "—"} · ${(s.created_at || "").slice(0, 10)}</div>
      <p style=${{ margin: "var(--s1) 0" }}><b>Measures:</b> ${s.what_it_measures}</p>
      <p style=${{ margin: "var(--s1) 0" }}><b>Why it matters:</b> ${s.why_it_matters}</p>
      <div class="admin-triage">
        <select class="ctl" value=${status} onChange=${e => setStatus(e.target.value)} aria-label="Status">
          ${statuses.map(st => html`<option key=${st} value=${st}>${st}</option>`)}
        </select>
        <textarea class="ctl" placeholder="Review notes…" value=${notes} rows=${2}
          onInput=${e => setNotes(e.target.value)} aria-label="Review notes"></textarea>
        <button class="btn small primary" disabled=${busy} onClick=${save}>Save</button>
      </div>
      ${status === "accepted" && html`<div class="caption" style=${{ marginTop: "var(--s2)" }}>Accepting queues it in the release backlog (Metrics tab).</div>`}
      ${s.reviewed_by && html`<div class="caption" style=${{ marginTop: "var(--s1)" }}>Last reviewed by ${s.reviewed_by}${s.reviewed_at ? " · " + s.reviewed_at.slice(0, 16).replace("T", " ") : ""}</div>`}
    </div>`;
}

/* ---- module 3: pulse builder + management ---- */
function AdminPulsesTab() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [view, setView] = useState({ mode: "list" });   // list | build | report
  const [extendPid, setExtendPid] = useState(null);
  const [extendVal, setExtendVal] = useState("");
  const load = () => api("/api/admin/pulses").then(setData).catch(e => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load pulses" body=${err} />`;
  if (!data) return adminSpinner;
  if (view.mode === "build") return html`<${AdminPulseBuilder} onDone=${() => { setView({ mode: "list" }); load(); }} onCancel=${() => setView({ mode: "list" })} />`;
  if (view.mode === "report") return html`<${AdminPulseReport} pid=${view.pid} onBack=${() => setView({ mode: "list" })} />`;
  const act = async (pid, verb, body) => {
    try { await api("/api/admin/pulses/" + pid + "/" + verb, { method: "POST", body: body || {} }); toast("Done."); load(); }
    catch (e) { toast(e.message, "error"); }
  };
  const applyExtend = (pid) => {
    if (!extendVal.trim()) { toast("Enter a close date/time.", "error"); return; }
    act(pid, "extend", { closes_at: extendVal.trim() }).then(() => { setExtendPid(null); setExtendVal(""); });
  };
  return html`
    <div>
      <div class="admin-toolbar">
        <button class="btn small primary" onClick=${() => setView({ mode: "build" })}>＋ New pulse</button>
        <span class="caption">${data.pulses.length} pulse${data.pulses.length === 1 ? "" : "s"}</span>
      </div>
      ${!data.pulses.length ? html`<${EmptyState} icon="zap" title="No pulses yet"
        body="Create a timely topical survey — reuse library questions or author bespoke ones." />` :
      html`<table class="data admin-table">
        <thead><tr>
          <th>Pulse</th><th>Status</th><th class="num">Qs</th><th class="num">Joined</th>
          <th class="num">Submitted</th><th>Window</th><th>Actions</th>
        </tr></thead>
        <tbody>${data.pulses.map(p => html`<tr key=${p.pulse_id}>
          <td><b>${p.name}</b>${p.description ? html`<div class="caption">${p.description}</div>` : ""}</td>
          <td><span class=${"admin-status admin-status-" + p.status}>${p.status}</span></td>
          <td class="num">${p.n_questions}</td>
          <td class="num">${p.n_participants}</td>
          <td class="num">${p.n_submitted}</td>
          <td class="caption">${p.closes_at ? p.closes_at.slice(0, 16) : "—"}</td>
          <td>
            ${extendPid === p.pulse_id ? html`
              <div class="admin-actions">
                <input class="ctl" style=${{ width: "180px" }} placeholder="YYYY-MM-DD HH:MM:SS"
                  value=${extendVal} onInput=${e => setExtendVal(e.target.value)} aria-label="New close date" />
                <button class="btn small primary" onClick=${() => applyExtend(p.pulse_id)}>Apply</button>
                <button class="btn small" onClick=${() => { setExtendPid(null); setExtendVal(""); }}>Cancel</button>
              </div>` : html`
              <div class="admin-actions">
                ${p.status === "draft" && html`<button class="btn small primary" onClick=${() => act(p.pulse_id, "open")}>Open</button>`}
                ${p.status === "open" && html`<button class="btn small" onClick=${() => { setExtendPid(p.pulse_id); setExtendVal(p.closes_at || ""); }}>Extend</button>`}
                ${p.status === "open" && html`<button class="btn small" onClick=${() => act(p.pulse_id, "close")}>Close</button>`}
                ${p.status === "closed" && html`<button class="btn small" onClick=${() => act(p.pulse_id, "archive")}>Archive</button>`}
                ${p.status !== "draft" && html`<button class="btn small" onClick=${() => setView({ mode: "report", pid: p.pulse_id })}>Report</button>`}
              </div>`}
          </td>
        </tr>`)}</tbody>
      </table>`}
    </div>`;
}

function AdminPulseReport({ pid, onBack }) {
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api("/api/admin/pulses/" + pid + "/report").then(setRep).catch(e => setErr(e.message)); }, [pid]);
  return html`
    <div>
      <button class="btn quiet" onClick=${onBack}>← All pulses</button>
      ${err ? html`<${EmptyState} icon="info" title="Couldn't load the report" body=${err} />`
        : !rep ? adminSpinner
        : html`<h2 class="section-title" style=${{ margin: "var(--s3) 0 0" }}>${rep.name}</h2>
               <${PulseReport} report=${rep} pid=${pid} me=${{ features: {} }} />`}
    </div>`;
}

const PULSE_NEW_TYPES = ["yes_no", "single_select", "multi_select", "numeric"];

function AdminPulseBuilder({ onDone, onCancel }) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [picked, setPicked] = useState([]);
  const [newQs, setNewQs] = useState([]);
  const [lib, setLib] = useState(null);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/api/questions").then(d => setLib(d.questions || [])).catch(() => setLib([])); }, []);
  const toggle = (id) => setPicked(p => p.includes(id) ? p.filter(x => x !== id) : [...p, id]);
  const addNew = () => setNewQs(n => [...n, { text: "", type: "yes_no", polarity: "neutral", optionsText: "Yes\nNo" }]);
  const setNQ = (i, patch) => setNewQs(n => n.map((x, j) => j === i ? { ...x, ...patch } : x));
  const removeNQ = (i) => setNewQs(n => n.filter((_, j) => j !== i));
  const needle = q.trim().toLowerCase();
  const libRows = (lib || []).filter(x => !needle || (x.title || "").toLowerCase().includes(needle) || (x.subpower || "").toLowerCase().includes(needle));
  const create = async () => {
    if (!name.trim()) { toast("Give the pulse a name.", "error"); return; }
    const bespoke = newQs.filter(nq => (nq.text || "").trim()).map(nq => {
      const isSel = ["single_select", "yes_no", "multi_select"].includes(nq.type);
      const labels = (nq.optionsText || "").split("\n").map(s => s.trim()).filter(Boolean);
      return {
        text: nq.text.trim(), type: nq.type, polarity: nq.polarity || "neutral",
        options: isSel ? labels.map((l, i) => ({ code: l.toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_|_$/g, "") || ("OPT" + i), label: l, order: i + 1, is_na: false })) : undefined,
      };
    });
    if (!picked.length && !bespoke.length) { toast("Add at least one question.", "error"); return; }
    setBusy(true);
    try {
      await api("/api/admin/pulses", { method: "POST", body: { name: name.trim(), description: desc.trim(), closes_at: closesAt.trim() || null, question_ids: picked, new_questions: bespoke } });
      toast("Pulse created as a draft.");
      onDone();
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  return html`
    <div class="card admin-card admin-form">
      <button class="btn quiet" onClick=${onCancel}>← All pulses</button>
      <h3 style=${{ margin: "var(--s2) 0 0" }}>New pulse</h3>
      <p class="caption">Created as a draft. Open it to snapshot the questions and let members join.</p>
      <label>Name<input class="ctl" value=${name} onInput=${e => setName(e.target.value)} placeholder="e.g. EU Pay Transparency readiness 2026" /></label>
      <label>Description<textarea class="ctl" rows=${2} value=${desc} onInput=${e => setDesc(e.target.value)}></textarea></label>
      <label>Closes at (optional)<input class="ctl" value=${closesAt} onInput=${e => setClosesAt(e.target.value)} placeholder="YYYY-MM-DD HH:MM:SS" /></label>

      <label>Reuse library questions ${picked.length ? html`<span class="admin-pill">${picked.length} picked</span>` : ""}</label>
      <input class="ctl" placeholder="Search the library…" value=${q} onInput=${e => setQ(e.target.value)} style=${{ marginBottom: "var(--s2)" }} />
      <div class="admin-qpick">
        ${lib === null ? adminSpinner : libRows.slice(0, 200).map(x => html`
          <label key=${x.id}>
            <input type="checkbox" checked=${picked.includes(x.id)} onChange=${() => toggle(x.id)} />
            <span>${x.title} <span class="caption">· ${x.subpower || "—"} · ${x.type}</span></span>
          </label>`)}
      </div>

      <div class="row spread" style=${{ marginTop: "var(--s3)" }}>
        <label style=${{ margin: 0 }}>Bespoke pulse questions</label>
        <button class="btn small" onClick=${addNew}>＋ Add question</button>
      </div>
      ${newQs.map((nq, i) => html`
        <div key=${i} class="admin-subform">
          <div class="row spread">
            <b class="caption">Question ${i + 1}</b>
            <button class="btn small quiet" onClick=${() => removeNQ(i)}>Remove</button>
          </div>
          <label>Text<input class="ctl" value=${nq.text} onInput=${e => setNQ(i, { text: e.target.value })} /></label>
          <div class="admin-grid2">
            <label>Type<select class="ctl" value=${nq.type} onChange=${e => setNQ(i, { type: e.target.value })}>
              ${PULSE_NEW_TYPES.map(t => html`<option key=${t} value=${t}>${t}</option>`)}
            </select></label>
            <label>Polarity<select class="ctl" value=${nq.polarity} onChange=${e => setNQ(i, { polarity: e.target.value })}>
              <option value="neutral">neutral</option>
              <option value="higher_is_better">higher_is_better</option>
              <option value="lower_is_better">lower_is_better</option>
            </select></label>
          </div>
          ${["single_select", "yes_no", "multi_select"].includes(nq.type) && html`
            <label>Options (one per line)<textarea class="ctl" rows=${3} value=${nq.optionsText} onInput=${e => setNQ(i, { optionsText: e.target.value })}></textarea></label>`}
        </div>`)}

      <div class="row" style=${{ gap: "var(--s2)", marginTop: "var(--s4)" }}>
        <button class="btn primary" disabled=${busy} onClick=${create}>Create draft</button>
        <button class="btn" onClick=${onCancel}>Cancel</button>
      </div>
    </div>`;
}

/* ---- module 3b: self-service pulse reviews (member-authored launches) ---- */
function AdminPulseReviewsTab() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [act, setAct] = useState({});   // pid -> { notes, feeGbp }
  const load = () => api("/api/admin/pulse-reviews").then(setData).catch(e => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load reviews" body=${err} />`;
  if (!data) return adminSpinner;
  const defGbp = Math.round((data.default_fee_pence || 75000) / 100);
  const setA = (pid, patch) => setAct(a => ({ ...a, [pid]: { ...(a[pid] || {}), ...patch } }));
  const clearA = (pid) => setAct(s => { const n = { ...s }; delete n[pid]; return n; });
  const decide = async (pid, decision) => {
    const a = act[pid] || {};
    const body = { decision, notes: a.notes || "" };
    if (decision === "approve") body.fee_pence = Math.max(0, Math.round(parseFloat(a.feeGbp != null ? a.feeGbp : defGbp) * 100));
    try { await api("/api/admin/pulses/" + pid + "/review", { method: "POST", body }); toast("Done."); clearA(pid); load(); }
    catch (e) { toast(e.message, "error"); }
  };
  const confirmLaunch = async (pid) => {
    if (!window.confirm("Confirm this launch WITHOUT a card payment (invoiced / manual)? It opens the pulse to the whole community.")) return;
    try { await api("/api/admin/pulses/" + pid + "/confirm-launch", { method: "POST", body: {} }); toast("Launched."); load(); }
    catch (e) { toast(e.message, "error"); }
  };
  const fee = (p) => "£" + ((p.launch_fee_pence || 0) / 100).toLocaleString("en-GB");
  const queue = data.pulses || [];
  const waiting = queue.filter(p => p.launch_status === "in_review");
  const rest = queue.filter(p => p.launch_status !== "in_review");
  const Card = (p) => {
    const a = act[p.pulse_id] || {};
    const needNote = (cb) => () => { if (!(a.notes || "").trim()) { toast("Add a note for the author.", "error"); return; } cb(); };
    return html`
      <div key=${p.pulse_id} class="card admin-card" style=${{ padding: "var(--s4)", marginBottom: "var(--s3)" }}>
        <div class="row spread">
          <div><b>${p.name}</b> <span class="caption">· ${p.owner_name}</span></div>
          <span class=${"admin-status admin-status-" + (p.launch_status || "draft")}>${(p.launch_status || "").replace(/_/g, " ")}</span>
        </div>
        ${p.description ? html`<div class="caption" style=${{ margin: "2px 0 var(--s2)" }}>${p.description}</div>` : ""}
        <div style=${{ marginTop: "var(--s2)" }}>
          ${(p.questions || []).map(q => html`<div key=${q.id} class="caption" style=${{ padding: "3px 0" }}>• ${q.text} <span style=${{ opacity: 0.7 }}>(${q.type})</span></div>`)}
        </div>
        ${p.review_notes ? html`<div class="caption" style=${{ marginTop: "var(--s2)" }}>Note to author: ${p.review_notes}</div>` : ""}
        ${p.launch_status === "in_review" ? html`
          <div style=${{ marginTop: "var(--s3)", borderTop: "1px solid var(--line)", paddingTop: "var(--s3)" }}>
            <textarea class="ctl" rows=${2} placeholder="Note to the author (required to request changes or reject)…"
              value=${a.notes || ""} onInput=${e => setA(p.pulse_id, { notes: e.target.value })}></textarea>
            <div class="admin-actions" style=${{ marginTop: "var(--s2)", alignItems: "center", flexWrap: "wrap" }}>
              <label class="caption" style=${{ display: "flex", alignItems: "center", gap: "var(--s1)", margin: 0 }}>Launch fee £
                <input class="ctl" style=${{ width: "90px" }} type="number" min="0"
                  value=${a.feeGbp != null ? a.feeGbp : defGbp} onInput=${e => setA(p.pulse_id, { feeGbp: e.target.value })} /></label>
              <button class="btn small primary" onClick=${() => decide(p.pulse_id, "approve")}>Approve</button>
              <button class="btn small" onClick=${needNote(() => decide(p.pulse_id, "changes"))}>Request changes</button>
              <button class="btn small quiet" onClick=${needNote(() => decide(p.pulse_id, "reject"))}>Reject</button>
            </div>
          </div>` : p.launch_status === "approved" ? html`
          <div class="admin-actions" style=${{ marginTop: "var(--s3)", alignItems: "center" }}>
            <span class="caption">Approved · ${fee(p)} fee · awaiting payment</span>
            <button class="btn small" onClick=${() => confirmLaunch(p.pulse_id)}>Confirm launch (no card)</button>
          </div>` : p.launch_status === "paid" ? html`
          <div class="caption" style=${{ marginTop: "var(--s2)" }}>Live · ${p.n_submitted} response${p.n_submitted === 1 ? "" : "s"} · ${fee(p)} fee</div>` : ""}
      </div>`;
  };
  return html`
    <div>
      ${data.payments_mode === "off" ? html`<div class="caption" style=${{ marginBottom: "var(--s2)" }}>Card payments are off (no Stripe keys) — approve, then use <b>Confirm launch (no card)</b> to open a pulse.</div>` : html`<div class="caption" style=${{ marginBottom: "var(--s2)" }}>Stripe is <b>${data.payments_mode}</b> mode — authors pay by card; <b>Confirm launch</b> is for invoiced/manual deals.</div>`}
      <div class="admin-toolbar"><b>Awaiting review</b> <span class="caption">${waiting.length}</span></div>
      ${waiting.length ? waiting.map(Card) : html`<${EmptyState} icon="list-checks" title="Nothing to review"
        body="Member-built surveys waiting for approval will appear here." />`}
      ${rest.length ? html`<div class="admin-toolbar" style=${{ marginTop: "var(--s4)" }}><b>Approved, live & past</b> <span class="caption">${rest.length}</span></div>` : ""}
      ${rest.map(Card)}
    </div>`;
}

/* ---- module 4: create metric (author -> backlog -> publish live) ---- */
function AdminMetricsTab() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [editing, setEditing] = useState(false);
  const load = () => api("/api/admin/backlog").then(setData).catch(e => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load the backlog" body=${err} />`;
  if (!data) return adminSpinner;
  if (editing) return html`<${AdminMetricEditor} onDone=${() => { setEditing(false); load(); }} onCancel=${() => setEditing(false)} />`;
  const publish = async (id) => {
    try { const r = await api("/api/admin/metrics/" + id + "/publish", { method: "POST", body: {} }); toast("Published live as " + r.question_id + "."); load(); }
    catch (e) { toast(e.message, "error"); }
  };
  const summarise = (b) => {
    if (b.source !== "admin_console") return b.detail || "";
    try { const m = JSON.parse(b.detail || "{}"); return (m.type || "?") + " · " + (m.sub_power || "?"); } catch (e) { return ""; }
  };
  return html`
    <div>
      <div class="admin-toolbar">
        <button class="btn small primary" onClick=${() => setEditing(true)}>＋ New metric</button>
        <span class="caption">${data.backlog.length} backlog item${data.backlog.length === 1 ? "" : "s"}</span>
      </div>
      ${!data.backlog.length ? html`<${EmptyState} icon="target" title="Backlog is empty"
        body="Author a metric here, or accept a member suggestion to queue one." />` :
      html`<table class="data admin-table">
        <thead><tr><th>Title</th><th>Detail</th><th>Source</th><th>Status</th><th>Created</th><th>Action</th></tr></thead>
        <tbody>${data.backlog.map(b => html`<tr key=${b.id}>
          <td><b>${b.title}</b></td>
          <td class="caption">${summarise(b)}</td>
          <td><span class="admin-pill">${b.source}</span></td>
          <td><span class=${"admin-status admin-status-" + b.status}>${b.status}</span></td>
          <td class="caption">${(b.created_at || "").slice(0, 10)}</td>
          <td>${b.source === "admin_console" && b.status === "queued"
            ? html`<button class="btn small primary" onClick=${() => publish(b.id)}>Publish live</button>`
            : html`<span class="caption">—</span>`}</td>
        </tr>`)}</tbody>
      </table>`}
    </div>`;
}

const METRIC_CATS = ["Pay", "Incentives", "Benefits", "Time Off", "Wellbeing", "Recognition", "Governance"];
const METRIC_TYPES = ["yes_no", "single_select", "multi_select", "numeric"];

function AdminMetricEditor({ onDone, onCancel }) {
  const [f, setF] = useState({
    text: "", short_description: "", help_text: "", definition: "",
    sub_power: "Pay", type: "yes_no", polarity: "neutral", options: "Yes\nNo",
    unit: "", unit_display_name: "", unit_type: "none",
  });
  const set = (patch) => setF(s => ({ ...s, ...patch }));
  const [busy, setBusy] = useState(false);
  const isSelect = ["single_select", "yes_no", "multi_select"].includes(f.type);
  const save = async () => {
    if (!f.text.trim()) { toast("Add the question text.", "error"); return; }
    setBusy(true);
    try {
      const body = { ...f, options: isSelect ? f.options.split("\n").map(s => s.trim()).filter(Boolean) : [] };
      await api("/api/admin/metrics/draft", { method: "POST", body });
      toast("Drafted to backlog — publish it from the list when ready.");
      onDone();
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  return html`
    <div class="card admin-card admin-form" style=${{ maxWidth: "640px" }}>
      <button class="btn quiet" onClick=${onCancel}>← Backlog</button>
      <h3 style=${{ margin: "var(--s2) 0 0" }}>New core metric</h3>
      <p class="caption">Always added unscored + optional — it never re-locks the unlock gate or needs back-filled answers. Saving drafts it to the backlog; you publish it live from the list.</p>
      <label>Question text<textarea class="ctl" rows=${2} value=${f.text} onInput=${e => set({ text: e.target.value })}></textarea></label>
      <label>Short title<input class="ctl" value=${f.short_description} onInput=${e => set({ short_description: e.target.value })} placeholder="(defaults to first 80 chars)" /></label>
      <div class="admin-grid2">
        <label>Category<select class="ctl" value=${f.sub_power} onChange=${e => set({ sub_power: e.target.value })}>
          ${METRIC_CATS.map(c => html`<option key=${c} value=${c}>${c}</option>`)}
        </select></label>
        <label>Type<select class="ctl" value=${f.type} onChange=${e => set({ type: e.target.value })}>
          ${METRIC_TYPES.map(t => html`<option key=${t} value=${t}>${t}</option>`)}
        </select></label>
      </div>
      <label>Polarity<select class="ctl" value=${f.polarity} onChange=${e => set({ polarity: e.target.value })}>
        <option value="neutral">neutral</option>
        <option value="higher_is_better">higher_is_better</option>
        <option value="lower_is_better">lower_is_better</option>
      </select></label>
      ${isSelect && html`<label>Options (one per line)<textarea class="ctl" rows=${3} value=${f.options} onInput=${e => set({ options: e.target.value })}></textarea></label>`}
      ${f.type === "numeric" && html`<div class="admin-grid2">
        <label>Unit type<select class="ctl" value=${f.unit_type} onChange=${e => set({ unit_type: e.target.value })}>
          <option value="none">none</option>
          <option value="percentage">percentage</option>
          <option value="currency">currency</option>
          <option value="number">number</option>
        </select></label>
        <label>Unit display<input class="ctl" value=${f.unit_display_name} onInput=${e => set({ unit_display_name: e.target.value })} placeholder="e.g. % of base salary" /></label>
      </div>`}
      <label>Help text<input class="ctl" value=${f.help_text} onInput=${e => set({ help_text: e.target.value })} /></label>
      <label>Definition<textarea class="ctl" rows=${2} value=${f.definition} onInput=${e => set({ definition: e.target.value })}></textarea></label>
      <div class="row" style=${{ gap: "var(--s2)", marginTop: "var(--s4)" }}>
        <button class="btn primary" disabled=${busy} onClick=${save}>Save to backlog</button>
        <button class="btn" onClick=${onCancel}>Cancel</button>
      </div>
    </div>`;
}
