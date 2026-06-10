/* Commercial layer UI: gap register, board pack, Ask lumi analyst, Peer Twin
   panel, shares, team, settings, upgrade. */
/* global html, useState, useEffect, useRef, api, fmtValue, pLabel, Chip, Term, Spinner, Modal,
   EmptyState, nav, SP_ICONS, SUPERPOWERS, fmtGBPCompact, cutQS, cutLabelOf */

// --------------------------------------------------------- gap register ----
window.GapRegisterPage = function ({ me, cut, cuts }) {
  const [data, setData] = useState(null);
  const [sp, setSp] = useState("");
  const [show, setShow] = useState("gaps"); // gaps | all
  useEffect(() => { setData(null); api("/api/gap-register?" + cutQS(cut)).then(setData); }, [cutKeyOf(cut)]);
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  let rows = data.rows.filter(r => !r.suppressed);
  if (sp) rows = rows.filter(r => r.superpower === sp);
  if (show === "gaps") rows = rows.filter(r => r.org_answered && r.in_place === false && (r.gap || 0) > 0);
  return html`
    <div>
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <h1 class="display-title">Practice & policy gap register</h1>
          <div class="caption" style=${{ marginTop: "4px" }}>
            What similar organisations have in place that you don't — sorted so the most commonly held missing items lead.
            Peer group: ${cutLabelOf(cut, cuts)}.
          </div>
        </div>
        <div class="row">
          <select class="ctl" value=${sp} onChange=${e => setSp(e.target.value)}>
            <option value="">All superpowers</option>
            ${SUPERPOWERS.map(s => html`<option key=${s} value=${s}>${s}</option>`)}
          </select>
          <select class="ctl" value=${show} onChange=${e => setShow(e.target.value)}>
            <option value="gaps">Gaps only</option><option value="all">Everything</option>
          </select>
          ${me.user.role === "admin" && html`
            <a class="btn" href=${"/api/gap-register.csv?" + cutQS(cut)} download>Download gap register (CSV)</a>`}
        </div>
      </div>

      <div class="sp-grid" style=${{ marginBottom: "var(--s4)" }}>
        ${SUPERPOWERS.filter(s => data.maturity[s]).map(s => {
          const mt = data.maturity[s];
          return html`
          <div key=${s} class="card sp-card" onClick=${() => setSp(sp === s ? "" : s)}
            style=${sp === s ? { borderColor: "var(--brand)" } : null}>
            <div class="row spread"><span class="sp-name"><${SpIcon} sp=${s} size=${14} /> ${s}</span></div>
            <div class="row spread" style=${{ marginTop: "6px" }}>
              <div><div class="metric-value" style=${{ fontSize: "20px" }}>${mt.org_score == null ? "—" : mt.org_score}</div><div class="caption">your maturity</div></div>
              <div style=${{ textAlign: "right" }}><div class="metric-value" style=${{ fontSize: "20px", color: "var(--ink-2)" }}>${mt.peer_median_score == null ? "—" : mt.peer_median_score}</div><div class="caption">peer median</div></div>
            </div>
            <div class="progressbar" style=${{ marginTop: "8px" }}><div style=${{ width: (mt.org_score || 0) + "%" }}></div></div>
          </div>`;
        })}
      </div>

      ${rows.length === 0 ? html`<${EmptyState} icon="list-checks" title=${show === "gaps" ? "No common gaps found" : "Nothing to show"}
        body=${show === "gaps" ? "Nothing widely adopted by this peer group is missing from your organisation." : "Try different filters."} />` :
      html`<div class="card" style=${{ padding: "var(--s4)" }}>
        <table class="data">
          <thead><tr><th>Practice / policy</th><th>Superpower</th><th>Your status</th>
            <th class="num">Peers with this</th><th class="num">Sector peers</th><th>Tier</th></tr></thead>
          <tbody>
            ${rows.slice(0, 80).map(r => html`
              <tr key=${r.question_id}>
                <td><b>${r.name}</b></td>
                <td>${r.superpower}</td>
                <td>${r.org_answered ? html`<span class=${"chip " + (r.in_place ? "good" : "bad")}>${r.in_place ? "In place" : "Not in place"}</span>
                  <div class="caption" style=${{ marginTop: "2px", maxWidth: "220px" }}>${r.org_status}</div>` :
                  html`<span class="chip">Not answered</span>`}</td>
                <td class="num"><b>${r.peer_adoption_pct == null ? "—" : r.peer_adoption_pct + "%"}</b><div class="caption">n=${r.n}</div></td>
                <td class="num">${r.sector_adoption_pct == null ? "—" : r.sector_adoption_pct + "%"}</td>
                <td><span class="chip">${r.tier}</span></td>
              </tr>`)}
          </tbody>
        </table>
        ${rows.length > 80 && html`<div class="caption" style=${{ padding: "10px" }}>Showing the top 80 of ${rows.length} rows — download the CSV for the full register.</div>`}
      </div>`}
    </div>`;
};

// ------------------------------------------------------------ board pack ---
window.BoardPackPage = function ({ me, cut }) {
  const [packs, setPacks] = useState(null);
  const [gen, setGen] = useState(false);
  const [err, setErr] = useState(null);
  useEffect(() => { api("/api/boardpacks").then(d => setPacks(d.packs)); }, []);
  const generate = async () => {
    setGen(true); setErr(null);
    try {
      const r = await api("/api/boardpack/generate", { method: "POST", body: { cut: cut.dim, cut_value: cut.value } });
      nav("/boardpack/" + r.pack_id);
    } catch (e) { setErr(e.message); }
    setGen(false);
  };
  return html`
    <div style=${{ maxWidth: "760px" }}>
      <h1 class="display-title">Board pack</h1>
      <p>A board-ready summary of your benchmark position: where you lead, the biggest gaps, what closing them is
      worth, and recommended actions — every figure cited with its percentile, peer group and sample size.</p>
      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <div class="row spread">
          <div>
            <b>Generate a new board pack</b>
            <div class="caption">Uses your current peer-group filter (${cut.dim === "all" ? "All peers" : cut.value || cut.dim}). Takes a few seconds.</div>
          </div>
          <button class="btn primary" disabled=${gen} onClick=${generate}>${gen ? html`<${Spinner} /> Writing…` : "Generate board pack"}</button>
        </div>
        ${err && html`<div class="error-text" style=${{ marginTop: "8px" }}>${err}</div>`}
      </div>
      ${packs && packs.length > 0 && html`
        <div class="card" style=${{ padding: "var(--s4)" }}>
          <h2 class="section-title">Previous packs</h2>
          <table class="data"><tbody>
            ${packs.map(p => html`
              <tr key=${p.pack_id}>
                <td>Board pack — ${new Date(p.created_at + "Z").toLocaleString("en-GB", { dateStyle: "long", timeStyle: "short" })}</td>
                <td style=${{ textAlign: "right" }}><button class="btn small" onClick=${() => nav("/boardpack/" + p.pack_id)}>Open</button></td>
              </tr>`)}
          </tbody></table>
        </div>`}
    </div>`;
};

window.BoardPackView = function ({ packId, me, shared, sharedData }) {
  const [pack, setPack] = useState(sharedData || null);
  const [shareLink, setShareLink] = useState(null);
  useEffect(() => {
    if (!sharedData) api("/api/boardpack/" + packId).then(setPack).catch(() => setPack({ error: true }));
  }, [packId]);
  if (!pack) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  if (pack.error) return html`<${EmptyState} title="Board pack not found" />`;
  const p = pack.payload, n = pack.narrative;
  const foot = `Generated ${p.generated_date} · Peer group: ${p.cut_label}, n=${p.cut_n != null ? p.cut_n : p.peer_pool.total} · Methodology v1`;
  const Footer = ({ page }) => html`<div class="pack-footer"><span>${foot}</span><span>lumi · ${page}</span></div>`;
  const makeShare = async () => {
    const r = await api("/api/shares", { method: "POST", body: { kind: "boardpack", config: { pack_id: packId }, expiry_days: 30 } });
    setShareLink(window.location.origin + r.url);
  };
  return html`
    <div>
      ${!shared && html`
        <div class="row spread no-print" style=${{ maxWidth: "210mm", margin: "0 auto var(--s4)" }}>
          <button class="btn quiet" onClick=${() => nav("/boardpack")}>← Back</button>
          <div class="row">
            ${n._fallback && html`<${Chip} kind="warn">Deterministic narrative — set ANTHROPIC_API_KEY for AI-written prose<//>`}
            ${me && me.user.role === "admin" && html`<button class="btn" onClick=${makeShare}>Create share link (30 days)</button>`}
            <button class="btn primary" onClick=${() => window.print()}>Download PDF</button>
          </div>
        </div>`}
      ${shareLink && html`
        <div class="card no-print" style=${{ maxWidth: "210mm", margin: "0 auto var(--s4)", padding: "var(--s3) var(--s4)" }}>
          Share link (read-only, 30 days): <a href=${shareLink}>${shareLink}</a>
        </div>`}

      <div class="pack-page">
        <div style=${{ marginTop: "40mm" }}>
          <div style=${{ fontSize: "13px", fontWeight: 700, color: "var(--brand-ink)", letterSpacing: ".1em" }}>LUMI PEOPLE ANALYTICS BENCHMARK</div>
          <h1 style=${{ fontSize: "34px", lineHeight: 1.15, margin: "12px 0 6px", letterSpacing: "-0.02em" }}>${p.organisation.name}</h1>
          <div style=${{ fontSize: "16px", color: "var(--ink-2)" }}>Board pack · ${p.collection_window}</div>
          <div class="row" style=${{ marginTop: "18px" }}>
            <${Chip} kind="accent">${p.organisation.industry || "Unclassified"}<//>
            <${Chip}>${p.organisation.fte_band ? p.organisation.fte_band + " FTE" : ""}<//>
            <${Chip}>Peer group: ${p.cut_label}<//>
          </div>
        </div>
        <${Footer} page="Cover" />
      </div>

      <div class="pack-page">
        <h2 class="section-title">Executive position</h2>
        <div class="card banner" style=${{ marginBottom: "16px", boxShadow: "none" }}>
          <div>
            <div class="metric-value">${p.headline.above_median} of ${p.headline.comparable_metrics}</div>
            <div class="caption">comparable metrics at or above the peer median (${p.headline.broadly_in_line} broadly in line, ${p.headline.below_median} below)</div>
          </div>
          <div style=${{ borderLeft: "1px solid var(--border)", paddingLeft: "20px" }}>
            <div class="metric-value">${p.peer_pool.total}</div>
            <div class="caption">organisations in the lumi peer pool</div>
          </div>
        </div>
        ${(n.executive_summary || "").split(/\n\n+/).map((para, i) => html`<p key=${i} style=${{ fontSize: "13.5px" }}>${para}</p>`)}
        <p class="caption">Peer-group composition: ${p.peer_pool.total} UK organisations across 14 sectors (${p.peer_pool.classified} fully classified);
        comparisons use the ${p.cut_label} cut unless stated. Figures resting on fewer than 5 organisations are never shown.</p>
        <${Footer} page="1" />
      </div>

      <div class="pack-page">
        <h2 class="section-title">Where ${p.organisation.name} leads</h2>
        <p>${n.strengths_narrative}</p>
        <${PackTable} rows=${p.strengths} good=${true} />
        <h2 class="section-title" style=${{ marginTop: "26px" }}>Largest gaps to peers</h2>
        <p>${n.gaps_narrative}</p>
        <${PackTable} rows=${p.gaps} good=${false} />
        <${Footer} page="2" />
      </div>

      <div class="pack-page">
        <h2 class="section-title">What closing the gaps is worth</h2>
        <p>${n.opportunity_narrative}</p>
        ${p.opportunities.length ? html`
          <table class="data" style=${{ marginBottom: "14px" }}>
            <thead><tr><th>Lever</th><th class="num">To peer median</th><th class="num">To upper quartile</th><th>Type</th></tr></thead>
            <tbody>${p.opportunities.map(o => html`
              <tr key=${o.label}><td><b>${o.label}</b><div class="caption">${o.formula}</div></td>
              <td class="num"><b>${fmtGBPCompact(o.to_p50_gbp)}/yr</b></td>
              <td class="num">${fmtGBPCompact(o.to_p75_gbp)}/yr</td>
              <td>${o.direction === "saving" ? "Potential saving" : "Investment to close"}</td></tr>`)}
            </tbody>
          </table>
          <p class="caption">Indicative modelling only. Assumptions: median salary £${(p.opportunity_assumptions.median_salary_gbp || 0).toLocaleString("en-GB")};
          cost per leaver ${p.opportunity_assumptions.cost_per_leaver_pct_salary}% of salary; agency premium ${p.opportunity_assumptions.agency_premium_pct}%;
          FTE from band midpoints. Edit these in Settings and regenerate.</p>` :
        html`<p class="caption">No £ opportunities could be modelled for this peer group (metrics suppressed or not yet answered).</p>`}
        <h2 class="section-title" style=${{ marginTop: "22px" }}>Recommended actions</h2>
        <ol style=${{ fontSize: "13.5px", paddingLeft: "20px" }}>
          ${(n.recommended_actions || []).map((a, i) => html`<li key=${i} style=${{ marginBottom: "7px" }}>${a}</li>`)}
        </ol>
        <${Footer} page="3" />
      </div>

      <div class="pack-page">
        <h2 class="section-title">Appendix — practices common among peers but not in place</h2>
        ${p.gap_register_top.length ? html`
          <table class="data">
            <thead><tr><th>Practice / policy</th><th>Superpower</th><th>Your status</th><th class="num">Peer adoption</th></tr></thead>
            <tbody>${p.gap_register_top.map((r, i) => html`
              <tr key=${i}><td>${r.name}</td><td>${r.superpower}</td><td class="caption">${r.your_status}</td>
              <td class="num"><b>${r.peer_adoption_pct}%</b> <span class="caption">(n=${r.n})</span></td></tr>`)}
            </tbody>
          </table>` : html`<p class="caption">No qualifying items.</p>`}
        <p class="caption" style=${{ marginTop: "14px" }}>Methodology: percentiles use linear interpolation; medians (P50) are
        preferred to means; aggregates resting on fewer than 5 organisations are suppressed; practice adoption means an answer
        scoring ≥50 on the question's 0–100 scale. Full methodology in the lumi platform.</p>
        <${Footer} page="4" />
      </div>
    </div>`;
};

function PackTable({ rows, good }) {
  if (!rows || !rows.length) return html`<p class="caption">None identified in this peer group.</p>`;
  return html`
    <table class="data">
      <thead><tr><th>Metric</th><th class="num">You</th><th class="num">Peer P50</th><th class="num">Percentile</th><th class="num">n</th></tr></thead>
      <tbody>
        ${rows.map((r, i) => html`
          <tr key=${i}>
            <td><b>${r.label}</b><div class="caption">${r.superpower} · ${r.cut_label}</div></td>
            <td class="num"><b>${r.value_display}</b></td>
            <td class="num">${r.p50_display || "—"}</td>
            <td class="num"><span class=${"chip " + (good ? "good" : "bad")}>${pLabel(r.percentile)}</span></td>
            <td class="num">${r.n}</td>
          </tr>`)}
      </tbody>
    </table>`;
}
window.PackTable = PackTable;

// ------------------------------------------------------------- Ask lumi ----
window.AnalystPane = function ({ onClose }) {
  const [msgs, setMsgs] = useState([{ role: "bot", text: "I'm lumi's benchmark analyst. Ask me how you compare with similar organisations — I'll only ever answer from the benchmark data, with the percentile, peer group and sample size cited." }]);
  const [starters, setStarters] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);
  useEffect(() => { api("/api/analyst/starters").then(d => setStarters(d.starters)).catch(() => {}); }, []);
  useEffect(() => { endRef.current && endRef.current.scrollIntoView({ behavior: "smooth" }); }, [msgs]);
  const ask = async (q) => {
    if (!q.trim() || busy) return;
    setMsgs(m => [...m, { role: "user", text: q }]);
    setInput(""); setBusy(true);
    try {
      const r = await api("/api/analyst", { method: "POST", body: { question: q } });
      setMsgs(m => [...m, { role: "bot", text: r.answer, chips: r.chips }]);
    } catch (e) {
      setMsgs(m => [...m, { role: "bot", text: "Sorry — something went wrong: " + e.message }]);
    }
    setBusy(false);
  };
  return html`
    <div class="analyst-pane">
      <div class="row spread" style=${{ padding: "var(--s4)", borderBottom: "1px solid var(--border)" }}>
        <b>Ask lumi</b>
        <button class="iconbtn" onClick=${onClose}>✕</button>
      </div>
      <div class="analyst-msgs">
        ${msgs.map((m, i) => html`
          <div key=${i} class=${"msg " + m.role}>
            ${m.text}
            ${m.chips && m.chips.length > 0 && html`
              <div>${m.chips.map((c, j) => html`
                <div key=${j} class="statchip" onClick=${() => { c.question_id && nav("/metric/" + c.question_id); onClose(); }}>
                  <span>${c.label}</span><b>${c.value}</b><span>${c.sub}</span>
                  ${c.question_id && html`<span style=${{ color: "var(--brand-ink)" }}>View metric →</span>`}
                </div>`)}</div>`}
          </div>`)}
        ${busy && html`<div class="msg bot"><${Spinner} /> Checking the benchmark…</div>`}
        ${msgs.length === 1 && starters.length > 0 && html`
          <div>
            <div class="caption" style=${{ marginBottom: "6px" }}>Try one of these — based on your biggest gaps:</div>
            ${starters.map((s, i) => html`
              <button key=${i} class="btn small" style=${{ margin: "0 6px 6px 0", whiteSpace: "normal", textAlign: "left" }}
                onClick=${() => ask(s)}>${s}</button>`)}
          </div>`}
        <div ref=${endRef}></div>
      </div>
      <div style=${{ padding: "var(--s3)", borderTop: "1px solid var(--border)", display: "flex", gap: "8px" }}>
        <input class="ctl" style=${{ flex: 1, maxWidth: "none" }} placeholder="e.g. How does our pension compare?"
          value=${input} onInput=${e => setInput(e.target.value)}
          onKeyDown=${e => { if (e.key === "Enter") ask(input); }} />
        <button class="btn primary" disabled=${busy} onClick=${() => ask(input)}>Ask</button>
      </div>
    </div>`;
};

// -------------------------------------------------------------- Peer Twin --
window.PeerTwinPanel = function ({ onUse, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => { api("/api/peer-twin").then(setData).catch(e => setData({ available: false, message: e.message })); }, []);
  return html`
    <${Modal} onClose=${onClose}>
      <h2 class="section-title">Organisations like you</h2>
      ${!data ? html`<${Spinner} />` :
      !data.available ? html`<p>${data.message}</p>` :
      html`<div>
        <p>${data.rationale.note}</p>
        <h3 style=${{ fontSize: "13px", margin: "14px 0 6px" }}>Why these peers?</h3>
        <table class="data">
          <thead><tr><th>Attribute</th><th>You</th><th class="num">Matching twin peers</th></tr></thead>
          <tbody>
            ${data.rationale.attributes.map(a => html`
              <tr key=${a.attribute}>
                <td>${a.attribute}</td><td><b>${a.your_value}</b></td>
                <td class="num">${a.matching_peers} of ${a.of}</td>
              </tr>`)}
          </tbody>
        </table>
        <p class="caption" style=${{ marginTop: "10px" }}>Similarity also weighs workforce shape (frontline, shift and unionised
        percentages). Peer names are never shown, and anything resting on fewer than 5 of these organisations stays hidden.</p>
        <div class="row" style=${{ justifyContent: "flex-end", marginTop: "10px" }}>
          <button class="btn" onClick=${onClose}>Close</button>
          <button class="btn primary" onClick=${() => { onUse(); onClose(); }}>Use as my peer group</button>
        </div>
      </div>`}
    <//>`;
};

// ----------------------------------------------------------------- shares --
window.SharesPage = function () {
  const [data, setData] = useState(null);
  const refresh = () => api("/api/shares").then(setData);
  useEffect(() => { refresh(); }, []);
  const revoke = async (t) => { await api("/api/shares/" + t, { method: "DELETE" }); refresh(); };
  const createDash = async (days) => {
    await api("/api/shares", { method: "POST", body: { kind: "dashboard", config: { cut: { dim: "all" } }, expiry_days: days } });
    refresh();
  };
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  return html`
    <div style=${{ maxWidth: "880px" }}>
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <h1 class="display-title">Manage shares</h1>
          <div class="caption" style=${{ marginTop: "4px" }}>Read-only links for people outside your lumi team. A link shows exactly what your team can see — your data plus safe peer aggregates — and nothing more.</div>
        </div>
        <div class="row">
          <button class="btn" onClick=${() => createDash(7)}>Share dashboard (7 days)</button>
          <button class="btn" onClick=${() => createDash(30)}>30 days</button>
          <button class="btn" onClick=${() => createDash(90)}>90 days</button>
        </div>
      </div>
      ${data.shares.length === 0 ? html`<${EmptyState} icon="link" title="No share links yet"
        body="Create a dashboard share above, or share a board pack from its page." />` :
      html`<div class="card" style=${{ padding: "var(--s4)" }}>
        <table class="data">
          <thead><tr><th>Type</th><th>Link</th><th>Expires</th><th>Status</th><th>Activity</th><th></th></tr></thead>
          <tbody>
            ${data.shares.map(s => html`
              <tr key=${s.token} style=${s.revoked ? { opacity: 0.55 } : null}>
                <td><b>${s.kind === "boardpack" ? "Board pack" : "Dashboard"}</b></td>
                <td>${s.revoked ? html`<span class="muted">revoked</span>` :
                  html`<a href=${s.url} target="_blank">${window.location.origin}${s.url.slice(0, 18)}…</a>
                  <button class="iconbtn" title="Copy link" onClick=${() => navigator.clipboard.writeText(window.location.origin + s.url)}>⧉</button>`}</td>
                <td>${s.expires_at ? new Date(s.expires_at + "Z").toLocaleDateString("en-GB") : "Never"}</td>
                <td>${s.revoked ? html`<span class="chip bad">Revoked</span>` :
                  (s.expires_at && new Date(s.expires_at + "Z") < new Date()) ? html`<span class="chip warn">Expired</span>` :
                  html`<span class="chip good">Live</span>`}</td>
                <td class="caption">${s.audit.map((a, i) => html`<div key=${i}>${a.action} by ${a.email || "?"} · ${new Date(a.at + "Z").toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" })}</div>`)}</td>
                <td>${!s.revoked && html`<button class="btn small danger" onClick=${() => revoke(s.token)}>Revoke</button>`}</td>
              </tr>`)}
          </tbody>
        </table>
      </div>`}
    </div>`;
};

// ------------------------------------------------------------------ team ---
window.TeamPage = function ({ me }) {
  const [data, setData] = useState(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const refresh = () => api("/api/team").then(setData);
  useEffect(() => { refresh(); }, []);
  const invite = async () => {
    setErr(null); setMsg(null);
    try {
      const r = await api("/api/team/invite", { method: "POST", body: { email, role } });
      setMsg(`Invite created (expires in ${r.expires_days} days). The link has been logged to the server console — in production this is emailed.`);
      setEmail(""); refresh();
    } catch (e) { setErr(e.message); }
  };
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  return html`
    <div style=${{ maxWidth: "760px" }}>
      <h1 class="display-title">Team</h1>
      <div class="card" style=${{ padding: "var(--s4)", margin: "var(--s4) 0" }}>
        <table class="data">
          <thead><tr><th>Member</th><th>Role</th><th>Joined</th></tr></thead>
          <tbody>
            ${data.users.map(u => html`
              <tr key=${u.email}><td><b>${u.display_name || u.email}</b><div class="caption">${u.email}</div></td>
              <td><span class=${"chip " + (u.role === "admin" ? "accent" : "")}>${u.role}</span></td>
              <td class="caption">${new Date(u.created_at + "Z").toLocaleDateString("en-GB")}</td></tr>`)}
          </tbody>
        </table>
      </div>
      ${me.user.role === "admin" && html`
        <div class="card" style=${{ padding: "var(--s4)" }}>
          <h2 class="section-title">Invite a colleague</h2>
          <div class="row">
            <input class="ctl" style=${{ flex: 1 }} placeholder="colleague@yourorg.co.uk" value=${email} onInput=${e => setEmail(e.target.value)} />
            <select class="ctl" value=${role} onChange=${e => setRole(e.target.value)}>
              <option value="viewer">Viewer — dashboards & board packs</option>
              <option value="admin">Admin — also submit data, share, manage team</option>
            </select>
            <button class="btn primary" onClick=${invite}>Send invite</button>
          </div>
          ${msg && html`<div class="ok-text" style=${{ marginTop: "8px" }}>${msg}</div>`}
          ${err && html`<div class="error-text" style=${{ marginTop: "8px" }}>${err}</div>`}
          ${data.invites.length > 0 && html`
            <h3 style=${{ fontSize: "13px", margin: "16px 0 6px" }}>Outstanding invites</h3>
            ${data.invites.map(i => html`
              <div key=${i.token} class="caption">${i.email} (${i.role}) — expires ${new Date(i.expires_at + "Z").toLocaleDateString("en-GB")}</div>`)}`}
        </div>`}
    </div>`;
};

// -------------------------------------------------------------- settings ---
window.SettingsPage = function ({ me, refreshMe }) {
  const [a, setA] = useState(null);
  const [editable, setEditable] = useState(false);
  const [msg, setMsg] = useState(null);
  useEffect(() => { api("/api/assumptions").then(d => { setA(d.assumptions); setEditable(d.editable); }); }, []);
  const save = async () => {
    await api("/api/assumptions", { method: "PUT", body: { assumptions: {
      median_salary_gbp: +a.median_salary_gbp, cost_per_leaver_pct_salary: +a.cost_per_leaver_pct_salary,
      agency_premium_pct: +a.agency_premium_pct } } });
    setMsg("Saved — £ figures across lumi now use these assumptions."); setTimeout(() => setMsg(null), 3000);
  };
  const togglePreview = async () => {
    await api("/api/me/preview-core", { method: "POST", body: { on: !me.user.preview_as_core } });
    refreshMe();
  };
  if (!a) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  return html`
    <div style=${{ maxWidth: "640px" }}>
      <h1 class="display-title">Settings</h1>
      <div class="card" style=${{ padding: "var(--s5)", margin: "var(--s4) 0" }}>
        <h2 class="section-title">£ modelling assumptions</h2>
        <p class="caption">Every "opportunity" figure in lumi is indicative and rests on these assumptions. Change them to match your organisation.</p>
        <div class="field"><label>Median salary (£/yr)</label>
          <input type="number" value=${a.median_salary_gbp} disabled=${!editable} onInput=${e => setA({ ...a, median_salary_gbp: e.target.value })} /></div>
        <div class="field"><label>Cost per leaver (% of salary — recruitment, cover and ramp-up)</label>
          <input type="number" value=${a.cost_per_leaver_pct_salary} disabled=${!editable} onInput=${e => setA({ ...a, cost_per_leaver_pct_salary: e.target.value })} /></div>
        <div class="field"><label>Agency premium (% over employed cost)</label>
          <input type="number" value=${a.agency_premium_pct} disabled=${!editable} onInput=${e => setA({ ...a, agency_premium_pct: e.target.value })} /></div>
        <div class="caption" style=${{ marginBottom: "10px" }}>Workforce mix by level and FTE band midpoints are fixed platform assumptions, shown in the <a href="#/methodology">methodology</a>.</div>
        ${editable ? html`<button class="btn primary" onClick=${save}>Save assumptions</button>` :
        html`<div class="caption">Only admins can edit assumptions.</div>`}
        ${msg && html`<div class="ok-text" style=${{ marginTop: "8px" }}>${msg}</div>`}
      </div>
      ${me.org.tier_entitlement === "full" && me.user.role === "admin" && html`
        <div class="card" style=${{ padding: "var(--s5)" }}>
          <h2 class="section-title">Preview as Core member</h2>
          <p class="caption">See lumi the way a Core-tier member sees it — Enhanced, Pulse and Strategic benchmarks lock. Useful for demos.</p>
          <button class="btn" onClick=${togglePreview}>${me.user.preview_as_core ? "Switch back to Full view" : "Preview as Core member"}</button>
        </div>`}
    </div>`;
};

// --------------------------------------------------------------- upgrade ---
window.UpgradePage = function () {
  return html`
    <div style=${{ maxWidth: "620px", margin: "0 auto", textAlign: "center", paddingTop: "60px" }}>
      <div style=${{ fontSize: "40px" }}>🔓</div>
      <h1 class="display-title">Unlock the full lumi benchmark</h1>
      <p>Core membership includes 138 benchmarks. The full set adds 640 more across Enhanced, Pulse and
      Strategic tiers — deeper reward data, wellbeing practice, leadership and change benchmarks.</p>
      <p class="caption">Talk to the lumi membership team to upgrade — this build doesn't take payments.</p>
      <a class="btn primary" href="mailto:members@lumi.example?subject=lumi%20Full%20membership">Contact the membership team</a>
    </div>`;
};
