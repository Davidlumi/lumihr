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
  let res;
  try { res = await fetch(path, init); }
  catch (e) { throw new ApiError(0, "Couldn't reach lumi — check your connection and try again."); }
  if (res.status === 401) { window.dispatchEvent(new Event("lumi:unauth")); throw new ApiError(401, "Not signed in"); }
  let data = null;
  try { data = await res.json(); } catch (e) { /* non-JSON */ }
  if (!res.ok) throw new ApiError(res.status, (data && data.detail) || "Something went wrong");
  return data;
};
class ApiError extends Error { constructor(status, msg) { super(msg); this.status = status; } }
window.ApiError = ApiError;

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
};

// ------------------------------------------------------------- atoms -------
window.Term = function ({ word, children }) {
  const key = (word || (typeof children === "string" ? children : "")).toLowerCase();
  const def = GLOSSARY[key];
  if (!def) return html`<span>${children}</span>`;
  return html`<span class="term">${children}<span class="tip">${def}</span></span>`;
};

window.Chip = ({ kind, title, children }) =>
  html`<span class=${"chip " + (kind || "")} title=${title || ""}>${children}</span>`;

window.NBadge = ({ n, cutLabel }) => html`
  <span class="chip" title="Number of organisations behind this comparison">
    <${Term} word="n">n=${n}<//>${cutLabel ? html` · ${cutLabel}` : null}
  </span>`;

window.Spinner = () => html`<span class="spinner"></span>`;

window.Modal = function ({ onClose, children, width, xl }) {
  useEffect(() => {
    const onKey = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return html`
    <div class="modal-back" onClick=${e => { if (e.target === e.currentTarget) onClose(); }}>
      <div class=${"modal" + (xl ? " xl" : "")} style=${width ? { width } : null}>${children}</div>
    </div>`;
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
window.toast = function (msg, kind) {
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
  host.appendChild(el);
  setTimeout(() => el.classList.add("show"), 16);
  setTimeout(() => { el.classList.remove("show"); setTimeout(() => el.remove(), 300); }, 3600);
};

// ----------------------------------------------------- UK number inputs ----
// Parse what a UK user might type into a money/number field: "£12,500", "12 500".
window.parseUKNumber = function (s) {
  if (s === null || s === undefined) return "";
  const cleaned = String(s).replace(/[£,\s]/g, "");
  return cleaned;
};
// Format a stored numeric string for display in an idle input: 12500 -> "12,500".
window.formatUKNumber = function (s, currency) {
  if (s === null || s === undefined || s === "") return "";
  const n = Number(String(s).replace(/[£,\s]/g, ""));
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
          <div class="logo" style=${{ padding: 0, marginBottom: "4px", display: "inline-block" }}>lumi<span>.benchmark</span></div>
          <h2 class="section-title" style=${{ marginTop: "10px" }}>Something went wrong</h2>
          <p class="caption">Your data is safe — this is a display problem, not a data one.</p>
          <button class="btn primary" onClick=${() => { window.location.hash = "/overview"; window.location.reload(); }}>Reload lumi</button>
        </div></div>`;
    }
    return this.props.children;
  }
};

// ------------------------------------------------------------- router ------
window.useRoute = function () {
  const [route, setRoute] = useState(window.location.hash.slice(1) || "/overview");
  useEffect(() => {
    const f = () => setRoute(window.location.hash.slice(1) || "/overview");
    window.addEventListener("hashchange", f);
    return () => window.removeEventListener("hashchange", f);
  }, []);
  return route;
};
window.nav = path => { window.location.hash = path; };

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
  if (card.type === "numeric") return ["quartile_band", "histogram", "box"];
  if (card.type === "matrix") {
    // categorical matrices have one honest representation: the per-level table
    if ((card.matrix_rows || []).some(r => r.block && r.block.kind === "select")) return ["matrix_table"];
    return ["heatmap", "grouped_bars"];
  }
  if (card.type === "multi_select") return ["bar"];
  // donut retired: bars for few-option categoricals, segmented band for scales
  if (card.type === "single_select" || card.type === "yes_no") return ["bar", "stacked_bar"];
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
  bar: "Bars", stacked_bar: "Distribution band",
  heatmap: "Heatmap", grouped_bars: "Grouped bars", matrix_table: "Per-level table",
};
