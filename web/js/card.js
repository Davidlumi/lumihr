/* BenchmarkCard — one vertical skeleton on every card:
   title (2-line clamp) → meta chips → chart region (fixed --chart-h, content
   centred) → plain-English readout pinned at the bottom → movement slot.
   The eye reads: what is this → how do I compare (position pill) → the detail. */
/* global html, useState, useRef, useEffect, api, fmtValue, pLabel, Chip, NBadge, Term, Modal, Icon,
   PercentileBand, Histogram, BoxPlot, OptionBars, StackedDist, MatrixHeat, MatrixGrouped,
   chartAlternatives, normaliseChart, CHART_LABELS, exportCardPNG, fmtGBPCompact, EmptyState, nav */

window.BenchmarkCard = function ({ card, prefs, onPref, onPin, pinned, size, cuts, globalCut, window: collWindow, onCutOverride, highlight }) {
  /* power controls (chart type, peer cut, pin) live in the zoom pop-out */
  const [expanded, setExpanded] = useState(false);
  const [zoomed, setZoomed] = useState(false);
  const [exportMsg, setExportMsg] = useState(null);
  const [localCard, setLocalCard] = useState(null);
  const ref = useRef(null);
  const c = localCard || card;
  const pref = (prefs || {})[card.id] || {};
  const chart = normaliseChart(c, pref.chart);
  const showP1090 = pref.p1090 !== false;
  const showValues = pref.values !== false;

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

  if (c.reduced) return html`<${ReducedCard} card=${c} />`;

  const doExport = async (mode) => {
    const res = await exportCardPNG(ref.current, {
      title: c.title, cutLabel: c.cut.label, n: c.n, window: collWindow,
      suffix: c.you && c.you.percentile != null ? `You: ${c.you.display} (${pLabel(c.you.percentile)})` : null,
    }, mode);
    setExportMsg(res === "copied" ? "Copied" : res === "downloaded" ? "Downloaded" : "No chart");
    setTimeout(() => setExportMsg(null), 1600);
  };

  const pos = cardPosition(c);

  return html`
    <div class=${"card bench-card" + (size === 2 ? " w2" : "") + (highlight ? " drop-target" : "")} ref=${ref}>
      <div class="bench-head">
        <h3 class="bench-title" title=${c.question_text}>${c.title}</h3>
        <button class="iconbtn title-info no-print" title="Full question, definition and method"
          onClick=${() => setExpanded(true)}><${Icon} name="info" size=${13} /></button>
        ${exportMsg && html`<${Chip} kind="accent">${exportMsg}<//>`}
        ${pos && html`<span class=${"pos-pill " + pos.kind} title=${pos.tip}>${pos.arrow} ${pos.label}</span>`}
      </div>
      <div class="bench-body">
        <div class="bench-words">
          <div class="bench-lead">${humanSentence(c).lead || ""}</div>
          <${WhatThisMeans} card=${c} pos=${pos} />
          ${c.opportunity && html`<${OpportunityPanel} opp=${c.opportunity} />`}
          <div class="bench-n" title="The number of organisations behind this comparison">
            n=${c.n}${cutNote(c)}</div>
        </div>
        <div class=${"bench-proof bench-chart" + (c.suppressed ? "" : " zoomable")} title=${c.suppressed ? undefined : "Click to expand"}
          onClick=${e => { if (!c.suppressed && !e.target.closest("a") && !e.target.closest(".bench-controls")) setZoomed(true); }}>
          <div class="bench-controls no-print">
            <button class="iconbtn" title="Download this chart as a PNG"
              onClick=${e => { e.stopPropagation(); doExport("download"); }}><${Icon} name="download" size=${13} /></button>
            <button class="iconbtn" title="Expand chart"
              onClick=${e => { e.stopPropagation(); setZoomed(true); }}><${Icon} name="maximize" size=${13} /></button>
          </div>
          <${CardBody} card=${c} chart=${chart} showP1090=${showP1090} showValues=${showValues} fav=${pos ? pos.kind : null} />
        </div>
      </div>
      ${expanded && html`<${CardDetail} card=${c} onClose=${() => setExpanded(false)} />`}
      ${zoomed && html`<${CardZoom} card=${c} pos=${pos} chart=${chart} pref=${pref} setPref=${setPref}
        cuts=${cuts} showP1090=${showP1090} showValues=${showValues} window=${collWindow}
        onPin=${onPin} pinned=${pinned}
        onClose=${() => setZoomed(false)} />`}
    </div>`;
};

/* The pop-out: the same card re-rendered large in a modal, with the full
   control cluster, readout and export to hand. */
window.CardZoom = function ({ card: c, pos, chart, pref, setPref, cuts, showP1090, showValues, window: collWindow, onPin, pinned, onClose }) {
  const ref = useRef(null);
  const [exportMsg, setExportMsg] = useState(null);
  const doExport = async (mode) => {
    const res = await exportCardPNG(ref.current, {
      title: c.title, cutLabel: c.cut.label, n: c.n, window: collWindow,
      suffix: c.you && c.you.percentile != null ? `You: ${c.you.display} (${pLabel(c.you.percentile)})` : null,
    }, mode);
    setExportMsg(res === "copied" ? "Copied to clipboard" : res === "downloaded" ? "Downloaded" : "No chart");
    setTimeout(() => setExportMsg(null), 1600);
  };
  return html`
    <${Modal} onClose=${onClose} xl=${true}>
      <div ref=${ref}>
        <div class="row spread" style=${{ alignItems: "flex-start", marginBottom: "var(--s2)" }}>
          <h2 class="section-title" style=${{ marginBottom: 0, paddingRight: "var(--s4)" }}>${c.title}</h2>
          <div class="row" style=${{ gap: "var(--s2)", flexWrap: "nowrap" }}>
            ${pos && html`<span class=${"pos-pill " + pos.kind} title=${pos.tip}>${pos.arrow} ${pos.label}</span>`}
            <button class="iconbtn" title="Close (Esc)" onClick=${onClose}><${Icon} name="close" size=${15} /></button>
          </div>
        </div>
        <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
          <div class="row" style=${{ gap: "var(--s1)" }}>
            <${NBadge} n=${c.n} cutLabel=${c.cut.label} />
            ${c.category && html`<${Chip}>${c.category}<//>`}
            ${exportMsg && html`<${Chip} kind="accent">${exportMsg}<//>`}
          </div>
          <div class="row no-print" style=${{ gap: "var(--s1)" }}>
            ${chartAlternatives(c).length > 1 && html`
              <select class="ctl" style=${{ height: "28px", fontSize: "12px" }} value=${chart}
                onChange=${e => setPref("chart", e.target.value)} title="Chart type">
                ${chartAlternatives(c).map(a => html`<option key=${a} value=${a}>${CHART_LABELS[a]}</option>`)}
              </select>`}
            ${cuts && html`
              <select class="ctl" style=${{ height: "28px", fontSize: "12px", maxWidth: "180px" }}
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
            <button class="btn small" onClick=${() => doExport("download")}><${Icon} name="download" size=${12} /> PNG</button>
            <button class="btn small" onClick=${() => doExport("clipboard")}><${Icon} name="copy" size=${12} /> Copy</button>
            ${onPin && html`<button class=${"btn small" + (pinned ? " feature" : "")} onClick=${() => onPin(c.id)}>
              <${Icon} name="star" size=${12} /> ${pinned ? "Pinned" : "Pin to My view"}</button>`}
          </div>
        </div>
        <div class="bench-chart xl">
          <${CardBody} card=${c} chart=${chart} showP1090=${showP1090} showValues=${showValues}
            fav=${pos ? pos.kind : null} xl=${true} />
        </div>
        ${c.opportunity && html`<${OpportunityPanel} opp=${c.opportunity} />`}
        <div class="bench-readout" style=${{ marginTop: "var(--s4)", minHeight: 0 }}>${c.readout || multiSelectReadout(c) || ""}</div>
        <p class="caption" style=${{ marginTop: "var(--s3)", marginBottom: 0 }}>
          <b>Question asked:</b> ${c.question_text}${c.definition ? html` · <b>Definition:</b> ${c.definition}` : ""}
        </p>
      </div>
    <//>`;
};

/* The plain-English answer that leads every card: "X in 10" phrasing first,
   the precise figures as a quiet supporting line. */
function humanSentence(c) {
  if (c.suppressed) {
    return { lead: "There aren't enough organisations in this peer group to show this safely.", support: "We never show a figure based on fewer than 5 organisations." };
  }
  if ((c.type === "single_select" || c.type === "yes_no") && c.you && c.block && c.block.options) {
    const mine = c.block.options.find(o => o.label.toLowerCase() === (c.you.label || "").toLowerCase());
    if (mine) {
      const x = Math.round(mine.pct / 10);
      const phrase = mine.pct < 5 ? "almost no similar organisations made the same choice"
        : x <= 0 ? "fewer than 1 in 10 similar organisations made the same choice"
        : x >= 10 ? "almost all similar organisations did the same"
        : `about ${x} in 10 similar organisations did the same`;
      return { lead: `You answered “${c.you.label}” — ${phrase}.`, support: c.readout };
    }
  }
  if (c.type === "multi_select") {
    return { lead: multiSelectReadout(c), support: null };
  }
  if (!c.you && !c.readout && c.type !== "matrix") {
    return { lead: "Answer this to see where you stand — the peer picture is already here.", support: null };
  }
  return { lead: c.readout, support: null };
}

/* 8.5 — the advisor gesture: a quiet, optional line on what good looks like.
   Deterministic copy from existing fields only; led by gap cards. */
window.WhatThisMeans = function ({ card: c, pos }) {
  const [open, setOpen] = useState(false);
  if (!pos || c.suppressed) return null;
  const lines = meaningLines(c, pos);
  if (!lines) return null;
  return html`
    <div>
      <button class="btn quiet small" style=${{ padding: "0", height: "18px", color: "var(--blue-bright)", fontFamily: "var(--font)" }}
        onClick=${() => setOpen(!open)}>${open ? "▾" : "▸"} What this means</button>
      ${open && html`<div class="caption" style=${{ marginTop: "var(--s1)" }}>${lines}</div>`}
    </div>`;
};

function meaningLines(c, pos) {
  const p50 = c.block && c.block.p50 != null ? fmtValue(c.block.p50, c.unit) : null;
  if (pos.kind === "bad") {
    if (c.category === "practice" || c.category === "policy") {
      return "Most similar organisations are further ahead here. A typical next step is to review whether a more formal approach would fit your size and sector — your peers' position suggests it's become standard practice.";
    }
    return "You're behind most similar organisations on this measure." + (p50 ? ` What good looks like: the peer median is ${p50} — a realistic first milestone.` : "");
  }
  if (pos.kind === "good") {
    return "You're ahead of most similar organisations here — worth protecting, and worth telling your people about.";
  }
  return "You're broadly in line with similar organisations — no urgent action, but watch your movement from the next cycle.";
}

/* only name the peer group on the card when it differs from the page filter */
function cutNote(c) {
  return c.cut && c.cut.label && c.cut.label !== "All peers" ? " · " + c.cut.label : "";
}

/* deterministic readout for multi-select cards (server sends none) */
function multiSelectReadout(c) {
  if (c.type !== "multi_select" || c.suppressed || !c.block || !c.block.options) return null;
  const opts = c.block.options.filter(o => !o.is_na);
  const top = opts.reduce((a, b) => (b.pct > (a ? a.pct : -1) ? b : a), null);
  const mine = c.you ? c.you.labels.length : null;
  if (mine != null && top) {
    return `You selected ${mine} of the ${opts.length} options tracked; the most common among similar organisations is “${top.label}” (${Math.round(top.pct)}%, n=${c.n}).`;
  }
  if (top) return `The most common selection among similar organisations is “${top.label}” (${Math.round(top.pct)}%, n=${c.n}).`;
  return null;
}

/* one at-a-glance position: polarity-adjusted, suppressed-safe.
   Returns null when no judgement applies (neutral polarity / no answer). */
function cardPosition(c) {
  if (c.suppressed || c.locked) return null;
  let p = null, pol = c.polarity;
  if (c.you && c.you.percentile != null) p = c.you.percentile;
  else if (c.score && c.score.percentile != null) { p = c.score.percentile; pol = c.score.polarity; }
  else if (c.type === "matrix" && c.matrix_rows) {
    const ps = c.matrix_rows.filter(r => r.you && r.you.percentile != null && !r.suppressed).map(r => r.you.percentile);
    if (ps.length) p = ps.reduce((a, b) => a + b, 0) / ps.length;
  }
  if (p == null || pol === "neutral" || !pol) return null;
  const adj = pol === "lower_is_better" ? 100 - p : p;
  const kind = adj > 55 ? "good" : adj < 45 ? "bad" : "mid";
  return {
    kind,
    arrow: kind === "good" ? "▲" : kind === "bad" ? "▼" : "●",
    label: (kind === "good" ? "Ahead" : kind === "bad" ? "Behind" : "In line") + " · P" + Math.round(p),
    tip: "Your position vs this peer group, adjusted for whether higher or lower is favourable.",
  };
}
window.cardPosition = cardPosition;

window.CardBody = function ({ card: c, chart, showP1090, showValues, fav, xl }) {
  // popped-out charts get a wider viewBox (more data room, same-size labels);
  // in-card charts get a narrower viewBox so labels render comfortably large
  // in the side-by-side proof column
  const W = xl ? 780 : 340;
  const rowH = xl ? 420 : undefined;
  if (c.suppressed) {
    return html`<div class="suppressed-box">
      <${Icon} name="shield" size=${18} />
      <div style=${{ fontWeight: 650, color: "var(--ink)" }}>Not enough data to show safely</div>
      <${Chip}>n=${c.n}<//>
    </div>`;
  }
  if (c.type === "numeric") {
    const you = c.you ? c.you.value : null;
    return html`
      <div>
        ${c.you ? html`
          <div class="row spread" style=${{ marginBottom: "0" }}>
            <div class="metric-value">${stripUnit(c.you.display, c.unit)}<span class="unit">${unitSuffix(c.unit)}</span></div>
            ${c.block && html`<div class="caption">Peer <${Term} word="median">median<//>: <b>${fmtValue(c.block.p50, c.unit)}</b></div>`}
          </div>` :
        html`<div class="noanswer-box" style=${{ marginBottom: "4px" }}>Answer this to see where you stand among the peers below. <a href="#/submission">Add your data</a></div>`}
        ${chart === "histogram" ? html`<${Histogram} histogram=${c.histogram} you=${you} unit=${c.unit} favourable=${fav} showValues=${showValues} width=${W} />`
        : chart === "box" ? html`<${BoxPlot} block=${c.block} you=${you} unit=${c.unit} favourable=${fav} showValues=${showValues} width=${W} />`
        : html`<${PercentileBand} block=${c.block} you=${you} unit=${c.unit} favourable=${fav} showP1090=${showP1090} showValues=${showValues} width=${W} />`}
      </div>`;
  }
  if (c.type === "single_select" || c.type === "yes_no" || c.type === "multi_select") {
    const youLabels = c.you ? c.you.labels : [];
    if (!c.block) return html`<div class="suppressed-box">No distribution available.</div>`;
    return html`
      <div>
        ${!c.you && html`<div class="noanswer-box" style=${{ marginBottom: "6px" }}><a href="#/submission" style=${{ color: "inherit" }}>Answer this to see where you stand.</a></div>`}
        ${chart === "stacked_bar" && c.type !== "multi_select"
          ? html`<${StackedDist} options=${c.block.options} youLabels=${youLabels} showValues=${showValues} width=${W} fav=${fav} />`
          : html`<${OptionBars} options=${c.block.options} youLabels=${youLabels} showValues=${showValues}
              width=${W} height=${rowH || (c.you ? 172 : 140)} fav=${fav} />`}
      </div>`;
  }
  if (c.type === "matrix") {
    const allSuppressed = (c.matrix_rows || []).every(r => r.suppressed);
    if (allSuppressed) return html`<div class="suppressed-box">
      <${Icon} name="shield" size=${18} />
      <div style=${{ fontWeight: 650, color: "var(--ink)" }}>Not enough data in this peer group</div>
      <div>Fewer than 5 organisations per level — try a wider peer group.</div></div>`;
    return chart === "grouped_bars"
      ? html`<${MatrixGrouped} rows=${c.matrix_rows} unit=${c.unit} showValues=${showValues} width=${W} height=${rowH} fav=${fav} />`
      : html`<${MatrixHeat} rows=${c.matrix_rows} unit=${c.unit} polarity=${c.polarity} showValues=${showValues} width=${W} height=${rowH} />`;
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

/* Day-30 reduced state: the metric stays visible as a shape, never as data.
   Encouraging restore message — a contribution prompt, not a paywall. */
window.ReducedCard = function ({ card: c }) {
  return html`
    <div class="card bench-card locked" id=${"q-" + c.id}>
      <div class="bench-head"><h3 class="bench-title">${c.title}</h3><${Chip} kind="accent">Paused<//></div>
      <div class="bench-n">n=${c.n}</div>
      <div class="bench-chart">
        <div class="blurred" aria-hidden="true">
          <svg viewBox="0 0 420 96" style=${{ width: "100%" }}>
            <rect x="20" y="44" width="380" height="12" rx="6" fill="var(--chart-band)"/>
            <rect x="105" y="44" width="175" height="12" rx="6" fill="var(--chart-band-mid)"/>
            <rect x="196" y="39" width="2.5" height="22" fill="var(--chart-median)"/>
          </svg>
        </div>
      </div>
      <div class="locked-overlay">
        <div class="caption" style=${{ textAlign: "center", maxWidth: "260px" }}>
          ${c.n} organisations have contributed here. Complete your reward data to restore this comparison.
        </div>
        <button class="btn small primary" onClick=${() => nav("/submission")}>Complete your reward data</button>
      </div>
    </div>`;
};

window.OpportunityPanel = function ({ opp }) {
  const main = opp.direction === "saving"
    ? `Closing to median ≈ ${fmtGBPCompact(opp.to_p50_gbp)}/yr`
    : `Reaching median ≈ ${fmtGBPCompact(opp.to_p50_gbp)}/yr investment`;
  return html`
    <div style=${{ background: "var(--blue-tint)", borderRadius: "var(--radius-sm)", padding: "var(--s2) var(--s3)", margin: "var(--s2) 0 0", fontSize: "var(--fs-label)" }}>
      <div class="row spread">
        <b>${main}</b>
        <span class="hastip" style=${{ position: "relative", cursor: "help", color: "var(--blue-deep)" }}>
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
      <div class="row" style=${{ marginTop: "var(--s3)" }}>
        <${Chip}>${c.superpower}${c.subpower ? " · " + c.subpower : ""}<//>
        <${Chip}>${c.category}<//>
        <${Chip}>peer group: ${c.cut.label}, n=${c.n}<//>
      </div>
      <p class="caption" style=${{ marginTop: "var(--s3)" }}>
        Percentiles use linear interpolation across all valid peer answers; anything based on fewer
        than 5 organisations is suppressed. See the <a href="#/methodology" onClick=${onClose}>methodology</a>.
      </p>
      <div class="row" style=${{ justifyContent: "flex-end" }}>
        <button class="btn" onClick=${onClose}>Close</button>
      </div>
    <//>`;
};
