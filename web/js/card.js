/* BenchmarkCard — one vertical skeleton on every card:
   title (2-line clamp) → meta chips → chart region (fixed --chart-h, content
   centred) → plain-English readout pinned at the bottom → movement slot.
   The eye reads: what is this → how do I compare (position pill) → the detail. */
/* global html, useState, useRef, useEffect, api, fmtValue, pLabel, Chip, NBadge, Term, Modal, Icon,
   PercentileBand, Histogram, BoxPlot, OptionBars, OrderedDist, MatrixHeat, MatrixGrouped,
   chartAlternatives, normaliseChart, CHART_LABELS, exportCardPNG, fmtGBPCompact, EmptyState, nav */

window.BenchmarkCard = function ({ card, prefs, onPref, onPin, pinned, size, cuts, globalCut, window: collWindow, highlight, signal }) {
  const [expanded, setExpanded] = useState(false);          // full question & definition
  const [override, setOverride] = useState(null);           // per-card peer cut — exploratory, never saved
  const [localCard, setLocalCard] = useState(null);
  const [cutBusy, setCutBusy] = useState(false);
  const ref = useRef(null);

  // a global selector change takes precedence and clears the override
  useEffect(() => { setOverride(null); setLocalCard(null); }, [globalCut]);

  // the override re-fetches the SAME per-cut aggregate the global selector
  // uses — chart, pill, position, readout and n all arrive as one card
  useEffect(() => {
    let dead = false;
    if (!override) { setLocalCard(null); return; }
    setCutBusy(true);
    const [dim, value] = override.split("::");
    api(`/api/benchmark/${card.id}?cut=${encodeURIComponent(dim)}${value ? "&cut_value=" + encodeURIComponent(value) : ""}`)
      .then(d => { if (!dead) setLocalCard(d); })
      .catch(() => { if (!dead) { setLocalCard(null); setOverride(null); toast("Couldn't load that peer group — showing the page's view.", "error"); } })
      .finally(() => { if (!dead) setCutBusy(false); });
    return () => { dead = true; };
  }, [override, card.id]);

  const c = (override && localCard) || card;
  const pref = (prefs || {})[card.id] || {};
  const chart = normaliseChart(c, pref.chart);
  if (c.reduced) return html`<${ReducedCard} card=${c} />`;

  const pos = cardPosition(c);
  const overridden = !!override && !!localCard;
  const globalKey = !globalCut || globalCut.startsWith("all") ? "all" : globalCut;
  const effectiveKey = override || globalKey;
  const sentence = humanSentence(c);

  const doExport = async () => {
    // exports carry the card's CURRENT cut label + n (c is the override card when set)
    const res = await exportCardPNG(ref.current, {
      title: c.title, cutLabel: c.cut.label, n: c.n, window: collWindow, card: c,
      suffix: c.you && c.you.percentile != null ? `You: ${c.you.display} (${pLabel(c.you.percentile)})` : null,
    }, "download");
    toast(res === "downloaded" ? `Chart downloaded — labelled ${c.cut.label}, n=${c.n}` : "Nothing to export yet");
  };
  const share = () => {
    // the deep link carries the cut this card is showing, never silently the default
    const cutPart = effectiveKey !== "all" ? "?cut=" + encodeURIComponent(effectiveKey) : "";
    navigator.clipboard.writeText(window.location.href.split("#")[0] + "#/metric/" + card.id + cutPart);
    toast("Link copied — opens this metric on " + c.cut.label);
  };

  const DIM_SHORT = { all: "All peers", industry: "Sector", fte_band: "Size" };
  return html`
    <div class=${"card bench-card stacked" + (size === 2 ? " w2" : "") + (highlight ? " drop-target" : "")} ref=${ref} id=${"q-" + card.id}>
      <div class="bench-head">
        <h3 class="bench-title" title=${c.question_text}>${c.title}</h3>
        ${overridden && html`
          <button class="chip accent cut-chip" title=${"This card compares against " + c.cut.label + " — the page is on " + (globalKey === "all" ? "All peers" : "another group") + ". Click to reset."}
            aria-label=${"Reset this card to the page's peer group"}
            onClick=${() => setOverride(null)}>${DIM_SHORT[c.cut.dim] || c.cut.label} ✕</button>`}
        ${cardSignalPill(c, signal)}
        <${KebabMenu} c=${c} cuts=${cuts} effectiveKey=${effectiveKey} globalKey=${globalKey}
          onCut=${k => setOverride(k === globalKey ? null : k)}
          onDetail=${() => setExpanded(true)} onPin=${onPin ? () => onPin(card.id) : null} pinned=${pinned}
          doExport=${doExport} share=${share} />
      </div>
      <div class=${"bench-chart-full" + (cutBusy ? " busy" : "")}
        role="img" aria-label=${c.title + " chart. " + (sentence.lead || "Peer benchmark distribution.") + " Based on " + c.n + " organisations, " + c.cut.label + "."}
        onClick=${e => { if (!c.suppressed && !e.target.closest("a") && !e.target.closest("button")) openMetric(c.id); }}
        title=${c.suppressed ? undefined : "Open full view"}>
        ${cutBusy ? html`<div class="skel" style=${{ height: "var(--chart-h)", borderRadius: "var(--radius-sm)" }}></div>` :
          html`<${CardBody} card=${c} chart=${chart} showP1090=${pref.p1090 !== false} showValues=${pref.values !== false} fav=${pos ? pos.kind : null} wide=${true} />`}
      </div>
      <div class="bench-lead">${sentence.lead || ""}</div>
      ${c.opportunity && html`<${OpportunityPanel} opp=${c.opportunity} />`}
      <${WhatThisMeans} card=${c} pos=${pos} />
      <div class="bench-n" title="The number of organisations behind this comparison">
        n=${c.n}${cutNote(c)}</div>
      ${expanded && html`<${CardDetail} card=${c} onClose=${() => setExpanded(false)} />`}
    </div>`;
};

/* The one consistent per-card control: a quiet kebab, keyboard-accessible,
   holding peer-group, full view, question/definition, pin, export, share.
   Context-aware: suppressed or unanswered cards never offer export/share. */
function KebabMenu({ c, cuts, effectiveKey, globalKey, onCut, onDetail, onPin, pinned, doExport, share }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    const onKey = e => { if (e.key === "Escape") setOpen(false); };
    const onDown = e => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
    window.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => { window.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", onDown); };
  }, [open]);
  const choices = [{ key: "all", label: "All peers" }];
  if (cuts && cuts.org_industry) choices.push({ key: "industry::" + cuts.org_industry, label: "Your sector: " + cuts.org_industry });
  if (cuts && cuts.org_fte_band) choices.push({ key: "fte_band::" + cuts.org_fte_band, label: "Your size: " + cuts.org_fte_band + " FTE" });
  (cuts && cuts.groups || []).forEach(g => choices.push({ key: "group::" + g.group_id, label: "Group: " + g.name }));
  const unprofiled = cuts && !cuts.org_industry && !cuts.org_fte_band;
  const exportable = !c.suppressed && !!c.you;
  const pick = (fn) => () => { setOpen(false); fn(); };
  return html`
    <div class="kebab-wrap no-print" ref=${wrapRef}>
      <button class="iconbtn kebab" aria-label="Card options" aria-haspopup="menu" aria-expanded=${open}
        onClick=${() => setOpen(!open)}>⋮</button>
      ${open && html`
        <div class="kebab-menu" role="menu" aria-label="Card options">
          <div class="kebab-label">Compare against</div>
          ${choices.map(ch => html`
            <button key=${ch.key} role="menuitemradio" aria-checked=${effectiveKey === ch.key}
              class=${"kebab-item" + (effectiveKey === ch.key ? " on" : "")}
              onClick=${pick(() => onCut(ch.key))}>
              <span class="kebab-check">${effectiveKey === ch.key ? "✓" : ""}</span>${ch.label}
              ${ch.key === globalKey ? html`<span class="caption" style=${{ marginLeft: "auto" }}>page</span>` : null}
            </button>`)}
          ${unprofiled && html`<button role="menuitem" class="kebab-item" onClick=${pick(() => nav("/profile"))}>
            Unlock sector & size — complete your profile</button>`}
          <div class="kebab-sep"></div>
          <button role="menuitem" class="kebab-item" onClick=${pick(() => openMetric(c.id))}>Open full view</button>
          <button role="menuitem" class="kebab-item" onClick=${pick(onDetail)}>Full question & definition</button>
          ${onPin && html`<button role="menuitem" class="kebab-item" onClick=${pick(onPin)}>${pinned ? "Unpin from My view" : "Pin to My view"}</button>`}
          ${exportable && html`
            <div class="kebab-sep"></div>
            <button role="menuitem" class="kebab-item" onClick=${pick(doExport)}>Download chart (PNG)</button>
            <button role="menuitem" class="kebab-item" onClick=${pick(share)}>Copy link (${c.cut.label})</button>`}
        </div>`}
    </div>`;
}

/* The plain-English answer that leads every card: "X in 10" phrasing first,
   the precise figures as a quiet supporting line. */
window.humanSentence = humanSentence;
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
  if (c.type === "matrix" && (c.matrix_rows || []).some(r => r.block && r.block.kind === "select")) {
    const live = c.matrix_rows.filter(r => !r.suppressed && r.block && r.block.modal_label);
    if (live.length) {
      const r0 = live[0];
      return { lead: `Level by level, the most common peer answer is shown below — e.g. ${r0.label}: “${r0.block.modal_label}” (${r0.block.modal_pct}% of ${r0.block.n} organisations).`, support: null };
    }
  }
  if (!c.you && !c.readout && c.type !== "matrix") {
    return { lead: "Answer this to see where you stand — the peer picture is already here.", support: null };
  }
  return { lead: c.readout, support: null };
}

/* 8.5 — the advisor gesture: a quiet, optional line on what good looks like.
   Deterministic copy from existing fields only; led by gap cards. */
window.WhatThisMeans = function ({ card: c, pos, defaultOpen }) {
  const [open, setOpen] = useState(!!defaultOpen);
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
      return "Most similar organisations are further ahead here. A typical next step is to review whether a more formal approach would fit your size and sector — the market's position suggests it's become standard practice.";
    }
    return "You're behind most similar organisations on this measure." + (p50 ? ` What good looks like: the market median is ${p50} — a realistic first milestone.` : "");
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

/* The per-card status pill: every card carries exactly one. Either the metric's
   signal (lens-coloured flag, never a verdict), or — if the user hasn't answered
   — a prompt to add data so it CAN flag, or a quiet "No flag" when answered and
   nothing crosses a threshold. Mirrors the Signals inbox language. */
// fallback tags only — the engine now supplies sig.tag in plain market language
const SIG_KIND = { money: "£ GAP", save: "HIGHER THAN MARKET", behind: "LOWER THAN MARKET",
  prevalence: "ON MARKET", outlier: "LOWER THAN MARKET", depth: "LOWER THAN MARKET", rare: "FEW OFFER THIS" };
const SIG_LENS_ICON = { save: "coins", attract: "magnet", retain: "anchor", engage: "heart" };
function cardAnswered(c) {
  // numeric/select/multi carry c.you; matrix answers live per-row in matrix_rows
  if (c.you) return true;
  if (c.type === "matrix" && c.matrix_rows) return c.matrix_rows.some(r => r.you);
  return false;
}
function cardSignalState(c, sig) {
  if (c.suppressed || c.reduced) return null;
  if (sig) return "signal";
  if (c.locked || !cardAnswered(c)) return "add";
  return "clear";
}
window.cardSignalState = cardSignalState;
function cardSignalPill(c, sig) {
  const state = cardSignalState(c, sig);
  if (!state) return null;
  if (state === "signal") {
    return html`<span class=${"sig-pill lens-" + sig.lens} title=${sig.stand || sig.label_short || sig.detail}>
      <${Icon} name=${SIG_LENS_ICON[sig.lens] || "flag"} size=${12} /> ${sig.tag || SIG_KIND[sig.kind] || sig.kind}</span>`;
  }
  if (state === "add") {
    const href = c.subpower ? "#/your-data/submit/" + encodeURIComponent(c.subpower) : "#/your-data";
    return html`<a class="sig-pill is-add" href=${href} onClick=${e => e.stopPropagation()}
      title=${"Add your data for this metric to see if it flags vs the market"}>
      <${Icon} name=${c.locked ? "lock" : "pencil"} size=${11} /> Add data</a>`;
  }
  return html`<span class="sig-pill is-clear" title="Nothing flags here — you're within the typical market range.">
    <${Icon} name="sparkle" size=${11} /> No flag</span>`;
}
window.cardSignalPill = cardSignalPill;

window.CardBody = function ({ card: c, chart, showP1090, showValues, fav, xl, wide }) {
  // popped-out charts get a wider viewBox (more data room, same-size labels);
  // in-card charts get a narrower viewBox so labels render comfortably large
  // in the side-by-side proof column
  const W = xl ? 780 : wide ? 620 : 340;
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
        html`<div class="noanswer-box" style=${{ marginBottom: "4px" }}>Answer this to see where you stand among the peers below. <a href="#/your-data/submit">Add your data</a></div>`}
        ${chart === "histogram" ? html`<${Histogram} histogram=${c.histogram} you=${you} unit=${c.unit} favourable=${fav} median=${c.block ? c.block.p50 : null} showValues=${showValues} width=${W} />`
        : chart === "box" ? html`<${BoxPlot} block=${c.block} you=${you} unit=${c.unit} favourable=${fav} showValues=${showValues} width=${W} />`
        : html`<${PercentileBand} block=${c.block} you=${you} unit=${c.unit} favourable=${fav} showP1090=${showP1090} showValues=${showValues} width=${W} />`}
      </div>`;
  }
  if (c.type === "single_select" || c.type === "yes_no" || c.type === "multi_select") {
    const youLabels = c.you ? c.you.labels : [];
    if (!c.block) return html`<div class="suppressed-box">No distribution available.</div>`;
    return html`
      <div>
        ${!c.you && html`<div class="noanswer-box" style=${{ marginBottom: "6px" }}><a href="#/your-data/submit" style=${{ color: "inherit" }}>Answer this to see where you stand.</a></div>`}
        ${chart === "ordered" && c.type !== "multi_select"
          ? html`<${OrderedDist} options=${c.block.options} youLabels=${youLabels} showValues=${showValues}
              width=${W} height=${rowH || (c.you ? 172 : 140)} fav=${fav} />`
          : html`<${OptionBars} options=${c.block.options} youLabels=${youLabels} showValues=${showValues}
              width=${W} height=${rowH || (c.you ? 172 : 140)} fav=${c.type === "multi_select" ? null : fav} />`}
      </div>`;
  }
  if (c.type === "matrix") {
    const allSuppressed = (c.matrix_rows || []).every(r => r.suppressed);
    if (allSuppressed) return html`<div class="suppressed-box">
      <${Icon} name="shield" size=${18} />
      <div style=${{ fontWeight: 650, color: "var(--ink)" }}>Not enough data in this peer group</div>
      <div>Fewer than 5 organisations per level — try a wider peer group.</div></div>`;
    // categorical matrices (Yes/No participation, ordered bands like notice
    // periods) carry per-row distributions, not quartiles
    const isSelect = (c.matrix_rows || []).some(r => r.block && r.block.kind === "select");
    if (isSelect) return html`<${MatrixSelect} rows=${c.matrix_rows} showValues=${showValues} />`;
    return chart === "grouped_bars"
      ? html`<${MatrixGrouped} rows=${c.matrix_rows} unit=${c.unit} showValues=${showValues} width=${W} height=${rowH} fav=${fav} />`
      : html`<${MatrixHeat} rows=${c.matrix_rows} unit=${c.unit} polarity=${c.polarity} showValues=${showValues} width=${W} height=${rowH} />`;
  }
  return null;
};

/* Categorical matrix: a prevalence HEATMAP. Levels are rows, the ordered
   answer bands are aligned columns, and each cell's single-hue intensity is
   how common that band is at that level. Aligned columns make the shape of
   the market legible at a glance (e.g. the notice period lengthening up the
   seniority ladder reads as a diagonal); the exact % sits in every cell, the
   most-common cell per row is ringed, and the org's own band is outlined.
   A stacked bar of near-identical blues could never carry this. */
window.MatrixSelect = function ({ rows }) {
  const live = (rows || []).filter(r => !r.suppressed && r.block && r.block.options);
  // Recover the true band order — rows carry their options in the column's
  // ordinal order but each holds only the bands it uses, so a naive first-seen
  // merge scrambles the scale. matrixBandOrder (shared with the PNG export twin)
  // does a topological merge → 1 week → … → More than 16 weeks regardless of
  // which row leads.
  const order = matrixBandOrder(live);
  // Intensity is scaled to the busiest cell anywhere in the matrix, so the
  // single most common combination is full strength and everything reads
  // relative to it. A concentrated level shows one dark cell; a split level
  // shows several mid cells — darkness = "how common".
  let maxPct = 1;
  live.forEach(r => (r.block.options || []).forEach(o => { if (o.pct > maxPct) maxPct = o.pct; }));
  const abbr = l => (l || "").replace(/^More than\s*/i, ">").replace(/\bweeks?\b/i, "wk")
    .replace(/\bmonths?\b/i, "mo").replace(/\bdays?\b/i, "d").trim();
  // Opaque cell colour, mixed white→brand-blue by prevalence. Opaque (not an
  // alpha wash) so a cell's shade never shifts with row striping or whatever
  // sits behind it — darkness is one honest scale across the whole grid.
  const mix = t => {
    const b = [37, 71, 176];
    return "rgb(" + Math.round(255 + (b[0] - 255) * t) + "," + Math.round(255 + (b[1] - 255) * t)
      + "," + Math.round(255 + (b[2] - 255) * t) + ")";
  };
  const fmtPct = p => { const r = Math.round(p); return r > 0 ? r + "%" : "<1%"; };
  return html`
    <div class="matrix-heat-wrap">
      <table class="matrix-heat">
        <thead>
          <tr>
            <th class="mh-lvl">Level</th>
            ${order.map(b => html`<th key=${b} class="mh-band" title=${b}>${abbr(b)}</th>`)}
            <th class="mh-you">You</th>
          </tr>
        </thead>
        <tbody>
          ${(rows || []).map(r => {
            if (r.suppressed || !r.block) return html`
              <tr key=${r.row_id} class="mh-row"><td class="mh-lvl"><span class="mh-lvl-txt" title=${r.label}>${r.label}</span></td>
                <td colspan=${order.length + 1} class="mh-supp caption">not enough organisations to show safely</td></tr>`;
            const pm = {}; (r.block.options || []).forEach(o => { pm[o.label] = o.pct; });
            const youLabel = r.you ? (r.you.label || r.you.display) : null;
            const modal = r.block.modal_label;
            return html`
              <tr key=${r.row_id} class="mh-row">
                <td class="mh-lvl"><span class="mh-lvl-txt" title=${r.label}>${r.label}</span></td>
                ${order.map(b => {
                  const pct = pm[b] || 0;
                  if (pct <= 0) return html`<td key=${b} class="mh-cell mh-empty" title=${r.label + " · " + b + " · no peers"}></td>`;
                  const t = 0.14 + 0.86 * (pct / maxPct);
                  const isMode = b === modal, isYou = youLabel && b === youLabel;
                  return html`<td key=${b} class=${"mh-cell" + (isMode ? " mode" : "") + (isYou ? " you" : "")}
                    style=${{ background: mix(t), color: t >= 0.52 ? "#fff" : "var(--ink)" }}
                    title=${r.label + " · " + b + " · " + pct.toFixed(1) + "% of the market"}>${fmtPct(pct)}</td>`;
                })}
                <td class="mh-you">${r.you ? html`<b>${abbr(r.you.display)}</b>` : html`<span class="caption">—</span>`}</td>
              </tr>`;
          })}
        </tbody>
      </table>
      <div class="matrix-scale">
        <span class="mscale"><span class="caption">fewer peers</span><span class="mscale-bar"></span><span class="caption">more peers</span></span>
        <span class="mleg"><b class="mh-mode-key">bold</b> = most common at each level</span>
        <span class="mleg"><span class="msw msw-you"></span>your organisation</span>
      </div>
    </div>`;
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
        <button class="btn small primary" onClick=${() => nav("/your-data/submit")}>Complete your reward data</button>
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
        <${Chip}>${c.subpower || c.superpower}<//>
        <${Chip}>${c.category}<//>
        <${Chip}>peer group: ${c.cut.label}, n=${c.n}<//>
      </div>
      <p class="caption" style=${{ marginTop: "var(--s3)" }}>
        Percentiles use linear interpolation across all valid market answers; anything based on fewer
        than 5 organisations is suppressed. See <a href="#/how-lumi-works/calculations" onClick=${onClose}>How this is calculated</a>.
      </p>
      <div class="row" style=${{ justifyContent: "flex-end" }}>
        <button class="btn" onClick=${onClose}>Close</button>
      </div>
    <//>`;
};
