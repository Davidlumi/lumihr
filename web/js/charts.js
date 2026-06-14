/* lumi chart library — one visual language, themed entirely by tokens.
   Rules: data ink is neutral grey; the organisation's own position is the ONLY
   accent (--you), drawn with one marker treatment everywhere; green/amber/red
   appear solely when polarity applies, and only on the "you" marker / delta
   cells. Categorical distributions use the muted --cat ramp. No gridlines or
   chrome that don't earn their place. */
/* global html, fmtValue, pLabel */

const CHART_W = 420;

const CAT_COLOURS = ["var(--cat-1)", "var(--cat-2)", "var(--cat-3)", "var(--cat-4)", "var(--cat-5)", "var(--cat-6)"];

function youColour(fav) {
  if (fav === "good") return "var(--favourable)";    // above the market
  if (fav === "bad") return "var(--unfavourable)";   // below the market
  // "mid" = on the market (inside the 25-75 band) reads neutral, never a verdict;
  // performance colour is reserved for genuine divergence from the market.
  return "var(--you)";
}

/* The single "you" marker: a filled blue diamond (performance-coloured where
   polarity applies) with a value label. Same treatment on every chart. */
function YouDot({ x, y, fav, label, labelY, anchor }) {
  const r = 8;
  return html`
    <g>
      <path d=${`M ${x} ${y - r} L ${x + r} ${y} L ${x} ${y + r} L ${x - r} ${y} Z`}
        fill=${youColour(fav)} stroke="#fff" stroke-width="1.8"/>
      ${label && html`<text x=${x} y=${labelY} text-anchor=${anchor || "middle"} font-size="10.5"
        font-weight="700" fill=${youColour(fav)}>${label}</text>`}
    </g>`;
}
window.YouDot = YouDot;

// ----------------------------------------------------- percentile band -----
// P10–P90 bar, P25–P75 emphasised, median line, "you" marker with value.
window.PercentileBand = function ({ block, you, unit, favourable, showP1090 = true, showValues = true, width = CHART_W }) {
  const W = width, H = 96, padL = 10, padR = 10, barY = 46, barH = 12;
  const lo = Math.min(block.p10, you != null ? you : block.p10);
  const hi = Math.max(block.p90, you != null ? you : block.p90);
  const span = (hi - lo) || 1;
  const x = v => padL + ((v - lo) / span) * (W - padL - padR);
  const marks = [];
  if (showP1090) marks.push(["P10", block.p10], ["P90", block.p90]);
  marks.push(["P25", block.p25], ["P75", block.p75]);
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      ${showP1090 && html`<rect x=${x(block.p10)} y=${barY} width=${Math.max(1, x(block.p90) - x(block.p10))} height=${barH} rx="6" fill="var(--chart-band)" />`}
      <rect x=${x(block.p25)} y=${barY} width=${Math.max(1, x(block.p75) - x(block.p25))} height=${barH} rx="6" fill="var(--chart-band-mid)" />
      <rect x=${x(block.p50) - 1} y=${barY - 5} width="2.5" height=${barH + 10} rx="1.25" fill="var(--chart-median)" />
      <text x=${x(block.p50)} y=${barY + barH + 18} text-anchor="middle" font-size="9.5" fill="var(--ink-soft)" font-weight="600">P50${showValues ? " · " + fmtValue(block.p50, unit) : ""}</text>
      ${marks.map(([lbl, v]) => html`
        <g key=${lbl}>
          <line x1=${x(v)} x2=${x(v)} y1=${barY - 2} y2=${barY + barH + 2} stroke="var(--chart-axis)" stroke-width="1"/>
          <text x=${x(v)} y=${barY + barH + 18} text-anchor="middle" font-size="9" fill="var(--ink-faint)">${lbl}</text>
        </g>`)}
      ${you != null && html`<${YouDot} x=${x(you)} y=${barY + barH / 2} fav=${favourable}
        label=${"You" + (showValues ? " · " + fmtValue(you, unit) : "")} labelY=${barY - 14} />`}
    </svg>`;
};

// ----------------------------------------------------------- histogram -----
window.Histogram = function ({ histogram: hist, you, unit, favourable, median = null, showValues = true, width = CHART_W }) {
  if (!hist || !hist.bins) return null;
  const W = width, H = 116, padL = 10, padB = 18, padT = 18;
  const n = hist.bins.length, maxC = Math.max(...hist.bins, 1);
  const bw = (W - padL * 2) / n;
  const x = v => padL + ((v - hist.min) / ((hist.max - hist.min) || 1)) * (W - padL * 2);
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      ${hist.bins.map((c, i) => html`
        <rect key=${i} x=${padL + i * bw + 1} width=${Math.max(1, bw - 2)}
          y=${padT + (1 - c / maxC) * (H - padT - padB)} height=${(c / maxC) * (H - padT - padB)}
          rx="2" fill="var(--chart-band-mid)" />`)}
      ${median != null && median >= hist.min && median <= hist.max && html`
        <g>
          <line x1=${x(median)} x2=${x(median)} y1=${padT} y2=${H - padB} stroke="var(--chart-median)"
            stroke-width="1.5" stroke-dasharray="3 3" />
          <text x=${x(median)} y=${H - 5} text-anchor="middle" font-size="9" fill="var(--ink-soft)" font-weight="600">P50</text>
        </g>`}
      <text x=${padL} y=${H - 4} font-size="9" fill="var(--ink-faint)">${fmtValue(hist.min, unit)}</text>
      <text x=${W - padL} y=${H - 4} text-anchor="end" font-size="9" fill="var(--ink-faint)">${fmtValue(hist.max, unit)}</text>
      ${you != null && html`
        <g>
          <line x1=${x(you)} x2=${x(you)} y1=${padT - 2} y2=${H - padB} stroke=${youColour(favourable)} stroke-width="2" />
          <${YouDot} x=${x(you)} y=${padT - 2} fav=${favourable}
            label=${"You" + (showValues ? " · " + fmtValue(you, unit) : "")} labelY=${10} />
        </g>`}
    </svg>`;
};

// ------------------------------------------------------------- box plot ----
window.BoxPlot = function ({ block, you, unit, favourable, showValues = true, width = CHART_W }) {
  const W = width, H = 104, padL = 10, padR = 10, midY = 50, boxH = 26;
  const lo = Math.min(block.p10, you != null ? you : block.p10);
  const hi = Math.max(block.p90, you != null ? you : block.p90);
  const span = (hi - lo) || 1;
  const x = v => padL + ((v - lo) / span) * (W - padL - padR);
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      <line x1=${x(block.p10)} x2=${x(block.p90)} y1=${midY} y2=${midY} stroke="var(--chart-axis)" stroke-width="1.4"/>
      <line x1=${x(block.p10)} x2=${x(block.p10)} y1=${midY - 9} y2=${midY + 9} stroke="var(--chart-axis)" stroke-width="1.4"/>
      <line x1=${x(block.p90)} x2=${x(block.p90)} y1=${midY - 9} y2=${midY + 9} stroke="var(--chart-axis)" stroke-width="1.4"/>
      <rect x=${x(block.p25)} y=${midY - boxH / 2} width=${Math.max(1, x(block.p75) - x(block.p25))} height=${boxH}
        rx="4" fill="var(--chart-band)" stroke="var(--chart-band-mid)"/>
      <rect x=${x(block.p50) - 1.25} y=${midY - boxH / 2} width="2.5" height=${boxH} fill="var(--chart-median)"/>
      <text x=${x(block.p10)} y=${midY + 28} text-anchor="middle" font-size="9" fill="var(--ink-faint)">P10</text>
      <text x=${x(block.p50)} y=${midY + 28} text-anchor="middle" font-size="9.5" fill="var(--ink-soft)" font-weight="600">P50${showValues ? " · " + fmtValue(block.p50, unit) : ""}</text>
      <text x=${x(block.p90)} y=${midY + 28} text-anchor="middle" font-size="9" fill="var(--ink-faint)">P90</text>
      ${you != null && html`<${YouDot} x=${x(you)} y=${midY} fav=${favourable}
        label=${"You" + (showValues ? " · " + fmtValue(you, unit) : "")} labelY=${midY - boxH / 2 - 8} />`}
    </svg>`;
};

// ------------------------------------------------------- option bars -------
// THE primary categorical language: muted bars, your option in the "you" accent.
window.OptionBars = function ({ options, youLabels, showValues = true, width = CHART_W, height, fav }) {
  const opts = options.filter(o => o.count > 0 || !o.is_na);
  const H = height || 172;
  // few options stretch to fill the chart region; many options compress to fit;
  // popped-out regions (H > 300) allow taller rows
  let cap = opts.length <= 3 ? 42 : opts.length <= 5 ? 32 : 27;
  if (H > 300) cap += 16;
  const rowH = Math.max(15, Math.min(cap, Math.floor((H - 6) / Math.max(opts.length, 1))));
  const fs = rowH >= 22 ? 10.5 : 9.5;
  // label gutter sized to the actual labels, not a fixed share of the card
  const longest = Math.max(...opts.map(o => Math.min(o.label.length, 34)), 3);
  const labelW = Math.min(190, Math.max(34, longest * fs * 0.54) + 10), W = width;
  const maxP = Math.max(...opts.map(o => o.pct), 1);
  const usedH = opts.length * rowH + 4;
  const mine = new Set((youLabels || []).map(s => s.toLowerCase()));
  return html`
    <svg viewBox="0 0 ${W} ${usedH}" style=${{ width: "100%", display: "block" }}>
      ${opts.map((o, i) => {
        const sel = mine.has(o.label.toLowerCase());
        const y = i * rowH;
        const bw = (o.pct / maxP) * (W - labelW - 86);
        const maxChars = Math.floor(labelW / (fs * 0.52));
        return html`
        <g key=${o.code}>
          <text x=${labelW - 8} y=${y + rowH / 2 + fs * 0.34} text-anchor="end" font-size=${fs}
            fill=${sel ? "var(--ink)" : "var(--ink-soft)"} font-weight=${sel ? 700 : 400}>
            ${o.label.length > maxChars ? o.label.slice(0, maxChars - 1) + "…" : o.label}</text>
          <rect x=${labelW} y=${y + Math.max(2, rowH * 0.16)} width=${Math.max(2, bw)}
            height=${Math.max(8, rowH - Math.max(4, rowH * 0.32))} rx="3.5"
            fill=${sel ? youColour(fav) : "var(--cat-5)"}/>
          ${showValues && html`<text x=${labelW + Math.max(2, bw) + 6} y=${y + rowH / 2 + fs * 0.34} font-size=${fs}
            fill=${sel ? youColour(fav) : "var(--ink-faint)"} font-weight=${sel ? 700 : 500}>${o.pct}%${sel ? " · You" : ""}</text>`}
        </g>`;
      })}
    </svg>`;
};

// ------------------------------------------------ ordered distribution ------
// THE chart for categorical scales (2026-06-12 redesign). One bar per
// category in the question's defined order, label directly beside its own
// bar, % on the bar, the org's answer marked IN PLACE — no detached legend,
// no "+N more": every category is visible, zero-count real options included
// so the scale's full shape shows (only zero-count N/A rows are dropped).
// A thin ordinal rail signals "this is a scale". Presentation only: the
// options arrive in library order from the same payload as before.
window.OrderedDist = function ({ options, youLabels, showValues = true, width = CHART_W, height, fav }) {
  const opts = (options || []).filter(o => o.count > 0 || !o.is_na);
  const H = height || 172;
  let cap = opts.length <= 3 ? 42 : opts.length <= 5 ? 32 : 27;
  if (H > 300) cap += 16;
  const rowH = Math.max(15, Math.min(cap, Math.floor((H - 6) / Math.max(opts.length, 1))));
  const fs = rowH >= 22 ? 10.5 : 9.5;
  const longest = Math.max(...opts.map(o => Math.min(o.label.length, 34)), 3);
  const labelW = Math.min(190, Math.max(34, longest * fs * 0.54) + 10), W = width;
  const railX = labelW + 5;
  const maxP = Math.max(...opts.map(o => o.pct), 1);
  const usedH = opts.length * rowH + 4;
  const mine = new Set((youLabels || []).map(s => s.toLowerCase()));
  return html`
    <svg viewBox="0 0 ${W} ${usedH}" style=${{ width: "100%", display: "block" }}>
      <line x1=${railX} x2=${railX} y1=${rowH / 2} y2=${usedH - rowH / 2 - 2}
        stroke="var(--chart-axis)" stroke-width="1"/>
      ${opts.map((o, i) => {
        const sel = mine.has(o.label.toLowerCase());
        const y = i * rowH, cy = y + rowH / 2;
        const bw = (o.pct / maxP) * (W - railX - 96);
        const maxChars = Math.floor(labelW / (fs * 0.52));
        return html`
        <g key=${o.code || o.label}>
          <text x=${labelW - 4} y=${cy + fs * 0.34} text-anchor="end" font-size=${fs}
            fill=${sel ? "var(--ink)" : "var(--ink-soft)"} font-weight=${sel ? 700 : 400}>
            ${o.label.length > maxChars ? o.label.slice(0, maxChars - 1) + "…" : o.label}</text>
          <circle cx=${railX} cy=${cy} r=${sel ? 3.4 : 2.2}
            fill=${sel ? youColour(fav) : "var(--chart-axis)"}/>
          <rect x=${railX + 6} y=${y + Math.max(2, rowH * 0.16)} width=${Math.max(o.pct > 0 ? 2 : 0.5, bw)}
            height=${Math.max(8, rowH - Math.max(4, rowH * 0.32))} rx="3.5"
            fill=${sel ? youColour(fav) : "var(--cat-5)"} opacity=${o.pct > 0 ? 1 : 0.45}/>
          ${showValues && html`<text x=${railX + 6 + Math.max(2, bw) + 6} y=${cy + fs * 0.34} font-size=${fs}
            fill=${sel ? youColour(fav) : "var(--ink-faint)"} font-weight=${sel ? 700 : 500}>${o.pct}%${sel ? " · You" : ""}</text>`}
        </g>`;
      })}
    </svg>`;
};

// --------------------------------------------------------------- heatmap ---
// Numeric matrix rows: a per-level DISTRIBUTION STRIP — the peer middle-50%
// (P25–P75) band, the median tick, and the org's own marker, all on ONE shared
// scale so levels are comparable at a glance (e.g. pay rising up the ladder
// reads as a staircase). Flanked by the exact peer-median and "you" numbers and
// the percentile. The "you" marker is delta-coloured by polarity (semantic use
// only — neutral metrics get the plain blue accent). HTML, tokenised, equal
// rows — parity with the categorical heatmap.
window.MatrixHeat = function ({ rows, unit, polarity, showValues = true }) {
  const live = (rows || []).filter(r => !r.suppressed && r.block);
  let lo = Infinity, hi = -Infinity;
  live.forEach(r => {
    const b = r.block, y = r.you ? r.you.value : null;
    [b.p25, b.p50, b.p75, y].forEach(v => { if (v != null) { if (v < lo) lo = v; if (v > hi) hi = v; } });
  });
  if (!isFinite(lo)) { lo = 0; hi = 1; }
  const rawLo = lo, rawHi = hi, pad = ((hi - lo) || 1) * 0.06;
  lo -= pad; hi += pad;
  const X = v => ((v - lo) / ((hi - lo) || 1)) * 100;
  const favOf = (you, p50) => {
    if (you == null || p50 == null) return null;
    const rel = p50 !== 0 ? (you - p50) / Math.abs(p50) : (you ? 1 : 0);
    if (Math.abs(rel) <= 0.02) return "mid";
    const above = rel > 0;
    if (polarity === "higher_is_better") return above ? "good" : "bad";
    if (polarity === "lower_is_better") return above ? "bad" : "good";
    return "mid";
  };
  return html`
    <div class="matrix-num-wrap">
      <table class="matrix-num">
        <thead>
          <tr>
            <th class="mn-lvl">Level</th>
            <th class="mn-num">Median</th>
            <th class="mn-strip-h">Where the market sits · you</th>
            <th class="mn-num">You</th>
            <th class="mn-num">Position</th>
          </tr>
        </thead>
        <tbody>
          ${(rows || []).map(r => {
            if (r.suppressed || !r.block) return html`
              <tr key=${r.row_id} class="mn-row"><td class="mn-lvl"><span class="mn-lvl-txt" title=${r.label}>${r.label}</span></td>
                <td colspan="4" class="mn-supp caption">not enough organisations to show safely</td></tr>`;
            const b = r.block, you = r.you ? r.you.value : null;
            const f = favOf(you, b.p50);
            return html`
              <tr key=${r.row_id} class="mn-row">
                <td class="mn-lvl"><span class="mn-lvl-txt" title=${r.label}>${r.label}</span></td>
                <td class="mn-num mn-p50">${fmtValue(b.p50, unit)}</td>
                <td class="mn-strip">
                  <div class="mn-track">
                    <div class="mn-iqr" style=${{ left: X(b.p25) + "%", width: Math.max(1.5, X(b.p75) - X(b.p25)) + "%" }}></div>
                    <div class="mn-median" style=${{ left: X(b.p50) + "%" }}></div>
                    ${you != null && html`<div class=${"mn-you" + (f === "good" ? " good" : f === "bad" ? " bad" : "")}
                      style=${{ left: X(you) + "%" }} title=${"You · " + r.you.display}></div>`}
                  </div>
                </td>
                <td class=${"mn-num mn-youval" + (f === "good" ? " good" : f === "bad" ? " bad" : "")}>
                  ${you != null ? html`<b>${r.you.display}</b>` : html`<span class="caption">—</span>`}</td>
                <td class="mn-num mn-pos">${r.you && r.you.percentile != null ? pLabel(r.you.percentile) : html`<span class="caption">—</span>`}</td>
              </tr>`;
          })}
        </tbody>
      </table>
      <div class="matrix-num-scale">
        <span class="mleg"><span class="mn-key-iqr"></span>middle 50% of the market</span>
        <span class="mleg"><span class="mn-key-median"></span>market median</span>
        <span class="mleg"><span class="mn-key-you"></span>your organisation</span>
        ${live.length > 0 && html`<span class="caption mn-scale-range">scale ${fmtValue(rawLo, unit)} – ${fmtValue(rawHi, unit)}</span>`}
      </div>
    </div>`;
};

// ---------------------------------------------------------- grouped bars ---
window.MatrixGrouped = function ({ rows, unit, showValues = true, width = CHART_W, height, fav }) {
  const H = height || 172;
  const rowH = Math.max(22, Math.min(H > 300 ? 52 : 34, Math.floor((H - 18) / Math.max(rows.length, 1))));
  const labelW = Math.min(150, width * 0.38), W = width;
  const usedH = rows.length * rowH + 16;
  const vals = rows.flatMap(r => [r.suppressed ? null : (r.block || {}).p50, r.you ? r.you.value : null]).filter(v => v != null);
  const maxV = Math.max(...vals, 1);
  const bw = v => Math.max(2, (v / maxV) * (W - labelW - 64));
  const bh = Math.max(6, Math.floor(rowH * 0.3));
  return html`
    <svg viewBox="0 0 ${W} ${usedH}" style=${{ width: "100%", display: "block" }}>
      ${rows.map((r, i) => {
        const y = i * rowH + 6;
        const p50 = r.suppressed ? null : (r.block || {}).p50;
        const you = r.you ? r.you.value : null;
        return html`
        <g key=${r.row_id}>
          <text x=${labelW - 8} y=${y + rowH / 2 - 2} text-anchor="end" font-size="9.5" fill="var(--ink-soft)">
            ${r.label.length > 22 ? r.label.slice(0, 21) + "…" : r.label}</text>
          ${p50 != null ? html`<rect x=${labelW} y=${y} width=${bw(p50)} height=${bh} rx="2.5" fill="var(--chart-band-mid)"/>` :
          html`<text x=${labelW} y=${y + bh - 1} font-size="9" fill="var(--ink-faint)">n<5 — suppressed</text>`}
          ${p50 != null && showValues && html`<text x=${labelW + bw(p50) + 5} y=${y + bh - 1} font-size="9" fill="var(--ink-faint)">${fmtValue(p50, unit)}</text>`}
          ${you != null && html`<rect x=${labelW} y=${y + bh + 2} width=${bw(you)} height=${bh} rx="2.5" fill=${youColour(fav)}/>`}
          ${you != null && showValues && html`<text x=${labelW + bw(you) + 5} y=${y + bh * 2 + 1} font-size="9" font-weight="700" fill=${youColour(fav)}>${fmtValue(you, unit)} · You</text>`}
        </g>`;
      })}
      <g>
        <rect x=${labelW} y=${usedH - 10} width="8" height="8" rx="2" fill="var(--chart-band-mid)"/>
        <text x=${labelW + 12} y=${usedH - 3} font-size="9" fill="var(--ink-soft)">Peer P50</text>
        <rect x=${labelW + 70} y=${usedH - 10} width="8" height="8" rx="2" fill=${youColour(fav)}/>
        <text x=${labelW + 82} y=${usedH - 3} font-size="9" fill="var(--ink-soft)">You</text>
      </g>
    </svg>`;
};

// ------------------------------------------------------------ quartile dots
window.QuartileDots = function ({ quartiles }) {
  const total = quartiles.reduce((a, b) => a + b, 0) || 1;
  return html`
    <div class="qdots" title="Where your metrics fall across market quartiles (Q1 lowest → Q4 highest)">
      ${quartiles.map((c, i) => html`
        <div key=${i} class="qdot" style=${{
          background: c ? `color-mix(in srgb, var(--cat-1) ${Math.round(22 + 78 * c / total)}%, var(--surface-sunk))` : "var(--surface-sunk)",
        }}></div>`)}
    </div>`;
};

// --------------------------------------- matrix export twins (HTML→SVG) ----
// The two matrix charts render as polished HTML (crisp text, easy layout), so
// the SVG raster exporter has nothing to serialise. Rather than rasterise the
// DOM (fragile), we rebuild an equivalent SVG from the SAME card data — sharing
// matrixBandOrder() with the on-screen renderer so the two can never drift.

// Topological band order for categorical matrices — the ONE non-trivial bit
// shared by the HTML heatmap (MatrixSelect) and this export twin.
window.matrixBandOrder = function (live) {
  const adj = new Map(), indeg = new Map(), nodes = [];
  const ensure = l => { if (!indeg.has(l)) { indeg.set(l, 0); adj.set(l, new Set()); nodes.push(l); } };
  (live || []).forEach(r => {
    const os = ((r.block && r.block.options) || []).map(o => o.label);
    os.forEach(ensure);
    for (let i = 0; i + 1 < os.length; i++) {
      if (!adj.get(os[i]).has(os[i + 1])) { adj.get(os[i]).add(os[i + 1]); indeg.set(os[i + 1], indeg.get(os[i + 1]) + 1); }
    }
  });
  const order = [], placed = new Set();
  while (order.length < nodes.length) {
    const pick = nodes.find(n => !placed.has(n) && indeg.get(n) === 0);
    if (pick == null) { nodes.forEach(n => { if (!placed.has(n)) { order.push(n); placed.add(n); } }); break; }
    order.push(pick); placed.add(pick); indeg.set(pick, -1);
    adj.get(pick).forEach(m => { if (indeg.get(m) > 0) indeg.set(m, indeg.get(m) - 1); });
  }
  return order;
};

function clipTxt(s, n) { s = String(s || ""); return s.length > n ? s.slice(0, n - 1) + "…" : s; }
function abbrBand(l) {
  return (l || "").replace(/^More than\s*/i, ">").replace(/\bweeks?\b/i, "wk")
    .replace(/\bmonths?\b/i, "mo").replace(/\bdays?\b/i, "d").trim();
}
function mixBlueRGB(t) {
  const b = [37, 71, 176];
  return "rgb(" + Math.round(255 + (b[0] - 255) * t) + "," + Math.round(255 + (b[1] - 255) * t)
    + "," + Math.round(255 + (b[2] - 255) * t) + ")";
}
function svgEl(W, H, inner) {
  const str = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}">`
    + `<g font-family="Helvetica, Arial, sans-serif">${inner}</g></svg>`;
  return new DOMParser().parseFromString(str, "image/svg+xml").documentElement;
}

function buildSelectSVG(card, tok) {
  const rows = card.matrix_rows || [];
  const live = rows.filter(r => !r.suppressed && r.block && r.block.options);
  const order = matrixBandOrder(live);
  let maxPct = 1; live.forEach(r => (r.block.options || []).forEach(o => { if (o.pct > maxPct) maxPct = o.pct; }));
  const Lw = 160, Yw = 64, bw = 58, Hh = 24, Rh = 30, n = order.length;
  const W = Lw + n * bw + Yw, R = rows.length, H = Hh + R * Rh + 4;
  let s = `<text x="4" y="${Hh - 8}" font-size="10" font-weight="700" fill="${tok.inkSoft}">LEVEL</text>`;
  order.forEach((b, ci) => { s += `<text x="${Lw + ci * bw + bw / 2}" y="${Hh - 8}" text-anchor="middle" font-size="9.5" font-weight="700" fill="${tok.inkSoft}">${esc(abbrBand(b))}</text>`; });
  s += `<text x="${W - 4}" y="${Hh - 8}" text-anchor="end" font-size="10" font-weight="700" fill="${tok.inkSoft}">YOU</text>`;
  rows.forEach((r, ri) => {
    const y = Hh + ri * Rh, cy = y + Rh / 2 + 4;
    s += `<text x="4" y="${cy}" font-size="11" fill="${tok.ink}">${esc(clipTxt(r.label, 24))}</text>`;
    if (r.suppressed || !r.block) { s += `<text x="${Lw}" y="${cy}" font-size="10" fill="${tok.inkSoft}">not enough organisations</text>`; return; }
    const pm = {}; (r.block.options || []).forEach(o => { pm[o.label] = o.pct; });
    const youLabel = r.you ? (r.you.label || r.you.display) : null, modal = r.block.modal_label;
    order.forEach((b, ci) => {
      const pct = pm[b] || 0, cx = Lw + ci * bw, ry = y + 3, ch = Rh - 6, cw = bw - 4;
      if (pct <= 0) { s += `<rect x="${cx}" y="${ry}" width="${cw}" height="${ch}" rx="6" fill="${tok.sunk}"/>`; return; }
      const t = 0.14 + 0.86 * (pct / maxPct);
      s += `<rect x="${cx}" y="${ry}" width="${cw}" height="${ch}" rx="6" fill="${mixBlueRGB(t)}"`
        + (youLabel && b === youLabel ? ` stroke="${tok.blueDeep}" stroke-width="2"` : "") + `/>`;
      const r0 = Math.round(pct);
      s += `<text x="${cx + cw / 2}" y="${ry + ch / 2 + 4}" text-anchor="middle" font-size="11" font-weight="${b === modal ? 700 : 600}" fill="${t >= 0.52 ? "#fff" : tok.ink}">${r0 > 0 ? r0 + "%" : "&lt;1%"}</text>`;
    });
    s += r.you
      ? `<text x="${W - 4}" y="${cy}" text-anchor="end" font-size="11" font-weight="700" fill="${tok.blueDeep}">${esc(abbrBand(r.you.display))}</text>`
      : `<text x="${W - 4}" y="${cy}" text-anchor="end" font-size="11" fill="${tok.inkSoft}">—</text>`;
  });
  return svgEl(W, H, s);
}

function buildNumSVG(card, tok) {
  const rows = card.matrix_rows || [], unit = card.unit, polarity = card.polarity;
  const live = rows.filter(r => !r.suppressed && r.block);
  let lo = Infinity, hi = -Infinity;
  live.forEach(r => { const b = r.block, yv = r.you ? r.you.value : null; [b.p25, b.p50, b.p75, yv].forEach(v => { if (v != null) { if (v < lo) lo = v; if (v > hi) hi = v; } }); });
  if (!isFinite(lo)) { lo = 0; hi = 1; }
  const pad = ((hi - lo) || 1) * 0.06, Lo = lo - pad, Hi = hi + pad;
  const Lw = 150, Mw = 66, Sw = 300, Yw = 70, Pw = 52, Hh = 24, Rh = 32;
  const Sx = Lw + Mw, W = Lw + Mw + Sw + Yw + Pw, R = rows.length, H = Hh + R * Rh + 4;
  const X = v => Sx + ((v - Lo) / ((Hi - Lo) || 1)) * Sw;
  const favOf = (you, p50) => {
    if (you == null || p50 == null) return null;
    const rel = p50 !== 0 ? (you - p50) / Math.abs(p50) : (you ? 1 : 0);
    if (Math.abs(rel) <= 0.02) return "mid";
    const a = rel > 0;
    if (polarity === "higher_is_better") return a ? "good" : "bad";
    if (polarity === "lower_is_better") return a ? "bad" : "good";
    return "mid";
  };
  let s = `<text x="4" y="${Hh - 8}" font-size="10" font-weight="700" fill="${tok.inkSoft}">LEVEL</text>`
    + `<text x="${Lw + Mw - 6}" y="${Hh - 8}" text-anchor="end" font-size="10" font-weight="700" fill="${tok.inkSoft}">MEDIAN</text>`
    + `<text x="${Sx + 4}" y="${Hh - 8}" font-size="10" font-weight="700" fill="${tok.inkSoft}">WHERE PEERS SIT · YOU</text>`
    + `<text x="${Sx + Sw + Yw - 6}" y="${Hh - 8}" text-anchor="end" font-size="10" font-weight="700" fill="${tok.inkSoft}">YOU</text>`
    + `<text x="${W - 4}" y="${Hh - 8}" text-anchor="end" font-size="10" font-weight="700" fill="${tok.inkSoft}">POS</text>`;
  rows.forEach((r, ri) => {
    const y = Hh + ri * Rh, cy = y + Rh / 2;
    s += `<text x="4" y="${cy + 4}" font-size="11" fill="${tok.ink}">${esc(clipTxt(r.label, 20))}</text>`;
    if (r.suppressed || !r.block) { s += `<text x="${Lw + Mw - 6}" y="${cy + 4}" text-anchor="end" font-size="10" fill="${tok.inkSoft}">n&lt;5</text>`; return; }
    const b = r.block, yv = r.you ? r.you.value : null, f = favOf(yv, b.p50);
    s += `<text x="${Lw + Mw - 6}" y="${cy + 4}" text-anchor="end" font-size="10.5" font-weight="600" fill="${tok.ink}">${esc(fmtValue(b.p50, unit))}</text>`;
    s += `<line x1="${Sx}" x2="${Sx + Sw}" y1="${cy}" y2="${cy}" stroke="${tok.grid}" stroke-width="1"/>`;
    s += `<rect x="${X(b.p25)}" y="${cy - 4.5}" width="${Math.max(2, X(b.p75) - X(b.p25))}" height="9" rx="4.5" fill="${tok.bandMid}"/>`;
    s += `<rect x="${X(b.p50) - 1}" y="${cy - 7.5}" width="2" height="15" fill="${tok.median}"/>`;
    if (yv != null) { const xx = X(yv), col = f === "good" ? tok.fav : f === "bad" ? tok.unfav : tok.you, rr = 5.5;
      s += `<path d="M ${xx} ${cy - rr} L ${xx + rr} ${cy} L ${xx} ${cy + rr} L ${xx - rr} ${cy} Z" fill="${col}" stroke="#fff" stroke-width="1.5"/>`; }
    const yvcol = f === "good" ? tok.fav : f === "bad" ? tok.unfav : tok.blueDeep;
    s += r.you
      ? `<text x="${Sx + Sw + Yw - 6}" y="${cy + 4}" text-anchor="end" font-size="11" font-weight="700" fill="${yvcol}">${esc(r.you.display)}</text>`
      : `<text x="${Sx + Sw + Yw - 6}" y="${cy + 4}" text-anchor="end" font-size="11" fill="${tok.inkSoft}">—</text>`;
    s += `<text x="${W - 4}" y="${cy + 4}" text-anchor="end" font-size="10.5" fill="${tok.inkSoft}">${esc(r.you && r.you.percentile != null ? pLabel(r.you.percentile) : "—")}</text>`;
  });
  return svgEl(W, H, s);
}

window.buildMatrixSVG = function (card) {
  const cs = getComputedStyle(document.documentElement), T = n => cs.getPropertyValue(n).trim() || "#333";
  const tok = { ink: T("--ink"), inkSoft: T("--ink-soft"), grid: T("--chart-grid"), sunk: T("--surface-sunk"),
    bandMid: T("--chart-band-mid"), median: T("--chart-median"), you: T("--you"), blueDeep: T("--blue-deep"),
    fav: T("--favourable"), unfav: T("--unfavourable") };
  const rows = card.matrix_rows || [];
  return rows.some(r => r.block && r.block.kind === "select") ? buildSelectSVG(card, tok) : buildNumSVG(card, tok);
};

// ------------------------------------------------------------- PNG export --
window.exportCardPNG = async function (cardEl, meta, mode) {
  // chart svg lives inside the chart container — scope the lookup so we never
  // grab a kebab/status icon; matrix cards render as HTML, so rebuild an SVG
  // twin from the card data.
  let svg = cardEl.querySelector(".bench-chart-full svg") || cardEl.querySelector(".metric-xl svg")
    || cardEl.querySelector(".bench-chart svg");
  if (!svg && meta.card && meta.card.type === "matrix") svg = buildMatrixSVG(meta.card);
  if (!svg) svg = cardEl.querySelector("svg");
  if (!svg) return false;
  const clone = svg.cloneNode(true);
  const vb = (svg.getAttribute("viewBox") || "0 0 420 120").split(" ").map(Number);
  const cw = vb[2], ch = vb[3];
  const PAD = 18, TITLE_H = 46, FOOT_H = 26;
  const W = cw + PAD * 2, H = ch + TITLE_H + FOOT_H + PAD;
  const wrap = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  wrap.setAttribute("viewBox", `0 0 ${W} ${H}`);
  wrap.setAttribute("width", W * 2); wrap.setAttribute("height", H * 2);
  const styles = getComputedStyle(document.documentElement);
  const resolve = node => {
    if (node.nodeType !== 1) return;
    for (const attr of ["fill", "stroke"]) {
      const v = node.getAttribute && node.getAttribute(attr);
      if (v && v.startsWith("var(")) {
        const name = v.slice(4, -1).trim();
        node.setAttribute(attr, styles.getPropertyValue(name).trim() || "#333");
      }
    }
    node.childNodes.forEach(resolve);
  };
  resolve(clone);
  wrap.innerHTML = `
    <rect x="0" y="0" width="${W}" height="${H}" fill="#ffffff"/>
    <text x="${PAD}" y="${PAD + 6}" font-family="Helvetica, Arial" font-size="13" font-weight="700" fill="#211B26">${esc(meta.title)}</text>
    <text x="${PAD}" y="${PAD + 24}" font-family="Helvetica, Arial" font-size="10" fill="#5B5560">${esc(meta.cutLabel)} · n=${meta.n}${meta.suffix ? " · " + esc(meta.suffix) : ""}</text>
    <text x="${PAD}" y="${H - 10}" font-family="Helvetica, Arial" font-size="9" fill="#8E8893">lumi people analytics benchmark · ${esc(meta.window || "")} · generated ${new Date().toLocaleDateString("en-GB")}</text>`;
  const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
  g.setAttribute("transform", `translate(${PAD}, ${TITLE_H + 8})`);
  g.setAttribute("font-family", "Helvetica, Arial, sans-serif");
  while (clone.firstChild) g.appendChild(clone.firstChild);
  wrap.appendChild(g);

  const blob = new Blob([new XMLSerializer().serializeToString(wrap)], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const img = new Image();
  await new Promise((res, rej) => { img.onload = res; img.onerror = rej; img.src = url; });
  const canvas = document.createElement("canvas");
  canvas.width = W * 2; canvas.height = H * 2;
  canvas.getContext("2d").drawImage(img, 0, 0);
  URL.revokeObjectURL(url);
  if (mode === "clipboard" && navigator.clipboard && window.ClipboardItem) {
    const png = await new Promise(r => canvas.toBlob(r, "image/png"));
    await navigator.clipboard.write([new ClipboardItem({ "image/png": png })]);
    return "copied";
  }
  const a = document.createElement("a");
  a.href = canvas.toDataURL("image/png");
  a.download = (meta.title || "lumi-chart").toLowerCase().replace(/[^a-z0-9]+/g, "-") + ".png";
  a.click();
  return "downloaded";
};
function esc(s) { return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;"); }
