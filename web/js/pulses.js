/* Pulses — Tier 2 timely topical surveys (2026-06-12).
   A SEPARATE surface from the core benchmark: opt-in cohort per pulse,
   give-to-get per pulse, fully independent of the core unlock gate.
   Reuses the submission input components (same file-global functions) and
   the chart primitives — but never the core nav/aggregates. */
/* global html, useState, useEffect, api, Spinner, EmptyState, nav, toast, Icon,
   PercentileBand, OptionBars, OrderedDist, InputForType */

window.PulsesPage = function ({ me }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api("/api/pulses").then(setData).catch(e => setErr(e.message)); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load pulses" body=${err} />`;
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  const open = data.pulses.filter(p => p.accepting);
  const past = data.pulses.filter(p => !p.accepting);
  const Card = (p) => html`
    <div key=${p.pulse_id} class="card pulse-card" onClick=${() => nav("/pulses/" + p.pulse_id)}
      style=${{ padding: "var(--s4)", marginBottom: "var(--s3)", cursor: "pointer" }}>
      <div class="row spread">
        <b>${p.name}</b>
        <span class="chip ${p.accepting ? "pulse-chip" : ""}">${p.accepting ? "open" : p.status}</span>
      </div>
      <div class="caption" style=${{ margin: "4px 0 6px" }}>${p.description}</div>
      <div class="caption num">${p.questions} questions · ${p.participants} participating
        ${p.closes_at ? " · closes " + p.closes_at.slice(0, 10) : ""}
        ${p.participated ? html` · <b style=${{ color: "var(--blue)" }}>you've taken part — report available</b>` :
          p.joined ? " · you've joined — finish your answers" : ""}</div>
    </div>`;
  return html`
    <div style=${{ maxWidth: "760px" }}>
      <h1 class="display-title">Pulses</h1>
      <p>Short, timely deep-dives on what's moving in reward right now — separate from your core
      benchmark. Each pulse has its own opt-in group and its own window; take part (free) and you
      see that pulse's report. Your core benchmark is never affected.</p>
      <h2 class="section-title" style=${{ marginTop: "var(--s4)" }}>Open now</h2>
      ${open.length ? open.map(Card) : html`<div class="caption">No pulse is open right now — new topics land here as they emerge.</div>`}
      <h2 class="section-title" style=${{ marginTop: "var(--s5)" }}>Closed & archived</h2>
      ${past.length ? past.map(Card) : html`<div class="caption">Past pulses and their reports will be kept here.</div>`}
    </div>`;
};

window.PulseDetailPage = function ({ me, pid }) {
  const [p, setP] = useState(null);
  const [err, setErr] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [issues, setIssues] = useState({});
  const refresh = () => api("/api/pulses/" + pid).then(d => {
    setP(d);
    const init = {};
    (d.question_list || []).forEach(q => {
      if (q.type === "matrix") Object.entries(q.current || {}).forEach(([rid, v]) => { if (v != null) init[q.id + "|" + rid] = v; });
      else if (q.current != null) init[q.id + "|"] = q.current;
    });
    setDrafts(init);
  }).catch(e => setErr(e.message));
  useEffect(() => { refresh(); }, [pid]);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load this pulse" body=${err} />`;
  if (!p) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;

  const editor = me.user.role === "admin" || me.user.role === "contributor";
  const join = async () => {
    try { await api("/api/pulses/" + pid + "/join", { method: "POST", body: {} }); toast("You're in — answer what applies and submit."); refresh(); }
    catch (e) { toast(e.message, "error"); }
  };
  const save = async (q, rowId, value) => {
    const key = q.id + "|" + (rowId || "");
    setDrafts(d => ({ ...d, [key]: value }));
    try {
      const r = await api("/api/pulses/" + pid + "/response", { method: "PUT",
        body: { question_id: q.id, matrix_row_id: rowId || "", value } });
      setIssues(s => ({ ...s, [key]: { errors: r.errors || [], warnings: r.warnings || [] } }));
    } catch (e) { toast(e.message, "error"); }
  };
  const submit = async () => {
    try { await api("/api/pulses/" + pid + "/submit", { method: "POST", body: {} }); toast("Thank you — this pulse's report is now yours."); refresh(); }
    catch (e) { toast(e.message, "error"); }
  };

  return html`
    <div style=${{ maxWidth: "780px" }}>
      <button class="btn quiet" onClick=${() => nav("/pulses")}>← All pulses</button>
      <div class="pulse-banner">Timely pulse — separate from your core benchmark</div>
      <h1 class="display-title" style=${{ margin: "6px 0 4px" }}>${p.name}</h1>
      <p class="caption">${p.description} · ${p.participants} organisation${p.participants === 1 ? "" : "s"} participating
        ${p.closes_at ? " · " + (p.accepting ? "closes" : "closed") + " " + p.closes_at.slice(0, 10) : ""}</p>

      ${p.report && html`<${PulseReport} report=${p.report} pid=${pid} me=${me} />`}

      ${!p.joined && p.accepting && html`
        <div class="card" style=${{ padding: "var(--s5)", margin: "var(--s4) 0" }}>
          <b>Take part to see this pulse's report</b>
          <p class="caption" style=${{ margin: "6px 0 10px" }}>Free for participants. Answer what applies —
            partial answers count. Taking part doesn't change your core benchmark or its unlock.</p>
          ${editor ? html`<button class="btn primary" onClick=${join}>Join this pulse</button>` :
            html`<div class="caption">Ask an Admin or Contributor on your team to join and answer.</div>`}
        </div>`}
      ${!p.joined && !p.accepting && !p.report && html`
        <${EmptyState} icon="lock" title="This pulse has closed"
          body="Its report belongs to the organisations that took part during the window." />`}

      ${p.joined && p.accepting && html`
        <div class="card" style=${{ margin: "var(--s4) 0" }}>
          <div class="qsec-head"><b>Your answers</b> <span class="caption">· answer what applies — skipped questions are simply excluded</span></div>
          ${p.question_list.map(q => html`
            <div key=${q.id} class="q-block">
              <div style=${{ fontWeight: 600, fontSize: "13.5px", marginBottom: "4px" }}>${q.text}</div>
              ${q.help_text && html`<div class="caption" style=${{ marginBottom: "6px" }}>${q.help_text}</div>`}
              <${InputForType} q=${q} drafts=${drafts} issues=${issues} save=${save} confirmValue=${() => {}} />
              ${(issues[q.id + "|"] || { errors: [] }).errors.map((e, i) => html`<div key=${i} class="error-text">${e}</div>`)}
              ${(issues[q.id + "|"] || { warnings: [] }).warnings.map((w, i) => html`<div key=${i} class="warn-text">⚠ ${w}</div>`)}
            </div>`)}
          <div style=${{ padding: "var(--s4)" }}>
            <button class="btn primary" onClick=${submit}>${p.participated ? "Update my submission" : "Submit and see the report"}</button>
          </div>
        </div>`}
    </div>`;
};

function PulseReport({ report, pid, me }) {
  if (report.below_floor) return html`
    <div class="card" style=${{ padding: "var(--s5)", margin: "var(--s4) 0", textAlign: "center" }}>
      <div style=${{ fontSize: "26px" }}>⏳</div>
      <b>Your responses are in — results appear once ${report.floor}+ organisations have taken part.</b>
      <div class="caption" style=${{ marginTop: "6px" }}>${report.participants} of ${report.floor} so far.
        Every answer stays protected by the same ${report.floor}-organisation rule as the core benchmark.</div>
    </div>`;
  return html`
    <div class="card" style=${{ margin: "var(--s4) 0" }}>
      <div class="qsec-head"><b>Pulse report</b> <span class="caption">· ${report.participants} organisations ·
        same methodology and ${report.floor}+ suppression as the core · whole-cohort view</span></div>
      ${report.questions.map(q => html`<${PulseQuestionBlock} key=${q.question_id} q=${q} pid=${pid} me=${me} />`)}
    </div>`;
}

function PulseQuestionBlock({ q, pid, me }) {
  const blk = q.block || {};
  const [com, setCom] = useState(null);
  const askAI = async () => {
    try { setCom("…"); setCom(await api("/api/pulses/" + pid + "/commentary", { method: "POST", body: { question_id: q.question_id } })); }
    catch (e) { setCom(null); toast(e.message, "error"); }
  };
  return html`
    <div class="q-block">
      <div style=${{ fontWeight: 600, marginBottom: "6px" }}>${q.title}</div>
      ${blk.suppressed ? html`
        <div class="caption">Fewer than 5 cohort answers for this question — protected, not shown.</div>` : html`
        <div>
          ${blk.p50 != null && html`<${PercentileBand} block=${blk} you=${null} unit=${q.unit} favourable=${null} />`}
          ${blk.options && (q.type === "multi_select"
            ? html`<${OptionBars} options=${blk.options} youLabels=${[]} />`
            : html`<${OrderedDist} options=${blk.options} youLabels=${[]} />`)}
          ${q.matrix_rows && html`
            <table class="data" style=${{ marginTop: "6px" }}>
              <thead><tr><th>Level</th><th class="num">Cohort</th></tr></thead>
              <tbody>${q.matrix_rows.map(r => html`
                <tr key=${r.row_id}><td>${r.label}</td>
                  <td class="num">${r.block && r.block.suppressed ? "—" :
                    r.block && r.block.p50 != null ? "median " + fmtValue(r.block.p50, q.unit) :
                    r.block && r.block.modal_label ? r.block.modal_label + " (" + r.block.modal_pct + "%)" : "—"}
                    ${r.block && r.block.n ? html`<span class="caption"> · n=${r.block.n}</span>` : ""}</td></tr>`)}
              </tbody></table>`}
          <div class="caption num" style=${{ marginTop: "4px" }}>n=${blk.n} · asked as ${q.as_asked_version || "v1"}</div>
          ${me.features && me.features.pulse_ai && html`
            <div style=${{ marginTop: "6px" }}>
              ${!com ? html`<button class="btn small" onClick=${askAI}>✦ Commentary</button>` :
                com === "…" ? html`<${Spinner} />` : html`
                <div class="def-box" style=${{ marginTop: "6px" }}>
                  ${Object.entries(com.parts || {}).map(([k, v]) => html`<p key=${k} style=${{ margin: "4px 0" }}>${v}</p>`)}
                </div>`}
            </div>`}
        </div>`}
    </div>`;
}
