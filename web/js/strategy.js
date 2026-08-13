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
function DomainOverrides({ domains, targets, globalValue, onSet }) {
  const [open, setOpen] = useState(false);
  if (!domains || !domains.length) return null;
  const t = targets || {};
  const n = Object.keys(t).length;
  return html`
    <div class="dom-ov">
      <button type="button" class=${"dom-reveal" + (open ? " open" : "")} aria-expanded=${open} onClick=${() => setOpen(o => !o)}>
        <${Icon} name="sliders" size=${13} /> Refine by area${n ? html` · <b>${n}</b> set` : ""}
        <span class="dom-chev">${open ? "▾" : "▸"}</span></button>
      ${open && html`<div class="dom-panel">
        <p class="dom-hint">Set a different aim for any area — the rest follow your overall position${globalValue ? html` (<b>${labelOf("market_position", globalValue)}</b>)` : ""}.</p>
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

function StrategyView({ me, data, strat, onEdit, canEdit = true }) {
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
  // FIXED numbering — sections must not renumber as async fetches resolve
  const NUM = { stance: "01", exhibit: "02", positions: "03", reading: "04" };
  return html`
    <div class="sd-wrap">
      <div class="sd-actions no-print">
        <button class="btn" onClick=${() => { const t = document.title; document.title = "lumi — " + orgName + " — Reward strategy — " + fmtDate(); window.print(); document.title = t; }}><${Icon} name="download" size=${14} /> Print / save as PDF</button>
        ${canEdit ? html`<button class="btn primary" onClick=${onEdit}><${Icon} name="pencil" size=${13} /> Edit strategy</button>` : null}
      </div>
      <div class="strat-pdf-head" aria-hidden="true"><b>lumi</b> · Reward strategy · ${orgName}${when ? " · captured " + when : ""} · generated ${fmtDate()}</div>
      <article class="sd-doc">
        <header class="sd-mast" style=${{ "--i": 0 }}>
          <div>
            <div class="sd-eyebrow">Reward strategy</div>
            <div class="sd-org">${orgName}</div>
          </div>
          <div class="sd-mast-meta">
            ${when && html`<div>Captured <b>${when}</b></div>`}
            <div>Set by your Admins · held in lumi</div>
          </div>
        </header>

        <section class="sd-sec" style=${{ "--i": 1 }}>
          <div class="sd-secnum">${NUM.stance} — The stance</div>
          ${stance.length ? stance.map((s, i) => html`<p key=${i} class=${"sd-stance" + (i === 0 ? " lead" : "")}>${s}</p>`)
            : html`<p class="sd-stance">No positions set yet — your benchmark is read neutrally.</p>`}
          <div class="sd-note">Below or above market here is a choice, not a verdict — lumi reads your numbers through it.</div>
        </section>

        ${hero === null ? html`
        <section class="sd-sec" style=${{ "--i": 2 }}>
          <div class="sd-secnum">${NUM.exhibit} — Position against intent</div>
          <div class="sd-note">Reading your live position…</div>
        </section>` : doms.length ? html`
        <section class="sd-sec" style=${{ "--i": 3 }}>
          <div class="sd-secnum">${NUM.exhibit} — Position against intent
            <span class="sd-secnote">${offAim.length ? offAim.length + " of " + doms.length + " areas off strategy" : "all " + doms.length + " areas on strategy"} · live · ${defCut && defCut !== "all" ? "vs your default peer group" : "vs all peers"}</span></div>
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
        <section class="sd-sec" style=${{ "--i": 4 }}>
          <div class="sd-secnum">${NUM.exhibit} — Position against intent</div>
          <div class="sd-note">Aim-vs-position appears once your benchmark unlocks.</div>
        </section>`}

        <section class="sd-sec" style=${{ "--i": 5 }}>
          <div class="sd-secnum">${NUM.positions} — The positions</div>
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

        ${ai === undefined && aiDark && canEdit ? html`
        <section class="sd-sec no-print">
          <div class="sd-secnum">${NUM.reading} — lumi's reading</div>
          <div class="sd-note">A short AI reading of this strategy against your live position appears here once AI insights are enabled for the platform.</div>
        </section>` : null}
        ${ai !== undefined ? html`
        <section style=${{ "--i": 6 }} class=${"sd-sec sd-ai" + (ai ? "" : " no-print")}>
          <div class="sd-secnum">${NUM.reading} — lumi's reading
            <span class="sd-secnote">AI · grounded only in the figures on this page</span></div>
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
  const isAdmin = me && me.user && me.user.role === "admin";
  useEffect(() => {
    api("/api/strategy").then(d => {
      setData(d);
      setStrat({ ...d.strategy });
      setPlaneA(d.plane_a.map(f => ({ ...f })));
      // restore an in-flight wizard draft: any navigation away used to silently
      // discard every answered dial (pre-prod audit 2026-08-12). The draft only
      // overlays an UNCOMMITTED session (cleared on save + on Cancel).
      try {
        const raw = sessionStorage.getItem("lumi-strat-draft");
        if (raw) {
          const dr = JSON.parse(raw);
          if (dr && dr.strat) { setStrat({ ...d.strategy, ...dr.strat }); if (dr.step != null) setStep(dr.step); if (d.completed_at) setEditing(true); }
        }
      } catch (e) { /* a corrupt draft never blocks the wizard */ }
    }).catch(e => setErr(e.message));
  }, []);
  // persist the wizard draft per keystroke while editing; cheap and crash-proof
  useEffect(() => {
    if (!data || (data.completed_at && !editing)) return;
    try { sessionStorage.setItem("lumi-strat-draft", JSON.stringify({ strat, step })); } catch (e) {}
  }, [strat, step, editing, data]);
  if (err) return html`<${EmptyState} tone="error" icon="compass" title="Couldn't load your strategy" body=${err + " — nothing is lost."}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!data) return html`<${PageLoading} />`;
  const complete = !!data.completed_at;
  if (!isAdmin) {
    // non-admins with a completed strategy still get the READ view — it explains
    // how their organisation's results are being read; only editing is admin-only.
    if (complete) return html`<${StrategyView} me=${me} data=${data} strat=${data.strategy || {}} canEdit=${false} />`;
    return html`<${EmptyState} icon="lock" title="Admin only"
      body="Your reward strategy is set by an organisation Admin — ask yours to complete it."
      action=${html`<button class="btn small primary" onClick=${() => nav("/overview")}>Explore the benchmark</button>`} />`;
  }
  if (complete && !editing) return html`<${StrategyView} me=${me} data=${data} strat=${strat} onEdit=${() => { setEditing(true); setStep(0); }} />`;

  const pick = (field, val) => setStrat(s => ({ ...s, [field]: val }));
  // per-domain override write: only set domains carry a key — null deletes (inherit global)
  const setDomainTarget = (dom, val) => setStrat(s => {
    const dt = { ...(s.domain_targets || {}) };
    if (val == null) delete dt[dom]; else dt[dom] = val;
    return { ...s, domain_targets: dt };
  });
  const planeBfields = ["market_position", "reward_mix", "pay_for_performance", "transparency",
    "location_approach", "benefits_lead", "family_position"];
  const planeCfields = ["primary_objective", "budget_direction", "acute_pressure", "risk_appetite"];

  // ---- the flow: one question per stage (GDS one-thing-per-page) --------------
  // stage: "facts" | question index | "review". step kept only as a legacy alias.
  const QUESTIONS = [...shownFields(planeBfields), ...shownFields(planeCfields)];
  const qIndex = typeof step === "number" && step >= 10 ? step - 10 : null;   // stages 10.. = questions
  const stage = step === 0 ? "facts" : step === 3 ? "review" : qIndex;
  const flash = (msg) => { setToast(msg); setTimeout(() => setToast(null), 3200); };
  const REDUCED = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // exit-fast / enter-slow swap (motion research: 120ms out ease-in, 200ms in ease-out;
  // reduced motion falls back to a quick opacity crossfade)
  const goTo = (nextStage) => {
    setLeaving(true);
    setTimeout(() => {
      setLeaving(false);
      setStep(nextStage === "facts" ? 0 : nextStage === "review" ? 3 : 10 + nextStage);
      window.scrollTo(0, 0);
      requestAnimationFrame(() => {
        const h = document.querySelector(".qstage .strat-title, .strat-step .strat-title");
        if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
      });
    }, REDUCED() ? 120 : 150);
  };
  const advance = () => {
    if (returnTo === "review") { setReturnTo(null); goTo("review"); return; }
    if (qIndex == null) { goTo(0); return; }
    if (qIndex >= QUESTIONS.length - 1) goTo("review"); else goTo(qIndex + 1);
  };
  const goBack = () => {
    if (returnTo === "review") { setReturnTo(null); goTo("review"); return; }
    if (stage === "review") { goTo(QUESTIONS.length - 1); return; }
    if (qIndex === 0) { goTo("facts"); return; }
    if (qIndex != null) goTo(qIndex - 1);
  };
  // single-select pick = the submit (Typeform split-advance): a short beat so the
  // choice and its effect line register, then move. Multi-select waits for Enter.
  const pickAndGo = (field, val) => {
    pick(field, val);
    setTimeout(advance, REDUCED() ? 300 : 650);
  };
  const changeFrom = (field) => {           // GOV.UK check-answers Change round-trip
    setReturnTo("review");
    goTo(QUESTIONS.indexOf(field));
  };
  const tryContinue = (field) => {          // Enter / Continue on a question stage
    if (REQUIRED.includes(field) && !strat[field]) {
      flash("This one changes how we read your results — choose a position to continue.");
      return;
    }
    advance();
  };

  const answered = QUESTIONS.filter(f => f === "benefits_lead" ? (strat[f] || []).length : strat[f]).length;
  const progress = stage === "facts" ? 0.04 : stage === "review" ? 1 : (qIndex + 1) / (QUESTIONS.length + 1);

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
      await api("/api/strategy", { method: "PUT", body: { strategy: strat, plane_a: pa,
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

  const curField = qIndex != null ? QUESTIONS[qIndex] : null;
  const isMulti = curField === "benefits_lead";
  const orgName = (me.org && me.org.name) || "Your organisation";

  // digit keys select scale stops / objective options (Typeform key badges)
  const onStageKeys = (e) => {
    if (stage !== qIndex || curField == null) return;
    if (e.key === "Enter" && (isMulti || strat[curField] || !REQUIRED.includes(curField))) { e.preventDefault(); tryContinue(curField); return; }
    const n = parseInt(e.key, 10);
    if (!n) return;
    const sk = SCALE_FIELD[curField];
    if (sk && SCALE[sk].stops[n - 1]) { e.preventDefault(); pickAndGo(curField, SCALE[sk].stops[n - 1].v); }
    else if (curField === "primary_objective" && OBJECTIVES[n - 1]) { e.preventDefault(); pickAndGo(curField, OBJECTIVES[n - 1].v); }
  };

  return html`
    <div class=${"strat-flow" + (qIndex != null ? " has-rail" : "")} onKeyDown=${onStageKeys}>
      ${/* one thin continuous progress bar (research: segments fill, linear map, no counters) */ ""}
      <div class="strat-progress" role="progressbar" aria-valuemin="0" aria-valuemax=${QUESTIONS.length + 2}
        aria-valuenow=${stage === "facts" ? 1 : stage === "review" ? QUESTIONS.length + 2 : qIndex + 2}
        aria-label="Strategy progress">
        <i style=${{ transform: "scaleX(" + progress + ")" }}></i>
      </div>

      ${stage !== "facts" || editing ? html`
        <div class="strat-topline no-print">
          ${stage !== "facts" ? html`<button class="btn quiet strat-back" onClick=${goBack} disabled=${saving || committed}>← Back</button>` : html`<span></span>`}
          <span class="strat-count">${stage === "review" ? "Review" : stage === "facts" ? "" : (qIndex + 1) + " of " + QUESTIONS.length}</span>
          ${editing && !committed ? html`<button class="btn quiet" disabled=${saving} onClick=${() => { setEditing(false); setStrat({ ...data.strategy }); setPlaneA(data.plane_a.map(f => ({ ...f }))); setStep(0); try { sessionStorage.removeItem("lumi-strat-draft"); } catch (e) {} }}>Cancel</button>` : html`<span></span>`}
        </div>` : null}

      ${qIndex != null && html`
        <aside class="strat-rail-live no-print" aria-label="Your strategy so far">
          <div class="srl-head">Your strategy so far</div>
          ${sdStance(strat, orgName).map((s, i) => html`<p key=${i} class="srl-line">${s}</p>`)}
          ${!sdStance(strat, "x").length ? html`<p class="srl-line muted">It builds here as you set positions.</p>` : null}
        </aside>`}

      ${stage === "facts" && html`
        <section key="facts" class=${"strat-step qstage" + (leaving ? " leaving" : "")}>
          <div class="strat-eyebrow">Your business <span class="strat-mode confirm">Pre-filled · confirm</span></div>
          <h1 class="strat-title">Does this still describe you?</h1>
          <p class="strat-sub">These shape who you're compared against — correct anything that's changed.</p>
          <div class="confirm-grid">
            ${planeA.map((f, i) => html`
              <div key=${f.key} class="confirm-row">
                <div><div class="cr-label">${f.label}</div><div class="cr-why">${f.why}</div></div>
                <div class="cr-seg" role="radiogroup" aria-label=${f.label}
                  onKeyDown=${e => {
                    if (!["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(e.key)) return;
                    e.preventDefault();
                    const wrap = e.currentTarget;                     // hoisted — nulled after the handler in React 18
                    const opts = (f.options || []).concat(f.value && !(f.options || []).includes(f.value) ? [f.value] : []);
                    const cur = Math.max(0, opts.indexOf(f.value));
                    const nxt = ("ArrowRight" === e.key || "ArrowDown" === e.key) ? Math.min(opts.length - 1, cur + 1) : Math.max(0, cur - 1);
                    setPlaneA(p => p.map((x, j) => j === i ? { ...x, value: opts[nxt] } : x));
                    requestAnimationFrame(() => { const el = wrap && wrap.querySelectorAll(".cr-opt")[nxt]; if (el) el.focus(); });
                  }}>
                  ${(f.options || []).concat(f.value && !(f.options || []).includes(f.value) ? [f.value] : []).map(o => html`
                    <button key=${o} type="button" class=${"cr-opt" + (o === f.value ? " on" : "")} role="radio" aria-checked=${o === f.value}
                      tabindex=${o === f.value || (!f.value && o === (f.options || [])[0]) ? 0 : -1}
                      onClick=${() => setPlaneA(p => p.map((x, j) => j === i ? { ...x, value: o } : x))}>${o}</button>`)}
                </div>
              </div>`)}
            <div class="derived-note"><${Icon} name="info" size=${15} />
              <div title="From your sector and size we estimate how heavily each reward £ lands on your P&L."><b>Labour intensity is worked out for you</b> — it estimates how heavily each reward £ lands on your P&L, from your sector and size.</div></div>
          </div>
          <div class="strat-stagefoot">
            <button class="btn primary strat-next" onClick=${advance}>Looks right <span class="kbd-hint">press Enter ↵</span></button>
          </div>
        </section>`}

      ${qIndex != null && html`
        <section key=${"q" + qIndex} class=${"strat-step qstage" + (leaving ? " leaving" : "")}>
          <div class="strat-eyebrow">${planeBfields.includes(curField) ? "Your philosophy" : "Right now"}
            ${fieldState(curField) === "context" ? html`<span class="strat-mode confirm">Context</span>` : null}</div>
          <${DialCard} field=${curField} value=${strat[curField]}
            onPick=${(f, v) => (isMulti ? pick(f, v) : pickAndGo(f, v))}
            required=${REQUIRED.includes(curField)} context=${fieldState(curField) === "context"}
            extra=${curField === "market_position" ? html`<${DomainOverrides} domains=${data.competitive_domains || []} targets=${strat.domain_targets} globalValue=${strat.market_position} onSet=${setDomainTarget} />` : null} />
          <div class="strat-stagefoot">
            ${isMulti || strat[curField]
              ? html`<button class="btn primary strat-next" onClick=${() => tryContinue(curField)}>Continue <span class="kbd-hint">press Enter ↵</span></button>`
              : REQUIRED.includes(curField)
                ? html`<span class="caption">Choose one to continue</span>`
                : html`<button class="btn quiet" onClick=${advance}>Skip — read neutrally</button>`}
          </div>
        </section>`}

      ${stage === "review" && html`
        <section key="review" class=${"strat-step qstage" + (leaving ? " leaving" : "")}>
          <div class=${"strat-done" + (committed ? " celebrating" : "")}><span class="strat-check"><${Icon} name="check" size=${22} /></span>
            <h1 class="strat-title" style=${{ textAlign: "center" }}>That's your strategy captured</h1>
            <p class="strat-sub" style=${{ margin: "var(--s2) auto 0", textAlign: "center" }}>Change anything before it goes live — each change returns you straight here.</p></div>
          <${ReviewSection} title="Your business" chip="confirmed" chipCls="confirmed"
            rows=${planeA.map(f => ({ label: f.label, value: f.value || "—" }))} onEdit=${() => { setReturnTo("review"); goTo("facts"); }} locked=${committed || saving} />
          <${ReviewSection} title="Your philosophy" chip="your choices" chipCls="choices"
            rows=${shownFields(planeBfields).map(f => ({ ...reviewRow(f, strat), field: f }))}
            onEdit=${() => { setReturnTo("review"); goTo(QUESTIONS.indexOf(shownFields(planeBfields)[0])); }}
            onChangeRow=${changeFrom} locked=${committed || saving} />
          <${ReviewSection} title="Right now" chip="this year" chipCls="choices"
            rows=${shownFields(planeCfields).map(f => ({ ...reviewRow(f, strat), field: f }))}
            onEdit=${() => { setReturnTo("review"); goTo(QUESTIONS.indexOf(shownFields(planeCfields)[0])); }}
            onChangeRow=${changeFrom} locked=${committed || saving} />
          <p class="strat-trust"><b>Company facts and choices, not employee data.</b> Organisation-level, set by an Admin — they shape how your results are read, never what your people see.</p>
          <div class="strat-stagefoot">
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
  if (!v) return { label: DIAL_LABEL[field], value: "Skipped — read neutrally", skipped: true };
  if (field === "market_position") {
    const dt = strat.domain_targets || {}, n = Object.keys(dt).length;
    return { label: DIAL_LABEL[field], value: labelOf(field, v) + (n ? " · " + n + " area" + (n === 1 ? "" : "s") + " refined" : "") };
  }
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
