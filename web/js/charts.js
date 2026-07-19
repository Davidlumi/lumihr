/* lumi chart library — one visual language, themed entirely by tokens.
   Rules: data ink is neutral grey; the organisation's own position is the ONLY
   accent (--you), drawn with one marker treatment everywhere; green/amber/red
   appear solely when polarity applies, and only on the "you" marker / delta
   cells. Categorical distributions use the muted --cat ramp. No gridlines or
   chrome that don't earn their place. */
/* global html, fmtValue, pLabel */

const CHART_W = 420;

function youColour(fav) {
  if (fav === "good") return "var(--favourable)";    // above the market
  if (fav === "bad") return "var(--unfavourable)";   // below the market
  // "mid" = on the market (inside the 25-75 band) reads neutral, never a verdict;
  // performance colour is reserved for genuine divergence from the market.
  return "var(--you)";
}
// a SHAPE cue for the verdict that survives greyscale / colour-blindness — mirrors
// the ▲/▼ on the position pill, so green-vs-red is never the only signal.
function favGlyph(fav) { return fav === "good" ? "▲" : fav === "bad" ? "▼" : ""; }

/* The single "you" marker: a filled blue diamond (performance-coloured where
   polarity applies) with a value label. Same treatment on every chart. When
   `bounds` [minX, maxX] is given the middle-anchored label is clamped to stay
   inside the canvas, so a "You · £12,345" at P90+ can't clip off the edge. */
function YouDot({ x, y, fav, label, labelY, anchor, bounds }) {
  const r = 8;
  let lx = x, la = anchor || "middle";
  if (label && bounds && la === "middle") {
    const halfW = (favGlyph(fav) ? 2 : 0) + label.length * 0.52 * 10.5 / 2;  // ~char width at fs 10.5
    lx = Math.max(bounds[0] + halfW, Math.min(bounds[1] - halfW, x));
  }
  return html`
    <g>
      <path d=${`M ${x} ${y - r} L ${x + r} ${y} L ${x} ${y + r} L ${x - r} ${y} Z`}
        fill=${youColour(fav)} stroke="#fff" stroke-width="1.8"/>
      ${label && html`<text x=${lx} y=${labelY} text-anchor=${la} font-size="10.5"
        font-weight="700" fill=${youColour(fav)}>${favGlyph(fav) ? favGlyph(fav) + " " : ""}${label}</text>`}
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
        label=${"You" + (showValues ? " · " + fmtValue(you, unit) : "")} labelY=${barY - 14} bounds=${[padL, W - padR]} />`}
    </svg>`;
};

// ----------------------------------------------------------- histogram -----
window.Histogram = function ({ histogram: hist, you, unit, favourable, median = null, showValues = true, width = CHART_W }) {
  if (!hist || !hist.bins) return null;
  const W = width, H = 116, padL = 10, padB = 18, padT = 18;
  const n = hist.bins.length, maxC = Math.max(...hist.bins, 1);
  const bw = (W - padL * 2) / n;
  const x = v => padL + ((v - hist.min) / ((hist.max - hist.min) || 1)) * (W - padL * 2);
  // The "you" marker can sit outside the peer min/max; clamp ONLY the marker to
  // the canvas so it pins to the edge instead of drawing off-screen. Bars and
  // axis labels keep the raw x() scale.
  const xClamp = v => Math.max(padL, Math.min(W - padL, x(v)));
  // Degenerate distribution: every peer gave the same value (one populated bin,
  // or a zero-width range). A lone spike reads as "spread" — render an honest
  // unanimous state instead, still placing the "you" marker against the consensus.
  const nonZero = hist.bins.filter(c => c > 0).length;
  const unanimous = nonZero <= 1 || hist.max === hist.min;
  if (unanimous) {
    const consensus = (hist.max + hist.min) / 2;
    const off = you != null && you !== consensus;
    return html`
      <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
        <line x1=${x(consensus)} x2=${x(consensus)} y1=${padT} y2=${H - padB} stroke="var(--chart-median)" stroke-width="2"/>
        <text x=${W / 2} y=${padT - 4} text-anchor="middle" font-size="10" fill="var(--ink-soft)" font-weight="600">The market is unanimous here</text>
        <text x=${x(consensus)} y=${H - 5} text-anchor="middle" font-size="9" fill="var(--ink-faint)">Everyone: ${fmtValue(consensus, unit)}</text>
        ${you != null && html`
          <${YouDot} x=${xClamp(you)} y=${padT + (H - padT - padB) / 2} fav=${off ? favourable : "mid"}
            anchor=${you < hist.min ? "start" : you > hist.max ? "end" : "middle"} bounds=${[padL, W - padL]}
            label=${"You" + (showValues ? " · " + fmtValue(you, unit) : "")} labelY=${padT + (H - padT - padB) / 2 - 14} />`}
      </svg>`;
  }
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      <line x1=${padL} x2=${padL} y1=${padT} y2=${H - padB} stroke="var(--chart-axis)" stroke-width="1" opacity="0.5"/>
      <line x1=${padL - 2} x2=${padL + 2} y1=${padT} y2=${padT} stroke="var(--chart-axis)" stroke-width="1" opacity="0.5"/>
      <text x=${padL + 1} y=${padT - 2} font-size="8.5" fill="var(--ink-faint)">${"max " + maxC}</text>
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
          <line x1=${xClamp(you)} x2=${xClamp(you)} y1=${padT - 2} y2=${H - padB} stroke=${youColour(favourable)} stroke-width="2" />
          <${YouDot} x=${xClamp(you)} y=${padT - 2} fav=${favourable}
            anchor=${you < hist.min ? "start" : you > hist.max ? "end" : "middle"} bounds=${[padL, W - padL]}
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
      ${you != null && html`<${YouDot} x=${x(you)} y=${midY} fav=${favourable} bounds=${[padL, W - padR]}
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
  // Match the server's whitespace-collapsing _norm_label so the "you" highlight
  // lands on the same option the server selected (plain toLowerCase missed labels
  // with internal/edge whitespace differences).
  const normLbl = s => (s || "").replace(/\s+/g, " ").trim().toLowerCase();
  const mine = new Set((youLabels || []).map(normLbl));
  // Many options can't fit the fixed chart box; flag it so the card grows to fit
  // (like matrix tables) instead of bleeding over the title above it.
  const tall = usedH > H;
  return html`
    <svg class=${tall ? "ob-tall" : ""} viewBox="0 0 ${W} ${usedH}" style=${{ width: "100%", display: "block" }}>
      ${opts.map((o, i) => {
        const sel = mine.has(normLbl(o.label));
        const y = i * rowH;
        const bw = (o.pct / maxP) * (W - labelW - 86);
        const maxChars = Math.floor(labelW / (fs * 0.52));
        return html`
        <g key=${o.code}>
          <text x=${labelW - 8} y=${y + rowH / 2 + fs * 0.34} text-anchor="end" font-size=${fs}
            fill=${sel ? "var(--ink)" : "var(--ink-soft)"} font-weight=${sel ? 700 : 400}>
            ${o.label.length > maxChars && html`<title>${o.label}</title>`}${o.label.length > maxChars ? o.label.slice(0, maxChars - 1) + "…" : o.label}</text>
          <rect x=${labelW} y=${y + Math.max(2, rowH * 0.16)} width=${Math.max(2, bw)}
            height=${Math.max(8, rowH - Math.max(4, rowH * 0.32))} rx="3.5"
            fill=${sel ? youColour(fav) : "var(--chart-cat)"}/>
          ${showValues && html`<text x=${labelW + Math.max(2, bw) + 6} y=${y + rowH / 2 + fs * 0.34} font-size=${fs}
            fill=${sel ? youColour(fav) : "var(--ink-faint)"} font-weight=${sel ? 700 : 500}>${o.pct}%${sel ? " · You" + (favGlyph(fav) ? " " + favGlyph(fav) : "") : ""}</text>`}
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
  // Match the server's whitespace-collapsing _norm_label so the "you" highlight
  // lands on the same option the server selected (plain toLowerCase missed labels
  // with internal/edge whitespace differences).
  const normLbl = s => (s || "").replace(/\s+/g, " ").trim().toLowerCase();
  const mine = new Set((youLabels || []).map(normLbl));
  return html`
    <svg viewBox="0 0 ${W} ${usedH}" style=${{ width: "100%", display: "block" }}>
      <line x1=${railX} x2=${railX} y1=${rowH / 2} y2=${usedH - rowH / 2 - 2}
        stroke="var(--chart-axis)" stroke-width="1"/>
      ${opts.map((o, i) => {
        const sel = mine.has(normLbl(o.label));
        const y = i * rowH, cy = y + rowH / 2;
        const bw = (o.pct / maxP) * (W - railX - 96);
        const maxChars = Math.floor(labelW / (fs * 0.52));
        return html`
        <g key=${o.code || o.label}>
          <text x=${labelW - 4} y=${cy + fs * 0.34} text-anchor="end" font-size=${fs}
            fill=${sel ? "var(--ink)" : "var(--ink-soft)"} font-weight=${sel ? 700 : 400}>
            ${o.label.length > maxChars && html`<title>${o.label}</title>`}${o.label.length > maxChars ? o.label.slice(0, maxChars - 1) + "…" : o.label}</text>
          <circle cx=${railX} cy=${cy} r=${sel ? 3.4 : 2.2}
            fill=${sel ? youColour(fav) : "var(--chart-axis)"}/>
          <rect x=${railX + 6} y=${y + Math.max(2, rowH * 0.16)} width=${Math.max(o.pct > 0 ? 2 : 0.5, bw)}
            height=${Math.max(8, rowH - Math.max(4, rowH * 0.32))} rx="3.5"
            fill=${sel ? youColour(fav) : "var(--chart-cat)"} opacity=${o.pct > 0 ? 1 : 0.5}/>
          ${showValues && html`<text x=${railX + 6 + Math.max(2, bw) + 6} y=${cy + fs * 0.34} font-size=${fs}
            fill=${sel ? youColour(fav) : "var(--ink-faint)"} font-weight=${sel ? 700 : 500}>${o.pct}%${sel ? " · You" + (favGlyph(fav) ? " " + favGlyph(fav) : "") : ""}</text>`}
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
  const favOf = (you, p50, pctl) => {
    if (you == null || p50 == null) return null;
    // percentile band (same MARKET_BAND the cards/tiles/signals use) so a matrix
    // row's colour agrees with its own Position column, not a separate ±2% rule
    if (pctl != null && polarity && polarity !== "neutral") {
      const band = (typeof window !== "undefined" && window.MARKET_BAND) || [35, 65];
      const adj = polarity === "lower_is_better" ? 100 - pctl : pctl;
      return adj > band[1] ? "good" : adj < band[0] ? "bad" : "mid";
    }
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
              <tr key=${r.row_id} class="mn-row"><th scope="row" class="mn-lvl"><span class="mn-lvl-txt" title=${r.label}>${r.label}</span></th>
                <td colspan="4" class="mn-supp caption">not enough organisations to show safely</td></tr>`;
            const b = r.block, you = r.you ? r.you.value : null;
            const f = favOf(you, b.p50, r.you ? r.you.percentile : null);
            return html`
              <tr key=${r.row_id} class="mn-row">
                <th scope="row" class="mn-lvl"><span class="mn-lvl-txt" title=${r.label}>${r.label}</span></th>
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
          ${r.unbenchmarked && html`<text x=${labelW} y=${y - 2} font-size="8" fill="var(--ink-faint)">EST — market comparison suppressed for this tier</text>`}
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
          background: c ? `color-mix(in srgb, var(--quartile-fill) ${Math.round(22 + 78 * c / total)}%, var(--surface-sunk))` : "var(--surface-sunk)",
        }}></div>`)}
    </div>`;
};

// --------------------------------------- matrix export twins (HTML→SVG) ----
// The two matrix charts render as polished HTML (crisp text, easy layout), so
// the SVG raster exporter has nothing to serialise. Rather than rasterise the
// DOM (fragile), we rebuild an equivalent SVG from the SAME card data — sharing
// matrixBandOrder() with the on-screen renderer so the two can never drift.

// Integer display percentages for one matrix row, largest-remainder over the
// exact counts, so a row's cells always sum to the engine's total. Shared by
// the HTML heatmap and the export twin — independent Math.round per cell let
// a .5/.5 row double-round upward (Director LTI rendered 26% + 75% = 101%).
window.matrixRowInts = function (opts) {
  const n = (opts || []).reduce((a, o) => a + (o.count || 0), 0);
  const raw = (opts || []).map(o => n ? (o.count || 0) * 100 / n : (o.pct || 0));
  const total = Math.round(raw.reduce((a, p) => a + p, 0));
  const fl = raw.map(Math.floor);
  let rem = total - fl.reduce((a, b) => a + b, 0);
  raw.map((p, i) => [p - fl[i], i]).sort((a, b) => b[0] - a[0])
    .slice(0, Math.max(rem, 0)).forEach(([, i]) => { fl[i]++; });
  const m = {};
  (opts || []).forEach((o, i) => { m[o.label] = fl[i]; });
  return m;
};

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
    const disp = matrixRowInts(r.block.options || []);
    const youLabel = r.you ? (r.you.label || r.you.display) : null, modal = r.block.modal_label;
    order.forEach((b, ci) => {
      const pct = pm[b] || 0, cx = Lw + ci * bw, ry = y + 3, ch = Rh - 6, cw = bw - 4;
      if (pct <= 0) { s += `<rect x="${cx}" y="${ry}" width="${cw}" height="${ch}" rx="6" fill="${tok.sunk}"/>`; return; }
      const t = 0.14 + 0.86 * (pct / maxPct);
      s += `<rect x="${cx}" y="${ry}" width="${cw}" height="${ch}" rx="6" fill="${mixBlueRGB(t)}"`
        + (youLabel && b === youLabel ? ` stroke="${tok.blueDeep}" stroke-width="2"` : "") + `/>`;
      const r0 = disp[b] || 0;
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
  const favOf = (you, p50, pctl) => {
    if (you == null || p50 == null) return null;
    if (pctl != null && polarity && polarity !== "neutral") {
      const band = (typeof window !== "undefined" && window.MARKET_BAND) || [35, 65];
      const adj = polarity === "lower_is_better" ? 100 - pctl : pctl;
      return adj > band[1] ? "good" : adj < band[0] ? "bad" : "mid";
    }
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
    const b = r.block, yv = r.you ? r.you.value : null, f = favOf(yv, b.p50, r.you ? r.you.percentile : null);
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
// lumi horizontal logo (navy mark + coral "you" dot + ink wordmark), inner
// markup only — designed to a 0 0 390 178 box (web/lumi_horizontal.svg). Inlined
// into the export SVG so the brand renders in one pass (no second image load /
// no canvas taint). Colours are literal brand hex per LOGO_STANDARDS.md.
const LUMI_EXPORT_LOGO = '<g transform="translate(-414.25 -156.25)"><path d="M 470.00 212.00 L 470.00 280.00 L 538.00 280.00" fill="none" stroke="#2048B0" stroke-width="17.0" stroke-linecap="round" stroke-linejoin="round"/><circle cx="490.00" cy="263.00" r="6.00" fill="#2048B0" opacity="0.35"/><circle cx="504.00" cy="254.00" r="6.00" fill="#2048B0" opacity="0.35"/><circle cx="520.00" cy="238.00" r="14.00" fill="#F08C6E"/></g><g transform="translate(50.162499999999994 -578.25)"><g transform="translate(120 700) scale(0.08955938697318008 -0.08955938697318008)"><path transform="translate(0 0)" d="M68 0V720H168V0Z" fill="#243642"/><path transform="translate(237 0)" d="M253 -12Q194 -12 150.5 12.0Q107 36 83.5 84.0Q60 132 60 205V504H160V216Q160 145 191.0 109.0Q222 73 280 73Q319 73 350.5 92.0Q382 111 400.0 147.0Q418 183 418 235V504H518V0H429L422 86Q399 40 355.0 14.0Q311 -12 253 -12Z" fill="#243642"/><path transform="translate(824 0)" d="M68 0V504H158L165 433Q189 472 229.0 494.0Q269 516 319 516Q357 516 388.0 505.5Q419 495 443.0 474.0Q467 453 482 422Q509 466 554.5 491.0Q600 516 651 516Q712 516 756.0 491.5Q800 467 823.0 418.5Q846 370 846 298V0H747V288Q747 358 718.5 394.0Q690 430 635 430Q598 430 569.0 411.0Q540 392 523.5 356.0Q507 320 507 268V0H407V288Q407 358 378.5 394.0Q350 430 295 430Q260 430 231.0 411.0Q202 392 185.0 356.0Q168 320 168 268V0Z" fill="#243642"/><path transform="translate(1731 0)" d="M68 0V504H168V0Z" fill="#243642"/></g><circle cx="285.64" cy="641.61" r="7.52" fill="#F08C6E"/></g>';

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
  const PAD = 18, TITLE_H = 46, FOOT_H = 46;   // taller footer carries the lumi logo + source
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
  // branded source footer: hairline · lumi logo (bottom-left) · "Source: lumi HR"
  // attribution + date (bottom-right). Logo scaled from its 0..390×0..178 box.
  const LOGO_H = 18, lscale = LOGO_H / 178, logoY = H - 32, sepY = H - 40, footY = H - 18;
  const src = `Source: lumi HR${meta.window ? " · " + esc(meta.window) : ""} · generated ${new Date().toLocaleDateString("en-GB")}`;
  wrap.innerHTML = `
    <rect x="0" y="0" width="${W}" height="${H}" fill="#ffffff"/>
    <text x="${PAD}" y="${PAD + 6}" font-family="Helvetica, Arial" font-size="13" font-weight="700" fill="#211B26">${esc(meta.title)}</text>
    <text x="${PAD}" y="${PAD + 24}" font-family="Helvetica, Arial" font-size="10" fill="#5B5560">${esc(meta.cutLabel)} · n=${meta.n}${meta.suffix ? " · " + esc(meta.suffix) : ""}</text>
    <line x1="${PAD}" y1="${sepY}" x2="${W - PAD}" y2="${sepY}" stroke="#E7E2DA" stroke-width="1"/>
    <g transform="translate(${PAD}, ${logoY}) scale(${lscale})">${LUMI_EXPORT_LOGO}</g>
    <text x="${W - PAD}" y="${footY}" text-anchor="end" font-family="Helvetica, Arial" font-size="9" fill="#8E8893">${src}</text>`;
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
