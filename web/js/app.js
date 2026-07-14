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
   AdminConsolePage, NotFoundPage */

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
const CUT_ROUTES = ["/overview", "/benchmark", "/superpower", "/myview", "/dashboards", "/metric", "/priorities", "/category/"];
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
      ["/profile", "Your profile"], ["/how-lumi-works", "How lumi works"], ["/admin", "Console"],
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
      document.title = hit ? hit[1] + " · lumi" : "lumi · UK reward benchmarking";
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
  const [activeHit, setActiveHit] = useState(-1);  // combobox: active option index (-1 = none)
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
    api("/api/cuts").then(setCuts);
    // a failed prefs fetch resolves to {} so the prefs gate below can never hang
    api("/api/prefs").then(d => setPrefs(d.prefs || {})).catch(() => setPrefs({}));
    api("/api/dashboards").then(d => setLayoutIds(new Set(((d.active && d.active.layout) || []).map(s => s.question_id))));
    api("/api/questions").then(setQIndex);
  }, [me && me.org && me.org.name]);
  // per-user DEFAULT peer group (2026-07-10, David): if the URL carries no explicit cut, open
  // on the member's saved default (prefs._peer_default) instead of all-peers. Once, on prefs
  // load — a later explicit "all" selection isn't overridden (initialHadCut latches).
  const initialHadCut = useRef(/[?&]cut=/.test(window.location.hash || ""));
  useEffect(() => {
    if (prefs && !initialHadCut.current && prefs._peer_default && prefs._peer_default !== "all") {
      initialHadCut.current = true;
      setGlobalCut(prefs._peer_default);
    }
  }, [prefs]);
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
  }, [route]);

  window.openMetricRequest = (prefill, source) => setMetricReq({ prefill: prefill || "", source: source || "button" });
  if (me === undefined) return html`<div class="auth-wrap"><${Spinner} /></div>`;
  const scope = me && me.scope ? me.scope : { superpowers: window.SUPERPOWERS || [], focused: false, question_count: 778 };
  window.SCOPE = scope;
  // the engine's market band (LUMI_MARKET_BAND) — cardPosition colours cards on
  // the SAME line as the tiles + signals, so they can never drift.
  if (me && me.config && me.config.market_band) window.MARKET_BAND = me.config.market_band;
  const activeSupers = scope.superpowers;
  if (me === null) return html`<${AuthScreen} route=${route} onAuthed=${() => { window.location.hash = "/overview"; refreshMe(); }} />`;
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
    const r = await api("/api/dashboards/pin", { method: "POST", body: { question_id: qid } });
    setLayoutIds(new Set(r.pinned_ids || []));
  };
  const setGlobalCut = (key) => {
    if (key === "all") setCut({ dim: "all", value: null });
    else if (key === "twin") setCut({ dim: "twin", value: null });
    else if (key === "manage-groups") setGroupsOpen(true);
    else { const [dim, value] = key.split("::"); setCut({ dim, value }); }
  };
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
    page = html`<${MetricPage} ...${pageProps} qid=${m[1]} />`;
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
  // Settings opened to ALL roles (2026-07-13, Defaults follow-up): it hosts settings that are
  // personal to the signed-in user — notifications, AI consent, and the landing peer group the
  // removed ★ used to set from the capsule. Org-level cards gate themselves per role inside
  // SettingsPage (assumptions read-only, sharing hidden, signal-email default read-only).
  else if (route.startsWith("/settings")) page =
    html`<${SettingsPage} me=${me} refreshMe=${refreshMe} cuts=${cuts} prefs=${prefs} onPref=${onPref} />`;
  else if (route.startsWith("/governance")) page = html`<${GovernancePage} me=${me} />`;
  else if ((m = route.match(/^\/run-a-pulse\/([^?]+)/))) page = me.user.role === "admin"
    ? html`<${PulseBuilderPage} me=${me} pid=${m[1]} />`
    : html`<${EmptyState} icon="lock" title="Admin only" body="Designing and launching a pulse is an Admin action." />`;
  else if (route.startsWith("/run-a-pulse")) page = me.user.role === "admin"
    ? html`<${RunPulsePage} me=${me} />`
    : html`<${EmptyState} icon="lock" title="Admin only" body="Designing and launching a pulse is an Admin action." />`;
  else if ((m = route.match(/^\/pulse\/(.+)$/))) page = html`<${PulseDetailPage} me=${me} pid=${m[1]} />`;
  else if (route.startsWith("/pulse")) page = html`<${PulsesPage} me=${me} />`;
  else if (route.startsWith("/profile")) page = html`<${ProfilePage} me=${me} refreshMe=${refreshMe} />`;
  else if (route.startsWith("/strategy")) page = html`<${StrategyPage} me=${me} />`;
  else if (route.startsWith("/admin")) page = me.user.platform_admin
    ? html`<${AdminConsolePage} me=${me} route=${route} />`
    : html`<${NotFoundPage} route=${route} />`;   // invisible to non-staff
  else if (route === "" || route === "/" || route.startsWith("/overview") || route.startsWith("/invite/") || route.startsWith("/reset/"))
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
                const q = opts[activeHit];
                if (q) { e.preventDefault(); setSearch(""); setActiveHit(-1); q.kind === "nav" ? nav(q.route) : openMetric(q.id); }
              }
            }} />
          ${searchPopOpen && html`<${SearchPop} qIndex=${qIndex} search=${search} role=${me.user.role}
            activeHit=${activeHit} onActiveHit=${setActiveHit}
            onGo=${(q) => { setSearch(""); setActiveHit(-1); q.kind === "nav" ? nav(q.route) : openMetric(q.id); }}
            onRequest=${() => { const term = search; setSearch(""); setActiveHit(-1); setMetricReq({ prefill: term, source: "search" }); }} />`}
        </div>
        <div class="topbar-right">
          <button class="btn feature suggest-pill" aria-label="Suggest a new metric" onClick=${() => setSuggestOpen(true)}>Suggest a metric</button>
          ${me.features && me.features.analyst && html`
          <button class="btn feature" title="Find a metric, learn a term, get help, or ask how you compare" onClick=${() => setAnalystOpen(true)}><${Icon} name="sparkle" size=${14} /> Ask lumi</button>`}
          <span class="topbar-sep" aria-hidden="true"></span>
          <${NotificationBell} me=${me} />
          <${ProfileMenu} me=${me} onSignOut=${async () => { await api("/api/auth/logout", { method: "POST" }); setMe(null); }} />
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
          <${RailItem} route=${route} path="/pulse" icon="zap" label="Pulse" />
          ${me.user.role === "admin" && html`<${RailItem} route=${route} path="/run-a-pulse" icon="list-checks" label="Run a pulse" />`}
        </div>
        <div class="nav-group">
          <${BenchmarkNav} route=${route} qIndex=${qIndex} prefs=${prefs} onPref=${onPref} collapsed=${railCollapsed} />
        </div>
        <div class="nav-group">
          <div class="nav-label">Your organisation</div>
          <${RailItem} route=${route} path="/your-data" icon="table" label="Your data" />
          ${me.user.role === "admin" && html`<${RailItem} route=${route} path="/strategy" icon="compass" label="Reward strategy" />`}
          ${me.user.role === "admin" && html`<${RailItem} route=${route} path="/team" icon="users" label="Team" />`}
          ${me.user.role === "admin" && html`<${RailItem} route=${route} path="/settings" icon="sliders-v" label="Settings" />`}
        </div>
        ${me.user.platform_admin && html`
        <div class="nav-group">
          <div class="nav-label">lumi staff</div>
          <${RailItem} route=${route} path="/admin" icon="shield" label="Console" />
        </div>`}
      </nav>
      <div class="main">
        <main class="content" id="main-content" tabindex="-1">
          ${benchRoute && !isOverview && !isCategory && html`<${PeerSetBar} me=${me} cut=${cut} cuts=${cuts}
            onSelect=${setGlobalCut} onTwinInfo=${() => setTwinOpen(true)}
            prefs=${prefs} onPref=${onPref} refreshMe=${refreshMe} />`}
          ${contrib && benchRoute && html`<${ContributionBanner} contrib=${contrib} />`}
          ${page}
        </main>
      </div>
      </div>${/* /.shell-body */""}
      ${unsub && !barHidden && !leaveTo && !route.startsWith("/your-data/review") && html`
        <div class="unsub-bar no-print" role="status">
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
      <p>Your answers are <b>saved</b> — they'll be here when you come back. But they're${" "}
      <b>not submitted to the benchmark yet</b>, so your position, signals and £ opportunity
      won't update until you do.</p>
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
          data-tip="Benchmark" aria-haspopup="true" aria-expanded=${flyout} onClick=${() => setFlyout(!flyout)}>
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
        : "The company facts behind your peer groups. Firmographics change — update them here any time."}</p>
      <p class="caption">These are organisation-level facts only — never personal data — and they're shown to no
      other member. They decide which peer groups you can compare against.</p>
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
    await api("/api/peer-groups/" + g.group_id, { method: "DELETE" });
    toast("Peer group deleted"); refresh();
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
          <p class="caption">Build a comparison group from company facts — sector, size, region and more.
          Private to your organisation. You'll only ever see <b>how many</b> organisations match, never which —
          and nothing shows unless at least ${options.min_orgs} match. That's what keeps it a benchmark.</p>
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
          <p class="caption" style=${{ margin: "0 0 var(--s2)" }}>Pick the facts a peer must match — choosing
          several options within one row means “any of these”. You'll never see which organisations match, only how many.</p>
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
                ? `Only ${count.match_count} organisation${count.match_count === 1 ? "" : "s"} currently match — at least ${count.min_orgs} are needed before any benchmark shows. You can still save it; it stays suppressed until enough organisations match.`
                : `${count.match_count} organisations currently match — comfortably above the minimum of ${count.min_orgs}.`}
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
      <p class="caption">There's nothing at <b>${route}</b> — it may be an old or mistyped link.
        If someone shared it with you, ask them for a fresh one — shared links can expire.</p>
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
        <p>You've been inactive for a while. For your organisation's data safety we'll sign you
        out in <span class="idle-count">${left}</span> seconds. Your saved answers are safe —
        the questionnaire autosaves as you go.</p>
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
window.ContributionBanner = function ({ contrib }) {
  if (contrib.insights_unlocked || !contrib.clock_started) return null;
  const pct = Math.round(contrib.core_pct || 0);
  if (contrib.reduced) return html`
    <div class="card contrib-banner paused">
      <div>
        <b>Your full benchmark is paused.</b>
        <div class="caption">The 30 days passed before your reward data reached 90% — everything you've explored is still here,
          and a sample stays open below. Complete your reward questions to restore the full benchmark and unlock your insights. You're at ${pct}%.</div>
      </div>
      <button class="btn primary small" onClick=${() => nav("/your-data/submit")}>Complete your reward data</button>
    </div>`;
  if (contrib.days_left > 7) return null;
  return html`
    <div class="card contrib-banner">
      <div>
        <b>${contrib.days_left} day${contrib.days_left === 1 ? "" : "s"} left to unlock your insights.</b>
        <div class="caption">You're at ${pct}% of your key reward questions — complete them and your insights go live with your real position.</div>
      </div>
      <button class="btn primary small" onClick=${() => nav("/your-data/submit")}>Continue your submission</button>
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
          : "8 quick facts (sector, size, region…) so we compare you to the right peers. Two minutes, company facts only." },
      { n: 2, label: "Review and accept the Data Contribution Terms", done: false,
        hint: role === "admin" ? "You accept once, for the whole organisation — your 30 days start then."
                               : "Your Admin does this — nothing is needed from you yet." },
      { n: 3, label: "Complete your reward data", done: false,
        hint: (basisN ? "About " + basisN + " key questions (~" + Math.round(basisN * 0.6 / 10) * 10 + " min), by section" : "Your reward questions by section") + " — autosaved, resume any time; insights unlock at " + targetPct + "%." },
      { n: 4, label: "Invite your team", done: false,
        hint: "Contributors fill the questionnaire; Viewers see the benchmark." },
    ];
    return html`
      <div class="card welcome-hero">
        <div style=${{ flex: "1.6 1 320px", minWidth: "280px" }}>
          <div class="row" style=${{ gap: "var(--s2)", marginBottom: "var(--s1)" }}>
            <span style=${{ color: "var(--blue)" }}><${Icon} name="sparkle" size=${18} /></span>
            <b style=${{ fontFamily: "var(--font-head)", fontSize: "var(--fs-h3)" }}>You're set up — here's what's next</b>
          </div>
          <p style=${{ margin: "2px 0 0" }}>Explore every metric and all ${pool.responding_orgs} peer
            organisations from day one. Your 30 days only start once your Admin accepts the data terms —
            setup never counts against you.</p>
        </div>
        <div style=${{ flex: "1.2 1 280px", minWidth: "260px" }}>
          ${steps.map(st => html`
            <div key=${st.n} class="next-step">
              <span class=${"next-step-n" + (st.done ? " done" : "")}>${st.done ? "✓" : st.n}</span>
              <div><b>${st.label}</b><div class="caption">${st.hint}</div></div>
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
  const setupSteps = [
    { label: "Tell us about your organisation", done: profiledPost },
    { label: "Accept the Data Contribution Terms", done: true },
    { label: "Complete your reward data", done: pct >= targetPct, now: pct < targetPct,
      note: pct + "% of " + targetPct + "%" },
    { label: "Invite your team", done: !!contrib.team_invited, optional: true },
  ];
  const doneCount = setupSteps.filter(s => s.done).length;
  return html`
    <div class="submit-banner">
      <div class="submit-banner-counter">
        <div class="submit-banner-days num">${contrib.days_left}</div>
        <div class="submit-banner-dayword">${contrib.days_left === 1 ? "day left" : "days left"}</div>
      </div>
      <div class="submit-banner-msg">
        <div class="submit-banner-head">Submit your reward data to unlock insights</div>
        <p class="submit-banner-body">At ${targetPct}% complete, your benchmark unlocks — the £ opportunity, your board pack and your biggest gaps. If day 30 arrives first, your benchmark simply pauses to a sample until you finish — nothing is lost.</p>
        <div class="submit-banner-progress">
          <div class="progressbar"><div style=${{ width: Math.min(100, pct / targetPct * 100) + "%" }}></div></div>
          <span class="caption submit-banner-pct"><b class="num">${pct}%</b> of ${targetPct}% complete · autosaves</span>
        </div>
      </div>
      <button class="btn primary submit-banner-cta" onClick=${() => nav("/your-data/submit")}>Continue submission</button>
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
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onEsc = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onEsc); };
  }, [open]);
  const go = (path) => { setOpen(false); nav(path); };
  return html`
    <div class="profile-menu" ref=${ref}>
      <button class=${"avatar" + (open ? " active" : "")} aria-haspopup="true" aria-expanded=${open}
        aria-label="Account menu" onClick=${() => setOpen(!open)}>${initialsOf(me.user)}</button>
      ${open && html`
        <div class="card profile-pop" role="group">
          <div class="profile-id">
            <div class="profile-id-name">${me.user.display_name || me.user.email}</div>
            <div class="profile-id-org">${me.org.name}</div>
          </div>
          <div class="profile-sep"></div>
          <button class="profile-item" onClick=${() => go("/profile")}>Your profile</button>
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
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const onEsc = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDoc); document.addEventListener("keydown", onEsc);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onEsc); };
  }, [open]);
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
      <button class=${"notif-btn" + (open ? " active" : "")} aria-haspopup="true" aria-expanded=${open}
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
          <div class="notif-foot">${me && me.user.role === "admin"
            ? html`<a href="#" onClick=${e => { e.preventDefault(); setOpen(false); nav("/settings"); }}>Notification settings →</a>`
            : html`<span class="caption">Ask your Admin to adjust notification settings.</span>`}</div>
        </div>`}
    </div>`;
}

/* The peer-set lens. It used to anchor the top bar, but it only changes the
   benchmark surfaces — so it now lives in a slim context strip at the top of
   those pages ("comparing against …"), and is absent everywhere else. Still
   global state (App owns `cut`); this is just where it's surfaced. */
function PeerSetBar({ me, cut, cuts, onSelect, onTwinInfo, inline, prefs, onPref, refreshMe }) {
  const note = (!me.org.classified || (cut.dim === "group" && cutTooSmall(cut, cuts)));
  // ★/🔔 default-setters REMOVED from the capsule (David 2026-07-12, "the icons at the end of
  // the bar do nothing — remove"): on the default all-peers view both read as already-set, so
  // they looked inert. Both defaults are now set from Settings → Defaults (2026-07-13):
  // prefs._peer_default drives the landing view (the load-default effect above) and
  // orgs.default_cut drives the signal-email sweep (PUT /api/org/signal-peers).
  return html`
    <div class=${"peerbar no-print" + (inline ? " peerbar-inline" : "")}>
      <span class="peerbar-lead"><${Icon} name="users" size=${13} /> Comparing against</span>
      <span class=${"peerbar-pill" + (cut.dim !== "all" ? " narrowed" : "")}>
        <span class="peerbar-selwrap">
        <select aria-label="Choose your peer group" class="peer-ctl"
          value=${cut.dim === "all" ? "all" : cut.dim === "twin" ? "twin" : cut.dim + "::" + cut.value}
          onChange=${e => { if (e.target.value === "twin-info") { onTwinInfo(); } else onSelect(e.target.value); }}>
          <option value="all">All peers · ${(me.peer_pool || {}).responding_orgs || "—"}</option>
          ${cuts && cuts.org_industry && html`<option value=${"industry::" + cuts.org_industry}>${cuts.org_industry} · ${cuts.industries[cuts.org_industry] || "?"}</option>`}
          ${me.org.classified && cuts && Object.keys(cuts.industries || {}).filter(i => i !== (cuts || {}).org_industry).map(i =>
            html`<option key=${i} value=${"industry::" + i}>${i} · ${cuts.industries[i]}</option>`)}
          ${me.org.classified && cuts && Object.keys(cuts.fte_bands || {}).map(b =>
            html`<option key=${b} value=${"fte_band::" + b}>${b} FTE · ${cuts.fte_bands[b]}</option>`)}
          ${cuts && cuts.twin_available && html`<option value="twin">Organisations like you</option>`}
          ${cuts && (cuts.groups || []).length > 0 && html`
            <optgroup label="Your groups">
              ${cuts.groups.map(g => html`<option key=${g.group_id} value=${"group::" + g.group_id}>
                ${g.name}${g.too_small ? " (too few orgs)" : ` · ${g.match_count}`}</option>`)}
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
  "/priorities": "/signals", "/profile": "/your-data" };
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
  { label: "Your data", route: "/your-data", group: "Pages", kw: "submit answers questionnaire enter" },
  { label: "Reward strategy", route: "/strategy", group: "Pages", role: "admin", kw: "objective market stance intent capture" },
  { label: "Team", route: "/team", group: "Pages", role: "admin", kw: "members invite roles colleagues" },
  { label: "Settings", route: "/settings", group: "Pages", role: "admin", kw: "assumptions sharing notifications account" },
  { label: "Your profile", route: "/profile", group: "Pages", kw: "company facts sector size region" },
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
      <div class="caption">${q.superpower}${q.subpower ? " · " + q.subpower : ""} · ${q.category} · n=${q.n}</div>
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
          <button class="btn small" style=${{ marginTop: "var(--s2)" }} onClick=${request}>Request this metric</button>
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
function MetricSignalBar({ qid }) {
  const [sig, setSig] = useState(null);
  const [status, setStatus] = useState(null);
  useEffect(() => {
    let dead = false;
    apiCached("/api/overview").then(o => {
      if (dead) return;
      const s = (o.signals_all || []).find(x => x.question_id === qid && x.status !== "dismissed") || null;
      setSig(s); setStatus(s ? s.status : null);
    }).catch(() => {});
    return () => { dead = true; };
  }, [qid]);
  if (!sig) return null;
  const onSet = (sid, st, days) => {
    setStatus(st || "active");
    signalAction(qid, st, days).catch(() => {});
    if (st === "dismissed") toast("Signal dismissed", null, { label: "Undo", fn: () => onSet(qid, null) });
    else if (st === "snoozed") toast("Snoozed", null, { label: "Undo", fn: () => onSet(qid, null) });
  };
  const word = LENS_WORD[sig.lens] || "the market";
  return html`
    <div class="metric-sigbar">
      <span class=${"signal-roundel lens-" + sig.lens}><${Icon} name=${LENS_ICON[sig.lens] || "flag"} size=${14} /></span>
      <div class="metric-sigbar-txt">
        <b>Flagged in your signals</b> — for ${word}${sig.risk_framed ? " · a risk floor" : ""}
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
  const [chartSel, setChartSel] = useState(() => { try { return sessionStorage.getItem("lumi-chart-pref:" + qid); } catch (e) { return null; } });
  const chartRef = useRef(null);
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
      .then(d => { if (!dead) setCard(d); })
      .catch(e => { if (!dead) setErr(e.message); })
      .finally(() => { if (!dead) setBusy(false); });
    return () => { dead = true; };
  }, [qid, sel.dim, sel.value]);
  if (err) return html`<${EmptyState} title="Couldn't load this metric"
    body=${err + " — nothing is lost; it usually works on a retry."}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!card) return html`
    <div>
      <div class="skel" style=${{ height: "32px", width: "440px", marginBottom: "var(--s3)" }}></div>
      <div class="skel" style=${{ height: "18px", width: "560px", marginBottom: "var(--s4)" }}></div>
      <div class="skel" style=${{ height: "420px", borderRadius: "var(--radius)" }}></div>
    </div>`;

  const cardStale = card && card.cut && (card.cut.dim !== sel.dim
    || (card.cut.value || null) !== (sel.value || null));
  if (!card || cardStale) return html`
    <div>
      <div class="skel" style=${{ height: "32px", width: "440px", marginBottom: "var(--s3)" }}></div>
      <div class="skel" style=${{ height: "18px", width: "560px", marginBottom: "var(--s4)" }}></div>
      <div class="skel" style=${{ height: "420px", borderRadius: "var(--radius)" }}></div>
    </div>`;

  const c = card;
  const pos = cardPosition(c);
  const aim = metricAim(c, pos);   // strategy read-through: this metric vs the org's declared domain aim
  const sent = humanSentence(c);
  // honest chart options only (curated per data type); the session preference
  // applies only where valid — normaliseChart falls back to this metric's default
  const alts = chartAlternatives(c);
  const chart = normaliseChart(c, chartSel);
  const pickChart = (t) => { setChartSel(t); try { sessionStorage.setItem("lumi-chart-pref:" + qid, t); } catch (e) {} };
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
  const profiled = !!(org.industry && org.fte_band);
  const doExport = async () => {
    const res = await exportCardPNG(chartRef.current, {
      title: c.title, cutLabel: c.cut.label, n: c.n, window: period, card: c,
      suffix: c.you && c.you.percentile != null ? `You: ${c.you.display} (${pLabel(c.you.percentile)})` : null,
    }, "download");
    toast(res === "downloaded" ? `Chart downloaded — labelled ${c.cut.label}, n=${c.n}` : "Nothing to export yet");
  };
  const share = () => {
    const cutPart = selKey !== "all" ? "?cut=" + encodeURIComponent(sel.dim + "::" + (sel.value || "")) : "";
    navigator.clipboard.writeText(window.location.href.split("#")[0] + "#/metric/" + qid + cutPart);
    toast("Link copied — opens this metric on " + c.cut.label);
  };
  const genCommentary = async (force) => {
    if (cmBusy) return null;
    setCmBusy(true); setCmErr(null);
    try {
      const r = await api("/api/metric-commentary", { method: "POST",
        body: { question_id: qid, cut: sel.dim, cut_value: sel.value, force: !!force } });
      setCommentary(r); return r;
    } catch (e) { setCmErr(e.message); return null; }
    finally { setCmBusy(false); }
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
    if (!commentary && !cmBusy && me.features && me.features.commentary) {
      toast("Writing your commentary for the one-pager…");
      await genCommentary(false);
      await new Promise(r => setTimeout(r, 400));   // let the narrative paint before the print dialog
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
        <span class="logo">lumi<span>.</span></span> · Metric one-pager · ${c.cut.label} · n=${c.n}${period ? " · " + period : ""}</div>
      <button class="btn quiet no-print" onClick=${goBack}>← Back</button>
      <div class="row spread" style=${{ alignItems: "flex-start", marginTop: "var(--s2)", gap: "var(--s4)" }}>
        <div style=${{ minWidth: 0 }}>
          <h1 class="display-title" style=${{ marginBottom: "var(--s1)" }}>${c.title}</h1>
          <p class="caption" style=${{ margin: "0 0 var(--s3)", maxWidth: "640px" }}>${c.question_text}</p>
          <div class="row" style=${{ gap: "var(--s2)" }}>
            <${Chip} kind="accent">${org.name}<//>
            ${org.industry && html`<${Chip}>${org.industry}<//>`}
            ${org.fte_band && html`<${Chip}>${org.fte_band} FTE<//>`}
            ${org.hq_region && html`<${Chip}>${org.hq_region}<//>`}
            ${period && html`<${Chip}>${period}<//>`}
          </div>
        </div>
        <div class="metric-head-side">
          ${c.classification && (c.classification.direction === "neutral" || c.classification.register === "Approach")
            ? html`<span class="pos-pill lg mid" title=${c.classification.register === "Approach"
                ? "lumi reads this as an approach — how, or how often, you do something. It has no better-or-worse, so it's shown as context, not an above/below-market verdict."
                : "This metric has no inherently good or bad direction — lumi shows it as context to weigh, not an above/below-market verdict."}>Context</span>`
            : pos && html`<span class=${"pos-pill lg " + pos.kind} title=${pos.tip}>${pos.arrow} ${pos.label}</span>`}
          ${aim && html`<div class="metric-aim" title="How this metric reads against the aim you declared for this area.">
            <span class="metric-aim-lbl">Your ${c.domain_aim.domain} aim: ${STANCE_VERB[c.domain_aim.stance] || c.domain_aim.stance}</span>
            <${AlignmentChip} target=${aim} compact=${true} />
          </div>`}
          <div class="metric-head-actions no-print">
            ${!c.suppressed && !(c.type === "matrix" && (c.matrix_rows || []).every(r => r.suppressed)) && html`<button class="btn small" onClick=${doExport} title="Download just the chart as a labelled PNG image"><${Icon} name="download" size=${13} /> Chart</button>`}
            ${!c.suppressed && html`<button class="btn small" onClick=${printMetric} title="Download a one-page PDF — the chart plus the written story (what it means for you)"><${Icon} name="file-text" size=${13} /> One-pager</button>`}
            <button class="btn small" onClick=${share} title="Copy a link that opens this metric on the current peer group"><${Icon} name="link" size=${13} /> Share</button>
            ${onPin && pinnedIds && html`<button class=${"btn small" + (pinnedIds.has(qid) ? " primary" : "")} onClick=${() => onPin(qid)}
              title=${pinnedIds.has(qid) ? "Remove this metric from your dashboard" : "Pin this metric to your dashboard"}>
              <${Icon} name=${pinnedIds.has(qid) ? "check" : "plus"} size=${13} /> ${pinnedIds.has(qid) ? "Pinned" : "Pin"}</button>`}
          </div>
        </div>
      </div>
      <${MetricSignalBar} qid=${qid} />

      <div class="card" style=${{ padding: "var(--s5)", marginTop: "var(--s4)" }}>
        <div class="row spread metric-controls">
          <div class="ctlgroup">
            <select class="ctl" aria-label="Peer group for this metric" value=${selKey} onChange=${e => setCutKey(e.target.value)}>
              <option value="all">All peers</option>
              ${org.industry && html`<option value=${"industry::" + org.industry}>Your sector: ${org.industry}</option>`}
              ${org.fte_band && html`<option value=${"fte_band::" + org.fte_band}>Your size: ${org.fte_band} FTE</option>`}
              ${sel.dim === "industry" && sel.value && sel.value !== org.industry && html`<option value=${"industry::" + sel.value}>Sector: ${sel.value}</option>`}
              ${sel.dim === "fte_band" && sel.value && sel.value !== org.fte_band && html`<option value=${"fte_band::" + sel.value}>Size: ${sel.value} FTE</option>`}
              ${cuts && cuts.twin_available && html`<option value="twin">Organisations like you</option>`}
              ${cuts && Object.keys(cuts.industries || {}).length > 0 && html`
                <optgroup label="Compare a sector">
                  ${Object.keys(cuts.industries).sort().map(i => html`<option key=${i} value=${"industry::" + i}>${i} · ${cuts.industries[i]}</option>`)}
                </optgroup>`}
              ${cuts && Object.keys(cuts.fte_bands || {}).length > 0 && html`
                <optgroup label="Compare a size band">
                  ${Object.keys(cuts.fte_bands).map(b => html`<option key=${b} value=${"fte_band::" + b}>${b} FTE · ${cuts.fte_bands[b]}</option>`)}
                </optgroup>`}
              ${cuts && (cuts.groups || []).length > 0 && html`
                <optgroup label="Your groups">
                  ${cuts.groups.map(g => html`<option key=${g.group_id} value=${"group::" + g.group_id}>${g.name}</option>`)}
                </optgroup>`}
            </select>
            <div class="hint">${c.cut.label} · n=${c.n}</div>
          </div>
          ${alts.length > 1 && html`
            <div class="chart-switch" role="group" aria-label="Chart type">
              ${alts.map(t => html`
                <button key=${t} class=${"chart-switch-btn" + (chart === t ? " on" : "")}
                  aria-pressed=${chart === t} onClick=${() => pickChart(t)}>${CHART_LABELS[t] || t}</button>`)}
            </div>`}
        </div>
        ${!profiled && html`<div class="caption" style=${{ marginBottom: "var(--s2)" }}>
          Sector, size and bespoke comparisons unlock once your company profile is complete —
          ${" "}<a href="#/profile">two minutes, company facts only</a>.</div>`}
        <div class="metric-xl" ref=${chartRef} style=${busy ? { opacity: .45 } : null}
          role="img" aria-label=${c.title + " chart. " + (sent.lead || "Peer benchmark distribution.") + " Based on " + c.n + " organisations, " + c.cut.label + "."}>
          ${c.suppressed ? html`
            <${EmptyState} icon="shield" title="Not enough organisations to show this safely"
              body=${"Fewer than 5 organisations in this peer group (" + c.cut.label + ") answered this question — protecting every member's data comes first. Try a broader peer group."}
              action=${html`<a class="btn small" href="#/how-lumi-works/suppression">Why figures are hidden</a>`} />` :
          html`<${CardBody} card=${c} chart=${chart} showP1090=${true} showValues=${true} fav=${pos ? pos.kind : null} xl=${true} />`}
        </div>
        ${!c.suppressed && html`
          <div class="bench-lead" style=${{ marginTop: "var(--s3)" }}>${sent.lead || ""}</div>
          <${ExactFigures} card=${c} />`}
      </div>

      ${/* THE primary read — promoted directly under the chart (2026-07-06). Always
            present: a deterministic aim-aware base line, upgraded by Generate to the
            full structured commentary. The standalone "What this means for you" card
            is retired into this. Shown whenever AI is available OR there's a
            deterministic read to give (practice metrics only get the AI version). */ ""}
      ${(me.features && me.features.commentary) || (pos && !c.suppressed) ? html`
        <${MetricCommentary} commentary=${commentary} busy=${cmBusy} err=${cmErr} onGenerate=${genCommentary}
          onSave=${saveCommentary} canEdit=${!!(me.user && me.user.role !== "viewer")}
          pos=${pos} card=${c} featureOn=${!!(me.features && me.features.commentary)} />` : null}

      <${MetricTrend} qid=${qid} />

      ${/* methodology demoted to a collapsed "About this metric" — reference detail
            (definition, how it's calculated, how lumi reads it), below the read, not
            competing with it. Was a co-equal card that mostly repeated the question. */ ""}
      <details class="card metric-about" style=${{ padding: "var(--s4) var(--s5)", marginTop: "var(--s4)" }}>
        <summary class="metric-about-sum"><span class="section-title" style=${{ margin: 0 }}>About this metric</span></summary>
        <div class="metric-about-body">
          ${c.definition && html`<p>${c.definition}</p>`}
          ${c.help_text && html`<p class="caption">${c.help_text}</p>`}
          <p class="caption"><${Term} word="percentile">Percentiles<//> use linear interpolation across all valid peer
          answers; medians, not averages. Figures resting on fewer than 5 organisations are
          ${" "}<a href="#/how-lumi-works/suppression">suppressed</a>.
          ${" "}<a href="#/how-lumi-works/calculations">How this is calculated</a>.</p>
          ${c.classification && c.classification.cls && html`
            <div class="mp-class-note">
              <div class="mp-class-head">
                <span class="mp-class-label">How lumi reads this</span>
                <span class=${"mp-class-chip " + mpReadChip(c.classification).cls}>${mpReadChip(c.classification).text}</span>
              </div>
              <p class="caption">${mpReadCopy(c.classification)}</p>
            </div>`}
          <div class="row" style=${{ marginTop: "var(--s3)" }}>
            <button class="btn quiet" onClick=${() => window.openMetricRequest(c.title, "metric-page")}>Request a related metric</button>
          </div>
        </div>
      </details>
      <div class="caption no-print" style=${{ margin: "var(--s4) 0" }}>
        From the <a href=${"#" + backTo}>${c.subpower || "Reward"}</a> category of your reward benchmark.
      </div>
      ${/* print-only source line for the one-pager PDF (hidden on screen) */ ""}
      <div class="metric-pdf-foot" aria-hidden="true">
        Source: lumi HR${period ? " · " + period : ""} · generated ${new Date().toLocaleDateString("en-GB")} · Percentiles use medians across valid peer answers; peer groups under 5 organisations are suppressed.</div>
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
function MetricCommentary({ commentary, busy, err, onGenerate, onSave, canEdit, pos, card, featureOn }) {
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
  return html`
    <div class=${"card metric-commentary" + (data ? " has-narrative" : "")} style=${{ padding: "var(--s5)", marginTop: "var(--s4)" }}>
      <div class="row spread" style=${{ alignItems: "flex-start" }}>
        <h2 class="section-title" style=${{ marginBottom: 0 }}><${Icon} name="sparkle" size=${14} /> What this means for you</h2>
        ${edited ? html`<span class="chip" style=${{ background: "var(--blue-tint)", color: "var(--blue-deep)" }}>Edited by your team</span>`
          : data ? html`<span class="chip warn no-print">AI draft — review &amp; edit</span>` : null}
      </div>
      ${detBase && html`<p style=${{ margin: "var(--s2) 0 0" }}>${detBase}</p>`}
      ${!data && !busy && featureOn && html`
        <p class="caption commentary-cta" style=${{ marginTop: detBase ? "var(--s3)" : "var(--s2)" }}>${detBase
          ? "Want the fuller read? A short, structured interpretation drafted from the figures on this page — yours to review, edit and make your own."
          : "A short, structured interpretation of this metric for your organisation, drafted from the figures on this page — yours to review, edit and make your own."}</p>
        ${err && html`<div class="error-text no-print" style=${{ marginBottom: "var(--s2)" }}>${err}</div>`}
        <button class="btn primary" onClick=${() => onGenerate(false)}><${Icon} name="sparkle" size=${13} /> Generate commentary</button>`}
      ${!data && !busy && !featureOn && !detBase && html`
        <p class="caption" style=${{ marginTop: "var(--s2)" }}>An interpretation appears here once your organisation's AI insights are switched on.</p>`}
      ${busy && html`<div class="row" style=${{ padding: "var(--s4) 0" }}><${Spinner} /> <span class="caption">Reading the figures on this page…</span></div>`}
      ${data && !editing && html`
        <div style=${{ marginTop: "var(--s3)" }}>
          ${CM_PARTS.map(([k, label]) => data.parts[k] && html`
            <div key=${k} style=${{ marginBottom: "var(--s3)" }}>
              <div class="caption" style=${{ fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", fontSize: "var(--fs-micro)" }}>${label}</div>
              <p style=${{ margin: "2px 0 0", whiteSpace: "pre-wrap" }}>${data.parts[k]}</p>
            </div>`)}
          <div class="caption metric-cm-foot" style=${{ borderTop: "1px solid var(--border)", paddingTop: "var(--s2)" }}>
            ${edited
              ? html`Edited by your team${data.edited_by ? " (" + data.edited_by + ")" : ""}${data.edited_at ? " · " + new Date(data.edited_at + "Z").toLocaleDateString("en-GB") : ""} — your organisation's own words. Consider your own context and seek professional input where relevant.`
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
              <label class="caption" style=${{ fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", fontSize: "var(--fs-micro)", display: "block", marginBottom: "2px" }}>${label}</label>
              <textarea class="ctl metric-cm-edit" rows=${3} value=${draft[k] || ""}
                onInput=${e => setDraft(d => ({ ...d, [k]: e.target.value }))}></textarea>
            </div>`)}
          <div class="row" style=${{ gap: "var(--s2)" }}>
            <button class="btn primary small" disabled=${saving} onClick=${doSave}>${saving ? "Saving…" : "Save your commentary"}</button>
            <button class="btn quiet small" disabled=${saving} onClick=${() => setEditing(false)}>Cancel</button>
          </div>
        </div>`}
    </div>`;
}

/* Exact figures: the analyst's row — your value, percentile, market quartiles, n. */
function ExactFigures({ card: c }) {
  const cells = [];
  if (c.type === "numeric" && c.block) {
    if (c.you && c.you.display != null) cells.push(["You", c.you.display + (c.you.percentile != null ? " · " + pLabel(c.you.percentile) : "")]);
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
      cells.push(["Your answer", c.you.label + (mine ? ` (${mine.pct}% of the market)` : "")]);
    }
    const top = [...c.block.options].sort((a, b) => b.pct - a.pct)[0];
    if (top) cells.push(["Most common", `${top.label} (${top.pct}%)`]);
  }
  cells.push(["Organisations", "n=" + c.n]);
  return html`
    <div class="exact-figs">
      ${cells.map(([k, v], i) => html`<div key=${i}><span class="caption">${k}</span><b class="num">${v}</b></div>`)}
    </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${ErrorBoundary}><${App} /><//>`);
