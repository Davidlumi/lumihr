/* Pulses — Tier 2 timely topical surveys (2026-06-12).
   A SEPARATE surface from the core benchmark: opt-in cohort per pulse,
   give-to-get per pulse, fully independent of the core unlock gate.
   Reuses the submission input components (same file-global functions) and
   the chart primitives — but never the core nav/aggregates. */
/* global html, useState, useEffect, api, Spinner, EmptyState, PageLoading, nav, toast, Icon,
   fmtValue, PercentileBand, OptionBars, OrderedDist, InputForType */

window.PulsesPage = function ({ me }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api("/api/pulses").then(setData).catch(e => setErr(e.message)); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load pulses" body=${err} />`;
  if (!data) return html`<${PageLoading} />`;
  const open = data.pulses.filter(p => p.accepting);
  const past = data.pulses.filter(p => !p.accepting);
  const Card = (p) => html`
    <div key=${p.pulse_id} class="card pulse-card" role="button" tabindex="0" onClick=${() => nav("/pulse/" + p.pulse_id)}
      onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nav("/pulse/" + p.pulse_id); } }}
      style=${{ padding: "var(--s4)", marginBottom: "var(--s3)", cursor: "pointer" }}>
      <div class="row spread">
        <b>${p.name}</b>
        <span class="chip ${p.accepting ? "pulse-chip" : ""}">${p.accepting ? "open" : p.status}</span>
      </div>
      <div class="caption" style=${{ margin: "var(--s1) 0 var(--s2)" }}>${p.description}</div>
      <div class="caption num">${p.questions} questions · ${p.participants} participating
        ${p.closes_at ? " · closes " + p.closes_at.slice(0, 10) : ""}
        ${p.participated ? html` · <b style=${{ color: "var(--blue)" }}>you've taken part — report available</b>` :
          p.joined ? " · you've joined — finish your answers" : ""}</div>
    </div>`;
  return html`
    <div style=${{ maxWidth: "760px" }}>
      <h1 class="display-title">Pulse</h1>
      <p>Short, timely deep-dives on what's moving in reward right now — separate from your core
      benchmark. Each pulse has its own opt-in group and its own window; take part (free) and you
      see that pulse's report. Your core benchmark is never affected.</p>
      ${me.user.role === "admin" && html`
        <div class="card" style=${{ padding: "var(--s4)", margin: "var(--s3) 0", display: "flex",
          justifyContent: "space-between", alignItems: "center", gap: "var(--s3)" }}>
          <div><b>Run your own pulse</b><div class="caption">Design a survey and launch it to the community.</div></div>
          <button class="btn primary" onClick=${() => nav("/run-a-pulse")}>Get started</button>
        </div>`}
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
  if (!p) return html`<${PageLoading} />`;

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
      <button class="btn quiet" onClick=${() => nav("/pulse")}>← All pulses</button>
      <div class="pulse-banner">Timely pulse — separate from your core benchmark</div>
      <h1 class="display-title" style=${{ margin: "var(--s2) 0 var(--s1)" }}>${p.name}</h1>
      <p class="caption">${p.description} · ${p.participants} organisation${p.participants === 1 ? "" : "s"} participating
        ${p.closes_at ? " · " + (p.accepting ? "closes" : "closed") + " " + p.closes_at.slice(0, 10) : ""}</p>

      ${p.report && html`<${PulseReport} report=${p.report} pid=${pid} me=${me} />`}

      ${!p.joined && p.accepting && html`
        <div class="card" style=${{ padding: "var(--s5)", margin: "var(--s4) 0" }}>
          <b>Take part to see this pulse's report</b>
          <p class="caption" style=${{ margin: "var(--s2) 0 var(--s3)" }}>Free for participants. Answer what applies —
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
              <div style=${{ fontWeight: 600, fontSize: "var(--fs-label)", marginBottom: "var(--s1)" }}>${q.text}</div>
              ${q.help_text && html`<div class="caption" style=${{ marginBottom: "var(--s2)" }}>${q.help_text}</div>`}
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

function pulseCsv(report) {
  const esc = s => '"' + String(s == null ? "" : s).replace(/"/g, '""') + '"';
  const rows = [["Question", "Answer / level", "Cohort %", "Cohort median", "n", "Your answer"]];
  (report.questions || []).forEach(q => {
    const blk = q.block || {};
    if (blk.suppressed) { rows.push([q.title, "(suppressed — fewer than 5)", "", "", "", ""]); return; }
    if (blk.options && blk.options.length) blk.options.forEach(o => rows.push([q.title, o.label, o.pct, "", blk.n, ""]));
    else if (blk.p50 != null) rows.push([q.title, "", "", blk.p50, blk.n, q.you || ""]);
    (q.matrix_rows || []).forEach(r => rows.push([q.title + " — " + r.label, "", "",
      (r.block && r.block.p50) != null ? r.block.p50 : "", (r.block && r.block.n) || "", r.you || ""]));
  });
  return rows.map(r => r.map(esc).join(",")).join("\r\n");
}
function downloadPulseCsv(report) {
  const blob = new Blob(["﻿" + pulseCsv(report)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url;
  a.download = "lumi-pulse-" + String(report.name || "report").replace(/[^a-z0-9]+/gi, "-").toLowerCase().slice(0, 40) + ".csv";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function printPulse(report) {
  const t = document.title;
  document.title = "lumi pulse — " + (report.name || "report");
  window.print();
  setTimeout(() => { document.title = t; }, 500);
}

function PulseReport({ report, pid, me }) {
  if (report.below_floor) return html`
    <div class="card" style=${{ padding: "var(--s5)", margin: "var(--s4) 0", textAlign: "center" }}>
      <div class="unlock-spark" style=${{ margin: "0 auto var(--s2)" }}><${Icon} name="flag" size=${20} /></div>
      <b>Your responses are in — results appear once ${report.floor}+ organisations have taken part.</b>
      <div class="caption" style=${{ marginTop: "var(--s2)" }}>${report.participants} of ${report.floor} so far.
        Every answer stays protected by the same ${report.floor}-organisation rule as the core benchmark.</div>
    </div>`;
  // the deterministic narrative ships in the payload (opens with it instantly);
  // when the AI surface is live it upgrades to the grounded model narrative
  const [nar, setNar] = useState(report.narrative || {});
  useEffect(() => {
    if (!(me.features && me.features.pulse_ai)) return;
    api("/api/pulses/" + pid + "/narrative", { method: "POST", body: {} })
      .then(r => { if (r && r.narrative && r.source === "model") setNar(r.narrative); })
      .catch(() => {});
  }, [pid]);
  const genDate = (report.generated_at || "").slice(0, 10);
  return html`
    <div class="pulse-report-doc" style=${{ margin: "var(--s4) 0" }}>
      <div class="pulse-pdf-head" aria-hidden="true"><span class="logo">lumi<span>.</span></span> · Pulse report</div>
      <div class="card">
        <div class="qsec-head row spread">
          <div><b>Pulse report</b> <span class="caption">· ${report.participants} organisations · ${report.floor}+ suppression · whole-cohort view${genDate ? " · " + genDate : ""}</span></div>
          <div class="row no-print" style=${{ gap: "var(--s2)" }}>
            <button class="btn small" onClick=${() => downloadPulseCsv(report)}><${Icon} name="download" size=${13} /> CSV</button>
            <button class="btn small primary" onClick=${() => printPulse(report)}><${Icon} name="file-text" size=${13} /> Download PDF</button>
          </div>
        </div>
        ${report.illustrative && html`<div class="caption" style=${{ margin: "var(--s2) 0", color: "var(--neutral-perf)" }}>Illustrative sample data — figures shown for demonstration.</div>`}
        ${(nar.summary || (nar.key_findings || []).length) && html`
          <div class="pulse-narrative">
            ${nar.summary && html`<p style=${{ margin: "0 0 var(--s2)" }}>${nar.summary}</p>`}
            ${(nar.key_findings || []).length ? html`
              <div class="pulse-findings">
                <div class="eyebrow" style=${{ marginBottom: "var(--s1)" }}>Key findings</div>
                <ol>${nar.key_findings.map((f, i) => html`<li key=${i}>${f}</li>`)}</ol>
              </div>` : null}
          </div>`}
        ${report.questions.map(q => html`<${PulseQuestionBlock} key=${q.question_id} q=${q} pid=${pid} me=${me} />`)}
        <div class="pulse-pdf-foot" aria-hidden="true">Private & confidential · Generated by lumi${genDate ? " · " + genDate : ""} · figures resting on fewer than 5 organisations are never shown</div>
      </div>
    </div>`;
}

function PulseQuestionBlock({ q, pid, me }) {
  const blk = q.block || {};
  const [com, setCom] = useState(null);
  const askAI = async () => {
    try { setCom("…"); setCom(await api("/api/pulses/" + pid + "/commentary", { method: "POST", body: { question_id: q.question_id } })); }
    catch (e) { setCom(null); toast(e.message, "error"); }
  };
  // the org's OWN answer, resolved to what the charts expect: a number for
  // numeric, or the chosen label(s) for selects ("; "-joined for multi)
  const youNum = q.you != null && q.you !== "" && !isNaN(parseFloat(q.you)) ? parseFloat(q.you) : null;
  const youLabels = q.you && q.type !== "numeric"
    ? (q.type === "multi_select" ? String(q.you).split(";").map(s => s.trim()).filter(Boolean) : [String(q.you)])
    : [];
  return html`
    <div class="q-block">
      <div style=${{ fontWeight: 600, marginBottom: "var(--s2)" }}>${q.title}</div>
      ${blk.suppressed ? html`
        <div class="caption">Fewer than 5 cohort answers for this question — protected, not shown.</div>` : html`
        <div>
          ${blk.p50 != null && html`<${PercentileBand} block=${blk} you=${youNum} unit=${q.unit} favourable=${null} />`}
          ${blk.options && (q.type === "multi_select"
            ? html`<${OptionBars} options=${blk.options} youLabels=${youLabels} />`
            : html`<${OrderedDist} options=${blk.options} youLabels=${youLabels} />`)}
          ${q.matrix_rows && html`
            <table class="data" style=${{ marginTop: "var(--s2)" }}>
              <thead><tr><th>Level</th><th class="num">Cohort</th><th class="num">You</th></tr></thead>
              <tbody>${q.matrix_rows.map(r => html`
                <tr key=${r.row_id}><td>${r.label}</td>
                  <td class="num">${r.block && r.block.suppressed ? "—" :
                    r.block && r.block.p50 != null ? "median " + fmtValue(r.block.p50, q.unit) :
                    r.block && r.block.modal_label ? r.block.modal_label + " (" + r.block.modal_pct + "%)" : "—"}
                    ${r.block && r.block.n ? html`<span class="caption"> · n=${r.block.n}</span>` : ""}</td>
                  <td class="num" style=${{ color: r.you != null && r.you !== "" ? "var(--blue-deep)" : "var(--ink-faint)", fontWeight: 600 }}>${r.you != null && r.you !== "" ? fmtValue(parseFloat(r.you), q.unit) : "—"}</td></tr>`)}
              </tbody></table>`}
          <div class="caption num" style=${{ marginTop: "var(--s1)" }}>n=${blk.n} · asked as ${q.as_asked_version || "v1"}${q.you != null && q.you !== "" && q.type !== "matrix" ? " · your answer marked" : ""}</div>
          ${me.features && me.features.pulse_ai && html`
            <div style=${{ marginTop: "var(--s2)" }}>
              ${!com ? html`<button class="btn small" onClick=${askAI}><${Icon} name="sparkle" size=${12} /> Commentary</button>` :
                com === "…" ? html`<${Spinner} />` : html`
                <div class="def-box" style=${{ marginTop: "var(--s2)" }}>
                  ${Object.entries(com.parts || {}).map(([k, v]) => html`<p key=${k} style=${{ margin: "var(--s1) 0" }}>${v}</p>`)}
                </div>`}
            </div>`}
        </div>`}
    </div>`;
}

/* ========== SELF-SERVICE PULSE BUILDER + PAID LAUNCH (2026-06-22) ============
   An org Admin designs their own survey, submits it for lumi review, and once
   approved pays a one-off launch fee that opens it to the whole community.
   Same engine, same firewall, same give-to-get 5+-org report as every pulse. */

const PULSE_BUILD_TYPES = ["yes_no", "single_select", "multi_select", "numeric"];
const TYPE_LABEL = { yes_no: "Yes / No", single_select: "Pick one", multi_select: "Pick many", numeric: "A number" };
const fmtFee = (pence) => "£" + ((pence || 0) / 100).toLocaleString("en-GB");
const LAUNCH_STEPS = [
  { key: "building", label: "Build" }, { key: "in_review", label: "lumi review" },
  { key: "approved", label: "Pay" }, { key: "paid", label: "Live" },
];
function launchStepIndex(ls) {
  return { building: 0, changes_requested: 0, in_review: 1, approved: 2, paid: 3 }[ls] || 0;
}

function LaunchStepper({ ls }) {
  const idx = launchStepIndex(ls);
  if (ls === "rejected") return html`<div class="pulse-stepper"><div class="pulse-step warn">
    <span class="pulse-step-dot"></span>Not approved</div></div>`;
  return html`
    <div class="pulse-stepper">
      ${LAUNCH_STEPS.map((s, i) => html`
        <div key=${s.key} class=${"pulse-step" + (i < idx ? " done" : "") + (i === idx ? " current" : "")}>
          <span class="pulse-step-dot"></span>${s.label}</div>`)}
    </div>`;
}

window.RunPulsePage = function ({ me }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { api("/api/org/pulses").then(setData).catch(e => setErr(e.message)); }, []);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load your surveys" body=${err} />`;
  if (!data) return html`<${PageLoading} />`;
  const chip = (p) => {
    const ls = p.launch_status;
    const tone = ls === "paid" ? "pulse-chip" : (ls === "rejected" || ls === "changes_requested") ? "warn" : "";
    const label = ls === "paid" ? (p.status === "open" ? "live" : p.status) : ls === "in_review" ? "in review"
      : ls === "changes_requested" ? "changes requested" : ls === "approved" ? "ready to pay"
      : ls === "rejected" ? "declined" : "draft";
    return html`<span class="chip ${tone}">${label}</span>`;
  };
  return html`
    <div style=${{ maxWidth: "780px" }}>
      <div class="row spread" style=${{ alignItems: "flex-end", gap: "var(--s3)" }}>
        <div>
          <h1 class="display-title" style=${{ margin: 0 }}>Run a pulse</h1>
          <p class="pulse-lead">Design your own short survey and launch it to the lumi community — answers come back
            as anonymised, 5+-organisation aggregates, the same protection as your core benchmark.</p>
        </div>
        <button class="btn primary" style=${{ flex: "none" }} onClick=${() => nav("/run-a-pulse/new")}>
          <${Icon} name="list-checks" size=${15} /> New survey</button>
      </div>

      <div class="pulse-how">
        <div class="pulse-how-step"><span class="pulse-how-num">1</span><div><b>Build</b><span class="caption">Design your questions</span></div></div>
        <div class="pulse-how-step"><span class="pulse-how-num">2</span><div><b>We review</b><span class="caption">A quick quality check</span></div></div>
        <div class="pulse-how-step"><span class="pulse-how-num">3</span><div><b>Go live</b><span class="caption">${me && me.config && me.config.pulse_launch_fee_pence ? "from " + fmtFee(me.config.pulse_launch_fee_pence) + " (ex VAT), confirmed at approval" : "Pay once"} · opens to all members</span></div></div>
      </div>

      ${!data.payments_enabled && html`<div class="pulse-note"><${Icon} name="info" size=${14} />
        <span>Card payments are being switched on — for now a lumi admin confirms your launch once it's approved.</span></div>`}

      ${!data.pulses.length ? html`
        <div class="card" style=${{ padding: "var(--s6) var(--s5)", textAlign: "center", marginTop: "var(--s3)" }}>
          <div class="pulse-empty-ico"><${Icon} name="list-checks" size=${24} /></div>
          <b>No surveys yet</b>
          <p class="caption" style=${{ margin: "var(--s1) auto var(--s3)", maxWidth: "44ch" }}>Ask the community a question only
            lumi can answer — pay equity, four-day weeks, AI in reward, whatever's on your board's mind.</p>
          <button class="btn primary" onClick=${() => nav("/run-a-pulse/new")}>Create your first survey</button>
        </div>` :
        html`<div style=${{ marginTop: "var(--s3)" }}>${data.pulses.map(p => html`
          <div key=${p.pulse_id} class="card pulse-srow" role="button" tabindex="0" onClick=${() => nav("/run-a-pulse/" + p.pulse_id)}
            onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nav("/run-a-pulse/" + p.pulse_id); } }}>
            <div class="row spread"><b>${p.name}</b>${chip(p)}</div>
            <div class="caption" style=${{ margin: "var(--s1) 0 0" }}>${p.n_questions} question${p.n_questions === 1 ? "" : "s"}${p.launch_status === "paid" ? ` · ${p.n_submitted} response${p.n_submitted === 1 ? "" : "s"}` : ""}${p.launch_fee_pence ? ` · ${fmtFee(p.launch_fee_pence)} launch fee` : ""}</div>
          </div>`)}</div>`}
    </div>`;
};

window.PulseBuilderPage = function ({ me, pid }) {
  const isNew = pid === "new";
  const [detail, setDetail] = useState(isNew ? { launch_status: "building", question_list: [] } : null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => { if (!isNew) api("/api/org/pulses/" + pid).then(setDetail).catch(e => setErr(e.message)); };
  useEffect(() => {
    load();
    if (isNew) return;
    const h = window.location.hash;
    if (h.indexOf("cancelled=1") >= 0) {
      toast("Payment cancelled — your survey is still approved, you can try again.", "error");
      nav("/run-a-pulse/" + pid);
    } else if (h.indexOf("paid=1") >= 0) {
      // DON'T trust the redirect — reconcile the Stripe session server-side so a
      // delayed/unconfigured webhook can't leave a paid-but-never-live pulse
      nav("/run-a-pulse/" + pid);   // strip the query first
      toast("Confirming your payment…");
      api("/api/org/pulses/" + pid + "/confirm-payment", { method: "POST", body: {} })
        .then(r => {
          if (r.state === "live") toast("Payment confirmed — your pulse is live to the community.", "success");
          else toast("Payment received — we're finalising your launch; this page will update shortly.");
          load();
        })
        .catch(() => { toast("We're confirming your payment — refresh in a moment."); load(); });
    }
  }, [pid]);
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load this survey" body=${err} />`;
  if (!detail) return html`<${PageLoading} />`;
  const ls = detail.launch_status;
  const editable = ls === "building" || ls === "changes_requested";

  const submitCreate = async (body) => { setBusy(true);
    try { const r = await api("/api/org/pulses", { method: "POST", body }); toast("Draft saved.", "success"); nav("/run-a-pulse/" + r.pulse_id); }
    catch (e) { toast(e.message, "error"); } setBusy(false); };
  const submitUpdate = async (body) => { setBusy(true);
    try { await api("/api/org/pulses/" + pid, { method: "PUT", body }); toast("Saved.", "success"); load(); }
    catch (e) { toast(e.message, "error"); } setBusy(false); };
  const submitForReview = async () => { setBusy(true);
    try {
      await api("/api/org/pulses/" + pid + "/submit-for-review", { method: "POST", body: {} });
      toast("Submitted for review — we'll be in touch.", "success");
      if (window.confettiBurst) window.confettiBurst({ count: 80, spread: 0.85, origin: { x: 0.5, y: 0.3 } });
      load();
    } catch (e) { toast(e.message, "error"); } setBusy(false); };
  const discard = async () => { if (!window.confirm("Discard this draft survey?")) return;
    try { await api("/api/org/pulses/" + pid, { method: "DELETE" }); toast("Discarded."); nav("/run-a-pulse"); }
    catch (e) { toast(e.message, "error"); } };

  return html`
    <div style=${{ maxWidth: "780px" }}>
      <button class="btn quiet" onClick=${() => nav("/run-a-pulse")}>← Your surveys</button>
      ${!isNew && html`<${LaunchStepper} ls=${ls} />`}
      ${ls === "changes_requested" && detail.review_notes && html`
        <div class="card" style=${{ padding: "var(--s4)", margin: "var(--s3) 0", borderLeft: "3px solid var(--amber-bright)" }}>
          <b>lumi asked for a few changes</b><p class="caption" style=${{ margin: "var(--s1) 0 0" }}>${detail.review_notes}</p></div>`}
      ${editable
        ? html`<${PulseComposer} initial=${detail} isNew=${isNew} busy=${busy}
            onSubmit=${isNew ? submitCreate : submitUpdate}
            onSubmitReview=${isNew ? null : submitForReview} onDiscard=${isNew ? null : discard} />`
        : html`<${PulseLaunchPanel} detail=${detail} pid=${pid} onChange=${load} />`}
    </div>`;
};

function PulseComposer({ initial, isNew, busy, onSubmit, onSubmitReview, onDiscard }) {
  const [name, setName] = useState(initial.name || "");
  const [desc, setDesc] = useState(initial.description || "");
  const [closesAt, setClosesAt] = useState(initial.closes_at || "");
  const [keep, setKeep] = useState((initial.question_list || []).map(q => ({ id: q.id, text: q.text, type: q.type })));
  const [newQs, setNewQs] = useState([]);
  const [lib, setLib] = useState(null);
  const [libQ, setLibQ] = useState("");
  const [showLib, setShowLib] = useState(false);
  useEffect(() => { if (showLib && lib === null) api("/api/questions").then(d => setLib(d.questions || [])).catch(() => setLib([])); }, [showLib]);
  const removeKeep = (id) => setKeep(k => k.filter(x => x.id !== id));
  const addLib = (x) => setKeep(k => k.some(i => i.id === x.id) ? k : [...k, { id: x.id, text: x.title, type: x.type }]);
  const addNew = () => setNewQs(n => [...n, { text: "", type: "yes_no", polarity: "neutral", optionsText: "Yes\nNo" }]);
  const setNQ = (i, patch) => setNewQs(n => n.map((x, j) => j === i ? { ...x, ...patch } : x));
  const removeNQ = (i) => setNewQs(n => n.filter((_, j) => j !== i));
  const liveNew = () => newQs.filter(nq => (nq.text || "").trim());
  const buildBody = () => {
    const bespoke = liveNew().map(nq => {
      const isSel = ["single_select", "yes_no", "multi_select"].includes(nq.type);
      const labels = (nq.optionsText || "").split("\n").map(s => s.trim()).filter(Boolean);
      return { text: nq.text.trim(), type: nq.type, polarity: nq.polarity || "neutral",
        options: isSel ? labels.map((l, i) => ({ code: l.toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_|_$/g, "") || ("OPT" + i), label: l, order: i + 1, is_na: false })) : undefined };
    });
    return { name: name.trim(), description: desc.trim(), closes_at: closesAt.trim() || null,
      question_ids: keep.map(k => k.id), new_questions: bespoke };
  };
  const valid = () => {
    if (!name.trim()) { toast("Give your survey a name.", "error"); return false; }
    if (!keep.length && !liveNew().length) { toast("Add at least one question.", "error"); return false; }
    return true;
  };
  const save = () => { if (valid()) onSubmit(buildBody()); };
  const saveThenReview = async () => { if (!valid()) return; await onSubmit(buildBody()); onSubmitReview(); };
  const needle = libQ.trim().toLowerCase();
  const libRows = (lib || []).filter(x => !needle || (x.title || "").toLowerCase().includes(needle) || (x.subpower || "").toLowerCase().includes(needle));
  return html`
    <div class="card pulse-form" style=${{ padding: "var(--s5)", marginTop: "var(--s3)" }}>
      <h2 class="section-title">${isNew ? "New survey" : "Edit your survey"}</h2>
      <p class="caption" style=${{ marginTop: "2px" }}>Members answer what applies; you get back anonymised aggregates (5+ organisations).</p>
      <label>Survey name<input class="ctl" value=${name} onInput=${e => setName(e.target.value)} placeholder="e.g. Four-day-week appetite 2026" /></label>
      <label>Description<textarea class="ctl" rows=${2} value=${desc} onInput=${e => setDesc(e.target.value)} placeholder="One line on what you're asking and why."></textarea></label>
      <label>Close date <span class="caption" style=${{ fontWeight: 400 }}>· optional</span>
        <input class="ctl" value=${closesAt} onInput=${e => setClosesAt(e.target.value)} placeholder="YYYY-MM-DD HH:MM:SS" /></label>

      <div class="qsec-head" style=${{ marginTop: "var(--s4)" }}><b>Questions</b> <span class="caption">· ${keep.length + liveNew().length} so far</span></div>
      ${keep.map(k => html`
        <div key=${k.id} class="pulse-keep-row">
          <span>${k.text} <span class="caption">· ${TYPE_LABEL[k.type] || k.type}</span></span>
          <button class="btn small quiet" onClick=${() => removeKeep(k.id)}>Remove</button></div>`)}
      ${newQs.map((nq, i) => html`
        <div key=${"n" + i} class="pulse-newq">
          <div class="row spread"><b class="caption">New question ${i + 1}</b>
            <button class="btn small quiet" onClick=${() => removeNQ(i)}>Remove</button></div>
          <label>Question<input class="ctl" value=${nq.text} onInput=${e => setNQ(i, { text: e.target.value })} placeholder="What do you want to ask?" /></label>
          <div class="row" style=${{ gap: "var(--s3)" }}>
            <label style=${{ flex: 1 }}>Answer type<select class="ctl" value=${nq.type} onChange=${e => setNQ(i, { type: e.target.value })}>
              ${PULSE_BUILD_TYPES.map(t => html`<option key=${t} value=${t}>${TYPE_LABEL[t]}</option>`)}</select></label>
            ${nq.type === "numeric" && html`<label style=${{ flex: 1 }}>Better when<select class="ctl" value=${nq.polarity} onChange=${e => setNQ(i, { polarity: e.target.value })}>
              <option value="neutral">no preference</option><option value="higher_is_better">higher</option><option value="lower_is_better">lower</option></select></label>`}
          </div>
          ${["single_select", "yes_no", "multi_select"].includes(nq.type) && html`
            <label>Options <span class="caption" style=${{ fontWeight: 400 }}>· one per line</span>
              <textarea class="ctl" rows=${3} value=${nq.optionsText} onInput=${e => setNQ(i, { optionsText: e.target.value })}></textarea></label>`}
        </div>`)}
      <div class="row" style=${{ gap: "var(--s2)", marginTop: "var(--s3)" }}>
        <button class="btn small" onClick=${addNew}>＋ Add a question</button>
        <button class="btn small quiet" onClick=${() => setShowLib(s => !s)}>${showLib ? "Hide library" : "＋ Add from the lumi library"}</button>
      </div>
      ${showLib && html`
        <div style=${{ marginTop: "var(--s2)" }}>
          <input class="ctl" style=${{ width: "100%" }} placeholder="Search the library…" value=${libQ} onInput=${e => setLibQ(e.target.value)} />
          <div class="pulse-libpick">
            ${lib === null ? html`<${Spinner} />` : libRows.slice(0, 120).map(x => html`
              <button key=${x.id} class="pulse-librow" disabled=${keep.some(k => k.id === x.id)} onClick=${() => addLib(x)}>
                ${x.title} <span class="caption">· ${x.subpower || "—"} · ${x.type}</span></button>`)}
          </div></div>`}
      <div class="row" style=${{ gap: "var(--s2)", marginTop: "var(--s5)", flexWrap: "wrap" }}>
        <button class="btn" disabled=${busy} onClick=${save}>${isNew ? "Save draft" : "Save changes"}</button>
        ${!isNew && onSubmitReview && html`<button class="btn primary" disabled=${busy} onClick=${saveThenReview}>Submit for review →</button>`}
        ${!isNew && onDiscard && html`<button class="btn quiet" style=${{ marginLeft: "auto" }} onClick=${onDiscard}>Discard</button>`}
      </div>
      ${isNew && html`<p class="caption" style=${{ marginTop: "var(--s2)" }}>Save the draft, then submit it for review when you're ready.</p>`}
    </div>`;
}

function PulseLaunchPanel({ detail, pid, onChange }) {
  const ls = detail.launch_status;
  useEffect(() => {
    if (ls === "paid") {
      const k = "lumi.pulse.celebrated." + pid;
      if (!localStorage.getItem(k)) {
        localStorage.setItem(k, "1");
        setTimeout(() => window.confettiBurst && window.confettiBurst({ origin: { x: 0.5, y: 0.34 } }), 250);
      }
    }
  }, [ls, pid]);
  const pay = async () => {
    try {
      const r = await api("/api/org/pulses/" + pid + "/checkout", { method: "POST", body: {} });
      if (r.mode === "stripe" && r.checkout_url) { window.location.href = r.checkout_url; return; }
      toast(r.message || "Launch requested — a lumi admin will confirm it shortly.", "info");
      onChange();
    } catch (e) { toast(e.message, "error"); }
  };
  const QList = () => html`
    <div class="card" style=${{ padding: "var(--s4)", marginTop: "var(--s3)" }}>
      <div class="qsec-head"><b>${detail.name}</b></div>
      ${detail.description ? html`<p class="caption">${detail.description}</p>` : ""}
      ${(detail.question_list || []).map(q => html`<div key=${q.id} class="caption" style=${{ padding: "3px 0" }}>• ${q.text} <span style=${{ opacity: 0.7 }}>(${TYPE_LABEL[q.type] || q.type})</span></div>`)}
    </div>`;
  if (ls === "in_review") return html`
    <div class="card" style=${{ padding: "var(--s5)", marginTop: "var(--s3)", textAlign: "center" }}>
      <div class="pulse-empty-ico"><${Icon} name="list-checks" size=${24} /></div>
      <b>With lumi for review</b>
      <p class="caption" style=${{ margin: "var(--s1) auto 0", maxWidth: "44ch" }}>We're checking your survey before it goes
        out to the community — usually within a couple of working days. We'll let you know when it's approved.</p>
    </div>
    ${QList()}`;
  if (ls === "approved") return html`
    <div class="card pulse-launch" style=${{ marginTop: "var(--s3)" }}>
      <div class="pulse-empty-ico"><${Icon} name="check" size=${24} /></div>
      <b style=${{ fontSize: "var(--fs-card-title)" }}>Approved — ready to launch</b>
      <p class="caption" style=${{ margin: "var(--s2) auto 0", maxWidth: "40ch" }}>Pay the one-off launch fee and your survey opens to the whole community.</p>
      <div class="pulse-fee">${fmtFee(detail.launch_fee_pence)}</div>
      <div class="caption" style=${{ marginBottom: "var(--s2)" }}>ex VAT · a VAT invoice and receipt are issued on payment</div>
      <button class="btn primary" onClick=${pay}>${detail.payments_enabled ? "Pay & launch →" : "Request launch"}</button>
      ${!detail.payments_enabled ? html`<p class="caption" style=${{ marginTop: "var(--s3)" }}>Card payments are being switched on — a lumi admin will confirm your launch.</p>` : ""}
    </div>
    ${QList()}`;
  if (ls === "paid") return html`
    <div class="card pulse-launch live" style=${{ marginTop: "var(--s3)" }}>
      <div class="pulse-empty-ico"><${Icon} name="sparkle" size=${24} /></div>
      <b style=${{ fontSize: "var(--fs-card-title)" }}>You're live — open to the community</b>
      <p class="caption" style=${{ margin: "var(--s2) auto var(--s3)", maxWidth: "40ch" }}>${detail.n_submitted || 0} response${detail.n_submitted === 1 ? "" : "s"} so far · results unlock at 5+ organisations.</p>
      <button class="btn primary" onClick=${() => nav("/pulse/" + pid)}>View the live pulse & report →</button>
    </div>`;
  if (ls === "rejected") return html`
    <${EmptyState} icon="info" title="Not approved for launch"
      body=${detail.review_notes || "lumi wasn't able to approve this survey for the community."} />`;
  return html`<${EmptyState} icon="info" title="Draft" body="Edit your survey to continue." />`;
}
