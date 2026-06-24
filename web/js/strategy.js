/* Reward strategy capture (2026-06-16) — three-plane onboarding.
   Plane A (confirm 4 business facts, pre-filled from the registry) · Plane B
   (7 philosophy dials) · Plane C (4 posture dials) · Review. Admin-only; also
   editable later in Settings. Captures a BROAD reward stance so the engines can
   tell "below market" from "below market, on purpose" — granularity lives in the
   questionnaire, never here (spec §0).

   Vocabulary: the market_position dial speaks the locked below/on/above-market
   words (lumi-terminology.md); enums stay lag/match/lead internally. */

// ---- dial data (copy verbatim from the signed mockup) -------------------------
// se = the one-line "signal-effect" reveal; pill markup inline. C dials carry none.
const SE = (t) => t;   // marker — strings may contain <b>/<span class="se-pill …">
const SCALE = {
  market: { q: 'As a broad stance, where do you aim to sit on pay against peers? <span class="strat-faint">You can refine by job family later.</span>',
    stops: [
      { v: "lag", t: "Below market", d: "By design, not by accident", se: 'A below-market position reads as <span class="se-pill amber">intended</span> — we won’t flag it as a gap to close.' },
      { v: "match", t: "On market", d: "In line with peers", se: 'An on-market position reads as <span class="se-pill green">on target</span> — where you mean to be.' },
      { v: "lead", t: "Above market", d: "By design, not by accident", se: 'An above-market position reads as <span class="se-pill green">intended</span>, not as overspend to flag.' } ] },
  mix: { q: "What does most of the work in your package?",
    stops: [
      { v: "cash", t: "Mostly pay", d: "Salary does most of the work", se: 'We’ll weigh your <b>cash position</b> heavily — base pay is your main lever.' },
      { v: "balanced", t: "Balanced", d: "Pay and benefits share the load", se: 'We’ll read pay and package <b>together</b>, neither dominating.' },
      { v: "benefits", t: "Mostly benefits", d: "The wider package is the draw", se: 'A below-market base reframes to <span class="se-pill blue">check total package</span> — your cash-light mix is deliberate, not a gap.' } ] },
  p4p: { q: "How much does pay reward strong performance?",
    stops: [
      { v: "egal", t: "Everyone similar", d: "Pay stays close across the board", se: 'Flat pay spreads read as <b>intended</b>, not a failure to reward top performers.' },
      { v: "moderate", t: "Some gap", d: "Strong performers paid a bit more", se: 'We’ll expect a <b>moderate</b> spread and read your spreads against that.' },
      { v: "strong", t: "Big gap", d: "Top performers paid well above", se: 'Wide pay spreads read as <span class="se-pill green">on strategy</span> — strong differentiation is the design.' } ] },
  transparency: { q: "How openly do you share pay information inside the company?",
    stops: [
      { v: "closed", t: "Private", d: "Pay isn’t shared", se: 'We’ll treat open-pay practices as <b>optional</b> for you, not expected.' },
      { v: "ranges", t: "Ranges shared", d: "People see the pay bands", se: 'Sharing ranges internally is your <b>stated</b> norm — we read against it.' },
      { v: "open", t: "Fully open", d: "Actual pay is visible", se: 'Full openness becomes a <span class="se-pill green">commitment we track</span> — gaps to it surface as actions.' } ] },
  location: { q: "Does where someone works change their pay?",
    stops: [
      { v: "local", t: "Local rates", d: "Pay follows the local area", se: 'We’ll give you <b>per-location</b> reads — local market rates matter to you.' },
      { v: "national", t: "One rate", d: "Same across the country", se: 'We’ll read you against a <b>national</b> market, one rate.' },
      { v: "agnostic", t: "Anywhere", d: "Same pay wherever you are", se: 'Per-location “below local market” signals are <span class="se-pill blue">switched off</span> — a single national read is the relevant one.' } ] },
  family: { q: "How far do you go on parental leave and caring for family?",
    stops: [
      { v: "statutory", t: "Legal minimum", d: "What the law requires", se: 'We’ll hold you to the <b>statutory</b> floor — extra spend reads as discretionary.' },
      { v: "market", t: "In line", d: "Around the same as peers", se: 'We’ll read you against the <b>market norm</b> for family benefits.' },
      { v: "over", t: "Generous", d: "More than most peers offer", se: 'A generous family position reads as <span class="se-pill green">on strategy</span> — your stated stance is the evidence it’s intended, not overspend.' } ] },
  budget: { q: "Which way is your pay and reward budget heading?",
    stops: [
      { v: "investing", t: "Investing", d: "More to spend" }, { v: "flat", t: "Flat", d: "Holding the line" },
      { v: "pressure", t: "Under pressure", d: "Tightening" } ] },
  pressure: { q: "What’s the shape of the year ahead?",
    stops: [
      { v: "bau", t: "Business as usual", d: "Steady" }, { v: "scaling", t: "Scaling fast", d: "Growing hard" },
      { v: "shock", t: "Through a shock", d: "Disrupted" } ] },
  risk: { q: "When the market shifts, how do you react?",
    stops: [
      { v: "early", t: "Move early", d: "Lead the change" }, { v: "follow", t: "Follow the pack", d: "Move with peers" },
      { v: "wait", t: "Wait & see", d: "Let it settle" } ] },
};
const OBJECTIVES = [
  { v: "attract", t: "Attract", d: "Win the talent race" }, { v: "retain", t: "Retain", d: "Hold who we have" },
  { v: "cost", t: "Control cost", d: "Reward discipline" }, { v: "compliance", t: "Get it right", d: "Tidy up policy and risk" },
  { v: "hold", t: "Hold steady", d: "No major change" },
];
const BENEFITS = [
  { v: "physical", t: "Physical / health" }, { v: "mental", t: "Mental wellbeing" },
  { v: "financial", t: "Financial" }, { v: "worklife", t: "Work-life" },
];
// field -> the SCALE key that renders it (the engine field name is the storage key)
const SCALE_FIELD = { market_position: "market", reward_mix: "mix", pay_for_performance: "p4p",
  transparency: "transparency", location_approach: "location", family_position: "family",
  budget_direction: "budget", acute_pressure: "pressure", risk_appetite: "risk" };
const REQUIRED = ["market_position", "reward_mix", "primary_objective"];
const DIAL_LABEL = { market_position: "Market position", reward_mix: "Total-reward mix",
  pay_for_performance: "Pay for performance", transparency: "Pay transparency",
  location_approach: "Location approach", benefits_lead: "Benefits lead", family_position: "Family-friendliness",
  primary_objective: "Primary objective", budget_direction: "Budget direction",
  acute_pressure: "Acute pressure", risk_appetite: "Risk appetite" };
// label of a stored value, for the review read-back
function labelOf(field, val) {
  if (field === "primary_objective") { const o = OBJECTIVES.find(o => o.v === val); return o ? o.t : val; }
  const sk = SCALE_FIELD[field];
  if (sk) { const s = SCALE[sk].stops.find(s => s.v === val); return s ? s.t : val; }
  return val;
}

const useLayoutEffect = React.useLayoutEffect;   // not re-exported globally like the others

// ---- ScaleTrack — connected track + thumb anchored to the MEASURED stop centre
function ScaleTrack({ skey, value, onPick, ariaLabel }) {
  const cfg = SCALE[skey];
  const stopsRef = useRef(null);
  const [thumb, setThumb] = useState(null);            // {left, fill} in px, measured
  const idx = cfg.stops.findIndex(s => s.v === value);
  // tactile delight: the thumb springs into place on each pick (not on first paint)
  const prevIdx = useRef(idx);
  const [settling, setSettling] = useState(false);
  useEffect(() => {
    if (idx >= 0 && prevIdx.current >= 0 && prevIdx.current !== idx) {
      setSettling(true); const t = setTimeout(() => setSettling(false), 440);
      prevIdx.current = idx; return () => clearTimeout(t);
    }
    prevIdx.current = idx;
  }, [idx]);
  useLayoutEffect(() => {
    const wrap = stopsRef.current; if (!wrap || idx < 0) { setThumb(null); return; }
    const btns = wrap.querySelectorAll(".scale-stop");
    const el = btns[idx]; if (!el) return;
    const c = el.offsetLeft + el.offsetWidth / 2;       // measured centre, not a guessed %
    setThumb({ left: c });
  }, [idx, value]);
  const move = (e) => {
    if (idx < 0) return;
    let n = idx;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") n = Math.min(cfg.stops.length - 1, idx + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") n = Math.max(0, idx - 1);
    else return;
    e.preventDefault(); onPick(cfg.stops[n].v);
  };
  return html`
    <div class="scale" role="presentation">
      <div class="scale-track"></div>
      <div class="scale-fill" style=${{ width: thumb ? thumb.left + "px" : "0" }}></div>
      ${thumb && html`<div class=${"scale-thumb" + (settling ? " settling" : "")} style=${{ left: thumb.left + "px" }}></div>`}
      <div class="scale-stops" role="radiogroup" aria-label=${ariaLabel} ref=${stopsRef} onKeyDown=${move}>
        ${cfg.stops.map(s => html`
          <button key=${s.v} class=${"scale-stop" + (s.v === value ? " on" : "")} role="radio"
            aria-checked=${s.v === value} tabindex=${s.v === value || (idx < 0 && s === cfg.stops[0]) ? 0 : -1}
            onClick=${() => onPick(s.v)}>
            <span class="ot">${s.t}</span><span class="od">${s.d}</span></button>`)}
      </div>
    </div>`;
}

// ---- a single dial card (scale | cards | chips) -------------------------------
function DialCard({ field, value, onPick, required }) {
  const sk = SCALE_FIELD[field];
  const flagged = required && !value;     // unset required → amber prompt
  const tag = required ? html`<span class="strat-req">Required</span>` : html`<span class="strat-opt">Optional</span>`;
  let body, se = null;
  if (sk) {
    const cfg = SCALE[sk];
    body = html`<${ScaleTrack} skey=${sk} value=${value} ariaLabel=${DIAL_LABEL[field]} onPick=${v => onPick(field, v)} />`;
    const stop = cfg.stops.find(s => s.v === value);
    if (stop && stop.se) se = stop.se;
    var q = cfg.q;
  } else if (field === "primary_objective") {
    var q = "What is pay and reward mainly for, right now?";
    body = html`<div class="dial-opts" role="radiogroup" aria-label="Primary objective">
      ${OBJECTIVES.map(o => html`<button key=${o.v} class=${"dial-opt" + (o.v === value ? " on" : "")}
        role="radio" aria-checked=${o.v === value} onClick=${() => onPick(field, o.v)}>
        <span class="ot">${o.t}</span><span class="od">${o.d}</span></button>`)}</div>`;
  } else if (field === "benefits_lead") {
    var q = "Which areas do your benefits focus on? Pick any that fit.";
    const sel = value || [];
    body = html`<div class="chip-row" role="group" aria-label="Benefits lead">
      ${BENEFITS.map(b => html`<button key=${b.v} class=${"strat-chip" + (sel.includes(b.v) ? " on" : "")}
        aria-pressed=${sel.includes(b.v)} onClick=${() => onPick(field, sel.includes(b.v) ? sel.filter(x => x !== b.v) : [...sel, b.v])}>
        <${Icon} name="check" size=${12} /> ${b.t}</button>`)}</div>`;
  }
  return html`
    <div class=${"dial-card" + (flagged ? " flagged" : "")} id=${"dial-" + field}>
      <div class="dial-head">
        <span class=${"dial-roundel" + (flagged ? " flagged" : "")}><${Icon} name=${DIAL_ICON[field] || "target"} size=${16} /></span>
        <div>
          <div class="dial-title">${DIAL_LABEL[field]} ${tag}</div>
          <div class="dial-q" dangerouslySetInnerHTML=${{ __html: q }}></div>
        </div>
      </div>
      ${body}
      ${se && html`<div class="signal-effect"><span class="se-eye"><${Icon} name="sparkle" size=${14} /></span>
        <span class="se-text" dangerouslySetInnerHTML=${{ __html: se }}></span></div>`}
    </div>`;
}
const DIAL_ICON = { market_position: "target", reward_mix: "coins", pay_for_performance: "bar-chart",
  transparency: "search", location_approach: "compass", benefits_lead: "heart", family_position: "users",
  primary_objective: "target", budget_direction: "trending-up", acute_pressure: "zap", risk_appetite: "shield" };

window.StrategyPage = function ({ me }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [step, setStep] = useState(0);                 // 0 A · 1 B · 2 C · 3 review
  const [strat, setStrat] = useState({});              // field -> value
  const [planeA, setPlaneA] = useState([]);            // editable Plane-A facts
  const [toast, setToast] = useState(null);
  const [saving, setSaving] = useState(false);
  const [committed, setCommitted] = useState(false);   // brief "captured" flourish before nav
  const isAdmin = me && me.user && me.user.role === "admin";
  useEffect(() => {
    api("/api/strategy").then(d => {
      setData(d);
      setStrat({ ...d.strategy });
      setPlaneA(d.plane_a.map(f => ({ ...f })));
    }).catch(e => setErr(e.message));
  }, []);
  if (err) return html`<${EmptyState} icon="compass" title="Couldn't load your strategy" body=${err} />`;
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "var(--s8)" }}><${Spinner} /></div>`;
  if (!isAdmin) return html`<${EmptyState} icon="lock" title="Admin only"
    body="Your reward strategy is set by an organisation Admin. Ask yours to complete it — you'll see your results read through it." />`;

  const pick = (field, val) => setStrat(s => ({ ...s, [field]: val }));
  const planeBfields = ["market_position", "reward_mix", "pay_for_performance", "transparency",
    "location_approach", "benefits_lead", "family_position"];
  const planeCfields = ["primary_objective", "budget_direction", "acute_pressure", "risk_appetite"];
  // required dials owned by each plane
  const planeReq = { 1: ["market_position", "reward_mix"], 2: ["primary_objective"] };
  const missingFor = (s) => (planeReq[s] || []).filter(f => !strat[f]);

  const flash = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3200); };
  const next = () => {
    const miss = missingFor(step);
    if (miss.length) {
      flash("Set " + miss.map(f => DIAL_LABEL[f]).join(" and ") + " first — they change how we read your results.");
      const el = document.getElementById("dial-" + miss[0]); if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    setStep(s => Math.min(3, s + 1)); window.scrollTo({ top: 0, behavior: "auto" });
  };
  const back = () => { setStep(s => Math.max(0, s - 1)); window.scrollTo({ top: 0, behavior: "auto" }); };

  const commit = async () => {
    setSaving(true);
    try {
      const pa = {}; planeA.forEach(f => { pa[f.key] = f.value; });
      await api("/api/strategy", { method: "PUT", body: { strategy: strat, plane_a: pa } });
      setCommitted(true);                                  // the payoff — a quiet flourish, then land on the dashboard
      if (window.confettiBurst) window.confettiBurst({ count: 90, duration: 2000, origin: { x: 0.5, y: 0.42 } });
      setTimeout(() => nav("/"), 1400);
    } catch (e) { flash("Couldn't save — try again."); setSaving(false); }
  };

  const STEPS = [
    { k: "A", name: "Your business" }, { k: "B", name: "Your philosophy" },
    { k: "C", name: "Right now" }, { k: "R", name: "Review" }];

  return html`
    <div class="strat-flow">
      <div class="strat-rail" role="group" aria-label="Progress">
        ${STEPS.slice(0, 3).map((s, i) => html`
          <div key=${s.k} class=${"strat-seg" + (step === i ? " active" : step > i ? " done" : "")}>
            <div class="strat-bar"><i style=${{ width: step > i ? "100%" : step === i ? "50%" : "0" }}></i></div>
            <div class="strat-meta"><span class="strat-letter">${step > i ? html`<${Icon} name="check" size=${11} />` : s.k}</span><span>${s.name}</span></div>
          </div>`)}
      </div>

      ${step === 0 && html`
        <section class="strat-step">
          <div class="strat-eyebrow">Your business <span class="strat-mode confirm">Pre-filled · confirm</span></div>
          <h1 class="strat-title">Does this still describe you?</h1>
          <p class="strat-sub">We've filled these in from what we already hold. They shape who you're compared against and how we read your results — correct anything that's changed.</p>
          <div class="confirm-grid">
            ${planeA.map((f, i) => html`
              <div key=${f.key} class="confirm-row">
                <div><div class="cr-label">${f.label}</div><div class="cr-why">${f.why}</div></div>
                <div class="cr-val">
                  <span class="cr-tag">On file</span>
                  <select aria-label=${f.label} value=${f.value || ""}
                    onChange=${e => setPlaneA(p => p.map((x, j) => j === i ? { ...x, value: e.target.value } : x))}>
                    ${!f.value && html`<option value="" disabled>Select…</option>`}
                    ${(f.options || []).map(o => html`<option key=${o} value=${o}>${o}</option>`)}
                    ${f.value && !(f.options || []).includes(f.value) ? html`<option value=${f.value}>${f.value}</option>` : null}
                  </select>
                </div>
              </div>`)}
            <div class="derived-note"><${Icon} name="info" size=${15} />
              <div><b>Labour intensity is worked out for you</b> — from your sector and size, so we know how heavily each reward £ lands on your P&L. Nothing to answer here.</div></div>
          </div>
        </section>`}

      ${step === 1 && html`
        <section class="strat-step">
          <div class="strat-eyebrow">Your philosophy <span class="strat-mode choose">Your call</span></div>
          <h1 class="strat-title">The positions you've chosen</h1>
          <p class="strat-sub">These are deliberate commitments, not facts about your business — so we ask you fresh. They're what let us tell "below the market" from "below the market, on purpose."</p>
          ${planeBfields.map(f => html`<${DialCard} key=${f} field=${f} value=${strat[f]} onPick=${pick} required=${REQUIRED.includes(f)} />`)}
        </section>`}

      ${step === 2 && html`
        <section class="strat-step">
          <div class="strat-eyebrow">Right now <span class="strat-mode choose">Your call</span></div>
          <h1 class="strat-title">What you're working on this year</h1>
          <p class="strat-sub">Philosophy is your long game; this is the near term. It changes yearly, so we ask it fresh — it tunes how urgently a gap is flagged and which moves we surface first.</p>
          ${planeCfields.map(f => html`<${DialCard} key=${f} field=${f} value=${strat[f]} onPick=${pick} required=${REQUIRED.includes(f)} />`)}
        </section>`}

      ${step === 3 && html`
        <section class="strat-step">
          <div class=${"strat-done" + (committed ? " celebrating" : "")}><span class="strat-check"><${Icon} name="check" size=${22} /></span>
            <h1 class="strat-title" style=${{ textAlign: "center" }}>That's your strategy captured</h1>
            <p class="strat-sub" style=${{ margin: "var(--s2) auto 0", textAlign: "center" }}>Here's what we'll read your benchmark through. Change anything before it goes live — you can edit all of this later in Settings.</p></div>
          <${ReviewSection} title="Your business" chip="confirmed" chipCls="confirmed"
            rows=${planeA.map(f => ({ label: f.label, value: f.value || "—" }))} onEdit=${() => setStep(0)} />
          <${ReviewSection} title="Your philosophy" chip="your choices" chipCls="choices"
            rows=${planeBfields.map(f => reviewRow(f, strat))} onEdit=${() => setStep(1)} />
          <${ReviewSection} title="Right now" chip="this year" chipCls="choices"
            rows=${planeCfields.map(f => reviewRow(f, strat))} onEdit=${() => setStep(2)} />
          <p class="strat-trust"><b>These are company facts and choices, not employee data.</b> They stay at organisation level, set only by an Admin, and shape how your results are read — never what your people see.</p>
        </section>`}

      <div class="strat-footer">
        <div class="strat-footer-in">
          <div class="strat-count">${["Your business · 4 facts to confirm", "Your philosophy · 7 dials", "Right now · 4 questions", "Review your strategy"][step]}</div>
          <div class="row" style=${{ gap: "var(--s2)" }}>
            ${step > 0 && !committed && html`<button class="btn" onClick=${back}>Back</button>`}
            ${step < 3 ? html`<button class="btn primary strat-next" onClick=${next}>${step === 0 ? "Looks right" : "Next"}</button>`
              : html`<button class=${"btn primary" + (committed ? " strat-saved" : "")} disabled=${saving || committed} onClick=${commit}>${
                  committed ? html`<${Icon} name="check" size=${15} /> Saved` : saving ? "Saving…" : "Save & finish"}</button>`}
          </div>
        </div>
      </div>
      ${toast && html`<div class="strat-toast" role="status" aria-live="polite">${toast}</div>`}
    </div>`;
};

function reviewRow(field, strat) {
  const v = strat[field];
  if (field === "benefits_lead") {
    const sel = v || [];
    return { label: DIAL_LABEL[field], value: sel.length ? sel.map(x => BENEFITS.find(b => b.v === x).t).join(", ") : "Skipped — read neutrally", skipped: !sel.length };
  }
  if (!v) return { label: DIAL_LABEL[field], value: "Skipped — read neutrally", skipped: true };
  return { label: DIAL_LABEL[field], value: labelOf(field, v) };
}
function ReviewSection({ title, chip, chipCls, rows, onEdit }) {
  return html`
    <div class="review-sec">
      <div class="review-h">${title} <span class=${"review-chip " + chipCls}>${chip}</span>
        <button class="review-edit" onClick=${onEdit}>Edit</button></div>
      <div class="review-list">
        ${rows.map((r, i) => html`<div key=${i} class="review-row">
          <span class="rr-label">${r.label}</span>
          <span class=${"rr-val" + (r.skipped ? " skipped" : "")}>${r.value}</span></div>`)}
      </div>
    </div>`;
}
