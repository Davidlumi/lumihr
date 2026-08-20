/* Pulses — Tier 2 timely topical surveys (2026-06-12).
   A SEPARATE surface from the core benchmark: opt-in cohort per pulse,
   give-to-get per pulse, fully independent of the core unlock gate.
   Reuses the submission input components (same file-global functions) and
   the chart primitives — but never the core nav/aggregates. */
/* global html, useState, useEffect, useRef, api, cutFromURL, cutToURL, Spinner, EmptyState, PageLoading, nav, toast, Icon,
   fmtValue, PercentileBand, OptionBars, OrderedDist, InputForType, exportCardPNG */

// deadline urgency — a relative read with a "soon" flag for the blue "closing soon" cue
function closesIn(iso, accepting) {
  if (!iso) return accepting ? { text: "open — no close date yet", soon: false } : null;
  const d = new Date(iso.replace(" ", "T"));
  if (isNaN(d)) return null;
  if (!accepting) return { text: "closed " + fmtDate(iso), soon: false };
  const days = Math.ceil((d - new Date()) / 86400000);
  if (days <= 0) return { text: "closing now", soon: true };
  if (days === 1) return { text: "closes tomorrow", soon: true };
  if (days <= 7) return { text: "closes in " + days + " days", soon: days <= 3 };
  return { text: "closes " + fmtDate(iso), soon: false };
}
function CloseChip({ p }) {
  const c = closesIn(p.closes_at, p.accepting);
  if (!c) return null;
  return html`<span class=${"pulse-close" + (c.soon ? " soon" : "")}>${c.soon ? html`<${Icon} name="flag" size=${11} /> ` : ""}${c.text}</span>`;
}

// Pulse (David 2026-08-11): ONE page, two tabs — Explore (community pulses, everyone) and Run a pulse
// (the org's own pulses + launch pipeline, admin only). Merges the former separate /pulse + /run-a-pulse
// pages; the route drives the tab (/pulse = explore, /run-a-pulse = run), so URLs + back-button hold.
window.PulsesPage = function ({ me, tab }) {
  const isAdmin = me.user.role === "admin";
  const isRun = tab === "run" && isAdmin;                 // "Run a pulse" tab (admin only)
  const [data, setData] = useState(null);                // community pulses (/api/pulses) — Explore
  const [org, setOrg] = useState(null);                  // this org's own pulses (/api/org/pulses) — Run
  const [err, setErr] = useState(null);                  // community-fetch error (Explore only)
  const [orgErr, setOrgErr] = useState(null);            // org-fetch error (Run only) — separate loads (review #6)
  const [liveMoment, setLiveMoment] = useState(null);
  const [reload, setReload] = useState(0);
  useEffect(() => { setErr(null); api("/api/pulses").then(setData).catch(e => setErr(e.message)); }, [reload]);
  useEffect(() => {
    if (!isAdmin) return;
    setOrgErr(null);
    api("/api/org/pulses").then(d => {
      setOrg(d);
      // the LIVE moment (delight): once per pulse (localStorage marker), the owner gets a burst banner
      try {
        const justLive = (d.pulses || []).filter(p => p.launch_status === "paid" && p.status === "open"
          && !localStorage.getItem("lumi-pulse-live-" + p.pulse_id));
        if (justLive.length) { justLive.forEach(p => localStorage.setItem("lumi-pulse-live-" + p.pulse_id, "1")); setLiveMoment(justLive[0]); }
      } catch (e) {}
    }).catch(e => setOrgErr(e.message));
  }, [isAdmin, reload]);
  // per-tab error + loading gates (review #6: was one shared err + a swallowed org catch → infinite spinner)
  const retry = html`<button class="btn small primary" onClick=${() => setReload(r => r + 1)}>Retry</button>`;
  if (isRun && orgErr) return html`<${EmptyState} tone="error" icon="info" title="Couldn't load your pulses" body=${orgErr + " — nothing is lost."} action=${retry} />`;
  if (!isRun && err) return html`<${EmptyState} tone="error" icon="info" title="Couldn't load pulses" body=${err + " — nothing is lost."} action=${retry} />`;
  if (isRun ? !org : !data) return html`<${PageLoading} />`;

  // momentum toward the 5+ report unlock — a calm blue count meter, never RAG
  const momentum = (p) => {
    if (p.floor && p.participants < p.floor) {
      const pct = Math.max(6, Math.min(100, Math.round(100 * p.participants / p.floor)));
      return html`<div class="pulse-momentum">
        <div class="pulse-meter"><i style=${{ width: pct + "%" }}></i></div>
        <span class="caption num">${p.participants} of ${p.floor} · report unlocks at ${p.floor}</span></div>`;
    }
    return html`<span class="caption num pulse-partic"><${Icon} name="users" size=${12} /> ${p.participants} participating</span>`;
  };
  const cardCta = (p) => p.participated ? "View report" : p.joined ? "Finish your answers" : p.accepting ? "Take part (free)" : "View";
  const goPulse = (p) => nav("/pulse/" + p.pulse_id);

  const communityCard = (p) => html`
    <article key=${p.pulse_id} class="card pulse-card" role="button" tabindex="0" aria-label=${p.name + " — " + cardCta(p)}
      onClick=${() => goPulse(p)} onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); goPulse(p); } }}>
      <div class="pulse-card-top">
        <span class="pulse-medallion"><${Icon} name=${p.icon || "zap"} size=${15} /></span>
        <div class="pulse-card-headwrap">
          <b class="pulse-card-name">${p.name}</b>
          <div class="pulse-card-meta"><${CloseChip} p=${p} /><span class="caption num">${p.questions} question${p.questions === 1 ? "" : "s"}</span></div>
        </div>
      </div>
      <div class="caption pulse-card-desc">${p.description}</div>
      ${p.teaser ? html`<div class="pulse-card-teaser"><b>${p.teaser.stat}</b><span> on ${p.teaser.on}</span></div>` : null}
      ${momentum(p)}
      <div class="pulse-card-foot">
        ${p.participated ? html`<span class="pulse-taken"><${Icon} name="check" size=${12} /> You've taken part</span>`
          : p.joined ? html`<span class="caption">Started — not yet submitted</span>` : html`<span></span>`}
        <span class="pulse-card-cta">${cardCta(p)} <span aria-hidden="true">→</span></span>
      </div>
    </article>`;

  // the soonest-closing OPEN pulse gets a full-width hero — the one thing you can join right now
  const heroCard = (p) => html`
    <article class="card pulse-hero"
      onClick=${e => { if (!e.target.closest("button")) goPulse(p); }}>
      ${/* the inner CTA <button> is THE control (a real button nested inside
            role="button" is a nested-interactive violation — screen readers
            announce two overlapping controls); the card surface stays a
            convenience click target for mouse users only */ ""}
      <div class="pulse-hero-body">
        <div class="pulse-hero-tag"><${Icon} name=${p.icon || "zap"} size=${13} /> Open pulse</div>
        <h2 class="pulse-hero-name">${p.name}</h2>
        <p class="pulse-hero-desc">${p.description}</p>
        <div class="pulse-hero-meta"><${CloseChip} p=${p} /><span class="pulse-dot">·</span>${momentum(p)}</div>
      </div>
      <div class="pulse-hero-cta">
        <button class="btn primary" onClick=${e => { e.stopPropagation(); goPulse(p); }}>${cardCta(p)} <span aria-hidden="true">→</span></button>
      </div>
    </article>`;

  const runChip = (p) => {
    const ls = p.launch_status;
    const tone = ls === "paid" ? "pulse-chip" : "chip-neutral";   // one-blue: workflow states read neutral, the label + nextStep carry the meaning (David 2026-08-11)
    const label = ls === "paid" ? (p.status === "open" ? "live" : p.status) : ls === "in_review" ? "in review"
      : ls === "changes_requested" ? "changes requested"
      : ls === "approved" ? (((org && org.credits && org.credits.balance) || 0) < ((org && org.launch_cost) || 1)
          ? "needs a credit" : "ready to launch")   // was "awaiting invoice" (review QW6)
      : ls === "rejected" ? "declined" : "draft";
    return html`<span class="chip ${tone}">${label}</span>`;
  };
  // "ready to launch" is a lie when the balance is 0 — the row used to invite an action
  // the member could not take, and only the wall on the detail page said why.
  const credBal = (org && org.credits && org.credits.balance) || 0;
  const credCost = (org && org.launch_cost) || 1;
  const nextStep = (p) => p.launch_status === "changes_requested" ? "Address lumi's notes"
    : p.launch_status === "approved"
      ? (credBal < credCost ? "Needs a credit — contact lumi" : "Request your launch")
      : null;

  const exploreView = () => {
    const open = [...data.pulses.filter(p => p.accepting)].sort((a, b) => (a.closes_at || "z") < (b.closes_at || "z") ? -1 : 1);
    const past = data.pulses.filter(p => !p.accepting);
    const mine = past.filter(p => p.participated);        // closed pulses whose report is yours — foregrounded
    const archived = past.filter(p => !p.participated);   // closed, your org sat out — the report belongs to participants
    if (!open.length && !past.length) return html`<${EmptyState} tone="invite" icon="zap" title="No pulses yet"
      body="Short, timely community deep-dives on reward land here — take part free to unlock each report."
      action=${isAdmin ? html`<button class="btn small primary" onClick=${() => nav("/run-a-pulse")}>Run a pulse →</button>` : null} />`;
    const section = (title, list) => html`
      <h2 class="section-title" style=${{ margin: "var(--s6) 0 var(--s3)" }}>${title}</h2>
      <div class="pulse-grid">${list.map(communityCard)}</div>`;
    return html`
      ${open.length ? html`${heroCard(open[0])}${open.length > 1 ? html`<div class="pulse-grid">${open.slice(1).map(communityCard)}</div>` : null}`
        : html`<div class="pulse-note" style=${{ marginTop: "var(--s4)" }}><${Icon} name="info" size=${14} /><span>No pulse is open right now — new topics land here as they emerge.</span></div>`}
      ${mine.length ? section("Your reports", mine) : null}
      ${archived.length ? section("Archived", archived) : null}`;
  };

  const orgRow = (p) => html`
    <article key=${p.pulse_id} class="card pulse-srow" role="button" tabindex="0" aria-label=${p.name + " — " + (p.launch_status || "draft")}
      onClick=${() => nav("/run-a-pulse/" + p.pulse_id)} onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nav("/run-a-pulse/" + p.pulse_id); } }}>
      <div class="row spread"><b>${p.name}</b>${runChip(p)}</div>
      <div class="caption" style=${{ margin: "var(--s1) 0 0" }}>${p.n_questions} question${p.n_questions === 1 ? "" : "s"}${p.launch_status === "paid" ? ` · ${p.n_submitted} organisation${p.n_submitted === 1 ? "" : "s"}` : ""}</div>
      ${nextStep(p) ? html`<div class="pulse-action"><${Icon} name="info" size=${11} /> ${nextStep(p)}</div>` : null}</article>`;

  const howSteps = html`<div class="pulse-how">
    <div class="pulse-how-step"><span class="pulse-how-num">1</span><div><b>Build</b><span class="caption">Design your questions</span></div></div>
    <div class="pulse-how-step"><span class="pulse-how-num">2</span><div><b>We review</b><span class="caption">A quick quality check</span></div></div>
    <div class="pulse-how-step"><span class="pulse-how-num">3</span><div><b>Go live</b><span class="caption">One credit · opens to all members</span></div></div>
  </div>`;

  const runView = () => {
    // action-required pulses first (review #10)
    const rank = p => (p.launch_status === "changes_requested" || p.launch_status === "approved") ? 0 : 1;
    const pulses = [...org.pulses].sort((a, b) => rank(a) - rank(b));
    return html`
      ${liveMoment && html`<div class="unlock-moment" role="status">
        <div class="unlock-spark"><${Icon} name="sparkle" size=${20} /></div>
        <div><b>“${liveMoment.name}” is live to the community</b>
          <p class="caption" style=${{ margin: "var(--s1) 0 0", maxWidth: "56ch" }}>Every lumi member can now answer — the report unlocks at ${liveMoment.floor || 5}+ organisations.</p></div>
        <button class="btn small unlock-x" aria-label="Dismiss" onClick=${() => setLiveMoment(null)}><${Icon} name="close" size=${13} /></button>
      </div>`}
      ${!pulses.length ? html`
        <div class="card pulse-first" style=${{ maxWidth: "640px", margin: "var(--s4) auto 0", padding: "var(--s7) var(--s6)", textAlign: "center" }}>
          <div class="pulse-empty-ico"><${Icon} name="list-checks" size=${24} /></div>
          <b>Ask the community a question only lumi can answer</b>
          <p class="caption" style=${{ margin: "var(--s1) auto var(--s5)", maxWidth: "42ch" }}>Pay equity, four-day weeks, AI in reward — your questions, answered as anonymised 5+-organisation aggregates.</p>
          ${howSteps}
          <button class="btn primary" style=${{ marginTop: "var(--s3)" }} onClick=${() => nav("/run-a-pulse/new")}>Create your first pulse</button>
        </div>` : html`
        <div class="row spread" style=${{ alignItems: "center", margin: "var(--s2) 0 var(--s3)" }}>
          <h2 class="section-title" style=${{ margin: 0 }}>Your pulses</h2>
          <button class="btn primary" style=${{ flex: "none" }} onClick=${() => nav("/run-a-pulse/new")}><${Icon} name="list-checks" size=${15} /> New pulse</button>
        </div>
        <div class="pulse-grid">${pulses.map(orgRow)}</div>
        <div class="pulse-note" style=${{ marginTop: "var(--s4)" }}><${Icon} name="info" size=${14} />
          <span>Build → we review → you request the launch → it opens to the community. Launching uses one credit.</span></div>`}`;
  };

  const taken = !isAdmin && data ? data.pulses.filter(p => p.participated).length : 0;
  return html`
    <div class="pulse-page" style=${{ maxWidth: "1120px", margin: "0 auto" }}>
      <div class="pulse-head">
        <div class="pulse-head-l">
          <h1 class="display-title" style=${{ margin: 0 }}>Pulse</h1>
          <p class="pulse-lead">${isRun
            ? "Design a pulse and launch it to the lumi community — answers come back as anonymised 5+-organisation aggregates."
            : "Short, timely community deep-dives on reward — take part free to unlock each report."}</p>
        </div>
        ${!isAdmin && taken ? html`<div class="pulse-head-stat"><b class="num">${taken}</b><span class="caption">pulse${taken === 1 ? "" : "s"} taken</span></div>` : null}
        ${isRun && org && org.credits ? html`<div class=${"pulse-head-stat pulse-credits" + (org.credits.balance ? "" : " none")}
            title=${org.credits.balance ? "One credit launches one pulse" : "Contact lumi to add credits"}>
          <b class="num">${org.credits.balance}</b><span class="caption">credit${org.credits.balance === 1 ? "" : "s"}</span></div>` : null}
      </div>
      ${isAdmin ? html`<div class="pulse-tabs" role="group" aria-label="Pulse views">
        <a href="#/pulse" class=${"pulse-tab" + (!isRun ? " on" : "")} aria-current=${!isRun ? "page" : undefined}>Explore</a>
        <a href="#/run-a-pulse" class=${"pulse-tab" + (isRun ? " on" : "")} aria-current=${isRun ? "page" : undefined}>Run a pulse</a>
      </div>` : null}
      ${isRun ? runView() : exploreView()}
    </div>`;
};

window.PulseDetailPage = function ({ me, pid }) {
  const [p, setP] = useState(null);
  const [err, setErr] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [issues, setIssues] = useState({});
  const [savedAt, setSavedAt] = useState(null);
  const [busy, setBusy] = useState(false);
  // The peer cut lives in the hash as ?cut=dim::value — the app's own deep-link contract
  // (cutFromURL/cutToURL), so a filtered pulse report is shareable and back-button safe
  // exactly like a filtered benchmark. The API takes it as two params, so convert here.
  // cutToURL uses history.replaceState, which does NOT fire hashchange — so the picker
  // drives state directly and the URL follows for shareability, rather than the other way
  // round. hashchange is still listened for, to catch a back/forward between cut states.
  const [cutSel, setCutSel] = useState(() => cutFromURL());
  useEffect(() => {
    const onHash = () => setCutSel(cutFromURL());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const applyCut = (c) => { setCutSel({ dim: c.dim, value: c.value || null }); cutToURL(c); };
  const cutQS = cutSel.dim === "all" ? ""
    : "?cut=" + encodeURIComponent(cutSel.dim) + (cutSel.value ? "&cut_value=" + encodeURIComponent(cutSel.value) : "");
  const refresh = () => api("/api/pulses/" + pid + cutQS).then(d => {
    setP(d);
    const init = {};
    (d.question_list || []).forEach(q => {
      if (q.type === "matrix") Object.entries(q.current || {}).forEach(([rid, v]) => { if (v != null) init[q.id + "|" + rid] = v; });
      else if (q.current != null) init[q.id + "|"] = q.current;
    });
    setDrafts(init);
  }).catch(e => setErr(e.message));
  useEffect(() => { refresh(); }, [pid, cutSel.dim, cutSel.value]);
  if (err) return html`<${EmptyState} tone="error" icon="info" title="Couldn't load this pulse" body=${err + " — nothing is lost."} action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!p) return html`<${PageLoading} />`;

  const editor = me.user.role === "admin" || me.user.role === "contributor";
  const join = async () => {
    try { await api("/api/pulses/" + pid + "/join", { method: "POST", body: {} }); toast("You're in — answer what applies and submit."); refresh(); }
    catch (e) { toast(e.message, "error"); }
  };
  // mirror the core wizard's data-loss safety: track in-flight saves (the global
  // beforeunload guard reads window._pendingSaves) and flush before submit so a
  // value being typed can't be lost when Submit fires (DebouncedNumber commits on blur)
  const flush = async () => {
    const el = document.activeElement; if (el && el.blur) el.blur();
    await new Promise(r => setTimeout(r, 60));
    let g = 0; while (window._pendingSaves > 0 && g < 80) { await new Promise(r => setTimeout(r, 50)); g++; }
  };
  const save = async (q, rowId, value) => {
    const key = q.id + "|" + (rowId || "");
    setDrafts(d => ({ ...d, [key]: value }));
    window._pendingSaves++;
    try {
      const r = await api("/api/pulses/" + pid + "/response", { method: "PUT",
        body: { question_id: q.id, matrix_row_id: rowId || "", value } });
      setIssues(s => ({ ...s, [key]: { errors: r.errors || [], warnings: r.warnings || [] } }));
      if (r.ok !== false) setSavedAt(new Date());
    } catch (e) { toast("Couldn't save your last answer — it's still here.", "error", { label: "Retry", fn: () => save(q, rowId, value) }); }
    finally { window._pendingSaves = Math.max(0, window._pendingSaves - 1); }
  };
  const submit = async () => {
    setBusy(true);
    await flush();
    const first = !p.participated;
    try {
      await api("/api/pulses/" + pid + "/submit", { method: "POST", body: {} });
      toast(first ? "Thank you — this pulse's report is now yours." : "Your answers are updated.", "success");
      if (first && window.confettiBurst) window.confettiBurst({ count: 120, duration: 2400, origin: { x: 0.5, y: 0.3 } });
      refresh();
    } catch (e) { toast(e.message, "error"); }
    setBusy(false);
  };
  const isAnswered = (q) => q.type === "matrix"
    ? (q.matrix_rows || []).some(r => drafts[q.id + "|" + r.row_id] != null && drafts[q.id + "|" + r.row_id] !== "")
    : (drafts[q.id + "|"] != null && drafts[q.id + "|"] !== "");
  const answeredCount = (p.question_list || []).filter(isAnswered).length;

  // 820px is a READING width — right for filling in the survey, far too narrow for a
  // dashboard of metric cards, which is what this page becomes once the report is in. With
  // the report showing, take the full content column so a pulse card is the same size as a
  // benchmark card (David 2026-08-20).
  return html`
    <div class=${"pulse-page" + (p.report ? " pulse-page-report" : "")}
      style=${p.report ? { margin: "0 auto" } : { maxWidth: "820px", margin: "0 auto" }}>
      <button class="btn quiet" onClick=${() => nav("/pulse")}>← All pulses</button>
      <div class="pulse-banner">Timely pulse — separate from your core benchmark</div>
      <h1 class="display-title pulse-title">${p.name}</h1>
      <p class="caption pulse-subhead">
        <span class="pulse-subhead-desc">${p.description} · ${p.participants} organisation${p.participants === 1 ? "" : "s"} participating</span>
        <${CloseChip} p=${p} /></p>

      ${/* Three states, one gate. Open: nobody has results yet, and saying so is the whole
            message. Closed but not yours: the card is there, greyed, with the route to buy
            it. Closed and yours: the report. (David 2026-08-20) */ ""}
      ${!p.report_available && p.participated && html`
        <div class="card pulse-waiting">
          <div class="pulse-empty-ico"><${Icon} name="clock" size=${24} /></div>
          <b>Your answers are in — results publish when this pulse closes</b>
          <p class="caption">Nobody sees the cohort while it is still answering, so no one can
            read the market before choosing their own answer.${p.closes_at
              ? " Closes " + fmtDate(p.closes_at) + "." : ""}</p>
        </div>`}

      ${p.report_locked && html`
        <div class="card pulse-locked">
          <div class="pulse-lock-body">
            <div class="pulse-empty-ico"><${Icon} name="lock" size=${24} /></div>
            <b>This pulse has closed — its report is open to the organisations that took part</b>
            <p class="caption">You didn't take part in “${p.name}”, so its results are locked.${" "}
              ${p.participants} organisation${p.participants === 1 ? "" : "s"} answered.${" "}
              Taking part in a pulse is always free; access to one you missed is bought from lumi.</p>
            <div class="pulse-lock-actions">
              <a class="btn primary" href=${"mailto:hello@lumihr.co.uk?subject=" +
                 encodeURIComponent("Pulse report access — " + p.name)}>Contact lumi for access</a>
              <button class="btn" onClick=${() => nav("/pulse")}>See open pulses</button>
            </div>
            <div class="caption pulse-lock-note">We'll invoice you and open it on your account.</div>
          </div>
          ${(p.question_list || []).length ? html`
            <div class="pulse-lock-peek">
              <div class="eyebrow">What it asked · ${p.question_list.length} question${p.question_list.length === 1 ? "" : "s"}</div>
              <ul>${p.question_list.slice(0, 6).map((q, i) => html`<li key=${i}>${q.text}</li>`)}</ul>
            </div>` : null}
        </div>`}

      ${p.report && html`<${PulseReport} report=${p.report} pid=${pid} me=${me}
         cut=${p.cut} onCut=${applyCut} />`}

      ${!p.joined && p.accepting && html`
        <div class="card" style=${{ padding: "var(--s5)", margin: "var(--s4) 0" }}>
          <b>Take part to see this pulse's report</b>
          <p class="caption" style=${{ margin: "var(--s2) 0 var(--s3)" }}>Free for participants — answer what applies.</p>
          ${(p.question_list || []).length ? html`
            <div class="pulse-teaser">
              <div class="eyebrow" style=${{ marginBottom: "var(--s2)" }}>What this pulse asks · ${p.question_list.length} question${p.question_list.length === 1 ? "" : "s"}</div>
              <ul>${p.question_list.slice(0, 6).map((q, i) => html`<li key=${i}>${q.text}</li>`)}</ul>
              <div class="caption" style=${{ marginTop: "var(--s2)" }}>Answers unlock once ${5}+ organisations have taken part.</div>
            </div>` : null}
          ${editor ? html`<button class="btn primary" style=${{ marginTop: "var(--s3)" }} onClick=${join}>Join this pulse</button>` :
            html`<div class="caption" style=${{ marginTop: "var(--s3)" }}>Ask an Admin or Contributor on your team to join and answer.</div>`}
        </div>`}
      ${!p.joined && !p.accepting && !p.report && html`
        <${EmptyState} icon="lock" title="This pulse has closed"
          body="Its report belongs to the organisations that took part during the window."
          action=${html`<button class="btn small" onClick=${() => nav("/pulse")}>See open pulses</button>`} />`}

      ${p.joined && p.accepting && html`
        <div class="card pulse-survey" style=${{ margin: "var(--s4) 0" }}>
          <div class="pulse-survey-head">
            <div class="row spread" style=${{ alignItems: "baseline", gap: "var(--s2)" }}>
              <div><b>Your answers</b> <span class="caption">· answer what applies — skipped questions are excluded</span></div>
              <div class=${"qwiz-saved" + (savedAt ? " on" : "")} role="status">
                ${savedAt ? "Saved " + savedAt.toLocaleTimeString("en-GB") : answeredCount + " of " + p.question_list.length + " answered · autosaves"}</div>
            </div>
            <div class="pulse-progress" role="progressbar" aria-valuenow=${answeredCount} aria-valuemin="0" aria-valuemax=${p.question_list.length}
              aria-label=${answeredCount + " of " + p.question_list.length + " answered"}>
              <div class="pulse-progress-fill" style=${{ width: (p.question_list.length ? Math.round(100 * answeredCount / p.question_list.length) : 0) + "%" }}></div>
            </div>
          </div>
          <div class="pulse-survey-body">
            ${p.question_list.map((q, qi) => { const ans = isAnswered(q); return html`
              <div key=${q.id} class=${"pulse-q" + (ans ? " answered" : "")}>
                <div class="pulse-q-head">
                  <span class="pulse-q-num" aria-hidden="true">${ans ? "✓" : qi + 1}</span>
                  <span class="pulse-q-text">${q.text}</span>
                </div>
                ${q.help_text && html`<div class="pulse-q-hint">${q.help_text}</div>`}
                <div class="pulse-q-input">
                  <${InputForType} q=${q} drafts=${drafts} issues=${issues} save=${save} confirmValue=${() => {}} />
                  ${(issues[q.id + "|"] || { errors: [] }).errors.map((e, i) => html`<div key=${i} class="error-text">${e}</div>`)}
                  ${(issues[q.id + "|"] || { warnings: [] }).warnings.map((w, i) => html`<div key=${i} class="warn-text">⚠ ${w}</div>`)}
                </div>
              </div>`; })}
          </div>
          <div class="pulse-survey-foot">
            <button class="btn primary" disabled=${busy} aria-busy=${busy ? "true" : "false"} onClick=${submit}>${busy ? html`<${Spinner} />` : (p.participated ? "Update my answers" : "Submit and see the report")}</button>
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
    if (blk.options && blk.options.length) {
      // mark WHICH option the member chose. The column existed and was always blank on
      // option rows, so a downloaded pulse showed the cohort and not the comparison —
      // the whole point of the export (2026-08-19).
      const normC = t => (t || "").replace(/\s+/g, " ").trim().toLowerCase();
      const picked = new Set(String(q.you == null ? "" : q.you).split(";").map(normC).filter(Boolean));
      blk.options.forEach(o => rows.push([q.title, o.label, o.pct, "", blk.n,
        picked.has(normC(o.label)) ? "Yes" : ""]));
    }
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

/* The peer cut on a pulse report — the SAME vocabulary as the benchmark selector
   (all / industry / size band / a saved group / Peer Twin), reading /api/cuts so the
   options are the member's own, not a second list that can drift from it. Whole cohort
   is the default: it is the honest headline for a pulse, and a member narrows from it. */
function PulseCutPicker({ cut, onCut }) {
  const [cuts, setCuts] = useState(null);
  const [open, setOpen] = useState(false);
  useEffect(() => { api("/api/cuts").then(setCuts).catch(() => {}); }, []);
  const cur = cut || { dim: "all" };
  const label = cur.label || "All participating organisations";
  const pick = (dim, value) => { setOpen(false); onCut({ dim, value }); };
  return html`
    <div class="pulse-cutwrap">
      <button class=${"btn small" + (cur.dim !== "all" ? " on" : "")} aria-haspopup="menu"
        aria-expanded=${open} onClick=${() => setOpen(o => !o)}>
        <${Icon} name="filter" size=${13} /> ${label}</button>
      ${open && cuts && html`
        <div class="cmp-menu pulse-cutmenu" role="menu">
          <button class="cutopt" role="menuitem" onClick=${() => pick("all", null)}>All participating organisations</button>
          ${cuts.twin_available ? html`<button class="cutopt" role="menuitem" onClick=${() => pick("twin", null)}>Peer Twin</button>` : null}
          ${(cuts.groups || []).length ? html`<div class="cutgrp">Your peer groups</div>` : null}
          ${(cuts.groups || []).map(g => html`<button key=${g.group_id} class="cutopt" role="menuitem"
             onClick=${() => pick("group", g.group_id)}>${g.name}</button>`)}
          <div class="cutgrp">Size</div>
          ${Object.keys(cuts.fte_bands || {}).map(b => html`<button key=${b} class="cutopt" role="menuitem"
             onClick=${() => pick("fte_band", b)}>${b}</button>`)}
          <div class="cutgrp">Industry</div>
          ${Object.keys(cuts.industries || {}).map(i => html`<button key=${i} class="cutopt" role="menuitem"
             onClick=${() => pick("industry", i)}>${i}</button>`)}
        </div>`}
    </div>`;
}

function PulseReport({ report, pid, me, cut, onCut }) {
  // the deterministic narrative ships in the payload (opens with it instantly);
  // when the AI surface is live it upgrades to the grounded model narrative.
  // Hooks run unconditionally BEFORE any early return (below_floor).
  const [nar, setNar] = useState(report.narrative || {});
  const [coms, setComs] = useState({});
  const [printing, setPrinting] = useState(false);
  const belowFloor = report.below_floor;
  useEffect(() => {
    if (belowFloor || !(me.features && me.features.pulse_ai)) return;
    api("/api/pulses/" + pid + "/narrative", { method: "POST", body: {} })
      .then(r => { if (r && r.narrative && r.source === "model") setNar(r.narrative); })
      .catch(() => {});
  }, [pid]);
  if (belowFloor) return html`
    <div class="card" style=${{ padding: "var(--s5)", margin: "var(--s4) 0", textAlign: "center" }}>
      <div class="unlock-spark" style=${{ margin: "0 auto var(--s2)" }}><${Icon} name="flag" size=${20} /></div>
      <b>Your answers are in — results appear once ${report.floor}+ organisations have taken part.</b>
      <div class="caption" style=${{ marginTop: "var(--s2)" }} title=${`Every answer stays protected by the same ${report.floor}-organisation rule as the core benchmark.`}>${report.participants} of ${report.floor} so far.</div>
    </div>`;
  const genDate = (report.generated_at || "").slice(0, 10);
  return html`
    <div class="pulse-report-doc" style=${{ margin: "var(--s4) 0" }}>
      <div class="pulse-pdf-head" aria-hidden="true"><span class="logo">lumi<span>.</span></span> · Pulse report</div>
      <div class="card">
        <div class="qsec-head row spread">
          <div><b>Pulse report</b> <span class="caption">· ${report.participants} organisations${cut && cut.dim !== "all" ? " in " + cut.label : ""} · every answer counted, nothing shown below ${report.floor} organisations${genDate ? " · " + genDate : ""}</span></div>
          <div class="row no-print" style=${{ gap: "var(--s2)" }}>
            ${onCut ? html`<${PulseCutPicker} cut=${cut} onCut=${onCut} />` : null}
            <button class="btn small" onClick=${() => downloadPulseCsv(report)}><${Icon} name="download" size=${13} /> CSV</button>
            <button class="btn small primary" disabled=${printing} onClick=${async () => {
              // A pulse PDF with charts and no observations is a slide deck. Write the read
              // for every question first, then print — the same "story is the centrepiece"
              // contract the metric one-pager keeps (David 2026-08-19).
              setPrinting(true);
              try {
                if (me.features && me.features.pulse_ai) {
                  const todo = (report.questions || []).filter(
                    q => !(q.block || {}).suppressed && !coms[q.question_id]);
                  if (todo.length) toast("Writing the observations for your report…");
                  const done = {};
                  for (const q of todo) {
                    try { done[q.question_id] = await api("/api/pulses/" + pid + "/commentary",
                      { method: "POST", body: { question_id: q.question_id } }); } catch (e) { /* print anyway */ }
                  }
                  if (Object.keys(done).length) setComs(c => ({ ...c, ...done }));
                  await nextPaint();
                }
                printPulse(report);
              } finally { setPrinting(false); }
            }}>${printing ? html`<${Spinner} />` : html`<${Icon} name="file-text" size=${13} />`} Print / save as PDF</button>
          </div>
        </div>
        ${report.illustrative && html`<div class="caption" style=${{ margin: "var(--s2) 0", color: "var(--ink-faint)" }}>Illustrative sample data.</div>`}
        ${(nar.summary || (nar.key_findings || []).length) && html`
          <div class="pulse-narrative">
            ${nar.summary && html`<p style=${{ margin: "0 0 var(--s2)" }}>${nar.summary}</p>`}
            ${(nar.key_findings || []).length ? html`
              <div class="pulse-findings">
                <div class="eyebrow" style=${{ marginBottom: "var(--s1)" }}>Key findings</div>
                <ol>${nar.key_findings.map((f, i) => html`<li key=${i}>${f}</li>`)}</ol>
              </div>` : null}
          </div>`}
      </div>
      ${/* The results read as a dashboard, not a document: the same .bench-grid of
            .bench-card the benchmark uses, so a pulse result looks and behaves like every
            other card on the platform (David 2026-08-19). The old single-card stack of
            question blocks had no card edges at all, which is why six charts melded. */ ""}
      <div class="bench-grid pulse-grid-cards">
        ${report.questions.map((q, i) => html`<${PulseQuestionBlock} key=${q.question_id} q=${q}
           pid=${pid} me=${me} idx=${i + 1} total=${report.questions.length} report=${report}
           com=${coms[q.question_id]} />`)}
      </div>
      <div class="pulse-pdf-foot" aria-hidden="true">Private & confidential · Generated by lumi${genDate ? " · " + genDate : ""} · figures resting on fewer than 5 organisations are never shown</div>
    </div>`;
}

// The SAME canvas width CardBody gives a benchmark card in this grid (wide -> 620), so a
// pulse result is drawn to the platform's own calibration rather than its own: same type
// size, same label gutter, same row height as every other card on the page.
const PULSE_CHART_W = 620;

/* The expanded view of ONE pulse question — the pulse equivalent of the metric page, and
   the surface the card's "Open full view" leads to. Same three things a metric one-pager
   gives you: the chart at full size, the written read of where you sit, and a print that
   puts both on one page. The commentary is fetched on arrival rather than on a click,
   because on this page it IS the content, not an extra. */
window.PulseQuestionPage = function ({ me, pid, qid }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [com, setCom] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api("/api/pulses/" + pid).then(setData).catch(e => setErr(e.message));
  }, [pid]);
  const q = data && (data.report.questions || []).find(x => x.question_id === qid);
  useEffect(() => {
    if (!q || !(me.features && me.features.pulse_ai) || (q.block || {}).suppressed) return;
    setBusy(true);
    api("/api/pulses/" + pid + "/commentary", { method: "POST", body: { question_id: qid } })
      .then(setCom).catch(() => {}).finally(() => setBusy(false));
  }, [pid, qid, !!q]);

  if (err) return html`<${EmptyState} icon="info" title="Couldn't open this question" body=${err} />`;
  if (!data) return html`<div style=${{ padding: "var(--s6)" }}><${Spinner} /></div>`;
  if (!q) return html`<${EmptyState} icon="info" title="Not part of this pulse"
    body="That question isn't in this pulse — it may have been withdrawn."
    action=${html`<button class="btn small primary" onClick=${() => nav("/pulse/" + pid)}>Back to the pulse</button>`} />`;

  const report = data.report, blk = q.block || {};
  const youNum = q.you != null && q.you !== "" && !isNaN(parseFloat(q.you)) ? parseFloat(q.you) : null;
  const youLabels = q.you && q.type !== "numeric"
    ? (q.type === "multi_select" ? String(q.you).split(";").map(t => t.trim()).filter(Boolean) : [String(q.you)])
    : [];
  const favNorm = t => (t || "").replace(/\s+/g, " ").trim().toLowerCase();
  const fav = q.favourable_label && youLabels.some(l => favNorm(l) === favNorm(q.favourable_label)) ? "good" : null;
  const genDate = (report.generated_at || "").slice(0, 10);

  const onePager = async () => {
    // the written read is the centrepiece of the page, so never print without it
    if (!com && me.features && me.features.pulse_ai && !blk.suppressed) {
      toast("Writing your commentary for the one-pager…");
      try { setCom(await api("/api/pulses/" + pid + "/commentary", { method: "POST", body: { question_id: qid } })); }
      catch (e) { toast("Couldn't write the commentary — printing the figures.", "error"); }
      await nextPaint();
    }
    const t = document.title;
    document.title = "lumi — " + q.title + " · one-pager";
    window.print();
    setTimeout(() => { document.title = t; }, 500);
  };

  return html`
    <div class="metric-page pulse-q-page">
      <div class="metric-pdf-head" aria-hidden="true">
        <span class="logo">lumi<span>.</span></span> · Pulse one-pager · ${report.name} · ${blk.n} organisations${genDate ? " · " + genDate : ""}</div>
      <button class="btn quiet no-print" onClick=${() => nav("/pulse/" + pid)}>← ${report.name}</button>
      <h1 class="display-title" style=${{ margin: "var(--s3) 0 var(--s1)" }}>${q.title}</h1>
      <p class="caption" style=${{ maxWidth: "70ch" }}>${q.text}</p>
      <div class="card" style=${{ marginTop: "var(--s4)", padding: "var(--s5)" }}>
        ${blk.suppressed ? html`<div class="caption">Fewer than ${report.floor} organisations answered — protected, not shown.</div>` : html`
          <div role="img" aria-label=${q.title + " — " + blk.n + " organisations answered."}>
            ${blk.p50 != null && html`<${PercentileBand} block=${blk} you=${youNum} unit=${q.unit} favourable=${null} width=${780} />`}
            ${blk.options && (q.type === "multi_select"
              ? html`<${OptionBars} options=${blk.options} youLabels=${youLabels} width=${780} height=${420} />`
              : html`<${OrderedDist} options=${blk.options} youLabels=${youLabels} fav=${fav} width=${780} height=${420} />`)}
          </div>
          <div class="bench-foot" style=${{ marginTop: "var(--s3)" }}>
            <span class="bench-n">${blk.n} of ${report.participants} organisations answered</span>
            ${q.you != null && q.you !== "" ? html`<span class="caption base-note">your answer marked</span>` : null}
          </div>`}
      </div>
      ${(com || busy) && html`
        <div class="card pulse-onepager-read" style=${{ marginTop: "var(--s4)", padding: "var(--s5)" }}>
          <div class="eyebrow">Where you sit</div>
          ${busy && !com ? html`<${Spinner} />` : Object.entries((com || {}).parts || {})
            .filter(([k]) => k !== "measures")
            .map(([k, v]) => html`<p key=${k} class=${"pcom-" + k}>${v}</p>`)}
        </div>`}
      <div class="row no-print" style=${{ gap: "var(--s2)", marginTop: "var(--s4)" }}>
        <button class="btn small primary" onClick=${onePager}><${Icon} name="file-text" size=${14} /> One-pager</button>
        <button class="btn small" onClick=${() => downloadPulseCsv({ ...report, questions: [q] })}>
          <${Icon} name="download" size=${13} /> CSV</button>
      </div>
      <div class="metric-pdf-foot" aria-hidden="true">Private & confidential · lumi pulse · figures resting on fewer than ${report.floor} organisations are never shown</div>
    </div>`;
};

function PulseQuestionBlock({ q, pid, me, idx, total, report, com }) {
  const blk = q.block || {};
  const [expanded, setExpanded] = useState(false);
  const ref = useRef(null);
  // the SAME export path a benchmark card uses — exportCardPNG finds the svg inside
  // .bench-chart-full, which this card has, so a pulse chart copies and downloads with
  // the identical framing, footer and labelling as every other chart on the platform
  const exportMeta = () => ({
    title: q.title, cutLabel: report.name, n: blk.n, n_real: blk.n_real || 0,
    window: null, card: { type: q.type, title: q.title, block: blk },
    org: (window.__orgName || ""), suffix: null,
  });
  const exportable = !blk.suppressed;
  const doExport = async () => {
    try {
      const res = await exportCardPNG(ref.current, exportMeta(), "download");
      toast(res === "downloaded" ? "Chart downloaded — labelled " + report.name + ", " + blk.n + " organisations"
                                 : "Nothing to export yet");
    } catch (e) { toast("Couldn't export the chart here.", "error"); }
  };
  const doCopy = async () => {
    try {
      const res = await exportCardPNG(ref.current, exportMeta(), "clipboard");
      if (res === "copied") toast("Chart copied — labelled " + report.name + ", " + blk.n + " organisations");
      else if (res === "downloaded") toast("Copy isn't available here — downloaded the chart instead.");
      else toast("Nothing to export yet");
    } catch (e) { toast("Couldn't copy the chart here.", "error"); }
  };
  // the org's OWN answer, resolved to what the charts expect: a number for
  // numeric, or the chosen label(s) for selects (";"-joined for multi)
  const youNum = q.you != null && q.you !== "" && !isNaN(parseFloat(q.you)) ? parseFloat(q.you) : null;
  const youLabels = q.you && q.type !== "numeric"
    ? (q.type === "multi_select" ? String(q.you).split(";").map(s => s.trim()).filter(Boolean) : [String(q.you)])
    : [];
  const favNorm = s => (s || "").replace(/\s+/g, " ").trim().toLowerCase();
  const fav = q.favourable_label && youLabels.some(l => favNorm(l) === favNorm(q.favourable_label)) ? "good" : null;

  const share = () => {
    const url = window.location.href.split("#")[0] + "#/pulse/" + pid;
    navigator.clipboard && navigator.clipboard.writeText(url);
    toast("Link copied.");
  };

  if (blk.suppressed) return html`
    <div class="card bench-card stacked pulse-qcard">
      <div class="bench-head"><h3 class="bench-title">${q.title}</h3></div>
      <div class="caption" style=${{ padding: "var(--s4) 0" }}>Fewer than 5 participating organisations — protected, not shown.</div>
    </div>`;

  return html`
    <div class="card bench-card stacked pulse-qcard" ref=${ref} id=${"pq-" + q.question_id}>
      <div class="bench-head">
        <h3 class="bench-title" title=${q.text}>${q.title}</h3>
      </div>
      <div class="bench-chart-full"
        role="img" aria-label=${q.title + " — " + (blk.n || 0) + " organisations answered."}
        title="Open full view"
        onClick=${e => { if (!e.target.closest("a") && !e.target.closest("button")) nav("/pulse/" + pid + "/q/" + q.question_id); }}>
        ${blk.p50 != null && html`<${PercentileBand} block=${blk} you=${youNum} unit=${q.unit} favourable=${null} width=${PULSE_CHART_W} />`}
        ${blk.options && (q.type === "multi_select"
          ? html`<${OptionBars} options=${blk.options} youLabels=${youLabels} width=${PULSE_CHART_W} height=${q.you ? 172 : 140} />`
          : html`<${OrderedDist} options=${blk.options} youLabels=${youLabels} fav=${fav} width=${PULSE_CHART_W} height=${q.you ? 172 : 140} />`)}
        ${q.matrix_rows && html`
          <div class="matrix-num-wrap"><table class="data">
            <thead><tr><th>Level</th><th class="num">Cohort</th><th class="num">You</th></tr></thead>
            <tbody>${q.matrix_rows.map(r => html`
              <tr key=${r.row_id}><td>${r.label}</td>
                <td class="num">${r.block && r.block.suppressed ? "—" :
                  r.block && r.block.p50 != null ? "median " + fmtValue(r.block.p50, q.unit) :
                  r.block && r.block.modal_label ? r.block.modal_label + " (" + r.block.modal_pct + "%)" : "—"}
                  ${r.block && r.block.n ? html`<span class="caption"> · n=${r.block.n}</span>` : ""}</td>
                <td class="num" style=${{ color: r.you != null && r.you !== "" ? "var(--blue-deep)" : "var(--ink-faint)", fontWeight: 600 }}>${r.you != null && r.you !== "" ? fmtValue(parseFloat(r.you), q.unit) : "—"}</td></tr>`)}
            </tbody></table></div>`}
      </div>

      ${com && com !== "…" && html`
        <div class="pulse-com">
          ${Object.entries(com.parts || {}).filter(([k]) => k !== "measures")
            .map(([k, v]) => html`<p key=${k} class=${"pcom-" + k}>${v}</p>`)}
        </div>`}
      ${com === "…" && html`<div class="pulse-com"><${Spinner} /></div>`}

      <div class="bench-foot">
        <span class="bench-n">${blk.n} organisation${blk.n === 1 ? "" : "s"}</span>
        ${q.you != null && q.you !== "" && q.type !== "matrix"
          ? html`<span class="caption base-note">your answer marked</span>` : null}
        ${/* the benchmark card's control row exactly, minus the pin — a pulse question has
              no dashboard to pin to. The written read is NOT a card control here either,
              for the same reason it is not one on a benchmark card: it belongs to the
              expanded view, which generates it on arrival. (David 2026-08-20) */ ""}
        <div class="card-tools no-print">
          <button class="iconbtn" title="Open full view" aria-label="Open full view"
            onClick=${() => nav("/pulse/" + pid + "/q/" + q.question_id)}><${Icon} name="maximize" size=${15} /></button>
          <button class="iconbtn" title="Question & definition" aria-label="Question & definition"
            onClick=${() => setExpanded(e => !e)}><${Icon} name="info" size=${15} /></button>
          ${exportable && html`<button class="iconbtn" title="Copy chart to clipboard" aria-label="Copy chart"
            onClick=${doCopy}><${Icon} name="copy" size=${15} /></button>`}
          ${exportable && html`<button class="iconbtn" title="Download chart (PNG)" aria-label="Download chart"
            onClick=${doExport}><${Icon} name="download" size=${15} /></button>`}
          ${exportable && html`<button class="iconbtn" title=${"Copy link · " + report.name} aria-label="Copy link"
            onClick=${share}><${Icon} name="link" size=${15} /></button>`}
        </div>
      </div>
      ${expanded && html`
        <div class="pulse-detail">
          <div class="eyebrow">Question ${idx} of ${total} · asked as</div>
          <p>${q.text}</p>
          <div class="caption">${TYPE_LABEL[q.type] || q.type} · ${blk.n} of ${report.participants} organisations answered</div>
          <button class="btn small quiet" onClick=${() => setExpanded(false)}>Close</button>
        </div>`}
    </div>`;
}

const PULSE_BUILD_TYPES = ["yes_no", "single_select", "multi_select", "numeric"];
const TYPE_LABEL = { yes_no: "Yes / No", single_select: "Pick one", multi_select: "Pick many", numeric: "A number" };
const LAUNCH_STEPS = [
  { key: "building", label: "Build" }, { key: "in_review", label: "lumi review" },
  { key: "approved", label: "Launch" }, { key: "paid", label: "Live" },
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

// RunPulsePage merged into PulsesPage's "Run a pulse" tab (David 2026-08-11). The /run-a-pulse route
// now renders <PulsesPage tab="run" />; the builder (/run-a-pulse/new · /run-a-pulse/<id>) is below.

window.PulseBuilderPage = function ({ me, pid }) {
  const isNew = pid === "new";
  const [detail, setDetail] = useState(isNew ? { launch_status: "building", question_list: [] } : null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = () => { if (!isNew) api("/api/org/pulses/" + pid).then(setDetail).catch(e => setErr(e.message)); };
  useEffect(() => {
    load();
    // PH-PAY-1: the ?paid=1 / ?cancelled=1 Stripe-redirect reconcile that lived
    // here was removed with the card path — all payments are by invoice, and
    // the launch opens when lumi confirms it.
  }, [pid]);
  if (err) return html`<${EmptyState} tone="error" icon="info" title="Couldn't load this pulse" body=${err + " — nothing is lost."} action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!detail) return html`<${PageLoading} />`;
  const ls = detail.launch_status;
  const editable = ls === "building" || ls === "changes_requested";

  const submitCreate = async (body, thenReview) => { setBusy(true);
    try {
      const r = await api("/api/org/pulses", { method: "POST", body });
      if (thenReview) {
        // one-step submit: create the draft, then send it for review with its fresh id.
        // If review fails we STILL navigate to the saved draft — a retry there can't create a duplicate.
        try { await api("/api/org/pulses/" + r.pulse_id + "/submit-for-review", { method: "POST", body: {} });
          toast("Submitted for review — we'll be in touch.", "success"); }
        catch (e2) { toast("Draft saved, but couldn't submit for review: " + e2.message, "error"); }
      } else { toast("Draft saved.", "success"); }
      nav("/run-a-pulse/" + r.pulse_id);
    } catch (e) { toast(e.message, "error"); }
    setBusy(false); };
  const submitUpdate = async (body) => { setBusy(true);
    try { await api("/api/org/pulses/" + pid, { method: "PUT", body }); toast("Saved.", "success"); load(); setBusy(false); return true; }
    catch (e) { toast(e.message, "error"); setBusy(false); return false; } };
  const submitForReview = async () => { setBusy(true);
    try {
      await api("/api/org/pulses/" + pid + "/submit-for-review", { method: "POST", body: {} });
      toast("Submitted for review — we'll be in touch.", "success");
      load();
    } catch (e) { toast(e.message, "error"); } setBusy(false); };
  const discard = async () => { if (!window.confirm("Discard this draft pulse?")) return;
    try { await api("/api/org/pulses/" + pid, { method: "DELETE" }); toast("Discarded."); nav("/run-a-pulse"); }
    catch (e) { toast(e.message, "error"); } };

  return html`
    <div class="pulse-page" style=${{ maxWidth: "820px", margin: "0 auto" }}>
      <button class="btn quiet" onClick=${() => nav("/run-a-pulse")}>← Your pulses</button>
      ${!isNew && html`<${LaunchStepper} ls=${ls} />`}
      ${ls === "changes_requested" && detail.review_notes && html`
        <div class="card" style=${{ padding: "var(--s4)", margin: "var(--s3) 0", borderLeft: "3px solid var(--blue-bright)" }}>
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
  const addNew = () => setNewQs(n => [...n, { text: "", type: "yes_no", polarity: "neutral", optionsText: "Yes\nNo", unitKind: "none", unitLabel: "", hint: "", favLabel: "" }]);
  const setNQ = (i, patch) => setNewQs(n => n.map((x, j) => j === i ? { ...x, ...patch } : x));
  const removeNQ = (i) => setNewQs(n => n.filter((_, j) => j !== i));
  const moveNQ = (i, d) => setNewQs(n => { const j = i + d; if (j < 0 || j >= n.length) return n;
    const c = [...n]; [c[i], c[j]] = [c[j], c[i]]; return c; });
  const [preview, setPreview] = useState(false);
  const [pvDrafts, setPvDrafts] = useState({});
  const pvSave = (q, rowId, v) => setPvDrafts(d => ({ ...d, [q.id + "|" + (rowId || "")]: v }));
  const liveNew = () => newQs.filter(nq => (nq.text || "").trim());
  // resolve a numeric draft's unit into the fields the server + report expect.
  // The schema already reads unit_type/unit/unit_display_name in _assemble_questions
  // and unit_block() derives the symbol — so this is a pure frontend addition.
  const pulseUnit = (nq) => {
    if (nq.type !== "numeric") return null;
    if (nq.unitKind === "percentage") return { unit_type: "percentage", unit: "%", unit_display_name: "%", block: { type: "percentage", symbol: "%", display_name: "%" } };
    if (nq.unitKind === "currency") return { unit_type: "currency", unit: "GBP", unit_display_name: "£", block: { type: "currency", symbol: "£", display_name: "£", currency_code: "GBP" } };
    const lbl = (nq.unitLabel || "").trim();
    if (nq.unitKind === "custom" && lbl) return { unit_type: "none", unit: lbl, unit_display_name: lbl, block: { type: "none", symbol: "", display_name: lbl } };
    return { unit_type: "none", unit: null, unit_display_name: "", block: { type: "none", symbol: "", display_name: "" } };
  };
  // build an InputForType-shaped question from a composer draft, for the preview
  const previewQ = (nq, i) => {
    const isSel = ["single_select", "yes_no", "multi_select"].includes(nq.type);
    const labels = (nq.optionsText || "").split("\n").map(s => s.trim()).filter(Boolean);
    const u = pulseUnit(nq);
    return { id: "pv-" + i, text: nq.text, title: nq.text, type: nq.type,
      options: isSel ? labels.map((l, j) => ({ code: "O" + j, label: l })) : [],
      na_allowed: nq.type === "numeric", matrix_rows: [],
      unit: u ? u.block : {}, unit_display_name: u ? u.unit_display_name : "", help_text: (nq.hint || "").trim() };
  };
  const buildBody = () => {
    const bespoke = liveNew().map(nq => {
      const isSel = ["single_select", "yes_no", "multi_select"].includes(nq.type);
      const labels = (nq.optionsText || "").split("\n").map(s => s.trim()).filter(Boolean);
      // favourable answer applies only to the single-choice types (ambiguous for multi)
      const favL = ["single_select", "yes_no"].includes(nq.type) ? (nq.favLabel || "").trim() : "";
      const q = { text: nq.text.trim(), type: nq.type, polarity: nq.polarity || "neutral",
        options: isSel ? labels.map((l, i) => ({ code: l.toUpperCase().replace(/[^A-Z0-9]+/g, "_").replace(/^_|_$/g, "") || ("OPT" + i), label: l, order: i + 1, is_na: false,
          ...(favL && l === favL ? { is_favourable: true } : {}) })) : undefined };
      const hint = (nq.hint || "").trim();
      if (hint) q.help_text = hint;
      const u = pulseUnit(nq);
      if (u && nq.unitKind && nq.unitKind !== "none") { q.unit_type = u.unit_type; q.unit = u.unit; q.unit_display_name = u.unit_display_name; }
      return q;
    });
    return { name: name.trim(), description: desc.trim(), closes_at: closesAt.trim() || null,
      question_ids: keep.map(k => k.id), new_questions: bespoke };
  };
  const valid = () => {
    if (!name.trim()) { toast("Give your pulse a name.", "error"); return false; }
    if (!keep.length && !liveNew().length) { toast("Add at least one question.", "error"); return false; }
    // select questions need real, distinct options — a zero-option "Pick one" saved
    // fine and produced an unanswerable pulse (P3 sweep 2026-08-13)
    for (const q of liveNew()) {
      if (q.type === "single_select" || q.type === "multi_select") {
        const opts = (q.options || []).map(o => (o || "").trim()).filter(Boolean);
        if (opts.length < 2) { toast(`"${(q.text || "This question").slice(0, 40)}" needs at least two options.`, "error"); return false; }
        if (new Set(opts.map(o => o.toLowerCase())).size !== opts.length) {
          toast(`"${(q.text || "This question").slice(0, 40)}" has duplicate options.`, "error"); return false;
        }
      }
    }
    return true;
  };
  const save = () => { if (valid()) onSubmit(buildBody(), false); };
  // one click from a full form to "in review": for a NEW pulse the create call
  // submits for review itself (onSubmit(body, true)); for an existing draft we
  // save then review, and only review if the save actually succeeded (a failed
  // PUT used to still fire the review call, submitting a stale draft).
  const saveThenReview = async () => {
    if (!valid()) return;
    if (isNew) { onSubmit(buildBody(), true); return; }
    const ok = await onSubmit(buildBody(), false);
    if (ok !== false) onSubmitReview();
  };
  const needle = libQ.trim().toLowerCase();
  const libRows = (lib || []).filter(x => !needle || (x.title || "").toLowerCase().includes(needle) || (x.subpower || "").toLowerCase().includes(needle));
  return html`
    <div class="card pulse-form" style=${{ padding: "var(--s5)", marginTop: "var(--s3)" }}>
      <h2 class="section-title">${isNew ? "New pulse" : "Edit your pulse"}</h2>
      
      <label>Pulse name<input class="ctl" maxlength="120" value=${name} onInput=${e => setName(e.target.value)} placeholder="e.g. Four-day-week appetite 2026" /></label>
      <label>Description<textarea class="ctl" maxlength="280" rows=${2} value=${desc} onInput=${e => setDesc(e.target.value)} placeholder="One line on what you're asking and why."></textarea></label>
      <label>Close date <span class="caption" style=${{ fontWeight: 400 }}>· optional — closes at end of that day</span>
        <input class="ctl" type="date" value=${(closesAt || "").slice(0, 10)} onInput=${e => setClosesAt(e.target.value)} /></label>

      <div class="qsec-head" style=${{ marginTop: "var(--s5)" }}><b>Questions</b> <span class="pulse-count-chip">${keep.length + liveNew().length}</span> <span class="caption">— the order members will see</span></div>
      ${keep.map((k, ki) => html`
        <div key=${k.id} class="pulse-keep-row">
          <span class="pulse-q-num">${ki + 1}</span>
          <div class="pulse-keep-main">
            <div class="pulse-keep-text">${k.text}</div>
            <div class="pulse-keep-meta"><span class="pulse-lib-tag">reused</span> <span class="caption">${TYPE_LABEL[k.type] || k.type}</span></div>
          </div>
          <button class="btn small quiet" onClick=${() => removeKeep(k.id)}>Remove</button></div>`)}
      ${newQs.map((nq, i) => html`
        <div key=${"n" + i} class="pulse-newq">
          <div class="pulse-newq-head">
            <span class="pulse-q-num">${keep.length + i + 1}</span>
            <b>New question</b>
            <div class="pulse-newq-tools">
              <button class="btn small quiet" title="Move up" aria-label="Move question up"
                disabled=${i === 0} onClick=${() => moveNQ(i, -1)}>↑</button>
              <button class="btn small quiet" title="Move down" aria-label="Move question down"
                disabled=${i === newQs.length - 1} onClick=${() => moveNQ(i, 1)}>↓</button>
              <button class="btn small quiet" onClick=${() => removeNQ(i)}>Remove</button></div></div>
          <label>Question<input class="ctl" maxlength="200" value=${nq.text} onInput=${e => setNQ(i, { text: e.target.value })} placeholder="What do you want to ask?" /></label>
          <div class="row" style=${{ gap: "var(--s3)" }}>
            <label style=${{ flex: 1 }}>Answer type<select class="ctl" value=${nq.type} onChange=${e => setNQ(i, { type: e.target.value })}>
              ${PULSE_BUILD_TYPES.map(t => html`<option key=${t} value=${t}>${TYPE_LABEL[t]}</option>`)}</select></label>
            ${nq.type === "numeric" && html`<label style=${{ flex: 1 }}>Better when<select class="ctl" value=${nq.polarity} onChange=${e => setNQ(i, { polarity: e.target.value })}>
              <option value="neutral">no preference</option><option value="higher_is_better">higher</option><option value="lower_is_better">lower</option></select></label>`}
          </div>
          ${nq.type === "numeric" && html`
            <div class="row" style=${{ gap: "var(--s3)" }}>
              <label style=${{ flex: 1 }}>Unit<select class="ctl" value=${nq.unitKind || "none"} onChange=${e => setNQ(i, { unitKind: e.target.value })}>
                <option value="none">no unit</option>
                <option value="percentage">percentage (%)</option>
                <option value="currency">£ (GBP)</option>
                <option value="custom">custom…</option></select></label>
              ${nq.unitKind === "custom" && html`<label style=${{ flex: 1 }}>Unit label<input class="ctl" maxlength="16" value=${nq.unitLabel || ""} onInput=${e => setNQ(i, { unitLabel: e.target.value })} placeholder="e.g. days, FTE" /></label>`}
            </div>`}
          ${["single_select", "yes_no", "multi_select"].includes(nq.type) && html`
            <label>Options <span class="caption" style=${{ fontWeight: 400 }}>· one per line</span>
              <textarea class="ctl" rows=${3} value=${nq.optionsText} onInput=${e => setNQ(i, { optionsText: e.target.value })}></textarea></label>`}
          ${["single_select", "yes_no"].includes(nq.type) && html`
            <label>Favourable answer <span class="caption" style=${{ fontWeight: 400 }}>· optional — marks the “better” answer in the results</span>
              <select class="ctl" value=${nq.favLabel || ""} onChange=${e => setNQ(i, { favLabel: e.target.value })}>
                <option value="">no preference</option>
                ${(nq.optionsText || "").split("\n").map(s => s.trim()).filter(Boolean).map(l => html`<option key=${l} value=${l}>${l}</option>`)}
              </select></label>`}
          <label>Hint for members <span class="caption" style=${{ fontWeight: 400 }}>· optional — shown under the question</span>
            <input class="ctl" maxlength="160" value=${nq.hint || ""} onInput=${e => setNQ(i, { hint: e.target.value })} placeholder="A short note to help members answer accurately." /></label>
        </div>`)}
      <button class="pulse-add-tile" onClick=${addNew}>+ Add a question</button>
      <div class="row" style=${{ marginTop: "var(--s2)" }}>
        <button class="btn small quiet" onClick=${() => setShowLib(s => !s)}>${showLib ? "Hide library" : "+ Add from the lumi library"}</button>
      </div>
      ${showLib && html`
        <div style=${{ marginTop: "var(--s2)" }}>
          <input class="ctl" style=${{ width: "100%" }} aria-label="Search the pulse library" placeholder="Search the library…" value=${libQ} onInput=${e => setLibQ(e.target.value)} />
          <div class="pulse-libpick">
            ${lib === null ? html`<${Spinner} />` : libRows.slice(0, 120).map(x => html`
              <button key=${x.id} class="pulse-librow" disabled=${keep.some(k => k.id === x.id)} onClick=${() => addLib(x)}>
                <span>${x.title} <span class="caption">· ${x.subpower || "—"} · ${TYPE_LABEL[x.type] || x.type}</span></span>
                <span class="pulse-lib-tags">
                  ${keep.some(k => k.id === x.id) ? html`<span class="pulse-lib-tag added">added</span>` : ""}
                  ${x.answered ? html`<span class="pulse-lib-tag" title="Your organisation has already answered this in the core benchmark">in your benchmark</span>` : ""}
                  ${x.locked ? html`<span class="pulse-lib-tag locked" title="A core benchmark metric — your benchmark result for it is behind the give-to-get wall, but you can still ask it as a pulse"><${Icon} name="lock" size=${11} /> core</span>` : ""}
                </span></button>`)}
          </div></div>`}
      ${(keep.length || liveNew().length) ? html`
        <div class="row" style=${{ gap: "var(--s2)", marginTop: "var(--s4)" }}>
          <button class="btn small quiet" onClick=${() => setPreview(p => !p)}>
            ${preview ? "Hide preview" : "Preview as a member"}</button>
        </div>` : ""}
      ${preview && html`
        <div class="pulse-preview">
          <div class="pulse-preview-head"><b>Preview</b> <span class="caption">· answers here aren't saved</span></div>
          <div class="pulse-preview-body">
            <h3 class="pulse-preview-title">${name || "Untitled pulse"}</h3>
            ${desc ? html`<p class="caption" style=${{ marginTop: "var(--s1)" }}>${desc}</p>` : ""}
            ${keep.map((k, i) => html`
              <div key=${"pvk" + k.id} class="pulse-preview-q">
                <div class="pulse-preview-label"><span class="pulse-preview-num">${i + 1}</span> ${k.text}</div>
                <p class="caption pulse-preview-reused">Reused library question · ${TYPE_LABEL[k.type] || k.type}</p>
              </div>`)}
            ${liveNew().map((nq, i) => { const q = previewQ(nq, i); return html`
              <div key=${"pvn" + i} class="pulse-preview-q">
                <div class="pulse-preview-label"><span class="pulse-preview-num">${keep.length + i + 1}</span> ${nq.text}</div>
                ${(nq.hint || "").trim() ? html`<div class="caption" style=${{ marginBottom: "var(--s2)" }}>${nq.hint}</div>` : ""}
                <${InputForType} q=${q} drafts=${pvDrafts} issues=${{}} save=${pvSave} confirmValue=${() => {}} />
              </div>`; })}
          </div>
        </div>` }
      <div class="row" style=${{ gap: "var(--s2)", marginTop: "var(--s5)", flexWrap: "wrap" }}>
        <button class="btn" disabled=${busy} onClick=${save}>${isNew ? "Save draft" : "Save changes"}</button>
        ${(isNew || onSubmitReview) && html`<button class="btn primary" disabled=${busy} onClick=${saveThenReview}>Submit for review →</button>`}
        ${!isNew && onDiscard && html`<button class="btn quiet" style=${{ marginLeft: "auto" }} onClick=${onDiscard}>Discard</button>`}
      </div>
      ${isNew && html`<p class="caption" style=${{ marginTop: "var(--s2)" }}>Submit for review now, or save a draft to finish later.</p>`}
    </div>`;
}

function PulseLaunchPanel({ detail, pid, onChange }) {
  const ls = detail.launch_status;
  const [paying, setPaying] = useState(false);
  const bal = (detail.credits && detail.credits.balance) || 0;
  const cost = detail.launch_cost || 1;
  const pay = async () => {
    if (paying) return;
    if (!window.confirm("Request the launch? This uses " + cost + " of your " + bal + " pulse credit" + (bal === 1 ? "" : "s") + ", and lumi opens it to the community on confirmation.")) return;
    setPaying(true);
    try {
      const r = await api("/api/org/pulses/" + pid + "/checkout", { method: "POST", body: {} });
      toast(r.message || "Launch requested — lumi will confirm shortly.", "info");
      onChange();
    } catch (e) { toast(e.message, "error"); }
    setPaying(false);
  };
  const QList = () => html`
    <div class="card" style=${{ padding: "var(--s4)", marginTop: "var(--s3)" }}>
      <div class="qsec-head"><b>${detail.name}</b></div>
      ${detail.description ? html`<p class="caption">${detail.description}</p>` : ""}
      ${(detail.question_list || []).map(q => html`<div key=${q.id} class="caption" style=${{ padding: "var(--s1) 0" }}>• ${q.text} <span style=${{ opacity: 0.7 }}>(${TYPE_LABEL[q.type] || q.type})</span></div>`)}
    </div>`;
  if (ls === "in_review") return html`
    <div class="card" style=${{ padding: "var(--s5)", marginTop: "var(--s3)", textAlign: "center" }}>
      <div class="pulse-empty-ico"><${Icon} name="list-checks" size=${24} /></div>
      <b>With lumi for review</b>
      <p class="caption" style=${{ margin: "var(--s1) auto 0", maxWidth: "44ch" }}>Review usually takes a couple of working days — we'll let you know when it's approved.</p>
    </div>
    ${QList()}`;
  if (ls === "approved" && bal < cost) return html`
    <div class="card pulse-launch" style=${{ marginTop: "var(--s3)" }}>
      <div class="pulse-empty-ico"><${Icon} name="info" size=${24} /></div>
      <b style=${{ fontSize: "var(--fs-card-title)" }}>Approved — you need a credit to launch</b>
      <p class="caption" style=${{ margin: "var(--s2) auto 0", maxWidth: "42ch" }}>Your pulse is ready and stays exactly as it is. Launching takes ${cost} credit and you have none left.</p>
      <div class="pulse-credit-wall">
        <a class="btn primary" href=${"mailto:hello@lumihr.co.uk?subject=" + encodeURIComponent("More pulse credits — " + (detail.name || "pulse"))}>Contact lumi for credits</a>
      </div>
      <div class="caption">We'll invoice you and add them to your account.</div>
    </div>
    ${QList()}`;
  if (ls === "approved") return html`
    <div class="card pulse-launch" style=${{ marginTop: "var(--s3)" }}>
      <div class="pulse-empty-ico"><${Icon} name="check" size=${24} /></div>
      <b style=${{ fontSize: "var(--fs-card-title)" }}>Approved — ready to launch</b>
      <p class="caption" style=${{ margin: "var(--s2) auto 0", maxWidth: "40ch" }}>Your pulse opens to the whole community as soon as lumi confirms it.</p>
      <div class="pulse-fee">${cost} credit</div>
      <div class="caption" style=${{ marginBottom: "var(--s2)" }}>${bal} available${bal - cost === 0 ? " · your last one" : ""}</div>
      <button class="btn primary" disabled=${paying} onClick=${pay}>${paying ? html`<${Spinner} />` : "Request launch"}</button>
    </div>
    ${QList()}`;
  if (ls === "paid") return html`
    <div class="card pulse-launch live" style=${{ marginTop: "var(--s3)" }}>
      <div class="pulse-empty-ico"><${Icon} name="sparkle" size=${24} /></div>
      <b style=${{ fontSize: "var(--fs-card-title)" }}>You're live — open to the community</b>
      <p class="caption" style=${{ margin: "var(--s2) auto var(--s3)", maxWidth: "40ch" }}>${detail.n_submitted || 0} organisation${detail.n_submitted === 1 ? "" : "s"} so far · results unlock at 5+ organisations.</p>
      <button class="btn primary" onClick=${() => nav("/pulse/" + pid)}>View the live pulse & report →</button>
    </div>`;
  if (ls === "rejected") return html`
    <${EmptyState} icon="info" title="Not approved for launch"
      body=${detail.review_notes || "lumi wasn't able to approve this pulse for the community."} />`;
  return html`<${EmptyState} icon="info" title="Draft" body="Edit your pulse to continue." />`;
}
