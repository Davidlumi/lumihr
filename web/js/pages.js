/* Dashboard pages: Executive overview, Superpower detail, My dashboards, My data, Methodology. */
/* global html, useState, useEffect, useMemo, api, fmtValue, pLabel, Chip, NBadge, Term, Spinner,
   BenchmarkCard, QuartileDots, fmtGBPCompact, EmptyState, nav */

const SUPERPOWERS = ["Reward"];  // nonrew-1: Reward-only product; the nine non-Reward areas are out of scope
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
        <span>Set where you aim to sit, so lumi can tell “below market” from “below market, on purpose”.</span>
      </div>
      <button class="btn primary strat-nudge-cta" onClick=${() => nav("/strategy")}>Set it up</button>
      <button class="strat-nudge-x" aria-label="Dismiss for now"
        onClick=${() => { try { sessionStorage.setItem(KEY, "1"); } catch (e) {} setHidden(true); }}><${Icon} name="close" size=${15} /></button>
    </div>`;
}
// Company-default-peer-group setup prompt (David 2026-08-11: "on company set up the user admin must
// create a default peer group"). A guided prompt (not a hard gate) shown to editors once the org is
// classified but no default is set — NON-dismissible, so it persists until they choose one. The
// default drives signals, alerts and everyone's landing view; set in Settings.
function PeerDefaultNudge() {
  return html`
    <div class="strat-nudge">
      <span class="strat-nudge-icon"><${Icon} name="users" size=${20} /></span>
      <div class="strat-nudge-body">
        <b>Choose your company's default peer group</b>
        <span>The group your signals, email alerts and everyone's view are measured against — one consistent frame for your whole organisation. You can still explore other groups any time.</span>
      </div>
      <button class="btn primary strat-nudge-cta" onClick=${() => nav("/settings")}>Choose group</button>
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
  const tip = "Confidence " + score + "/10 — " + n + " organisations in this comparison. "
    + "20 or more peers rates 7–10 (high confidence); 5–19 rates 4–6 (directional — treat as a "
    + "steer, not a verdict); fewer than 5 is never shown."
    + (win ? " " + win + " baseline — movement shows from your next cycle." : "");
  return html`
    <span class=${"conf-chip conf-" + band} tabindex="0" role="note" aria-label=${tip}
      onKeyDown=${e => { if (e.key === "Escape") e.currentTarget.blur(); }}>
      <span class="conf-meter" aria-hidden="true"><i></i><i class=${score >= 4 ? "" : "off"}></i><i class=${score >= 7 ? "" : "off"}></i></span>
      <span class="conf-label">Confidence</span>
      <span class="conf-score num">${score}/10</span>
      <span class="num" style=${{ fontSize: "var(--fs-micro)", color: "var(--ink-faint)", marginLeft: "var(--s1)" }}>${n} peers</span>
      <span class="indic-tip">${tip}</span>
    </span>`;
}
window.OverviewPage = function ({ me, refreshMe, cut, cuts, prefs, onPref, onPin, pinnedIds, onCut, onTwinInfo }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  // newcomer captured ONCE at first mount — ReturnStrip stamps _seen.visit on mount,
  // which would otherwise flip this false mid-celebration (deep-QA 2026-08-09)
  const newcomerRef = useRef(!(prefs && prefs._seen));
  // Home dashboard lens (persisted in prefs._overview): MARKET view (gauge + below/
  // on/above) vs PRACTICE view (how you operate — the differ/approach read), and
  // whether the reward-strategy stance is APPLIED. Strategy-off re-fetches the
  // overview WITHOUT the lens (absolute colours, impact-ordered signals, plain verdict).
  const _ov = (prefs && prefs._overview) || {};
  // Practice lens retired from the home (2026-08-11, David: "clean dashboard") — the
  // practice-choices card was its only entry, so the home is MARKET-only now. Forcing
  // market here also stops a stale persisted view:"practice" from stranding a returning
  // user in the orphaned lens (or rendering practice bars inside the market layout).
  const [view, setViewState] = useState("market");
  const [applyStrat, setApplyState] = useState(_ov.apply_strategy !== false);
  // domain-bar mode (David 2026-07-11: "we still need the stacked bars ... implement a toggle"):
  // "counts" = the ratified count-proportional stacked bar; "position" = the fixed-band
  // percentile bar with the true-P marker. Per-user, persisted with the other lens prefs.
  const [barMode, setBarModeState] = useState(_ov.bar === "position" ? "position" : "counts");
  // setView retired 2026-08-11 (its only caller was the removed Market|Practice segment; the
  // home is market-only now). setViewState stays for the market-forcing initializer above.
  const setApplyStrat = (b) => { setApplyState(b); onPref("_overview", { view, apply_strategy: b, bar: barMode }); };
  const setBarMode = (m) => { setBarModeState(m); onPref("_overview", { view, apply_strategy: applyStrat, bar: m }); };
  // Ship review 2026-07-09 Pack 1 §3: prefs arrive async (GET /api/prefs lands after
  // mount), so the one-shot useState initializers above read {} on a cold load / deep
  // link and silently discard a saved practice-view / strategy-off choice. Sync the
  // lens state from the pref once it lands — idempotent: a user toggle writes the pref
  // via onPref, so the echo re-set is a no-op re-assign of the same value.
  useEffect(() => {
    // view stays market-only (practice lens retired from the home 2026-08-11); only the
    // strategy + bar-mode prefs sync in once they land.
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
    body=${err + " — nothing is lost."}
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

      ${unlocked ? html`<${ReturnStrip} prefs=${prefs} onPref=${onPref} />` : null}
      ${unlocked && !(prefs && prefs._seen && prefs._seen.unlock) &&
        html`<${UnlockMoment} newcomer=${newcomerRef.current} onDismiss=${() => onPref && onPref("_seen", { ...((prefs && prefs._seen) || {}), unlock: true })} />`}

      <${OverviewHero} data=${data} cut=${cut} cuts=${cuts} orgKey=${me.org && me.org.name}
        view=${view} applyStrat=${applyStrat} setApplyStrat=${setApplyStrat}
        barMode=${barMode} setBarMode=${setBarMode}
        me=${me} onCut=${onCut} onTwinInfo=${onTwinInfo} prefs=${prefs} onPref=${onPref} refreshMe=${refreshMe}
        sampleN=${sampleN} unlocked=${unlocked} />

    </div>`;
};

// Return recognition (2026-08-09 delight review): one dismissible line when the
// member has been away >7 days and things moved — pure recognition, no counters
// animating. Stamps prefs._seen.visit on every Overview mount.
function ReturnStrip({ prefs, onPref }) {
  const [line, setLine] = useState(null);
  const prefsRef = useRef(prefs);
  prefsRef.current = prefs;   // always the latest, so the deferred stamp reads live _seen
  useEffect(() => {
    const last = (prefs && prefs._seen && prefs._seen.visit) ? new Date(prefs._seen.visit) : null;
    // stamp merges onto the LATEST _seen (via ref) so a concurrent write — e.g. the
    // unlock-dismissed flag set between mount and this async callback — is never clobbered
    const stamp = () => onPref && onPref("_seen", { ...((prefsRef.current && prefsRef.current._seen) || {}), visit: new Date().toISOString() });
    if (!last || isNaN(last)) { stamp(); return; }
    if ((Date.now() - last.getTime()) / 86400000 < 7) { stamp(); return; }
    api("/api/notifications").then(d => {
      // events carry event_kind (appeared|moved|cleared) + detected_at (server/notifications.py)
      const evs = (d.events || []).filter(e => e.detected_at && new Date(e.detected_at) > last && !e.confirm);
      const cleared = evs.filter(e => e.event_kind === "cleared").length;
      const appeared = evs.filter(e => e.event_kind === "appeared").length;
      if (appeared || cleared) {
        const bits = [];
        if (cleared) bits.push(cleared + " signal" + (cleared === 1 ? "" : "s") + " cleared");
        if (appeared) bits.push(appeared + " new flag" + (appeared === 1 ? "" : "s"));
        setLine("Since you were last here — " + bits.join(", ") + ".");
      }
      stamp();
    }).catch(stamp);
  }, []);
  if (!line) return null;
  return html`<div class="return-strip" role="status">
    <${Icon} name="flag" size=${13} /> ${line}
    <button class="iconbtn" aria-label="Dismiss" onClick=${() => setLine(null)}><${Icon} name="close" size=${12} /></button>
  </div>`;
}

// Org-wide unlock moment: insights unlock for the WHOLE organisation the moment
// one member submits (sticky, server-stamped) — so every OTHER member next signs
// in to a silently different product. This one-time, per-user (prefs._seen.unlock)
// banner introduces the three things that just came alive. Shown to whoever hasn't
// dismissed it, not only the person who clicked Submit.
window.UnlockMoment = function ({ onDismiss, newcomer }) {
  // a week-one joiner (no prefs._seen at all) gets ORIENTATION, not a celebration
  // written for someone who watched the journey (2026-08-09 persona review)
  return html`
    <div class="card unlock-moment" role="status">
      <button class="iconbtn unlock-x" aria-label="Dismiss" onClick=${onDismiss}><${Icon} name="close" size=${14} /></button>
      <div class="unlock-spark"><${Icon} name="sparkle" size=${22} /></div>
      <div style=${{ flex: 1, minWidth: "240px" }}>
        <b style=${{ fontFamily: "var(--font-head)", fontSize: "var(--fs-subhead)" }}>${newcomer ? "New to lumi?" : "Your insights are live"}</b>
        <p style=${{ margin: "0 0 var(--s3)" }}>${newcomer ? "This is your organisation's live reward benchmark — your position, the signals worth attention, and how every number is built:" : "Your organisation's reward data is in:"}</p>
        <div class="unlock-links">
          <button class="btn small" onClick=${() => { nav("/signals"); onDismiss && onDismiss(); }}><${Icon} name="flag" size=${13} /> Your signals</button>
          ${/* the £ opportunity lives INSIDE signals (money flags) since the 80/20 hero —
                this used to say "(below)" and point at a tile that no longer renders */ ""}
          
          <button class="btn small" onClick=${() => { nav("/overview"); onDismiss && onDismiss(); }}><${Icon} name="file-text" size=${13} /> Export a board pack — on your Overview</button>
          ${newcomer ? html`<a class="btn small quiet" href="#/how-lumi-works">How the numbers work</a>` : null}
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
  const menuRef = useRef(null);
  useMenuClose(menuRef, open, setOpen);
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
    <div class="bp-export" ref=${menuRef}>
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
   kind=dashboard, config {cut, cut_value}, 30-day expiry; on success the
   dialog shows the public link with a copy button. */
function ShareButton({ me, cut, name, layout }) {
  const [open, setOpen] = useState(false);
  if (!me || !me.user || me.user.role !== "admin") return null;
  if (me.contribution && !me.contribution.insights_unlocked) return null;   // nothing to share until the benchmark unlocks (mirror ExportBoardPack)
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
          cut: (cut && cut.dim) || "all", cut_value: (cut && cut.value) || null,
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
          A read-only public link — headline position, leads and gaps, and ${hasLayout ? "the cards on this dashboard" : "your team's pinned cards"}. Anyone with the link can view it for 30 days; no sign-in needed.</p>
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
// A taste of what unlocks — shared by the /signals SignalsLocked hero AND the
// home Overview insight-lock (empty-state review: the most-seen locked surface
// used a bare "£—k" placeholder; it now shows the same concrete teaser vocabulary).
const SIGNAL_TEASERS = [
  { lens: "save", icon: "coins", tag: "£ GAP", name: "Bonus opportunity", stand: "sits below the market median for your size" },
  { lens: "retain", icon: "magnet", tag: "LOWER THAN MARKET", name: "Company sick pay", stand: "below where most of your peers land" },
  { lens: "engage", icon: "users", tag: "COMMON — YOU DON'T", name: "Paid parental leave", stand: "offered by 8 in 10 similar organisations" },
  { lens: "attract", icon: "star", tag: "HIGHER THAN MARKET", name: "Holiday allowance", stand: "ahead of the market for your size" },
];

function OverviewHero({ data, cut, cuts, orgKey, view, applyStrat, setApplyStrat, barMode, setBarMode,
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
  const _viewTotal = _viewLive.length;                 // kept: qa_overview 9c binds the card's
                                                       // signals total to this live-set length
  // Per-domain counts for the instrument's scent dots. Each count deep-links to the
  // Signals INBOX filtered to that domain, so it must count what that click shows:
  // every live kind (position AND practice/differs), excluding dismissed, saved and
  // still-snoozed rows. Counting the view-filtered band pool instead left 7 of 8
  // domain counts disagreeing with the page they open (pre-prod audit 2026-08-12).
  const _domCounts = {};
  (data.signals_all || [])
    .filter(s => s.status !== "dismissed" && s.status !== "saved"
      && !(s.status === "snoozed" && (!s.snooze_until || new Date(s.snooze_until) > new Date())))
    .forEach(s => { if (s.domain) _domCounts[s.domain] = (_domCounts[s.domain] || 0) + 1; });
  // scent-click → the Signals page FILTERED to that domain (David 2026-08-11). The home band
  // was retired, so each Position-by-domain count deep-links to /signals showing only that
  // domain's signals. The domain rides a module global (Overview→Signals is a client-side hash
  // nav, so it survives); SignalsPage reads + clears it on mount. nav stays a BARE route so the
  // app's cut-reapply logic is untouched. (_domCounts above feeds the per-row count.)
  const goToSignals = (dom) => { window.__sigJumpDomain = (typeof dom === "string" && dom) ? dom : null; nav("/signals"); };
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
      ${/* company-default-peer-group setup prompt (David 2026-08-11): editors, org classified, no
            default set yet — persists until they choose one (signals/alerts/landing all use it). */ ""}
      ${!locked && me && me.user && (me.user.role === "admin" || me.user.role === "contributor")
        && me.org && me.org.classified && !me.org.signal_peer_cut && html`<${PeerDefaultNudge} />`}
      ${/* the full-width CONTEXT TOOLBAR (spatial restructure 2026-07-12): peer context —
            "Comparing against [capsule ★🔔] [confidence]" — anchors LEFT; the view lenses
            (Market/Practice + strategy switch) anchor RIGHT; the row's width does the
            separating. The peer picker shows even pre-unlock; the lenses need data. */ ""}
      <div class="ov-controls">
        <div class="ov-ctx">
          <${PeerSetBar} me=${me} cut=${cut} cuts=${cuts} onSelect=${onCut} onTwinInfo=${onTwinInfo} inline=${true}
            prefs=${prefs} onPref=${onPref} refreshMe=${refreshMe} />
          ${unlocked ? html`<${ConfidenceChip} n=${sampleN} window=${data.snapshot && data.snapshot.window} />` : null}
          ${/* period/baseline label ("2026 H1 · baseline") removed 2026-08-11 (David) — the
                collection window still rides the ConfidenceChip's detail; the standalone
                caption was noise in the controls row. */ ""}
        </div>
        ${!locked ? html`
        <div class="ov-lens">
          ${/* the Market|Practice seg RETIRED (Diff 4 ruling 2, 2026-07-14): practice is one
                bucket card on the market dashboard, and the lens view is reached through its
                click-through only. The Counts|Position toggle on Position-by-domain is a
                different control and stays. */ ""}
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
      ${/* Practice lens + practice-choices card retired from the home 2026-08-11 (David:
            "clean dashboard"). The home is MARKET-only now; PracticeBucketCard and the
            practice-mode DomainInstrument rows stay defined but are no longer mounted here. */ ""}
      <div class="ov-top">
        <${OverallArc} market=${m} approach=${data.hero.approach} pending=${locked} pct=${Math.round((data.contribution && data.contribution.core_pct) || 0)} orgKey=${orgKey} stratOff=${data.strategy_complete && !applyStrat} absentDisclosed=${(data.headline && data.headline.absent_disclosed) || 0} contribution=${data.contribution} canEdit=${me && me.user && (me.user.role === "admin" || me.user.role === "contributor")} heroCta=${data.contribution && !data.contribution.insights_unlocked && !data.contribution.reduced} />
        <${DomainInstrument} market=${m} prevalence=${data.hero.prevalence} domains=${data.hero.domains}
          view=${view} pending=${locked} sigCounts=${_domCounts} onScent=${goToSignals}
          barMode=${barMode} setBarMode=${setBarMode} />
      </div>
      ${/* Home signals band retired 2026-08-11 (David: "clean dashboard" — "the bottom signals
            detail"). Signals live on the dedicated Signals page; the per-domain scent counts on
            Position-by-domain deep-link there via goToSignals. SignalsPanel stays defined but is
            no longer mounted here (its total-binding strings still satisfy qa_overview 9c). */ ""}
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
        <p class="strat-intro">Where your position <b>delivers the strategy you set</b> — and where it pulls against it. Read from your figures and declared aims; each finding signposts its signals.</p>
        <button class="btn primary" onClick=${run}>Run the check</button>`}
      ${st.phase === "loading" && html`
        <div class="strat-loading"><${Spinner} /> Reading your strategy against your data…
          </div>`}
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
  if (t.alignment === "on_target") return "On aim — you aim to sit " + w;
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
const ALIGN_LABEL = { on_target: "On aim", behind: "Behind aim", ahead: "Ahead of aim" };
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
const STRAT_CLAUSE = { on_target: "On aim — where you mean to be.", behind: "Behind aim — short of where you mean to be.", ahead: "Ahead of aim — past where you mean to be." };
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
function OverallArc({ market, approach, pending, pct, orgKey, stratOff, absentDisclosed, contribution, canEdit, heroCta }) {
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
        <div class="arc-word arc-word-pending">${(() => {
          const t = Math.round((contribution && contribution.target_pct) || 90);
          return `Your position unlocks at ${t}%`;
        })()}</div>
        <div class="arc-lean">${(pct || 0) === 0
          ? "Answer your key reward questions and your market position appears here."
          : (() => {
              const need = window.unlockNeed(contribution);
              return need > 0
                ? `You're ${need} key question${need === 1 ? "" : "s"} away — then your position appears here.`
                : "Almost there — it appears once enough is comparable.";
            })()}</div>
      </div>
      <div class="arc-legend num"><span class="arc-pending-note">Data pending — ${pct || 0}% of key reward questions submitted</span></div>
      ${canEdit && !heroCta ? html`<button class="btn small primary arc-pending-cta" onClick=${() => nav("/your-data")}>${window.submitVerb((pct || 0) === 0)}</button>` : null}
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
            total=${market.pool} centerNum=${market.pool} sub="metrics" centerWord=${headWord} size=${192} stroke=${20} />   ${/* stroke 26→20 (2026-08-11): the 216px breathing-room scale thickened the ring to ~29px, which cramped the small above/on-market segments — a lighter ring gives them air */""}
        </div>
        <div class="arc-caption num">
          <span class="arc-lean">${headLean}</span>
          <span class="arc-caption-sep" aria-hidden="true">—</span>
          <span><i class="arc-leg-dot di-fill-below" aria-hidden="true"></i><span class="arc-leg-fig">${market.below}</span> below</span>
          <span><i class="arc-leg-dot di-fill-on" aria-hidden="true"></i><span class="arc-leg-fig">${market.at}</span> on market</span>
          <span><i class="arc-leg-dot di-fill-above" aria-hidden="true"></i><span class="arc-leg-fig">${market.above}</span> above</span>
        </div>
      </div>
      ${/* N/A-disclosure count line removed 2026-08-11 (home-page cleanup); absent metrics
            are still excluded from below/on/above by the engine — just not captioned here. */ ""}
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
          </div>`;
      })()}
      ${!market.target && !stratOff ? html`
        <button class="arc-target arc-target-unset" onClick=${() => nav("/strategy")}
          title="Set your market-position stance so lumi reads this against your aim, not a generic flag.">
          <${Icon} name="target" size=${13} /><span>Set your reward strategy</span>
        </button>` : null}
    </div>`;
}


// PRACTICE lens for the hero — the TWIN of OverallArc (the market donut), in the PURPLE theme
// (2026-07-09 harmonisation). Shows PREVALENCE (common / alternative / rare) on a purple ladder
// donut + centred legend, mirroring "Where you stand" exactly — same build, different hue. Practice
// is "how common", never good/bad, so it stays purple and never enters the RAG channel. (Was
// ApproachPanel — a 2-way "off the norm / in line" split that used a different framing AND colour
// from its own 3-way domain bars; that differ read lives on in signals + the category page.)
/* THE PRACTICE BUCKET CARD (Diff 4, ratified 2026-07-14): practice as ONE aggregate
   read on the market dashboard. Crop discipline: title + headline + split + basis sit
   in the card's top region; rare stances render below. Locked vocabulary — in line /
   off the norm; NO RAG colour anywhere on it (POSITION_RING brief unpre-empted);
   descriptive, never prescriptive. Click-through = the practice lens view.
   RETIRED from the home 2026-08-11 (David: "clean dashboard") — no longer mounted; kept
   defined for possible re-use / a future practice surface. */
function PracticeBucketCard({ bucket, onOpen }) {
  const b = bucket;
  const splitBasis = b.in_line + b.off_norm;
  return html`
    <div class="card prac-bucket" role="button" tabindex="0"
      onClick=${onOpen} onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onOpen(); } }}
      title="Open the practice lens — every practice choice, with how common each is among your peers.">
      <div class="prac-bucket-top">
        <div class="cat-brief-collab" style=${{ marginBottom: 0 }}>Practice choices</div>
        <div class="prac-bucket-head">
          <span class="prac-bucket-split num"><b>${b.in_line}</b> in line <span class="prac-dot">·</span>
            <b>${b.off_norm}</b> off the norm <span class="prac-dot">·</span>
            <b>${b.low_peer}</b> low peer data</span></div>
        <div class="caption prac-bucket-basis">${b.answered} of ${b.book} answered · peer pools under 5 excluded${b.ms_excluded ? ` · ${b.ms_excluded} pick-all-that-apply question${b.ms_excluded === 1 ? "" : "s"} counted separately` : ""}</div>
      </div>
      ${(b.rare_stances || []).length ? html`
        <div class="prac-bucket-rare">
          ${b.rare_stances.map(r => html`
            <div key=${r.label} class="prac-rare-row">
              <span class="prac-rare-lab">${r.label}</span>
              <span class="caption">Only ${r.orgs} of ${r.n} organisation${r.n === 1 ? "" : "s"} (${r.share_pct}%) — “${r.stance}”</span>
            </div>`)}
        </div>` : null}
      <div class="caption prac-bucket-foot" title="Rarity is the signal — whether it's deliberate is your call.">Open the practice lens →</div>
    </div>`;
}

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
            total=${pool} centerNum=${pool} sub="practices" centerWord=${word} size=${192} stroke=${20} />   ${/* stroke 26→20 (2026-08-11): the 216px breathing-room scale thickened the ring to ~29px, which cramped the small above/on-market segments — a lighter ring gives them air */""}
        </div>
        <div class="arc-caption num">
          <span class="arc-lean">${cap}</span>
          <span class="arc-caption-sep" aria-hidden="true">—</span>
          <span><i class="arc-leg-dot di-fill-common" aria-hidden="true"></i><span class="arc-leg-fig">${common}</span> common</span>
          <span><i class="arc-leg-dot di-fill-alt" aria-hidden="true"></i><span class="arc-leg-fig">${alt}</span> alternative</span>
          <span><i class="arc-leg-dot di-fill-rare" aria-hidden="true"></i><span class="arc-leg-fig">${rare}</span> rare</span>
        </div>
      </div>
      
    </div>`;
}


// B' taxonomy (Diff 1, 2026-07-14): 8 domains. Legacy 7-domain keys retained below so
// STORED payloads (board packs, cached summaries) keep their icons — degrade contract.
const CAT_ICON = {
  /* Icon review 2026-08-04: metaphors sharpened — Pensions reads as the NEST
     (home), not a ship's anchor; Benefits reads as PERKS (star), not abstract
     layers. Identity stays monochrome blue by brand law (one blue; plum/teal
     retired) — shape and name carry identity, never a hue ramp. */
  "Pay": "coins", "Pensions & Savings": "home", "Health & Protection": "shield",
  "Benefits & Lifestyle": "star", "Time Off & Family": "sun",
  "Incentives & Recognition": "trending-up", "Wellbeing": "heart",
  "Governance & Transparency": "list-checks",
  "Incentives": "trending-up", "Benefits": "shield", "Time Off": "sun",
  "Recognition": "award", "Governance": "list-checks" };

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
  // G&T special-case sentence DELETED (Diff 4; dead since the Diff-2 competitiveness
  // ruling — no live domain carries competitiveness=false).
  if (!pos || !pos.pool) return label + " — no comparable market position yet.";
  // counts-only + the verbal adverb — no P-number anywhere (RAG-only law, 2026-07-09)
  let s = label + ": " + pos.below + " below, " + pos.at + " on market, " + pos.above +
    " above of " + pos.pool + " comparable — " + leanCaption(pos) + ".";
  // strategy channel (2026-07-09): the row glyph is decorative, so the on-aim / behind / ahead
  // read must ride the accessible name — words only, never a lag/match/lead literal or a P-number.
  if (d.target && STRAT_CLAUSE[d.target.alignment]) s += " " + STRAT_CLAUSE[d.target.alignment];
  return s;
}
function DomainInstrument({ market, prevalence, domains, view, pending, sigCounts, onScent, barMode, setBarMode }) {
  const doms = domains || [];
  const practice = view === "practice";
  // (footer sums retired 2026-07-09 with both footers — the donut legends carry the org totals.)
  // standfirst removed (David 2026-07-09): the per-domain rows carry the read; the summary
  // sentence duplicated the donut + repeated what the bars already show. Kept ONLY for the
  // pending/locked state, where there are no rows yet to explain themselves.
  const stand = pending
    ? "Your per-domain position appears once enough of your data is comparable."
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
          // noRate DELETED (Diff 4): keyed on competitiveness===false — dead since Diff 2;
          // a below-floor domain still gets the honest "no position yet" state below.
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
                  : (!pos || !pos.pool) ? html`<span class="di-sub">no position yet</span>`
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
                  : html`<span class="di-norate">no practices tracked in this peer group yet</span>`)
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
                : html`<span class="di-norate">no position yet</span>`}
              </span>
              <span class="di-cell di-evid num">
                ${/* both stacked bars print their counts inside (2026-07-09); this column carries
                      ONLY the Governance practices count (no bar). The P-number moved onto the
                      position dot itself (David 2026-07-11: "only show counts no p and vice
                      versa" — each mode is pure; the "ind." tag went with it, the hollow dot +
                      aria carry the indicative basis). */ ""}
              </span>
              <span class="di-cell di-scentcol">
                ${!pending && nSig > 0 ? html`
                  <button class="di-scent"
                    title=${"See " + label + "'s " + nSig + " signal" + (nSig === 1 ? "" : "s") + " on the Signals page"}
                    aria-label=${"See " + label + "'s " + nSig + " signal" + (nSig === 1 ? "" : "s") + " on the Signals page"}
                    onClick=${e => { e.stopPropagation(); onScent && onScent(d.name); }}>${nSig}</button>` : null}
              </span>
              <span class=${"di-cell di-chipcol" + (!practice && stratSum ? " di-stratcol" : "")}>
                ${/* strategy channel (2026-07-09): position view shows the navy target glyph on
                      EVERY row (David: "see if you're aligned or not"); the header carries the
                      count. Practice view shows NOTHING here — strategy alignment is a market-
                      position concept, it has no meaning against the practice mix (harmonised). */ ""}
                ${pending || practice ? null
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

// RETIRED from the home 2026-08-11 (David: "clean dashboard" — "the bottom signals detail").
// No longer mounted; the dedicated SignalsPage is the live signals surface. Kept defined
// (its total-binding strings still satisfy qa_overview check 9c, and it may be re-used).
function SignalsPanel({ signals, total, newCount, locked, contribution, view, stratOn, objective, cutActive, domainFilter, onClearDomain, heroCta }) {
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
      let failed = false;
      const t = setTimeout(() => {
        if (failed) return;                              // a fast reject already reverted — don't re-hide
        setStOv(p => ({ ...p, [sid]: status }));
        setLeaving(p => { const n = { ...p }; delete n[sid]; return n; });
      }, 260);
      signalAction(sid, status, days).catch(() => {
        failed = true; clearTimeout(t);
        setStOv(p => { const n = { ...p }; delete n[sid]; return n; });
        setLeaving(p => { const n = { ...p }; delete n[sid]; return n; });
        toast("Couldn't save that — try again", "error");
      });
    } else {
      setStOv(p => ({ ...p, [sid]: status || "active" }));
      signalAction(sid, status, days).catch(() => {
        setStOv(p => { const n = { ...p }; delete n[sid]; return n; });
        toast("Couldn't save that — try again", "error");
      });
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
        : (total > shown.length ? "top " + shown.length + " of " + total + " · " : "")) + (view === "practice" ? "ranked by rarity" : (stratOn ? (objective ? "ordered for " + objective.toLowerCase() : "ranked by gap to your aim") : "ranked by market gap")) + " · we flag, you decide"}</div>` : null}
      ${locked ? html`
        <div class="insight-lock" style=${{ marginTop: "var(--s2)", flex: 1 }}>
          <div class="blurred" aria-hidden="true">
            ${SIGNAL_TEASERS.slice(0, 3).map((t, i) => html`
              <div key=${i} class=${"signal-row lens-" + t.lens + " sig-teaser"}>
                <span class="signal-roundel"><${Icon} name=${t.icon} size=${15} /></span>
                <span class="signal-body"><b class="sig-name">${t.name}</b><span class="sig-stand">${t.stand}</span></span>
                <span class="sig-tag">${t.tag}</span>
              </div>`)}
          </div>
          <div class="lock-note">
            ${(() => {
              const lp = Math.round((contribution && contribution.core_pct) || 0);
              const lt = (contribution && contribution.target_pct) || 90;
              return html`
                <${Chip} kind="accent"><${Icon} name="lock" size=${11} /> Locked<//>
                <div class="caption" style=${{ textAlign: "center", maxWidth: "280px" }}>
                  ${lp > 0
                    ? html`You're at <b>${lp}%</b> of your key questions — <b>${lt}%</b> unlocks your £ gaps, where you sit against the market, and the practices most peers offer that you don't.`
                    : html`Answer your key reward questions and lumi shows your <b>£ gaps</b>, where you sit against the market, and the practices <b>most peers offer that you don't</b>.`}
                  ${contribution && contribution.days_left != null ? html` <span class="num">${contribution.days_left} days left.</span>` : null}</div>
                <div class="progressbar il-lock-prog" aria-hidden="true"><div style=${{ width: Math.min(100, lt ? 100 * lp / lt : 0) + "%" }}></div></div>
                ${!heroCta ? html`<button class="btn small primary" onClick=${() => nav("/your-data")}>${lp > 0 ? "Continue your reward data" : "Add your reward data"}</button>` : null}`;
            })()}
          </div>
        </div>` :
      shown.length === 0 ? html`
        <div class="signals-empty">
          <span class="signals-empty-ring"><${Icon} name="flag" size=${18} /></span>
          <div class="caption" style=${{ maxWidth: "320px" }}>Nothing crosses a signal threshold right now — signals appear as your position or the market moves.</div>
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
    <span class="sig-stand">${s.stand || s.detail}${s.n ? html` · ${compositionLabel(s.n, s.n_real)}` : null}</span></button>`,
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
        <button class=${"sig-act" + (snoozeOpen ? " on" : "")} title="Snooze — pick a return date" aria-label="Snooze signal" aria-haspopup="true" aria-expanded=${snoozeOpen} onClick=${() => setSnoozeOpen(o => !o)}><${Icon} name="clock" size=${15} /></button>
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
  const teasers = SIGNAL_TEASERS;
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
            <b>Key questions ${pct}%</b>
            <span class="caption">unlocks at ${target}%${contrib.reduced ? " · paused to a sample — finish to restore" : (days != null ? ` · ${days} days left` : "")}</span>
          </div>
          <div class="progressbar"><div style=${{ width: Math.min(100, target ? 100 * pct / target : 0) + "%" }}></div></div>
          ${!contrib.reduced && days != null ? html`<p class="caption sig-unlock-clocknote">No rush — if the ${days} days pass, your benchmark just pauses to a sample until you finish. Nothing is deleted.</p>` : null}
        </div>
        ${canEdit
          ? html`<button class="btn primary sig-unlock-cta" onClick=${() => nav("/your-data")}>
              <${Icon} name="pencil" size=${14} /> ${pct > 0 ? "Continue your reward data" : "Add your reward data"}</button>
            <p class="caption sig-unlock-reassure">Autosaved as you go · private to your organisation · resume any time.</p>`
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
  else if (s.kind === "rare")
    // one kind, three shapes: a common option the org LACKS (worth=true), an absence
    // answer (org has nothing), or a genuinely distinctive choice
    r = s.worth ? "most of your peers provide this and you don't"
      : s.absence ? "almost all of your peers have something in place here"
      : "few of your peers make this choice";
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
const SIG_SNOOZE = [["Next week", 7], ["2 weeks", 14], ["6 weeks", 42], ["3 months", 90]];
const sigRetDate = days => new Date(Date.now() + days * 86400000)
  .toLocaleDateString("en-GB", { day: "numeric", month: "short" });
// shared dropdown chrome: close on outside click / Escape (focus back on the trigger)
// useMenuClose hoisted to core.js (window.useMenuClose) — single source for popover dismiss.
// "Snooze ▾" verb — labelled "Until…", each option shows its return date.
function SigSnoozeMenu({ onPick }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useMenuClose(ref, open, setOpen);
  return html`<span class="brf-later-wrap" ref=${ref}>
    <button type="button" class=${"brf-verb" + (open ? " on" : "")} aria-haspopup="true" aria-expanded=${open}
      onClick=${() => setOpen(o => !o)}>Snooze <span class="sfold-caret" aria-hidden="true">▾</span></button>
    ${open ? html`<div class="brf-menu" role="menu" ref=${el => { if (el && !el._f) { el._f = 1; const b = el.querySelector("button"); if (b) b.focus(); } }}>
      <div class="brf-menu-lbl">Until…</div>
      ${SIG_SNOOZE.map(([lab, days]) => html`<button key=${days} class="brf-menu-opt" role="menuitem"
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
    ${open ? html`<div class="brf-menu" role="menu" ref=${el => { if (el && !naming && !el._f) { el._f = 1; const b = el.querySelector("button"); if (b) b.focus(); } }}>
      ${opts.length ? html`<div class="brf-menu-lbl">To folder…</div>` : null}
      ${opts.map(f => html`<button key=${f} class="brf-menu-opt" role="menuitem" onClick=${() => pick(f)}>
        <${Icon} name="folder" size=${12} /> ${f}</button>`)}
      ${naming ? html`<div class="sfold-newrow">
        <input type="text" class="sfold-newinput" placeholder="Folder name" aria-label="New folder name" maxlength="40" value=${nm}
          ref=${el => { if (el && !el._f) { el._f = 1; el.focus(); } }} onInput=${e => setNm(e.target.value)}
          onKeyDown=${e => { if (e.key === "Enter") { e.preventDefault(); commit(); } }} />
        <button type="button" class="sfold-newgo" disabled=${!nm.trim()} onClick=${commit}>Add</button>
      </div>` : html`<button class="brf-menu-opt" role="menuitem" onClick=${() => setNaming(true)}>
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
        <input type="text" class="sfold-newinput" maxlength="40" aria-label=${"Rename folder " + name} value=${nm}
          ref=${el => { if (el && !el._f) { el._f = 1; el.focus(); } }} onInput=${e => setNm(e.target.value)}
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
// The org's DEFAULT peer group for signals (orgs.default_cut, exposed as me.org.signal_peer_cut) —
// a "dim::value" string or null. Signals + alert emails are anchored to it (David 2026-08-11), so
// the Signals page reads it instead of the app-wide selector. NULL / unset → all peers.
function signalCut(me) {
  const raw = me && me.org && me.org.signal_peer_cut;
  if (!raw) return { dim: "all", value: null };
  const i = String(raw).indexOf("::");
  return i < 0 ? { dim: String(raw), value: null } : { dim: raw.slice(0, i), value: raw.slice(i + 2) };
}
window.SignalsPage = function ({ me, prefs, onPref, cut, cuts }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const _ret = returnUiState("lumi-signals-ui") || {};   // Back-leg restore (Pack 1 §1)
  // active view: {kind:"all"} | {kind:"folder",name} | {kind:"snoozed"} | {kind:"dismissed"}
  const [view, setView] = useState(_ret.view && _ret.view.kind ? _ret.view : { kind: "all" });
  // market-position filter (David 2026-08-11): "all" | "below" | "on" | "above" — narrows the
  // current view to signals sitting that way vs the market (practice signals show only under "all").
  const [posFilter, setPosFilter] = useState(_ret.pos || "all");
  const [sortMode, setSortMode] = useState(_ret.sort || "priority");   // priority | domain | gap (David 2026-08-11)
  const [kbIdx, setKbIdx] = useState(-1);   // keyboard-triage focus ring index into the shown list (-1 = none)
  const [domFilter, setDomFilter] = useState(null);   // domain filter axis — composes with position (null = all domains)
  const [textQuery, setTextQuery] = useState("");     // client-side find-by-name over the current view
  const [flashSid, setFlashSid] = useState(null);     // a restored/woken/recovered card flashes back into place
  const [stratOpen, setStratOpen] = useState(false);  // the strategy-check strip (now above the feed) starts collapsed
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
  useEffect(() => { saveUiState("lumi-signals-ui", { view, pos: posFilter, sort: sortMode }); }, [view, posFilter, sortMode]);
  // Overview per-domain scent chip → land on THIS domain's signals only (2026-08-11). The
  // domain rides a module global set by OverviewHero.goToSignals (client-side hash nav, so it
  // survives); consume + clear it once on mount, showing the domain-filtered view.
  useEffect(() => {
    const d = window.__sigJumpDomain;
    if (d) { window.__sigJumpDomain = null; setView({ kind: "all" }); setDomFilter(d); }   // domain is a filter axis now
  }, []);
  // Signals are ANCHORED TO THE ORG DEFAULT PEER GROUP (David 2026-08-11: "signals should only be
  // tied to the company default — otherwise alerts will be all over the place"). The server computes
  // signals against orgs.default_cut regardless of the requested cut, so the page and the nightly
  // alert emails always agree; we fetch with that same cut so the confidence chip + peer label match
  // the signals. Reverses the 2026-07-10 "signals honour the app-wide selector" — the app-wide
  // selector is now hidden on /signals (app.js), and this page ignores it.
  const sigCut = signalCut(me);
  const _applyStrat = ((prefs && prefs._overview) || {}).apply_strategy !== false;
  const _cutKey = cutKeyOf(sigCut);
  // NEW handling (David 2026-08-11): DON'T clear NEW on load (that hid what was new before the user
  // scrolled). Stash the current ids and mark them seen on UNMOUNT, so this visit keeps its badges.
  const seenRef = useRef([]);
  useEffect(() => {
    let live = true;
    setData(null);
    apiCached("/api/overview?" + cutQS(sigCut) + (_applyStrat ? "" : "&strategy=off")).then(d => {
      if (!live) return;
      setData(d);
      seenRef.current = (d.signals_all || []).map(s => s.sig_id || s.question_id);
    }).catch(e => { if (live) setErr(e.message); });
    return () => { live = false; };
  }, [_cutKey, _applyStrat]);
  useEffect(() => () => { const ids = seenRef.current; if (ids && ids.length) api("/api/signals/seen", { method: "POST", body: { sig_ids: ids } }).catch(() => {}); }, []);
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
  const goToDomain = (dom) => { setView({ kind: "all" }); setPosFilter("all"); setDomFilter(dom); };   // strategy-check → filter to that domain (never dead-ends under a stale filter)
  // keyboard triage (David 2026-08-11): j/k move a focus ring, e/s/f act, Enter opens. Bound ONCE
  // (a stable listener above the early returns to satisfy hook order); it reads the live list +
  // handlers from kbRef, which the render refreshes each pass once data is in.
  const kbRef = useRef({});
  useEffect(() => {
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target; if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable || t.tagName === "SELECT")) return;
      const st = kbRef.current; const list = st.items || [];
      if (!list.length) return;
      const k = (e.key || "").toLowerCase();
      if (k === "j" || e.key === "ArrowDown") { e.preventDefault(); st.setKbIdx(i => Math.min((i < 0 ? -1 : i) + 1, list.length - 1)); }
      else if (k === "k" || e.key === "ArrowUp") { e.preventDefault(); st.setKbIdx(i => Math.max((i < 0 ? 0 : i) - 1, 0)); }
      else if (st.idx >= 0 && st.idx < list.length) {
        const s = list[st.idx];
        if (k === "e") { e.preventDefault(); st.dismissIt(s); }
        else if (k === "s") { e.preventDefault(); st.snoozeIt(s, 14); }
        else if (k === "f") { e.preventDefault(); st.fileIt(s); }
        else if (e.key === "Enter" || k === "o") { e.preventDefault(); window.openMetric(s.question_id); }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  // keep the focused card in view; reset the ring whenever the shown list changes underneath it
  useEffect(() => { if (kbIdx < 0) return; const el = document.querySelectorAll(".signals-page .brf-card")[kbIdx]; if (el) scrollIntoViewSafe(el, { block: "nearest" }); }, [kbIdx]);
  useEffect(() => { setKbIdx(-1); }, [view.kind, view.name, posFilter, sortMode, domFilter, textQuery]);
  // a restored card (Undo / wake / recover) flashes back into place using the existing sig-group-flash primitive
  useEffect(() => {
    if (!flashSid) return;
    const esc = window.CSS && CSS.escape ? CSS.escape(flashSid) : flashSid;
    const el = document.querySelector('.brf-card[data-sid="' + esc + '"]');
    if (el) { scrollIntoViewSafe(el, { block: "nearest" }); el.classList.add("sig-group-flash"); setTimeout(() => el.classList.remove("sig-group-flash"), 1700); }
    setFlashSid(null);
  }, [flashSid, view, posFilter, domFilter]);
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
      .catch(() => { setActing(a => { const n = { ...a }; delete n[sid]; return n; }); setActingSnz(m => { const n = { ...m }; delete n[sid]; return n; }); toast("Couldn't save that — try again", "error"); });
  };

  // ---- verbs (2026-07-10, David: toast instead of stub rows). Every action lets the card
  // leave the list with a soft exit (leaveThen), then a single confirmation toast carries
  // the Undo — the same restore paths the in-place stubs used, so nothing is lost.
  // cap the toast stack at 3 (was: wipe the host on every toast, which destroyed earlier Undos
  // still inside their TTL and blanked the live region mid-announcement — David review #2)
  const sigToast = (msg, undo) => {
    const h = document.getElementById("toast-host"); if (h) { while (h.children.length >= 3) h.removeChild(h.firstChild); }
    toast(msg, null, { label: "Undo", fn: undo }); };
  const _cssEsc = (v) => window.CSS && CSS.escape ? CSS.escape(v) : v;
  const leaveThen = (sid, fn) => {
    const el = document.querySelector('.brf-card[data-sid="' + _cssEsc(sid) + '"]');
    // keyboard/AT: don't drop focus to <body> when the acted card unmounts — move it to a neighbour (David review #3)
    const nb = el && ((el.nextElementSibling && el.nextElementSibling.classList.contains("brf-card") && el.nextElementSibling)
      || (el.previousElementSibling && el.previousElementSibling.classList.contains("brf-card") && el.previousElementSibling));
    const nbSid = nb ? nb.getAttribute("data-sid") : null;
    const focusNb = () => { if (!nbSid) return; const n = document.querySelector('.brf-card[data-sid="' + _cssEsc(nbSid) + '"]'); const v = n && n.querySelector(".brf-verb"); if (v) v.focus(); };
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!el || reduce) { fn(); setTimeout(focusNb, 20); return; }   // reduced-motion (or no node): snap
    el.style.height = el.offsetHeight + "px";
    void el.offsetHeight;                                // commit the measured height first
    el.classList.add("brf-leave");
    el.style.height = "0px";
    setTimeout(() => { fn(); setTimeout(focusNb, 20); }, 240);
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
    sigToast("Dismissed — " + sigName(s) + " · recover any time from the Dismissed tab", () => setStatus(sid, null)); }); };
  const unsave = (s) => { const sid = sidOf(s); leaveThen(sid, () => {
    setStatus(sid, null);
    sigToast("Removed from saved — back in your feed — " + sigName(s), () => setStatus(sid, "saved")); }); };

  // ---- folder-view verbs (same pattern: exit + toast-borne Undo)
  const moveTo = (s, name) => { const sid = sidOf(s); const prev = assign[sid]; leaveThen(sid, () => {
    const fl = folders.includes(name) ? folders : [...folders, name];
    writeSig({ folders: fl, assign: { ...assign, [sid]: name } });
    sigToast("Moved to “" + name + "” — " + sigName(s), () => writeSig({ folders: fl, assign: { ...assign, [sid]: prev } })); }); };
  const unfolder = (s) => { const sid = sidOf(s); const prev = assign[sid]; leaveThen(sid, () => {
    const na = { ...assign }; delete na[sid]; writeSig({ folders, assign: na });
    setStatus(sid, null); setFlashSid(sid);
    sigToast("Back in your feed — " + sigName(s),
      () => { writeSig({ folders, assign: { ...assign, [sid]: prev } }); setStatus(sid, "saved"); }); }); };
  const wake = (s) => { const sid = sidOf(s);
    const iso = s.snooze_until ? (s.snooze_until.includes("T") ? s.snooze_until : s.snooze_until.replace(" ", "T") + "Z") : null;
    const days = iso ? Math.max(1, Math.ceil((new Date(iso).getTime() - Date.now()) / 86400000)) : 14;
    leaveThen(sid, () => { setStatus(sid, null); setFlashSid(sid);
      sigToast("Back in your feed — " + sigName(s), () => setStatus(sid, "snoozed", days)); }); };
  const recover = (s) => { const sid = sidOf(s); leaveThen(sid, () => { setStatus(sid, null); setFlashSid(sid);
    sigToast("Recovered — back in your feed — " + sigName(s), () => setStatus(sid, "dismissed")); }); };

  // ---- folder ops (rename keeps every assignment; delete returns signals to the feed —
  // assignments clear, statuses untouched, nothing is deleted)
  const renameFolder = (from, to) => {
    if (folders.includes(to)) { toast("A folder with that name already exists", "error"); return; }
    const na = {}; Object.keys(assign).forEach(k => { na[k] = assign[k] === from ? to : assign[k]; });
    writeSig({ folders: folders.map(f => f === from ? to : f), assign: na });
    if (view.kind === "folder" && view.name === from) setView({ kind: "folder", name: to }); };
  const deleteFolder = (name) => {
    const prevFolders = folders, prevAssign = assign, prevView = view;   // snapshot for Undo (house pattern)
    const ids = Object.keys(assign).filter(k => assign[k] === name);
    const na = { ...assign }; ids.forEach(k => delete na[k]);
    writeSig({ folders: folders.filter(f => f !== name), assign: na });
    setView({ kind: "all" });
    sigToast('Folder "' + name + '" deleted — ' + (ids.length ? "its " + ids.length + " signal" + (ids.length === 1 ? "" : "s") + " back in your feed" : "it was empty"),
      () => { writeSig({ folders: prevFolders, assign: prevAssign }); setView(prevView); }); };
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
  // quick-saves from the home briefing / metric pages (status "saved", no folder yet)
  // surface in a built-in Saved view — a star anywhere is never invisible here; filing
  // it to a named folder from that view keeps the one-vocabulary promise.
  const savedItems = all.filter(s => s.status === "saved" && !assign[sidOf(s)]);
  const feedItems = all.filter(s => s.status !== "dismissed" && s.status !== "snoozed" && s.status !== "saved" && !assign[sidOf(s)]);
  const ordKey = s => [s.status === "priority" ? 0 : 1, s.new ? 0 : 1, s.risk_framed ? 0 : 1, s.worth ? 0 : 1, -(s.gap_pct || 0), -(s.n || 0)];
  feedItems.sort((a, b) => { const ka = ordKey(a), kb = ordKey(b);
    for (let i = 0; i < ka.length; i++) { if (ka[i] !== kb[i]) return ka[i] - kb[i]; } return 0; });
  const feedN = feedItems.length;
  const snoozedItems = all.filter(s => s.status === "snoozed");
  const dismissedItems = all.filter(s => s.status === "dismissed");
  // a folder deleted elsewhere (another tab) can leave a stale view — fall back to the feed
  const v = ((view.kind === "folder" && !folders.includes(view.name)) || (view.kind === "saved" && !savedItems.length)) ? { kind: "all" } : view;
  const baseItems = v.kind === "folder" ? all.filter(s => assign[sidOf(s)] === v.name)
    : v.kind === "snoozed" ? snoozedItems
    : v.kind === "dismissed" ? dismissedItems
    : v.kind === "saved" ? savedItems
    : feedItems;
  // domain filter axis + find-by-name compose with the view (David 2026-08-11); domain replaces the
  // old {kind:"domain"} view — the Overview scent chip + StrategyCheck both set this one filter.
  const domainOpts = Array.from(new Set(baseItems.map(s => s.domain).filter(Boolean))).sort((a, b) => domainLabel(a).localeCompare(domainLabel(b)));
  const tq = textQuery.trim().toLowerCase();
  const viewItems = baseItems.filter(s => (!domFilter || (s.domain || "") === domFilter)
    && (!tq || ((s.name || s.label_short || "") + " " + domainLabel(s.domain || "")).toLowerCase().includes(tq)));
  // market-position filter: counts come from the current view, then narrow the list to the picked
  // position ("all" keeps everything, incl. practice signals which carry no below/on/above position)
  const posCounts = { below: 0, on: 0, above: 0, practice: 0 };
  // practice/differs signals carry no market position — they get their own chip so the
  // four counts SUM to "All" (they used to cover 38 of 49 with no visible explanation)
  viewItems.forEach(s => {
    if (posCounts[s.position] != null) posCounts[s.position]++;
    else if (s.position === "differs" || s.position === "practice") posCounts.practice++;
  });
  const hasPos = (posCounts.below + posCounts.on + posCounts.above) > 0;   // any positioned (non-practice) signals here?
  const posOn = posFilter !== "all" && hasPos;                            // a stale filter is ignored on a practice-only view
  const shownItems = posOn
    ? viewItems.filter(s => posFilter === "practice"
        ? (s.position === "differs" || s.position === "practice")
        : s.position === posFilter)
    : viewItems;
  const POS_LABEL = { below: "Below market", on: "On market", above: "Above market", practice: "Practice differs" };
  const triaged = dismissedItems.length + snoozedItems.length + savedItems.length + Object.keys(assign).length;   // #28: a genuine cleared queue vs a quiet org
  const emptyLine = posOn ? "No signals " + POS_LABEL[posFilter].toLowerCase() + " in this view — clear the position filter to see the rest."
    : tq ? 'No signals match "' + textQuery.trim() + '" — clear the search to see the rest.'
    : domFilter ? "No live signals in " + domainLabel(domFilter) + " right now — clear the domain filter, or check the Snoozed and Dismissed tabs."
    : v.kind === "saved" ? "Nothing saved — star a signal anywhere in lumi and it lands here."
    : v.kind === "folder" ? 'Nothing in "' + v.name + '" yet — File a signal from the feed to keep it here.'
    : v.kind === "snoozed" ? "Nothing snoozed — a snoozed signal waits here and returns to your feed on its date."
    : v.kind === "dismissed" ? "Nothing dismissed — anything you dismiss is kept here and can be recovered."
    : triaged > 0 ? "Inbox zero. Everything's filed — saved, snoozed or dismissed. New signals land here as your position or the market moves."
    : "Nothing needs your attention right now — new signals land here as your position or the market moves.";

  // ---- sort (David 2026-08-11): priority (machine order) · by domain · biggest gap first ----
  const ordCmp = (a, b) => { const ka = ordKey(a), kb = ordKey(b); for (let i = 0; i < ka.length; i++) { if (ka[i] !== kb[i]) return ka[i] - kb[i]; } return 0; };
  const sortedItems = sortMode === "gap" ? [...shownItems].sort((a, b) => (b.gap_pct || 0) - (a.gap_pct || 0) || ordCmp(a, b))
    : sortMode === "domain" ? [...shownItems].sort((a, b) => domainLabel(a.domain || "~").localeCompare(domainLabel(b.domain || "~")) || ordCmp(a, b))
    : [...shownItems].sort(ordCmp);
  // f = quick-save to the star-fed "Saved" tab (folderless), the single "save" concept (File to… is folders)
  const fileIt = (s) => { const sid = sidOf(s); leaveThen(sid, () => { setStatus(sid, "saved"); sigToast("Saved for later — " + sigName(s), () => setStatus(sid, null)); }); };
  // bulk actions on a NARROWED active view (a position filter, or a single domain) — one Undo reverts the batch
  const bulkable = v.kind === "all" && (posOn || !!domFilter) && sortedItems.length >= 2;   // bulk on a narrowed feed (position or domain)
  const bulkAct = (status, days) => {
    const items = sortedItems.slice();
    const prior = items.map(s => ({ sid: sidOf(s), status: s.status || null }));
    items.forEach(s => setStatus(sidOf(s), status, days));
    setKbIdx(-1);
    sigToast((status === "dismissed" ? "Dismissed " : "Snoozed ") + items.length + " signal" + (items.length === 1 ? "" : "s")
      + (status === "snoozed" ? " · until " + sigRetDate(days) : ""), () => prior.forEach(p => setStatus(p.sid, p.status)));
  };
  kbRef.current = { items: sortedItems, idx: kbIdx, setKbIdx, dismissIt, snoozeIt, fileIt };

  // ---- the evidence card (Briefing anatomy, unchanged): caption + risk shield, stand-
  // sentence headline, "Flagged because … · n · verified/estimate", soft chips, gap bar,
  // lens tag, On plan, "See the evidence →". Verbs vary by the active folder view.
  const sigCard = (s, focused) => {
    const sid = sidOf(s);
    // (the in-place stub row retired 2026-07-10, David: toast instead of stub rows)
    const tone = brfTone(s);
    const gapDir = s.position === "above" ? "above" : s.position === "on" ? "off" : "below";
    // the whole card opens the metric (verbs/menus stopPropagation); keyboard ring adds .kb-focus
    return html`<article key=${sid} class=${"brf-card brf-tone-" + tone + (focused ? " kb-focus" : "")} data-dom=${s.domain || ""} data-sid=${sid}
      onClick=${() => window.openMetric(s.question_id)}>
      <div class="brf-cap">
        <span class="brf-cap-name">${s.name || s.label_short}</span>
        ${s.domain ? html`<span class="brf-cap-dom">· ${domainLabel(s.domain)}</span>` : null}
        ${s.new ? html`<span class="sig-new-tag">NEW</span>` : null}
        ${s.status === "priority" ? html`<span class="sfold-prio" title="Prioritised — ranks first in your feed"><${Icon} name="pin" size=${10} /> priority</span>` : null}
        ${s.risk_framed ? html`<span class="brf-shield"><${Icon} name="shield" size=${10} /> risk</span>` : null}
        ${v.kind === "snoozed" && s.snooze_until ? html`<span class="sfold-snz"><${Icon} name="clock" size=${10} /> ${snoozeReturn(s.snooze_until)}</span>` : null}
      </div>
      <h3 class="brf-head">${brfCap(s.stand || s.detail)}</h3>
      <div class="brf-why"><b>Flagged because:</b> ${brfRule(s)}${s.n != null ? html`<span class="num"> · ${compositionLabel(s.n, s.n_real)}</span>` : null}${provMark(s)}${s.strategy_note ? html`<span class="sig-strat-note"> · ${s.strategy_note}</span>` : null}</div>
      <div class="brf-chips">
        <span class=${"brf-pos brf-pos-" + tone}>${brfChipText(s)}</span>
        ${s.gap_pct != null ? html`<span class=${"brf-gap brf-gap-" + tone} aria-label=${"About " + s.gap_pct + "% " + gapDir + " the market median"}>${s.gap_pct}% ${gapDir}</span>` : null}
        ${s.lens ? html`<span class="brf-lens" title=${LENS_DESC[s.lens] || null}>${LENS_LABEL[s.lens] || s.lens}</span>` : null}
        ${s.confirm ? html`<span class="brf-onplan"><${Icon} name="check" size=${11} /> On plan</span>` : null}
      </div>
      ${s.strategy_influence && s.strategy_influence.length ? html`
        <div class="brf-strat"><${Icon} name="compass" size=${11} /> ${sigStratLine(s.strategy_influence)}</div>` : null}
      <div class="brf-verbs" onClick=${e => e.stopPropagation()}>
        ${v.kind === "all" ? html`
          <${SigFolderMenu} label="File to…" folders=${folders} onPick=${n => saveTo(s, n)} />
          <${SigSnoozeMenu} onPick=${d => snoozeIt(s, d)} />
          <button type="button" class="brf-verb" onClick=${() => dismissIt(s)}>Dismiss</button>`
        : v.kind === "folder" ? html`
          <${SigFolderMenu} label="Move to…" folders=${folders} exclude=${v.name} onPick=${n => moveTo(s, n)} />
          <button type="button" class="brf-verb" onClick=${() => unfolder(s)}>Remove from folder</button>`
        : v.kind === "saved" ? html`
          <${SigFolderMenu} label="File to folder…" folders=${folders} onPick=${n => saveTo(s, n)} />
          <button type="button" class="brf-verb" onClick=${() => unsave(s)}>Remove from saved</button>`
        : v.kind === "snoozed" ? html`
          <button type="button" class="brf-verb" onClick=${() => wake(s)}>Wake now</button>`
        : html`
          <button type="button" class="sfold-recover" onClick=${() => recover(s)}><${Icon} name="refresh" size=${12} /> Recover</button>`}
        <button type="button" class="brf-see" onClick=${() => openMetric(s.question_id)}>See the evidence <span aria-hidden="true">→</span></button>
      </div>
    </article>`;
  };

  const isFold = f => v.kind === "folder" && v.name === f;
  const unread = feedItems.filter(s => s.new).length;   // NEW badge count on the Inbox pill (no longer cleared on mount)
  const navyFooter = html`
    <div class="brf-navy">
      <div class="brf-navy-reg"><${Icon} name="table" size=${15} />
        <span><b>Full gap register</b> — every metric against the market, not just those flagged. <a href="#/priorities">Open the register</a>${me.user && me.user.role === "admin" ? html` · <a href=${"/api/gap-register.csv?" + cutQS(sigCut)} download onClick=${() => toast("Gap register downloading — " + cutLabelOf(sigCut, cuts) + ".")}>Download CSV</a>` : null}</span>
      </div>
      <div class="brf-life"><span class="brf-life-note">Snooze and Dismiss file signals into their folders — <b>nothing is deleted</b>.</span></div>
    </div>`;
  return html`
    <div class="signals-page brf-page" style=${{ maxWidth: "1120px", margin: "0 auto" }}>
      <div class="ov-aurora" aria-hidden="true"></div>
      <h1 class="display-title" style=${{ marginBottom: "var(--s2)" }}>Signals</h1>
      ${/* Signals are anchored to the org DEFAULT peer group (David 2026-08-11), so the page and
            the nightly email alerts never flag different things. Trust surface = that group's
            ConfidenceChip + a note naming it; the app-wide selector is hidden on /signals (app.js).
            (Reverses the 2026-07-10 "honour the app-wide selector" — that made alerts and the page
            disagree the moment a cut was chosen.) */ ""}
      ${unlocked ? html`<div class="conf-line" style=${{ justifyContent: "flex-start", marginTop: 0, marginBottom: "var(--s1)" }}>
        <${ConfidenceChip} n=${cutSize(sigCut, cuts, me.peer_pool)} window=${data.snapshot && data.snapshot.window} />
      </div>
      <div class="sig-subhead" style=${{ marginBottom: "var(--s4)" }}>
        <span class="caption sig-peer-note">Flagged against your <span class="indic-flag sig-peergrp" tabindex="0" role="note" aria-label=${"Default peer group: " + ((me.org && me.org.signal_peer_label) || "all peers")} onKeyDown=${e => { if (e.key === "Escape") e.currentTarget.blur(); }}><b>default peer group</b> <${Icon} name="info" size=${11} /><span class="indic-tip">${(me.org && me.org.signal_peer_label) || "all peers"} — set in Settings; the same group your email alerts use.</span></span>${me.user && (me.user.role === "admin" || me.user.role === "contributor") ? html` · <a href="#/settings">Change</a>` : ""}</span>
        <a href="#/priorities" class="btn small sig-reg-btn"><${Icon} name="table" size=${13} /> Full gap register</a>
      </div>` : null}
      ${!unlocked ? html`<${SignalsLocked} contrib=${contrib} me=${me} />`
      : all.length === 0 ? html`
        <div class="signals-empty" style=${{ marginTop: "var(--s5)" }}>
          <span class="signals-empty-ring"><${Icon} name="flag" size=${18} /></span>
          <div class="caption" style=${{ maxWidth: "380px" }}>Nothing to flag yet — signals appear here as your position or the market moves. Meanwhile, browse every metric in the <a href="#/priorities">full gap register</a>.</div>
        </div>
        ${navyFooter}`
      : html`
        ${/* FOLDER NAV — the only control above the feed: All · user folders · Snoozed ·
              Dismissed · a quiet + New folder. The active user folder carries a small "…"
              (Rename / Delete). */ ""}
        <div class="sfold-nav" role="group" aria-label="Signal folders">
          <button type="button" class=${"sfold-pill sfold-inbox" + (v.kind === "all" ? " on" : "")} aria-pressed=${v.kind === "all"}
            onClick=${() => setView({ kind: "all" })}>Inbox <b class="num">${feedN}</b>${unread > 0 ? html`<span class="sfold-unread" title=${unread + " new since your last visit"}>${unread}</span>` : null}</button>
          ${folders.map(f => html`<span key=${"f-" + f} class="sfold-pillwrap">
            <button type="button" class=${"sfold-pill" + (isFold(f) ? " on" : "")} aria-pressed=${isFold(f)}
              onClick=${() => setView({ kind: "folder", name: f })}><${Icon} name="folder" size=${12} /> ${f} <b class="num">${cntFolder(f)}</b></button>
            ${isFold(f) ? html`<${SigFolderOps} name=${f} onRename=${to => renameFolder(f, to)} onDelete=${() => deleteFolder(f)} />` : null}
          </span>`)}
          ${savedItems.length ? html`<button type="button" class=${"sfold-pill" + (v.kind === "saved" ? " on" : "")} aria-pressed=${v.kind === "saved"}
            onClick=${() => setView({ kind: "saved" })}><${Icon} name="star" size=${12} /> Saved <b class="num">${savedItems.length}</b></button>` : null}
          ${navNaming ? html`<span class="sfold-newrow sfold-newrow-nav">
            <input type="text" class="sfold-newinput" placeholder="Folder name" aria-label="New folder name" maxlength="40" value=${navNm}
              ref=${el => { if (el && !el._f) { el._f = 1; el.focus(); } }} onInput=${e => setNavNm(e.target.value)}
              onKeyDown=${e => { if (e.key === "Enter") { e.preventDefault(); commitNavFolder(); }
                if (e.key === "Escape") { setNavNaming(false); setNavNm(""); } }} />
            <button type="button" class="sfold-newgo" disabled=${!navNm.trim()} onClick=${commitNavFolder}>Add</button>
          </span>` : html`<button type="button" class="sfold-new" onClick=${() => setNavNaming(true)}>+ New folder</button>`}
          ${/* lifecycle bins pushed right, recessive — filing, not active triage */ ""}
          <span class="sfold-life">
            <button type="button" class=${"sfold-pill sfold-quiet" + (v.kind === "snoozed" ? " on" : "")} aria-pressed=${v.kind === "snoozed"}
              onClick=${() => setView({ kind: "snoozed" })}><${Icon} name="clock" size=${12} /> Snoozed <b class="num">${snoozedItems.length}</b></button>
            <button type="button" class=${"sfold-pill sfold-quiet" + (v.kind === "dismissed" ? " on" : "")} aria-pressed=${v.kind === "dismissed"}
              onClick=${() => setView({ kind: "dismissed" })}><${Icon} name="close" size=${12} /> Dismissed <b class="num">${dismissedItems.length}</b></button>
          </span>
        </div>

        ${domFilter ? html`
          <div class="sfold-filter">
            <span class="sfold-filter-lab">Domain: <b>${domainLabel(domFilter)}</b> · <span class="num">${viewItems.length}</span> signal${viewItems.length === 1 ? "" : "s"}</span>
            <button type="button" class="sfold-filter-clear" onClick=${() => setDomFilter(null)}><${Icon} name="close" size=${11} /> Clear domain</button>
          </div>` : null}

        ${/* market-position filter — narrow the current view to below / on / above the market (David 2026-08-11) */ ""}
        ${hasPos ? html`
          <div class="sig-posfilter" role="group" aria-label="Filter by market position">
            <span class="sig-posfilter-lab">Position</span>
            <button type="button" class=${"sig-pos-pill" + (posFilter === "all" ? " on" : "")} aria-pressed=${posFilter === "all"}
              onClick=${() => setPosFilter("all")}>All <b class="num">${viewItems.length}</b></button>
            ${["below", "on", "above", "practice"].map(p => html`
              <button key=${p} type="button" class=${"sig-pos-pill pos-" + p + (posFilter === p ? " on" : "")} aria-pressed=${posFilter === p}
                onClick=${() => setPosFilter(posFilter === p ? "all" : p)}>
                <span class="pos-dot"></span>${POS_LABEL[p]} <b class="num">${posCounts[p]}</b></button>`)}
          </div>` : null}

        ${/* strategy-check moved ABOVE the feed (David review #17) — a collapsible orienting strip */ ""}
        ${v.kind === "all" && data.strategy_complete ? html`
          <div class=${"sig-strat-strip" + (stratOpen ? " open" : "")}>
            <button type="button" class="sig-strat-toggle" aria-expanded=${stratOpen} onClick=${() => setStratOpen(o => !o)}>
              <${Icon} name="compass" size=${14} /> <span>Are you delivering the strategy you set?</span>
              <span class="sfold-caret" aria-hidden="true">${stratOpen ? "▴" : "▾"}</span>
            </button>
            ${stratOpen ? html`<${StrategyCheck} onGoToDomain=${goToDomain} signalDomains=${signalDomains} />` : null}
          </div>` : null}

        ${baseItems.length > 0 ? html`
          <div class="sig-toolbar">
            <input class="sig-search" type="search" placeholder="Find a signal…" aria-label="Find a signal by name"
              value=${textQuery} onInput=${e => setTextQuery(e.target.value)} />
            ${domainOpts.length > 1 ? html`<label class="sig-sort">Domain
              <select value=${domFilter || ""} onChange=${e => setDomFilter(e.target.value || null)} aria-label="Filter by domain">
                <option value="">All domains</option>
                ${domainOpts.map(d => html`<option key=${d} value=${d}>${domainLabel(d)}</option>`)}
              </select></label>` : null}
            ${sortedItems.length > 1 ? html`<label class="sig-sort">Sort
              <select value=${sortMode} onChange=${e => setSortMode(e.target.value)} aria-label="Sort signals">
                <option value="priority">Priority</option>
                <option value="domain">By domain</option>
                <option value="gap">Biggest gap</option>
              </select></label>` : null}
            ${bulkable ? html`<span class="sig-bulk">
              <span class="sig-bulk-lab">${sortedItems.length} shown</span>
              <button type="button" class="sig-bulk-btn" onClick=${() => bulkAct("snoozed", 14)}>Snooze all</button>
              <button type="button" class="sig-bulk-btn" onClick=${() => bulkAct("dismissed")}>Dismiss all</button>
            </span>` : null}
            <span class="sig-kbhint" aria-hidden="true">j / k move · e·s·f triage · ⏎ open</span>
          </div>` : null}

        ${sortedItems.length === 0 ? html`
            <div class="signals-empty sfold-empty" role="status" style=${{ marginTop: "var(--s5)" }}>
              <span class="signals-empty-ring"><${Icon} name=${v.kind === "snoozed" ? "clock" : v.kind === "dismissed" ? "close" : v.kind === "folder" ? "folder" : "flag"} size=${18} /></span>
              <div class="caption" style=${{ maxWidth: "380px" }}>${emptyLine}</div>
            </div>`
          : sortMode === "domain" ? (() => {
              const rows = []; let last = null;
              sortedItems.forEach((s, i) => {
                const dl = s.domain ? domainLabel(s.domain) : "Other";
                if (dl !== last) { last = dl; rows.push(html`<div key=${"dh-" + i} class="sig-domhead">${dl}</div>`); }
                rows.push(sigCard(s, i === kbIdx));
              });
              return rows;
            })()
          : sortedItems.map((s, i) => sigCard(s, i === kbIdx))}

        ${navyFooter}`}
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
        ` : html`
        <div class="tile-band" style=${{ marginTop: "var(--s1)" }}>
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
        Movement shows here from your next cycle.
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
    // fetch per page builds the qid -> signal map for every card's status pill.
    // 2026-08-09 review: honour the strategy-off preference like every other surface.
    apiCached("/api/overview?" + cutQS(cut) + (((prefs && prefs._overview) || {}).apply_strategy !== false ? "" : "&strategy=off")).then(o => {
      if (!live) return;
      const m = {}; (o.signals_all || []).forEach(s => { (m[s.question_id] = m[s.question_id] || []).push(s); }); setSigMap(m);
    }).catch(() => { if (live) setSigMap({}); });
    return () => { live = false; };
  }, [sp, cutKeyOf(cut), ((prefs && prefs._overview) || {}).apply_strategy]);
  useEffect(() => {
    if (data && focusQ) {
      const el = document.getElementById("q-" + focusQ);
      if (el) scrollIntoViewSafe(el);
    }
  }, [data, focusQ]);
  if (err) return html`<${EmptyState} title="Couldn't load this section"
    body=${err + " — nothing is lost."}
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
  // every "clear*" variant (clear / clear-practice / clear-unbenchmarked) is one
  // "No signal" bucket — else practice/unbenchmarked no-flag cards drop from the count AND filter.
  // Protected (suppressed) cards count as "No signal" too: nothing is flagged on them,
  // and leaving them bucket-less made the three chips sum to 326 of "328 benchmarks".
  const sigBucket = (st, c) => (st && st.indexOf("clear") === 0) ? "clear" : (st || (c && c.suppressed ? "clear" : st));
  cards.forEach(c => { const b = sigBucket(cardSignalState(c, sigMap[c.id]), c); if (b) sigCounts[b]++; });
  if (sigF) cards = cards.filter(c => sigBucket(cardSignalState(c, sigMap[c.id]), c) === sigF);

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
              <option value="">All types</option>
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
        action=${html`<button class="btn small" onClick=${() => { setCat(""); setSigF(""); }}>Clear filters</button>`} />`}
      ${bySub.map(g => html`
        <div key=${g.sub} style=${{ marginBottom: "var(--s5)" }}>
          ${!subF && html`<h2 class="section-title">${g.sub}</h2>`}
          <div class="bench-grid">
            ${g.cards.map(c => html`
              <div key=${c.id} id=${"q-" + c.id}>
                <${Guarded}><${BenchmarkCard} card=${c} prefs=${prefs} onPref=${onPref} onPin=${onPin}
                  pinned=${pinnedIds.has(c.id)} cuts=${cuts} globalCut=${cutKeyOf(cut)} signal=${sigMap[c.id]}
                  window=${me.peer_pool && me.peer_pool.collection_window} highlight=${focusQ === c.id} /><//>
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
  // "prevalence" retired from the embedded view too (Diff 4 ruling 4, 2026-07-14):
  // domain pages exclude practice from analysis — the narrative reads position only here.
  const EMB_SLOTS = SLOTS.filter(([k]) => k !== "notable" && k !== "prevalence");
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
          <div class="cat-sum-caveat">AI insights can write this in fuller prose — <a href="#/settings">review ${"&"} enable</a>.</div>` : null}
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
    body=${err + " — nothing is lost."}
    action=${html`<button class="btn small primary" onClick=${() => setCatRetry(k => k + 1)}>Retry</button>`} />`;
  if (!ov || !bench) return html`<div>${Head("Loading…")}<${SkeletonGrid} count=${4} /></div>`;

  const hero = ((ov.hero && ov.hero.domains) || []).find(d => d.name === name);
  // an unknown/legacy domain name (stale bookmark, renamed domain) must not crash the
  // whole app on hero.drivers below — name the miss and offer the way back
  if (!hero) return html`<div>${Head(name)}
    <${EmptyState} icon="info" title="This category isn't in your benchmark"
      body=${`"${name}" doesn't match any of your reward areas — it may have been renamed.`}
      action=${html`<button class="btn small primary" onClick=${() => nav("/benchmark")}>See all benchmarks</button>`} /></div>`;
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
  // "Print / save as PDF" pattern); the pack mirrors the CURRENT view — cut, strategy state,
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
              <span class="caption" style=${{ display: "block" }}>Every benchmark as shown</span></button>
            <button class="bp-menu-item" role="menuitem" onClick=${() => printPack(false)}>
              <b>Figures only</b>
              <span class="caption" style=${{ display: "block" }}>Positions, values and peer stats — no charts</span></button>
            <a class="bp-menu-item" role="menuitem" href=${"/api/benchmark.csv?" + cutQS(cut) + "&sp=" + encodeURIComponent(name)} download onClick=${() => toast("Spreadsheet downloading — " + domainLabel(name) + " on " + cutLabelOf(cut, cuts) + ".")}>
              <b>Spreadsheet (CSV)</b>
              <span class="caption" style=${{ display: "block" }}>The raw numbers on this peer group</span></a>
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
            html`<span class="caption cat-brief-span">Not enough positioned metrics for a market stance yet — this area is assessed on practice.</span>`}
          ${/* practice read-line RETIRED (Diff 4 ruling 3, 2026-07-14): domain pages exclude
                practice from analysis — the home bucket and the practice lens carry the
                story; practice ROWS stay in the metric list below, tagged. */ ""}
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
          <b>All benchmarks</b><span class="pulse-count-chip">${cards.length}</span>
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
              <${Guarded}><${BenchmarkCard} card=${c} prefs=${prefs} onPref=${onPref} onPin=${onPin}
                pinned=${pinnedIds.has(c.id)} cuts=${cuts} globalCut=${cutKeyOf(cut)} signal=${sigMap[c.id]}
                window=${me.peer_pool && me.peer_pool.collection_window} /><//>
            </div>`)}
        </div>`}
      </section>
    </div>`;
};

// --------------------------------------------------------- my dashboards ---
// Several named, saveable dashboards per user. A switcher tab-bar sits above the
// same draggable card grid the old single "My view" used; the active dashboard
// is what the global pin-star (anywhere in the app) writes to.
window.DashboardsPage = function ({ me, cut, cuts, prefs, onPref, setPinned, onCut, onTwinInfo, refreshMe }) {
  const [list, setList] = useState(null);       // [{id,name,position,count,cut}]
  const [activeId, setActiveId] = useState(null);
  const [layout, setLayout] = useState(null);   // active dashboard's slots
  // Per-dashboard peer sample (2026-08-11, David): each dashboard owns its cut. This is the
  // EFFECTIVE cut for every card on the active dashboard — NOT the app-wide selector (which is
  // hidden on this page). Defaults to all-peers until the user picks a sample for the dashboard.
  const [activeCut, setActiveCut] = useState({ dim: "all", value: null });
  const [cards, setCards] = useState({});
  const [drag, setDrag] = useState(null);
  const [sigMap, setSigMap] = useState({});
  const [renaming, setRenaming] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [confirmDel, setConfirmDel] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);          // §4.10(2): a failed load must not hang on the skeleton
  const [opsOpen, setOpsOpen] = useState(false); // the dashboard's ⋯ menu (rename/duplicate/delete)
  const nameRef = useRef(null);
  const opsRef = useRef(null);
  const cancelRename = useRef(false);   // Escape sets this so the input's onBlur doesn't commit
  useMenuClose(opsRef, opsOpen, setOpsOpen);

  const applyActive = (id, lay, dcut) => {
    setActiveId(id); setLayout(lay); setCards({});
    setActiveCut(dcut && dcut.dim ? dcut : { dim: "all", value: null });
    if (setPinned) setPinned((lay || []).map(s => s.question_id));
  };
  // cache key folds in the EFFECTIVE peer cut (this dashboard's sample, or a slot's own
  // override), so switching the dashboard's sample yields a fresh key → refetch, not a stale card.
  const cardKey = slot => slotKey(slot) + "|" + cutKeyOf(slot.cut || activeCut);
  const reload = () => { setErr(null); return api("/api/dashboards").then(d => {
    setList(d.dashboards); applyActive(d.active_id, d.active.layout, d.active.cut);
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
    // 2026-08-09 review: honour the strategy-off preference like every other surface.
    // Signal overlay reflects THIS dashboard's sample (activeCut), not the app-wide selector.
    apiCached("/api/overview?" + cutQS(activeCut) + (((prefs && prefs._overview) || {}).apply_strategy !== false ? "" : "&strategy=off")).then(o => {
      if (!live) return;
      const m = {}; (o.signals_all || []).forEach(s => { (m[s.question_id] = m[s.question_id] || []).push(s); }); setSigMap(m);
    }).catch(() => { if (live) setSigMap({}); });
    return () => { live = false; };
  }, [cutKeyOf(activeCut), ((prefs && prefs._overview) || {}).apply_strategy]);
  useEffect(() => {
    if (!layout) return;
    // one request per cut group instead of one per pinned card (20 pins was 20 GETs)
    const missing = layout.filter(slot => !cards[cardKey(slot)]);
    if (!missing.length) return;
    const groups = new Map();
    missing.forEach(slot => {
      const qs = cutQS(slot.cut || activeCut);
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
  }, [layout, cutKeyOf(activeCut)]);
  useEffect(() => { if (renaming && nameRef.current) { nameRef.current.focus(); nameRef.current.select(); } }, [renaming]);

  if (err) return html`<${EmptyState} title="Couldn't load your dashboards"
    body=${err + " — nothing is lost."}
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
  // R-P10/R-P2: the printed artefact names its comparison object. Static
  // "reference panel" is EXACT today (real n = 0 everywhere); Phase 1 replaces
  // it with the ruled composition chip (panel / members+panel / members).
  const peerLabel = (!activeCut || !activeCut.dim || activeCut.dim === "all")
    ? "All peers · " + (SHOW_COMPOSITION_IN_PRODUCT
        ? compositionLabel((me.peer_pool || {}).responding_orgs, (me.peer_pool || {}).real_orgs)
        : ((me.peer_pool || {}).responding_orgs || "—"))
    : activeCut.dim === "twin" ? "Organisations like you"
    : (activeCut.value || activeCut.dim);
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
  // keyboard path for reorder (WCAG 2.1.1) — the drag handle is a real button;
  // arrows move the card one slot, the live region reports the new position.
  const moveBy = (i, delta) => {
    const j = i + delta;
    if (j < 0 || j >= layout.length) return;
    const next = [...layout];
    const [m] = next.splice(i, 1);
    next.splice(j, 0, m);
    persist(next);
    const el = document.getElementById("dash-reorder-live");
    if (el) el.textContent = "Moved to position " + (j + 1) + " of " + next.length;
  };

  const switchTo = async (id) => {
    if (id === activeId || busy) return;
    setBusy(true); setRenaming(false); setConfirmDel(false);
    try {
      await api(`/api/dashboards/${id}/activate`, { method: "POST" });
      const d = await api(`/api/dashboards/${id}`);
      applyActive(id, d.layout, d.cut);
    } catch (e) { toast("Couldn't switch dashboard — try again.", "error"); }
    finally { setBusy(false); }
  };
  // Set THIS dashboard's peer sample (David 2026-08-11). PeerSetBar hands us a cut KEY;
  // parse it, apply locally (cards refetch — cardKey folds in the cut), and persist to the
  // dashboard. "manage-groups" is the app-level modal, so delegate it to the global handler.
  const setDashboardCut = (key) => {
    if (key === "manage-groups") { onCut && onCut(key); return; }
    const c = key === "all" || !key ? { dim: "all", value: null }
      : key === "twin" ? { dim: "twin", value: null }
      : (() => { const [dim, value] = key.split("::"); return { dim, value }; })();
    setActiveCut(c);
    const stored = c.dim === "all" ? null : c;
    setList(l => l.map(d => d.id === activeId ? { ...d, cut: stored } : d));
    api(`/api/dashboards/${activeId}`, { method: "PUT", body: { cut: stored } })
      .catch(() => toast("Couldn't save this dashboard's sample — it may reset next visit.", "error"));
  };
  const createNew = async () => {
    if (busy) return;
    setBusy(true); setConfirmDel(false);
    try {
      // auto-number so three fresh dashboards don't all read "New dashboard"
      const base = "New dashboard";
      const taken = new Set(list.map(x => x.name));
      let nm = base, k = 2;
      while (taken.has(nm)) nm = base + " " + (k++);
      const d = await api("/api/dashboards", { method: "POST", body: { name: nm } });
      await reload();
      setNameDraft(d.name); setRenaming(true);
    } catch (e) { toast("Couldn't create the dashboard — try again.", "error"); }
    finally { setBusy(false); }
  };
  const duplicate = async () => {
    if (busy) return;
    setBusy(true); setConfirmDel(false);
    try {
      await api("/api/dashboards", { method: "POST", body: { name: activeName + " copy", clone_from: activeId } });
      await reload();
      toast("Dashboard duplicated.");
    } catch (e) { toast("Couldn't duplicate the dashboard — try again.", "error"); }
    finally { setBusy(false); }
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
      applyActive(r.active_id, d.layout, d.cut);
      toast("Dashboard deleted.");
    } catch (e) { toast("Couldn't delete the dashboard — try again.", "error"); }
    finally { setBusy(false); }
  };
  // "Save as team default" button removed 2026-08-11 (David); the /api/myview/save-default
  // endpoint stays for any admin flow that seeds a new user's first dashboard.
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
      ${/* Download PDF + Share moved into the dashboard toolbar below (David 2026-08-11): up
            here beside the page title they read as universal/app-level actions, but they act on
            the ACTIVE dashboard — so they belong with its header. */ ""}
      <h1 class="display-title no-print" style=${{ marginBottom: "var(--s3)" }}>My dashboards</h1>

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
          ${/* the dashboard's structural actions (rename / duplicate / delete) collapse into one
                ⋯ menu (David 2026-08-11, "messy and clunky") — the three bare icons (the × read as
                a close) crowded the name. Reuses the shared kebab pattern (useMenuClose + brf-menu).
                The card count is dropped here: the active tab already carries its own count badge. */ ""}
          ${!renaming && html`
            <span class="brf-later-wrap dash-ops no-print" ref=${opsRef}>
              <button type="button" class="iconbtn kebab" aria-haspopup="menu" aria-expanded=${opsOpen}
                aria-label="Dashboard options" title="Rename, duplicate or delete this dashboard"
                onClick=${() => setOpsOpen(o => !o)}><span aria-hidden="true">⋯</span></button>
              ${opsOpen && html`<div class="brf-menu dash-menu" role="menu">
                <button class="brf-menu-opt" role="menuitem" onClick=${() => { setOpsOpen(false); startRename(); }}><${Icon} name="pencil" size=${13} /> Rename</button>
                <button class="brf-menu-opt" role="menuitem" disabled=${busy} onClick=${() => { setOpsOpen(false); duplicate(); }}><${Icon} name="copy" size=${13} /> Duplicate</button>
                <button class="brf-menu-opt" role="menuitem" disabled=${busy} onClick=${() => { setOpsOpen(false); setConfirmDel(true); }}><${Icon} name="close" size=${13} /> ${onlyOne ? "Reset dashboard" : "Delete dashboard"}</button>
              </div>`}
            </span>`}
        </div>
        <div class="dash-toolbar-r no-print">
          ${/* per-dashboard SAMPLE + per-dashboard ACTIONS (2026-08-11, David): the sample selector
                belongs to THIS dashboard (app-wide bar hidden on this page, app.js); Download PDF +
                Share act on the active dashboard, so they live in its header, not the page title. */ ""}
          <${PeerSetBar} me=${me} cut=${activeCut} cuts=${cuts} onSelect=${setDashboardCut}
            onTwinInfo=${onTwinInfo || (() => {})} inline=${true} prefs=${prefs} onPref=${onPref} refreshMe=${refreshMe} />
          <button class="btn small" onClick=${downloadPDF} disabled=${layout.length === 0}
            title=${layout.length === 0 ? "Add a card first" : "Download this dashboard as a PDF"}>
            <${Icon} name="download" size=${14} /> Download PDF</button>
          <${ShareButton} me=${me} cut=${activeCut} name=${activeName} layout=${layout} />
        </div>
      </div>

      ${confirmDel && html`
        <div class="dash-confirm" role="alertdialog" aria-label="Confirm dashboard change" ref=${el => { if (el && !el.dataset.focused) { el.dataset.focused = "1"; const b = el.querySelector("button"); if (b) b.focus(); } }}>
          <span><b>${onlyOne ? "Reset" : "Delete"} “${activeName}”?</b> ${onlyOne ? "It will be cleared back to your starting layout." : "This can't be undone."}</span>
          <div class="row" style=${{ gap: "var(--s2)" }}>
            <button class="btn small" onClick=${() => setConfirmDel(false)}>Cancel</button>
            <button class="btn small danger" onClick=${doDelete}>${onlyOne ? "Reset" : "Delete"}</button>
          </div>
        </div>`}

      ${layout.length === 0 && html`<${EmptyState} tone="invite" icon="star" title="This dashboard is empty"
        body="Use the pin icon on any benchmark card — it lands here."
        action=${html`<button class="btn small primary" onClick=${() => nav("/overview")}>Browse the benchmark</button>`} />`}

      <div id="dash-reorder-live" class="sr-only" aria-live="polite"></div>
      <div class=${"bench-grid" + (busy ? " is-busy" : "")}>
        ${layout.map((slot, i) => {
          const c = cards[cardKey(slot)];
          return html`
          <div key=${slotKey(slot)} draggable="true" class=${drag === i ? "dragging" : ""}
            onDragStart=${() => setDrag(i)} onDragOver=${e => e.preventDefault()} onDrop=${() => onDrop(i)}
            style=${slot.size === 2 ? { gridColumn: "span 2" } : null}>
            ${!c ? html`<${SkeletonCard} />` :
            c.error ? html`<div class="card bench-card"><${EmptyState} tone="error" title="Couldn't load this card" body="Nothing is lost — reopen the page to try again." /></div>` :
            html`<${Guarded}><${BenchmarkCard} card=${c} prefs=${prefs} onPref=${onPref} size=${slot.size}
              onPin=${() => remove(slot.question_id)} pinned=${true} cuts=${cuts} globalCut=${cutKeyOf(activeCut)} signal=${sigMap[slot.question_id]}
              footTools=${html`
                <button class="iconbtn" title=${slot.size === 2 ? "Single width" : "Double width"} aria-label="Card width" onClick=${() => resize(slot.question_id, slot.size === 2 ? 1 : 2)}>${slot.size === 2 ? "1×" : "2×"}</button>
                <button class="iconbtn" title="Reorder — drag, or focus and use arrow keys"
                  aria-label=${"Reorder card — position " + (i + 1) + " of " + layout.length + ". Use arrow keys to move."}
                  style=${{ cursor: "grab" }}
                  onKeyDown=${e => {
                    if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); moveBy(i, -1); }
                    else if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); moveBy(i, 1); }
                  }}>⠿</button>`} /><//>`}
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
  /* Redesigned 2026-08-04 (Your data pass). Two rules learned the hard way:
     1. THE NUMBER IS NEVER ANIMATED — the old rAF loop froze forever in hidden/
        background tabs, leaving "12%" on an org at 96%. Text shows the true
        value from the first paint; only the arc eases in, via a CSS transition
        the compositor settles correctly even when the tab was hidden.
     2. Completion is not performance — no RAG. Progress is the house blue
        (single-hue magnitude); green appears only at 100%, as the complete
        status. Amber never belonged here. */
  const target = Math.max(0, Math.min(100, pct));
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const [armed, setArmed] = useState(reduce);
  useEffect(() => {
    if (reduce) return;
    const t = setTimeout(() => setArmed(true), 30);   // arm on the next paint
    return () => clearTimeout(t);
  }, []);
  const r = (size - stroke) / 2, C = 2 * Math.PI * r;
  const off = C * (1 - (armed ? target : 0) / 100);
  const done = target >= 100;
  const col = done ? "var(--favourable)" : "var(--blue)";
  // per-instance gradient id — multiple rings coexist on viewer pages
  const gid = useState(() => "ringg" + (++CompletionRing._uid))[0];
  const cx = size / 2;
  return html`<svg width=${size} height=${size} viewBox=${"0 0 " + size + " " + size} class="comp-ring" aria-hidden="true">
    <defs><linearGradient id=${gid} x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color=${done ? "#2E7D52" : "#2048B0"} />
      <stop offset="1" stop-color=${done ? "#4FA372" : "#2E62D9"} />
    </linearGradient></defs>
    <circle cx=${cx} cy=${cx} r=${r} fill="none"
      stroke="color-mix(in srgb, #2048B0 6%, #F4F1EC)" stroke-width=${stroke} />
    <circle cx=${cx} cy=${cx} r=${r} fill="none" stroke=${"url(#" + gid + ")"} stroke-width=${stroke} stroke-linecap="round"
      stroke-dasharray=${C} stroke-dashoffset=${off} transform=${"rotate(-90 " + cx + " " + cx + ")"}
      style=${reduce ? null : { transition: "stroke-dashoffset 850ms cubic-bezier(0.33, 1, 0.68, 1)" }} />
    ${target > 3 && target < 100 && html`<circle
      cx=${cx + r * Math.cos((target / 100) * 2 * Math.PI - Math.PI / 2)}
      cy=${cx + r * Math.sin((target / 100) * 2 * Math.PI - Math.PI / 2)}
      r=${Math.max(2.5, stroke / 2 - 1.5)} fill="#fff" stroke=${col} stroke-width="2"
      style=${{ opacity: armed ? 1 : 0, transition: reduce ? null : "opacity 300ms ease 800ms" }} />`}
    <text x="50%" y="50%" text-anchor="middle" dominant-baseline="central" class="comp-ring-pct" style=${{ fill: col }}>${Math.round(target)}%</text>
  </svg>`;
}
CompletionRing._uid = 0;
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
  // Proximity to the unlock gate — the North-Star lever (empty-state review). The
  // gate measures KEY (required) questions only, so the page leads with those, not
  // the all-question totals that make a close org look far away.
  const locked = !c.insights_unlocked;
  const corePct = Math.round(c.core_pct || 0);
  const need = window.unlockNeed(c);            // exact key questions left to unlock
  const mins = window.keyMinutes(need);
  const keyLeftOf = d => (d.questions || []).filter(q => q.required && !q.answered).length;
  // One forward CTA, gate-aware. Until firmographics + data terms are cleared,
  // the on-ramp (/your-data/submit) runs those gates; after that the CTA points
  // at the SHORTEST path to unlock — the area with the fewest unanswered key
  // questions — not just whichever area sorts first.
  const profiled = !!(me && me.org && me.org.classified);   // firmographics done
  const termsAccepted = !!c.terms_accepted;                 // data terms accepted
  const gated = !profiled || !termsAccepted;
  const domainsArr = data.domains || [];
  const keyDomains = domainsArr.filter(d => keyLeftOf(d) > 0).sort((a, b) => keyLeftOf(a) - keyLeftOf(b));
  const nextDomain = keyDomains[0] || domainsArr.find(d => d.answered < d.total);
  const cta = gated
    ? { label: !profiled ? "Add your reward data" : "Review the data terms", to: "/your-data/submit" }
    : nextDomain
      ? { label: fresh ? "Add your reward data" : (locked && need > 0 ? `Continue — ${need} key to unlock` : "Continue your reward data"), to: "/your-data/" + encodeURIComponent(nextDomain.name) }
      : { label: "Review & submit", to: "/your-data/review" };
  return html`
    <div class="yourdata">
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <h1 class="display-title">Your data</h1>
          <div class="caption" style=${{ marginTop: "var(--s1)" }}>Everything your organisation has entered — autosaved and private to your team.</div>
        </div>
        ${canEdit && !fresh && html`<button class="btn primary" onClick=${() => nav(cta.to)}><${Icon} name="pencil" size=${14} /> ${cta.label}</button>`}
      </div>

      <div class=${"card data-hero" + (fresh ? " fresh" : "")}>
        <div class="data-hero-ringwrap" title=${locked ? "This dial tracks your key questions — insights unlock at " + target + "%. Optional extras don't gate unlock." : "You've unlocked — this now tracks every question you've answered."}>
          <${CompletionRing} pct=${locked ? corePct : data.pct} size=${118} stroke=${12} />
          <div class="caption" style=${{ textAlign: "center", marginTop: "var(--s1)" }}>${locked ? "key questions · unlocks at " + target + "%" : "all questions"}</div>
        </div>
        <div class="data-hero-body">
          <div class="data-hero-fig">${fresh ? html`<b>Let's build your reward benchmark.</b>`
            : html`<span class="dh-num">${data.answered}</span><span class="dh-den"> / ${data.total}</span><span class="dh-lbl">questions answered</span>`}</div>
          ${fresh ? html`<p class="data-hero-payoff">Answer your ${c.basis_total || "key"} key questions and lumi shows exactly where your pay, benefits and policies sit against your peer group — your £ gaps, the practices most peers offer that you don't, and a board-ready pack.</p>` : null}
          ${c.insights_unlocked ? html`
            <div class="data-unlock good"><span class="du-ico"><${Icon} name="sparkle" size=${14} /></span>
              <div><b>Insights unlocked</b> — thank you for contributing to the benchmark.</div></div>` : html`
            <div class="data-unlock"><span class="du-ico"><${Icon} name=${fresh ? "sparkle" : "lock"} size=${14} /></span>
              <div><b>${fresh ? "Insights unlock at " + target + "% of your key questions."
                : "You're at " + Math.round(c.core_pct || 0) + "% of your key questions — " + target + "% unlocks your insights."}</b>${c.days_left != null ? ` ${c.days_left} days left.` : ""}
                </div></div>`}
          ${fresh && canEdit && html`<button class="btn primary data-start" onClick=${() => nav(cta.to)}><${Icon} name="pencil" size=${14} /> ${cta.label}</button>`}
          ${fresh && canEdit && html`<p class="caption data-hero-reassure">Autosaved as you go · private to your organisation · resume any time.</p>`}
          ${!fresh && canEdit && !gated && html`<a class="data-review-link" href="#/your-data/review">Review & submit your data →</a>`}
          ${c.reduced && html`
            <div class="data-access warn">
              <${Icon} name="shield" size=${13} />
              <span><b>Access reduced.</b> Complete your data to ${target}% to restore full access.</span>
            </div>`}
          ${!fresh && html`
            <div class="dh-stats">
              ${locked && need > 0 ? html`<div class="dh-stat key"><b>${need}</b><span>key question${need === 1 ? "" : "s"} to unlock${mins ? " · " + mins : ""}</span></div>` : null}
              <div class="dh-stat"><b>${domainsArr.filter(d => d.answered >= d.total).length}</b><span>of ${domainsArr.length} areas complete</span></div>
              ${(!locked || need === 0) ? html`<div class="dh-stat"><b>${data.total - data.answered}</b><span>question${data.total - data.answered === 1 ? "" : "s"} remaining</span></div>` : null}
              ${data.to_refresh > 0 && html`<div class="dh-stat refresh"><b>${data.to_refresh}</b><span>due a refresh</span></div>`}
            </div>`}
        </div>
      </div>

      <div class="row spread" style=${{ marginTop: "var(--s5)", alignItems: "baseline" }}>
        <h2 class="section-title" style=${{ margin: 0 }}>By area</h2>
        
      </div>
      ${/* Redesigned 2026-08-04: the 8-domain world outgrew the ring-per-card
          grid (a 7-column rule left one orphan card, and eight donuts encode
          eight numbers in a lot of ink). Rows on ONE shared 0-100 scale make
          the domains comparable at a glance — the same instrument philosophy
          as the Overview domain ruler. Bars are the house blue (magnitude,
          single hue); green appears only as the Complete status chip. */ ""}
      <div class="card data-rows">
        ${domainsArr.map((d, di) => {
          const done = d.answered >= d.total;
          const keyLeft = keyLeftOf(d);
          return html`
          <div key=${d.name} class="data-row" role="button" tabindex="0"
            style=${{ "--i": di }}
            aria-label=${domainLabel(d.name) + ": " + d.answered + " of " + d.total + " answered"
              + (locked && keyLeft > 0 ? ", " + keyLeft + " of them key questions" : "")
              + (d.to_refresh > 0 ? ", " + d.to_refresh + " due a refresh" : "")}
            onClick=${() => nav("/your-data/" + encodeURIComponent(d.name))}
            onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nav("/your-data/" + encodeURIComponent(d.name)); } }}>
            <span class="cat-icon"><${Icon} name=${CAT_ICON[d.name] || "award"} size=${14} /></span>
            <span class="data-row-name">${domainLabel(d.name)}</span>
            <span class="data-bar" aria-hidden="true">
              ${d.answered > 0 && html`<span class=${"data-bar-fill" + (done ? " done" : "")}
                style=${{ width: Math.max(d.pct, 3) + "%" }}></span>`}
            </span>
            <span class="data-row-count"><b>${d.answered}</b><span class="drc-den">/${d.total}</span></span>
            ${/* one chip per row (subtractive bias): unanswered work first —
                completion drives access — then refresh-due trumps Complete: a
                finished area whose answers have aged needs attention, not
                celebration. The aria-label always carries both counts. */ ""}
            ${!done
              ? (locked && keyLeft > 0
                  ? html`<span class="data-q-flag todo"><${Icon} name="pencil" size=${13} /> ${keyLeft} key to do</span>`
                  : html`<span class="data-q-flag todo"><${Icon} name="pencil" size=${13} /> ${d.total - d.answered} to do</span>`)
              : d.to_refresh > 0
                ? html`<span class="data-q-flag refresh"><${Icon} name="refresh" size=${13} /> ${d.to_refresh} to refresh</span>`
                : html`<span class="data-q-flag ok"><${Icon} name="award" size=${13} /> Complete</span>`}
            <span class="data-row-go"><${Icon} name="chevron-right" size=${15} /></span>
          </div>`;
        })}
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
  if (d.to_refresh > 0) tabs.push({ k: "refresh", label: "To refresh", n: d.to_refresh });
  const qs = d.questions.filter(x => filter === "all" ? true
    : filter === "refresh" ? x.needs_refresh
    : (filter === "answered") === x.answered);
  return html`
    <div class="yourdata">
      <a class="caption back-link" href="#/your-data"><${Icon} name="chevron-left" size=${13} /> Your data</a>
      <div class="row spread" style=${{ alignItems: "center", margin: "var(--s1) 0 var(--s4)" }}>
        <div class="row" style=${{ gap: "var(--s3)", alignItems: "center" }}>
          <span class="cat-glyph"><${Icon} name=${CAT_ICON[section] || "award"} size=${20} /></span>
          <div><h1 class="display-title">${domainLabel(section)}</h1>
            <div class="caption meta">${d.answered} of ${d.total} answered${d.to_refresh > 0 ? " · " + d.to_refresh + " due a refresh" : ""}</div></div>
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
                ${q.required ? html`<span class="data-q-req" title="Counts toward the 90% that unlocks your insights">key</span>` : ""}</div>
              ${q.answered ? (q.rows ? html`
                <div class="data-q-rows">${q.rows.map((rw, i) => html`<span key=${i}><span class="muted">${rw.row}:</span> ${dataVal(rw.value, q)}</span>`)}</div>`
                : html`<div class="data-q-val">${dataVal(q.value, q)}</div>`)
                : html`<div class="data-q-none">Not answered yet${canEdit ? html` — <a href=${"#/your-data/submit/" + encodeURIComponent(section)}>add your answer</a>` : ""}</div>`}
              ${q.needs_refresh && html`<div class="data-q-updated">Last updated ${fmtUpdated(q.last_updated)}${q.refresh_months ? ", re-checked every " + q.refresh_months + " months" : ""} — check it's still current${canEdit ? html`. <a href=${"#/your-data/submit/" + encodeURIComponent(section)}>Update or re-confirm</a>` : ""}</div>`}
            </div>
            <span class=${"data-q-flag " + (q.needs_refresh ? "refresh" : q.answered ? "ok" : "todo")}>
              <${Icon} name=${q.needs_refresh ? "refresh" : q.answered ? "award" : "pencil"} size=${13} /> ${q.needs_refresh ? "Refresh" : q.answered ? "Answered" : "To do"}</span>
          </div>`)}
      </div>`}
    </div>`;
};
function fmtUpdated(s) {
  // submitted_at is sqlite UTC "YYYY-MM-DD HH:MM:SS" — normalise for Safari
  if (!s) return "a while ago";
  const dt = new Date(s.replace(" ", "T") + "Z");
  return isNaN(dt) ? "a while ago"
    : dt.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}
window.fmtUpdated = fmtUpdated;   // DomainPage (submission.js) shows the same line
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
    body=${err + " — nothing is lost."}
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
        

        ${/* ---------- §4.1 Calculations ---------- */ ""}
        <h2 class="how-section-head" id="calculations">How the numbers are calculated</h2>
        <p class="caption">Benchmark snapshot dated ${m.snapshot_date} · collection window ${m.collection_window} · methodology v${m.methodology_version || 1}</p>

        <div class="card how-card" id="market-position">
          <h3 class="section-title">Where you stand — your market position</h3>
          <p>For everything we measure, we compare your figure to the same measure across your peer group and place you in one of three positions: <b>below market</b> (under where most peers sit), <b>on market</b> (in line — we allow a sensible margin so tiny differences aren't treated as gaps), or <b>above market</b>. We do this measure by measure, roll it up for each area of reward, and bring it together into a single headline.</p>
          <p><b>Two kinds of thing we measure.</b> Some measures have a going rate — pay, pension, holiday, bonus levels — so "below, on or above market" genuinely means something. Others are choices with no right answer — which share scheme you run, how you structure a benefit, how often you review pay. There's no rate to be under or over; you're simply doing it differently. We show where your choice sits — <b>common</b> (what most peers do), an <b>alternative</b> pattern, or a <b>rare</b> choice — a difference to be aware of, not a gap to close. That's why your headline won't match the total number of things we measure: only the market-rate measures feed it.</p>
          <p><b>Practices with more than one part.</b> Some choices are a set rather than a single
          answer — which benefits you offer, which allowances you pay. For these we look at the
          <b> market core</b>: the options at least half of your peer group offers. Offer the full core and
          your set reads <b>common</b>; offer part of it, an <b>alternative</b> pattern; none of it, a
          <b> rare</b> choice. Options you offer beyond the core never count against you. Where no single
          option reaches half the market, we compare against the single most-offered option instead.${" "}
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
          ${/* replaced 2026-07-14 (Diff 4 ruling 5, verbatim copy) — the old paragraph taught
                the Governance carve-out, retired by the Diff-2 competitiveness ruling. */ ""}
          <p>Governance and transparency metrics that can be ordered by generosity or
          maturity count toward your market position like any other domain. Practice
          choices — where organisations differ by design rather than by generosity —
          never carry a market verdict: they're shown as in line or off the norm,
          with how common each choice is among your peers.</p>
          <p class="caption">Where a comparison rests on only a few organisations, we mark the verdict <b>indicative</b> — a steer, not a precise figure.</p>
        </div>

        <div class="card how-card" id="who-compared">
          <h3 class="section-title">Who you're compared with (market norms)</h3>
          ${/* R-P10 (2026-08-08): the pool IS a reference panel today — say so,
              leading with the anchor register, not apologising for it. R-P1
              first-use description verbatim. The old sentence ("built only from
              organisations that have completed a lumi submission") read as
              member-sourced and was false in the reading any member would take. */ ""}
          <p>The comparison pool is a reference panel of ${m.peer_pool.responding_orgs} UK
          organisation profiles, modelled from published UK survey data rather than lumi member submissions.
          Every panel figure is calibrated against lumi's anchor register: graded published sources with
          explicit bases, metric by metric. ${m.peer_pool.classified_orgs} profiles carry full firmographics (sector, size, region, ownership)
          and appear in filtered peer groups, while ${m.unclassified_count} sit in the "All peers" group only.
          As member organisations complete submissions, their data joins the pool and each figure states its
          composition alongside n.</p>
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
          <p><b>Your percentile.</b> Your P-number is the share of organisations in the comparison whose value sits below yours
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
          <p>Above the floor, every peer group carries a confidence label so you can weigh the sample: <b>20 or more</b>${" "}
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
          <p>This snapshot ingested ${m.reconciliation.files} member submissions (${(m.reconciliation.answer_rows || 0).toLocaleString("en-GB")} answers).${" "}
          ${m.reconciliation.matched_orgs} organisations were matched to the lumi member registry by normalised company
          name; ${m.reconciliation.file_only_orgs} submissions without a registry profile are retained as Unclassified;${" "}
          ${m.reconciliation.registry_only_orgs} registry members have not yet submitted and are excluded from every
          aggregate. Near-miss name matches are flagged for human review and never joined automatically.</p>
          <p><b>£ modelling assumptions.</b> Opportunity figures use FTE band midpoints, a UK all-sector median salary of
          £${(m.assumptions.median_salary_gbp || 0).toLocaleString("en-GB")} (editable in Settings), a cost per leaver of${" "}
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
          <p>lumi is a benchmarking co-operative: its value depends on
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
          ${me && me.user.platform_admin && html`
            <p class="caption" style=${{ marginTop: "var(--s3)" }}>lumi staff: the question-set release console lives in
            <a href="#/governance">the governance console</a>.</p>`}
        </div>

        ${/* ---------- §4.3 Legal ---------- */ ""}
        <h2 class="how-section-head" id="legal">Legal</h2>
        <div class="card how-card">
          <p class="caption">Documents still in review are marked <b>Draft</b>.</p>
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
   → treated as not-thin by design; recorded as a known gap in DECISIONS.md).
   R-P9 (RULED 2026-08-08): this number — and the ConfidenceChip it feeds — reads
   TOTAL n DELIBERATELY. A 212-org calibrated panel genuinely is a more stable
   figure than a 6-org one; the chip is not lying about what it measures, and it
   is always paired with composition (R-P2). Do NOT re-point this at real n
   later thinking you found a bug. */
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
  if (cut.dim === "twin") {
    // 2026-08-09 persona review: the methodology promises every peer group a
    // confidence label — the twin pool size now rides /api/cuts (twin_n)
    return cuts && typeof cuts.twin_n === "number" ? cuts.twin_n : null;
  }
  return null;
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
  const W = 930, H = 130, PAD = 40;   // same canvas width as the hero chart above it
  const xStep = (W - PAD * 2) / Math.max(1, pts.length - 1);
  let xi = 0;
  const segs = t.segments.map(seg => seg.map(p => {
    const v = p.p50 != null ? p.p50 : p.modal_pct;
    const pt = { x: PAD + xi * xStep, y: H - 28 - ((v - lo) / span) * (H - 56), v, p };
    xi += 1;
    return pt;
  }));
  const lastPt = segs.length ? segs[segs.length - 1][segs[segs.length - 1].length - 1] : null;
  const trendAria = "Market median by period: " + pts.map(p => p.period + " " + fmtValue(p.p50 != null ? p.p50 : p.modal_pct, null)).join(", ")
    + "." + (t.breaks.length ? " " + t.breaks.length + " comparability reset" + (t.breaks.length === 1 ? "" : "s") + "." : "");
  return html`
    <div class="card" style=${{ padding: "var(--s5)", marginTop: "var(--s4)" }}>
      <h2 class="section-title">Across data periods</h2>
      ${t.breaks.length > 0 && html`
        <div class="caption" style=${{ marginBottom: "var(--s2)", display: "flex", gap: "var(--s2)", alignItems: "flex-start" }}>
          <${Icon} name="info" size=${13} style=${{ flex: "none", marginTop: "2px" }} />
          <span>This question changed materially (${t.breaks.map(b => b.release_id).join(", ")}) —
          values either side of the break aren't comparable, so the trend resets rather than joining up.</span>
        </div>`}
      <svg viewBox=${"0 0 " + W + " " + H} style=${{ width: "100%" }} role="img" aria-label=${trendAria}>
        ${segs.map((seg, si) => html`
          <g key=${si}>
            ${seg.length > 1 && html`<polyline fill="none" stroke="var(--blue)" stroke-width="2"
              points=${seg.map(d => d.x + "," + d.y).join(" ")} />`}
            ${seg.map((d, i) => html`
              <g key=${i}>
                <circle cx=${d.x} cy=${d.y} r=${lastPt && d === lastPt ? 5.5 : 4} fill="var(--blue)" />
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
            aria-label="New backlog item" placeholder="Add a candidate change for a future release…" value=${title}
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