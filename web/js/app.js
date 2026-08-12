/* lumi root app: shell, navigation, global peer filter, search, routing. */

/* Brand lockups, inlined verbatim from lumi_brand_kit (wordmark is outlined —
   no font dependency; injected via innerHTML so the designer SVG isn't mangled
   by React attribute casing). Full horizontal lockup in the rail; symbol-only
   mark when the rail is collapsed. */
const LUMI_LOGO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="390" height="178" viewBox="0 0 390 178" role="img" aria-label="lumi"><title>lumi</title><g transform="translate(-414.25 -156.25)"><path d="M 470.00 212.00 L 470.00 280.00 L 538.00 280.00" fill="none" stroke="#2048B0" stroke-width="17.0" stroke-linecap="round" stroke-linejoin="round"/><circle cx="490.00" cy="263.00" r="6.00" fill="#2048B0" opacity="0.35"/><circle cx="504.00" cy="254.00" r="6.00" fill="#2048B0" opacity="0.35"/><circle cx="520.00" cy="238.00" r="14.00" fill="#F08C6E"/></g><g transform="translate(50.162499999999994 -578.25)"><g transform="translate(120 700) scale(0.08955938697318008 -0.08955938697318008)"><path transform="translate(0 0)" d="M68 0V720H168V0Z" fill="#243642"/><path transform="translate(237 0)" d="M253 -12Q194 -12 150.5 12.0Q107 36 83.5 84.0Q60 132 60 205V504H160V216Q160 145 191.0 109.0Q222 73 280 73Q319 73 350.5 92.0Q382 111 400.0 147.0Q418 183 418 235V504H518V0H429L422 86Q399 40 355.0 14.0Q311 -12 253 -12Z" fill="#243642"/><path transform="translate(824 0)" d="M68 0V504H158L165 433Q189 472 229.0 494.0Q269 516 319 516Q357 516 388.0 505.5Q419 495 443.0 474.0Q467 453 482 422Q509 466 554.5 491.0Q600 516 651 516Q712 516 756.0 491.5Q800 467 823.0 418.5Q846 370 846 298V0H747V288Q747 358 718.5 394.0Q690 430 635 430Q598 430 569.0 411.0Q540 392 523.5 356.0Q507 320 507 268V0H407V288Q407 358 378.5 394.0Q350 430 295 430Q260 430 231.0 411.0Q202 392 185.0 356.0Q168 320 168 268V0Z" fill="#243642"/><path transform="translate(1731 0)" d="M68 0V504H168V0Z" fill="#243642"/></g><circle cx="285.64" cy="641.61" r="7.52" fill="#F08C6E"/></g></svg>`;
const LUMI_MARK_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120" role="img" aria-label="lumi"><title>lumi</title><path d="M 30.00 22.00 L 30.00 90.00 L 98.00 90.00" fill="none" stroke="#2048B0" stroke-width="17.0" stroke-linecap="round" stroke-linejoin="round"/><circle cx="50.00" cy="73.00" r="6.00" fill="#2048B0" opacity="0.35"/><circle cx="64.00" cy="64.00" r="6.00" fill="#2048B0" opacity="0.35"/><circle cx="80.00" cy="48.00" r="14.00" fill="#F08C6E"/></svg>`;
// Reversed lockup (white wordmark + white L-axis + coral dot) — for the navy brand bar only.
// Exact bytes of lumi_horizontal_reversed.svg (brand kit) — wordmark is outlined, not re-typeset.
const LUMI_LOGO_REVERSED_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="390" height="178" viewBox="0 0 390 178" role="img" aria-label="lumi"><title>lumi</title><g transform="translate(-414.25 -156.25)"><path d="M 470.00 212.00 L 470.00 280.00 L 538.00 280.00" fill="none" stroke="#FFFFFF" stroke-width="17.0" stroke-linecap="round" stroke-linejoin="round"/><circle cx="490.00" cy="263.00" r="6.00" fill="rgba(255,255,255,0.45)"/><circle cx="504.00" cy="254.00" r="6.00" fill="rgba(255,255,255,0.45)"/><circle cx="520.00" cy="238.00" r="14.00" fill="#F08C6E"/></g><g transform="translate(50.162499999999994 -578.25)"><g transform="translate(120 700) scale(0.08955938697318008 -0.08955938697318008)"><path transform="translate(0 0)" d="M68 0V720H168V0Z" fill="#FFFFFF"/><path transform="translate(237 0)" d="M253 -12Q194 -12 150.5 12.0Q107 36 83.5 84.0Q60 132 60 205V504H160V216Q160 145 191.0 109.0Q222 73 280 73Q319 73 350.5 92.0Q382 111 400.0 147.0Q418 183 418 235V504H518V0H429L422 86Q399 40 355.0 14.0Q311 -12 253 -12Z" fill="#FFFFFF"/><path transform="translate(824 0)" d="M68 0V504H158L165 433Q189 472 229.0 494.0Q269 516 319 516Q357 516 388.0 505.5Q419 495 443.0 474.0Q467 453 482 422Q509 466 554.5 491.0Q600 516 651 516Q712 516 756.0 491.5Q800 467 823.0 418.5Q846 370 846 298V0H747V288Q747 358 718.5 394.0Q690 430 635 430Q598 430 569.0 411.0Q540 392 523.5 356.0Q507 320 507 268V0H407V288Q407 358 378.5 394.0Q350 430 295 430Q260 430 231.0 411.0Q202 392 185.0 356.0Q168 320 168 268V0Z" fill="#FFFFFF"/><path transform="translate(1731 0)" d="M68 0V504H168V0Z" fill="#FFFFFF"/></g><circle cx="285.64" cy="641.61" r="7.52" fill="#F08C6E"/></g></svg>`;
window.LUMI_LOGO_SVG = LUMI_LOGO_SVG;   // the board pack cover renders the real mark (commercial.js, 2026-07-02)
/* global html, useState, useEffect, useMemo, useRef, api, useRoute, nav, Chip, Spinner, AuthScreen,
   OverviewPage, SuperpowerPage, CategoryPage, DashboardsPage, YourDataPage, DomainDataView, HowLumiWorksPage, GapRegisterPage, SignalsPage, StrategyPage, RailItem,
   BoardPackView, AnalystPane, PeerTwinPanel, SharesPage, TeamPage, SettingsPage,
   SubmissionPage, BenchmarkCard, SUPERPOWERS, SP_ICONS, EmptyState, cutLabelOf, cutKeyOf,
   AdminConsolePage, NotFoundPage, setPoolTotal */

/* Deep linking: the peer cut lives in the hash query (?cut=industry::X) so a
   filtered view is shareable and back-button-safe. Section is already in the
   route; this completes the main views. */
function cutFromURL() {
  const m = (window.location.hash || "").match(/[?&]cut=([^&]+)/);
  if (!m) return { dim: "all", value: null };
  const raw = decodeURIComponent(m[1]);
  if (raw === "twin") return { dim: "twin", value: null };
  const [dim, value] = raw.split("::");
  return value ? { dim, value } : { dim: "all", value: null };
}
function cutToURL(cut) {
  const h = window.location.hash || "#/overview";
  const base = h.replace(/[?&]cut=[^&]*/, "").replace(/[?&]$/, "");
  if (cut.dim === "all") { if (base !== h) history.replaceState(null, "", base); return; }
  const enc = encodeURIComponent(cut.dim === "twin" ? "twin" : cut.dim + "::" + cut.value);
  const next = base + (base.includes("?") ? "&" : "?") + "cut=" + enc;
  if (next !== h) history.replaceState(null, "", next);
}
// The benchmark-family routes are the only surfaces whose URL carries the peer
// cut (mirrors the benchRoute test in App) — everything else stays clean.
const CUT_ROUTES = ["/overview", "/benchmark", "/superpower", "/myview", "/dashboards", "/metric", "/priorities", "/signals", "/category/"];
const isCutRoute = r => r === "" || r === "/" || CUT_ROUTES.some(p => r.startsWith(p));

function App() {
  const route = useRoute();
  const [me, setMe] = useState(undefined);          // undefined=loading, null=unauth
  // Per-route document titles + focus handoff: SPAs are silent on navigation for
  // screen-reader users unless the title changes and focus lands in the content.
  const prevRouteRef = useRef(null);
  useEffect(() => {
    const TITLES = [["/overview", "Overview"], ["/dashboards", "My dashboards"], ["/signals", "Signals"],
      ["/priorities", "Priorities"], ["/pulse", "Pulse"], ["/run-a-pulse", "Run a pulse"],
      ["/benchmark", "Benchmark"], ["/metric/", "Metric"], ["/your-data", "Your data"],
      ["/boardpack", "Board packs"],
      ["/strategy", "Reward strategy"], ["/team", "Team"], ["/settings", "Settings"],
      ["/shares", "Manage shares"],
      ["/profile", "Company profile"], ["/how-lumi-works", "How lumi works"], ["/admin", "Console"],
      ["/governance", "Governance"]];
    // named routes first (category/superpower carry their name in the path);
    // the signed-out shell is always "Sign in", never a page it isn't showing
    let m;
    if (me === null) document.title = "Sign in · lumi";
    else if ((m = route.match(/^\/(?:category|superpower)\/([^?]+)/)))
      document.title = decodeURIComponent(m[1]) + " · lumi";
    else if (route.startsWith("/boardpack/")) document.title = "Board pack · lumi";
    else {
      const hit = TITLES.find(([p]) => route.startsWith(p));
      // /admin renders NotFound for non-staff — the tab title must not claim
      // a Console page that is not being shown (Batch 0, 2026-08-08)
      const t = (hit && hit[0] === "/admin" && !(me && me.user && me.user.platform_admin))
        ? "Page not found" : hit && hit[1];
      document.title = t ? t + " · lumi" : "lumi · UK reward benchmarking";
    }
    if (prevRouteRef.current !== null && prevRouteRef.current !== route) {
      const el = document.getElementById("main-content");
      if (el) el.focus({ preventScroll: true });
    }
    prevRouteRef.current = route;
  }, [route, me]);
  const [cut, setCut] = useState(cutFromURL());
  const [cuts, setCuts] = useState(null);
  // prefs: null = not loaded yet, {} = loaded-and-empty. Pages read saved view
  // prefs (strategy off, practice view) in one-shot useState initializers, so
  // the distinction matters — see the prefs gate below (ship review, Pack 1.3).
  const [prefs, setPrefs] = useState(null);
  const [layoutIds, setLayoutIds] = useState(new Set());
  const [analystOpen, setAnalystOpen] = useState(false);
  const [metricReq, setMetricReq] = useState(null);   // {prefill, source} | null
  const [twinOpen, setTwinOpen] = useState(false);
  const [groupsOpen, setGroupsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [qIndex, setQIndex] = useState(null);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);   // mobile nav drawer (<900px)
  const [activeHit, setActiveHit] = useState(-1);
  const [searchFocused, setSearchFocused] = useState(false);  // combobox: active option index (-1 = none)
  const searchHitsRef = useRef([]);                // current activatable search options (for Enter)
  const searchRef = useRef(null);
  const searchWrapRef = useRef(null);              // the .topbar-search container (popup + input)
  // Reset the combobox active option whenever the query changes.
  useEffect(() => { setActiveHit(-1); }, [search]);
  // Ship review 2026-07-09 (Pack 1.5): the results popup used to ride over every
  // subsequent page — it only closed on Escape or a hit click. Close it on any
  // route change and on mousedown outside the search container (same pattern as
  // the BenchmarkNav flyout below).
  useEffect(() => { setSearch(""); setActiveHit(-1); }, [route]);
  useEffect(() => {
    if (!search) return;
    const onDoc = (e) => {
      const w = searchWrapRef.current;
      if (w && !w.contains(e.target)) { setSearch(""); setActiveHit(-1); }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [!!search]);
  // Keep the keyboard-active option scrolled into view in the results listbox.
  useEffect(() => {
    if (activeHit < 0) return;
    const el = document.getElementById("search-hit-" + activeHit);
    if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
  }, [activeHit]);
  // Global "jump to search" — ⌘K / Ctrl-K anywhere, or "/" when not already typing
  // (the command-palette affordance modern tools train users to reach for).
  useEffect(() => {
    const onKey = (e) => {
      const tag = (e.target.tagName || "").toLowerCase();
      const typing = tag === "input" || tag === "textarea" || e.target.isContentEditable;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); searchRef.current && searchRef.current.focus(); }
      else if (e.key === "/" && !typing) { e.preventDefault(); searchRef.current && searchRef.current.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  // Mobile nav drawer: the open state lives here; the body class is the shared
  // contract app.css styles against. Escape closes the drawer.
  useEffect(() => {
    document.body.classList.toggle("nav-open", navOpen);
    if (!navOpen) return;
    const onEsc = (e) => { if (e.key === "Escape") setNavOpen(false); };
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [navOpen]);
  // Close the drawer on any route change (e.g. a sidebar nav-link click).
  useEffect(() => { setNavOpen(false); }, [route]);
  const [unsub, setUnsub] = useState(false);        // org has saved-but-unsubmitted drafts
  const [barHidden, setBarHidden] = useState(false); // user dismissed the reminder bar this view
  const [leaveTo, setLeaveTo] = useState(null);      // pending destination held by the leave-guard
  const prefsTimer = useRef(null);

  const refreshMe = () => api("/api/me").then(setMe).catch(() => setMe(null));
  useEffect(() => { setPoolTotal(me && me.peer_pool ? me.peer_pool.responding_orgs : null);
    window.__orgName = (me && me.org && me.org.name) || ""; }, [me]);
  useEffect(() => {
    const pre = window._mePrefetch;
    window._mePrefetch = null;                    // one shot — refreshes go through api()
    if (pre) pre.then(d => { if (d) setMe(d); else refreshMe(); });
    else refreshMe();
  }, []);
  useEffect(() => {
    const f = () => setMe(null);
    window.addEventListener("lumi:unauth", f);
    return () => window.removeEventListener("lumi:unauth", f);
  }, []);
  useEffect(() => {
    if (!me) return;
    api("/api/cuts").then(setCuts).catch(() => setCuts(c => c || { industries: {}, fte_bands: {}, groups: [] }));
    // a failed prefs fetch resolves to {} so the prefs gate below can never hang
    api("/api/prefs").then(d => setPrefs(d.prefs || {})).catch(() => setPrefs({}));
    api("/api/dashboards").then(d => setLayoutIds(new Set(((d.active && d.active.layout) || []).map(s => s.question_id)))).catch(() => {});
    api("/api/questions").then(setQIndex).catch(() => {});
  }, [me && me.org && me.org.name]);
  // Landing peer group = the COMPANY DEFAULT (org.default_cut → me.org.signal_peer_cut), David
  // 2026-08-11: the admin-set company default drives signals AND is the app-wide default, so every
  // member opens on the SAME group (the per-user landing pref was dropped). An explicit cut in the
  // URL still wins (shared links / back button); applied once, and a later explicit "all" isn't
  // overridden (initialHadCut latches).
  const initialHadCut = useRef(/[?&]cut=/.test(window.location.hash || ""));
  useEffect(() => {
    const def = me && me.org && me.org.signal_peer_cut;
    if (def && !initialHadCut.current && def !== "all") {
      initialHadCut.current = true;
      setGlobalCut(def);
    }
  }, [me && me.org && me.org.signal_peer_cut]);
  // Ship review 2026-07-09 B3 (+ the hashchange companion): nav() writes a bare
  // hash, so keying this effect on the cut alone meant every route change ERASED
  // ?cut= — a refresh then silently swapped Directional·15 for the 220-org pool,
  // breaking the deep-link promise above. Reconcile both ways on navigation:
  // a hash that carries its own cut (shared link, back button, hand-edited URL)
  // wins and is adopted into state; a bare hash on a benchmark surface gets the
  // active cut re-serialised so refresh/copy always reproduce the view. A cut
  // change without a route change (the selector) writes through as before.
  const cutRouteRef = useRef(route);
  useEffect(() => {
    const routeChanged = cutRouteRef.current !== route;
    cutRouteRef.current = route;
    if (routeChanged) {
      if (/[?&]cut=/.test(window.location.hash || "")) {
        const urlCut = cutFromURL();
        if (urlCut.dim !== cut.dim || (urlCut.value || null) !== (cut.value || null)) { setCut(urlCut); return; }
      } else if (!isCutRoute(route)) return;   // never pollute non-benchmark URLs
    }
    cutToURL(cut);
  }, [route, cutKeyOf(cut)]);
  // Unsubmitted-changes reminder: seed the flag from the server on load (so a
  // returning member with leftover drafts is reminded), then follow live edits.
  useEffect(() => {
    if (me && me.contribution) { window._unsubmitted = (me.contribution.pending_changes || 0) > 0; setUnsub(window._unsubmitted); setBarHidden(false); }
  }, [me]);
  useEffect(() => {
    const f = () => { setUnsub(!!window._unsubmitted); setBarHidden(false); };
    window.addEventListener("lumi:unsubmitted", f);
    return () => window.removeEventListener("lumi:unsubmitted", f);
  }, []);
  // the card "Add to dashboard" picker can change the active dashboard from any
  // surface — keep the global pinned set (star-fill) in step with the server.
  useEffect(() => {
    const f = () => api("/api/dashboards").then(d => setLayoutIds(new Set(((d.active && d.active.layout) || []).map(s => s.question_id)))).catch(() => {});
    window.addEventListener("lumi:pins-changed", f);
    return () => window.removeEventListener("lumi:pins-changed", f);
  }, []);
  // Leave-guard: clicking out of the Your-data flow with unsubmitted changes
  // opens a confirm dialog instead of navigating straight away. Re-registered
  // on each route change so it knows where the user currently is.
  useEffect(() => {
    window._leaveGuard = (path) => {
      if (!window._unsubmitted) return false;
      const onData = route.startsWith("/your-data");
      const staying = path.startsWith("/your-data") || path.startsWith("/profile");
      if (onData && !staying) { setLeaveTo(path); return true; }
      return false;
    };
    return () => { window._leaveGuard = null; };
  }, [route]);
  useEffect(() => {
    const y = consumeReturnScroll(window.location.hash);
    if (y != null) {
      // the page below loads async — keep trying briefly until the height exists
      let tries = 0;
      const t = setInterval(() => {
        window.scrollTo(0, y);
        if (Math.abs(window.scrollY - y) < 4 || ++tries > 20) clearInterval(t);
      }, 150);
      return () => clearInterval(t);
    }
    // forward navigation starts at the top — without this, arriving from a
    // long page lands the new page mid-scroll (review #28, 2026-08-08)
    window.scrollTo(0, 0);
  }, [route]);

  window.openMetricRequest = (prefill, source) => setMetricReq({ prefill: prefill || "", source: source || "button" });
  if (me === undefined) return html`<div class="auth-wrap"><${Spinner} /></div>`;
  const scope = me && me.scope ? me.scope : { superpowers: window.SUPERPOWERS || [], focused: false };
  window.SCOPE = scope;
  // the engine's market band (LUMI_MARKET_BAND) — cardPosition colours cards on
  // the SAME line as the tiles + signals, so they can never drift.
  if (me && me.config && me.config.market_band) window.MARKET_BAND = me.config.market_band;
  const activeSupers = scope.superpowers;
  if (me === null) {
    // remember where the user was headed — session expiry or a cold deep link
    // must return them there, not dump them on Overview
    const h = (window.location.hash || "").replace(/^#/, "");
    if (h && !/^\/(invite|reset|register)\b/.test(h) && h !== "/" && h !== "/overview")
      window.__resumeRoute = h;
    return html`<${AuthScreen} route=${route} onAuthed=${() => {
      window.location.hash = window.__resumeRoute || "/overview";
      window.__resumeRoute = null; refreshMe();
    }} />`;
  }
  // Ship review 2026-07-09 (Pack 1.3): pages read saved view prefs (strategy
  // off / practice view / rail state) in one-shot useState initializers, so a
  // cold load or deep link used to mount with EMPTY prefs, render the default
  // view, then re-run the whole engine pass when the real prefs landed. Hold
  // the shell one beat until /api/prefs resolves (null = still loading; a
  // fetch failure resolves to {} above, so this can never hang).
  if (prefs === null) return html`<div class="auth-wrap"><${Spinner} /></div>`;

  // collapsible rail (nav pkg Item 3): persisted per user alongside the
  // Benchmark expand-state. Manual choice is authoritative — no resize override.
  const _railPrefs = (prefs && prefs._nav) || {};
  const railCollapsed = !!_railPrefs.sidebar_collapsed;
  const toggleRail = () => onPref("_nav", { ..._railPrefs, sidebar_collapsed: !railCollapsed });

  const onPref = (qid, p) => {
    const next = { ...prefs, [qid]: p };
    setPrefs(next);
    clearTimeout(prefsTimer.current);
    prefsTimer.current = setTimeout(() => api("/api/prefs", { method: "PUT", body: { prefs: next } })
      .catch(() => toast("Couldn't save your view settings — they may reset next visit.", "error")), 800);
  };
  // the global pin-star toggles a card on the user's ACTIVE dashboard
  const onPin = async (qid) => {
    try {
      const was = layoutIds.has(qid);
      const r = await api("/api/dashboards/pin", { method: "POST", body: { question_id: qid } });
      setLayoutIds(new Set(r.pinned_ids || []));
      toast(was ? "Removed from your dashboard" : "Added to your dashboard");
    } catch (e) { toast("Couldn't update your dashboard — try again", "error"); }
  };
  // A hoisted function declaration (NOT a const arrow): an effect above (the landing-cut effect)
  // closes over setGlobalCut, and on a mid-session auth drop the render early-returns <AuthScreen>
  // before a const on this line would initialise — a temporal-dead-zone crash ("Cannot access
  // 'setGlobalCut' before initialization" → the whole app white-screens instead of showing sign-in).
  // Hoisting makes it defined from the top of every render, so that path can never TDZ. (2026-08-11)
  function setGlobalCut(key) {
    if (key === "all") setCut({ dim: "all", value: null });
    else if (key === "twin") setCut({ dim: "twin", value: null });
    else if (key === "manage-groups") setGroupsOpen(true);
    else { const [dim, value] = key.split("::"); setCut({ dim, value }); }
  }
  const refreshCuts = () => api("/api/cuts").then(setCuts);

  const pageProps = { me, refreshMe, cut, cuts, prefs, onPref, onPin, pinnedIds: layoutIds,
    setPinned: (ids) => setLayoutIds(new Set(ids)),
    onCut: setGlobalCut, onTwinInfo: () => setTwinOpen(true) };
  const contrib = me.contribution || null;

  let page = null, m;
  if (route.startsWith("/superpower/")) {
    // legacy URLs (pre-2026.1 terminology) redirect to the category route
    const [, qs] = route.slice("/superpower/".length).split("?");
    const p = new URLSearchParams(qs || "");
    nav("/benchmark" + (p.get("sub") ? "?cat=" + encodeURIComponent(p.get("sub")) : ""));
    page = null;
  } else if (route.startsWith("/benchmark")) {
    const qs = route.includes("?") ? route.slice(route.indexOf("?") + 1) : "";
    const params = new URLSearchParams(qs);
    const focusQ = params.get("focus");
    const subF = params.get("cat");
    page = html`<${SuperpowerPage} ...${pageProps} sp="Reward" focusQ=${focusQ} subF=${subF} />`;
  } else if ((m = route.match(/^\/category\/([^?]+)/))) {
    page = html`<${CategoryPage} ...${pageProps} name=${decodeURIComponent(m[1])} />`;
  } else if ((m = route.match(/^\/metric\/([^?]+)/))) {
    // ship review 2026-07-09 B2: match must stop at the query string — (.+$)
    // swallowed "?cut=…" into the qid, so every link the Share button mints
    // fetched a mangled id and hung on the cardStale skeleton forever.
    // key by qid: a metric→metric navigation must remount (fresh card/chart/commentary
    // state) — without it the old metric's figures can paint under the new URL.
    page = html`<${MetricPage} key=${m[1]} ...${pageProps} qid=${m[1]} />`;
  } else if ((m = route.match(/^\/boardpack\/(.+)$/))) {
    page = html`<${BoardPackView} packId=${m[1]} me=${me} />`;
  } else if (route.startsWith("/boardpack")) {   // bare route = the packs home (used to fall through to Overview)
    page = html`<${BoardPacksPage} me=${me} />`;
  } else if (route.startsWith("/myview")) { nav("/dashboards"); page = null; }   // legacy → renamed surface
  else if (route.startsWith("/dashboards")) page = html`<${DashboardsPage} ...${pageProps} />`;
  else if (route.startsWith("/your-data/submit")) {
    // Legacy submit tree → the unified Your-data routes. The bare on-ramp keeps
    // running the firmographics/terms gates (then bounces to /your-data); the
    // deeper URLs redirect to their unified equivalents so old links still work.
    const seg = route.split("/")[3];
    const sub = seg ? seg.split("?")[0] : "";
    if (!sub) page = html`<${SubmissionPage} me=${me} refreshMe=${refreshMe} />`;
    else if (sub === "review") { nav("/your-data/review"); page = null; }
    else { nav("/your-data/" + sub); page = null; }
  }
  else if (route.startsWith("/your-data/review")) {
    page = html`<${SubmissionPage} me=${me} refreshMe=${refreshMe} section="review" />`;
  }
  else if ((m = route.match(/^\/your-data\/(.+)$/))) {
    // One domain page. Editors get the unified review+edit surface (gate-wrapped
    // DomainPage); viewers get the read-only DomainDataView.
    const seg = decodeURIComponent(m[1].split("?")[0]);
    const canEdit = me.user.role === "admin" || me.user.role === "contributor";
    page = canEdit
      ? html`<${SubmissionPage} me=${me} refreshMe=${refreshMe} section=${seg} />`
      : html`<${DomainDataView} me=${me} section=${seg} />`;
  }
  else if (route.startsWith("/your-data")) page = html`<${YourDataPage} me=${me} />`;
  else if (route.startsWith("/how-lumi-works")) {
    const anchor = route.slice("/how-lumi-works".length).replace(/^\//, "").split("?")[0] || null;
    page = html`<${HowLumiWorksPage} me=${me} anchor=${anchor} />`;
  }
  else if (route.startsWith("/methodology")) { nav("/how-lumi-works/calculations"); page = null; }
  else if (route.startsWith("/signals")) page = html`<${SignalsPage} ...${pageProps} />`;
  else if (route.startsWith("/priorities")) page = html`<${GapRegisterPage} ...${pageProps} />`;
  else if (route.startsWith("/team")) page = me.user.role === "admin"
    ? html`<${TeamPage} me=${me} />`
    : html`<${EmptyState} icon="lock" title="Team is an Admin area" body="Your organisation's Admin manages members and roles." />`;
  // Sharing moved off Settings to its own admin route (2026-08-11 design review): the share-link
  // console is a full CRUD table, too heavy to sit inline among the calm settings cards. Settings
  // keeps a delegate entry card ("Manage share links →"), mirroring Company profile → /profile.
  else if (route.startsWith("/shares")) page = me.user.role === "admin"
    ? html`<${SharesPage} />`
    : html`<${EmptyState} icon="lock" title="Sharing is an Admin area" body="Your organisation's Admin creates and manages read-only share links." />`;
  // Settings opened to ALL roles (2026-07-13, Defaults follow-up): it hosts settings that are
  // personal to the signed-in user — notifications, AI consent, and the landing peer group the
  // removed ★ used to set from the capsule. Org-level cards gate themselves per role inside
  // SettingsPage (assumptions read-only, sharing hidden, signal-email default read-only).
  else if (route.startsWith("/settings")) page =
    html`<${SettingsPage} me=${me} refreshMe=${refreshMe} cuts=${cuts} prefs=${prefs} onPref=${onPref} />`;
  else if (route.startsWith("/governance")) page = me.user.platform_admin
    ? html`<${GovernancePage} me=${me} />`
    : html`<${NotFoundPage} route=${route} />`;   // staff-only, invisible to members (craft review 2026-08-09)
  else if ((m = route.match(/^\/run-a-pulse\/([^?]+)/))) page = me.user.role === "admin"
    ? html`<${PulseBuilderPage} me=${me} pid=${m[1]} />`
    : html`<${EmptyState} icon="lock" title="Admin only" body="Designing and launching a pulse is an Admin action."
        action=${html`<button class="btn small primary" onClick=${() => nav("/pulse")}>See open pulses</button>`} />`;
  else if (route.startsWith("/run-a-pulse")) page = me.user.role === "admin"
    ? html`<${PulsesPage} me=${me} tab="run" />`   // Pulse page, "Run a pulse" tab (merged 2026-08-11)
    : html`<${EmptyState} icon="lock" title="Admin only" body="Designing and launching a pulse is an Admin action."
        action=${html`<button class="btn small primary" onClick=${() => nav("/pulse")}>See open pulses</button>`} />`;
  else if ((m = route.match(/^\/pulse\/(.+)$/))) page = html`<${PulseDetailPage} me=${me} pid=${m[1]} />`;
  else if (route.startsWith("/pulse")) page = html`<${PulsesPage} me=${me} tab="explore" />`;
  else if (route.startsWith("/register") || (route.startsWith("/reset") && !route.startsWith("/reset/"))) {
    // a bare register/reset deep link while signed in lands home, never a 404 (craft
    // review) — /invite/ and /reset/<token> keep their real handlers below
    page = html`<${PageLoading} />`; setTimeout(() => nav("/overview"), 0);
  }
  else if (route.startsWith("/profile")) page = html`<${ProfilePage} me=${me} refreshMe=${refreshMe} />`;
  else if (route.startsWith("/strategy")) page = html`<${StrategyPage} me=${me} />`;
  else if (route.startsWith("/admin")) page = me.user.platform_admin
    ? html`<${AdminConsolePage} me=${me} route=${route} />`
    : html`<${NotFoundPage} route=${route} />`;   // invisible to non-staff
  else if (route.startsWith("/invite/"))
    // An invite link while SIGNED IN used to fall silently into Overview — the
    // current session's org kept winning and the operator never learned why
    // ("keeps jumping to tester", 2026-08-04). Now an explicit interstitial.
    page = html`<${InviteWhileAuthed} me=${me} token=${route.split("/")[2]} />`;
  else if (route === "" || route === "/" || route.startsWith("/overview") || route.startsWith("/reset/"))
    page = html`<${OverviewPage} ...${pageProps} />`;
  else page = html`<${NotFoundPage} route=${route} />`;

  const benchRoute = route.startsWith("/overview") || route.startsWith("/superpower") || route.startsWith("/benchmark") ||
    route.startsWith("/myview") || route.startsWith("/dashboards") || route.startsWith("/metric") || route.startsWith("/priorities") || route.startsWith("/category/") || route.startsWith("/signals") || route === "" || route === "/";
  // the Overview renders the peer-cut inline in its title row (saves a row of
  // vertical space); every other bench surface keeps the standalone strip.
  const isOverview = route.startsWith("/overview") || route === "" || route === "/";
  // category pages joined the inline club (2026-07-13, "the nav takes way too much space"):
  // CategoryPage renders PeerSetBar inside its one-row masthead, same as the Overview.
  const isCategory = route.startsWith("/category/");
  // My dashboards owns its peer sample PER DASHBOARD (2026-08-11, David) — it renders its own
  // PeerSetBar in the dashboard toolbar, so the app-wide selector is suppressed on this page.
  const isDashboards = route.startsWith("/dashboards") || route.startsWith("/myview");
  // Signals are anchored to the org DEFAULT peer group (David 2026-08-11), NOT the app-wide
  // selector — so the selector is hidden on /signals; the page names its own default group.
  // (/priorities is the full gap register, a benchmark table — it KEEPS the app-wide selector.)
  const isSignals = route.startsWith("/signals");
  // the metric detail page renders its OWN "Comparing against" bar under the Back button
  // (David 2026-08-12) — suppress the app-wide selector here so there aren't two peer pills.
  const isMetric = route.startsWith("/metric");

  // Combobox: the search popup is open at >1 char with an index; keep the
  // activatable-option list in a ref so the input's Enter handler can act on it.
  const searchPopOpen = !!(search.length > 1 && qIndex);
  searchHitsRef.current = searchPopOpen ? searchOptions(qIndex, search, me.user.role) : [];

  return html`
    <div class="shell">
      ${/* ship review 2026-07-09 B9: href alone set the hash, and the router
            resolved "main-content" → the 404 page for every keyboard user
            (WCAG 2.4.1). Focus the target directly (it carries tabindex="-1")
            and leave the URL untouched. href stays for skip-link semantics. */ ""}
      <a class="skip-link" href="#main-content" onClick=${e => {
        e.preventDefault();
        const el = document.getElementById("main-content");
        if (el) el.focus();
      }}>Skip to content</a>
      <${IdleGuard} onSignOut=${async () => { await api("/api/auth/logout", { method: "POST" }).catch(() => {}); setMe(null); }} />
      <header class="topbar brandbar no-print">
        <button class="nav-hamburger" aria-label="Open menu" aria-expanded=${navOpen}
          onClick=${() => setNavOpen(o => !o)}><${Icon} name="menu" size=${20} /></button>
        <a class="brandbar-logo" href="#/overview" aria-label="lumi benchmark home"
          dangerouslySetInnerHTML=${{ __html: LUMI_LOGO_REVERSED_SVG }}></a>
        <div class="topbar-search" ref=${searchWrapRef}>
          <span class="topbar-search-icon"><${Icon} name="search" size=${15} /></span>
          <input ref=${searchRef} class="ctl" placeholder="Search metrics, pages & help… (⌘K)"
            aria-label="Search reward metrics" value=${search}
            role="combobox" aria-controls="searchpop-list" aria-autocomplete="list"
            aria-expanded=${searchPopOpen} aria-activedescendant=${activeHit >= 0 ? "search-hit-" + activeHit : ""}
            onInput=${e => setSearch(e.target.value)}
            onKeyDown=${e => {
              if (e.key === "Escape") { setSearch(""); setActiveHit(-1); e.target.blur(); return; }
              if (!searchPopOpen) return;
              const opts = searchHitsRef.current;
              if (e.key === "ArrowDown") { e.preventDefault(); if (opts.length) setActiveHit(i => (i + 1) % opts.length); }
              else if (e.key === "ArrowUp") { e.preventDefault(); if (opts.length) setActiveHit(i => (i <= 0 ? opts.length - 1 : i - 1)); }
              else if (e.key === "Enter") {
                // no highlight yet -> the first result is the obvious intent
                const q = opts[activeHit] || opts[0];
                if (q) { e.preventDefault(); setSearch(""); setActiveHit(-1); q.kind === "nav" ? nav(q.route) : openMetric(q.id); }
              }
            }}
            onFocus=${() => setSearchFocused(true)}
            onBlur=${e => { const to = e.relatedTarget; if (to && to.closest && to.closest(".searchpop")) return; setTimeout(() => setSearchFocused(false), 160); }} />
          ${!searchPopOpen && searchFocused && !search && qIndex ? html`<${SearchZeroState} qIndex=${qIndex}
            onGo=${(qid) => { setSearch(""); setSearchFocused(false); openMetric(qid); }} />` : null}
          ${searchPopOpen && html`<${SearchPop} qIndex=${qIndex} search=${search} role=${me.user.role}
            activeHit=${activeHit} onActiveHit=${setActiveHit}
            onGo=${(q) => { setSearch(""); setActiveHit(-1); q.kind === "nav" ? nav(q.route) : openMetric(q.id); }}
            onRequest=${() => { const term = search; setSearch(""); setActiveHit(-1); setMetricReq({ prefill: term, source: "search" }); }} />`}
        </div>
        <div class="topbar-right">
          <${DataProgressChip} contrib=${contrib} role=${me.user.role} platformAdmin=${me.user.platform_admin} />
          <button class="btn feature suggest-pill" aria-label="Suggest a new metric" onClick=${() => setSuggestOpen(true)}>Suggest a metric</button>
          ${me.features && me.features.analyst && html`
          <button class="btn feature" title="Find a metric, learn a term, get help, or ask how you compare" onClick=${() => setAnalystOpen(true)}><${Icon} name="sparkle" size=${14} /> Ask lumi</button>`}
          <span class="topbar-sep" aria-hidden="true"></span>
          <${NotificationBell} me=${me} />
          <${ProfileMenu} me=${me} onSignOut=${async () => { await api("/api/auth/logout", { method: "POST" }).catch(() => {}); setMe(null); }} />
        </div>
      </header>
      <div class="shell-body">
      <div class="nav-scrim no-print" onClick=${() => setNavOpen(false)} aria-hidden="true"></div>
      <nav class=${"sidebar no-print" + (railCollapsed ? " collapsed" : "")} aria-label="Main navigation">
        <div class="sidebar-head">
          <button class="rail-toggle" aria-expanded=${!railCollapsed}
            aria-label=${railCollapsed ? "Expand sidebar" : "Collapse sidebar"}
            title=${railCollapsed ? "Expand sidebar" : "Collapse sidebar"} onClick=${toggleRail}>
            <${Icon} name=${railCollapsed ? "chevron-right" : "chevron-left"} size=${16} />
          </button>
        </div>
        <div class="nav-group">
          <${RailItem} route=${route} path="/overview" icon="home" label="Overview" />
          <${RailItem} route=${route} path="/dashboards" icon="table" label="My dashboards" />
          <${RailItem} route=${route} path="/signals" icon="flag" label="Signals" />
          ${/* "Priorities" (the gap register) was folded into Signals — its
               prevalence flags ARE the gap list. The page stays reachable at
               /priorities as the full exhaustive register + CSV export, linked
               from Signals, but it is no longer a rail surface. */ ""}
          <${RailItem} route=${route} path="/pulse" icon="zap" label="Pulse" />${/* "Run a pulse" is now a tab inside Pulse (admin only) — 2026-08-11 */ ""}
        </div>
        <div class="nav-group">
          <${BenchmarkNav} route=${route} qIndex=${qIndex} prefs=${prefs} onPref=${onPref} collapsed=${railCollapsed} />
        </div>
        <div class="nav-group">
          <div class="nav-label">Your organisation</div>
          <${RailItem} route=${route} path="/your-data" icon="table" label="Your data" />
          ${me.user.role === "admin" && html`<${RailItem} route=${route} path="/strategy" icon="compass" label="Reward strategy" />`}
          ${me.user.role === "admin" && html`<${RailItem} route=${route} path="/team" icon="users" label="Team" />`}
          <${RailItem} route=${route} path="/settings" icon="sliders-v" label="Settings" />
        </div>
        ${me.user.platform_admin && html`
        <div class="nav-group">
          <div class="nav-label">lumi staff</div>
          <${RailItem} route=${route} path="/admin" icon="shield" label="Console" />
        </div>`}
      </nav>
      <div class="main">
        <main class="content" id="main-content" tabindex="-1">
          ${benchRoute && !isOverview && !isCategory && !isDashboards && !isSignals && !isMetric && html`<${PeerSetBar} me=${me} cut=${cut} cuts=${cuts}
            onSelect=${setGlobalCut} onTwinInfo=${() => setTwinOpen(true)}
            prefs=${prefs} onPref=${onPref} refreshMe=${refreshMe} />`}
          ${contrib && benchRoute && html`<${ContributionBanner} contrib=${contrib} />`}
          ${page}
        </main>
      </div>
      </div>${/* /.shell-body */""}
      ${unsub && !barHidden && !leaveTo && !route.startsWith("/your-data/review")
        && (me.user.role === "admin" || me.user.role === "contributor") && html`${/* viewers
          cannot submit — the reminder is an editor's call to action (QA 2026-08-04) */ ""}
        <div class="unsub-bar no-print" role="status" ref=${el => { if (el) document.body.classList.add("has-unsub-bar"); else document.body.classList.remove("has-unsub-bar"); }}>
          <span class="unsub-bar-msg"><span class="unsub-dot"><${Icon} name="award" size=${13} /></span>
            Your answers are <b>saved</b> — but not submitted to the benchmark yet.</span>
          <button class="btn small primary" onClick=${() => nav("/your-data/review")}>Review & submit</button>
          <button class="unsub-x" aria-label="Hide reminder" onClick=${() => setBarHidden(true)}><${Icon} name="close" size=${14} /></button>
        </div>`}
      ${leaveTo && html`<${LeaveSubmitModal}
        onReview=${() => { setLeaveTo(null); window._navRaw("/your-data/review"); }}
        onLeave=${() => { const d = leaveTo; setLeaveTo(null); window._navRaw(d); }}
        onClose=${() => setLeaveTo(null)} />`}
      ${analystOpen && html`<${AnalystPane} onClose=${() => setAnalystOpen(false)} />`}
      ${metricReq && html`<${RequestMetricModal} prefill=${metricReq.prefill} source=${metricReq.source}
        onClose=${() => setMetricReq(null)} />`}
      ${suggestOpen && html`<${SuggestMetricModal} onClose=${() => setSuggestOpen(false)} userEmail=${me.user && me.user.email} />`}
      ${twinOpen && html`<${PeerTwinPanel} onClose=${() => setTwinOpen(false)} onUse=${() => setGlobalCut("twin")} />`}
      ${groupsOpen && html`<${PeerGroupsModal} onClose=${() => { setGroupsOpen(false); refreshCuts(); }}
        onUse=${(gid) => { setCut({ dim: "group", value: gid }); setGroupsOpen(false); refreshCuts(); }} />`}
    </div>`;
}

/* Leave-guard dialog: shown when a member navigates out of the Your-data flow
   with autosaved-but-unsubmitted changes. The honest framing is "saved, not
   submitted" — nothing is lost by leaving; the benchmark just won't update
   until they submit. */
function LeaveSubmitModal({ onReview, onLeave, onClose }) {
  // through the house Modal so it traps/restores focus and closes on Escape
  return html`
    <${Modal} onClose=${onClose} width="460px" role="alertdialog" label="Unsubmitted changes">
      <h2 class="section-title" style=${{ marginTop: 0 }}>You haven't submitted yet</h2>
      <p>Your answers are <b>saved</b> — but <b>not submitted</b>, so your position, signals and £ opportunity won't update until you submit.</p>
      <div class="row" style=${{ gap: "var(--s3)", marginTop: "var(--s4)", justifyContent: "flex-end" }}>
        <button class="btn" onClick=${onLeave}>Leave for now</button>
        <button class="btn primary" onClick=${onReview}>Review & submit</button>
      </div>
    <//>`;
}

/* The Benchmark group (chrome spec section 1.1): parent line is label +
   chevron only — the total lives on the "All" child. Expand state persists
   per user via the prefs store (key _nav); default expanded on first visit —
   the category breadth is part of the pitch. */
/* One nav row: icon + label + optional count. Carries aria-label and data-tip
   (label + count) so the COLLAPSED rail keeps an accessible name and shows a
   hover/focus tooltip (nav pkg Item 3). */
window.RailItem = function ({ route, path, icon, label, count }) {
  const tip = label + (count != null ? " · " + count : "");
  return html`
    <button class=${navCls(route, path)} onClick=${() => nav(path)} aria-label=${tip} data-tip=${tip}>
      <${Icon} name=${icon} size=${15} />
      <span class="nav-txt">${label}</span>
      ${count != null && html`<span class="nav-count">${count}</span>`}
    </button>`;
};

window.BenchmarkNav = function ({ route, qIndex, prefs, onPref, collapsed }) {
  const [flyout, setFlyout] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!flyout) return;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setFlyout(false); };
    const onEsc = (e) => { if (e.key === "Escape") setFlyout(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onEsc); };
  }, [flyout]);
  if (!qIndex) return null;
  const navPrefs = (prefs && prefs._nav) || {};
  const open = navPrefs.benchmark_open !== false;
  const toggle = () => onPref && onPref("_nav", { ...navPrefs, benchmark_open: !open });
  const secs = sectionList(qIndex);
  const total = qIndex.questions.filter(q => !q.locked).length;
  const allActive = route.startsWith("/benchmark") && !route.includes("cat=");
  const benchActive = route.startsWith("/benchmark") || route.startsWith("/category/") || route.startsWith("/metric");
  const secLabel = domainLabel;   // the shared display helper (core.js) — one source for the "Time off" label

  // COLLAPSED: the group can't show an inline child list, so the Benchmark
  // icon opens a flyout popover beside the rail with all eight categories +
  // counts. Closes on click-away/Escape. No child is ever dropped.
  if (collapsed) {
    const goCat = (q) => { setFlyout(false); nav(q); };
    return html`
      <div class="rail-flyout-wrap" ref=${ref}>
        <button class=${"nav-item" + (benchActive ? " active" : "")} aria-label="Benchmark"
          data-tip="Benchmark" aria-expanded=${flyout} onClick=${() => setFlyout(!flyout)}>
          <${SpIcon} sp="Reward" />
        </button>
        ${flyout && html`
          <div class="card rail-flyout" role="group">
            <div class="rail-flyout-head">Benchmark</div>
            <button class=${"rail-flyout-item" + (allActive ? " active" : "")}
              onClick=${() => goCat("/benchmark")}>All<span class="nav-count">${total}</span></button>
            ${secs.map(sec => html`
              <button key=${sec.name}
                class=${"rail-flyout-item" + (route.includes("/category/" + encodeURIComponent(sec.name)) ? " active" : "")}
                onClick=${() => goCat("/category/" + encodeURIComponent(sec.name))}>
                ${secLabel(sec.name)}<span class="nav-count">${sec.count}</span></button>`)}
          </div>`}
      </div>`;
  }

  return html`
    <button class=${"nav-item nav-parent" + (route.startsWith("/metric") ? " active" : "")} aria-expanded=${open} aria-label="Benchmark" data-tip="Benchmark" onClick=${toggle}>
      <${SpIcon} sp="Reward" /><span class="nav-txt">Benchmark</span>
      <span class=${"nav-chev" + (open ? " open" : "")}><${Icon} name="chevron-down" size=${14} /></span>
    </button>
    ${open && html`
      <button class=${"nav-item nav-child" + (allActive ? " active" : "")} onClick=${() => nav("/benchmark")}>
        <span class="nav-txt">All</span>
        <span class="nav-count">${total}</span>
      </button>
      ${secs.map(sec => {
        const active = route.includes("/category/" + encodeURIComponent(sec.name));
        return html`
          <button key=${sec.name} class=${"nav-item nav-child" + (active ? " active" : "")}
            onClick=${() => nav("/category/" + encodeURIComponent(sec.name))}>
            <span class="nav-txt">${secLabel(sec.name)}</span>
            <span class="nav-count">${sec.count}</span>
          </button>`;
      })}`}`;
};

/* Company profile: org-level, ~8 fields, captured once by the Admin so the
   benchmark can compare against the right peers. Benign company facts only —
   no personal data. Choice sets mirror the seed registry. */
window.ProfilePage = function ({ me, refreshMe }) {
  const [data, setData] = useState(null);
  const [vals, setVals] = useState({});
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);
  useEffect(() => {
    api("/api/org-profile").then(d => { setData(d); setVals(d.values); }).catch(e => setErr(e.message));
  }, []);
  if (err) return html`<${EmptyState} title="Couldn't load your profile" body=${err} />`;
  if (!data) return html`<${PageLoading} />`;
  const canEdit = data.can_edit;
  const firstRun = !me.org.classified;
  const CORE = [["industry", "Industry / sector"], ["fte_band", "Organisation size (full-time employees)"],
                ["hq_region", "HQ region"], ["ownership_type", "Ownership"]];
  const RICH = [["unionised_level", "How much of your workforce is unionised?"],
                ["hr_maturity", "How developed is your HR function?"],
                ["business_maturity", "Where is the business in its life cycle?"],
                ["operating_model", "How do you operate?"]];
  const Field = ([k, label], required) => html`
    <div class="field" key=${k}>
      <label htmlFor=${"prof-" + k}>${label}${required && html`<span style=${{ color: "var(--unfavourable)" }}> *</span>`}</label>
      <select id=${"prof-" + k} value=${vals[k] || ""} disabled=${!canEdit} onChange=${e => setVals({ ...vals, [k]: e.target.value })}>
        <option value="">Choose…</option>
        ${(data.choices[k] || []).map(o => html`<option key=${o} value=${o}>${o}</option>`)}
      </select>
    </div>`;
  const coreDone = CORE.every(([k]) => vals[k]);
  const save = async () => {
    if (saving) return;
    setSaving(true); setErr(null);
    try {
      const r = await api("/api/org-profile", { method: "PUT", body: vals });
      await refreshMe();
      toast(r.core_complete ? "Profile saved — your peer groups are live." : "Profile saved.");
      if (firstRun && r.core_complete) nav("/overview");
    } catch (e) { setErr(e.message); }
    setSaving(false);
  };
  return html`
    <div style=${{ maxWidth: "620px" }}>
      ${!firstRun && html`<button class="btn quiet" onClick=${() => window.history.back()}>← Back</button>`}
      <h1 class="display-title" style=${{ marginTop: "var(--s2)" }}>${firstRun ? "Tell us about your organisation" : "Company profile"}</h1>
      <p>${firstRun
        ? "So we can compare you to the right peers — sector, size and a few company facts. About two minutes."
        : "The company facts behind your peer groups — update them any time."}</p>
      <p class="caption">Organisation-level facts only — never personal data, never shown to another member. They decide your peer groups.</p>
      <div class="card" style=${{ padding: "var(--s5)", margin: "var(--s4) 0" }}>
        <h2 class="section-title">The essentials</h2>
        ${CORE.map(f => Field(f, true))}
        <h2 class="section-title" style=${{ marginTop: "var(--s4)" }}>Sharper peer groups <span class="caption" style=${{ fontWeight: 400 }}>(recommended — powers "Organisations like you")</span></h2>
        ${RICH.map(f => Field(f, false))}
        ${err && html`<div class="error-text" style=${{ marginBottom: "var(--s2)" }}>${err}</div>`}
        ${canEdit ? html`
          <button class="btn primary" disabled=${saving || !coreDone} onClick=${save}>
            ${saving ? html`<${Spinner} />` : firstRun ? "Save and see your benchmark" : "Save profile"}</button>
          ${!coreDone && html`<div class="caption" style=${{ marginTop: "var(--s2)" }}>The four essentials are needed before peer groups work.</div>`}` :
        html`<div class="caption">Only your organisation's Admin can edit the company profile.</div>`}
      </div>
    </div>`;
};

/* Custom peer groups: filter-based, private to the org. The live match count
   keeps the user honest against the suppression floor BEFORE they save —
   and the server enforces the same floor regardless. Membership is never
   shown, only the count. */
window.PeerGroupsModal = function ({ onClose, onUse }) {
  const [options, setOptions] = useState(null);
  const [groups, setGroups] = useState(null);
  const [editing, setEditing] = useState(null);    // null=list | {} new | group obj
  const [name, setName] = useState("");
  const [criteria, setCriteria] = useState({});
  const [count, setCount] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const previewTimer = useRef(null);
  const refresh = () => api("/api/peer-groups").then(d => setGroups(d.groups));
  useEffect(() => { api("/api/peer-groups/options").then(setOptions); refresh(); }, []);

  const startNew = () => { setEditing({}); setName(""); setCriteria({}); setCount(null); setErr(null); };
  const startEdit = (g) => { setEditing(g); setName(g.name); setCriteria(g.criteria); setCount({ match_count: g.match_count, too_small: g.too_small, min_orgs: g.min_orgs }); setErr(null); };
  const toggle = (field, value) => {
    const cur = new Set(criteria[field] || []);
    cur.has(value) ? cur.delete(value) : cur.add(value);
    const next = { ...criteria, [field]: Array.from(cur) };
    if (!next[field].length) delete next[field];
    setCriteria(next);
    clearTimeout(previewTimer.current);
    if (Object.keys(next).length === 0) { setCount(null); return; }
    previewTimer.current = setTimeout(() =>
      api("/api/peer-groups/preview", { method: "POST", body: { criteria: next } })
        .then(setCount).catch(() => setCount(null)), 350);
  };
  const save = async () => {
    if (busy) return;
    setBusy(true); setErr(null);
    try {
      const body = { name, criteria };
      const saved = editing.group_id
        ? await api("/api/peer-groups/" + editing.group_id, { method: "PUT", body })
        : await api("/api/peer-groups", { method: "POST", body });
      toast(`Peer group “${saved.name}” saved`);
      setEditing(null); refresh();
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const del = async (g) => {
    if (!window.confirm(`Delete the peer group “${g.name}”? This only removes the saved filter — no data is affected.`)) return;
    try { await api("/api/peer-groups/" + g.group_id, { method: "DELETE" }); toast("Peer group deleted"); refresh(); }
    catch (e) { toast("Couldn't delete that peer group — try again", "error"); }
  };

  if (!options || !groups) return html`<${Modal} onClose=${onClose} label="Manage peer groups"><${Spinner} /><//>`;
  return html`
    <${Modal} onClose=${onClose} xl=${true} label="Manage peer groups">
      ${editing === null ? html`
        <div>
          <div class="row spread">
            <h2 class="section-title" style=${{ marginBottom: 0 }}>Your peer groups</h2>
            <button class="btn primary small" onClick=${startNew}>+ Create peer group</button>
          </div>
          <p class="caption">Build a peer group from company facts — sector, size, region and more.
          Private to your organisation. You'll only ever see <b>how many</b> organisations match, never which —
          and nothing shows unless at least ${options.min_orgs} match.</p>
          ${groups.length === 0 && html`<${EmptyState} title="No peer groups yet"
            body="Create one — e.g. “UK mid-size manufacturers” — and it appears in the peer-group selector." />`}
          ${groups.map(g => html`
            <div key=${g.group_id} class="card" style=${{ padding: "var(--s3) var(--s4)", marginBottom: "var(--s2)" }}>
              <div class="row spread">
                <div style=${{ minWidth: 0 }}>
                  <b>${g.name}</b>
                  <span class=${"chip " + (g.too_small ? "warn" : "")} style=${{ marginLeft: "var(--s2)" }}>
                    ${g.too_small ? `only ${g.match_count} match — needs ${g.min_orgs}` : `${g.match_count} organisations`}</span>
                  <div class="caption" style=${{ marginTop: "2px" }}>
                    ${Object.entries(g.criteria).map(([f, vs]) => {
                      const fl = (options.fields.find(x => x.key === f) || {}).label || f;
                      return fl + ": " + vs.join(" or ");
                    }).join(" · ")}</div>
                </div>
                <div class="row" style=${{ flex: "none" }}>
                  ${!g.too_small && html`<button class="btn small" onClick=${() => onUse(g.group_id)}>Use</button>`}
                  <button class="btn small quiet" onClick=${() => startEdit(g)}>Edit</button>
                  <button class="btn small quiet" onClick=${() => del(g)}>Delete</button>
                </div>
              </div>
            </div>`)}
        </div>` : html`
        <div>
          <h2 class="section-title">${editing.group_id ? "Edit peer group" : "Create a peer group"}</h2>
          <div class="field" style=${{ maxWidth: "360px" }}>
            <label>Group name</label>
            <input value=${name} autoFocus placeholder=${"e.g. UK mid-size manufacturers"}
              onInput=${e => setName(e.target.value)} />
          </div>
          <p class="caption" style=${{ margin: "0 0 var(--s2)" }}>Pick the facts a peer must match — several options in one row means “any of these”.</p>
          <div class="group-fields">
            ${options.fields.map(f => html`
              <div key=${f.key} class="group-field">
                <div class="caption" style=${{ fontWeight: 700, marginBottom: "var(--s1)" }}>${f.label}
                  ${!(criteria[f.key] || []).length && html`<span style=${{ fontWeight: 400 }}> · any</span>`}</div>
                <div class="chip-row">
                  ${f.choices.map(v => html`
                    <button key=${v} class=${"crit-chip" + ((criteria[f.key] || []).includes(v) ? " on" : "")}
                      aria-pressed=${(criteria[f.key] || []).includes(v)}
                      onClick=${() => toggle(f.key, v)}>${v}</button>`)}
                </div>
              </div>`)}
          </div>
          <div class=${"group-count" + (count && count.too_small ? " warn" : "")} aria-live="polite">
            ${Object.keys(criteria).length === 0 ? "Choose at least one criterion."
              : count === null ? html`<${Spinner} />`
              : count.too_small
                ? `Only ${count.match_count} organisation${count.match_count === 1 ? "" : "s"} currently match — at least ${count.min_orgs} are needed before any benchmark shows. You can still save it.`
                : `${count.match_count} organisations currently match.`}
          </div>
          ${err && html`<div class="error-text" style=${{ marginBottom: "var(--s2)" }}>${err}</div>`}
          <div class="row">
            <button class="btn primary" disabled=${busy || !name.trim() || Object.keys(criteria).length === 0} onClick=${save}>
              ${busy ? html`<${Spinner} />` : "Save group"}</button>
            <button class="btn" onClick=${() => setEditing(null)}>Back</button>
          </div>
        </div>`}
    <//>`;
};

window.NotFoundPage = function ({ route }) {
  return html`
    <div style=${{ maxWidth: "480px", margin: "var(--s7) auto", textAlign: "center" }}>
      <div style=${{ color: "var(--ink-faint)", marginBottom: "var(--s3)" }}><${Icon} name="search" size=${26} /></div>
      <h1 class="display-title">That page doesn't exist</h1>
      <p class="caption">There's nothing at <b>${route}</b> — it may be an old or mistyped link.</p>
      <div class="row" style=${{ gap: "var(--s2)", justifyContent: "center", flexWrap: "wrap" }}>
        <button class="btn primary" onClick=${() => nav("/overview")}>Back to your overview</button>
        <button class="btn quiet" onClick=${() => nav("/how-lumi-works")}>How lumi works</button>
      </div>
    </div>`;
};

/* Idle session guard: after IDLE_MIN minutes without input, warn with a
   60-second countdown and a "stay signed in" option; sign out if ignored.
   Client-side policy only — no security logic changed. */
window.IdleGuard = function ({ onSignOut }) {
  const IDLE_MIN = window.LUMI_IDLE_MIN || 30;   // overridable for testing
  const [warn, setWarn] = useState(false);
  const [left, setLeft] = useState(60);
  const last = useRef(Date.now());
  const warnRef = useRef(false);
  useEffect(() => { warnRef.current = warn; }, [warn]);
  useEffect(() => {
    let throttled = 0;
    const touch = () => { const now = Date.now(); if (now - throttled > 2000) { throttled = now; last.current = now; } };
    ["mousemove", "mousedown", "keydown", "scroll", "touchstart"].forEach(ev =>
      window.addEventListener(ev, touch, { passive: true }));
    const iv = setInterval(() => {
      const idleMin = window.LUMI_IDLE_MIN || IDLE_MIN;
      if (!warnRef.current && Date.now() - last.current > idleMin * 60000) { setWarn(true); setLeft(60); }
    }, window.LUMI_IDLE_MIN ? 1000 : 15000);
    return () => { clearInterval(iv); ["mousemove", "mousedown", "keydown", "scroll", "touchstart"].forEach(ev =>
      window.removeEventListener(ev, touch)); };
  }, []);
  useEffect(() => {
    if (!warn) return;
    const iv = setInterval(() => setLeft(l => {
      if (l <= 1) { clearInterval(iv); onSignOut(); return 0; }
      return l - 1;
    }), 1000);
    return () => clearInterval(iv);
  }, [warn]);
  if (!warn) return null;
  const stay = async () => { try { await api("/api/me"); } catch (e) { /* handled globally */ } last.current = Date.now(); setWarn(false); };
  // house Modal = trap + restore; dismissing (Escape/backdrop) means "stay"
  return html`
    <${Modal} onClose=${stay} width="420px" role="alertdialog" label="Session timeout warning">
      <div style=${{ textAlign: "center" }}>
        <h2 class="section-title">Still there?</h2>
        <p>You'll be signed out in <span class="idle-count">${left}</span> seconds. Your answers are autosaved.</p>
        <div class="row" style=${{ justifyContent: "center" }}>
          <button class="btn primary" autoFocus onClick=${stay}>Stay signed in</button>
          <button class="btn" onClick=${onSignOut}>Sign out now</button>
        </div>
      </div>
    <//>`;
};

window.sectionList = function (qIndex) {
  const m = new Map();
  for (const q of qIndex.questions) {
    if (q.locked || !q.subpower) continue;
    if (!m.has(q.subpower)) m.set(q.subpower, { name: q.subpower, order: q.sub_power_order || 999, count: 0 });
    m.get(q.subpower).count++;
  }
  return Array.from(m.values()).sort((a, b) => a.order - b.order);
};

/* The contribution countdown now lives only in the unsubmitted-state banner
   (see WelcomeHero) — the duplicate nav chip was removed 2026-06-15. */

/* Gentle reminders as the deadline nears (7 days / 1 day), and the fair,
   forewarned day-30 message. Quiet banners, never modals. */
/* Quiet data-completion chip in the brandbar (David 2026-07-13, "subtly provide a data
   completed % — to prompt people to provide data"): a micro progress ring + percentage,
   clicking through to Your data. Editors only (Viewers can't submit — never render a
   control that can't act) and gone at 100% — its job is done, the bar stays clean. The
   louder ContributionBanner still owns the pre-unlock deadline story; this is the gentle
   always-there cue after that banner earns its retirement. */
function DataProgressChip({ contrib, role, platformAdmin }) {
  // staff org carries no benchmark data by design — a 0% nudge there is noise
  if (!contrib || role === "viewer" || platformAdmin) return null;
  const pct = Math.round(contrib.core_pct || 0);
  if (pct >= 100) return null;
  const c = 2 * Math.PI * 7;
  const target = Math.round(contrib.target_pct || 90);
  const tip = pct >= target
    ? `${pct}% of your key reward questions answered — finishing the set sharpens every benchmark you get back.`
    : `${pct}% of your key reward questions answered — ${target}% unlocks your full benchmark.`;
  return html`
    <button type="button" class="databar-chip" title=${tip} aria-label=${tip + " Open Your data."}
      onClick=${() => nav("/your-data/submit")}>
      <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
        <circle cx="9" cy="9" r="7" fill="none" stroke="rgba(255,255,255,.28)" stroke-width="2.5" />
        <circle cx="9" cy="9" r="7" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round"
          stroke-dasharray=${c} stroke-dashoffset=${c * (1 - Math.min(100, Math.max(0, pct)) / 100)}
          transform="rotate(-90 9 9)" />
      </svg>
      <span class="num">${pct}%</span>
    </button>`;
}

window.ContributionBanner = function ({ contrib }) {
  if (contrib.insights_unlocked || !contrib.clock_started) return null;
  const pct = Math.round(contrib.core_pct || 0);
  if (contrib.reduced) return html`
    <div class="card contrib-banner paused">
      <div>
        <b>Your full benchmark is paused.</b>
        <div class="caption">The 30 days passed before your reward data was complete — everything you've explored is still here, and a sample stays open below. You're at ${pct}%.</div>
      </div>
      <button class="btn primary small" onClick=${() => nav("/your-data")}>${window.submitVerb(pct === 0)}</button>
    </div>`;
  if (contrib.days_left > 7) return null;
  const need = window.unlockNeed(contrib);
  return html`
    <div class="card contrib-banner">
      <div>
        <b>${need > 0 ? `You're ${need} key question${need === 1 ? "" : "s"} from your insights.` : `You're ${pct}% of the way to your insights.`}</b>
        <div class="caption">Complete your key reward questions and your insights go live with your real position — ${contrib.days_left} day${contrib.days_left === 1 ? "" : "s"} left in your window, but nothing is lost if it passes; your benchmark simply pauses to a sample until you finish.</div>
      </div>
      <button class="btn primary small" onClick=${() => nav("/your-data")}>${window.submitVerb(pct === 0)}</button>
    </div>`;
};

/* The warm first-run welcome on the overview — confident and light, one
   obvious next step. Founding members contribute data, never payment. */
window.WelcomeHero = function ({ contrib, pool, me }) {
  const pct = Math.round(contrib.core_pct || 0);
  const role = me && me.user ? me.user.role : "viewer";
  // Source the onboarding numbers from live scope + the dynamic unlock threshold
  // so they never drift on a release (questions added/removed, threshold tuned).
  const scopeN = (me && me.scope && me.scope.question_count) || (window.SCOPE && window.SCOPE.question_count) || null;
  const basisN = (contrib && contrib.basis_total) || (me && me.scope && me.scope.required_size) || null;
  const targetPct = Math.round(contrib.target_pct || 90);
  if (!contrib.terms_accepted) {
    /* First-run "you're set up — next steps": welcoming, not a wizard.
       The profile gate ("who you are") comes before the contribution gate
       ("share your data") — never both walls at once. */
    const profiled = !!(me && me.org && me.org.classified);
    const steps = [
      { n: 1, label: "Tell us about your organisation", done: profiled,
        hint: profiled ? "Done — your peer groups are live."
          : role === "admin" ? "8 quick facts (sector, size, region…) so we compare you to the right peers. Two minutes, company facts only."
          : "Your Admin does this — nothing is needed from you." },
      { n: 2, label: "Review and accept the Data Contribution Terms", done: false,
        hint: role === "admin" ? "You accept once, for the whole organisation — your 30 days start then."
                               : "Your Admin does this — nothing is needed from you yet." },
      { n: 3, label: "Complete your reward data", done: false,
        hint: (basisN ? "About " + basisN + " key questions (~" + Math.round(basisN * 0.6 / 10) * 10 + " min), by section" : "Your reward questions by section") + " — autosaved, resume any time; insights unlock at " + targetPct + "%." },
      { n: 4, label: "Invite your team", done: false,
        hint: role === "admin" ? "Contributors fill the questionnaire; Viewers see the benchmark."
          : "Your Admin does this — nothing is needed from you." },
    ];
    return html`
      <div class="card welcome-hero">
        <div style=${{ flex: "1.6 1 320px", minWidth: "280px" }}>
          <div class="row" style=${{ gap: "var(--s2)", marginBottom: "var(--s1)" }}>
            <span style=${{ color: "var(--blue)" }}><${Icon} name="sparkle" size=${18} /></span>
            <b style=${{ fontFamily: "var(--font-head)", fontSize: "var(--fs-subhead)" }}>Welcome — your benchmark is ready to build</b>
          </div>
          <p style=${{ margin: "2px 0 0" }}>Answer your reward questions and lumi shows exactly where you sit against your ${pool.responding_orgs}-organisation peer group — your <b>£ gaps</b>, the practices <b>most peers offer that you don't</b>, and a <b>board-ready pack</b>. Explore every metric now; your 30 days only start once your Admin accepts the data terms, so setup never counts against you.</p>
        </div>
        <div style=${{ flex: "1.2 1 280px", minWidth: "260px" }}>
          ${steps.map(st => html`
            <div key=${st.n} class=${"next-step" + (st.n === 3 && !st.done ? " is-value" : "")}>
              <span class=${"next-step-n" + (st.done ? " done" : "")}>${st.done ? "✓" : st.n}</span>
              <div><b>${st.label}</b>${st.n === 3 && !st.done ? html` <span class="next-step-badge">unlocks your insights</span>` : null}<div class="caption">${st.hint}</div></div>
            </div>`)}
          <div class="row" style=${{ marginTop: "var(--s2)" }}>
            ${role === "admin" && !profiled && html`<button class="btn primary" onClick=${() => nav("/profile")}>Tell us about your organisation</button>`}
            ${role === "admin" && profiled && html`<button class="btn primary" onClick=${() => nav("/your-data/submit")}>Review the data terms</button>`}
            ${role === "admin" && html`<button class="btn" onClick=${() => nav("/team")}>Invite your team</button>`}
            ${role !== "admin" && html`<button class="btn primary" onClick=${() => nav("/benchmark")}>Explore the benchmark</button>`}
          </div>
        </div>
      </div>`;
  }
  // post-terms: the submit banner PLUS a persistent, itemised setup checklist so
  // the multi-session journey isn't represented by one % bar. Steps carry real
  // done-state (profile/terms/data/team) and don't evaporate the moment terms
  // are accepted — they run until insights unlock.
  const profiledPost = !!(me && me.org && me.org.classified);
  const need = window.unlockNeed(contrib);
  const mins = window.keyMinutes(need);
  const setupSteps = [
    { label: "Tell us about your organisation", done: profiledPost },
    { label: "Accept the Data Contribution Terms", done: true },
    { label: "Complete your reward data", done: pct >= targetPct, now: pct < targetPct,
      note: pct >= targetPct ? pct + "%"
        : need > 0 ? need + " key to go" + (mins ? " · " + mins : "")
        : pct + "% answered · " + targetPct + "% unlocks" },
    { label: "Invite your team", done: !!contrib.team_invited, optional: true },
  ];
  const doneCount = setupSteps.filter(s => s.done).length;
  return html`
    <div class="submit-banner">
      <div class="submit-banner-msg">
        <div class="submit-banner-head">${need > 0
          ? `You're ${need} key question${need === 1 ? "" : "s"} from your insights`
          : `You're ${pct}% of the way to your insights`}</div>
        <p class="submit-banner-body">At ${targetPct}%, lumi unlocks your <b>£ opportunity</b>, your <b>biggest gaps</b> and a <b>board-ready pack</b>. Your answers autosave and stay private to your organisation.</p>
        <div class="submit-banner-progress">
          <div class="progressbar"><div style=${{ width: Math.min(100, pct / targetPct * 100) + "%" }}></div></div>
          <span class="caption submit-banner-pct"><b class="num">${pct}%</b> of ${targetPct}%${contrib.days_left != null ? html` · <span class="num">${contrib.days_left}</span> ${contrib.days_left === 1 ? "day" : "days"} left in your window` : ""}</span>
        </div>
        ${contrib.days_left != null ? html`<p class="caption submit-banner-reassure">No rush to finish today — if day 30 arrives first, your benchmark simply pauses to a sample until you're done. Nothing you've entered is lost.</p>` : null}
      </div>
      ${role === "viewer"
        ? html`<span class="caption">Your Admin or a Contributor completes the data.</span>`
        : html`<button class="btn primary submit-banner-cta" onClick=${() => nav("/your-data")}>Continue your reward data</button>`}
    </div>
    <div class="setup-checklist card">
      <div class="setup-checklist-head"><span class="eyebrow">Setup · ${doneCount} of ${setupSteps.length}</span></div>
      <div class="setup-steps">
        ${setupSteps.map((s, i) => html`
          <div key=${i} class=${"setup-step" + (s.done ? " done" : "") + (s.now ? " now" : "")}>
            <span class="setup-tick">${s.done ? html`<${Icon} name="check" size=${13} />` : html`<span class="setup-dot"></span>`}</span>
            <span class="setup-label">${s.label}${s.optional && !s.done ? html` <span class="caption">· optional</span>` : null}</span>
            ${s.note ? html`<span class="caption setup-note num">${s.note}</span>` : null}
          </div>`)}
      </div>
    </div>`;
};

function cutHint(cut, cuts, me) {
  const total = (me.peer_pool || {}).responding_orgs || "all";
  if (cut.dim === "industry") return `Comparing against ${cut.value} only — change here.`;
  if (cut.dim === "fte_band") return `Comparing against ${cut.value}-employee organisations — change here.`;
  if (cut.dim === "twin") return "Comparing against organisations most like yours — change here.";
  if (cut.dim === "group") {
    const g = cuts && (cuts.groups || []).find(g => g.group_id === cut.value);
    if (!g) return "Comparing against your custom group.";
    return g.too_small
      ? `Only ${g.match_count} organisation${g.match_count === 1 ? "" : "s"} match “${g.name}” — at least ${g.min_orgs} are needed before a benchmark shows.`
      : `Comparing against “${g.name}” — ${g.match_count} organisations.`;
  }
  return `Comparing against all ${total} organisations — change here.`;
}

/* Initials for the avatar: first letters of the display name, else the email. */
function initialsOf(user) {
  const src = (user.display_name || "").trim() || (user.email || "");
  const parts = src.split(/[\s@._-]+/).filter(Boolean);
  const a = (parts[0] || src || "?")[0] || "?";
  const b = parts.length > 1 ? (parts[parts.length - 1][0] || "") : "";
  return (a + b).toUpperCase();
}

function cutTooSmall(cut, cuts) {
  if (cut.dim !== "group") return false;
  const g = cuts && (cuts.groups || []).find(g => g.group_id === cut.value);
  return !!(g && g.too_small);
}

/* Profile menu (chrome spec §3): the avatar at the far right of the top bar.
   Opens an identity header (signed-in user + their org, non-clickable) then
   Your profile / How lumi works / Sign out. The account block and all
   reference links now live HERE — the sidebar has no footer. */
function ProfileMenu({ me, onSignOut }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useMenuClose(ref, open, setOpen);
  const go = (path) => { setOpen(false); nav(path); };
  return html`
    <div class="profile-menu" ref=${ref}>
      <button class=${"avatar" + (open ? " active" : "")} aria-expanded=${open}
        aria-label="Account menu" onClick=${() => setOpen(!open)}>${initialsOf(me.user)}</button>
      ${open && html`
        <div class="card profile-pop" role="group">
          <div class="profile-id">
            <div class="profile-id-name">${me.user.display_name || me.user.email}</div>
            <div class="profile-id-org">${me.org.name}</div>
          </div>
          <div class="profile-sep"></div>
          <button class="profile-item" onClick=${() => go("/profile")}>Company profile</button>
          ${me.user.role === "admin" ? html`<button class="profile-item" onClick=${() => go("/strategy")}>Reward strategy</button>` : null}
          <button class="profile-item" onClick=${() => go("/how-lumi-works")}>How lumi works</button>
          <div class="profile-sep"></div>
          <button class="profile-item" onClick=${() => { setOpen(false); onSignOut(); }}>Sign out</button>
        </div>`}
    </div>`;
}

/* The notification bell (chrome): every member's in-app inbox of signal-change
   alerts. Unread count + a dropdown grouped by lens; each row opens its metric
   and marks itself read. Polls quietly — the nightly sweep feeds it. */
const NOTIF_LENS = {
  attract: { label: "Attract", icon: "magnet" }, retain: { label: "Retain", icon: "anchor" },
  engage: { label: "Engage", icon: "heart" }, save: { label: "Save", icon: "coins" },
};
const NOTIF_LENS_ORDER = ["attract", "retain", "engage", "save"];

function NotificationBell({ me }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState(null);
  const ref = useRef(null);
  const load = () => api("/api/notifications").then(setData).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 120000); return () => clearInterval(t); }, []);
  useMenuClose(ref, open, setOpen);
  if (!data || !data.inbox_enabled) return null;        // inbox switched off → no bell
  const unread = data.unread || 0;
  const events = data.events || [];
  const markAll = async () => { await api("/api/notifications/read", { method: "POST", body: { all: true } }).catch(() => {}); load(); };
  const openEvent = (ev) => {
    setOpen(false);
    api("/api/notifications/read", { method: "POST", body: { event_ids: [ev.id] } }).catch(() => {});
    openMetric(ev.question_id);
  };
  const groups = NOTIF_LENS_ORDER.map(l => ({ lens: l, items: events.filter(e => e.lens === l) })).filter(g => g.items.length);
  return html`
    <div class="notif-bell" ref=${ref}>
      <button class=${"notif-btn" + (open ? " active" : "")} aria-expanded=${open}
        aria-label=${"Notifications" + (unread ? " — " + unread + " unread" : "")} onClick=${() => setOpen(!open)}>
        <${Icon} name="bell" size=${17} />
        ${unread > 0 && html`<span class="notif-badge">${unread > 99 ? "99+" : unread}</span>`}
      </button>
      ${open && html`
        <div class="card notif-pop" role="group">
          <div class="notif-head">
            <b>Notifications</b>
            ${unread > 0 ? html`<button class="notif-mark" onClick=${markAll}>Mark all read</button>` : null}
          </div>
          ${events.length === 0 ? html`
            <div class="notif-empty"><span class="notif-empty-ring"><${Icon} name="bell" size=${18} /></span>
              <div class="caption">No changes yet. When your position against the market moves — a flag appears, clears, or shifts — it lands here.</div></div>` :
          html`<div class="notif-list">
            ${groups.map(g => html`
              <div key=${g.lens} class="notif-group">
                <div class=${"notif-group-head lens-" + g.lens}><${Icon} name=${NOTIF_LENS[g.lens].icon} size=${12} /> ${NOTIF_LENS[g.lens].label}</div>
                ${g.items.map(ev => html`
                  <button key=${ev.id} class=${"notif-row lens-" + g.lens + (ev.read ? "" : " unread")} onClick=${() => openEvent(ev)}>
                    <span class="notif-row-title">${ev.title}</span>
                    <span class="notif-row-body">${ev.body}</span>
                  </button>`)}
              </div>`)}
          </div>`}
          <div class="notif-foot"><a href="#" onClick=${e => { e.preventDefault(); setOpen(false); nav("/settings"); }}>Notification settings →</a></div>
        </div>`}
    </div>`;
}

/* The peer-set lens. It used to anchor the top bar, but it only changes the
   benchmark surfaces — so it now lives in a slim context strip at the top of
   those pages ("comparing against …"), and is absent everywhere else. Still
   global state (App owns `cut`); this is just where it's surfaced. */
function PeerSetBar({ me, cut, cuts, onSelect, onTwinInfo, inline, prefs, onPref, refreshMe }) {
  const note = (!me.org.classified || (cut.dim === "group" && cutTooSmall(cut, cuts)));
  // ★/🔔 default-setters REMOVED from the capsule (David 2026-07-12). The ONE company default
  // (orgs.default_cut) is set from Settings → Company default peer group; it drives signals +
  // alerts AND everyone's landing view (the per-user _peer_default pref was dropped 2026-08-11).
  //
  // Menu ORDER (David 2026-08-11): the company default sits at the TOP labelled "Company Default",
  // then the org's own custom groups, then the built-in market cuts. Putting the usual selection at
  // the top also stops the native <select> popup opening scrolled off the top of the viewport.
  const poolN = (me.peer_pool || {}).responding_orgs || "—";
  const hasDefault = !!(me.org && me.org.signal_peer_cut);
  const defCut = hasDefault ? me.org.signal_peer_cut : "all";
  const bandLow = s => { const m = String(s).replace(/,/g, "").match(/\d+/); return m ? parseInt(m[0], 10) : 0; };
  const defGid = defCut.indexOf("group::") === 0 ? defCut.slice(7) : null;
  const defGroup = defGid && ((cuts && cuts.groups) || []).find(g => g.group_id === defGid);
  const defCount = defGroup ? defGroup.match_count
    : defCut === "all" ? poolN
    : defCut.indexOf("industry::") === 0 ? ((cuts && cuts.industries) || {})[defCut.slice(10)]
    : defCut.indexOf("fte_band::") === 0 ? ((cuts && cuts.fte_bands) || {})[defCut.slice(10)]
    : defCut === "twin" ? (cuts && cuts.twin_n) : null;
  const defOptLabel = hasDefault
    ? "Company Default" + (defCount != null ? " · " + defCount : "")
    : "All peers · " + poolN;
  // custom groups, minus whichever one IS the default (it shows once, at the top)
  const customGroups = ((cuts && cuts.groups) || []).filter(g => ("group::" + g.group_id) !== defCut);
  // built-in market cuts (all peers, sectors, sizes, similar orgs), minus the default one
  const marketOpts = [];
  if (defCut !== "all") marketOpts.push({ value: "all", label: "All peers · " + poolN });
  if (me.org.classified && cuts) {
    if (cuts.org_industry) marketOpts.push({ value: "industry::" + cuts.org_industry, label: cuts.org_industry + " · " + (cuts.industries[cuts.org_industry] || "?") });
    Object.keys(cuts.industries || {}).filter(i => i !== cuts.org_industry).forEach(i => marketOpts.push({ value: "industry::" + i, label: i + " · " + cuts.industries[i] }));
    Object.keys(cuts.fte_bands || {}).sort((x, y) => bandLow(x) - bandLow(y)).forEach(b => marketOpts.push({ value: "fte_band::" + b, label: b + " FTE · " + cuts.fte_bands[b] }));
    if (cuts.twin_available) marketOpts.push({ value: "twin", label: "Organisations like you" + (typeof cuts.twin_n === "number" ? " · " + cuts.twin_n : "") });
  }
  const marketShown = marketOpts.filter(o => o.value !== defCut);
  return html`
    <div class=${"peerbar no-print" + (inline ? " peerbar-inline" : "")}>
      <span class="peerbar-lead"><${Icon} name="users" size=${13} /> Comparing against</span>
      <span class=${"peerbar-pill" + (cut.dim !== "all" ? " narrowed" : "")}>
        <span class="peerbar-selwrap">
        <select aria-label="Choose your peer group" class="peer-ctl"
          value=${cut.dim === "all" ? "all" : cut.dim === "twin" ? "twin" : cut.dim + "::" + cut.value}
          onChange=${e => { if (e.target.value === "twin-info") { onTwinInfo(); } else onSelect(e.target.value); }}>
          <option value=${defCut}>${defOptLabel}</option>
          ${customGroups.length > 0 && html`
            <optgroup label="Your peer groups">
              ${customGroups.map(g => html`<option key=${g.group_id} value=${"group::" + g.group_id}>
                ${g.name}${g.too_small ? " (too few organisations)" : ` · ${g.match_count}`}</option>`)}
            </optgroup>`}
          ${marketShown.length > 0 && html`
            <optgroup label="Other peer sets">
              ${marketShown.map(o => html`<option key=${o.value} value=${o.value}>${o.label}</option>`)}
            </optgroup>`}
          ${me.org.classified && html`<option value="manage-groups">+ Create / manage peer groups…</option>`}
        </select>
        <span class="peerbar-caret"><${Icon} name="chevron-down" size=${13} /></span>
        </span>
      </span>
      ${cut.dim === "twin" && html`<button class="btn small" onClick=${onTwinInfo}>Why these peers?</button>`}
      ${note && html`
        <span class="peerset-note">${!me.org.classified
          ? (me.user.role === "admin"
              ? html`<a href="#/profile">Add your company profile</a> to compare by sector & size`
              : "Your Admin can add the company profile to unlock sector & size")
          : html`${cutHint(cut, cuts, me)} ${" "}<a href="#/how-lumi-works/suppression">Why?</a>`}</span>`}
    </div>`;
}

// deep routes with no rail item of their own light up their parent, so the
// sidebar always shows where you are (metric→Benchmark, priorities→Signals, …)
const RAIL_PARENT = { "/metric": "/benchmark", "/category": "/benchmark",
  "/priorities": "/signals", "/profile": "/your-data", "/run-a-pulse": "/pulse" };
function navCls(route, path) {
  let r = route;
  for (const pfx in RAIL_PARENT) { if (r.startsWith(pfx)) { r = RAIL_PARENT[pfx]; break; } }
  const active = path === "/overview" ? (r === "/" || r === "" || r.startsWith("/overview")) : r.startsWith(path);
  return "nav-item" + (active ? " active" : "");
}

/* Levenshtein edit distance — small, iterative, good enough for typo-tolerant
   metric search over a ~200-question index. */
function editDistance(a, b) {
  const m = a.length, n = b.length;
  if (!m) return n; if (!n) return m;
  let prev = Array.from({ length: n + 1 }, (_, j) => j);
  for (let i = 1; i <= m; i++) {
    const cur = [i];
    for (let j = 1; j <= n; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
    }
    prev = cur;
  }
  return prev[n];
}

const STOP_WORDS = new Set(["the", "a", "an", "of", "and", "or", "to", "for", "is", "in", "by", "your", "you", "do"]);

/* Fuzzy near-miss suggestions (chrome spec §5): when an exact substring search
   finds nothing, find titles whose tokens are within a typo of the query
   tokens ("allownace" -> allowance, "pention" -> pension). Token similarity =
   1 - editDistance / longerLength; a query token matches a title token at
   >= 0.7. Ranked by matched-token count then average similarity, top 3. */
function fuzzyMatches(questions, query) {
  const qTokens = query.toLowerCase().split(/[^a-z0-9]+/).filter(t => t.length >= 3 && !STOP_WORDS.has(t));
  if (!qTokens.length) return [];
  const scored = [];
  for (const q of questions) {
    const tTokens = (q.title || "").toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
    if (!tTokens.length) continue;
    let matched = 0, simSum = 0;
    for (const qt of qTokens) {
      let best = 0;
      for (const tt of tTokens) {
        if (Math.abs(tt.length - qt.length) > 3) continue;
        const sim = 1 - editDistance(qt, tt) / Math.max(qt.length, tt.length);
        if (sim > best) best = sim;
      }
      if (best >= 0.7) { matched++; simSum += best; }
    }
    if (matched > 0) scored.push({ q, matched, avg: simSum / matched });
  }
  scored.sort((a, b) => b.matched - a.matched || b.avg - a.avg);
  return scored.slice(0, 3).map(x => x.q);
}

// Command-palette destinations (⌘K reaches pages + help, not only metrics).
// Each is a route; role-gated ones are filtered per member. kind="nav" so the
// activation handlers can tell them from metric hits.
const NAV_INDEX = [
  { label: "Overview", route: "/overview", group: "Pages", kw: "home dashboard where you stand" },
  { label: "My dashboards", route: "/dashboards", group: "Pages", kw: "pinned cards saved views" },
  { label: "Signals", route: "/signals", group: "Pages", kw: "flags priorities inbox" },
  { label: "Priorities — the gap register", route: "/priorities", group: "Pages", kw: "gaps register full list export csv" },
  { label: "Pulse", route: "/pulse", group: "Pages", kw: "surveys check-ins" },
  { label: "Benchmark", route: "/benchmark", group: "Pages", kw: "all metrics categories compare" },
  { label: "Board packs", route: "/boardpack", group: "Pages", kw: "board report export pdf pack briefing" },
  { label: "Your data", route: "/your-data", group: "Pages", kw: "submit answers questionnaire enter" },
  { label: "Reward strategy", route: "/strategy", group: "Pages", role: "admin", kw: "objective market stance intent capture" },
  { label: "Team", route: "/team", group: "Pages", role: "admin", kw: "members invite roles colleagues" },
  { label: "Settings", route: "/settings", group: "Pages", kw: "assumptions sharing notifications account" },
  { label: "Company profile", route: "/profile", group: "Pages", kw: "company facts sector size region" },
  { label: "How lumi works", route: "/how-lumi-works", group: "Help", kw: "help methodology co-op legal" },
  { label: "How the numbers are calculated", route: "/how-lumi-works/calculations", group: "Help", kw: "methodology median percentile suppression method" },
  { label: "Why figures are hidden", route: "/how-lumi-works/suppression", group: "Help", kw: "suppressed hidden anonymity fewer than 5 n<5" },
  { label: "Glossary", route: "/how-lumi-works/glossary", group: "Help", kw: "terms definitions jargon percentile median" },
];

function navMatches(search, role) {
  const s = search.toLowerCase();
  return NAV_INDEX.filter(n => !n.role || n.role === role)
    .filter(n => n.label.toLowerCase().includes(s) || (n.kw || "").includes(s))
    .slice(0, 5)
    .map(n => ({ ...n, kind: "nav" }));
}

// The ordered list of activatable search options: metric hits (or fuzzy
// suggestions when none) first, then matching pages/help below. Shared by
// SearchPop (render) and the combobox keyboard handler in App, so arrow-key
// navigation and the rendered rows can never drift.
function searchOptions(qIndex, search, role) {
  const s = search.toLowerCase();
  const hits = qIndex.questions.filter(q => (q.title || "").toLowerCase().includes(s)).slice(0, 12);
  const metrics = hits.length ? hits : fuzzyMatches(qIndex.questions, search);
  return [...metrics, ...navMatches(search, role)];
}

// ⌘K zero state (2026-08-09 delight review): recents make the trained gesture
// land somewhere useful before the first keystroke.
function SearchZeroState({ qIndex, onGo }) {
  let recents = [];
  try { recents = JSON.parse(localStorage.getItem("lumi-recents") || "[]"); } catch (e) {}
  const byId = {}; (qIndex.questions || []).forEach(q => { byId[q.id] = q; });
  const rows = recents.map(id => byId[id] && { id, title: byId[id].title }).filter(Boolean).slice(0, 5);
  if (!rows.length) return null;
  return html`<div class="searchpop" role="listbox" aria-label="Recent metrics">
    <div class="searchpop-head caption">Recent</div>
    ${rows.map(r => html`<button key=${r.id} class="search-hit" role="option"
      onMouseDown=${e => { e.preventDefault(); onGo(r.id); }}
      onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onGo(r.id); } }}>${r.title}</button>`)}
  </div>`;
}

function SearchPop({ qIndex, search, role, onGo, onRequest, activeHit, onActiveHit }) {
  const s = search.toLowerCase();
  const hits = qIndex.questions.filter(q => (q.title || "").toLowerCase().includes(s)).slice(0, 12);
  const suggestions = hits.length === 0 ? fuzzyMatches(qIndex.questions, search) : [];
  const metrics = hits.length ? hits : suggestions;   // the metric rows (indices 0..M-1)
  const navs = navMatches(search, role);              // pages/help (indices M..M+N-1)
  const request = () => (onRequest ? onRequest() : window.openMetricRequest(search, "search"));
  const setActive = (i) => onActiveHit && onActiveHit(i);
  const metricRow = (q, i, extra) => html`
    <div key=${q.id} id=${"search-hit-" + i} class=${"search-hit" + (extra || "")} role="option"
      aria-selected=${activeHit === i} onMouseEnter=${() => setActive(i)} onClick=${() => onGo(q)}>
      <b style=${{ fontSize: "var(--fs-label)" }}>${q.title}</b> ${q.locked && html`<${Icon} name="lock" size=${11} style=${{ verticalAlign: "-1px", color: "var(--ink-faint)" }} />`}
      <div class="caption">${q.superpower}${q.subpower ? " · " + q.subpower : ""} · ${q.category} · ${compositionLabel(q.n, q.n_real)}</div>
    </div>`;
  return html`
    <div class="searchpop" id="searchpop-list" role="listbox" aria-label="Search results">
      ${hits.map((q, i) => metricRow(q, i))}
      ${hits.length === 0 && suggestions.length > 0 && html`
        <div class="caption" style=${{ padding: "var(--s1) 0 var(--s1) 2px" }}>Did you mean…</div>
        ${suggestions.map((q, i) => metricRow(q, i, " search-suggest"))}`}
      ${navs.length > 0 && html`
        <div class="search-divider"></div>
        <div class="caption" style=${{ padding: "0 0 var(--s1) 2px" }}>Pages & help</div>
        ${navs.map((nItem, j) => { const idx = metrics.length + j; return html`
          <div key=${nItem.route} id=${"search-hit-" + idx} class="search-hit search-nav" role="option"
            aria-selected=${activeHit === idx} onMouseEnter=${() => setActive(idx)} onClick=${() => onGo(nItem)}>
            <b style=${{ fontSize: "var(--fs-label)" }}>${nItem.label}</b>
            <div class="caption">${nItem.group}</div>
          </div>`; })}`}
      ${metrics.length === 0 && navs.length === 0 && html`
        <div class="search-empty"><div class="search-nores">
          <div class="caption">No reward metric or page matches “${search}”.</div>
          <button class="btn small" style=${{ marginTop: "var(--s2)" }} onClick=${request}>Suggest this metric</button>
        </div></div>`}
    </div>`;
}

// single-metric page (deep links from analyst chips / opportunity tile)
// Analyst/detailed view (spec §6.3): the engine's internal class/register made
// legible on the single-metric page — never on the default chip rows.
function mpReadChip(cl) {
  if (cl.register === "Approach") return { cls: "differs", text: "a practice choice" };
  if (cl.register === "Substance") {
    if (!cl.competitive_domain) return { cls: "context", text: "beside the headline" };
    if (cl.direction === "neutral") return { cls: "context", text: "context" };
    if (cl.direction === "lower_is_better") return { cls: "fav", text: "favourable when low" };
    return { cls: "headline", text: "in the headline" };
  }
  return { cls: "context", text: "tracked" };
}
function mpReadCopy(cl) {
  if (cl.register === "Approach") {
    const what = cl.cls === "Practice" ? "a practice — how, or how often, you do something"
      : "a structural choice — which approach you take";
    return "lumi reads this as a " + cl.cls + " (" + what + "). It has no better-or-worse, so it shows as "
      + "“a practice choice” and never feeds your competitiveness headline."
      + (cl.weight && cl.weight !== 1 ? " Weighted ×" + cl.weight + " for materiality." : "");
  }
  if (cl.register === "Substance") {
    const base = cl.cls === "Provision" ? "a Provision (a market benefit, compared to peer take-up)" : "a Level (a market rate)";
    const dir = cl.direction === "lower_is_better" ? "Lower is better here, so sitting below market reads as favourable, not a gap."
      : cl.direction === "neutral" ? "There’s no inherently good direction, so it’s shown as context, not a verdict — and kept out of the headline."
      : "Higher is better, so it feeds your competitiveness headline.";
    const head = cl.competitive_domain ? "lumi reads this as " + base + ". "
      : "lumi reads this as " + base + ", but governance sits beside the headline — it isn’t a competitiveness measure. ";
    return head + dir + (cl.weight && cl.weight !== 1 ? " Weighted ×" + cl.weight + " for materiality." : "");
  }
  return "lumi tracks this metric but hasn’t classified it for the competitiveness headline.";
}
// The signal that brought you here: the breadcrumb (WHY it flagged) + the SAME triage
// controls the signal carried (pin / save / snooze / dismiss), so a director can act on
// the metric from its own page instead of bouncing back to the briefing. Sourced from
// the warm /api/overview cache (you almost always arrive from it); no signal → renders
// nothing. Acts on question_id — the key signal_actions already uses.
const LENS_WORD = { save: "cost", attract: "attraction", retain: "retention", engage: "engagement" };
function MetricSignalBar({ qid, sig }) {
  // the signal lookup is lifted into MetricPage (one fetch feeds this strip AND the
  // chart's marker colour, so they can never disagree); this renders + triages only.
  const [status, setStatus] = useState(sig ? sig.status : null);
  useEffect(() => { setStatus(sig ? sig.status : null); }, [sig]);
  if (!sig) return null;
  const onSet = (sid, st, days) => {
    const prev = status;
    setStatus(st || "active");
    signalAction(qid, st, days).catch(() => {
      setStatus(prev);                                   // revert the optimistic flip
      toast("Couldn't save that — try again", "error");
    });
    if (st === "dismissed") toast("Signal dismissed", null, { label: "Undo", fn: () => onSet(qid, null) });
    else if (st === "snoozed") toast("Snoozed", null, { label: "Undo", fn: () => onSet(qid, null) });
  };
  const word = LENS_WORD[sig.lens];
  return html`
    <div class="metric-sigbar">
      <span class=${"signal-roundel lens-" + sig.lens}><${Icon} name=${LENS_ICON[sig.lens] || "flag"} size=${14} /></span>
      <div class="metric-sigbar-txt">
        <b>Flagged in your signals</b>${word ? " — for " + word : ""}${sig.risk_framed ? " · a risk floor" : ""}
        ${sig.stand || sig.detail ? html`<span class="caption"> · ${sig.stand || sig.detail}</span>` : null}
      </div>
      <${SignalActions} status=${status === "active" ? null : status} sid=${qid} onSet=${onSet} />
    </div>`;
}

function MetricPage({ qid, me, cut, cuts, prefs, onPref, onPin, pinnedIds }) {
  const org = me.org;
  // the page's own cut — initialised from the global selector / deep link,
  // and re-synced when the global selector changes (same semantics as cards)
  const globalSel = cut.dim === "industry" ? { dim: "industry", value: cut.value || org.industry }
    : cut.dim === "fte_band" ? { dim: "fte_band", value: cut.value || org.fte_band }
    : cut.dim === "twin" ? { dim: "twin", value: null }
    : cut.dim === "group" ? { dim: "group", value: cut.value }
    : { dim: "all", value: null };
  const [sel, setSel] = useState(globalSel);
  const [card, setCard] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const [retryTick, setRetryTick] = useState(0);     // in-place retry (no full reload)
  // chart preference round-trips with the benchmark card: saved pref first, then the
  // session fallback (viewers can't persist prefs but still keep their choice locally)
  const [chartSel, setChartSel] = useState(() => {
    const saved = ((prefs || {})[qid] || {}).chart;
    if (saved) return saved;
    try { return sessionStorage.getItem("lumi-chart-pref:" + qid); } catch (e) { return null; }
  });
  const [showInfo, setShowInfo] = useState(false);   // on-demand definition & methodology (the chart's info tool)
  const [sig, setSig] = useState(null);              // this metric's live signal — feeds the sigbar AND the marker colour
  const chartRef = useRef(null);
  const genRef = useRef(null);                       // in-flight commentary generate (one-pager awaits it)
  useEffect(() => {
    let dead = false;
    apiCached("/api/overview").then(o => {
      if (dead) return;
      setSig((o.signals_all || []).find(x => x.question_id === qid && x.status !== "dismissed") || null);
    }).catch(() => {});
    return () => { dead = true; };
  }, [qid]);
  // the browser tab / history entry names the metric, not just "Metric"
  useEffect(() => { if (card && card.title) document.title = card.title + " · lumi"; }, [card && card.title]);
  // primary narrative state, lifted here (was inside MetricCommentary) so the one-pager
  // can ENSURE the commentary is written before it opens the print dialog.
  const [commentary, setCommentary] = useState(null);
  const [cmBusy, setCmBusy] = useState(false);
  const [cmErr, setCmErr] = useState(null);
  // hydrate an existing (AI or edited) commentary on load — peek never generates, so a
  // saved edit reappears on return and the CTA can't silently overwrite it.
  useEffect(() => {
    setCommentary(null); setCmErr(null);
    // §4.10(1): only peek when commentary is enabled — with the feature off there is no
    // generate/save path, so nothing exists to hydrate, and the call would 403 on every load.
    if (!(me.features && me.features.commentary)) return;
    let dead = false;
    api("/api/metric-commentary", { method: "POST",
      body: { question_id: qid, cut: sel.dim, cut_value: sel.value, peek: true } })
      .then(r => { if (!dead && r && r.parts) setCommentary(r); })
      .catch(() => {});
    return () => { dead = true; };
  }, [qid, sel.dim, sel.value]);
  useEffect(() => { setSel(globalSel); }, [cutKeyOf(cut)]);
  useEffect(() => {
    let dead = false;
    setBusy(true); setErr(null);
    const qs = "cut=" + encodeURIComponent(sel.dim) + (sel.value ? "&cut_value=" + encodeURIComponent(sel.value) : "");
    api(`/api/benchmark/${qid}?` + qs)
      .then(d => {
        if (dead) return;
        setCard(d);
        // the server resolves an unknown/deleted peer group to all-peers and echoes the
        // resolved cut — adopt it, or staleCut stays true forever (permanent dim, dead
        // exports) beside a selector naming a group that no longer exists
        if (d && d.cut && !d.reduced && d.cut.dim === "all" && sel.dim === "group") {
          setSel({ dim: "all", value: null });
          toast("That peer group no longer exists — showing All peers.");
        }
      })
      .catch(e => { if (!dead) setErr(e.message); })
      .finally(() => { if (!dead) setBusy(false); });
    return () => { dead = true; };
  }, [qid, sel.dim, sel.value, retryTick]);
  if (err) return html`<${EmptyState} tone="error" icon="info" title="Couldn't load this metric"
    body=${String(err).replace(/\.$/, "") + " — nothing is lost."}
    action=${html`<button class="btn small primary" onClick=${() => { setErr(null); setRetryTick(t => t + 1); }}>Retry</button>`} />`;
  // first load only — one skeleton mirroring the page silhouette (utility row, title, hero card).
  // A peer-group change never comes back here: the frame stays mounted and the chart dims.
  if (!card || card.id !== qid) return html`
    <div class="metric-page">
      <div class="skel" style=${{ height: "28px", width: "100%", maxWidth: "560px", marginBottom: "var(--s4)" }}></div>
      <div class="skel" style=${{ height: "34px", width: "100%", maxWidth: "440px", marginBottom: "var(--s2)" }}></div>
      <div class="skel" style=${{ height: "16px", width: "100%", maxWidth: "520px", marginBottom: "var(--s4)" }}></div>
      <div class="skel" style=${{ height: "520px", borderRadius: "var(--radius)" }}></div>
    </div>`;

  const c = card;
  // reduced (paused) org on a non-sample metric: the server sends a minimal payload with
  // no block/you — the grid guards this (card.js), and without the same guard here a
  // numeric metric dereferences block.p10 and white-screens the whole app
  if (c.reduced) return html`
    <div class="metric-page">
      <button class="btn quiet small" onClick=${() => nav("/benchmark")}>← Back</button>
      <${ReducedCard} card=${c} />
    </div>`;
  // a cut change re-fetches into the SAME frame: dim the chart + disable exports while
  // the new figures load, but never unmount the selector the user is holding
  const staleCut = c.cut && (c.cut.dim !== sel.dim || (c.cut.value || null) !== (sel.value || null));
  const busyNow = busy || staleCut;
  const pos = cardPosition(c);
  const exportable = !c.suppressed && !(c.type === "matrix" && (c.matrix_rows || []).every(r => r.suppressed));   // only a drawn chart can copy/download
  // the marker colour follows the FLAG when this metric carries a live signal (same rule
  // as the cards, card.js cardFav) — the sigbar and the chart can never disagree
  const cfav = (typeof cardFav === "function" ? cardFav(c, sig) : null) || (pos ? pos.kind : null);
  const aim = metricAim(c, pos);   // strategy read-through: this metric vs the org's declared domain aim
  const sent = humanSentence(c);
  // honest chart options only (curated per data type); the session preference
  // applies only where valid — normaliseChart falls back to this metric's default
  const alts = chartAlternatives(c);
  const chart = normaliseChart(c, chartSel);
  const pickChart = (t) => {
    setChartSel(t);
    try { sessionStorage.setItem("lumi-chart-pref:" + qid, t); } catch (e) {}
    // persist alongside the card prefs — MUST spread the existing per-metric pref
    // object (onPref replaces it wholesale, so a bare {chart} would clobber p1090/values)
    if (onPref) onPref(qid, { ...((prefs || {})[qid] || {}), chart: t });
  };
  const period = (me.snapshots && me.snapshots[0] && me.snapshots[0].collection_window) || "";
  const backTo = "/benchmark" + (c.subpower ? "?cat=" + encodeURIComponent(c.subpower) : "");
  const goBack = () => {
    let hasReturn = false;
    try { hasReturn = !!sessionStorage.getItem("lumi-return"); } catch (e) {}
    if (hasReturn) window.history.back(); else nav(backTo);
  };
  const selKey = sel.dim + (sel.value ? "::" + sel.value : "");
  const setCutKey = (k) => {
    if (k === "all") setSel({ dim: "all", value: null });
    else if (k === "twin") setSel({ dim: "twin", value: null });
    else { const [dim, value] = k.split("::"); setSel({ dim, value }); }
  };
  // company default at the TOP of the selector, labelled "Company Default" — consistent with the
  // app-wide PeerSetBar (David 2026-08-12). me.org.signal_peer_cut is the org's default peer group;
  // it's lifted out of its category list below so it shows once, at the top.
  const bandLow = s => { const m = String(s).replace(/,/g, "").match(/\d+/); return m ? parseInt(m[0], 10) : 0; };
  const hasDefault = !!(me.org && me.org.signal_peer_cut && me.org.signal_peer_cut !== "all");
  const defCut = hasDefault ? me.org.signal_peer_cut : "all";
  const defGid = defCut.indexOf("group::") === 0 ? defCut.slice(7) : null;
  const defGroup = defGid && ((cuts && cuts.groups) || []).find(g => g.group_id === defGid);
  const defCount = defGroup ? defGroup.match_count
    : defCut.indexOf("industry::") === 0 ? ((cuts && cuts.industries) || {})[defCut.slice(10)]
    : defCut.indexOf("fte_band::") === 0 ? ((cuts && cuts.fte_bands) || {})[defCut.slice(10)]
    : defCut === "twin" ? (cuts && cuts.twin_n) : null;
  const poolN = (me.peer_pool || {}).responding_orgs;
  const defOptLabel = hasDefault ? "Company Default" + (defCount != null ? " · " + defCount : "") : "All peers" + (poolN ? " · " + poolN : "");
  const profiled = !!(org.industry && org.fte_band);
  const exportMeta = () => ({
    title: c.title, cutLabel: c.cut.label, n: c.n, n_real: c.n_real, window: period, card: c, org: (window.__orgName || ""),
    suffix: c.you && c.you.percentile != null ? `You: ${c.you.display} (${pLabel(c.you.percentile)})` : null,
  });
  const doExport = async () => {
    try {
      const res = await exportCardPNG(chartRef.current, exportMeta(), "download");
      toast(res === "downloaded" ? `Chart downloaded — labelled ${c.cut.label}, ${compositionLabel(c.n, c.n_real)}` : "Nothing to export yet");
    } catch (e) { toast("Couldn't export the chart here.", "error"); }
  };
  const doCopy = async () => {
    try {
      const res = await exportCardPNG(chartRef.current, exportMeta(), "clipboard");
      if (res === "copied") toast(`Chart copied — labelled ${c.cut.label}, ${compositionLabel(c.n, c.n_real)}`);
      else if (res === "downloaded") toast(`Copy isn't available here — downloaded the chart instead (${c.cut.label}, ${compositionLabel(c.n, c.n_real)})`);
      else toast("Nothing to export yet");
    } catch (e) {
      try { const res = await exportCardPNG(chartRef.current, exportMeta(), "download");
        toast(res === "downloaded" ? `Copy failed — downloaded the chart instead (${c.cut.label}, ${compositionLabel(c.n, c.n_real)})` : "Nothing to export yet"); }
      catch (e2) { toast("Couldn't copy the chart here.", "error"); }
    }
  };
  const share = async () => {
    // same serialisation as cutToURL: twin is the bare token — "twin::" parses back
    // as {dim:'all'} and the recipient silently lands on the wrong peer set
    const cutPart = selKey !== "all" ? "?cut=" + encodeURIComponent(sel.dim === "twin" ? "twin" : sel.dim + "::" + (sel.value || "")) : "";
    const url = window.location.href.split("#")[0] + "#/metric/" + qid + cutPart;
    // the toast must not lie: confirm the write landed, else hand the link over manually
    try { await navigator.clipboard.writeText(url); toast("Link copied — opens this metric on " + c.cut.label); }
    catch (e) { window.prompt("Copy this link", url); }
  };
  const genCommentary = (force) => {
    if (cmBusy) return genRef.current;   // already writing — share the in-flight promise
    setCmBusy(true); setCmErr(null);
    const p = api("/api/metric-commentary", { method: "POST",
        body: { question_id: qid, cut: sel.dim, cut_value: sel.value, force: !!force } })
      .then(r => { setCommentary(r); return r; })
      .catch(e => { setCmErr(e.message); return null; })
      .finally(() => { setCmBusy(false); genRef.current = null; });
    genRef.current = p;
    return p;
  };
  // save a member-edited commentary — the org's own words become the stored draft
  const saveCommentary = async (parts) => {
    const r = await api("/api/metric-commentary/save", { method: "POST",
      body: { question_id: qid, cut: sel.dim, cut_value: sel.value, parts } });
    setCommentary(r); return r;
  };
  // One-pager (PDF): the written story is the CENTREPIECE, so ensure it's generated
  // first (AI when live, deterministic keyless — the endpoint always returns a
  // structured read), then print. Already generated → prints straight away. The
  // chart-only PNG (doExport) stays. Reuses the browser print pipeline (pulse/board
  // pack pattern) — no new dependency, no server round-trip.
  const printMetric = async () => {
    if (!commentary && me.features && me.features.commentary) {
      toast("Writing your commentary for the one-pager…");
      // await the IN-FLIGHT generate if one is already running, else start one; an
      // honest fallback when the write fails (the deterministic read still prints)
      const r = await (genRef.current || genCommentary(false));
      if (!r) toast("Couldn't write the commentary — printing the standard read.", "error");
      await new Promise(res => requestAnimationFrame(() => requestAnimationFrame(res)));   // let it paint
    }
    const t = document.title;
    document.title = "lumi — " + c.title + " · one-pager";
    window.print();
    setTimeout(() => { document.title = t; }, 500);
  };

  return html`
    <div class="metric-page">
      ${/* print-only masthead for the one-pager PDF (hidden on screen) */ ""}
      <div class="metric-pdf-head" aria-hidden="true">
        <span class="logo">lumi<span>.</span></span> · Metric one-pager · ${c.cut.label} · ${compositionLabel(c.n, c.n_real)}${c.base ? " · of " + c.base.label : ""}${period ? " · " + period : ""}</div>
      ${/* one slim utility row: Back (named for its destination) + the peer selector —
            merged so the title lands sooner (David fork 2026-08-12) */ ""}
      <div class="row spread no-print metric-utility">
        <button class="btn quiet" style=${{ flex: "none" }} onClick=${goBack}>← ${c.subpower || "Benchmarks"}</button>
        <div class="peerbar" style=${{ margin: 0 }}>
        <span class="peerbar-lead"><${Icon} name="users" size=${13} /> Comparing against</span>
        <span class=${"peerbar-pill" + (selKey !== "all" ? " narrowed" : "")}
          title=${!profiled ? "Sector, size and bespoke comparisons unlock once your company profile is complete — add it under Settings → Company profile." : undefined}>
          <span class="peerbar-selwrap">
            <select aria-label="Peer group for this metric" class="peer-ctl" value=${selKey} onChange=${e => setCutKey(e.target.value)}>
              ${/* order kept consistent with the app-wide PeerSetBar (David 2026-08-12):
                    Company Default → All peers → your groups → sectors → size → similar orgs. */ ""}
              <option value=${defCut}>${defOptLabel}</option>
              ${hasDefault && html`<option value="all">All peers${poolN ? " · " + poolN : ""}</option>`}
              ${cuts && (cuts.groups || []).filter(g => ("group::" + g.group_id) !== defCut).length > 0 && html`
                <optgroup label="Your groups">
                  ${cuts.groups.filter(g => ("group::" + g.group_id) !== defCut).map(g => html`<option key=${g.group_id} value=${"group::" + g.group_id}>${g.name}</option>`)}
                </optgroup>`}
              ${cuts && Object.keys(cuts.industries || {}).length > 0 && html`
                <optgroup label="Compare a sector">
                  ${org.industry && ("industry::" + org.industry) !== defCut && html`<option value=${"industry::" + org.industry}>Your sector: ${org.industry}</option>`}
                  ${sel.dim === "industry" && sel.value && sel.value !== org.industry && !(cuts.industries || {})[sel.value] && html`<option value=${"industry::" + sel.value}>${sel.value}</option>`}
                  ${Object.keys(cuts.industries).filter(i => i !== org.industry && ("industry::" + i) !== defCut).sort().map(i => html`<option key=${i} value=${"industry::" + i}>${i} · ${cuts.industries[i]}</option>`)}
                </optgroup>`}
              ${cuts && Object.keys(cuts.fte_bands || {}).length > 0 && html`
                <optgroup label="Compare a size band">
                  ${org.fte_band && ("fte_band::" + org.fte_band) !== defCut && html`<option value=${"fte_band::" + org.fte_band}>Your size: ${org.fte_band} FTE</option>`}
                  ${sel.dim === "fte_band" && sel.value && sel.value !== org.fte_band && !(cuts.fte_bands || {})[sel.value] && html`<option value=${"fte_band::" + sel.value}>${sel.value} FTE</option>`}
                  ${Object.keys(cuts.fte_bands).filter(b => b !== org.fte_band && ("fte_band::" + b) !== defCut).sort((x, y) => bandLow(x) - bandLow(y)).map(b => html`<option key=${b} value=${"fte_band::" + b}>${b} FTE · ${cuts.fte_bands[b]}</option>`)}
                </optgroup>`}
              ${cuts && cuts.twin_available && defCut !== "twin" && html`<option value="twin">Organisations like you${typeof cuts.twin_n === "number" ? " · " + cuts.twin_n : ""}</option>`}
            </select>
            <span class="peerbar-caret"><${Icon} name="chevron-down" size=${13} /></span>
          </span>
        </span>
        <span class="peerset-note">${compositionLabel(c.n, c.n_real)}${c.base ? html`<span class="base-note" title="This metric applies to a subset of organisations — the chart and n cover only those where it applies."> · of ${c.base.label}${c.base.excluded ? ` · ${c.base.excluded} not-applicable excluded` : ""}</span>` : ""}</span>
        </div>
      </div>
      <${MetricSignalBar} qid=${qid} sig=${sig} />

      <div class="card metric-hero-card" aria-busy=${busyNow ? "true" : "false"} style=${{ padding: "var(--s5)", marginTop: "var(--s4)" }}>
        ${/* CARD HEAD (David 2026-08-12): the chart's title lives IN the card, and every
              metric carries a clear market indicator — below / on / above market — with
              the strategy-alignment chip beside it. No-verdict states stay ruled and
              honest: Protected (suppressed), No comparison (unbenchmarked), Context
              (neutral/approach), Not yet answered. Tips are keyboard-reachable. */ ""}
        <div class="metric-card-head">
          <div class="metric-card-titles">
            <h1 class="metric-card-title">${c.title}</h1>
            <p class="caption" style=${{ margin: 0, maxWidth: "640px" }}>${c.question_text}</p>
          </div>
          <div class="metric-verdicts">
            ${c.suppressed
              ? html`<span class="ctx-chip hastip" tabindex="0">Protected<span class="tip">Fewer than 5 organisations in this peer group answered — figures this thin are never shown, so there's no market verdict to give.</span></span>`
              : c.unbenchmarked && !c.practice
              ? html`<span class="ctx-chip hastip" tabindex="0">No comparison<span class="tip">No verified market anchor yet — the distribution is shown for information; no market verdict renders until this metric is anchored.</span></span>`
              : c.practice
              ? html`<span class="ctx-chip hastip" tabindex="0">A practice choice
                  <span class="prac-band">· ${c.prevalence_band === "match" ? "common"
                    : c.prevalence_band === "common_alt" ? "alternative"
                    : c.prevalence_band === "rarer" ? "rare" : "low peer data"}</span>
                  <span class="tip">${c.prevalence_band === "match" ? "Your choice is the market's most common answer here."
                    : c.prevalence_band === "common_alt" ? "Your choice is an established alternative — off the mode, but well represented among peers."
                    : c.prevalence_band === "rarer" ? "Your choice is rare among peers — worth being deliberate about."
                    : "A how-you-do-it choice — too few peers in this group to grade how common yours is."} A practice has no better-or-worse — lumi shows how common your choice is, never a verdict.</span></span>`
              : c.classification && (c.classification.direction === "neutral" || c.classification.register === "Approach")
              ? html`<span class="ctx-chip hastip" tabindex="0">Context<span class="tip">${c.classification.register === "Approach"
                  ? "lumi reads this as an approach — how, or how often, you do something. It has no better-or-worse, so it's shown as context, not an above/below-market verdict."
                  : "This metric has no inherently good or bad direction — lumi shows it as context to weigh, not an above/below-market verdict."}</span></span>`
              : pos
              ? html`<span class=${"pos-pill lg hastip " + pos.kind + (pos.kind === "good" ? " pill-glow" : "")} tabindex="0">${pos.arrow} ${pos.label}<span class="tip">${pos.tip}</span></span>`
              : c.you_na
              ? html`<span class="ctx-chip hastip" tabindex="0">Doesn't apply to you<span class="tip">Your answer says this doesn't apply to your organisation — so there's no market position to give. The peer distribution is shown for context.</span></span>`
              : (c.you || (c.matrix_rows || []).some(r => r.you))
              ? html`<span class="ctx-chip hastip" tabindex="0">Not yet rated<span class="tip">Your answer is in — this answer type doesn't carry a market rating yet, so the distribution is shown for information.</span></span>`
              : html`<a class="btn small primary" href=${qHref(c)}
                  title=${c.is_required ? "A key question that unlocks your insights — answer it to see where you stand." : "Answer this question to see whether you're below, on or above the market."}>
                  <${Icon} name=${c.locked ? "lock" : "pencil"} size=${13} /> Add your answer</a>`}
            ${aim && html`<${AlignmentChip} target=${aim} />`}
          </div>
        </div>
        ${/* THE READ, as one column (David fork 2026-08-12): the narrative lead → your
              numbers → the chart. The lead is the AI narrative's "How you compare" part
              (David 2026-08-12: the position description comes from the AI narrative,
              not the deterministic sentence) — hydrated by the commentary peek, shown
              only once it exists; the commentary card below skips the lifted part. */ ""}
        ${!c.suppressed && commentary && commentary.parts && commentary.parts.compare
          ? html`<p class="metric-lead"><${Icon} name="sparkle" size=${15} style=${{ flex: "none", color: "var(--blue)", marginTop: "5px" }} /><span>${commentary.parts.compare}</span></p>` : null}
        ${(() => {
          const showStats = c.type === "numeric" && c.you && !c.suppressed;
          const showSwitch = exportable && alts.length > 1;
          if (!showStats && !showSwitch) return null;
          const youInk = cfav === "good" ? "var(--favourable-ink)" : cfav === "bad" ? "var(--unfavourable-ink)" : "var(--you)";
          return html`<div class="row spread metric-statrow">
            <div class="metric-stats">
              ${showStats && html`
                <div class="metric-stat">
                  <span class="caption">You${c.you.percentile != null ? " · " + pLabel(c.you.percentile) : ""}</span>
                  <div class="metric-value" style=${{ color: youInk }}>${stripUnit(c.you.display, c.unit)}<span class="unit">${unitSuffix(c.unit)}</span></div>
                </div>
                ${c.block && c.block.p50 != null && html`<div class="metric-stat mkt">
                  <span class="caption">Market <${Term} word="median">median<//></span>
                  <div class="metric-value">${fmtValue(c.block.p50, c.unit)}</div>
                </div>`}`}
            </div>
            ${showSwitch && html`
              <div class="chart-switch" role="group" aria-label="Chart type">
                ${alts.map(t => html`
                  <button key=${t} class=${"chart-switch-btn" + (chart === t ? " on" : "")}
                    aria-pressed=${chart === t} onClick=${() => pickChart(t)}>${CHART_LABELS[t] || t}</button>`)}
              </div>`}
          </div>`;
        })()}
        <div class=${"metric-stage" + (busyNow ? " busy" : "")}>
          <div class="metric-xl" ref=${chartRef}>
            ${c.suppressed ? html`
              <${EmptyState} icon="shield" title="Not enough organisations to show this safely"
                body=${"Fewer than 5 organisations in this peer group (" + c.cut.label + ") answered this question. Try a broader peer group."}
                action=${html`<div class="row" style=${{ gap: "var(--s3)", alignItems: "center", justifyContent: "center", flexWrap: "wrap" }}>
                  ${selKey !== "all" ? html`<button class="btn small primary" onClick=${() => setCutKey("all")}>Compare against all peers</button>` : null}
                  <a class="caption" href="#/how-lumi-works/suppression">Why figures are hidden</a></div>`} />` :
            html`<div key=${chart} class="metric-chart-swap" role="img"
              aria-label=${c.title + " chart. " + (sent.lead || "Peer benchmark distribution.") + " Based on " + c.n + " " + compositionNoun(c.n_real) + ", " + c.cut.label + "."}>
              <${CardBody} card=${c} chart=${chart} showP1090=${true} showValues=${true} fav=${cfav} xl=${true} />
            </div>`}
          </div>
        </div>
        ${/* one closing band: the analyst's figures + the quick tools under a single hairline */ ""}
        <div class="metric-foot-band">
          ${!c.suppressed && html`<${ExactFigures} card=${c} pos=${cfav} skipYou=${c.type === "numeric" && !!c.you} />`}
          <div class="card-tools no-print">
            <button class=${"iconbtn" + (showInfo ? " on" : "")} title="Definition & methodology" aria-label="Definition & methodology" aria-expanded=${showInfo} aria-controls="metric-info" onClick=${() => setShowInfo(v => !v)}><${Icon} name="info" size=${15} /></button>
            ${exportable && html`<button class="iconbtn" disabled=${busyNow} title="Copy chart to clipboard" aria-label="Copy chart" onClick=${doCopy}><${Icon} name="copy" size=${15} /></button>`}
            ${exportable && html`<button class="iconbtn" disabled=${busyNow} title="Download chart (PNG)" aria-label="Download chart" onClick=${doExport}><${Icon} name="download" size=${15} /></button>`}
            <button class="iconbtn" title=${"Copy link · " + c.cut.label} aria-label="Copy link" onClick=${share}><${Icon} name="link" size=${15} /></button>
            ${!c.suppressed && html`<button class="iconbtn" disabled=${busyNow} title="Print or save a one-page PDF — the chart plus your written commentary." aria-label="One-pager PDF" onClick=${printMetric}><${Icon} name="file-text" size=${15} /></button>`}
            ${onPin && pinnedIds && html`<button class=${"iconbtn" + (pinnedIds.has(qid) ? " on" : "")} onClick=${() => onPin(qid)}
              title=${pinnedIds.has(qid) ? "Remove this metric from your dashboard" : "Pin this metric to your dashboard"}
              aria-label=${pinnedIds.has(qid) ? "Unpin from dashboard" : "Pin to dashboard"} aria-pressed=${pinnedIds.has(qid)}><${Icon} name="pin" size=${15} /></button>`}
          </div>
        </div>
        ${showInfo && html`
          <div class="metric-info-reveal" id="metric-info" style=${{ marginTop: "var(--s3)" }}>
            ${c.definition && html`<p class="caption" style=${{ margin: "0 0 var(--s2)" }}>${c.definition}</p>`}
            ${c.help_text && html`<p class="caption" style=${{ margin: "0 0 var(--s2)" }}>${c.help_text}</p>`}
            <p class="caption" style=${{ margin: 0 }}><${Term} word="percentile">Percentiles<//> use linear interpolation across all valid peer answers; medians, not averages. Figures resting on fewer than 5 organisations are ${" "}<a href="#/how-lumi-works/suppression">suppressed</a>. ${" "}<a href="#/how-lumi-works/calculations">How this is calculated</a>.</p>
          </div>`}
      </div>

      ${/* THE primary read — promoted directly under the chart (2026-07-06). Always
            present: a deterministic aim-aware base line, upgraded by Generate to the
            full structured commentary. The standalone "What this means for you" card
            is retired into this. Shown whenever AI is available OR there's a
            deterministic read to give (practice metrics only get the AI version). */ ""}
      ${!c.suppressed ? html`
        <${MetricCommentary} commentary=${commentary} busy=${cmBusy} err=${cmErr} onGenerate=${genCommentary}
          onSave=${saveCommentary} canEdit=${!!(me.user && me.user.role !== "viewer")}
          pos=${pos} card=${c} featureOn=${!!(me.features && me.features.commentary)}
          omitPart=${!c.suppressed && commentary && commentary.parts && commentary.parts.compare ? "compare" : null} />` : null}

      <${MetricTrend} qid=${qid} />

      ${/* "About this metric" (definition / methodology / classification / suggest) removed from the
            metric page per David 2026-08-12 — the question sits under the title; methodology lives in
            How-lumi-works and the global "Suggest a metric". */ ""}
      ${c.subpower ? html`<div class="caption no-print" style=${{ margin: "var(--s4) 0" }}>
        From the <a href=${"#" + backTo}>${c.subpower}</a> category.
      </div>` : null}
      ${/* print-only source line for the one-pager PDF (hidden on screen) */ ""}
      <div class="metric-pdf-foot" aria-hidden="true">
        Source: lumi HR${period ? " · " + period : ""} · generated ${fmtDate()} · Percentiles use linear interpolation across all valid peer answers; peer groups under 5 organisations are suppressed.${(me.peer_pool || {}).responding_orgs ? html`
        Comparison pool: ${me.peer_pool.responding_orgs} UK organisation profiles. See lumihr.co.uk methodology for sources.` : ""}</div>
    </div>`;
}

/* AI commentary: on-demand, per metric + cut, grounded server-side and
   validated before anything is shown. Framed to sanity-check, not to obey. */
// PRIMARY interpretation card — "What this means for you". Presentational (2026-07-06):
// MetricPage owns generate/save so the one-pager can ensure it's written before print.
// Base = the deterministic aim-aware read; Generate upgrades to the AI-drafted 4-part
// commentary; EDIT (2026-07-07) lets a member reshape the draft into their own reviewed
// note — advice and recommendations they OWN (server stores source='edited', unvalidated
// for directives, deliberately: the human owns their words).
const CM_PARTS = [["measures", "What this measures"], ["compare", "How you compare"],
                  ["implications", "Implications"], ["considerations", "Recommendations"]];
function MetricCommentary({ commentary, busy, err, onGenerate, onSave, canEdit, pos, card, featureOn, omitPart }) {
  const data = commentary;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);
  const [saving, setSaving] = useState(false);
  const edited = data && data.source === "edited";
  const detBase = !data && pos && !card.suppressed && window.meaningLines ? window.meaningLines(card, pos) : null;
  const startEdit = () => { setDraft({ ...(data.parts || {}) }); setEditing(true); };
  const doSave = async () => {
    setSaving(true);
    try { await onSave(draft); setEditing(false); toast("Commentary saved — this is now your note."); }
    catch (e) { toast(e.message || "Couldn't save", "error"); }
    setSaving(false);
  };
  const regen = () => {
    if (edited && !window.confirm("Regenerating replaces your edited version with a fresh AI draft. Continue?")) return;
    onGenerate(true);
  };
  // feature off + nothing to say = say nothing: a full card announcing an interpretation
  // ISN'T here would only dilute the chart it follows
  if (!featureOn && !detBase && !data && !busy) return null;
  return html`
    <div class=${"card metric-commentary" + (data || detBase ? " has-narrative" : "")} style=${{ padding: "var(--s5)", marginTop: "var(--s4)" }}>
      <div class="row spread" style=${{ alignItems: "flex-start" }}>
        <h2 class="section-title" style=${{ marginBottom: 0 }}><${Icon} name="sparkle" size=${14} /> What this means for you</h2>
        ${edited ? html`<span class="chip" style=${{ background: "var(--blue-tint)", color: "var(--blue-deep)" }}>Edited by your team</span>`
          : data ? html`<span class="chip warn no-print">AI draft — review &amp; edit</span>` : null}
      </div>
      ${detBase && html`<p style=${{ margin: "var(--s2) 0 0" }}>${detBase}</p>`}
      ${/* a failed generate/regenerate is visible in EVERY state, not only pre-first-draft */ ""}
      ${err && !busy && html`<div class="error-text no-print" style=${{ margin: "var(--s2) 0 0" }}>${err}</div>`}
      ${!data && !busy && featureOn && html`
        <p class="caption commentary-cta no-print" style=${{ marginTop: detBase ? "var(--s3)" : "var(--s2)" }}>A structured interpretation drafted from the figures on this page — yours to review and edit.</p>
        <button class="btn primary no-print" onClick=${() => onGenerate(false)}><${Icon} name="sparkle" size=${13} /> Generate commentary</button>`}
      ${busy && html`<div class="row" style=${{ padding: "var(--s4) 0" }}><${Spinner} /> <span class="caption">Reading the figures on this page…</span></div>`}
      ${data && !editing && html`
        <div style=${{ marginTop: "var(--s3)" }}>
          ${/* omitPart = a part lifted to the top of the chart card (the lead) — shown
                once there, still editable here in edit mode */ ""}
          ${CM_PARTS.map(([k, label]) => k !== omitPart && data.parts[k] && html`
            <div key=${k} style=${{ marginBottom: "var(--s3)" }}>
              <div class="caption" style=${{ fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", fontSize: "var(--fs-micro)" }}>${label}</div>
              <p style=${{ margin: "2px 0 0", whiteSpace: "pre-wrap" }}>${data.parts[k]}</p>
            </div>`)}
          <div class="caption metric-cm-foot" style=${{ borderTop: "1px solid var(--border)", paddingTop: "var(--s2)" }}>
            ${edited
              ? html`Your organisation's own words${data.edited_by ? " — edited by " + data.edited_by : ""}${data.edited_at ? " · " + fmtDate(data.edited_at + "Z") : ""}. Consider your own context and seek professional input where relevant.`
              : "An AI-drafted starting point — edit it into your own advice, or take it as a prompt for your own judgement. Consider your own context and seek professional input where relevant."}
          </div>
          <div class="row no-print" style=${{ marginTop: "var(--s2)", gap: "var(--s2)", flexWrap: "wrap" }}>
            ${canEdit && html`<button class="btn small" onClick=${startEdit}><${Icon} name="pencil" size=${13} /> Edit</button>`}
            <button class="btn small quiet" onClick=${regen}>Regenerate</button>
            ${data.cached && !edited && html`<span class="caption">Regenerates automatically when the figures change.</span>`}
          </div>
        </div>`}
      ${data && editing && html`
        <div style=${{ marginTop: "var(--s3)" }}>
          <p class="caption" style=${{ marginTop: 0 }}>Edit any section — write it in your own words, including advice and recommendations. This becomes your organisation's saved note (it replaces the AI draft) and appears on the one-pager.</p>
          ${CM_PARTS.map(([k, label]) => html`
            <div key=${k} style=${{ marginBottom: "var(--s3)" }}>
              <label class="caption" htmlFor=${"cm-edit-" + k} style=${{ fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", fontSize: "var(--fs-micro)", display: "block", marginBottom: "2px" }}>${label}</label>
              <textarea class="ctl metric-cm-edit" id=${"cm-edit-" + k} rows=${3} value=${draft[k] || ""}
                onInput=${e => setDraft(d => ({ ...d, [k]: e.target.value }))}></textarea>
            </div>`)}
          <div class="row" style=${{ gap: "var(--s2)" }}>
            <button class="btn primary small" disabled=${saving} onClick=${doSave}>${saving ? "Saving…" : "Save your commentary"}</button>
            <button class="btn quiet small" disabled=${saving} onClick=${() => setEditing(false)}>Cancel</button>
          </div>
        </div>`}
    </div>`;
}

/* Exact figures: the analyst's row — your value, percentile, market quartiles, n.
   pos = the marker's fav read ("good"/"bad"/…) so the You figure matches the chart
   marker exactly; skipYou drops the You cell when the hero stat pair already shows it. */
function ExactFigures({ card: c, pos, skipYou }) {
  const cells = [];
  if (c.type === "numeric" && c.block) {
    if (!skipYou && c.you && c.you.display != null) cells.push(["You", c.you.display + (c.you.percentile != null ? " · " + pLabel(c.you.percentile) : ""), "you"]);
    // full P10–P90 spread (was P25/50/75 only) — the board pack prints P10/P90, so
    // the screen a director checks it against now shows the same tails. Same n≥10
    // graduated-display rule the pack uses, so a thin sample never over-claims.
    const cols = c.n >= 10
      ? [["p10", "Market P10"], ["p25", "Market P25"], ["p50", "Market median"], ["p75", "Market P75"], ["p90", "Market P90"]]
      : [["p25", "Market P25"], ["p50", "Market median"], ["p75", "Market P75"]];
    for (const [k, lbl] of cols) {
      if (c.block[k] != null) cells.push([lbl, fmtValue(c.block[k], c.unit)]);
    }
  } else if (c.block && c.block.options) {
    if (c.you && c.you.label) {
      const mine = c.block.options.find(o => o.label === c.you.label);
      cells.push(["Your answer", c.you.label + (mine ? ` (${mine.pct}% of the market)` : ""), "you"]);
    }
    const top = [...c.block.options].sort((a, b) => b.pct - a.pct)[0];
    if (top) cells.push(["Most common", `${top.label} (${top.pct}%)`]);
  }
  cells.push(["Peer group", compositionLabel(c.n, c.n_real)]);
  if (cells.length === 1) return null;   // a lone n row (matrix metrics) isn't a strip — the peerbar already shows it
  const youInk = pos === "good" ? "var(--favourable-ink)" : pos === "bad" ? "var(--unfavourable-ink)" : "var(--you)";
  return html`
    <div class="exact-figs">
      ${cells.map(([k, v, cls], i) => html`<div key=${i} class=${cls || ""}><span class="caption">${k}</span><b class="num" style=${cls === "you" ? { color: youInk } : null}>${v}</b></div>`)}
    </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${ErrorBoundary}><${App} /><//>`);
