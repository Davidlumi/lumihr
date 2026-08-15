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
  { id: "populations", phase: 1, label: "By level", opt: true },
  { id: "post",       phase: 1, label: "This year" },
  { id: "principles", phase: 2, label: "Principles", opt: true },
  { id: "review",     phase: 3, label: "Review & save" },
];
const PHASES = [
  { t: "Your business" }, { t: "How you reward" },
  { t: "Your principles", note: "optional" }, { t: "Review & save" },
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

function SdDocSections({ data, canEdit, onEdit, onPlan, which }) {
  // `which` renders only the named sections, so the document groups them under the
  // brief's three-part spine (Intent / Position / Delivery). onEdit(pageId) jumps
  // the wizard straight to the step that captures that section.
  const show = (k) => !which || which.includes(k);
  const doc = data.document || {};
  const cons = doc.constraints || {};

  return html`
    <${React.Fragment}>
      ${show("principles") && html`<${SdDocSec} id="sdx-principles" icon="star" title="Our reward principles"
        isSet=${(doc.principles || []).length > 0} canEdit=${canEdit} onAdd=${() => onEdit("principles")}>
        <ol class="sd-principles">${(doc.principles || []).map((p, i) => html`<li key=${i}>${p}</li>`)}</ol>
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

    <//>`;
}

function orgCompareWords(me, doc) {
  // R1: the comparator IN WORDS, never a benchmark table. House vocabulary: the peer
  // member is a "company" (lumi-terminology), and the label already carries its unit.
  const label = doc.comparator_label || "All peers";
  const cut = doc.comparator_cut || "";
  if (!cut || label === "All peers") return "We compare ourselves to UK companies across our whole peer group.";
  if (cut.startsWith("industry::")) return "We compare ourselves to UK companies in our sector — " + label + ".";
  if (cut.startsWith("fte_band::")) return "We compare ourselves to UK companies of similar size — " + label + ".";
  return "We compare ourselves to our peer group, " + label + ".";
}

function StrategyView({ me, data, strat, onEdit, canEdit = true, onReload }) {
  const orgName = (me.org && me.org.name) || "Your organisation";
  const stance = sdStance(strat, orgName);
  // R1 (2026-08-14): the exported document carries NO peer figures by default — the
  // live position exhibit is an optional evidence block, off in print until opted in.
  // R1 inverted (2026-08-15, reward-director review): the EVIDENCE belongs in the
  // approved document; the AI reading never prints. A board paper of assertions with
  // the data removed was exactly backwards.
  const [approving, setApproving] = useState(false);
  const [apOpen, setApOpen] = useState(false);
  const [apForm, setApForm] = useState({});
  const [versions, setVersions] = useState(null);
  const [showVers, setShowVers] = useState(false);
  const ver = data.version || null;
  const sub = data.submitted || null;
  const canApprove = data.can_approve;
  const doc0 = data.document || {};
  // What is empty right now — shown BEFORE approving, never discovered after.
  // MUST mirror _unstated_sections() in app.py, which is what the version record
  // stores: this list used to count Governance / Commitments / Measures / Roadmap,
  // all retired from capture 2026-08-15, so every approval warned about four
  // sections nobody could ever state.
  const unstated = [
    ["Principles", (doc0.principles || []).length],
    ["Peer group", doc0.comparator_cut != null ? 1 : 0],
    ["Constraints", ((doc0.constraints || {}).selected || []).length || ((doc0.constraints || {}).notes ? 1 : 0)],
    ["Position by level", (doc0.population_targets || []).length],
    ["Action plan", doc0.action_plan ? 1 : 0],
  ].filter(r => !r[1]).map(r => r[0]);
  const loadVersions = () => { setShowVers(v => !v);
    if (versions === null) api("/api/strategy/versions").then(r => setVersions(r.versions || [])).catch(() => setVersions([])); };
  const [planBusy, setPlanBusy] = useState(false);
  const buildPlan = async () => {
    if (planBusy) return;
    setPlanBusy(true);
    try {
      const r = await api("/api/strategy/plan", { method: "POST", body: {} });
      if (r && r.ok === false) toast(r.reason === "locked" ? "Your insights unlock once your data is in." : "Set your strategy first.", "error");
      else { onReload && onReload(); toast("Plan built from your gaps."); }
    } catch (e) { toast(e && e.message || "Couldn't build the plan.", "error"); }
    setPlanBusy(false);
  };
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
  const when = data.completed_at ? fmtDate(data.completed_at) : null;
  const valOf = (f) => f === "benefits_lead"
    ? ((strat.benefits_lead || []).length ? "Leads on " + (strat.benefits_lead || []).map(x => (BENEFITS.find(b => b.v === x) || {}).t.toLowerCase()).join(", ") : null)
    : (strat[f] ? labelOf(f, strat[f]) : null);
  const ctxBits = [];   // every dial is live post-2026-08-09 — the demoted strip retired
  // ---- 2026-08-16 simplification ----
  // Four progress systems used to sit on a six-section document: a completeness
  // meter, a jump-nav of state dots, "Part 1 / Part 2" dividers and a per-card
  // Stated / Not yet stated badge. The badge alone carries it; the rest were
  // ceremony on a page you can read in one scroll. All three are gone.
  //
  // The stance prose and the eleven-row dial ledger also said the same thing
  // twice — the ledger adding a boilerplate "why it matters" column identical
  // for every org. The dials are now a chip strip under the prose they explain.
  const DIALS = ["market_position", "reward_mix", "pay_for_performance", "transparency",
                 "location_approach", "benefits_lead", "family_position",
                 "primary_objective", "budget_direction", "acute_pressure", "risk_appetite"];
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
        </div>
      </div>
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

        <section class="sd-sec sdx-card sdx-lead" id="sdx-stance">
          <${SecHead} icon="flag" title="What we say" chip=${html`<span class="sdx-state live">From your dials</span>`} />
          ${stance.length ? stance.map((s, i) => html`<p key=${i} class=${"sd-stance" + (i === 0 ? " lead" : "")}>${s}</p>`)
            : html`<p class="sd-stance">No positions set yet — your benchmark is read neutrally.</p>`}
          <div class="sdx-dials">
            ${DIALS.map(f => { const v = valOf(f) || (strat[f] ? labelOf(f, strat[f]) : null);
              const extra = f === "market_position" && Object.keys(strat.domain_targets || {}).length;
              return html`<span key=${f} class=${"sdx-dchip" + (v ? "" : " off")} title=${SD_DRIVES[f] || ""}>
                <i>${DIAL_LABEL[f]}</i>${v || "Not set"}${extra ? html` <u>+${extra}</u>` : ""}</span>`; })}
          </div>
          <div class="sd-note">Below or above market here is a choice, not a verdict — lumi reads your numbers through it.</div>
        </section>

        <${SdDocSections} data=${data} canEdit=${canEdit} onEdit=${onEdit} onPlan=${buildPlan}
          which=${["principles", "comparator", "constraints"]} />

        <${SdDocSections} data=${data} canEdit=${canEdit} onEdit=${onEdit} onPlan=${() => nav("/plan")}
          which=${["populations"]} />

        <section class="sd-sec sdx-card no-print sdx-handoff">
          <${SecHead} icon="download" title="Take this away" chip=${html`<span class="sdx-state live">Document</span>`} />
          <p class="sd-note sd-ex-cap">Your <b>Total Reward Strategy</b> as a laid-out document — cover, stated
            intent, principles, lumi's written reading of it, and the approval record — ready to save as a PDF
            and put in front of a board.</p>
          <div class="row" style=${{ gap: "var(--s2)", flexWrap: "wrap" }}>
            <button class="btn primary" onClick=${() => nav("/report/strategy")}><${Icon} name="download" size=${13} /> Open the strategy document</button>
            <button class="btn" onClick=${() => nav("/plan")}><${Icon} name="zap" size=${13} /> Where you stand against it</button>
          </div>
        </section>

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
  const [cuts, setCuts] = useState(null);
  const [cmpSectors, setCmpSectors] = useState([]);
  const [cmpSizes, setCmpSizes] = useState([]);
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
  // every level starts at the median (2026-08-15, David: "default it all to the median
  // and the user can then adjust") — seeded when the member actually reaches the step,
  // never during render.
  useEffect(() => {
    if (!data) return;
    const pg = PAGES[typeof step === "number" && step >= 0 && step < PAGES.length ? step : 0];
    if (!pg || pg.id !== "populations") return;
    setDoc(d => ((d.population_targets || []).length ? d
      : { ...d, population_targets: (data.populations || []).map(l => ({ label: l, position: "match" })) }));
  }, [step, data]);

  // the commitments step needs the live lookups — fetched once, on first entry
  useEffect(() => {
    if (!data || mopts !== null) return;                 // once, as soon as the wizard has data
    api("/api/strategy/measure-options").then(r => setMopts(r)).catch(() => setMopts({ options: [] }));
    api("/api/peer-groups").then(r => setGroups(r.groups || r || [])).catch(() => setGroups([]));
    api("/api/peer-groups/options").then(r => setChoices(r)).catch(() => setChoices({}));
    api("/api/cuts").then(r => setCuts(r)).catch(() => setCuts({}));
    // seed the picker from the org's CURRENT peer group — one control, one truth
    api("/api/me").then(r => {
      const c = ((r.org || {}).signal_peer_criteria) || {};
      setCmpSectors(c.industry || []); setCmpSizes(c.fte_band || []);
    }).catch(() => {});
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
  const OBJ_BUDGET = 10;
  const objW = strat.objective_weights || {};
  const objLeft = OBJ_BUDGET - Object.values(objW).reduce((a, b) => a + (b || 0), 0);
  const setObj = (k, v) => setStrat(st2 => {
    const w = { ...(st2.objective_weights || {}) };
    if (v <= 0) delete w[k]; else w[k] = v;
    const top = Object.entries(w).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0];
    return { ...st2, objective_weights: w, primary_objective: top ? top[0] : st2.primary_objective };
  });
  const bandLow = (x) => { const m = String(x).replace(/,/g, "").match(/\d+/); return m ? parseInt(m[0], 10) : 0; };
  const cons = doc.constraints || {};
  const principles = doc.principles || [];
  const pops = doc.population_targets || [];
  const isSet = (p) => ({
    facts: planeA.every(f => f.value),
    // the comparator only counts as SET when the member actually chose one — a default
    // must never be scored as a decision (both persona reviews caught this)
    compare: doc.comparator_cut != null,
    phil: !!(strat.market_position && strat.reward_mix),
    populations: (doc.population_targets || []).length > 0,
    post: !!strat.primary_objective,
    principles: principles.filter(p2 => (p2 || "").trim()).length > 0,
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
    if (cur.id === "post" && !strat.primary_objective) { flash("Give at least one objective some points to continue."); return; }
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
      // the peer group is saved through the SAME route Settings uses, so there is one
      // code path and one resulting cut (criteria -> single cut / group, server-side)
      if (cmpSectors.length || cmpSizes.length) {
        await api("/api/org/signal-peers", { method: "PUT",
          body: { criteria: { industry: cmpSectors, fte_band: cmpSizes } } });
      }
      const docOut = { ...doc };
      delete docOut.comparator_label;
      delete docOut.comparator_cut;              // derived from the peer group above
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
            <p class="strat-sub">Name the market first — "above market" only means something once you've said which market. This is <b>your organisation's peer group</b>: the one your benchmark, your signals and this document all read from.</p>
          </header>
          <div class="sdw-dials">
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="users" size=${16} /></span>
                <div><div class="dial-title">Your peer group</div>
                <div class="dial-q">Pick the sectors and sizes you compare against — the SAME control as Settings, because it is the same peer group. Change it here and every benchmark read changes with it.</div></div></div>
              ${!cuts ? html`<p class="sd-note">Loading your peer options…</p>` : html`
                <div class="sigpeer-grid">
                  ${["industry", "fte_band"].map(dim => {
                    const opts = dim === "industry" ? Object.entries(cuts.industries || {})
                      : Object.entries(cuts.fte_bands || {}).sort((x, y) => bandLow(x[0]) - bandLow(y[0]));
                    const sel = dim === "industry" ? cmpSectors : cmpSizes;
                    const setSel = dim === "industry" ? setCmpSectors : setCmpSizes;
                    const suffix = dim === "industry" ? "" : " FTE";
                    return html`<div key=${dim} class="sigpeer-col">
                      <div class="sigpeer-lbl">${dim === "industry" ? "Sectors" : "Sizes"}</div>
                      <div class="sigpeer-opts">
                        ${opts.map(([v, n]) => html`<label key=${v} class=${"sigpeer-chk" + (sel.includes(v) ? " on" : "")}>
                          <input type="checkbox" checked=${sel.includes(v)}
                            onChange=${() => setSel(sel.includes(v) ? sel.filter(x => x !== v) : [...sel, v])} />
                          <span class="sigpeer-name">${v}${suffix}</span><span class="sigpeer-n">${n}</span></label>`)}
                      </div>
                    </div>`; })}
                </div>`}
              <div class="signal-effect"><span class="se-eye"><${Icon} name="sparkle" size=${14} /></span>
                <span class="se-text">${(cmpSectors.length + cmpSizes.length)
                  ? "We compare ourselves to UK companies matching " + [cmpSectors.join(", "), cmpSizes.map(z => z + " FTE").join(", ")].filter(Boolean).join(" · ") + "."
                  : "We compare ourselves to UK companies across our whole peer group."}
                  <b> Saving moves your whole benchmark to this group.</b></span></div>
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
            sub=${"Every level starts at the median. Adjust any that sit differently by design — these are the same levels your matrix questions use, so a position here reads straight against them."} />
          <div class="sdw-dials">
            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="layers" size=${16} /></span>
                <div><div class="dial-title">Position by level <span class="sdw-opt">all seven</span></div>
                <div class="dial-q">Your overall position${strat.market_position ? html` (<b>${labelOf("market_position", strat.market_position)}</b>)` : ""} is the organisation-wide aim; these say where each level sits within it.</div></div></div>
              ${(data.populations || []).map(lbl => {
                const row = pops.find(p => p.label === lbl) || { label: lbl, position: "match" };
                const setPop = (patch) => setD({ population_targets:
                  (data.populations || []).map(l2 => {
                    const cur2 = pops.find(p => p.label === l2) || { label: l2, position: "match" };
                    return l2 === lbl ? { ...cur2, ...patch } : cur2;
                  }) });
                const off = row.position && row.position !== "match";
                return html`<div key=${lbl} class=${"sdw-poprow" + (off ? " off" : "")}>
                  <div class="sdw-pop-head">
                    <span class="sdw-pop-name">${lbl}</span>
                    <div class="sdw-popseg" role="radiogroup" aria-label=${lbl + " market position"}>
                      ${SCALE.market.stops.map(st2 => html`<button key=${st2.v} type="button"
                        class=${"sdw-seg-opt" + (row.position === st2.v ? " on" : "")}
                        role="radio" aria-checked=${row.position === st2.v}
                        onClick=${() => setPop({ position: st2.v })}>${st2.t}</button>`)}
                    </div>
                  </div>
                  ${off ? html`<input class="ctl" maxlength="240" placeholder=${"Why " + lbl + " sits differently (optional)"}
                    value=${row.note || ""} onInput=${e => setPop({ note: e.target.value })} />` : null}
                </div>`; })}
              <div class="signal-effect"><span class="se-eye"><${Icon} name="info" size=${14} /></span>
                <span class="se-text">These are statements in your document. Your benchmark reads the whole organisation, so lumi never marks a level position right or wrong.</span></div>
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
            <div class="dial-card" id="dial-primary_objective">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="target" size=${16} /></span>
                <div><div class="dial-title">What reward is for, right now
                  <span class=${"sdw-opt" + (objLeft === 0 ? " done" : "")}>${objLeft} of ${OBJ_BUDGET} points left</span></div>
                <div class="dial-q">Spread ${OBJ_BUDGET} points across these. You cannot give everything to everything — where the points go is the priority we surface first.</div></div></div>
              ${OBJECTIVES.map(o => { const v = (strat.objective_weights || {})[o.v] || 0; return html`
                <div key=${o.v} class="sdw-objrow">
                  <div class="sdw-obj-l"><b>${o.t}</b><span>${o.d}</span></div>
                  <div class="sdw-obj-r">
                    <button type="button" class="sdw-obj-btn" disabled=${v <= 0} aria-label=${"Less " + o.t}
                      onClick=${() => setObj(o.v, v - 1)}>−</button>
                    <span class="sdw-obj-n">${v}</span>
                    <button type="button" class="sdw-obj-btn" disabled=${objLeft <= 0} aria-label=${"More " + o.t}
                      onClick=${() => setObj(o.v, v + 1)}>+</button>
                    <span class="sdw-obj-bar" aria-hidden="true"><i style=${{ width: (100 * v / OBJ_BUDGET) + "%" }}></i></span>
                  </div>
                </div>`; })}
              ${strat.primary_objective ? html`<div class="signal-effect"><span class="se-eye"><${Icon} name="sparkle" size=${14} /></span>
                <span class="se-text">Your highest-rated objective — <b>${labelOf("primary_objective", strat.primary_objective)}</b> — is the lens your signals surface first.</span></div>` : null}
            </div>
            ${dialsOf(POST.filter(f => f !== "primary_objective"))}
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
          <${ReviewSection} title="Your principles" chip="optional" chipCls="choices"
            rows=${[
              { label: "Reward principles", value: principles.filter(p2 => (p2 || "").trim()).length ? principles.filter(p2 => (p2 || "").trim()).length + " stated" : "Not included", skipped: !principles.filter(p2 => (p2 || "").trim()).length, field: "principles" },
              { label: "Position by level", value: pops.length ? pops.map(p => p.label).join(", ") : "Not included", skipped: !pops.length, field: "populations" },
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
  // the SAME wording the benchmark and Signals use for the peer group (server
  // _default_cut_info): sector name, "<band> FTE", or the saved group's name.
  const cut = (doc || {}).comparator_cut;
  if (!cut) return "All peers";
  const [dim, val] = cut.split("::");
  if (dim === "industry") return val;
  if (dim === "fte_band") return val + " FTE";
  const g = (groups || []).find(x => x.group_id === val);
  return g ? g.name : "All peers";
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

// ============================ REWARD PLAN =====================================
// The strategy section says what you INTEND. This says where you actually are, the
// gaps between the two, and what to do about them (2026-08-15, David: "a whole new
// section which shows where you are now, the gaps and the plan to improve with roi").
// Everything here is engine-computed: positions from the benchmark, gaps from the
// alignment rules, levers from David's inventory, £ from the money model.
const RP_STATUS = { evidenced: { t: "Holding", cls: "ok" }, behind_intent: { t: "Behind intent", cls: "warn" },
  contradicted: { t: "Contradicted", cls: "bad" }, not_evidenced: { t: "Not yet evidenced", cls: "" } };

window.RewardPlanPage = function ({ me }) {
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(null);            // which gap's options are expanded
  const canEdit = me && me.user && ["admin", "contributor"].includes(me.user.role);
  const load = () => api("/api/strategy/alignment").then(setD).catch(e => setErr(e.message));
  useEffect(() => { load(); }, []);
  if (err) return html`<${EmptyState} tone="error" icon="compass" title="Couldn't load your reward plan"
    body=${err + " — nothing is lost."}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!d) return html`<${PageLoading} />`;
  if (d.ok === false) return html`<${EmptyState} icon="compass" title="Set your reward strategy first"
    body="Your plan is built from the gap between what you said you'd do and what your data shows — so it starts with your strategy."
    action=${html`<button class="btn small primary" onClick=${() => nav("/strategy")}>Go to Reward strategy</button>`} />`;

  const commitments = d.commitments || [];
  const gaps = commitments.filter(c => c.status === "behind_intent" || c.status === "contradicted");
  const holding = commitments.filter(c => c.status === "evidenced");
  const unevidenced = commitments.filter(c => c.status === "not_evidenced");
  const plan = d.plan;
  const optsFor = (id) => (d.options || []).find(o => o.commitment_id === id);
  // ---- gaps grouped BY DOMAIN (2026-08-16) ----------------------------------
  // A flat list of nine gaps made you assemble "everything about Pay" in your own
  // head. They group by category now, so each domain is one card you can act on —
  // and each card carries the two ways out of it: its signals, and its data.
  const domAlign = {};
  (d.domains || []).forEach(x => { domAlign[x.name] = (x.target || {}).alignment; });
  const groups = [];
  gaps.forEach(c => {
    let g = groups.find(x => x.cat === c.category);
    if (!g) { g = { cat: c.category, items: [], align: domAlign[c.category] }; groups.push(g); }
    g.items.push(c);
  });
  // David 2026-08-16: "the reward plan must link to signals — so the user can jump
  // into any domain and see what they need to do for alignment". The feed already
  // filters on domain and on strategy alignment; this hands it both at once.
  const toSignals = (cat, align) => {
    window.__sigJump = { domain: cat, strat: align ? [align] : [] };
    nav("/signals");
  };
  const build = async () => {
    setBusy(true);
    try { const r = await api("/api/strategy/plan", { method: "POST", body: {} });
      if (r && r.ok === false) toast(r.reason === "locked" ? "Your insights unlock once your data is in." : "Set your strategy first.", "error");
      else { await load(); toast("Plan rebuilt from your current gaps."); }
    } catch (e) { toast(e && e.message || "Couldn't build the plan.", "error"); }
    setBusy(false);
  };

  return html`
    <div class="rp-wrap">
      <div class="rp-hero">
        <div>
          <div class="sd-eyebrow sdx-eyebrow">Reward plan</div>
          <h1 class="sdx-org">Where you are, and what to do about it</h1>
          <p class="strat-sub">Your stated strategy against your own data on <b>${d.cut_label}</b>${d.objective ? html`, read through your <b>${d.objective}</b> objective` : ""}.</p>
        </div>
        <div class="rp-hero-side">
          <div class="rp-tally">
            <div class="rp-tally-n">${gaps.length}</div>
            <div class="rp-tally-l">${gaps.length === 1 ? "gap to close" : "gaps to close"}</div>
          </div>
          <button class="btn quiet" onClick=${() => nav("/strategy")}>View your strategy</button>
        </div>
      </div>

      ${/* ---- 1. where you are now ---- */ ""}
      <section class="card rp-sec">
        <h2 class="rp-h">Where you are now</h2>
        <p class="sd-note sd-ex-cap">The shaded band is your strategy; the dot is where you land. Pick any area to open its signals.</p>
        <div class="sd-ex-row sd-ex-head" aria-hidden="true">
          <span class="sd-axis-key"><span class="sd-zone-swatch"></span> your strategy <span class="sd-mark actual"></span> your position</span>
          <span class="sd-axis sd-axis-labels">${SD_ZONES_F().map(([l, r], i) => html`<i key=${i} style=${{ left: ((l + r) / 2) + "%" }}>${["below", "on market", "above"][i]}</i>`)}</span>
          <span></span>
        </div>
        <div class="sd-exhibit">
          ${(d.domains || []).map(dom => {
            const al = (dom.target || {}).alignment;
            const read = al === "on_target" ? { t: "On strategy", cls: "ok" } : al === "ahead" ? { t: "Above strategy", cls: "ahead" }
              : al === "behind" ? { t: "Below strategy", cls: "behind" } : { t: "—", cls: "" };
            return html`<button key=${dom.name} class="sd-ex-row rp-ex-row" onClick=${() => toSignals(dom.name, al)}
              title=${"See " + domainLabel(dom.name) + " signals for this alignment"}>
              <span class="sd-ex-name">${dom.name}</span>
              <${SdAxis} intent=${(dom.target || {}).stance} actual=${dom.position && dom.position.verdict}
                pctl=${dom.position && dom.position.depth_pctl} align=${al} />
              <span class=${"sd-ex-read " + read.cls}>${read.t}</span>
            </button>`; })}
        </div>
        <div class="rp-tiles">
          ${[["off strategy", gaps.length, "warn"], ["holding", holding.length, "ok"],
             ["not yet evidenced", unevidenced.length, ""]].map(([l, n, cls]) => html`
            <div key=${l} class=${"rp-tile " + cls}>
              <div class="rp-tile-n">${n}</div>
              <div class="rp-tile-l">${l}</div>
            </div>`)}
        </div>
      </section>

      ${/* ---- 2. the gaps, one card per domain ---- */ ""}
      <section class="card rp-sec" id="rp-gaps">
        <h2 class="rp-h">The gaps <span class="rp-h-n">${gaps.length}</span></h2>
        <p class="sd-note sd-ex-cap">One card per area. Every card ends with the two ways in: the live signals for that area, and the data behind them.</p>
        ${groups.length ? html`<div class="rp-groups">
          ${groups.map(g => html`
            <div key=${g.cat} class="rp-group">
              <div class="rp-group-head">
                <h3 class="rp-group-t">${domainLabel(g.cat)}</h3>
                <span class=${"rp-chip " + (g.items.some(c => c.status === "contradicted") ? "bad"
                  : g.items.every(c => c.direction === "past") ? "warn" : "warn")}>${
                  g.items.some(c => c.status === "contradicted") ? "Contradicted"
                    : g.items.every(c => c.direction === "past") ? "Past intent" : "Behind intent"}</span>
              </div>
              ${g.items.map(c => { const ob = optsFor(c.id); return html`
                <div key=${c.id} class="rp-gap">
                  <p class="rp-gap-say">${c.statement}</p>
                  ${ob && ob.levers && ob.levers.length ? html`
                    <button class="rp-more" onClick=${() => setOpen(open === c.id ? null : c.id)}>
                      ${open === c.id ? "Hide" : "What the market does about it"} · ${ob.levers.length}</button>
                    ${open === c.id ? html`
                      <div class="rp-levers">
                        <p class="caption">${ob.framing}</p>
                        ${ob.levers.map(l => html`<div key=${l.lever_id} class="rp-lever">
                          <div class="rp-lever-t"><b>${l.name}</b> <span class="sd-doc-meta">${l.cost_character} · ${l.speed} · ${l.reversibility} to reverse</span></div>
                          <div class="caption">${l.what_it_is}</div>
                          <div class="caption rp-trade"><${Icon} name="info" size=${12} /> ${l.trade_off}</div>
                        </div>`)}
                      </div>` : null}`
                  : ob && ob.coverage_note ? html`<p class="sd-note rp-note">${ob.coverage_note}</p>` : null}
                </div>`; })}
              <div class="rp-group-foot">
                <button class="rp-go" onClick=${() => toSignals(g.cat, g.align)}>
                  <${Icon} name="zap" size=${13} /> ${domainLabel(g.cat)} signals</button>
                <a class="rp-go" href=${"#/category/" + encodeURIComponent(g.cat)}>
                  <${Icon} name="bar-chart" size=${13} /> The data behind it</a>
              </div>
            </div>`)}
        </div>`
        : html`<${EmptyState} icon="check" title="Nothing is off strategy"
            body="Every commitment your data can speak to matches what you said. Come back after your next data refresh." />`}
        ${unevidenced.length ? html`<p class="sd-note">${unevidenced.length} commitment${unevidenced.length === 1 ? "" : "s"} can't be assessed yet — the metrics behind ${unevidenced.length === 1 ? "it" : "them"} are unanswered.</p>` : null}
      </section>

      ${/* ---- 3. the plan ---- */ ""}
      <section class="card rp-sec">
        <div class="rp-h-row">
          <h2 class="rp-h">The plan</h2>
          ${canEdit ? html`<button class="btn ${plan ? "" : "primary"}" disabled=${busy} onClick=${build}>
            ${busy ? "Building…" : plan ? "Rebuild" : "Build my plan"}</button>` : null}
        </div>
        ${plan ? html`
          <p class="sd-stance lead">${plan.summary}</p>
          <div class="rp-actions">
            ${(plan.actions || []).map((a, i) => html`
              <div key=${i} class="rp-action">
                <div class="rp-action-n">${i + 1}</div>
                <div class="rp-action-b">
                  <div class="rp-action-t">${a.title} <span class="sd-doc-meta">${domainLabel(a.category || "")} · ${a.horizon}</span></div>
                  <div class="caption">${a.why}</div>
                  <div class="rp-roi"><${Icon} name="coins" size=${13} /> ${a.roi}</div>
                </div>
              </div>`)}
          </div>
          <p class="sd-note">${plan.basis} Built ${plan.built_at ? fmtDate(plan.built_at) : ""}.</p>`
        : html`<${EmptyState} icon="zap" title="No plan built yet"
            body="lumi will turn the gaps above into a sequenced plan — each action with what it typically returns, using the indicative £ from your own benchmark."
            action=${canEdit ? html`<button class="btn small primary" disabled=${busy} onClick=${build}>${busy ? "Building…" : "Build my plan"}</button>` : null} />`}
      </section>

      ${/* ---- 4. take it away ---- */ ""}
      <section class="card rp-sec rp-handoff">
        <div class="rp-h-row">
          <div>
            <h2 class="rp-h">Take this away</h2>
            <p class="sd-note sd-ex-cap">Everything above as a laid-out <b>Reward Position ${"&"} Plan</b> report —
              executive summary, findings, the gaps with their options and trade-offs, and the plan with what
              each action returns. Ready to save as a PDF.</p>
          </div>
          <button class="btn primary" onClick=${() => nav("/report/plan")}>
            <${Icon} name="download" size=${13} /> Open the report</button>
        </div>
      </section>
    </div>`;
};
