/* lumi-staff back office (D2): a cross-tenant staff console, gated on
   me.user.platform_admin. Loads AFTER submission.js + pulses.js so it can reuse
   their file-global components (InputForType, PulseReport). Authors
   definitions/metadata only — never answer data. */
/* global html, useState, useEffect, api, Icon, EmptyState, Spinner, toast, nav,
   InputForType, PulseReport */

const ADMIN_TABS = [
  { key: "orgs", label: "Organisations", icon: "table" },
  { key: "users", label: "Users", icon: "users" },
  { key: "suggestions", label: "Suggestions", icon: "bulb" },
  { key: "pulses", label: "Pulses", icon: "zap" },
  { key: "pulse-reviews", label: "Pulse reviews", icon: "list-checks" },
  { key: "metrics", label: "Metrics", icon: "target" },
  { key: "billing", label: "Billing", icon: "coins" },
  { key: "compliance", label: "Compliance", icon: "lock" },
  { key: "ops", label: "Ops", icon: "sliders" },
  { key: "audit", label: "Audit", icon: "clock" },
];

const adminSpinner = html`<${PageLoading} />`;

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
        ${active === "users" && html`<${AdminUsersTab} />`}
        ${active === "suggestions" && html`<${AdminSuggestionsTab} />`}
        ${active === "pulses" && html`<${AdminPulsesTab} />`}
        ${active === "pulse-reviews" && html`<${AdminPulseReviewsTab} />`}
        ${active === "metrics" && html`<${AdminMetricsTab} />`}
        ${active === "billing" && html`<${AdminBillingTab} />`}
        ${active === "compliance" && html`<${AdminComplianceTab} />`}
        ${active === "ops" && html`<${AdminOpsTab} />`}
        ${active === "audit" && html`<${AdminAuditTab} />`}
      </div>
    </div>`;
};

/* ---- module 1: organisations (cross-tenant; click a row to drill in) ---- */
function AdminOrgsTab() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState(null);   // org_id | null
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/api/admin/orgs").then(setData).catch(e => setErr(e.message)); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load organisations" body=${err} />`;
  if (!data) return adminSpinner;
  if (selected) return html`<${AdminOrgDetail} orgId=${selected} onBack=${() => setSelected(null)} />`;
  const create = async () => {
    if (!newName.trim()) { toast("Give the organisation a name.", "error"); return; }
    setBusy(true);
    try {
      const r = await api("/api/admin/orgs", { method: "POST", body: { name: newName.trim() } });
      toast("Created — now invite its founding Admin.");
      setCreating(false); setNewName("");
      setSelected(r.org_id);
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  const needle = q.trim().toLowerCase();
  const rows = data.orgs.filter(o => !needle
    || (o.name || "").toLowerCase().includes(needle)
    || (o.industry || "").toLowerCase().includes(needle));
  return html`
    <div>
      <div class="admin-toolbar">
        <button class="btn small primary" onClick=${() => setCreating(c => !c)}>＋ New organisation</button>
        <input class="ctl" placeholder="Filter by name or industry…" value=${q}
          onInput=${e => setQ(e.target.value)} aria-label="Filter organisations" />
        <span class="caption">${rows.length} of ${data.total} organisations · click a row for detail</span>
      </div>
      ${creating && html`
        <div class="card admin-card" style=${{ marginBottom: "var(--s3)" }}>
          <label>Organisation name
            <input class="ctl" value=${newName} onInput=${e => setNewName(e.target.value)}
              onKeyDown=${e => { if (e.key === "Enter") create(); }}
              placeholder="e.g. Meridian Foods Ltd" /></label>
          <div class="caption" style=${{ margin: "var(--s1) 0 var(--s2)" }}>
            Creates a full-tier member organisation. No account or password is set here —
            you invite the founding Admin from the org's page and they join themselves.</div>
          <div class="admin-actions">
            <button class="btn small primary" disabled=${busy} onClick=${create}>Create organisation</button>
            <button class="btn small" onClick=${() => setCreating(false)}>Cancel</button>
          </div>
        </div>`}
      <table class="data admin-table">
        <thead><tr>
          <th>Organisation</th><th>Industry</th><th>Size</th><th>Source</th>
          <th class="num">Users</th><th>Profile</th><th>Submitted</th><th>Insights</th>
        </tr></thead>
        <tbody>
          ${rows.map(o => html`<tr key=${o.org_id} style=${{ cursor: "pointer", opacity: o.deactivated ? 0.55 : 1 }} onClick=${() => setSelected(o.org_id)}>
            <td><b>${o.name}</b>${o.deactivated ? html` <span class="admin-status admin-status-rejected">deactivated</span>` : ""}</td>
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

/* ---- module 1b: org drill-down (detail + users + terms) ---- */
function AdminOrgDetail({ orgId, onBack }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const load = () => api("/api/admin/orgs/" + orgId).then(setD).catch(e => setErr(e.message));
  useEffect(() => { load(); }, [orgId]);
  if (err) return html`<div><button class="btn quiet" onClick=${onBack}>← All organisations</button>
    <${EmptyState} icon="info" title="Couldn't load the organisation" body=${err} /></div>`;
  if (!d) return adminSpinner;
  const o = d.org;
  const fact = (label, value) => html`<div><div class="caption">${label}</div><div><b>${value == null || value === "" ? "—" : value}</b></div></div>`;
  const orgDeactivate = async () => {
    const msg = o.deactivated_at
      ? "Reactivate " + (o.name || "this organisation") + "? Members can sign in again immediately."
      : "Deactivate " + (o.name || "this organisation") + "?\n\nEvery member is signed out and locked out until you reactivate. Nothing is deleted — their data and settings are untouched.";
    if (!window.confirm(msg)) return;
    try {
      const verb = o.deactivated_at ? "reactivate" : "deactivate";
      const r = await api("/api/admin/orgs/" + orgId + "/" + verb, { method: "POST", body: {} });
      toast(o.deactivated_at ? "Reactivated." : "Deactivated — " + r.sessions_revoked + " session" + (r.sessions_revoked === 1 ? "" : "s") + " revoked.");
      load();
    } catch (e) { toast(e.message, "error"); }
  };
  return html`
    <div>
      <button class="btn quiet" onClick=${onBack}>← All organisations</button>
      <div class="row spread" style=${{ alignItems: "baseline" }}>
        <h2 class="section-title" style=${{ margin: "var(--s3) 0 var(--s1)" }}>${o.name || "(unnamed org)"}
          ${o.deactivated_at ? html` <span class="admin-status admin-status-rejected">deactivated</span>` : ""}</h2>
        ${o.source !== "staff" && html`<button class=${"btn small" + (o.deactivated_at ? " primary" : " quiet")} onClick=${orgDeactivate}>
          ${o.deactivated_at ? "Reactivate organisation" : "Deactivate organisation"}</button>`}
      </div>
      ${o.deactivated_at && html`<div class="caption" style=${{ color: "var(--red, #b3261e)", marginBottom: "var(--s2)" }}>
        Deactivated ${o.deactivated_at.slice(0, 16)} — members can't sign in and pending invites won't complete. Data is untouched.</div>`}
      <div class="caption" style=${{ marginBottom: "var(--s3)" }}>
        <span class="admin-pill">${o.source}</span> · ${o.tier_entitlement} tier · created ${(o.created_at || "").slice(0, 10)}
      </div>
      <div class="card admin-card" style=${{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))", gap: "var(--s3)" }}>
        ${fact("Industry", o.industry)}
        ${fact("Subsector", o.subsector)}
        ${fact("Size (FTE)", o.fte_band)}
        ${fact("HQ region", o.hq_region)}
        ${fact("Ownership", o.ownership_type)}
        ${fact("Profile classified", o.classified ? "Yes" : "No")}
        ${fact("Submission complete", o.submission_complete ? "Yes" : "No")}
        ${fact("Insights unlocked", o.insights_unlocked_at ? o.insights_unlocked_at.slice(0, 10) : "Locked")}
        ${fact("Contribution clock", o.clock_start ? "Started " + o.clock_start.slice(0, 10) : "Not started")}
        ${fact("Unlocked release", o.unlocked_release)}
        ${fact("Answers stored", d.counts.answers)}
        ${fact("Draft cells", d.counts.drafts)}
        ${fact("Peer groups", d.counts.peer_groups)}
        ${fact("Suggestions sent", d.counts.suggestions)}
        ${fact("Strategy captured", d.strategy && d.strategy.completed_at ? d.strategy.completed_at.slice(0, 10) : "No")}
      </div>

      <div class="admin-toolbar" style=${{ marginTop: "var(--s4)" }}><b>Members</b> <span class="caption">${d.users.length}</span></div>
      ${!d.users.length ? html`<div class="caption" style=${{ marginBottom: "var(--s2)" }}>No members yet — invite the founding Admin below.</div>` :
      html`<table class="data admin-table">
        <thead><tr><th>Email</th><th>Name</th><th>Role</th><th class="num">Live sessions</th><th>Joined</th><th>Actions</th></tr></thead>
        <tbody>${d.users.map(u => html`<tr key=${u.user_id} style=${{ opacity: u.disabled_at ? 0.55 : 1 }}>
          <td><b>${u.email || "—"}</b>${u.platform_admin ? html` <span class="admin-pill">staff</span>` : ""}${u.disabled_at ? html` <span class="admin-status admin-status-rejected">deactivated</span>` : ""}</td>
          <td>${u.display_name || "—"}</td>
          <td>${u.role}</td>
          <td class="num">${u.active_sessions}</td>
          <td class="caption">${(u.created_at || "").slice(0, 10)}</td>
          <td><${AdminUserActions} user=${u} onChanged=${load} /></td>
        </tr>`)}</tbody>
      </table>`}
      <${AdminOrgInvitePanel} orgId=${orgId} invites=${d.invites || []} onChanged=${load} />

      <div class="admin-toolbar" style=${{ marginTop: "var(--s4)" }}><b>Terms acceptances</b> <span class="caption">${d.terms.length} · the DPA evidence trail</span></div>
      ${!d.terms.length ? html`<div class="caption">None recorded.</div>` :
      html`<table class="data admin-table">
        <thead><tr><th>Kind</th><th>Version</th><th>Accepted by</th><th>When</th></tr></thead>
        <tbody>${d.terms.map((t, i) => html`<tr key=${i}>
          <td><span class="admin-pill">${t.kind}</span></td>
          <td>v${t.version}</td>
          <td>${t.email || t.user_id}</td>
          <td class="caption">${(t.accepted_at || "").slice(0, 16)}</td>
        </tr>`)}</tbody>
      </table>`}
    </div>`;
}

/* Invite members into any org (staff may mint the founding Admin — the tenant
   path stays promotion-only). The invitee sets their own password and accepts
   the terms on join; the console only hands out the link. */
function AdminOrgInvitePanel({ orgId, invites, onChanged }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("admin");
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState(null);
  const sendInvite = async () => {
    if (!email.trim()) { toast("Enter the invitee's email address.", "error"); return; }
    setBusy(true);
    try {
      const r = await api("/api/admin/orgs/" + orgId + "/invite", { method: "POST", body: { email: email.trim(), role } });
      setLink(r.link);
      toast("Invite created — expires in " + r.expires_days + " days. Emailed if SMTP is configured; copy the link to be sure.");
      setEmail("");
      onChanged();
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  const revoke = async (token) => {
    if (!window.confirm("Revoke this invite? The link stops working immediately.")) return;
    try { await api("/api/admin/invites/" + token + "/revoke", { method: "POST", body: {} }); toast("Revoked."); onChanged(); }
    catch (e) { toast(e.message, "error"); }
  };
  const copy = (l) => { navigator.clipboard && navigator.clipboard.writeText(l); toast("Copied."); };
  return html`
    <div>
      <div class="admin-toolbar" style=${{ marginTop: "var(--s4)" }}><b>Invite a member</b></div>
      <div class="admin-actions" style=${{ flexWrap: "wrap", alignItems: "center" }}>
        <input class="ctl" style=${{ minWidth: "260px" }} placeholder="person@company.co.uk" value=${email}
          onInput=${e => setEmail(e.target.value)} onKeyDown=${e => { if (e.key === "Enter") sendInvite(); }}
          aria-label="Invitee email" />
        <select class="ctl" value=${role} onChange=${e => setRole(e.target.value)} aria-label="Role">
          <option value="admin">Admin</option>
          <option value="contributor">Contributor</option>
          <option value="viewer">Viewer</option>
        </select>
        <button class="btn small primary" disabled=${busy} onClick=${sendInvite}>Create invite</button>
        ${link && html`<button class="btn small" onClick=${() => copy(link)}>Copy latest link</button>`}
      </div>
      ${invites.length ? html`
        <div class="admin-toolbar" style=${{ marginTop: "var(--s3)" }}><b>Pending invites</b> <span class="caption">${invites.length}</span></div>
        <table class="data admin-table">
          <thead><tr><th>Email</th><th>Role</th><th>Expires</th><th>Actions</th></tr></thead>
          <tbody>${invites.map(i => html`<tr key=${i.token}>
            <td><b>${i.email || "—"}</b></td>
            <td>${i.role}</td>
            <td class="caption">${(i.expires_at || "").slice(0, 16)}</td>
            <td><div class="admin-actions">
              <button class="btn small" onClick=${() => copy(i.link)}>Copy link</button>
              <button class="btn small quiet" onClick=${() => revoke(i.token)}>Revoke</button>
            </div></td>
          </tr>`)}</tbody>
        </table>` : ""}
    </div>`;
}

/* Shared per-user support actions: force sign-out + reset link. */
function AdminUserActions({ user, onChanged }) {
  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState(null);
  const forceOut = async () => {
    if (!window.confirm("Sign " + (user.email || "this user") + " out of every device?")) return;
    setBusy(true);
    try {
      const r = await api("/api/admin/users/" + user.user_id + "/logout", { method: "POST", body: {} });
      toast(r.sessions_revoked + " session" + (r.sessions_revoked === 1 ? "" : "s") + " revoked.");
      if (onChanged) onChanged();
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  const resetLink = async () => {
    setBusy(true);
    try {
      const r = await api("/api/admin/users/" + user.user_id + "/reset-link", { method: "POST", body: {} });
      setLink(r.link);
      toast("Reset link created — expires in " + r.expires_in_hours + " hours.");
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  const copy = () => { navigator.clipboard && navigator.clipboard.writeText(link); toast("Copied."); };
  const toggleActive = async () => {
    const deactivating = !user.disabled_at;
    if (deactivating && !window.confirm("Deactivate " + (user.email || "this account") + "?\n\nThey are signed out everywhere and can't sign in until you reactivate. Nothing is deleted.")) return;
    setBusy(true);
    try {
      await api("/api/admin/users/" + user.user_id + "/" + (deactivating ? "deactivate" : "reactivate"), { method: "POST", body: {} });
      toast(deactivating ? "Deactivated." : "Reactivated — they can sign in again.");
      if (onChanged) onChanged();
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  if (user.disabled_at) return html`
    <div class="admin-actions" style=${{ flexWrap: "wrap" }}>
      <button class="btn small primary" disabled=${busy} onClick=${toggleActive}>Reactivate</button>
    </div>`;
  return html`
    <div class="admin-actions" style=${{ flexWrap: "wrap" }}>
      <button class="btn small" disabled=${busy} onClick=${forceOut}>Sign out everywhere</button>
      ${link ? html`<button class="btn small primary" onClick=${copy}>Copy reset link</button>`
             : html`<button class="btn small" disabled=${busy} onClick=${resetLink}>Reset link</button>`}
      ${!user.platform_admin && html`<button class="btn small quiet" disabled=${busy} onClick=${toggleActive}>Deactivate</button>`}
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

/* ---- module 5: user support (exact-email lookup — deliberately no browse:
   the identity store's no-bulk contract means staff look a member up by the
   address they already hold, or drill in via their organisation) ---- */
function AdminUsersTab() {
  const [email, setEmail] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const look = async () => {
    if (!email.trim()) { toast("Type the member's email address.", "error"); return; }
    setBusy(true);
    try { setResult(await api("/api/admin/users/lookup?email=" + encodeURIComponent(email.trim()))); }
    catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  const u = result && result.found ? result.user : null;
  return html`
    <div>
      <div class="admin-toolbar">
        <input class="ctl" style=${{ minWidth: "280px" }} placeholder="member@company.co.uk" value=${email}
          onInput=${e => setEmail(e.target.value)} onKeyDown=${e => { if (e.key === "Enter") look(); }}
          aria-label="Email to look up" />
        <button class="btn small primary" disabled=${busy} onClick=${look}>Look up</button>
        <span class="caption">Exact email only — or drill in from the Organisations tab.</span>
      </div>
      ${result && !result.found && html`<${EmptyState} icon="users" title="No account with that email"
        body="Check the spelling — the lookup is exact, not fuzzy." />`}
      ${u && html`
        <div class="card admin-card">
          <div class="row spread">
            <div><b>${u.email}</b>${u.platform_admin ? html` <span class="admin-pill">staff</span>` : ""}${u.disabled_at ? html` <span class="admin-status admin-status-rejected">deactivated</span>` : ""}</div>
            <span class="admin-pill">${u.role || "—"}</span>
          </div>
          <div class="caption" style=${{ margin: "var(--s1) 0 var(--s2)" }}>
            ${u.display_name || "—"} · ${u.org_name || "—"} · joined ${(u.created_at || "").slice(0, 10)}
          </div>
          <div class="caption" style=${{ marginBottom: "var(--s2)" }}>
            ${u.active_sessions} live session${u.active_sessions === 1 ? "" : "s"}
            ${u.sessions.length ? " · newest " + (u.sessions[0].created_at || "").slice(0, 16) + " → expires " + (u.sessions[0].expires_at || "").slice(0, 16) : ""}
          </div>
          <${AdminUserActions} user=${u} onChanged=${look} />
        </div>`}
    </div>`;
}

/* ---- module 6: billing — the pulse-launch order ledger ---- */
function AdminBillingTab() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api("/api/admin/orders").then(setData).catch(e => setErr(e.message)); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load orders" body=${err} />`;
  if (!data) return adminSpinner;
  const gbp = (p) => "£" + ((p || 0) / 100).toLocaleString("en-GB");
  if (!data.orders.length) return html`<${EmptyState} icon="coins" title="No orders yet"
    body="Self-service pulse launch fees will appear here once members start paying (or you confirm invoiced launches)." />`;
  return html`
    <div>
      <div class="admin-toolbar">
        <b>${gbp(data.total_paid_pence)} collected</b>
        <span class="caption">${data.orders.length} order${data.orders.length === 1 ? "" : "s"} · Stripe ${data.payments_mode}</span>
      </div>
      <table class="data admin-table">
        <thead><tr><th>Pulse</th><th>Organisation</th><th class="num">Amount</th><th>Status</th><th>Method</th><th>Created</th><th>Paid</th></tr></thead>
        <tbody>${data.orders.map(o => html`<tr key=${o.order_id}>
          <td><b>${o.pulse_name || o.pulse_id}</b></td>
          <td>${o.org_name || "—"}</td>
          <td class="num">${gbp(o.amount_pence)}</td>
          <td><span class=${"admin-status admin-status-" + o.status}>${o.status}</span></td>
          <td class="caption">${o.stripe_payment_intent === "staff-confirmed" ? "invoiced / manual" : (o.stripe_payment_intent ? "card" : "—")}</td>
          <td class="caption">${(o.created_at || "").slice(0, 16)}</td>
          <td class="caption">${(o.paid_at || "").slice(0, 16) || "—"}</td>
        </tr>`)}</tbody>
      </table>
    </div>`;
}

/* ---- module 7: compliance — terms acceptance evidence (org-named; emails
   stay org-scoped in the org drill-down, per the identity no-bulk contract) ---- */
function AdminComplianceTab() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api("/api/admin/terms").then(setData).catch(e => setErr(e.message)); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load acceptances" body=${err} />`;
  if (!data) return adminSpinner;
  return html`
    <div>
      <div class="admin-toolbar">
        <b>${data.total} acceptance${data.total === 1 ? "" : "s"} on record</b>
        <span class="caption">current versions: platform v${data.versions.platform} · data-contribution v${data.versions.data_contribution} · who accepted is in each org's drill-down</span>
      </div>
      <table class="data admin-table">
        <thead><tr><th>Organisation</th><th>Kind</th><th>Version</th><th>Accepted</th></tr></thead>
        <tbody>${data.acceptances.map((t, i) => html`<tr key=${i}>
          <td><b>${t.org_name || t.org_id}</b></td>
          <td><span class="admin-pill">${t.kind}</span></td>
          <td>v${t.version}</td>
          <td class="caption">${(t.accepted_at || "").slice(0, 16)}</td>
        </tr>`)}</tbody>
      </table>
    </div>`;
}

/* ---- module 8: ops — health, modes, config, and the sweep trigger ---- */
function AdminOpsTab() {
  const [h, setH] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [err, setErr] = useState(null);
  const [sweeping, setSweeping] = useState(false);
  const load = () => {
    api("/api/admin/health").then(setH).catch(e => setErr(e.message));
    api("/api/admin/config").then(d => setCfg(d.config)).catch(() => setCfg([]));
  };
  useEffect(() => { load(); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load health" body=${err} />`;
  if (!h || cfg === null) return adminSpinner;
  const mb = (b) => b == null ? "—" : (b / (1024 * 1024)).toFixed(1) + " MB";
  const up = (s) => s >= 86400 ? Math.floor(s / 86400) + "d " + Math.floor((s % 86400) / 3600) + "h"
    : s >= 3600 ? Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m" : Math.floor(s / 60) + "m";
  const c = h.counts, m = h.modes;
  const stat = (label, value, warn) => html`
    <div class="card admin-card" style=${{ padding: "var(--s3)" }}>
      <div class="caption">${label}</div>
      <div style=${{ fontSize: "20px", fontWeight: 700, color: warn ? "var(--red, #b3261e)" : "inherit" }}>${value}</div>
    </div>`;
  const sweep = async (withDigest) => {
    if (!window.confirm(withDigest
      ? "Run the signal sweep AND send the daily+weekly email digests to every opted-in member?"
      : "Run the cross-tenant signal sweep now? (No emails — recompute only.)")) return;
    setSweeping(true);
    try {
      const r = await api("/api/notifications/run-sweep" + (withDigest ? "?digest=daily,weekly" : ""), { method: "POST", body: {} });
      toast(r.orgs_swept + " orgs swept, " + r.events + " events" + (r.digests_sent != null ? ", " + r.digests_sent + " digests sent" : "") + ".");
      load();
    } catch (e) { toast(e.message, "error"); }
    setSweeping(false);
  };
  return html`
    <div>
      <div class="admin-toolbar"><b>Platform health</b>
        <span class="caption">up ${up(h.uptime_seconds)} · release ${h.release ? h.release.release_id : "—"}</span></div>
      <div style=${{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: "var(--s2)" }}>
        ${stat("Organisations", c.orgs_total)}
        ${stat("Members", c.users)}
        ${stat("Live sessions", c.active_sessions)}
        ${stat("Answer rows", c.answers_rows.toLocaleString("en-GB"))}
        ${stat("Active metrics", c.questions_active)}
        ${stat("New suggestions", (c.suggestions_by_status && c.suggestions_by_status.new) || 0)}
        ${stat("Backlog queued", c.backlog_queued)}
        ${stat("AI", m.ai_effective, m.ai_effective === "live")}
        ${stat("Payments", m.payments, m.payments === "live")}
        ${stat("Signal sweep", m.signal_sweep ? "on · " + String(m.sweep_hour_utc).padStart(2, "0") + "h UTC" : "off")}
        ${stat("Email (SMTP)", m.smtp_configured ? "configured" : "console-logged")}
        ${stat("lumi.db", mb(h.storage.lumi_db.db))}
        ${stat("identity.db", mb(h.storage.identity_db.db))}
        ${stat("Backups", h.storage.backups_total)}
      </div>
      ${m.base_url_is_localhost && html`<div class="caption" style=${{ marginTop: "var(--s2)", color: "var(--red, #b3261e)" }}>
        ⚠ LUMI_BASE_URL is ${m.base_url} — emailed invite/reset/share links will break for real recipients. Set it before go-live.</div>`}

      <div class="admin-toolbar" style=${{ marginTop: "var(--s4)" }}><b>Signal sweep</b>
        <span class="caption">recomputes change events for every org — the nightly job, on demand</span></div>
      <div class="admin-actions">
        <button class="btn small" disabled=${sweeping} onClick=${() => sweep(false)}>Run sweep now</button>
        <button class="btn small" disabled=${sweeping} onClick=${() => sweep(true)}>Run sweep + send digests</button>
      </div>

      <div class="admin-toolbar" style=${{ marginTop: "var(--s4)" }}><b>Configuration</b>
        <span class="caption">effective environment · secrets shown as set/unset only</span></div>
      <table class="data admin-table">
        <thead><tr><th>Variable</th><th>Value</th><th>What it does</th></tr></thead>
        <tbody>${cfg.map(v => html`<tr key=${v.name}>
          <td><code class="caption">${v.name}</code></td>
          <td>${!v.set ? html`<span class="caption">unset</span>`
            : v.kind === "secret" ? html`<span class="admin-pill">set · hidden</span>`
            : html`<b>${v.value}</b>`}</td>
          <td class="caption">${v.description}</td>
        </tr>`)}</tbody>
      </table>

      ${h.storage.backups.length ? html`
        <div class="admin-toolbar" style=${{ marginTop: "var(--s4)" }}><b>Latest backups</b></div>
        <table class="data admin-table">
          <thead><tr><th>File</th><th class="num">Size</th><th>Modified</th></tr></thead>
          <tbody>${h.storage.backups.map(b => html`<tr key=${b.file}>
            <td><code class="caption">${b.file}</code></td>
            <td class="num">${mb(b.bytes)}</td>
            <td class="caption">${b.modified}</td>
          </tr>`)}</tbody>
        </table>` : ""}
    </div>`;
}

/* ---- module 9: the audit trail ---- */
function AdminAuditTab() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api("/api/admin/audit?limit=200").then(setData).catch(e => setErr(e.message)); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load the audit trail" body=${err} />`;
  if (!data) return adminSpinner;
  if (!data.entries.length) return html`<${EmptyState} icon="clock" title="No staff actions recorded yet"
    body="Every write you make through this console lands here — who, what, when." />`;
  const detail = (e) => {
    try {
      const d = JSON.parse(e.detail_json || "null");
      if (!d) return "";
      return Object.entries(d).filter(([, v]) => v != null)
        .map(([k, v]) => k + ": " + v).join(" · ");
    } catch (x) { return ""; }
  };
  return html`
    <div>
      <div class="admin-toolbar"><b>${data.total} action${data.total === 1 ? "" : "s"} on record</b>
        <span class="caption">showing the latest ${data.entries.length} · append-only</span></div>
      <table class="data admin-table">
        <thead><tr><th>When (UTC)</th><th>Actor</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead>
        <tbody>${data.entries.map(e => html`<tr key=${e.id}>
          <td class="caption">${(e.created_at || "").slice(0, 16)}</td>
          <td>${e.actor_email || e.actor_user_id}</td>
          <td><span class="admin-pill">${e.action}</span></td>
          <td class="caption">${e.target_kind ? e.target_kind + " · " + (e.target_id || "") : "—"}</td>
          <td class="caption">${detail(e)}</td>
        </tr>`)}</tbody>
      </table>
    </div>`;
}
