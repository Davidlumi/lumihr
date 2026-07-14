/* lumi core: htm binding, API client, formatters, shared atoms, hash router. */
/* global React, ReactDOM, htm */
window.html = htm.bind(React.createElement);
window.h = React.createElement;
const { useState, useEffect, useRef, useMemo, useCallback } = React;
window.useState = useState; window.useEffect = useEffect; window.useRef = useRef;
window.useMemo = useMemo; window.useCallback = useCallback;

// ------------------------------------------------------------------ API ----
window.api = async function (path, opts) {
  opts = opts || {};
  const init = { method: opts.method || "GET", headers: {}, credentials: "same-origin" };
  if (opts.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.body);
  }
  if (opts.signal) init.signal = opts.signal;
  let res;
  try { res = await fetch(path, init); }
  catch (e) {
    if (e && e.name === "AbortError") throw e;   // caller-initiated — let them handle it
    throw new ApiError(0, "Couldn't reach lumi — check your connection and try again.");
  }
  if (res.status === 401) { window.dispatchEvent(new Event("lumi:unauth")); throw new ApiError(401, "Not signed in"); }
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON */ }
  if (!res.ok) throw new ApiError(res.status, (data && data.detail) || "Something went wrong");
  return data;
};
class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }
window.ApiError = ApiError;

// Session cache for GET payloads several surfaces share (/api/overview is
// fetched by five pages) — back-navigation inside the TTL renders instantly
// instead of re-running the whole engine pass. Keyed by full path+query, so
// peer-cut and strategy variants never collide. Invalidate on writes.
const _apiCache = new Map();
const _apiInflight = new Map();   // §4.10(3): concurrent identical fetches share ONE request
window.apiCached = function (path, ttl) {
  const hit = _apiCache.get(path);
  if (hit && Date.now() - hit.ts < (ttl || 60000)) return Promise.resolve(hit.data);
  const flying = _apiInflight.get(path);
  if (flying) return flying;   // two components asking during the same flight join it
  const p = api(path)
    .then(d => { _apiCache.set(path, { ts: Date.now(), data: d }); return d; })
    .finally(() => _apiInflight.delete(path));
  _apiInflight.set(path, p);
  return p;
};
window.apiCacheInvalidate = function (prefix) {
  for (const k of [..._apiCache.keys()]) if (!prefix || k.startsWith(prefix)) _apiCache.delete(k);
  for (const k of [..._apiInflight.keys()]) if (!prefix || k.startsWith(prefix)) _apiInflight.delete(k);
};

// ----------------------------------------------------------- formatters ----
window.fmtValue = function (v, unit) {
  if (v === null || v === undefined) return "—";
  const ut = (unit && unit.type) || "none";
  if (ut === "currency") return "£" + Math.round(v).toLocaleString("en-GB");
  // small decimals (multipliers like 1.25x) keep 2dp; larger values stay 1dp
  const dp = Math.abs(v) < 10 ? 2 : 1;
  let s = (Math.round(v * Math.pow(10, dp)) / Math.pow(10, dp)).toLocaleString("en-GB", { maximumFractionDigits: dp });
  if (ut === "percentage") return s + "%";
  if (ut === "days" || ut === "hours" || ut === "weeks") return s + " " + ut;
  return s;
};
window.fmtGBP = v => "£" + Math.round(v).toLocaleString("en-GB");
window.fmtGBPCompact = v => {
  const a = Math.abs(v);
  if (a >= 1e6) return "£" + (v / 1e6).toFixed(1).replace(/\.0$/, "") + "m";
  if (a >= 1e3) return "£" + Math.round(v / 1e3) + "k";
  return "£" + Math.round(v);
};
window.pLabel = r => "P" + Math.round(r);

// glossary used for first-use tooltips (plain-English, UK gov style register)
window.GLOSSARY = {
  percentile: "If you lined all organisations up from lowest to highest, the percentile tells you where a value sits. P75 means three quarters of organisations are at or below it.",
  median: "The middle value: half of organisations are above it, half below. We show medians (P50) rather than averages so one unusual organisation can't skew the picture.",
  quartile: "Quarter of the peer group. The top quartile is the highest 25% of values; the interquartile range (P25–P75) is the middle half.",
  suppressed: "When fewer than 5 organisations are behind a number we don't show it, so no individual organisation's data can be worked out.",
  "peer group": "The organisations you're being compared with. Use the filter to compare against everyone, your industry, organisations your size, or organisations like you.",
  n: "The number of organisations behind this comparison. A benchmark without its sample size isn't publishable — so n is always shown.",
  indicative: "A modelled, directional figure built on the stated assumptions — useful for sizing a conversation, not for budgeting.",
  "market position": "Where you sit versus peers on a measure — below, on, or above market. The headline is built only from market-rate measures where higher is better, so it answers one question: how competitive is your reward?",
  "a practice choice": "You do something differently from most peers on a measure with no better-or-worse — a choice, not a gap to close.",
  favourable: "A measure where being lower is the good outcome — such as a pay gap — and you sit on the good side of the market.",
  context: "A measure with no inherently good direction, shown as a fact to weigh rather than a verdict.",
};

// ------------------------------------------------------------- atoms -------
window.Term = function ({ word, children }) {
  const key = (word || (typeof children === "string" ? children : "")).toLowerCase();
  const def = GLOSSARY[key];
  if (!def) return html`<span>${children}</span>`;
  // focusable so keyboard/touch users can reach the definition (hover-only
  // excluded them); Escape blurs to dismiss the tip (WCAG 1.4.13)
  return html`<span class="term" tabindex="0" onKeyDown=${e => { if (e.key === "Escape") e.target.blur(); }}>${children}<span class="tip" role="tooltip">${def}</span></span>`;
};

window.Chip = ({ kind, title, children }) =>
  html`<span class=${"chip " + (kind || "")} title=${title || ""}>${children}</span>`;

window.NBadge = ({ n, cutLabel }) => html`
  <span class="chip" title="Number of organisations behind this comparison">
    <${Term} word="n">n=${n}<//>${cutLabel ? html` · ${cutLabel}` : null}
  </span>`;

window.Spinner = () => html`<span class="spinner"></span>`;

window.Modal = function ({ onClose, children, width, xl, label, role }) {
  const cardRef = useRef(null);
  useEffect(() => {
    const onKey = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  // Focus management (mirrors commercial.js SuggestModal): capture the trigger,
  // focus the first focusable inside .modal (or the .modal itself), restore on unmount.
  useEffect(() => {
    const trigger = document.activeElement;
    const t = setTimeout(() => {
      const el = cardRef.current;
      if (!el) return;
      const first = [...el.querySelectorAll('button, input, textarea, select, [tabindex]:not([tabindex="-1"])')]
        .filter(n => !n.disabled && n.offsetParent)[0];
      (first || el).focus();
    }, 0);
    return () => { clearTimeout(t); if (trigger && trigger.focus) trigger.focus(); };
  }, []);
  // Trap Tab/Shift+Tab within .modal (wrap first↔last).
  const onKeyDown = (e) => {
    if (e.key !== "Tab" || !cardRef.current) return;
    const f = [...cardRef.current.querySelectorAll('button, input, textarea, select, [tabindex]:not([tabindex="-1"])')]
      .filter(el => !el.disabled && el.offsetParent);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  return html`
    <div class="modal-back" onClick=${e => { if (e.target === e.currentTarget) onClose(); }}>
      <div class=${"modal" + (xl ? " xl" : "")} style=${width ? { width } : null} ref=${cardRef} tabindex="-1" role=${role || "dialog"} aria-modal="true" aria-label=${label || "Dialog"} onKeyDown=${onKeyDown}>${children}</div>
    </div>`;
};

// The one member-facing label that differs from the data key: the "Time Off" domain
// renders sentence-case "Time off" everywhere (nav, tiles, headings). Display only —
// routes, keys, CAT_ICON lookups and server strings keep "Time Off".
window.domainLabel = n => ({
  "Time Off": "Time off",                                  // legacy key — stored payloads
  "Pensions & Savings": "Pensions & savings",
  "Health & Protection": "Health & protection",
  "Benefits & Lifestyle": "Benefits & lifestyle",
  "Time Off & Family": "Time off & family",
  "Incentives & Recognition": "Incentives & recognition",
  "Governance & Transparency": "Governance & transparency",
}[n] || n);

// The standard centred page spinner — one atom instead of the copy-pasted row.
window.PageLoading = () => html`<div class="row" style=${{ justifyContent: "center", padding: "var(--s8)" }}><${Spinner} /></div>`;

// "You are here on a ruler" — the percentile scale strip the board pack prints,
// a shared atom so the SCREEN shows the same instant read (below ← on market
// → above, with a P-marker). band=[low,high] from window.MARKET_BAND (engine-sourced).
// Zone colours are the SOFT gauge tints — the platform's one RAG fill, same as the donut.
// Pass comparable+inLine for the one-line context sentence; compact = strip + labels only.
// (The short-lived `mini` dot-scale variant was replaced same-day by the banded domain bar —
// Option B, David: "combine the position in market with the stacked bar".)
// RESURRECTED 2026-07-11 (David: "on reflection we do need the user to be able to see their
// position in the market overall and for each domain") — reverses the 2026-07-09 "RAG is the
// ONLY position indicator" retirement. The explained-P form (band context + n + basis flags)
// is the pattern the board pack already ratified; bare unexplained P-numbers stay banned.
// "3rd", "21st", "12th" — every spoken percentile goes through this (a P3 domain read "3th").
window.pctlOrdinal = function (n) {
  const s = ["th", "st", "nd", "rd"], v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
};

// ONE practice-prevalence word rule (extracted 2026-07-12 so the BOARD PACK and the home
// PracticeArc can never contradict): majority-common → Typical / "mostly common choices";
// rare-led → Distinctive / "often its own pattern"; else Varied / "a mixed pattern".
// Descriptive, never a grade.
window.prevalenceWord = function (common, alt, rare, pool) {
  const share = pool ? common / pool : 0;
  const word = (common >= alt && common >= rare)
    ? (share >= 0.5 ? "Typical" : "Varied")
    : (rare >= alt && rare >= common) ? "Distinctive" : "Varied";
  const cap = word === "Typical" ? "mostly common choices"
            : word === "Distinctive" ? "often its own pattern" : "a mixed pattern";
  return { word, cap };
};

// ONE confidence-score rule (2026-07-12, the 10-point rating): monotonic in n, ANCHORED to
// the published tiers — >=20 peers (High) spans 7–10 green; 5–19 (Directional) spans 4–6
// amber; below 5 is suppressed so red 1–3 never renders live. Used by the dashboard badge
// AND the board pack so the two can never disagree.
window.confScore = function (n) {
  if (n == null || n < 5) return null;
  const score = n >= 150 ? 10 : n >= 100 ? 9 : n >= 60 ? 8 : n >= 20 ? 7 : n >= 15 ? 6 : n >= 10 ? 5 : 4;
  return { score, band: score >= 7 ? "green" : "amber", tier: score >= 7 ? "high confidence" : "directional" };
};

window.PercentileRuler = function ({ pctl, band, comparable, inLine, compact }) {
  if (pctl == null || !band || band.length !== 2) return null;
  const lo = band[0], hi = band[1], p = Math.round(pctl);
  return html`
    <div class="bp-scale-wrap" style=${compact ? { margin: "var(--s3) 0 0" } : null}>
      <div class="bp-scale" role="img"
        aria-label=${"Your typical comparable metric sits at the " + pctlOrdinal(p) + " percentile; the on-market band runs P" + lo + " to P" + hi + "."}>
        <div class="bp-scale-zone z-below" style=${{ width: lo + "%" }}></div>
        <div class="bp-scale-zone z-on" style=${{ width: (hi - lo) + "%" }}></div>
        <div class="bp-scale-zone z-above" style=${{ width: (100 - hi) + "%" }}></div>
        ${/* the PILL marker (2026-07-12, pack-methodology incorporation) — the same one-object
              P-inside-ink grammar as the dashboard rows and overall marker, so board pack,
              category pages and home all speak one marker language. */ ""}
        <div class="bp-scale-pill num" style=${{ left: Math.min(96, Math.max(4, pctl)) + "%" }}>P${p}</div>
      </div>
      ${/* vocabulary harmonised (fix class B, David 2026-07-11 ruling): ONE register —
            below/on/above market — everywhere this atom renders, INCLUDING the board pack
            (the old less/more-competitive axis wording is retired product-wide). */ ""}
      <div class="caption bp-scale-labels"><span>below market</span><span>on market</span><span>above market</span></div>
      ${!compact && comparable ? html`<p class="caption" style=${{ marginTop: "var(--s2)" }}>Your typical comparable metric sits at <b>P${p}</b>; ${inLine} of ${comparable} comparable metrics sit within the on-market band.</p>` : null}
    </div>`;
};

// Reduced-motion-safe scroll: an explicit behavior:"smooth" option OVERRIDES the
// CSS scroll-behavior backstop per spec, so every programmatic scroll goes
// through here instead of calling scrollIntoView({behavior:"smooth"}) directly.
window.scrollIntoViewSafe = function (el, opts) {
  if (!el || !el.scrollIntoView) return;
  const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ block: "center", ...(opts || {}), behavior: reduce ? "auto" : ((opts && opts.behavior) || "smooth") });
};

window.EmptyState = ({ icon, title, body, action }) => html`
  <div class="suppressed-box" style=${{ minHeight: "140px" }}>
    <div style=${{ color: "var(--ink-faint)" }}>${typeof icon === "string" && window.Icon ? html`<${Icon} name=${icon} size=${20} />` : (icon || (window.Icon ? html`<${Icon} name="info" size=${20} />` : "—"))}</div>
    <div style=${{ fontWeight: 650, color: "var(--ink)" }}>${title}</div>
    ${body ? html`<div>${body}</div>` : null}
    ${action || null}
  </div>`;

// ------------------------------------------------------------- toasts ------
// Lightweight background-action feedback: bottom-left, auto-dismiss, no deps.
window.toast = function (msg, kind, action) {
  let host = document.getElementById("toast-host");
  if (!host) {
    host = document.createElement("div");
    host.id = "toast-host";
    host.setAttribute("role", "status");
    host.setAttribute("aria-live", "polite");
    document.body.appendChild(host);
  }
  const el = document.createElement("div");
  el.className = "toast" + (kind ? " " + kind : "");
  el.textContent = msg;
  if (action && action.label && action.fn) {
    const btn = document.createElement("button");
    btn.className = "toast-action";
    btn.textContent = action.label;
    btn.onclick = () => { action.fn(); el.classList.remove("show"); setTimeout(() => el.remove(), 300); };
    el.appendChild(btn);
  }
  host.appendChild(el);
  setTimeout(() => el.classList.add("show"), 16);
  const ttl = action ? 6500 : 3600;   // undo needs a beat longer
  setTimeout(() => { el.classList.remove("show"); setTimeout(() => el.remove(), 300); }, ttl);
};

// ----------------------------------------------------- UK number inputs ----
// Parse what a UK user might type into a money/number field: "£12,500", "12 500".
window.parseUKNumber = function (s) {
  if (s === null || s === undefined) return "";
  const cleaned = String(s).replace(/[£,%\s]/g, "");
  return cleaned;
};
// Format a stored numeric string for display in an idle input: 12500 -> "12,500".
window.formatUKNumber = function (s, currency) {
  if (s === null || s === undefined || s === "") return "";
  const n = Number(String(s).replace(/[£,%\s]/g, ""));
  if (!isFinite(n)) return String(s);
  const txt = n.toLocaleString("en-GB", { maximumFractionDigits: 2 });
  return currency ? "£" + txt : txt;
};

// ------------------------------------------------------ error boundary -----
// Render crashes become a branded, recoverable screen — never a blank page.
window.ErrorBoundary = class extends React.Component {
  constructor(props) { super(props); this.state = { err: null }; }
  static getDerivedStateFromError(err) { return { err }; }
  render() {
    if (this.state.err) {
      return html`
        <div class="auth-wrap"><div class="card auth-card" style=${{ textAlign: "center" }}>
          <div class="logo" style=${{ padding: 0, marginBottom: "var(--s1)", display: "inline-block" }}>lumi<span>.benchmark</span></div>
          <h2 class="section-title" style=${{ marginTop: "var(--s3)" }}>Something went wrong</h2>
          <p class="caption">Your data is safe — this is a display problem, not a data one.</p>
          <button class="btn primary" onClick=${() => { window.location.hash = "/overview"; window.location.reload(); }}>Reload lumi</button>
        </div></div>`;
    }
    return this.props.children;
  }
};

// ------------------------------------------------------------- router ------
/* Chrome rationalisation (2026-06-12, spec section 7): every old route 301s to
   its new home — typed links, bookmarks and emails must never 404. The map is
   applied inside useRoute so every consumer only ever sees canonical routes. */
window.mapLegacyRoute = function (r) {
  if (r.startsWith("/gap-register")) return "/priorities";
  if (r.startsWith("/pulses")) return "/pulse" + r.slice("/pulses".length);
  if (r.startsWith("/reward")) return "/benchmark" + r.slice("/reward".length);
  if (r.startsWith("/mydata")) return "/your-data";
  if (r.startsWith("/submission")) return "/your-data/submit" + r.slice("/submission".length);
  // /boardpack was a legacy no-op that bounced to Overview; it's now the real
  // board-packs home (U2), so it routes normally — no remap.
  if (r.startsWith("/shares")) return "/settings?tab=sharing";
  return null;
};

function canonicalRoute() {
  const r = window.location.hash.slice(1) || "/overview";
  const mapped = window.mapLegacyRoute(r);
  if (mapped) {
    window.location.replace("#" + mapped);
    return mapped;
  }
  return r;
}

window.useRoute = function () {
  const [route, setRoute] = useState(canonicalRoute());
  useEffect(() => {
    const f = () => setRoute(canonicalRoute());
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return route;
};
// Navigation goes through a single chokepoint so an optional leave-guard can
// intercept it (e.g. "you have unsubmitted changes"). _navRaw is the
// unguarded jump the guard itself uses once the user confirms.
window._navRaw = path => { window.location.hash = path; };
window.nav = path => {
  if (window._leaveGuard && window._leaveGuard(path)) return;   // guard opened a dialog
  window._navRaw(path);
};

// Unsubmitted-changes flag: drafts autosave server-side but only reach the
// benchmark on submit. markUnsubmitted() is called after a successful draft
// save, clearUnsubmitted() after a submit; the App listens for the event to
// drive the reminder bar + leave-guard.
window._unsubmitted = false;
window.markUnsubmitted = () => { window._unsubmitted = true; window.dispatchEvent(new CustomEvent("lumi:unsubmitted")); };
window.clearUnsubmitted = () => { window._unsubmitted = false; window.dispatchEvent(new CustomEvent("lumi:unsubmitted")); };

/* Lightweight, dependency-free canvas confetti for the genuine "you did it"
   moments (a section completed, a submission landed, insights unlocked). One
   self-removing canvas per burst; honours prefers-reduced-motion. */
window.confettiBurst = function (opts) {
  opts = opts || {};
  try {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  } catch (e) {}
  const count = opts.count || 130;
  const duration = opts.duration || 2600;
  const spread = opts.spread || 1;          // 1 = full burst; <1 = tighter
  // celebrate in the lumi palette — resolve brand tokens at runtime (canvas
  // fillStyle can't read CSS vars directly), with brand-hex fallbacks.
  const _cs = getComputedStyle(document.documentElement);
  const _tok = (n, fb) => (_cs.getPropertyValue(n).trim() || fb);
  const colors = opts.colors || [
    _tok("--blue-bright", "#2E62D9"), _tok("--favourable", "#2E7D52"),
    _tok("--amber-bright", "#F5A60A"), _tok("--lumi-coral", "#F08C6E"),
    _tok("--blue", "#2048B0"), _tok("--differs", "#6257C9")];
  const origin = opts.origin || { x: 0.5, y: 0.32 };
  const cv = document.createElement("canvas");
  cv.setAttribute("aria-hidden", "true");
  cv.style.cssText = "position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;z-index:9999";
  document.body.appendChild(cv);
  const ctx = cv.getContext("2d");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const W = () => window.innerWidth, H = () => window.innerHeight;
  const resize = () => { cv.width = W() * dpr; cv.height = H() * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
  resize();
  window.addEventListener("resize", resize);
  const ox = origin.x * W(), oy = origin.y * H();
  const P = [];
  for (let i = 0; i < count; i++) {
    const a = Math.random() * Math.PI * 2;
    const speed = (5 + Math.random() * 8) * spread;
    P.push({
      x: ox, y: oy, vx: Math.cos(a) * speed, vy: Math.sin(a) * speed - (5 + Math.random() * 5),
      g: 0.16 + Math.random() * 0.12, size: 5 + Math.random() * 7,
      color: colors[(Math.random() * colors.length) | 0],
      rot: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.34,
      shape: Math.random() < 0.5 ? "rect" : "circle",
    });
  }
  let start = null;
  function frame(t) {
    if (start === null) start = t;
    const e = t - start, fade = Math.max(0, 1 - e / duration);
    ctx.clearRect(0, 0, W(), H());
    for (const p of P) {
      p.vy += p.g; p.vx *= 0.992; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx.save(); ctx.globalAlpha = fade; ctx.translate(p.x, p.y); ctx.rotate(p.rot); ctx.fillStyle = p.color;
      if (p.shape === "rect") ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.62);
      else { ctx.beginPath(); ctx.arc(0, 0, p.size / 2, 0, 7); ctx.fill(); }
      ctx.restore();
    }
    if (e < duration) requestAnimationFrame(frame);
    else { window.removeEventListener("resize", resize); cv.remove(); }
  }
  requestAnimationFrame(frame);
};

/* The metric full page is each metric's home. openMetric remembers where the
   user came from (route + scroll) so Back restores their exact position. */
window.openMetric = function (qid) {
  try {
    sessionStorage.setItem("lumi-return", JSON.stringify({
      hash: window.location.hash, y: window.scrollY || document.documentElement.scrollTop || 0 }));
  } catch (e) {}
  nav("/metric/" + qid);
};
window.consumeReturnScroll = function (hash) {
  try {
    const raw = sessionStorage.getItem("lumi-return");
    if (!raw) return null;
    const saved = JSON.parse(raw);
    if (saved.hash !== hash) return null;
    sessionStorage.removeItem("lumi-return");
    return saved.y;
  } catch (e) { return null; }
};

// ------------------------------------------------- chart-type compatibility -
// Never offer a chart type that misrepresents the data shape.
window.chartAlternatives = function (card) {
  if (card.type === "numeric") {
    // only offer the histogram when the engine actually carries binned values —
    // a banded/derived numeric has no bins, so the switch would render blank
    const hasBins = card.histogram && card.histogram.bins && card.histogram.bins.length > 1;
    return hasBins ? ["quartile_band", "histogram", "box"] : ["quartile_band", "box"];
  }
  if (card.type === "matrix") {
    // categorical matrices have one honest representation: the per-level table
    if ((card.matrix_rows || []).some(r => r.block && r.block.kind === "select")) return ["matrix_table"];
    return ["heatmap", "grouped_bars"];
  }
  if (card.type === "multi_select") return ["bar"];
  // 2026-06-12: ordered scales have ONE honest representation — the ordered
  // distribution (labels on their own bars, every category visible, You in place,
  // a thin ordinal rail signalling "this is a scale").
  if (card.type === "single_select") return ["ordered"];
  if (card.type === "yes_no") {
    // a TRUE binary (≤2 real answers) is NOT a scale → plain bars, no ordinal rail.
    // many "yes_no" metrics actually carry a middle/partial state (Yes/No/Partially/
    // In development/…) — that gradient keeps the ordered distribution, which shows
    // the spread honestly.
    const realOpts = ((card.block && card.block.options) || []).filter(o => !o.is_na);
    return realOpts.length > 2 ? ["ordered"] : ["bar"];
  }
  return ["bar"];
};
window.normaliseChart = function (card, pref) {
  const alts = chartAlternatives(card);
  let def = card.chart_default;
  if (def === "quartile") def = "quartile_band";
  if (!alts.includes(def)) def = alts[0];
  return (pref && alts.includes(pref)) ? pref : def;
};
window.CHART_LABELS = {
  quartile_band: "Percentile band", histogram: "Histogram", box: "Box plot",
  bar: "Bars", ordered: "Ordered distribution",
  heatmap: "Distribution", grouped_bars: "Grouped bars", matrix_table: "Per-level table",
};
