/* Dashboard pages: Executive overview, Superpower detail, My view, My data, Methodology. */
/* global html, useState, useEffect, useMemo, api, fmtValue, pLabel, Chip, NBadge, Term, Spinner,
   BenchmarkCard, QuartileDots, fmtGBPCompact, EmptyState, nav */

const SUPERPOWERS = ["Reward", "Processes", "Wellbeing", "Growth", "Capability",
  "Inclusivity", "Attract", "Leadership", "Purpose", "Change"];
window.SUPERPOWERS = SUPERPOWERS;
window.SECTION_ORDER = { "Pay": 1, "Benefits": 2, "Incentives": 3, "Transparency": 4, "Progression": 5 };
window.secOrder = sec => (window.SECTION_ORDER_LIVE && window.SECTION_ORDER_LIVE[sec]) || window.SECTION_ORDER[sec] || 99;
/* SpIcon: the one consistent superpower glyph (line-icon family from icons.js) */
window.SpIcon = ({ sp, size = 15 }) => html`<${Icon} name=${SP_ICON[sp] || "target"} size=${size} />`;

// ------------------------------------------------------------ overview -----
window.OverviewPage = function ({ me, cut, cuts, prefs, onPref, onPin, pinnedIds }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    setData(null); setErr(null);
    api("/api/overview?" + cutQS(cut)).then(setData).catch(e => setErr(e.message));
  }, [cutKeyOf(cut)]);
  if (err) return html`<${EmptyState} title="Couldn't load the overview"
    body=${err + " — nothing is lost; it usually works on a retry."}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!data) return html`
    <div>
      <div class="skel" style=${{ height: "30px", width: "320px", marginBottom: "10px" }}></div>
      <div class="skel" style=${{ height: "20px", width: "480px", marginBottom: "16px" }}></div>
      <div class="skel" style=${{ height: "180px", marginBottom: "16px", borderRadius: "var(--radius)" }}></div>
      <${SkeletonGrid} count=${3} />
    </div>`;
  const h = data.headline;
  const pctAbove = h.comparable_metrics ? Math.round(100 * h.above_median / h.comparable_metrics) : 0;
  return html`
    <div>
      <div class="hero">
        <div>
          <h1 class="display-title">${data.org.name}</h1>
          <div class="row" style=${{ marginTop: "6px" }}>
            ${data.synthetic_pool && html`<span class="chip warn hastip" style=${{ position: "relative", cursor: "help" }}>
              Illustrative sample data
              <span class="tip">The current peer pool is realistic but synthetic seed data, generated to behave like a UK benchmark while real member submissions build up. It must not be read as real benchmark data.</span>
            </span>`}
            ${cut.dim !== "all" && html`<${Chip} kind="accent">filter: ${cutLabelOf(cut, cuts)}<//>`}
          </div>
        </div>
        <div style=${{ marginLeft: "auto" }}>
          <${ExportBoardPack} me=${me} cut=${cut} />
        </div>
      </div>

      ${data.contribution && !data.contribution.insights_unlocked && !data.contribution.reduced &&
        html`<${WelcomeHero} contrib=${data.contribution} pool=${data.peer_pool} me=${me} />`}

      <${OverviewHero} data=${data} cut=${cut} cuts=${cuts} />

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

/* ============== the 80/20 home hero (2026-06-12 redesign) ==============
   Three questions, top to bottom: where do I sit overall (the arc), what
   should I look at (signals — flags, never advice), where do I sit per
   category (seven tiles). Leads/gaps become micro-band chips. The £
   opportunity lives inside signals; the journey strip returns when a second
   data period exists. */
function OverviewHero({ data, cut, cuts }) {
  const m = data.hero && data.hero.market;
  const locked = data.callouts && data.callouts.gaps_locked;
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
      <div class="ov-top">
        <${OverallArc} market=${m} />
        <${SignalsPanel} signals=${data.signals} locked=${locked} contribution=${data.contribution} />
      </div>
      <div class="cat-grid">
        ${(data.hero.domains || []).map(d => html`<${CategoryTile} key=${d.name} d=${d} />`)}
      </div>
      <div class="grid2" style=${{ margin: "var(--s4) 0", gap: "var(--s4)" }}>
        <${ChipColumn} title="You lead" items=${data.leads} good=${true} />
        ${locked ? html`
          <div class="card" style=${{ padding: "var(--s4)" }}>
            <div class="caption" style=${{ marginBottom: "6px" }}>Biggest gaps</div>
            <div class="insight-lock">
              <div class="blurred" aria-hidden="true">
                <div class="callout bad">Your largest gap appears here once unlocked.</div>
                <div class="callout bad">Where peers commonly lead.</div>
              </div>
              <div class="lock-note">
                <${Chip} kind="accent"><${Icon} name="lock" size=${11} /> Locked<//>
                <div class="caption" style=${{ textAlign: "center", maxWidth: "260px" }}>Unlock by completing your key reward questions.</div>
                <button class="btn small primary" onClick=${() => nav("/your-data/submit")}>Submit data</button>
              </div>
            </div>
          </div>` :
          html`<${ChipColumn} title="Biggest gaps" items=${data.lags} good=${false} />`}
      </div>
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
   (below=amber, on=green, above=red) on warm paper. */
function OverallArc({ market }) {
  // Hooks run BEFORE the early return so the order is stable when market is
  // null vs present. The needle sweeps from straight-up to its data angle on
  // mount (and re-sweeps when the cut changes) — a precision instrument
  // finding its reading. Reduced-motion lands it directly.
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const lean = market ? Math.max(-1, Math.min(1, market.lean || 0)) : 0;
  const rot = lean * 90;                                       // (frac-0.5)*180 == lean*90
  const [shownRot, setShownRot] = useState(reduced ? rot : 0);
  useEffect(() => {
    if (reduced) { setShownRot(rot); return; }
    const id = setTimeout(() => setShownRot(rot), 90);         // paint at 0, then sweep
    return () => clearTimeout(id);
  }, [rot, reduced]);

  if (!market) return html`
    <div class="card arc-card"><div class="card-head"><${Icon} name="compass" size=${15} /><span>Where you stand</span></div>
      <div class="caption" style=${{ padding: "var(--s4) var(--s2)" }}>
      Your overall position appears once enough of your data is comparable.</div></div>`;
  const v = market.verdict;                                   // "below" | "at" | "above"
  const T = market.lean_threshold || 0.25;                    // band join = verdict threshold
  const word = v === "above" ? "Above" : v === "below" ? "Below" : "On market";
  // traffic light: on=green (target), above=red (premium cost), below=amber (lagging)
  const wordCol = v === "below" ? "var(--neutral-perf)" : v === "above" ? "var(--unfavourable)" : "var(--favourable)";
  const needleCol = v === "below" ? "var(--amber-bright)" : v === "above" ? "var(--unfavourable)" : "var(--favourable)";
  const tipCol = v === "below" ? "#F8C24A" : v === "above" ? "#E07B72" : "#1D9E75";

  // geometry: semicircle, hub at base centre. frac 0=far below (left), 1=far
  // above (right). value v -> frac (v+1)/2. Heavier stroke for a substantial dial.
  const CX = 140, CY = 138, R = 102, W = 13;
  const capF = (W / 2 / R) / Math.PI, gapF = 0.02;
  const toFrac = (val) => (val + 1) / 2;
  const polar = (frac, r) => { const a = Math.PI * (1 - frac); return [CX + r * Math.cos(a), CY - r * Math.sin(a)]; };
  const arcPath = (f0, f1) => {
    const [x0, y0] = polar(f0, R), [x1, y1] = polar(f1, R);
    return "M " + x0.toFixed(1) + " " + y0.toFixed(1) +
      " A " + R + " " + R + " 0 " + ((f1 - f0) > 0.5 ? 1 : 0) + " 1 " + x1.toFixed(1) + " " + y1.toFixed(1);
  };
  const j1 = toFrac(-T), j2 = toFrac(T);                       // band joins at ±threshold
  // The band the needle rests in is the verdict — render it RICHER (the eye
  // lands on the answer); the dormant zones stay quiet. Active uses a 70% mix
  // of its hue, dormant the ~40% --gauge-* tokens.
  const rich = { below: "color-mix(in srgb, var(--amber-bright) 70%, var(--surface))",
                 at: "color-mix(in srgb, var(--favourable) 66%, var(--surface))",
                 above: "color-mix(in srgb, var(--unfavourable) 64%, var(--surface))" };
  const bands = [
    { k: "below", d: arcPath(capF, j1 - gapF), col: v === "below" ? rich.below : "var(--gauge-below)" },
    { k: "at", d: arcPath(j1 + gapF, j2 - gapF), col: v === "at" ? rich.at : "var(--gauge-on)" },
    { k: "above", d: arcPath(j2 + gapF, 1 - capF), col: v === "above" ? rich.above : "var(--gauge-above)" },
  ];
  // band-join ticks — notches where the colours meet (the verdict thresholds)
  const tick = (frac, r0, r1) => { const [ox, oy] = polar(frac, r0), [ix, iy] = polar(frac, r1); return { ox, oy, ix, iy }; };
  const joins = [tick(j1, R + 6, R - 6), tick(j2, R + 6, R - 6)];
  // minor graduations — a quiet inner scale, the precision-instrument cue.
  const MINOR = 24;
  const minors = [];
  for (let i = 1; i < MINOR; i++) {
    const f = capF + (i / MINOR) * (1 - 2 * capF);
    if (Math.abs(f - j1) < 0.02 || Math.abs(f - j2) < 0.02 || Math.abs(f - 0.5) < 0.02) continue;
    const long = (i % 4 === 0);
    minors.push(tick(f, R - 11, R - (long ? 17 : 14.5)));
  }
  const tipY = CY - (R - 7);
  // peer-median marker — frac 0.5 (net lean 0 = exactly the market middle), so
  // "you vs the median" is explicit. A small downward caret above the arc.
  const [mx, my] = polar(0.5, R + 13);
  const medD = "M " + (mx - 4).toFixed(1) + " " + (my - 6).toFixed(1) +
    " L " + (mx + 4).toFixed(1) + " " + (my - 6).toFixed(1) + " L " + mx.toFixed(1) + " " + my.toFixed(1) + " Z";
  // lean descriptor — turns the tilt into words (honest about a below-lean even
  // when the verdict is On market).
  const mag = Math.abs(lean);
  const leanWord = (() => {
    if (v === "at") {
      if (mag < 0.06) return "evenly balanced";
      return "slightly " + (lean < 0 ? "below" : "above") + "-leaning";
    }
    const past = mag - T;
    const strength = past > 0.2 ? "clearly" : past > 0.08 ? "moderately" : "marginally";
    return strength + " " + (v === "below" ? "below" : "above") + " the market";
  })();

  return html`
    <div class="card arc-card">
      <div class="card-spot" aria-hidden="true"></div>
      <div class="card-head"><${Icon} name="compass" size=${15} /><span>Where you stand</span></div>
      <div class="arc-stage">
        <svg viewBox="0 0 280 170" class="arc-svg" role="img"
          aria-label=${"Gauge: " + market.at + " of " + market.pool + " metrics on market, " + market.below + " below, " + market.above + " above. Overall: " + word + ", " + leanWord + ". The market median sits at centre."}>
          <defs>
            <filter id="needleShadow" x="-40%" y="-40%" width="180%" height="180%">
              <feDropShadow dx="0" dy="1.8" stdDeviation="2" flood-color="#211B26" flood-opacity="0.24"/>
            </filter>
            <radialGradient id="dialSheen" cx="50%" cy="92%" r="72%">
              <stop offset="0%" stop-color="#ffffff" stop-opacity="0.85"/>
              <stop offset="55%" stop-color="#ffffff" stop-opacity="0.28"/>
              <stop offset="100%" stop-color="#ffffff" stop-opacity="0"/>
            </radialGradient>
          </defs>
          ${/* radial sheen on the dial face — quiet dimensionality */ ""}
          <path d=${"M " + (CX - R - 9) + " " + CY + " A " + (R + 9) + " " + (R + 9) + " 0 0 1 " + (CX + R + 9) + " " + CY + " Z"}
            fill="url(#dialSheen)" opacity="0.6"/>
          <path d=${arcPath(capF, 1 - capF)} fill="none" stroke="var(--surface-sunk)" stroke-width=${W + 3} stroke-linecap="round"/>
          ${bands.map((b, i) => html`<path key=${i} d=${b.d} fill="none" stroke=${b.col} stroke-width=${W} stroke-linecap="round"
            pathLength="1" class="arc-band" style=${{ animationDelay: (140 + i * 120) + "ms" }}/>`)}
          <g class="arc-minors">
            ${minors.map((t, i) => html`<line key=${"m" + i} x1=${t.ox.toFixed(1)} y1=${t.oy.toFixed(1)} x2=${t.ix.toFixed(1)} y2=${t.iy.toFixed(1)}
              stroke="var(--ink-faint)" stroke-width="1" opacity="0.28"/>`)}
          </g>
          ${joins.map((t, i) => html`<line key=${"j" + i} x1=${t.ox.toFixed(1)} y1=${t.oy.toFixed(1)} x2=${t.ix.toFixed(1)} y2=${t.iy.toFixed(1)}
            stroke="var(--ink-faint)" stroke-width="1.25" opacity="0.55"/>`)}
          ${/* peer-median marker */ ""}
          <g class="arc-median">
            <path d=${medD} fill="var(--ink-soft)" opacity="0.7"><title>The market median sits at centre</title></path>
          </g>
          <g class="arc-needle" style=${{ transform: "rotate(" + shownRot.toFixed(2) + "deg)", transformOrigin: CX + "px " + CY + "px" }}>
            <circle class="arc-tip-glow" cx=${CX} cy=${tipY.toFixed(1)} r="5" fill=${tipCol} />
            <g filter="url(#needleShadow)">
              <path d=${"M " + CX + " " + CY + " L " + (CX - 3.4) + " " + (CY - 8) + " L " + CX + " " + tipY.toFixed(1) + " L " + (CX + 3.4) + " " + (CY - 8) + " Z"} fill=${needleCol}/>
              <circle cx=${CX} cy=${tipY.toFixed(1)} r="5" fill=${tipCol} stroke="var(--surface)" stroke-width="1.75"/>
            </g>
          </g>
          <circle cx=${CX} cy=${CY} r="8" fill="var(--surface)" stroke=${needleCol} stroke-width="3.25"/>
          <circle cx=${CX} cy=${CY} r="2.25" fill=${needleCol}/>
        </svg>
      </div>
      <div class="arc-verdict">
        <div class="arc-word num" style=${{ color: wordCol }}>${word}</div>
        <div class="arc-lean">${leanWord}</div>
      </div>
      <div class="arc-legend num">
        <span><span class="arc-leg-fig"><${CountUp} to=${market.below} /></span> Below</span>
        <span><span class="arc-leg-fig"><${CountUp} to=${market.at} /></span> On market</span>
        <span><span class="arc-leg-fig"><${CountUp} to=${market.above} /></span> Above</span>
      </div>
    </div>`;
}


const LENS_ICON = { save: "coins", attract: "magnet", retain: "anchor", engage: "heart" };
const CAT_ICON = { "Pay": "coins", "Incentives": "trending-up", "Benefits": "shield",
  "Time Off": "sun", "Wellbeing": "heart", "Recognition": "award", "Governance": "list-checks" };
function SignalsPanel({ signals, locked, contribution }) {
  const sigs = signals || [];
  return html`
    <div class="card signals-card">
      <div class="card-spot" aria-hidden="true"></div>
      <div class="card-head">
        <${Icon} name="flag" size=${15} />
        <span>Signals${sigs.length ? " · " + sigs.length : ""}</span>
        <span class="sig-head-note">flags worth a look — peer facts, never advice</span>
      </div>
      ${locked ? html`
        <div class="insight-lock" style=${{ marginTop: "8px", flex: 1 }}>
          <div class="blurred" aria-hidden="true">
            ${[1, 2, 3].map(i => html`<div key=${i} class="signal-row"><span class="signal-val">£—k</span><span class="caption">a flag appears here once unlocked</span></div>`)}
          </div>
          <div class="lock-note">
            <${Chip} kind="accent"><${Icon} name="lock" size=${11} /> Locked<//>
            <div class="caption" style=${{ textAlign: "center", maxWidth: "260px" }}>
              Signals unlock with your insights — complete your key reward questions${contribution && contribution.days_left != null ? ` (${contribution.days_left} days left)` : ""}.</div>
            <button class="btn small primary" onClick=${() => nav("/your-data/submit")}>Submit data</button>
          </div>
        </div>` :
      sigs.length === 0 ? html`
        <div class="signals-empty">
          <span class="signals-empty-ring"><${Icon} name="flag" size=${18} /></span>
          <div class="caption" style=${{ maxWidth: "320px" }}>No flags right now — nothing in your data crosses a signal threshold. They'll appear here as your position or the market moves.</div>
        </div>` :
      [html`<div class="signals-list" key="list">
        ${sigs.map((s, i) => html`
          <div key=${i} class=${"signal-row lens-" + s.lens} onClick=${() => openMetric(s.question_id)} role="button" tabindex="0">
            <span class="signal-roundel"><${Icon} name=${LENS_ICON[s.lens] || "flag"} size=${16} /></span>
            <span class="signal-val num">${s.value_display}</span>
            <span class="signal-detail" title=${s.detail}>${s.label_short || s.detail}</span>
            <span class="lens-tag">${s.lens}</span>
            <span class="signal-go" aria-hidden="true">→</span>
          </div>`)}
      </div>`,
      html`<div class="signals-foot" key="foot">
        <span>Tap a flag to open the metric behind it.</span>
        <a href="#/priorities">See all priorities →</a>
      </div>`]}
    </div>`;
}

function CategoryTile({ d }) {
  const post = d.position || d.market;
  const verdict = post ? post.verdict : null;
  const ev = d.position_evidence;
  const indicative = d.position_basis === "indicative";
  const evCount = ev ? ev.polarised + ev.practice : 0;
  const evNote = ev ? ("based on " + evCount + " positioned metric" + (evCount === 1 ? "" : "s") +
    (indicative ? " — indicative, not a full market verdict" : "")) : "";
  // pay-positioning traffic light (David, 2026-06-12): at market = green
  // (aligned), above = red (premium cost), below = amber (lagging)
  const col = verdict === "below" ? "var(--amber-bright)" : verdict === "above" ? "var(--unfavourable)"
    : verdict ? "var(--favourable)" : "var(--you)";
  const chip = verdict === "below" ? "below" : verdict === "above" ? "above" : verdict ? "on market" : "practice view";
  const chipCls = verdict === "below" ? "chip-mid" : verdict === "above" ? "chip-bad" : verdict ? "chip-good" : "chip-practice";
  const vCls = verdict === "below" ? "v-below" : verdict === "above" ? "v-above" : verdict ? "v-at" : "v-practice";
  const prev = d.prevalence || {};
  const dot = d.dot;
  return html`
    <div class=${"card cat-tile " + vCls} onClick=${() => nav("/benchmark?cat=" + encodeURIComponent(d.name))} role="button" tabindex="0">
      <span style=${{ display: "inline-flex", alignItems: "center", gap: "8px", fontWeight: 600, fontSize: "13px" }}>
        <span class="cat-icon"><${Icon} name=${CAT_ICON[d.name] || "award"} size=${14} /></span>${d.name}</span>
      <span class="row" style=${{ gap: "5px", alignSelf: "flex-start", alignItems: "center" }}>
        <span class=${"chip tile-chip " + chipCls + (indicative ? " chip-indicative" : "")} title=${evNote}>${chip}</span>
        ${indicative && html`<span class="indic-flag" title=${evNote}>≈ indicative</span>`}
      </span>
      ${dot != null ? html`
        <div class="tile-band" style=${{ margin: 0 }}>
          <div class="tile-band-mid"></div>
          <div class="band-tick"></div>
          <div class="tile-dot" style=${{ left: "calc(" + Math.min(97, Math.max(3, dot)) + "% - 6px)", background: col }}></div>
        </div>` : html`
        <div class="tile-band" style=${{ margin: 0 }}>
          <div class="tile-fill" style=${{ width: (prev.pool ? Math.round(100 * prev.with_majority / prev.pool) : 0) + "%" }}></div>
        </div>`}
      <div class="row spread" style=${{ minHeight: "18px" }}>
        <span class="caption num" title="practices in line with the peer majority">${prev.with_majority != null ? prev.with_majority + "/" + prev.pool : ""}</span>
      </div>
    </div>`;
}

function ChipColumn({ title, items, good }) {
  return html`
    <div class="card" style=${{ padding: "var(--s4)" }}>
      <div class="caption" style=${{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px",
        color: good ? "var(--favourable)" : "var(--unfavourable)", fontWeight: 650 }}>
        <${Icon} name=${good ? "star" : "target"} size=${14} /> ${title}</div>
      ${(items || []).length === 0 ? html`<div class="caption" style=${{ color: "var(--ink-faint)" }}>Nothing stands out in this peer group yet.</div>` :
      items.map((it, i) => html`
        <div key=${i} class="chip-row" onClick=${() => openMetric(it.question_id)} role="button" tabindex="0">
          <span class="chip-label">${it.label}</span>
          <span class="chip-band"><span class="band-tick"></span><span class="tile-dot" style=${{ left: "calc(" + Math.min(96, Math.max(2, it.adjusted)) + "% - 5px)", background: good ? "var(--favourable)" : "var(--unfavourable)", width: "10px", height: "10px", top: "-2.5px" }}></span></span>
          <span class=${"num p-pill " + (good ? "good" : "bad")}>P${Math.round(it.percentile)}</span>
        </div>`)}
    </div>`;
}


/* The two-signal hero. Market position carries a verdict (performance
   palette); practice prevalence is information (neutral palette, never
   red/amber/green — "less common" is not "bad"). */
const MARKET_LABEL = { above: "Above market", at: "On market", below: "Below market" };
const MARKET_KIND = { above: "good", at: "mid", below: "bad" };
const MARKET_ARROW = { above: "▲", at: "●", below: "▼" };

function MarketPill({ m, lg }) {
  if (!m) return null;
  return html`<span class=${"pos-pill " + (lg ? "lg " : "") + MARKET_KIND[m.verdict]}
    title=${`${m.above} above · ${m.at} at · ${m.below} below market, across ${m.pool} comparable positioned metrics`}>
    ${MARKET_ARROW[m.verdict]} ${MARKET_LABEL[m.verdict]}</span>`;
}

function PrevLine({ p, compact }) {
  if (!p) return html`<span class="caption">no comparable practices yet</span>`;
  return html`<span class=${"prev-line" + (compact ? " caption" : "")}>
    <b class="num">${p.with_majority}</b> of ${p.pool} practices with the peer majority${p.less_common ? html` · <b class="num">${p.less_common}</b> less common` : ""}</span>`;
}

window.HeroSignals = function ({ hero, cut, cuts }) {
  if (!hero) return null;
  const m = hero.market;
  const noData = !m && !hero.prevalence;
  return html`
    <div style=${{ flex: "1.9 1 340px", minWidth: "320px" }}>
      <div class="eyebrow">Where you stand · ${cutLabelOf(cut, cuts)}</div>
      ${noData ? html`
        <div style=${{ marginTop: "6px" }}>
          <b style=${{ fontFamily: "var(--font-head)", fontSize: "var(--fs-h3)" }}>Answer your reward data to see where you stand.</b>
          <div class="caption" style=${{ marginTop: "4px" }}>No verdict is shown until it can be computed from your own answers.</div>
        </div>` : html`
        <div class="row" style=${{ gap: "var(--s3)", alignItems: "center", margin: "6px 0 2px" }}>
          ${m ? html`<${MarketPill} m=${m} lg=${true} />` : html`<span class="caption">Not enough positioned metrics for a market verdict yet.</span>`}
          ${m && html`<span class="caption num">${m.above} above · ${m.at} at · ${m.below} below, of ${m.pool} positioned metrics</span>`}
        </div>
        <div style=${{ marginBottom: "var(--s3)" }}><${PrevLine} p=${hero.prevalence} compact=${true} /></div>
        <div class="domain-rows">
          ${hero.domains.map(d => html`
            <div key=${d.name} class="domain-row" onClick=${() => nav("/benchmark?cat=" + encodeURIComponent(d.name))}>
              <span class="domain-name">${d.name}</span>
              ${d.market ? html`<${MarketPill} m=${d.market} />` :
                d.prevalence || d.polarised_comparable ? html`<span class="chip" title="Too few polarised metrics for an honest market verdict — practice comparison only">practice view</span>` :
                html`<span class="caption">not enough comparable data yet</span>`}
              <span class="domain-prev"><${PrevLine} p=${d.prevalence} compact=${true} /></span>
            </div>`)}
        </div>`}
    </div>`;
};

function jumpToItem(item) { if (item) openMetric(item.question_id); }

window.OpportunityTile = function ({ opp, contrib, actionGaps }) {
  if (!opp) return null;
  if (opp.locked) return html`
    <div class="opp-hero insight-lock">
      <div class="eyebrow">Total identified opportunity</div>
      <div class="blurred" aria-hidden="true">
        <div class="metric-value lg" style=${{ color: "var(--blue)" }}>£———<span class="unit">/yr</span></div>
        <div class="caption">what closing your gaps to the peer median is worth</div>
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
            html`potential savings if you matched the peer median${opp.total_investment_to_p50_gbp ? html` — plus ${fmtGBPCompact(opp.total_investment_to_p50_gbp)}/yr to close benefit gaps` : ""}` :
            opp.total_investment_to_p50_gbp > 0 ? "what it would take to close your benefit gaps to the peer median" : "no gaps to the peer median identified"}</div>
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
        ${actionGaps > 0 && html`<div class="caption" style=${{ marginTop: "6px", paddingTop: "6px", borderTop: "1px solid var(--border)" }}>
          Plus <a href="#/priorities"><b class="num">${actionGaps}</b> practice gaps</a> where most peers do something you don't — the non-£ to-do list.</div>`}` :
      html`<div class="caption" style=${{ marginTop: "6px" }}>Declare your FTE band in <a href="#/your-data/submit">your submission</a> to size the £ opportunity of closing gaps to the peer median.</div>`}
    </div>`;
};

window.TrajectoryTile = function ({ movement }) {
  return html`
    <div style=${{ flex: "1 1 190px", minWidth: "190px", borderLeft: "1px solid var(--border)", paddingLeft: "var(--s5)", display: "flex", flexDirection: "column" }}>
      <div class="caption" style=${{ fontWeight: 650, textTransform: "uppercase", letterSpacing: ".06em" }}>Your journey</div>
      <svg viewBox="0 0 170 44" style=${{ width: "170px", display: "block", margin: "10px 0 6px" }}>
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
  const ui = (prefs && prefs._ui_section) || {};
  const [cat, setCatRaw] = useState(ui.cat || "");
  const setCat = v => { setCatRaw(v); onPref && onPref("_ui_section", { ...ui, cat: v }); };

  useEffect(() => {
    setData(null); setErr(null);
    api(`/api/benchmarks/${encodeURIComponent(sp)}?` + cutQS(cut)).then(setData).catch(e => setErr(e.message));
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

          </div>
        </div>
      </div>
      ${cards.length === 0 && html`<${EmptyState} title="Nothing matches these filters"
        body="Try clearing the category filter." action=${html`<button class="btn small" onClick=${() => setCat("")}>Clear filter</button>`} />`}
      ${bySub.map(g => html`
        <div key=${g.sub} style=${{ marginBottom: "var(--s5)" }}>
          ${!subF && html`<h2 class="section-title">${g.sub}</h2>`}
          <div class="bench-grid">
            ${g.cards.map(c => html`
              <div key=${c.id} id=${"q-" + c.id}>
                <${BenchmarkCard} card=${c} prefs=${prefs} onPref=${onPref} onPin=${onPin}
                  pinned=${pinnedIds.has(c.id)} cuts=${cuts} globalCut=${cutKeyOf(cut)}
                  window=${me.peer_pool && me.peer_pool.collection_window} highlight=${focusQ === c.id} />
              </div>`)}
          </div>
        </div>`)}
    </div>`;
};

// ----------------------------------------------------------- my view -------
window.MyViewPage = function ({ me, cut, cuts, prefs, onPref }) {
  const [layout, setLayout] = useState(null);
  const [source, setSource] = useState(null);
  const [cards, setCards] = useState({});
  const [drag, setDrag] = useState(null);
  const [saved, setSaved] = useState(null);
  useEffect(() => { api("/api/myview").then(d => { setLayout(d.layout); setSource(d.source); }); }, []);
  useEffect(() => {
    if (!layout) return;
    layout.forEach(slot => {
      const key = slotKey(slot);
      if (cards[key]) return;
      const c = slot.cut || cut;
      api(`/api/benchmark/${slot.question_id}?` + cutQS(c))
        .then(d => setCards(prev => ({ ...prev, [key]: d })))
        .catch(() => setCards(prev => ({ ...prev, [key]: { error: true } })));
    });
  }, [layout, cutKeyOf(cut)]);
  if (!layout) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;

  const persist = async (next) => {
    setLayout(next);
    await api("/api/myview", { method: "PUT", body: { layout: next } });
  };
  const remove = qid => persist(layout.filter(s => s.question_id !== qid));
  const resize = (qid, size) => persist(layout.map(s => s.question_id === qid ? { ...s, size } : s));
  const onDrop = idx => {
    if (drag === null || drag === idx) { setDrag(null); return; }
    const next = [...layout];
    const [moved] = next.splice(drag, 1);
    next.splice(idx, 0, moved);
    setDrag(null);
    persist(next);
  };
  const saveDefault = async () => {
    await api("/api/myview/save-default", { method: "POST", body: { layout } });
    setSaved("Saved as your organisation's default view");
    setTimeout(() => setSaved(null), 2500);
  };
  return html`
    <div>
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <h1 class="display-title">My view</h1>
          <div class="caption" style=${{ marginTop: "4px" }}>
            ${source === "starter" ? "A starter view of your 8 biggest gaps and 4 biggest strengths — pin any card from anywhere in lumi (☆), drag to reorder, resize, or remove." :
            source === "org_default" ? "Your organisation's default view — make it your own by pinning, dragging and resizing." :
            "Your pinned view. Drag to reorder; cards keep their own peer-group and chart settings."}
          </div>
        </div>
        <div class="row">
          ${saved && html`<${Chip} kind="good">${saved}<//>`}
          ${me.user.role === "admin" && html`<button class="btn" onClick=${saveDefault} title="New team members will inherit this layout">Save as team default</button>`}
        </div>
      </div>
      ${layout.length === 0 && html`<${EmptyState} icon="star" title="Nothing pinned yet"
        body="Use the star on any benchmark card to pin it here."
        action=${html`<button class="btn small" onClick=${() => nav("/overview")}>Back to overview</button>`} />`}
      <div class="bench-grid">
        ${layout.map((slot, i) => {
          const c = cards[slotKey(slot)];
          return html`
          <div key=${slotKey(slot)} draggable="true" class=${drag === i ? "dragging" : ""}
            onDragStart=${() => setDrag(i)} onDragOver=${e => e.preventDefault()} onDrop=${() => onDrop(i)}
            style=${slot.size === 2 ? { gridColumn: "span 2" } : null}>
            ${!c ? html`<${SkeletonCard} />` :
            c.error ? html`<div class="card bench-card"><${EmptyState} title="Couldn't load this card" /></div>` :
            html`<div style=${{ position: "relative" }}>
              <${BenchmarkCard} card=${c} prefs=${prefs} onPref=${onPref} size=${slot.size}
                onPin=${() => remove(slot.question_id)} pinned=${true} cuts=${cuts} globalCut=${cutKeyOf(cut)} />
              <div class="no-print" style=${{ position: "absolute", bottom: "8px", right: "10px", display: "flex", gap: "2px" }}>
                <button class="iconbtn" title="Card width" onClick=${() => resize(slot.question_id, slot.size === 2 ? 1 : 2)}>${slot.size === 2 ? "1×" : "2×"}</button>
                <span class="iconbtn" title="Drag to reorder" style=${{ cursor: "grab" }}>⠿</span>
              </div>
            </div>`}
          </div>`;
        })}
      </div>
    </div>`;
};
function slotKey(slot) { return slot.question_id + "|" + (slot.row_id || "") + "|" + JSON.stringify(slot.cut || {}); }

// ----------------------------------------------------------- my data -------
/* Your data (chrome spec section 1.3): ONE destination for the org's data —
   view/manage (the old My data) with Submit as the primary action inside the
   page, role-gated (hidden, not disabled, for viewers). */
window.YourDataPage = function ({ me }) {
  const [data, setData] = useState(null);
  const [qstr, setQ] = useState("");
  useEffect(() => { api("/api/my-data").then(setData); }, []);
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  const ql = qstr.toLowerCase();
  const rows = data.rows.filter(r => !ql || (r.title + " " + r.question + " " + (r.matrix_row || "") + " " + r.value).toLowerCase().includes(ql));
  const focused = window.SCOPE && window.SCOPE.focused;
  const bySp = [];
  for (const r of rows) {
    const key = focused ? (r.subpower || "General") : r.superpower;
    let g = bySp.find(g => g.sp === key);
    if (!g) { g = { sp: key, sup: r.superpower, rows: [] }; bySp.push(g); }
    g.rows.push(r);
  }
  if (focused) bySp.sort((a, b) => secOrder(a.sp) - secOrder(b.sp));
  return html`
    <div>
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <h1 class="display-title">Your data</h1>
          <div class="caption" style=${{ marginTop: "4px" }}>Everything your organisation has submitted (${data.rows.length} answers). Only your team can see this.</div>
        </div>
        <div class="row" style=${{ gap: "var(--s3)" }}>
          <input class="ctl" placeholder="Search your answers…" value=${qstr} onInput=${e => setQ(e.target.value)} />
          ${me && (me.user.role === "admin" || me.user.role === "contributor") &&
            html`<button class="btn primary" onClick=${() => nav("/your-data/submit")}><${Icon} name="pencil" size=${14} /> Submit data</button>`}
        </div>
      </div>
      ${rows.length === 0 && html`<${EmptyState} title="No answers match" body="Try a different search term." />`}
      ${bySp.map(g => html`
        <div key=${g.sp} class="card" style=${{ marginBottom: "var(--s4)", padding: "var(--s4)" }}>
          <h2 class="section-title" style=${{ display: "flex", alignItems: "center", gap: "8px" }}>${window.SCOPE && window.SCOPE.focused ? "" : html`<${SpIcon} sp=${g.sp} />`} ${g.sp} <span class="caption">(${g.rows.length})</span></h2>
          <table class="data">
            <thead><tr><th>Benchmark</th><th>Level / row</th><th class="num">Your answer</th></tr></thead>
            <tbody>
              ${g.rows.map((r, i) => html`
                <tr key=${i}>
                  <td title=${r.question}>${r.title}</td>
                  <td>${r.matrix_row || "—"}</td>
                  <td class="num"><b>${formatAnswer(r)}</b></td>
                </tr>`)}
            </tbody>
          </table>
        </div>`)}
    </div>`;
};
function formatAnswer(r) {
  if (r.type === "numeric" || r.type === "matrix") {
    const f = parseFloat(String(r.value).replace(/[£,%]/g, ""));
    if (!isNaN(f)) return fmtValue(f, r.unit);
  }
  return r.value;
}

// -------------------------------------------------------- methodology ------
window.MethodologyPage = function () {
  const [m, setM] = useState(null);
  useEffect(() => { api("/api/methodology").then(setM); }, []);
  if (!m) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  const industries = Object.keys(m.composition);
  return html`
    <div style=${{ maxWidth: "880px" }}>
      <h1 class="display-title">Methodology</h1>
      <p class="caption">Benchmark snapshot dated ${m.snapshot_date} · collection window ${m.collection_window} · methodology v1</p>

      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Who you're compared with</h2>
        ${m.synthetic_pool && html`
          <div style=${{ background: "var(--neutral-perf-tint)", borderRadius: "var(--radius-sm)", padding: "var(--s3) var(--s4)", marginBottom: "var(--s3)", fontSize: "var(--fs-body)" }}>
            <b>Illustrative sample data.</b> The current benchmark pool is <b>synthetic seed data</b>: 220 simulated
            organisations whose answers were generated from published UK HR and reward norms and each organisation's
            firmographic profile, pending real member submissions. It is designed to behave believably for
            demonstration and launch seeding — it is not real member data and must not be cited as a market statistic.
          </div>`}
        <p>The peer group contains <b>${m.peer_pool.responding_orgs} UK organisations</b> that have completed a lumi benchmark submission.
        ${m.peer_pool.classified_orgs} carry full firmographic profiles (sector, size, region, ownership) and appear in filtered peer
        groups; ${m.unclassified_count} are awaiting classification, stay in the "All peers" group only, and are shown as "Unclassified".</p>
        <table class="data" style=${{ marginTop: "10px" }}>
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

      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">The question set and how insights unlock</h2>
        <p>Your reward benchmark is <b>one flat set of ${(window.SCOPE || {}).question_count || 180} questions</b>,
        organised by section (Pay, Benefits, Incentives, Transparency, Progression). There are no membership tiers —
        every member sees and can answer every question.</p>
        <p><b>Unlocking your insights.</b> The £ opportunity, board pack and biggest-gaps views unlock when you have
        answered your <b>key reward questions</b> — the subset flagged as applying to every organisation. Selecting
        “Not applicable” or “Don't know” <b>counts as answering</b>: engaging with a question that doesn't apply to
        you is a complete answer, so an organisation can never be locked out by questions that don't apply to it.
        A multi-row (matrix) question counts once. The same completion drives the 30-day contribution clock that
        starts when your Admin accepts the Data Contribution Terms.</p>
      </div>

      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">How the numbers are calculated</h2>
        <p><b>Percentiles.</b> P10, P25, P50 (median), P75 and P90 are calculated with linear interpolation across all
        valid peer answers — the same method used by the main survey houses. We benchmark on medians rather than
        averages so a single unusual organisation cannot skew a figure.</p>
        <p><b>Small-sample protection.</b> Any figure that would rest on fewer than ${m.suppression_floor} organisations is not shown.
        You will see "not enough organisations to show this safely" instead. This rule applies to every peer group —
        including bespoke groups such as Peer Twin — and is enforced in one place in the calculation engine.</p>
        <p><b>Multiple-choice questions.</b> Distributions show the share of answering organisations choosing each option.
        For "select all that apply" questions, the denominator is the number of organisations that answered the question
        — so percentages can sum to more than 100.</p>
        <p><b>Favourable vs peers.</b> Each question carries a polarity: higher is better (e.g. offer acceptance rate),
        lower is better (e.g. regretted attrition), or neutral (e.g. salary increase budget, where "better" depends on
        strategy). Green/amber/red colouring is polarity-adjusted and is never applied to neutral metrics.</p>
        <p><b>Practice adoption.</b> We treat a practice or policy as <b>in place</b> when an organisation gives a real,
        substantive answer — any genuine frequency, approach or level counts (reviewing pay quarterly is a pay review cycle).
        Only explicit absence answers ("No", "None", "No formal policy", "Never") count as <b>not in place</b>;
        clearly partial answers ("Partially", "In development") count as <b>partly in place</b>; and "Don't know" or
        "Not applicable" answers are excluded rather than counted against anyone. Peer adoption is the share of
        assessable answers that are at least partly in place, under the same rule.</p>
        <p><b>Your percentile.</b> Your P-number is the share of peer organisations whose value sits below yours
        (ties counted half), so P63 means you are higher than about 6 in 10 peers.</p>
      </div>

      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Where the data comes from</h2>
        <p>This snapshot ingested ${m.reconciliation.files} member submissions (${(m.reconciliation.answer_rows || 0).toLocaleString("en-GB")} answers).
        ${m.reconciliation.matched_orgs} organisations were matched to the lumi member registry by normalised company name;
        ${m.reconciliation.file_only_orgs} submissions without a registry profile are retained in "All peers" as Unclassified;
        ${m.reconciliation.registry_only_orgs} registry members have not yet submitted and are excluded from every aggregate.
        Near-miss name matches are flagged for human review and never joined automatically. New members declare their own
        firmographics at sign-up, which removes this reconciliation step for future windows.</p>
        <p><b>Snapshots.</b> Every collection window is stored as a separate snapshot; submissions are versioned and never
        overwrite history. From your second window onwards, movement ("vs last period") appears on each benchmark card and
        the trajectory module.</p>
        <p><b>£ modelling assumptions.</b> Opportunity figures use FTE band midpoints
        (${Object.entries(m.assumptions.fte_band_midpoints || {}).map(([k, v]) => `${k}: ${v.toLocaleString("en-GB")}`).join("; ")}),
        a UK all-sector median salary of £${(m.assumptions.median_salary_gbp || 0).toLocaleString("en-GB")} (editable in Settings),
        a cost per leaver of ${m.assumptions.cost_per_leaver_pct_salary}% of salary and an agency premium of
        ${m.assumptions.agency_premium_pct}%. They are assumptions, clearly labelled, and every £ figure is indicative.</p>
      </div>

      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Glossary</h2>
        ${Object.entries(GLOSSARY).map(([k, v]) => html`
          <p key=${k} style=${{ margin: "6px 0" }}><b style=${{ textTransform: "capitalize" }}>${k}.</b> ${v}</p>`)}
        <p style=${{ margin: "6px 0" }}><b>Peer Twin.</b> A bespoke peer group of the organisations most similar to yours across
        industry, size, ownership and workforce shape. The group is recalculated as the membership grows; member names are never shown.</p>
        <p style=${{ margin: "6px 0" }}><b>Polarity.</b> Whether a higher value is favourable, unfavourable, or neither, for colour-coding your position.</p>
      </div>
    </div>`;
};

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
  if (!m) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
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

        <div class="card how-card" id="who-compared">
          <h3 class="section-title">Who you're compared with (peer norms)</h3>
          ${m.synthetic_pool && html`
            <div class="how-note">
              <b>Illustrative sample data.</b> The current benchmark pool is <b>synthetic seed data</b>: ${m.peer_pool.responding_orgs} simulated
              organisations whose answers were generated from published UK HR and reward norms and each organisation's
              firmographic profile, pending real member submissions. It behaves believably for demonstration and launch
              seeding — it is not real member data and must not be cited as a market statistic.
            </div>`}
          <p>A peer norm is built only from organisations that have completed a lumi submission. The pool holds
          <b>${m.peer_pool.responding_orgs} UK organisations</b>; ${m.peer_pool.classified_orgs} carry full firmographic
          profiles (sector, size, region, ownership) and appear in filtered peer groups, while ${m.unclassified_count}
          await classification and sit in the "All peers" group only.</p>
          <table class="data" style=${{ marginTop: "10px" }}>
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
          <p><b>Favourable vs peers.</b> Each question carries a polarity — higher is better, lower is better, or
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
            <p key=${k} style=${{ margin: "6px 0" }}><b style=${{ textTransform: "capitalize" }}>${k}.</b> ${v}</p>`)}
          <p style=${{ margin: "6px 0" }}><b>Peer Twin.</b> A bespoke peer group of the organisations most similar to yours
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
            <p class="caption" style=${{ marginTop: "10px" }}>Admins: the question-set release console — current release, change
            log and backlog — lives in <a href="#/governance">the governance console</a>.</p>`}
        </div>

        ${/* ---------- §4.3 Legal ---------- */ ""}
        <h2 class="how-section-head" id="legal">Legal</h2>
        <div class="card how-card">
          <p class="caption">Each document is its own page; this is the index. All documents are currently
          <span class="chip warn">DRAFT — pending legal review</span>.</p>
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
        <div class="caption" style=${{ marginBottom: "6px" }}>
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
      <div class="caption">Peer median by collection period · question ${t.question_version || ""}. A reset marks a
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
  if (!g) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
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
        ${g.current_release && g.current_release.notes && html`<div class="caption" style=${{ marginTop: "4px" }}>${g.current_release.notes}</div>`}
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
        <div class="row" style=${{ gap: "8px", margin: "8px 0" }}>
          <input style=${{ flex: 1, height: "34px", padding: "0 10px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)" }}
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
