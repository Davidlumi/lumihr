/* Questionnaire engine — rendered entirely from library metadata.
   Entry guardrails (2026-06-12): soft warnings never block — a member can
   always save their real value; the only refusals are malformed input.
   N/A is first-class (never faked with 0 or blank); units show inline. */
/* global html, useState, useEffect, useRef, api, Chip, Spinner, EmptyState, nav, SP_ICONS, SUPERPOWERS, toast */

window.SubmissionPage = function ({ me, refreshMe, section }) {
  const [state, setState] = useState(null);
  const [err, setErr] = useState(null);
  const refresh = () => api("/api/submission/state").then(setState).catch(e => setErr(e));
  useEffect(() => { refresh(); }, []);
  // The no-section route is now purely a gate on-ramp: once firmographics and
  // the data terms are cleared, bounce to the single "Your data" home — there
  // is no second "submission home" any more.
  useEffect(() => {
    if (state && !section && state.firmographics_done && state.data_terms_accepted) nav("/your-data");
  }, [state, section]);
  if (err) return err.status === 403
    ? html`<${EmptyState} icon="lock" title="Submitting data is a Contributor task" body=${err.message} />`
    : html`<${EmptyState} title="Couldn't load your data" body=${err.message + " — nothing is lost."}
        action=${html`<button class="btn small primary" onClick=${() => { setErr(null); refresh(); }}>Retry</button>`} />`;
  if (!state) return html`<${PageLoading} />`;
  if (!state.firmographics_done) return html`
    <div style=${{ maxWidth: "560px" }}>
      <h1 class="display-title">First, tell us who you are</h1>
      <p>Before the data terms and the questionnaire, we need a few company facts — sector, size,
      region — so the benchmark compares you to the right peers. Two minutes, organisation-level only.</p>
      ${me.user.role === "admin"
        ? html`<button class="btn primary" onClick=${() => nav("/profile")}>Complete your company profile</button>`
        : html`<${EmptyState} icon="lock" title="Waiting on your Admin"
            body="Your organisation's Admin completes the company profile first — then the data terms, then the questionnaire opens." />`}
    </div>`;
  if (!state.data_terms_accepted) return html`<${DataTermsGate} me=${me} refreshMe=${refreshMe}
    onAccepted=${() => { refresh(); refreshMe(); }} />`;
  if (section === "review") return html`<${ReviewStep} state=${state} refresh=${refresh} refreshMe=${refreshMe} />`;
  if (section) return html`<${DomainPage} sp=${section} state=${state} refresh=${refresh} refreshMe=${refreshMe} />`;
  // gates cleared, no section → redirecting to /your-data (above effect)
  return html`<${PageLoading} />`;
};

/* Layer 2 — the Data Contribution Terms. Accepted once, by an Admin, on
   behalf of the organisation, before first submission. Starts the 30-day
   contribution clock. */
function DataTermsGate({ me, onAccepted }) {
  const [terms, setTerms] = useState(null);
  const [tick, setTick] = useState(false);
  const [full, setFull] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  useEffect(() => { api("/api/terms").then(setTerms).catch(e => setErr(e.message)); }, []);
  const isAdmin = me.user.role === "admin";
  const accept = async () => {
    setBusy(true); setErr(null);
    try { await api("/api/terms/accept-data", { method: "POST", body: { accept: tick } }); onAccepted(); }
    catch (e) { setErr(e.message); }
    setBusy(false);
  };
  return html`
    <div style=${{ maxWidth: "680px" }}>
      <h1 class="display-title">Data Contribution Terms</h1>
      <p>Before your organisation's first submission, your Admin reviews and accepts the terms that
      govern how contributed data is used. ${isAdmin ? "You accept once, on behalf of your whole organisation — your team never re-accepts." :
      "Your Admin does this — once accepted, you can begin submitting."}</p>
      <div class="card" style=${{ padding: "var(--s5)", margin: "var(--s4) 0" }}>
        <h2 class="section-title">The essentials</h2>
        <div class="terms-li">• Organisation-level data only — no employee-level or personal data.</div>
        <div class="terms-li">• Your answers appear only inside anonymised aggregates — never shown to another member.</div>
        <div class="terms-li">• Nothing is shown unless at least <b>5 organisations</b> contribute to it (the suppression rule).</div>
        <div class="terms-li">• Hosted in the UK/EU. Never sold, never shared for third-party use, never used to train external AI.</div>
        <div class="terms-li">• You can export your own data any time, and ask for it to be deleted.</div>
        <div class="row" style=${{ marginTop: "var(--s3)", gap: "var(--s3)" }}>
          <a href="#" onClick=${e => { e.preventDefault(); setFull(!full); }}>
            ${full ? "Hide the full terms" : "Read the full terms"}</a>
          <a href="/api/terms/dpa" download>Download the full Data Sharing Agreement (DPA)</a>
        </div>
        ${full && terms && html`
          <div style=${{ maxHeight: "320px", overflow: "auto", border: "1px solid var(--border)",
                         borderRadius: "var(--radius-sm)", padding: "var(--s3)", marginTop: "var(--s3)" }}>
            <${TermsText} text=${terms.data_contribution.text} />
          </div>`}
        <div class="caption" style=${{ marginTop: "var(--s3)" }}>
          <span class="chip">Current version · v${terms ? terms.data_contribution.version : "…"}</span>
        </div>
      </div>
      ${isAdmin ? html`
        <div class="card" style=${{ padding: "var(--s4)" }}>
          <label class="terms-tick">
            <input type="checkbox" checked=${tick} onChange=${e => setTick(e.target.checked)} />
            <span><b>I accept these Data Contribution Terms on behalf of my organisation.</b></span>
          </label>
          <div class="caption" style=${{ margin: "var(--s1) 0 var(--s3)" }}>Your acceptance is recorded (organisation,
            your name, date, terms version) and starts your organisation's 30 days to contribute.</div>
          ${err && html`<div class="error-text" role="alert" style=${{ marginBottom: "var(--s2)" }}>${err}</div>`}
          <button class="btn primary" disabled=${!tick || busy} onClick=${accept}>
            ${busy ? html`<${Spinner} />` : "Accept and begin"}</button>
        </div>` : html`
        <${EmptyState} icon="lock" title="Waiting on your Admin"
          body="Only your organisation's Admin can accept the Data Contribution Terms. Once they have, you can start submitting here — your 30 days to contribute start at that moment, so no time is being lost." />`}
    </div>`;
}

// Belt-and-braces with autosave: a counter of debounced-but-unsaved edits and
// in-flight saves. Only a genuine in-flight loss triggers the warning.
window._pendingSaves = 0;
window.addEventListener("beforeunload", (e) => {
  if (window._pendingSaves > 0) { e.preventDefault(); e.returnValue = ""; }
});

// ---------------------------------------------------- domain (your data) ----
// ONE page per section (Pay, Benefits, …) — the single place a member reviews
// AND enters their data. Default is a reviewable LIST: every question with its
// status and current value, click a row to edit it inline (autosaves). An
// opt-in GUIDED mode steps through one question at a time with Save & next.
// There is no separate "submit" surface — this is it.
function DomainPage({ sp, state, refresh, refreshMe }) {
  const [data, setData] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [issues, setIssues] = useState({});   // key -> {errors, warnings}
  const [savedAt, setSavedAt] = useState(null);
  const [loadErr, setLoadErr] = useState(null);
  const [mode, setMode] = useState(() => /[?&]mode=guided/.test(window.location.hash) ? "guided" : "list");
  const [filter, setFilter] = useState("all");   // all | answered | unanswered (list mode)
  const [openId, setOpenId] = useState(null);    // expanded row in list mode
  const [step, setStep] = useState(0);           // current question in guided mode
  const prevDoneRef = useRef(null);              // celebrate only on the transition to complete
  const focusedRef = useRef(false);              // honour ?focus=<qid> once per section load
  useEffect(() => {
    setData(null); setLoadErr(null); setIssues({}); setStep(0); setOpenId(null); focusedRef.current = false;
    api("/api/submission/section/" + encodeURIComponent(sp)).catch(e => { setLoadErr(e.message); throw e; }).then(d => {
      setData(d);
      const init = {};
      d.questions.forEach(q => {
        if (q.type === "matrix") {
          Object.entries(q.current || {}).forEach(([rid, v]) => { if (v != null) init[q.id + "|" + rid] = v; });
          if (q.current_na) init[q.id + "|"] = "Not applicable";
        } else if (q.current != null) init[q.id + "|"] = q.current;
      });
      setDrafts(init);
    });
  }, [sp]);
  // Delight: a little confetti + a nod the moment a whole section is finished
  // — but only on the transition, never on a section that loads already done.
  useEffect(() => {
    if (!data) { prevDoneRef.current = null; return; }
    const qs = data.questions;
    const isAns = (q) => q.type === "matrix"
      ? (q.matrix_rows || []).some(r => (drafts[q.id + "|" + r.row_id] || "") !== "") || (drafts[q.id + "|"] || "") === "Not applicable"
      : (drafts[q.id + "|"] || "") !== "";
    const total = qs.length, doneN = qs.filter(isAns).length;
    if (prevDoneRef.current != null && prevDoneRef.current < total && doneN === total && total > 0) {
      toast("Nice — " + sp + " is complete ✨");
      window.confettiBurst({ count: 100, duration: 2200, origin: { x: 0.5, y: 0.26 } });
    }
    prevDoneRef.current = doneN;
  }, [drafts, data]);
  // Deep-link from a card's "Add data": open that exact question, in list mode,
  // and scroll it into view with a brief highlight.
  useEffect(() => {
    if (!data || focusedRef.current) return;
    focusedRef.current = true;
    const m = window.location.hash.match(/[?&]focus=([^&#]+)/);
    const qid = m ? decodeURIComponent(m[1]) : null;
    if (!qid || !data.questions.some(q => q.id === qid)) return;
    setMode("list"); setFilter("all"); setOpenId(qid);
    setTimeout(() => {
      const el = document.getElementById("dq-" + qid);
      if (el) { scrollIntoViewSafe(el); el.classList.add("dq-flash"); setTimeout(() => el.classList.remove("dq-flash"), 1700); }
    }, 140);
  }, [data]);
  if (loadErr) return html`<${EmptyState} icon="info" title="Couldn't load this area"
    body=${loadErr + " — your saved answers are safe."}
    action=${html`<button class="btn small primary" onClick=${() => nav("/your-data")}>Back to Your data</button>`} />`;
  if (!data) return html`<${PageLoading} />`;

  const save = async (q, rowId, value) => {
    const key = q.id + "|" + (rowId || "");
    setDrafts(d => ({ ...d, [key]: value }));
    window._pendingSaves++;
    try {
      const r = await api("/api/submission/draft", { method: "PUT",
        body: { question_id: q.id, matrix_row_id: rowId || "", value } });
      setIssues(s => ({ ...s, [key]: { errors: r.errors || [], warnings: r.warnings || [] } }));
      if (r.ok) { setSavedAt(new Date()); window.markUnsubmitted(); }
    } catch (e) {
      setIssues(s => ({ ...s, [key]: { errors: [(e.message || "Couldn't save this answer") + " — your value is still here, just not saved yet."], warnings: [] } }));
      toast("Couldn't save your last answer", "error", { label: "Retry", fn: () => save(q, rowId, value) });
    } finally {
      window._pendingSaves = Math.max(0, window._pendingSaves - 1);
    }
  };
  // Soft-warning confirm: the value is ALREADY saved (warnings never gate
  // saving) — this records the override quietly for optional later review.
  const confirmValue = async (q, rowId) => {
    const key = q.id + "|" + (rowId || "");
    try {
      await api("/api/submission/confirm-value", { method: "POST",
        body: { question_id: q.id, matrix_row_id: rowId || "", value: drafts[key] } });
      setIssues(s => ({ ...s, [key]: { errors: [], warnings: [] } }));
      toast("Noted — your value is kept.");
    } catch (e) { toast(e.message || "Couldn't record the confirmation.", "error"); }
  };

  const answeredQ = (q) => {
    if (q.type === "matrix")
      return q.matrix_rows.some(r => (drafts[q.id + "|" + r.row_id] || "") !== "") ||
             (drafts[q.id + "|"] || "") !== "";
    return (drafts[q.id + "|"] || "") !== "";
  };
  // Collapsed-row value summary (mirrors the read-only DomainDataView display).
  const fmtV = (q, raw) => {
    if (raw == null || raw === "") return "";
    if (String(raw) === "Not applicable") return "Not applicable";
    if (q.type === "numeric" || q.type === "matrix") {
      const f = parseFloat(String(raw).replace(/[£,%\s]/g, ""));
      if (!isNaN(f)) return fmtValue(f, q.unit);
    }
    return String(raw);
  };
  const summarize = (q) => {
    if (q.type === "matrix") {
      if ((drafts[q.id + "|"] || "") === "Not applicable") return "Not applicable";
      return (q.matrix_rows || []).filter(r => (drafts[q.id + "|" + r.row_id] || "") !== "")
        .map(r => ({ row: r.label, val: fmtV(q, drafts[q.id + "|" + r.row_id]) }));
    }
    return fmtV(q, drafts[q.id + "|"]);
  };

  const keyQs = data.questions.filter(q => q.is_required);
  const optQs = data.questions.filter(q => !q.is_required);
  const ordered = keyQs.concat(optQs);            // key first, then optional
  const total = ordered.length;
  const done = ordered.filter(answeredQ).length;
  const pct = total ? Math.round(100 * done / total) : 0;
  const sections = state.sections.map(s => s.section);
  const idx = sections.indexOf(sp);

  // Flush any debounced/in-flight edit before we navigate or switch mode, so a
  // value is never left behind.
  const flush = async () => {
    const el = document.activeElement;
    if (el && el.blur) el.blur();
    await new Promise(r => setTimeout(r, 60));   // let the blur-commit fire its PUT
    let g = 0;
    while (window._pendingSaves > 0 && g < 80) { await new Promise(r => setTimeout(r, 50)); g++; }
  };
  const toGuided = async () => { await flush(); const gap = ordered.findIndex(q => !answeredQ(q)); setStep(gap >= 0 ? gap : 0); setMode("guided"); window.scrollTo(0, 0); };
  const toList = async () => { await flush(); setMode("list"); window.scrollTo(0, 0); };
  const goSection = async (to) => { await flush(); nav("/your-data/" + encodeURIComponent(to)); };

  const header = html`
    <div class="row spread" style=${{ marginBottom: "var(--s3)" }}>
      <a class="caption back-link" href="#/your-data"><${Icon} name="chevron-left" size=${13} /> Your data</a>
      <div class="caption">Section ${idx + 1} of ${sections.length}</div>
    </div>
    <div class="row spread" style=${{ alignItems: "center", marginBottom: "var(--s3)" }}>
      <div>
        <h1 class="display-title" style=${{ margin: "0 0 3px" }}>${sp}</h1>
        <div class=${"qwiz-saved" + (savedAt ? " on" : "")} role="status">
          ${savedAt ? "Saved " + savedAt.toLocaleTimeString("en-GB") : done + " of " + total + " answered · autosaves as you go"}</div>
      </div>
      <div style=${{ minWidth: "128px" }}>
        <div class="progressbar"><div style=${{ width: pct + "%" }}></div></div>
        <div class="caption" style=${{ textAlign: "right", marginTop: "var(--s1)" }}>${pct}% complete</div>
      </div>
    </div>`;

  // ----------------------------------------------------------- GUIDED mode --
  if (mode === "guided") {
    const at = Math.min(step, Math.max(0, total - 1));
    const cur = ordered[at];
    const goTo = async (i) => { await flush(); setStep(i); window.scrollTo(0, 0); };
    const next = async () => {
      await flush();
      if (at < total - 1) { setStep(at + 1); window.scrollTo(0, 0); }
      else if (idx < sections.length - 1) nav("/your-data/" + encodeURIComponent(sections[idx + 1]) + "?mode=guided");
      else nav("/your-data/review");
    };
    const prev = async () => {
      await flush();
      if (at > 0) { setStep(at - 1); window.scrollTo(0, 0); }
      else setMode("list");
    };
    const isLast = at >= total - 1;
    const curError = cur && Object.entries(issues).some(([k, v]) => k.indexOf(cur.id + "|") === 0 && (v.errors || []).length > 0);
    const curAnswered = cur && answeredQ(cur);
    const optionalStart = cur && !cur.is_required && at === keyQs.length;
    const nextLabel = isLast ? (idx < sections.length - 1 ? "Save & next section →" : "Save & review →") : "Save & next →";
    return html`
      <div class="yourdata" style=${{ maxWidth: "720px" }}>
        ${header}
        <div class="row spread dompage-modebar">
          <div class="caption">Step-by-step · question <b>${at + 1}</b> of ${total}</div>
          <button class="btn small" onClick=${toList}><${Icon} name="table" size=${13} /> List view</button>
        </div>
        <div class="qwiz-pips" role="tablist" aria-label="Questions in this section">
          ${ordered.map((q, i) => html`
            <button key=${q.id} role="tab" aria-selected=${i === at} title=${(i + 1) + ". " + q.text}
              class=${"qwiz-pip" + (answeredQ(q) ? " done" : "") + (i === at ? " now" : "") + (q.is_required ? " key" : "")}
              onClick=${() => goTo(i)}></button>`)}
        </div>
        ${optionalStart && html`
          <div class="qwiz-divider"><span>Optional from here</span> — these add depth to your benchmarks when you have the data to hand.</div>`}
        <div class="qwiz-card card">
          <${QuestionInput} key=${cur.id} q=${cur} drafts=${drafts}
            issues=${issues} save=${save} confirmValue=${confirmValue} />
        </div>
        <div class="qwiz-nav row spread">
          <button class="btn" onClick=${prev}>← ${at > 0 ? "Back" : "List view"}</button>
          <div class="row" style=${{ gap: "var(--s3)", alignItems: "center" }}>
            ${!curAnswered && !cur.is_required && html`
              <a class="qwiz-skip" href="#" onClick=${e => { e.preventDefault(); next(); }}>Skip for now</a>`}
            <button class="btn primary" disabled=${curError} onClick=${next}>${nextLabel}</button>
          </div>
        </div>
        ${curError && html`<div class="caption" style=${{ textAlign: "right", marginTop: "var(--s2)", color: "var(--unfavourable)" }}>
          Fix the value above to continue.</div>`}
      </div>`;
  }

  // ------------------------------------------------------------- LIST mode --
  const tabs = [{ k: "all", label: "All", n: total }, { k: "answered", label: "Answered", n: done },
    { k: "unanswered", label: "To answer", n: total - done }];
  // The open row stays in the list even once it stops matching the filter, so a
  // multi-entry answer (multi-select, or a matrix with several rows) doesn't
  // vanish mid-edit the instant its first value makes it "answered".
  const visible = ordered.filter(q => q.id === openId || filter === "all" || (filter === "answered") === answeredQ(q));
  return html`
    <div class="yourdata" style=${{ maxWidth: "780px" }}>
      ${header}
      <div class="row spread dompage-modebar">
        <div class="sig-tabs">
          ${tabs.map(t => html`<button key=${t.k} class=${"sig-tab" + (filter === t.k ? " on" : "")} onClick=${() => setFilter(t.k)}>
            ${t.label} <span class="num">${t.n}</span></button>`)}
        </div>
        <button class="btn small" onClick=${toGuided} title="Walk through this section one question at a time">
          <${Icon} name="sparkle" size=${13} /> Step me through it</button>
      </div>

      ${visible.length === 0 ? html`
        <div class="signals-empty" style=${{ marginTop: "var(--s5)" }}>
          <span class="signals-empty-ring"><${Icon} name=${filter === "unanswered" ? "award" : "table"} size=${18} /></span>
          <div class="caption">${filter === "unanswered" ? "Nothing left to answer in " + sp + " — fully complete." : "No questions here yet."}</div>
        </div>` :
      html`<div class="dq-list">
        ${visible.map(q => {
          const open = openId === q.id;
          const ans = answeredQ(q);
          const sum = summarize(q);
          const hasErr = Object.entries(issues).some(([k, v]) => k.indexOf(q.id + "|") === 0 && (v.errors || []).length > 0);
          return html`
            <div key=${q.id} id=${"dq-" + q.id} class=${"dq-row" + (ans ? "" : " unans") + (open ? " open" : "") + (hasErr ? " err" : "")}>
              <div class="dq-summary" role="button" tabindex="0" aria-expanded=${open}
                onClick=${() => setOpenId(open ? null : q.id)}
                onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpenId(open ? null : q.id); } }}>
                <div class="dq-sum-left">
                  <div class="data-q-title">${q.title || q.text}
                    ${q.is_required ? html`<span class="data-q-req" title="Counts toward the completion that keeps your access">required</span>` : ""}</div>
                  ${open ? null : (ans
                    ? (Array.isArray(sum)
                        ? html`<div class="data-q-rows">${sum.map((r, i) => html`<span key=${i}><span class="muted">${r.row}:</span> ${r.val}</span>`)}</div>`
                        : html`<div class="data-q-val">${sum || "—"}</div>`)
                    : html`<div class="data-q-none">Not answered yet — <span class="dq-add">add it</span></div>`)}
                </div>
                <div class="dq-sum-right">
                  <span class=${"data-q-flag " + (ans ? "ok" : "todo")}>
                    <${Icon} name=${ans ? "award" : "pencil"} size=${13} /> ${ans ? "Answered" : "To do"}</span>
                  <span class="dq-chev"><${Icon} name=${open ? "chevron-up" : "chevron-down"} size=${15} /></span>
                </div>
              </div>
              ${open && html`<div class="dq-editor">
                <${QuestionInput} q=${q} drafts=${drafts} issues=${issues} save=${save} confirmValue=${confirmValue} />
              </div>`}
            </div>`;
        })}
      </div>`}

      <div class="qwiz-nav row spread" style=${{ marginTop: "var(--s4)" }}>
        <button class="btn" disabled=${idx <= 0} onClick=${() => goSection(sections[idx - 1])}>← ${sections[idx - 1] || "Your data"}</button>
        <div class="row" style=${{ gap: "var(--s3)" }}>
          ${idx < sections.length - 1 && html`<button class="btn" onClick=${() => goSection(sections[idx + 1])}>${sections[idx + 1]} →</button>`}
          <button class="btn primary" onClick=${async () => { await flush(); nav("/your-data/review"); }}>Review & submit →</button>
        </div>
      </div>
    </div>`;
}

function QuestionInput({ q, drafts, issues, save, confirmValue }) {
  const key = q.id + "|";
  const iss = issues[key] || { errors: [], warnings: [] };
  const [showDef, setShowDef] = useState(false);
  const hasDef = q.definition && q.definition !== q.help_text;
  return html`
    <div class="q-block">
      <div class="row" style=${{ marginBottom: "var(--s1)", alignItems: "baseline", gap: "var(--s2)" }}>
        <div style=${{ fontWeight: 600, fontSize: "var(--fs-label)", flex: 1 }}>${q.text}
          ${q.is_required && html` <span class="chip key-chip" title="Counts toward unlocking your insights">key</span>`}</div>
      </div>
      ${q.help_text && html`<div class="caption" style=${{ marginBottom: "var(--s2)" }}>${q.help_text}
        ${hasDef && html` <a class="def-toggle" href="#" onClick=${e => { e.preventDefault(); setShowDef(!showDef); }}>${showDef ? "Hide definition" : "What counts?"}</a>`}</div>`}
      ${!q.help_text && hasDef && html`<div class="caption" style=${{ marginBottom: "var(--s2)" }}>
        <a class="def-toggle" href="#" onClick=${e => { e.preventDefault(); setShowDef(!showDef); }}>${showDef ? "Hide definition" : "What counts?"}</a></div>`}
      ${showDef && html`<div class="def-box">${q.definition}</div>`}
      <${InputForType} q=${q} drafts=${drafts} issues=${issues} save=${save} confirmValue=${confirmValue} />
      <${IssueNotes} iss=${iss} onConfirm=${() => confirmValue(q, "")} />
    </div>`;
}

/* Errors block (malformed input only); warnings allow — with one click to
   confirm a genuine outlier ("warn, never block"). */
function IssueNotes({ iss, onConfirm }) {
  return html`
    ${iss.errors.map((e, i) => html`<div key=${"e" + i} class="error-text" role="alert">${e}</div>`)}
    ${iss.warnings.length > 0 && html`
      <div class="warn-panel">
        ${iss.warnings.map((w, i) => html`<div key=${i} class="warn-text">⚠ ${w}</div>`)}
        <div class="row" style=${{ gap: "var(--s2)", marginTop: "var(--s2)", alignItems: "center" }}>
          <button class="btn small" onClick=${onConfirm}>Yes, it's right — keep it</button>
          <span class="caption">or correct the value above. Your answer is saved either way.</span>
        </div>
      </div>`}`;
}

/* "Not applicable" is a first-class answer — never faked with 0, never left
   blank. It counts as answered for the unlock gate and is excluded from
   market medians. */
function NAToggle({ checked, onChange }) {
  return html`
    <label class="na-toggle">
      <input type="checkbox" checked=${checked} onChange=${e => onChange(e.target.checked)} />
      <span>Not applicable to us</span>
    </label>`;
}

function InputForType({ q, drafts, issues, save, confirmValue }) {
  const key = q.id + "|";
  const val = drafts[key];
  if (q.type === "yes_no") {
    return html`<div class="seg-toggle" role="radiogroup" aria-label=${q.text}>
      ${q.options.map(o => html`
        <button key=${o.code} class=${"seg-btn" + (val === o.label ? " on" : "")}
          role="radio" aria-checked=${val === o.label}
          onClick=${() => save(q, "", o.label)}>${o.label}</button>`)}
    </div>`;
  }
  if (q.type === "single_select") {
    return html`<div>
      ${q.options.map(o => html`
        <label key=${o.code} class="radio-row">
          <input type="radio" name=${q.id} checked=${val === o.label} onChange=${() => save(q, "", o.label)} />
          <span>${o.label}</span>
        </label>`)}
    </div>`;
  }
  if (q.type === "multi_select") {
    const selected = new Set((val || "").split(";").map(s => s.trim()).filter(Boolean));
    const noneOpts = q.options.filter(o => o.label.toLowerCase().startsWith("none")).map(o => o.label);
    const toggle = (label) => {
      const next = new Set(selected);
      if (next.has(label)) next.delete(label);
      else {
        // "None" is exclusive — selecting it clears others; selecting others clears it
        if (noneOpts.includes(label)) next.clear();
        else noneOpts.forEach(n => next.delete(n));
        next.add(label);
      }
      save(q, "", Array.from(next).join("; "));
    };
    return html`<div>
      ${q.options.map(o => html`
        <label key=${o.code} class="check-row">
          <input type="checkbox" checked=${selected.has(o.label)} onChange=${() => toggle(o.label)} />
          <span>${o.label}</span>
        </label>`)}
    </div>`;
  }
  if (q.type === "numeric") {
    const isNA = val === "Not applicable";
    return html`<div class="row" style=${{ gap: "var(--s3)", alignItems: "center", flexWrap: "wrap" }}>
      <${DebouncedNumber} value=${isNA ? "" : val} unitName=${q.unit_display_name} unit=${q.unit}
        disabled=${isNA} onSave=${v => save(q, "", v)} />
      ${q.na_allowed && html`<${NAToggle} checked=${isNA}
        onChange=${on => save(q, "", on ? "Not applicable" : "")} />`}
    </div>`;
  }
  if (q.type === "matrix") {
    const cols = (q.matrix && q.matrix.columns) || [{ label: q.unit_display_name || "Value" }];
    const col0 = cols[0] || {};
    const isSelect = col0.type === "select" && (col0.options || []).length > 0;
    const isNA = drafts[key] === "Not applicable";
    const setNA = (on) => {
      save(q, "", on ? "Not applicable" : "");
      if (on) q.matrix_rows.forEach(r => { if ((drafts[q.id + "|" + r.row_id] || "") !== "") save(q, r.row_id, ""); });
    };
    return html`
      <div>
      <table class="data matrix-grid" style=${isNA ? { opacity: 0.45 } : null}>
        <thead><tr><th>Level</th>${cols.map((c, i) => html`<th key=${i} class="num">${c.label}${
          q.unit && q.unit.symbol && !isSelect && !(c.label || "").includes(q.unit.symbol)
            ? " (" + q.unit.symbol + ")" : ""}</th>`)}</tr></thead>
        <tbody>
          ${q.matrix_rows.map(r => {
            const rkey = q.id + "|" + r.row_id;
            const iss = issues[rkey] || { errors: [], warnings: [] };
            const flagged = iss.errors.length > 0 || iss.warnings.length > 0;
            // the soft-warning / error sits in its OWN full-width row directly
            // beneath, not crammed into the narrow value cell where it read as
            // an untethered floating box.
            return [
              html`
              <tr key=${r.row_id} class=${flagged ? "mg-row-flagged" : ""}>
                <td>${r.label}</td>
                <td class="num">
                  ${isSelect ? html`
                    <select class="band-select" disabled=${isNA} value=${drafts[rkey] || ""}
                      aria-label=${r.label + " — " + (col0.label || "value")}
                      onChange=${e => save(q, r.row_id, e.target.value)}>
                      <option value="">Choose…</option>
                      ${col0.options.map(o => html`<option key=${o} value=${o}>${o}</option>`)}
                    </select>` : html`
                    <${DebouncedNumber} value=${drafts[rkey]} compact=${true} unit=${q.unit}
                      disabled=${isNA} onSave=${v => save(q, r.row_id, v)} />`}
                </td>
              </tr>`,
              flagged ? html`
                <tr key=${r.row_id + "::note"} class="mg-note-row">
                  <td colspan=${cols.length + 1} class="mg-note-cell">
                    <${IssueNotes} iss=${iss} onConfirm=${() => confirmValue(q, r.row_id)} />
                  </td>
                </tr>` : null,
            ];
          })}
        </tbody>
      </table>
      ${q.na_allowed && html`<div style=${{ marginTop: "var(--s2)" }}><${NAToggle} checked=${isNA} onChange=${setNA} /></div>`}
      </div>`;
  }
  return null;
}

/* UK conventions in the input itself: a currency field shows £12,500 when
   idle and accepts "£12,500" / "12500" / "12 500" while typing; the canonical
   plain number is what's saved. Percentages stay human end-to-end: 8.5 means
   8.5% at entry, in storage, in the warn thresholds and in aggregation. The
   unit (£ prefix / % suffix) sits inside the field so nobody has to guess
   what the number means. */
function DebouncedNumber({ value, onSave, unitName, unit, compact, disabled }) {
  const isCurrency = unit && unit.type === "currency";
  const isNumber = unit && ["currency", "none"].includes(unit.type);
  const sym = (unit && unit.symbol) || "";
  const fmt = (raw) => (isCurrency || isNumber) ? formatUKNumber(raw, false) : (raw == null ? "" : raw);
  const [v, setV] = useState(fmt(value));
  const [editing, setEditing] = useState(false);
  const t = useRef(null);
  useEffect(() => { if (!editing) setV(fmt(value)); }, [value, editing]);
  const commit = (nv) => onSave(parseUKNumber(nv));
  const change = (nv) => {
    setV(nv);
    clearTimeout(t.current);
    t.current = setTimeout(() => commit(nv), 600);
  };
  return html`
    <span class="row" style=${{ gap: "var(--s2)", display: "inline-flex", alignItems: "center" }}>
      <span class=${"unit-input" + (compact ? " compact" : "") + (disabled ? " disabled" : "")}>
        ${sym === "£" && html`<span class="unit-sym">£</span>`}
        <input inputmode="decimal" value=${v} disabled=${disabled}
          aria-label=${unitName || "Value"}
          onFocus=${() => { setEditing(true); setV(parseUKNumber(v)); }}
          onInput=${e => change(e.target.value)}
          onBlur=${() => { clearTimeout(t.current); commit(v); setEditing(false); setV(fmt(parseUKNumber(v))); }} />
        ${sym && sym !== "£" && html`<span class="unit-sym">${sym}</span>`}
      </span>
      ${unitName && !compact && unitName !== sym && html`<span class="caption">${unitName}</span>`}
    </span>`;
}

// ----------------------------------------------------------------- review --
function ReviewStep({ state, refresh, refreshMe }) {
  const [val, setVal] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);
  const [err, setErr] = useState(null);
  const runValidate = () => { setVal(null);
    api("/api/submission/validate", { method: "POST", body: {} }).then(setVal).catch(() => setVal({ _error: true })); };
  useEffect(() => { runValidate(); }, []);
  // The payoff: confetti when a submission lands — a full three-cannon volley
  // the moment insights unlock, a gentler single burst otherwise.
  useEffect(() => {
    if (!done) return;
    if (done.benchmark_unlocked) {
      window.confettiBurst({ count: 200, duration: 3400, origin: { x: 0.5, y: 0.3 } });
      setTimeout(() => window.confettiBurst({ count: 110, duration: 2800, spread: 0.9, origin: { x: 0.18, y: 0.45 } }), 220);
      setTimeout(() => window.confettiBurst({ count: 110, duration: 2800, spread: 0.9, origin: { x: 0.82, y: 0.45 } }), 420);
    } else {
      window.confettiBurst({ count: 120, duration: 2400, origin: { x: 0.5, y: 0.32 } });
    }
  }, [done]);
  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api("/api/submission/submit", { method: "POST", body: {} });
      window.clearUnsubmitted();   // drafts committed and cleared server-side
      setDone(r); refreshMe();
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  if (done) return html`
    <div class=${"success-pop" + (done.benchmark_unlocked ? " unlocked" : "")} style=${{ maxWidth: "560px", margin: "0 auto", textAlign: "center", paddingTop: "var(--s8)" }}>
      <div class="success-ring">${done.benchmark_unlocked ? html`<${Icon} name="sparkle" size=${34} />` : "✓"}</div>
      ${done.benchmark_unlocked ? html`
        <h1 class="display-title">Your insights are unlocked</h1>
        <p>${done.answers_saved} answers saved — and you've reached <b>${done.completion_pct}%</b> of your key reward
        questions. The £ opportunity, your board pack and your biggest gaps to the market are now live with your real position.
        Thank you for contributing to the pool — that's what makes the benchmark work.</p>
        <button class="btn primary" onClick=${() => nav("/overview")}>See where you stand</button>` : html`
        <h1 class="display-title">Submission received</h1>
        <p>${done.answers_saved} answers saved and the benchmark has been refreshed — peer group sizes already include you.
        Key questions answered: <b>${done.completion_pct}%</b>.</p>
        <p class="caption">Reach ${state.threshold_pct}% of your key reward questions to unlock your insights —
        the £ opportunity, board pack and biggest gaps. “Not applicable” counts as an answer.</p>`}
    </div>`;
  if (val && val._error) return html`<${EmptyState} title="Couldn't check your submission"
    body="Nothing is lost — your answers are saved. Try again in a moment."
    action=${html`<button class="btn small primary" onClick=${runValidate}>Try again</button>`} />`;
  if (!val) return html`<${PageLoading} />`;
  return html`
    <div style=${{ maxWidth: "680px" }}>
      <button class="btn quiet" onClick=${() => nav("/your-data")}>← Your data</button>
      <h1 class="display-title" style=${{ margin: "var(--s2) 0 var(--s3)" }}>Review and submit</h1>
      <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s3)" }}>
        <div class="row spread" style=${{ alignItems: "baseline", marginBottom: "var(--s2)" }}>
          <b>${val.pending_changes > 0
            ? `${val.pending_changes} ${val.pending_changes === 1 ? "change" : "changes"} ready to submit`
            : "No new changes to submit"}</b>
          <span class="num caption"><b>${state.basis_answered}</b> of ${state.basis_total} key questions</span>
        </div>
        <div class="progressbar"><div style=${{ width: Math.min(100, state.threshold_pct ? 100 * state.completion_pct / state.threshold_pct : 0) + "%" }}></div></div>
        <div class="caption" style=${{ marginTop: "var(--s2)" }}>
          ${state.completion_pct >= state.threshold_pct
            ? html`<span style=${{ color: "var(--favourable)", fontWeight: 600 }}>✓ Past the ${state.threshold_pct}% unlock threshold</span> — submitting keeps your insights live with your latest data.`
            : html`${state.completion_pct}% of your key questions answered · insights unlock at <b>${state.threshold_pct}%</b>`}
        </div>
      </div>
      ${val.problems.length > 0 && html`
        <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s3)", borderColor: "var(--unfavourable)" }}>
          <b style=${{ color: "var(--unfavourable)" }}>Fix these before submitting</b>
          ${val.problems.map((p, i) => html`
            <div key=${i} style=${{ marginTop: "var(--s2)" }}>${p.title}${p.matrix_row_id ? " — " + p.matrix_row_id.replace(/_/g, " ") : ""}: ${p.errors.join("; ")}</div>`)}
        </div>`}
      ${val.unanswered_required.length > 0 && html`
        <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s3)" }}>
          <b>Unanswered key questions (${val.unanswered_required.length})</b>
          <div class="caption" style=${{ margin: "2px 0 var(--s1)" }}>“Not applicable” counts as an answer — use it where a question doesn't apply.</div>
          ${val.unanswered_required.slice(0, 12).map((u, i) => html`
            <div key=${i} class="caption" style=${{ marginTop: "var(--s1)" }}>
              <a href=${"#/your-data/" + encodeURIComponent(u.section || u.superpower)}>${u.section || u.superpower}</a> — ${u.title}</div>`)}
          ${val.unanswered_required.length > 12 && html`<div class="caption">…and ${val.unanswered_required.length - 12} more.</div>`}
        </div>`}
      <div class="card" style=${{ padding: "var(--s5)" }}>
        <p>Submitting saves a timestamped version of your answers into the current collection window and refreshes the
        live benchmark. Nothing is ever overwritten — future windows will show your movement.</p>
        ${err && html`<div class="error-text" role="alert" style=${{ marginBottom: "var(--s2)" }}>${err}</div>`}
        <button class="btn primary" disabled=${busy || val.problems.length > 0 || !(val.pending_changes > 0)} onClick=${submit}>
          ${busy ? html`<${Spinner} /> Submitting…` : val.pending_changes > 0 ? "Submit my data" : "Nothing new to submit"}</button>
        <div class="caption" style=${{ marginTop: "var(--s3)" }}>
          Your data is shared only as protected peer aggregates, never your raw answers or identity. See the
          ${" "}<a href="#/how-lumi-works/legal">Privacy Notice and data-sharing terms</a>
          ${" "}and <a href="#/how-lumi-works/co-op">how the co-op works</a>.</div>
      </div>
    </div>`;
}
