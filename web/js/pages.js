/* Dashboard pages: Executive overview, Superpower detail, My dashboards, My data, Methodology. */
/* global html, useState, useEffect, useMemo, api, fmtValue, pLabel, Chip, NBadge, Term, Spinner,
   BenchmarkCard, QuartileDots, fmtGBPCompact, EmptyState, nav */

const SUPERPOWERS = ["Reward", "Processes", "Wellbeing", "Growth", "Capability",
  "Inclusivity", "Attract", "Leadership", "Purpose", "Change"];
window.SUPERPOWERS = SUPERPOWERS;
/* SpIcon: the one consistent superpower glyph (line-icon family from icons.js) */
window.SpIcon = ({ sp, size = 15 }) => html`<${Icon} name=${SP_ICON[sp] || "target"} size=${size} />`;

// ------------------------------------------------------------ overview -----
// Dashboard nudge — Admins who haven't set their reward strategy. Quietly
// dismissible per-session; reappears next visit until the stance is captured
// (the strategy_complete flag, not a permanent dismiss).
function StrategyNudge() {
  const KEY = "lumi-strat-nudge";
  const [hidden, setHidden] = useState(() => { try { return sessionStorage.getItem(KEY) === "1"; } catch (e) { return false; } });
  if (hidden) return null;
  return html`
    <div class="strat-nudge">
      <span class="strat-nudge-icon"><${Icon} name="compass" size=${20} /></span>
      <div class="strat-nudge-body">
        <b>Set your reward strategy</b>
        <span>Tell us your stance — where you aim to sit, what your package leads on — so we can read “below market” from “below market, on purpose.” Two minutes.</span>
      </div>
      <button class="btn primary strat-nudge-cta" onClick=${() => nav("/strategy")}>Set it up</button>
      <button class="strat-nudge-x" aria-label="Dismiss for now"
        onClick=${() => { try { sessionStorage.setItem(KEY, "1"); } catch (e) {} setHidden(true); }}><${Icon} name="close" size=${15} /></button>
    </div>`;
}
window.OverviewPage = function ({ me, cut, cuts, prefs, onPref, onPin, pinnedIds, onCut, onTwinInfo }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  // Home dashboard lens (persisted in prefs._overview): MARKET view (gauge + below/
  // on/above) vs PRACTICE view (how you operate — the differ/approach read), and
  // whether the reward-strategy stance is APPLIED. Strategy-off re-fetches the
  // overview WITHOUT the lens (absolute colours, impact-ordered signals, plain verdict).
  const _ov = (prefs && prefs._overview) || {};
  const [view, setViewState] = useState(_ov.view === "practice" ? "practice" : "market");
  const [applyStrat, setApplyState] = useState(_ov.apply_strategy !== false);
  const setView = (v) => { setViewState(v); onPref("_overview", { view: v, apply_strategy: applyStrat }); };
  const setApplyStrat = (b) => { setApplyState(b); onPref("_overview", { view, apply_strategy: b }); };
  useEffect(() => {
    setData(null); setErr(null);
    api("/api/overview?" + cutQS(cut) + (applyStrat ? "" : "&strategy=off")).then(setData).catch(e => setErr(e.message));
  }, [cutKeyOf(cut), applyStrat]);
  if (err) return html`<${EmptyState} title="Couldn't load the overview"
    body=${err + " — nothing is lost; it usually works on a retry."}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!data) return html`
    <div>
      <div class="skel" style=${{ height: "30px", width: "320px", marginBottom: "var(--s3)" }}></div>
      <div class="skel" style=${{ height: "20px", width: "480px", marginBottom: "var(--s4)" }}></div>
      <div class="skel" style=${{ height: "180px", marginBottom: "var(--s4)", borderRadius: "var(--radius)" }}></div>
      <${SkeletonGrid} count=${3} />
    </div>`;
  const h = data.headline;
  const pctAbove = h.comparable_metrics ? Math.round(100 * h.above_median / h.comparable_metrics) : 0;
  // Single source of truth for peer-sample confidence. The caveat is the ONLY
  // surface that flags a thin cut; gauge / cards / panels / signals read this and
  // render nothing extra. Gated on insights unlocked so it never stacks on the
  // data-pending gauge (below the 90% gate). Window [5, 20): below 5 a cut is
  // fully suppressed (no verdict to caveat, = SUPPRESSION_FLOOR); 20 is the round
  // upper edge (DECISIONS.md).
  const unlocked = !!(data.contribution && data.contribution.insights_unlocked);
  const sampleN = cutSize(cut, cuts, me.peer_pool);
  const thinSample = unlocked && sampleN != null && sampleN >= 5 && sampleN < 20;
  return html`
    <div>
      <div class="hero">
        <h1 class="display-title">${data.org.name}</h1>
        <div class="hero-actions">
          <${PeerSetBar} me=${me} cut=${cut} cuts=${cuts} onSelect=${onCut} onTwinInfo=${onTwinInfo} inline=${true} />
          <${ExportBoardPack} me=${me} cut=${cut} />
          <${ShareButton} me=${me} cut=${cut} name=${data.org && data.org.name} />
          ${thinSample && html`
            <div class="sample-caveat-line">
              <span class="indic-flag" tabindex="0" role="note">
                <${Icon} name="info" size=${11} /> Small sample · ${sampleN} peers
                <span class="indic-tip">Verdicts are compared against ${sampleN} organisations — treat as directional.</span>
              </span>
            </div>`}
        </div>
      </div>

      ${data.contribution && !data.contribution.insights_unlocked && !data.contribution.reduced &&
        html`<${WelcomeHero} contrib=${data.contribution} pool=${data.peer_pool} me=${me} />`}

      <${OverviewHero} data=${data} cut=${cut} cuts=${cuts} orgKey=${me.org && me.org.name}
        view=${view} applyStrat=${applyStrat} setView=${setView} setApplyStrat=${setApplyStrat} />

    </div>`;
};

/* Board pack as an export action (chrome spec section 1.2): generate from the
   Overview under the current peer filter; previous packs live in the small
   menu. Hidden while insights are locked — the artifact is written from the
   org's own position. The one-time pulse highlights the new home for anyone
   arriving via the old /boardpack route. */
function ExportBoardPack({ me, cut }) {
  const contrib = me.contribution;
  const [open, setOpen] = useState(false);
  const [packs, setPacks] = useState(null);
  const [gen, setGen] = useState(false);
  const [err, setErr] = useState(null);
  const [pulse, setPulse] = useState(false);
  useEffect(() => {
    try {
      if (sessionStorage.getItem("lumi-bp-migrated")) {
        setPulse(true);
        sessionStorage.removeItem("lumi-bp-migrated");
      }
    } catch (e) {}
  }, []);
  if (contrib && !contrib.insights_unlocked) return null;
  const generate = async () => {
    setGen(true); setErr(null);
    try {
      const r = await api("/api/boardpack/generate", { method: "POST", body: { cut: cut.dim, cut_value: cut.value } });
      nav("/boardpack/" + r.pack_id);
    } catch (e) { setErr(e.message); setOpen(true); }
    setGen(false);
  };
  const toggle = () => {
    setOpen(!open);
    if (!packs) api("/api/boardpacks").then(d => setPacks(d.packs || [])).catch(() => setPacks([]));
  };
  return html`
    <div class="bp-export">
      <button class=${"btn small" + (pulse ? " pulse-once" : "")} disabled=${gen} onClick=${generate}
        title="A board-ready narrative of your reward position, written from your live benchmark under the current peer filter.">
        <${Icon} name="file-text" size=${14} /> ${gen ? "Writing…" : "Export board pack"}</button>
      <button class="btn small" aria-label="Previous board packs" aria-expanded=${open} onClick=${toggle}>
        <${Icon} name="chevron-down" size=${13} /></button>
      ${open && html`
        <div class="card bp-menu">
          ${err && html`<div class="error-text" style=${{ padding: "var(--s2)" }}>${err}</div>`}
          ${packs == null && html`<div class="caption" style=${{ padding: "var(--s2)" }}>Loading…</div>`}
          ${packs && packs.length === 0 && !err && html`<div class="caption" style=${{ padding: "var(--s2)" }}>No packs yet — Export writes one from your live position.</div>`}
          ${(packs || []).map(p => html`
            <button key=${p.pack_id} class="bp-menu-item" onClick=${() => nav("/boardpack/" + p.pack_id)}>
              ${new Date(p.created_at + "Z").toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
            </button>`)}
        </div>`}
    </div>`;
}

/* Share this view (chrome spec): a read-only public link to the current
   dashboard view, scoped to the active peer filter. Admin-only (mirrors the
   board-pack share gate + /api/shares require_admin). The button sits beside
   Export board pack on the Overview header and on My dashboards. Posts
   kind=dashboard, config {cut, cut_value, name}, 30-day expiry; on success the
   dialog shows the public link with a copy button. */
function ShareButton({ me, cut, name }) {
  const [open, setOpen] = useState(false);
  if (!me || !me.user || me.user.role !== "admin") return null;
  return html`
    <button class="btn small" onClick=${() => setOpen(true)}
      title="Create a read-only public link to this view (30 days).">
      <${Icon} name="link" size=${14} /> Share</button>
    ${open && html`<${ShareDialog} cut=${cut} name=${name} onClose=${() => setOpen(false)} />`}`;
}

function ShareDialog({ cut, name, onClose }) {
  const [link, setLink] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [copied, setCopied] = useState(false);
  const create = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api("/api/shares", { method: "POST", body: {
        kind: "dashboard",
        config: { cut: (cut && cut.dim) || "all", cut_value: (cut && cut.value) || null, name: name || null },
        expiry_days: 30 } });
      setLink(window.location.origin + "/share/" + r.token);
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const copy = async () => {
    try { await navigator.clipboard.writeText(link); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch (e) { setErr("Couldn't copy — select the link and copy manually."); }
  };
  return html`
    <${window.Modal} onClose=${onClose} label="Share this view" width="460px">
      <div style=${{ padding: "var(--s4)" }}>
        <h2 style=${{ margin: "0 0 var(--s2)", fontSize: "var(--fs-subhead)" }}>Share this view</h2>
        <p class="caption" style=${{ marginTop: 0 }}>
          Create a read-only public link to this dashboard under its current peer filter. Anyone with the link can view it for 30 days; no sign-in needed.</p>
        ${err && html`<div class="error-text" style=${{ margin: "var(--s2) 0" }}>${err}</div>`}
        ${!link ? html`
          <div class="row" style=${{ gap: "var(--s2)", marginTop: "var(--s3)" }}>
            <button class="btn primary" disabled=${busy} onClick=${create}>${busy ? "Creating…" : "Create link"}</button>
            <button class="btn quiet" onClick=${onClose}>Cancel</button>
          </div>` : html`
          <div style=${{ marginTop: "var(--s3)" }}>
            <div class="row" style=${{ gap: "var(--s2)", alignItems: "stretch" }}>
              <input class="ctl" readOnly value=${link} aria-label="Public link"
                onFocus=${e => e.target.select()} style=${{ flex: 1 }} />
              <button class="btn" onClick=${copy} title="Copy link">
                <${Icon} name=${copied ? "check" : "copy"} size=${14} /> ${copied ? "Copied" : "Copy"}</button>
            </div>
            <div class="caption" style=${{ marginTop: "var(--s2)" }}>Read-only · expires in 30 days.</div>
            <div class="row" style=${{ marginTop: "var(--s3)" }}>
              <button class="btn quiet" onClick=${onClose}>Done</button>
            </div>
          </div>`}
      </div>
    <//>`;
}

/* ============== the 80/20 home hero (2026-06-12 redesign) ==============
   Three questions, top to bottom: where do I sit overall (the arc), what
   should I look at (signals — flags, never advice), where do I sit per
   category (seven tiles). Leads/gaps become micro-band chips. The £
   opportunity lives inside signals; the journey strip returns when a second
   data period exists. */
function OverviewHero({ data, cut, cuts, orgKey, view, applyStrat, setView, setApplyStrat }) {
  const m = data.hero && data.hero.market;
  const locked = data.callouts && data.callouts.gaps_locked;
  // Signals follow the Market/Practice lens: MARKET view shows market-position signals
  // (below/on/above), PRACTICE view shows practice signals (differs-from-market +
  // differs-from-peers). signals_all is impact-sorted, so slice() gives the top of each.
  const _sigPos = view === "practice" ? ["differs", "practice"] : ["below", "on", "above"];
  const _viewSigs = (data.signals_all || []).filter(s => _sigPos.indexOf(s.position) !== -1);
  const _viewLive = _viewSigs.filter(s => s.status !== "dismissed");   // full ranked live pool — the panel
  const _viewTotal = _viewLive.length;                 // slices top-4 AFTER its optimistic dismiss filter
                                                       // (filter-before-slice, so a dismiss backfills #5 from the tail)
  const _viewNew = _viewSigs.filter(s => s.new && s.status !== "dismissed").length;
  // Cursor spotlight on the hero cards — a faint brand-tinted glow follows the
  // pointer (the tactile, alive feel). Direct DOM writes, no React re-render.
  useEffect(() => {
    const onMove = (e) => {
      const el = e.target.closest && e.target.closest(".ov-top .card");
      if (!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", ((e.clientX - r.left) / r.width * 100).toFixed(1) + "%");
      el.style.setProperty("--my", ((e.clientY - r.top) / r.height * 100).toFixed(1) + "%");
    };
    document.addEventListener("mousemove", onMove, { passive: true });
    return () => document.removeEventListener("mousemove", onMove);
  }, []);
  return html`
    <div class="ov-wrap">
      <div class="ov-aurora" aria-hidden="true"></div>
      ${data.strategy_can_edit && !data.strategy_complete && html`<${StrategyNudge} />`}
      ${!locked && html`
        <div class="ov-controls">
          <div class="ov-seg" role="group" aria-label="Dashboard lens">
            ${[["market", "Market position"], ["practice", "Practice"]].map(([k, lab]) => html`
              <button key=${k} type="button" class=${"ov-seg-btn" + (view === k ? " on" : "")} aria-pressed=${view === k}
                onClick=${() => setView && setView(k)}>${lab}</button>`)}
          </div>
          ${data.strategy_complete && html`
            <button type="button" class=${"ov-strat" + (applyStrat ? " on" : "")} role="switch" aria-checked=${applyStrat}
              onClick=${() => setApplyStrat && setApplyStrat(!applyStrat)}
              title=${applyStrat
                ? "Reading against your reward strategy — aim-aware colours and signal order. Click for the absolute market view."
                : "Showing the absolute market view (no stance applied). Click to read against your reward strategy."}>
              <span class="ov-strat-track"><span class="ov-strat-knob"></span></span>
              <span class="ov-strat-lbl">${applyStrat ? "Strategy applied" : "Strategy off"}</span>
            </button>`}
        </div>`}
      <div class="ov-top">
        ${view === "practice"
          ? html`<${ApproachPanel} approach=${data.hero.approach} pending=${locked} />`
          : html`<${OverallArc} market=${m} approach=${data.hero.approach} pending=${locked} pct=${Math.round((data.contribution && data.contribution.core_pct) || 0)} orgKey=${orgKey} stratOff=${data.strategy_complete && !applyStrat} />`}
        <${SignalsPanel} signals=${_viewLive} total=${_viewTotal} newCount=${_viewNew} locked=${locked} contribution=${data.contribution} view=${view} />
      </div>
      <div class="cat-grid">
        ${(data.hero.domains || []).map(d => html`<${CategoryTile} key=${d.name} d=${d} pending=${locked} aim=${marketAim(m)} view=${view} />`)}
      </div>
    </div>`;
}

/* Reward strategy check: AI synthesis of "are you delivering your own strategy?".
   Findings are computed server-side from your data + declared stance (the model
   only narrates them); on-demand so it doesn't spend on every load. Lives on the
   Signals page so each finding can signpost (onGoToDomain) to its signal group. */
function StrategyCheck({ onGoToDomain, signalDomains }) {
  const [st, setSt] = useState({ phase: "idle" });
  const cardRef = useRef(null);
  // Cursor spotlight — the same alive, brand-tinted glow the home hero cards carry,
  // so this reads as part of the same dashboard family.
  useEffect(() => {
    const el = cardRef.current; if (!el) return;
    const onMove = (e) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", ((e.clientX - r.left) / r.width * 100).toFixed(1) + "%");
      el.style.setProperty("--my", ((e.clientY - r.top) / r.height * 100).toFixed(1) + "%");
    };
    el.addEventListener("mousemove", onMove, { passive: true });
    return () => el.removeEventListener("mousemove", onMove);
  }, []);
  const run = async () => {
    setSt({ phase: "loading" });
    try {
      const r = await api("/api/strategy-diagnosis", { method: "POST", body: {} });
      if (!r.ok) { setSt({ phase: r.reason === "locked" ? "locked" : "nostrat" }); return; }
      setSt({ phase: "done", parts: r.parts || {}, source: r.source,
              onPlan: r.on_plan || [], illustrative: (r.caveats || {}).illustrative });
    } catch (e) { setSt({ phase: "error", error: e.message }); }
  };
  const f = st.parts || {};
  const hasDomain = (d) => !!(d && onGoToDomain && (!signalDomains || signalDomains.has(d)));
  const realFindings = (f.findings || []).some(x => x.area);   // off-plan, not the all-on-plan affirmation
  return html`
    <div class="card strat-diag" ref=${cardRef}>
      <div class="card-spot" aria-hidden="true"></div>
      <div class="card-head">
        <${Icon} name="compass" size=${15} /><span>Reward strategy check</span>
        <span class="sig-head-note">are you delivering the strategy you set?</span>
        ${st.phase === "done" && html`<span class="strat-badge">AI · review before use</span>`}
      </div>
      ${st.phase === "idle" && html`
        <p class="strat-intro">See where your market position is <b>delivering the reward strategy you set</b> —
          and where it's pulling against it. Read only from your own figures and your declared aims;
          each call signposts the signals behind it.</p>
        <button class="btn primary" onClick=${run}>Run the check</button>`}
      ${st.phase === "loading" && html`
        <div class="strat-loading"><${Spinner} /> Reading your strategy against your data…
          <span class="caption">a few seconds</span></div>`}
      ${st.phase === "done" && html`
        <p class="strat-summary">${f.summary}</p>
        <div class="strat-findings">
          ${(f.findings || []).map((x, i) => html`
            <div class="strat-finding" key=${i}>
              <div class="sf-head">${x.headline}</div>
              <div class="sf-detail">${x.detail}</div>
              <div class="sf-opt">${x.option}</div>
              ${hasDomain(x.area) && html`
                <button class="sf-jump" onClick=${() => onGoToDomain(x.area)}>
                  See the ${x.area} signals <${Icon} name="chevron-down" size=${13} /></button>`}
            </div>`)}
        </div>
        ${realFindings && st.onPlan && st.onPlan.length ? html`
          <div class="strat-onplan">
            <${Icon} name="check" size=${13} />
            <span><b>On plan:</b> ${st.onPlan.map((d, i) => html`${i ? html`<span class="sep"> · </span>` : null}${
              hasDomain(d)
                ? html`<button class="sf-jump-inline" onClick=${() => onGoToDomain(d)}>${d}</button>`
                : html`<span>${d}</span>`}`)} — tracking the aim you set.</span>
          </div>` : null}
        <div class="row spread strat-foot">
          <span class="caption">${st.source === "deterministic" ? "Rule-based read. " : ""}A starting point for your own judgement — not advice.</span>
          <button class="btn small" onClick=${run}>Re-run</button>
        </div>`}
      ${st.phase === "error" && html`
        <div class="error-text">Couldn't run the check — ${st.error}. <a href="#" onClick=${e => { e.preventDefault(); run(); }}>Retry</a></div>`}
    </div>`;
}

/* a quiet count-up for hero numbers (respects prefers-reduced-motion) */
function CountUp({ to, ms = 750 }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setV(to); return; }
    let raf; const t0 = performance.now();
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / ms);
      setV(Math.round(to * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  return html`${v}`;
}

/* The hero gauge (2026-06-13 rebuild): a precise instrument, not three fat
   segments. A quiet three-band scale is the backdrop; a single tapered needle
   pivots from the base centre, its angle driven by market.lean — the SAME
   value that bands the verdict word, so needle and word agree by construction.
   The band joins sit at the verdict threshold (±lean_threshold), so the band
   the needle rests in IS the verdict. The 34/46/14 counts move to a hairline
   legend — they are not the gauge's job. Real traffic-light palette
   (below=red · on=amber · above=green) on warm paper. */
// Proportional "Where you stand" arc geometry (2026-06-15). Shared by the
// needle-rotation helper and the render so they never diverge.
const ARC = { CX: 140, CY: 138, R: 102, W: 15 };
ARC.capF = (ARC.W / 2 / ARC.R) / Math.PI;
function arcSeams(market) {
  // block boundaries on the semicircle, each block ∝ its count.
  const pool = market.pool || (market.below + market.at + market.above) || 1;
  const span = 1 - 2 * ARC.capF;
  return {
    s0: ARC.capF,
    s1: ARC.capF + (market.below / pool) * span,
    s2: ARC.capF + ((market.below + market.at) / pool) * span,
    s3: 1 - ARC.capF,
  };
}
function proportionalNeedleRot(market) {
  // The centroid needle stays INSIDE the verdict block, positioned by the lean's
  // offset within that verdict's lean-range — so it never contradicts the word
  // while the proportional blocks carry the distribution. Returns a CSS rotation
  // (deg, clockwise-from-up); frac->rot is (frac-0.5)*180.
  const T = market.lean_threshold || 0.25;
  const lean = Math.max(-1, Math.min(1, market.lean || 0));
  const { s0, s1, s2, s3 } = arcSeams(market);
  const lerp = (a, b, t) => a + (b - a) * Math.max(0, Math.min(1, t));
  const v = market.verdict;
  let f = v === "above" ? lerp(s2, s3, (lean - T) / (1 - T))
        : v === "below" ? lerp(s0, s1, (lean + 1) / (1 - T))
        : lerp(s1, s2, (lean + T) / (2 * T));
  if (!isFinite(f)) f = 0.5;
  return (f - 0.5) * 180;
}

// strategy market_position reframe (§5.2): read the verdict against the member's
// declared target — an above-market member who AIMED there is on target, not flagged.
const STANCE_WORD = { lag: "below market", match: "on market", lead: "above market" };
function targetCopy(t) {
  const w = STANCE_WORD[t.stance] || "your aim";
  if (t.alignment === "on_target") return "On strategy — you aim to sit " + w;
  if (t.alignment === "ahead") return "Ahead of strategy — you aim to sit " + w;
  return "Behind strategy — you aim to sit " + w;
}
// ---- market-position colour code. After the RAG/strategy separation sweep (2026-06-27, see
// DECISIONS), POSITION is one fixed colour language everywhere: marketTone maps below=amber /
// on=green / above=red, strategy-INVARIANT. It drives the hero gauge donut, the category tiles,
// the MarketSpectrum bands and the cat-hero chip — identical strategy-on or off. The org's
// STRATEGY (alignment vs its declared aim) is a SEPARATE navy channel — the AlignmentChip pill +
// the spectrum's "your aim" bracket, strategy-on only — and NEVER recolours position. The per-
// signal rows keep their own polarity-aware tone (a below-market lower-is-better metric is
// honestly green). The retired attainment lens (attainTone / bandToneAim / ATTAIN_ALIGN) is gone.
const MKT_BIDX = { below: 0, on: 1, at: 1, above: 2 };
function marketAim(market) {
  return market && market.target ? ({ lag: 0, match: 1, lead: 2 })[market.target.stance] : null;
}
function marketTone(key) {                  // absolute market DIRECTION: below=amber · on=green · above=red (a fact, no stance)
  const idx = MKT_BIDX[key];
  if (idx == null) return "neutral";
  return idx === 0 ? "amber" : idx === 1 ? "green" : "red";   // below=amber · on=green · above=red (position lens)
}
// (Retired 2026-06-27, RAG/strategy separation sweep: the attainment lens — POS_RANK,
// bandToneAim, attainTone, ATTAIN_ALIGN — colour-bled strategy into position and is fully
// removed. Position now colours via marketTone above; alignment rides the AlignmentChip.)
const MKT_SOFT = { green: "var(--gauge-on)", amber: "var(--gauge-below)", red: "var(--gauge-above)",
                   redover: "color-mix(in srgb, var(--unfavourable-deep) 42%, var(--surface))",
                   grey: "color-mix(in srgb, var(--grey-neutral) 30%, var(--surface))",
                   neutral: "color-mix(in srgb, var(--chart-band-mid) 65%, var(--surface))" };
const MKT_RICH = { green: "color-mix(in srgb, var(--favourable) 56%, var(--surface))",
                   amber: "color-mix(in srgb, var(--amber-bright) 58%, var(--surface))",
                   red: "color-mix(in srgb, var(--unfavourable) 54%, var(--surface))",
                   redover: "color-mix(in srgb, var(--unfavourable-deep) 72%, var(--surface))",
                   grey: "color-mix(in srgb, var(--grey-neutral) 62%, var(--surface))",
                   neutral: "var(--chart-band-mid)" };
const MKT_CHIP = { green: "chip-good", red: "chip-bad", redover: "chip-bad-over", amber: "chip-mid", grey: "chip-neutral-mkt", neutral: "chip-practice" };
const MKT_VCLS = { green: "v-at", red: "v-above", redover: "v-above-over", amber: "v-below", grey: "v-neutral-mkt", neutral: "v-practice" };

// ── ALIGNMENT INDICATOR — the SEPARATE strategy channel (RAG/strategy separation, Phase B,
// 2026-06-27, ruling R2). The aggregate-position surfaces (the hero gauge + the category
// tiles) carry no signal-row to host an "On plan" pill, so the strategy relationship rides
// as this NAVY chip: a target glyph + a short, aim-relative label. It reads ONLY
// target.alignment (server _market_target → {stance, alignment}); with no target it renders
// NOTHING, so a strategy-off view degrades to pure RAG position colour with zero indicators.
// NAVY by design — never amber/green/red (that would re-merge with the position RAG) and
// never coral (risk) — so the two channels stay visually distinct. The label distinguishes
// behind vs ahead, which the old attainment colour could not (it lumped both as amber); the
// full sentence (targetCopy) rides as the title. DORMANT in Phase B: defined here, wired onto
// NO surface yet — the gauge / tiles / spectrum / category-hero revert passes adopt it.
const ALIGN_LABEL = { on_target: "On strategy", behind: "Behind strategy", ahead: "Ahead of strategy" };
// Compact tile chip: the state WORD alone — the full "… strategy" phrase overflows the tile's
// own-row even at the 11px type floor (David 2026-06-27). "strategy" is implied by the navy
// align-row context; the full phrase still rides the tooltip (targetCopy) + the gauge & hero chips.
const ALIGN_LABEL_SHORT = { on_target: "On", behind: "Behind", ahead: "Ahead" };
function AlignmentChip({ target, compact }) {
  if (!target || !ALIGN_LABEL[target.alignment]) return null;
  const label = (compact ? ALIGN_LABEL_SHORT : ALIGN_LABEL)[target.alignment];
  return html`<span class=${"align-chip align-" + target.alignment + (compact ? " align-chip-sm" : "")}
    title=${targetCopy(target)}><${Icon} name="target" size=${compact ? 11 : 12} /> ${label}</span>`;
}

// Shared "market spectrum" marker chart — the proportional below/on/above blocks
// unrolled onto a below↔above axis, with the org's declared AIM drawn on the axis
// and a "you are here" centroid marker. ONE component for the overview hero AND
// every domain page, so the read is identical everywhere. `market`: {below,at,above,
// pool,lean,verdict,lean_threshold}; `aim`: stance index (lag 0 / match 1 / lead 2)
// or null. Chart-only — callers supply their own verdict word/chip + counts.
function MarketSpectrum({ market, aim }) {
  const pool = market && (market.pool || ((market.below || 0) + (market.at || 0) + (market.above || 0)));
  if (!market || !pool) return null;
  const T = market.lean_threshold || 0.25;
  const lean = Math.max(-1, Math.min(1, market.lean != null ? market.lean : (market.above - market.below) / pool));
  const v = market.verdict || (lean < -T ? "below" : lean > T ? "above" : "at");
  const { s0, s1, s2, s3 } = arcSeams({ pool, below: market.below, at: market.at, above: market.above });
  const lerpC = (a, b, t) => a + (b - a) * Math.max(0, Math.min(1, t));
  const SPX0 = 24, SPX1 = 256, SPY = 58, SPH = 20;
  const spx = (frac) => SPX0 + frac * (SPX1 - SPX0);
  const spBands = [
    { k: "below", a: s0, b: s1, on: v === "below" },
    { k: "on", a: s1, b: s2, on: v === "at" },
    { k: "above", a: s2, b: s3, on: v === "above" },
  ].filter(g => g.b - g.a > 0.004).map(g => {
    // PASS 3 (RAG/strategy separation, 2026-06-27): POSITION lens, not attainment — each band
    // carries its OWN marketTone hue (below=amber / on=green / above=red), the verdict band rich.
    // Strategy NEVER enters the band hue now → strategy-off and strategy-on render identical bands
    // (on==off parity). Alignment stays SPATIAL: the navy "your aim" bracket + the you-marker show
    // where your aim sits vs where you are — strategy-on only, recoloured navy to match the
    // alignment channel (the gauge/tile AlignmentChip). On the scale, ABOVE-market is now a red BAND.
    const tone = marketTone(g.k);   // PER-BAND: below=amber / on=green / above=red (not one verdict hue)
    const n = g.k === "below" ? market.below : g.k === "on" ? market.at : market.above;
    return { k: g.k, x0: spx(g.a), x1: spx(g.b), col: g.on ? MKT_RICH[tone] : MKT_SOFT[tone], on: g.on, n };
  });
  const cF = v === "above" ? lerpC(s2, s3, (lean - T) / (1 - T))
           : v === "below" ? lerpC(s0, s1, (lean + 1) / (1 - T))
           : lerpC(s1, s2, (lean + T) / (2 * T));
  const youX = spx(Math.max(s0, Math.min(s3, isFinite(cF) ? cF : 0.5)));
  const aimZone = aim == null ? null : aim === 0 ? [s0, s1] : aim === 1 ? [s1, s2] : [s2, s3];
  const aimX0 = aimZone ? spx(aimZone[0]) : null, aimX1 = aimZone ? spx(aimZone[1]) : null;
  const aimMid = aimZone ? (aimX0 + aimX1) / 2 : null;
  const zoneLabels = spBands.filter(b => b.x1 - b.x0 > 26).map(b => ({
    x: (b.x0 + b.x1) / 2, t: b.k === "below" ? "below market" : b.k === "on" ? "on market" : "above market" }));
  const word = v === "above" ? "Above" : v === "below" ? "Below" : "On market";
  return html`
    <div class="arc-stage spectrum-stage">
      <svg viewBox="0 0 280 108" class="spectrum-svg" role="img"
        aria-label=${"Of " + pool + " comparable metrics, " + market.below + " below market, " + market.at + " on market, " + market.above + " above — overall " + word + (aimMid != null ? ", read against your aim zone" : "") + "."}>
        ${aimMid != null ? html`<g>
          <text x=${aimMid.toFixed(1)} y="19" text-anchor="middle" font-size="10.5" font-weight="600" fill="var(--navy)">your aim</text>
          <path d=${"M " + (aimX0 + 1).toFixed(1) + " 33 L " + (aimX0 + 1).toFixed(1) + " 27 L " + (aimX1 - 1).toFixed(1) + " 27 L " + (aimX1 - 1).toFixed(1) + " 33"} fill="none" stroke="var(--navy)" stroke-width="1.5"/>
          <line x1=${(aimX0 + 1).toFixed(1)} y1="33" x2=${(aimX0 + 1).toFixed(1)} y2=${SPY - 2} stroke="var(--navy)" stroke-width="1" stroke-dasharray="2 3" opacity="0.4"/>
          <line x1=${(aimX1 - 1).toFixed(1)} y1="33" x2=${(aimX1 - 1).toFixed(1)} y2=${SPY - 2} stroke="var(--navy)" stroke-width="1" stroke-dasharray="2 3" opacity="0.4"/>
        </g>` : null}
        <rect x=${SPX0 - 2} y=${SPY - 2} width=${SPX1 - SPX0 + 4} height=${SPH + 4} rx=${((SPH + 4) / 2).toFixed(1)} fill="var(--surface-sunk)"/>
        ${spBands.map(b => html`<rect key=${b.k} x=${(b.x0 + 1).toFixed(1)} y=${SPY} width=${Math.max(2, b.x1 - b.x0 - 2).toFixed(1)} height=${SPH} rx="3" fill=${b.col}/>`)}
        ${spBands.filter(b => b.x1 - b.x0 > 26).map(b => html`<text key=${"n" + b.k} x=${((b.x0 + b.x1) / 2).toFixed(1)} y=${SPY + SPH / 2} text-anchor="middle" dominant-baseline="central" font-size="10.5" font-weight="600" fill=${b.on ? "#fff" : "var(--ink-soft)"}>${b.n}</text>`)}
        <line x1=${youX.toFixed(1)} y1=${SPY - 7} x2=${youX.toFixed(1)} y2=${SPY + SPH + 7} stroke="var(--ink-soft)" stroke-width="2"/>
        <circle cx=${youX.toFixed(1)} cy=${SPY - 7} r="4" fill="var(--ink)" stroke="var(--surface)" stroke-width="1.5"/>
        ${zoneLabels.map((z, i) => html`<text key=${i} x=${z.x.toFixed(1)} y=${SPY + SPH + 20} text-anchor="middle" font-size="10.5" fill="var(--ink-soft)">${z.t}</text>`)}
      </svg>
    </div>`;
}

// Simple DONUT (ring) chart for the hero — segments ∝ count, a quiet total in the
// centre. Replaces the needle dial (2026-06-23). Used for BOTH the market read
// (below/on/above) and the practice read (differ/in-line); colours passed in by the
// caller so it stays a dumb renderer. Segments draw from 12 o'clock, clockwise.
function Donut({ segments, total, centerNum, sub, size, stroke, centerWord }) {
  size = size || 188; stroke = stroke || 26;
  const r = (size - stroke) / 2, cx = size / 2, cy = size / 2, C = 2 * Math.PI * r;
  let acc = 0;
  const arcs = (segments || []).filter(s => s.value > 0).map((s, i) => {
    const len = total ? (s.value / total) * C : 0;
    const gap = len > 8 ? 3 : 0;             // a small breather between real segments; none for slivers
    const drawn = Math.max(0.5, len - gap);
    const node = html`<circle key=${i} cx=${cx} cy=${cy} r=${r} fill="none" stroke=${s.color}
      stroke-width=${stroke} stroke-linecap="butt"
      stroke-dasharray=${drawn.toFixed(2) + " " + (C - drawn).toFixed(2)}
      stroke-dashoffset=${(-acc).toFixed(2)} transform=${"rotate(-90 " + cx + " " + cy + ")"} />`;
    acc += len;
    return node;
  });
  return html`
    <div class="donut" style=${{ width: size + "px", height: size + "px" }}>
      <svg viewBox=${"0 0 " + size + " " + size} class="donut-svg" aria-hidden="true">
        <circle cx=${cx} cy=${cy} r=${r} fill="none" stroke="var(--surface-sunk)" stroke-width=${stroke} />
        ${arcs}
      </svg>
      <div class="donut-center">
        ${centerWord
          ? html`<div class="donut-word">${centerWord}</div>
              <div class="donut-count num">${centerNum}${sub ? " " + sub : ""}</div>`
          : html`<div class="donut-num num">${centerNum}</div>
              ${sub ? html`<div class="donut-sub">${sub}</div>` : null}`}
      </div>
    </div>`;
}

// Shared position-verdict TEXT (extracted 2026-06-27, domain-page Pass 1) — ONE source for the
// verdict WORD + the magnitude caption, used by the home gauge AND the domain Market-position
// donut so the two surfaces read identically (no drift). Both take the market/_pool_verdict shape.
function verdictWord(v) { return v === "above" ? "Above" : v === "below" ? "Below" : "On market"; }
function leanCaption(market) {
  // magnitude adverb from percentile DEPTH (how far, not how many); falls back to the count lean
  // when depth_pctl is absent; verdict "at" → evenly balanced / leaning slightly.
  const v = market.verdict, T = market.lean_threshold || 0.25;
  const lean = Math.max(-1, Math.min(1, market.lean || 0)), mag = Math.abs(lean);
  if (v === "at") {
    if (mag < 0.06) return "evenly balanced";
    return "leaning slightly " + (lean < 0 ? "below" : "above");
  }
  const dp = market.depth_pctl, past = mag - T;
  const byCount = past > 0.2 ? "clearly" : past > 0.08 ? "moderately" : "marginally";
  const strength = dp == null ? byCount
    : v === "below" ? (dp < 25 ? "clearly" : dp < 40 ? "moderately" : "marginally")
    : (dp > 75 ? "clearly" : dp > 60 ? "moderately" : "marginally");
  return strength + " " + (v === "below" ? "below" : "above") + " the market";
}
function OverallArc({ market, approach, pending, pct, orgKey, stratOff }) {
  // Hooks run BEFORE the early return so the order is stable when market is null
  // vs present. 2.1 — the needle settles ONCE per org, on the first populated
  // render (localStorage gate); every later visit snaps. Reduced motion + no
  // localStorage both fall back to snapping (off means off).
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // needle now points at the centroid's position WITHIN the proportional arc
  // (computed up-front so the settle-animation hook below can target it).
  const rot = market ? proportionalNeedleRot(market) : 0;
  const animateNeedle = useMemo(() => {
    if (reduced || pending || !market) return false;
    try {
      const key = "lumi.gauge.firstPopulatedRender." + (orgKey || "default");
      if (localStorage.getItem(key) === "true") return false;  // already celebrated
      localStorage.setItem(key, "true");
      return true;                                             // first populated render → settle
    } catch (e) { return false; }                              // no localStorage → snap
  }, []);
  const [shownRot, setShownRot] = useState(animateNeedle ? 0 : rot);
  useEffect(() => {
    if (!animateNeedle) { setShownRot(rot); return; }          // snap to the reading
    const id = setTimeout(() => setShownRot(rot), 90);         // paint at 0, then settle
    return () => clearTimeout(id);
  }, [rot]);
  // Data-pending: below the insights-unlock threshold a verdict from a handful of
  // metrics isn't credible — greyed dial, no needle, not a reading.
  if (pending) return html`
    <div class="card arc-card arc-pending">
      <div class="card-spot" aria-hidden="true"></div>
      <div class="card-head"><${Icon} name="compass" size=${15} /><span>Where you stand</span></div>
      <div class="arc-stage">
        <svg viewBox="0 0 280 170" class="arc-svg" role="img" aria-label="Not enough data to position yet — keep submitting.">
          <path d="M 38 138 A 102 102 0 0 1 242 138" fill="none" stroke="var(--surface-sunk)" stroke-width="16" stroke-linecap="round"/>
          <path d="M 38 138 A 102 102 0 0 1 242 138" fill="none" stroke="var(--chart-band-mid)" stroke-width="13" stroke-linecap="round"/>
          <circle cx="140" cy="138" r="8" fill="var(--surface)" stroke="#9AA3B5" stroke-width="3.25"/>
          <circle cx="140" cy="138" r="2.25" fill="#9AA3B5"/>
        </svg>
      </div>
      <div class="arc-verdict">
        <div class="arc-word arc-word-pending">Not enough data to position yet</div>
        <div class="arc-lean">Keep submitting — your position appears once enough data is comparable.</div>
      </div>
      <div class="arc-legend num"><span class="arc-pending-note">Data pending — ${pct || 0}% of key reward questions submitted</span></div>
    </div>`;

  if (!market) return html`
    <div class="card arc-card"><div class="card-head"><${Icon} name="compass" size=${15} /><span>Where you stand</span></div>
      <div class="caption" style=${{ padding: "var(--s4) var(--s2)" }}>
      Your overall position appears once enough of your data is comparable.</div></div>`;
  const v = market.verdict;                                   // "below" | "at" | "above"
  const word = verdictWord(v);                                // shared verdict-text helper
  // The BANDS stay ABSOLUTE RAG (below=red, on=amber, above=green) — they're the
  // factual composition, sized by count, and must never hide the gap. The VERDICT
  // WORD carries NO good/bad colour (2026-06-23, "mirror, not consultant"): the verdict
  // word renders in neutral ink, IDENTICAL on Strategy ON and OFF — the on-target meaning
  // lives only in the footer line. The donut bands keep their position colour; the word
  // never judges below/on/above as success or failure.
  // (Retired 2026-06-27: the pre-Donut proportional-arc render — bands / seam ticks / needle,
  // all computed here but never rendered since the Donut replaced the dial — is removed along
  // with the attainment lens it depended on. The live gauge is the <Donut> below, per-band by
  // marketTone; the centroid position is handled by proportionalNeedleRot / animateNeedle.)
  const leanWord = leanCaption(market);                       // shared magnitude-caption helper
  // PASS 5 (RAG/strategy separation, 2026-06-27) — the verdict WORD + subtitle = market POSITION,
  // strategy-INVARIANT, matching the gauge colour + the below/on/above counts. Was a FIX-2
  // attainment override (on/ahead of aim → "On target" / "...as you intend") that put the
  // ALIGNMENT channel into the word, competing with the position colour (an amber gauge under
  // "On target" read as a contradiction). Alignment now lives ONLY in the navy AlignmentChip pill
  // below; strategy-off already showed these position strings, so strategy-on now matches (on==off).
  const headWord = word;
  const headLean = leanWord;
  // PASS 1 (RAG/strategy separation, 2026-06-27) — the ring colours by POSITION, not
  // attainment: each band carries its OWN marketTone hue (below=amber / on=green / above=red),
  // the verdict band richer so the eye lands. Strategy NEVER enters the gauge colour now, so
  // strategy-off and strategy-on render the SAME hue per band (on==off colour parity — the
  // canary). The alignment relationship moved OUT of colour and INTO the navy AlignmentChip
  // below. (Pass 5 also moved the verdict WORD to position — _onTarget is fully retired.)

  return html`
    <div class="card arc-card">
      <div class="card-spot" aria-hidden="true"></div>
      <div class="card-head">
        <${Icon} name="compass" size=${15} /><span>Where you stand</span>
      </div>
      <div class="arc-stage" role="img"
        aria-label=${"Where you stand: of " + market.pool + " comparable metrics, " + market.below + " below market, " + market.at + " on market, " + market.above + " above. Overall: " + word + ", " + leanWord + "."}>
        <${Donut}
          segments=${[
            { value: market.below, color: (v === "below" ? MKT_RICH : MKT_SOFT)[marketTone("below")] },
            { value: market.at, color: (v === "at" ? MKT_RICH : MKT_SOFT)[marketTone("at")] },
            { value: market.above, color: (v === "above" ? MKT_RICH : MKT_SOFT)[marketTone("above")] },
          ]}
          total=${market.pool} centerNum=${market.pool} sub="metrics" centerWord=${headWord} size=${210} stroke=${28} />
      </div>
      <div class="arc-verdict">
        ${/* PASS 6: the verdict WORD moved into the donut centre; this keeps only the magnitude
              adverb (clearly/moderately/marginally below/above the market) as one quiet caption. */ ""}
        <div class="arc-lean">${headLean}</div>
      </div>
      <div class="arc-legend num">
        <span><span class="arc-leg-fig">${market.below}</span> Below</span>
        <span><span class="arc-leg-fig">${market.at}</span> On market</span>
        <span><span class="arc-leg-fig">${market.above}</span> Above</span>
      </div>
      ${market.target ? html`
        <div class="arc-target"><${AlignmentChip} target=${market.target} /></div>`
      : stratOff ? html`
        <div class="arc-target arc-target-off" title="You've turned your reward strategy off — this is the absolute market view, with no aim applied. Switch it back on above to read against your stance.">
          <${Icon} name="target" size=${13} /><span>Strategy off — absolute market view</span>
        </div>`
      : html`
        <button class="arc-target arc-target-unset" onClick=${() => nav("/strategy")}
          title="Set your market-position stance so lumi reads this against your aim, not a generic flag.">
          <${Icon} name="target" size=${13} /><span>Set your reward strategy to read this against your aim</span>
        </button>`}
    </div>`;
}


// PRACTICE lens for the hero (the dashboard toggle's "Practice" view): the approach
// read — how many competitive practices differ from the market norm — as the headline,
// with a proportional differ/in-line bar. The market gauge's sibling, shown INSTEAD of
// it (the two-axis split: market position vs practice difference, never mixed on screen).
function ApproachPanel({ approach, pending }) {
  if (pending || !approach || !approach.pool) return html`
    <div class="card arc-card">
      <div class="card-head"><${Icon} name="layers" size=${15} /><span>How you compare on practice</span></div>
      <div class="caption" style=${{ padding: "var(--s4) var(--s2)" }}>
        ${pending ? "Your practice mix appears once enough of your data is comparable."
                  : "No practice metrics are comparable in this peer set yet."}</div>
    </div>`;
  const differ = approach.differ, inLine = approach.in_line, pool = approach.pool;
  const fr = pool ? Math.round(1000 * differ / pool) / 10 : 0;
  return html`
    <div class="card arc-card">
      <div class="card-spot" aria-hidden="true"></div>
      <div class="card-head"><${Icon} name="layers" size=${15} /><span>How you compare on practice</span></div>
      <div class="appr-stage">
        <div class="arc-stage" role="img"
          aria-label=${differ + " of " + pool + " practices differ from the market norm; " + inLine + " in line."}>
          <${Donut}
            segments=${[
              { value: differ, color: "var(--differs)" },
              { value: inLine, color: "var(--chart-band-mid)" },
            ]}
            total=${pool} centerNum=${pool} sub="practices" size=${210} stroke=${28} />
        </div>
        <div class="appr-headline num"><b>${approach.differ}</b> of ${approach.pool} practices differ from market</div>
        <div class="appr-legend num">
          <span><span class="appr-dot appr-dot-differ"></span><b>${differ}</b> differ</span>
          <span><span class="appr-dot appr-dot-inline"></span><b>${inLine}</b> in line with the market</span>
        </div>
      </div>
      <div class="appr-note caption">A different way of doing things, not a gap to close — the ones worth acting on appear in your signals.</div>
    </div>`;
}


const LENS_ICON = { save: "coins", attract: "magnet", retain: "anchor", engage: "heart" };
const CAT_ICON = { "Pay": "coins", "Incentives": "trending-up", "Benefits": "shield",
  "Time Off": "sun", "Wellbeing": "heart", "Recognition": "award", "Governance": "list-checks" };
function SignalsPanel({ signals, total, newCount, locked, contribution, view }) {
  const sigs = signals || [];
  // triage actions are available on every signal — the home briefing keeps a local
  // optimistic overlay so a dismiss/priority/save updates instantly (the server has
  // the truth on next load).
  const [stOv, setStOv] = useState({});
  const [leaving, setLeaving] = useState({});                 // sid -> true while its dismiss animates out (kept in `shown` until the fade ends)
  const listRef = useRef(null);
  const posRef = useRef(null);                                // sid -> offsetTop from the last paint (null on first paint, so the initial list never animates in)
  const reduceMotion = typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const effStatus = s => { const k = s.sig_id || s.question_id; return k in stOv ? stOv[k] : s.status; };
  // Dismiss → backfill choreography. Dismiss is two-phase: flag the row `leaving` (CSS
  // fades it out in place, count stays 3), then after the fade COMMIT the dismiss so the
  // row drops from `shown` and the next-ranked signal backfills the tail. Pin/Save never
  // change membership, so they commit instantly; reduced-motion commits instantly too.
  const onSet = (sid, status) => {
    if (status === "dismissed" && !reduceMotion) {
      setLeaving(p => ({ ...p, [sid]: true }));
      signalAction(sid, status).catch(() => {});
      setTimeout(() => {
        setStOv(p => ({ ...p, [sid]: "dismissed" }));
        setLeaving(p => { const n = { ...p }; delete n[sid]; return n; });
      }, 260);
    } else {
      setStOv(p => ({ ...p, [sid]: status || "active" }));
      signalAction(sid, status).catch(() => {});
    }
  };
  const shown = sigs.filter(s => effStatus(s) !== "dismissed").slice(0, 3);   // filter-before-slice: a dismiss backfills #4 from the tail
  // FLIP the briefing on every commit: survivors slide up from where they were, the
  // backfilled row rises + fades in. Runs before paint so there's no flash at the old
  // layout; the first paint (posRef null) only records positions — no entrance on load.
  React.useLayoutEffect(() => {
    const listEl = listRef.current;
    if (!listEl) { posRef.current = null; return; }
    const rows = listEl.querySelectorAll(".signal-row[data-sid]");
    const cur = new Map();
    rows.forEach(el => cur.set(el.getAttribute("data-sid"), el.offsetTop));
    const prev = posRef.current;
    posRef.current = cur;
    if (!prev || reduceMotion) return;
    rows.forEach(el => {
      const sid = el.getAttribute("data-sid");
      const was = prev.get(sid), top = cur.get(sid);
      if (was == null) {                                       // backfilled row — rise + fade in
        el.style.transition = "none"; el.style.transform = "translateY(12px)"; el.style.opacity = "0";
        el.getBoundingClientRect();
        requestAnimationFrame(() => {
          el.style.transition = "transform .34s cubic-bezier(.22,.61,.36,1), opacity .3s ease";
          el.style.transform = ""; el.style.opacity = "";
          setTimeout(() => { el.style.transition = ""; }, 380);
        });
      } else if (was !== top) {                                // survivor — FLIP slide to its new slot
        el.style.transition = "none"; el.style.transform = "translateY(" + (was - top) + "px)";
        el.getBoundingClientRect();
        requestAnimationFrame(() => {
          el.style.transition = "transform .34s cubic-bezier(.22,.61,.36,1)";
          el.style.transform = "";
          setTimeout(() => { el.style.transition = ""; }, 380);
        });
      }
    });
  });
  return html`
    <div class="card signals-card">
      <div class="card-spot" aria-hidden="true"></div>
      <div class="card-head">
        <${Icon} name="flag" size=${15} />
        <span>Signals${total > shown.length ? " · top " + shown.length : (shown.length ? " · " + shown.length : "")}</span>
        ${newCount > 0 ? html`<span class="sig-new-chip">${newCount} new</span>` : null}
        <span class="sig-head-note">${view === "practice" ? "practice differences — we flag, you decide" : "market positions — we flag, you decide"}</span>
      </div>
      ${!locked && shown.length > 0 ? html`<div class="sig-ranknote num">${view === "practice" ? "ranked by rarity" : "ranked by market gap"}</div>` : null}
      ${locked ? html`
        <div class="insight-lock" style=${{ marginTop: "var(--s2)", flex: 1 }}>
          <div class="blurred" aria-hidden="true">
            ${[1, 2, 3].map(i => html`<div key=${i} class="signal-row"><span class="signal-val">£—k</span><span class="caption">a signal appears here once unlocked</span></div>`)}
          </div>
          <div class="lock-note">
            <${Chip} kind="accent"><${Icon} name="lock" size=${11} /> Locked<//>
            <div class="caption" style=${{ textAlign: "center", maxWidth: "260px" }}>
              Signals unlock with your insights — complete your key reward questions${contribution && contribution.days_left != null ? ` (${contribution.days_left} days left)` : ""}.</div>
            <button class="btn small outline-navy" onClick=${() => nav("/your-data/submit")}>Submit data</button>
          </div>
        </div>` :
      shown.length === 0 ? html`
        <div class="signals-empty">
          <span class="signals-empty-ring"><${Icon} name="flag" size=${18} /></span>
          <div class="caption" style=${{ maxWidth: "320px" }}>No signals right now — nothing in your data crosses a signal threshold. They'll appear here as your position or the market moves.</div>
        </div>` :
      [html`<div class="signals-list" key="list" ref=${listRef}>
        ${shown.map(s => { const pt = posTag(s); const sid = s.sig_id || s.question_id; return html`
          <div key=${sid} data-sid=${sid} class=${"signal-row sig-row-axis sig-tone-" + pt.tone + (s.new ? " is-new" : "") + (s.risk_framed ? " is-risk" : "") + (s.confirm ? " is-confirm" : "") + (leaving[sid] ? " sig-leaving" : "")} onClick=${() => openMetric(s.question_id)} onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openMetric(s.question_id); } }} role="button" tabindex="0">
            ${sigParts(s, pt)}
            <${SignalActions} status=${effStatus(s)} sid=${sid} onSet=${onSet} />
          </div>`; })}
      </div>`,
      html`<div class="signals-foot" key="foot">
        <span>Tap a signal to open the metric · prioritise, save or dismiss with the icons.</span>
        <a href="#/signals">${total > shown.length ? "See all " + total + " signals →" : "See all signals →"}</a>
      </div>`]}
    </div>`;
}

/* The dedicated Signals explore page — the WHOLE organisation's flags, not the
   home's capped briefing. Grouped by outcome lens (attract / retain / engage /
   save), filterable, each row the peer fact with a click through to the metric.
   Flags, never advice: the user decides whether each difference is good or bad. */
const LENS_ORDER = ["attract", "retain", "engage", "save"];
const LENS_LABEL = { attract: "Attract", retain: "Retain", engage: "Engage", save: "Save" };
const LENS_DESC = { attract: "how you draw talent in", retain: "what keeps people staying",
  engage: "how people experience work", save: "where your spend sits vs the market" };
// legacy fallback tags (the engine now supplies s.tag in plain market language)
const KIND_LABEL = { money: "£ GAP", save: "HIGHER THAN MARKET", behind: "LOWER THAN MARKET",
  prevalence: "MOST DO THIS", outlier: "LOWER THAN MARKET", depth: "LOWER THAN MARKET", rare: "FEW OFFER THIS" };
// Every row reads the same three things in the same order: what it is (bold) ·
// where you stand (the market fact) · the categorical tag. "Worth a look" leads
// only where there's a supported worse direction (behind / a common practice you
// lack). The tag answers one question — how do you compare to the market?
const sigParts = (s, pt) => [
  html`<span class=${"signal-roundel lens-" + s.lens} key="r"><${Icon} name=${LENS_ICON[s.lens] || "flag"} size=${15} /></span>`,
  html`<span class="signal-body" key="b">
    <b class="sig-name">${s.new ? html`<span class="sig-new-tag">NEW</span> ` : null}${s.name || s.label_short}${s.risk_framed ? html` <span class="sig-risk"><${Icon} name="shield" size=${11} /> Risk</span>` : null}${s.confirm ? html` <span class="sig-onplan"><${Icon} name="check" size=${11} /> On plan</span>` : null}</b>
    <span class="sig-stand">${s.stand || s.detail}</span></span>`,
  html`<span class=${"pos-tag pos-" + (pt ? pt.tone : "neutral")} key="t">${s.tag || KIND_LABEL[s.kind] || s.kind}</span>`,
];
// Triage controls (prioritise · save · dismiss / restore) — ONE shared control on
// EVERY signal wherever it appears: the home briefing, each domain page, and the
// Signals explore page. onSet(sid, status) persists + optimistically updates; status
// is the final state (null = back to active/inbox). Toggle logic lives here so every
// surface behaves identically.
function SignalActions({ status, sid, onSet }) {
  return html`<span class="sig-actions" onClick=${e => e.stopPropagation()}>
    ${status === "dismissed" ? html`
      <button class="sig-act" title="Restore to inbox" aria-label="Restore signal to inbox" onClick=${() => onSet(sid, null)}><${Icon} name="refresh" size=${15} /></button>` : html`
      <button class=${"sig-act" + (status === "priority" ? " on" : "")} title=${status === "priority" ? "Remove priority" : "Prioritise"} aria-label="Prioritise signal" aria-pressed=${status === "priority"} onClick=${() => onSet(sid, status === "priority" ? null : "priority")}><${Icon} name="pin" size=${15} /></button>
      <button class=${"sig-act" + (status === "saved" ? " on" : "")} title=${status === "saved" ? "Remove from saved" : "Save"} aria-label="Save signal" aria-pressed=${status === "saved"} onClick=${() => onSet(sid, status === "saved" ? null : "saved")}><${Icon} name="star" size=${15} /></button>
      <button class="sig-act" title="Dismiss" aria-label="Dismiss signal" onClick=${() => onSet(sid, "dismissed")}><${Icon} name="close" size=${15} /></button>`}
  </span>`;
}
// Persist a triage action (home panel + domain pages call this; the Signals page keeps
// its own statuses state). Best-effort — the optimistic UI is the caller's.
function signalAction(sid, status) {
  return api("/api/signals/action", { method: "POST", body: { question_id: sid, status: status || "active" } });
}
const SIG_TABS = [
  { k: "inbox", label: "Inbox", icon: "flag", f: s => s.status !== "dismissed" },
  { k: "priority", label: "Priority", icon: "pin", f: s => s.status === "priority" },
  { k: "saved", label: "Saved", icon: "star", f: s => s.status === "saved" },
  { k: "dismissed", label: "Dismissed", icon: "close", f: s => s.status === "dismissed" },
];
// Market-position axis (spec §6.3): the cut users come for. below/above = Substance,
// differs = Approach — so this single control subsumes the register split. `practice` is
// the NON-MARKET bucket: signals on a non-competitive domain (Governance) which has no
// market rate, so they read "differs from peers", never a market verdict (Governance
// scoping ruling — signals layer; same competitiveness flag the hero scopes by).
const SIG_POSITIONS = [
  { k: "below", label: "below market" },
  { k: "on", label: "on market" },
  { k: "above", label: "above market" },
  { k: "differs", label: "differs from market" },
  { k: "practice", label: "differs from peers" },
];
const SIG_DOMAINS = ["Pay", "Incentives", "Benefits", "Time Off", "Wellbeing", "Recognition", "Governance"];
const POS_TAG_TEXT = { below: "below market", on: "on market", above: "above market", differs: "differs from market", practice: "differs from peers" };
// Solid stance-aware colour for a market position — the SAME palette the home gauge
// uses, so the two surfaces speak one colour language (on the aim = green, past it =
// amber, short of it = red). Approach (differs) carries no market stance → purple.
const SIG_TONE_SOLID = { green: "var(--favourable)", amber: "var(--amber-bright)",
  red: "var(--unfavourable)", neutral: "var(--chart-band-mid)", approach: "var(--differs)" };
function posColor(k) { return (k === "differs" || k === "practice") ? SIG_TONE_SOLID.approach : SIG_TONE_SOLID[marketTone(k)]; }
// The factual position word stays true to the number; the COLOUR is direction-corrected
// absolute RAG, exactly like the home dashboard — worse than market red, on market amber,
// better than market green. Approach metrics (differs) and non-competitive practice
// signals (practice) carry no market position → purple; neutral-polarity metrics are
// context → navy; lower-is-better metrics flip (below the market = good = green, above
// = worse = red).
// severity ADVERB (Ruling A, 2026-06-26): per-metric REAL-TERMS %-gap from the peer median
// calibrates the verdict word, mirroring the hero's depth adverb but per-metric (a reward director
// judges materiality in gap SIZE, not percentile rank — so the hero stays percentile, the signal
// reads real-gap; different scopes, both calibrated). clearly >40% · moderately 15-40% · marginally
// 3-15% · <3% = at-market noise, NO adverb. ONLY positioned value verdicts (below/above) — server
// attaches s.gap_pct only there (prevalence/neutral/no-value excluded by property).
function severityAdverb(s) {
  const g = s.gap_pct;
  if (g == null || g < 3 || (s.position !== "below" && s.position !== "above")) return "";
  return (g > 40 ? "clearly " : g >= 15 ? "moderately " : "marginally ");
}
function posTag(s) {
  const text = POS_TAG_TEXT[s.position] || "differs from market";
  if (s.position === "practice") return { text, tone: "approach", hint: "" };
  if (s.polarity === "neutral") return { text, tone: "neutral", hint: "context, not a verdict" };
  if (s.position === "differs")  return { text, tone: "approach", hint: "" };
  const adv = severityAdverb(s);
  if (s.polarity === "lower")    return { text: adv + text, tone: s.position === "below" ? "green" : "red", hint: "lower is better" };
  return { text: adv + text, tone: marketTone(s.position), hint: "" };
}
// ANCHOR PROVENANCE mark (stage 2, ruling B, 2026-06-26): the market-median anchor's source quality —
// a QUIET, TEXT-ONLY mark on the figure line (so it composes near "market median £Y", distinct from the
// verdict adverb in the pill and from the page-level peer-n caveat). THREE-STATE: A/B/C collapse to
// "verified source" (grade + citation on hover — the Anchor Register payoff); EST → "estimate" (honest
// "no published source"); UNKNOWN (s.anchor_grade absent) → NOTHING (silent default for the ~86%).
// TEXT, NOT a check — the row's green ✓ "On plan" pill already owns the check glyph (no clash).
function provMark(s) {
  const g = s.anchor_grade;
  if (!g) return null;                                   // UNKNOWN — unmarked, byte-identical
  if (g === "EST")
    return html`<span class="sig-prov sig-prov-est" tabindex="0" title="Curator estimate — no published source. Treat directionally."> · estimate</span>`;
  return html`<span class="sig-prov sig-prov-ok" tabindex="0" title=${"Verified anchor (Grade " + g + ")" + (s.anchor_source ? " · " + s.anchor_source : "")}> · verified source</span>`;
}
// The locked Signals state is the single biggest pull to submit data, so it
// sells the payoff: what signals do, how close you are, and a blurred taste of
// the real thing (the actual tag vocabulary, detail obscured).
function SignalsLocked({ contrib, me }) {
  const pct = Math.round(contrib.core_pct || 0);
  const target = contrib.target_pct || 90;
  const days = contrib.days_left;
  const canEdit = me && (me.user.role === "admin" || me.user.role === "contributor");
  const teasers = [
    { lens: "save", icon: "coins", tag: "£ GAP", name: "Bonus opportunity", stand: "sits below the market median for your size" },
    { lens: "retain", icon: "magnet", tag: "LOWER THAN MARKET", name: "Company sick pay", stand: "below where most of your peers land" },
    { lens: "engage", icon: "users", tag: "MOST DO THIS", name: "Paid parental leave", stand: "offered by 8 in 10 similar organisations" },
    { lens: "attract", icon: "star", tag: "HIGHER THAN MARKET", name: "Holiday allowance", stand: "ahead of the market — a story worth telling" },
  ];
  return html`
    <div class="sig-unlock">
      <div class="card sig-unlock-hero">
        <div class="sig-unlock-ring"><${Icon} name="flag" size=${26} /></div>
        <h2 class="display-title" style=${{ margin: "0 0 var(--s2)" }}>Your signals are waiting</h2>
        <p style=${{ margin: "0 auto", maxWidth: "440px" }}>Once your reward data is in, lumi surfaces the handful
        of things worth your attention — the <b>£ gaps</b>, where you sit <b>behind or ahead</b> of the market, and the
        practices <b>most peers offer that you don't</b>. No dashboards to wade through; we flag, you decide.</p>
        <div class="sig-unlock-prog">
          <div class="row spread" style=${{ marginBottom: "var(--s2)", alignItems: "baseline" }}>
            <b>Reward data ${pct}%</b>
            <span class="caption">unlocks at ${target}%${days != null ? ` · ${days} days left` : ""}</span>
          </div>
          <div class="progressbar"><div style=${{ width: Math.min(100, target ? 100 * pct / target : 0) + "%" }}></div></div>
        </div>
        ${canEdit
          ? html`<button class="btn primary sig-unlock-cta" onClick=${() => nav("/your-data")}>
              <${Icon} name="pencil" size=${14} /> ${pct > 0 ? "Continue adding your data" : "Add your reward data"}</button>`
          : html`<div class="caption" style=${{ marginTop: "var(--s3)" }}>Your Admin or a Contributor adds the reward data that unlocks these for the whole team.</div>`}
      </div>
      <div class="sig-teaser-label caption">A taste of what you'll unlock</div>
      <div class="sig-teaser-grid" aria-hidden="true">
        ${teasers.map((t, i) => html`
          <div key=${i} class=${"signal-row lens-" + t.lens + " sig-teaser"}>
            <span class="signal-roundel"><${Icon} name=${t.icon} size=${15} /></span>
            <span class="signal-body">
              <b class="sig-name">${t.name}</b>
              <span class="sig-stand">${t.stand}</span></span>
            <span class="sig-tag">${t.tag}</span>
            <span class="sig-teaser-lock"><${Icon} name="lock" size=${12} /></span>
          </div>`)}
      </div>
    </div>`;
}

window.SignalsPage = function ({ me }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [tab, setTab] = useState("inbox");
  const [posF, setPosF] = useState("all");             // market-position filter (single-select)
  const [provF, setProvF] = useState(false);           // "verified source" filter (independent predicate)
  const [riskF, setRiskF] = useState(false);           // "risk only" filter (independent predicate)
  const [groupBy, setGroupBy] = useState("domain");    // domain · lens
  const [acting, setActing] = useState({});            // optimistic status overrides
  const [jumpTo, setJumpTo] = useState(null);          // strategy-check → domain signpost
  useEffect(() => {
    api("/api/overview").then(d => {
      setData(d);
      // viewing the Signals page clears NEW: mark every current signal seen
      const ids = (d.signals_all || []).map(s => s.sig_id || s.question_id);
      if (ids.length) api("/api/signals/seen", { method: "POST", body: { sig_ids: ids } }).catch(() => {});
    }).catch(e => setErr(e.message));
  }, []);
  // Strategy-check signpost: once the view has re-rendered to show the target
  // domain's group, scroll it into view and flash it. Runs after the state the
  // jump set (tab/filter/groupBy) has committed.
  useEffect(() => {
    if (!jumpTo) return;
    const el = document.getElementById("sig-dom-" + jumpTo);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      el.classList.add("sig-group-flash");
      setTimeout(() => el.classList.remove("sig-group-flash"), 1700);
    }
    setJumpTo(null);
  }, [jumpTo, tab, posF, groupBy]);
  // surface the named domain's signals on the same page, then scroll to them
  const goToDomain = (dom) => { setTab("inbox"); setPosF("all"); setProvF(false); setRiskF(false); setGroupBy("domain"); setJumpTo(dom); };
  if (err) return html`<${EmptyState} icon="flag" title="Couldn't load your signals" body=${err} />`;
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "var(--s8)" }}><${Spinner} /></div>`;
  const contrib = data.contribution || {};
  // Signals only exist once insights unlock. For everyone short of that — and
  // especially a brand-new 0%-data member — this page is the single biggest
  // reason to submit, so it gets an engaging teaser rather than a dead end.
  const unlocked = data.contribution ? !!contrib.insights_unlocked : !(data.callouts && data.callouts.gaps_locked);
  // triage identity is sig_id (= question_id, or qid::row_id for a matrix row)
  const all = (data.signals_all || []).map(s => { const sid = s.sig_id || s.question_id; return { ...s, status: acting[sid] !== undefined ? acting[sid] : (s.status || null) }; });
  // domains that have at least one live signal — so the strategy check only
  // signposts where there's actually something to land on.
  const signalDomains = new Set(all.filter(s => s.status !== "dismissed").map(s => s.domain).filter(Boolean));
  // Signals rows colour by market DIRECTION (below/on/above) — a per-metric FACT, NOT an
  // attainment verdict: a metric has a position, not a stance; attainment is domain-level (the
  // MetricPage ruling). The strategy relationship (confirm / tension) is carried by the row's
  // icon/treatment, never by colour. (No stance `aim` here — that was orphaned attainment plumbing
  // from the removed alignTone; the tiles, which ARE domains, colour by attainment via attainTone.)

  const setStatus = (sid, status) => {
    setActing(a => ({ ...a, [sid]: status }));
    api("/api/signals/action", { method: "POST", body: { question_id: sid, status: status || "active" } })
      .catch(() => { setActing(a => { const n = { ...a }; delete n[sid]; return n; }); toast("Couldn't save that — try again", "error"); });
  };
  const toggle = (sid, cur, target) => setStatus(sid, cur === target ? null : target);

  const counts = {}; SIG_TABS.forEach(t => { counts[t.k] = all.filter(t.f).length; });
  const cur = SIG_TABS.find(t => t.k === tab) || SIG_TABS[0];
  // Triage order within a domain group (Pass 3.5, ruling A — PIN beats confirm). PIN is checked
  // FIRST: a pinned ("priority") row lifts to the group TOP even when confirm — the user's explicit
  // "keep this up top" is a POSITION instruction that wins the genuine conflict with confirm's
  // position-demotion. UNPINNED confirm still sinks to the TAIL (rank 3 — Pass 3's L4 demote-not-
  // delete mirror, fully preserved). SAVE stays rank 1: it's a RETRIEVAL instruction (orthogonal to
  // position), so a saved+confirm row still tail-clumps — no conflict to resolve (A′ rejected as
  // over-reach). Degrades byte-identical: strategy-off → s.confirm falsy → the confirm?3 branch never
  // fires → rank collapses to priority?0 : saved?1 : 2 (pre-Pass-3).
  const rank = s => (s.status === "priority" ? 0 : s.confirm ? 3 : s.status === "saved" ? 1 : 2);
  const triaged = all.filter(cur.f);                              // current triage tab
  // NEUTRAL-polarity signals (cost/spend context) are NEVER coloured by verdict —
  // engine principle #5 — so they're excluded from the position bar/chip composition
  // (which is absolute RAG via posColor). They still render as rows with their navy
  // "context, not a verdict" tag, and stay reachable under the position filter.
  const posCounts = {}; triaged.forEach(s => { if (s.polarity === "neutral") return; posCounts[s.position] = (posCounts[s.position] || 0) + 1; });
  const effPos = (posF !== "all" && !posCounts[posF]) ? "all" : posF;   // a filter the tab emptied falls back
  // NEW-DATA filters (scoped B, 2026-06-26): provenance + risk are INDEPENDENT predicates that AND with the
  // position single-select — a director wants "below market AND verified source", not either/or. Pure VIEW op.
  const isVerified = s => s.anchor_grade === "A" || s.anchor_grade === "B" || s.anchor_grade === "C";
  const provCount = triaged.filter(isVerified).length;
  const riskCount = triaged.filter(s => s.risk_framed).length;
  const visible = triaged.filter(s => effPos === "all" || s.position === effPos)
    .filter(s => !provF || isVerified(s)).filter(s => !riskF || s.risk_framed);
  const order = groupBy === "domain" ? SIG_DOMAINS : LENS_ORDER;
  const groups = order.map(k => ({ key: k,
    items: visible.filter(s => (groupBy === "domain" ? s.domain : s.lens) === k).sort((a, b) => rank(a) - rank(b)) }))
    .filter(g => g.items.length);

  const Row = (s) => { const sid = s.sig_id || s.question_id; const pt = posTag(s); return html`
    <div key=${sid} class=${"signal-row sig-row-axis sig-tone-" + pt.tone + (s.status === "dismissed" ? " is-dismissed" : "") + (s.new ? " is-new" : "") + (s.risk_framed ? " is-risk" : "") + (s.confirm ? " is-confirm" : "")} role="button" tabindex="0"
      onClick=${() => openMetric(s.question_id)}
      onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openMetric(s.question_id); } }}>
      <span class="signal-body">
        <b class="sig-name">${s.new ? html`<span class="sig-new-tag">NEW</span> ` : null}${s.name || s.label_short}${s.risk_framed ? html` <span class="sig-risk"><${Icon} name="shield" size=${11} /> Risk</span>` : null}${s.confirm ? html` <span class="sig-onplan"><${Icon} name="check" size=${11} /> On plan</span>` : null}</b>
        <span class="sig-stand">${s.stand || s.detail}${provMark(s)}${pt.hint ? html`<span class="sig-hint"> · ${pt.hint}</span>` : null}${s.strategy_note ? html`<span class="sig-strat-note"> · ${s.strategy_note}</span>` : null}</span></span>
      <span class=${"pos-tag pos-" + pt.tone}>${pt.text}</span>
      <${SignalActions} status=${s.status} sid=${sid} onSet=${setStatus} />
    </div>`; };

  return html`
    <div class="signals-page" style=${{ maxWidth: "880px" }}>
      <div class="ov-aurora" aria-hidden="true"></div>
      <h1 class="display-title" style=${{ marginBottom: "var(--s1)" }}>Signals</h1>
      ${unlocked ? html`<p style=${{ maxWidth: "680px", marginTop: 0 }}>Your organisation's signals — grounded in your peer data, never advice. Each shows where you sit against the market, or a practice most peers have that you don't; <b>we flag, you decide</b> whether it matters. Prioritise, save or dismiss to triage what's worth your attention.</p>` : null}
      ${unlocked && data.strategy_complete ? html`<${StrategyCheck} onGoToDomain=${goToDomain} signalDomains=${signalDomains} />` : null}
      ${!unlocked ? html`<${SignalsLocked} contrib=${contrib} me=${me} />` : html`
        <div class="sig-tabs">
          ${SIG_TABS.map(t => html`<button key=${t.k} class=${"sig-tab" + (tab === t.k ? " on" : "")} onClick=${() => setTab(t.k)}>
            <${Icon} name=${t.icon} size=${14} /> ${t.label} <span class="num">${counts[t.k]}</span></button>`)}
        </div>
        ${triaged.length === 0 ? html`
          <div class="signals-empty" style=${{ marginTop: "var(--s5)" }}>
            <span class="signals-empty-ring"><${Icon} name=${cur.icon} size=${18} /></span>
            <div class="caption" style=${{ maxWidth: "360px" }}>${
              tab === "inbox" ? "Inbox zero — every signal triaged, or nothing crosses a threshold yet."
              : tab === "dismissed" ? "Nothing dismissed. Tip: dismiss a signal to clear it from your inbox and the home briefing."
              : "Nothing " + cur.label.toLowerCase() + " yet — use the " + (tab === "priority" ? "pin" : "star") + " on any signal to " + (tab === "priority" ? "prioritise" : "save") + " it."}</div>
          </div>` : html`
        <div class="sig-summary card">
          <div class="sig-summary-top">
            <span class="num"><b>${visible.length}</b> signal${visible.length === 1 ? "" : "s"}${effPos === "all" ? "" : " · " + (POS_TAG_TEXT[effPos] || effPos)}</span>
            ${data.strategy_objective && html`<span class="sig-strat-order" title="Each area is ordered for your stance — pins stay on top. Set in your reward strategy.">
              <${Icon} name="compass" size=${12} /> ordered for your <b>${data.strategy_objective}</b> strategy${data.strategy_can_edit ? html` · <a onClick=${(e) => { e.preventDefault(); nav("/strategy"); }} href="#/strategy">edit</a>` : null}</span>`}
          </div>
          <div class="sig-bar" role="img" aria-label="Signals by market position">
            ${SIG_POSITIONS.filter(p => posCounts[p.k]).map(p => html`<span key=${p.k} class=${effPos === "all" || effPos === p.k ? "" : "dim"} style=${{ flex: posCounts[p.k], background: posColor(p.k) }}></span>`)}
          </div>
          <div class="sig-controls">
            <div class="sig-chips">
              <button class=${"sig-chip" + (effPos === "all" ? " on" : "")} aria-pressed=${effPos === "all"} onClick=${() => setPosF("all")}>All <span class="n">${triaged.length}</span></button>
              ${SIG_POSITIONS.filter(p => posCounts[p.k]).map(p => html`
                <button key=${p.k} class=${"sig-chip" + (effPos === p.k ? " on" : "")} aria-pressed=${effPos === p.k} onClick=${() => setPosF(effPos === p.k ? "all" : p.k)}>
                  <span class="sig-chip-dot" style=${{ background: posColor(p.k) }}></span>${p.label} <span class="n">${posCounts[p.k]}</span></button>`)}
            </div>
            ${(provCount || riskCount) ? html`<div class="sig-filters" role="group" aria-label="Show only">
              <span class="sig-filters-lbl">show only</span>
              ${provCount ? html`<button class=${"sig-fchip" + (provF ? " on" : "")} aria-pressed=${provF} onClick=${() => setProvF(v => !v)} title="Show only verdicts backed by a verified, published source (the rest are estimate-flagged or unsourced).">verified source <span class="n">${provCount}</span></button>` : null}
              ${riskCount ? html`<button class=${"sig-fchip sig-fchip-risk" + (riskF ? " on" : "")} aria-pressed=${riskF} onClick=${() => setRiskF(v => !v)} title="Show only duty-of-care risk signals (statutory / floor exposures)."><${Icon} name="shield" size=${11} /> risk <span class="n">${riskCount}</span></button>` : null}
            </div>` : null}
            <div class="sig-groupby">group by
              <div class="seg" role="group" aria-label="Group by">
                <button class=${groupBy === "domain" ? "on" : ""} aria-pressed=${groupBy === "domain"} onClick=${() => setGroupBy("domain")}>domain</button>
                <button class=${groupBy === "lens" ? "on" : ""} aria-pressed=${groupBy === "lens"} onClick=${() => setGroupBy("lens")}>lens</button>
              </div>
            </div>
          </div>
        </div>
        ${groups.length === 0 ? html`<div class="signals-empty" style=${{ marginTop: "var(--s4)" }}><div class="caption">No signals match this view${(provF || riskF || effPos !== "all") ? " — clear a filter to see more" : ""}.</div></div>` :
        groups.map(g => html`
          <section key=${g.key} id=${groupBy === "domain" ? "sig-dom-" + g.key : null} class="sig-group">
            <div class="sig-grouphead">
              ${groupBy === "lens" ? html`<span class=${"signal-roundel lens-" + g.key}><${Icon} name=${LENS_ICON[g.key]} size=${14} /></span>` : html`<span class="sig-grouphead-icon"><${Icon} name=${CAT_ICON[g.key] || "award"} size=${15} /></span>`}
              <b class="gname">${groupBy === "domain" ? g.key : LENS_LABEL[g.key]}</b>
              <span class="gmeta">${groupBy === "lens" ? LENS_DESC[g.key] + " · " : ""}${g.items.length}</span>
            </div>
            <div class="signals-list">${g.items.map(Row)}</div>
          </section>`)}`}
        <div class="sig-register-foot">
          <${Icon} name="table" size=${15} />
          <div>
            <b>Want the complete picture?</b> Signals shows only the signals that cross a threshold.
            The <a href="#/priorities">full gap register</a> lists every metric's presence against the market.
            ${me.user.role === "admin" ? html` <a href="/api/gap-register.csv" download>Download CSV</a>.` : null}
          </div>
        </div>`}
    </div>`;
};

function CategoryTile({ d, pending, aim, view }) {
  const post = d.position || d.market;
  const noRate = d.competitiveness === false;
  const prev = d.prevalence || {};
  const ap = pending ? null : d.approach;

  // PRACTICE LENS (the dashboard "Practice" view): every card shows its approach read —
  // how many of this area's practices differ from the market norm (a count, never a
  // verdict). The market bar/verdict is hidden; the two concepts never share the card.
  if (view === "practice") {
    const pool = ap && ap.pool, differ = ap && ap.differ;
    const fr = pool ? Math.round(1000 * differ / pool) / 10 : 0;
    return html`
      <div class="card cat-tile cat-tile-practice" onClick=${() => nav("/category/" + encodeURIComponent(d.name))} onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nav("/category/" + encodeURIComponent(d.name)); } }} role="button" tabindex="0">
        <span style=${{ display: "inline-flex", alignItems: "center", gap: "var(--s2)", fontWeight: 600, fontSize: "var(--fs-label)" }}>
          <span class="cat-icon"><${Icon} name=${CAT_ICON[d.name] || "award"} size=${14} /></span>${d.name}</span>
        ${pending ? html`<div class="caption num" style=${{ marginTop: "var(--s2)" }}>Appears once unlocked</div>`
          : (pool ? html`
            <div class="cat-axis num">differ</div>
            <div class="catp-bar" title="How many of this area's practices differ from the market norm — a different way of doing things, not a gap."
              role="img" aria-label=${differ + " of " + pool + " practices differ from the market norm."}>
              <div class="catp-bar-fill" style=${{ width: fr + "%" }}></div></div>
            <div class="cat-differ num"><span class="cat-differ-dot"></span><span class="cat-differ-txt"><b>${differ}</b> of ${pool} differ</span></div>`
          : html`<div class="caption num" style=${{ marginTop: "var(--s2)" }}>${prev.pool || 0} practices tracked</div>`)}
      </div>`;
  }

  // MARKET LENS (default): the verdict chip + proportional below/on/above bar with the
  // per-domain lean needle. The practice differ line now lives in the Practice view.
  // Data-pending: a per-category verdict on ~1% of data isn't credible — neutral fallback.
  const verdict = pending ? null : (post ? post.verdict : null);
  const ev = d.position_evidence;
  const indicative = pending ? false : (d.position_basis === "indicative");
  const evCount = ev ? ev.polarised + ev.practice : 0;
  const evNote = ev ? ("based on " + evCount + " positioned metric" + (evCount === 1 ? "" : "s") +
    (indicative ? " — indicative, not a full market verdict" : "")) : "";
  // PASS 2 (RAG/strategy separation, 2026-06-27) — tile chip / top-border / bar colour by
  // POSITION, not attainment: tone = marketTone(verdict) (below=amber / on=green / above=red),
  // strategy-INVARIANT. Was ATTAIN_ALIGN[d.target.alignment] / attainTone(verdict, aim) — the
  // org's aim recolouring the position. The alignment relationship now rides the compact navy
  // AlignmentChip in the header (strategy-on only); strategy never enters the tile hue, so
  // strategy-off and strategy-on render the SAME per-tile colour (on==off parity). The chip
  // TEXT stays the direction word (below / on market / above); no verdict (practice / no market
  // rate) → practice tint. R3: an above-market tile now reaches marketTone "red" → the v-above
  // border + chip-bad, previously unreachable under the attainment lens (which only emitted
  // green/amber/grey). (v-above-over / "redover" stays retired — it was a strategy-overshoot
  // concept with no meaning in the pure position lens.)
  const tone = verdict ? marketTone(verdict) : null;
  const chip = verdict === "below" ? "below" : verdict === "above" ? "above" : verdict ? "on market" : noRate ? "no market rate" : "practice view";
  const chipCls = tone ? MKT_CHIP[tone] : "chip-practice";
  const vCls = tone ? MKT_VCLS[tone] : "v-practice";
  const positioned = !pending && post && post.pool > 0;
  const vKey = verdict === "below" ? "below" : verdict === "above" ? "above" : "on";
  const segs = positioned ? [{ k: "below", n: post.below }, { k: "on", n: post.at }, { k: "above", n: post.above }] : [];
  let markFrac = 0.5;
  if (positioned) {
    const T = post.lean_threshold || 0.25, lz = Math.max(-1, Math.min(1, post.lean || 0));
    const b1 = post.below / post.pool, b2 = (post.below + post.at) / post.pool;
    const lp = (a, z, t) => a + (z - a) * Math.max(0, Math.min(1, t));
    markFrac = verdict === "above" ? lp(b2, 1, (lz - T) / (1 - T))
             : verdict === "below" ? lp(0, b1, (lz + 1) / (1 - T))
             : lp(b1, b2, (lz + T) / (2 * T));
    markFrac = Math.max(0.025, Math.min(0.975, markFrac));
  }
  return html`
    <div class=${"card cat-tile " + vCls + (noRate ? " cat-tile-norate" : "")} onClick=${() => nav("/category/" + encodeURIComponent(d.name))} onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nav("/category/" + encodeURIComponent(d.name)); } }} role="button" tabindex="0">
      <span style=${{ display: "inline-flex", alignItems: "center", gap: "var(--s2)", fontWeight: 600, fontSize: "var(--fs-label)" }}>
        <span class="cat-icon"><${Icon} name=${CAT_ICON[d.name] || "award"} size=${14} /></span>${d.name}</span>
      <span class="row" style=${{ gap: "var(--s1)", alignSelf: "flex-start", alignItems: "center" }}>
        <span class=${"chip tile-chip " + chipCls + (indicative ? " chip-indicative" : "")} title=${evNote}>${chip}</span>
        ${indicative && html`<span class="indic-flag" tabindex="0" role="note"><${Icon} name="info" size=${11} /> indicative<span class="indic-tip">Verdict shown with limited comparable data — treat as a directional read.</span></span>`}
      </span>
      ${positioned ? html`
        <div class="cat-axis num">position</div>
        <div class=${"cat-pos" + (indicative ? " cat-pos-indic" : "")}>
          <div class="cat-bar" title=${evNote} role="img"
            aria-label=${post.below + " below, " + post.at + " on market, " + post.above + " above. " + evNote}>
            <div class="cat-bar-track">
              ${segs.map(s => { const st = tone;   /* FIX 1: whole bar = one attainment hue (per-domain via d.target); the marker carries direction */
                return html`<div key=${s.k} class="cat-bar-seg"
                  style=${{ width: (100 * s.n / post.pool).toFixed(2) + "%", background: s.k === vKey ? MKT_RICH[st] : MKT_SOFT[st] }}></div>`; })}
            </div>
            <div class="cat-bar-mark" style=${{ left: (markFrac * 100).toFixed(1) + "%" }}><i></i></div>
          </div>
        </div>` : noRate ? html`
        <div class="cat-na num" style=${{ marginTop: "var(--s2)" }}
          title="No market rate to be under or over — these are approach choices, not a market position.">N/A</div>` : html`
        <div class="tile-band" style=${{ margin: "2px 0 0" }}>
          <div class="tile-fill" style=${{ width: (prev.pool ? Math.round(100 * prev.with_majority / prev.pool) : 0) + "%" }}></div>
        </div>
        ${prev.with_majority != null && html`<div class="caption num" title="practices in line with the market majority">${prev.with_majority}/${prev.pool} in line with the market</div>`}`}
      ${/* PASS (tile alignment label): a quiet STRATEGY row beneath the POSITION bar, mirroring
            its "POSITION" label (same .cat-axis) so the abbreviated state word reads against it
            ("STRATEGY: Behind/On/Ahead"). Position primary (the fixed fact), alignment secondary
            (the strategy overlay) — primary-then-secondary, matching the gauge. Both label + chip
            gate on d.target → hide together strategy-off (no orphan label). */ ""}
      ${d.target ? html`
        <div class="cat-axis num">strategy</div>
        <div class="cat-tile-align"><${AlignmentChip} target=${d.target} compact=${true} /></div>` : null}
    </div>`;
}



function jumpToItem(item) { if (item) openMetric(item.question_id); }

window.OpportunityTile = function ({ opp, contrib, actionGaps }) {
  if (!opp) return null;
  if (opp.locked) return html`
    <div class="opp-hero insight-lock">
      <div class="eyebrow">Total identified opportunity</div>
      <div class="blurred" aria-hidden="true">
        <div class="metric-value lg" style=${{ color: "var(--blue)" }}>£———<span class="unit">/yr</span></div>
        <div class="caption">what closing your gaps to the market median is worth</div>
        <div class="opp-row"><span>Largest opportunity</span><b>£——/yr</b></div>
        <div class="opp-row"><span>Second opportunity</span><b>£——/yr</b></div>
      </div>
      <div class="lock-note">
        <${Chip} kind="accent"><${Icon} name="lock" size=${11} /> Locked<//>
        <div class="caption" style=${{ textAlign: "center", maxWidth: "240px" }}>
          ${opp.item_count ? `${opp.item_count} £-sized opportunities are waiting. ` : ""}Unlock by completing your key reward questions${opp.days_left != null ? ` — ${opp.days_left} days left` : ""}.</div>
        <button class="btn small primary" onClick=${() => nav("/your-data/submit")}>Submit data</button>
      </div>
    </div>`;
  const total = opp.total_savings_to_p50_gbp > 0 ? opp.total_savings_to_p50_gbp : opp.total_investment_to_p50_gbp;
  return html`
    <div class="opp-hero">
      <div class="eyebrow">Total identified opportunity</div>
      ${opp.fte_known ? html`
        <div>
          <div class="metric-value lg" style=${{ color: "var(--blue)" }}>${fmtGBPCompact(total)}<span class="unit">/yr</span></div>
          <div class="caption">${opp.total_savings_to_p50_gbp > 0 ?
            html`potential savings if you matched the market median${opp.total_investment_to_p50_gbp ? html` — plus ${fmtGBPCompact(opp.total_investment_to_p50_gbp)}/yr to close benefit gaps` : ""}` :
            opp.total_investment_to_p50_gbp > 0 ? "what it would take to close your benefit gaps to the market median" : "no gaps to the market median identified"}</div>
        </div>
        <div style=${{ marginTop: "var(--s2)" }}>
          ${opp.items.map(i => html`
            <div key=${i.question_id}>
              <div class="opp-row">
                <a href=${"#/metric/" + i.question_id}>${i.label}</a>
                <b>${fmtGBPCompact(i.to_p50_gbp)}/yr <span class="caption" style=${{ fontWeight: 400 }}>${i.direction === "saving" ? "saving" : "to close"}</span></b>
              </div>
              ${i.to_p75_gbp > i.to_p50_gbp && html`
                <div class="opp-row" style=${{ borderBottom: 0, paddingTop: 0 }}>
                  <span class="caption">…or match the upper quartile</span>
                  <span class="caption num">${fmtGBPCompact(i.to_p75_gbp)}/yr</span>
                </div>`}
              ${(i.rows || []).filter(r => r.p50 != null && r.your_value < r.p50).slice(0, 3).map(r => html`
                <div key=${r.row_id} class="opp-row" style=${{ borderBottom: 0, paddingTop: 0 }}>
                  <span class="caption">${r.label}</span>
                  <span class="caption num">you ${r.your_value}% · peers ${Math.round(r.p50 * 10) / 10}%</span>
                </div>`)}
            </div>`)}
        </div>
        <div class="caption" style=${{ marginTop: "auto" }}><${Term} word="indicative">Indicative<//> — based on assumptions you can change in <a href="#/settings">Settings</a>.</div>
        ${actionGaps > 0 && html`<div class="caption" style=${{ marginTop: "var(--s2)", paddingTop: "var(--s2)", borderTop: "1px solid var(--border)" }}>
          Plus <a href="#/priorities"><b class="num">${actionGaps}</b> practice gaps</a> where most peers do something you don't — the non-£ to-do list.</div>`}` :
      html`<div class="caption" style=${{ marginTop: "var(--s2)" }}>Declare your FTE band in <a href="#/your-data/submit">your submission</a> to size the £ opportunity of closing gaps to the market median.</div>`}
    </div>`;
};

window.TrajectoryTile = function ({ movement }) {
  return html`
    <div style=${{ flex: "1 1 190px", minWidth: "190px", borderLeft: "1px solid var(--border)", paddingLeft: "var(--s5)", display: "flex", flexDirection: "column" }}>
      <div class="caption" style=${{ fontWeight: 650, textTransform: "uppercase", letterSpacing: ".06em" }}>Your journey</div>
      <svg viewBox="0 0 170 44" style=${{ width: "170px", display: "block", margin: "var(--s3) 0 var(--s2)" }}>
        <polyline points="4,30 40,30" stroke="var(--blue)" stroke-width="2.5" fill="none" stroke-linecap="round"/>
        <circle cx="40" cy="30" r="5" fill="var(--blue)"/>
        <circle cx="40" cy="30" r="9" fill="none" stroke="var(--blue-tint-2)" stroke-width="2"/>
        <polyline points="40,30 80,24 120,20 160,12" stroke="var(--blue-tint-2)" stroke-width="2" stroke-dasharray="3 4" fill="none"/>
        <circle cx="160" cy="12" r="3.5" fill="none" stroke="var(--blue-tint-2)" stroke-width="1.5"/>
      </svg>
      <div class="caption" style=${{ color: "var(--ink-soft)" }}><b style=${{ color: "var(--blue)" }}>This is your baseline.</b>${" "}
        From your next cycle you'll see exactly where you've moved — every card grows a "vs last time" story.</div>
    </div>`;
};

// ----------------------------------------------------- superpower detail ---// ----------------------------------------------------- superpower detail ---
window.SuperpowerPage = function ({ sp, cut, cuts, prefs, onPref, onPin, pinnedIds, me, focusQ, subF }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [sigMap, setSigMap] = useState({});
  const ui = (prefs && prefs._ui_section) || {};
  const [cat, setCatRaw] = useState(ui.cat || "");
  const [sigF, setSigF] = useState("");
  const setCat = v => { setCatRaw(v); onPref && onPref("_ui_section", { ...ui, cat: v }); };

  useEffect(() => {
    setData(null); setErr(null);
    api(`/api/benchmarks/${encodeURIComponent(sp)}?` + cutQS(cut)).then(setData).catch(e => setErr(e.message));
    // signals come from the same computed data the home/category pages use; one
    // fetch per page builds the qid -> signal map for every card's status pill
    api("/api/overview?" + cutQS(cut)).then(o => {
      const m = {}; (o.signals_all || []).forEach(s => { (m[s.question_id] = m[s.question_id] || []).push(s); }); setSigMap(m);
    }).catch(() => setSigMap({}));
  }, [sp, cutKeyOf(cut)]);
  useEffect(() => {
    if (data && focusQ) {
      const el = document.getElementById("q-" + focusQ);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [data, focusQ]);
  if (err) return html`<${EmptyState} title="Couldn't load this section"
    body=${err + " — nothing is lost; it usually works on a retry."}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!data) return html`
    <div>
      <div class="page-head">
        <div class="titleblock">
          <div class="sp-glyph"><${SpIcon} sp=${sp} size=${20} /></div>
          <div><h1 class="display-title">${sp}</h1><div class="caption meta">Loading benchmarks…</div></div>
        </div>
      </div>
      <${SkeletonGrid} count=${6} />
    </div>`;
  let cards = data.cards;
  if (subF) cards = cards.filter(c => (c.subpower || "General") === subF);
  if (cat) cards = cards.filter(c => c.category === cat);
  const sigCounts = { signal: 0, add: 0, clear: 0 };
  cards.forEach(c => { const st = cardSignalState(c, sigMap[c.id]); if (st) sigCounts[st]++; });
  if (sigF) cards = cards.filter(c => cardSignalState(c, sigMap[c.id]) === sigF);

  const bySub = [];
  for (const c of cards) {
    let g = bySub.find(g => g.sub === (c.subpower || "General"));
    if (!g) { g = { sub: c.subpower || "General", order: c.sub_power_order || 999, cards: [] }; bySub.push(g); }
    g.cards.push(c);
  }
  bySub.sort((a, b) => a.order - b.order);
  return html`
    <div>
      <div class="page-head">
        <div class="titleblock">
          <div class="sp-glyph"><${SpIcon} sp=${sp} size=${20} /></div>
          <div>
            <h1 class="display-title">${subF || (window.SCOPE && window.SCOPE.focused ? "All reward" : sp)}</h1>
            <div class="caption meta">${cards.length} benchmarks${subF && window.SCOPE && window.SCOPE.focused ? " · part of your reward benchmark" : ""} · peer group: ${cutLabelOf(cut, cuts)}${me && me.peer_pool && me.peer_pool.collection_window ? ` · benchmark data: ${me.peer_pool.collection_window}` : (me && me.snapshots && me.snapshots[0] ? ` · benchmark data: ${me.snapshots[0].collection_window}` : "")}</div>
          </div>
        </div>
        <div class="controls" style=${{ alignItems: "flex-start" }}>
          <div class="ctlgroup">
            <select class="ctl" aria-label="Filter by question type" value=${cat} onChange=${e => setCat(e.target.value)}>
              <option value="">All question types</option>
              <option value="metric">Metrics</option><option value="practice">Practices</option>
              <option value="policy">Policies</option><option value="benefit">Benefits</option>
            </select>
            <div class="hint">Show only one kind of question.</div>
          </div>
          <div class="ctlgroup">
            <select class="ctl" aria-label="Filter by signal" value=${sigF} onChange=${e => setSigF(e.target.value)}>
              <option value="">All signals</option>
              <option value="signal">Flagged · ${sigCounts.signal}</option>
              <option value="add">Needs data · ${sigCounts.add}</option>
              <option value="clear">No signal · ${sigCounts.clear}</option>
            </select>
            <div class="hint">Flagged, needs data, or no signal.</div>
          </div>
        </div>
      </div>
      ${cards.length === 0 && html`<${EmptyState} title="Nothing matches these filters"
        body="Try clearing the filters." action=${html`<button class="btn small" onClick=${() => { setCat(""); setSigF(""); }}>Clear filters</button>`} />`}
      ${bySub.map(g => html`
        <div key=${g.sub} style=${{ marginBottom: "var(--s5)" }}>
          ${!subF && html`<h2 class="section-title">${g.sub}</h2>`}
          <div class="bench-grid">
            ${g.cards.map(c => html`
              <div key=${c.id} id=${"q-" + c.id}>
                <${BenchmarkCard} card=${c} prefs=${prefs} onPref=${onPref} onPin=${onPin}
                  pinned=${pinnedIds.has(c.id)} cuts=${cuts} globalCut=${cutKeyOf(cut)} signal=${sigMap[c.id]}
                  window=${me.peer_pool && me.peer_pool.collection_window} highlight=${focusQ === c.id} />
              </div>`)}
          </div>
        </div>`)}
    </div>`;
};

// A part-to-whole donut for practice prevalence: the three buckets (match the
// majority / a common alternative / a rarer choice) partition the assessed pool.
// Neutral blue tones, NOT the performance palette — prevalence informs, it doesn't
// judge. Centre holds the headline count; the legend names each slice.
function prevDonut(prev) {
  const segs = [
    { k: "majority", v: prev.with_majority || 0, c: "var(--blue-deep)", label: "match the market majority" },
    { k: "common", v: prev.established || 0, c: "color-mix(in srgb, var(--blue) 46%, var(--surface-sunk))", label: "a common alternative" },
    { k: "rare", v: prev.less_common || 0, c: "color-mix(in srgb, var(--blue) 16%, var(--surface-sunk))", label: "a rarer choice" },
  ].filter(s => s.v > 0);
  const total = prev.pool, r = 54, C = 2 * Math.PI * r;
  let acc = 0;
  const arcs = segs.map(s => {
    const len = (s.v / total) * C, off = -acc; acc += len;
    return html`<circle key=${s.k} cx="70" cy="70" r=${r} fill="none" stroke=${s.c} stroke-width="15"
      stroke-dasharray=${len + " " + (C - len)} stroke-dashoffset=${off} transform="rotate(-90 70 70)" />`;
  });
  return html`
    <div class="cat-prev-wrap">
      <div class="cat-donut" role="img"
        aria-label=${prev.with_majority + " of " + total + " practices match the market majority"}>
        <svg viewBox="0 0 140 140" aria-hidden="true">
          <circle cx="70" cy="70" r=${r} fill="none" stroke="var(--surface-sunk)" stroke-width="15" />
          ${arcs}
        </svg>
        <div class="cat-donut-center"><b>${prev.with_majority}</b><span>of ${total}</span></div>
      </div>
      <div class="cat-prev-legend">
        ${segs.map(s => html`
          <div key=${s.k} class="cat-leg-row">
            <span class="cat-leg-dot" style=${{ background: s.c }}></span>
            <b>${s.v}</b><span>${s.label}</span>
          </div>`)}
      </div>
    </div>`;
}

// -------------------------------------------------- category detail --------
/* The dedicated expanded view for one sub-domain (Pay, Benefits, …). It mirrors
   and explains the overview tile: a market-position read + practice-prevalence
   split at the top, then THIS category's signals, then every metric in it.
   Flags never advise — the user decides whether a difference is good or bad. */
// §2 (domain-page Pass 3b): the AI domain summary — a describe-only "mirror" of the org's
// position across this domain's metrics. Auto-fetches on mount + on cut/strategy change (lazy,
// no button); always present once me.features.domain_summary is on — the server ships a
// validated deterministic FLOOR when the model is down, so the block never disappears on infra.
// Four describe-only slots (position / notable / prevalence-or-approach / provenance) rendered
// as-is: NO client editorialising, no recommendations, no actions. It describes and stops.
function DomainSummary({ name, cut, applyStrat }) {
  const [st, setSt] = useState({ phase: "loading" });
  useEffect(() => {
    let live = true;
    setSt({ phase: "loading" });
    api("/api/domain-summary", { method: "POST",
        body: { domain: name, cut: cut.dim, cut_value: cut.value, apply_strategy: applyStrat } })
      .then(r => { if (live) setSt({ phase: "done", parts: r.parts || {}, source: r.source, caveats: r.caveats || {} }); })
      .catch(e => { if (live) setSt({ phase: "error", error: e.message }); });
    return () => { live = false; };
  }, [name, cutKeyOf(cut), applyStrat]);
  const f = st.parts || {};
  const SLOTS = [["position", "Market position"], ["notable", "Notable metrics"], ["prevalence", "Practices"]];
  return html`
    <section class="cat-section cat-summary">
      <div class="cat-sec-head"><span class="cat-sec-ico cat-sum-ico"><${Icon} name="sparkle" size=${14} /></span>
        <b>How your ${name} reads</b>
        <span class="cat-ai-tag">AI-generated · a description of your data, not advice</span></div>
      ${st.phase === "loading" ? html`
        <div class="cat-summary-body">${[0, 1, 2].map(i => html`<div key=${i} class="cat-sum-skel"></div>`)}</div>` :
        st.phase === "error" ? html`
        <div class="cat-summary-body"><p class="caption">Couldn't load this summary — ${st.error}.</p></div>` :
        html`
        <div class="cat-summary-body">
          ${SLOTS.map(([k, label]) => f[k] ? html`
            <div key=${k} class="cat-sum-part">
              <div class="cat-sum-label">${label}</div>
              <p class="cat-sum-text">${f[k]}</p>
            </div>` : null)}
          ${f.provenance ? html`<div class="cat-sum-prov">${f.provenance}</div>` : null}
          ${st.source === "deterministic" ? html`
            <div class="cat-sum-caveat">A plain-data summary, written from your figures.</div>` : null}
        </div>`}
    </section>`;
}

window.CategoryPage = function ({ name, cut, cuts, prefs, onPref, onPin, pinnedIds, me }) {
  const [ov, setOv] = useState(null);
  const [bench, setBench] = useState(null);
  const [err, setErr] = useState(null);
  const [type, setType] = useState("");
  const [posSel, setPosSel] = useState([]);     // market-position chip filter (multi-select; [] = all)
  // PART B (2026-06-24) — honour the overview's strategy-off toggle so the attainment lens
  // stays consistent across surfaces: when the user has turned their strategy OFF on the
  // overview (persisted pref _overview.apply_strategy === false), fetch this category with
  // &strategy=off too, so market.target comes back null → aim null → attainTone yields the
  // grey "no judgement" hue here as well (no separate flag; same source of truth, same param
  // as the overview at line ~45). Real-aim by default.
  const _ovp = (prefs && prefs._overview) || {};
  const applyStrat = _ovp.apply_strategy !== false;
  useEffect(() => {
    setOv(null); setBench(null); setErr(null); setType(""); setPosSel([]);
    Promise.all([
      api("/api/overview?" + cutQS(cut) + (applyStrat ? "" : "&strategy=off")),
      api("/api/benchmarks/Reward?" + cutQS(cut)),
    ]).then(([o, b]) => { setOv(o); setBench(b); }).catch(e => setErr(e.message));
  }, [name, cutKeyOf(cut), applyStrat]);

  const Head = (meta) => html`
    <div class="page-head">
      <div class="titleblock">
        <a class="caption back-link" href="#/overview"><${Icon} name="chevron-left" size=${13} /> Overview</a>
        <div class="row" style=${{ gap: "var(--s3)", alignItems: "center" }}>
          <div class="cat-glyph"><${Icon} name=${CAT_ICON[name] || "award"} size=${20} /></div>
          <div><h1 class="display-title">${name}</h1><div class="caption meta">${meta}</div></div>
        </div>
      </div>
    </div>`;

  if (err) return html`<${EmptyState} title="Couldn't load this category"
    body=${err + " — nothing is lost; it usually works on a retry."}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!ov || !bench) return html`<div>${Head("Loading…")}<${SkeletonGrid} count=${4} /></div>`;

  const hero = ((ov.hero && ov.hero.domains) || []).find(d => d.name === name);
  const all = (bench.cards || []).filter(c => (c.subpower || "General") === name);
  const sigMap = {}; (ov.signals_all || []).forEach(s => { (sigMap[s.question_id] = sigMap[s.question_id] || []).push(s); });
  const sigCounts = { signal: 0, add: 0, clear: 0 };
  all.forEach(c => { const st = cardSignalState(c, sigMap[c.id]); if (st) sigCounts[st]++; });
  // §2 grid filter: TYPE (kept) + market-POSITION chips (multi-select; [] = all). cardBand reads
  // the server's firewall-reviewed c.market_band (Pass 2a — the SAME _metric_bands the §1 donut
  // counts), mapping the engine's 'at' to the chip's 'on'. count===donut===filtered-grid BY
  // CONSTRUCTION (one source, metric-level). null (Approach / neutral / non-positioned) matches
  // no chip. Strategy-invariant (market_band is strategy-free).
  const cardBand = c => { const b = c.market_band; return b === "at" ? "on" : b; };
  let cards = type ? all.filter(c => c.category === type) : all;
  if (posSel.length) cards = cards.filter(c => posSel.includes(cardBand(c)));

  // position read (same traffic-light language as the tile / hero gauge)
  const pos = hero && (hero.position || hero.market);
  const verdict = pos && pos.verdict;
  // §1 CARD A counts DISTINCT positioned METRICS (matrix metric = its own verdict) — the unit
  // the grid + position chips share — NOT the per-reading mass the home needle keeps (ruling
  // 2026-06-27). Donut segments/counts/pool read posM; the verdict WORD + lean adverb stay
  // mass-level (the canonical domain read, consistent with tile/chip/home). Falls back to mass
  // if an older payload lacks position_metrics.
  const posM = (hero && hero.position_metrics) || pos;
  const indicative = hero && hero.position_basis === "indicative";
  const ev = hero && hero.position_evidence;
  const evC = ev ? ev.polarised + ev.practice : 0;
  // PASS 4 (RAG/strategy separation, 2026-06-27): the category-detail hero chip colours by
  // POSITION, not attainment — tone = marketTone(verdict) (below=amber / on=green / above=red),
  // strategy-INVARIANT. Was ATTAIN_ALIGN[hero.target.alignment] / attainTone(verdict, aim). The
  // alignment relationship now rides the navy AlignmentChip beside the verdict chip (strategy-on
  // only); strategy never enters the hero hue → strategy-off and strategy-on render the SAME chip
  // colour (on==off parity). aim is still read for the MarketSpectrum's spatial aim bracket.
  const aim = marketAim(ov.hero && ov.hero.market);
  const tone = verdict ? marketTone(verdict) : null;
  const chip = verdict === "below" ? "below" : verdict === "above" ? "above" : verdict ? "on market" : "practice view";
  const chipCls = tone ? MKT_CHIP[tone] : "chip-practice";
  const prev = (hero && hero.prevalence) || {};
  const dot = hero && hero.dot;
  // counts-reconciliation (2026-06-28): the <20 thin-cut caveat must reach the DOMAIN page too —
  // otherwise the "small sample · directional" qualifier lives only on the overview hero, and a
  // user reading §1/§2/grid at n=15 sees no warning. Same window [5, 20) + insights-unlocked gate.
  const sampleN = cutSize(cut, cuts, me.peer_pool);
  const thinSample = !!(ov.contribution && ov.contribution.insights_unlocked) && sampleN != null && sampleN >= 5 && sampleN < 20;
  // §1 (domain-page Pass 1, 2026-06-27): two RAG donuts via the shared <Donut>. CARD A (position)
  // — per-band marketTone segments + a verdict-WORD centre (verdictWord/leanCaption, the SAME
  // helpers as the home gauge). CARD B (prevalence) — its OWN blue palette (NOT marketTone:
  // practice is not a market position), a count-HEADLINE centre, no alignment chip.
  const posSegs = posM ? ["below", "at", "above"].map(k => ({ value: posM[k] || 0, color: (verdict === k ? MKT_RICH : MKT_SOFT)[marketTone(k)] })) : [];
  const prevSegs = [
    { value: prev.with_majority || 0, color: "var(--blue-deep)" },
    { value: prev.established || 0, color: "color-mix(in srgb, var(--blue) 46%, var(--surface-sunk))" },
    { value: prev.less_common || 0, color: "color-mix(in srgb, var(--blue) 16%, var(--surface-sunk))" },
  ];

  return html`
    <div class="category-page">
      ${Head(`${all.length} benchmark${all.length === 1 ? "" : "s"} · peer group: ${cutLabelOf(cut, cuts)}`)}

      ${thinSample ? html`
        <div class="cat-thin-caveat">
          <span class="indic-flag" tabindex="0" role="note">
            <${Icon} name="info" size=${11} /> Small sample · ${sampleN} peers
            <span class="indic-tip">This domain is compared against ${sampleN} organisations — treat the reads here as directional.</span>
          </span>
        </div>` : null}

      ${ov.strategy_complete ? html`
        <div class="cat-strat-bar">
          <button type="button" class=${"ov-strat" + (applyStrat ? " on" : "")} role="switch" aria-checked=${applyStrat}
            onClick=${() => onPref && onPref("_overview", { ..._ovp, apply_strategy: !applyStrat })}
            title=${applyStrat
              ? "Reading against your reward strategy — the alignment chip shows how this domain tracks your aim. Click for the absolute market view."
              : "Showing the absolute market view (no stance applied). Click to read against your reward strategy."}>
            <span class="ov-strat-track"><span class="ov-strat-knob"></span></span>
            <span class="ov-strat-lbl">${applyStrat ? "Strategy applied" : "Strategy off"}</span>
          </button>
        </div>` : null}
      <div class="cat-hero">
        <div class="card cat-pos-card">
          <div class="cat-hero-label">Market position</div>
          ${posM && posM.pool ? html`
            <${Donut} segments=${posSegs} total=${posM.pool} centerNum=${posM.pool} sub="metrics" centerWord=${verdictWord(verdict)} size=${210} stroke=${28} />
            <div class="cat-card-cap">${leanCaption(pos)}${indicative ? " · indicative" : ""}</div>
            <div class="cat-card-counts num">
              <span><b>${posM.below}</b> below</span><span><b>${posM.at}</b> on market</span><span><b>${posM.above}</b> above</span>
            </div>
            ${hero.target ? html`<div class="cat-card-align"><${AlignmentChip} target=${hero.target} /></div>` : null}` :
            html`<div class="caption" style=${{ marginTop: "var(--s4)" }}>Not enough positioned metrics here to read a market stance yet — this category is assessed on practice prevalence.</div>`}
        </div>
        <div class="card cat-pos-card">
          <div class="cat-hero-label">Practice prevalence</div>
          ${prev.pool ? html`
            <${Donut} segments=${prevSegs} total=${prev.pool} centerNum=${prev.with_majority} sub=${"of " + prev.pool + " practice" + (prev.pool === 1 ? "" : "s")} size=${210} stroke=${28} />
            <div class="cat-card-cap">match the market majority</div>
            <div class="cat-card-counts num">
              <span><b>${prev.with_majority}</b> match</span><span><b>${prev.established}</b> common alt</span><span><b>${prev.less_common}</b> rarer</span>
            </div>` :
            html`<div class="caption" style=${{ marginTop: "var(--s4)" }}>No practice questions assessed in this category yet.</div>`}
        </div>
      </div>

      ${me.features && me.features.domain_summary ? html`<${DomainSummary} name=${name} cut=${cut} applyStrat=${applyStrat} />` : null}

      <section class="cat-section">
        <div class="cat-sec-head"><span class="cat-sec-ico"><${Icon} name="table" size=${14} /></span>
          <b>All metrics</b><span class="caption">${cards.length} shown</span>
          ${sigCounts.signal ? html`<a class="cat-flag-link" href="#/signals" title="${sigCounts.signal} metric${sigCounts.signal === 1 ? "" : "s"} here ${sigCounts.signal === 1 ? "is" : "are"} flagged — open the Signals view"><${Icon} name="flag" size=${12} /> ${sigCounts.signal} flagged →</a>` : null}
          <div class="cat-filters">
            ${posM && posM.pool ? html`<div class="sig-chips cat-pos-chips" role="group" aria-label="Filter by market position">
              <button type="button" class=${"sig-chip" + (posSel.length === 0 ? " on" : "")} aria-pressed=${posSel.length === 0} onClick=${() => setPosSel([])}>All</button>
              ${[{ k: "below", n: posM.below, lab: "below" }, { k: "on", n: posM.at, lab: "on market" }, { k: "above", n: posM.above, lab: "above" }].filter(p => p.n).map(p => html`
                <button key=${p.k} type="button" class=${"sig-chip" + (posSel.includes(p.k) ? " on" : "")} aria-pressed=${posSel.includes(p.k)}
                  onClick=${() => setPosSel(sel => sel.includes(p.k) ? sel.filter(x => x !== p.k) : [...sel, p.k])}>
                  ${p.lab} <span class="n">${p.n}</span></button>`)}
            </div>` : null}
            <select class="ctl" aria-label="Filter by question type" value=${type} onChange=${e => setType(e.target.value)}>
              <option value="">All types</option><option value="metric">Metrics</option>
              <option value="practice">Practices</option><option value="policy">Policies</option><option value="benefit">Benefits</option>
            </select>
          </div></div>
        ${cards.length === 0 ? html`<${EmptyState} title="No metrics match these filters"
          action=${html`<button class="btn small" onClick=${() => { setType(""); setPosSel([]); }}>Clear filters</button>`} /> ` :
        html`<div class="bench-grid">
          ${cards.map(c => html`
            <div key=${c.id} id=${"q-" + c.id}>
              <${BenchmarkCard} card=${c} prefs=${prefs} onPref=${onPref} onPin=${onPin}
                pinned=${pinnedIds.has(c.id)} cuts=${cuts} globalCut=${cutKeyOf(cut)} signal=${sigMap[c.id]}
                window=${me.peer_pool && me.peer_pool.collection_window} />
            </div>`)}
        </div>`}
      </section>
    </div>`;
};

// --------------------------------------------------------- my dashboards ---
// Several named, saveable dashboards per user. A switcher tab-bar sits above the
// same draggable card grid the old single "My view" used; the active dashboard
// is what the global pin-star (anywhere in the app) writes to.
window.DashboardsPage = function ({ me, cut, cuts, prefs, onPref, setPinned }) {
  const [list, setList] = useState(null);       // [{id,name,position,count}]
  const [activeId, setActiveId] = useState(null);
  const [layout, setLayout] = useState(null);   // active dashboard's slots
  const [cards, setCards] = useState({});
  const [drag, setDrag] = useState(null);
  const [saved, setSaved] = useState(null);
  const [sigMap, setSigMap] = useState({});
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [confirmDel, setConfirmDel] = useState(false);
  const [busy, setBusy] = useState(false);
  const nameRef = useRef(null);
  const cancelRename = useRef(false);   // Escape sets this so the input's onBlur doesn't commit

  const applyActive = (id, lay) => {
    setActiveId(id); setLayout(lay); setCards({});
    if (setPinned) setPinned((lay || []).map(s => s.question_id));
  };
  // cache key folds in the EFFECTIVE peer cut, so changing the global filter
  // (or a slot's own cut) yields a fresh key → refetch, not a stale card.
  const cardKey = slot => slotKey(slot) + "|" + cutKeyOf(slot.cut || cut);
  const reload = () => api("/api/dashboards").then(d => {
    setList(d.dashboards); applyActive(d.active_id, d.active.layout);
  });
  useEffect(() => { reload(); }, []);
  // a card's "Add to dashboard" picker (anywhere) can change this dashboard's
  // contents — keep the tab counts + the active grid in sync without a full reset.
  useEffect(() => {
    const f = () => api("/api/dashboards").then(d => {
      setList(d.dashboards); setLayout(d.active.layout);
      if (setPinned) setPinned((d.active.layout || []).map(s => s.question_id));
    }).catch(() => {});
    window.addEventListener("lumi:pins-changed", f);
    return () => window.removeEventListener("lumi:pins-changed", f);
  }, []);
  useEffect(() => {
    api("/api/overview?" + cutQS(cut)).then(o => {
      const m = {}; (o.signals_all || []).forEach(s => { (m[s.question_id] = m[s.question_id] || []).push(s); }); setSigMap(m);
    }).catch(() => setSigMap({}));
  }, [cutKeyOf(cut)]);
  useEffect(() => {
    if (!layout) return;
    layout.forEach(slot => {
      const key = cardKey(slot);
      if (cards[key]) return;
      const c = slot.cut || cut;
      api(`/api/benchmark/${slot.question_id}?` + cutQS(c))
        .then(d => setCards(prev => ({ ...prev, [key]: d })))
        .catch(() => setCards(prev => ({ ...prev, [key]: { error: true } })));
    });
  }, [layout, cutKeyOf(cut)]);
  useEffect(() => { if (renaming && nameRef.current) { nameRef.current.focus(); nameRef.current.select(); } }, [renaming]);

  if (!list || !layout) return html`<div class="row" style=${{ justifyContent: "center", padding: "var(--s8)" }}><${Spinner} /></div>`;
  const active = list.find(d => d.id === activeId) || {};
  const activeName = active.name || "My dashboard";

  const persist = async (next) => {
    setLayout(next);
    if (setPinned) setPinned(next.map(s => s.question_id));
    setList(l => l.map(d => d.id === activeId ? { ...d, count: next.length } : d));
    await api(`/api/dashboards/${activeId}`, { method: "PUT", body: { layout: next } }).catch(() => {});
  };
  const remove = qid => persist(layout.filter(s => s.question_id !== qid));
  const resize = (qid, size) => persist(layout.map(s => s.question_id === qid ? { ...s, size } : s));
  const onDrop = idx => {
    if (drag === null || drag === idx) { setDrag(null); return; }
    const next = [...layout];
    const [moved] = next.splice(drag, 1);
    next.splice(idx, 0, moved);
    setDrag(null); persist(next);
  };

  const switchTo = async (id) => {
    if (id === activeId || busy) return;
    setBusy(true); setRenaming(false); setConfirmDel(false);
    try {
      await api(`/api/dashboards/${id}/activate`, { method: "POST" });
      const d = await api(`/api/dashboards/${id}`);
      applyActive(id, d.layout);
    } finally { setBusy(false); }
  };
  const createNew = async () => {
    if (busy) return;
    setBusy(true); setConfirmDel(false);
    try {
      const d = await api("/api/dashboards", { method: "POST", body: { name: "New dashboard" } });
      await reload();
      setNameDraft(d.name); setRenaming(true);
    } finally { setBusy(false); }
  };
  const duplicate = async () => {
    if (busy) return;
    setBusy(true); setConfirmDel(false);
    try {
      await api("/api/dashboards", { method: "POST", body: { name: activeName + " copy", clone_from: activeId } });
      await reload();
    } finally { setBusy(false); }
  };
  const startRename = () => { setNameDraft(activeName); setRenaming(true); };
  const commitName = async () => {
    if (!renaming) return;
    if (cancelRename.current) { cancelRename.current = false; setRenaming(false); return; }  // Escape — discard
    const nm = (nameDraft || "").trim().slice(0, 60) || activeName;
    setRenaming(false);
    setList(l => l.map(d => d.id === activeId ? { ...d, name: nm } : d));
    await api(`/api/dashboards/${activeId}`, { method: "PUT", body: { name: nm } }).catch(() => {});
  };
  const doDelete = async () => {
    setConfirmDel(false); setBusy(true);
    try {
      const r = await api(`/api/dashboards/${activeId}`, { method: "DELETE" });
      setList(r.dashboards);
      const d = await api(`/api/dashboards/${r.active_id}`);
      applyActive(r.active_id, d.layout);
    } finally { setBusy(false); }
  };
  const saveDefault = async () => {
    await api("/api/myview/save-default", { method: "POST", body: { layout } });
    setSaved("Saved as your team's starting layout");
    setTimeout(() => setSaved(null), 2500);
  };
  const onlyOne = list.length <= 1;

  return html`
    <div>
      <div class="row spread" style=${{ marginBottom: "var(--s3)" }}>
        <div>
          <h1 class="display-title">My dashboards</h1>
          <div class="caption" style=${{ marginTop: "var(--s1)" }}>
            Build and save as many views as you like — pin cards from anywhere in lumi (☆), drag to arrange, and switch between them here.
          </div>
        </div>
        <div class="row">
          ${saved && html`<${Chip} kind="good">${saved}<//>`}
          <${ShareButton} me=${me} cut=${null} name=${activeName} />
          ${me.user.role === "admin" && html`<button class="btn" onClick=${saveDefault} title="New team members start from this layout">Save as team default</button>`}
        </div>
      </div>

      <div class="dash-tabs" role="group" aria-label="Your dashboards">
        ${list.map(d => html`
          <button key=${d.id} type="button" aria-pressed=${d.id === activeId}
            class=${"dash-tab" + (d.id === activeId ? " on" : "")} onClick=${() => switchTo(d.id)}>
            <span class="dash-tab-name">${d.name}</span>
            <span class="dash-tab-count">${d.count}</span>
          </button>`)}
        <button class="dash-tab dash-tab-new" onClick=${createNew} disabled=${busy} title="Create a new dashboard">
          <span aria-hidden="true">＋</span> New</button>
      </div>

      <div class="dash-toolbar">
        <div class="dash-toolbar-l">
          ${renaming
            ? html`<input ref=${nameRef} class="ctl dash-name-input" value=${nameDraft} maxlength="60"
                aria-label="Dashboard name"
                onInput=${e => setNameDraft(e.target.value)}
                onBlur=${commitName}
                onKeyDown=${e => { if (e.key === "Enter") { e.preventDefault(); commitName(); } else if (e.key === "Escape") { cancelRename.current = true; setRenaming(false); } }} />`
            : html`<h2 class="dash-name" onDoubleClick=${startRename} title="Double-click to rename">${activeName}</h2>`}
          ${!renaming && html`
            <div class="dash-actions no-print">
              <button class="iconbtn" title="Rename" onClick=${startRename}><${Icon} name="pencil" size=${14} /></button>
              <button class="iconbtn" title="Duplicate this dashboard" onClick=${duplicate} disabled=${busy}><${Icon} name="copy" size=${14} /></button>
              <button class="iconbtn" title=${onlyOne ? "Reset this dashboard" : "Delete this dashboard"} onClick=${() => setConfirmDel(true)} disabled=${busy}><${Icon} name="close" size=${14} /></button>
            </div>`}
        </div>
        <div class="caption">${layout.length} card${layout.length === 1 ? "" : "s"}</div>
      </div>

      ${confirmDel && html`
        <div class="dash-confirm" role="alertdialog">
          <span><b>${onlyOne ? "Reset" : "Delete"} “${activeName}”?</b> ${onlyOne ? "It will be cleared back to your starting layout." : "This can't be undone."}</span>
          <div class="row" style=${{ gap: "var(--s2)" }}>
            <button class="btn small" onClick=${() => setConfirmDel(false)}>Cancel</button>
            <button class="btn small danger" onClick=${doDelete}>${onlyOne ? "Reset" : "Delete"}</button>
          </div>
        </div>`}

      ${layout.length === 0 && html`<${EmptyState} icon="star" title="This dashboard is empty"
        body="Pin a card with the star (☆) on any benchmark — across Overview, Benchmark or Signals — and it lands here."
        action=${html`<button class="btn small" onClick=${() => nav("/overview")}>Browse the benchmark</button>`} />`}

      <div class=${"bench-grid" + (busy ? " is-busy" : "")}>
        ${layout.map((slot, i) => {
          const c = cards[cardKey(slot)];
          return html`
          <div key=${slotKey(slot)} draggable="true" class=${drag === i ? "dragging" : ""}
            onDragStart=${() => setDrag(i)} onDragOver=${e => e.preventDefault()} onDrop=${() => onDrop(i)}
            style=${slot.size === 2 ? { gridColumn: "span 2" } : null}>
            ${!c ? html`<${SkeletonCard} />` :
            c.error ? html`<div class="card bench-card"><${EmptyState} title="Couldn't load this card" /></div>` :
            html`<${BenchmarkCard} card=${c} prefs=${prefs} onPref=${onPref} size=${slot.size}
              onPin=${() => remove(slot.question_id)} pinned=${true} cuts=${cuts} globalCut=${cutKeyOf(cut)} signal=${sigMap[slot.question_id]}
              footTools=${html`
                <button class="iconbtn" title=${slot.size === 2 ? "Single width" : "Double width"} aria-label="Card width" onClick=${() => resize(slot.question_id, slot.size === 2 ? 1 : 2)}>${slot.size === 2 ? "1×" : "2×"}</button>
                <span class="iconbtn" title="Drag to reorder" aria-label="Drag to reorder" style=${{ cursor: "grab" }}>⠿</span>`} />`}
          </div>`;
        })}
      </div>
    </div>`;
};
window.MyViewPage = window.DashboardsPage;   // back-compat alias
function slotKey(slot) { return slot.question_id + "|" + (slot.row_id || "") + "|" + JSON.stringify(slot.cut || {}); }

// ----------------------------------------------------------- my data -------
/* Your data (chrome spec section 1.3): ONE destination for the org's data —
   view/manage (the old My data) with Submit as the primary action inside the
   page, role-gated (hidden, not disabled, for viewers). */
// a compact completion ring (pct in centre); colour cues the progress band.
// On mount the arc draws and the number counts up — once, reduced-motion safe.
function CompletionRing({ pct, size = 72, stroke = 8 }) {
  const target = Math.max(0, Math.min(100, pct));
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { setShown(target); return; }
    let raf, start = null; const dur = 850;
    const tick = (t) => {
      if (start === null) start = t;
      const k = Math.min(1, (t - start) / dur), e = 1 - Math.pow(1 - k, 3); // easeOutCubic
      setShown(target * e);
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  const r = (size - stroke) / 2, C = 2 * Math.PI * r, off = C * (1 - shown / 100);
  const col = target >= 90 ? "var(--favourable)" : target >= 50 ? "var(--blue)" : "var(--amber-bright)";
  const cx = size / 2;
  return html`<svg width=${size} height=${size} viewBox=${"0 0 " + size + " " + size} class="comp-ring" aria-hidden="true">
    <circle cx=${cx} cy=${cx} r=${r} fill="none" stroke="var(--surface-sunk)" stroke-width=${stroke} />
    <circle cx=${cx} cy=${cx} r=${r} fill="none" stroke=${col} stroke-width=${stroke} stroke-linecap="round"
      stroke-dasharray=${C} stroke-dashoffset=${off} transform=${"rotate(-90 " + cx + " " + cx + ")"} />
    <text x="50%" y="50%" text-anchor="middle" dominant-baseline="central" class="comp-ring-pct" style=${{ fill: col }}>${Math.round(shown)}%</text>
  </svg>`;
}
window.CompletionRing = CompletionRing;

window.YourDataPage = function ({ me }) {
  const [data, setData] = useState(null);
  useEffect(() => { api("/api/data-overview").then(setData).catch(() => setData({ error: true })); }, []);
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "var(--s8)" }}><${Spinner} /></div>`;
  if (data.error) return html`<${EmptyState} title="Couldn't load your data" />`;
  const c = data.contribution || {};
  const canEdit = me && (me.user.role === "admin" || me.user.role === "contributor");
  const target = c.target_pct || 90;
  const fresh = data.answered === 0;            // brand-new: a start, not a deficit
  // One forward CTA, gate-aware. Until firmographics + data terms are cleared,
  // the on-ramp (/your-data/submit) runs those gates; after that the CTA points
  // straight into the first unfinished area, or to Review & submit when done.
  const profiled = !!(me && me.org && me.org.classified);   // firmographics done
  const termsAccepted = !!c.terms_accepted;                 // data terms accepted
  const gated = !profiled || !termsAccepted;
  const nextDomain = (data.domains || []).find(d => d.answered < d.total);
  const cta = gated
    ? { label: !profiled ? "Get started" : "Review the data terms", to: "/your-data/submit" }
    : nextDomain
      ? { label: fresh ? "Start answering" : "Continue answering", to: "/your-data/" + encodeURIComponent(nextDomain.name) }
      : { label: "Review & submit", to: "/your-data/review" };
  return html`
    <div class="yourdata">
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <h1 class="display-title">Your data</h1>
          <div class="caption" style=${{ marginTop: "var(--s1)" }}>Everything your organisation has submitted — only your team can see this.</div>
        </div>
        ${canEdit && !fresh && html`<button class="btn primary" onClick=${() => nav(cta.to)}><${Icon} name="pencil" size=${14} /> ${cta.label}</button>`}
      </div>

      <div class=${"card data-hero" + (fresh ? " fresh" : "")}>
        <${CompletionRing} pct=${data.pct} size=${118} stroke=${12} />
        <div class="data-hero-body">
          <div class="data-hero-fig">${fresh ? html`<b>Let's build your reward benchmark.</b>`
            : html`<b>${data.answered}</b> of ${data.total} answered`}</div>
          ${c.insights_unlocked ? html`
            <div class="data-unlock good"><span class="du-ico"><${Icon} name="sparkle" size=${14} /></span>
              <div><b>Insights unlocked</b> — thank you for contributing to the benchmark.</div></div>` : html`
            <div class="data-unlock"><span class="du-ico"><${Icon} name=${fresh ? "sparkle" : "lock"} size=${14} /></span>
              <div><b>${fresh ? "Answer your reward questions to unlock your insights." : "Reach " + target + "% to unlock your insights."}</b>${c.days_left != null ? ` ${c.days_left} days to go.` : ""}</div></div>`}
          ${fresh && canEdit && html`<button class="btn primary data-start" onClick=${() => nav(cta.to)}><${Icon} name="pencil" size=${14} /> ${cta.label}</button>`}
          ${!fresh && canEdit && !gated && html`<a class="data-review-link" href="#/your-data/review">Review & submit your data →</a>`}
          ${c.reduced && html`
            <div class="data-access warn">
              <${Icon} name="shield" size=${13} />
              <span><b>Access reduced.</b> Your benchmark is in teaser mode until you reach ${target}%. Complete your data to restore full access.</span>
            </div>`}
        </div>
      </div>

      <h2 class="section-title" style=${{ marginTop: "var(--s5)" }}>By area <span class="caption">${fresh ? "tap an area to start answering its questions" : "tap an area to view or complete its questions"}</span></h2>
      <div class="data-domains">
        ${(data.domains || []).map(d => html`
          <div key=${d.name} class="card data-domain" role="button" tabindex="0"
            onClick=${() => nav("/your-data/" + encodeURIComponent(d.name))}
            onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nav("/your-data/" + encodeURIComponent(d.name)); } }}>
            <div class="data-domain-head"><span class="cat-icon"><${Icon} name=${CAT_ICON[d.name] || "award"} size=${14} /></span> ${d.name}</div>
            <${CompletionRing} pct=${d.pct} size=${78} stroke=${8} />
            ${d.answered >= d.total ? html`<div class="data-done"><${Icon} name="award" size=${11} /> Complete</div>`
              : html`<div class="caption">${d.answered} of ${d.total} · <span class="data-todo">${d.total - d.answered} to do</span></div>`}
          </div>`)}
      </div>
    </div>`;
};

window.DomainDataView = function ({ me, section }) {
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState("all");
  useEffect(() => { api("/api/data-overview").then(setData).catch(() => setData({ error: true })); }, []);
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "var(--s8)" }}><${Spinner} /></div>`;
  const d = (data.domains || []).find(x => x.name === section);
  if (!d) return html`<${EmptyState} icon="table" title="Area not found"
    action=${html`<button class="btn small" onClick=${() => nav("/your-data")}>Back to Your data</button>`} />`;
  const canEdit = me && (me.user.role === "admin" || me.user.role === "contributor");
  const tabs = [{ k: "all", label: "All", n: d.total }, { k: "answered", label: "Answered", n: d.answered },
    { k: "unanswered", label: "To answer", n: d.total - d.answered }];
  const qs = d.questions.filter(x => filter === "all" || (filter === "answered") === x.answered);
  return html`
    <div class="yourdata">
      <a class="caption back-link" href="#/your-data"><${Icon} name="chevron-left" size=${13} /> Your data</a>
      <div class="row spread" style=${{ alignItems: "center", margin: "var(--s1) 0 var(--s4)" }}>
        <div class="row" style=${{ gap: "var(--s3)", alignItems: "center" }}>
          <span class="cat-glyph"><${Icon} name=${CAT_ICON[section] || "award"} size=${20} /></span>
          <div><h1 class="display-title">${section}</h1>
            <div class="caption meta">${d.answered} of ${d.total} answered</div></div>
        </div>
        <div class="row" style=${{ gap: "var(--s3)", alignItems: "center" }}>
          <${CompletionRing} pct=${d.pct} size=${56} stroke=${7} />
          ${canEdit && html`<button class="btn primary" onClick=${() => nav("/your-data/submit/" + encodeURIComponent(section))}><${Icon} name="pencil" size=${14} /> ${d.answered < d.total ? "Complete" : "Edit"} ${section}</button>`}
        </div>
      </div>

      <div class="sig-tabs">
        ${tabs.map(t => html`<button key=${t.k} class=${"sig-tab" + (filter === t.k ? " on" : "")} onClick=${() => setFilter(t.k)}>
          ${t.label} <span class="num">${t.n}</span></button>`)}
      </div>

      ${qs.length === 0 ? html`<div class="signals-empty" style=${{ marginTop: "var(--s5)" }}>
          <span class="signals-empty-ring"><${Icon} name=${filter === "unanswered" ? "sparkle" : "table"} size=${18} /></span>
          <div class="caption">${filter === "unanswered" ? "Nothing left to answer in " + section + " — fully complete." : "No questions here yet."}</div>
        </div>` :
      html`<div class="data-qlist">
        ${qs.map(q => html`
          <div key=${q.question_id} class=${"data-q" + (q.answered ? "" : " unans")}>
            <div class="data-q-main">
              <div class="data-q-title">${q.title}
                ${q.required ? html`<span class="data-q-req" title="Counts toward the completion that keeps your access">required</span>` : ""}</div>
              ${q.answered ? (q.rows ? html`
                <div class="data-q-rows">${q.rows.map((rw, i) => html`<span key=${i}><span class="muted">${rw.row}:</span> ${dataVal(rw.value, q)}</span>`)}</div>`
                : html`<div class="data-q-val">${dataVal(q.value, q)}</div>`)
                : html`<div class="data-q-none">Not answered yet${canEdit ? html` — <a href=${"#/your-data/submit/" + encodeURIComponent(section)}>answer now</a>` : ""}</div>`}
            </div>
            <span class=${"data-q-flag " + (q.answered ? "ok" : "todo")}>
              <${Icon} name=${q.answered ? "award" : "pencil"} size=${13} /> ${q.answered ? "Answered" : "To do"}</span>
          </div>`)}
      </div>`}
    </div>`;
};
function dataVal(value, q) {
  if (q && (q.type === "numeric" || q.type === "matrix")) {
    const f = parseFloat(String(value).replace(/[£,%]/g, ""));
    if (!isNaN(f)) return fmtValue(f, q.unit);
  }
  return value;
}

/* ===================== How lumi works hub (chrome spec §4) =================
   One trust page, three anchored sections, side-tab navigation. Replaces the
   separate Methodology, Core governance and legal destinations. Every §4.1
   sub-card carries a STABLE id so metric pages (§6.1) and the suppression
   tooltip (§6.2) can deep-link straight to it via /how-lumi-works/<anchor>.
   The phrase "co-op governance" appears nowhere as a heading or label. */
window.HOW_LUMI_TABS = [
  { key: "calculations", label: "How the numbers are calculated" },
  { key: "co-op", label: "How the co-op works" },
  { key: "legal", label: "Legal" },
];

window.HowLumiWorksPage = function ({ me, anchor }) {
  const [m, setM] = useState(null);
  const [legal, setLegal] = useState(null);
  const [doc, setDoc] = useState(null);   // open legal document key | null
  useEffect(() => { api("/api/methodology").then(setM); api("/api/legal").then(d => setLegal(d.documents)); }, []);
  // deep-link: /how-lumi-works/<anchor> scrolls that element into view once
  // the content has rendered.
  useEffect(() => {
    if (!m || !anchor) return;
    // defer past layout: the methodology tables grow the page after first
    // paint, so an immediate scroll lands on a stale position.
    const t = setTimeout(() => {
      const el = document.getElementById(anchor);
      if (!el) return;
      // instant, not smooth: a smooth animation re-targets as the methodology
      // tables grow the page mid-scroll and overshoots the anchor.
      el.scrollIntoView({ behavior: "auto", block: "start" });
      el.classList.add("anchor-flash");
      setTimeout(() => el.classList.remove("anchor-flash"), 1600);
    }, 220);
    return () => clearTimeout(t);
  }, [m, anchor]);
  if (!m) return html`<div class="row" style=${{ justifyContent: "center", padding: "var(--s8)" }}><${Spinner} /></div>`;
  const industries = Object.keys(m.composition);
  const sectionTab = (HOW_LUMI_TABS.find(t => t.key === anchor) || HOW_LUMI_TABS[0]).key;
  const go = (k) => nav("/how-lumi-works/" + k);
  return html`
    <div class="how-hub">
      <aside class="how-tabs no-print">
        <div class="nav-label">How lumi works</div>
        ${HOW_LUMI_TABS.map(t => html`
          <button key=${t.key} class=${"how-tab" + (sectionTab === t.key ? " active" : "")} onClick=${() => go(t.key)}>${t.label}</button>`)}
      </aside>
      <div class="how-body" style=${{ maxWidth: "820px" }}>
        <h1 class="display-title">How lumi works</h1>
        <p class="caption">What's in your benchmark, how the numbers are built, how the co-operative runs, and where the legal documents live.</p>

        ${/* ---------- §4.1 Calculations ---------- */ ""}
        <h2 class="how-section-head" id="calculations">How the numbers are calculated</h2>
        <p class="caption" style=${{ marginTop: "-4px" }}>Benchmark snapshot dated ${m.snapshot_date} · collection window ${m.collection_window} · methodology v1</p>

        <div class="card how-card" id="market-position">
          <h3 class="section-title">Where you stand — your market position</h3>
          <p>For everything we measure, we compare your figure to the same measure across your peer group and place you in one of three positions: <b>below market</b> (under where most peers sit), <b>on market</b> (in line — we allow a sensible margin so tiny differences aren't treated as gaps), or <b>above market</b>. We do this measure by measure, roll it up for each area of reward, and bring it together into a single headline.</p>
          <p><b>Two kinds of thing we measure.</b> Some measures have a going rate — pay, pension, holiday, bonus levels — so "below, on or above market" genuinely means something. Others are choices with no right answer — which share scheme you run, how you structure a benefit, how often you review pay. There's no rate to be under or over; you're simply doing it differently. We label these <b>differs from market</b> — a difference to be aware of, not a gap to close. That's why your headline won't match the total number of things we measure: only the market-rate measures feed it.</p>
          <p><b>When "below market" isn't a bad thing.</b> A few measures are better when they're lower — your CEO-to-employee pay ratio, your gender pay gap. Below market there is good news, so we show it as <b>favourable</b> rather than a gap. Some measures have no good direction at all — workforce cost as a share of revenue could mean you're lean, or under-investing. We show these as <b>context</b>: a fact to weigh, not a verdict. The label always tells the truth about the number; the colour tells you how to read it.</p>
          <div class="mp-legend">
            <span><i class="sw" style=${{ background: "var(--amber-bright)" }}></i> below market</span>
            <span><i class="sw" style=${{ background: "var(--favourable)" }}></i> on market / favourable</span>
            <span><i class="sw" style=${{ background: "var(--unfavourable)" }}></i> above market</span>
            <span><i class="sw" style=${{ background: "var(--differs)" }}></i> differs from market</span>
            <span><i class="sw" style=${{ background: "var(--navy)" }}></i> context</span>
          </div>
          <p><b>The headline answers one question.</b> "Where you stand" is a read on how competitive your reward is — are you paying and providing at the market rate? So it's built only from the market-rate measures where higher is better. Governance (your pay ratio, your pay gap) isn't about competitiveness — you don't compete on a low pay ratio — so it sits beside the headline, not inside it. The same goes for any market-rate measure with no competitive direction, like your workforce cost as a share of revenue. That keeps the headline answering one clear thing rather than blending several.</p>
          <p class="caption">Where a comparison rests on only a few companies, we mark the verdict <b>indicative</b> — a steer, not a precise figure.</p>
        </div>

        <div class="card how-card" id="who-compared">
          <h3 class="section-title">Who you're compared with (market norms)</h3>
          <p>A peer norm is built only from organisations that have completed a lumi submission. The pool holds
          <b>${m.peer_pool.responding_orgs} UK organisations</b>; ${m.peer_pool.classified_orgs} carry full firmographic
          profiles (sector, size, region, ownership) and appear in filtered peer groups, while ${m.unclassified_count}
          await classification and sit in the "All peers" group only.</p>
          <table class="data" style=${{ marginTop: "var(--s3)" }}>
            <thead><tr><th>Sector</th>${m.fte_bands.map(b => html`<th key=${b} class="num">${b}</th>`)}<th class="num">Total</th></tr></thead>
            <tbody>
              ${industries.map(ind => {
                const row = m.composition[ind];
                const tot = Object.values(row).reduce((a, b) => a + b, 0);
                return html`<tr key=${ind}><td>${ind}</td>
                  ${m.fte_bands.map(b => html`<td key=${b} class="num">${row[b] || "·"}</td>`)}
                  <td class="num"><b>${tot}</b></td></tr>`;
              })}
            </tbody>
          </table>
        </div>

        <div class="card how-card" id="percentiles">
          <h3 class="section-title">Percentiles and your position</h3>
          <p><b>Percentiles.</b> P10, P25, P50 (median), P75 and P90 use linear interpolation across all valid peer
          answers — the same method the main survey houses use. We benchmark on medians, not averages, so a single
          unusual organisation cannot skew a figure.</p>
          <p><b>Your percentile.</b> Your P-number is the share of peer organisations whose value sits below yours
          (ties counted half), so P63 means you are higher than about 6 in 10 peers.</p>
          <p><b>Favourable vs the market.</b> Each question carries a polarity — higher is better, lower is better, or
          neutral (where "better" depends on strategy). Green/amber/red colouring is polarity-adjusted and is never
          applied to neutral metrics.</p>
        </div>

        <div class="card how-card" id="suppression">
          <h3 class="section-title">Small-sample protection</h3>
          <p>Any figure that would rest on fewer than <b>${m.suppression_floor} organisations</b> is not shown — you
          see "not enough organisations to show this safely" instead. This floor is the single suppression rule, applied
          to <b>every</b> peer group — including bespoke groups such as Peer Twin and your own custom groups — and it is
          enforced in one place in the calculation engine, so no view can route around it.</p>
          <p class="caption">No peer figure is ever derived from a single organisation, and member identities are never
          shown in any group.</p>
        </div>

        <div class="card how-card" id="versioning">
          <h3 class="section-title">Versioning and comparability</h3>
          <p>The question set changes through scheduled releases. ${" "}
          <b>2026.1</b> restructured the catalogue into seven categories; <b>2026.2</b> added forward-looking questions.
          Every collection window is stored as a separate, versioned snapshot — submissions never overwrite history.</p>
          <p><b>Comparability breaks.</b> When a question changes materially, values either side of the change aren't
          comparable, so trends <i>reset</i> at the break rather than joining a misleading continuous line.</p>
        </div>

        <div class="card how-card" id="sources">
          <h3 class="section-title">Where the data comes from</h3>
          <p>This snapshot ingested ${m.reconciliation.files} member submissions (${(m.reconciliation.answer_rows || 0).toLocaleString("en-GB")} answers).
          ${m.reconciliation.matched_orgs} organisations were matched to the lumi member registry by normalised company
          name; ${m.reconciliation.file_only_orgs} submissions without a registry profile are retained as Unclassified;
          ${m.reconciliation.registry_only_orgs} registry members have not yet submitted and are excluded from every
          aggregate. Near-miss name matches are flagged for human review and never joined automatically.</p>
          <p><b>£ modelling assumptions.</b> Opportunity figures use FTE band midpoints, a UK all-sector median salary of
          £${(m.assumptions.median_salary_gbp || 0).toLocaleString("en-GB")} (editable in Settings), a cost per leaver of
          ${m.assumptions.cost_per_leaver_pct_salary}% of salary and an agency premium of ${m.assumptions.agency_premium_pct}%.
          They are assumptions, clearly labelled, and every £ figure is indicative.</p>
        </div>

        <div class="card how-card" id="glossary">
          <h3 class="section-title">Glossary</h3>
          ${Object.entries(GLOSSARY).map(([k, v]) => html`
            <p key=${k} style=${{ margin: "var(--s2) 0" }}><b style=${{ textTransform: "capitalize" }}>${k}.</b> ${v}</p>`)}
          <p style=${{ margin: "var(--s2) 0" }}><b>Peer Twin.</b> A bespoke peer group of the organisations most similar to yours
          across industry, size, ownership and workforce shape, recalculated as the membership grows; member names are never shown.</p>
        </div>

        ${/* ---------- §4.2 How the co-op works ---------- */ ""}
        <h2 class="how-section-head" id="co-op">How the co-op works</h2>
        <div class="card how-card">
          <h3 class="section-title">A give-to-get co-operative</h3>
          <p>lumi is a benchmarking co-operative: the data you see comes from members like you, so the value depends on
          everyone contributing. <b>Participating organisations benchmark for free</b> — you give your reward data and,
          in return, you get the peer picture. Organisations that want the benchmark without contributing pay; members
          who contribute do not.</p>
          <p><b>Founding membership.</b> Organisations joining in the launch phase are founding members and benchmark
          free for their first year while the pool builds.</p>
        </div>
        <div class="card how-card">
          <h3 class="section-title">How your data is shared — and how it isn't</h3>
          <p>Your submission only ever appears inside <b>aggregates</b>. Other members see peer distributions and
          percentiles, never your raw answers and never your organisation's identity within a group. The small-sample
          floor (above) means no aggregate can be traced back to a single contributor.</p>
          <p>Share links carry the same protection: a recipient sees exactly what your team can see — your own data plus
          safe peer aggregates — and nothing more.</p>
        </div>
        <div class="card how-card">
          <h3 class="section-title">Suppression and ethics</h3>
          <p>We benchmark on medians, suppress thin samples, exclude "don't know" and "not applicable" rather than
          counting them against anyone, and never present a neutral metric with a good/bad colour. The benchmark is a
          mirror, not a scoreboard — it tells you where you stand, never what you must do.</p>
          ${me && me.user.role === "admin" && html`
            <p class="caption" style=${{ marginTop: "var(--s3)" }}>Admins: the question-set release console — current release, change
            log and backlog — lives in <a href="#/governance">the governance console</a>.</p>`}
        </div>

        ${/* ---------- §4.3 Legal ---------- */ ""}
        <h2 class="how-section-head" id="legal">Legal</h2>
        <div class="card how-card">
          <p class="caption">Each document is its own page; this is the index. Any document still in review is marked <b>Draft</b>.</p>
          <div class="legal-list">
            ${(legal || []).map(d => html`
              <button key=${d.key} class="legal-row" onClick=${() => setDoc(d.key)}>
                <span>${d.title}</span>
                ${d.draft && html`<span class="chip warn" style=${{ marginLeft: "auto" }}>Draft</span>`}
                <span class="legal-row-go" aria-hidden="true">→</span>
              </button>`)}
            ${legal == null && html`<div class="caption">Loading…</div>`}
          </div>
          <div class="caption" style=${{ marginTop: "var(--s3)" }}>
            <a href="/api/terms/dpa" download>Download the full Data Sharing Agreement (DPA)</a>
          </div>
        </div>
      </div>
      ${doc && html`<${LegalDocModal} docKey=${doc} onClose=${() => setDoc(null)} />`}
    </div>`;
};

/* A single legal document, read-only (chrome spec §4.3). Fetches the text on
   demand from the public /api/legal/<key> route. */
window.LegalDocModal = function ({ docKey, onClose }) {
  const [d, setD] = useState(null);
  useEffect(() => { api("/api/legal/" + docKey).then(setD).catch(() => setD({ error: true })); }, [docKey]);
  return html`
    <div class="modal-back" onClick=${onClose}>
      <div class="card legal-modal" style=${{ maxWidth: "660px", width: "92%", maxHeight: "82vh", overflow: "auto", padding: "var(--s5)" }}
        onClick=${e => e.stopPropagation()}>
        <div class="row spread" style=${{ marginBottom: "var(--s3)" }}>
          <h2 class="section-title" style=${{ margin: 0 }}>${d && d.title || "Legal"}</h2>
          <button class="btn quiet small" onClick=${onClose}>Close</button>
        </div>
        ${!d ? html`<${Spinner} />`
          : d.error ? html`<div class="error-text">Couldn't load this document.</div>`
          : html`${d.draft && html`<div class="how-note" style=${{ marginBottom: "var(--s3)" }}>This document is <b>DRAFT — pending legal review</b>.</div>`}
              <${TermsText} text=${d.text} />`}
      </div>
    </div>`;
};

// shared helpers
window.cutQS = function (cut) {
  let qs = "cut=" + encodeURIComponent(cut.dim || "all");
  if (cut.value) qs += "&cut_value=" + encodeURIComponent(cut.value);
  return qs;
};
window.cutKeyOf = cut => (cut.dim || "all") + "::" + (cut.value || "");
window.cutLabelOf = function (cut, cuts) {
  if (cut.dim === "industry") return cut.value || (cuts && cuts.org_industry) || "Your industry";
  if (cut.dim === "fte_band") return (cut.value || (cuts && cuts.org_fte_band) || "Your size") + " FTE";
  if (cut.dim === "twin") return "Organisations like you";
  if (cut.dim === "group") {
    const g = cuts && (cuts.groups || []).find(g => g.group_id === cut.value);
    return g ? g.name : "Your group";
  }
  return "All peers";
};

/* Pool size of the currently selected cut — mirrors the "· N" the peer control
   (PeerSetBar) shows, so the small-sample caveat's number always equals it.
   Returns null when size isn't known (the twin cut doesn't expose its pool size
   → treated as not-thin by design; recorded as a known gap in DECISIONS.md). */
window.cutSize = function (cut, cuts, peerPool) {
  if (!cut || !cut.dim || cut.dim === "all") {
    const n = (peerPool || {}).responding_orgs;
    return typeof n === "number" ? n : null;
  }
  if (cut.dim === "industry") {
    const n = cuts && cuts.industries && cuts.industries[cut.value];
    return typeof n === "number" ? n : null;
  }
  if (cut.dim === "fte_band") {
    const n = cuts && cuts.fte_bands && cuts.fte_bands[cut.value];
    return typeof n === "number" ? n : null;
  }
  if (cut.dim === "group") {
    const g = cuts && (cuts.groups || []).find(x => x.group_id === cut.value);
    return g && typeof g.match_count === "number" ? g.match_count : null;
  }
  return null; // twin — pool size not exposed
};

/* ===================== versioning & governance (2026-06-12) ===============
   MetricTrend: the same question version across data periods. Comparability
   breaks are ENFORCED: each segment draws separately and a visible reset
   divider sits between segments — never a continuous line across a break. */
window.MetricTrend = function ({ qid }) {
  const [t, setT] = useState(null);
  useEffect(() => { setT(null); api("/api/trend/" + qid).then(setT).catch(() => setT(false)); }, [qid]);
  if (!t || t.periods < 2) return null;   // one period = nothing to trend yet
  const pts = t.segments.flat();
  const vals = pts.map(p => p.p50 != null ? p.p50 : p.modal_pct).filter(v => v != null);
  if (!vals.length) return null;
  const lo = Math.min(...vals), hi = Math.max(...vals), span = (hi - lo) || 1;
  const W = 640, H = 120, PAD = 34;
  const xStep = (W - PAD * 2) / Math.max(1, pts.length - 1);
  let xi = 0;
  const segs = t.segments.map(seg => seg.map(p => {
    const v = p.p50 != null ? p.p50 : p.modal_pct;
    const pt = { x: PAD + xi * xStep, y: H - 28 - ((v - lo) / span) * (H - 56), v, p };
    xi += 1;
    return pt;
  }));
  return html`
    <div class="card" style=${{ padding: "var(--s5)", marginTop: "var(--s4)" }}>
      <h2 class="section-title">Across data periods</h2>
      ${t.breaks.length > 0 && html`
        <div class="caption" style=${{ marginBottom: "var(--s2)" }}>
          ⚠ This question changed materially (${t.breaks.map(b => b.release_id).join(", ")}) —
          values either side of the break aren't comparable, so the trend resets rather than joining up.
        </div>`}
      <svg viewBox=${"0 0 " + W + " " + H} style=${{ width: "100%", maxWidth: W + "px" }}>
        ${segs.map((seg, si) => html`
          <g key=${si}>
            ${seg.length > 1 && html`<polyline fill="none" stroke="var(--blue)" stroke-width="2"
              points=${seg.map(d => d.x + "," + d.y).join(" ")} />`}
            ${seg.map((d, i) => html`
              <g key=${i}>
                <circle cx=${d.x} cy=${d.y} r="4" fill="var(--blue)" />
                <text x=${d.x} y=${d.y - 9} text-anchor="middle" font-size="10" fill="var(--ink-soft)">${fmtValue(d.v, null)}</text>
                <text x=${d.x} y=${H - 8} text-anchor="middle" font-size="10" fill="var(--ink-soft)">${d.p.period}</text>
              </g>`)}
          </g>`)}
        ${segs.slice(0, -1).map((seg, si) => {
          // every segment boundary IS a comparability break by construction
          const xBreak = (seg[seg.length - 1].x + (segs[si + 1] ? segs[si + 1][0].x : seg[seg.length - 1].x)) / 2;
          return html`
            <g key=${"b" + si}>
              <line x1=${xBreak} y1="10" x2=${xBreak} y2=${H - 22} stroke="var(--unfavourable)"
                stroke-width="1.5" stroke-dasharray="4 3" />
              <text x=${xBreak} y=${H - 26} text-anchor="middle" font-size="9" fill="var(--unfavourable)">reset</text>
            </g>`;
        })}
      </svg>
      <div class="caption">Market median by collection period · question ${t.question_version || ""}. A reset marks a
        comparability break — the question changed, so a single line would splice incomparable data.</div>
    </div>`;
};

/* Admin read surface: current release, history, change log, backlog. The
   backlog QUEUES for a release — nothing here changes the live core. */
window.GovernancePage = function ({ me }) {
  const [g, setG] = useState(null);
  const [err, setErr] = useState(null);
  const [title, setTitle] = useState("");
  const refresh = () => api("/api/governance").then(setG).catch(e => setErr(e.message));
  useEffect(() => { refresh(); }, []);
  if (err) return html`<${EmptyState} icon="lock" title="Admins only" body=${err} />`;
  if (!g) return html`<div class="row" style=${{ justifyContent: "center", padding: "var(--s8)" }}><${Spinner} /></div>`;
  const addBacklog = async () => {
    if (!title.trim()) return;
    await api("/api/governance/backlog", { method: "POST", body: { title } });
    setTitle(""); refresh(); toast("Queued for a future release — the live core is unchanged.");
  };
  const ingest = async () => {
    const r = await api("/api/governance/ingest-requests", { method: "POST", body: {} });
    toast(r.ingested + " member request(s) pulled into the backlog."); refresh();
  };
  return html`
    <div style=${{ maxWidth: "880px" }}>
      <h1 class="display-title">Core question-set governance</h1>
      <p>The core changes slowly and deliberately: scheduled <b>releases</b>, a queued backlog, and one
      emergency lane reserved for questions an external change has made factually wrong. Retired questions
      are never deleted — history always resolves.</p>

      <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s4)" }}>
        <div class="row spread">
          <div><b>Current release:</b> ${g.current_release ? g.current_release.release_id : "—"}
            <span class="caption"> · released ${g.current_release && g.current_release.released_at}</span></div>
          <div class="caption num">${g.core_size} live questions · ${g.required_size} required</div>
        </div>
        ${g.current_release && g.current_release.notes && html`<div class="caption" style=${{ marginTop: "var(--s1)" }}>${g.current_release.notes}</div>`}
      </div>

      <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Releases</h2>
        <table class="data"><thead><tr><th>Release</th><th>Status</th><th>Released</th><th>Signed off</th></tr></thead>
          <tbody>${g.releases.map(r => html`
            <tr key=${r.release_id}><td><b>${r.release_id}</b></td><td>${r.status}</td>
              <td class="num">${r.released_at}</td><td>${r.signed_off_by || "—"}</td></tr>`)}
          </tbody></table>
      </div>

      <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Change log</h2>
        ${g.changelog.length === 0 ? html`<div class="caption">No changes yet.</div>` : html`
          <table class="data"><thead><tr><th>Release</th><th>Lane</th><th>Type</th><th>Question</th><th>Detail</th></tr></thead>
            <tbody>${g.changelog.map(c => html`
              <tr key=${c.id}><td>${c.release_id || "—"}</td>
                <td>${c.lane === "emergency" ? html`<span class="chip warn">emergency</span>` : c.lane}</td>
                <td>${c.change_type}</td><td class="caption">${c.question_id || "—"}</td>
                <td class="caption">${c.detail}</td></tr>`)}
            </tbody></table>`}
      </div>

      <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s5)" }}>
        <div class="row spread">
          <h2 class="section-title">Backlog (queued for a release — never auto-applied)</h2>
          <button class="btn small" onClick=${ingest}>Pull in member requests</button>
        </div>
        <div class="row" style=${{ gap: "var(--s2)", margin: "var(--s2) 0" }}>
          <input style=${{ flex: 1, height: "34px", padding: "0 var(--s3)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)" }}
            placeholder="Add a candidate change for a future release…" value=${title}
            onInput=${e => setTitle(e.target.value)} />
          <button class="btn small primary" onClick=${addBacklog}>Queue it</button>
        </div>
        ${g.backlog.length === 0 ? html`<div class="caption">Backlog is empty.</div>` : html`
          <table class="data"><thead><tr><th>Item</th><th>Source</th><th>Status</th><th>Added</th></tr></thead>
            <tbody>${g.backlog.map(b => html`
              <tr key=${b.id}><td>${b.title}</td><td class="caption">${b.source}</td>
                <td>${b.status}</td><td class="num caption">${b.created_at}</td></tr>`)}
            </tbody></table>`}
      </div>
    </div>`;
};
