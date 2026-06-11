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
  if (fav === "good") return "var(--favourable)";
  if (fav === "bad") return "var(--unfavourable)";
  if (fav === "mid") return "var(--neutral-perf)";
  return "var(--you)";   // neutral polarity: the plain "you" accent
}

/* The single "you" marker: a filled plum diamond (performance-coloured where
   polarity applies) with a value label. Same treatment on every chart. */
function YouDot({ x, y, fav, label, labelY, anchor }) {
  const r = 7;
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
window.Histogram = function ({ histogram: hist, you, unit, favourable, showValues = true, width = CHART_W }) {
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
window.OptionBars = function ({ options, youLabels, showValues = true, width = CHART_W, height }) {
  const opts = options.filter(o => o.count > 0 || !o.is_na);
  const H = height || 172;
  // few options stretch to fill the chart region; many options compress to fit
  const cap = opts.length <= 3 ? 42 : opts.length <= 5 ? 32 : 27;
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
            fill=${sel ? "var(--you)" : "var(--cat-4)"}/>
          ${showValues && html`<text x=${labelW + Math.max(2, bw) + 6} y=${y + rowH / 2 + fs * 0.34} font-size=${fs}
            fill=${sel ? "var(--you)" : "var(--ink-soft)"} font-weight=${sel ? 700 : 500}>${o.pct}%${sel ? " · You" : ""}</text>`}
        </g>`;
      })}
    </svg>`;
};

// ------------------------------------------------------- stacked band ------
// For ordered scales: segmented distribution band, categorical ramp, YOU pin.
window.StackedDist = function ({ options, youLabels, showValues = true, width = CHART_W }) {
  const W = width, H = 118, barY = 34, barH = 26;
  const opts = options.filter(o => o.pct > 0);
  const mine = new Set((youLabels || []).map(s => s.toLowerCase()));
  let acc = 0;
  const segs = opts.map((o, i) => {
    const x0 = (acc / 100) * W; acc += o.pct;
    return { ...o, x0, w: (o.pct / 100) * W, colour: CAT_COLOURS[i % CAT_COLOURS.length], sel: mine.has(o.label.toLowerCase()) };
  });
  const youSeg = segs.find(s => s.sel);
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      ${segs.map(s => html`
        <g key=${s.code}>
          <rect x=${s.x0} y=${barY} width=${Math.max(1, s.w - 1)} height=${barH} fill=${s.colour} rx="2"
            opacity=${youSeg && !s.sel ? 0.55 : 1}
            stroke=${s.sel ? "var(--you)" : "none"} stroke-width=${s.sel ? 2 : 0}/>
          ${showValues && s.w > 36 && html`<text x=${s.x0 + s.w / 2} y=${barY + barH / 2 + 3.5} text-anchor="middle"
            font-size="10" font-weight="600" fill=${s.sel || segs.indexOf(s) < 3 ? "#fff" : "var(--ink-soft)"}>${Math.round(s.pct)}%</text>`}
        </g>`)}
      ${youSeg && html`
        <g>
          <line x1=${youSeg.x0 + youSeg.w / 2} x2=${youSeg.x0 + youSeg.w / 2} y1=${barY - 8} y2=${barY} stroke="var(--you)" stroke-width="1.5"/>
          <${YouDot} x=${youSeg.x0 + youSeg.w / 2} y=${barY - 13} fav=${null}
            label=${"You · " + youSeg.label.slice(0, 28)} labelY=${barY - 25}
            anchor=${youSeg.x0 + youSeg.w / 2 < 90 ? "start" : youSeg.x0 + youSeg.w / 2 > W - 90 ? "end" : "middle"} />
        </g>`}
      ${segs.slice(0, segs.length > 4 ? 3 : 4).map((s, i) => html`
        <g key=${"lg" + s.code}>
          <rect x=${i * (W / 4)} y=${barY + barH + 14} width="8" height="8" rx="2" fill=${s.colour}/>
          <text x=${i * (W / 4) + 12} y=${barY + barH + 21.5} font-size="9" fill="var(--ink-soft)">
            ${s.label.length > 18 ? s.label.slice(0, 17) + "…" : s.label}</text>
        </g>`)}
      ${segs.length > 4 && html`<text x=${3 * (W / 4)} y=${barY + barH + 21.5} font-size="9" fill="var(--ink-faint)">+${segs.length - 3} more</text>`}
    </svg>`;
};

// --------------------------------------------------------------- heatmap ---
// Matrix rows: peer P50 vs you, delta-coloured by polarity (semantic use only).
window.MatrixHeat = function ({ rows, unit, polarity, showValues = true, width = CHART_W, height }) {
  const H = height || 172;
  const rowH = Math.max(15, Math.min(24, Math.floor((H - 18) / Math.max(rows.length, 1))));
  const fs = rowH >= 20 ? 10.5 : 9.5;
  const labelW = Math.min(170, width * 0.42), W = width;
  const usedH = rows.length * rowH + 18;
  const cellW = (W - labelW - 10) / 3;
  const deltaCol = (you, p50) => {
    if (you == null || p50 == null) return "var(--surface-sunk)";
    const rel = p50 !== 0 ? (you - p50) / Math.abs(p50) : (you ? 1 : 0);
    let state = rel > 0.02 ? (polarity === "lower_is_better" ? "bad" : polarity === "higher_is_better" ? "good" : null)
      : rel < -0.02 ? (polarity === "lower_is_better" ? "good" : polarity === "higher_is_better" ? "bad" : null) : "mid";
    if (state === "good") return "var(--favourable-tint)";
    if (state === "bad") return "var(--unfavourable-tint)";
    if (state === "mid") return "var(--surface-sunk)";
    return "var(--you-soft)";   // neutral polarity: plain "you" tint, no judgement
  };
  return html`
    <svg viewBox="0 0 ${W} ${usedH}" style=${{ width: "100%", display: "block" }}>
      <text x=${labelW + cellW / 2} y="11" text-anchor="middle" font-size="8.5" letter-spacing="0.5" fill="var(--ink-faint)" font-weight="650">PEER P50</text>
      <text x=${labelW + cellW * 1.5} y="11" text-anchor="middle" font-size="8.5" letter-spacing="0.5" fill="var(--ink-faint)" font-weight="650">YOU</text>
      <text x=${labelW + cellW * 2.5} y="11" text-anchor="middle" font-size="8.5" letter-spacing="0.5" fill="var(--ink-faint)" font-weight="650">PERCENTILE</text>
      ${rows.map((r, i) => {
        const y = 16 + i * rowH;
        const you = r.you ? r.you.value : null;
        const p50 = r.suppressed ? null : (r.block || {}).p50;
        const maxChars = Math.floor(labelW / (fs * 0.52));
        return html`
        <g key=${r.row_id}>
          <text x=${labelW - 8} y=${y + rowH / 2 + fs * 0.34} text-anchor="end" font-size=${fs} fill="var(--ink-soft)">
            ${r.label.length > maxChars ? r.label.slice(0, maxChars - 1) + "…" : r.label}</text>
          <rect x=${labelW} y=${y + 1} width=${cellW - 3} height=${rowH - 3} rx="4" fill="var(--surface-sunk)"/>
          <text x=${labelW + cellW / 2 - 1} y=${y + rowH / 2 + fs * 0.34} text-anchor="middle" font-size=${fs} fill="var(--ink-soft)" font-weight="500">
            ${r.suppressed ? "n<5" : (showValues ? fmtValue(p50, unit) : "")}</text>
          <rect x=${labelW + cellW} y=${y + 1} width=${cellW - 3} height=${rowH - 3} rx="4" fill=${r.suppressed ? "var(--surface-sunk)" : deltaCol(you, p50)}/>
          <text x=${labelW + cellW * 1.5 - 1} y=${y + rowH / 2 + fs * 0.34} text-anchor="middle" font-size=${fs} font-weight="700" fill="var(--ink)">
            ${you == null ? "—" : (showValues ? fmtValue(you, unit) : "")}</text>
          <text x=${labelW + cellW * 2.5 - 1} y=${y + rowH / 2 + fs * 0.34} text-anchor="middle" font-size=${fs} fill="var(--ink-soft)">
            ${r.suppressed || !r.you || r.you.percentile == null ? "—" : pLabel(r.you.percentile)}</text>
        </g>`;
      })}
    </svg>`;
};

// ---------------------------------------------------------- grouped bars ---
window.MatrixGrouped = function ({ rows, unit, showValues = true, width = CHART_W, height }) {
  const H = height || 172;
  const rowH = Math.max(22, Math.min(34, Math.floor((H - 18) / Math.max(rows.length, 1))));
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
          ${you != null && html`<rect x=${labelW} y=${y + bh + 2} width=${bw(you)} height=${bh} rx="2.5" fill="var(--you)"/>`}
          ${you != null && showValues && html`<text x=${labelW + bw(you) + 5} y=${y + bh * 2 + 1} font-size="9" font-weight="700" fill="var(--you)">${fmtValue(you, unit)} · You</text>`}
        </g>`;
      })}
      <g>
        <rect x=${labelW} y=${usedH - 10} width="8" height="8" rx="2" fill="var(--chart-band-mid)"/>
        <text x=${labelW + 12} y=${usedH - 3} font-size="9" fill="var(--ink-soft)">Peer P50</text>
        <rect x=${labelW + 70} y=${usedH - 10} width="8" height="8" rx="2" fill="var(--you)"/>
        <text x=${labelW + 82} y=${usedH - 3} font-size="9" fill="var(--ink-soft)">You</text>
      </g>
    </svg>`;
};

// ------------------------------------------------------------ quartile dots
window.QuartileDots = function ({ quartiles }) {
  const total = quartiles.reduce((a, b) => a + b, 0) || 1;
  return html`
    <div class="qdots" title="Where your metrics fall across peer quartiles (Q1 lowest → Q4 highest)">
      ${quartiles.map((c, i) => html`
        <div key=${i} class="qdot" style=${{
          background: c ? `color-mix(in srgb, var(--cat-1) ${Math.round(22 + 78 * c / total)}%, var(--surface-sunk))` : "var(--surface-sunk)",
        }}></div>`)}
    </div>`;
};

// ------------------------------------------------------------- PNG export --
window.exportCardPNG = async function (cardEl, meta, mode) {
  const svg = cardEl.querySelector(".bench-chart svg") || cardEl.querySelector("svg");
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
    <text x="${PAD}" y="${PAD + 6}" font-family="Helvetica, Arial" font-size="13" font-weight="700" fill="#191C1E">${esc(meta.title)}</text>
    <text x="${PAD}" y="${PAD + 24}" font-family="Helvetica, Arial" font-size="10" fill="#5A6066">${esc(meta.cutLabel)} · n=${meta.n}${meta.suffix ? " · " + esc(meta.suffix) : ""}</text>
    <text x="${PAD}" y="${H - 10}" font-family="Helvetica, Arial" font-size="9" fill="#9CA2A8">lumi people analytics benchmark · ${esc(meta.window || "")} · generated ${new Date().toLocaleDateString("en-GB")}</text>`;
  const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
  g.setAttribute("transform", `translate(${PAD}, ${TITLE_H + 8})`);
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
