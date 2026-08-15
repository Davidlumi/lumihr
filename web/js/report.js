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
  // one page (David 2026-08-16): intent AND position in a single artefact
  full: {
    eyebrow: "REWARD STRATEGY & PLAN",
    title: "Total Reward Strategy & Plan",
    file: "Reward strategy and plan",
    lead: "What we intend our reward to do, where it sits against that intent, and the plan to close the difference.",
  },
};

// A model part that came back on the deterministic floor still reads as prose, so the
// document never says which is which inline — the provenance line on the last page does.
function rrProse(s) { return (s || "").trim(); }

// 1st / 2nd / 3rd / 11th — a hardcoded "th" printed "the 32th percentile" on a board
// page. Every number ending 1, 2 or 3 outside the teens was wrong.
// Engine statements carry raw category names ("Incentives & Recognition"); the
// headings beside them use the house sentence case ("Incentives & recognition").
// Both on one sheet read as sloppy, so prose is normalised to the house form.
function rrCase(text) {
  let out = text || "";
  ["Incentives & Recognition", "Benefits & Lifestyle", "Time Off & Family",
   "Pensions & Savings", "Health & Protection", "Governance & Transparency"].forEach(c => {
    out = out.split(c).join(domainLabel(c));
  });
  return out;
}

function rrOrdinal(n) {
  const v = Math.round(n), t = v % 100;
  if (t >= 11 && t <= 13) return v + "th";
  return v + ({ 1: "st", 2: "nd", 3: "rd" }[v % 10] || "th");
}

// a, b and c — a board paper is prose, not a comma-separated list
function rrList(items) {
  const a = (items || []).filter(Boolean);
  if (!a.length) return "";
  if (a.length === 1) return a[0];
  return a.slice(0, -1).join(", ") + " and " + a[a.length - 1];
}

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

function RrH({ n, children, sub, edit }) {
  return html`
    <div class="rr-h">
      ${n ? html`<span class="rr-h-n">${n}</span>` : null}
      <div class="rr-h-row">
        <h2 class="rr-h-t">${children}</h2>
        ${edit || null}
      </div>
      ${sub ? html`<p class="rr-h-s">${sub}</p>` : null}
    </div>`;
}

// An editable block of generated prose. The author's wording, once saved, IS the
// document — the generated text stays underneath and is restored by clearing.
// Only PROSE is editable: positions, counts, gaps and £ are what the engine found,
// and a document that let you retype those would stop being evidence.
function RrProse({ value, generated, sectionKey, canEdit, onSave, className }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const shown = value != null && value !== "" ? value : generated;
  const edited = value != null && value !== "";
  if (!editing) {
    return html`
      <div class=${"rr-prose" + (edited ? " is-edited" : "")}>
        <p class=${className || "rr-p"}>${rrProse(shown)}</p>
        ${canEdit ? html`
          <div class="rr-prose-tools no-print">
            ${edited ? html`<span class="rr-edited">Your wording</span>` : null}
            <button class="rr-edit" onClick=${() => { setDraft(shown || ""); setEditing(true); }}>
              <${Icon} name="pencil" size=${11} /> Edit</button>
          </div>` : null}
      </div>`;
  }
  const save = async (text) => {
    setSaving(true);
    try { await onSave(sectionKey, text); setEditing(false); }
    catch (e) { toast(e && e.message || "Couldn't save that edit.", "error"); }
    setSaving(false);
  };
  return html`
    <div class="rr-prose editing no-print">
      <textarea class="ctl rr-ta" rows="7" value=${draft} disabled=${saving}
        aria-label="Section wording" onInput=${e => setDraft(e.target.value)}></textarea>
      <div class="rr-prose-foot">
        <button class="btn small primary" disabled=${saving} onClick=${() => save(draft)}>
          ${saving ? "Saving…" : "Save wording"}</button>
        <button class="btn small quiet" disabled=${saving} onClick=${() => setEditing(false)}>Cancel</button>
        ${edited ? html`<button class="btn small quiet" disabled=${saving} onClick=${() => save("")}
          title="Drop your wording and go back to what lumi wrote">Restore lumi's wording</button>` : null}
      </div>
    </div>`;
}

const RR_ALIGN_WORD = { on_target: "On strategy", ahead: "Above strategy", behind: "Below strategy" };
const RR_POS_WORD = { below: "below market", at: "on market", above: "above market" };
const RR_STANCE_WORD = { lag: "below market", match: "on market", lead: "above market" };

// `chips` / `extraActions` / `hideBack` exist so /strategy can BE this document rather
// than link to it (David 2026-08-16: "replace this page with just a view of the PDF
// report"). The governance controls — edit, send for approval, approve, version
// history — ride in the same toolbar instead of on a second bar above it.
window.RewardReportPage = function ({ kind, me, chips, extraActions, hideBack, before, autoPlan, onEditSection }) {
  const K = RRD[kind] || RRD.strategy;
  const canEditDoc = me && me.user && ["admin", "contributor"].includes(me.user.role);
  // which spine(s) this document runs — "full" is both, on one page
  const wantsIntent = kind !== "plan";
  const wantsPlan = kind !== "strategy";
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
    if (wantsPlan) {
      jobs.push(api("/api/strategy-diagnosis", { method: "POST", body }).then(r => setDg(r && r.ok === false ? false : r)).catch(() => setDg(false)));
    }
    return Promise.all(jobs);
  };
  const [planBusy, setPlanBusy] = useState(false);
  const buildPlan = async (a) => {
    setPlanBusy(true);
    try {
      const r = await api("/api/strategy/plan", { method: "POST", body: {} });
      if (r && r.ok === false) {
        if (r.reason === "locked") toast("Your insights unlock once your data is in.", "error");
      } else {
        const fresh = await api("/api/strategy/alignment");
        setAl(fresh);
        if (a) toast("Plan rebuilt from your current gaps.");
      }
    } catch (e) { if (a) toast(e && e.message || "Couldn't build the plan.", "error"); }
    setPlanBusy(false);
  };
  useEffect(() => {
    Promise.all([api("/api/strategy"), api("/api/strategy/alignment")])
      .then(([s, a]) => {
        setSt(s); setAl(a);
        // "do the same for the reward plan SO IT GETS GENERATED" (David 2026-08-16):
        // the plan used to sit behind a Build my plan button, so the document opened
        // saying it had no plan. It writes itself on first open instead — once only,
        // for someone who could have pressed the button anyway, and never when one is
        // already stored (the endpoint persists it, so this costs one call per org).
        // never auto-build against a locked org: the endpoint would refuse, and a
        // silent failed call on every open is worse than no call
        if (autoPlan && a && a.ok !== false && !a.plan && (a.data_state || {}).unlocked !== false) buildPlan(false);
      })
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
  // author overrides: the wording a reward director saved over the generated prose
  const ovr = doc.narrative_overrides || {};
  const saveNarrative = async (key, text) => {
    const r = await api("/api/strategy/narrative", { method: "PUT", body: { key, text } });
    setSt(s => ({ ...s, document: { ...(s.document || {}), narrative_overrides: r.narrative_overrides } }));
    toast(text ? "Your wording saved." : "Restored lumi's wording.");
  };
  // Captured sections aren't prose — you change them by changing what you STATED,
  // so their edit affordance jumps into the wizard at the step that captures them.
  const EditAt = (pageId, label) => (canEditDoc && onEditSection) ? html`
    <button class="rr-edit no-print" title=${"Change this in the strategy set-up"}
      onClick=${() => onEditSection(pageId)}><${Icon} name="pencil" size=${11} /> ${label || "Edit"}</button>` : null;
  const Prose = ({ k, generated, className }) => html`
    <${RrProse} sectionKey=${k} value=${ovr[k]} generated=${generated} className=${className}
      canEdit=${!!canEditDoc} onSave=${saveNarrative} />`;
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

  // gaps grouped by area
  const domAlign = {};
  domains.forEach(x => { domAlign[x.name] = (x.target || {}).alignment; });
  const groups = [];
  gaps.forEach(c => {
    let g = groups.find(x => x.cat === c.category);
    if (!g) { g = { cat: c.category, items: [], align: domAlign[c.category] }; groups.push(g); }
    g.items.push(c);
  });
  // The document is also the working surface now, so each area keeps the two ways out
  // it had on the old screen (David 2026-08-16: "the reward plan must link to signals").
  // Screen-only: a printed page can't be clicked, and a PDF full of dead buttons reads
  // like a broken web page rather than a report.
  const toSignals = (cat, align) => {
    window.__sigJump = { domain: cat, strat: align ? [align] : [] };
    nav("/signals");
  };

  const regen = async () => {
    setBusy(true);
    setCm(null); if (wantsPlan) setDg(null);
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
  const aiWaiting = cm === null || (wantsPlan && dg === null);
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

  if (wantsIntent) {
    P("Strategic intent", "intent");
    P("How we position reward", "dials");
    if ((doc.principles || []).length || doc.comparator_cut != null
        || ((doc.constraints || {}).selected || []).length || (doc.constraints || {}).notes) P("Principles, peers and constraints", "prin");
    if ((doc.population_targets || []).length) P("Position by employee population", "pops");
    P("Tensions and what to watch", "tension");
  }
  // No position read yet (a new org states its strategy BEFORE its data): the whole
  // position half collapses to one honest page rather than drawing an empty table,
  // tiles that say "0 off strategy", and a plan CTA the lock would refuse.
  const dstate = al.data_state || {};
  const hasPosition = (dstate.positioned || domains.length) > 0 && dstate.unlocked !== false;
  if (wantsPlan && !hasPosition) {
    P("Where you'll stand", "awaiting");
  } else if (wantsPlan) {
    P("Position at a glance", "position");
    if (dg && (dg.parts || {}).findings && dg.parts.findings.length)
      Prun("Findings", "findings", dg.parts.findings, () => 2, 6);
    // THE MAIN PART OF THE REPORT (David 2026-08-16): one dedicated section per domain
    // — its count and market position, its signals, a commentary on how it sits against
    // the market, and the recommendations that follow. The flat "gaps by area" run is
    // gone: a gap belongs inside its domain's section, not in a separate list.
    (al.domain_blocks || []).filter(b => b.competitive !== false).forEach(b => {
      // count + position + signals + commentary on one sheet; the recommendations that
      // follow from them on the next. Together they overran A4, and a domain section
      // that spills makes the footer's page count disagree with the paper.
      // Split only when there is a real options table to show. An OVERSPEND domain's
      // "what follows" is a statement and a two-line explanation — printing that on its
      // own A4 sheet used 17% of the page and read as padding in a board document.
      const hasFollow = (b.gaps || []).length > 0
        && (b.options || []).some(o => (o.levers || []).length);
      P(domainLabel(b.name), "domain", { block: b, half: "read", parts: hasFollow ? 2 : 1, part: 0 });
      if (hasFollow) P(domainLabel(b.name) + " (cont.)", "domain", { block: b, half: "follow", parts: 2, part: 1 });
    });
    if (plan && (plan.actions || []).length)
      // budget 5, not 7: the first sheet also carries the summary lede, and three
      // actions with their why + return overran A4 by ~55px
      Prun("The plan", "planp", plan.actions, () => 2, 5);
    else
      P("The plan", "planp", { items: [], part: 0, parts: 1 });
  }
  if (wantsIntent) P("Governance and approval", "gov");
  P("Method and basis", "method");
  const TOTAL = pages.length;
  // Section numbers derive from the page list rather than being written into each body:
  // once the two spines merge into one document, hardcoded "02"s collide and skip.
  const SEC_NO = {};
  let _sn = 0;
  const secKey = (p) => p.body === "domain" ? "domain:" + (p.block || {}).name : p.body;
  pages.forEach(p => { const k = secKey(p);
    if (p.body !== "cover" && !(k in SEC_NO)) SEC_NO[k] = ("0" + (++_sn)).slice(-2); });

  // Commentary on how one domain sits against the market. Composed from that domain's
  // OWN numbers so it is always available, always grounded, and instant — and it is the
  // editable default: an author who wants different words replaces them in place.
  const domProse = (b) => {
    const p = b.position || {}, aim = b.aim || {}, cnt = b.count || {};
    const name = domainLabel(b.name);
    const total = (p.below || 0) + (p.at || 0) + (p.above || 0);
    if (!p.verdict || !total) {
      return name + " does not yet have enough comparable data for a market read. "
        + (cnt.metrics ? cnt.metrics + " metrics are answered here; a verdict needs enough of them to be comparable against your peer group." : "Answering more of this area unlocks its position.");
    }
    const bits = [];
    bits.push(name + " reads " + (RR_POS_WORD[p.verdict] || p.verdict) + " overall"
      + (p.pctl != null ? ", around the " + rrOrdinal(p.pctl) + " percentile of " + cutLabel : "")
      + ", on " + cnt.metrics + " benchmarked " + (cnt.metrics === 1 ? "metric" : "metrics") + ".");
    const parts = [];
    if (p.below) parts.push(p.below + " " + (p.below === 1 ? "sits" : "sit") + " below market");
    if (p.at) parts.push(p.at + " " + (p.at === 1 ? "sits" : "sit") + " on it");
    if (p.above) parts.push(p.above + " " + (p.above === 1 ? "sits" : "sit") + " above");
    if (parts.length) bits.push("Of those, " + rrList(parts) + ".");
    if (aim.stance) {
      const w = { on_target: "which matches the position your strategy sets",
                  behind: "which sits short of the position your strategy sets",
                  ahead: "which sits past the position your strategy sets" }[aim.alignment];
      bits.push("You aim " + RR_STANCE_WORD[aim.stance] + " here" + (w ? ", " + w : "") + ".");
    } else {
      bits.push("No aim is set for " + name + ", so lumi reads it neutrally.");
    }
    if ((b.gaps || []).length) {
      // "below" was wrong twice over: the recommendations sit on the FOLLOWING sheet,
      // and on an overspend domain there are none — the section explains why instead.
      const past = (b.gaps || []).every(g => g.direction === "past");
      bits.push(past
        ? "Sitting past your own aim is not closed by adding to the package, so the section that follows sets out why rather than what to add."
        : "What follows sets out the options against that difference.");
    }
    return bits.join(" ");
  };
  // ------------------------------------------------------------------ bodies ----
  const Body = ({ kindOf, items, part, parts, start, num, block, half }) => {
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
      <${RrH} n=${num}>Executive summary<//>
      ${aiWaiting ? html`<p class="rr-p rr-muted">Writing the commentary…</p>`
        : html`<${Prose} k="exec_summary" className="rr-lede" generated=${
            rrCase((wantsPlan ? (dg && dg.parts && dg.parts.summary) : null)
            || (cm && cm.parts && cm.parts.reading) || "")} />`}
      <div class="rr-stats">
        ${hasPosition ? html`
          <div><b>${domains.length}</b><span>areas benchmarked</span></div>
          <div><b>${gaps.length}</b><span>${gaps.length === 1 ? "gap to close" : "gaps to close"}</span></div>
          <div><b>${holding.length}</b><span>${holding.length === 1 ? "commitment holding" : "commitments holding"}</span></div>`
        : html`
          ${/* a 0/0 gap tally before any data reads as "all is well" — it means "we cannot tell yet" */ ""}
          <div><b>${commitments.length}</b><span>commitments stated</span></div>
          <div><b>${Math.round((al.data_state || {}).core_pct || 0)}%</b><span>of your data in</span></div>
          <div><b>—</b><span>position: awaiting data</span></div>`}
      </div>
      ${/* two columns: a per-domain report runs to ~20 sections and a single-column
           contents list pushed this sheet past A4 (2026-08-16). Continuation pages
           are dropped — a reader wants the section, not every sheet it spans. */ ""}
      <div class="rr-toc">
        <div class="rr-toc-h">Contents</div>
        <div class="rr-toc-cols">
          ${pages.map((p, i) => ({ p, n: i + 1 })).filter(x => x.p.title && !/\(cont\.\)$/.test(x.p.title)).map(x => html`
            <div key=${x.p.title} class="rr-toc-row"><span>${x.p.title}</span><i>${x.n + 1}</i></div>`)}
        </div>
      </div>`;

    if (kindOf === "intent") {
      const stance = sdStance(strat, orgName);
      return html`
        <${RrH} n=${num} edit=${EditAt("phil", "Change the dials")} sub="The strategy as stated by the organisation. lumi reads the benchmark through it — a position below or above market here is a choice, not a verdict.">Strategic intent<//>
        ${stance.length ? stance.map((s, i) => html`<p key=${i} class=${"rr-p" + (i === 0 ? " rr-lede" : "")}>${s}</p>`)
          : html`<p class="rr-p">No positions set — the benchmark is read neutrally.</p>`}`;
        // NB: commentary.reading is the executive summary on page 2 — repeating it here
        // as a "lumi's reading" callout put the same paragraph twice in one document.
    }

    if (kindOf === "dials") return html`
      <${RrH} n=${num} edit=${EditAt("phil", "Change the dials")} sub="Each dial below is a stated choice. The third column is what it changes in how your benchmark is read.">How we position reward<//>
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
        <${RrH} n=${num} edit=${EditAt("principles", "Edit principles")}>Principles, peers and constraints<//>
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
      <${RrH} n=${num} edit=${EditAt("populations", "Edit levels")} sub="Stated positions for named groups. lumi holds no executive pay data, so these are never scored against the benchmark.">Position by employee population<//>
      <table class="rr-table">
        <thead><tr><th>Population</th><th>Stated position</th><th>Note</th></tr></thead>
        <tbody>${(doc.population_targets || []).map(p => html`
          <tr key=${p.label}><td>${p.label}</td><td><b>${SD_STANCE[p.position] || "—"}</b></td><td class="rr-sm">${p.note || ""}</td></tr>`)}</tbody>
      </table>`;

    if (kindOf === "tension") return html`
      <${RrH} n=${num} sub="Where the stated strategy pulls against itself, or against what the data shows.">Tensions and what to watch<//>
      ${cm && cm.parts ? html`
        <h3 class="rr-sh">Tensions</h3>
        <${Prose} k="tensions" generated=${rrCase(cm.parts.tensions)} />
        <h3 class="rr-sh">What to watch</h3>
        <${Prose} k="watch" generated=${rrCase(cm.parts.watch)} />`
        : html`<p class="rr-p rr-muted">${aiWaiting ? "Writing the commentary…" : "Commentary is unavailable for this document."}</p>`}
      <div class="rr-callout quiet">
        <div class="rr-callout-h">Where you stand against this</div>
        <p class="rr-p">Your live position against this strategy, the gaps it opens and the plan to close
        them are set out in the companion <b>Reward Position ${"&"} Plan</b> document.</p>
      </div>`;

    if (kindOf === "gov") return html`
      <${RrH} n=${num}>Governance and approval<//>
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

    // ---- ONE DOMAIN, in full: count, position, signals, commentary, what follows ----
    if (kindOf === "domain") {
      const b = block || {};
      const isRead = (half || "read") === "read";
      const inlineFollow = isRead && (b.gaps || []).length && (parts || 1) === 1;
      const sigShown = (b.signals || []).slice(0, inlineFollow ? 2 : 4);
      const pos = b.position || {};
      const aim = b.aim || {};
      const cnt = b.count || {};
      const total = (pos.below || 0) + (pos.at || 0) + (pos.above || 0);
      const pctOf = (v) => total ? Math.round((100 * (v || 0)) / total) : 0;
      const readWord = RR_ALIGN_WORD[aim.alignment];
      return html`
        <${RrH} n=${num} sub=${isRead
          ? "How " + domainLabel(b.name) + " sits against " + cutLabel + ", and what your strategy asks of it."
          : null}>${domainLabel(b.name)}${isRead ? "" : " — what follows"}<//>

        ${!isRead ? null : html`
        ${/* count + market position, side by side — the two facts a reader wants first */ ""}
        <div class="rr-dom-head">
          <div class="rr-dom-stat">
            <span class="rr-dom-k">Metrics benchmarked</span>
            <b>${cnt.metrics || 0}</b>
            <span class="rr-sm">${cnt.pool ? "against " + cnt.pool + " peer readings" : "on your own data"}</span>
          </div>
          <div class="rr-dom-stat">
            <span class="rr-dom-k">Market position</span>
            <b class=${"rr-verdict v-" + (pos.verdict || "none")}>${RR_POS_WORD[pos.verdict] || "no read yet"}</b>
            <span class="rr-sm">${pos.pctl != null ? "around the " + rrOrdinal(pos.pctl) + " percentile" : "not enough comparable data"}</span>
          </div>
          <div class="rr-dom-stat">
            <span class="rr-dom-k">Against your aim</span>
            <b class=${"rr-align a-" + (aim.alignment || "none")}>${readWord || "No aim set"}</b>
            <span class="rr-sm">${aim.stance ? "you aim " + RR_STANCE_WORD[aim.stance] : "read neutrally"}</span>
          </div>
        </div>

        ${total ? html`
          <div class="rr-split" role="img"
            aria-label=${pos.below + " below, " + pos.at + " on, " + pos.above + " above market"}>
            ${[["below", pos.below], ["at", pos.at], ["above", pos.above]].map(([k, v]) => v ? html`
              <span key=${k} class=${"rr-split-seg s-" + k} style=${{ flex: v }}>
                <i>${v}</i>${RR_POS_WORD[k]}</span>` : null)}
          </div>` : null}`}

        ${!isRead ? null : html`
        ${/* commentary on alignment to market — the analytic heart of the section */ ""}
        <h3 class="rr-sh">How this reads</h3>
        <${Prose} k=${"domain:" + b.name} generated=${domProse(b)} />

        ${/* a sheet that ALSO carries the follow content has room for fewer signals —
             sized so the combined sheet still lands inside A4 */ ""}
        ${(sigShown || []).length ? html`
          <h3 class="rr-sh">What ${domainLabel(b.name)} is flagging${b.signal_count > sigShown.length
            ? html` <span class="rr-sm">(${sigShown.length} of ${b.signal_count})</span>` : ""}</h3>
          <table class="rr-table tight">
            <thead><tr><th>Signal</th><th>Yours</th><th>Reads</th></tr></thead>
            <tbody>${sigShown.map(sg => html`
              <tr key=${sg.question_id || sg.title}>
                <td><b>${sg.title}</b>${sg.detail ? html`<br /><span class="rr-sm">${sg.detail}</span>` : ""}</td>
                <td class="rr-sm">${sg.value || "—"}</td>
                <td class="rr-sm">${RR_POS_WORD[sg.position] || sg.position || "—"}</td>
              </tr>`)}</tbody>
          </table>` : null}`}

        ${isRead ? null : html`
          ${/* the sheet heading already reads "<domain> — what follows"; repeating it
               as an h3 directly underneath said the same thing twice */ ""}
          ${b.gaps.map(c => html`<p key=${c.id} class="rr-p">${rrCase(c.statement)}</p>`)}
          ${(b.options || []).some(o => (o.levers || []).length) ? html`
            <table class="rr-table tight">
              <thead><tr><th>Option</th><th>Cost</th><th>Speed</th><th>Trade-off</th></tr></thead>
              <tbody>${b.options.flatMap(o => (o.levers || []).map(l => html`
                <tr key=${l.lever_id}><td><b>${l.name}</b><br /><span class="rr-sm">${l.what_it_is}</span></td>
                  <td class="rr-sm">${l.cost_character}</td><td class="rr-sm">${l.speed}</td>
                  <td class="rr-sm">${l.trade_off}</td></tr>`))}</tbody>
            </table>`
          : html`<p class="rr-p rr-sm rr-muted">${(b.options.find(o => o.coverage_note) || {}).coverage_note || ""}</p>`}`}

        ${isRead && !(b.gaps || []).length ? html`
          <p class="rr-p rr-sm">Nothing in ${domainLabel(b.name)} currently runs against your stated aim.</p>` : null}
        ${/* not split (no options table): the short explanation rides on the read sheet */ ""}
        ${isRead && (b.gaps || []).length && (parts || 1) === 1 ? html`
          <h3 class="rr-sh">What follows for ${domainLabel(b.name)}</h3>
          ${b.gaps.map(c => html`<p key=${c.id} class="rr-p">${rrCase(c.statement)}</p>`)}
          <p class="rr-p rr-sm rr-muted">${(b.options.find(o => o.coverage_note) || {}).coverage_note || ""}</p>` : null}

        <div class="rr-gap-foot no-print">
          <button class="rp-go" onClick=${() => toSignals(b.name, aim.alignment)}>
            <${Icon} name="zap" size=${13} /> ${domainLabel(b.name)} signals</button>
          <a class="rp-go" href=${"#/category/" + encodeURIComponent(b.name)}>
            <${Icon} name="bar-chart" size=${13} /> The data behind it</a>
        </div>`;
    }

    if (kindOf === "awaiting") {
      const need = Math.max(0, Math.ceil(((dstate.basis_total || 0) * (dstate.target_pct || 0)) / 100) - (dstate.answered || 0));
      return html`
        <${RrH} n=${num} sub="This half of the document is written from your own submitted data, read against your peer group. It fills in as your data arrives — nothing here is estimated in the meantime.">Where you'll stand<//>
        <p class="rr-lede">Your strategy above is stated and in force: lumi is already reading every
        benchmark through it. What it cannot yet do is tell you where you actually sit against it.</p>
        <div class="rr-stats">
          <div><b>${Math.round(dstate.core_pct || 0)}%</b><span>of your key metrics answered</span></div>
          <div><b>${need}</b><span>${need === 1 ? "answer to unlock" : "answers to unlock"}</span></div>
          <div><b>${commitments.length}</b><span>commitments waiting on evidence</span></div>
        </div>
        <p class="rr-p">Once your data is in, these pages complete the document: your position against
        each stated aim, the gaps that opens, what the market does about each one, and a sequenced plan
        with what each action returns.</p>
        ${canEditDoc ? html`
          <div class="rr-cta no-print">
            <button class="btn primary" onClick=${() => nav("/your-data")}>Add your data</button>
            <span class="rr-sm">Roughly ${need > 40 ? "an hour" : need > 15 ? "half an hour" : "a few minutes"} of work, and it only has to be done once.</span>
          </div>` : null}`;
    }

    if (kindOf === "position") return html`
      <${RrH} n=${num} sub=${"Each area's live benchmark on " + cutLabel + ", read against the position the strategy states for it."}>Position at a glance<//>
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
      <${RrH} n=${num} sub=${first ? "Where the declared strategy and the live position diverge, and what organisations in this position commonly consider." : null}>Findings${contd}<//>
      ${(items || []).map((f, i) => html`
        <div key=${i} class="rr-finding">
          <div class="rr-finding-h">${rrCase(f.headline)}</div>
          <p class="rr-p">${rrCase(rrProse(f.detail))}</p>
          ${f.option ? html`<p class="rr-p rr-opt"><span>Options</span>${rrCase(rrProse(f.option))}</p>` : null}
        </div>`)}
      ${part === parts - 1 && (dg.on_plan || []).length ? html`
        <p class="rr-p rr-sm">Tracking with intent: ${(dg.on_plan || []).map(domainLabel).join(", ")}.</p>` : null}`;

    if (kindOf === "gapsp") return html`
      <${RrH} n=${num} sub=${first ? "One entry per area, with what the market commonly does about it and what each option costs you elsewhere." : null}>The gaps, by area${contd}<//>
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
          <div class="rr-gap-foot no-print">
            <button class="rp-go" onClick=${() => toSignals(g.cat, g.align)}>
              <${Icon} name="zap" size=${13} /> ${domainLabel(g.cat)} signals</button>
            <a class="rp-go" href=${"#/category/" + encodeURIComponent(g.cat)}>
              <${Icon} name="bar-chart" size=${13} /> The data behind it</a>
          </div>
        </div>`)}`;

    if (kindOf === "planp") return html`
      <${RrH} n=${num} sub=${first ? "This is the roll-up of the sections above: every action below is one of the options already set out under its own domain, sequenced across all of them." : null}>The plan${contd}<//>
      ${plan ? html`
        ${first ? html`<${Prose} k="plan_summary" className="rr-lede" generated=${rrCase(plan.summary)} />` : null}
        <ol class="rr-plan" start=${start || 1}>
          ${(items || []).map((a, i) => html`
            <li key=${i}>
              <div class="rr-plan-t">${a.title}
                <span class="rr-sm"> · from ${domainLabel(a.category || "")}${
                  SEC_NO["domain:" + a.category] ? " (§" + SEC_NO["domain:" + a.category] + ")" : ""} · ${a.horizon}</span></div>
              <p class="rr-p">${rrCase(rrProse(a.why))}</p>
              <div class="rr-roi"><span>Return</span>${a.roi}</div>
            </li>`)}
        </ol>
        ${part === parts - 1 ? html`<p class="rr-p rr-sm">${plan.basis}${plan.built_at ? " Built " + fmtDate(plan.built_at) + "." : ""}</p>` : null}`
      : html`<p class="rr-p rr-muted">${planBusy
          ? "Sequencing your gaps into a plan…"
          : "No plan is stored yet. Use Rebuild plan above to sequence these gaps into actions with their indicative return."}</p>`}`;

    if (kindOf === "method") return html`
      <${RrH} n=${num}>Method and basis<//>
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
      ${before || null}
      <div class="row spread no-print rr-bar">
        <div class="row rr-bar-l">
          ${hideBack ? null : html`<button class="btn quiet" onClick=${() => nav(kind === "plan" ? "/plan" : "/strategy")}>← Back</button>`}
          ${chips || null}
        </div>
        <div class="row">
          ${aiWaiting ? html`<${Chip} kind="accent">Writing commentary…<//>` : null}
          ${planBusy ? html`<${Chip} kind="accent">Writing the plan…<//>` : null}
          ${extraActions || null}
          ${autoPlan ? html`<button class="btn" disabled=${planBusy} onClick=${() => buildPlan(true)}
            title="Re-sequence the plan from your current gaps">${planBusy ? "Writing…" : "Rebuild plan"}</button>` : null}
          <button class="btn" disabled=${busy || aiWaiting} onClick=${regen}
            title="Rewrite the commentary from your current position">${busy ? "Rewriting…" : "Rewrite commentary"}</button>
          <button class="btn primary" onClick=${doPrint}><${Icon} name="download" size=${14} /> Save as PDF</button>
        </div>
      </div>
      ${pages.map((p, i) => html`
        <${RrSheet} key=${i} page=${i + 1} total=${TOTAL} foot=${foot} cover=${p.cover}
          prov=${i === TOTAL - 1 ? prov : null}>
          <${Body} kindOf=${p.body} items=${p.items} part=${p.part} parts=${p.parts} start=${p.start} num=${SEC_NO[secKey(p)]} block=${p.block} half=${p.half} />
        <//>`)}
    </div>`;
};
