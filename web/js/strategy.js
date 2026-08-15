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

// ---- Total Reward Strategy document sections (2026-08-14, brief v2 Artefact A) ----
// The document-grade content: principles, comparator, constraints, governance,
// commitments, measures, roadmap. View renders "Not yet stated" honestly (never
// silently dropped); Admins edit inline per section — member words only, the model
// never authors a commitment (guardrail 9). Saves ride the same PUT as the wizard.
const CONSTRAINT_LABEL = { affordability: "Affordability", collective_bargaining: "Collective bargaining",
  statutory_pressure: "Statutory / regulatory pressure", headcount_change: "Headcount change",
  system_change: "Systems / payroll change", other: "Other" };
const CADENCE_LABEL = { annual: "Annually", twice_yearly: "Twice a year", quarterly: "Quarterly", ad_hoc: "Ad hoc" };
const HORIZON_LABEL = { this_cycle: "This cycle", next_cycle: "Next cycle", multi_cycle: "Multi-cycle" };

function SdDocSec({ id, icon, title, note, isSet, editing, canEdit, onEdit, onCancel, onSave, saving, children, editor }) {
  // 2026-08-15 redesign: every section is a DEFINED card — icon chip, title, an honest
  // status chip, a real Edit button; an empty section renders an add-tile (a genuine
  // affordance), never just grey text. The "01 —" numbered eyebrows are retired.
  return html`
    <section class="sd-sec sdx-card" id=${id}>
      <div class="sdx-sechead">
        <span class=${"sdx-ico" + (isSet ? " on" : "")}><${Icon} name=${icon} size=${15} /></span>
        <h3 class="sdx-title">${title}</h3>
        <span class=${"sdx-state " + (isSet ? "set" : "empty")}>${isSet ? "Stated" : "Not yet stated"}</span>
        ${canEdit && !editing && isSet ? html`<button class="sd-doc-edit no-print" onClick=${onEdit}>Edit</button>` : null}
      </div>
      ${note && !editing ? html`<p class="sd-note sd-ex-cap">${note}</p>` : null}
      ${editing ? html`<div class="sd-doc-editor no-print">${editor}
        <div class="sd-doc-edfoot">
          <button class="btn primary" disabled=${saving} onClick=${onSave}>${saving ? "Saving…" : "Save"}</button>
          <button class="btn quiet" disabled=${saving} onClick=${onCancel}>Cancel</button>
        </div></div>`
      : isSet ? children
      : canEdit ? html`<button class="sdx-addtile no-print" onClick=${onEdit}><${Icon} name="plus" size=${14} /> Add ${title.toLowerCase()}</button>
                  <p class="sd-stance sd-unstated print-only-line">Not yet stated.</p>`
      : html`<p class="sd-stance sd-unstated">Not yet stated.</p>`}
    </section>`;
}

function SdDocSections({ me, data, canEdit, onReload, which }) {
  // `which` (2026-08-15 redesign): render only the named sections, so the document can
  // group them under the brief's three-part spine (Intent / Position / Delivery).
  const show = (k) => !which || which.includes(k);
  const doc = data.document || {};
  const [editing, setEditing] = useState(null);     // section key being edited
  const [draft, setDraft] = useState({});
  const [saving, setSaving] = useState(false);
  const [groups, setGroups] = useState(null);       // saved peer groups (lazy)
  const [choices, setChoices] = useState(null);     // industry/size vocab (lazy)
  const [mopts, setMopts] = useState(null);         // measure options (lazy)
  const open = (key, seed) => {
    setEditing(key); setDraft(seed);
    if (key === "comparator" && groups === null) {
      api("/api/peer-groups").then(r => setGroups(r.groups || r || [])).catch(() => setGroups([]));
      api("/api/peer-groups/options").then(r => setChoices(r)).catch(() => setChoices({}));
    }
    if ((key === "measures" || key === "commitments") && mopts === null)
      api("/api/strategy/measure-options").then(r => setMopts(r)).catch(() => setMopts({ options: [] }));
  };
  const close = () => { setEditing(null); setDraft({}); };
  const save = async (patch) => {
    setSaving(true);
    try {
      const d = { ...doc }; delete d.comparator_label;
      await api("/api/strategy", { method: "PUT", body: {
        strategy: data.strategy, document: { ...d, ...patch },
        // preserve the transparency reconfirm state — a document edit must never
        // silently demote a live dial back to inert (engine reads live-only)
        transparency_confirmed: (data.provenance || {}).transparency === "live" } });
      apiCacheInvalidate("/api/overview");
      close(); onReload && onReload();
    } catch (e) { toast(e && e.message || "Couldn't save — try again.", "error"); }
    setSaving(false);
  };
  const gov = doc.reward_governance || {};
  const cons = doc.constraints || {};
  const seg = doc.segments || {};
  const cm = doc.commitments || {};
  const wb = (cm["Wellbeing"] || {}).metric_ids || [];
  const gvStmt = (cm["Governance & Transparency"] || {}).statement || "";
  const notStated = html`<p class="sd-stance sd-unstated">Not yet stated.</p>`;
  const mTitle = (qid) => { const o = ((mopts || {}).options || []).find(x => x.id === qid); return o ? o.title : qid; };

  return html`
    <${React.Fragment}>
      ${show("principles") && html`<${SdDocSec} id="sdx-principles" icon="star" title="Our reward principles" isSet=${(doc.principles || []).length > 0}
        canEdit=${canEdit} editing=${editing === "principles"} saving=${saving}
        onEdit=${() => open("principles", { principles: [...(doc.principles || [])], seg: { ...seg } })}
        onCancel=${close} onSave=${() => save({ principles: (draft.principles || []).filter(p => p.trim()),
          segments: draft.seg && (draft.seg.differentiated || (draft.seg.segments || []).length) ? draft.seg : null })}
        editor=${html`<div>
          ${Array.from({ length: Math.min(6, (draft.principles || []).length + 1) }, (_, i) => html`
            <input key=${i} class="ctl sd-doc-in" maxlength="140" placeholder=${"Principle " + (i + 1) + " — your words, ~140 characters"}
              value=${(draft.principles || [])[i] || ""}
              onInput=${e => setDraft(d => { const p = [...(d.principles || [])]; p[i] = e.target.value; return { ...d, principles: p }; })} />`)}
          <label class="sd-doc-check"><input type="checkbox" checked=${!!(draft.seg || {}).differentiated}
            onChange=${e => setDraft(d => ({ ...d, seg: { ...(d.seg || {}), differentiated: e.target.checked } }))} />
            We deliberately pay more for scarce or critical segments</label>
          ${(draft.seg || {}).differentiated ? html`<input class="ctl sd-doc-in" placeholder="Name the segments, comma-separated (e.g. Engineering, HGV drivers)"
            value=${((draft.seg || {}).segments || []).join(", ")}
            onInput=${e => setDraft(d => ({ ...d, seg: { ...(d.seg || {}), segments: e.target.value.split(",").map(s => s.trim()).filter(Boolean).slice(0, 6) } }))} />` : null}
        </div>`}>
        ${(doc.principles || []).length ? html`<ol class="sd-principles">
            ${doc.principles.map((p, i) => html`<li key=${i}>${p}</li>`)}</ol>` : notStated}
        ${seg.differentiated ? html`<p class="sd-note">Pay is deliberately differentiated for: <b>${(seg.segments || []).join(", ") || "named segments"}</b>.</p>` : null}
      <//>`}

      ${show("comparator") && html`<${SdDocSec} id="sdx-comparator" icon="users" title="Who we compare ourselves to" isSet=${true}
        note="The comparator in words — figures live in the benchmark, not here."
        canEdit=${canEdit} editing=${editing === "comparator"} saving=${saving}
        onEdit=${() => open("comparator", { comparator_cut: doc.comparator_cut || "all" })}
        onCancel=${close} onSave=${() => save({ comparator_cut: draft.comparator_cut === "all" ? null : draft.comparator_cut })}
        editor=${html`<div>
          <select class="ctl" value=${draft.comparator_cut || "all"}
            onChange=${e => setDraft(d => ({ ...d, comparator_cut: e.target.value }))}>
            <option value="all">All peers</option>
            ${((choices || {}).fields || []).filter(f => f.key === "industry").flatMap(f => f.choices || []).map(c =>
              html`<option key=${"i" + c} value=${"industry::" + c}>Sector — ${c}</option>`)}
            ${((choices || {}).fields || []).filter(f => f.key === "fte_band").flatMap(f => f.choices || []).map(c =>
              html`<option key=${"f" + c} value=${"fte_band::" + c}>Size — ${c}</option>`)}
            ${(groups || []).map(g => html`<option key=${g.group_id} value=${"group::" + g.group_id}>Saved group — ${g.name}</option>`)}
          </select>
          <p class="sd-note">A saved peer group can't be deleted while it is this strategy's comparator.</p>
        </div>`}>
        <p class="sd-stance">${orgCompareWords(me, doc)}</p>
      <//>`}

      ${show("constraints") && html`<${SdDocSec} id="sdx-constraints" icon="anchor" title="What constrains us" isSet=${!!((cons.selected || []).length || cons.notes)}
        canEdit=${canEdit} editing=${editing === "constraints"} saving=${saving}
        onEdit=${() => open("constraints", { sel: [...(cons.selected || [])], notes: cons.notes || "" })}
        onCancel=${close} onSave=${() => save({ constraints: { selected: draft.sel || [], notes: draft.notes || "" } })}
        editor=${html`<div>
          ${(data.constraint_options || []).map(c => html`<label key=${c} class="sd-doc-check">
            <input type="checkbox" checked=${(draft.sel || []).includes(c)}
              onChange=${e => setDraft(d => ({ ...d, sel: e.target.checked ? [...(d.sel || []), c] : (d.sel || []).filter(x => x !== c) }))} />
            ${CONSTRAINT_LABEL[c] || c}</label>`)}
          <input class="ctl sd-doc-in" maxlength="300" placeholder="Anything else worth naming (optional)"
            value=${draft.notes || ""} onInput=${e => setDraft(d => ({ ...d, notes: e.target.value }))} />
        </div>`}>
        ${(cons.selected || []).length || cons.notes ? html`
          <p class="sd-stance">${(cons.selected || []).map(c => CONSTRAINT_LABEL[c] || c).join(" · ")}${cons.notes ? (((cons.selected || []).length ? " — " : "") + cons.notes) : ""}</p>` : notStated}
      <//>`}

      ${show("governance") && html`<${SdDocSec} id="sdx-governance" icon="shield" title="How reward is governed" isSet=${!!Object.keys(gov).length}
        canEdit=${canEdit} editing=${editing === "governance"} saving=${saving}
        onEdit=${() => open("governance", { ...gov })}
        onCancel=${close} onSave=${() => save({ reward_governance: draft })}
        editor=${html`<div class="sd-doc-grid2">
          <label>Owner<input class="ctl" maxlength="80" placeholder="e.g. Chief People Officer" value=${draft.owner || ""}
            onInput=${e => setDraft(d => ({ ...d, owner: e.target.value }))} /></label>
          <label>Approved by<input class="ctl" maxlength="80" placeholder="e.g. Remuneration Committee" value=${draft.approver || ""}
            onInput=${e => setDraft(d => ({ ...d, approver: e.target.value }))} /></label>
          <label>Review cadence<select class="ctl" value=${draft.review_cadence || ""}
            onChange=${e => setDraft(d => ({ ...d, review_cadence: e.target.value || null }))}>
            <option value="">—</option>
            ${(data.cadence_options || []).map(c => html`<option key=${c} value=${c}>${CADENCE_LABEL[c] || c}</option>`)}
          </select></label>
          <label>Effective date<input class="ctl" type="date" value=${draft.effective_date || ""}
            onInput=${e => setDraft(d => ({ ...d, effective_date: e.target.value }))} /></label>
        </div>`}>
        ${Object.keys(gov).length ? html`<div class="sd-ledger">
          ${[["Owner", gov.owner], ["Approved by", gov.approver],
             ["Review cadence", gov.review_cadence && (CADENCE_LABEL[gov.review_cadence] || gov.review_cadence)],
             ["Effective date", gov.effective_date]].filter(r => r[1]).map(([k, v]) => html`
            <div key=${k} class="sd-led-row"><span class="sd-led-name">${k}</span><span class="sd-led-val">${v}</span><span class="sd-led-why"></span></div>`)}
        </div>` : notStated}
      <//>`}

      ${show("commitments") && html`<${SdDocSec} id="sdx-commitments" icon="heart" title="What we offer and how we operate" isSet=${!!(wb.length || gvStmt)}
        note="Wellbeing is measured by what's offered, not a market rate; governance by how you operate — stated here as commitments, never positions."
        canEdit=${canEdit} editing=${editing === "commitments"} saving=${saving}
        onEdit=${() => open("commitments", { wb: [...wb], stmt: gvStmt })}
        onCancel=${close} onSave=${() => { const c = {};
          if ((draft.wb || []).length) c["Wellbeing"] = { metric_ids: draft.wb };
          if ((draft.stmt || "").trim()) c["Governance & Transparency"] = { statement: draft.stmt.trim() };
          save({ commitments: c }); }}
        editor=${html`<div>
          <div class="sd-doc-sub">Wellbeing — what we will offer</div>
          ${mopts === null ? html`<p class="sd-note">Loading…</p>` :
            (mopts.options || []).filter(o => o.category === "Wellbeing").map(o => html`
              <label key=${o.id} class="sd-doc-check"><input type="checkbox" checked=${(draft.wb || []).includes(o.id)}
                onChange=${e => setDraft(d => { const w = new Set(d.wb || []); e.target.checked ? w.add(o.id) : w.delete(o.id);
                  return { ...d, wb: [...w].slice(0, 6) }; })} />${o.title}</label>`)}
          <div class="sd-doc-sub">Governance ${"&"} transparency — how we operate</div>
          <textarea class="ctl sd-doc-in" rows="3" maxlength="240"
            placeholder="Your words — e.g. 'Pay ranges are shared internally; equal-pay reviewed annually; every offer signed off against the framework.'"
            value=${draft.stmt || ""} onInput=${e => setDraft(d => ({ ...d, stmt: e.target.value }))}></textarea>
        </div>`}>
        ${wb.length ? html`<p class="sd-stance"><b>Wellbeing — we offer:</b> ${wb.map(mTitle).join(" · ")}</p>` : null}
        ${gvStmt ? html`<p class="sd-stance"><b>Governance —</b> ${gvStmt}</p>` : null}
        ${!wb.length && !gvStmt ? notStated : null}
      <//>`}

      ${show("measures") && html`<${SdDocSec} id="sdx-measures" icon="table" title="How we'll know it's working" isSet=${(doc.measures || []).length > 0}
        note="Measures are metrics lumi already measures — the review reports them against your comparator."
        canEdit=${canEdit} editing=${editing === "measures"} saving=${saving}
        onEdit=${() => open("measures", { m: [...(doc.measures || [])] })}
        onCancel=${close} onSave=${() => save({ measures: draft.m || [] })}
        editor=${html`<div>
          <p class="sd-note">Choose up to 8 — aim for 5+ covering each area you commit on. Greyed metrics are below the reporting floor on your current comparator.</p>
          <div class="sd-doc-mlist">
          ${mopts === null ? html`<p class="sd-note">Loading…</p>` :
            (mopts.options || []).map(o => html`
              <label key=${o.id} class=${"sd-doc-check" + (o.suppressed ? " dim" : "")}>
                <input type="checkbox" checked=${(draft.m || []).includes(o.id)}
                  disabled=${!(draft.m || []).includes(o.id) && (draft.m || []).length >= 8}
                  onChange=${e => setDraft(d => { const m = new Set(d.m || []); e.target.checked ? m.add(o.id) : m.delete(o.id);
                    return { ...d, m: [...m].slice(0, 8) }; })} />
                <span>${o.title} <span class="sd-doc-meta">${o.category}${o.context ? " · tracked as a level" : ""}${o.suppressed ? " · below floor here" : ""}</span></span>
              </label>`)}
          </div>
        </div>`}>
        ${(doc.measures || []).length ? html`<ol class="sd-principles">
          ${doc.measures.map(qid => html`<li key=${qid}>${mopts ? mTitle(qid) : qid}</li>`)}</ol>` : notStated}
      <//>`}

      ${show("roadmap") && html`<${SdDocSec} id="sdx-roadmap" icon="clock" title="What changes this year" isSet=${(doc.roadmap || []).length > 0}
        canEdit=${canEdit} editing=${editing === "roadmap"} saving=${saving}
        onEdit=${() => open("roadmap", { items: (doc.roadmap || []).map(r => ({ ...r })) })}
        onCancel=${close} onSave=${() => save({ roadmap: (draft.items || []).filter(r => (r.title || "").trim()) })}
        editor=${html`<div>
          ${Array.from({ length: Math.min(6, (draft.items || []).length + 1) }, (_, i) => { const it = (draft.items || [])[i] || {}; return html`
            <div key=${i} class="sd-doc-rmrow">
              <input class="ctl" maxlength="120" placeholder=${"Change " + (i + 1)} value=${it.title || ""}
                onInput=${e => setDraft(d => { const xs = [...(d.items || [])]; xs[i] = { ...(xs[i] || {}), title: e.target.value }; return { ...d, items: xs }; })} />
              <select class="ctl" value=${it.horizon || ""}
                onChange=${e => setDraft(d => { const xs = [...(d.items || [])]; xs[i] = { ...(xs[i] || {}), horizon: e.target.value || undefined }; return { ...d, items: xs }; })}>
                <option value="">When?</option>
                ${(data.horizon_options || []).map(h => html`<option key=${h} value=${h}>${HORIZON_LABEL[h] || h}</option>`)}
              </select>
            </div>`; })}
        </div>`}>
        ${(doc.roadmap || []).length ? html`<ol class="sd-principles">
          ${doc.roadmap.map((r, i) => html`<li key=${i}>${r.title}${r.horizon ? html` <span class="sd-doc-meta">· ${HORIZON_LABEL[r.horizon] || r.horizon}</span>` : ""}</li>`)}</ol>` : notStated}
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
  const [evidenceInPrint, setEvidenceInPrint] = useState(false);
  const [approving, setApproving] = useState(false);
  const ver = data.version || null;
  const approve = async () => {
    setApproving(true);
    try { await api("/api/strategy/approve", { method: "POST", body: {} }); onReload && onReload(); toast("Approved — this version now stands."); }
    catch (e) { toast(e && e.message || "Couldn't approve.", "error"); }
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
    { id: "sdx-comparator", icon: "users", label: "Comparator", set: true, part: 1 },
    { id: "sdx-constraints", icon: "anchor", label: "Constraints", set: !!(((_doc.constraints || {}).selected || []).length || (_doc.constraints || {}).notes), part: 1 },
    { id: "sdx-governance", icon: "shield", label: "Governance", set: !!Object.keys(_doc.reward_governance || {}).length, part: 1 },
    { id: "sdx-exhibit", icon: "target", label: "Position vs intent", set: doms.length > 0, part: 2, live: true },
    { id: "sdx-positions", icon: "sliders", label: "The positions", set: !!data.completed_at, part: 2, live: true },
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
          </div>
        </div>
        <div class="sdx-hero-side">
          <div class="sdx-actions">
            ${canEdit ? html`<button class="btn primary" onClick=${onEdit}><${Icon} name="pencil" size=${13} /> Edit strategy</button>` : null}
            ${canEdit ? html`<button class="btn" disabled=${approving} onClick=${approve} title="Stamp this as an approved version — the review always cites a specific version.">
              ${approving ? "Approving…" : (ver ? "Approve v" + (ver.version + 1) : "Approve v1")}</button>` : null}
            <button class="btn" onClick=${() => { const t = document.title; document.title = "lumi — " + orgName + " — Reward strategy — " + fmtDate(); window.print(); document.title = t; }}><${Icon} name="download" size=${14} /> Print / PDF</button>
          </div>
          <div class="sdx-meter" role="img" aria-label=${"Document " + statedN + " of " + METER.length + " sections stated"}>
            <div class="sdx-meter-line"><b>${statedN} of ${METER.length}</b> sections stated</div>
            <div class="sdx-meter-bar"><i style=${{ width: (100 * statedN / METER.length) + "%" }}></i></div>
          </div>
          <label class="sd-evi-toggle" title="Off by default — the exported document describes your comparator in words, with no peer figures (your ruling R1).">
            <input type="checkbox" checked=${evidenceInPrint} onChange=${e => setEvidenceInPrint(e.target.checked)} />
            Include live position evidence in the export</label>
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
            ${ver ? html`<div>Version <b>${ver.version}</b> · approved ${fmtDate(ver.approved_at)} by ${ver.approved_by}${ver.dirty ? html` · <span class="sd-dirty">edits since approval</span>` : ""}</div>`
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

        <${SdDocSections} me=${me} data=${data} canEdit=${canEdit} onReload=${onReload}
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

        <${SdDocSections} me=${me} data=${data} canEdit=${canEdit} onReload=${onReload}
          which=${["commitments"]} />

        <div class="sdx-part"><span>Part 3</span> Delivery — how we'll run it</div>

        <${SdDocSections} me=${me} data=${data} canEdit=${canEdit} onReload=${onReload}
          which=${["measures", "roadmap"]} />

        ${ai === undefined && aiDark && canEdit ? html`
        <section class="sd-sec sdx-card no-print" id="sdx-reading">
          <${SecHead} icon="sparkle" title="lumi's reading" on=${false} />
          <div class="sd-note">A short AI reading of this strategy against your live position appears here once AI insights are enabled for the platform.</div>
        </section>` : null}
        ${ai !== undefined ? html`
        <section id="sdx-reading" class=${"sd-sec sdx-card sd-ai" + (ai ? "" : " no-print")}>
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
        const raw = sessionStorage.getItem("lumi-strat-draft");
        if (raw) {
          const dr = JSON.parse(raw);
          if (dr && dr.strat) { setStrat({ ...d.strategy, ...dr.strat }); if (dr.doc) setDoc({ ...seedDoc(d), ...dr.doc }); if (dr.step != null) setStep(dr.step); if (d.completed_at) setEditing(true); }
        }
      } catch (e) { /* a corrupt draft never blocks the wizard */ }
    }).catch(e => setErr(e.message));
  }, []);
  // persist the wizard draft per keystroke while editing; cheap and crash-proof
  useEffect(() => {
    if (!data || (data.completed_at && !editing)) return;
    try { sessionStorage.setItem("lumi-strat-draft", JSON.stringify({ strat, doc, step })); } catch (e) {}
  }, [strat, doc, step, editing, data]);
  // the commitments step needs the live lookups — fetched once, on first entry
  useEffect(() => {
    if (step !== 3 || mopts !== null) return;
    api("/api/strategy/measure-options").then(r => setMopts(r)).catch(() => setMopts({ options: [] }));
    api("/api/peer-groups").then(r => setGroups(r.groups || r || [])).catch(() => setGroups([]));
    api("/api/peer-groups/options").then(r => setChoices(r)).catch(() => setChoices({}));
  }, [step, data]);
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
  if (complete && !editing) return html`<${StrategyView} me=${me} data=${data} strat=${strat} onReload=${reload} onEdit=${() => { setEditing(true); setStep(0); }} />`;

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

  // ---- the flow (2026-08-15 redesign): SECTION PAGES with a labelled stepper.
  // David: "dedicated sections at the top, proper progress, all the questions for
  // each section on ONE page". Four steps: business facts · philosophy · this year ·
  // review. Legacy one-question drafts (10+i) map onto their owning section.
  const PHIL = shownFields(planeBfields);
  const POST = shownFields(planeCfields);
  const secOf = (st) => {
    if (st === 1) return 1;
    if (st === 2) return 2;
    if (st === 3) return 3;                              // principles & commitments
    if (st === 4) return 4;                              // review
    if (typeof st === "number" && st >= 10) return (st - 10) < PHIL.length ? 1 : 2;   // legacy draft
    return 0;
  };
  const sec = secOf(step);
  const flash = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3200); };
  const countOf = (fields) => fields.filter(f => f === "benefits_lead" ? (strat[f] || []).length
    : f === "domain_targets" ? Object.keys(strat[f] || {}).length : strat[f]).length;
  const missingReq = REQUIRED.filter(f => !strat[f]);
  // the 8 document sub-sections and whether each is stated (drives the step count)
  const _cm = doc.commitments || {};
  const DOC_STATED = [
    (doc.principles || []).length > 0,
    true,                                                                    // comparator always stated (All peers default)
    !!(((doc.constraints || {}).selected || []).length || (doc.constraints || {}).notes),
    !!Object.keys(doc.reward_governance || {}).length,
    !!((((_cm["Wellbeing"] || {}).metric_ids) || []).length || (_cm["Governance & Transparency"] || {}).statement),
    (doc.measures || []).length > 0,
    (doc.roadmap || []).length > 0,
    !!((doc.segments || {}).differentiated || ((doc.segments || {}).segments || []).length),
  ];
  const STEPS = [
    { t: "Your business", n: planeA.filter(f => f.value).length, of: planeA.length },
    { t: "Your philosophy", n: countOf(PHIL), of: PHIL.length },
    { t: "This year", n: countOf(POST), of: POST.length },
    { t: "Principles & plans", n: DOC_STATED.filter(Boolean).length, of: DOC_STATED.length },
    { t: "Review & save", n: null, of: null },
  ];
  const goSec = (i) => { setStep(i); window.scrollTo(0, 0); };
  const nextFrom = (i) => {
    // required dials gate THEIR OWN section's Continue (server still holds the real gate)
    if (i === 1 && (!strat.market_position || !strat.reward_mix)) {
      flash("Market position and total-reward mix change how we read your results — set both to continue.");
      const el = document.querySelector(".dial-card.flagged"); if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    if (i === 2 && !strat.primary_objective) {
      flash("Choose what reward is mainly for right now to continue.");
      return;
    }
    goSec(i + 1);
  };
  const changeFrom = (field) => goSec(PHIL.includes(field) ? 1 : POST.includes(field) ? 2 : 3);
  const setD = (patch) => setDoc(d => ({ ...d, ...patch }));
  const answered = countOf([...PHIL, ...POST]);

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
      // transparency reconfirm marker (step-3 tagging unit 2): saving through the now-live field
      // means the user has SEEN the transparency dial — confirm it so the engine reads the value
      // (a pre-wiring stored value stays inert until this). True only while the field is live.
      // the survey now carries the document fields too (2026-08-15) — always the WHOLE
      // object, so a survey save can never null a field edited on the document view
      const docOut = { ...doc }; delete docOut.comparator_label;
      await api("/api/strategy", { method: "PUT", body: { strategy: strat, plane_a: pa, document: docOut,
        transparency_confirmed: fieldState("transparency") === "live" } });
      setCommitted(true);                                  // a governance act closes quietly — no confetti
      try { sessionStorage.removeItem("lumi-strat-draft"); } catch (e) {}
      // window-qualified: the local [toast, setToast] state shadows the global toast()
      // in this scope (pre-prod audit 2026-08-12: every Save & finish threw here, after
      // the PUT had already succeeded)
      window.toast("Saved — your benchmark now reads through this strategy.");
      apiCacheInvalidate("/api/overview");
      const wasEdit = editing;
      const settle = () => { setEditing(false); setCommitted(false); setSaving(false); setStep(0); window.scrollTo(0, 0); };
      setTimeout(() => {
        if (wasEdit) {
          // exit editing only once the refetch lands — the view must never render stale data,
          // and an Edit click in the flourish window can't be re-seeded underneath the user
          api("/api/strategy")
            .then(d => { setData(d); setStrat({ ...d.strategy }); setPlaneA(d.plane_a.map(f => ({ ...f }))); settle(); })
            .catch(settle);
        } else nav("/");
      }, 1400);
    } catch (e) { flash(e && e.message && e.status !== 0 ? e.message : "Couldn't save — try again."); setSaving(false); }
  };

  const orgName = (me.org && me.org.name) || "Your organisation";
  const dialsOf = (fields) => fields.map(f => f === "domain_targets"
    ? html`<div key="dt" class="dial-card" id="dial-domain_targets">
        <div class="dial-head">
          <span class="dial-roundel"><${Icon} name="sliders" size=${16} /></span>
          <div>
            <div class="dial-title">Position by area <span class="sdw-opt">Optional</span></div>
            <div class="dial-q">Aim differently anywhere? The rest follow your overall position${strat.market_position ? html` (<b>${labelOf("market_position", strat.market_position)}</b>)` : ""}.</div>
          </div>
        </div>
        <${DomainOverrides} domains=${data.position_domains || data.competitive_domains || []}
          targets=${strat.domain_targets} globalValue=${strat.market_position} onSet=${setDomainTarget} />
      </div>`
    : html`<${DialCard} key=${f} field=${f} value=${strat[f]} onPick=${pick}
        required=${REQUIRED.includes(f)} context=${fieldState(f) === "context"} />`);

  const Stepper = () => html`
    <ol class="sdw-steps no-print" aria-label="Strategy set-up progress">
      ${STEPS.map((s, i) => {
        const done = s.of != null && s.n >= s.of && i < sec;
        const state = i === sec ? "current" : i < sec || done ? "done" : "todo";
        return html`<li key=${i} class=${"sdw-step " + state}>
          <button type="button" class="sdw-step-btn" aria-current=${i === sec ? "step" : undefined}
            onClick=${() => { if (!saving && !committed) goSec(i); }}>
            <span class="sdw-step-node">${state === "done" ? html`<${Icon} name="check" size=${13} />` : i + 1}</span>
            <span class="sdw-step-txt"><b>${s.t}</b>
              <em>${s.of != null ? s.n + " of " + s.of + " set" : (missingReq.length ? "almost there" : "ready")}</em></span>
          </button>
          ${i < STEPS.length - 1 ? html`<span class="sdw-step-line" aria-hidden="true"></span>` : null}
        </li>`; })}
    </ol>`;

  const Foot = ({ backTo, nextLabel, onNext, primary = true }) => html`
    <div class="sdw-foot">
      ${backTo != null ? html`<button class="btn quiet" disabled=${saving || committed} onClick=${() => goSec(backTo)}>← ${STEPS[backTo].t}</button>` : html`<span></span>`}
      <button class=${"btn " + (primary ? "primary" : "")} disabled=${saving || committed} onClick=${onNext}>${nextLabel}</button>
    </div>`;

  return html`
    <div class="strat-flow sdw">
      <div class="sdw-top no-print">
        <div class="sdw-topline">
          <span class="sdw-crumb">Reward strategy${editing ? " · editing" : ""}</span>
          ${editing && !committed ? html`<button class="btn quiet" disabled=${saving} onClick=${() => { setEditing(false); setStrat({ ...data.strategy }); setPlaneA(data.plane_a.map(f => ({ ...f }))); setStep(0); try { sessionStorage.removeItem("lumi-strat-draft"); } catch (e) {} }}>Cancel</button>` : null}
        </div>
        <${Stepper} />
      </div>

      ${sec === 0 && html`
        <section key="facts" class="sdw-page">
          <header class="sdw-head">
            <h1 class="strat-title">Does this still describe you?</h1>
            <p class="strat-sub">Pre-filled from your company profile. These shape who you're compared against — correct anything that's changed, then continue.</p>
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
                    const cur = Math.max(0, opts.indexOf(f.value));
                    const nxt = ("ArrowRight" === e.key || "ArrowDown" === e.key) ? Math.min(opts.length - 1, cur + 1) : Math.max(0, cur - 1);
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
          <div class="derived-note"><${Icon} name="info" size=${15} />
            <div title="From your sector and size we estimate how heavily each reward £ lands on your P&L."><b>Labour intensity is worked out for you</b> — it estimates how heavily each reward £ lands on your P&L, from your sector and size.</div></div>
          <${Foot} nextLabel="Looks right — your philosophy →" onNext=${() => goSec(1)} />
        </section>`}

      ${sec === 1 && html`
        <section key="phil" class="sdw-page">
          <header class="sdw-head">
            <h1 class="strat-title">How you reward</h1>
            <p class="strat-sub">Your philosophy — the positions lumi reads your benchmark through. Two are required; skip anything else and it reads neutrally.</p>
          </header>
          <div class="sdw-dials">${dialsOf(PHIL)}</div>
          <${Foot} backTo=${0} nextLabel="Continue — this year →" onNext=${() => nextFrom(1)} />
        </section>`}

      ${sec === 2 && html`
        <section key="posture" class="sdw-page">
          <header class="sdw-head">
            <h1 class="strat-title">This year</h1>
            <p class="strat-sub">Your posture right now — it sharpens which signals surface first, and changes with the year.</p>
          </header>
          <div class="sdw-dials">${dialsOf(POST)}</div>
          <${Foot} backTo=${1} nextLabel="Continue — principles & plans →" onNext=${() => nextFrom(2)} />
        </section>`}

      ${sec === 3 && html`
        <section key="docstep" class="sdw-page">
          <header class="sdw-head">
            <h1 class="strat-title">Principles ${"&"} plans</h1>
            <p class="strat-sub">The words of your strategy document — pick a starter and make it yours, or write your own. Everything here is optional and appears verbatim in your document.</p>
          </header>
          <div class="sdw-dials">

            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="star" size=${16} /></span>
                <div><div class="dial-title">Our reward principles <span class="sdw-opt">up to 6</span></div>
                <div class="dial-q">The yardstick your document opens with — tap a starter to add it, then edit it into your own words.</div></div></div>
              <div class="sdw-starters">
                ${PRINCIPLE_STARTERS.filter(s => !(doc.principles || []).includes(s)).map(s => html`
                  <button key=${s} type="button" class="sdw-starter" disabled=${(doc.principles || []).length >= 6}
                    onClick=${() => setD({ principles: [...(doc.principles || []), s].slice(0, 6) })}>
                    <${Icon} name="plus" size=${11} /> ${s}</button>`)}
              </div>
              ${(doc.principles || []).map((p, i) => html`
                <div key=${i} class="sdw-lirow">
                  <input class="ctl" maxlength="140" value=${p}
                    onInput=${e => setD({ principles: (doc.principles || []).map((x, j) => j === i ? e.target.value : x) })} />
                  <button type="button" class="sdw-li-x" aria-label="Remove principle" onClick=${() => setD({ principles: (doc.principles || []).filter((x, j) => j !== i) })}>✕</button>
                </div>`)}
              ${(doc.principles || []).length < 6 ? html`
                <button type="button" class="sdx-addtile" onClick=${() => setD({ principles: [...(doc.principles || []), ""] })}>
                  <${Icon} name="plus" size=${13} /> Write your own</button>` : null}
            </div>

            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="users" size=${16} /></span>
                <div><div class="dial-title">Who we compare ourselves to</div>
                <div class="dial-q">The peer frame your strategy is written against — described in words in the document, no figures.</div></div></div>
              <select class="ctl" value=${doc.comparator_cut || "all"}
                onChange=${e => setD({ comparator_cut: e.target.value === "all" ? null : e.target.value })}>
                <option value="all">All peers</option>
                ${((choices || {}).fields || []).filter(f => f.key === "industry").flatMap(f => f.choices || []).map(c =>
                  html`<option key=${"i" + c} value=${"industry::" + c}>Sector — ${c}</option>`)}
                ${((choices || {}).fields || []).filter(f => f.key === "fte_band").flatMap(f => f.choices || []).map(c =>
                  html`<option key=${"f" + c} value=${"fte_band::" + c}>Size — ${c}</option>`)}
                ${(groups || []).map(g => html`<option key=${g.group_id} value=${"group::" + g.group_id}>Saved group — ${g.name}</option>`)}
              </select>
              <label class="sd-doc-check" style=${{ marginTop: "var(--s3)" }}>
                <input type="checkbox" checked=${!!(doc.segments || {}).differentiated}
                  onChange=${e => setD({ segments: { ...(doc.segments || {}), differentiated: e.target.checked } })} />
                We deliberately pay more for scarce or critical segments</label>
              ${(doc.segments || {}).differentiated ? html`<input class="ctl" style=${{ marginTop: "var(--s2)" }}
                placeholder="Name the segments, comma-separated (e.g. Engineering, HGV drivers)"
                value=${((doc.segments || {}).segments || []).join(", ")}
                onInput=${e => setD({ segments: { ...(doc.segments || {}), segments: e.target.value.split(",").map(s => s.trim()).filter(Boolean).slice(0, 6) } })} />` : null}
            </div>

            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="anchor" size=${16} /></span>
                <div><div class="dial-title">What constrains us</div>
                <div class="dial-q">Pick what genuinely limits reward decisions this year — add anything else in your own words.</div></div></div>
              <div class="chip-row">
                ${(data.constraint_options || []).map(c => { const sel = ((doc.constraints || {}).selected || []).includes(c); return html`
                  <button key=${c} type="button" class=${"strat-chip" + (sel ? " on" : "")} aria-pressed=${sel}
                    onClick=${() => { const cur = (doc.constraints || {}).selected || [];
                      setD({ constraints: { ...(doc.constraints || {}), selected: sel ? cur.filter(x => x !== c) : [...cur, c] } }); }}>
                    <${Icon} name="check" size=${12} /> ${CONSTRAINT_LABEL[c] || c}</button>`; })}
              </div>
              <input class="ctl" style=${{ marginTop: "var(--s3)" }} maxlength="300" placeholder="Anything else worth naming (optional)"
                value=${(doc.constraints || {}).notes || ""}
                onInput=${e => setD({ constraints: { ...(doc.constraints || {}), notes: e.target.value } })} />
            </div>

            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="shield" size=${16} /></span>
                <div><div class="dial-title">How reward is governed</div>
                <div class="dial-q">Board credibility — who owns it, who approves it, and how often it's reviewed.</div></div></div>
              <div class="sd-doc-grid2">
                <label>Owner<input class="ctl" maxlength="80" placeholder="e.g. Chief People Officer" value=${(doc.reward_governance || {}).owner || ""}
                  onInput=${e => setD({ reward_governance: { ...(doc.reward_governance || {}), owner: e.target.value } })} /></label>
                <label>Approved by<input class="ctl" maxlength="80" placeholder="e.g. Remuneration Committee" value=${(doc.reward_governance || {}).approver || ""}
                  onInput=${e => setD({ reward_governance: { ...(doc.reward_governance || {}), approver: e.target.value } })} /></label>
                <label>Review cadence<select class="ctl" value=${(doc.reward_governance || {}).review_cadence || ""}
                  onChange=${e => setD({ reward_governance: { ...(doc.reward_governance || {}), review_cadence: e.target.value || null } })}>
                  <option value="">—</option>
                  ${(data.cadence_options || []).map(c => html`<option key=${c} value=${c}>${CADENCE_LABEL[c] || c}</option>`)}
                </select></label>
                <label>Effective date<input class="ctl" type="date" value=${(doc.reward_governance || {}).effective_date || ""}
                  onInput=${e => setD({ reward_governance: { ...(doc.reward_governance || {}), effective_date: e.target.value } })} /></label>
              </div>
            </div>

            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="heart" size=${16} /></span>
                <div><div class="dial-title">What we offer ${"&"} how we operate <span class="sdw-opt">Optional</span></div>
                <div class="dial-q">Wellbeing is a commitment to what you offer; governance to how you operate — never a market position.</div></div></div>
              <div class="sd-doc-sub">Wellbeing — we will offer</div>
              ${mopts === null ? html`<p class="sd-note">Loading your metric list…</p>` :
                (mopts.options || []).filter(o => o.category === "Wellbeing").map(o => { const w = ((doc.commitments || {})["Wellbeing"] || {}).metric_ids || []; const on = w.includes(o.id); return html`
                <label key=${o.id} class="sd-doc-check"><input type="checkbox" checked=${on}
                  onChange=${e => { const nw = e.target.checked ? [...w, o.id].slice(0, 6) : w.filter(x => x !== o.id);
                    const cm2 = { ...(doc.commitments || {}) };
                    if (nw.length) cm2["Wellbeing"] = { metric_ids: nw }; else delete cm2["Wellbeing"];
                    setD({ commitments: cm2 }); }} />${o.title}</label>`; })}
              <div class="sd-doc-sub">Governance ${"&"} transparency — how we operate</div>
              <div class="sdw-starters">
                ${GOV_STMT_STARTERS.map(s => html`<button key=${s} type="button" class="sdw-starter"
                  onClick=${() => setD({ commitments: { ...(doc.commitments || {}), "Governance & Transparency": { statement: s } } })}>
                  <${Icon} name="plus" size=${11} /> ${s}</button>`)}
              </div>
              <textarea class="ctl" rows="2" maxlength="240" placeholder="Your words — how pay is governed and shared"
                value=${((doc.commitments || {})["Governance & Transparency"] || {}).statement || ""}
                onInput=${e => { const cm2 = { ...(doc.commitments || {}) };
                  if (e.target.value.trim()) cm2["Governance & Transparency"] = { statement: e.target.value }; else delete cm2["Governance & Transparency"];
                  setD({ commitments: cm2 }); }}></textarea>
            </div>

            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="table" size=${16} /></span>
                <div><div class="dial-title">How we'll know it's working <span class="sdw-opt">up to 8</span></div>
                <div class="dial-q">Measures lumi already tracks — the review reports them against your comparator each cycle.</div></div></div>
              ${mopts === null ? html`<p class="sd-note">Loading your metric list…</p>` : html`
                <div class="sd-doc-mlist">
                  ${(mopts.options || []).map(o => { const m = doc.measures || []; const on = m.includes(o.id); return html`
                    <label key=${o.id} class=${"sd-doc-check" + (o.suppressed ? " dim" : "")}>
                      <input type="checkbox" checked=${on} disabled=${!on && m.length >= 8}
                        onChange=${e => setD({ measures: e.target.checked ? [...m, o.id].slice(0, 8) : m.filter(x => x !== o.id) })} />
                      <span>${o.title} <span class="sd-doc-meta">${o.category}${o.context ? " · tracked as a level" : ""}${o.suppressed ? " · below floor here" : ""}</span></span>
                    </label>`; })}
                </div>`}
            </div>

            <div class="dial-card">
              <div class="dial-head"><span class="dial-roundel"><${Icon} name="clock" size=${16} /></span>
                <div><div class="dial-title">What changes this year <span class="sdw-opt">up to 6</span></div>
                <div class="dial-q">The roadmap — tap a common change to add it, then make it yours, or write your own.</div></div></div>
              <div class="sdw-starters">
                ${ROADMAP_STARTERS.filter(s => !(doc.roadmap || []).some(r => r.title === s)).map(s => html`
                  <button key=${s} type="button" class="sdw-starter" disabled=${(doc.roadmap || []).length >= 6}
                    onClick=${() => setD({ roadmap: [...(doc.roadmap || []), { title: s }].slice(0, 6) })}>
                    <${Icon} name="plus" size=${11} /> ${s}</button>`)}
              </div>
              ${(doc.roadmap || []).map((r, i) => html`
                <div key=${i} class="sdw-lirow">
                  <input class="ctl" maxlength="120" value=${r.title || ""}
                    onInput=${e => setD({ roadmap: (doc.roadmap || []).map((x, j) => j === i ? { ...x, title: e.target.value } : x) })} />
                  <select class="ctl sdw-li-sel" value=${r.horizon || ""}
                    onChange=${e => setD({ roadmap: (doc.roadmap || []).map((x, j) => j === i ? { ...x, horizon: e.target.value || undefined } : x) })}>
                    <option value="">When?</option>
                    ${(data.horizon_options || []).map(h => html`<option key=${h} value=${h}>${HORIZON_LABEL[h] || h}</option>`)}
                  </select>
                  <button type="button" class="sdw-li-x" aria-label="Remove roadmap item" onClick=${() => setD({ roadmap: (doc.roadmap || []).filter((x, j) => j !== i) })}>✕</button>
                </div>`)}
              ${(doc.roadmap || []).length < 6 ? html`
                <button type="button" class="sdx-addtile" onClick=${() => setD({ roadmap: [...(doc.roadmap || []), { title: "" }] })}>
                  <${Icon} name="plus" size=${13} /> Write your own</button>` : null}
            </div>

          </div>
          <${Foot} backTo=${2} nextLabel="Review & save →" onNext=${() => goSec(4)} />
        </section>`}

      ${sec === 4 && html`
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
            rows=${planeA.map(f => ({ label: f.label, value: f.value || "—" }))} onEdit=${() => goSec(0)} locked=${committed || saving} />
          <${ReviewSection} title="Your philosophy" chip="your choices" chipCls="choices"
            rows=${PHIL.map(f => ({ ...reviewRow(f, strat), field: f }))}
            onEdit=${() => goSec(1)} onChangeRow=${changeFrom} locked=${committed || saving} />
          <${ReviewSection} title="This year" chip="right now" chipCls="choices"
            rows=${POST.map(f => ({ ...reviewRow(f, strat), field: f }))}
            onEdit=${() => goSec(2)} onChangeRow=${changeFrom} locked=${committed || saving} />
          <${ReviewSection} title="Principles & plans" chip="your document" chipCls="choices"
            rows=${[
              { label: "Reward principles", value: (doc.principles || []).filter(p => p.trim()).length ? (doc.principles || []).filter(p => p.trim()).length + " stated" : "Not yet stated", skipped: !(doc.principles || []).filter(p => p.trim()).length },
              { label: "Comparator", value: doc.comparator_cut ? doc.comparator_cut.split("::")[1] || doc.comparator_cut : "All peers" },
              { label: "Constraints", value: ((doc.constraints || {}).selected || []).length ? ((doc.constraints || {}).selected || []).map(c => CONSTRAINT_LABEL[c] || c).join(", ") : "Not yet stated", skipped: !((doc.constraints || {}).selected || []).length },
              { label: "Governance of reward", value: (doc.reward_governance || {}).owner || (doc.reward_governance || {}).approver ? [((doc.reward_governance || {}).owner), ((doc.reward_governance || {}).approver)].filter(Boolean).join(" · ") : "Not yet stated", skipped: !((doc.reward_governance || {}).owner || (doc.reward_governance || {}).approver) },
              { label: "Commitments", value: (((doc.commitments || {})["Wellbeing"] || {}).metric_ids || []).length || ((doc.commitments || {})["Governance & Transparency"] || {}).statement ? "Stated" : "Not yet stated", skipped: !((((doc.commitments || {})["Wellbeing"] || {}).metric_ids || []).length || ((doc.commitments || {})["Governance & Transparency"] || {}).statement) },
              { label: "Measures", value: (doc.measures || []).length ? (doc.measures || []).length + " chosen" : "Not yet stated", skipped: !(doc.measures || []).length },
              { label: "Roadmap", value: (doc.roadmap || []).filter(r => (r.title || "").trim()).length ? (doc.roadmap || []).filter(r => (r.title || "").trim()).length + " changes" : "Not yet stated", skipped: !(doc.roadmap || []).filter(r => (r.title || "").trim()).length },
            ]}
            onEdit=${() => goSec(3)} locked=${committed || saving} />
          <p class="strat-trust"><b>Company facts and choices, not employee data.</b> Organisation-level, set by an Admin — they shape how your results are read, never what your people see.</p>
          <div class="sdw-foot">
            <button class="btn quiet" disabled=${saving || committed} onClick=${() => goSec(3)}>← Principles ${"&"} plans</button>
            <button class=${"btn primary" + (committed ? " strat-saved" : "")} disabled=${saving || committed} onClick=${commit}>${
              committed ? html`<${Icon} name="check" size=${15} /> Saved` : saving ? "Saving…" : "Save & finish"}</button>
          </div>
        </section>`}

      <div class="sr-only" role="status" aria-live="polite">${toast || ""}</div>
      ${toast && html`<div class="strat-toast">${toast}</div>`}
    </div>`;
};

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
