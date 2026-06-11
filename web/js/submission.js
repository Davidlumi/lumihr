/* Questionnaire engine — rendered entirely from library metadata. */
/* global html, useState, useEffect, useRef, api, Chip, Spinner, EmptyState, nav, SP_ICONS, SUPERPOWERS */

window.SubmissionPage = function ({ me, refreshMe, section }) {
  const [state, setState] = useState(null);
  const refresh = () => api("/api/submission/state").then(setState);
  useEffect(() => { refresh(); }, []);
  if (!state) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  if (!state.is_admin) return html`<${EmptyState} icon="lock" title="Submission is an admin task"
    body="Only admins can enter or edit your organisation's data. Ask your lumi admin for access." />`;
  if (!state.firmographics_done) return html`<${FirmographicsStep} state=${state} onDone=${() => { refresh(); refreshMe(); }} />`;
  if (section === "review") return html`<${ReviewStep} state=${state} refresh=${refresh} refreshMe=${refreshMe} />`;
  if (section) return html`<${SectionForm} sp=${section} state=${state} refresh=${refresh} />`;
  return html`<${SubmissionHome} state=${state} />`;
};

function SubmissionHome({ state }) {
  const totalQ = state.sections.reduce((a, s) => a + s.questions, 0);
  const totalA = state.sections.reduce((a, s) => a + s.answered, 0);
  return html`
    <div style=${{ maxWidth: "760px" }}>
      <h1 class="display-title">Your submission</h1>
      <p>lumi is a co-operative: you see the pool because you've contributed to it. Answer at
      least${" "}<b>${state.threshold_pct}% of Core questions</b> to unlock peer comparison. Everything autosaves — come back any time.</p>
      <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s4)" }}>
        <div class="row spread" style=${{ marginBottom: "6px" }}>
          <b>Core completion</b>
          <span class="num"><b>${state.core_completion_pct}%</b> of ${state.threshold_pct}% needed</span>
        </div>
        <div class="progressbar"><div style=${{ width: Math.min(100, state.core_completion_pct / state.threshold_pct * 100) + "%" }}></div></div>
        <div class="caption" style=${{ marginTop: "6px" }}>${totalA} of ${totalQ} questions answered overall</div>
      </div>
      ${state.sections.map(s => html`
        <div key=${s.superpower} class="card" style=${{ padding: "var(--s3) var(--s4)", marginBottom: "var(--s2)", cursor: "pointer" }}
          onClick=${() => nav("/submission/" + s.superpower)}>
          <div class="row spread">
            <b style=${{ display: "inline-flex", alignItems: "center", gap: "8px" }}><${SpIcon} sp=${s.superpower} /> ${s.superpower}</b>
            <span class="caption num">${s.answered}/${s.questions} answered · ${s.core_answered}/${s.core_questions} core</span>
          </div>
          <div class="progressbar" style=${{ marginTop: "6px" }}>
            <div style=${{ width: (s.questions ? 100 * s.answered / s.questions : 0) + "%" }}></div>
          </div>
        </div>`)}
      <div class="row" style=${{ justifyContent: "flex-end", marginTop: "var(--s4)" }}>
        <button class="btn primary" onClick=${() => nav("/submission/review")}>Review and submit</button>
      </div>
    </div>`;
}

function FirmographicsStep({ state, onDone }) {
  const [f, setF] = useState(state.firmographics);
  const [err, setErr] = useState(null);
  const c = state.choices;
  const save = async () => {
    setErr(null);
    if (!f.industry || !f.fte_band || !f.hq_region || !f.ownership_type) {
      setErr("Industry, FTE band, region and ownership are needed before benchmarking can unlock."); return;
    }
    try { await api("/api/submission/firmographics", { method: "PUT", body: f }); onDone(); }
    catch (e) { setErr(e.message); }
  };
  const Sel = ({ k, label, opts, free }) => html`
    <div class="field">
      <label>${label}</label>
      ${free ? html`<input value=${f[k] || ""} onInput=${e => setF({ ...f, [k]: e.target.value })} placeholder="e.g. Grocery & Convenience"/>` :
      html`<select value=${f[k] || ""} onChange=${e => setF({ ...f, [k]: e.target.value })}>
        <option value="">Choose…</option>
        ${opts.map(o => html`<option key=${o} value=${o}>${o}</option>`)}
      </select>`}
    </div>`;
  return html`
    <div style=${{ maxWidth: "560px" }}>
      <h1 class="display-title">About your organisation</h1>
      <p>This is how lumi builds your peer groups — it takes a minute and only needs doing once.</p>
      <div class="card" style=${{ padding: "var(--s5)" }}>
        <${Sel} k="industry" label="Industry" opts=${c.industries} />
        <${Sel} k="subsector" label="Subsector (optional)" free=${true} />
        <${Sel} k="fte_band" label="Size (full-time equivalent employees)" opts=${c.fte_bands} />
        <${Sel} k="hq_region" label="HQ region" opts=${c.regions} />
        <${Sel} k="ownership_type" label="Ownership" opts=${c.ownership_types} />
        ${err && html`<div class="error-text" style=${{ marginBottom: "10px" }}>${err}</div>`}
        <button class="btn primary" onClick=${save}>Save and start the questionnaire</button>
      </div>
    </div>`;
}

// ------------------------------------------------------------ section form -
function SectionForm({ sp, state, refresh }) {
  const [data, setData] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [issues, setIssues] = useState({});   // key -> {errors, warnings}
  const [savedAt, setSavedAt] = useState(null);
  useEffect(() => {
    setData(null);
    api("/api/submission/section/" + encodeURIComponent(sp)).then(d => {
      setData(d);
      const init = {};
      d.questions.forEach(q => {
        if (q.type === "matrix") Object.entries(q.current || {}).forEach(([rid, v]) => { if (v != null) init[q.id + "|" + rid] = v; });
        else if (q.current != null) init[q.id + "|"] = q.current;
      });
      setDrafts(init);
    });
  }, [sp]);
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;

  const save = async (q, rowId, value) => {
    const key = q.id + "|" + (rowId || "");
    setDrafts(d => ({ ...d, [key]: value }));
    try {
      const r = await api("/api/submission/draft", { method: "PUT",
        body: { question_id: q.id, matrix_row_id: rowId || "", value } });
      setIssues(s => ({ ...s, [key]: { errors: r.errors || [], warnings: r.warnings || [] } }));
      if (r.ok) setSavedAt(new Date());
    } catch (e) {
      setIssues(s => ({ ...s, [key]: { errors: [e.message], warnings: [] } }));
    }
  };

  const bySub = [];
  for (const q of data.questions) {
    let g = bySub.find(g => g.sub === (q.subpower || "General"));
    if (!g) { g = { sub: q.subpower || "General", order: q.sub_power_order || 999, qs: [] }; bySub.push(g); }
    g.qs.push(q);
  }
  bySub.sort((a, b) => a.order - b.order);
  const ACTIVE = (window.SCOPE && window.SCOPE.superpowers) || SUPERPOWERS;
  const idx = ACTIVE.indexOf(sp);
  return html`
    <div style=${{ maxWidth: "780px" }}>
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <button class="btn quiet" onClick=${() => nav("/submission")}>← All sections</button>
          <h1 class="display-title" style=${{ marginTop: "6px", display: "flex", alignItems: "center", gap: "10px" }}><${SpIcon} sp=${sp} size=${20} /> ${sp}</h1>
        </div>
        <div class="caption">${savedAt ? "All changes autosaved · " + savedAt.toLocaleTimeString("en-GB") : "Changes autosave as you type"}</div>
      </div>
      ${bySub.map(g => html`
        <div key=${g.sub} class="card" style=${{ marginBottom: "var(--s4)" }}>
          <div style=${{ padding: "var(--s3) var(--s4)", borderBottom: "1px solid var(--border)", background: "var(--surface-sunk)", borderRadius: "var(--radius) var(--radius) 0 0" }}>
            <b>${g.sub}</b> <span class="caption">· ${g.qs.length} questions</span>
          </div>
          ${g.qs.map(q => html`<${QuestionInput} key=${q.id} q=${q} drafts=${drafts} issues=${issues} save=${save} />`)}
        </div>`)}
      <div class="row spread" style=${{ marginBottom: "var(--s6)" }}>
        <button class="btn" disabled=${idx <= 0} onClick=${() => nav("/submission/" + ACTIVE[idx - 1])}>← ${ACTIVE[idx - 1] || ""}</button>
        ${idx < ACTIVE.length - 1 ?
          html`<button class="btn primary" onClick=${() => nav("/submission/" + ACTIVE[idx + 1])}>${ACTIVE[idx + 1]} →</button>` :
          html`<button class="btn primary" onClick=${() => nav("/submission/review")}>Review and submit →</button>`}
      </div>
    </div>`;
}

function QuestionInput({ q, drafts, issues, save }) {
  const key = q.id + "|";
  const iss = issues[key] || { errors: [], warnings: [] };
  return html`
    <div class="q-block">
      <div class="row spread" style=${{ marginBottom: "4px", alignItems: "flex-start" }}>
        <div style=${{ fontWeight: 600, fontSize: "13.5px", flex: 1 }}>${q.text}
          ${q.is_required && html`<span style=${{ color: "var(--unfavourable)" }}> *</span>`}</div>
        <${Chip}>${q.tier}<//>
      </div>
      ${q.help_text && html`<div class="caption" style=${{ marginBottom: "8px" }}>${q.help_text}</div>`}
      <${InputForType} q=${q} drafts=${drafts} issues=${issues} save=${save} />
      ${iss.errors.map((e, i) => html`<div key=${i} class="error-text">${e}</div>`)}
      ${iss.warnings.map((w, i) => html`<div key=${i} class="warn-text">⚠ ${w}</div>`)}
    </div>`;
}

function InputForType({ q, drafts, issues, save }) {
  const key = q.id + "|";
  const val = drafts[key];
  if (q.type === "single_select" || q.type === "yes_no") {
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
    return html`<${DebouncedNumber} value=${val} unitName=${q.unit_display_name} onSave=${v => save(q, "", v)} />`;
  }
  if (q.type === "matrix") {
    const cols = (q.matrix && q.matrix.columns) || [{ label: q.unit_display_name || "Value" }];
    return html`
      <table class="data matrix-grid">
        <thead><tr><th>Level</th>${cols.map((c, i) => html`<th key=${i} class="num">${c.label}</th>`)}</tr></thead>
        <tbody>
          ${q.matrix_rows.map(r => {
            const rkey = q.id + "|" + r.row_id;
            const iss = issues[rkey] || { errors: [], warnings: [] };
            return html`
            <tr key=${r.row_id}>
              <td>${r.label}</td>
              <td class="num">
                <${DebouncedNumber} value=${drafts[rkey]} compact=${true} onSave=${v => save(q, r.row_id, v)} />
                ${iss.errors.map((e, i) => html`<div key=${i} class="error-text">${e}</div>`)}
                ${iss.warnings.map((w, i) => html`<div key=${i} class="warn-text">⚠ ${w}</div>`)}
              </td>
            </tr>`;
          })}
        </tbody>
      </table>`;
  }
  return null;
}

function DebouncedNumber({ value, onSave, unitName, compact }) {
  const [v, setV] = useState(value == null ? "" : value);
  const t = useRef(null);
  useEffect(() => { setV(value == null ? "" : value); }, [value]);
  const change = (nv) => {
    setV(nv);
    clearTimeout(t.current);
    t.current = setTimeout(() => onSave(nv), 600);
  };
  return html`
    <span class="row" style=${{ gap: "6px", display: "inline-flex" }}>
      <input style=${compact ? null : { width: "150px", padding: "7px 9px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", textAlign: "right" }}
        inputmode="decimal" value=${v} onInput=${e => change(e.target.value)} onBlur=${() => { clearTimeout(t.current); onSave(v); }} />
      ${unitName && !compact && html`<span class="caption">${unitName}</span>`}
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
      <h1 class="display-title">Submission received</h1>
      <p>${done.answers_saved} answers saved and the benchmark has been refreshed — peer group sizes already include you.
      Core completion: <b>${done.core_completion_pct}%</b>.</p>
      ${done.benchmark_unlocked ?
        html`<button class="btn primary" onClick=${() => nav("/overview")}>See your benchmark</button>` :
        html`<p class="caption">Answer more Core questions to reach ${state.threshold_pct}% and unlock peer comparison.</p>`}
    </div>`;
  if (!val) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  return html`
    <div style=${{ maxWidth: "680px" }}>
      <button class="btn quiet" onClick=${() => nav("/submission")}>← All sections</button>
      <h1 class="display-title" style=${{ margin: "6px 0 12px" }}>Review and submit</h1>
      ${val.problems.length > 0 && html`
        <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s3)", borderColor: "var(--unfavourable)" }}>
          <b style=${{ color: "var(--unfavourable)" }}>Fix these before submitting</b>
          ${val.problems.map((p, i) => html`
            <div key=${i} style=${{ marginTop: "6px" }}>${p.title}${p.matrix_row_id ? " — " + p.matrix_row_id.replace(/_/g, " ") : ""}: ${p.errors.join("; ")}</div>`)}
        </div>`}
      ${val.unanswered_required.length > 0 && html`
        <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s3)" }}>
          <b>Unanswered required questions (${val.unanswered_required.length})</b>
          ${val.unanswered_required.slice(0, 12).map((u, i) => html`
            <div key=${i} class="caption" style=${{ marginTop: "4px" }}>
              <a href=${"#/submission/" + u.superpower}>${u.superpower}</a> — ${u.title}</div>`)}
          ${val.unanswered_required.length > 12 && html`<div class="caption">…and ${val.unanswered_required.length - 12} more.</div>`}
        </div>`}
      <div class="card" style=${{ padding: "var(--s5)" }}>
        <p>Submitting saves a timestamped version of your answers into the current collection window and refreshes the
        live benchmark. Nothing is ever overwritten — future windows will show your movement.</p>
        ${err && html`<div class="error-text" style=${{ marginBottom: "8px" }}>${err}</div>`}
        <button class="btn primary" disabled=${busy || val.problems.length > 0} onClick=${submit}>
          ${busy ? html`<${Spinner} /> Submitting…` : "Submit my data"}</button>
      </div>
    </div>`;
}
