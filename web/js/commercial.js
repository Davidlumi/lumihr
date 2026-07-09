/* Commercial layer UI: gap register, board pack, Ask lumi analyst, Peer Twin
   panel, shares, team, settings, upgrade. */
/* global html, useState, useEffect, useRef, api, fmtValue, pLabel, Chip, Term, Spinner, Modal,
   EmptyState, nav, Icon, SP_ICONS, SUPERPOWERS, fmtGBPCompact, cutQS, cutLabelOf */

// --------------------------------------------------------- gap register ----
window.gapGroups = function (data) {
  const focused = window.SCOPE && window.SCOPE.focused;
  if (focused && data.maturity_sections) {
    return Object.entries(data.maturity_sections)
      .sort((a, b) => (a[1].order || 99) - (b[1].order || 99)).map(([k]) => k);
  }
  return SUPERPOWERS.filter(s => data.maturity && data.maturity[s]);
};

window.GapRegisterPage = function ({ me, cut, cuts, prefs, onPref }) {
  const ui = (prefs && prefs._ui_gap) || {};
  const [data, setData] = useState(null);
  const [sp, setSpRaw] = useState(ui.sp || "");
  const [show, setShowRaw] = useState(ui.show || "gaps"); // gaps | all
  // filter choices persist per user, server-side, like chart prefs
  const setSp = v => { setSpRaw(v); onPref && onPref("_ui_gap", { ...ui, sp: v }); };
  const setShow = v => { setShowRaw(v); onPref && onPref("_ui_gap", { ...ui, show: v }); };
  const [gerr, setGerr] = useState(null);
  const [gretry, setGretry] = useState(0);
  // client-side column sort. Default: peer adoption desc (the server's "most
  // commonly held missing items lead" order); STATUS_RANK orders the status column.
  const [sort, setSort] = useState({ key: "peer_adoption_pct", dir: -1 });
  useEffect(() => { setData(null); setGerr(null);
    api("/api/gap-register?" + cutQS(cut)).then(setData).catch(e => setGerr(e.message)); }, [cutKeyOf(cut), gretry]);
  if (gerr) return html`<${EmptyState} title="Couldn't load the register" body=${gerr}
    action=${html`<button class="btn small primary" onClick=${() => setGretry(k => k + 1)}>Retry</button>`} />`;
  if (!data) return html`<${PageLoading} />`;
  const focused = window.SCOPE && window.SCOPE.focused;
  let rows = data.rows.filter(r => !r.suppressed);
  if (sp) rows = rows.filter(r => (focused ? (r.subpower || "General") : r.superpower) === sp);
  if (show === "gaps") rows = rows.filter(r => r.org_answered && r.in_place === false && (r.gap || 0) > 0);
  const STATUS_RANK = { not_in_place: 0, partial: 1, unknown: 2, in_place: 3 };
  const sortVal = (r, k) => k === "name" ? (r.name || "").toLowerCase()
    : k === "area" ? (focused ? (r.subpower || "") : r.superpower || "").toLowerCase()
    : k === "status" ? (STATUS_RANK[r.status] != null ? STATUS_RANK[r.status] : 9)
    : (r[k] == null ? -1 : r[k]);   // numerics; nulls sort last on desc
  rows = [...rows].sort((a, b) => { const av = sortVal(a, sort.key), bv = sortVal(b, sort.key);
    return av < bv ? -sort.dir : av > bv ? sort.dir : 0; });
  const onSort = (k) => setSort(s => s.key === k ? { key: k, dir: -s.dir } : { key: k, dir: k === "name" || k === "area" ? 1 : -1 });
  const sortArrow = (k) => sort.key === k ? html` <span aria-hidden="true">${sort.dir === 1 ? "▲" : "▼"}</span>` : null;
  const areaLabel = focused ? "Section" : "Area";
  return html`
    <div>
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <a class="caption" href="#/signals" style=${{ display: "inline-flex", alignItems: "center", gap: "var(--s1)", marginBottom: "var(--s1)" }}>
            <${Icon} name="chevron-left" size=${13} /> Back to Signals</a>
          <h1 class="display-title">Full gap register</h1>
          <div class="caption" style=${{ marginTop: "var(--s1)" }}>
            Every metric's presence against the market — what similar organisations have in place that you don't, sorted so the most commonly held missing items lead.
            Signals surfaces the flags that cross a threshold; this is the complete list. Peer group: ${cutLabelOf(cut, cuts)}.
          </div>
        </div>
        <div class="row">
          <select class="ctl" value=${sp} onChange=${e => setSp(e.target.value)}>
            <option value="">${window.SCOPE && window.SCOPE.focused ? "All sections" : "All areas"}</option>
            ${gapGroups(data).map(s => html`<option key=${s} value=${s}>${s}</option>`)}
          </select>
          <select class="ctl" value=${show} onChange=${e => setShow(e.target.value)}>
            <option value="gaps">Gaps only</option><option value="all">Everything</option>
          </select>
          <a class="btn" href=${"/api/benchmark.csv?" + cutQS(cut)} download>Download data (CSV)</a>
          ${me.user.role === "admin" && html`
            <a class="btn" href=${"/api/gap-register.csv?" + cutQS(cut)} download>Download gap register (CSV)</a>`}
        </div>
      </div>

      ${rows.length === 0 ? html`<${EmptyState} icon="list-checks" title=${show === "gaps" ? "No common gaps found" : "Nothing to show"}
        body=${show === "gaps" ? "Nothing widely adopted by this peer group is missing from your organisation." : "Try different filters."} />` :
      html`<div class="card" style=${{ padding: "0", overflow: "hidden" }}>
        <div style=${{ overflowX: "auto" }}>
        <table class="data gap-table">
          <thead><tr>
            <th><button class="th-sort" onClick=${() => onSort("name")}>Metric${sortArrow("name")}</button></th>
            <th><button class="th-sort" onClick=${() => onSort("area")}>${areaLabel}${sortArrow("area")}</button></th>
            <th><button class="th-sort" onClick=${() => onSort("status")}>Your status${sortArrow("status")}</button></th>
            <th class="num"><button class="th-sort" onClick=${() => onSort("peer_adoption_pct")}>Market${sortArrow("peer_adoption_pct")}</button></th>
            <th class="num"><button class="th-sort" onClick=${() => onSort("sector_adoption_pct")}>Sector${sortArrow("sector_adoption_pct")}</button></th>
            <th class="num"><button class="th-sort" onClick=${() => onSort("n")}>n${sortArrow("n")}</button></th>
          </tr></thead>
          <tbody>
            ${rows.map(r => { const c = gapStatusChip(r); return html`
              <tr key=${r.question_id}>
                <td><a href=${"#/metric/" + r.question_id}>${r.name}</a>
                  <div class="caption gap-sentence">${gapSentence(r)}</div></td>
                <td class="caption">${focused ? (r.subpower || "") : r.superpower}</td>
                <td><span class=${"chip " + c[0]}>${c[1]}</span></td>
                <td class="num">${r.peer_adoption_pct != null ? r.peer_adoption_pct + "%" : "—"}</td>
                <td class="num">${r.sector_adoption_pct != null ? r.sector_adoption_pct + "%" : "—"}</td>
                <td class="num">${r.n}</td>
              </tr>`; })}
          </tbody>
        </table>
        </div>
        <div class="caption" style=${{ padding: "var(--s3) var(--s5)" }}>${rows.length} metric${rows.length === 1 ? "" : "s"} shown · click a column to sort · download the CSV for the raw data.</div>
      </div>`}
    </div>`;
};

// the "reads like a colleague would say it" sentence + status chip — kept as the
// table row's detail line so sortability doesn't cost the plain-English voice
function gapSentence(r) {
  const x = r.peer_adoption_pct != null ? Math.round(r.peer_adoption_pct / 10) : null;
  const peers = x == null ? "Not enough market data to compare safely."
    : x >= 10 ? "Almost all similar organisations have this"
    : x <= 0 ? "Very few similar organisations have this"
    : `About ${x} in 10 similar organisations have this`;
  const you = r.status === "in_place" ? " — and so do you."
    : r.status === "partial" ? " — you're partly there."
    : r.status === "not_in_place" ? " — you don't yet."
    : r.org_answered ? " — yours isn't assessable from your answer."
    : " — you haven't answered this yet.";
  return peers + (x == null ? " " : "") + you;
}
function gapStatusChip(r) {
  return r.status === "in_place" ? ["good", "In place"]
    : r.status === "partial" ? ["warn", "Partially"]
    : r.status === "not_in_place" ? ["bad", "Not in place"]
    : ["", r.org_answered ? "Not assessable" : "Not answered"];
}

// ------------------------------------------------------------ board pack ---// ------------------------------------------------------------ board pack ---
/* numbered, colour-coded section head — the pack's document furniture (2026-07-02) */
function PackSecHead({ num, title }) {
  return html`<div class=${"bp-sechead bp-c" + num}>
    <span class="bp-secnum num">${String(num).padStart(2, "0")}</span>
    <h2 class="section-title">${title}</h2>
  </div>`;
}

window.BoardPackView = function ({ packId, me, shared, sharedData }) {
  const [pack, setPack] = useState(sharedData || null);
  const [shareLink, setShareLink] = useState(null);
  const [shareBusy, setShareBusy] = useState(false);
  const [expiry, setExpiry] = useState(30);
  const [regen, setRegen] = useState(false);
  useEffect(() => {
    if (!sharedData) { setPack(null); api("/api/boardpack/" + packId).then(setPack).catch(() => setPack({ error: true })); }
  }, [packId]);
  if (!pack) return html`<${PageLoading} />`;
  if (pack.error) return html`<${EmptyState} title="Board pack not found" />`;
  const p = pack.payload, n = pack.narrative;
  const mVerdict = p.headline.market && p.headline.market.verdict;
  const foot = `Generated ${p.generated_date} · Peer group: ${p.cut_label}, n=${p.cut_n != null ? p.cut_n : p.peer_pool.total} · Methodology v${p.methodology_version || 1}`;
  const Footer = ({ page }) => html`<div class="pack-footer"><span>${foot}</span><span>Private ${"&"} confidential</span><span class="pack-pageno">lumi · ${page}</span></div>`;
  const makeShare = async () => {
    setShareBusy(true);
    try {
      const r = await api("/api/shares", { method: "POST", body: { kind: "boardpack", config: { pack_id: packId }, expiry_days: expiry } });
      setShareLink(window.location.origin + r.url);
    } catch (e) { toast(e.message, "error"); }
    setShareBusy(false);
  };
  const regenerate = async () => {
    setRegen(true);
    try {
      const r = await api("/api/boardpack/generate", { method: "POST",
        body: { cut: (p.cut && p.cut.dim) || "all", cut_value: p.cut ? p.cut.value : null } });
      nav("/boardpack/" + r.pack_id);
    } catch (e) { toast(e.message, "error"); }
    setRegen(false);
  };
  // evidence CSV (Sprint 2): the vendor convention — the data behind the document,
  // exported client-side from the pack's own stored payload (nothing recomputed)
  const downloadCsv = () => {
    const esc = v => v == null ? "" : /[",\n]/.test(String(v)) ? '"' + String(v).replace(/"/g, '""') + '"' : String(v);
    const lines = [];
    lines.push("# Board pack data — " + p.organisation.name);
    lines.push("# " + foot + " · Private & confidential");
    lines.push("section,metric,area,peer group,you,P10,P25,P50,P75,P90,percentile,n,notes");
    const row = (section, r) => lines.push([section, r.label, r.superpower, r.cut_label, r.value_display,
      r.p10_display, r.p25_display, r.p50_display, r.p75_display, r.p90_display, r.percentile, r.n,
      r.polarity === "lower_is_better" ? "lower is better" : ""].map(esc).join(","));
    (p.strengths || []).forEach(r => row("strength", r));
    (p.gaps || []).forEach(r => row("gap", r));
    (p.opportunities || []).forEach(o => lines.push(["opportunity", o.label, "", o.cut_label, "", "", "", "", "", "", "", "",
      o.direction + " · to P50 " + o.to_p50_gbp + " GBP/yr · to P75 " + o.to_p75_gbp + " GBP/yr"].map(esc).join(",")));
    (p.gap_register_top || []).forEach(r => lines.push(["practice gap", r.name, r.superpower, "", r.your_status,
      "", "", "", "", "", "", r.n, "peer adoption " + r.peer_adoption_pct + "%"].map(esc).join(",")));
    const blob = new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "Board pack data — " + p.organisation.name + " — " + p.generated_date + ".csv";
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
  };
  const stale = !shared && pack.current_collection_window && p.collection_window
    && pack.current_collection_window !== p.collection_window;
  // the Strategy-alignment page is conditional (needs a declared, completed strategy in
  // the pack — old packs and strategy-less orgs skip it), so later page numbers shift
  const hasStrat = !!(p.strategy_alignment && p.strategy_alignment.overall_aim);
  const PN = { money: hasStrat ? 5 : 4, watch: hasStrat ? 6 : 5, evid: hasStrat ? 7 : 6, appx: hasStrat ? 8 : 7 };
  const POS_WORD = { below: "below market", at: "on market", above: "above market" };
  // B6 (2026-07-09 ship review): strategy alignment is NAVY, never RAG. The §04 chip
  // previously rendered on_target green / behind red (and left 'ahead' bare — an
  // asymmetric scale) on the same page that says "lumi never judges the strategy
  // itself". Render the navy .align-chip (app.css:2869 — the in-app AlignmentChip's
  // carrier) for all three states so the pack matches the dashboard's own read.
  const ALIGN_WORD = { on_target: "on aim", ahead: "ahead of aim", behind: "behind aim" };
  const toc = [["How to read this pack", "1"], ["Executive summary", "2"], ["Position by area", "3"]]
    .concat(hasStrat ? [["Strategy alignment", "4"]] : [])
    .concat([["What closing the gaps is worth", String(PN.money)], ["What to watch", String(PN.watch)],
             ["The evidence", String(PN.evid)], ["Appendix — peer practices", String(PN.appx)]]);
  return html`
    <div>
      ${!shared && html`
        <div class="row spread no-print" style=${{ maxWidth: "210mm", margin: "0 auto var(--s4)" }}>
          <button class="btn quiet" onClick=${() => nav("/overview")}>← Back</button>
          <div class="row">
            ${n._fallback && html`<${Chip} kind="warn">Standard narrative — AI-written commentary arrives at go-live<//>`}
            <button class="btn" disabled=${regen} title="Write a fresh pack from your live benchmark on this pack's peer cut" onClick=${regenerate}>${regen ? "Writing…" : "Regenerate"}</button>
            ${me && me.user.role === "admin" && html`
              <select class="ctl" style=${{ width: "auto" }} value=${expiry} aria-label="Share link expiry"
                onChange=${e => setExpiry(parseInt(e.target.value, 10))}>
                <option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option>
              </select>
              <button class="btn" disabled=${shareBusy} onClick=${makeShare}>${shareBusy ? "Creating…" : "Create share link"}</button>`}
            <button class="btn" title="The data behind this document, as a spreadsheet" onClick=${downloadCsv}>Download data (CSV)</button>
            <button class="btn primary" onClick=${() => { const t = document.title; document.title = "Board pack — " + p.organisation.name + " — " + p.generated_date; window.print(); document.title = t; }}>Download PDF</button>
          </div>
        </div>`}
      ${stale && html`
        <div class="card no-print bp-stale" style=${{ maxWidth: "210mm", margin: "0 auto var(--s4)", padding: "var(--s3) var(--s4)" }}>
          This pack reads from the <b>${p.collection_window}</b> snapshot; the benchmark has moved to
          <b> ${pack.current_collection_window}</b>. Regenerate for current numbers.
        </div>`}
      ${shareLink && html`
        <div class="card no-print" style=${{ maxWidth: "210mm", margin: "0 auto var(--s4)", padding: "var(--s3) var(--s4)" }}>
          Share link (read-only, ${expiry} days): <a href=${shareLink}>${shareLink}</a>
          <button class="btn small" style=${{ marginLeft: "var(--s3)" }}
            onClick=${() => { navigator.clipboard.writeText(shareLink); toast("Link copied", "success"); }}>Copy</button>
        </div>`}

      <div class="pack-page">
        <div style=${{ marginTop: "36mm" }}>
          ${window.LUMI_LOGO_SVG
            ? html`<div class="bp-logo" dangerouslySetInnerHTML=${{ __html: window.LUMI_LOGO_SVG }}></div>`
            : html`<div style=${{ fontSize: "var(--fs-label)", fontWeight: 700, color: "var(--blue-deep)", letterSpacing: ".1em" }}>lumi</div>`}
          <div style=${{ fontSize: "var(--fs-label)", fontWeight: 700, color: "var(--blue-deep)", letterSpacing: ".1em", marginTop: "var(--s3)" }}>UK REWARD BENCHMARKING</div>
          <div class=${"pack-accent" + (mVerdict ? " v-" + mVerdict : "")}></div>
          <h1 style=${{ fontSize: "34px", lineHeight: 1.15, margin: "var(--s3) 0 var(--s2)", letterSpacing: "-0.02em" }}>${p.organisation.name}</h1>
          <div style=${{ fontSize: "var(--fs-card-title)", color: "var(--ink-soft)" }}>Board pack · ${p.collection_window}</div>
          <div class="row" style=${{ marginTop: "var(--s4)" }}>
            <${Chip} kind="accent">${p.organisation.industry || "Unclassified"}<//>
            ${p.organisation.fte_band ? html`<${Chip}>${p.organisation.fte_band + " FTE"}<//>` : null}
            <${Chip}>Peer group: ${p.cut_label}<//>
          </div>
          <div class="bp-toc">
            <div class="bp-toc-title">Contents</div>
            ${toc.map(([t, pg]) => html`
              <div key=${pg} class="bp-toc-row"><span>${t}</span><span class="bp-toc-dots"></span><span class="num">${pg}</span></div>`)}
          </div>
        </div>
        <${Footer} page="Cover" />
      </div>

      <div class="pack-page">
        <${PackSecHead} num=${1} title="How to read this pack" />
        <dl class="bp-method">
          <dt>Data effective</dt>
          <dd>${p.collection_window} collection window; figures are read from the live benchmark at generation (${p.generated_date}).
            No aging or annualisation is applied — none is needed: the benchmark is live, not an annual survey.</dd>
          <dt>Peer group</dt>
          <dd>${p.cut_label}, n=${p.cut_n != null ? p.cut_n : p.peer_pool.total}, drawn from a pool of ${p.peer_pool.total} UK organisations (${p.peer_pool.classified} fully classified).${
            p.cut_criteria && Object.keys(p.cut_criteria).length
              ? " Constructed from: " + Object.entries(p.cut_criteria).map(([k, v]) => k.replace(/_/g, " ") + ": " + (Array.isArray(v) ? v.join(", ") : v)).join(" · ") + "."
              : ""}</dd>
          <dt>Weighting</dt>
          <dd>Organisation-weighted throughout — every organisation contributes once, regardless of size.</dd>
          <dt>Suppression</dt>
          <dd>Figures resting on fewer than 5 organisations are never shown — including to us.</dd>
          <dt>Anonymity</dt>
          <dd>Peer organisations are never named — by design. Every comparison is against the group, never an individual organisation.</dd>
          <dt>Matching</dt>
          <dd>Comparisons use lumi's registry of defined metrics: every organisation answers the same defined question, so figures compare
            like with like. There is no job-title matching to go wrong.</dd>
        </dl>
        <p class="caption">Benchmarks are a steer, not a verdict. Where a comparison rests on a thin cut it is marked
          <b> indicative</b> — interpret those with caution, and treat any single figure as the start of a conversation
          rather than the end of one.</p>
        <${Footer} page="1" />
      </div>

      <div class="pack-page">
        <${PackSecHead} num=${2} title="Executive summary" />
        <div class="bp-statrow">
          ${mVerdict ? html`<div class="bp-stat">
              <div class="metric-value">${mVerdict === "below" ? "Below market" : mVerdict === "above" ? "Above market" : "On market"}</div>
              <div class="caption">overall position — the dashboard verdict</div>
            </div>` : null}
          <div class="bp-stat">
            <div class="metric-value">${p.headline.above_median} of ${p.headline.comparable_metrics}</div>
            <div class="caption">comparable metrics above the market median (${p.headline.broadly_in_line} broadly in line, ${p.headline.below_median} below)</div>
          </div>
          <div class="bp-stat">
            <div class="metric-value">${p.peer_pool.total}</div>
            <div class="caption">organisations in the lumi peer pool</div>
          </div>
        </div>
        ${n.key_findings && n.key_findings.length ? html`
          <div class="bp-findings">
            <div class="bp-findings-title">Key findings</div>
            <ol>${n.key_findings.map((f, i) => html`<li key=${i}>${f}</li>`)}</ol>
          </div>` : null}
        ${(n.executive_summary || "").split(/\n\n+/).map((para, i) => html`<p key=${i} style=${{ fontSize: "var(--fs-label)" }}>${para}</p>`)}
        <p class="caption" style=${{ marginTop: "var(--s2)" }}>Narrative ${n._fallback
          ? "composed directly from the figures in this pack"
          : "written by lumi's AI analyst from the figures in this pack, with every number validated against them"} — nothing outside the pack's data is used.</p>
        ${p.band && p.headline.market && p.headline.market.depth_pctl != null ? html`
          <div class="bp-scale-wrap">
            <div class="bp-scale" role="img"
              aria-label=${"Your typical comparable metric sits at the " + Math.round(p.headline.market.depth_pctl) + "th percentile; the on-market band runs P" + p.band.low + " to P" + p.band.high + "."}>
              <div class="bp-scale-zone z-below" style=${{ width: p.band.low + "%" }}></div>
              <div class="bp-scale-zone z-on" style=${{ width: (p.band.high - p.band.low) + "%" }}></div>
              <div class="bp-scale-zone z-above" style=${{ width: (100 - p.band.high) + "%" }}></div>
              <div class="bp-scale-marker" style=${{ left: Math.min(99, Math.max(1, p.headline.market.depth_pctl)) + "%" }}><span>P${Math.round(p.headline.market.depth_pctl)}</span></div>
            </div>
            <div class="caption bp-scale-labels"><span>less competitive</span><span>on market</span><span>more competitive</span></div>
            <p class="caption" style=${{ marginTop: "var(--s2)" }}>Your typical comparable metric sits at <b>P${Math.round(p.headline.market.depth_pctl)}</b>;${" "}
              ${p.headline.broadly_in_line} of ${p.headline.comparable_metrics} comparable metrics sit within the on-market band.</p>
          </div>` : null}
        ${pack.previous && pack.previous.comparable_metrics != null
          && (pack.previous.above_median !== p.headline.above_median
              || pack.previous.broadly_in_line !== p.headline.broadly_in_line
              || pack.previous.below_median !== p.headline.below_median) ? html`
          <p class="caption">Since your last pack (${pack.previous.generated_date}): above the median ${pack.previous.above_median} → ${p.headline.above_median}, broadly in line ${pack.previous.broadly_in_line} → ${p.headline.broadly_in_line}, below ${pack.previous.below_median} → ${p.headline.below_median}.</p>` : null}
        ${p.movement ? html`<p class="caption">${p.movement}</p>` : null}
        <${Footer} page="2" />
      </div>

      <div class="pack-page">
        <${PackSecHead} num=${3} title="Position by area" />
        <div class="bp-position-row">
          ${window.Donut && p.headline.comparable_metrics ? html`
            <div class="bp-donut" role="img" aria-label=${p.headline.below_median + " of " + p.headline.comparable_metrics + " comparable metrics below the market median, " + p.headline.broadly_in_line + " broadly in line, " + p.headline.above_median + " above."}>
              ${"" /* soft gauge palette (2026-07-09 ship review, colour-doctrine pack): market
                     position renders in the muted --gauge-* mixes everywhere (Overview donut,
                     domain instruments) — this pack donut was the last full-strength RAG hold-out.
                     Segments AND key dots swap together; print-color-adjust is already exact. */}
              <${window.Donut} segments=${[
                  { value: p.headline.below_median, color: "var(--gauge-below)" },
                  { value: p.headline.broadly_in_line, color: "var(--gauge-on)" },
                  { value: p.headline.above_median, color: "var(--gauge-above)" },
                ]} total=${p.headline.comparable_metrics} centerNum=${p.headline.comparable_metrics} sub="metrics"
                centerWord=${mVerdict === "below" ? "Below" : mVerdict === "above" ? "Above" : mVerdict === "at" ? "On market" : undefined}
                size=${150} stroke=${20} />
              <div class="caption bp-donut-key"><span class="bp-key-dot" style=${{ background: "var(--gauge-below)" }}></span>below · <span class="bp-key-dot" style=${{ background: "var(--gauge-on)" }}></span>in line · <span class="bp-key-dot" style=${{ background: "var(--gauge-above)" }}></span>above</div>
            </div>` : null}
          ${p.by_section && Object.keys(p.by_section).length ? html`
            <table class="data bp-domains">
              <thead><tr><th>Area</th><th class="num">Above</th><th class="num">In line</th><th class="num">Below</th></tr></thead>
              <tbody>${Object.entries(p.by_section).sort((a, b) => b[1].available - a[1].available)
                .filter(([, v]) => v.available > 0).slice(0, 7).map(([k, v]) => html`
                <tr key=${k}><td><b>${domainLabel(k)}</b> <span class="caption">· ${v.available}</span></td>
                  <td class="num">${v.above}</td><td class="num">${v.inline}</td><td class="num">${v.below}</td></tr>`)}
              </tbody>
            </table>` : null}
        </div>
        ${n.position_commentary ? html`<p style=${{ fontSize: "var(--fs-label)" }}>${n.position_commentary}</p>` : null}
        ${p.band ? html`
          <div class="bp-callout">
            <b>What "competitive" means here</b>
            <p class="caption" style=${{ margin: "var(--s1) 0 0" }}>The reference point is the peer median (P50) — the middle of the market, not its ceiling.
              A position between P${p.band.low} and P${p.band.high} reads as on market: small differences are never treated as gaps.
              Percentiles locate you among peers — P25 means a quarter of them sit at or below you on that measure.</p>
          </div>` : null}
        ${p.maturity && p.maturity.Reward && p.maturity.Reward.org_score != null ? html`
          <p class="caption">Practice maturity: your average practice score is <b>${p.maturity.Reward.org_score}/100</b>${p.maturity.Reward.peer_median_score != null ? html` against a peer average of <b>${p.maturity.Reward.peer_median_score}/100</b>` : null}.</p>` : null}
        <p class="caption">Peer-group composition: ${p.peer_pool.total} UK organisations across 14 sectors (${p.peer_pool.classified} fully classified);
        comparisons use the ${p.cut_label} cut unless stated. Figures resting on fewer than 5 organisations are never shown.</p>
        <${Footer} page="3" />
      </div>

      ${hasStrat ? html`
      <div class="pack-page">
        <${PackSecHead} num=${4} title="Strategy alignment" />
        <p style=${{ fontSize: "var(--fs-label)" }}>
          The board's declared reward strategy${p.strategy_alignment.objective ? html` centres on a <b>${p.strategy_alignment.objective}</b> objective` : null},
          with an overall aim to sit <b>${p.strategy_alignment.overall_aim}</b>${p.strategy_alignment.domains.some(d => d.aim_is_override) ? " (with area-level aims where set below)" : ""}.
          The table reads today's position in each area against that aim.
        </p>
        ${p.strategy_alignment.domains.length ? html`
          <table class="data">
            <thead><tr><th>Area</th><th>Your aim</th><th>Your position</th><th class="num">Read</th></tr></thead>
            <tbody>${p.strategy_alignment.domains.map(d => html`
              <tr key=${d.name}>
                <td><b>${domainLabel(d.name)}</b>${d.aim_is_override ? html` <span class="caption">· area aim</span>` : null}</td>
                <td>${d.aim || "—"}</td>
                <td>${POS_WORD[d.position] || "—"}</td>
                <td class="num">${ALIGN_WORD[d.alignment]
                  ? html`<span class=${"align-chip align-" + d.alignment}><${Icon} name="target" size=${11} /> ${ALIGN_WORD[d.alignment]}</span>`
                  : "—"}</td>
              </tr>`)}
            </tbody>
          </table>` : null}
        ${n.strategy_commentary ? html`<p style=${{ fontSize: "var(--fs-label)" }}>${n.strategy_commentary}</p>` : null}
        <p class="caption">Alignment reads your position against your own declared aim — lumi never judges the strategy itself.
          Aims are set by your Admins under Reward strategy and can be changed at any time.</p>
        <${Footer} page="4" />
      </div>` : null}

      <div class="pack-page">
        <${PackSecHead} num=${PN.money} title="What closing the gaps is worth" />
        <p>${n.opportunity_narrative}</p>
        ${p.opportunities.length ? html`
          ${p.opportunity_totals && (p.opportunity_totals.investment_to_p50_gbp || p.opportunity_totals.savings_to_p50_gbp) ? html`
            <p style=${{ fontSize: "var(--fs-label)" }}><b>
              ${p.opportunity_totals.investment_to_p50_gbp ? "Indicative total investment to reach the peer median: " + fmtGBPCompact(p.opportunity_totals.investment_to_p50_gbp) + "/yr" : ""}
              ${p.opportunity_totals.investment_to_p50_gbp && p.opportunity_totals.savings_to_p50_gbp ? " · " : ""}
              ${p.opportunity_totals.savings_to_p50_gbp ? "modelled savings: " + fmtGBPCompact(p.opportunity_totals.savings_to_p50_gbp) + "/yr" : ""}
            </b></p>` : null}
          <table class="data" style=${{ marginBottom: "var(--s3)" }}>
            <thead><tr><th>Lever</th><th class="num">To market median</th><th class="num">To upper quartile</th><th>Type</th></tr></thead>
            <tbody>${p.opportunities.map(o => html`
              <tr key=${o.label}><td><b>${o.label}</b><div class="caption">${o.formula}</div></td>
              <td class="num"><b>${fmtGBPCompact(o.to_p50_gbp)}/yr</b></td>
              <td class="num">${fmtGBPCompact(o.to_p75_gbp)}/yr</td>
              <td>${o.direction === "saving" ? "Potential saving" : "Investment to close"}</td></tr>`)}
            </tbody>
          </table>
          <p class="caption">Indicative modelling only. Assumptions: median salary £${(p.opportunity_assumptions.median_salary_gbp || 0).toLocaleString("en-GB")};
          cost per leaver ${p.opportunity_assumptions.cost_per_leaver_pct_salary}% of salary; agency premium ${p.opportunity_assumptions.agency_premium_pct}%;
          FTE from band midpoints. Edit these in Settings and regenerate.</p>
          <div class="bp-qbox">
            <b>Questions the board may ask</b>
            <ul>
              ${p.opportunity_totals && p.opportunity_totals.investment_to_p50_gbp ? html`<li>"What would it cost to reach the market median?" — the modelled total is ${fmtGBPCompact(p.opportunity_totals.investment_to_p50_gbp)}/yr on the stated assumptions.</li>` : null}
              ${p.opportunities[0] ? html`<li>"Which single lever moves us most?" — ${p.opportunities[0].label} (${fmtGBPCompact(p.opportunities[0].to_p50_gbp)}/yr to the median).</li>` : null}
              <li>"How reliable are these figures?" — medians from n=${p.cut_n != null ? p.cut_n : p.peer_pool.total} organisations; anything resting on fewer than 5 is suppressed.</li>
            </ul>
          </div>` :
        html`<p class="caption">No £ opportunities could be modelled for this peer group (metrics suppressed or not yet answered).</p>`}
        <${Footer} page=${String(PN.money)} />
      </div>

      <div class="pack-page">
        <${PackSecHead} num=${PN.watch} title="What to watch" />
        ${p.signals && p.signals.length ? html`
          <p class="caption" style=${{ marginTop: "-4px" }}>The benchmark's top flagged items — the same balanced briefing the lumi dashboard shows, in the absolute view.</p>
          <div class="bp-signals">
            ${p.signals.map((s, i) =>
              // context metrics (2026-07-09 ship review, Pack-3 §2): the engine refuses to
              // verdict these (bucket='context'), yet in the pack they read like genuine gaps
              // ("Workforce cost per FTE" as a £16.5k underpayment). Mark them with the navy
              // not-a-verdict chip; packs stored before the bucket field simply show no chip.
              html`
              <div key=${i} class="bp-signal">
                <b>${s.name}</b>${s.risk ? html` <span class="bp-risk">Risk</span>` : null}${s.bucket === "context" ? html` <span class="align-chip">Context — not a verdict</span>` : null}
                <div class="caption">${s.stand}${s.domain ? " · " + s.domain : ""}</div>
              </div>`)}
          </div>` : null}
        ${p.strategy && p.strategy.objective ? html`
          <p class="caption">Declared reward strategy: <b>${p.strategy.objective}</b> — the dashboard orders these signals for that stance.</p>` : null}
        <h2 class="section-title" style=${{ marginTop: p.signals && p.signals.length ? "var(--s5)" : "0" }}>Options to consider</h2>
        <p class="caption" style=${{ marginTop: "-4px", marginBottom: "var(--s2)" }}>A starting point for your own judgement — not advice.
          lumi is a mirror, not a scoreboard: it tells you where you stand, never what you must do.</p>
        <ol style=${{ fontSize: "var(--fs-label)", paddingLeft: "var(--s5)" }}>
          ${(n.recommended_actions || []).map((a, i) => html`<li key=${i} style=${{ marginBottom: "var(--s2)" }}>${a}</li>`)}
        </ol>
        <${Footer} page=${String(PN.watch)} />
      </div>

      <div class="pack-page">
        <${PackSecHead} num=${PN.evid} title=${"The evidence — where " + p.organisation.name + " leads"} />
        <p>${n.strengths_narrative}</p>
        <${PackTable} rows=${p.strengths} good=${true} />
        <h2 class="section-title" style=${{ marginTop: "var(--s4)" }}>Largest gaps to the market</h2>
        <p>${n.gaps_narrative}</p>
        <${PackTable} rows=${p.gaps} good=${false} />
        ${n.evidence_commentary ? html`<p style=${{ fontSize: "var(--fs-label)" }}>${n.evidence_commentary}</p>` : null}
        <${Footer} page=${String(PN.evid)} />
      </div>

      <div class="pack-page">
        <${PackSecHead} num=${PN.appx} title="Appendix — practices common among peers but not in place" />
        ${p.gap_register_top.length ? html`
          <table class="data">
            <thead><tr><th>Practice / policy</th><th>Area</th><th>Your status</th><th class="num">Peer adoption</th></tr></thead>
            <tbody>${p.gap_register_top.slice(0, 8).map((r, i) => html`
              <tr key=${i}><td>${r.name}</td><td>${r.superpower}</td><td class="caption">${r.your_status}</td>
              <td class="num"><b>${r.peer_adoption_pct}%</b> <span class="caption">(n=${r.n})</span></td></tr>`)}
            </tbody>
          </table>` : html`<p class="caption">No qualifying items.</p>`}
        <p class="caption" style=${{ marginTop: "var(--s3)" }}>Methodology: percentiles use linear interpolation; medians (P50) are
        preferred to means; aggregates resting on fewer than 5 organisations are suppressed; practice adoption is the share of
        assessable peer answers where the practice is at least partly in place ('Don't know' and 'Not applicable' answers excluded). Full methodology in the lumi platform.</p>
        <${Footer} page=${String(PN.appx)} />
      </div>
    </div>`;
};

function PackTable({ rows, good }) {
  if (!rows || !rows.length) return html`<p class="caption">None identified in this peer group.</p>`;
  // quartile/tail columns render only when the pack carries them (2026-07-02, WTW/Mercer
  // percentile-spread convention; Sprint-2 graduated display) — packs stored earlier keep
  // the old 5-column layout. Masked statistics (thin cuts) show as '—' with the legend.
  const hasQ = rows.some(r => r.p25_display || r.p75_display);
  const hasT = rows.some(r => r.p10_display || r.p90_display);
  const masked = rows.some(r => (r.p50_display && hasQ && !r.p25_display) || (r.p50_display && hasT && !r.p10_display));
  return html`
    <table class=${"data" + (hasT ? " bp-wide" : "")}>
      <thead><tr><th>Metric</th><th class="num">You</th>${hasT ? html`<th class="num">P10</th>` : null}${hasQ ? html`<th class="num">P25</th>` : null}<th class="num">${hasQ ? "P50" : "Peer P50"}</th>${hasQ ? html`<th class="num">P75</th>` : null}${hasT ? html`<th class="num">P90</th>` : null}<th class="num">${hasT ? "Pctl" : "Percentile"}</th><th class="num">n</th></tr></thead>
      <tbody>
        ${rows.map((r, i) => {
          // colour by the metric's own direction when the pack carries it (2026-07-02);
          // packs stored before that fall back to the old table-membership colour
          const cls = r.favourable ? (r.favourable === "good" ? "good" : r.favourable === "bad" ? "bad" : "") : (good ? "good" : "bad");
          return html`
          <tr key=${i}>
            <td><b>${r.label}</b><div class="caption">${r.superpower} · ${r.cut_label}${r.polarity === "lower_is_better" ? " · lower is better here" : ""}</div></td>
            <td class="num"><b>${r.value_display}</b></td>
            ${hasT ? html`<td class="num">${r.p10_display || "—"}</td>` : null}
            ${hasQ ? html`<td class="num">${r.p25_display || "—"}</td>` : null}
            <td class="num">${r.p50_display || html`<span class="caption" title="Score metric — peers are compared by score, not a single median value">score</span>`}</td>
            ${hasQ ? html`<td class="num">${r.p75_display || "—"}</td>` : null}
            ${hasT ? html`<td class="num">${r.p90_display || "—"}</td>` : null}
            <td class="num"><span class=${"chip " + cls}>${pLabel(r.percentile)}</span></td>
            <td class="num">${r.n}</td>
          </tr>`; })}
      </tbody>
    </table>
    ${masked ? html`<p class="caption bp-masknote">— = sample too small for that statistic (quartiles need n≥7, P10/P90 need n≥10; nothing below n=5 is ever shown).</p>` : null}`;
}
window.PackTable = PackTable;

// ------------------------------------------------------------- Ask lumi ----
const ANALYST_GREETING = { role: "bot", text: "Hi — I'm lumi. I can help you find a metric, explain a term, or show you how to use the platform. And ask how you compare on anything — I'll answer from the benchmark with the percentile, peer group and sample size cited." };

window.AnalystPane = function ({ onClose }) {
  const paneRef = useRef(null);
  const inputRef = useRef(null);
  // Esc anywhere closes (house idiom — Modal binds the same window listener);
  // with focus trapped in the pane below, the global binding is effectively scoped.
  useEffect(() => {
    const onKey = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  // Focus management (mirrors core.js Modal): capture the trigger, move focus
  // to the question input on open, restore the trigger on close.
  useEffect(() => {
    const trigger = document.activeElement;
    const t = setTimeout(() => { inputRef.current && inputRef.current.focus(); }, 0);
    return () => { clearTimeout(t); if (trigger && trigger.focus) trigger.focus(); };
  }, []);
  // Trap Tab/Shift+Tab within the pane (wrap first↔last, same idiom as Modal).
  const trapTab = (e) => {
    if (e.key !== "Tab" || !paneRef.current) return;
    const f = [...paneRef.current.querySelectorAll('button, input, textarea, select, [tabindex]:not([tabindex="-1"])')]
      .filter(el => !el.disabled && el.offsetParent);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  // The transcript survives close/reopen (one stray Esc must not wipe a
  // conversation) — session-scoped, never persisted anywhere.
  const [msgs, setMsgs] = useState(window._analystMsgs || [ANALYST_GREETING]);
  useEffect(() => { window._analystMsgs = msgs; }, [msgs]);
  const [starters, setStarters] = useState([]);
  const [showIdeas, setShowIdeas] = useState(msgs.length === 1);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef(null);
  const endRef = useRef(null);
  useEffect(() => { api("/api/analyst/starters").then(d => setStarters(d.starters)).catch(() => {}); }, []);
  useEffect(() => {
    const reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    endRef.current && endRef.current.scrollIntoView({ behavior: reduce ? "auto" : "smooth" });
  }, [msgs, busy]);
  useEffect(() => () => { abortRef.current && abortRef.current.abort(); }, []);
  const ask = async (q) => {
    if (!q.trim() || busy) return;
    setMsgs(m => [...m, { role: "user", text: q }]);
    setInput(""); setBusy(true); setShowIdeas(false);
    const ctl = new AbortController();
    abortRef.current = ctl;
    const timer = setTimeout(() => ctl.abort(), 60000);
    try {
      const r = await api("/api/analyst", { method: "POST", body: { question: q }, signal: ctl.signal });
      setMsgs(m => [...m, { role: "bot", text: r.answer, chips: r.chips, links: r.links, noMetric: r.no_metric, topic: r.topic }]);
    } catch (e) {
      const friendly = (e && e.name === "AbortError")
        ? "That took longer than it should — give it another go."
        : (e.status === 400 || e.status === 403 || e.status === 429 || e.status === 0)
          ? e.message
          : "Sorry — something went wrong on our side. Try again in a moment.";
      setMsgs(m => [...m, { role: "bot", text: friendly, retryQ: q }]);
    }
    clearTimeout(timer);
    abortRef.current = null;
    setBusy(false);
  };
  return html`
    <div class="analyst-pane" ref=${paneRef} role="dialog" aria-modal="true" aria-label="Ask lumi" onKeyDown=${trapTab}>
      <div class="row spread" style=${{ padding: "var(--s4)", borderBottom: "1px solid var(--border)" }}>
        <b>Ask lumi</b>
        <div class="row" style=${{ gap: "var(--s1)" }}>
          <button class="iconbtn" aria-label="Ideas to try" title="Ideas to try" onClick=${() => setShowIdeas(v => !v)}><${Icon} name="sparkle" size=${14} /></button>
          <button class="iconbtn" aria-label="Close Ask lumi (Esc)" title="Close (Esc)" onClick=${onClose}><${Icon} name="close" size=${14} /></button>
        </div>
      </div>
      <div class="analyst-msgs" aria-live="polite" aria-relevant="additions">
        ${msgs.map((m, i) => html`
          <div key=${i} class=${"msg " + m.role}>
            ${m.text}
            ${m.role === "bot" && i > 0 && m.text && !m.retryQ && html`
              <button class="msg-copy" aria-label="Copy answer" title="Copy"
                onClick=${() => { navigator.clipboard && navigator.clipboard.writeText(m.text).then(() => toast("Copied")); }}><${Icon} name="copy" size=${12} /></button>`}
            ${m.retryQ && html`
              <div><button class="btn small" style=${{ marginTop: "var(--s2)" }}
                onClick=${() => ask(m.retryQ)}>Try again</button></div>`}
            ${m.noMetric && html`
              <div><button class="btn small" style=${{ marginTop: "var(--s2)" }}
                onClick=${() => window.openMetricRequest(m.topic, "ask-lumi")}>Request this metric</button></div>`}
            ${m.links && m.links.length > 0 && html`
              <div style=${{ marginTop: "var(--s2)", display: "flex", gap: "var(--s2)", flexWrap: "wrap" }}>
                ${m.links.map((l, j) => html`<button key=${j} class="btn small outline-navy"
                  onClick=${() => { nav(l.route); onClose(); }}>${l.label} →</button>`)}</div>`}
            ${m.chips && m.chips.length > 0 && html`
              <div>${m.chips.map((c, j) => html`
                <div key=${j} class="statchip" role=${c.question_id ? "button" : null} tabindex=${c.question_id ? "0" : null}
                  onKeyDown=${c.question_id ? (e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nav("/metric/" + c.question_id); onClose(); } }) : null}
                  onClick=${() => { c.question_id && nav("/metric/" + c.question_id); onClose(); }}>
                  <span>${c.label}</span><b>${c.value}</b><span>${c.sub}</span>
                  ${c.question_id && html`<span style=${{ color: "var(--blue-deep)" }}>View metric →</span>`}
                </div>`)}</div>`}
          </div>`)}
        ${busy && html`<div class="msg bot"><span class="tdots" aria-hidden="true"><span></span><span></span><span></span></span> Looking that up…</div>`}
        ${showIdeas && starters.length > 0 && html`
          <div>
            <div class="caption" style=${{ marginBottom: "var(--s2)" }}>Try one of these — compare, find a metric, learn a term, or get help:</div>
            ${starters.map((s, i) => html`
              <button key=${i} class="btn small" style=${{ margin: "0 var(--s2) var(--s2) 0", whiteSpace: "normal", textAlign: "left" }}
                onClick=${() => ask(s)}>${s}</button>`)}
          </div>`}
        <div ref=${endRef}></div>
      </div>
      <div style=${{ padding: "var(--s3)", borderTop: "1px solid var(--border)", display: "flex", gap: "var(--s2)" }}>
        <input class="ctl" ref=${inputRef} style=${{ flex: 1, maxWidth: "none" }}
          placeholder="Ask about a metric, a term, or how lumi works…" aria-label="Ask lumi a question"
          value=${input} onInput=${e => setInput(e.target.value)}
          onKeyDown=${e => { if (e.key === "Enter" && !e.isComposing && e.keyCode !== 229) ask(input); }} />
        <button class="btn primary" disabled=${busy} aria-busy=${busy ? "true" : "false"} onClick=${() => ask(input)}>Ask</button>
      </div>
    </div>`;
};

// -------------------------------------------------------------- Peer Twin --
window.PeerTwinPanel = function ({ onUse, onClose }) {
  useEffect(() => {
    const onKey = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  const [data, setData] = useState(null);
  useEffect(() => { api("/api/peer-twin").then(setData).catch(e => setData({ available: false, message: e.message })); }, []);
  return html`
    <${Modal} onClose=${onClose}>
      <h2 class="section-title">Organisations like you</h2>
      ${!data ? html`<${Spinner} />` :
      !data.available ? html`<p>${data.message}</p>` :
      html`<div>
        <p>${data.rationale.note}</p>
        <h3 style=${{ fontSize: "var(--fs-label)", margin: "var(--s3) 0 var(--s2)" }}>Why these peers?</h3>
        <table class="data">
          <thead><tr><th>Attribute</th><th>You</th><th class="num">Matching twin peers</th></tr></thead>
          <tbody>
            ${data.rationale.attributes.map(a => html`
              <tr key=${a.attribute}>
                <td>${a.attribute}</td><td><b>${a.your_value}</b></td>
                <td class="num">${a.matching_peers} of ${a.of}</td>
              </tr>`)}
          </tbody>
        </table>
        <p class="caption" style=${{ marginTop: "var(--s3)" }}>Similarity also weighs workforce shape (frontline, shift and unionised
        percentages). Peer names are never shown, and anything resting on fewer than 5 of these organisations stays hidden.</p>
        <div class="row" style=${{ justifyContent: "flex-end", marginTop: "var(--s3)" }}>
          <button class="btn" onClick=${onClose}>Close</button>
          <button class="btn primary" onClick=${() => { onUse(); onClose(); }}>Use as my peer group</button>
        </div>
      </div>`}
    <//>`;
};

// ----------------------------------------------------------------- shares --
window.SharesPage = function ({ embedded }) {
  const [data, setData] = useState(null);
  const refresh = () => api("/api/shares").then(setData);
  useEffect(() => { refresh(); }, []);
  const [making, setMaking] = useState(false);
  // B10 + high-pack 2·5 (2026-07-09 ship review): revoked links collapse behind a toggle —
  // every link ever minted rendered forever (122 rows, 111 revoked → a 16,500px Settings page).
  const [showRevoked, setShowRevoked] = useState(false);
  const revoke = async (t) => { await api("/api/shares/" + t, { method: "DELETE" }); refresh(); toast("Share link revoked"); };
  const createDash = async (days) => {
    if (making) return;
    setMaking(true);
    try {
      await api("/api/shares", { method: "POST", body: { kind: "dashboard", config: { cut: { dim: "all" } }, expiry_days: days } });
      refresh(); toast("Share link created (" + days + " days)");
    } catch (e) { toast(e.message || "Couldn't create the share link", "error"); }
    setMaking(false);
  };
  if (!data) return html`<${PageLoading} />`;
  return html`
    <div style=${{ maxWidth: "880px" }}>
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <h1 class="display-title">Manage shares</h1>
          <div class="caption" style=${{ marginTop: "var(--s1)" }}>Read-only links for people outside your lumi team. A link shows exactly what your team can see — your data plus safe peer aggregates — and nothing more.</div>
        </div>
        <div class="row">
          <button class="btn" disabled=${making} onClick=${() => createDash(7)}>Share dashboard (7 days)</button>
          <button class="btn" disabled=${making} onClick=${() => createDash(30)}>30 days</button>
          <button class="btn" disabled=${making} onClick=${() => createDash(90)}>90 days</button>
        </div>
      </div>
      ${data.shares.length === 0 ? html`<${EmptyState} icon="link" title="No share links yet"
        body="Create a dashboard share above, or share a board pack from its page." />` :
      html`<div class="card" style=${{ padding: "var(--s4)" }}>
        ${(() => {
          // B10 (2026-07-09 ship review): the 894px table bled 300px+ past the ~590px settings
          // card onto bare canvas — contain it in an overflow-x:auto wrap (house pattern:
          // the gap-register table above / .matrix-heat-wrap, app.css). The audit trail —
          // the widest, tallest cell — now shows the latest event only, with earlier events
          // behind a native <details> disclosure (high-pack 2·5; audit arrives oldest-first).
          const fmtAudit = a => `${a.action} by ${a.email || "?"} · ${new Date(a.at + "Z").toLocaleString("en-GB", { dateStyle: "short", timeStyle: "short" })}`;
          const revokedShares = data.shares.filter(s => s.revoked);
          const rows = showRevoked ? data.shares : data.shares.filter(s => !s.revoked);
          return html`
        ${rows.length === 0 ? html`<p class="caption" style=${{ margin: 0 }}>No live share links.</p>` : html`
        <div style=${{ overflowX: "auto" }}>
        <table class="data">
          <thead><tr><th>Type</th><th>Link</th><th>Expires</th><th>Status</th><th>Activity</th><th></th></tr></thead>
          <tbody>
            ${rows.map(s => html`
              <tr key=${s.token} style=${s.revoked ? { opacity: 0.55 } : null}>
                <td><b>${s.kind === "boardpack" ? "Board pack" : "Dashboard"}</b></td>
                <td>${s.revoked ? html`<span class="muted">revoked</span>` :
                  html`<a href=${s.url} target="_blank">${window.location.origin}${s.url.slice(0, 18)}…</a>
                  <button class="iconbtn" title="Copy link" aria-label="Copy share link" onClick=${() => { navigator.clipboard.writeText(window.location.origin + s.url); toast("Link copied to clipboard"); }}><${Icon} name="copy" size=${14} /></button>`}</td>
                <td>${s.expires_at ? new Date(s.expires_at + "Z").toLocaleDateString("en-GB") : "Never"}</td>
                <td>${s.revoked ? html`<span class="chip bad">Revoked</span>` :
                  (s.expires_at && new Date(s.expires_at + "Z") < new Date()) ? html`<span class="chip warn">Expired</span>` :
                  html`<span class="chip good">Live</span>`}</td>
                <td class="caption">${s.audit.length === 0 ? "—" : html`
                  <div>${fmtAudit(s.audit[s.audit.length - 1])}</div>
                  ${s.audit.length > 1 ? html`
                    <details>
                      <summary style=${{ cursor: "pointer" }}>${s.audit.length - 1} earlier event${s.audit.length === 2 ? "" : "s"}</summary>
                      ${s.audit.slice(0, -1).reverse().map((a, i) => html`<div key=${i}>${fmtAudit(a)}</div>`)}
                    </details>` : null}`}</td>
                <td>${!s.revoked && html`<button class="btn small danger" onClick=${() => revoke(s.token)}>Revoke</button>`}</td>
              </tr>`)}
          </tbody>
        </table>
        </div>`}
        ${revokedShares.length > 0 ? html`
          <button class="btn small quiet" style=${{ marginTop: "var(--s3)" }} onClick=${() => setShowRevoked(v => !v)}>
            ${showRevoked ? "Hide revoked" : "Show revoked (" + revokedShares.length + ")"}</button>` : null}`;
        })()}
      </div>`}
    </div>`;
};

// ------------------------------------------------------------------ team ---
const ROLE_DESC = {
  admin: "Full control — data, team, sharing, and accepting the organisation's data terms.",
  contributor: "Submits and edits the organisation's reward data.",
  viewer: "Sees the benchmark and board packs — no editing.",
};

window.TeamPage = function ({ me }) {
  const [data, setData] = useState(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("contributor");
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const refresh = () => api("/api/team").then(setData);
  useEffect(() => { refresh(); }, []);
  const isAdmin = me.user.role === "admin";
  const [inviting, setInviting] = useState(false);
  const [inviteLink, setInviteLink] = useState(null);
  const invite = async () => {
    if (inviting) return;
    setErr(null); setMsg(null); setInviting(true);
    try {
      const r = await api("/api/team/invite", { method: "POST", body: { email, role } });
      setMsg(`Invite sent to ${email} — the link expires in ${r.expires_days} days. You can also copy it and share it yourself:`);
      setInviteLink(r.link);
      toast("Invite sent to " + email);
      setEmail(""); refresh();
    } catch (e) { setErr(e.message); }
    setInviting(false);
  };
  const setMemberRole = async (uEmail, newRole) => {
    setErr(null); setMsg(null);
    try {
      await api("/api/team/role", { method: "PUT", body: { email: uEmail, role: newRole } });
      setMsg(`${uEmail} is now ${ROLE_LABEL[newRole]}.`); refresh();
      toast(uEmail + " is now " + ROLE_LABEL[newRole]);
    } catch (e) { setErr(e.message); refresh(); }
  };
  const remove = async (uEmail) => {
    setErr(null); setMsg(null);
    if (!window.confirm(`Remove ${uEmail} from your organisation? Their account is deleted; your organisation's data is unaffected.`)) return;
    try { await api("/api/team/member", { method: "DELETE", body: { email: uEmail } }); setMsg(`${uEmail} removed.`); refresh(); toast(uEmail + " removed from your organisation"); }
    catch (e) { setErr(e.message); }
  };
  if (!data) return html`<${PageLoading} />`;
  return html`
    <div style=${{ maxWidth: "800px" }}>
      <h1 class="display-title">Team</h1>
      <p class="caption">Everyone here works on the same organisation — one dataset, one benchmark, one
        contribution clock. Roles decide who can edit.</p>
      <div class="card" style=${{ padding: "var(--s4)", margin: "var(--s4) 0" }}>
        <table class="data">
          <thead><tr><th>Member</th><th>Role</th><th>Joined</th>${isAdmin && html`<th></th>`}</tr></thead>
          <tbody>
            ${data.users.map(u => html`
              <tr key=${u.email}><td><b>${u.display_name || u.email}</b><div class="caption">${u.email}${u.email === me.user.email ? " (you)" : ""}</div></td>
              <td>${isAdmin ? html`
                <select class="ctl" style=${{ minWidth: "130px" }} value=${u.role}
                  title=${ROLE_DESC[u.role]}
                  onChange=${e => setMemberRole(u.email, e.target.value)}>
                  <option value="admin">Admin</option>
                  <option value="contributor">Contributor</option>
                  <option value="viewer">Viewer</option>
                </select>` :
                html`<span class=${"chip " + (u.role === "admin" ? "accent" : "")} title=${ROLE_DESC[u.role]}>${ROLE_LABEL[u.role] || u.role}</span>`}</td>
              <td class="caption">${new Date(u.created_at + "Z").toLocaleDateString("en-GB")}</td>
              ${isAdmin && html`<td style=${{ textAlign: "right" }}>
                <button class="btn small quiet" onClick=${() => remove(u.email)}>Remove</button></td>`}</tr>`)}
          </tbody>
        </table>
        ${msg && html`<div class="ok-text" role="status" style=${{ marginTop: "var(--s2)" }}>${msg}</div>`}
        ${inviteLink && html`<div class="row" style=${{ marginTop: "var(--s2)", gap: "var(--s2)" }}>
          <input class="ctl" readonly value=${inviteLink} style=${{ flex: 1, maxWidth: "none" }} aria-label="Invite link"
            onFocus=${e => e.target.select()} />
          <button class="btn small" onClick=${() => { navigator.clipboard && navigator.clipboard.writeText(inviteLink).then(() => toast("Invite link copied")); }}>Copy link</button>
        </div>`}
        ${err && html`<div class="error-text" role="alert" style=${{ marginTop: "var(--s2)" }}>${err}</div>`}
        <div class="caption" style=${{ marginTop: "var(--s3)" }}>
          <b>Admin</b> — ${ROLE_DESC.admin}<br/>
          <b>Contributor</b> — ${ROLE_DESC.contributor}<br/>
          <b>Viewer</b> — ${ROLE_DESC.viewer}<br/>
          Your organisation always keeps at least one Admin — promote a colleague before stepping back.
        </div>
      </div>
      ${isAdmin && html`
        <div class="card invite-form" style=${{ padding: "var(--s4)" }}>
          <h2 class="section-title">Invite a colleague</h2>
          <div class="row">
            <input class="ctl" style=${{ flex: 1 }} placeholder="colleague@yourorg.co.uk" aria-label="Colleague's email address"
              value=${email} onInput=${e => setEmail(e.target.value)} onKeyDown=${e => { if (e.key === "Enter") invite(); }} />
            <select class="ctl" value=${role} onChange=${e => setRole(e.target.value)}>
              <option value="contributor">Contributor — fills the questionnaire</option>
              <option value="viewer">Viewer — dashboards & board packs</option>
            </select>
            <button class="btn primary" disabled=${inviting} onClick=${invite}>${inviting ? html`<${Spinner} />` : "Send invite"}</button>
          </div>
          <div class="caption" style=${{ marginTop: "var(--s2)" }}>Invites expire after 7 days. Need another Admin?
            Invite them as Contributor, then promote them above. Joiners accept the Platform Terms only —
            your Data Contribution agreement covers the whole organisation.</div>
          ${data.invites.length > 0 && html`
            <h3 style=${{ fontSize: "var(--fs-label)", margin: "var(--s4) 0 var(--s2)" }}>Outstanding invites</h3>
            ${data.invites.map(i => html`
              <div key=${i.token} class="caption row spread">
                <span>${i.email} (${ROLE_LABEL[i.role] || i.role}) — expires ${new Date(i.expires_at + "Z").toLocaleDateString("en-GB")}</span>
                <button class="btn small quiet" onClick=${async () => { await api("/api/team/invite/" + i.token, { method: "DELETE" }); refresh(); toast("Invite revoked"); }}>Revoke</button>
              </div>`)}`}
        </div>`}
    </div>`;
};

// -------------------------------------------------------------- settings ---
// Personal notification preferences — the bell (default on), the email digest
// (opt-in), which lenses you hear about, good news, and a personal £ floor.
const NOTIF_LENSES = [
  { k: "attract", label: "Attract", icon: "magnet" }, { k: "retain", label: "Retain", icon: "anchor" },
  { k: "engage", label: "Engage", icon: "heart" }, { k: "save", label: "Save", icon: "coins" },
];
function NotificationsSettings() {
  const [p, setP] = useState(null);
  const [floor, setFloor] = useState(10000);
  const [saved, setSaved] = useState(false);
  useEffect(() => { api("/api/notify-prefs").then(d => { setP(d.prefs); setFloor(d.min_money_floor || 10000); }).catch(() => {}); }, []);
  if (!p) return html`<div class="row" style=${{ padding: "var(--s4) 0" }}><${Spinner} /></div>`;
  const save = (next) => {
    setP(next);
    api("/api/notify-prefs", { method: "PUT", body: { prefs: next } })
      .then(() => { setSaved(true); setTimeout(() => setSaved(false), 1500); }).catch(() => {});
  };
  const toggleLens = (l) => {
    const set = new Set(p.lenses);
    if (set.has(l)) set.delete(l); else set.add(l);
    save({ ...p, lenses: Array.from(set) });
  };
  const goodNews = p.events.includes("cleared");
  return html`
    <div class="notif-prefs">
      <label class="na-toggle" style=${{ marginBottom: "var(--s3)" }}>
        <input type="checkbox" checked=${p.inbox_enabled} onChange=${e => save({ ...p, inbox_enabled: e.target.checked })} />
        <span><b>Show the notification bell</b> — your in-app inbox of changes</span>
      </label>
      <div class="field">
        <label>Email digest</label>
        <div class="seg-toggle" role="radiogroup" aria-label="Email digest frequency">
          ${["off", "daily", "weekly"].map(f => html`
            <button key=${f} class=${"seg-btn" + (p.email_frequency === f ? " on" : "")} role="radio"
              aria-checked=${p.email_frequency === f} onClick=${() => save({ ...p, email_frequency: f })}>
              ${f.charAt(0).toUpperCase() + f.slice(1)}</button>`)}
        </div>
        <div class="caption" style=${{ marginTop: "var(--s2)" }}>A weekly digest is on by default — at most 3 a week, never more than one a day. Switch to Daily or Off any time — and every email tells you how to unsubscribe.</div>
      </div>
      <div class="field">
        <label>What to hear about</label>
        <div class="notif-lens-checks">
          ${NOTIF_LENSES.map(l => html`
            <label key=${l.k} class="check-row notif-lens-check">
              <input type="checkbox" checked=${p.lenses.includes(l.k)} onChange=${() => toggleLens(l.k)} />
              <span class=${"lens-" + l.k}><${Icon} name=${l.icon} size=${13} /> ${l.label}</span>
            </label>`)}
        </div>
      </div>
      <label class="na-toggle">
        <input type="checkbox" checked=${goodNews}
          onChange=${e => save({ ...p, events: e.target.checked ? ["appeared", "moved", "cleared"] : ["appeared", "moved"] })} />
        <span>Include good news — tell me when a flag <b>clears</b></span>
      </label>
      <div class="field" style=${{ marginTop: "var(--s3)" }}>
        <label>£ changes smaller than this won't notify me</label>
        <div class="unit-input" style=${{ maxWidth: "180px" }}>
          <span class="unit-sym">£</span>
          <input type="number" step="1000" min=${floor} value=${p.min_money_gbp}
            onChange=${e => save({ ...p, min_money_gbp: Math.max(floor, parseInt(e.target.value, 10) || 0) })} />
        </div>
        <div class="caption" style=${{ marginTop: "var(--s2)" }}>Your floor can be stricter than lumi's (£${floor.toLocaleString("en-GB")}), never looser.</div>
      </div>
      ${saved && html`<div class="ok-text" style=${{ marginTop: "var(--s2)" }}>Saved.</div>`}
    </div>`;
}

// high-pack 2·4 (2026-07-09 ship review): early acceptances were logged against "1.0-draft"
// terms ids while the published docs and server constants are v1.0 finals (app.py:164) —
// Settings rendered the internal suffix verbatim on the trust surface. Strip it at render;
// the stored-row migration ('1.0-draft'→'1.0') is tracked server-side.
const termsVer = v => String(v == null ? "" : v).replace(/-draft$/, "");

window.SettingsPage = function ({ me, refreshMe }) {
  const [a, setA] = useState(null);
  const [editable, setEditable] = useState(false);
  const [msg, setMsg] = useState(null);
  const [aiDoc, setAiDoc] = useState(false);
  const [aiBusy, setAiBusy] = useState(false);
  const ai = me.ai_insights || {};
  const setAiConsent = async (consent) => {
    if (aiBusy) return; setAiBusy(true);
    try { await api("/api/ai-consent", { method: "POST", body: { consent } }); await refreshMe(); } catch (e) {}
    setAiBusy(false);
  };
  useEffect(() => { api("/api/assumptions").then(d => { setA(d.assumptions); setEditable(d.editable); }); }, []);
  const save = async () => {
    await api("/api/assumptions", { method: "PUT", body: { assumptions: {
      median_salary_gbp: +a.median_salary_gbp, cost_per_leaver_pct_salary: +a.cost_per_leaver_pct_salary,
      agency_premium_pct: +a.agency_premium_pct } } });
    setMsg("Saved — £ figures across lumi now use these assumptions."); setTimeout(() => setMsg(null), 3000);
  };
  if (!a) return html`<${PageLoading} />`;
  return html`
    <div style=${{ maxWidth: "640px" }}>
      <h1 class="display-title">Settings</h1>
      <div class="card" style=${{ padding: "var(--s5)", margin: "var(--s4) 0" }}>
        <h2 class="section-title">£ modelling assumptions</h2>
        <p class="caption">Every "opportunity" figure in lumi is indicative and rests on these assumptions. Change them to match your organisation.</p>
        <div class="field"><label>Median salary (£/yr)</label>
          <input type="number" value=${a.median_salary_gbp} disabled=${!editable} onInput=${e => setA({ ...a, median_salary_gbp: e.target.value })} /></div>
        <div class="field"><label>Cost per leaver (% of salary — recruitment, cover and ramp-up)</label>
          <input type="number" value=${a.cost_per_leaver_pct_salary} disabled=${!editable} onInput=${e => setA({ ...a, cost_per_leaver_pct_salary: e.target.value })} /></div>
        <div class="field"><label>Agency premium (% over employed cost)</label>
          <input type="number" value=${a.agency_premium_pct} disabled=${!editable} onInput=${e => setA({ ...a, agency_premium_pct: e.target.value })} /></div>
        <div class="caption" style=${{ marginBottom: "var(--s3)" }}>Workforce mix by level and FTE band midpoints are fixed platform assumptions, shown in the <a href="#/methodology">methodology</a>.</div>
        ${editable ? html`<button class="btn primary" onClick=${save}>Save assumptions</button>` :
        html`<div class="caption">Only admins can edit assumptions.</div>`}
        ${msg && html`<div class="ok-text" style=${{ marginTop: "var(--s2)" }}>${msg}</div>`}
      </div>
      <div class="card" id="notifications" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Notifications</h2>
        <p class="caption">When your position against the market changes — a flag appears, clears, or shifts —
          we record it to your bell and (if you opt in) an email digest. These are personal to you.</p>
        <${NotificationsSettings} />
      </div>
      <div class="card" id="ai-insights" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">AI Insights</h2>
        <p class="caption">Short, written interpretations of <b>your own benchmark figures</b>, generated by AI —
          a description of your data, not advice. AI Insights are on by default; you can turn them off here at any
          time, and this setting is personal to you.</p>
        <div class="row spread" style=${{ alignItems: "center", marginTop: "var(--s3)" }}>
          <div>
            <b>${ai.consented ? "On for you" : "Off"}</b>${ai.consented && ai.consented_at ? html`
              <span class="caption"> · since ${new Date(ai.consented_at + "Z").toLocaleDateString("en-GB")}
              ${" "}(v${termsVer(ai.version || ai.terms_version)})</span>` : null}
          </div>
          <button class=${"btn small" + (ai.consented ? "" : " primary")} disabled=${aiBusy}
            onClick=${() => setAiConsent(!ai.consented)}>
            ${aiBusy ? html`<${Spinner} />` : ai.consented ? "Turn off AI Insights" : "Turn on AI Insights"}</button>
        </div>
        ${ai.consented && !ai.master ? html`<div class="caption" style=${{ marginTop: "var(--s2)" }}>
          AI Insights aren't switched on across lumi yet — your setting is saved and applies the moment they go
          live.</div>` : null}
        <div class="caption" style=${{ marginTop: "var(--s2)" }}>
          Read the <a onClick=${e => { e.preventDefault(); setAiDoc(true); }} style=${{ cursor: "pointer" }}>AI Insights Terms</a>.</div>
      </div>
      ${aiDoc && html`<${LegalDocModal} docKey="ai_insights" onClose=${() => setAiDoc(false)} />`}
      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Company profile</h2>
        <p class="caption">The organisation facts behind your peer groups — sector, size, region, ownership
        and workforce shape. ${me.user.role === "admin" ? "Firmographics change; update them any time." : "Your Admin keeps these up to date."}</p>
        <a class="btn small" href="#/profile">${me.user.role === "admin" ? "View / edit profile" : "View profile"}</a>
      </div>
      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Terms & agreements</h2>
        ${me.org.data_terms && me.org.data_terms.accepted ? html`
          <p>Data Contribution Terms <b>accepted</b> by <b>${me.org.data_terms.accepted_by}</b> on
            ${" "}${new Date(me.org.data_terms.accepted_at + "Z").toLocaleDateString("en-GB")} (v${termsVer(me.org.data_terms.version)}).
            This logged acceptance is your organisation's agreement — it covers your whole team.</p>` : html`
          <p>Data Contribution Terms <b>not yet accepted</b> — your organisation's Admin reviews and accepts
            them on the <a href="#/your-data/submit">Your data</a> page before the first submission.</p>`}
        <div class="row" style=${{ gap: "var(--s3)" }}>
          <a href="/api/terms/dpa" download class="btn small">Download the full Data Sharing Agreement (DPA)</a>
        </div>
        <div class="caption" style=${{ marginTop: "var(--s2)" }}>The DPA is optional — for members whose legal or
          data-protection teams want the fuller instrument. These are the current
          ${" "}<span class="chip">published versions</span></div>
      </div>
      <div class="card" id="sharing" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <${SharesPage} embedded=${true} />
      </div>
    </div>`;
};

// -------------------------------------------------------- request a metric --
window.RequestMetricModal = function ({ prefill, source, onClose }) {
  const [text, setText] = useState(prefill || "");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState(null);
  const submit = async () => {
    if (!text.trim() || busy) return;
    setBusy(true); setErr(null);
    try {
      await api("/api/metric-requests", { method: "POST", body: { text, notes, source: source || "button" } });
      setDone(true);
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  return html`
    <${Modal} onClose=${onClose}>
      ${done ? html`
        <div style=${{ textAlign: "center", padding: "var(--s4) 0" }}>
          <div style=${{ color: "var(--blue)", marginBottom: "var(--s2)" }}><${Icon} name="sparkle" size=${22} /></div>
          <h2 class="section-title">Thanks — we'll consider this for the next benchmark cycle.</h2>
          <button class="btn" style=${{ marginTop: "var(--s3)" }} onClick=${onClose}>Close</button>
        </div>` : html`
        <div>
          <h2 class="section-title">Request a metric</h2>
          <p class="caption" style=${{ marginTop: "-4px" }}>lumi is shaped by its members — tell us what to measure.</p>
          <div class="field" style=${{ marginTop: "var(--s4)" }}>
            <label>What would you like to benchmark?</label>
            <input autoFocus value=${text} onInput=${e => setText(e.target.value)}
              placeholder="e.g. car allowance for field sales reps"
              onKeyDown=${e => { if (e.key === "Enter") submit(); }} />
          </div>
          <div class="field">
            <label>Anything that would help us define it? <span class="muted">(optional)</span></label>
            <textarea rows="3" value=${notes} onInput=${e => setNotes(e.target.value)}
              placeholder="Context, units, who it applies to…"></textarea>
          </div>
          ${err && html`<div class="error-text" style=${{ marginBottom: "var(--s2)" }}>${err}</div>`}
          <div class="row" style=${{ justifyContent: "flex-end" }}>
            <button class="btn quiet" onClick=${onClose}>Cancel</button>
            <button class="btn primary" disabled=${busy || !text.trim()} onClick=${submit}>
              ${busy ? html`<${Spinner} />` : "Send to lumi"}</button>
          </div>
        </div>`}
    <//>`;
};

// ----------------------------------------------------- suggest a metric -----
// Richer, structured suggestion (distinct from the lightweight search "request
// a metric"): name + definition + rationale + optional category, its own table
// and endpoint. The honest subtitle deliberately does NOT promise inclusion —
// suggestions are input to a deliberate, research-standards review.
window.SUGGEST_CATEGORIES = ["Pay", "Incentives", "Benefits", "Time off", "Wellbeing", "Recognition", "Governance", "Not sure"];
window.SuggestMetricModal = function ({ onClose, userEmail }) {
  const [name, setName] = useState("");
  const [measures, setMeasures] = useState("");
  const [matters, setMatters] = useState("");
  const [category, setCategory] = useState("");
  const [errs, setErrs] = useState({});
  const [general, setGeneral] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [closing, setClosing] = useState(false);
  const cardRef = useRef(null);
  const nameRef = useRef(null);
  // 2.6 — animated close: play the exit animation, then unmount. Reduced motion
  // skips the delay entirely (off means off). Focus return happens on unmount.
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const close = () => {
    if (reduced) { onClose(); return; }
    setClosing(true);
    setTimeout(onClose, 250);
  };
  // focus the first field on open; restore focus to the trigger (the pill) on close
  useEffect(() => {
    const trigger = document.activeElement;
    const t = setTimeout(() => nameRef.current && nameRef.current.focus(), 0);
    return () => { clearTimeout(t); if (trigger && trigger.focus) trigger.focus(); };
  }, []);
  // Escape closes; Tab cycles within the card (close → fields → cancel → submit → close)
  const onKeyDown = (e) => {
    if (e.key === "Escape") { close(); return; }
    if (e.key !== "Tab" || !cardRef.current) return;
    const f = [...cardRef.current.querySelectorAll("button, input, textarea, select")].filter(el => !el.disabled && el.offsetParent);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  const submit = async () => {
    if (busy) return;
    const next = {};
    if (!name.trim()) next.name = "Please add a metric name.";
    if (!measures.trim()) next.measures = "Please describe what it measures.";
    if (!matters.trim()) next.matters = "Please explain why it matters.";
    setErrs(next); setGeneral(null);
    if (Object.keys(next).length) return;   // no API call while invalid
    setBusy(true);
    try {
      await api("/api/suggestions", { method: "POST", body: {
        metric_name: name.trim(), what_it_measures: measures.trim(),
        why_it_matters: matters.trim(), suggested_category: category || null } });
      setDone(true);
    } catch (e) {
      if (e.status === 401) setGeneral("Please sign in again to submit.");
      else if (e.status === 400 && typeof e.message === "string") setGeneral(e.message);
      else setGeneral("Something went wrong. Please try again.");
      setBusy(false);
    }
  };
  return html`
    <div class=${"suggest-back" + (closing ? " closing" : "")} onClick=${e => { if (e.target === e.currentTarget) close(); }}>
      <div class=${"suggest-modal" + (closing ? " closing" : "")} ref=${cardRef} role="dialog" aria-modal="true" aria-labelledby="suggest-title" onKeyDown=${onKeyDown}>
        <button class="suggest-close" aria-label="Close" onClick=${close}><${Icon} name="close" size=${16} /></button>
        <div class="suggest-head">
          <h2 id="suggest-title" class="suggest-title">Suggest a metric</h2>
          <p class="suggest-sub">Help shape lumi's methodology. We review every suggestion against our research standards and email you when we've made a decision.</p>
        </div>
        ${done ? html`
          <div class="suggest-done">
            <div class="suggest-done-ring"><${Icon} name="check" size=${24} /></div>
            <div class="suggest-done-head">Thanks — we've got it.</div>
            <div class="suggest-done-body">${userEmail
              ? html`We'll email you at ${userEmail} when we've reviewed your suggestion.`
              : html`We'll email you when we've reviewed your suggestion.`}</div>
            <button class="btn primary suggest-done-btn" onClick=${close}>Done</button>
          </div>` : html`
          <div class="suggest-body">
            <div class="suggest-field">
              <label for="sg-name">Metric name</label>
              <input id="sg-name" ref=${nameRef} class=${"suggest-input" + (errs.name ? " err" : "")} value=${name}
                onInput=${e => setName(e.target.value)} placeholder="e.g. Internal mobility rate" />
              <div class="suggest-hint">Short and specific. What would you call this on a dashboard?</div>
              ${errs.name && html`<div class="suggest-err" role="alert">${errs.name}</div>`}
            </div>
            <div class="suggest-field">
              <label for="sg-measures">What it measures</label>
              <textarea id="sg-measures" rows="3" class=${"suggest-input" + (errs.measures ? " err" : "")} value=${measures}
                onInput=${e => setMeasures(e.target.value)} placeholder="e.g. The percentage of open roles filled by internal candidates over a 12-month period."></textarea>
              <div class="suggest-hint">One or two sentences. Treat this as the definition.</div>
              ${errs.measures && html`<div class="suggest-err" role="alert">${errs.measures}</div>`}
            </div>
            <div class="suggest-field">
              <label for="sg-matters">Why it matters</label>
              <textarea id="sg-matters" rows="3" class=${"suggest-input" + (errs.matters ? " err" : "")} value=${matters}
                onInput=${e => setMatters(e.target.value)} placeholder="e.g. It signals how well an organisation develops and retains internal talent — relevant for engagement and retention benchmarking."></textarea>
              <div class="suggest-hint">What decision would this help reward leaders make?</div>
              ${errs.matters && html`<div class="suggest-err" role="alert">${errs.matters}</div>`}
            </div>
            <div class="suggest-field">
              <label for="sg-cat">Suggested category</label>
              <select id="sg-cat" class="suggest-input" value=${category} onInput=${e => setCategory(e.target.value)}>
                <option value="">Select a category if you know</option>
                ${SUGGEST_CATEGORIES.map(c => html`<option key=${c} value=${c}>${c}</option>`)}
              </select>
            </div>
            ${general && html`<div class="suggest-err suggest-general">${general}</div>`}
          </div>
          <div class="suggest-foot">
            <button class="btn quiet suggest-cancel" onClick=${close}>Cancel</button>
            <button class="btn primary suggest-submit" disabled=${busy} onClick=${submit}>${busy ? "Submitting…" : "Submit suggestion"}</button>
          </div>`}
      </div>
    </div>`;
};

// --------------------------------------------------- board packs home (U2) ---
/* Every stored pack, org-scoped, with open + admin delete. The export menu's
   dropdown stays the quick path; this page gives packs a real URL (#/boardpack)
   — before it, the bare route fell through to Overview and a pack was only
   reachable right after generating or via a kept link. */
window.BoardPacksPage = function ({ me }) {
  const [packs, setPacks] = useState(null);
  const [err, setErr] = useState(null);
  const load = () => { setErr(null); api("/api/boardpacks").then(d => setPacks(d.packs || [])).catch(e => setErr(e.message)); };
  useEffect(() => { load(); }, []);
  const del = async (p) => {
    if (!window.confirm("Delete this board pack? Any share links minted for it will stop working.")) return;
    try { await api("/api/boardpack/" + p.pack_id, { method: "DELETE" }); toast("Board pack deleted."); load(); }
    catch (e) { toast(e.message, "error"); }
  };
  if (err) return html`<${EmptyState} icon="info" title="Couldn't load your board packs" body=${err}
    action=${html`<button class="btn small primary" onClick=${load}>Try again</button>`} />`;
  if (!packs) return html`<${PageLoading} />`;
  return html`
    <div style=${{ maxWidth: "720px" }}>
      <a class="caption back-link" href="#/overview"><${Icon} name="chevron-left" size=${13} /> Overview</a>
      <h1 class="display-title" style=${{ margin: "var(--s2) 0 var(--s1)" }}>Board packs</h1>
      <p class="caption" style=${{ marginBottom: "var(--s4)" }}>Every pack your team has generated — each a snapshot
        of your position when it was written. Export a fresh one from Overview.</p>
      ${packs.length === 0 ? html`<${EmptyState} icon="file-text" title="No board packs yet"
        body="Export writes a board-ready narrative of your position under the current peer filter."
        action=${html`<button class="btn small primary" onClick=${() => nav("/overview")}>Go to Overview</button>`}/>` :
      html`<div class="bp-list">
        ${packs.map(p => html`
          <div key=${p.pack_id} class="card bp-list-row">
            <div class="bp-list-main" role="button" tabindex="0" aria-label=${"Open board pack — " + (p.cut_label || "All peers")}
              onClick=${() => nav("/boardpack/" + p.pack_id)}
              onKeyDown=${e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); nav("/boardpack/" + p.pack_id); } }}>
              <b>${p.cut_label || "All peers"}</b>${p.collection_window ? html` <span class="caption">· ${p.collection_window}</span>` : ""}
              <div class="caption">${new Date(p.created_at + "Z").toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}${p.created_by ? " · " + p.created_by : ""}${p.ai ? " · AI narrative" : ""}</div>
            </div>
            <div class="row" style=${{ gap: "var(--s2)", flex: "none" }}>
              <button class="btn small" onClick=${() => nav("/boardpack/" + p.pack_id)}>Open</button>
              ${me.user.role === "admin" && html`<button class="btn small quiet" onClick=${() => del(p)}>Delete</button>`}
            </div>
          </div>`)}
      </div>`}
    </div>`;
};
