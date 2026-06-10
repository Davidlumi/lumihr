/* BenchmarkCard — every state designed: normal, suppressed, locked, no-answer.
   Driven entirely by library metadata via the card payload from the API. */
/* global html, useState, useRef, useEffect, api, fmtValue, pLabel, Chip, NBadge, Term, Modal,
   PercentileBand, Histogram, BoxPlot, OptionBars, StackedDist, Donut, MatrixHeat, MatrixGrouped,
   chartAlternatives, normaliseChart, CHART_LABELS, exportCardPNG, fmtGBPCompact, EmptyState, nav */

window.BenchmarkCard = function ({ card, prefs, onPref, onPin, pinned, size, cuts, globalCut, window: collWindow, onCutOverride, highlight }) {
  const [expanded, setExpanded] = useState(false);
  const [exportMsg, setExportMsg] = useState(null);
  const [localCard, setLocalCard] = useState(null);
  const ref = useRef(null);
  const c = localCard || card;
  const pref = (prefs || {})[card.id] || {};
  const chart = normaliseChart(c, pref.chart);
  const showP1090 = pref.p1090 !== false;
  const showValues = pref.values !== false;

  // per-card peer-cut override (fetches just this card under another cut)
  const cutKey = pref.cut || null;
  useEffect(() => {
    let dead = false;
    if (!cutKey) { setLocalCard(null); return; }
    const [dim, value] = cutKey.split("::");
    api(`/api/benchmark/${card.id}?cut=${encodeURIComponent(dim)}${value ? "&cut_value=" + encodeURIComponent(value) : ""}`)
      .then(d => { if (!dead) setLocalCard(d); })
      .catch(() => { if (!dead) setLocalCard(null); });
    return () => { dead = true; };
  }, [cutKey, card.id, globalCut]);

  const setPref = (k, v) => onPref && onPref(card.id, { ...pref, [k]: v });

  if (c.locked) return html`<${LockedCard} card=${c} size=${size} />`;

  const doExport = async (mode) => {
    const res = await exportCardPNG(ref.current, {
      title: c.title, cutLabel: c.cut.label, n: c.n, window: collWindow,
      suffix: c.you && c.you.percentile != null ? `You: ${c.you.display} (${pLabel(c.you.percentile)})` : null,
    }, mode);
    setExportMsg(res === "copied" ? "Copied" : res === "downloaded" ? "Downloaded" : "No chart");
    setTimeout(() => setExportMsg(null), 1600);
  };

  const fav = c.favourable || (c.score ? favFromScore(c.score) : null);

  return html`
    <div class=${"card bench-card" + (size === 2 ? " w2" : "") + (highlight ? " drop-target" : "")} ref=${ref}>
      <div class="bench-head">
        <h3 class="bench-title" title=${c.question_text}>${c.title}</h3>
        <div class="bench-controls no-print">
          ${chartAlternatives(c).length > 1 && html`
            <select class="ctl" style=${{ padding: "2px 5px", fontSize: "11px" }} value=${chart}
              onChange=${e => setPref("chart", e.target.value)} title="Chart type">
              ${chartAlternatives(c).map(a => html`<option key=${a} value=${a}>${CHART_LABELS[a]}</option>`)}
            </select>`}
          ${cuts && html`
            <select class="ctl" style=${{ padding: "2px 5px", fontSize: "11px", maxWidth: "120px" }}
              value=${pref.cut || ""} onChange=${e => setPref("cut", e.target.value || undefined)} title="Peer group for this card">
              <option value="">Page filter</option>
              <option value="all">All peers</option>
              ${cuts.org_industry && html`<option value=${"industry::" + cuts.org_industry}>${cuts.org_industry}</option>`}
              ${cuts.org_fte_band && html`<option value=${"fte_band::" + cuts.org_fte_band}>${cuts.org_fte_band} FTE</option>`}
              ${cuts.twin_available && html`<option value="twin">Organisations like you</option>`}
            </select>`}
          ${(c.type === "numeric") && html`
            <button class="iconbtn" title="Show/hide P10 and P90" onClick=${() => setPref("p1090", !showP1090)}>P10/90</button>`}
          <button class=${"iconbtn" + (showValues ? " on" : "")} title="Show/hide value labels" onClick=${() => setPref("values", !showValues)}>123</button>
          <button class="iconbtn" title="Download PNG (with title, peer group and n baked in)" onClick=${() => doExport("download")}>⤓</button>
          <button class="iconbtn" title="Copy PNG to clipboard" onClick=${() => doExport("clipboard")}>⧉</button>
          ${onPin && html`<button class=${"iconbtn" + (pinned ? " on" : "")} title=${pinned ? "Remove from My view" : "Pin to My view"}
            onClick=${() => onPin(c.id)}>${pinned ? "★" : "☆"}</button>`}
          <button class="iconbtn" title="Full question, definition and method" onClick=${() => setExpanded(true)}>ⓘ</button>
        </div>
      </div>
      <div class="bench-meta">
        ${c.you && c.you.percentile != null && html`<${Chip} kind=${fav === "good" ? "good" : fav === "bad" ? "bad" : fav === "mid" ? "warn" : "accent"}
          title="Your percentile position in this peer group"><${Term} word="percentile">${pLabel(c.you.percentile)}<//><//>`}
        <${NBadge} n=${c.n} cutLabel=${c.cut.label} />
        ${c.category && html`<${Chip}>${c.category}<//>`}
        ${exportMsg && html`<${Chip} kind="accent">${exportMsg}<//>`}
      </div>
      <${CardBody} card=${c} chart=${chart} showP1090=${showP1090} showValues=${showValues} fav=${fav} />
      ${c.opportunity && html`<${OpportunityPanel} opp=${c.opportunity} />`}
      ${c.readout && html`<div class="bench-readout">${c.readout}</div>`}
      <div class="movement" style=${{ marginTop: "6px" }}>
        <span title="Movement vs your previous benchmark will appear here once a second collection window exists.">↗</span>
        ${c.movement === null ? "First benchmark — movement appears from your next cycle." : ""}
      </div>
      ${expanded && html`<${CardDetail} card=${c} onClose=${() => setExpanded(false)} />`}
    </div>`;
};

function favFromScore(score) {
  if (!score || score.percentile == null || score.polarity === "neutral") return null;
  const r = score.polarity === "lower_is_better" ? 100 - score.percentile : score.percentile;
  return r > 55 ? "good" : r < 45 ? "bad" : "mid";
}

window.CardBody = function ({ card: c, chart, showP1090, showValues, fav }) {
  if (c.suppressed) {
    return html`<div class="suppressed-box">
      <div style=${{ fontSize: "20px" }}>🛡</div>
      <div style=${{ fontWeight: 650, color: "var(--ink)" }}>Not enough data in this peer group</div>
      <div>Fewer than 5 organisations answered here, so we don't show it — this protects every member's data. Try a wider peer group.</div>
      <${Chip}>n=${c.n}<//>
    </div>`;
  }
  if (c.type === "numeric") {
    const you = c.you ? c.you.value : null;
    return html`
      <div>
        ${c.you ? html`
          <div class="row spread" style=${{ marginBottom: "2px" }}>
            <div class="metric-value">${stripUnit(c.you.display, c.unit)}<span class="unit">${unitSuffix(c.unit)}</span></div>
            ${c.block && html`<div class="caption">Peer <${Term} word="median">median<//>: <b class="num">${fmtValue(c.block.p50, c.unit)}</b></div>`}
          </div>` :
        html`<div class="noanswer-box">You haven't answered this question yet — peers are shown without your marker.<br/>
          <a href="#/submission">Add your data</a></div>`}
        ${chart === "histogram" ? html`<${Histogram} histogram=${c.histogram} you=${you} unit=${c.unit} favourable=${fav} showValues=${showValues} />`
        : chart === "box" ? html`<${BoxPlot} block=${c.block} you=${you} unit=${c.unit} favourable=${fav} showValues=${showValues} />`
        : html`<${PercentileBand} block=${c.block} you=${you} unit=${c.unit} favourable=${fav} showP1090=${showP1090} showValues=${showValues} />`}
      </div>`;
  }
  if (c.type === "single_select" || c.type === "yes_no" || c.type === "multi_select") {
    const youLabels = c.you ? c.you.labels : [];
    if (!c.block) return html`<div class="suppressed-box">No distribution available.</div>`;
    return html`
      <div>
        ${!c.you && html`<div class="noanswer-box" style=${{ marginBottom: "8px" }}>You haven't answered this question yet.</div>`}
        ${chart === "stacked_bar" && c.type !== "multi_select" ? html`<${StackedDist} options=${c.block.options} youLabels=${youLabels} showValues=${showValues} />`
        : chart === "donut" && c.type !== "multi_select" ? html`<${Donut} options=${c.block.options} youLabels=${youLabels} />`
        : html`<${OptionBars} options=${c.block.options} youLabels=${youLabels} showValues=${showValues} />`}
      </div>`;
  }
  if (c.type === "matrix") {
    const allSuppressed = (c.matrix_rows || []).every(r => r.suppressed);
    if (allSuppressed) return html`<div class="suppressed-box">
      <div style=${{ fontWeight: 650, color: "var(--ink)" }}>Not enough data in this peer group</div>
      <div>Fewer than 5 organisations per level — try a wider peer group.</div></div>`;
    return chart === "grouped_bars"
      ? html`<${MatrixGrouped} rows=${c.matrix_rows} unit=${c.unit} showValues=${showValues} />`
      : html`<${MatrixHeat} rows=${c.matrix_rows} unit=${c.unit} polarity=${c.polarity} showValues=${showValues} />`;
  }
  return null;
};

function unitSuffix(unit) {
  if (!unit) return "";
  if (unit.type === "percentage") return "%";
  if (unit.type === "days" || unit.type === "hours" || unit.type === "weeks") return " " + unit.type;
  return "";
}
function stripUnit(display, unit) {
  if (!display) return display;
  if (unit && unit.type === "percentage") return display.replace(/%$/, "");
  if (unit && ["days", "hours", "weeks"].includes(unit.type)) return display.replace(/ \w+$/, "");
  return display;
}

window.LockedCard = function ({ card: c, size }) {
  return html`
    <div class=${"card bench-card" + (size === 2 ? " w2" : "")}>
      <div class="bench-head"><h3 class="bench-title">${c.title}</h3></div>
      <div class="bench-meta"><${NBadge} n=${c.n} cutLabel=${(c.cut || {}).label || "All peers"} /><${Chip} kind="warn">${c.tier}<//></div>
      <div class="blurred" aria-hidden="true">
        <svg viewBox="0 0 360 90" style=${{ width: "100%" }}>
          <rect x="20" y="38" width="320" height="14" rx="7" fill="var(--chart-band)"/>
          <rect x="90" y="38" width="150" height="14" rx="7" fill="var(--chart-band-mid)"/>
          <rect x="168" y="34" width="3" height="22" fill="var(--chart-median)"/>
          <circle cx="230" cy="45" r="7" fill="var(--accent)"/>
        </svg>
        <div class="bench-readout">This benchmark compares your position against similar organisations.</div>
      </div>
      <div class="locked-overlay">
        <${Chip} kind="warn">🔒 ${c.tier} tier<//>
        <div class="caption" style=${{ textAlign: "center", maxWidth: "260px" }}>
          This benchmark is part of lumi's ${c.tier} set. ${c.n} organisations have contributed to it.
        </div>
        <button class="btn small primary" onClick=${() => nav("/upgrade")}>Unlock with lumi Full</button>
      </div>
    </div>`;
};

window.OpportunityPanel = function ({ opp }) {
  const [open, setOpen] = useState(false);
  const main = opp.direction === "saving"
    ? `Closing to median ≈ ${fmtGBPCompact(opp.to_p50_gbp)}/yr`
    : `Reaching median ≈ ${fmtGBPCompact(opp.to_p50_gbp)}/yr investment`;
  return html`
    <div style=${{ background: "var(--accent-soft)", borderRadius: "var(--r1)", padding: "8px 12px", margin: "8px 0 2px", fontSize: "12.5px" }}>
      <div class="row spread">
        <b>${main}</b>
        <span class="hastip" style=${{ position: "relative", cursor: "help", color: "var(--accent-ink)" }}>
          formula
          <span class="tip">${opp.formula}. All figures are <b>indicative</b> and rest on the assumptions in Settings.</span>
        </span>
      </div>
      <div class="caption">To P75 ≈ ${fmtGBPCompact(opp.to_p75_gbp)}/yr · <${Term} word="indicative">indicative<//> · ${opp.cut_label}</div>
      ${!opp.fte_known && html`<div class="warn-text">Add your FTE band to size this opportunity.</div>`}
    </div>`;
};

window.CardDetail = function ({ card: c, onClose }) {
  return html`
    <${Modal} onClose=${onClose}>
      <h2 class="section-title">${c.title}</h2>
      <p><b>Question asked:</b> ${c.question_text}</p>
      ${c.definition && html`<p><b>Definition:</b> ${c.definition}</p>`}
      ${c.help_text && html`<p class="caption">${c.help_text}</p>`}
      <div class="row" style=${{ marginTop: "12px" }}>
        <${Chip}>${c.superpower}${c.subpower ? " · " + c.subpower : ""}<//>
        <${Chip}>${c.category}<//>
        <${Chip}>${c.tier} tier<//>
        <${Chip}>peer group: ${c.cut.label}, n=${c.n}<//>
      </div>
      <p class="caption" style=${{ marginTop: "12px" }}>
        Percentiles use linear interpolation across all valid peer answers; anything based on fewer
        than 5 organisations is suppressed. See the <a href="#/methodology" onClick=${onClose}>methodology</a>.
      </p>
      <div class="row" style=${{ justifyContent: "flex-end" }}>
        <button class="btn" onClick=${onClose}>Close</button>
      </div>
    <//>`;
};
