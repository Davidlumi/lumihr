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
// Masthead CONFIDENCE badge (2026-07-09 chip; COMPACTED to a 10-point rating 2026-07-12,
// David: "just the icon … a 10 rating scale with colour coding"). The single trust surface:
// an always-on badge (once insights unlock) rating the ACTIVE peer set by its live n. The
// 10-point score is ANCHORED to the published tiers — never invented: >=20 peers (the "High
// confidence" tier) spans 7–10 (green); 5–19 ("Directional") spans 4–6 (amber); below 5 the
// cut is suppressed server-side, so the red 1–3 band never renders on a live surface (it
// exists for completeness). Monotonic in n; the full sentence lives in the tooltip + aria.
// NOTE: RAG on a trust surface reverses the 2026-07-09 navy-only ruling — David's explicit
// call ("will leave with you"). The words stay tier-true so methodology copy still holds.
function ConfidenceChip({ n, window: win }) {
  const cs = confScore(n);   // the ONE score rule (core.js) — shared with the board pack
  if (!cs) return null;
  const score = cs.score, band = cs.band;
  const tip = "Confidence " + score + "/10 — " + n + " peer organisations behind this comparison. "
    + "20 or more peers rates 7–10 (high confidence); 5–19 rates 4–6 (directional — treat as a "
    + "steer, not a verdict); fewer than 5 is never shown."
    + (win ? " " + win + " baseline — movement shows from your next cycle." : "");
  return html`
    <span class=${"conf-chip conf-" + band} tabindex="0" role="note" aria-label=${tip}
      onKeyDown=${e => { if (e.key === "Escape") e.currentTarget.blur(); }}>
      <span class="conf-meter" aria-hidden="true"><i></i><i class=${score >= 4 ? "" : "off"}></i><i class=${score >= 7 ? "" : "off"}></i></span>
      <span class="conf-score num">${score}/10</span>
      <span class="indic-tip">${tip}</span>
    </span>`;
}
window.OverviewPage = function ({ me, refreshMe, cut, cuts, prefs, onPref, onPin, pinnedIds, onCut, onTwinInfo }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  // Home dashboard lens (persisted in prefs._overview): MARKET view (gauge + below/
  // on/above) vs PRACTICE view (how you operate — the differ/approach read), and
  // whether the reward-strategy stance is APPLIED. Strategy-off re-fetches the
  // overview WITHOUT the lens (absolute colours, impact-ordered signals, plain verdict).
  const _ov = (prefs && prefs._overview) || {};
  const [view, setViewState] = useState(_ov.view === "practice" ? "practice" : "market");
  const [applyStrat, setApplyState] = useState(_ov.apply_strategy !== false);
  // domain-bar mode (David 2026-07-11: "we still need the stacked bars ... implement a toggle"):
  // "counts" = the ratified count-proportional stacked bar; "position" = the fixed-band
  // percentile bar with the true-P marker. Per-user, persisted with the other lens prefs.
  const [barMode, setBarModeState] = useState(_ov.bar === "position" ? "position" : "counts");
  const setView = (v) => { setViewState(v); onPref("_overview", { view: v, apply_strategy: applyStrat, bar: barMode }); };
  const setApplyStrat = (b) => { setApplyState(b); onPref("_overview", { view, apply_strategy: b, bar: barMode }); };
  const setBarMode = (m) => { setBarModeState(m); onPref("_overview", { view, apply_strategy: applyStrat, bar: m }); };
  // Ship review 2026-07-09 Pack 1 §3: prefs arrive async (GET /api/prefs lands after
  // mount), so the one-shot useState initializers above read {} on a cold load / deep
  // link and silently discard a saved practice-view / strategy-off choice. Sync the
  // lens state from the pref once it lands — idempotent: a user toggle writes the pref
  // via onPref, so the echo re-set is a no-op re-assign of the same value.
  useEffect(() => {
    setViewState(_ov.view === "practice" ? "practice" : "market");
    setApplyState(_ov.apply_strategy !== false);
    setBarModeState(_ov.bar === "position" ? "position" : "counts");
  }, [_ov.view, _ov.apply_strategy, _ov.bar]);
  const [retryKey, setRetryKey] = useState(0);
  useEffect(() => {
    // Ship review 2026-07-09 B4 (cut-switch race): the live-flag guard — the house
    // pattern from DomainSummary/MetricPage/BenchmarkCard — so a slow older response
    // can never land after a newer cut's fetch and render the wrong peer group's
    // numbers under the new cut's label.
    let live = true;
    setData(null); setErr(null);
    apiCached("/api/overview?" + cutQS(cut) + (applyStrat ? "" : "&strategy=off"))
      .then(d => { if (live) setData(d); }).catch(e => { if (live) setErr(e.message); });
    return () => { live = false; };
  }, [cutKeyOf(cut), applyStrat, retryKey]);
  if (err) return html`<${EmptyState} title="Couldn't load the overview"
    body=${err + " — nothing is lost; it usually works on a retry."}
    action=${html`<button class="btn small primary" onClick=${() => setRetryKey(k => k + 1)}>Retry</button>`} />`;
  if (!data) return html`
    <div>
      <div class="skel" style=${{ height: "30px", width: "320px", marginBottom: "var(--s3)" }}></div>
      <div class="skel" style=${{ height: "20px", width: "480px", marginBottom: "var(--s4)" }}></div>
      <div class="skel" style=${{ height: "180px", marginBottom: "var(--s4)", borderRadius: "var(--radius)" }}></div>
      <${SkeletonGrid} count=${3} />
    </div>`;
  const h = data.headline;
  const pctAbove = h.comparable_metrics ? Math.round(100 * h.above_median / h.comparable_metrics) : 0;
  // Single source of truth for peer-sample confidence: the masthead ConfidenceChip
  // (2026-07-09 — replaced the "Benchmarked against…" subtitle AND the thin-sample
  // caveat as the one trust surface; David: "the sample should have its own area with
  // a confidence rating"). Gauge / cards / panels / signals render nothing extra.
  // Gated on insights unlocked so it never stacks on the data-pending gauge (below
  // the 90% gate). Thresholds unchanged: >=20 High, [5, 20) Directional, below 5 a
  // cut is fully suppressed (= SUPPRESSION_FLOOR, DECISIONS.md).
  const unlocked = !!(data.contribution && data.contribution.insights_unlocked);
  const sampleN = cutSize(cut, cuts, me.peer_pool);
  return html`
    <div>
      <div class="hero">
        <div class="hero-title-wrap">
          <h1 class="display-title">${data.org.name}</h1>
        </div>
        <div class="hero-actions">
          ${/* SPATIAL restructure (2026-07-12, David: "still very cramped"): the title line
                keeps ONLY the two actions — the peer capsule + confidence chip moved down into
                the full-width context toolbar (ov-controls), where the row's width separates
                peer context (left) from the view lenses (right) instead of piling five bordered
                shapes against the right edge. */ ""}
          <${ExportBoardPack} me=${me} cut=${cut} />
          <${ShareButton} me=${me} cut=${cut} name=${data.org && data.org.name} />
        </div>
      </div>

      ${data.contribution && !data.contribution.insights_unlocked && !data.contribution.reduced &&
        html`<${WelcomeHero} contrib=${data.contribution} pool=${data.peer_pool} me=${me} />`}

      ${unlocked && !(prefs && prefs._seen && prefs._seen.unlock) &&
        html`<${UnlockMoment} onDismiss=${() => onPref && onPref("_seen", { ...((prefs && prefs._seen) || {}), unlock: true })} />`}

      <${OverviewHero} data=${data} cut=${cut} cuts=${cuts} orgKey=${me.org && me.org.name}
        view=${view} applyStrat=${applyStrat} setView=${setView} setApplyStrat=${setApplyStrat}
        barMode=${barMode} setBarMode=${setBarMode}
        me=${me} onCut=${onCut} onTwinInfo=${onTwinInfo} prefs=${prefs} onPref=${onPref} refreshMe=${refreshMe}
        sampleN=${sampleN} unlocked=${unlocked} />

    </div>`;
};

// Org-wide unlock moment: insights unlock for the WHOLE organisation the moment
// one member submits (sticky, server-stamped) — so every OTHER member next signs
// in to a silently different product. This one-time, per-user (prefs._seen.unlock)
// banner introduces the three things that just came alive. Shown to whoever hasn't
// dismissed it, not only the person who clicked Submit.
window.UnlockMoment = function ({ onDismiss }) {
  return html`
    <div class="card unlock-moment" role="status">
      <button class="iconbtn unlock-x" aria-label="Dismiss" onClick=${onDismiss}><${Icon} name="close" size=${14} /></button>
      <div class="unlock-spark"><${Icon} name="sparkle" size=${22} /></div>
      <div style=${{ flex: 1, minWidth: "240px" }}>
        <b style=${{ fontFamily: "var(--font-head)", fontSize: "var(--fs-h3)" }}>Your insights are live</b>
        <p style=${{ margin: "2px 0 var(--s3)" }}>Your organisation's reward data is in — here's what just came alive:</p>
        <div class="unlock-links">
          <button class="btn small" onClick=${() => { nav("/signals"); onDismiss && onDismiss(); }}><${Icon} name="flag" size=${13} /> Your signals</button>
          ${/* the £ opportunity lives INSIDE signals (money flags) since the 80/20 hero —
                this used to say "(below)" and point at a tile that no longer renders */ ""}
          <button class="btn small" onClick=${() => { nav("/signals"); onDismiss && onDismiss(); }}><${Icon} name="coins" size=${13} /> £ opportunity — in your signals</button>
          <button class="btn small" onClick=${() => onDismiss && onDismiss()}><${Icon} name="file-text" size=${13} /> Export a board pack (top right)</button>
        </div>
      </div>
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
  // UN-GATED 2026-07-11 (David: "the board pack has disappeared"): the pack composes fully
  // without AI (deterministic narrative, labelled "composed directly from the figures"), so
  // hiding the button behind me.features.boardpack hid a working feature whenever AI was off.
  // The flag now scopes the Claude call server-side; the button always renders.
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
  // Generation is editor+ (server 403s Viewers since 2026-07-13); a Viewer gets one honest
  // "Board packs" menu button instead of a dead Export half — same rule as the removed ★/🔔:
  // never render a control that can't act.
  const isEditor = me.user && (me.user.role === "admin" || me.user.role === "contributor");
  return html`
    <div class="bp-export">
      ${isEditor && html`<button class=${"btn small" + (pulse ? " pulse-once" : "")} disabled=${gen} onClick=${generate}
        title="A board-ready narrative of your reward position, written from your live benchmark under the current peer filter.">
        <${Icon} name="file-text" size=${14} /> ${gen ? "Writing…" : "Export board pack"}</button>`}
      <button class="btn small" aria-label="Previous board packs" aria-expanded=${open} onClick=${toggle}>
        ${isEditor ? null : html`<${Icon} name="file-text" size=${14} /> Board packs `}<${Icon} name="chevron-down" size=${13} /></button>
      ${open && html`
        <div class="card bp-menu">
          ${err && html`<div class="caption" style=${{ padding: "var(--s2)", maxWidth: "280px" }}>${err}${" "}
            <a href="#/settings" onClick=${e => { e.preventDefault(); nav("/settings"); }}>Review AI settings →</a></div>`}
          ${packs == null && html`<div class="caption" style=${{ padding: "var(--s2)" }}>Loading…</div>`}
          ${packs && packs.length === 0 && !err && html`<div class="caption" style=${{ padding: "var(--s2)" }}>No packs yet — Export writes one from your live position.</div>`}
          ${(packs || []).map(p => html`
            <div key=${p.pack_id} class="bp-menu-row">
              <button class="bp-menu-item" onClick=${() => nav("/boardpack/" + p.pack_id)}>
                <b>${p.cut_label || "All peers"}</b>${p.collection_window ? " · " + p.collection_window : ""}
                <span class="caption" style=${{ display: "block" }}>
                  ${new Date(p.created_at + "Z").toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}${p.created_by ? " · " + p.created_by : ""}${p.ai ? " · AI narrative" : ""}</span>
              </button>
              ${me.user.role === "admin" && html`<button class="bp-menu-del" aria-label="Delete this board pack" title="Delete"
                onClick=${async (e) => { e.stopPropagation();
                  if (!window.confirm("Delete this board pack? Any share links to it will stop working.")) return;
                  try { await api("/api/boardpack/" + p.pack_id, { method: "DELETE" });
                        setPacks(ps => (ps || []).filter(x => x.pack_id !== p.pack_id)); toast("Board pack deleted"); }
                  catch (e2) { toast(e2.message, "error"); } }}>
                <${Icon} name="close" size=${12} /></button>`}
            </div>`)}
          <button class="bp-menu-item bp-menu-all" onClick=${() => nav("/boardpack")}>All board packs →</button>
        </div>`}
    </div>`;
}

/* Share this view (chrome spec): a read-only public link to the current
   dashboard view, scoped to the active peer filter. Admin-only (mirrors the
   board-pack share gate + /api/shares require_admin). The button sits beside
   Export board pack on the Overview header and on My dashboards. Posts
   kind=dashboard, config {cut, cut_value, name}, 30-day expiry; on success the
   dialog shows the public link with a copy button. */
function ShareButton({ me, cut, name, layout }) {
  const [open, setOpen] = useState(false);
  if (!me || !me.user || me.user.role !== "admin") return null;
  return html`
    <button class="btn small" onClick=${() => setOpen(true)}
      title="Create a read-only public link to your benchmark summary (30 days).">
      <${Icon} name="link" size=${14} /> Share</button>
    ${open && html`<${ShareDialog} cut=${cut} name=${name} layout=${layout} onClose=${() => setOpen(false)} />`}`;
}

function ShareDialog({ cut, name, layout, onClose }) {
  const [link, setLink] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [copied, setCopied] = useState(false);
  // when the caller passes a dashboard layout, the link shows THOSE cards; otherwise
  // it falls back to the org's team-default selection (server side).
  const hasLayout = Array.isArray(layout) && layout.length > 0;
  const create = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await api("/api/shares", { method: "POST", body: {
        kind: "dashboard",
        config: {
          cut: (cut && cut.dim) || "all", cut_value: (cut && cut.value) || null, name: name || null,
          layout: hasLayout ? layout.map(s => ({ question_id: s.question_id, row_id: s.row_id, size: s.size })) : undefined,
        },
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
          Create a read-only public link to your organisation's benchmark summary — headline position, leads and gaps, and ${hasLayout ? "the cards on this dashboard" : "your team's pinned cards"}. Anyone with the link can view it for 30 days; no sign-in needed.</p>
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
function OverviewHero({ data, cut, cuts, orgKey, view, applyStrat, setView, setApplyStrat, barMode, setBarMode,
                        me, onCut, onTwinInfo, prefs, onPref, refreshMe, sampleN, unlocked }) {
  const m = data.hero && data.hero.market;
  const locked = data.callouts && data.callouts.gaps_locked;
  // Signals follow the Market/Practice lens: MARKET view shows market-position signals
  // (below/on/above), PRACTICE view shows practice signals (differs-from-market +
  // differs-from-peers). The TOP of the panel is the engine's RATIFIED balanced
  // briefing for the view (server cap_briefing: behind-cap + reserved slot + per-lens
  // cap — data.signals / data.signals_practice); the rest of the impact-ranked pool
  // follows as the tail, so a dismiss/snooze still backfills from #4 onward. A stale
  // payload without the practice key degrades to pure impact order (yesterday's read).
  const _sigPos = view === "practice" ? ["differs", "practice"] : ["below", "on", "above"];
  const _pool = (data.signals_all || []).filter(s => _sigPos.indexOf(s.position) !== -1);
  const _brief = view === "practice" ? (data.signals_practice || []) : (data.signals || []);
  const _bk = new Set(_brief.map(s => s.sig_id || s.question_id));
  const _viewSigs = [..._brief, ..._pool.filter(s => !_bk.has(s.sig_id || s.question_id))];
  const _viewLive = _viewSigs.filter(s => s.status !== "dismissed");   // full ranked live pool — the panel
  const _viewTotal = _viewLive.length;                 // slices top-3 AFTER its optimistic dismiss filter
                                                       // (filter-before-slice, so a dismiss backfills #4 from the tail)
  const _viewNew = _viewSigs.filter(s => s.new && s.status !== "dismissed").length;
  // Per-domain live signal counts for the instrument's scent dots — derived from the
  // SAME filter-before-slice pool that feeds the band's "See all N", so the seven
  // counts always total the band's number (never raw signals_all, which still holds
  // dismissed rows).
  const _domCounts = {};
  _viewLive.forEach(s => { if (s.domain) _domCounts[s.domain] = (_domCounts[s.domain] || 0) + 1; });
  // scent-click → DOMAIN-FILTERED signals (David 2026-07-12, "if you click on the signals
  // count it takes you to only those signals"): the count chip now scrolls AND filters the
  // band below to that domain; the chip beside the Signals title clears it. Reset on lens
  // switch (the pool changes meaning).
  const [sigDomain, setSigDomain] = useState(null);
  useEffect(() => { setSigDomain(null); }, [view]);
  const scrollToSignals = (domain) => {
    setSigDomain(domain && typeof domain === "string" ? domain : null);
    // Chrome ABORTS a smooth scroll when the filter's row churn shifts layout at animation
    // start (observed: scrollY dies at 1px). Self-healing scroll: smooth attempt after the
    // re-render, then snap to the target if the smooth got cancelled. Reduced-motion snaps.
    setTimeout(() => {
      const el = document.querySelector(".ov-signals-band");
      if (!el) return;
      const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const target = () => Math.round(el.getBoundingClientRect().top + window.scrollY);
      window.scrollTo({ top: target(), behavior: reduce ? "auto" : "smooth" });
      if (!reduce) setTimeout(() => {
        if (Math.abs(window.scrollY - target()) > 40) window.scrollTo({ top: target(), behavior: "auto" });
      }, 500);
    }, 60);
  };
  // Cursor spotlight on the hero cards — a faint brand-tinted glow follows the
  // pointer (the tactile, alive feel). Direct DOM writes, no React re-render.
  // (.ov-wrap scope, 2026-07-08: the signals card moved below the hero row, so the
  // old ".ov-top .card" selector silently dropped its spotlight when it moved.)
  useEffect(() => {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const onMove = (e) => {
      const el = e.target.closest && e.target.closest(".ov-wrap .card");
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
      ${!locked && data.strategy_can_edit && !data.strategy_complete && html`<${StrategyNudge} />`}
      ${/* the full-width CONTEXT TOOLBAR (spatial restructure 2026-07-12): peer context —
            "Comparing against [capsule ★🔔] [confidence]" — anchors LEFT; the view lenses
            (Market/Practice + strategy switch) anchor RIGHT; the row's width does the
            separating. The peer picker shows even pre-unlock; the lenses need data. */ ""}
      <div class="ov-controls">
        <div class="ov-ctx">
          <${PeerSetBar} me=${me} cut=${cut} cuts=${cuts} onSelect=${onCut} onTwinInfo=${onTwinInfo} inline=${true}
            prefs=${prefs} onPref=${onPref} refreshMe=${refreshMe} />
          ${unlocked ? html`<${ConfidenceChip} n=${sampleN} window=${data.snapshot && data.snapshot.window} />` : null}
        </div>
        ${!locked ? html`
        <div class="ov-lens">
          <div class="ov-seg" role="group" aria-label="Dashboard lens">
            ${[["market", "Market"], ["practice", "Practice"]].map(([k, lab]) => html`
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
        </div>` : null}
      </div>
      <div class="ov-top">
        ${view === "practice"
          ? html`<${PracticeArc} prevalence=${data.hero.prevalence} pending=${locked} />`
          : html`<${OverallArc} market=${m} approach=${data.hero.approach} pending=${locked} pct=${Math.round((data.contribution && data.contribution.core_pct) || 0)} orgKey=${orgKey} stratOff=${data.strategy_complete && !applyStrat} />`}
        <${DomainInstrument} market=${m} prevalence=${data.hero.prevalence} domains=${data.hero.domains}
          view=${view} pending=${locked} sigCounts=${_domCounts} onScent=${scrollToSignals}
          activeScent=${sigDomain} barMode=${barMode} setBarMode=${setBarMode} />
      </div>
      ${/* TrajectoryTile retired from the scan path (2026-07-09 subtraction): a full card band
            promising the future between the hero and the action queue. Its one load-bearing
            clause moved into the header subtitle ("baseline — movement shows from your next
            cycle"); the component stays for cycle 2, when it will carry real movement. */ ""}
      <div class="ov-signals-band">
        <${SignalsPanel} signals=${_viewLive} total=${_viewTotal} newCount=${_viewNew} locked=${locked} contribution=${data.contribution} view=${view} stratOn=${!!data.strategy_applied}
          cutActive=${!!(cut && cut.dim && cut.dim !== "all")} domainFilter=${sigDomain} onClearDomain=${() => setSigDomain(null)} />
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
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
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
// The DomainInstrument's strategy channel (David 2026-07-09): the same navy AlignmentChip data,
// collapsed to ONE glyph per row so the wide RAG bar owns the row. NAVY only (never RAG hues) and
// walled into its own column — arrows/tick read as strategy, not market movement. on_target = calm
// outlined tick; behind = filled disc, down arrow; ahead = filled disc, up arrow (the filled discs
// draw the eye to anything off strategy). No target → renders nothing, so strategy-off degrades to
// pure RAG position with zero strategy indicators (on==off parity holds). Full read rides the row
// aria-label + this title; the glyph is decorative.
const STRAT_GLYPH = { on_target: { cls: "on", icon: "check" }, behind: { cls: "off", icon: "arrow-down" }, ahead: { cls: "off", icon: "arrow-up" } };
const STRAT_CLAUSE = { on_target: "On strategy — you're on aim.", behind: "Behind strategy — short of your aim.", ahead: "Ahead of strategy — past your aim." };
function StrategyMark({ target }) {
  const g = target && STRAT_GLYPH[target.alignment];
  if (!g) return null;
  return html`<span class=${"di-smark di-smark-" + g.cls} title=${targetCopy(target)} aria-hidden="true">
    <${Icon} name=${g.icon} size=${13} strokeWidth=${2.4} /></span>`;
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
// Optional onSeg (Signals redesign, 2026-07-01): when the caller keys its segments
// (s.k) and passes onSeg, each painted arc becomes clickable (SVG visiblePainted =
// the stroke only) and reports its key. No caller passing neither → byte-identical.
function Donut({ segments, total, centerNum, sub, size, stroke, centerWord, onSeg }) {
  size = size || 188; stroke = stroke || 26;
  const r = (size - stroke) / 2, cx = size / 2, cy = size / 2, C = 2 * Math.PI * r;
  let acc = 0;
  const arcs = (segments || []).filter(s => s.value > 0).map((s, i) => {
    const len = total ? (s.value / total) * C : 0;
    const gap = len > 8 ? 3 : 0;             // a small breather between real segments; none for slivers
    // a 1-of-many segment must stay clickable (it's the filter affordance) — floor
    // the DRAWN arc at ~6px so the smallest bucket isn't a 0.5px unhittable hairline
    const drawn = Math.max(len > 0 ? 6 : 0.5, len - gap);
    const click = onSeg && s.k != null;
    const node = html`<circle key=${i} cx=${cx} cy=${cy} r=${r} fill="none" stroke=${s.color}
      stroke-width=${stroke} stroke-linecap="butt"
      stroke-dasharray=${drawn.toFixed(2) + " " + (C - drawn).toFixed(2)}
      stroke-dashoffset=${(-acc).toFixed(2)} transform=${"rotate(-90 " + cx + " " + cy + ")"}
      style=${click ? { cursor: "pointer" } : null} onClick=${click ? () => onSeg(s.k) : null} />`;
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
window.Donut = Donut;   // shared primitive (board pack renders it from commercial.js, 2026-07-02)

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
      <div class="card-head"><${Icon} name="compass" size=${15} /><h2 class="card-head-title">Where you stand</h2></div>
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
        <div class="arc-lean">${(pct || 0) === 0
          ? "Add your reward data — your position appears once enough of it is comparable."
          : "Keep submitting — your position appears once enough data is comparable."}</div>
      </div>
      <div class="arc-legend num"><span class="arc-pending-note">Data pending — ${pct || 0}% of key reward questions submitted</span></div>
    </div>`;

  if (!market) return html`
    <div class="card arc-card"><div class="card-head"><${Icon} name="compass" size=${15} /><h2 class="card-head-title">Where you stand</h2></div>
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
        <${Icon} name="compass" size=${15} /><h2 class="card-head-title">Where you stand</h2>
        ${/* polish 2026-07-11: the strategy read is STATUS, so it docks in the header (it sat
              as a fifth stacked row under the donut). The unset state stays a bottom CTA. */ ""}
        ${market.target ? html`
          <span class="card-head-side"><${AlignmentChip} target=${market.target} /></span>`
        : stratOff ? html`
          <span class="card-head-side arc-target-off" title="You've turned your reward strategy off — this is the absolute market view, with no aim applied. Switch it back on above to read against your stance.">
            <${Icon} name="target" size=${13} /><span>Strategy off</span>
          </span>` : null}
      </div>
      ${/* FIX CLASS C (aggregate-marker rebuild 2026-07-11): donut and legend sit SIDE BY SIDE
            (donut shows spread, marker shows position — different jobs, both kept; stacks under
            the narrow breakpoint); the strip is replaced by the single overall marker on the
            SAME scale grammar as the domain rows, at the overall depth_pctl (D4: unweighted
            metric pool — domain-equal logged as the rejected alternative). */ ""}
      <div class="arc-duo">
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
        <div class="arc-caption num">
          <span class="arc-lean">${headLean}</span>
          <span class="arc-caption-sep" aria-hidden="true">—</span>
          <span><i class="arc-leg-dot di-fill-below" aria-hidden="true"></i><span class="arc-leg-fig">${market.below}</span> below</span>
          <span><i class="arc-leg-dot di-fill-on" aria-hidden="true"></i><span class="arc-leg-fig">${market.at}</span> on market</span>
          <span><i class="arc-leg-dot di-fill-above" aria-hidden="true"></i><span class="arc-leg-fig">${market.above}</span> above</span>
        </div>
      </div>
      ${(() => {
        const band = window.MARKET_BAND || [35, 65];
        const depth = market.depth_pctl;
        if (depth == null) return null;
        // premium pass 2026-07-12: ONE marker grammar everywhere — the overall marker is the
        // same ink P-pill the domain rows carry (the bare dot retired); the caption keeps the
        // load-bearing "typical metric" phrase without repeating the figure the pill shows.
        const pl = Math.min(96, Math.max(4, depth));
        return html`
          <div class="arc-marker">
            <span class="di-markrow arc-markscale" role="img"
              aria-label=${"Overall: typical metric at the " + pctlOrdinal(Math.round(depth)) + " percentile; the on-market band runs P" + band[0] + " to P" + band[1] + "."}>
              <span class="di-mk-zone z-below" style=${{ width: band[0] + "%" }}></span>
              <span class="di-mk-zone z-on" style=${{ width: (band[1] - band[0]) + "%" }}></span>
              <span class="di-mk-zone z-above" style=${{ width: (100 - band[1]) + "%" }}></span>
              <span class="di-mk-centre" aria-hidden="true"></span>
              <span class="di-pill num" style=${{ left: pl + "%" }}
                title=${"Typical metric at the " + pctlOrdinal(Math.round(depth)) + " percentile — the median of your per-metric percentiles, not a rank among peers."}>P${Math.round(depth)}</span>
            </span>
            <div class="caption bp-scale-labels"><span>below market</span><span>on market</span><span>above market</span></div>
            <div class="caption arc-marker-cap num">typical metric · on-market band P${band[0]}–${band[1]}</div>
          </div>`;
      })()}
      ${!market.target && !stratOff ? html`
        <button class="arc-target arc-target-unset" onClick=${() => nav("/strategy")}
          title="Set your market-position stance so lumi reads this against your aim, not a generic flag.">
          <${Icon} name="target" size=${13} /><span>Set your reward strategy to read this against your aim</span>
        </button>` : null}
    </div>`;
}


// PRACTICE lens for the hero — the TWIN of OverallArc (the market donut), in the PURPLE theme
// (2026-07-09 harmonisation). Shows PREVALENCE (common / alternative / rare) on a purple ladder
// donut + centred legend, mirroring "Where you stand" exactly — same build, different hue. Practice
// is "how common", never good/bad, so it stays purple and never enters the RAG channel. (Was
// ApproachPanel — a 2-way "off the norm / in line" split that used a different framing AND colour
// from its own 3-way domain bars; that differ read lives on in signals + the category page.)
function PracticeArc({ prevalence, pending }) {
  if (pending || !prevalence || !prevalence.pool) return html`
    <div class="card arc-card">
      <div class="card-head"><${Icon} name="layers" size=${15} /><h2 class="card-head-title">How you compare on practice</h2></div>
      <div class="caption" style=${{ padding: "var(--s4) var(--s2)" }}>
        ${pending ? "Your practice mix appears once enough of your data is comparable."
                  : "No practice metrics are comparable in this peer set yet."}</div>
    </div>`;
  // interpolated RAW from the engine prevalence fields (rendered == engine; qa_overview 9b)
  const common = prevalence.with_majority, alt = prevalence.established, rare = prevalence.less_common, pool = prevalence.pool;
  // centre word + caption derive from ONE rule so they never contradict (descriptive, never a
  // grade) — the rule moved to core.js prevalenceWord (2026-07-12) so the BOARD PACK reads
  // practice with the same words as this card. Mirrors the market donut's word+caption pairing.
  const { word, cap } = prevalenceWord(common, alt, rare, pool);
  return html`
    <div class="card arc-card">
      <div class="card-spot" aria-hidden="true"></div>
      <div class="card-head" title="How common each of your practice choices is among peers — a different question from the market-position read.">
        <${Icon} name="layers" size=${15} /><h2 class="card-head-title">How you compare on practice</h2></div>
      ${/* the practice twin missed the fix-class-C restructure (David 2026-07-12, "spacing
            looks odd") — it now shares the market card's arc-duo wrapper, so the stacked
            caption rules apply: lean on its own centred line, separator hidden, counts on
            one centred row. Same anatomy, purple theme. */ ""}
      <div class="arc-duo">
        <div class="arc-stage" role="img"
          aria-label=${"How you compare on practice: of " + pool + " tracked practices, " + common + " common, " + alt + " alternative, " + rare + " rare."}>
          <${Donut}
            segments=${[
              { value: common, color: "var(--prev-common)" },
              { value: alt, color: "var(--prev-alt)" },
              { value: rare, color: "var(--prev-rare)" },
            ]}
            total=${pool} centerNum=${pool} sub="practices" centerWord=${word} size=${210} stroke=${28} />
        </div>
        <div class="arc-caption num">
          <span class="arc-lean">${cap}</span>
          <span class="arc-caption-sep" aria-hidden="true">—</span>
          <span><i class="arc-leg-dot di-fill-common" aria-hidden="true"></i><span class="arc-leg-fig">${common}</span> common</span>
          <span><i class="arc-leg-dot di-fill-alt" aria-hidden="true"></i><span class="arc-leg-fig">${alt}</span> alternative</span>
          <span><i class="arc-leg-dot di-fill-rare" aria-hidden="true"></i><span class="arc-leg-fig">${rare}</span> rare</span>
        </div>
      </div>
      <div class="appr-note caption">A different way of doing things, not a gap to close — the ones worth acting on appear in your signals.</div>
    </div>`;
}


const LENS_ICON = { save: "coins", attract: "magnet", retain: "anchor", engage: "heart" };
const CAT_ICON = { "Pay": "coins", "Incentives": "trending-up", "Benefits": "shield",
  "Time Off": "sun", "Wellbeing": "heart", "Recognition": "award", "Governance": "list-checks" };

// ═══ DOMAIN INSTRUMENT (2026-07-08 hero redesign) — the per-domain analysis that sits
// BESIDE the summary donut: seven rows on ONE shared P0–P100 ruler, so the domains are
// comparable at a glance for the first time. Two connective devices weld it to the donut:
// a dashed navy hairline at the org's OVERALL percentile runs through every row, and the
// evidence column sums exactly to the donut's below/on/above counts ("sums to the dial").
// DATA RULES (verified against the live payload, 2026-07-08 judge pass):
//   · rows read d.position.* uniformly — Recognition's `market` key is null (indicative
//     basis), its counts live under position and are REQUIRED for the footer sum;
//   · dots plot position.depth_pctl, NEVER d.dot (Wellbeing dot=79.4 contradicts its
//     "below" verdict; depth_pctl=25.2 agrees);
//   · dot colour is navy always — position is strategy-INVARIANT; the strategy
//     relationship rides the separate navy AlignmentChip (on==off dot parity canary).
// PRACTICE LENS: same skeleton, re-skinned to prevalence (with_majority/established/
// less_common) — the ONLY practice decomposition that sums to the overall (92/47/36/175);
// approach.* deliberately NOT used for rows (domain approach sums ≠ the ApproachPanel).
function domainStandfirst(market, doms, view, prevalence) {
  if (view === "practice") {
    if (!prevalence || !prevalence.pool) return null;
    const share = prevalence.with_majority / prevalence.pool;
    const opener = share >= 0.5 ? "Most of your practices are common choices"
                                : "Many of your practices follow their own pattern";
    const ranked = doms.filter(d => d.prevalence && d.prevalence.pool >= 5)
      .map(d => ({ name: domainLabel(d.name), share: d.prevalence.with_majority / d.prevalence.pool }))
      .sort((a, b) => a.share - b.share);
    const tail = ranked.length ? "; " + ranked[0].name + " differs most from the peer pattern" : "";
    return opener + " — " + prevalence.with_majority + " of your " + prevalence.pool +
      " tracked practices sit with the majority" + tail + ".";
  }
  if (!market || !market.pool) return null;
  const vw = market.verdict === "above" ? "above" : market.verdict === "at" ? "broadly in line with" : "below";
  const base = "You're " + vw + " the market across your reward areas";
  const mk = doms.filter(d => d.position_basis === "market" && d.position && d.position.pool)
    .map(d => ({ name: domainLabel(d.name), below: d.position.below || 0, above: d.position.above || 0, pool: d.position.pool,
                 bshare: (d.position.below || 0) / d.position.pool, ashare: (d.position.above || 0) / d.position.pool }));
  if (mk.length < 2) return base + ".";
  if (market.verdict === "above") {
    const r = mk.slice().sort((a, b) => b.ashare - a.ashare);
    return base + " — furthest ahead on " + r[0].name + " and " + r[1].name + "; " +
      r[r.length - 1].name + " sits closest to the market.";
  }
  const r = mk.slice().sort((a, b) => b.bshare - a.bshare);
  return base + " — furthest behind on " + r[0].name + " and " + r[1].name + "; " +
    r[r.length - 1].name + " sits closest to the market.";
}
// short prevalence subline for a practice row — the full prevalence.verdict is a
// sentence that overflows the identity column; this fits.
function prevShort(pv) {
  if (!pv || !pv.pool) return "";
  const s = pv.with_majority / pv.pool;
  return s >= 0.55 ? "mostly common choices" : s >= 0.34 ? "a mixed pattern" : "often its own pattern";
}
// one citable sentence per row — the tooltip AND the row button's aria-label
function domainRowSentence(d, view) {
  const label = domainLabel(d.name);
  if (view === "practice") {
    const pv = d.prevalence || {};
    if (!pv.pool) return label + " — no practices tracked yet.";
    return label + ": " + (pv.verdict || "practice alignment") + " · " + pv.with_majority +
      " common, " + pv.established + " alternative, " + pv.less_common + " rare of " + pv.pool + " tracked.";
  }
  const pos = d.position;
  if (d.competitiveness === false) return label + " — no market rate; approach choices only. See the Practice lens.";
  if (!pos || !pos.pool) return label + " — no comparable market position yet.";
  // counts-only + the verbal adverb — no P-number anywhere (RAG-only law, 2026-07-09)
  let s = label + ": " + pos.below + " below, " + pos.at + " on market, " + pos.above +
    " above of " + pos.pool + " comparable — " + leanCaption(pos) + ".";
  // strategy channel (2026-07-09): the row glyph is decorative, so the on-aim / behind / ahead
  // read must ride the accessible name — words only, never a lag/match/lead literal or a P-number.
  if (d.target && STRAT_CLAUSE[d.target.alignment]) s += " " + STRAT_CLAUSE[d.target.alignment];
  return s;
}
function DomainInstrument({ market, prevalence, domains, view, pending, sigCounts, onScent, activeScent, barMode, setBarMode }) {
  const doms = domains || [];
  const practice = view === "practice";
  // (footer sums retired 2026-07-09 with both footers — the donut legends carry the org totals.)
  // standfirst removed (David 2026-07-09): the per-domain rows carry the read; the summary
  // sentence duplicated the donut + repeated what the bars already show. Kept ONLY for the
  // pending/locked state, where there are no rows yet to explain themselves.
  const stand = pending
    ? "Your per-domain position appears here once enough of your data is comparable — complete your key reward questions to unlock it."
    : null;
  const openDomain = (name) => nav("/category/" + encodeURIComponent(name));
  // strategy summary (2026-07-09): an always-on anchor so the navy channel says something even at
  // zero drift — "all N on aim" flips to "N off aim". Reads ONLY targets (strategy-off → no targets
  // → null → nothing renders, on==off parity). Position view only; words only (no lag/match/lead).
  const withTarget = practice ? [] : doms.filter(d => d.target && ALIGN_LABEL[d.target.alignment]);
  const offAim = withTarget.filter(d => d.target.alignment !== "on_target").length;
  const stratSum = (pending || !withTarget.length) ? null
    : offAim === 0 ? "Strategy · all " + withTarget.length + " on aim"
    : "Strategy · " + offAim + " off aim";
  return html`
    <div class="card dom-instr">
      <div class="card-spot" aria-hidden="true"></div>
      <div class="card-head">
        <${Icon} name="layers" size=${15} />
        <h2 class="card-head-title">${practice ? "Practice by domain" : "Position by domain"}</h2>
        <span class="card-head-side">
          ${stratSum ? html`<span class="di-strat-sum">${stratSum}</span>` : null}
          ${/* bar-mode toggle (David 2026-07-11): the user decides — count-proportional stacked
                segments vs the fixed-band percentile bar with the true-P marker. Market view
                only (practice has no market position). Persisted per user in prefs._overview. */ ""}
          ${!practice && !pending && setBarMode ? html`
            <span class="ov-seg ov-seg-mini" role="group" aria-label="How the domain bars read">
              <button type="button" class=${"ov-seg-btn" + (barMode !== "position" ? " on" : "")} aria-pressed=${barMode !== "position"}
                title="Segment widths show how many metrics sit below, on and above market"
                onClick=${() => setBarMode("counts")}>Counts</button>
              <button type="button" class=${"ov-seg-btn" + (barMode === "position" ? " on" : "")} aria-pressed=${barMode === "position"}
                title="A percentile scale — the marker shows where your typical metric sits against the on-market band"
                onClick=${() => setBarMode("position")}>Position</button>
            </span>` : null}
        </span>
      </div>
      ${stand ? html`<p class=${"di-standfirst" + (pending ? " di-standfirst-pending" : "")}>${stand}</p>` : null}
      ${/* both lenses now key their stacked bar with a swatch row: market = soft RAG (below/on/
            above), practice = the purple ladder (common/alternative/rare). Same construction,
            each keeps its own theme. */ ""}
      <div class="di-axis" aria-hidden="true">
        <span class="di-cell di-ident"></span>
        <span class="di-cell di-trackcell di-axis-scale">
          ${practice ? html`
          <span class="di-axis-key">
            <span class="di-kk"><i class="di-sw di-fill-common"></i>common</span>
            <span class="di-kk"><i class="di-sw di-fill-alt"></i>alternative</span>
            <span class="di-kk"><i class="di-sw di-fill-rare"></i>rare</span>
          </span>`
          : barMode === "position" ? html`
          ${/* position mode: axis WORDS only up here — the reference strip is gone (David
                2026-07-12, "remove the top reference bar"); the rows' own zone seams carry
                the band geometry. */ ""}
          <span class="di-axis-poskey">
            <span class="di-pk-labels"><span>below market</span><span>on market</span><span>above market</span></span>
          </span>`
          : html`
          <span class="di-axis-key">
            <span class="di-kk"><i class="di-sw di-fill-below"></i>below</span>
            <span class="di-kk"><i class="di-sw di-fill-on"></i>on market</span>
            <span class="di-kk"><i class="di-sw di-fill-above"></i>above</span>
          </span>`}
        </span>
        <span class="di-cell di-evid"></span>
        ${/* column headers (David 2026-07-11: "the signal count is not obvious as they have no
              header, same with the strategy marker") */ ""}
        ${/* column headers follow their CONTENT (mode-pass fix 2026-07-12): SIGNALS hides when
              no domain has a live signal; AIM hides when strategy renders no ticks (stratSum
              null, e.g. strategy off) — a header must never float over an empty column. */ ""}
        <span class="di-cell di-scentcol di-colhead">${pending || !Object.values(sigCounts || {}).some(v => v > 0) ? null : "Signals"}</span>
        <span class="di-cell di-chipcol di-colhead">${pending || practice || !stratSum ? null : "Aim"}</span>
        <span class="di-cell di-chev"></span>
      </div>
      <div class="di-rows di-rows-anim" key=${practice ? "practice" : barMode}>
        ${/* FIX CLASS A (locked): the marker view sorts WORST-FIRST — lowest depth_pctl at the
              top; rows with no position (Governance, not-yet) keep to the bottom. The counts
              view keeps the canonical section order. */ ""}
        ${(!practice && barMode === "position"
          ? [...doms].sort((a, b) => {
              const da = a.position && a.position.depth_pctl, db = b.position && b.position.depth_pctl;
              if (da == null && db == null) return 0;
              if (da == null) return 1;
              if (db == null) return -1;
              return da - db;
            })
          : doms).map((d, i) => {
          const label = domainLabel(d.name);
          const sentence = domainRowSentence(d, view);
          const pos = d.position;
          const noRate = d.competitiveness === false;
          const pv = d.prevalence || {};
          const nSig = (sigCounts && sigCounts[d.name]) || 0;
          const pct = pos && pos.depth_pctl != null ? Math.min(99, Math.max(1, pos.depth_pctl)) : null;
          return html`
            <div key=${d.name} class="di-row" title=${sentence} onClick=${() => openDomain(d.name)}>
              <span class="di-cell di-ident">
                <h3 class="di-name"><button class="di-open" aria-label=${sentence}
                  onClick=${e => { e.stopPropagation(); openDomain(d.name); }}>${label}</button></h3>
                ${/* sublines survive ONLY for the empty states now — the bar carries the read in
                      both lenses (harmonised 2026-07-09: the practice "mostly common" subline
                      dropped, matching the market rows' name-only identity). */ ""}
                ${pending ? null : practice
                  ? (pv.pool ? null : html`<span class="di-sub">no practices tracked yet</span>`)
                  : (!noRate && (!pos || !pos.pool)) ? html`<span class="di-sub">no position yet</span>`
                  : null}
                ${/* counts sub-label REMOVED from the marker view (David 2026-07-12, "remove the
                      text below each domain") — the counts live in the Counts toggle state and
                      the row aria; single-line rows restore the pitch. */ ""}
              </span>
              <span class="di-cell di-trackcell">
                ${pending ? html`<span class="di-track di-track-pending" aria-hidden="true"></span>`
                : practice ? (pv.pool ? html`
                  ${/* PRACTICE STACKED BAR (2026-07-09 harmonisation): the SAME flex bar as market,
                        counts inside common/alternative/rare, on the purple ladder — practice reads
                        as the market lens's twin. */ ""}
                  <span class="di-bar" aria-hidden="true">
                    ${[["with_majority", "di-fill-common"], ["established", "di-fill-alt"], ["less_common", "di-fill-rare"]].map(([k, cls]) => {
                      const v = pv[k] || 0;
                      if (!v) return null;
                      const mw = (String(v).length * 8 + 18) + "px";
                      return html`<span key=${k} class=${"di-fill " + cls} style=${{ flexGrow: v, minWidth: mw }}><span class="di-fillnum">${v}</span></span>`;
                    })}
                  </span>`
                  : html`<span class="di-norate">no practices tracked in this peer set yet</span>`)
                : noRate ? html`<span class="di-norate">No market rate — see the Practice lens</span>`
                : pos && pos.pool ? html`
                  ${/* STACKED RAG BAR (David, 2026-07-09): each row is one bar split below=amber /
                        on=green / above=red, segments sized to the METRIC COUNT in each band with the
                        count printed INSIDE (min-width floor so a lone 1 never floats out). Soft
                        gauge tones — the platform's one RAG fill, same as the donut. RAG-only law
                        holds: colours + counts, zero P-anything. The count is the citation, so the
                        separate evidence line is retired. */ ""}
                  ${/* TWO PURE bar modes, user-toggled (David 2026-07-11, "only show counts no p
                        and vice versa"):
                        COUNTS — the ratified count-proportional stacked segments (2026-07-09),
                        counts printed inside; no P anywhere on the row.
                        POSITION — a dot-scale freed from the bar: soft band track (P35/P65 from
                        the engine), an ink dot at the true percentile with its P-label riding
                        the dot (hollow dot = indicative basis; aria carries the word). */ ""}
                  ${barMode !== "position" ? html`
                  <span class="di-bar" aria-hidden="true">
                    ${[["below", "di-fill-below"], ["at", "di-fill-on"], ["above", "di-fill-above"]].map(([k, cls]) => {
                      const v = pos[k] || 0;
                      if (!v) return null;
                      const mw = (String(v).length * 8 + 18) + "px";
                      return html`<span key=${k} class=${"di-fill " + cls} style=${{ flexGrow: v, minWidth: mw }}><span class="di-fillnum">${v}</span></span>`;
                    })}
                  </span>`
                  : (() => {
                    // FIX CLASS A (aggregate-marker rebuild, spec 2026-07-11): the single-marker
                    // form — one shared below/on/above-market scale (soft zones KEPT by David's
                    // ruling), a dashed market centre line, ONE ink dot at the org's depth_pctl
                    // (D1 — never the lean). No connector/stem, no band pill (locked). Indicative
                    // (fewer distinct polarised questions than the domain floor) = hollow dashed
                    // ring; the word rides the aria.
                    const band = window.MARKET_BAND || [35, 65];
                    const depth = pos.depth_pctl;
                    if (depth == null) return html`<span class="di-norate">no position depth yet</span>`;
                    const left = Math.min(99, Math.max(1, depth));
                    // mk-neutral (ruled 2026-07-12): the Position state is the NEUTRAL-MIRROR —
                    // grey zones, ink markers; RAG lives in the Counts state. SCOPED to the
                    // domain rows only: the overall gauge-card marker reuses .di-markrow and
                    // must keep its soft-RAG per the keep-RAG ruling.
                    // pill marker (David 2026-07-12, "new dot format"): ONE object — the P
                    // rides INSIDE an ink pill, killing the dot/label spacing problem.
                    // Indicative = dashed pill. Counts live in the aria (the sub-label they
                    // used to ride under the name is gone).
                    const pl = Math.min(96, Math.max(4, left));
                    return html`<span class="di-markrow mk-neutral" role="img"
                      aria-label=${"Typical metric at the " + pctlOrdinal(Math.round(depth)) + " percentile" + (d.position_basis === "indicative" ? " (indicative)" : "") + "; the on-market band runs P" + band[0] + " to P" + band[1] + ". " + (pos.below || 0) + " below, " + (pos.at || 0) + " on market, " + (pos.above || 0) + " above."}>
                      <span class="di-mk-zone z-below" style=${{ width: band[0] + "%" }}></span>
                      <span class="di-mk-zone z-on" style=${{ width: (band[1] - band[0]) + "%" }}></span>
                      <span class="di-mk-zone z-above" style=${{ width: (100 - band[1]) + "%" }}></span>
                      <span class="di-mk-centre" aria-hidden="true"></span>
                      <span class=${"di-pill num" + (d.position_basis === "indicative" ? " ind" : "")} style=${{ left: pl + "%" }}
                        title=${"Typical metric at the " + pctlOrdinal(Math.round(depth)) + " percentile — the median of this domain's per-metric percentiles, not a rank among peers."}>P${Math.round(depth)}</span>
                    </span>`;
                  })()}`
                : html`<span class="di-norate">no comparable position yet</span>`}
              </span>
              <span class="di-cell di-evid num">
                ${/* both stacked bars print their counts inside (2026-07-09); this column carries
                      ONLY the Governance practices count (no bar). The P-number moved onto the
                      position dot itself (David 2026-07-11: "only show counts no p and vice
                      versa" — each mode is pure; the "ind." tag went with it, the hollow dot +
                      aria carry the indicative basis). */ ""}
                ${(!pending && !practice && noRate) ? html`${pv.pool || 0} practices` : null}
              </span>
              <span class="di-cell di-scentcol">
                ${!pending && nSig > 0 ? html`
                  <button class=${"di-scent" + (activeScent === d.name ? " on" : "")} aria-pressed=${activeScent === d.name}
                    title=${activeScent === d.name
                      ? "Showing only " + label + "'s signals below — click to show all"
                      : nSig + " signal" + (nSig === 1 ? "" : "s") + " in " + label + " — show only these below"}
                    aria-label=${nSig + " signal" + (nSig === 1 ? "" : "s") + " in " + label + " — show only these in the signals list below"}
                    onClick=${e => { e.stopPropagation(); onScent && onScent(activeScent === d.name ? null : d.name); }}>${nSig}</button>` : null}
              </span>
              <span class=${"di-cell di-chipcol" + (!practice && stratSum ? " di-stratcol" : "")}>
                ${/* strategy channel (2026-07-09): position view shows the navy target glyph on
                      EVERY row (David: "see if you're aligned or not"); the header carries the
                      count. Practice view shows NOTHING here — strategy alignment is a market-
                      position concept, it has no meaning against the practice mix (harmonised). */ ""}
                ${pending || practice ? null
                  : noRate ? (stratSum ? html`<span class="di-smark-dash" aria-hidden="true">—</span>` : null)
                  : html`<${StrategyMark} target=${d.target} />`}
              </span>
              <span class="di-cell di-chev" aria-hidden="true"><${Icon} name="chevron-right" size=${15} /></span>
            </div>`;
        })}
      </div>
      ${/* both footers retired (2026-07-09): each repeated its donut legend digit-for-digit.
            The practice donut (PracticeArc) now cites the org common/alt/rare totals, so the
            practice footer is redundant too — dropped, matching the market lens. */ ""}
    </div>`;
}

function SignalsPanel({ signals, total, newCount, locked, contribution, view, stratOn, cutActive, domainFilter, onClearDomain }) {
  // domain filter (2026-07-12): a scent-chip click narrows the band to ONE domain's signals —
  // uncapped (the count chip promised N; show N), the briefing cap applies only unfiltered.
  const sigs = (signals || []).filter(s => !domainFilter || s.domain === domainFilter);
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
  const onSet = (sid, status, days) => {
    // dismiss AND snooze both remove the signal from the briefing — animate them out
    if ((status === "dismissed" || status === "snoozed") && !reduceMotion) {
      setLeaving(p => ({ ...p, [sid]: true }));
      signalAction(sid, status, days).catch(() => {});
      setTimeout(() => {
        setStOv(p => ({ ...p, [sid]: status }));
        setLeaving(p => { const n = { ...p }; delete n[sid]; return n; });
      }, 260);
    } else {
      setStOv(p => ({ ...p, [sid]: status || "active" }));
      signalAction(sid, status, days).catch(() => {});
    }
    // same recovery the Signals page offers — a home-briefing dismiss/snooze was one-way
    if (status === "dismissed") toast("Signal dismissed", null, { label: "Undo", fn: () => onSet(sid, null) });
    else if (status === "snoozed") toast("Snoozed · " + snoozeReturn(new Date(Date.now() + days * 86400000).toISOString()), null, { label: "Undo", fn: () => onSet(sid, null) });
  };
  const _live = sigs.filter(s => effStatus(s) !== "dismissed" && effStatus(s) !== "snoozed");
  const shown = domainFilter ? _live : _live.slice(0, 3);   // filter-before-slice: a dismiss/snooze backfills #4 from the tail; a domain filter shows the domain WHOLE
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
        <h2 class="card-head-title">Signals</h2>
        ${newCount > 0 ? html`<span class="sig-new-chip">${newCount} new</span>` : null}
        ${domainFilter ? html`
          <button type="button" class="sig-domchip" onClick=${onClearDomain}
            title="Showing this domain only — click to show all signals">
            ${domainLabel(domainFilter)} only <${Icon} name="close" size=${11} /></button>` : null}
      </div>
      ${/* ONE quiet meta line (2026-07-09 header collapse): scope + rank + posture, replacing
            the title suffix + count pill + slogan note + separate ranknote. The rank caption
            must stay TRUE: with the strategy lens applied the engine re-ranks by stance, so
            the plain-gap claim only holds strategy-off. "we flag, you decide" kept visible
            here by the founder's call (brand posture earns its one clause). */ ""}
      ${/* polish 2026-07-11: " · strategy applied" folded INTO the rank claim ("ranked by gap
            to your aim") — same truth, one clause fewer; the founder's posture clause stays. */ ""}
      ${!locked && shown.length > 0 ? html`<div class="sig-ranknote num">${(domainFilter
        ? domainLabel(domainFilter) + " · " + shown.length + " of " + total + " · "
        : (total > shown.length ? "top " + shown.length + " of " + total + " · " : "")) + (view === "practice" ? "ranked by rarity" : (stratOn ? "ranked by gap to your aim" : "ranked by market gap")) + " · we flag, you decide"}</div>` : null}
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
          <div key=${sid} data-sid=${sid} class=${"signal-row sig-row-axis sig-tone-" + pt.tone + (s.new ? " is-new" : "") + (s.risk_framed ? " is-risk" : "") + (s.confirm ? " is-confirm" : "") + (leaving[sid] ? " sig-leaving" : "")} onClick=${() => openMetric(s.question_id)}>
            ${sigParts(s, pt)}
            <${SignalActions} status=${effStatus(s)} sid=${sid} onSet=${onSet} />
          </div>`; })}
      </div>`,
      html`<div class="signals-foot" key="foot">
        <span></span>
        ${/* Ship review 2026-07-09 Pack 1 §6: the Signals page always reads the ALL-PEERS
              basis (its fetch carries no cut — App doesn't pass one), so when the home is on
              a narrower cut this link silently switches peer group. Say so on the link. */ ""}
        ${/* polish 2026-07-11: the total already scopes the meta line ("top 3 of N") — repeating
              it here made the same number appear three times in one card. */ ""}
        <a href="#/signals">${"See all signals" + (cutActive ? " (all peers)" : "") + " →"}</a>
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
  prevalence: "COMMON — YOU DON'T", outlier: "LOWER THAN MARKET", depth: "LOWER THAN MARKET", rare: "A RARE CHOICE" };
// Every row reads the same three things in the same order: what it is (bold) ·
// where you stand (the market fact) · the categorical tag. "Worth a look" leads
// only where there's a supported worse direction (behind / a common practice you
// lack). The tag answers one question — how do you compare to the market?
const sigParts = (s, pt) => [
  html`<span class=${"signal-roundel lens-" + s.lens} key="r"><${Icon} name=${LENS_ICON[s.lens] || "flag"} size=${15} /></span>`,
  // the BODY is the row's one real control (a11y: the row div is a mouse convenience,
  // never role="button" — buttons inside a button are a nested-interactive violation).
  // Keyboard lands here; the triage buttons are focusable SIBLINGS, not descendants.
  html`<button class="signal-body sig-open" key="b" onClick=${e => { e.stopPropagation(); openMetric(s.question_id); }}>
    <b class="sig-name">${s.new ? html`<span class="sig-new-tag">NEW</span> ` : null}${s.name || s.label_short}${s.risk_framed ? html` <span class="sig-risk"><${Icon} name="shield" size=${11} /> Risk</span>` : null}${s.confirm ? html` <span class="sig-onplan"><${Icon} name="check" size=${11} /> On plan</span>` : null}</b>
    <span class="sig-stand">${s.stand || s.detail}${s.n ? html` · n=${s.n}` : null}</span></button>`,
  // 2026-07-09 row diet (home briefing only — the explore page keeps both):
  // · the unlabelled grey gap-dash read as noise on the calm home band — retired here;
  // · ONE verdict carrier per row — prevalence/rare bodies state the fact in the sentence
  //   ("67% of the market does this, you don't"), so their caps pill was a duplicate;
  //   the pill stays where it is the sole verdict word (value gaps).
  (s.kind === "prevalence" || s.kind === "rare") ? null :
    html`<span class=${"pos-tag pos-" + (pt ? pt.tone : "neutral")} key="t">${s.tag || KIND_LABEL[s.kind] || s.kind}</span>`,
];
// Triage controls (prioritise · save · dismiss / restore) — ONE shared control on
// EVERY signal wherever it appears: the home briefing, each domain page, and the
// Signals explore page. onSet(sid, status) persists + optimistically updates; status
// is the final state (null = back to active/inbox). Toggle logic lives here so every
// surface behaves identically.
function SignalActions({ status, sid, onSet }) {
  const [snoozeOpen, setSnoozeOpen] = useState(false);
  const wrapRef = useRef(null);
  useEffect(() => {
    if (!snoozeOpen) return;
    const away = e => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setSnoozeOpen(false); };
    // Escape closes too (keyboard parity with click-away) and hands focus back to
    // the clock trigger so the keyboard user isn't dropped at the document root.
    const esc = e => { if (e.key === "Escape") {
      setSnoozeOpen(false);
      const t = wrapRef.current && wrapRef.current.querySelector("button.sig-act");
      if (t) t.focus();
    } };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, [snoozeOpen]);
  const snooze = days => { setSnoozeOpen(false); onSet(sid, "snoozed", days); };
  return html`<span class="sig-actions" onClick=${e => e.stopPropagation()}>
    ${status === "dismissed" ? html`
      <button class="sig-act" title="Restore to inbox" aria-label="Restore signal to inbox" onClick=${() => onSet(sid, null)}><${Icon} name="refresh" size=${15} /></button>`
    : status === "snoozed" ? html`
      <button class="sig-act" title="Return to inbox now" aria-label="Un-snooze signal, return to inbox" onClick=${() => onSet(sid, null)}><${Icon} name="refresh" size=${15} /></button>` : html`
      <button class=${"sig-act" + (status === "priority" ? " on" : "")} title=${status === "priority" ? "Remove priority" : "Prioritise"} aria-label="Prioritise signal" aria-pressed=${status === "priority"} onClick=${() => onSet(sid, status === "priority" ? null : "priority")}><${Icon} name="pin" size=${15} /></button>
      <button class=${"sig-act" + (status === "saved" ? " on" : "")} title=${status === "saved" ? "Remove from saved" : "Save"} aria-label="Save signal" aria-pressed=${status === "saved"} onClick=${() => onSet(sid, status === "saved" ? null : "saved")}><${Icon} name="star" size=${15} /></button>
      <span class="sig-snooze-wrap" ref=${wrapRef}>
        <button class=${"sig-act" + (snoozeOpen ? " on" : "")} title="Snooze — revisit next cycle" aria-label="Snooze signal" aria-haspopup="true" aria-expanded=${snoozeOpen} onClick=${() => setSnoozeOpen(o => !o)}><${Icon} name="clock" size=${15} /></button>
        ${snoozeOpen ? html`<div class="sig-snooze-menu" role="group">
          <div class="sig-snooze-lbl">Snooze until…</div>
          <button class="sig-snooze-opt" onClick=${() => snooze(14)}>2 weeks</button>
          <button class="sig-snooze-opt" onClick=${() => snooze(42)}>6 weeks</button>
          <button class="sig-snooze-opt" onClick=${() => snooze(90)}>3 months</button>
        </div>` : null}
      </span>
      <button class="sig-act" title="Dismiss" aria-label="Dismiss signal" onClick=${() => onSet(sid, "dismissed")}><${Icon} name="close" size=${15} /></button>`}
  </span>`;
}
// Persist a triage action (home panel + domain pages call this; the Signals page keeps
// its own statuses state). Best-effort — the optimistic UI is the caller's.
function signalAction(sid, status, days) {
  return api("/api/signals/action", { method: "POST",
    body: { question_id: sid, status: status || "active", ...(days ? { snooze_days: days } : {}) } })
    // Ship review 2026-07-09 Pack 1 §4: a triage from the home briefing / metric page
    // never invalidated the cached /api/overview, so a dismissed signal resurrected for
    // up to 60s on the next surface. Same invalidate-on-write the SignalsPage already
    // does in its own setStatus.
    .then(r => { apiCacheInvalidate("/api/overview"); return r; });
}
// (SIG_TABS retired 2026-07-09 with the Briefing rebuild — the five status tabs became the
// navy-footer lifecycle strip; pins simply stay in the brief.)
// friendly "back in ~N weeks/days" from a snooze_until — accepts both the SQLite
// "YYYY-MM-DD HH:MM:SS" (UTC, no tz) form and a full ISO string.
function snoozeReturn(until) {
  if (!until) return "";
  const iso = until.includes("T") ? until : until.replace(" ", "T") + "Z";
  const ms = new Date(iso).getTime() - Date.now();
  if (isNaN(ms) || ms <= 0) return "due back now";
  const days = Math.ceil(ms / 86400000);
  if (days >= 14) return "back in ~" + Math.round(days / 7) + " weeks";
  if (days > 1) return "back in " + days + " days";
  return "back tomorrow";
}
// Market-position axis (spec §6.3): the cut users come for. below/above = Substance,
// differs = Approach — so this single control subsumes the register split. `practice` is
// the NON-MARKET bucket: signals on a non-competitive domain (Governance) which has no
// market rate, so they read "differs from peers", never a market verdict (Governance
// scoping ruling — signals layer; same competitiveness flag the hero scopes by).
const SIG_DOMAINS = ["Pay", "Incentives", "Benefits", "Time Off", "Wellbeing", "Recognition", "Governance"];
// Per-row Position fallback text. The rendered row tag is s.tag (so Practice rows now read their
// own common/alternative/rare tag directly); this is only a defensive fallback for a Position row
// that somehow lacks a tag. The differs/practice entries retired with the chip re-bucket (2026-06-30).
const POS_TAG_TEXT = { below: "below market", on: "on market", above: "above market" };
// Solid stance-aware colour for a market position — the SAME palette the home gauge
// uses, so the two surfaces speak one colour language (on the aim = green, past it =
// amber, short of it = red). Approach (differs) carries no market stance → purple.
const SIG_TONE_SOLID = { green: "var(--favourable)", amber: "var(--amber-bright)",
  red: "var(--unfavourable)", neutral: "var(--chart-band-mid)", approach: "var(--differs)" };
function posColor(k) { return (k === "differs" || k === "practice") ? SIG_TONE_SOLID.approach : SIG_TONE_SOLID[marketTone(k)]; }
// (bucketColor retired 2026-07-09 with the Briefing rebuild — ledger dots key by the
// direction-corrected TONE via BRF_DOT, so lower-is-better metrics keep their flip.)
// (bucketColorSoft retired 2026-07-09 with the Briefing rebuild — the header donut died with
// the summary card; the soft gauge palette lives on in the brief-card chips via CSS tokens.)
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
  const text = POS_TAG_TEXT[s.position] || "";   // fallback only; the row renders s.tag
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
    { lens: "engage", icon: "users", tag: "COMMON — YOU DON'T", name: "Paid parental leave", stand: "offered by 8 in 10 similar organisations" },
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
            <span class="caption">unlocks at ${target}%${contrib.reduced ? " · paused to a sample — finish to restore" : (days != null ? ` · ${days} days left` : "")}</span>
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

// Ship review 2026-07-09 Pack 1 §1/§2: triage/filter state survives the open-signal→Back
// round trip. The pages stash their working set in sessionStorage on every change; on mount
// they restore it ONLY when this render IS the Back leg — detected by the lumi-return marker
// (openMetric writes it, core.js; App's scroll-restore effect consumes it AFTER children
// initialise, so during a child's useState initializers it still points at this hash). A
// fresh navigation carries no matching marker → clean defaults, exactly as before.
function returnUiState(key) {
  try {
    const r = JSON.parse(sessionStorage.getItem("lumi-return") || "null");
    if (!r || r.hash !== window.location.hash) return null;
    return JSON.parse(sessionStorage.getItem(key) || "null");
  } catch (e) { return null; }
}
function saveUiState(key, obj) { try { sessionStorage.setItem(key, JSON.stringify(obj)); } catch (e) {} }

/* SIGNALS PAGE — "FOLDERS" (founder simplification, 2026-07-10; replaces the two-tier
   Briefing). Founder's spec, verbatim intent: "keep it simple — just load ALL of the
   signals", then let the user SAVE to a folder they NAME, SNOOZE to a snooze folder on a
   user-set timeline (returns to the feed when it elapses), and DISMISS to a dismissed
   folder where it can be RECOVERED. So: ONE flat feed of every live signal (the Briefing's
   evidence-card anatomy, machine order and per-card triage kept exactly), and a single
   folder-nav row of pills — no tabs, donut, chips, group-by, brief/ledger split or family
   rows. Signal STATUS stays on the existing /api/signals/action contract (saved / snoozed /
   dismissed — unchanged); folder NAMES + {sig_id → folder} assignments ride the SAME
   per-user prefs store other pages use (key "_signals": { folders: [...], assign: {} }) —
   see onPref in app.js. PRESERVED exactly: triage API + optimistic overrides + Undo (on the
   confirmation toast since 2026-07-10 — the in-place stub rows retired, David: toast instead),
   seen-marking on load, strategy-check goToDomain jump + flash, gap-register
   navy footer + "nothing is deleted", locked teaser, returnUiState back-leg restore (now the
   active folder), openMetric deep links, the all-peers basis line, "we flag, you decide". */
// card/chip tone — prevalence & rare reads are PRACTICE observations (purple) even when their
// position bucket is market (the EAP case); everything else follows posTag's direction-corrected
// tone (soft RAG; approach=purple; neutral=navy). Doctrine: soft RAG = market position only.
function brfTone(s) {
  if (s.kind === "prevalence" || s.kind === "rare") return "approach";
  return posTag(s).tone || "neutral";
}
// the labelled-provenance rule clause: WHY the engine flagged this, in one plain sentence
// (NN/g labelled provenance — never hover-hidden). Calibrated by the same severityAdverb the
// old rows used; risk appended as the duty-of-care clause.
function brfRule(s) {
  let r;
  if (s.kind === "money") r = "the gap carries a £ cost against the peer median";
  else if (s.kind === "prevalence") r = "most of your peers provide this and you don't";
  else if (s.kind === "rare") r = "few of your peers make this choice";
  else if (s.position === "below" || s.position === "above")
    r = "your value sits " + severityAdverb(s) + (s.position === "below" ? "below" : "above") + " the peer median";
  else if (s.bucket === "peer position") r = "you sit apart from most of your peers here";
  else if (s.bucket === "context") r = "a neutral peer read — context, not a verdict";
  else r = "your approach differs from the usual peer pattern";
  if (s.risk_framed) r += ", and it carries duty-of-care risk";
  return r;
}
function brfChipText(s) {
  if (s.kind === "prevalence" || s.kind === "rare" || s.position === "differs" || s.position === "practice")
    return (s.tag || s.bucket || "").toLowerCase();
  const pt = posTag(s);
  return pt.text || (s.tag || s.bucket || "").toLowerCase();
}
const brfCap = t => t ? t.charAt(0).toUpperCase() + t.slice(1) : t;
const brfVerified = s => s.anchor_grade === "A" || s.anchor_grade === "B" || s.anchor_grade === "C";
// (brfFamKey / BRF_MKT_BUCKETS / BRF_DOT / BrfLater / BrfOverflow retired 2026-07-10 with the
// Folders simplification — the ledger bands and family roll-ups died with the two-tier split.)

// Snooze options — the same snooze_days API; the menu shows the actual return date.
const SIG_SNOOZE = [["1 week", 7], ["2 weeks", 14], ["Next cycle", 42]];
const sigRetDate = days => new Date(Date.now() + days * 86400000)
  .toLocaleDateString("en-GB", { day: "numeric", month: "short" });
// shared dropdown chrome: close on outside click / Escape (focus back on the trigger)
function useMenuClose(ref, open, setOpen) {
  useEffect(() => {
    if (!open) return;
    const away = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const esc = e => { if (e.key === "Escape") { setOpen(false); const t = ref.current && ref.current.querySelector("button"); if (t) t.focus(); } };
    document.addEventListener("mousedown", away); document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", esc); };
  }, [open]);
}
// "Snooze ▾" verb — labelled "Until…", each option shows its return date.
function SigSnoozeMenu({ onPick }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useMenuClose(ref, open, setOpen);
  return html`<span class="brf-later-wrap" ref=${ref}>
    <button type="button" class=${"brf-verb" + (open ? " on" : "")} aria-haspopup="true" aria-expanded=${open}
      onClick=${() => setOpen(o => !o)}>Snooze <span class="sfold-caret" aria-hidden="true">▾</span></button>
    ${open ? html`<div class="brf-menu" role="group">
      <div class="brf-menu-lbl">Until…</div>
      ${SIG_SNOOZE.map(([lab, days]) => html`<button key=${days} class="brf-menu-opt"
        onClick=${() => { setOpen(false); onPick(days, lab); }}>${lab}<span class="sfold-ret num">${sigRetDate(days)}</span></button>`)}
    </div>` : null}
  </span>`;
}
// "Save ▾" / "Move to… ▾" verb — existing folder names + an inline "New folder…" name input.
function SigFolderMenu({ label, folders, exclude, onPick }) {
  const [open, setOpen] = useState(false);
  const [naming, setNaming] = useState(false);
  const [nm, setNm] = useState("");
  const ref = useRef(null);
  useMenuClose(ref, open, setOpen);
  const pick = name => { setOpen(false); setNaming(false); setNm(""); onPick(name); };
  const commit = () => { const t = nm.trim(); if (t) pick(t); };
  const opts = (folders || []).filter(f => f !== exclude);
  return html`<span class="brf-later-wrap" ref=${ref}>
    <button type="button" class=${"brf-verb" + (open ? " on" : "")} aria-haspopup="true" aria-expanded=${open}
      onClick=${() => { setOpen(o => !o); setNaming(false); setNm(""); }}>${label} <span class="sfold-caret" aria-hidden="true">▾</span></button>
    ${open ? html`<div class="brf-menu" role="group">
      ${opts.length ? html`<div class="brf-menu-lbl">To folder…</div>` : null}
      ${opts.map(f => html`<button key=${f} class="brf-menu-opt" onClick=${() => pick(f)}>
        <${Icon} name="folder" size=${12} /> ${f}</button>`)}
      ${naming ? html`<div class="sfold-newrow">
        <input type="text" class="sfold-newinput" placeholder="Folder name" maxlength="40" value=${nm}
          ref=${el => el && el.focus()} onInput=${e => setNm(e.target.value)}
          onKeyDown=${e => { if (e.key === "Enter") { e.preventDefault(); commit(); } }} />
        <button type="button" class="sfold-newgo" disabled=${!nm.trim()} onClick=${commit}>Add</button>
      </div>` : html`<button class="brf-menu-opt" onClick=${() => setNaming(true)}>
        <${Icon} name="plus" size=${12} /> New folder…</button>`}
    </div>` : null}
  </span>`;
}
// small "…" on the ACTIVE folder pill — Rename / Delete, kept minimal (delete returns the
// folder's signals to the plain feed; it never deletes a signal).
function SigFolderOps({ name, onRename, onDelete }) {
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [nm, setNm] = useState(name);
  const ref = useRef(null);
  useMenuClose(ref, open, setOpen);
  const commit = () => { const t = nm.trim(); if (t && t !== name) onRename(t); setOpen(false); setRenaming(false); };
  return html`<span class="brf-later-wrap" ref=${ref}>
    <button type="button" class="sfold-ops" aria-haspopup="true" aria-expanded=${open}
      aria-label=${"Folder options — " + name} title="Rename or delete this folder"
      onClick=${() => { setOpen(o => !o); setRenaming(false); setNm(name); }}><span aria-hidden="true">⋯</span></button>
    ${open ? html`<div class="brf-menu" role="group">
      ${renaming ? html`<div class="sfold-newrow">
        <input type="text" class="sfold-newinput" maxlength="40" value=${nm}
          ref=${el => el && el.focus()} onInput=${e => setNm(e.target.value)}
          onKeyDown=${e => { if (e.key === "Enter") { e.preventDefault(); commit(); } }} />
        <button type="button" class="sfold-newgo" disabled=${!nm.trim()} onClick=${commit}>Save</button>
      </div>` : [
        html`<button key="r" class="brf-menu-opt" onClick=${() => setRenaming(true)}><${Icon} name="pencil" size=${12} /> Rename</button>`,
        html`<button key="d" class="brf-menu-opt" onClick=${() => { setOpen(false); onDelete(); }}><${Icon} name="close" size=${12} /> Delete folder</button>`,
      ]}
    </div>` : null}
  </span>`;
}

// The per-signal "why this is ranked" line (David 2026-07-10): renders the engine's
// strategy_influence (which reward-strategy inputs moved this signal + direction) as ONE quiet
// navy fact — explains the ranking, never advises. Empty when strategy is off/unset. Navy, not RAG.
const STRAT_AIM_TEXT = { lag: "below-market", match: "on-market", lead: "above-market" };
// natural per-(field, value) phrase — so the line reads "…by your cost objective" / "…by your
// crisis footing", never "your shock current pressure". Fallback: the field's generic phrase.
const STRAT_PHRASE = {
  primary_objective: { cost: "your cost objective", attract: "your attract objective", retain: "your retention objective", compliance: "your compliance objective", hold: "your steady-state objective" },
  pay_for_performance: { strong: "your strong pay-for-performance stance", egal: "your egalitarian-pay stance" },
  transparency: { open: "your open-pay goal" },
  budget_direction: { investing: "your investment budget", pressure: "your budget pressure" },
  acute_pressure: { scaling: "your scaling push", shock: "your crisis footing" },
  risk_appetite: { early: "your early-adopter appetite", wait: "your wait-and-see stance" },
  benefits_lead: {},
};
const STRAT_FIELD_GENERIC = {
  primary_objective: "your reward objective", pay_for_performance: "your pay-for-performance stance",
  transparency: "your transparency stance", budget_direction: "your budget direction",
  acute_pressure: "your current pressure", risk_appetite: "your risk appetite", benefits_lead: "your wellbeing focus",
};
function _stratPhrase(x) {
  return (STRAT_PHRASE[x.field] || {})[x.value] || STRAT_FIELD_GENERIC[x.field] || "your strategy";
}
function sigStratLine(infl) {
  if (!infl || !infl.length) return null;
  const aim = infl.find(x => x.field === "aim");
  const nudge = (dir) => infl.filter(x => x.dir === dir).map(_stratPhrase);
  const parts = [];
  if (aim) parts.push("against your " + (STRAT_AIM_TEXT[aim.value] || aim.value) + " aim" + (aim.domain ? " on " + domainLabel(aim.domain) : ""));
  const ups = nudge("up"), downs = nudge("down");
  if (ups.length) parts.push("ranked up by " + ups.join(", "));
  if (downs.length) parts.push("ranked down by " + downs.join(", "));
  if (!parts.length) return null;
  const s = parts.join(" · ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}
window.SignalsPage = function ({ me, prefs, onPref, cut, cuts }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const _ret = returnUiState("lumi-signals-ui") || {};   // Back-leg restore (Pack 1 §1)
  // active view: {kind:"all"} | {kind:"folder",name} | {kind:"snoozed"} | {kind:"dismissed"}
  const [view, setView] = useState(_ret.view && _ret.view.kind ? _ret.view : { kind: "all" });
  // (stubs state retired 2026-07-10, David: toast instead of stub rows — an actioned card
  // now leaves the list with a soft exit and the Undo rides the confirmation toast.)
  const [acting, setActing] = useState({});            // optimistic status overrides
  const [actingSnz, setActingSnz] = useState({});      // optimistic snooze_until (ISO) so the chip shows before a refetch
  const [jumpTo, setJumpTo] = useState(null);          // strategy-check → domain signpost
  const [navNaming, setNavNaming] = useState(false);   // "+ New folder" inline name input
  const [navNm, setNavNm] = useState("");
  // Folder names + assignments persist on the SAME per-user prefs store the other pages use
  // (OverviewPage's onPref pattern; PUT /api/prefs debounced in app.js), under "_signals".
  // localStorage is only a defensive fallback for a mount without the prefs props — the
  // router passes them (app.js route table), so it shouldn't run in practice.
  const [lsSig, setLsSig] = useState(() => { try { return JSON.parse(localStorage.getItem("lumi-signals-folders") || "null"); } catch (e) { return null; } });
  const sigP = (prefs && prefs._signals) || (onPref ? null : lsSig) || {};
  const folders = sigP.folders || [];
  const assign = sigP.assign || {};
  const writeSig = next => {
    if (onPref) onPref("_signals", next);
    else { try { localStorage.setItem("lumi-signals-folders", JSON.stringify(next)); } catch (e) {} setLsSig(next); }
  };
  // …stash the working set on every change, so the next openMetric→Back restores it
  useEffect(() => { saveUiState("lumi-signals-ui", { view }); }, [view]);
  // Signals now honour the app-wide PEER CUT (David 2026-07-10: the page hardcoded all-peers and
  // ignored the selector) AND the overview strategy toggle (so the strategy re-rank + the per-signal
  // "why ranked" line degrade to pure market when strategy is off). Same source-of-truth params as
  // every other bench surface — cutQS + &strategy=off — so the feed recomputes on the chosen group.
  const _applyStrat = ((prefs && prefs._overview) || {}).apply_strategy !== false;
  const _cutKey = cut ? cutKeyOf(cut) : "all";
  useEffect(() => {
    let live = true;
    setData(null);
    apiCached("/api/overview?" + cutQS(cut) + (_applyStrat ? "" : "&strategy=off")).then(d => {
      if (!live) return;
      setData(d);
      // viewing the Signals page clears NEW: mark every current signal seen
      const ids = (d.signals_all || []).map(s => s.sig_id || s.question_id);
      if (ids.length) api("/api/signals/seen", { method: "POST", body: { sig_ids: ids } }).catch(() => {});
    }).catch(e => { if (live) setErr(e.message); });
    return () => { live = false; };
  }, [_cutKey, _applyStrat]);
  // Strategy-check signpost: the feed is flat now, so jump to the FIRST card of the target
  // domain (every card carries data-dom) and flash it — same sig-group-flash as before.
  useEffect(() => {
    if (!jumpTo) return;
    const el = document.querySelector('.brf-card[data-dom="' + (window.CSS && CSS.escape ? CSS.escape(jumpTo) : jumpTo) + '"]');
    if (el) {
      scrollIntoViewSafe(el, { block: "start" });
      el.classList.add("sig-group-flash");
      setTimeout(() => el.classList.remove("sig-group-flash"), 1700);
    }
    setJumpTo(null);
  }, [jumpTo, view]);
  const goToDomain = (dom) => { setView({ kind: "all" }); setJumpTo(dom); };
  if (err) return html`<${EmptyState} icon="flag" title="Couldn't load your signals" body=${err}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!data) return html`
    <div>
      <div class="skel" style=${{ height: "30px", width: "180px", marginBottom: "var(--s3)" }}></div>
      <div class="skel" style=${{ height: "20px", width: "420px", marginBottom: "var(--s4)" }}></div>
      <div class="skel" style=${{ height: "36px", width: "520px", marginBottom: "var(--s4)", borderRadius: "999px" }}></div>
      ${[0, 1, 2, 3].map(i => html`<div key=${i} class="skel" style=${{ height: "120px", marginBottom: "var(--s3)", borderRadius: "14px" }}></div>`)}
    </div>`;
  const contrib = data.contribution || {};
  const unlocked = data.contribution ? !!contrib.insights_unlocked : !(data.callouts && data.callouts.gaps_locked);
  // triage identity is sig_id (= question_id, or qid::row_id for a matrix row)
  const sidOf = s => s.sig_id || s.question_id;
  const all = (data.signals_all || []).map(s => { const sid = sidOf(s);
    return { ...s, status: acting[sid] !== undefined ? acting[sid] : (s.status || null),
             snooze_until: actingSnz[sid] !== undefined ? actingSnz[sid] : s.snooze_until }; });
  const signalDomains = new Set(all.filter(s => s.status !== "dismissed").map(s => s.domain).filter(Boolean));

  const setStatus = (sid, status, days) => {
    setActing(a => ({ ...a, [sid]: status }));
    setActingSnz(m => ({ ...m, [sid]: status === "snoozed" ? new Date(Date.now() + days * 86400000).toISOString() : null }));
    api("/api/signals/action", { method: "POST", body: { question_id: sid, status: status || "active", ...(days ? { snooze_days: days } : {}) } })
      .then(() => apiCacheInvalidate("/api/overview"))
      .catch(() => { setActing(a => { const n = { ...a }; delete n[sid]; return n; }); toast("Couldn't save that — try again", "error"); });
  };

  // ---- verbs (2026-07-10, David: toast instead of stub rows). Every action lets the card
  // leave the list with a soft exit (leaveThen), then a single confirmation toast carries
  // the Undo — the same restore paths the in-place stubs used, so nothing is lost.
  const sigToast = (msg, undo) => {
    const h = document.getElementById("toast-host"); if (h) h.textContent = "";   // one at a time
    toast(msg, null, { label: "Undo", fn: undo }); };
  const leaveThen = (sid, fn) => {
    const esc = window.CSS && CSS.escape ? CSS.escape(sid) : sid;
    const el = document.querySelector('.brf-card[data-sid="' + esc + '"]');
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!el || reduce) { fn(); return; }                 // reduced-motion (or no node): snap
    el.style.height = el.offsetHeight + "px";
    void el.offsetHeight;                                // commit the measured height first
    el.classList.add("brf-leave");
    el.style.height = "0px";
    setTimeout(fn, 240);
  };
  const sigName = s => s.name || s.label_short;

  const saveTo = (s, name) => { const sid = sidOf(s); leaveThen(sid, () => {
    const fl = folders.includes(name) ? folders : [...folders, name];
    writeSig({ folders: fl, assign: { ...assign, [sid]: name } });
    setStatus(sid, "saved");
    sigToast("Saved to “" + name + "” — " + sigName(s), () => {
      const na = { ...assign }; delete na[sid]; writeSig({ folders: fl, assign: na });
      setStatus(sid, null); }); }); };
  const snoozeIt = (s, days) => { const sid = sidOf(s); leaveThen(sid, () => {
    setStatus(sid, "snoozed", days);
    sigToast("Snoozed until " + sigRetDate(days) + " — " + sigName(s), () => setStatus(sid, null)); }); };
  const dismissIt = (s) => { const sid = sidOf(s); leaveThen(sid, () => {
    setStatus(sid, "dismissed");
    sigToast("Dismissed — recover any time from the Dismissed folder", () => setStatus(sid, null)); }); };

  // ---- folder-view verbs (same pattern: exit + toast-borne Undo)
  const moveTo = (s, name) => { const sid = sidOf(s); const prev = assign[sid]; leaveThen(sid, () => {
    const fl = folders.includes(name) ? folders : [...folders, name];
    writeSig({ folders: fl, assign: { ...assign, [sid]: name } });
    sigToast("Moved to “" + name + "” — " + sigName(s), () => writeSig({ folders: fl, assign: { ...assign, [sid]: prev } })); }); };
  const unfolder = (s) => { const sid = sidOf(s); const prev = assign[sid]; leaveThen(sid, () => {
    const na = { ...assign }; delete na[sid]; writeSig({ folders, assign: na });
    setStatus(sid, null);
    sigToast("Back in your feed — " + sigName(s),
      () => { writeSig({ folders, assign: { ...assign, [sid]: prev } }); setStatus(sid, "saved"); }); }); };
  const wake = (s) => { const sid = sidOf(s);
    const iso = s.snooze_until ? (s.snooze_until.includes("T") ? s.snooze_until : s.snooze_until.replace(" ", "T") + "Z") : null;
    const days = iso ? Math.max(1, Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000)) : 14;
    leaveThen(sid, () => { setStatus(sid, null);
      sigToast("Awake — back in your feed — " + sigName(s), () => setStatus(sid, "snoozed", days)); }); };
  const recover = (s) => { const sid = sidOf(s); leaveThen(sid, () => { setStatus(sid, null);
    sigToast("Recovered — back in your feed — " + sigName(s), () => setStatus(sid, "dismissed")); }); };

  // ---- folder ops (rename keeps every assignment; delete returns signals to the feed —
  // assignments clear, statuses untouched, nothing is deleted)
  const renameFolder = (from, to) => {
    if (folders.includes(to)) { toast("A folder with that name already exists", "error"); return; }
    const na = {}; Object.keys(assign).forEach(k => { na[k] = assign[k] === from ? to : assign[k]; });
    writeSig({ folders: folders.map(f => f === from ? to : f), assign: na });
    if (view.kind === "folder" && view.name === from) setView({ kind: "folder", name: to }); };
  const deleteFolder = (name) => {
    const ids = Object.keys(assign).filter(k => assign[k] === name);
    const na = { ...assign }; ids.forEach(k => delete na[k]);
    writeSig({ folders: folders.filter(f => f !== name), assign: na });
    setView({ kind: "all" });
    toast('Folder "' + name + '" deleted — ' + (ids.length ? "its " + ids.length + " signal" + (ids.length === 1 ? "" : "s") + " returned to your feed" : "it was empty")); };
  const commitNavFolder = () => { const t = navNm.trim(); if (!t) return;
    if (!folders.includes(t)) writeSig({ folders: [...folders, t], assign });
    setNavNaming(false); setNavNm(""); setView({ kind: "folder", name: t }); };

  // ---- the sets. The feed is every live (non-snoozed, non-dismissed) signal that isn't
  // filed in a named folder; folders + Snoozed + Dismissed partition the rest, so the pill
  // counts always reconcile to the total. Machine order kept from the Briefing:
  // new → risk → worth → |gap| → n, one flat list, ALL loaded (no pagination).
  const present = new Set(all.map(sidOf));
  const cntFolder = name => Object.keys(assign).filter(k => assign[k] === name && present.has(k)).length;
  // (stubFor retired 2026-07-10, David: toast instead of stub rows — an actioned card simply
  // leaves the feed; the Undo lives on the toast, so no placeholder row holds its slot.)
  const feedItems = all.filter(s => s.status !== "dismissed" && s.status !== "snoozed" && !assign[sidOf(s)]);
  const ordKey = s => [s.new ? 0 : 1, s.risk_framed ? 0 : 1, s.worth ? 0 : 1, -(s.gap_pct || 0), -(s.n || 0)];
  feedItems.sort((a, b) => { const ka = ordKey(a), kb = ordKey(b);
    for (let i = 0; i < ka.length; i++) { if (ka[i] !== kb[i]) return ka[i] - kb[i]; } return 0; });
  const feedN = feedItems.length;
  const snoozedItems = all.filter(s => s.status === "snoozed");
  const dismissedItems = all.filter(s => s.status === "dismissed");
  // a folder deleted elsewhere (another tab) can leave a stale view — fall back to the feed
  const v = (view.kind === "folder" && !folders.includes(view.name)) ? { kind: "all" } : view;
  const viewItems = v.kind === "folder" ? all.filter(s => assign[sidOf(s)] === v.name)
    : v.kind === "snoozed" ? snoozedItems
    : v.kind === "dismissed" ? dismissedItems
    : feedItems;
  const emptyLine = v.kind === "folder" ? 'Nothing in "' + v.name + '" yet — Save a signal from the feed to file it here.'
    : v.kind === "snoozed" ? "Nothing snoozed — a snoozed signal waits here and returns to your feed on its date."
    : v.kind === "dismissed" ? "Nothing dismissed — anything you dismiss is kept here and can be recovered."
    : "Everything is filed — every signal is saved to a folder, snoozed or dismissed.";

  // ---- the evidence card (Briefing anatomy, unchanged): caption + risk shield, stand-
  // sentence headline, "Flagged because … · n · verified/estimate", soft chips, gap bar,
  // lens tag, On plan, "See the evidence →". Verbs vary by the active folder view.
  const sigCard = (s) => {
    const sid = sidOf(s);
    // (the in-place stub row retired 2026-07-10, David: toast instead of stub rows)
    const tone = brfTone(s);
    return html`<article key=${sid} class=${"brf-card brf-tone-" + tone} data-dom=${s.domain || ""} data-sid=${sid}>
      <div class="brf-cap">
        <span class="brf-cap-name">${s.name || s.label_short}</span>
        ${s.domain ? html`<span class="brf-cap-dom">· ${domainLabel(s.domain)}</span>` : null}
        ${s.new ? html`<span class="sig-new-tag">NEW</span>` : null}
        ${s.risk_framed ? html`<span class="brf-shield"><${Icon} name="shield" size=${10} /> risk</span>` : null}
        ${v.kind === "snoozed" && s.snooze_until ? html`<span class="sfold-snz"><${Icon} name="clock" size=${10} /> ${snoozeReturn(s.snooze_until)}</span>` : null}
      </div>
      <h3 class="brf-head">${brfCap(s.stand || s.detail)}</h3>
      <div class="brf-why"><b>Flagged because:</b> ${brfRule(s)}${s.n != null ? html`<span class="num"> · n=${s.n}</span>` : null}${provMark(s)}${s.strategy_note ? html`<span class="sig-strat-note"> · ${s.strategy_note}</span>` : null}</div>
      <div class="brf-chips">
        <span class=${"brf-pos brf-pos-" + tone}>${brfChipText(s)}</span>
        ${s.gap_pct != null ? html`<span class="brf-gapbar" title=${"About " + s.gap_pct + "% from the market median"} aria-hidden="true"><i style=${{ width: Math.max(6, Math.min(100, s.gap_pct)) + "%" }}></i></span>` : null}
        ${s.lens ? html`<span class="brf-lens">${s.lens}</span>` : null}
        ${s.confirm ? html`<span class="brf-onplan"><${Icon} name="check" size=${11} /> On plan</span>` : null}
      </div>
      ${s.strategy_influence && s.strategy_influence.length ? html`
        <div class="brf-strat"><${Icon} name="compass" size=${11} /> ${sigStratLine(s.strategy_influence)}</div>` : null}
      <div class="brf-verbs">
        ${v.kind === "all" ? html`
          <${SigFolderMenu} label="Save" folders=${folders} onPick=${n => saveTo(s, n)} />
          <${SigSnoozeMenu} onPick=${d => snoozeIt(s, d)} />
          <button type="button" class="brf-verb" onClick=${() => dismissIt(s)}>Dismiss</button>`
        : v.kind === "folder" ? html`
          <${SigFolderMenu} label="Move to…" folders=${folders} exclude=${v.name} onPick=${n => moveTo(s, n)} />
          <button type="button" class="brf-verb" onClick=${() => unfolder(s)}>Remove from folder</button>`
        : v.kind === "snoozed" ? html`
          <button type="button" class="brf-verb" onClick=${() => wake(s)}>Wake now</button>`
        : html`
          <button type="button" class="sfold-recover" onClick=${() => recover(s)}><${Icon} name="refresh" size=${12} /> Recover</button>`}
        <button type="button" class="brf-see" onClick=${() => openMetric(s.question_id)}>See the evidence <span aria-hidden="true">→</span></button>
      </div>
    </article>`;
  };

  const isFold = f => v.kind === "folder" && v.name === f;
  return html`
    <div class="signals-page brf-page" style=${{ maxWidth: "880px" }}>
      <div class="ov-aurora" aria-hidden="true"></div>
      <h1 class="display-title" style=${{ marginBottom: "var(--s1)" }}>Signals</h1>
      ${unlocked ? html`<p class="brf-std" style=${{ maxWidth: "680px", marginTop: 0 }}>Grounded in your peer data, never advice: <b>we flag, you decide</b>.</p>` : null}
      ${/* the page now HONOURS the peer selector (2026-07-10) — so its trust surface is the same
            ConfidenceChip as the masthead, reading the ACTIVE cut's n. The old hardcoded
            "Peer group: All peers · 220" line lied the moment a cut was chosen (David: "comparing
            against shows different sample to the text"). */ ""}
      ${unlocked ? html`<div class="conf-line" style=${{ justifyContent: "flex-start", marginTop: 0, marginBottom: "var(--s3)" }}>
        <${ConfidenceChip} n=${cutSize(cut, cuts, me.peer_pool)} window=${data.snapshot && data.snapshot.window} />
      </div>` : null}
      ${!unlocked ? html`<${SignalsLocked} contrib=${contrib} me=${me} />`
      : all.length === 0 ? html`
        <div class="signals-empty" style=${{ marginTop: "var(--s5)" }}>
          <span class="signals-empty-ring"><${Icon} name="flag" size=${18} /></span>
          <div class="caption" style=${{ maxWidth: "360px" }}>Nothing to flag yet — signals appear here as your position or the market moves.</div>
        </div>`
      : html`
        ${/* FOLDER NAV — the only control above the feed: All · user folders · Snoozed ·
              Dismissed · a quiet + New folder. The active user folder carries a small "…"
              (Rename / Delete). */ ""}
        <div class="sfold-nav" role="group" aria-label="Signal folders">
          <button type="button" class=${"sfold-pill" + (v.kind === "all" ? " on" : "")} aria-pressed=${v.kind === "all"}
            onClick=${() => setView({ kind: "all" })}>All signals <b class="num">${feedN}</b></button>
          ${folders.map(f => html`<span key=${"f-" + f} class="sfold-pillwrap">
            <button type="button" class=${"sfold-pill" + (isFold(f) ? " on" : "")} aria-pressed=${isFold(f)}
              onClick=${() => setView({ kind: "folder", name: f })}><${Icon} name="folder" size=${12} /> ${f} <b class="num">${cntFolder(f)}</b></button>
            ${isFold(f) ? html`<${SigFolderOps} name=${f} onRename=${to => renameFolder(f, to)} onDelete=${() => deleteFolder(f)} />` : null}
          </span>`)}
          <button type="button" class=${"sfold-pill" + (v.kind === "snoozed" ? " on" : "")} aria-pressed=${v.kind === "snoozed"}
            onClick=${() => setView({ kind: "snoozed" })}><${Icon} name="clock" size=${12} /> Snoozed <b class="num">${snoozedItems.length}</b></button>
          <button type="button" class=${"sfold-pill" + (v.kind === "dismissed" ? " on" : "")} aria-pressed=${v.kind === "dismissed"}
            onClick=${() => setView({ kind: "dismissed" })}><${Icon} name="check" size=${12} /> Dismissed <b class="num">${dismissedItems.length}</b></button>
          ${navNaming ? html`<span class="sfold-newrow sfold-newrow-nav">
            <input type="text" class="sfold-newinput" placeholder="Folder name" maxlength="40" value=${navNm}
              ref=${el => el && el.focus()} onInput=${e => setNavNm(e.target.value)}
              onKeyDown=${e => { if (e.key === "Enter") { e.preventDefault(); commitNavFolder(); }
                if (e.key === "Escape") { setNavNaming(false); setNavNm(""); } }} />
            <button type="button" class="sfold-newgo" disabled=${!navNm.trim()} onClick=${commitNavFolder}>Add</button>
          </span>` : html`<button type="button" class="sfold-new" onClick=${() => setNavNaming(true)}>+ New folder</button>`}
        </div>

        ${viewItems.length === 0 ? html`<div class="sfold-empty caption">${emptyLine}</div>` : viewItems.map(sigCard)}

        ${v.kind === "all" && data.strategy_complete ? html`<${StrategyCheck} onGoToDomain=${goToDomain} signalDomains=${signalDomains} />` : null}
        ${/* navy trust footer: the register + the promise — filing is never deletion */ ""}
        <div class="brf-navy">
          <div class="brf-navy-reg">
            <${Icon} name="table" size=${15} />
            <span><b>Full gap register</b> — every metric's presence against the market, beyond what crosses a threshold. <a href="#/priorities">Open the register</a>${me.user.role === "admin" ? html` · <a href="/api/gap-register.csv" download>Download CSV</a>` : null}</span>
          </div>
          <div class="brf-life"><span class="brf-life-note">Snooze and Dismiss file signals into their folders — <b>nothing is deleted</b>.</span></div>
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
      <div class="card cat-tile cat-tile-practice" onClick=${() => nav("/category/" + encodeURIComponent(d.name))}>
        <h3 class="cat-tile-name"><button class="cat-open" onClick=${e => { e.stopPropagation(); nav("/category/" + encodeURIComponent(d.name)); }}>
          <span class="cat-icon"><${Icon} name=${CAT_ICON[d.name] || "award"} size=${14} /></span>${domainLabel(d.name)}</button></h3>
        ${pending ? html`<div class="caption num cat-pending-note">Appears once your data is in</div>`
          : (pool ? html`
            <div class="cat-axis num">off the norm</div>
            <div class="catp-bar" title="How many of this area's practices are off the norm — a different way of doing things, not a gap."
              role="img" aria-label=${differ + " of " + pool + " practices off the norm."}>
              <div class="catp-bar-fill" style=${{ width: fr + "%" }}></div></div>
            <div class="cat-differ num"><span class="cat-differ-dot"></span><span class="cat-differ-txt"><b>${differ}</b> of ${pool} off the norm</span></div>`
          : html`<div class="caption num" style=${{ marginTop: "var(--s2)" }}>${prev.pool || 0} practices tracked</div>`)}
      </div>`;
  }

  // MARKET LENS (default): the verdict chip + proportional below/on/above bar with the
  // per-domain lean needle. The practice differ line now lives in the Practice view.
  // PENDING (brand-new org, gaps_locked): the market view had NO pending guard, so a
  // no-data tile fell through to the "practice view" chip + an empty bar — the 7 tiles
  // read as populated jargon while the gauge + signals above correctly said "not enough
  // data". Match the practice view's pending treatment so the whole hero speaks with one
  // voice on day one. (2026-07-07 new-user empty-state review.)
  if (pending) {
    return html`
      <div class="card cat-tile v-practice cat-tile-pending" onClick=${() => nav("/category/" + encodeURIComponent(d.name))}>
        <h3 class="cat-tile-name"><button class="cat-open" onClick=${e => { e.stopPropagation(); nav("/category/" + encodeURIComponent(d.name)); }}>
          <span class="cat-icon"><${Icon} name=${CAT_ICON[d.name] || "award"} size=${14} /></span>${domainLabel(d.name)}</button></h3>
        <div class="caption num cat-pending-note">Appears once your data is in</div>
      </div>`;
  }
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
    <div class=${"card cat-tile " + vCls + (noRate ? " cat-tile-norate" : "")} onClick=${() => nav("/category/" + encodeURIComponent(d.name))}>
      ${/* a11y: the tile div is a mouse convenience; the NAME is the real control
            (h3 for the page outline; indic-flag stays a focusable sibling, not a
            descendant of an interactive — no nested-interactive violation). */ ""}
      <h3 class="cat-tile-name"><button class="cat-open" onClick=${e => { e.stopPropagation(); nav("/category/" + encodeURIComponent(d.name)); }}>
        <span class="cat-icon"><${Icon} name=${CAT_ICON[d.name] || "award"} size=${14} /></span>${domainLabel(d.name)}</button></h3>
      <span class="row" style=${{ gap: "var(--s1)", alignSelf: "flex-start", alignItems: "center" }}>
        <span class=${"chip tile-chip " + chipCls + (indicative ? " chip-indicative" : "")} title=${evNote}>${chip}</span>
        ${indicative && html`<span class="indic-flag" tabindex="0" role="note" onKeyDown=${e => { if (e.key === "Escape") e.currentTarget.blur(); }}><${Icon} name="info" size=${11} /> indicative<span class="indic-tip">Verdict shown with limited comparable data — treat as a directional read.</span></span>`}
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
          title="No market rate to be under or over — these are approach choices, not a market position.">N/A</div>
        <div class="cat-na-note">Approach choices — no market rate to sit above or below.</div>` : html`
        <div class="tile-band" style=${{ margin: "2px 0 0" }}>
          <div class="tile-fill" style=${{ width: (prev.pool ? Math.round(100 * prev.with_majority / prev.pool) : 0) + "%" }}></div>
        </div>
        ${prev.with_majority != null && html`<div class="caption num" title=${prev.verdict || ""}>${prev.with_majority}/${prev.pool} ${prev.states.with_majority}</div>`}`}
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

/* (OpportunityTile retired 2026-07-06 — dead since the 80/20 hero moved the £
   opportunity into money signals; it rendered nowhere. The UnlockMoment button
   now points at Signals, where the £ flags actually live.) */

/* "Your journey" strip — BUILT at the 80/20 redesign, wired 2026-07-06. One
   snapshot = the baseline state below; when a second collection period exists
   this strip is where "since last cycle" movement returns. Slim horizontal
   band under the hero row: the sparkline seeds the expectation that the
   dashboard is a moving story, not a static readout. */
window.TrajectoryTile = function ({ windowLabel }) {
  return html`
    <div class="ov-journey">
      <svg viewBox="0 0 170 44" class="ov-journey-spark" aria-hidden="true">
        <polyline points="4,30 40,30" stroke="var(--blue)" stroke-width="2.5" fill="none" stroke-linecap="round"/>
        <circle cx="40" cy="30" r="5" fill="var(--blue)"/>
        <circle cx="40" cy="30" r="9" fill="none" stroke="var(--blue-tint-2)" stroke-width="2"/>
        <polyline points="40,30 80,24 120,20 160,12" stroke="var(--blue-tint-2)" stroke-width="2" stroke-dasharray="3 4" fill="none"/>
        <circle cx="160" cy="12" r="3.5" fill="none" stroke="var(--blue-tint-2)" stroke-width="1.5"/>
      </svg>
      <div class="ov-journey-copy caption">
        <b>This is your ${windowLabel ? windowLabel + " " : ""}baseline.</b>${" "}
        From your next cycle you'll see exactly where you've moved — every card grows a "vs last time" story.
      </div>
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
    // Ship review 2026-07-09 B4 (cut-switch race, reproduced live: all 243 cards swapped
    // to n=220 figures under a "Retail · 15" selector): the live-flag guard — the house
    // pattern from DomainSummary/MetricPage/BenchmarkCard — so a slower older cut's
    // response can never land after the newer one and render under the wrong label.
    let live = true;
    setData(null); setErr(null);
    api(`/api/benchmarks/${encodeURIComponent(sp)}?` + cutQS(cut))
      .then(d => { if (live) setData(d); }).catch(e => { if (live) setErr(e.message); });
    // signals come from the same computed data the home/category pages use; one
    // fetch per page builds the qid -> signal map for every card's status pill
    apiCached("/api/overview?" + cutQS(cut)).then(o => {
      if (!live) return;
      const m = {}; (o.signals_all || []).forEach(s => { (m[s.question_id] = m[s.question_id] || []).push(s); }); setSigMap(m);
    }).catch(() => { if (live) setSigMap({}); });
    return () => { live = false; };
  }, [sp, cutKeyOf(cut)]);
  useEffect(() => {
    if (data && focusQ) {
      const el = document.getElementById("q-" + focusQ);
      if (el) scrollIntoViewSafe(el);
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
  // Honest-header (interim, 2026-06-30): disclose rated-vs-recorded so the two donut
  // subset-lenses reconcile with the "N benchmarks" headline. PURE DISPLAY — derived
  // from the pool flags each card already carries (market_band ⇔ position donut,
  // prevalence_band ⇔ alignment donut). A card in BOTH pools is one card in `cards`,
  // so the union counts each metric ONCE (no overlap arithmetic to drift). Respects the
  // active filters because it reads the same post-filter `cards` the headline counts.
  // NOT the routing fix — the "not yet rated" remainder is the open gate-conflation gap.
  const _positioned = cards.filter(c => c.market_band).length;
  const _aligned = cards.filter(c => c.prevalence_band).length;
  const _both = cards.filter(c => c.market_band && c.prevalence_band).length;
  const _rated = cards.filter(c => c.market_band || c.prevalence_band).length;
  const _recorded = cards.length - _rated;
  const _ratedParts = [_positioned ? `${_positioned} positioned` : null,
                       _aligned ? `${_aligned} aligned` : null].filter(Boolean).join(" + ");
  const _ratedTip = `${_rated} rated${_ratedParts ? " = " + _ratedParts : ""}`
    + (_both ? ` (${_both} counted in both)` : "")
    + (_recorded ? `. ${_recorded} not yet rated.` : ".");
  // Suppressed in the reduced/data-pending contributor state: those cards carry no band
  // fields, so any count would be a false "0 rated". Show the plain headline instead.
  const _ratedClause = data.reduced ? null : html`<span style=${{ cursor: "help", borderBottom: "1px dotted currentColor" }}
    title=${_ratedTip} aria-label=${_ratedTip}> · ${_rated} rated${_recorded ? ` · ${_recorded} not yet rated` : ""}</span>`;
  return html`
    <div>
      <div class="page-head">
        <div class="titleblock">
          <div class="sp-glyph"><${SpIcon} sp=${sp} size=${20} /></div>
          <div>
            <h1 class="display-title">${subF || (window.SCOPE && window.SCOPE.focused ? "All reward" : sp)}</h1>
            ${/* "peer group: …" dropped 2026-07-07 — it duplicated the "Comparing against"
                  peer bar directly above this header (declutter). */ ""}
            <div class="caption meta">${cards.length} benchmarks${_ratedClause}${subF && window.SCOPE && window.SCOPE.focused ? " · part of your reward benchmark" : ""}${me && me.peer_pool && me.peer_pool.collection_window ? ` · benchmark data: ${me.peer_pool.collection_window}` : (me && me.snapshots && me.snapshots[0] ? ` · benchmark data: ${me.snapshots[0].collection_window}` : "")}</div>
          </div>
        </div>
        <div class="controls" style=${{ alignItems: "flex-start" }}>
          <div class="ctlgroup">
            <select class="ctl" aria-label="Filter by question type" value=${cat} onChange=${e => setCat(e.target.value)}>
              <option value="">All question types</option>
              <option value="metric">Metrics</option><option value="practice">Practices</option>
              <option value="policy">Policies</option><option value="benefit">Benefits</option>
            </select>
          </div>
          <div class="ctlgroup">
            <select class="ctl" aria-label="Filter by signal" value=${sigF} onChange=${e => setSigF(e.target.value)}>
              <option value="">All signals</option>
              <option value="signal">Flagged · ${sigCounts.signal}</option>
              <option value="add">Needs data · ${sigCounts.add}</option>
              <option value="clear">No signal · ${sigCounts.clear}</option>
            </select>
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
function DomainSummary({ name, cut, applyStrat, embedded, aiNudge }) {
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
  // EMBEDDED FORMAT (David 2026-07-13, "look at the format"): inside the briefing the
  // "notable" slot is a wall of truncated fragments DUPLICATING the drivers list beside it,
  // and the slot labels re-say what the read band above already shows — so embedded renders
  // just position + practices as two clean paragraphs, provenance as the quiet foot. The
  // standalone variant keeps all slots.
  const EMB_SLOTS = SLOTS.filter(([k]) => k !== "notable");
  // the tag is honest about the SOURCE (gate split 2026-07-13): AI wording only when the
  // model actually wrote it; the deterministic floor is labelled as composed from figures
  const tag = st.source === "model" ? "AI-generated · a description of your data, not advice"
                                    : "written from your figures · not advice";
  const mkBody = (slots, labels) => st.phase === "loading" ? html`
      <div class="cat-summary-body">${[0, 1, 2].map(i => html`<div key=${i} class="cat-sum-skel"></div>`)}</div>` :
    st.phase === "error" ? html`
      <div class="cat-summary-body"><p class="caption">Couldn't load this summary — ${st.error}.</p></div>` :
    html`
      <div class="cat-summary-body">
        ${slots.map(([k, label]) => f[k] ? html`
          <div key=${k} class="cat-sum-part">
            ${labels ? html`<div class="cat-sum-label">${label}</div>` : null}
            <p class="cat-sum-text">${f[k]}</p>
          </div>` : null)}
        ${f.provenance ? html`<div class="cat-sum-prov">${f.provenance}</div>` : null}
        ${aiNudge && st.phase === "done" && st.source !== "model" ? html`
          <div class="cat-sum-caveat">AI Insights can write this in fuller prose — <a href="#/settings">review ${"&"} enable</a>.</div>` : null}
      </div>`;
  const body = mkBody(SLOTS, true);
  if (embedded) return html`
    <div class="cat-brief-narrwrap">
      <div class="cat-brief-collab">The read <span class="cat-brief-collab-sub">· ${tag}</span></div>
      ${mkBody(EMB_SLOTS, false)}
    </div>`;
  return html`
    <section class="cat-section cat-summary">
      <div class="cat-sec-head"><span class="cat-sec-ico cat-sum-ico"><${Icon} name="sparkle" size=${14} /></span>
        <b>How your ${domainLabel(name)} reads</b>
        <span class="cat-ai-tag">${tag}</span></div>
      ${body}
    </section>`;
}

window.CategoryPage = function ({ name, cut, cuts, prefs, onPref, onPin, pinnedIds, me, onCut, onTwinInfo, refreshMe }) {
  const [ov, setOv] = useState(null);
  const [bench, setBench] = useState(null);
  const [err, setErr] = useState(null);
  // Ship review 2026-07-09 Pack 1 §2: the chip/type filters ride the same Back-leg
  // restore as the Signals page (returnUiState — only when lumi-return points here),
  // so the scroll offset App restores lands on the SAME working set, not a reset grid.
  const _fret = returnUiState("lumi-cat-ui");
  const _fl = (_fret && _fret.name === name) ? _fret : null;
  const [type, setType] = useState(_fl ? _fl.type || "" : "");
  const [posSel, setPosSel] = useState(_fl ? _fl.posSel || [] : []);     // market-position chip filter (multi-select; [] = all)
  const [prevSel, setPrevSel] = useState(_fl ? _fl.prevSel || [] : []);  // practice-prevalence chip filter — MUTUALLY EXCLUSIVE with posSel
  const [noneSel, setNoneSel] = useState(_fl ? !!_fl.noneSel : false);   // "no reading yet" chip (cards in neither lens)
  const [dl, setDl] = useState(false);   // Download-analysis menu (hook stays ABOVE the early returns)
  useEffect(() => { saveUiState("lumi-cat-ui", { name, type, posSel, prevSel, noneSel }); },
    [name, type, posSel, prevSel, noneSel]);
  // PART B (2026-06-24) — honour the overview's strategy-off toggle so the attainment lens
  // stays consistent across surfaces: when the user has turned their strategy OFF on the
  // overview (persisted pref _overview.apply_strategy === false), fetch this category with
  // &strategy=off too, so market.target comes back null → aim null → attainTone yields the
  // grey "no judgement" hue here as well (no separate flag; same source of truth, same param
  // as the overview at line ~45). Real-aim by default.
  const _ovp = (prefs && prefs._overview) || {};
  const applyStrat = _ovp.apply_strategy !== false;
  const [catRetry, setCatRetry] = useState(0);
  const _fltMounted = useRef(false);   // skip the filter reset on mount so a Back-leg restore survives
  useEffect(() => {
    // Ship review 2026-07-09 B4 (cut-switch race): live-flag guard (house pattern —
    // DomainSummary/MetricPage/BenchmarkCard) so a slower older cut's response can't
    // land after the newer one and paint the wrong peer group under the new label.
    let live = true;
    setOv(null); setBench(null); setErr(null);
    // filters still reset on a REAL name/cut change — just not on the first run,
    // which may carry the restored Back-leg working set (Pack 1 §2 above).
    if (_fltMounted.current) { setType(""); setPosSel([]); setPrevSel([]); setNoneSel(false); }
    _fltMounted.current = true;
    Promise.all([
      apiCached("/api/overview?" + cutQS(cut) + (applyStrat ? "" : "&strategy=off")),
      apiCached("/api/benchmarks/Reward?" + cutQS(cut)),
    ]).then(([o, b]) => { if (live) { setOv(o); setBench(b); } }).catch(e => { if (live) setErr(e.message); });
    return () => { live = false; };
  }, [name, cutKeyOf(cut), applyStrat, catRetry]);

  // ONE-ROW MASTHEAD (David 2026-07-13, "the nav takes way too much space"): crumb, title,
  // confidence, peer selector and Download share a single row — the app-level PeerSetBar
  // strip and the standalone badge row are gone (the Overview's own pattern). The selector
  // and badge render in the LOADING state too, so switching cuts never loses the control.
  const _unlocked = me.contribution && me.contribution.insights_unlocked;
  const _sampleN = cutSize(cut, cuts, me.peer_pool);
  // glyph + "N benchmarks" meta dropped (David 2026-07-13): the icon decorated, the count
  // already lives in the briefing header ("of 59") and the grid header ("59 shown") — the
  // masthead is crumb · title · controls, nothing else.
  const Head = (meta, actions) => html`
    <div class="page-head cat-masthead">
      <div class="titleblock">
        <h1 class="display-title">${domainLabel(name)}</h1>
      </div>
      <div class="controls cat-masthead-ctl">
        ${_unlocked ? html`<${ConfidenceChip} n=${_sampleN} window=${me.peer_pool && me.peer_pool.collection_window} />` : null}
        <${PeerSetBar} me=${me} cut=${cut} cuts=${cuts} onSelect=${onCut} onTwinInfo=${onTwinInfo}
          inline=${true} prefs=${prefs} onPref=${onPref} refreshMe=${refreshMe} />
        ${actions || null}
      </div>
    </div>`;

  if (err) return html`<${EmptyState} title="Couldn't load this category"
    body=${err + " — nothing is lost; it usually works on a retry."}
    action=${html`<button class="btn small primary" onClick=${() => setCatRetry(k => k + 1)}>Retry</button>`} />`;
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
  // §2 second filter DIMENSION (prevalence-filtering Pass B): c.prevalence_band (match/common_alt/
  // rarer, the SAME prevalence_items pool the §1 donut counts; null = not a prevalence-rated
  // practice). MUTUALLY EXCLUSIVE with position (the two are near-disjoint — cross-AND mostly
  // empties the grid; only one group is ever non-empty, enforced in the chip handlers), so this
  // AND-chains as a no-op when prevSel is empty. null-safe (includes(null) is false).
  const cardPrevBand = c => c.prevalence_band;
  // FILTER FIXES (2026-07-09, David: "the filters seem odd"): (a) chip counts recompute against
  // the TYPE-filtered set, so a chip's number always equals what clicking it shows (they lied
  // under the type dropdown before); (b) "no reading yet" chip — after the one-category
  // partition, cards with neither band were invisible to every filter; now a filterable state;
  // (c) Clear clears EVERYTHING including the type dropdown.
  const typed = type ? all.filter(c => c.category === type) : all;
  const chipN = k => typed.filter(c => cardBand(c) === k).length;
  const prevChipN = k => typed.filter(c => cardPrevBand(c) === k).length;
  const noneN = typed.filter(c => !cardBand(c) && !cardPrevBand(c)).length;
  let cards = typed;
  if (posSel.length) cards = cards.filter(c => posSel.includes(cardBand(c)));
  if (prevSel.length) cards = cards.filter(c => prevSel.includes(cardPrevBand(c)));
  if (noneSel) cards = cards.filter(c => !cardBand(c) && !cardPrevBand(c));
  // one bar, one vocabulary: chip labels for the practice group come from the engine's own
  // state words (prev.states) with static fallbacks for domains with no practice pool
  const _st = (hero && hero.prevalence && hero.prevalence.states) || {};
  const _prevChipDefs = [
    { k: "match", lab: _st.with_majority || "common", n: prevChipN("match") },
    { k: "common_alt", lab: _st.established || "alternative", n: prevChipN("common_alt") },
    { k: "rarer", lab: _st.less_common || "rare", n: prevChipN("rarer") },
  ];
  const _typeLab = { metric: "metrics", practice: "practices", policy: "policies", benefit: "benefits" };
  const _fdesc = [
    ...posSel.map(k => k === "on" ? "on market" : k + " market"),
    ...prevSel.map(k => (_prevChipDefs.find(d => d.k === k) || {}).lab),
    ...(noneSel ? ["no reading yet"] : []),
    ...(type ? [_typeLab[type] || type] : []),
  ].filter(Boolean).join(" · ");

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
  // insights collapse — per-user pref, applies to every domain page (one setting, not per-domain)
  const catUi = (prefs && prefs._cat) || {};
  const heroHidden = !!catUi.hero_hidden;
  const setHeroHidden = v => onPref && onPref("_cat", { ...catUi, hero_hidden: v });
  // ANALYSIS PACK (David 2026-07-13): a print product from the live page — the briefing +
  // every metric card, with charts or figures-only. Client-side print (the board-pack
  // "Download PDF" pattern); the pack mirrors the CURRENT view — cut, strategy state,
  // folded insights and active filters all print as seen, which is the honest contract.
  const printPack = (withCharts) => {
    setDl(false);
    const root = document.documentElement;
    root.classList.add("print-analysis");
    if (!withCharts) root.classList.add("print-nocharts");
    const t = document.title;
    document.title = `${domainLabel(name)} analysis — ${me.org.name}`;
    setTimeout(() => {
      window.print();
      document.title = t;
      root.classList.remove("print-analysis", "print-nocharts");
    }, 60);
  };
  const cutLab = cut.dim === "all" ? "All peers" : cut.dim === "twin" ? "Organisations like you"
    : cut.dim === "group" ? ((((cuts || {}).groups || []).find(g => g.group_id === cut.value)) || {}).name || "Your peer group"
    : cut.value;
  // counts-reconciliation (2026-06-28): the <20 thin-cut caveat must reach the DOMAIN page too —
  // otherwise the "small sample · directional" qualifier lives only on the overview hero, and a
  // user reading §1/§2/grid at n=15 sees no warning. Same window [5, 20) + insights-unlocked gate.
  const sampleN = cutSize(cut, cuts, me.peer_pool);
  // (thinSample retired 2026-07-09 — the always-on ConfidenceChip carries the rating; its own
  // thresholds live inside the component, same source as the home masthead.)
  // donut segment maps retired with the donuts (briefing build, 2026-07-13)

  return html`
    <div class="category-page">
      <div class="pack-print-head" aria-hidden="true">
        <div class="pack-print-brand">lumi</div>
        <div class="pack-print-title">
          <b>${domainLabel(name)} — reward analysis</b>
          <span>${me.org.name} · Peer group: ${cutLab}${sampleN != null ? ` (n=${sampleN})` : ""} ·
            ${new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" })}</span>
        </div>
      </div>
      <div class="pack-print-foot" aria-hidden="true">
        <span>${me.org.name} · ${domainLabel(name)} analysis</span>
        <span>Private ${"&"} confidential</span><span>lumi</span>
      </div>
      ${/* "peer group: …" dropped 2026-07-07 — duplicated the "Comparing against" peer
            bar above (same trim as the benchmark grid header; consistency). */ ""}
      ${Head(`${all.length} benchmark${all.length === 1 ? "" : "s"}`, html`
        <div class="bp-export">
          <button class="btn small" aria-expanded=${dl} aria-haspopup="menu" onClick=${() => setDl(v => !v)}
            title="Download this analysis as a document — the briefing plus every benchmark in this domain, on the current peer group.">
            <${Icon} name="file-text" size=${14} /> Download analysis <${Icon} name="chevron-down" size=${12} /></button>
          ${dl && html`<div class="card bp-menu" role="menu">
            <button class="bp-menu-item" role="menuitem" onClick=${() => printPack(true)}>
              <b>With metric charts</b>
              <span class="caption" style=${{ display: "block" }}>Every benchmark as shown — charts included</span></button>
            <button class="bp-menu-item" role="menuitem" onClick=${() => printPack(false)}>
              <b>Figures only</b>
              <span class="caption" style=${{ display: "block" }}>Positions, values and peer stats — no charts</span></button>
          </div>`}
        </div>`)}

      ${/* confidence chip moved INTO the one-row masthead (2026-07-13) — the standalone
            badge row below the title is gone. */ ""}

      ${/* Insights collapse (David 2026-07-13, "allow the user to hide the dashboard"): the whole
            pre-grid insight block — strategy bar, both read cards, AI summary — folds behind a
            per-user pref (_cat.hero_hidden). Collapsed, a one-line strip keeps the essential read
            (verdict chip + typical-metric P + practice word — all fields already computed) so the
            page never goes headless; the confidence chip above stays (it rates the grid too). */ ""}
      ${heroHidden ? html`
        <div class="cat-insights-strip">
          <span class=${"chip " + chipCls}>${chip}</span>
          ${pos && pos.depth_pctl != null ? html`<span class="caption num">typical metric at P${Math.round(pos.depth_pctl)}${indicative ? " (indicative)" : ""}</span>` : null}
          ${prev.pool ? (w => w ? html`<span class="caption">practice: ${w.word.toLowerCase()} — ${prev.with_majority} of ${prev.pool} common</span>` : null)(
            window.prevalenceWord && prevalenceWord(prev.with_majority || 0, prev.established || 0, prev.less_common || 0, prev.pool)) : null}
          <button type="button" class="btn small cat-insights-toggle" aria-expanded="false"
            onClick=${() => setHeroHidden(false)}><${Icon} name="chevron-down" size=${13} /> Show insights</button>
        </div>` : html`
      ${/* THE BRIEFING (David's "build a", 2026-07-13): the donut cards retired for a
            three-part band — compact read (home grammar: chip + ruler pill + counts),
            drivers (top gaps + strength, the engine's own top_gaps definition), and the
            narrative (deterministic floor for everyone; AI prose only behind the
            compliance-reserved gate). ~200px where the donuts spent ~500 saying less. */ ""}
      <div class="card cat-brief">
        <div class="cat-brief-head">
          ${/* label + lens counts dropped (David 2026-07-13) — the band speaks for itself;
                the row carries only the two controls. */ ""}
          ${ov.strategy_complete ? html`
            <button type="button" class=${"ov-strat" + (applyStrat ? " on" : "")} role="switch" aria-checked=${applyStrat}
              onClick=${() => onPref && onPref("_overview", { ..._ovp, apply_strategy: !applyStrat })}
              title=${applyStrat
                ? "Reading against your reward strategy — the alignment chip shows how this domain tracks your aim. Click for the absolute market view."
                : "Showing the absolute market view (no stance applied). Click to read against your reward strategy."}>
              <span class="ov-strat-track"><span class="ov-strat-knob"></span></span>
              <span class="ov-strat-lbl">${applyStrat ? "Strategy applied" : "Strategy off"}</span>
            </button>` : null}
          <button type="button" class="btn small cat-insights-toggle" aria-expanded="true"
            onClick=${() => setHeroHidden(true)}><${Icon} name="chevron-up" size=${13} /> Hide insights</button>
        </div>
        <div class="cat-brief-read">
          <span class="cat-brief-lab">Market</span>
          ${posM && posM.pool ? html`
            <span class=${"chip " + chipCls + (indicative ? " chip-indicative" : "")}>${chip}</span>
            <div class="cat-brief-ruler">${pos && pos.depth_pctl != null ? html`
              <${PercentileRuler} pctl=${pos.depth_pctl} band=${window.MARKET_BAND || [35, 65]} compact=${true} />` : null}</div>
            <span class="cat-brief-counts num"><b>${posM.below}</b> below · <b>${posM.at}</b> on market · <b>${posM.above}</b> above${indicative ? html` <span class="caption">· indicative</span>` : ""}${hero.target ? html` <${AlignmentChip} target=${hero.target} />` : ""}</span>` :
            html`<span class="caption cat-brief-span">Not enough positioned metrics for a market stance yet — this category is assessed on practice.</span>`}
          <span class="cat-brief-lab">Practice</span>
          ${prev.pool ? (w => html`
            <span class="chip chip-practice">${w ? w.word.toLowerCase() : "—"}</span>
            <div class="cat-brief-minibar" role="img"
              aria-label=${`${prev.with_majority} ${prev.states.with_majority}, ${prev.established} ${prev.states.established}, ${prev.less_common} ${prev.states.less_common} of ${prev.pool}`}>
              <span style=${{ width: (100 * prev.with_majority / prev.pool) + "%", background: "var(--prev-common)" }}></span>
              <span style=${{ width: (100 * prev.established / prev.pool) + "%", background: "var(--prev-alt)" }}></span>
              <span style=${{ width: (100 * prev.less_common / prev.pool) + "%", background: "var(--prev-rare)" }}></span>
            </div>
            <span class="cat-brief-counts num"><b>${prev.with_majority}</b> ${prev.states.with_majority} · <b>${prev.established}</b> ${prev.states.established} · <b>${prev.less_common}</b> ${prev.states.less_common}</span>`)(
            window.prevalenceWord && prevalenceWord(prev.with_majority || 0, prev.established || 0, prev.less_common || 0, prev.pool)) :
            html`<span class="caption cat-brief-span">No practice questions assessed in this category yet.</span>`}
        </div>
        <div class="cat-brief-body">
          <div class="cat-brief-drivers">
            <div class="cat-brief-collab">What's driving it</div>
            ${(hero.drivers || []).length ? (hero.drivers || []).map(d => html`
              <button key=${d.question_id + d.kind} type="button" class="cat-driver" onClick=${() => openMetric(d.question_id)}
                title=${"Open " + d.label}>
                <${Icon} name=${d.kind === "gap" ? "arrow-down" : "arrow-up"} size=${13} />
                <span class="cat-driver-lab">${d.label}</span>
                <span class=${"num cat-driver-p " + d.kind}>P${Math.round(d.percentile)}${d.polarity === "lower_is_better" ? html` <i>· lower is better</i>` : ""}</span>
              </button>`) : html`<div class="caption">No positioned metrics to rank yet.</div>`}
            ${sigCounts.signal ? html`<a class="cat-flag-link" href="#/signals" title="Open the Signals view"><${Icon} name="flag" size=${12} /> ${sigCounts.signal} flagged in Signals →</a>` : null}
          </div>
          <div class="cat-brief-narr">
            <${DomainSummary} name=${name} cut=${cut} applyStrat=${applyStrat} embedded=${true}
              aiNudge=${!(me.features && me.features.domain_summary) && me.ai_insights && me.ai_insights.master && me.ai_insights.needs_decision} />
          </div>
        </div>
      </div>`}

      <section class="cat-section">
        ${/* FILTERS SEPARATED from the insight cards (David 2026-07-13): one bar, one home for
              the whole working set — position group + practice group + no-reading + type + Clear.
              The cards above are pure reads now. The section head NAMES the active filter next to
              the count, so the grid never changes silently. Mutual exclusion between the two chip
              groups is unchanged — but now both groups sit side by side, so the swap is visible. */ ""}
        <div class="cat-sec-head"><span class="cat-sec-ico"><${Icon} name="table" size=${14} /></span>
          <b>All metrics</b><span class="pulse-count-chip">${cards.length}</span>
          <span class="caption">shown${_fdesc ? html` · filtered to <b>${_fdesc}</b>` : ""}</span>
          ${sigCounts.signal ? html`<a class="cat-flag-link" href="#/signals" title="${sigCounts.signal} metric${sigCounts.signal === 1 ? "" : "s"} here ${sigCounts.signal === 1 ? "is" : "are"} flagged — open the Signals view"><${Icon} name="flag" size=${12} /> ${sigCounts.signal} flagged →</a>` : null}
        </div>
        <div class="cat-filterbar" role="group" aria-label="Filter the metrics">
          <span class="cat-filter-cue"><${Icon} name="sliders" size=${11} /> Filter</span>
          ${[{ k: "below", lab: "below" }, { k: "on", lab: "on market" }, { k: "above", lab: "above" }].map(p => ({ ...p, n: chipN(p.k) })).filter(p => p.n).length ? html`
            <span class="cat-fgroup" role="group" aria-label="By market position">
              <span class="cat-fgroup-lab">Position</span>
              ${[{ k: "below", lab: "below" }, { k: "on", lab: "on market" }, { k: "above", lab: "above" }].map(p => ({ ...p, n: chipN(p.k) })).filter(p => p.n).map(p => html`
                <button key=${p.k} type="button" class=${"sig-chip" + (posSel.includes(p.k) ? " on" : "")} aria-pressed=${posSel.includes(p.k)}
                  title="Filters the grid by market position — replaces any practice filter"
                  onClick=${() => { setPrevSel([]); setNoneSel(false); setPosSel(sel => sel.includes(p.k) ? sel.filter(x => x !== p.k) : [...sel, p.k]); }}>
                  ${p.lab} <span class="n">${p.n}</span></button>`)}
            </span>` : null}
          ${_prevChipDefs.filter(p => p.n).length ? html`
            <span class="cat-fgroup" role="group" aria-label="By practice prevalence">
              <span class="cat-fgroup-lab">Practice</span>
              ${_prevChipDefs.filter(p => p.n).map(p => html`
                <button key=${p.k} type="button" class=${"sig-chip" + (prevSel.includes(p.k) ? " on" : "")} aria-pressed=${prevSel.includes(p.k)}
                  title="Filters the grid by practice prevalence — replaces any position filter"
                  onClick=${() => { setPosSel([]); setNoneSel(false); setPrevSel(sel => sel.includes(p.k) ? sel.filter(x => x !== p.k) : [...sel, p.k]); }}>
                  ${p.lab} <span class="n">${p.n}</span></button>`)}
            </span>` : null}
          ${noneN ? html`
            <button type="button" class=${"sig-chip" + (noneSel ? " on" : "")} aria-pressed=${noneSel}
              title="Metrics with no market or practice reading yet — unanswered, thin data, or awaiting a rating method"
              onClick=${() => { setPosSel([]); setPrevSel([]); setNoneSel(v => !v); }}>
              no reading yet <span class="n">${noneN}</span></button>` : null}
          <span class="cat-fbar-right">
            ${(posSel.length || prevSel.length || noneSel || type) ? html`<button type="button" class="cat-clear" onClick=${() => { setPosSel([]); setPrevSel([]); setNoneSel(false); setType(""); }}>Clear filters</button>` : null}
            <select class="ctl" aria-label="Filter by question type" value=${type} onChange=${e => setType(e.target.value)}>
              <option value="">All types</option><option value="metric">Metrics</option>
              <option value="practice">Practices</option><option value="policy">Policies</option><option value="benefit">Benefits</option>
            </select>
          </span>
        </div>
        ${cards.length === 0 ? html`<${EmptyState} title="No metrics match these filters"
          action=${html`<button class="btn small" onClick=${() => { setType(""); setPosSel([]); setPrevSel([]); setNoneSel(false); }}>Clear filters</button>`} /> ` :
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
  const [err, setErr] = useState(null);          // §4.10(2): a failed load must not hang on the skeleton
  const [dlOpen, setDlOpen] = useState(false);   // Download menu (PDF / CSV)
  const nameRef = useRef(null);
  const dlRef = useRef(null);
  const cancelRename = useRef(false);   // Escape sets this so the input's onBlur doesn't commit

  const applyActive = (id, lay) => {
    setActiveId(id); setLayout(lay); setCards({});
    if (setPinned) setPinned((lay || []).map(s => s.question_id));
  };
  // cache key folds in the EFFECTIVE peer cut, so changing the global filter
  // (or a slot's own cut) yields a fresh key → refetch, not a stale card.
  const cardKey = slot => slotKey(slot) + "|" + cutKeyOf(slot.cut || cut);
  const reload = () => { setErr(null); return api("/api/dashboards").then(d => {
    setList(d.dashboards); applyActive(d.active_id, d.active.layout);
  }).catch(e => setErr(e.message)); };
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
    // Ship review 2026-07-09 B4 (cut-switch race): live-flag guard so a slower older
    // cut's overview can't repaint the signal pills after the newer cut's map landed.
    let live = true;
    apiCached("/api/overview?" + cutQS(cut)).then(o => {
      if (!live) return;
      const m = {}; (o.signals_all || []).forEach(s => { (m[s.question_id] = m[s.question_id] || []).push(s); }); setSigMap(m);
    }).catch(() => { if (live) setSigMap({}); });
    return () => { live = false; };
  }, [cutKeyOf(cut)]);
  useEffect(() => {
    if (!layout) return;
    // one request per cut group instead of one per pinned card (20 pins was 20 GETs)
    const missing = layout.filter(slot => !cards[cardKey(slot)]);
    if (!missing.length) return;
    const groups = new Map();
    missing.forEach(slot => {
      const qs = cutQS(slot.cut || cut);
      if (!groups.has(qs)) groups.set(qs, []);
      groups.get(qs).push(slot);
    });
    groups.forEach((slots, qs) => {
      api(`/api/benchmark-batch?ids=${slots.map(s => s.question_id).join(",")}&` + qs)
        .then(d => setCards(prev => {
          const next = { ...prev };
          slots.forEach(s => { next[cardKey(s)] = (d.cards && d.cards[s.question_id]) || { error: true }; });
          return next;
        }))
        .catch(() => setCards(prev => {
          const next = { ...prev };
          slots.forEach(s => { next[cardKey(s)] = { error: true }; });
          return next;
        }));
    });
  }, [layout, cutKeyOf(cut)]);
  useEffect(() => { if (renaming && nameRef.current) { nameRef.current.focus(); nameRef.current.select(); } }, [renaming]);
  useEffect(() => {
    if (!dlOpen) return;
    const onDown = e => { if (dlRef.current && !dlRef.current.contains(e.target)) setDlOpen(false); };
    const onKey = e => { if (e.key === "Escape") setDlOpen(false); };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDown); document.removeEventListener("keydown", onKey); };
  }, [dlOpen]);

  if (err) return html`<${EmptyState} title="Couldn't load your dashboards"
    body=${err + " — nothing is lost; it usually works on a retry."}
    action=${html`<button class="btn small primary" onClick=${() => { setList(null); reload(); }}>Retry</button>`} />`;
  if (!list || !layout) return html`
    <div>
      <div class="skel" style=${{ height: "30px", width: "240px", marginBottom: "var(--s3)" }}></div>
      <div class="skel" style=${{ height: "36px", width: "420px", marginBottom: "var(--s4)", borderRadius: "999px" }}></div>
      <${SkeletonGrid} count=${4} />
    </div>`;
  const active = list.find(d => d.id === activeId) || {};
  const activeName = active.name || "My dashboard";
  // print-header context (Download PDF reuses the browser print pipeline, like the
  // board pack / pulse / metric one-pager). Peer label mirrors the "Comparing against" bar.
  const peerLabel = (!cut || !cut.dim || cut.dim === "all")
    ? "All peers · " + ((me.peer_pool || {}).responding_orgs || "—")
    : (cut.value || cut.dim);
  const printDate = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

  const persist = async (next) => {
    setLayout(next);
    if (setPinned) setPinned(next.map(s => s.question_id));
    setList(l => l.map(d => d.id === activeId ? { ...d, count: next.length } : d));
    await api(`/api/dashboards/${activeId}`, { method: "PUT", body: { layout: next } })
      .catch(() => toast("Couldn't save that change — it may reset next visit.", "error"));
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
    await api(`/api/dashboards/${activeId}`, { method: "PUT", body: { name: nm } })
      .catch(() => toast("Couldn't save the name — it may reset next visit.", "error"));
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
  // Download PDF: name the document, hand off to the browser's print pipeline
  // (a dashboard-scoped @media print block hides the app chrome + tabs/toolbar and
  // reveals a print header/footer), then restore the title. print() blocks, so the
  // restore is synchronous — same pattern as the board pack share view.
  const downloadPDF = () => {
    if (!layout.length) return;
    const t = document.title;
    document.title = activeName + " — " + ((me.org && me.org.name) || "lumi") + " — lumi benchmark";
    window.print();
    document.title = t;
  };
  const onlyOne = list.length <= 1;

  return html`
    <div>
      <div class="dash-print-head" aria-hidden="true">
        <div class="dash-print-brand">lumi<span>benchmark</span></div>
        <div class="dash-print-title">${activeName}</div>
        <div class="dash-print-meta">${peerLabel} · ${layout.length} card${layout.length === 1 ? "" : "s"}${me.org && me.org.name ? " · " + me.org.name : ""} · ${printDate}</div>
      </div>
      <div class="row spread no-print" style=${{ marginBottom: "var(--s3)" }}>
        <div>
          <h1 class="display-title">My dashboards</h1>
          <div class="caption" style=${{ marginTop: "var(--s1)" }}>
            Pin any card to build a view — drag to arrange, and switch between your saved dashboards here.
          </div>
        </div>
        <div class="row">
          ${saved && html`<${Chip} kind="good">${saved}<//>`}
          <div class="dash-dl" ref=${dlRef}>
            <button class="btn small" onClick=${() => setDlOpen(o => !o)} disabled=${layout.length === 0}
              aria-haspopup="menu" aria-expanded=${dlOpen}
              title=${layout.length === 0 ? "Add a card first" : "Download this dashboard"}>
              <${Icon} name="download" size=${14} /> Download <span class="dash-dl-chev" aria-hidden="true">▾</span></button>
            ${dlOpen && html`
              <div class="dash-dl-menu" role="group">
                <button class="dash-dl-item" onClick=${() => { setDlOpen(false); downloadPDF(); }}>
                  <b>PDF</b><small>Print-ready document — every card</small></button>
                <a class="dash-dl-item" href=${"/api/dashboards/" + activeId + "/export.csv?" + cutQS(cut)}
                  download onClick=${() => setDlOpen(false)}>
                  <b>Spreadsheet (CSV)</b><small>The numbers behind each card</small></a>
              </div>`}
          </div>
          <${ShareButton} me=${me} cut=${null} name=${activeName} layout=${layout} />
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
          <span aria-hidden="true">+</span> New</button>
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
        body="Use the pin icon on any benchmark card — across Overview, Benchmark or Signals — and it lands here."
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
      <div class="dash-print-foot" aria-hidden="true">
        Private & confidential · Generated by lumi · UK reward benchmarking · figures resting on fewer than 5 organisations are never shown
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
  const [ydRetry, setYdRetry] = useState(0);
  useEffect(() => { setData(null); api("/api/data-overview").then(setData).catch(() => setData({ error: true })); }, [ydRetry]);
  if (!data) return html`
    <div>
      <div class="skel" style=${{ height: "30px", width: "200px", marginBottom: "var(--s4)" }}></div>
      <div class="skel" style=${{ height: "120px", marginBottom: "var(--s4)", borderRadius: "var(--radius)" }}></div>
      <${SkeletonGrid} count=${4} />
    </div>`;
  if (data.error) return html`<${EmptyState} title="Couldn't load your data"
    action=${html`<button class="btn small primary" onClick=${() => setYdRetry(k => k + 1)}>Retry</button>`} />`;
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
            <div class="data-domain-head"><span class="cat-icon"><${Icon} name=${CAT_ICON[d.name] || "award"} size=${14} /></span> ${domainLabel(d.name)}</div>
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
  if (!data) return html`<${PageLoading} />`;
  const d = (data.domains || []).find(x => x.name === section);
  if (!d) return html`<${EmptyState} icon="table" title="Area not found"
    action=${html`<button class="btn small" onClick=${() => nav("/your-data")}>Back to Your data</button>`} />`;
  const canEdit = me && (me.user.role === "admin" || me.user.role === "contributor");
  const tabs = [{ k: "all", label: "All", n: d.total }, { k: "answered", label: "Answered", n: d.answered },
    { k: "unanswered", label: "To do", n: d.total - d.answered }];
  const qs = d.questions.filter(x => filter === "all" || (filter === "answered") === x.answered);
  return html`
    <div class="yourdata">
      <a class="caption back-link" href="#/your-data"><${Icon} name="chevron-left" size=${13} /> Your data</a>
      <div class="row spread" style=${{ alignItems: "center", margin: "var(--s1) 0 var(--s4)" }}>
        <div class="row" style=${{ gap: "var(--s3)", alignItems: "center" }}>
          <span class="cat-glyph"><${Icon} name=${CAT_ICON[section] || "award"} size=${20} /></span>
          <div><h1 class="display-title">${domainLabel(section)}</h1>
            <div class="caption meta">${d.answered} of ${d.total} answered</div></div>
        </div>
        <div class="row" style=${{ gap: "var(--s3)", alignItems: "center" }}>
          <${CompletionRing} pct=${d.pct} size=${56} stroke=${7} />
          ${canEdit && html`<button class="btn primary" onClick=${() => nav("/your-data/submit/" + encodeURIComponent(section))}><${Icon} name="pencil" size=${14} /> ${d.answered < d.total ? "Complete" : "Edit"} ${domainLabel(section)}</button>`}
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
  const [err, setErr] = useState(null);   // §4.10(2): don't hang on the loader if methodology fails
  const load = () => { setErr(null); api("/api/methodology").then(setM).catch(e => setErr(e.message)); };
  useEffect(() => { load(); api("/api/legal").then(d => setLegal(d.documents)).catch(() => {}); }, []);
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
  if (err) return html`<${EmptyState} title="Couldn't load how lumi works"
    body=${err + " — nothing is lost; it usually works on a retry."}
    action=${html`<button class="btn small primary" onClick=${load}>Retry</button>`} />`;
  if (!m) return html`<${PageLoading} />`;
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
        <p class="caption" style=${{ marginTop: "-4px" }}>Benchmark snapshot dated ${m.snapshot_date} · collection window ${m.collection_window} · methodology v${m.methodology_version || 1}</p>

        <div class="card how-card" id="market-position">
          <h3 class="section-title">Where you stand — your market position</h3>
          <p>For everything we measure, we compare your figure to the same measure across your peer group and place you in one of three positions: <b>below market</b> (under where most peers sit), <b>on market</b> (in line — we allow a sensible margin so tiny differences aren't treated as gaps), or <b>above market</b>. We do this measure by measure, roll it up for each area of reward, and bring it together into a single headline.</p>
          <p><b>Two kinds of thing we measure.</b> Some measures have a going rate — pay, pension, holiday, bonus levels — so "below, on or above market" genuinely means something. Others are choices with no right answer — which share scheme you run, how you structure a benefit, how often you review pay. There's no rate to be under or over; you're simply doing it differently. We show where your choice sits — <b>common</b> (what most peers do), an <b>alternative</b> pattern, or a <b>rare</b> choice — a difference to be aware of, not a gap to close. That's why your headline won't match the total number of things we measure: only the market-rate measures feed it.</p>
          <p><b>Practices with more than one part.</b> Some choices are a set rather than a single
          answer — which benefits you offer, which allowances you pay. For these we look at the
          <b> market core</b>: the options at least half of your peer group offers. Offer the full core and
          your set reads <b>common</b>; offer part of it, an <b>alternative</b> pattern; none of it, a
          <b> rare</b> choice. Options you offer beyond the core never count against you. Where no single
          option reaches half the market, we compare against the single most-offered option instead.
          <span class="caption">(Methodology v2, introduced July 2026 — board packs generated before it
          are labelled v1 and read as they were built.)</span></p>
          <p><b>When "below market" isn't a bad thing.</b> A few measures are better when they're lower — your CEO-to-employee pay ratio, your gender pay gap. Below market there is good news, so we show it as <b>favourable</b> rather than a gap. Some measures have no good direction at all — workforce cost as a share of revenue could mean you're lean, or under-investing. We show these as <b>context</b>: a fact to weigh, not a verdict. The label always tells the truth about the number; the colour tells you how to read it.</p>
          <div class="mp-legend">
            <span><i class="sw" style=${{ background: "var(--amber-bright)" }}></i> below market</span>
            <span><i class="sw" style=${{ background: "var(--favourable)" }}></i> on market / favourable</span>
            <span><i class="sw" style=${{ background: "var(--unfavourable)" }}></i> above market</span>
            <span><i class="sw" style=${{ background: "var(--differs)" }}></i> a practice choice: common / alternative / rare</span>
            <span><i class="sw" style=${{ background: "var(--navy)" }}></i> context</span>
          </div>
          <p><b>The headline answers one question.</b> "Where you stand" is a read on how competitive your reward is — are you paying and providing at the market rate? So it's built only from the market-rate measures where higher is better. Governance (your pay ratio, your pay gap) isn't about competitiveness — you don't compete on a low pay ratio — so it sits beside the headline, not inside it. The same goes for any market-rate measure with no competitive direction, like your workforce cost as a share of revenue. That keeps the headline answering one clear thing rather than blending several.</p>
          <p class="caption">Where a comparison rests on only a few organisations, we mark the verdict <b>indicative</b> — a steer, not a precise figure.</p>
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
          <p>Above the floor, every peer cut carries a confidence label so you can weigh the sample: <b>20 or more</b>
          organisations reads as <b>High confidence</b>; <b>5–19</b> reads as <b>Directional</b> — a steer, not a verdict.</p>
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
            <p key=${k} style=${{ margin: "var(--s2) 0" }}><b>${k.charAt(0).toUpperCase() + k.slice(1)}.</b> ${v}</p>`)}
          <p style=${{ margin: "var(--s2) 0" }}><b>Peer Twin.</b> A bespoke peer group of the organisations most similar to yours
          across industry, size, ownership and workforce shape, recalculated as the membership grows; member names are never shown.</p>
        </div>

        ${/* ---------- §4.2 How the co-op works ---------- */ ""}
        <h2 class="how-section-head" id="co-op">How the co-op works</h2>
        <div class="card how-card">
          <h3 class="section-title">A give-to-get co-operative</h3>
          ${/* Ship review 2026-07-09 B7 (RESOLVED 2026-07-11, David: "delete the free promise"):
                this card once claimed contributors benchmark FREE + a founding-year-free promise, while
                /pricing ships £5,000 contributing vs £10,000 non-contributing. The unverifiable "free"
                claims are gone for good — no founding-year-free clause — and pricing defers to the one
                authoritative surface (the pricing page) rather than hardcoding rates in two places. */ ""}
          <p>lumi is a benchmarking co-operative: the data you see comes from members like you, so the value depends on
          everyone contributing. <b>Contributing members pay less</b> — you give your reward data and, in return, you
          get the full peer picture at a lower membership rate than organisations that want the benchmark without
          contributing. Current rates are on <a href="/pricing" target="_blank" rel="noopener">the pricing page</a>.</p>
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
  // house Modal so keyboard users get focus trap/restore + Escape on the one
  // overlay members must be able to read before agreeing to anything
  return html`
    <${Modal} onClose=${onClose} width="660px" label=${(d && d.title) || "Legal document"}>
      <div class="row spread" style=${{ marginBottom: "var(--s3)" }}>
        <h2 class="section-title" style=${{ margin: 0 }}>${d && d.title || "Legal"}</h2>
        <button class="btn quiet small" onClick=${onClose}>Close</button>
      </div>
      ${!d ? html`<${Spinner} />`
        : d.error ? html`<div class="error-text" role="alert">Couldn't load this document.</div>`
        : html`${d.draft && html`<div class="how-note" style=${{ marginBottom: "var(--s3)" }}>This document is <b>DRAFT — pending legal review</b>.</div>`}
            <${TermsText} text=${d.text} />`}
    <//>`;
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
  // Ship review 2026-07-09 B4: live-flag guard — a slower older qid's trend response
  // must never land after a newer metric's fetch and draw under the wrong metric.
  useEffect(() => {
    let live = true;
    setT(null);
    api("/api/trend/" + qid).then(d => { if (live) setT(d); }).catch(() => { if (live) setT(false); });
    return () => { live = false; };
  }, [qid]);
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
  if (!g) return html`<${PageLoading} />`;
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
