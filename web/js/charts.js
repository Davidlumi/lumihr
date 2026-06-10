/* lumi chart library — bespoke SVG, no chart-framework chrome.
   Every chart is exportable: renderers take pure data so the PNG pipeline can
   re-render them with title / peer-cut / n / attribution baked in. */
/* global html, fmtValue, pLabel */

const CHART_W = 360;

function favColour(fav) {
  if (fav === "good") return "var(--good)";
  if (fav === "bad") return "var(--bad)";
  if (fav === "mid") return "var(--warn)";
  return "var(--accent)";
}

// ----------------------------------------------------- percentile band -----
// P10–P90 bar, P25–P75 emphasised, median marker, "You" marker with label.
window.PercentileBand = function ({ block, you, unit, favourable, showP1090 = true, showValues = true, width = CHART_W }) {
  const W = width, H = 86, padL = 8, padR = 8, barY = 40, barH = 14;
  const lo = Math.min(block.p10, you != null ? you : block.p10);
  const hi = Math.max(block.p90, you != null ? you : block.p90);
  const span = (hi - lo) || 1;
  const x = v => padL + ((v - lo) / span) * (W - padL - padR);
  const marks = [];
  if (showP1090) marks.push(["P10", block.p10], ["P90", block.p90]);
  marks.push(["P25", block.p25], ["P75", block.p75]);
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      ${showP1090 && html`<rect x=${x(block.p10)} y=${barY} width=${Math.max(1, x(block.p90) - x(block.p10))} height=${barH} rx="7" fill="var(--chart-band)" />`}
      <rect x=${x(block.p25)} y=${barY} width=${Math.max(1, x(block.p75) - x(block.p25))} height=${barH} rx="7" fill="var(--chart-band-mid)" />
      <rect x=${x(block.p50) - 1.5} y=${barY - 4} width="3" height=${barH + 8} rx="1.5" fill="var(--chart-median)" />
      <text x=${x(block.p50)} y=${barY + barH + 16} text-anchor="middle" font-size="9.5" fill="var(--ink-2)">P50${showValues ? " · " + fmtValue(block.p50, unit) : ""}</text>
      ${marks.map(([lbl, v]) => html`
        <g key=${lbl}>
          <line x1=${x(v)} x2=${x(v)} y1=${barY - 2} y2=${barY + barH + 2} stroke="var(--ink-3)" stroke-width="1" opacity="0.55"/>
          <text x=${x(v)} y=${barY + barH + 16} text-anchor="middle" font-size="9" fill="var(--ink-3)">${lbl}</text>
        </g>`)}
      ${you != null && html`
        <g>
          <circle cx=${x(you)} cy=${barY + barH / 2} r="7" fill=${favColour(favourable)} stroke="#fff" stroke-width="2"/>
          <text x=${x(you)} y=${barY - 12} text-anchor="middle" font-size="11" font-weight="700" fill=${favColour(favourable)}>
            You${showValues ? " · " + fmtValue(you, unit) : ""}</text>
        </g>`}
    </svg>`;
};

// ----------------------------------------------------------- histogram -----
window.Histogram = function ({ histogram: hist, you, unit, favourable, showValues = true, width = CHART_W }) {
  if (!hist || !hist.bins) return null;
  const W = width, H = 110, padL = 8, padB = 18, padT = 14;
  const n = hist.bins.length, maxC = Math.max(...hist.bins, 1);
  const bw = (W - padL * 2) / n;
  const x = v => padL + ((v - hist.min) / ((hist.max - hist.min) || 1)) * (W - padL * 2);
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      ${hist.bins.map((c, i) => html`
        <rect key=${i} x=${padL + i * bw + 1} width=${Math.max(1, bw - 2)}
          y=${padT + (1 - c / maxC) * (H - padT - padB)} height=${(c / maxC) * (H - padT - padB)}
          rx="2" fill="var(--chart-bar)" />`)}
      <text x=${padL} y=${H - 4} font-size="9" fill="var(--ink-3)">${fmtValue(hist.min, unit)}</text>
      <text x=${W - padL} y=${H - 4} text-anchor="end" font-size="9" fill="var(--ink-3)">${fmtValue(hist.max, unit)}</text>
      ${you != null && html`
        <g>
          <line x1=${x(you)} x2=${x(you)} y1=${padT - 2} y2=${H - padB} stroke=${favColour(favourable)} stroke-width="2.5" />
          <text x=${x(you)} y=${padT - 4} text-anchor="middle" font-size="10" font-weight="700" fill=${favColour(favourable)}>
            You${showValues ? " · " + fmtValue(you, unit) : ""}</text>
        </g>`}
    </svg>`;
};

// ------------------------------------------------------------- box plot ----
window.BoxPlot = function ({ block, you, unit, favourable, showValues = true, width = CHART_W }) {
  const W = width, H = 96, padL = 8, padR = 8, midY = 46, boxH = 26;
  const lo = Math.min(block.p10, you != null ? you : block.p10);
  const hi = Math.max(block.p90, you != null ? you : block.p90);
  const span = (hi - lo) || 1;
  const x = v => padL + ((v - lo) / span) * (W - padL - padR);
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      <line x1=${x(block.p10)} x2=${x(block.p90)} y1=${midY} y2=${midY} stroke="var(--ink-3)" stroke-width="1.4"/>
      <line x1=${x(block.p10)} x2=${x(block.p10)} y1=${midY - 9} y2=${midY + 9} stroke="var(--ink-3)" stroke-width="1.4"/>
      <line x1=${x(block.p90)} x2=${x(block.p90)} y1=${midY - 9} y2=${midY + 9} stroke="var(--ink-3)" stroke-width="1.4"/>
      <rect x=${x(block.p25)} y=${midY - boxH / 2} width=${Math.max(1, x(block.p75) - x(block.p25))} height=${boxH}
        rx="4" fill="var(--chart-band)" stroke="var(--chart-band-mid)"/>
      <rect x=${x(block.p50) - 1.5} y=${midY - boxH / 2} width="3" height=${boxH} fill="var(--chart-median)"/>
      <text x=${x(block.p10)} y=${midY + 26} text-anchor="middle" font-size="9" fill="var(--ink-3)">P10</text>
      <text x=${x(block.p50)} y=${midY + 26} text-anchor="middle" font-size="9.5" fill="var(--ink-2)">P50${showValues ? " · " + fmtValue(block.p50, unit) : ""}</text>
      <text x=${x(block.p90)} y=${midY + 26} text-anchor="middle" font-size="9" fill="var(--ink-3)">P90</text>
      ${you != null && html`
        <g>
          <circle cx=${x(you)} cy=${midY} r="7" fill=${favColour(favourable)} stroke="#fff" stroke-width="2"/>
          <text x=${x(you)} y=${midY - boxH / 2 - 6} text-anchor="middle" font-size="11" font-weight="700" fill=${favColour(favourable)}>
            You${showValues ? " · " + fmtValue(you, unit) : ""}</text>
        </g>`}
    </svg>`;
};

// ------------------------------------------------------- option bars -------
window.OptionBars = function ({ options, youLabels, showValues = true, width = 420 }) {
  const rowH = 24, labelW = Math.min(190, width * 0.44), W = width;
  const opts = options.filter(o => o.count > 0 || !o.is_na);
  const maxP = Math.max(...opts.map(o => o.pct), 1);
  const H = opts.length * rowH + 4;
  const mine = new Set((youLabels || []).map(s => s.toLowerCase()));
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      ${opts.map((o, i) => {
        const sel = mine.has(o.label.toLowerCase());
        const y = i * rowH;
        const bw = (o.pct / maxP) * (W - labelW - 86);
        return html`
        <g key=${o.code}>
          <text x=${labelW - 8} y=${y + rowH / 2 + 3.5} text-anchor="end" font-size="10.5"
            fill=${sel ? "var(--ink)" : "var(--ink-2)"} font-weight=${sel ? 700 : 400}>
            ${o.label.length > 30 ? o.label.slice(0, 29) + "…" : o.label}</text>
          <rect x=${labelW} y=${y + 4} width=${Math.max(2, bw)} height=${rowH - 9} rx="3.5"
            fill=${sel ? "var(--chart-bar-hi)" : "var(--chart-bar)"} opacity=${sel ? 1 : 0.75}/>
          ${showValues && html`<text x=${labelW + Math.max(2, bw) + 6} y=${y + rowH / 2 + 3.5} font-size="10.5"
            fill="var(--ink-2)" font-weight=${sel ? 700 : 400}>${o.pct}%${sel ? " · You" : ""}</text>`}
        </g>`;
      })}
    </svg>`;
};

// ------------------------------------------------------- stacked bar -------
const STACK_COLOURS = ["#0F766E", "#3D9690", "#6CB4AF", "#9CCDC9", "#C7E2E0", "#E2D9C8", "#D9C09A", "#C9A36B", "#B98843", "#A06D2E"];
window.StackedDist = function ({ options, youLabels, showValues = true, width = CHART_W }) {
  const W = width, H = 92, barY = 30, barH = 26;
  const opts = options.filter(o => o.pct > 0);
  const mine = new Set((youLabels || []).map(s => s.toLowerCase()));
  let acc = 0;
  const segs = opts.map((o, i) => {
    const x0 = (acc / 100) * W; acc += o.pct;
    return { ...o, x0, w: (o.pct / 100) * W, colour: STACK_COLOURS[i % STACK_COLOURS.length], sel: mine.has(o.label.toLowerCase()) };
  });
  const youSeg = segs.find(s => s.sel);
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      ${segs.map(s => html`
        <g key=${s.code} class="hastip">
          <rect x=${s.x0} y=${barY} width=${Math.max(1, s.w - 1)} height=${barH} fill=${s.colour}
            stroke=${s.sel ? "var(--ink)" : "none"} stroke-width=${s.sel ? 2 : 0} rx="2"/>
          ${showValues && s.w > 34 && html`<text x=${s.x0 + s.w / 2} y=${barY + barH / 2 + 3.5} text-anchor="middle"
            font-size="10" font-weight="600" fill="#fff">${Math.round(s.pct)}%</text>`}
        </g>`)}
      ${youSeg && html`
        <g>
          <path d="M ${youSeg.x0 + youSeg.w / 2} ${barY - 6} l -5 -8 l 10 0 z" fill="var(--ink)"/>
          <text x=${Math.min(Math.max(youSeg.x0 + youSeg.w / 2, 26), W - 26)} y=${barY - 17} text-anchor="middle" font-size="10.5" font-weight="700" fill="var(--ink)">You</text>
        </g>`}
      ${segs.slice(0, 4).map((s, i) => html`
        <g key=${"lg" + s.code}>
          <rect x=${i * (W / 4)} y=${barY + barH + 12} width="8" height="8" rx="2" fill=${s.colour}/>
          <text x=${i * (W / 4) + 12} y=${barY + barH + 19.5} font-size="9" fill="var(--ink-2)">
            ${s.label.length > 17 ? s.label.slice(0, 16) + "…" : s.label}</text>
        </g>`)}
    </svg>`;
};

// ----------------------------------------------------------------- donut ---
window.Donut = function ({ options, youLabels, width = CHART_W }) {
  const opts = options.filter(o => o.pct > 0);
  const mine = new Set((youLabels || []).map(s => s.toLowerCase()));
  const W = width, H = 130, cx = 70, cy = 65, r = 48, sw = 20;
  let a0 = -Math.PI / 2;
  const segs = opts.map((o, i) => {
    const a1 = a0 + (o.pct / 100) * Math.PI * 2;
    const seg = { ...o, a0, a1, colour: STACK_COLOURS[i % STACK_COLOURS.length], sel: mine.has(o.label.toLowerCase()) };
    a0 = a1; return seg;
  });
  const arc = (s) => {
    const large = (s.a1 - s.a0) > Math.PI ? 1 : 0;
    const x0 = cx + r * Math.cos(s.a0), y0 = cy + r * Math.sin(s.a0);
    const x1 = cx + r * Math.cos(s.a1), y1 = cy + r * Math.sin(s.a1);
    return `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`;
  };
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      ${segs.map(s => html`<path key=${s.code} d=${arc(s)} fill="none" stroke=${s.colour}
        stroke-width=${s.sel ? sw + 7 : sw} opacity=${s.sel ? 1 : 0.85}/>`)}
      ${segs.filter(s => s.sel).map(s => html`
        <text key=${"c" + s.code} x=${cx} y=${cy + 1} text-anchor="middle" font-size="13" font-weight="700" fill="var(--ink)">${Math.round(s.pct)}%</text>`)}
      ${segs.filter(s => s.sel).map(s => html`
        <text key=${"cy" + s.code} x=${cx} y=${cy + 14} text-anchor="middle" font-size="9" fill="var(--ink-2)">You</text>`)}
      ${segs.slice(0, 6).map((s, i) => html`
        <g key=${"lg" + s.code}>
          <rect x="150" y=${14 + i * 18} width="8" height="8" rx="2" fill=${s.colour}/>
          <text x="163" y=${21.5 + i * 18} font-size="9.5" fill=${s.sel ? "var(--ink)" : "var(--ink-2)"} font-weight=${s.sel ? 700 : 400}>
            ${s.label.length > 26 ? s.label.slice(0, 25) + "…" : s.label} · ${s.pct}%${s.sel ? " · You" : ""}</text>
        </g>`)}
    </svg>`;
};

// --------------------------------------------------------------- heatmap ---
// rows = matrix rows; peer median vs you with delta colouring.
window.MatrixHeat = function ({ rows, unit, polarity, showValues = true, width = CHART_W }) {
  const rowH = 26, labelW = Math.min(170, width * 0.42), W = width;
  const H = rows.length * rowH + 26;
  const cellW = (W - labelW - 10) / 3;
  const deltaCol = (you, p50) => {
    if (you == null || p50 == null) return "var(--surface-2)";
    const rel = p50 !== 0 ? (you - p50) / Math.abs(p50) : (you ? 1 : 0);
    let good = rel > 0.02 ? (polarity === "lower_is_better" ? "bad" : polarity === "higher_is_better" ? "good" : null)
      : rel < -0.02 ? (polarity === "lower_is_better" ? "good" : polarity === "higher_is_better" ? "bad" : null) : "mid";
    if (good === "good") return "var(--good-soft)";
    if (good === "bad") return "var(--bad-soft)";
    if (good === "mid") return "var(--surface-2)";
    return "var(--accent-soft)";
  };
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      <text x=${labelW + cellW / 2} y="12" text-anchor="middle" font-size="9" fill="var(--ink-3)" font-weight="600">PEER P50</text>
      <text x=${labelW + cellW * 1.5} y="12" text-anchor="middle" font-size="9" fill="var(--ink-3)" font-weight="600">YOU</text>
      <text x=${labelW + cellW * 2.5} y="12" text-anchor="middle" font-size="9" fill="var(--ink-3)" font-weight="600">PERCENTILE</text>
      ${rows.map((r, i) => {
        const y = 18 + i * rowH;
        const you = r.you ? r.you.value : null;
        const p50 = r.suppressed ? null : (r.block || {}).p50;
        return html`
        <g key=${r.row_id}>
          <text x=${labelW - 8} y=${y + rowH / 2 + 3.5} text-anchor="end" font-size="10.5" fill="var(--ink-2)">
            ${r.label.length > 26 ? r.label.slice(0, 25) + "…" : r.label}</text>
          <rect x=${labelW} y=${y + 1} width=${cellW - 3} height=${rowH - 4} rx="4" fill="var(--surface-2)"/>
          <text x=${labelW + cellW / 2 - 1} y=${y + rowH / 2 + 3.5} text-anchor="middle" font-size="10.5" fill="var(--ink-2)" font-weight="500">
            ${r.suppressed ? "n<5" : (showValues ? fmtValue(p50, unit) : "")}</text>
          <rect x=${labelW + cellW} y=${y + 1} width=${cellW - 3} height=${rowH - 4} rx="4" fill=${r.suppressed ? "var(--surface-2)" : deltaCol(you, p50)}/>
          <text x=${labelW + cellW * 1.5 - 1} y=${y + rowH / 2 + 3.5} text-anchor="middle" font-size="10.5" font-weight="700" fill="var(--ink)">
            ${you == null ? "—" : (showValues ? fmtValue(you, unit) : "")}</text>
          <text x=${labelW + cellW * 2.5 - 1} y=${y + rowH / 2 + 3.5} text-anchor="middle" font-size="10.5" fill="var(--ink-2)">
            ${r.suppressed || !r.you || r.you.percentile == null ? "—" : pLabel(r.you.percentile)}</text>
        </g>`;
      })}
    </svg>`;
};

// ---------------------------------------------------------- grouped bars ---
window.MatrixGrouped = function ({ rows, unit, showValues = true, width = CHART_W }) {
  const rowH = 34, labelW = Math.min(150, width * 0.4), W = width;
  const H = rows.length * rowH + 18;
  const vals = rows.flatMap(r => [r.suppressed ? null : (r.block || {}).p50, r.you ? r.you.value : null]).filter(v => v != null);
  const maxV = Math.max(...vals, 1);
  const bw = v => Math.max(2, (v / maxV) * (W - labelW - 64));
  return html`
    <svg viewBox="0 0 ${W} ${H}" style=${{ width: "100%", display: "block" }}>
      ${rows.map((r, i) => {
        const y = i * rowH + 8;
        const p50 = r.suppressed ? null : (r.block || {}).p50;
        const you = r.you ? r.you.value : null;
        return html`
        <g key=${r.row_id}>
          <text x=${labelW - 8} y=${y + 14} text-anchor="end" font-size="10" fill="var(--ink-2)">
            ${r.label.length > 22 ? r.label.slice(0, 21) + "…" : r.label}</text>
          ${p50 != null ? html`<rect x=${labelW} y=${y} width=${bw(p50)} height="10" rx="2.5" fill="var(--chart-band-mid)"/>` :
          html`<text x=${labelW} y=${y + 8} font-size="9" fill="var(--ink-3)">n<5 — suppressed</text>`}
          ${p50 != null && showValues && html`<text x=${labelW + bw(p50) + 5} y=${y + 8.5} font-size="9" fill="var(--ink-3)">${fmtValue(p50, unit)}</text>`}
          ${you != null && html`<rect x=${labelW} y=${y + 12} width=${bw(you)} height="10" rx="2.5" fill="var(--chart-bar-hi)"/>`}
          ${you != null && showValues && html`<text x=${labelW + bw(you) + 5} y=${y + 20.5} font-size="9" font-weight="700" fill="var(--ink)">${fmtValue(you, unit)} You</text>`}
        </g>`;
      })}
      <g>
        <rect x=${labelW} y=${H - 11} width="8" height="8" rx="2" fill="var(--chart-band-mid)"/>
        <text x=${labelW + 12} y=${H - 4} font-size="9" fill="var(--ink-2)">Peer P50</text>
        <rect x=${labelW + 70} y=${H - 11} width="8" height="8" rx="2" fill="var(--chart-bar-hi)"/>
        <text x=${labelW + 82} y=${H - 4} font-size="9" fill="var(--ink-2)">You</text>
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
          background: c ? `color-mix(in srgb, var(--accent) ${Math.round(30 + 70 * c / total)}%, var(--surface-2))` : "var(--surface-2)",
        }}></div>`)}
    </div>`;
};

// ------------------------------------------------------------- PNG export --
// Re-render the card chart into a standalone SVG with title, peer cut, n and
// lumi attribution baked in, then rasterise via canvas.
window.exportCardPNG = async function (cardEl, meta, mode) {
  const svg = cardEl.querySelector("svg");
  if (!svg) return false;
  const clone = svg.cloneNode(true);
  const vb = (svg.getAttribute("viewBox") || "0 0 360 120").split(" ").map(Number);
  const cw = vb[2], ch = vb[3];
  const PAD = 18, TITLE_H = 46, FOOT_H = 26;
  const W = cw + PAD * 2, H = ch + TITLE_H + FOOT_H + PAD;
  const wrap = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  wrap.setAttribute("viewBox", `0 0 ${W} ${H}`);
  wrap.setAttribute("width", W * 2); wrap.setAttribute("height", H * 2);
  // resolve CSS variables so the standalone file matches the app
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
    <text x="${PAD}" y="${PAD + 6}" font-family="Helvetica, Arial" font-size="13" font-weight="700" fill="#1C1917">${esc(meta.title)}</text>
    <text x="${PAD}" y="${PAD + 24}" font-family="Helvetica, Arial" font-size="10" fill="#57534E">${esc(meta.cutLabel)} · n=${meta.n}${meta.suffix ? " · " + esc(meta.suffix) : ""}</text>
    <text x="${PAD}" y="${H - 10}" font-family="Helvetica, Arial" font-size="9" fill="#A8A29E">lumi people analytics benchmark · ${esc(meta.window || "")} · generated ${new Date().toLocaleDateString("en-GB")}</text>`;
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
