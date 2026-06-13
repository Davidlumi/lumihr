/* Questionnaire engine — rendered entirely from library metadata.
   Entry guardrails (2026-06-12): soft warnings never block — a member can
   always save their real value; the only refusals are malformed input.
   N/A is first-class (never faked with 0 or blank); units show inline. */
/* global html, useState, useEffect, useRef, api, Chip, Spinner, EmptyState, nav, SP_ICONS, SUPERPOWERS, toast */

window.SubmissionPage = function ({ me, refreshMe, section }) {
  const [state, setState] = useState(null);
  const [err, setErr] = useState(null);
  const refresh = () => api("/api/submission/state").then(setState).catch(e => setErr(e.message));
  useEffect(() => { refresh(); }, []);
  if (err) return html`<${EmptyState} icon="lock" title="Submitting data is a Contributor task"
    body=${err} />`;
  if (!state) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
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
  if (section) return html`<${SectionForm} sp=${section} state=${state} refresh=${refresh} />`;
  return html`<${SubmissionHome} state=${state} />`;
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
          <a onClick=${e => { e.preventDefault(); setFull(!full); }} style=${{ cursor: "pointer" }}>
            ${full ? "Hide the full terms" : "Read the full terms"}</a>
          <a href="/api/terms/dpa" download>Download the full Data Sharing Agreement (DPA)</a>
        </div>
        ${full && terms && html`
          <div style=${{ maxHeight: "320px", overflow: "auto", border: "1px solid var(--border)",
                         borderRadius: "var(--radius-sm)", padding: "var(--s3)", marginTop: "var(--s3)" }}>
            <${TermsText} text=${terms.data_contribution.text} />
          </div>`}
        <div class="caption" style=${{ marginTop: "var(--s3)" }}>
          <span class="chip warn">DRAFT — pending legal review · v${terms ? terms.data_contribution.version : "…"}</span>
        </div>
      </div>
      ${isAdmin ? html`
        <div class="card" style=${{ padding: "var(--s4)" }}>
          <label class="terms-tick">
            <input type="checkbox" checked=${tick} onChange=${e => setTick(e.target.checked)} />
            <span><b>I accept these Data Contribution Terms on behalf of my organisation.</b></span>
          </label>
          <div class="caption" style=${{ margin: "4px 0 10px" }}>Your acceptance is recorded (organisation,
            your name, date, terms version) and starts your organisation's 30 days to contribute.</div>
          ${err && html`<div class="error-text" style=${{ marginBottom: "8px" }}>${err}</div>`}
          <button class="btn primary" disabled=${!tick || busy} onClick=${accept}>
            ${busy ? html`<${Spinner} />` : "Accept and begin"}</button>
        </div>` : html`
        <${EmptyState} icon="lock" title="Waiting on your Admin"
          body="Only your organisation's Admin can accept the Data Contribution Terms. Once they have, you can start submitting here — your 30 days to contribute start at that moment, so no time is being lost." />`}
    </div>`;
}

// ------------------------------------------------------------------- home --
// One card per section (sub-power): Pay, Benefits, Incentives, Transparency,
// Progression — each with its own progress. Key (required) questions drive
// the unlock gate, so their count is shown separately.
function SubmissionHome({ state }) {
  const totalQ = state.sections.reduce((a, s) => a + s.questions, 0);
  const totalA = state.sections.reduce((a, s) => a + s.answered, 0);
  return html`
    <div style=${{ maxWidth: "760px" }}>
      <h1 class="display-title">Your submission</h1>
      <p>lumi is a co-operative: you see the pool because you've contributed to it. Answer your
      ${" "}<b>key reward questions</b> to unlock your insights — “Not applicable” counts as an answer,
      so nothing that doesn't apply to you can hold you back. Everything autosaves — come back any time.</p>
      <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s4)" }}>
        <div class="row spread" style=${{ marginBottom: "6px" }}>
          <b>Key reward questions</b>
          <span class="num"><b>${state.basis_answered}</b> of ${state.basis_total} answered · insights unlock at ${state.threshold_pct}%</span>
        </div>
        <div class="progressbar"><div style=${{ width: Math.min(100, state.completion_pct / state.threshold_pct * 100) + "%" }}></div></div>
        <div class="caption" style=${{ marginTop: "6px" }}>${totalA} of ${totalQ} questions answered overall</div>
      </div>
      ${state.sections.map(s => html`
        <div key=${s.section} class="card section-card" style=${{ padding: "var(--s3) var(--s4)", marginBottom: "var(--s2)", cursor: "pointer" }}
          onClick=${() => nav("/your-data/submit/" + encodeURIComponent(s.section))}>
          <div class="row spread">
            <b>${s.section}</b>
            <span class="caption num">${s.answered} of ${s.questions} done${s.key_questions ?
              html` · <b>${s.key_answered}/${s.key_questions}</b> key` : ""}</span>
          </div>
          <div class="progressbar" style=${{ marginTop: "6px" }}>
            <div style=${{ width: (s.questions ? 100 * s.answered / s.questions : 0) + "%" }}></div>
          </div>
        </div>`)}
      <div class="row" style=${{ justifyContent: "flex-end", marginTop: "var(--s4)" }}>
        <button class="btn primary" onClick=${() => nav("/your-data/submit/review")}>Review and submit</button>
      </div>
    </div>`;
}

// Belt-and-braces with autosave: a counter of debounced-but-unsaved edits and
// in-flight saves. Only a genuine in-flight loss triggers the warning.
window._pendingSaves = 0;
window.addEventListener("beforeunload", (e) => {
  if (window._pendingSaves > 0) { e.preventDefault(); e.returnValue = ""; }
});

// ------------------------------------------------------------ section form -
// One sub-power per page. Key questions first (they unlock insights), the
// optional ones after, under their own divider.
function SectionForm({ sp, state, refresh }) {
  const [data, setData] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [issues, setIssues] = useState({});   // key -> {errors, warnings}
  const [savedAt, setSavedAt] = useState(null);
  const [loadErr, setLoadErr] = useState(null);
  useEffect(() => {
    setData(null); setLoadErr(null); setIssues({});
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
  if (loadErr) return html`<${EmptyState} icon="info" title="Couldn't load this section"
    body=${loadErr + " — your saved answers are safe."}
    action=${html`<button class="btn small primary" onClick=${() => nav("/your-data/submit")}>Back to all sections</button>`} />`;
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;

  const save = async (q, rowId, value) => {
    const key = q.id + "|" + (rowId || "");
    setDrafts(d => ({ ...d, [key]: value }));
    window._pendingSaves++;
    try {
      const r = await api("/api/submission/draft", { method: "PUT",
        body: { question_id: q.id, matrix_row_id: rowId || "", value } });
      setIssues(s => ({ ...s, [key]: { errors: r.errors || [], warnings: r.warnings || [] } }));
      if (r.ok) setSavedAt(new Date());
    } catch (e) {
      setIssues(s => ({ ...s, [key]: { errors: [(e.message || "Couldn't save this answer") + " — check your connection and change the value again to retry."], warnings: [] } }));
      toast("Couldn't save your last answer — it will need re-entering.", "error");
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
  const keyQs = data.questions.filter(q => q.is_required);
  const optQs = data.questions.filter(q => !q.is_required);
  const done = data.questions.filter(answeredQ).length;
  const keyDone = keyQs.filter(answeredQ).length;
  const sections = state.sections.map(s => s.section);
  const idx = sections.indexOf(sp);
  const block = (qs) => qs.map(q => html`<${QuestionInput} key=${q.id} q=${q} drafts=${drafts}
      issues=${issues} save=${save} confirmValue=${confirmValue} />`);
  return html`
    <div style=${{ maxWidth: "780px" }}>
      <div class="row spread" style=${{ marginBottom: "var(--s3)" }}>
        <div>
          <button class="btn quiet" onClick=${() => nav("/your-data/submit")}>← All sections</button>
          <h1 class="display-title" style=${{ marginTop: "6px" }}>${sp}</h1>
        </div>
        <div style=${{ textAlign: "right" }}>
          <div class="num" style=${{ fontWeight: 600 }}>${done} of ${data.questions.length} done</div>
          <div class="caption">${savedAt ? "All changes autosaved · " + savedAt.toLocaleTimeString("en-GB") : "Changes autosave as you type"}</div>
        </div>
      </div>
      <div class="progressbar" style=${{ marginBottom: "var(--s4)" }}>
        <div style=${{ width: (data.questions.length ? 100 * done / data.questions.length : 0) + "%" }}></div>
      </div>
      ${keyQs.length > 0 && html`
        <div class="card" style=${{ marginBottom: "var(--s4)" }}>
          <div class="qsec-head">
            <b>Key questions</b> <span class="caption">· ${keyDone}/${keyQs.length} answered — these unlock your insights</span>
          </div>
          ${block(keyQs)}
        </div>`}
      ${optQs.length > 0 && html`
        <div class="card" style=${{ marginBottom: "var(--s4)" }}>
          <div class="qsec-head">
            <b>Optional</b> <span class="caption">· ${optQs.length} questions — add depth to your benchmarks when you have the data to hand</span>
          </div>
          ${block(optQs)}
        </div>`}
      <div class="row spread" style=${{ marginBottom: "var(--s6)" }}>
        <button class="btn" disabled=${idx <= 0} onClick=${() => nav("/your-data/submit/" + encodeURIComponent(sections[idx - 1]))}>← ${sections[idx - 1] || ""}</button>
        ${idx < sections.length - 1 ?
          html`<button class="btn primary" onClick=${() => nav("/your-data/submit/" + encodeURIComponent(sections[idx + 1]))}>${sections[idx + 1]} →</button>` :
          html`<button class="btn primary" onClick=${() => nav("/your-data/submit/review")}>Review and submit →</button>`}
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
      <div class="row" style=${{ marginBottom: "4px", alignItems: "baseline", gap: "8px" }}>
        <div style=${{ fontWeight: 600, fontSize: "13.5px", flex: 1 }}>${q.text}
          ${q.is_required && html` <span class="chip key-chip" title="Counts toward unlocking your insights">key</span>`}</div>
      </div>
      ${q.help_text && html`<div class="caption" style=${{ marginBottom: "6px" }}>${q.help_text}
        ${hasDef && html` <a class="def-toggle" onClick=${e => { e.preventDefault(); setShowDef(!showDef); }}>${showDef ? "Hide definition" : "What counts?"}</a>`}</div>`}
      ${!q.help_text && hasDef && html`<div class="caption" style=${{ marginBottom: "6px" }}>
        <a class="def-toggle" onClick=${e => { e.preventDefault(); setShowDef(!showDef); }}>${showDef ? "Hide definition" : "What counts?"}</a></div>`}
      ${showDef && html`<div class="def-box">${q.definition}</div>`}
      <${InputForType} q=${q} drafts=${drafts} issues=${issues} save=${save} confirmValue=${confirmValue} />
      <${IssueNotes} iss=${iss} onConfirm=${() => confirmValue(q, "")} />
    </div>`;
}

/* Errors block (malformed input only); warnings allow — with one click to
   confirm a genuine outlier ("warn, never block"). */
function IssueNotes({ iss, onConfirm }) {
  return html`
    ${iss.errors.map((e, i) => html`<div key=${"e" + i} class="error-text">${e}</div>`)}
    ${iss.warnings.length > 0 && html`
      <div class="warn-panel">
        ${iss.warnings.map((w, i) => html`<div key=${i} class="warn-text">⚠ ${w}</div>`)}
        <div class="row" style=${{ gap: "8px", marginTop: "6px", alignItems: "center" }}>
          <button class="btn small" onClick=${onConfirm}>Yes, it's right — keep it</button>
          <span class="caption">or correct the value above. Your answer is saved either way.</span>
        </div>
      </div>`}`;
}

/* "Not applicable" is a first-class answer — never faked with 0, never left
   blank. It counts as answered for the unlock gate and is excluded from
   peer medians. */
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
    return html`<div class="row" style=${{ gap: "14px", alignItems: "center", flexWrap: "wrap" }}>
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
      ${q.na_allowed && html`<div style=${{ marginTop: "6px" }}><${NAToggle} checked=${isNA} onChange=${setNA} /></div>`}
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
    <span class="row" style=${{ gap: "6px", display: "inline-flex", alignItems: "center" }}>
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
  useEffect(() => { api("/api/submission/validate", { method: "POST", body: {} }).then(setVal); }, []);
  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api("/api/submission/submit", { method: "POST", body: {} });
      setDone(r); refreshMe();
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  if (done) return html`
    <div class="success-pop" style=${{ maxWidth: "560px", margin: "0 auto", textAlign: "center", paddingTop: "60px" }}>
      <div class="success-ring">✓</div>
      ${done.benchmark_unlocked ? html`
        <h1 class="display-title">Your insights are unlocked</h1>
        <p>${done.answers_saved} answers saved — and you've reached <b>${done.completion_pct}%</b> of your key reward
        questions. The £ opportunity, your board pack and your biggest gaps to peers are now live with your real position.
        Thank you for contributing to the pool — that's what makes the benchmark work.</p>
        <button class="btn primary" onClick=${() => nav("/overview")}>See where you stand</button>` : html`
        <h1 class="display-title">Submission received</h1>
        <p>${done.answers_saved} answers saved and the benchmark has been refreshed — peer group sizes already include you.
        Key questions answered: <b>${done.completion_pct}%</b>.</p>
        <p class="caption">Reach ${state.threshold_pct}% of your key reward questions to unlock your insights —
        the £ opportunity, board pack and biggest gaps. “Not applicable” counts as an answer.</p>`}
    </div>`;
  if (!val) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  return html`
    <div style=${{ maxWidth: "680px" }}>
      <button class="btn quiet" onClick=${() => nav("/your-data/submit")}>← All sections</button>
      <h1 class="display-title" style=${{ margin: "6px 0 12px" }}>Review and submit</h1>
      ${val.problems.length > 0 && html`
        <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s3)", borderColor: "var(--unfavourable)" }}>
          <b style=${{ color: "var(--unfavourable)" }}>Fix these before submitting</b>
          ${val.problems.map((p, i) => html`
            <div key=${i} style=${{ marginTop: "6px" }}>${p.title}${p.matrix_row_id ? " — " + p.matrix_row_id.replace(/_/g, " ") : ""}: ${p.errors.join("; ")}</div>`)}
        </div>`}
      ${val.unanswered_required.length > 0 && html`
        <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s3)" }}>
          <b>Unanswered key questions (${val.unanswered_required.length})</b>
          <div class="caption" style=${{ margin: "2px 0 4px" }}>“Not applicable” counts as an answer — use it where a question doesn't apply.</div>
          ${val.unanswered_required.slice(0, 12).map((u, i) => html`
            <div key=${i} class="caption" style=${{ marginTop: "4px" }}>
              <a href=${"#/your-data/submit/" + encodeURIComponent(u.section || u.superpower)}>${u.section || u.superpower}</a> — ${u.title}</div>`)}
          ${val.unanswered_required.length > 12 && html`<div class="caption">…and ${val.unanswered_required.length - 12} more.</div>`}
        </div>`}
      <div class="card" style=${{ padding: "var(--s5)" }}>
        <p>Submitting saves a timestamped version of your answers into the current collection window and refreshes the
        live benchmark. Nothing is ever overwritten — future windows will show your movement.</p>
        ${err && html`<div class="error-text" style=${{ marginBottom: "8px" }}>${err}</div>`}
        <button class="btn primary" disabled=${busy || val.problems.length > 0} onClick=${submit}>
          ${busy ? html`<${Spinner} /> Submitting…` : "Submit my data"}</button>
        <div class="caption" style=${{ marginTop: "var(--s3)" }}>
          Your data is shared only as protected peer aggregates, never your raw answers or identity. See the
          ${" "}<a href="#/how-lumi-works/legal">Privacy Notice and data-sharing terms</a>
          ${" "}and <a href="#/how-lumi-works/co-op">how the co-op works</a>.</div>
      </div>
    </div>`;
}
