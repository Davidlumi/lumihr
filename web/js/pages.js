/* Dashboard pages: Executive overview, Superpower detail, My view, My data, Methodology. */
/* global html, useState, useEffect, useMemo, api, fmtValue, pLabel, Chip, NBadge, Term, Spinner,
   BenchmarkCard, QuartileDots, fmtGBPCompact, EmptyState, nav */

const SUPERPOWERS = ["Reward", "Processes", "Wellbeing", "Growth", "Capability",
  "Inclusivity", "Attract", "Leadership", "Purpose", "Change"];
window.SUPERPOWERS = SUPERPOWERS;
window.SECTION_ORDER = { "Pay": 1, "Benefits": 2, "Incentives": 3, "Transparency": 4, "Progression": 5 };
window.secOrder = sec => (window.SECTION_ORDER_LIVE && window.SECTION_ORDER_LIVE[sec]) || window.SECTION_ORDER[sec] || 99;
/* SpIcon: the one consistent superpower glyph (line-icon family from icons.js) */
window.SpIcon = ({ sp, size = 15 }) => html`<${Icon} name=${SP_ICON[sp] || "target"} size=${size} />`;

// ------------------------------------------------------------ overview -----
window.OverviewPage = function ({ me, cut, cuts, prefs, onPref, onPin, pinnedIds }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    setData(null); setErr(null);
    api("/api/overview?" + cutQS(cut)).then(setData).catch(e => setErr(e.message));
  }, [cutKeyOf(cut)]);
  if (err) return html`<${EmptyState} title="Couldn't load the overview" body=${err} />`;
  if (!data) return html`
    <div>
      <div class="skel" style=${{ height: "30px", width: "320px", marginBottom: "10px" }}></div>
      <div class="skel" style=${{ height: "20px", width: "480px", marginBottom: "16px" }}></div>
      <div class="skel" style=${{ height: "180px", marginBottom: "16px", borderRadius: "var(--radius)" }}></div>
      <${SkeletonGrid} count=${3} />
    </div>`;
  const h = data.headline;
  const pctAbove = h.comparable_metrics ? Math.round(100 * h.above_median / h.comparable_metrics) : 0;
  return html`
    <div>
      <div class="hero">
        <div>
          <h1 class="display-title">${data.org.name}</h1>
          <div class="row" style=${{ marginTop: "6px" }}>
            <${Chip} kind="accent">${data.org.industry || "Unclassified"}<//>
            <${Chip}>${data.org.fte_band ? data.org.fte_band + " FTE" : "Size not declared"}<//>
            <${Chip}>${data.org.hq_region || "Region not declared"}<//>
            <${Chip} title="Organisations contributing to this benchmark"><${Term} word="peer group">peer group<//>: ${data.peer_pool.responding_orgs} organisations<//>
            <${Chip}>${data.snapshot.window}<//>
            ${data.synthetic_pool && html`<span class="chip warn hastip" style=${{ position: "relative", cursor: "help" }}>
              Illustrative sample data
              <span class="tip">The current peer pool is realistic but synthetic seed data, generated to behave like a UK benchmark while real member submissions build up. It must not be read as real benchmark data.</span>
            </span>`}
            ${cut.dim !== "all" && html`<${Chip} kind="accent">filter: ${cutLabelOf(cut, cuts)}<//>`}
          </div>
        </div>
      </div>

      <div class="card banner" style=${{ marginBottom: "var(--s4)" }}>
        <div style=${{ flex: "1.7 1 320px", minWidth: "300px" }}>
          <div class="section-title" style=${{ marginBottom: "4px" }}>
            You're above the peer <${Term} word="median">median<//> on
            <span style=${{ color: "var(--plum-deep)" }}> ${h.above_median} of ${h.comparable_metrics} </span>
            ${" "}<span class="hastip" style=${{ position: "relative", cursor: "help", borderBottom: "1px dotted var(--ink-faint)" }}>comparable metrics<span class="tip">Counted wherever your answer and at least 5 peers' answers can be compared, adjusted for whether higher or lower is the good direction. Anything based on fewer than 5 organisations is left out.</span></span>
          </div>
          <div class="caption">${h.below_median} sit below the median and ${h.broadly_in_line} are broadly in line — based on ${cutLabelOf(cut, cuts)}.</div>
          <div style=${{ marginTop: "16px" }}>
            <div class="pstrip"><div class="mark" style=${{ left: `calc(${Math.max(2, Math.min(98, pctAbove))}% - 2px)` }}></div></div>
            <div class="caption" style=${{ marginTop: "4px" }}>That's <b>${pctAbove}%</b> of your comparable metrics at or above the peer median.</div>
          </div>
        </div>
        <${OpportunityTile} opp=${data.opportunity} />
        <${TrajectoryTile} movement=${data.movement} />
      </div>

      <div class="grid2" style=${{ margin: "var(--s6) 0 var(--s4)" }}>
        <div>
          <h2 class="section-title">Where you lead</h2>
          ${data.callouts.strengths.length ? data.callouts.strengths.map((t, i) => html`
            <div key=${i} class="callout good" onClick=${() => jumpToItem(data.callouts.strength_items[i])} style=${{ cursor: "pointer" }}>${t}</div>`) :
          html`<${EmptyState} title="No clear strengths yet" body="Once more of your data is comparable, your strongest positions appear here." />`}
        </div>
        <div>
          <h2 class="section-title">Biggest gaps to peers</h2>
          ${data.callouts.gaps.length ? data.callouts.gaps.map((t, i) => html`
            <div key=${i} class="callout bad" onClick=${() => jumpToItem(data.callouts.gap_items[i])} style=${{ cursor: "pointer" }}>${t}</div>`) :
          html`<${EmptyState} title="No comparable gaps" body="Nothing stands out below the peer median in this peer group." />`}
        </div>
      </div>

      ${window.SCOPE && window.SCOPE.focused ? html`
        <h2 class="section-title">Your position by section</h2>
        <div class="sp-grid">
          ${Object.entries(h.by_section || {}).sort((a, b) => secOrder(a[0]) - secOrder(b[0])).map(([sec, c]) => html`
            <div key=${sec} class="card sp-card" onClick=${() => nav("/superpower/Reward?sub=" + encodeURIComponent(sec))}>
              <div class="row spread" style=${{ marginBottom: "6px" }}>
                <span class="sp-name">${sec}</span>
                <span class="caption">${c.available} metrics</span>
              </div>
              ${c.available ? html`
                <div class="row" style=${{ gap: "8px", marginBottom: "8px" }}>
                  <span class="chip good">▲ ${c.above}</span>
                  <span class="chip bad">▼ ${c.below}</span>
                  ${c.inline ? html`<span class="chip">= ${c.inline}</span>` : null}
                </div>
                <${QuartileDots} quartiles=${c.quartiles} />` :
              html`<div class="caption">No comparable metrics in this peer group yet.</div>`}
            </div>`)}
        </div>` : html`
        <h2 class="section-title">Your position by area</h2>
        <div class="sp-grid">
          ${(window.SCOPE ? window.SCOPE.superpowers : SUPERPOWERS).map(sp => {
            const c = h.by_superpower[sp] || { available: 0, above: 0, below: 0, inline: 0, quartiles: [0, 0, 0, 0] };
            return html`
            <div key=${sp} class="card sp-card" onClick=${() => nav("/superpower/" + sp)}>
              <div class="row spread" style=${{ marginBottom: "6px" }}>
                <span class="sp-name"><${SpIcon} sp=${sp} /> ${sp}</span>
                <span class="caption">${c.available} metrics</span>
              </div>
              ${c.available ? html`
                <div class="row" style=${{ gap: "8px", marginBottom: "8px" }}>
                  <span class="chip good">▲ ${c.above}</span>
                  <span class="chip bad">▼ ${c.below}</span>
                  ${c.inline ? html`<span class="chip">= ${c.inline}</span>` : null}
                </div>
                <${QuartileDots} quartiles=${c.quartiles} />` :
              html`<div class="caption">No comparable metrics in this peer group yet.</div>`}
            </div>`;
          })}
        </div>`}
    </div>`;
};

function jumpToItem(item) { if (item) nav("/superpower/" + item.superpower + "?focus=" + item.question_id); }

window.OpportunityTile = function ({ opp }) {
  if (!opp) return null;
  const total = opp.total_savings_to_p50_gbp > 0 ? opp.total_savings_to_p50_gbp : opp.total_investment_to_p50_gbp;
  return html`
    <div class="opp-hero">
      <div class="eyebrow">Total identified opportunity</div>
      ${opp.fte_known ? html`
        <div>
          <div class="metric-value lg" style=${{ color: "var(--plum)" }}>${fmtGBPCompact(total)}<span class="unit">/yr</span></div>
          <div class="caption">${opp.total_savings_to_p50_gbp > 0 ?
            html`potential savings if you matched the peer median${opp.total_investment_to_p50_gbp ? html` — plus ${fmtGBPCompact(opp.total_investment_to_p50_gbp)}/yr to close benefit gaps` : ""}` :
            opp.total_investment_to_p50_gbp > 0 ? "what it would take to close your benefit gaps to the peer median" : "no gaps to the peer median identified"}</div>
        </div>
        <div style=${{ marginTop: "var(--s2)" }}>
          ${opp.items.map(i => html`
            <div key=${i.question_id} class="opp-row">
              <a href=${"#/metric/" + i.question_id}>${i.label}</a>
              <b>${fmtGBPCompact(i.to_p50_gbp)}/yr <span class="caption" style=${{ fontWeight: 400 }}>${i.direction === "saving" ? "saving" : "to close"}</span></b>
            </div>`)}
        </div>
        <div class="caption" style=${{ marginTop: "auto" }}><${Term} word="indicative">Indicative<//> — based on assumptions you can change in <a href="#/settings">Settings</a>.</div>` :
      html`<div class="caption" style=${{ marginTop: "6px" }}>Declare your FTE band in <a href="#/submission">your submission</a> to size the £ opportunity of closing gaps to the peer median.</div>`}
    </div>`;
};

window.TrajectoryTile = function ({ movement }) {
  return html`
    <div style=${{ flex: "1 1 190px", minWidth: "190px", borderLeft: "1px solid var(--border)", paddingLeft: "var(--s5)" }}>
      <div class="caption" style=${{ fontWeight: 650, textTransform: "uppercase", letterSpacing: ".06em" }}>Trajectory</div>
      <svg viewBox="0 0 170 44" style=${{ width: "170px", display: "block", margin: "6px 0" }}>
        <polyline points="4,30 40,30" stroke="var(--you)" stroke-width="2.5" fill="none" stroke-linecap="round"/>
        <circle cx="40" cy="30" r="4" fill="var(--you)"/>
        <polyline points="40,30 80,24 120,20 160,14" stroke="var(--border)" stroke-width="2" stroke-dasharray="3 4" fill="none"/>
        <circle cx="160" cy="14" r="3.5" fill="none" stroke="var(--border)" stroke-width="1.5"/>
      </svg>
      <div class="caption">${movement.message}</div>
    </div>`;
};

// ----------------------------------------------------- superpower detail ---
window.SuperpowerPage = function ({ sp, cut, cuts, prefs, onPref, onPin, pinnedIds, me, focusQ }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [cat, setCat] = useState("");
  const [tier, setTier] = useState("");
  useEffect(() => {
    setData(null); setErr(null);
    api(`/api/benchmarks/${encodeURIComponent(sp)}?` + cutQS(cut)).then(setData).catch(e => setErr(e.message));
  }, [sp, cutKeyOf(cut)]);
  useEffect(() => {
    if (data && focusQ) {
      const el = document.getElementById("q-" + focusQ);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [data, focusQ]);
  if (err) return html`<${EmptyState} title="Couldn't load this section" body=${err} />`;
  if (!data) return html`
    <div>
      <div class="page-head">
        <div class="titleblock">
          <div class="sp-glyph"><${SpIcon} sp=${sp} size=${20} /></div>
          <div><h1 class="display-title">${sp}</h1><div class="caption meta">Loading benchmarks…</div></div>
        </div>
      </div>
      <${SkeletonGrid} count=${6} />
    </div>`;
  let cards = data.cards;
  if (cat) cards = cards.filter(c => c.category === cat);
  if (tier) cards = cards.filter(c => (tier === "Core" ? c.tier === "Core" : c.tier !== "Core"));
  const bySub = [];
  for (const c of cards) {
    let g = bySub.find(g => g.sub === (c.subpower || "General"));
    if (!g) { g = { sub: c.subpower || "General", order: c.sub_power_order || 999, cards: [] }; bySub.push(g); }
    g.cards.push(c);
  }
  bySub.sort((a, b) => a.order - b.order);
  return html`
    <div>
      <div class="page-head">
        <div class="titleblock">
          <div class="sp-glyph"><${SpIcon} sp=${sp} size=${20} /></div>
          <div>
            <h1 class="display-title">${sp}</h1>
            <div class="caption meta">${data.cards.length} benchmarks · peer group: ${cutLabelOf(cut, cuts)}</div>
          </div>
        </div>
        <div class="controls" style=${{ alignItems: "flex-start" }}>
          <div class="ctlgroup">
            <select class="ctl" value=${cat} onChange=${e => setCat(e.target.value)}>
              <option value="">All question types</option>
              <option value="metric">Metrics</option><option value="practice">Practices</option>
              <option value="policy">Policies</option><option value="benefit">Benefits</option>
            </select>
            <div class="hint">Show only one kind of question.</div>
          </div>
          <div class="ctlgroup">
            <select class="ctl" value=${tier} onChange=${e => setTier(e.target.value)}>
              <option value="">All tiers</option><option value="Core">Core</option><option value="plus">Enhanced+</option>
            </select>
            <div class="hint">Filter by membership tier.</div>
          </div>
        </div>
      </div>
      ${cards.length === 0 && html`<${EmptyState} title="Nothing matches these filters"
        body="Try clearing the category or tier filter." action=${html`<button class="btn small" onClick=${() => { setCat(""); setTier(""); }}>Clear filters</button>`} />`}
      ${bySub.map(g => html`
        <div key=${g.sub} style=${{ marginBottom: "var(--s5)" }}>
          <h2 class="section-title">${g.sub}</h2>
          <div class="bench-grid">
            ${g.cards.map(c => html`
              <div key=${c.id} id=${"q-" + c.id}>
                <${BenchmarkCard} card=${c} prefs=${prefs} onPref=${onPref} onPin=${onPin}
                  pinned=${pinnedIds.has(c.id)} cuts=${cuts} globalCut=${cutKeyOf(cut)}
                  window=${me.peer_pool && me.peer_pool.collection_window} highlight=${focusQ === c.id} />
              </div>`)}
          </div>
        </div>`)}
    </div>`;
};

// ----------------------------------------------------------- my view -------
window.MyViewPage = function ({ me, cut, cuts, prefs, onPref }) {
  const [layout, setLayout] = useState(null);
  const [source, setSource] = useState(null);
  const [cards, setCards] = useState({});
  const [drag, setDrag] = useState(null);
  const [saved, setSaved] = useState(null);
  useEffect(() => { api("/api/myview").then(d => { setLayout(d.layout); setSource(d.source); }); }, []);
  useEffect(() => {
    if (!layout) return;
    layout.forEach(slot => {
      const key = slotKey(slot);
      if (cards[key]) return;
      const c = slot.cut || cut;
      api(`/api/benchmark/${slot.question_id}?` + cutQS(c))
        .then(d => setCards(prev => ({ ...prev, [key]: d })))
        .catch(() => setCards(prev => ({ ...prev, [key]: { error: true } })));
    });
  }, [layout, cutKeyOf(cut)]);
  if (!layout) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;

  const persist = async (next) => {
    setLayout(next);
    await api("/api/myview", { method: "PUT", body: { layout: next } });
  };
  const remove = qid => persist(layout.filter(s => s.question_id !== qid));
  const resize = (qid, size) => persist(layout.map(s => s.question_id === qid ? { ...s, size } : s));
  const onDrop = idx => {
    if (drag === null || drag === idx) { setDrag(null); return; }
    const next = [...layout];
    const [moved] = next.splice(drag, 1);
    next.splice(idx, 0, moved);
    setDrag(null);
    persist(next);
  };
  const saveDefault = async () => {
    await api("/api/myview/save-default", { method: "POST", body: { layout } });
    setSaved("Saved as your organisation's default view");
    setTimeout(() => setSaved(null), 2500);
  };
  return html`
    <div>
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <h1 class="display-title">My view</h1>
          <div class="caption" style=${{ marginTop: "4px" }}>
            ${source === "starter" ? "A starter view of your 8 biggest gaps and 4 biggest strengths — pin any card from anywhere in lumi (☆), drag to reorder, resize, or remove." :
            source === "org_default" ? "Your organisation's default view — make it your own by pinning, dragging and resizing." :
            "Your pinned view. Drag to reorder; cards keep their own peer-group and chart settings."}
          </div>
        </div>
        <div class="row">
          ${saved && html`<${Chip} kind="good">${saved}<//>`}
          ${me.user.role === "admin" && html`<button class="btn" onClick=${saveDefault} title="New team members will inherit this layout">Save as team default</button>`}
        </div>
      </div>
      ${layout.length === 0 && html`<${EmptyState} icon="star" title="Nothing pinned yet"
        body="Use the star on any benchmark card to pin it here."
        action=${html`<button class="btn small" onClick=${() => nav("/overview")}>Back to overview</button>`} />`}
      <div class="bench-grid">
        ${layout.map((slot, i) => {
          const c = cards[slotKey(slot)];
          return html`
          <div key=${slotKey(slot)} draggable="true" class=${drag === i ? "dragging" : ""}
            onDragStart=${() => setDrag(i)} onDragOver=${e => e.preventDefault()} onDrop=${() => onDrop(i)}
            style=${slot.size === 2 ? { gridColumn: "span 2" } : null}>
            ${!c ? html`<${SkeletonCard} />` :
            c.error ? html`<div class="card bench-card"><${EmptyState} title="Couldn't load this card" /></div>` :
            html`<div style=${{ position: "relative" }}>
              <${BenchmarkCard} card=${c} prefs=${prefs} onPref=${onPref} size=${slot.size}
                onPin=${() => remove(slot.question_id)} pinned=${true} cuts=${cuts} globalCut=${cutKeyOf(cut)} />
              <div class="no-print" style=${{ position: "absolute", bottom: "8px", right: "10px", display: "flex", gap: "2px" }}>
                <button class="iconbtn" title="Card width" onClick=${() => resize(slot.question_id, slot.size === 2 ? 1 : 2)}>${slot.size === 2 ? "1×" : "2×"}</button>
                <span class="iconbtn" title="Drag to reorder" style=${{ cursor: "grab" }}>⠿</span>
              </div>
            </div>`}
          </div>`;
        })}
      </div>
    </div>`;
};
function slotKey(slot) { return slot.question_id + "|" + (slot.row_id || "") + "|" + JSON.stringify(slot.cut || {}); }

// ----------------------------------------------------------- my data -------
window.MyDataPage = function () {
  const [data, setData] = useState(null);
  const [qstr, setQ] = useState("");
  useEffect(() => { api("/api/my-data").then(setData); }, []);
  if (!data) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  const ql = qstr.toLowerCase();
  const rows = data.rows.filter(r => !ql || (r.title + " " + r.question + " " + (r.matrix_row || "") + " " + r.value).toLowerCase().includes(ql));
  const bySp = [];
  for (const r of rows) {
    let g = bySp.find(g => g.sp === r.superpower);
    if (!g) { g = { sp: r.superpower, rows: [] }; bySp.push(g); }
    g.rows.push(r);
  }
  return html`
    <div>
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <h1 class="display-title">My data</h1>
          <div class="caption" style=${{ marginTop: "4px" }}>Everything your organisation has submitted (${data.rows.length} answers). Only your team can see this.</div>
        </div>
        <input class="ctl" placeholder="Search your answers…" value=${qstr} onInput=${e => setQ(e.target.value)} />
      </div>
      ${rows.length === 0 && html`<${EmptyState} title="No answers match" body="Try a different search term." />`}
      ${bySp.map(g => html`
        <div key=${g.sp} class="card" style=${{ marginBottom: "var(--s4)", padding: "var(--s4)" }}>
          <h2 class="section-title" style=${{ display: "flex", alignItems: "center", gap: "8px" }}><${SpIcon} sp=${g.sp} /> ${g.sp} <span class="caption">(${g.rows.length})</span></h2>
          <table class="data">
            <thead><tr><th>Benchmark</th><th>Level / row</th><th class="num">Your answer</th><th>Tier</th></tr></thead>
            <tbody>
              ${g.rows.map((r, i) => html`
                <tr key=${i}>
                  <td title=${r.question}>${r.title}</td>
                  <td>${r.matrix_row || "—"}</td>
                  <td class="num"><b>${formatAnswer(r)}</b></td>
                  <td><span class="chip">${r.tier}</span></td>
                </tr>`)}
            </tbody>
          </table>
        </div>`)}
    </div>`;
};
function formatAnswer(r) {
  if (r.type === "numeric" || r.type === "matrix") {
    const f = parseFloat(String(r.value).replace(/[£,%]/g, ""));
    if (!isNaN(f)) return fmtValue(f, r.unit);
  }
  return r.value;
}

// -------------------------------------------------------- methodology ------
window.MethodologyPage = function () {
  const [m, setM] = useState(null);
  useEffect(() => { api("/api/methodology").then(setM); }, []);
  if (!m) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  const industries = Object.keys(m.composition);
  return html`
    <div style=${{ maxWidth: "880px" }}>
      <h1 class="display-title">Methodology</h1>
      <p class="caption">Benchmark snapshot dated ${m.snapshot_date} · collection window ${m.collection_window} · methodology v1</p>

      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Who you're compared with</h2>
        ${m.synthetic_pool && html`
          <div style=${{ background: "var(--neutral-perf-tint)", borderRadius: "var(--radius-sm)", padding: "var(--s3) var(--s4)", marginBottom: "var(--s3)", fontSize: "var(--fs-body)" }}>
            <b>Illustrative sample data.</b> The current benchmark pool is <b>synthetic seed data</b>: 220 simulated
            organisations whose answers were generated from published UK HR and reward norms and each organisation's
            firmographic profile, pending real member submissions. It is designed to behave believably for
            demonstration and launch seeding — it is not real member data and must not be cited as a market statistic.
          </div>`}
        <p>The peer group contains <b>${m.peer_pool.responding_orgs} UK organisations</b> that have completed a lumi benchmark submission.
        ${m.peer_pool.classified_orgs} carry full firmographic profiles (sector, size, region, ownership) and appear in filtered peer
        groups; ${m.unclassified_count} are awaiting classification, stay in the "All peers" group only, and are shown as "Unclassified".</p>
        <table class="data" style=${{ marginTop: "10px" }}>
          <thead><tr><th>Sector</th>${m.fte_bands.map(b => html`<th key=${b} class="num">${b}</th>`)}<th class="num">Total</th></tr></thead>
          <tbody>
            ${industries.map(ind => {
              const row = m.composition[ind];
              const tot = Object.values(row).reduce((a, b) => a + b, 0);
              return html`<tr key=${ind}><td>${ind}</td>
                ${m.fte_bands.map(b => html`<td key=${b} class="num">${row[b] || "·"}</td>`)}
                <td class="num"><b>${tot}</b></td></tr>`;
            })}
          </tbody>
        </table>
      </div>

      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">How the numbers are calculated</h2>
        <p><b>Percentiles.</b> P10, P25, P50 (median), P75 and P90 are calculated with linear interpolation across all
        valid peer answers — the same method used by the main survey houses. We benchmark on medians rather than
        averages so a single unusual organisation cannot skew a figure.</p>
        <p><b>Small-sample protection.</b> Any figure that would rest on fewer than ${m.suppression_floor} organisations is not shown.
        You will see "not enough organisations to show this safely" instead. This rule applies to every peer group —
        including bespoke groups such as Peer Twin — and is enforced in one place in the calculation engine.</p>
        <p><b>Multiple-choice questions.</b> Distributions show the share of answering organisations choosing each option.
        For "select all that apply" questions, the denominator is the number of organisations that answered the question
        — so percentages can sum to more than 100.</p>
        <p><b>Favourable vs peers.</b> Each question carries a polarity: higher is better (e.g. offer acceptance rate),
        lower is better (e.g. regretted attrition), or neutral (e.g. salary increase budget, where "better" depends on
        strategy). Green/amber/red colouring is polarity-adjusted and is never applied to neutral metrics.</p>
        <p><b>Practice adoption.</b> Practice and policy questions are scored 0–100 using lumi's scoring configuration.
        We treat a practice as "in place" when an organisation's answer scores 50 or more on that question's scale; peer
        adoption rates use the same rule.</p>
        <p><b>Your percentile.</b> Your P-number is the share of peer organisations whose value sits below yours
        (ties counted half), so P63 means you are higher than about 6 in 10 peers.</p>
      </div>

      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Where the data comes from</h2>
        <p>This snapshot ingested ${m.reconciliation.files} member submissions (${(m.reconciliation.answer_rows || 0).toLocaleString("en-GB")} answers).
        ${m.reconciliation.matched_orgs} organisations were matched to the lumi member registry by normalised company name;
        ${m.reconciliation.file_only_orgs} submissions without a registry profile are retained in "All peers" as Unclassified;
        ${m.reconciliation.registry_only_orgs} registry members have not yet submitted and are excluded from every aggregate.
        Near-miss name matches are flagged for human review and never joined automatically. New members declare their own
        firmographics at sign-up, which removes this reconciliation step for future windows.</p>
        <p><b>Snapshots.</b> Every collection window is stored as a separate snapshot; submissions are versioned and never
        overwrite history. From your second window onwards, movement ("vs last period") appears on each benchmark card and
        the trajectory module.</p>
        <p><b>£ modelling assumptions.</b> Opportunity figures use FTE band midpoints
        (${Object.entries(m.assumptions.fte_band_midpoints || {}).map(([k, v]) => `${k}: ${v.toLocaleString("en-GB")}`).join("; ")}),
        a UK all-sector median salary of £${(m.assumptions.median_salary_gbp || 0).toLocaleString("en-GB")} (editable in Settings),
        a cost per leaver of ${m.assumptions.cost_per_leaver_pct_salary}% of salary and an agency premium of
        ${m.assumptions.agency_premium_pct}%. They are assumptions, clearly labelled, and every £ figure is indicative.</p>
      </div>

      <div class="card" style=${{ padding: "var(--s5)", marginBottom: "var(--s4)" }}>
        <h2 class="section-title">Glossary</h2>
        ${Object.entries(GLOSSARY).map(([k, v]) => html`
          <p key=${k} style=${{ margin: "6px 0" }}><b style=${{ textTransform: "capitalize" }}>${k}.</b> ${v}</p>`)}
        <p style=${{ margin: "6px 0" }}><b>Peer Twin.</b> A bespoke peer group of the organisations most similar to yours across
        industry, size, ownership and workforce shape. The group is recalculated as the membership grows; member names are never shown.</p>
        <p style=${{ margin: "6px 0" }}><b>Polarity.</b> Whether a higher value is favourable, unfavourable, or neither, for colour-coding your position.</p>
      </div>
    </div>`;
};

// shared helpers
window.cutQS = function (cut) {
  let qs = "cut=" + encodeURIComponent(cut.dim || "all");
  if (cut.value) qs += "&cut_value=" + encodeURIComponent(cut.value);
  return qs;
};
window.cutKeyOf = cut => (cut.dim || "all") + "::" + (cut.value || "");
window.cutLabelOf = function (cut, cuts) {
  if (cut.dim === "industry") return cut.value || (cuts && cuts.org_industry) || "Your industry";
  if (cut.dim === "fte_band") return (cut.value || (cuts && cuts.org_fte_band) || "Your size") + " FTE";
  if (cut.dim === "twin") return "Organisations like you";
  return "All peers";
};
