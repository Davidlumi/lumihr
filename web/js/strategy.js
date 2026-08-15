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
  market: { q: 'Where do you aim to sit on pay against peers?',
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
      { v: "open", t: "Fully open", d: "Actual pay is visible", se: 'Full openness becomes a <span class="se-pill green">commitment we track</span> — we track your openness commitments against it.' } ] },
  location: { q: "Does where someone works change their pay?",
    stops: [
      { v: "local", t: "Local rates", d: "Pay follows the local area", se: 'We’ll give you <b>per-location</b> reads — local market rates matter to you.' },
      { v: "national", t: "One rate", d: "Same across the country", se: 'We’ll read you against a <b>national</b> market, one rate.' },
      { v: "agnostic", t: "Anywhere", d: "Same pay wherever you are", se: 'Per-location “below local market” signals are <span class="se-pill blue">switched off</span> — a single national read is the relevant one.' } ] },
  family: { q: "How far do you go on parental leave and caring for family?",
    stops: [
      { v: "statutory", t: "Legal minimum", d: "What the law requires", se: 'We’ll hold you to the <b>statutory</b> floor — extra spend reads as discretionary.' },
      { v: "market", t: "In line", d: "Around the same as peers", se: 'We’ll read you against the <b>market norm</b> for family benefits.' },
      { v: "over", t: "Generous", d: "More than most peers offer", se: 'A generous family position reads as <span class="se-pill green">on strategy</span> — intended, not overspend.' } ] },
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
// FIELD_STATE (2026-06-24) — three-state survey field VISIBILITY (UI-only; persistence,
// enums, the save route, the completion gate and the engine are ALL untouched).
//   "coming"  → wired in a later step, HIDE for now (drives nothing yet, so don't ask).
//   "context" → collected deliberately (board-pack narrative / future) but NOT wired to
//               surfacing, SHOW BUT LABEL honestly so the user isn't misled.
//   "live" (default) → wired, drives output, render normally (no label).
// Re-showing a "coming" field once it's wired is a ONE-LINE flip to "live".
// 2026-08-09 review: budget/acute/risk are LIVE signal re-rankers (signals.py _parts)
// — the "context" honesty labels were stale and told members the opposite.
const FIELD_STATE = { transparency: "live",
  budget_direction: "live", risk_appetite: "live", acute_pressure: "live" };
const fieldState = (f) => FIELD_STATE[f] || "live";
const shownFields = (fields) => fields.filter(f => fieldState(f) !== "coming");   // render/review only
const DIAL_LABEL = { market_position: "Market position", domain_targets: "Position by area",
  reward_mix: "Total-reward mix",
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

// ---- the capture flow: step-by-step pages in four phases (module-level so the
// document view can jump straight to the step that captures a section) ----------
const PAGES = [
  { id: "facts",      phase: 0, label: "Your business" },
  { id: "compare",    phase: 0, label: "Who you compare to" },
  { id: "phil",       phase: 1, label: "How you reward" },
  { id: "populations", phase: 1, label: "By population", opt: true },
  { id: "post",       phase: 1, label: "This year" },
  { id: "principles", phase: 2, label: "Principles", opt: true },
  { id: "commit",     phase: 2, label: "Commitments", opt: true },
  { id: "measures",   phase: 2, label: "Measures", opt: true },
  { id: "roadmap",    phase: 2, label: "Roadmap", opt: true },
  { id: "governance", phase: 2, label: "Governance", opt: true },
  { id: "review",     phase: 3, label: "Review & save" },
];
const PHASES = [
  { t: "Your business" }, { t: "How you reward" },
  { t: "Your document", note: "all optional" }, { t: "Review & save" },
];
const PAGE_IX = {}; PAGES.forEach((p, i) => { PAGE_IX[p.id] = i; });

// ---- starter libraries (2026-08-15, David: "stock answers they can select then
// modify, as well as free text"). Selecting a starter ADDS IT AS EDITABLE TEXT —
// the saved words are always the member's own (guardrail 9); these are prompts,
// not content the model authors. R9: David refines this list in his own words.
const PRINCIPLE_STARTERS = [
  "We pay for the role and the market, and we can explain every pay decision.",
  "Total reward is more than pay — we invest in benefits people actually use.",
  "We reward performance visibly, without leaving anyone behind.",
  "Fairness first: same work, same reward, checked every year.",
  "We aim to be competitive where it matters most for our people.",
  "Simple beats clever — everyone should understand how their pay works.",
  "We look after health and wellbeing before perks.",
  "Reward supports long careers here, not just this year's hire.",
];
const GOV_STMT_STARTERS = [
  "Pay ranges are shared internally; equal pay is reviewed annually.",
  "Every offer and pay change is signed off against the framework.",
  "Reward decisions are documented, benchmarked and reviewed by the board each year.",
];
const ROADMAP_STARTERS = [
  "Introduce formal salary bands", "Review family leave against the market",
  "Launch a financial-wellbeing programme", "Move the pay review to a merit matrix",
  "Publish pay ranges on job adverts", "Rebroker the benefits package",
];

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
  const measureThumb = () => {
    const wrap = stopsRef.current; if (!wrap || idx < 0) { setThumb(null); return; }
    const el = wrap.querySelectorAll(".scale-stop")[idx]; if (!el) return;
    setThumb({ left: el.offsetLeft + el.offsetWidth / 2 });   // measured centre, not a guessed %
  };
  useLayoutEffect(measureThumb, [idx, value]);
  // the px position above goes stale when the track's width changes (window
  // resize, tablet rotation, a parent reflow) — re-anchor the thumb + fill on any
  // resize so the dial never detaches from the selected stop.
  useEffect(() => {
    const wrap = stopsRef.current;
    if (!wrap || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => measureThumb());
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [idx, value]);
  const move = (e) => {
    let n;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") n = idx < 0 ? 0 : Math.min(cfg.stops.length - 1, idx + 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") n = idx < 0 ? cfg.stops.length - 1 : Math.max(0, idx - 1);
    else return;
    e.preventDefault(); onPick(cfg.stops[n].v);
    // keep focus with the selection (roving tabindex re-targets on re-render)
    requestAnimationFrame(() => {
      const el = stopsRef.current && stopsRef.current.querySelectorAll(".scale-stop")[n];
      if (el) el.focus();
    });
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
            <span class="kbd" aria-hidden="true">${cfg.stops.indexOf(s) + 1}</span>
            <span class="ot">${s.t}</span><span class="od">${s.d}</span></button>`)}
      </div>
    </div>`;
}

// ---- a single dial card (scale | cards | chips) -------------------------------
function DialCard({ field, value, onPick, required, context, extra }) {
  const sk = SCALE_FIELD[field];
  const flagged = required && !value;     // unset required → amber prompt
  const tag = null;   // Required/Optional pills retired — requirement enforced quietly at Next
  let body, se = null;
  if (sk) {
    const cfg = SCALE[sk];
    body = html`<${ScaleTrack} skey=${sk} value=${value} ariaLabel=${DIAL_LABEL[field]} onPick=${v => onPick(field, v)} />`;
    const stop = cfg.stops.find(s => s.v === value);
    if (stop && stop.se) se = stop.se;
    var q = cfg.q;
  } else if (field === "primary_objective") {
    var q = "What is pay and reward mainly for, right now?";
    body = html`<div class="dial-opts" role="radiogroup" aria-label="Primary objective"
      onKeyDown=${e => {
        if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(e.key)) return;
        e.preventDefault();
        const wrap = e.currentTarget;
        const cur = Math.max(0, OBJECTIVES.findIndex(x => x.v === value));
        const nxt = ("ArrowRight" === e.key || "ArrowDown" === e.key) ? Math.min(OBJECTIVES.length - 1, cur + 1) : Math.max(0, cur - 1);
        onPick(field, OBJECTIVES[nxt].v);
        requestAnimationFrame(() => { const el = wrap && wrap.querySelectorAll(".dial-opt")[nxt]; if (el) el.focus(); });
      }}>
      ${OBJECTIVES.map(o => html`<button key=${o.v} class=${"dial-opt" + (o.v === value ? " on" : "")}
        role="radio" aria-checked=${o.v === value}
        tabindex=${o.v === value || (!value && o === OBJECTIVES[0]) ? 0 : -1}
        onClick=${() => onPick(field, o.v)}>
        <span class="kbd" aria-hidden="true">${OBJECTIVES.indexOf(o) + 1}</span>
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
    <div class=${"dial-card" + (flagged ? " flagged" : "")} id=${"dial-" + field} aria-invalid=${flagged ? "true" : undefined}>
      ${flagged ? html`<span class="sr-only">Required — choose a position to continue.</span>` : null}
      <div class="dial-head">
        <span class=${"dial-roundel" + (flagged ? " flagged" : "")}><${Icon} name=${DIAL_ICON[field] || "target"} size=${16} /></span>
        <div>
          ${/* the "Context" title chip dropped 2026-07-07 — it duplicated the clearer
                "Kept for context — doesn't shape your signals yet" note below the dial. */ ""}
          <div class="dial-title">${DIAL_LABEL[field]} ${tag}</div>
          <div class="dial-q" dangerouslySetInnerHTML=${{ __html: q }}></div>
        </div>
      </div>
      ${body}
      ${se && !context && html`<div class="signal-effect"><span class="se-eye"><${Icon} name="sparkle" size=${14} /></span>
        <span class="se-text" dangerouslySetInnerHTML=${{ __html: se }}></span></div>`}
      ${context && html`<div class="signal-effect strat-ctx-note"><span class="se-eye"><${Icon} name="info" size=${14} /></span>
        <span class="se-text">Kept for context — this doesn't shape your signals yet.</span></div>`}
      ${extra || null}
    </div>`;
}
const DIAL_ICON = { market_position: "target", reward_mix: "coins", pay_for_performance: "bar-chart",
  transparency: "search", location_approach: "compass", benefits_lead: "heart", family_position: "users",
  primary_objective: "target", budget_direction: "trending-up", acute_pressure: "zap", risk_appetite: "shield" };

// Per-domain market-position overrides (step-3 layer 2) — Option A "global + reveal" (David
// 2026-06-24): the global market_position dial stays the default; this reveals an override
// ScaleTrack per COMPETITIVE domain (config-derived list from /api/strategy, never hardcoded),
// only on opt-in. An UNSET domain sends NO key → inherits the global aim (layer-1 degrade); a
// "Clear" deletes the key. Optional — never a required gate. Writes strat.domain_targets only.
function DomainOverrides({ domains, targets, globalValue, onSet, standalone = false }) {
  // standalone (2026-08-14, R3 promoted stage): the panel IS the stage — always open,
  // no reveal chrome. The embedded reveal form is kept for any other call site.
  const [open, setOpen] = useState(standalone);
  if (!domains || !domains.length) return null;
  const t = targets || {};
  const n = Object.keys(t).length;
  return html`
    <div class="dom-ov">
      ${!standalone && html`<button type="button" class=${"dom-reveal" + (open ? " open" : "")} aria-expanded=${open} onClick=${() => setOpen(o => !o)}>
        <${Icon} name="sliders" size=${13} /> Refine by area${n ? html` · <b>${n}</b> set` : ""}
        <span class="dom-chev">${open ? "▾" : "▸"}</span></button>`}
      ${open && html`<div class="dom-panel">
        ${!standalone && html`<p class="dom-hint">Set a different aim for any area — the rest follow your overall position${globalValue ? html` (<b>${labelOf("market_position", globalValue)}</b>)` : ""}.</p>`}
        ${domains.map(dom => html`<div key=${dom} class="dom-row">
          <div class="dom-row-head"><span class="dom-name">${dom}</span>
            ${t[dom] ? html`<button type="button" class="dom-clear" onClick=${() => onSet(dom, null)}>Clear · follow overall</button>`
                     : html`<span class="dom-inherit">follows overall</span>`}</div>
          <${ScaleTrack} skey="market" value=${t[dom]} ariaLabel=${dom + " market position"} onPick=${v => onSet(dom, v)} />
        </div>`)}
      </div>`}
    </div>`;
}

// ---- the strategy DOCUMENT — the completed strategy as a typeset deliverable ----
// One sheet, navy masthead, three numbered sections: the stance in authored prose,
// position against intent (the live centrepiece), and the positions ledger.
const SD_STANCE = { lag: "below market", match: "on market", lead: "above market" };
const SD_IDX = { lag: 0, match: 1, lead: 2, below: 0, on: 1, above: 2, at: 1 };
const SD_MIX = { cash: "is led by base pay", balanced: "balances pay and benefits", benefits: "leads on benefits over pay" };
const SD_P4P = { egal: "pay is held close across the board", moderate: "performance earns a measured premium", strong: "top performers are paid well above the rest" };
const SD_TRANS = { closed: "held privately", ranges: "shared as ranges", open: "fully open" };
const SD_FAM = { statutory: "set at the statutory floor", market: "in line with the market", over: "deliberately generous" };
const SD_OBJ = { attract: "winning talent", retain: "holding on to the people you have", cost: "cost discipline", compliance: "getting the foundations right", hold: "holding steady" };
const SD_DRIVES = {
  market_position: "The aim every position is read against.",
  reward_mix: "How pay and package figures are weighed together.",
  pay_for_performance: "The pay-spread shape read as intended.",
  transparency: "Which openness practices count as commitments.",
  location_approach: "Whether local pay markets are read separately.",
  benefits_lead: "The benefit areas read as deliberate leads.",
  family_position: "The family-support bar you are held to.",
  primary_objective: "What your signals surface first.",
  budget_direction: "Weights saving or investment signals with the budget's direction.",
  acute_pressure: "Sharpens which signal lenses surface first this year.",
  risk_appetite: "Weights early-mover practice signals up or down.",
};

function sdStance(strat, orgName) {
  // one idea per sentence — assembled prose must read authored, never jammed
  const parts = [];
  if (strat.market_position) {
    const n = Object.keys(strat.domain_targets || {}).length;
    parts.push(orgName + " aims to sit " + SD_STANCE[strat.market_position] + " on reward."
      + (n ? " " + (n === 1 ? "One area is set differently." : n + " areas are set differently.") : ""));
  }
  const pkg = [];
  if (strat.reward_mix && SD_MIX[strat.reward_mix]) pkg.push("The package " + SD_MIX[strat.reward_mix]);
  if (strat.pay_for_performance && SD_P4P[strat.pay_for_performance]) pkg.push(SD_P4P[strat.pay_for_performance]);
  if (pkg.length) parts.push(pkg.join("; ") + ".");
  const s2 = [];
  if (strat.transparency && SD_TRANS[strat.transparency]) s2.push("Pay information is " + SD_TRANS[strat.transparency]);
  if (strat.family_position && SD_FAM[strat.family_position]) s2.push("family support is " + SD_FAM[strat.family_position]);
  if (s2.length) parts.push(s2.join("; ") + ".");
  if (strat.primary_objective && SD_OBJ[strat.primary_objective]) parts.push("The focus this year is " + SD_OBJ[strat.primary_objective] + ".");
  return parts;
}

// aim (a ZONE, shaded navy) vs position (one dot at the true percentile).
// The three zone extents follow the real market band (P35-65) on an 8-92% track;
// on aim = the dot sits inside the shaded stretch. One band, one dot, one chip.
// zone extents DERIVED from the live market band through the same mapper as the
// dot — zone, dot and alignment chip cannot disagree (2026-08-09 persona review:
// a hardcoded 58.4 drew the aim zone to P60 while alignment read to P65)
const sdPX = (p) => 8 + Math.max(0, Math.min(100, p)) * 0.84;
const sdBand = () => (typeof window !== "undefined" && window.MARKET_BAND) || [35, 65];
const SD_ZONES_F = () => { const [lo, hi] = sdBand(); return [[8, sdPX(lo)], [sdPX(lo), sdPX(hi)], [sdPX(hi), 92]]; };
const sdPctlX = (p) => sdPX(p) + "%";
function SdAxis({ intent, actual, pctl, align }) {
  const ii = SD_IDX[intent], ai = SD_IDX[actual];
  const SD_ZONES = SD_ZONES_F();
  const dotX = (pctl != null && ai != null) ? sdPctlX(pctl)
    : (ai != null ? ((SD_ZONES[ai][0] + SD_ZONES[ai][1]) / 2) + "%" : null);
  // dot colour follows ALIGNMENT (RAG since 2026-08-13, matching the overview glyph):
  // on=green / below=amber / above=red — the page reads intent, not raw market position
  const acls = " a-" + (align || "off");
  return html`<span class="sd-axis" aria-hidden="true">
    ${SD_ZONES.map(([l, r], i) => html`<span key=${i}
      class=${"sd-zone" + (i === ii ? " aimed" : "")}
      style=${{ left: l + "%", width: (r - l) + "%" }}></span>`)}
    ${dotX && html`<span class=${"sd-mark actual" + acls} style=${{ left: dotX }} title="Your position"></span>`}
  </span>`;
}

// ---- Total Reward Strategy document sections (2026-08-15: READ-ONLY) ---------
// The document PRESENTS; the survey CAPTURES. Every field is captured step-by-step
// in the wizard, so these sections carry NO inline editors — two write paths for the
// same field was the mess (David 2026-08-15: "it is all still showing at the end").
// An unstated section says so plainly and links an Admin to the step that captures it.
const CONSTRAINT_LABEL = { affordability: "Affordability", collective_bargaining: "Collective bargaining",
  statutory_pressure: "Statutory / regulatory pressure", headcount_change: "Headcount change",
  system_change: "Systems / payroll change", other: "Other" };
const CADENCE_LABEL = { annual: "Annually", twice_yearly: "Twice a year", quarterly: "Quarterly", ad_hoc: "Ad hoc" };
const HORIZON_LABEL = { this_cycle: "This cycle", next_cycle: "Next cycle", multi_cycle: "Multi-cycle" };

function SdDocSec({ id, icon, title, note, isSet, canEdit, onAdd, children }) {
  return html`
    <section class="sd-sec sdx-card" id=${id}>
      <div class="sdx-sechead">
        <span class=${"sdx-ico" + (isSet ? " on" : "")}><${Icon} name=${icon} size=${15} /></span>
        <h3 class="sdx-title">${title}</h3>
        <span class=${"sdx-state " + (isSet ? "set" : "empty")}>${isSet ? "Stated" : "Not yet stated"}</span>
      </div>
      ${note ? html`<p class="sd-note sd-ex-cap">${note}</p>` : null}
      ${isSet ? children : html`
        <p class="sd-stance sd-unstated">Not yet stated${canEdit ? " — optional, and the document is honest about it" : ""}.</p>
        ${canEdit && onAdd ? html`<button class="sdx-addlink no-print" onClick=${onAdd}>
          <${Icon} name="pencil" size=${12} /> Add this in the strategy set-up</button>` : null}`}
    </section>`;
}

function SdDocSections({ data, canEdit, onEdit, which }) {
  // `which` renders only the named sections, so the document groups them under the
  // brief's three-part spine (Intent / Position / Delivery). onEdit(pageId) jumps
  // the wizard straight to the step that captures that section.
  const show = (k) => !which || which.includes(k);
  const doc = data.document || {};
  const gov = doc.reward_governance || {};
  const cons = doc.constraints || {};
  const seg = doc.segments || {};
  const cm = doc.commitments || {};
  const wb = (cm["Wellbeing"] || {}).metric_ids || [];
  const gvStmt = (cm["Governance & Transparency"] || {}).statement || "";
  // metric titles for committed provisions + measures (lazy; ids alone read as noise)
  const [titles, setTitles] = useState(null);
  useEffect(() => {
    if (titles !== null || (!wb.length && !(doc.measures || []).length)) return;
    api("/api/strategy/measure-options")
      .then(r => { const m = {}; (r.options || []).forEach(o => { m[o.id] = o.title; }); setTitles(m); })
      .catch(() => setTitles({}));
  }, [wb.length, (doc.measures || []).length]);
  const mTitle = (qid) => (titles && titles[qid]) || qid;

  return html`
    <${React.Fragment}>
      ${show("principles") && html`<${SdDocSec} id="sdx-principles" icon="star" title="Our reward principles"
        isSet=${(doc.principles || []).length > 0} canEdit=${canEdit} onAdd=${() => onEdit("principles")}>
        <ol class="sd-principles">${(doc.principles || []).map((p, i) => html`<li key=${i}>${p}</li>`)}</ol>
        ${seg.differentiated ? html`<p class="sd-note">Pay is deliberately differentiated for: <b>${(seg.segments || []).join(", ") || "named segments"}</b>.</p>` : null}
      <//>`}

      ${show("comparator") && html`<${SdDocSec} id="sdx-comparator" icon="users" title="Who we compare ourselves to"
        note="The comparator in words — figures live in the benchmark, not here."
        isSet=${true} canEdit=${canEdit} onAdd=${() => onEdit("compare")}>
        <p class="sd-stance">${orgCompareWords(null, doc)}</p>
      <//>`}

      ${show("constraints") && html`<${SdDocSec} id="sdx-constraints" icon="anchor" title="What constrains us"
        isSet=${!!((cons.selected || []).length || cons.notes)} canEdit=${canEdit} onAdd=${() => onEdit("compare")}>
        <p class="sd-stance">${(cons.selected || []).map(c => CONSTRAINT_LABEL[c] || c).join(" · ")}${cons.notes ? (((cons.selected || []).length ? " — " : "") + cons.notes) : ""}</p>
      <//>`}

      ${show("governance") && html`<${SdDocSec} id="sdx-governance" icon="shield" title="How reward is governed"
        isSet=${!!Object.keys(gov).length} canEdit=${canEdit} onAdd=${() => onEdit("governance")}>
        <div class="sd-ledger">
          ${[["Owner", gov.owner], ["Approved by", gov.approver],
             ["Review cadence", gov.review_cadence && (CADENCE_LABEL[gov.review_cadence] || gov.review_cadence)],
             ["Effective date", gov.effective_date]].filter(r => r[1]).map(([k, v]) => html`
            <div key=${k} class="sd-led-row"><span class="sd-led-name">${k}</span><span class="sd-led-val">${v}</span><span class="sd-led-why"></span></div>`)}
        </div>
      <//>`}

      ${show("commitments") && html`<${SdDocSec} id="sdx-commitments" icon="heart" title="What we offer and how we operate"
        note="Wellbeing is measured by what's offered, not a market rate; governance by how you operate — stated here as commitments, never positions."
        isSet=${!!(wb.length || gvStmt)} canEdit=${canEdit} onAdd=${() => onEdit("commit")}>
        ${wb.length ? html`<p class="sd-stance"><b>Wellbeing — we offer:</b> ${wb.map(mTitle).join(" · ")}</p>` : null}
        ${gvStmt ? html`<p class="sd-stance"><b>Governance —</b> ${gvStmt}</p>` : null}
      <//>`}

      ${show("populations") && html`<${SdDocSec} id="sdx-populations" icon="layers" title="Position by employee population"
        note="Stated positions for named groups. lumi holds no executive pay data, so these are never scored against the benchmark."
        isSet=${(doc.population_targets || []).length > 0} canEdit=${canEdit} onAdd=${() => onEdit("populations")}>
        <div class="sd-ledger">
          ${(doc.population_targets || []).map(p => html`
            <div key=${p.label} class="sd-led-row"><span class="sd-led-name">${p.label}</span>
              <span class="sd-led-val">${SD_STANCE[p.position] || "—"}</span>
              <span class="sd-led-why">${p.note || ""}</span></div>`)}
        </div>
      <//>`}

      ${show("measures") && html`<${SdDocSec} id="sdx-measures" icon="table" title="How we'll know it's working"
        note="Measures are metrics lumi already measures — the review reports them against your comparator."
        isSet=${(doc.measures || []).length > 0} canEdit=${canEdit} onAdd=${() => onEdit("measures")}>
        <div class="sd-ledger">
          ${(doc.measures || []).map(m => { const o = m && m.id ? m : { id: m }; return html`
            <div key=${o.id} class="sd-led-row">
              <span class="sd-led-name">${mTitle(o.id)}</span>
              <span class="sd-led-val">${o.target ? "→ " + o.target : "No target set"}${o.baseline ? html` <span class="sd-led-sub">· from ${o.baseline}</span>` : ""}</span>
              <span class="sd-led-why">${o.owner ? "Owner: " + o.owner : ""}</span>
            </div>`; })}
        </div>
      <//>`}

      ${show("roadmap") && html`<${SdDocSec} id="sdx-roadmap" icon="clock" title="What changes this year"
        isSet=${(doc.roadmap || []).length > 0} canEdit=${canEdit} onAdd=${() => onEdit("roadmap")}>
        <ol class="sd-principles">${(doc.roadmap || []).map((r, i) => html`<li key=${i}>${r.title}${r.horizon ? html` <span class="sd-doc-meta">· ${HORIZON_LABEL[r.horizon] || r.horizon}</span>` : ""}</li>`)}</ol>
      <//>`}
    <//>`;
}

function orgCompareWords(me, doc) {
  // R1: the comparator IN WORDS, never a benchmark table
  const label = doc.comparator_label || "All peers";
  if (label === "All peers") return "We compare ourselves to UK organisations across the lumi peer pool.";
  const cut = doc.comparator_cut || "";
  if (cut.startsWith("industry::")) return "We compare ourselves to UK organisations in our sector — " + label + ".";
  if (cut.startsWith("fte_band::")) return "We compare ourselves to UK organisations of similar size (" + label + " employees).";
  return "We compare ourselves to our saved peer group — " + label + ".";
}

function StrategyView({ me, data, strat, onEdit, canEdit = true, onReload }) {
  const [hero, setHero] = useState(null);
  // anchor the live position read to the ORG DEFAULT peer group — the same basis as the
  // Overview chip and Signals (default-cut anchoring doctrine). A bare /api/overview here
  // read all-peers, so this page said "5 of 8 off aim" beside an Overview saying "1 off
  // aim" (pre-prod audit 2026-08-12).
  const defCut = (me && me.org && me.org.signal_peer_cut) || "all";
  useEffect(() => {
    let qs = "";
    if (defCut && defCut !== "all") {
      const [dim, value] = defCut === "twin" ? ["twin", null] : defCut.split("::");
      qs = "?cut=" + encodeURIComponent(dim) + (value ? "&cut_value=" + encodeURIComponent(value) : "");
    }
    apiCached("/api/overview" + qs).then(o => setHero(o.hero || null)).catch(() => setHero(null));
  }, [defCut]);
  // lumi's reading — the grounded AI overlay. undefined = hidden (AI off / no access),
  // null = available but not generated, object = the three parts.
  const [ai, setAi] = useState(undefined);
  const [aiBusy, setAiBusy] = useState(false);
  const [aiDark, setAiDark] = useState(false);   // 403 = switched off for the platform
  useEffect(() => {
    api("/api/strategy/commentary", { method: "POST", body: { peek: true } })
      .then(r => setAi(r.parts || null)).catch(e => { setAi(undefined); if (e && e.status === 403) setAiDark(true); });
  }, []);
  const genAi = async (force) => {
    setAiBusy(true);
    try { const r = await api("/api/strategy/commentary", { method: "POST", body: force ? { force: true } : {} }); setAi(r.parts); }
    catch (e) { toast(e.message, "error"); }
    setAiBusy(false);
  };
  const orgName = (me.org && me.org.name) || "Your organisation";
  const stance = sdStance(strat, orgName);
  // R1 (2026-08-14): the exported document carries NO peer figures by default — the
  // live position exhibit is an optional evidence block, off in print until opted in.
  // R1 inverted (2026-08-15, reward-director review): the EVIDENCE belongs in the
  // approved document; the AI reading never prints. A board paper of assertions with
  // the data removed was exactly backwards.
  const [evidenceInPrint, setEvidenceInPrint] = useState(true);
  const [approving, setApproving] = useState(false);
  const [apOpen, setApOpen] = useState(false);
  const [apForm, setApForm] = useState({});
  const [versions, setVersions] = useState(null);
  const [showVers, setShowVers] = useState(false);
  const ver = data.version || null;
  const sub = data.submitted || null;
  const canApprove = data.can_approve;
  const doc0 = data.document || {};
  const cm0 = doc0.commitments || {};
  // what is empty right now — shown BEFORE approving, never discovered after
  const unstated = [
    ["Principles", (doc0.principles || []).length],
    ["Comparator", doc0.comparator_cut != null ? 1 : 0],
    ["Constraints", ((doc0.constraints || {}).selected || []).length || ((doc0.constraints || {}).notes ? 1 : 0)],
    ["Governance", Object.keys(doc0.reward_governance || {}).length],
    ["Commitments", (((cm0["Wellbeing"] || {}).metric_ids) || []).length || ((cm0["Governance & Transparency"] || {}).statement ? 1 : 0)],
    ["Measures", (doc0.measures || []).length],
    ["Roadmap", (doc0.roadmap || []).length],
    ["Population positions", (doc0.population_targets || []).length],
  ].filter(r => !r[1]).map(r => r[0]);
  const loadVersions = () => { setShowVers(v => !v);
    if (versions === null) api("/api/strategy/versions").then(r => setVersions(r.versions || [])).catch(() => setVersions([])); };
  const sendForApproval = async () => {
    try { await api("/api/strategy/submit", { method: "POST", body: {} }); onReload && onReload();
      toast("Sent for approval — an Admin can now sign it off."); }
    catch (e) { toast(e && e.message || "Couldn't send.", "error"); }
  };
  const approve = async () => {
    setApproving(true);
    try {
      await api("/api/strategy/approve", { method: "POST", body: { ...apForm, confirmed: true } });
      setApOpen(false); setApForm({}); setVersions(null); onReload && onReload();
      toast("Approved — this version now stands.");
    } catch (e) { toast(e && e.message || "Couldn't approve.", "error"); }
    setApproving(false);
  };
  const doms = (hero && hero.domains || []).filter(d => d.target);
  const offAim = doms.filter(d => d.target.alignment && d.target.alignment !== "on_target");
  const when = data.completed_at ? fmtDate(data.completed_at) : null;
  const aimRead = (d) => {
    // the server's alignment (positions.py _market_target) is the single source of truth
    const al = d.target.alignment;
    if (al === "on_target") return { t: "On strategy", cls: "ok" };
    if (al === "ahead") return { t: "Above strategy", cls: "ahead" };
    if (al === "behind") return { t: "Below strategy", cls: "behind" };
    return { t: "—", cls: "" };
  };
  const philosophy = ["market_position", "reward_mix", "pay_for_performance", "transparency", "location_approach", "benefits_lead", "family_position"];
  const valOf = (f) => f === "benefits_lead"
    ? ((strat.benefits_lead || []).length ? "Leads on " + (strat.benefits_lead || []).map(x => (BENEFITS.find(b => b.v === x) || {}).t.toLowerCase()).join(", ") : null)
    : (strat[f] ? labelOf(f, strat[f]) : null);
  const ctxBits = [];   // every dial is live post-2026-08-09 — the demoted strip retired
  // ---- 2026-08-15 redesign: defined sections + progress ----
  // The document's section map drives BOTH the jump-nav (state dots) and the
  // completeness meter. `live` sections read the benchmark and never count as
  // "to write"; the meter counts the eight authored sections only.
  const _doc = data.document || {};
  const _cm = _doc.commitments || {};
  const SECTIONS = [
    { id: "sdx-stance", icon: "flag", label: "The stance", set: !!data.completed_at, part: 1 },
    { id: "sdx-principles", icon: "star", label: "Principles", set: (_doc.principles || []).length > 0, part: 1 },
    { id: "sdx-comparator", icon: "users", label: "Comparator", set: _doc.comparator_cut != null, part: 1 },
    { id: "sdx-constraints", icon: "anchor", label: "Constraints", set: !!(((_doc.constraints || {}).selected || []).length || (_doc.constraints || {}).notes), part: 1 },
    { id: "sdx-governance", icon: "shield", label: "Governance", set: !!Object.keys(_doc.reward_governance || {}).length, part: 1 },
    { id: "sdx-exhibit", icon: "target", label: "Position vs intent", set: doms.length > 0, part: 2, live: true },
    { id: "sdx-positions", icon: "sliders", label: "The positions", set: !!data.completed_at, part: 2, live: true },
    { id: "sdx-populations", icon: "layers", label: "Populations", set: (_doc.population_targets || []).length > 0, part: 2 },
    { id: "sdx-commitments", icon: "heart", label: "Commitments", set: !!((((_cm["Wellbeing"] || {}).metric_ids) || []).length || (_cm["Governance & Transparency"] || {}).statement), part: 2 },
    { id: "sdx-measures", icon: "table", label: "Measures", set: (_doc.measures || []).length > 0, part: 3 },
    { id: "sdx-roadmap", icon: "clock", label: "Roadmap", set: (_doc.roadmap || []).length > 0, part: 3 },
  ];
  const METER = SECTIONS.filter(s => !s.live);
  const statedN = METER.filter(s => s.set).length;
  const jump = (id) => { const el = document.getElementById(id); if (el) el.scrollIntoView({ behavior: "smooth", block: "start" }); };
  const SecHead = ({ icon, title, on = true, chip = null }) => html`
    <div class="sdx-sechead">
      <span class=${"sdx-ico" + (on ? " on" : "")}><${Icon} name=${icon} size=${15} /></span>
      <h3 class="sdx-title">${title}</h3>
      ${chip}
    </div>`;
  return html`
    <div class="sd-wrap sdx">
      ${apOpen ? html`
        <div class="sdx-modal no-print" role="dialog" aria-modal="true" aria-label="Record the approval">
          <div class="sdx-modal-card">
            <h3 class="sdx-title">Record the approval</h3>
            <p class="sd-note">This becomes the governance record on the document — and the version your reward review cites. It is permanent; a later approval supersedes it.</p>
            ${unstated.length ? html`
              <div class="sdw-missing" style=${{ marginBottom: "var(--s3)" }}>
                <${Icon} name="info" size=${15} />
                <div><b>${unstated.length} section${unstated.length === 1 ? " is" : "s are"} unstated</b> — ${unstated.join(", ")}.
                  You can still approve; the version records exactly what was and wasn't stated.</div>
              </div>` : null}
            <div class="sd-doc-grid2">
              <label>Approved by<input class="ctl" maxlength="80" placeholder="e.g. Remuneration Committee, or the CEO"
                value=${apForm.approver_body || ""} onInput=${e => setApForm(f => ({ ...f, approver_body: e.target.value }))} /></label>
              <label>Date they approved it<input class="ctl" type="date" value=${apForm.approval_date || ""}
                onInput=${e => setApForm(f => ({ ...f, approval_date: e.target.value }))} /></label>
              <label>Effective from<input class="ctl" type="date" value=${apForm.effective_date || ""}
                onInput=${e => setApForm(f => ({ ...f, effective_date: e.target.value }))} /></label>
              <label>Next review<input class="ctl" type="date" value=${apForm.next_review || ""}
                onInput=${e => setApForm(f => ({ ...f, next_review: e.target.value }))} /></label>
            </div>
            ${sub ? html`<p class="sd-note">Drafted by <b>${sub.by}</b> — recorded on the version alongside your approval.</p>` : null}
            <div class="sd-doc-edfoot">
              <button class="btn primary" disabled=${approving || !(apForm.approver_body || "").trim()} onClick=${approve}>
                ${approving ? "Recording…" : "Confirm approval"}</button>
              <button class="btn quiet" disabled=${approving} onClick=${() => setApOpen(false)}>Cancel</button>
            </div>
          </div>
        </div>` : null}
      ${/* ---- hero: identity + status + progress + actions (screen only) ---- */ ""}
      <div class="sdx-hero no-print">
        <div class="sdx-hero-main">
          <div class="sd-eyebrow sdx-eyebrow">Reward strategy</div>
          <h1 class="sdx-org">${orgName}</h1>
          <div class="sdx-chips">
            ${ver ? html`<span class="sdx-chip ok"><${Icon} name="check" size=${12} /> Version ${ver.version} · approved ${fmtDate(ver.approved_at)}</span>`
                  : html`<span class="sdx-chip draft">Draft — not yet approved</span>`}
            ${ver && ver.dirty ? html`<span class="sdx-chip warn">edits since approval</span>` : null}
            ${when ? html`<span class="sdx-chip">Captured ${when}</span>` : null}
            ${sub ? html`<span class="sdx-chip warn">Awaiting approval · sent by ${sub.by}</span>` : null}
            ${ver ? html`<button class="sdx-chip sdx-chip-btn no-print" onClick=${loadVersions}>
              ${showVers ? "Hide" : "Version history"}</button>` : null}
          </div>
          ${showVers ? html`<div class="sdx-vers no-print">
            ${versions === null ? html`<p class="sd-note">Loading…</p>`
              : versions.length ? versions.map(v => html`
                <div key=${v.version} class=${"sdx-ver" + (v.status === "approved" ? " on" : "")}>
                  <b>v${v.version}</b> ${v.status === "approved" ? "current" : "superseded"}
                  · approved by <b>${v.approver_body || v.approved_by}</b>${v.approval_date ? " on " + v.approval_date : ""}
                  ${v.effective_date ? html` · effective ${v.effective_date}` : ""}
                  ${v.next_review ? html` · next review ${v.next_review}` : ""}
                  ${v.submitted_by ? html` · drafted by ${v.submitted_by}` : ""}
                  ${(v.unstated || []).length ? html`<span class="sdx-ver-un">${v.unstated.length} section${v.unstated.length === 1 ? "" : "s"} unstated at approval</span>` : null}
                </div>`)
              : html`<p class="sd-note">No approved versions yet.</p>`}
          </div>` : null}
        </div>
        <div class="sdx-hero-side">
          <div class="sdx-actions">
            ${canEdit ? html`<button class="btn primary" onClick=${() => onEdit()}><${Icon} name="pencil" size=${13} /> Edit strategy</button>` : null}
            ${canEdit && !canApprove && !sub ? html`<button class="btn" onClick=${sendForApproval}
              title="Hand this to an Admin to sign off.">Send for approval</button>` : null}
            ${canApprove ? html`<button class="btn" disabled=${approving} onClick=${() => setApOpen(true)}
              title="Record the approval — who approved it, when, and from when it applies.">
              ${ver ? "Approve v" + (ver.version + 1) : "Approve v1"}</button>` : null}
            <button class="btn" onClick=${() => { const t = document.title; document.title = "lumi — " + orgName + " — Reward strategy — " + fmtDate(); window.print(); document.title = t; }}><${Icon} name="download" size=${14} /> Print / PDF</button>
          </div>
          <div class="sdx-meter" role="img" aria-label=${"Document " + statedN + " of " + METER.length + " sections stated"}>
            <div class="sdx-meter-line"><b>${statedN} of ${METER.length}</b> sections stated</div>
            <div class="sdx-meter-bar"><i style=${{ width: (100 * statedN / METER.length) + "%" }}></i></div>
          </div>
          <label class="sd-evi-toggle" title="Your position against intent, with its peer group named. Untick for a words-only document.">
            <input type="checkbox" checked=${evidenceInPrint} onChange=${e => setEvidenceInPrint(e.target.checked)} />
            Include the evidence exhibit in the export</label>
        </div>
      </div>
      ${/* ---- section jump-nav with state dots (screen only) ---- */ ""}
      <nav class="sdx-nav no-print" aria-label="Document sections">
        ${SECTIONS.map(s => html`<button key=${s.id} class="sdx-nav-chip" onClick=${() => jump(s.id)}>
          <span class=${"sdx-dot" + (s.set ? " on" : "")}></span>${s.label}</button>`)}
      </nav>
      <div class="strat-pdf-head" aria-hidden="true"><b>lumi</b> · Reward strategy · ${orgName}${when ? " · captured " + when : ""} · generated ${fmtDate()}</div>
      <article class="sd-doc sdx-doc">
        <header class="sd-mast sdx-printmast">
          <div>
            <div class="sd-eyebrow">Reward strategy</div>
            <div class="sd-org">${orgName}</div>
          </div>
          <div class="sd-mast-meta">
            ${ver ? html`<div>Version <b>${ver.version}</b> · approved by <b>${ver.approver_body || ver.approved_by}</b>${ver.approval_date ? " on " + ver.approval_date : " " + fmtDate(ver.approved_at)}${ver.dirty ? html` · <span class="sd-dirty">edits since approval</span>` : ""}</div>
                          ${ver.effective_date ? html`<div>Effective ${ver.effective_date}${ver.next_review ? " · next review " + ver.next_review : ""}</div>` : null}`
                  : html`<div><span class="sd-dirty">Draft — not yet approved</span></div>`}
            ${when && html`<div>Captured <b>${when}</b></div>`}
            <div>Set by your Admins · held in lumi</div>
          </div>
        </header>

        <div class="sdx-part"><span>Part 1</span> Intent — what we say</div>

        <section class="sd-sec sdx-card" id="sdx-stance">
          <${SecHead} icon="flag" title="The stance" chip=${html`<span class="sdx-state live">From your dials</span>`} />
          ${stance.length ? stance.map((s, i) => html`<p key=${i} class=${"sd-stance" + (i === 0 ? " lead" : "")}>${s}</p>`)
            : html`<p class="sd-stance">No positions set yet — your benchmark is read neutrally.</p>`}
          <div class="sd-note">Below or above market here is a choice, not a verdict — lumi reads your numbers through it.</div>
        </section>

        <${SdDocSections} data=${data} canEdit=${canEdit} onEdit=${onEdit}
          which=${["principles", "comparator", "constraints", "governance"]} />

        <div class="sdx-part"><span>Part 2</span> Position — what the data shows</div>

        ${hero === null ? html`
        <section class="sd-sec sdx-card" id="sdx-exhibit">
          <${SecHead} icon="target" title="Position against intent" />
          <div class="sd-note">Reading your live position…</div>
        </section>` : doms.length ? html`
        <section class=${"sd-sec sdx-card" + (evidenceInPrint ? "" : " no-print")} id="sdx-exhibit">
          <${SecHead} icon="target" title="Position against intent"
            chip=${html`<span class="sdx-state live">${offAim.length ? offAim.length + " of " + doms.length + " off strategy" : "all on strategy"} · live</span>`} />
          <p class="sd-note sd-ex-cap">Each row places your live benchmark against where you aim to sit. The shaded band is your strategy; the dot is where you actually land. Inside the band is on strategy.</p>
          <div class="sd-ex-row sd-ex-head" aria-hidden="true">
            <span class="sd-axis-key"><span class="sd-zone-swatch"></span> your strategy <span class="sd-mark actual"></span> your position</span>
            <span class="sd-axis sd-axis-labels">${SD_ZONES_F().map(([l, r], i) => html`<i key=${i} style=${{ left: ((l + r) / 2) + "%" }}>${["below", "on market", "above"][i]}</i>`)}</span>
            <span></span>
          </div>
          <div class="sd-exhibit">
            ${doms.map(d => { const r = aimRead(d); return html`
              <a key=${d.name} class="sd-ex-row" href=${"#/category/" + encodeURIComponent(d.name)}>
                <span class="sd-ex-name">${d.name}${Object.keys(strat.domain_targets || {}).some(k => d.name === k || d.name.startsWith(k)) ? html` <span class="sd-ex-ov" title="This area has its own aim, set separately from your global stance.">refined aim</span>` : ""}</span>
                <span class="sr-only">aim ${SD_STANCE[d.target.stance] || "not set"}, position ${d.position && d.position.verdict ? (d.position.verdict === "at" ? "on market" : d.position.verdict + " market") : "not read yet"}.</span>
                <${SdAxis} intent=${d.target.stance} actual=${d.position && d.position.verdict} pctl=${d.position && d.position.depth_pctl} align=${d.target.alignment} />
                <span class=${"sd-ex-read " + r.cls}>${r.t}</span>
              </a>`; })}
          </div>
        </section>` : html`
        <section class="sd-sec sdx-card" id="sdx-exhibit">
          <${SecHead} icon="target" title="Position against intent" on=${false} />
          <div class="sd-note">Aim-vs-position appears once your benchmark unlocks.</div>
        </section>`}

        <section class="sd-sec sdx-card" id="sdx-positions">
          <${SecHead} icon="sliders" title="The positions" chip=${html`<span class="sdx-state live">From your dials</span>`} />
          <div class="sd-ledger">
            ${philosophy.map(f => { const v = valOf(f); return html`
              <div key=${f} class=${"sd-led-row" + (v ? "" : " unset")}>
                <span class="sd-led-name">${DIAL_LABEL[f]}</span>
                <span class="sd-led-val">${v || "Not set"}${f === "market_position" && Object.keys(strat.domain_targets || {}).length ? html` <span class="sd-led-sub">· ${Object.keys(strat.domain_targets || {}).length} area${Object.keys(strat.domain_targets || {}).length === 1 ? "" : "s"} refined</span>` : ""}</span>
                <span class="sd-led-why">${v ? SD_DRIVES[f] : "Read neutrally."}</span>
              </div>`; })}
            ${["primary_objective", "budget_direction", "acute_pressure", "risk_appetite"].map(f => html`
            <div key=${f} class=${"sd-led-row" + (strat[f] ? "" : " unset")}>
              <span class="sd-led-name">${DIAL_LABEL[f]}</span>
              <span class="sd-led-val">${strat[f] ? labelOf(f, strat[f]) : "Not set"}</span>
              <span class="sd-led-why">${strat[f] ? SD_DRIVES[f] : "Read neutrally."}</span>
            </div>`)}
          </div>
          ${ctxBits.length ? html`<div class="sd-ctx">Noted for context — ${ctxBits.join(" · ")}</div>` : null}
        </section>

        <${SdDocSections} data=${data} canEdit=${canEdit} onEdit=${onEdit}
          which=${["populations", "commitments"]} />

        <div class="sdx-part"><span>Part 3</span> Delivery — how we'll run it</div>

        <${SdDocSections} data=${data} canEdit=${canEdit} onEdit=${onEdit}
          which=${["measures", "roadmap"]} />

        ${ai === undefined && aiDark && canEdit ? html`
        <section class="sd-sec sdx-card no-print" id="sdx-reading">
          <${SecHead} icon="sparkle" title="lumi's reading" on=${false} />
          <div class="sd-note">A short AI reading of this strategy against your live position appears here once AI insights are enabled for the platform.</div>
        </section>` : null}
        ${ai !== undefined ? html`
        <section id="sdx-reading" class="sd-sec sdx-card sd-ai no-print">
          <${SecHead} icon="sparkle" title="lumi's reading"
            chip=${html`<span class="sdx-state live">AI · grounded only in the figures on this page</span>`} />
          ${ai ? html`
            <div role="status" class="sr-only">Reading generated.</div>
            <p class="sd-ai-p"><b>Where you stand.</b> ${ai.reading}</p>
            <p class="sd-ai-p"><b>Tensions.</b> ${ai.tensions}</p>
            <p class="sd-ai-p"><b>To watch.</b> ${ai.watch}</p>
            <div class="sd-note">A description of your strategy against your data, not advice.
              <button class="sd-ai-refresh no-print" disabled=${aiBusy} onClick=${() => genAi(true)}>Regenerate</button></div>`
          : html`
            <p class="sd-note" style=${{ marginBottom: "var(--s3)" }}>A short reading of this strategy against your live position — generated from the figures above, nothing else.</p>
            ${aiBusy ? html`<div class="sd-ai-skel" aria-hidden="true"><i></i><i></i><i></i></div>` : null}
            <button class="btn no-print" disabled=${aiBusy} aria-label=${aiBusy ? "Generating the reading" : "Generate the reading"} onClick=${() => genAi(false)}>${aiBusy ? html`<${Spinner} />` : "Generate the reading"}</button>`}
        </section>` : null}
        <footer class="sd-docfoot" style=${{ "--i": 6 }}>Company facts and choices, not employee data — organisation-level, set by an Admin, shaping how your results are read, never what your people see.</footer>
      </article>

      <div class="strat-pdf-foot" aria-hidden="true">Private ${"&"} confidential · Prepared in lumi · lumihr.co.uk</div>
    </div>`;
}

window.StrategyPage = function ({ me }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [step, setStep] = useState(0);                 // 0 A · 1 B · 2 C · 3 review
  const [strat, setStrat] = useState({});              // field -> value
  const [planeA, setPlaneA] = useState([]);            // editable Plane-A facts
  const [toast, setToast] = useState(null);
  const [saving, setSaving] = useState(false);
  const [committed, setCommitted] = useState(false);   // brief "captured" flourish before nav
  const [leaving, setLeaving] = useState(false);       // stage exit animation in flight
  const [returnTo, setReturnTo] = useState(null);      // "review" → change round-trip lands back on review
  const [editing, setEditing] = useState(false);       // a completed strategy shows the VIEW until Edit
  // document-grade fields captured IN the survey (2026-08-15, David): principles,
  // comparator, segments, constraints, governance, commitments, measures, roadmap.
  // Seeded from the stored document; the wizard PUT always sends the WHOLE object
  // so a survey save can never null a field edited elsewhere.
  const [doc, setDoc] = useState({});
  const [mopts, setMopts] = useState(null);            // measure options (lazy, step 4)
  const [srvDraft, setSrvDraft] = useState(null);       // a saved draft waiting to be resumed
  const [approving, setApprovingState] = useState(false);
  const [mq, setMq] = useState("");                    // measures search (the library is ~200 long)
  const [showAllM, setShowAllM] = useState(false);     // measures: suggested set vs the whole library
  const [groups, setGroups] = useState(null);          // saved peer groups (lazy, step 4)
  const [choices, setChoices] = useState(null);        // industry/size vocab (lazy, step 4)
  const isAdmin = me && me.user && me.user.role === "admin";
  const seedDoc = (d) => { const x = { ...(d.document || {}) }; delete x.comparator_label; return x; };
  useEffect(() => {
    api("/api/strategy").then(d => {
      setData(d);
      setStrat({ ...d.strategy });
      setPlaneA(d.plane_a.map(f => ({ ...f })));
      setDoc(seedDoc(d));
      // restore an in-flight wizard draft: any navigation away used to silently
      // discard every answered dial (pre-prod audit 2026-08-12). The draft only
      // overlays an UNCOMMITTED session (cleared on save + on Cancel).
      try {
        const raw = localStorage.getItem("lumi-strat-draft-v2");
        if (raw) {
          const dr = JSON.parse(raw);
          if (dr && dr.strat && !d.completed_at) {   // local crash copy for an unfinished capture
            // an UNFINISHED first capture resumes exactly where it stopped (the draft
            // now survives closing the tab — it is the multi-sitting case)
            setStrat({ ...d.strategy, ...dr.strat });
            if (dr.doc) setDoc({ ...seedDoc(d), ...dr.doc });
            if (dr.step != null) setStep(dr.step);
          } else if (dr) {
            // a saved strategy always opens from the stored truth: a stale draft must
            // never silently overlay it, force edit mode, or clobber a deep link
            localStorage.removeItem("lumi-strat-draft-v2");
          }
        }
      } catch (e) { /* a corrupt draft never blocks the wizard */ }
      // the server draft wins over the local copy — it is the shared, durable one
      api("/api/strategy/draft").then(r => {
        const dd = r && r.draft;
        if (!dd) return;
        if (!d.completed_at) {
          if (dd.strat) setStrat(s2 => ({ ...s2, ...dd.strat }));
          if (dd.doc) setDoc(dd.doc);
          if (dd.planeA) setPlaneA(dd.planeA);
          if (dd.step != null) setStep(dd.step);
        }
        setSrvDraft({ at: r.saved_at, by: r.by, payload: dd });
      }).catch(() => {});
    }).catch(e => setErr(e.message));
  }, []);
  // the draft is saved TO THE SERVER as you go (2026-08-15, all three personas: a
  // multi-sitting job cannot live in one browser tab). localStorage stays as crash
  // insurance only; the server copy is what a colleague or another device sees.
  const [draftAt, setDraftAt] = useState(null);
  const draftTimer = useRef(null);
  useEffect(() => {
    if (!data || (data.completed_at && !editing)) return;
    try { localStorage.setItem("lumi-strat-draft-v2", JSON.stringify({ strat, doc, step, at: new Date().toISOString() })); } catch (e) {}
    if (!(data.can_edit !== false)) return;
    clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => {
      api("/api/strategy/draft", { method: "PUT", body: { draft: { strat, doc, planeA, step } } })
        .then(r => setDraftAt(r.saved_at || new Date().toISOString())).catch(() => {});
    }, 900);
    return () => clearTimeout(draftTimer.current);
  }, [strat, doc, planeA, step, editing, data]);
  // the commitments step needs the live lookups — fetched once, on first entry
  useEffect(() => {
    if (!data || mopts !== null) return;                 // once, as soon as the wizard has data
    api("/api/strategy/measure-options").then(r => setMopts(r)).catch(() => setMopts({ options: [] }));
    api("/api/peer-groups").then(r => setGroups(r.groups || r || [])).catch(() => setGroups([]));
    api("/api/peer-groups/options").then(r => setChoices(r)).catch(() => setChoices({}));
  }, [data]);
  if (err) return html`<${EmptyState} tone="error" icon="compass" title="Couldn't load your strategy" body=${err + " — nothing is lost."}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!data) return html`<${PageLoading} />`;
  const complete = !!data.completed_at;
  // document-section saves refetch here so the view never renders stale content
  const reload = () => api("/api/strategy").then(d => { setData(d); setStrat({ ...d.strategy }); setPlaneA(d.plane_a.map(f => ({ ...f }))); }).catch(() => {});
  if (!isAdmin) {
    // non-admins with a completed strategy still get the READ view — it explains
    // how their organisation's results are being read; only editing is admin-only.
    if (complete) return html`<${StrategyView} me=${me} data=${data} strat=${data.strategy || {}} canEdit=${false} />`;
    return html`<${EmptyState} icon="lock" title="Admin only"
      body="Your reward strategy is set by an organisation Admin — ask yours to complete it."
      action=${html`<button class="btn small primary" onClick=${() => nav("/overview")}>Explore the benchmark</button>`} />`;
  }
  if (complete && !editing) return html`<${StrategyView} me=${me} data=${data} strat=${strat} onReload=${reload} onEdit=${(pid) => { setEditing(true); setStep(pid ? (PAGE_IX[pid] != null ? PAGE_IX[pid] : 0) : 0); window.scrollTo(0, 0); }} />`;

  const pick = (field, val) => setStrat(s => ({ ...s, [field]: val }));
  // per-domain override write: only set domains carry a key — null deletes (inherit global)
  const setDomainTarget = (dom, val) => setStrat(s => {
    const dt = { ...(s.domain_targets || {}) };
    if (val == null) delete dt[dom]; else dt[dom] = val;
    return { ...s, domain_targets: dt };
  });
  // domain_targets promoted to a first-class stage (R3 rescope, 2026-08-14): the six
  // position categories (R3b) get their own screen straight after the global dial.
  const planeBfields = ["market_position", "domain_targets", "reward_mix", "pay_for_performance", "transparency",
    "location_approach", "benefits_lead", "family_position"];
  const planeCfields = ["primary_objective", "budget_direction", "acute_pressure", "risk_appetite"];
  const PHIL = shownFields(planeBfields);
  const POST = shownFields(planeCfields);

  // ---- the flow (2026-08-15, persona review): STEP-BY-STEP pages in four phases.
  // Every document field is captured here, one short step at a time — the document
  // view only PRESENTS (David: "it is all still showing at the end ... it is all a
  // mess"). The comparator is asked BEFORE the position dials, because "above market"
  // means nothing until the market is named (reward-director review).
  const ix = typeof step === "number" && step >= 0 && step < PAGES.length ? step
    : (typeof step === "number" && step >= 10 ? ((step - 10) < PHIL.length ? PAGE_IX.phil : PAGE_IX.post) : 0);
  const cur = PAGES[ix];
  const curPhase = cur.phase;
  const subPages = PAGES.filter(p => p.phase === curPhase);
  const flash = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3200); };
  const setD = (patch) => setDoc(d => ({ ...d, ...patch }));
  const gov = doc.reward_governance || {};
  const cons = doc.constraints || {};
  const seg = doc.segments || {};
  const cm = doc.commitments || {};
  const wbIds = (cm["Wellbeing"] || {}).metric_ids || [];
  const gvStmt = (cm["Governance & Transparency"] || {}).statement || "";
  const principles = doc.principles || [];
  const pops = doc.population_targets || [];
  const roadmap = doc.roadmap || [];
  const measures = doc.measures || [];
  const isSet = (p) => ({
    facts: planeA.every(f => f.value),
    // the comparator only counts as SET when the member actually chose one — a default
    // must never be scored as a decision (both persona reviews caught this)
    compare: doc.comparator_cut != null || !!seg.differentiated,
    phil: !!(strat.market_position && strat.reward_mix),
    populations: (doc.population_targets || []).length > 0,
    post: !!strat.primary_objective,
    principles: principles.filter(p2 => (p2 || "").trim()).length > 0,
    commit: !!(wbIds.length || gvStmt),
    measures: measures.length > 0,
    roadmap: roadmap.filter(r => (r.title || "").trim()).length > 0,
    governance: !!Object.keys(gov).length,
    review: false,
  })[p.id];
  const go = (i) => { setStep(i); window.scrollTo(0, 0); };
  const goId = (id) => go(PAGE_IX[id]);
  const missingReq = REQUIRED.filter(f => !strat[f]);
  const next = () => {
    if (cur.id === "phil" && (!strat.market_position || !strat.reward_mix)) {
      flash("Market position and total-reward mix change how we read your results — set both to continue.");
      const el = document.querySelector(".dial-card.flagged"); if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    if (cur.id === "post" && !strat.primary_objective) { flash("Choose what reward is mainly for right now to continue."); return; }
    go(Math.min(ix + 1, PAGES.length - 1));
  };
  const changeFrom = (field) => goId(PHIL.includes(field) ? "phil" : "post");

  const commit = async () => {
    setSaving(true);
    try {
      // only facts the user actually changed travel — an untouched DERIVED fact
      // (workforce shape) must not become a registry override on save
      const pa = {};
      planeA.forEach((f, i) => {
        const orig = (data.plane_a || [])[i] || {};
        if (f.value && f.value !== orig.value) pa[f.key] = f.value;
      });
      // the survey carries the document fields too — always the WHOLE object, so a
      // save can never null a field. Blank rows are dropped, never stored.
      const docOut = { ...doc };
      delete docOut.comparator_label;
      docOut.principles = principles.map(p2 => (p2 || "").trim()).filter(Boolean);
      docOut.roadmap = roadmap.filter(r => (r.title || "").trim());
      // transparency reconfirm marker: saving through the now-live field means the user
      // has SEEN the dial — confirm it so the engine reads the value.
      await api("/api/strategy", { method: "PUT", body: { strategy: strat, plane_a: pa, document: docOut,
        transparency_confirmed: fieldState("transparency") === "live" } });
      setCommitted(true);                                  // a governance act closes quietly — no confetti
      try { localStorage.removeItem("lumi-strat-draft-v2"); } catch (e) {}
      api("/api/strategy/draft", { method: "DELETE" }).catch(() => {});
      window.toast("Saved — your benchmark now reads through this strategy.");
      apiCacheInvalidate("/api/overview");
      // land on the DOCUMENT, first run included — the artefact is the payoff and the
      // old flow sent first-time completers to Home, never showing what they'd made.
      const settle = () => { setEditing(false); setCommitted(false); setSaving(false); setStep(0); window.scrollTo(0, 0); };
      setTimeout(() => {
        api("/api/strategy")
          .then(d => { setData(d); setStrat({ ...d.strategy }); setPlaneA(d.plane_a.map(f => ({ ...f }))); setDoc(seedDoc(d)); settle(); })
          .catch(settle);
      }, 1400);
    } catch (e) { flash(e && e.message && e.status !== 0 ? e.message : "Couldn't save — try again."); setSaving(false); }
  };

  const orgName = (me.org && me.org.name) || "Your organisation";
  const dialsOf = (fields) => fields.map(f => f === "domain_targets"
    ? html`<div key="dt" class="dial-card" id="dial-domain_targets">
        <div class="dial-head">
          <span class="dial-roundel"><${Icon} name="sliders" size=${16} /></span>
          <div>
            <div class="dial-title">Aim by category <span class="sdw-opt">Optional</span></div>
            <div class="dial-q">Aim differently anywhere? Every category follows your overall position${strat.market_position ? html` (<b>${labelOf("market_position", strat.market_position)}</b>)` : ""} unless you set it here.</div>
          </div>
        </div>
        <${DomainOverrides} domains=${data.position_domains || data.competitive_domains || []}
          targets=${strat.domain_targets} globalValue=${strat.market_position} onSet=${setDomainTarget} />
      </div>`
    : html`<${DialCard} key=${f} field=${f} value=${strat[f]} onPick=${pick}
        required=${REQUIRED.includes(f)} context=${fieldState(f) === "context"} />`);

  const Stepper = () => html`
    <div class="sdw-steps no-print">
      <ol class="sdw-phases" aria-label="Strategy set-up">
        ${PHASES.map((p, i) => {
          const state = i === curPhase ? "current" : i < curPhase ? "done" : "todo";
          return html`<li key=${i} class=${"sdw-ph " + state}>
            <button type="button" class="sdw-ph-btn" aria-current=${i === curPhase ? "step" : undefined}
              onClick=${() => { if (!saving && !committed) go(PAGE_IX[PAGES.filter(x => x.phase === i)[0].id]); }}>
              <span class="sdw-ph-node">${state === "done" ? html`<${Icon} name="check" size=${12} />` : i + 1}</span>
              <span class="sdw-ph-txt"><b>${p.t}</b>${p.note ? html`<em>${p.note}</em>` : null}</span>
            </button>
            ${i < PHASES.length - 1 ? html`<span class="sdw-ph-line" aria-hidden="true"></span>` : null}
          </li>`;
        })}
      </ol>
      ${subPages.length > 1 ? html`
        <div class="sdw-substeps" aria-label="Steps in this section">
          ${subPages.map(p => html`<button key=${p.id} type="button"
            class=${"sdw-sub" + (p.id === cur.id ? " on" : "")}
            onClick=${() => { if (!saving && !committed) goId(p.id); }}>
            <span class=${"sdx-dot" + (isSet(p) ? " on" : "")}></span>${p.label}</button>`)}
        </div>` : null}
    </div>`;

  // one footer shape for every page: Back · (Skip the rest) · Continue
  const Foot = ({ label }) => html`
    <div class="sdw-foot">
      ${ix > 0 ? html`<button class="btn quiet" disabled=${saving || committed} onClick=${() => go(ix - 1)}>← Back</button>` : html`<span></span>`}
      <div class="sdw-foot-r">
        ${cur.opt ? html`<button class="btn quiet" disabled=${saving || committed} onClick=${() => goId("review")}>Skip the rest</button>` : null}
        <button class="btn primary" disabled=${saving || committed} onClick=${next}>${label || (cur.opt && !isSet(cur) ? "Skip this step →" : "Continue →")}</button>
      </div>
    </div>`;

  const OptHead = ({ title, sub }) => html`
    <header class="sdw-head">
      <div class="sdw-optflag"><${Icon} name="info" size=${13} /> Optional — leave it blank and the document simply won't include it</div>
      <h1 class="strat-title">${title}</h1>
      <p class="strat-sub">${sub}</p>
    </header>`;

  return html`
    <div class="strat-flow sdw">
      <div class="sdw-top no-print">
        <div class="sdw-topline">
          <span class="sdw-crumb">Reward strategy${editing ? " · editing" : ""}
            ${draftAt ? html`<span class="sdw-saved"><${Icon} name="check" size=${11} /> Draft saved</span>` : null}</span>
          ${editing && !committed ? html`<button class="btn quiet" disabled=${saving} onClick=${() => { setEditing(false); setStrat({ ...data.strategy }); setPlaneA(data.plane_a.map(f => ({ ...f }))); setDoc(seedDoc(data)); setStep(0); try { localStorage.removeItem("lumi-strat-draft-v2"); } catch (e) {} api("/api/strategy/draft", { method: "DELETE" }).catch(() => {}); }}>Cancel</button>` : null}
        </div>
        <${Stepper} />
      </div>

      ${cur.id === "facts" && html`
        <section key="facts" class="sdw-page">
          <header class="sdw-head">
            <h1 class="strat-title">Does this still describe you?</h1>
            <p class="strat-sub">Pre-filled from your company profile. These shape who you're compared against — correct anything that's changed.</p>
          </header>
          <div class="sdw-factgrid">
            ${planeA.map((f, i) => html`
              <div key=${f.key} class="sdw-fact">
                <div class="sdw-fact-label">${f.label}${f.derived ? html` <span class="sdw-opt">estimated</span>` : ""}</div>
                <div class="sdw-fact-why">${f.why}</div>
                <div class="sdw-seg" role="radiogroup" aria-label=${f.label}
                  onKeyDown=${e => {
                    if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(e.key)) return;
                    e.preventDefault();
                    const wrap = e.currentTarget;
                    const opts = (f.options || []).concat(f.value && !(f.options || []).includes(f.value) ? [f.value] : []);
                    const c0 = Math.max(0, opts.indexOf(f.value));
                    const nxt = ("ArrowRight" === e.key || "ArrowDown" === e.key) ? Math.min(opts.length - 1, c0 + 1) : Math.max(0, c0 - 1);
                    setPlaneA(p => p.map((x, j) => j === i ? { ...x, value: opts[nxt] } : x));
                    requestAnimationFrame(() => { const el = wrap && wrap.querySelectorAll(".sdw-seg-opt")[nxt]; if (el) el.focus(); });
                  }}>
                  ${(f.options || []).concat(f.value && !(f.options || []).includes(f.value) ? [f.value] : []).map(o => html`
                    <button key=${o} type="button" class=${"sdw-seg-opt" + (o === f.value ? " on" : "")} role="radio" aria-checked=${o === f.value}
                      tabindex=${o === f.value || (!f.value && o === (f.options || [])[0]) ? 0 : -1}
                      onClick=${() => setPlaneA(p => p.map((x, j) => j === i ? { ...x, value: o } : x))}>
                      ${o === f.value ? html`<${Icon} name="check" size=${12} />` : null} ${o}</button>`)}
                </div>
              </div>`)}
          </div>
          <${Foot} />
        </section>`}

      ${cur.id === "compare" && html`
        <section key="compare" class="sdw-page">
          <header class="sdw-head">
            <h1 class="strat-title">Who do you compare yourselves to?</h1>
            <p class="strat-sub">Name the market first — "above market" only means something once you've said which market. This is the peer group your whole strategy is written against.</p>
          </header>
          <div class="sdw-dials">
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="users" size=${16} /></span>
                <div><div class="dial-title">Your comparator</div>
                <div class="dial-q">Your document describes this in words; the figures stay in the benchmark.</div></div></div>
              <select class="ctl" value=${doc.comparator_cut || "all"}
                onChange=${e => setD({ comparator_cut: e.target.value === "all" ? null : e.target.value })}>
                <option value="all">All peers — every company in the lumi pool</option>
                ${((choices || {}).fields || []).filter(f => f.key === "industry").flatMap(f => f.choices || []).map(c =>
                  html`<option key=${"i" + c} value=${"industry::" + c}>Sector — ${c}</option>`)}
                ${((choices || {}).fields || []).filter(f => f.key === "fte_band").flatMap(f => f.choices || []).map(c =>
                  html`<option key=${"f" + c} value=${"fte_band::" + c}>Size — ${c} employees</option>`)}
                ${(groups || []).map(g => html`<option key=${g.group_id} value=${"group::" + g.group_id}>Saved peer group — ${g.name}</option>`)}
              </select>
              <div class="signal-effect"><span class="se-eye"><${Icon} name="sparkle" size=${14} /></span>
                <span class="se-text">${orgCompareWords(null, { ...doc, comparator_label: comparatorLabel(doc, groups) })}</span></div>
            </div>
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="magnet" size=${16} /></span>
                <div><div class="dial-title">Scarce or critical roles <span class="sdw-opt">Optional</span></div>
                <div class="dial-q">Do you deliberately pay some groups above the rest, whatever your overall position?</div></div></div>
              <label class="sd-doc-check"><input type="checkbox" checked=${!!seg.differentiated}
                onChange=${e => setD({ segments: { ...seg, differentiated: e.target.checked } })} />
                Yes — some roles are paid differently by design</label>
              ${seg.differentiated ? html`<input class="ctl" style=${{ marginTop: "var(--s2)" }}
                placeholder="Name them, comma-separated (e.g. Engineering, HGV drivers)"
                value=${(seg.segments || []).join(", ")}
                onInput=${e => setD({ segments: { ...seg, segments: e.target.value.split(",").map(s2 => s2.trim()).filter(Boolean).slice(0, 6) } })} />` : null}
            </div>
          </div>
          <${Foot} />
        </section>`}

      ${cur.id === "phil" && html`
        <section key="phil" class="sdw-page">
          <header class="sdw-head">
            <h1 class="strat-title">How you reward</h1>
            <p class="strat-sub">The positions lumi reads your benchmark through. Two are required; skip anything else and we simply won't judge it either way.</p>
          </header>
          <div class="sdw-dials">${dialsOf(PHIL)}</div>
          <${Foot} />
        </section>`}

      ${cur.id === "populations" && html`
        <section key="populations" class="sdw-page">
          <${OptHead} title="Do different groups sit differently?"
            sub=${"Most organisations aim differently for their executive population than for everyone else. State it here and it appears in your document — lumi holds no executive pay data, so we never score these against the benchmark."} />
          <div class="sdw-dials">
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="layers" size=${16} /></span>
                <div><div class="dial-title">Position by employee population <span class="sdw-opt">up to 5</span></div>
                <div class="dial-q">Your overall position${strat.market_position ? html` (<b>${labelOf("market_position", strat.market_position)}</b>)` : ""} covers everyone you don't name here.</div></div></div>
              ${(data.populations || []).map(lbl => {
                const row = pops.find(p => p.label === lbl);
                return html`<div key=${lbl} class="sdw-poprow">
                  <div class="sdw-pop-head">
                    <label class="sd-doc-check"><input type="checkbox" checked=${!!row}
                      onChange=${e => setD({ population_targets: e.target.checked
                        ? [...pops, { label: lbl, position: strat.market_position || "match" }].slice(0, 5)
                        : pops.filter(p => p.label !== lbl) })} />${lbl}</label>
                    ${row ? html`<div class="sdw-popseg">
                      ${SCALE.market.stops.map(st2 => html`<button key=${st2.v} type="button"
                        class=${"sdw-seg-opt" + (row.position === st2.v ? " on" : "")}
                        onClick=${() => setD({ population_targets: pops.map(p => p.label === lbl ? { ...p, position: st2.v } : p) })}>${st2.t}</button>`)}
                    </div>` : null}
                  </div>
                  ${row ? html`<input class="ctl" maxlength="240" placeholder="Why — e.g. total comp at upper quartile, benchmarked against listed peers"
                    value=${row.note || ""}
                    onInput=${e => setD({ population_targets: pops.map(p => p.label === lbl ? { ...p, note: e.target.value } : p) })} />` : null}
                </div>`; })}
              <div class="signal-effect"><span class="se-eye"><${Icon} name="info" size=${14} /></span>
                <span class="se-text">These are statements in your document. Your benchmark reads the whole organisation, so lumi never marks a population position right or wrong.</span></div>
            </div>
          </div>
          <${Foot} />
        </section>`}

      ${cur.id === "post" && html`
        <section key="post" class="sdw-page">
          <header class="sdw-head">
            <h1 class="strat-title">This year</h1>
            <p class="strat-sub">Your posture right now, and what limits it — this sharpens which signals surface first, and changes with the year.</p>
          </header>
          <div class="sdw-dials">
            ${dialsOf(POST)}
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="anchor" size=${16} /></span>
                <div><div class="dial-title">What constrains us <span class="sdw-opt">Optional</span></div>
                <div class="dial-q">What genuinely limits reward decisions this year? Your document names these as context.</div></div></div>
              <div class="chip-row">
                ${(data.constraint_options || []).map(c => { const sel = (cons.selected || []).includes(c); return html`
                  <button key=${c} type="button" class=${"strat-chip" + (sel ? " on" : "")} aria-pressed=${sel}
                    onClick=${() => { const curSel = cons.selected || [];
                      setD({ constraints: { ...cons, selected: sel ? curSel.filter(x => x !== c) : [...curSel, c] } }); }}>
                    <${Icon} name="check" size=${12} /> ${CONSTRAINT_LABEL[c] || c}</button>`; })}
              </div>
              <input class="ctl" style=${{ marginTop: "var(--s3)" }} maxlength="300" placeholder="Anything else worth naming (optional)"
                value=${cons.notes || ""} onInput=${e => setD({ constraints: { ...cons, notes: e.target.value } })} />
            </div>
          </div>
          <${Foot} />
        </section>`}

      ${cur.id === "principles" && html`
        <section key="principles" class="sdw-page">
          <${OptHead} title="Your reward principles"
            sub=${"The few lines your document opens with — the yardstick everything else is read against. Tap a starter to add it, then make it yours."} />
          <div class="sdw-dials">
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="star" size=${16} /></span>
                <div><div class="dial-title">Principles <span class="sdw-opt">up to 6</span></div>
                <div class="dial-q">Starters are prompts, not policy — edit any you use so the words are genuinely yours.</div></div></div>
              <div class="sdw-starters">
                ${PRINCIPLE_STARTERS.filter(s2 => !principles.includes(s2)).map(s2 => html`
                  <button key=${s2} type="button" class="sdw-starter" disabled=${principles.length >= 6}
                    onClick=${() => setD({ principles: [...principles, s2].slice(0, 6) })}>
                    <${Icon} name="plus" size=${11} /> ${s2}</button>`)}
              </div>
              ${principles.map((p2, i) => html`
                <div key=${i} class="sdw-lirow">
                  <input class="ctl" maxlength="140" value=${p2} placeholder="Your principle, in your words"
                    onInput=${e => setD({ principles: principles.map((x, j) => j === i ? e.target.value : x) })} />
                  <button type="button" class="sdw-li-x" aria-label="Remove principle" onClick=${() => setD({ principles: principles.filter((x, j) => j !== i) })}>✕</button>
                </div>`)}
              ${principles.length < 6 ? html`
                <button type="button" class="sdx-addtile" onClick=${() => setD({ principles: [...principles, ""] })}>
                  <${Icon} name="plus" size=${13} /> Write your own</button>` : null}
            </div>
          </div>
          <${Foot} />
        </section>`}

      ${cur.id === "commit" && html`
        <section key="commit" class="sdw-page">
          <${OptHead} title="What you offer, and how you operate"
            sub=${"Wellbeing and governance can't carry a market position — they're measured by what you offer and how you work. State them as commitments instead."} />
          <div class="sdw-dials">
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="heart" size=${16} /></span>
                <div><div class="dial-title">Wellbeing — what we will offer</div>
                <div class="dial-q">Tick what you commit to providing. Your review checks these against your own answers each cycle.</div></div></div>
              ${mopts === null ? html`<p class="sd-note">Loading your metric list…</p>` :
                (mopts.options || []).filter(o => o.category === "Wellbeing").map(o => { const on = wbIds.includes(o.id); return html`
                <label key=${o.id} class="sd-doc-check"><input type="checkbox" checked=${on}
                  onChange=${e => { const nw = e.target.checked ? [...wbIds, o.id].slice(0, 6) : wbIds.filter(x => x !== o.id);
                    const cm2 = { ...cm };
                    if (nw.length) cm2["Wellbeing"] = { metric_ids: nw }; else delete cm2["Wellbeing"];
                    setD({ commitments: cm2 }); }} />${o.title}</label>`; })}
            </div>
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="shield" size=${16} /></span>
                <div><div class="dial-title">Governance — how we operate</div>
                <div class="dial-q">One or two lines on how pay is governed and shared. A starter APPENDS to what you've written — nothing is overwritten.</div></div></div>
              <div class="sdw-starters">
                ${GOV_STMT_STARTERS.map(s2 => html`<button key=${s2} type="button" class="sdw-starter"
                  onClick=${() => { const t0 = gvStmt.trim();
                    const merged = (t0 ? t0.replace(/\.$/, "") + ". " + s2 : s2).slice(0, 240);
                    setD({ commitments: { ...cm, "Governance & Transparency": { statement: merged } } }); }}>
                  <${Icon} name="plus" size=${11} /> ${s2}</button>`)}
              </div>
              <textarea class="ctl" rows="3" maxlength="240" placeholder="Your words — only claim what you actually do"
                value=${gvStmt}
                onInput=${e => { const cm2 = { ...cm };
                  if (e.target.value.trim()) cm2["Governance & Transparency"] = { statement: e.target.value }; else delete cm2["Governance & Transparency"];
                  setD({ commitments: cm2 }); }}></textarea>
            </div>
          </div>
          <${Foot} />
        </section>`}

      ${cur.id === "measures" && (() => {
        const all = (mopts || {}).options || [];
        const posCats = new Set(Object.keys(strat.domain_targets || {}));
        const suggested = all.filter(o => !o.suppressed && (posCats.size ? posCats.has(o.category) : true));
        const q = mq.trim().toLowerCase();
        const list = q ? all.filter(o => o.title.toLowerCase().includes(q) || (o.category || "").toLowerCase().includes(q))
                       : (showAllM ? all : suggested);
        return html`
        <section key="measures" class="sdw-page">
          <${OptHead} title="How you'll know it's working"
            sub=${"Pick a handful of metrics lumi already tracks. Your review reports them against your comparator each cycle — most organisations choose five to eight."} />
          <div class="sdw-dials">
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="table" size=${16} /></span>
                <div><div class="dial-title">Your measures <span class="sdw-opt">${measures.length} of 8 chosen</span></div>
                <div class="dial-q">Greyed rows are below the reporting floor on your comparator right now — you can still choose them; they'll report once enough peers answer.</div></div></div>
              <div class="sdw-msearch">
                <input class="ctl" placeholder="Search your metrics…" value=${mq} onInput=${e => setMq(e.target.value)} />
                ${!q ? html`<button type="button" class="sdw-mtoggle" onClick=${() => setShowAllM(v => !v)}>
                  ${showAllM ? "Show suggested only" : "Show all " + all.length}</button>` : null}
              </div>
              <p class="sd-note" style=${{ margin: "0 0 var(--s2)" }}>
                ${mopts === null ? "Loading your metric list…"
                  : q ? list.length + " matching"
                  : showAllM ? "Every metric you can see" : "Suggested from the areas you set a position on"}</p>
              <div class="sd-doc-mlist">
                ${list.slice(0, 60).map(o => { const on = measures.some(m => m.id === o.id); return html`
                  <label key=${o.id} class=${"sd-doc-check" + (o.suppressed ? " dim" : "")}>
                    <input type="checkbox" checked=${on} disabled=${!on && measures.length >= 8}
                      onChange=${e => setD({ measures: e.target.checked ? [...measures, { id: o.id }].slice(0, 8) : measures.filter(x => x.id !== o.id) })} />
                    <span>${o.title} <span class="sd-doc-meta">${o.category}${o.context ? " · tracked as a level" : ""}${o.suppressed ? " · below floor" : ""}</span></span>
                  </label>`; })}
                ${list.length > 60 ? html`<p class="sd-note">${list.length - 60} more — search to narrow.</p>` : null}
              </div>
            </div>
            ${measures.length ? html`
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="target" size=${16} /></span>
                <div><div class="dial-title">Where each one needs to get to <span class="sdw-opt">Optional</span></div>
                <div class="dial-q">A measure without a target is a topic. Say where you are, where you want to be, and who owns it — your words, printed as given.</div></div></div>
              ${measures.map((m, i) => { const o = all.find(x => x.id === m.id) || {}; return html`
                <div key=${m.id} class="sdw-mrow">
                  <div class="sdw-mrow-title">${o.title || m.id}</div>
                  <div class="sdw-mrow-fields">
                    <input class="ctl" maxlength="80" placeholder="Baseline today" value=${m.baseline || ""}
                      onInput=${e => setD({ measures: measures.map((x, j) => j === i ? { ...x, baseline: e.target.value } : x) })} />
                    <input class="ctl" maxlength="80" placeholder="Target" value=${m.target || ""}
                      onInput=${e => setD({ measures: measures.map((x, j) => j === i ? { ...x, target: e.target.value } : x) })} />
                    <input class="ctl" maxlength="80" placeholder="Owner" value=${m.owner || ""}
                      onInput=${e => setD({ measures: measures.map((x, j) => j === i ? { ...x, owner: e.target.value } : x) })} />
                  </div>
                </div>`; })}
            </div>` : null}
          </div>
          <${Foot} />
        </section>`; })()}

      ${cur.id === "roadmap" && html`
        <section key="roadmap" class="sdw-page">
          <${OptHead} title="What changes this year"
            sub=${"The short list of things you intend to do about reward this cycle. Tap a common change to add it, then make it yours."} />
          <div class="sdw-dials">
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="clock" size=${16} /></span>
                <div><div class="dial-title">Your roadmap <span class="sdw-opt">up to 6</span></div>
                <div class="dial-q">Only what you've actually decided — this is a plan, not a wish list.</div></div></div>
              <div class="sdw-starters">
                ${ROADMAP_STARTERS.filter(s2 => !roadmap.some(r => r.title === s2)).map(s2 => html`
                  <button key=${s2} type="button" class="sdw-starter" disabled=${roadmap.length >= 6}
                    onClick=${() => setD({ roadmap: [...roadmap, { title: s2 }].slice(0, 6) })}>
                    <${Icon} name="plus" size=${11} /> ${s2}</button>`)}
              </div>
              ${roadmap.map((r, i) => html`
                <div key=${i} class="sdw-lirow">
                  <input class="ctl" maxlength="120" value=${r.title || ""} placeholder="What you're changing"
                    onInput=${e => setD({ roadmap: roadmap.map((x, j) => j === i ? { ...x, title: e.target.value } : x) })} />
                  <select class="ctl sdw-li-sel" value=${r.horizon || ""}
                    onChange=${e => setD({ roadmap: roadmap.map((x, j) => j === i ? { ...x, horizon: e.target.value || undefined } : x) })}>
                    <option value="">When?</option>
                    ${(data.horizon_options || []).map(h => html`<option key=${h} value=${h}>${HORIZON_LABEL[h] || h}</option>`)}
                  </select>
                  <button type="button" class="sdw-li-x" aria-label="Remove roadmap item" onClick=${() => setD({ roadmap: roadmap.filter((x, j) => j !== i) })}>✕</button>
                </div>`)}
              ${roadmap.length < 6 ? html`
                <button type="button" class="sdx-addtile" onClick=${() => setD({ roadmap: [...roadmap, { title: "" }] })}>
                  <${Icon} name="plus" size=${13} /> Write your own</button>` : null}
            </div>
          </div>
          <${Foot} />
        </section>`}

      ${cur.id === "governance" && html`
        <section key="governance" class="sdw-page">
          <${OptHead} title="How reward is governed"
            sub=${"Who owns reward, who signs it off, and how often it's reviewed. If that's you and the CEO, say so — small is a legitimate answer."} />
          <div class="sdw-dials">
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="shield" size=${16} /></span>
                <div><div class="dial-title">Ownership ${"&"} review</div>
                <div class="dial-q">This prints as the governance block of your document.</div></div></div>
              <div class="sd-doc-grid2">
                <label>Owner<input class="ctl" maxlength="80" placeholder="e.g. HR Director" value=${gov.owner || ""}
                  onInput=${e => setD({ reward_governance: { ...gov, owner: e.target.value } })} /></label>
                <label>Signed off by<input class="ctl" maxlength="80" placeholder="e.g. CEO, or Remuneration Committee" value=${gov.approver || ""}
                  onInput=${e => setD({ reward_governance: { ...gov, approver: e.target.value } })} /></label>
                <label>Review cadence<select class="ctl" value=${gov.review_cadence || ""}
                  onChange=${e => setD({ reward_governance: { ...gov, review_cadence: e.target.value || null } })}>
                  <option value="">—</option>
                  ${(data.cadence_options || []).map(c => html`<option key=${c} value=${c}>${CADENCE_LABEL[c] || c}</option>`)}
                </select></label>
                <label>Effective from<input class="ctl" type="date" value=${gov.effective_date || ""}
                  onInput=${e => setD({ reward_governance: { ...gov, effective_date: e.target.value } })} /></label>
              </div>
            </div>
          </div>
          <${Foot} label="Review & save →" />
        </section>`}

      ${cur.id === "review" && html`
        <section key="review" class="sdw-page">
          <div class=${"strat-done" + (committed ? " celebrating" : "")}><span class="strat-check"><${Icon} name="check" size=${22} /></span>
            <h1 class="strat-title" style=${{ textAlign: "center" }}>That's your strategy captured</h1>
            <p class="strat-sub" style=${{ margin: "var(--s2) auto 0", textAlign: "center" }}>Change anything before it goes live — each change returns you straight here.</p></div>
          ${missingReq.length ? html`
            <div class="sdw-missing" role="alert">
              <${Icon} name="info" size=${15} />
              <div><b>${missingReq.length === 1 ? "One required position is" : missingReq.length + " required positions are"} not set</b>
                (${missingReq.map(f => DIAL_LABEL[f]).join(", ")}) — you can save, but your strategy stays incomplete and the benchmark reads neutrally until they're set.
                <button class="sdw-missing-go" onClick=${() => changeFrom(missingReq[0])}>Set now</button></div>
            </div>` : null}
          <${ReviewSection} title="Your business" chip="confirmed" chipCls="confirmed"
            rows=${planeA.map(f => ({ label: f.label, value: f.value || "—" }))
              .concat([{ label: "Comparator", value: comparatorLabel(doc, groups) }])}
            onEdit=${() => goId("facts")} locked=${committed || saving} />
          <${ReviewSection} title="How you reward" chip="your choices" chipCls="choices"
            rows=${PHIL.map(f => ({ ...reviewRow(f, strat), field: f }))}
            onEdit=${() => goId("phil")} onChangeRow=${changeFrom} locked=${committed || saving} />
          <${ReviewSection} title="This year" chip="right now" chipCls="choices"
            rows=${POST.map(f => ({ ...reviewRow(f, strat), field: f }))
              .concat([{ label: "Constraints", value: (cons.selected || []).length ? (cons.selected || []).map(c => CONSTRAINT_LABEL[c] || c).join(", ") : "Not included", skipped: !(cons.selected || []).length }])}
            onEdit=${() => goId("post")} onChangeRow=${changeFrom} locked=${committed || saving} />
          <${ReviewSection} title="Your document" chip="optional" chipCls="choices"
            rows=${[
              { label: "Principles", value: principles.filter(p2 => (p2 || "").trim()).length ? principles.filter(p2 => (p2 || "").trim()).length + " stated" : "Not included", skipped: !principles.filter(p2 => (p2 || "").trim()).length, field: "principles" },
              { label: "Commitments", value: (wbIds.length || gvStmt) ? "Stated" : "Not included", skipped: !(wbIds.length || gvStmt), field: "commit" },
              { label: "Measures", value: measures.length ? measures.length + " chosen" : "Not included", skipped: !measures.length, field: "measures" },
              { label: "Roadmap", value: roadmap.filter(r => (r.title || "").trim()).length ? roadmap.filter(r => (r.title || "").trim()).length + " changes" : "Not included", skipped: !roadmap.filter(r => (r.title || "").trim()).length, field: "roadmap" },
              { label: "Governance", value: Object.keys(gov).length ? [gov.owner, gov.approver].filter(Boolean).join(" · ") || "Stated" : "Not included", skipped: !Object.keys(gov).length, field: "governance" },
            ]}
            onEdit=${() => goId("principles")} onChangeRow=${(pg) => goId(pg)} locked=${committed || saving} />
          <p class="strat-trust"><b>Company facts and choices, not employee data.</b> Organisation-level, set by an Admin — they shape how your results are read, never what your people see.</p>
          <div class="sdw-foot">
            <button class="btn quiet" disabled=${saving || committed} onClick=${() => go(ix - 1)}>← Back</button>
            <button class=${"btn primary" + (committed ? " strat-saved" : "")} disabled=${saving || committed} onClick=${commit}>${
              committed ? html`<${Icon} name="check" size=${15} /> Saved` : saving ? "Saving…" : "Save & finish"}</button>
          </div>
        </section>`}

      <div class="sr-only" role="status" aria-live="polite">${toast || ""}</div>
      ${toast && html`<div class="strat-toast">${toast}</div>`}
    </div>`;
};

// the comparator in the member's own vocabulary (never the raw enum tail)
function comparatorLabel(doc, groups) {
  const cut = (doc || {}).comparator_cut;
  if (!cut) return "All peers";
  const [dim, val] = cut.split("::");
  if (dim === "industry") return "Sector — " + val;
  if (dim === "fte_band") return "Size — " + val + " employees";
  const g = (groups || []).find(x => x.group_id === val);
  return "Saved peer group" + (g ? " — " + g.name : "");
}

function reviewRow(field, strat) {
  const v = strat[field];
  if (field === "benefits_lead") {
    const sel = v || [];
    return { label: DIAL_LABEL[field], value: sel.length ? sel.map(x => BENEFITS.find(b => b.v === x).t).join(", ") : "Skipped — read neutrally", skipped: !sel.length };
  }
  if (field === "domain_targets") {
    const dt = v || {}, n = Object.keys(dt).length;
    return n ? { label: DIAL_LABEL[field], value: Object.entries(dt).map(([d, s]) => d + " — " + labelOf("market_position", s)).join(" · ") }
             : { label: DIAL_LABEL[field], value: "Every area follows your overall position", skipped: true };
  }
  if (!v) return { label: DIAL_LABEL[field], value: "Skipped — read neutrally", skipped: true };
  return { label: DIAL_LABEL[field], value: labelOf(field, v) };
}
function ReviewSection({ title, chip, chipCls, rows, onEdit, onChangeRow, locked }) {
  return html`
    <div class="review-sec">
      <div class="review-h">${title} <span class=${"review-chip " + chipCls}>${chip}</span>
        <button class="review-edit" disabled=${locked} aria-label=${"Edit " + title.toLowerCase()} onClick=${() => { if (!locked) onEdit(); }}>Edit</button></div>
      <div class="review-list">
        ${rows.map((r, i) => html`<div key=${i} class="review-row">
          <span class="rr-label">${r.label}</span>
          <span class=${"rr-val" + (r.skipped ? " skipped" : "")}>${r.value}</span>
          ${onChangeRow && r.field ? html`<button class="rr-change" disabled=${locked} aria-label=${"Change " + r.label.toLowerCase()}
            onClick=${() => { if (!locked) onChangeRow(r.field); }}>Change</button>` : null}</div>`)}
      </div>
    </div>`;
}
