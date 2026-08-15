// ============================ REWARD DOCUMENTS ================================
// The two reward sections used to END on a screen — a stack of cards you scrolled
// and then had nothing to hand anyone. David 2026-08-16: "create a Willis Towers
// Watson grade experience for their reward strategy and reward plan — the output
// should be a downloadable report or strategy document, with commentary."
//
// So both now terminate in a real A4 artefact, laid out on the SAME sheet chrome as
// the board pack (.pack-page, running footer, page numbers, Private & confidential)
// so the three documents read as one family. One click opens Save-as-PDF.
//
// Nothing here computes: the deterministic substance comes from /api/strategy and
// /api/strategy/alignment, and the prose from three generators that already exist and
// already validate — strategy commentary, strategy diagnosis, action plan. Each one
// carries its own deterministic floor, so a model outage costs polish, never a page.

const RRD = {
  strategy: {
    eyebrow: "REWARD STRATEGY",
    title: "Total Reward Strategy",
    file: "Reward strategy",
    lead: "What we intend our reward to do, and how it is positioned.",
  },
  plan: {
    eyebrow: "REWARD PLAN",
    title: "Reward Position & Plan",
    file: "Reward plan",
    lead: "Where the package sits against that intent, the gaps it opens, and the plan to close them.",
  },
};

// A model part that came back on the deterministic floor still reads as prose, so the
// document never says which is which inline — the provenance line on the last page does.
function rrProse(s) { return (s || "").trim(); }

function RrSheet({ page, total, foot, prov, children, cover }) {
  return html`
    <div class=${"pack-page rr-sheet" + (cover ? " rr-cover" : "")}>
      <div class="rr-body">${children}</div>
      <div class="pack-footer-wrap">
        ${prov ? html`<div class="pack-provline">${prov}</div>` : null}
        <div class="pack-footer">
          <span>${foot}</span>
          <span>Private ${"&"} confidential</span>
          <span class="pack-pageno">lumi · ${page} of ${total}</span>
        </div>
      </div>
    </div>`;
}

function RrH({ n, children, sub }) {
  return html`
    <div class="rr-h">
      ${n ? html`<span class="rr-h-n">${n}</span>` : null}
      <h2 class="rr-h-t">${children}</h2>
      ${sub ? html`<p class="rr-h-s">${sub}</p>` : null}
    </div>`;
}

const RR_ALIGN_WORD = { on_target: "On strategy", ahead: "Above strategy", behind: "Below strategy" };
const RR_POS_WORD = { below: "below market", at: "on market", above: "above market" };
const RR_STANCE_WORD = { lag: "below market", match: "on market", lead: "above market" };

window.RewardReportPage = function ({ kind, me }) {
  const K = RRD[kind] || RRD.strategy;
  const [st, setSt] = useState(null);         // /api/strategy
  const [al, setAl] = useState(null);         // /api/strategy/alignment
  const [cm, setCm] = useState(null);         // AI: reading / tensions / watch
  const [dg, setDg] = useState(null);         // AI: summary / findings   (plan only)
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const orgName = (me.org && me.org.name) || "Your organisation";

  const loadNarrative = (force) => {
    const body = force ? { force: true } : {};
    const jobs = [api("/api/strategy/commentary", { method: "POST", body }).then(setCm).catch(() => setCm(false))];
    if (kind === "plan") {
      jobs.push(api("/api/strategy-diagnosis", { method: "POST", body }).then(r => setDg(r && r.ok === false ? false : r)).catch(() => setDg(false)));
    }
    return Promise.all(jobs);
  };
  useEffect(() => {
    Promise.all([api("/api/strategy"), api("/api/strategy/alignment")])
      .then(([s, a]) => { setSt(s); setAl(a); })
      .catch(e => setErr(e.message));
    loadNarrative(false);
  }, [kind]);

  if (err) return html`<${EmptyState} tone="error" icon="compass" title="Couldn't build the document"
    body=${err + " — nothing is lost."}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Try again</button>`} />`;
  if (!st || !al) return html`<${PageLoading} />`;
  if (!st.completed_at) return html`<${EmptyState} icon="compass" title="Set your reward strategy first"
    body="This document is written from your stated strategy — so it starts there."
    action=${html`<button class="btn small primary" onClick=${() => nav("/strategy")}>Go to Reward strategy</button>`} />`;

  const doc = st.document || {};
  const strat = st.strategy || {};
  const ver = st.version || null;
  const commitments = al.commitments || [];
  const gaps = commitments.filter(c => c.status === "behind_intent" || c.status === "contradicted");
  const holding = commitments.filter(c => c.status === "evidenced");
  const unevid = commitments.filter(c => c.status === "not_evidenced");
  const domains = (al.domains || []);
  const plan = al.plan;
  const optsFor = (id) => (al.options || []).find(o => o.commitment_id === id);
  const today = fmtDate();
  const cutLabel = al.cut_label || "your peer group";

  // gaps grouped by area, exactly as the working screen groups them
  const groups = [];
  gaps.forEach(c => {
    let g = groups.find(x => x.cat === c.category);
    if (!g) { g = { cat: c.category, items: [] }; groups.push(g); }
    g.items.push(c);
  });

  const regen = async () => {
    setBusy(true);
    setCm(null); if (kind === "plan") setDg(null);
    try { await loadNarrative(true); toast("Commentary rewritten from your current position."); }
    catch (e) { toast("Couldn't rewrite the commentary.", "error"); }
    setBusy(false);
  };
  const doPrint = () => {
    const t = document.title;
    document.title = "lumi — " + orgName + " — " + K.file + " — " + today;
    window.print();
    document.title = t;
  };

  const foot = "Generated " + today + " · Peer group: " + cutLabel
    + (ver ? " · Version " + ver.version : " · Draft");
  const aiWaiting = cm === null || (kind === "plan" && dg === null);
  const sources = [];
  if (cm && cm.source) sources.push("commentary " + cm.source);
  if (dg && dg.source) sources.push("findings " + dg.source);
  if (plan && plan.source) sources.push("plan " + plan.source);

  // ---- the page list, built per kind so numbering is derived, never hand-counted ----
  const pages = [];
  const P = (title, body, opts) => pages.push({ title, body, ...(opts || {}) });
  // A section longer than one sheet would flow onto a continuation page at print time,
  // and then the "N of M" in the footer disagrees with the paper in your hand. Long runs
  // are chunked to a sheet's worth instead, so the count is derived from real sheets.
  // Chunked by WEIGHT, not by count: a gap area carrying a four-lever options table is
  // three times the height of one carrying a coverage note, so a fixed items-per-sheet
  // still overran. Budget is in rough "block" units against a sheet's usable body.
  const chunk = (arr, weigh, budget) => {
    const out = []; let cur = [], w = 0;
    arr.forEach(it => {
      const iw = Math.max(1, weigh(it));
      if (cur.length && w + iw > budget) { out.push(cur); cur = []; w = 0; }
      cur.push(it); w += iw;
    });
    if (cur.length) out.push(cur);
    return out.length ? out : [[]];
  };
  const Prun = (title, body, arr, weigh, budget) => {
    let seen = 0;                              // running offset so a split <ol> keeps numbering
    chunk(arr, weigh, budget).forEach((items, i, all) => {
      P(i === 0 ? title : title + " (cont.)", body, { items, part: i, parts: all.length, start: seen + 1 });
      seen += items.length;
    });
  };

  P(null, "cover", { cover: true });

  // §1 executive summary — the AI opening, on its own page with the contents
  P("Executive summary", "exec");

  if (kind === "strategy") {
    P("Strategic intent", "intent");
    P("How we position reward", "dials");
    if ((doc.principles || []).length || doc.comparator_cut != null
        || ((doc.constraints || {}).selected || []).length || (doc.constraints || {}).notes) P("Principles, peers and constraints", "prin");
    if ((doc.population_targets || []).length) P("Position by employee population", "pops");
    P("Tensions and what to watch", "tension");
    P("Governance and approval", "gov");
  } else {
    P("Position against intent", "position");
    if (dg && (dg.parts || {}).findings && dg.parts.findings.length)
      Prun("Findings", "findings", dg.parts.findings, () => 2, 6);
    if (groups.length)
      Prun("The gaps, by area", "gapsp", groups,
           g => 1 + g.items.reduce((n, c) => n + ((optsFor(c.id) || {}).levers || []).length + 1, 0), 5);
    if (plan && (plan.actions || []).length)
      Prun("The plan", "planp", plan.actions, () => 2, 7);
    else
      P("The plan", "planp", { items: [], part: 0, parts: 1 });
  }
  P("Method and basis", "method");
  const TOTAL = pages.length;

  // ------------------------------------------------------------------ bodies ----
  const Body = ({ kindOf, items, part, parts, start }) => {
    const first = !part;                       // only sheet 1 of a run carries the intro
    const contd = parts > 1 ? " (" + (part + 1) + " of " + parts + ")" : "";
    if (kindOf === "cover") return html`
      <div class="rr-cover-in">
        ${window.LUMI_LOGO_SVG
          ? html`<div class="bp-logo" dangerouslySetInnerHTML=${{ __html: window.LUMI_LOGO_SVG }}></div>`
          : html`<div class="rr-wordmark">lumi</div>`}
        <div class="rr-eyebrow">${K.eyebrow}</div>
        <div class="rr-accent"></div>
        <h1 class="rr-title">${orgName}</h1>
        <div class="rr-subtitle">${K.title}</div>
        <p class="rr-lead">${K.lead}</p>
        <div class="rr-cover-meta">
          <div><span>Prepared</span>${today}</div>
          <div><span>Peer group</span>${cutLabel}</div>
          ${al.objective ? html`<div><span>Objective</span>${al.objective}</div>` : null}
          <div><span>Status</span>${ver ? "Version " + ver.version + ", approved" + (ver.approval_date ? " " + ver.approval_date : "") : "Draft — not yet approved"}</div>
        </div>
      </div>`;

    if (kindOf === "exec") return html`
      <${RrH} n="01">Executive summary<//>
      ${aiWaiting ? html`<p class="rr-p rr-muted">Writing the commentary…</p>`
        : html`<p class="rr-lede">${rrProse(
            (kind === "plan" ? (dg && dg.parts && dg.parts.summary) : null)
            || (cm && cm.parts && cm.parts.reading) || "")}</p>`}
      <div class="rr-stats">
        <div><b>${domains.length}</b><span>areas benchmarked</span></div>
        <div><b>${gaps.length}</b><span>${gaps.length === 1 ? "gap to close" : "gaps to close"}</span></div>
        <div><b>${holding.length}</b><span>${holding.length === 1 ? "commitment holding" : "commitments holding"}</span></div>
      </div>
      <div class="rr-toc">
        <div class="rr-toc-h">Contents</div>
        ${pages.filter(p => p.title).map((p, i) => html`
          <div key=${p.title} class="rr-toc-row"><span>${p.title}</span><i>${i + 2}</i></div>`)}
      </div>`;

    if (kindOf === "intent") {
      const stance = sdStance(strat, orgName);
      return html`
        <${RrH} n="02" sub="The strategy as stated by the organisation. lumi reads the benchmark through it — a position below or above market here is a choice, not a verdict.">Strategic intent<//>
        ${stance.length ? stance.map((s, i) => html`<p key=${i} class=${"rr-p" + (i === 0 ? " rr-lede" : "")}>${s}</p>`)
          : html`<p class="rr-p">No positions set — the benchmark is read neutrally.</p>`}`;
        // NB: commentary.reading is the executive summary on page 2 — repeating it here
        // as a "lumi's reading" callout put the same paragraph twice in one document.
    }

    if (kindOf === "dials") return html`
      <${RrH} n="03" sub="Each dial below is a stated choice. The third column is what it changes in how your benchmark is read.">How we position reward<//>
      <table class="rr-table">
        <thead><tr><th>Dimension</th><th>Our position</th><th>What it drives</th></tr></thead>
        <tbody>
          ${["market_position", "reward_mix", "pay_for_performance", "transparency", "location_approach",
             "benefits_lead", "family_position", "primary_objective", "budget_direction",
             "acute_pressure", "risk_appetite"].map(f => {
            const v = f === "benefits_lead"
              ? ((strat.benefits_lead || []).length ? "Leads on " + (strat.benefits_lead || []).map(x => ((BENEFITS.find(b => b.v === x) || {}).t || "").toLowerCase()).filter(Boolean).join(", ") : null)
              : (strat[f] ? labelOf(f, strat[f]) : null);
            const n = Object.keys(strat.domain_targets || {}).length;
            return html`<tr key=${f} class=${v ? "" : "rr-unset"}>
              <td>${DIAL_LABEL[f]}</td>
              <td><b>${v || "Not stated"}</b>${f === "market_position" && n ? html`<br /><span class="rr-sm">${n} area${n === 1 ? "" : "s"} set differently</span>` : ""}</td>
              <td class="rr-sm">${v ? (SD_DRIVES[f] || "") : "Read neutrally."}</td>
            </tr>`; })}
        </tbody>
      </table>`;

    if (kindOf === "prin") {
      const cons = doc.constraints || {};
      return html`
        <${RrH} n="04">Principles, peers and constraints<//>
        ${(doc.principles || []).length ? html`
          <h3 class="rr-sh">Our reward principles</h3>
          <ol class="rr-ol">${(doc.principles || []).map((p, i) => html`<li key=${i}>${p}</li>`)}</ol>` : null}
        <h3 class="rr-sh">Who we compare ourselves to</h3>
        <p class="rr-p">${orgCompareWords(null, doc)}</p>
        ${(cons.selected || []).length || cons.notes ? html`
          <h3 class="rr-sh">What constrains us</h3>
          <p class="rr-p">${(cons.selected || []).map(c => CONSTRAINT_LABEL[c] || c).join(" · ")}${cons.notes ? (((cons.selected || []).length ? " — " : "") + cons.notes) : ""}</p>` : null}`;
    }

    if (kindOf === "pops") return html`
      <${RrH} n="05" sub="Stated positions for named groups. lumi holds no executive pay data, so these are never scored against the benchmark.">Position by employee population<//>
      <table class="rr-table">
        <thead><tr><th>Population</th><th>Stated position</th><th>Note</th></tr></thead>
        <tbody>${(doc.population_targets || []).map(p => html`
          <tr key=${p.label}><td>${p.label}</td><td><b>${SD_STANCE[p.position] || "—"}</b></td><td class="rr-sm">${p.note || ""}</td></tr>`)}</tbody>
      </table>`;

    if (kindOf === "tension") return html`
      <${RrH} n="06" sub="Where the stated strategy pulls against itself, or against what the data shows.">Tensions and what to watch<//>
      ${cm && cm.parts ? html`
        <h3 class="rr-sh">Tensions</h3>
        <p class="rr-p">${rrProse(cm.parts.tensions)}</p>
        <h3 class="rr-sh">What to watch</h3>
        <p class="rr-p">${rrProse(cm.parts.watch)}</p>`
        : html`<p class="rr-p rr-muted">${aiWaiting ? "Writing the commentary…" : "Commentary is unavailable for this document."}</p>`}
      <div class="rr-callout quiet">
        <div class="rr-callout-h">Where you stand against this</div>
        <p class="rr-p">Your live position against this strategy, the gaps it opens and the plan to close
        them are set out in the companion <b>Reward Position ${"&"} Plan</b> document.</p>
      </div>`;

    if (kindOf === "gov") return html`
      <${RrH} n="07">Governance and approval<//>
      <table class="rr-table">
        <tbody>
          <tr><td>Status</td><td><b>${ver ? "Approved" : "Draft — not yet approved"}</b>${ver && ver.dirty ? html` <span class="rr-sm">(edits since approval)</span>` : ""}</td></tr>
          ${ver ? html`<tr><td>Version</td><td><b>${ver.version}</b></td></tr>` : null}
          ${ver ? html`<tr><td>Approved by</td><td>${ver.approver_body || ver.approved_by || "—"}</td></tr>` : null}
          ${ver && ver.approval_date ? html`<tr><td>Date of approval</td><td>${ver.approval_date}</td></tr>` : null}
          ${ver && ver.effective_date ? html`<tr><td>Effective from</td><td>${ver.effective_date}</td></tr>` : null}
          ${ver && ver.next_review ? html`<tr><td>Next review</td><td>${ver.next_review}</td></tr>` : null}
          ${st.completed_at ? html`<tr><td>Strategy captured</td><td>${fmtDate(st.completed_at)}</td></tr>` : null}
        </tbody>
      </table>
      ${(ver && (ver.unstated || []).length) ? html`
        <p class="rr-p rr-sm">${ver.unstated.length} section${ver.unstated.length === 1 ? " was" : "s were"} unstated
        at approval: ${ver.unstated.join(", ")}. The version record carries exactly what was and was not stated.</p>` : null}`;

    if (kindOf === "position") return html`
      <${RrH} n="02" sub=${"Each area's live benchmark on " + cutLabel + ", read against the position the strategy states for it."}>Position against intent<//>
      <table class="rr-table">
        <thead><tr><th>Area</th><th>Stated aim</th><th>Live position</th><th>Read</th></tr></thead>
        <tbody>${domains.map(d => {
          const t = d.target || {};
          const p = d.position || {};
          return html`<tr key=${d.name}>
            <td>${domainLabel(d.name)}</td>
            <td>${RR_STANCE_WORD[t.stance] || "—"}</td>
            <td>${RR_POS_WORD[p.verdict] || "no read yet"}</td>
            <td><b class=${"rr-align a-" + (t.alignment || "none")}>${RR_ALIGN_WORD[t.alignment] || "—"}</b></td>
          </tr>`; })}</tbody>
      </table>
      <div class="rr-stats">
        <div><b>${gaps.length}</b><span>off strategy</span></div>
        <div><b>${holding.length}</b><span>holding</span></div>
        <div><b>${unevid.length}</b><span>not yet evidenced</span></div>
      </div>`;

    if (kindOf === "findings") return html`
      <${RrH} n="03" sub=${first ? "Where the declared strategy and the live position diverge, and what organisations in this position commonly consider." : null}>Findings${contd}<//>
      ${(items || []).map((f, i) => html`
        <div key=${i} class="rr-finding">
          <div class="rr-finding-h">${f.headline}</div>
          <p class="rr-p">${rrProse(f.detail)}</p>
          ${f.option ? html`<p class="rr-p rr-opt"><span>Options</span>${rrProse(f.option)}</p>` : null}
        </div>`)}
      ${part === parts - 1 && (dg.on_plan || []).length ? html`
        <p class="rr-p rr-sm">Tracking with intent: ${(dg.on_plan || []).map(domainLabel).join(", ")}.</p>` : null}`;

    if (kindOf === "gapsp") return html`
      <${RrH} n="04" sub=${first ? "One entry per area, with what the market commonly does about it and what each option costs you elsewhere." : null}>The gaps, by area${contd}<//>
      ${(items || []).map(g => html`
        <div key=${g.cat} class="rr-gap">
          <div class="rr-gap-h">${domainLabel(g.cat)}</div>
          ${g.items.map(c => { const ob = optsFor(c.id); return html`
            <div key=${c.id}>
              <p class="rr-p">${c.statement}</p>
              ${ob && (ob.levers || []).length ? html`
                <table class="rr-table tight">
                  <thead><tr><th>Option</th><th>Cost</th><th>Speed</th><th>Trade-off</th></tr></thead>
                  <tbody>${ob.levers.map(l => html`
                    <tr key=${l.lever_id}><td><b>${l.name}</b><br /><span class="rr-sm">${l.what_it_is}</span></td>
                      <td class="rr-sm">${l.cost_character}</td><td class="rr-sm">${l.speed}</td>
                      <td class="rr-sm">${l.trade_off}</td></tr>`)}</tbody>
                </table>`
              : ob && ob.coverage_note ? html`<p class="rr-p rr-sm rr-muted">${ob.coverage_note}</p>` : null}
            </div>`; })}
        </div>`)}`;

    if (kindOf === "planp") return html`
      <${RrH} n="05" sub=${first ? "Sequenced from the gaps above. Every action is one of the options already set out; nothing here is invented." : null}>The plan${contd}<//>
      ${plan ? html`
        ${first ? html`<p class="rr-lede">${rrProse(plan.summary)}</p>` : null}
        <ol class="rr-plan" start=${start || 1}>
          ${(items || []).map((a, i) => html`
            <li key=${i}>
              <div class="rr-plan-t">${a.title}<span class="rr-sm"> · ${domainLabel(a.category || "")} · ${a.horizon}</span></div>
              <p class="rr-p">${rrProse(a.why)}</p>
              <div class="rr-roi"><span>Return</span>${a.roi}</div>
            </li>`)}
        </ol>
        ${part === parts - 1 ? html`<p class="rr-p rr-sm">${plan.basis}${plan.built_at ? " Built " + fmtDate(plan.built_at) + "." : ""}</p>` : null}`
      : html`<p class="rr-p rr-muted">No plan has been built yet. Open <b>Reward plan</b> and choose
        “Build my plan” to sequence these gaps into actions with their indicative return.</p>`}`;

    if (kindOf === "method") return html`
      <${RrH} n=${kind === "plan" ? "06" : "08"}>Method and basis<//>
      <p class="rr-p">Positions are computed from your own submitted data against <b>${cutLabel}</b>, on the
      same engine and the same suppression rules that govern every figure in lumi. Alignment is reported as
      counts against the commitments your strategy makes — never as a score, index or grade.</p>
      <p class="rr-p">Where a commitment's evidence is unanswered, this document says so rather than
      estimating: ${unevid.length} commitment${unevid.length === 1 ? " sits" : "s sit"} unevidenced today.
      Indicative figures come from lumi's cost model on its published assumptions, and appear only where that
      model has a figure for the area in question.</p>
      <p class="rr-p">Written commentary is generated from the figures in this document and validated before
      it is shown: it cannot introduce a number that is not here, direct you to act, or make a legal
      determination. Where validation fails, a plainer standard wording is used instead.</p>
      <p class="rr-p rr-sm">Company facts and choices, not employee data — organisation-level, set by an
      Admin, shaping how your results are read, never what your people see.</p>`;

    return null;
  };

  const prov = "Positions on " + cutLabel + " · " + (sources.length ? "Commentary: " + sources.join(", ") : "Standard wording");

  return html`
    <div class="rr-wrap">
      <div class="row spread no-print rr-bar">
        <button class="btn quiet" onClick=${() => nav(kind === "plan" ? "/plan" : "/strategy")}>← Back</button>
        <div class="row">
          ${aiWaiting ? html`<${Chip} kind="accent">Writing commentary…<//>` : null}
          <button class="btn" disabled=${busy || aiWaiting} onClick=${regen}
            title="Rewrite the commentary from your current position">${busy ? "Rewriting…" : "Rewrite commentary"}</button>
          <button class="btn primary" onClick=${doPrint}><${Icon} name="download" size=${14} /> Save as PDF</button>
        </div>
      </div>
      ${pages.map((p, i) => html`
        <${RrSheet} key=${i} page=${i + 1} total=${TOTAL} foot=${foot} cover=${p.cover}
          prov=${i === TOTAL - 1 ? prov : null}>
          <${Body} kindOf=${p.body} items=${p.items} part=${p.part} parts=${p.parts} start=${p.start} />
        <//>`)}
    </div>`;
};
