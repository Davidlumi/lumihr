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

// THE SPINE (2026-08-16, David: "proper titles, subtitles, sections — as if they spent
// £10k with Mercer"). Forty-five sheets without parts is a stack of pages; with them it
// is a document you can find your way around. Front matter — cover, executive summary,
// the ask — deliberately sits OUTSIDE the parts: it is what a reader who reads three
// pages reads, and burying it inside Part A would bury the ask with it.
const RR_PARTS = [
  { id: "A", title: "The reward strategy",
    lead: "What this organisation intends its reward to do, the positions it has chosen, "
        + "and the principles and constraints those choices sit inside. Nothing in this part "
        + "is a measurement — every position here is a stated intention." },
  { id: "B", title: "Where the package stands",
    lead: "The live benchmark for each area of reward, read against the position the strategy "
        + "sets for it. One section per area: the evidence behind the read, the market position "
        + "it produces, what the area is flagging, and how the two compare." },
  { id: "C", title: "What follows",
    lead: "The actions the gaps in Part B lead to, sequenced across cycles — with what they "
        + "cost, what they expose the organisation to, and a record of the options that were "
        + "weighed and not taken." },
  { id: "D", title: "Governance and method",
    lead: "How this document was approved and by whom, and how every figure in it was "
        + "produced — the peer basis, the suppression rules and the limits of each read." },
];
const RR_PART = {};
RR_PARTS.forEach(p => { RR_PART[p.id] = p; });

// Typographic punctuation. A document set in straight typewriter quotes reads as a
// printout however good the words are, and it is the cheapest mark of care available.
// Applied to the document's own voice — headings, decks, prose and captions — and to
// the engine strings that flow through them; never to code, ids or numbers.
function rrType(s) {
  if (typeof s !== "string") return s;
  return s
    .replace(/(\w)'(\w)/g, "$1’$2")          // don't -> don’t
    .replace(/(^|[\s(\[—-])'/g, "$1‘")  // an opening single quote
    .replace(/'/g, "’")                      // anything left closes
    .replace(/(^|[\s(\[—-])"/g, "$1“")  // an opening double quote
    .replace(/"/g, "”");
}
// htm hands a heading its children as a string or an array of them
function rrTypeAny(x) {
  return Array.isArray(x) ? x.map(rrTypeAny) : rrType(x);
}

// A model part that came back on the deterministic floor still reads as prose, so the
// document never says which is which inline — the provenance line on the last page does.
function rrProse(s) { return (s || "").trim(); }

// 1st / 2nd / 3rd / 11th — a hardcoded "th" printed "the 32th percentile" on a board
// page. Every number ending 1, 2 or 3 outside the teens was wrong.
// Engine statements carry raw category names ("Incentives & Recognition"); the
// headings beside them use the house sentence case ("Incentives & recognition").
// Both on one sheet read as sloppy, so prose is normalised to the house form.
function rrCase(text) {
  let out = rrType(text || "");
  ["Incentives & Recognition", "Benefits & Lifestyle", "Time Off & Family",
   "Pensions & Savings", "Health & Protection", "Governance & Transparency"].forEach(c => {
    out = out.split(c).join(domainLabel(c));
  });
  return out;
}

// The decision line is a sentence fragment ("approve the action scheduled for this
// cycle") composed server-side so it can also be read aloud mid-paragraph. On its own
// line under DECISION SOUGHT it needs a capital, and only there.
function rrCap(text) {
  const t = (text || "").trim();
  return t ? t[0].toUpperCase() + t.slice(1) : t;
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

function RrSheet({ page, total, foot, prov, children, cover, divider, head }) {
  return html`
    <div id=${"rr-sheet-" + page}
      class=${"pack-page rr-sheet" + (cover ? " rr-cover" : "") + (divider ? " rr-div-sheet" : "")}>
      ${/* the running head — a reader holding sheet 31 of a printed document has no
           other way to know where they are. Cover and part dividers carry their own
           identity and would only be repeating themselves. */ ""}
      ${head ? html`
        <div class="rr-run">
          <span class="rr-run-l">${head.left}</span>
          <span class="rr-run-r">${head.right}</span>
        </div>` : null}
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

// WHERE AM I, and how do I get somewhere else. Forty-one sheets is a long scroll, and
// the only way to find a section used to be to scroll past everything before it.
//
// Its OWN component, deliberately: reading position changes on every scroll tick, and
// holding that state in the page meant re-rendering all forty-one sheets each time. The
// readout ran a whole probe behind because the re-render could not keep up — the visible
// symptom of a real cost. Nothing outside this component re-renders while you scroll.
function RrNav({ items, total, onGo }) {
  const [here, setHere] = useState(0);
  useEffect(() => {
    // IntersectionObserver, not a scroll listener. The hand-rolled version measured
    // rects on scroll + a trailing timeout and still went stale: a fast jump fires one
    // event, sometimes before the browser has committed the offset, and once you are
    // stationary nothing arrives to correct it. The observer is told when visibility
    // changes rather than having to guess, costs nothing while you are not scrolling,
    // and cannot miss the event that matters.
    const sheets = [].slice.call(document.querySelectorAll(".rr-sheet"));
    if (!sheets.length || typeof IntersectionObserver === "undefined") return undefined;
    // The observer is the TRIGGER; the measurement is taken fresh from the DOM each
    // time. Remembering each entry's height instead looked tidier and was wrong: on a
    // long jump the destination reports itself but a departing sheet does not always
    // report its exit, so its stale height kept winning and the readout sat on "Cover"
    // while you were on sheet 12. Recomputing costs 41 rects on a visibility change.
    const measure = () => {
      const vh = window.innerHeight;
      let best = -1, cur = 0;
      for (let i = 0; i < sheets.length; i++) {
        const r = sheets[i].getBoundingClientRect();
        if (r.bottom < 0 || r.top > vh) continue;
        const shown = Math.min(r.bottom, vh) - Math.max(r.top, 0);
        if (shown > best) { best = shown; cur = i; }
      }
      setHere(cur);
    };
    const io = new IntersectionObserver(measure,
      { threshold: [0, 0.02, 0.25, 0.5, 0.75, 1] });
    sheets.forEach(s => io.observe(s));
    return () => io.disconnect();
  }, [total]);
  const cur = items[here] || {};
  return html`
    <div class="rr-nav">
      <span class="rr-nav-at">
        <b>${cur.cover ? "Cover" : cur.divider ? "Part " + cur.pt : rrType(cur.title || "")}</b>
        <i>${here + 1} / ${total}</i>
      </span>
      <select class="ctl rr-nav-go" aria-label="Jump to a section"
        value=${String(here)} onChange=${e => onGo(Number(e.target.value))}>
        ${items.filter(x => x.cover || x.divider || (x.title && !x.cont)).map(x => html`
          <option key=${x.i} value=${String(x.i)}>${x.cover ? "Cover"
            : x.divider ? "Part " + x.pt + " — " + x.partTitle
            : (x.no ? x.no + "  " : "") + rrType(x.title)}</option>`)}
      </select>
    </div>`;
}

// Exhibit caption. Every table in a consultancy document is numbered and named, so it
// can be referred to in a meeting ("look at exhibit 12") and so a reader can tell a
// figure that was produced from one that was asserted. Numbers are DERIVED from a walk
// of the finished page list — hand-written ones drift the moment a section is added.
function RrEx({ ex }) {
  if (!ex) return null;
  return html`
    <div class="rr-ex"><span class="rr-ex-n">Exhibit ${ex.n}</span>${rrType(ex.cap)}</div>`;
}

function RrH({ n, children, sub, edit }) {
  return html`
    <div class="rr-h">
      ${n ? html`<span class="rr-h-n">${n}</span>` : null}
      <div class="rr-h-row">
        <h2 class="rr-h-t">${rrTypeAny(children)}</h2>
        ${edit || null}
      </div>
      ${sub ? html`<p class="rr-h-s">${rrTypeAny(sub)}</p>` : null}
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
        <p class=${className || "rr-p"}>${rrType(rrProse(shown))}</p>
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

// The decision control on one option (2026-08-16, David's #3: record what you decided
// NOT to do). Module scope, not an inline closure inside the page: a component redefined
// on every render is a NEW type to React, so the panel would unmount mid-typing and lose
// the reason field. Prints as a plain badge — every control here is screen-only.
function RrDecCell({ cur, states, canEdit, onSave }) {
  const [open, setOpen] = useState(false);
  const [why, setWhy] = useState("");
  const [saving, setSaving] = useState(false);
  if (!canEdit && !cur) return null;
  const set = async (state) => {
    setSaving(true);
    try { await onSave(state, why); setOpen(false); }
    catch (e) { /* onSave surfaces its own toast */ }
    setSaving(false);
  };
  return html`
    <div class="rr-dec-wrap">
      ${cur ? html`
        <span class=${"rr-dec d-" + cur.state}>${states[cur.state] || cur.state}</span>
        ${cur.reason ? html`<span class="rr-sm rr-dec-why">${cur.reason}</span>` : null}` : null}
      ${canEdit ? html`
        <button class="rr-dec-btn no-print" onClick=${() => { setWhy((cur && cur.reason) || ""); setOpen(!open); }}>
          <${Icon} name="pencil" size=${10} /> ${cur ? "Change decision" : "Record a decision"}</button>` : null}
      ${canEdit && open ? html`
        <div class="rr-dec-panel no-print">
          <input class="ctl rr-dec-in" placeholder="Why — one line, for the record" value=${why}
            maxLength=${400} disabled=${saving} aria-label="Reason for this decision"
            onInput=${e => setWhy(e.target.value)} />
          <div class="rr-dec-acts">
            ${Object.keys(states).map(s => html`
              <button key=${s} disabled=${saving}
                class=${"rr-dec-set" + (cur && cur.state === s ? " on" : "")}
                onClick=${() => set(s)}>${states[s]}</button>`)}
            ${cur ? html`<button class="rr-dec-clear" disabled=${saving}
              onClick=${() => set("")}>Clear</button>` : null}
          </div>
        </div>` : null}
    </div>`;
}

// The in-app "what it drives" copy talks about signals and lenses — product vocabulary
// that has no place in a board document ("Sharpens which signal lenses surface first").
// These say the same thing in the register of the paper it is printed in.
const RR_DRIVES = {
  market_position: "The position every area is read against.",
  reward_mix: "How pay and wider benefits are weighed together.",
  pay_for_performance: "The spread between individuals that is treated as intended.",
  transparency: "Which openness practices count as commitments.",
  location_approach: "Whether local pay markets are read separately.",
  benefits_lead: "The benefit areas treated as deliberate leads.",
  family_position: "The family-support bar the organisation is held to.",
  primary_objective: "The lens the whole document is read through.",
  budget_direction: "Whether saving or investment is weighed more heavily.",
  acute_pressure: "The operating condition the year’s choices are made in.",
  risk_appetite: "How early the organisation expects to move on emerging practice.",
};

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
  const [stm, setStm] = useState(null);       // AI: the six narrative sections (intent)
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const orgName = (me.org && me.org.name) || "Your organisation";

  const loadNarrative = (force) => {
    const body = force ? { force: true } : {};
    const jobs = [api("/api/strategy/commentary", { method: "POST", body }).then(setCm).catch(() => setCm(false))];
    if (wantsIntent) {
      jobs.push(api("/api/strategy/statement", { method: "POST", body })
        .then(r => setStm(r && r.ok === false ? false : r)).catch(() => setStm(false)));
    }
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

  // ---- BOARD-PAPER READS (2026-08-16) ---------------------------------------
  // Six things a reward director found missing: the document never ASKED for a
  // decision, carried no aggregate cost, recorded no rejected option, listed the
  // plan instead of scheduling it, named no risks, and showed no movement.
  const money = al.money || {};
  const theAsk = al.the_ask || {};
  const risks = al.risks || [];
  const trend = al.trend || {};
  const schedule = al.schedule || [];
  const decisions = al.option_decisions || {};
  const DEC_STATES = al.option_decision_states || {};
  const gbp = (n) => "£" + Math.round(n || 0).toLocaleString("en-GB");
  const decKey = (cat, lever) => (cat || "") + "|" + (lever || "");
  const saveDecision = async (cat, lever, state, reason) => {
    try {
      const r = await api("/api/strategy/option-decision",
        { method: "PUT", body: { category: cat, lever_id: lever, state: state, reason: reason || "" } });
      setAl(a => ({ ...a, option_decisions: r.option_decisions }));
      toast(state ? "Decision recorded." : "Decision cleared.");
    } catch (e) { toast(e && e.message || "Couldn't record that decision.", "error"); }
  };
  // Every option that has been decided on, in document order — the not-taken record.
  // Deduped: one lever can be offered against TWO commitments in the same area (a
  // position gap and a coherence rule both reaching for it), and the record listed it
  // twice under an identical React key.
  const decidedRows = [];
  const decSeen = {};
  (al.domain_blocks || []).forEach(b => {
    (b.options || []).forEach(o => (o.levers || []).forEach(l => {
      const k = decKey(b.name, l.lever_id);
      const d = decisions[k];
      if (d && d.state && !decSeen[k]) { decSeen[k] = 1; decidedRows.push({ k, cat: b.name, lever: l, dec: d }); }
    }));
  });
  const nPriced = money.priced || 0;
  const nGaps = money.gaps_total || 0;

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
    setCm(null); if (wantsPlan) setDg(null); if (wantsIntent) setStm(null);
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
  const aiWaiting = cm === null || (wantsPlan && dg === null) || (wantsIntent && stm === null);
  const sources = [];
  if (cm && cm.source) sources.push("commentary " + cm.source);
  if (dg && dg.source) sources.push("findings " + dg.source);
  if (plan && plan.source) sources.push("plan " + plan.source);

  // ---- the page list, built per kind so numbering is derived, never hand-counted ----
  const pages = [];
  // `pt` is the DOCUMENT part (A/B/C/D) — deliberately not `part`, which Prun already
  // uses for the chunk index of a split section. Two different "part"s on one page
  // object would be a bug waiting to happen.
  let curPt = null;
  const P = (title, body, opts) => pages.push({ title, body, pt: curPt, ...(opts || {}) });
  // Open a part: a divider sheet, then everything that follows belongs to it until the
  // next PART call. Dividers for a part that turns out to hold one section are dropped
  // again below — a divider page announcing a single page is padding, not structure.
  const PART = (id) => { curPt = id; pages.push({ title: null, body: "divider", pt: id, divider: true }); };
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

  // §2 THE ASK. A board paper requests a decision; this document only ever described
  // one (2026-08-16). It sits directly behind the executive summary because that is
  // where a reader who reads two pages and nothing else will look for it.
  if (wantsPlan) P("What we're asking the board to approve", "ask");

  if (wantsIntent) {
    PART("A");
    // The narrative of the strategy — the thing a Mercer or WTW paper opens with, and
    // what "just broken sentences" was standing in for. Two sheets so each section has
    // room to be prose rather than a caption.
    P("The strategy", "story1");
    P("The strategy (cont.)", "story2");
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
    PART("B");
    P("Where you'll stand", "awaiting");
  } else if (wantsPlan) {
    PART("B");
    P("Position at a glance", "position");
    // Movement belongs with the position read, not at the back. It cannot be built
    // today — there is one aggregated collection window — and the page says so rather
    // than the absence being discovered by whoever asks "are we improving?".
    P("Movement since the last review", "trend");
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
      const allLev = (b.options || []).flatMap(o => (o.levers || []));
      const hasFollow = (b.gaps || []).length > 0 && allLev.length > 0;
      // A coherence shortfall now draws BOTH registers, so an options table can run to ten
      // rows and overflow its sheet. Chunk at five — the same weight discipline the rest of
      // the document uses, rather than letting one area silently spill.
      // 4, not 5 (2026-08-16): each lever row now carries its decision badge and the
      // author's reason, which added ~200px to a five-row sheet and pushed it past A4
      const followSheets = hasFollow ? Math.max(1, Math.ceil(allLev.length / 4)) : 0;
      P(domainLabel(b.name), "domain", { block: b, half: "read", parts: hasFollow ? 2 : 1, part: 0 });
      for (let k = 0; k < followSheets; k++) {
        P(domainLabel(b.name) + (k ? " (cont.)" : " (cont.)"), "domain",
          { block: b, half: "follow", parts: 2, part: 1, levSlice: [k * 4, k * 4 + 4],
            levPart: k, levParts: followSheets });
      }
    });
    PART("C");
    // THE SCHEDULE before the plan: the shape across cycles, then the detail. The plan
    // carried a horizon per action all along and printed them as a flat numbered run,
    // which reads as a to-do list rather than a programme (2026-08-16).
    // weight = the group heading plus a row per action, so a ten-action programme
    // splits at a sheet boundary instead of running past A4
    if (schedule.length) Prun("The schedule", "sched", schedule, (s) => 1 + s.actions.length, 7);
    if (plan && (plan.actions || []).length) {
      // budget 5, not 7: the first sheet also carries the summary lede, and three
      // actions with their why + return overran A4 by ~55px
      // ordered by horizon so the detail runs in the same sequence the schedule shows
      const ordered = schedule.length
        ? schedule.reduce((a, s) => a.concat(s.actions), [])
        : plan.actions;
      Prun("The plan", "planp", ordered, () => 2, 5);
    } else {
      P("The plan", "planp", { items: [], part: 0, parts: 1 });
    }
    // What it costs, what could go wrong, and what was turned down — the three
    // sections a board paper is expected to carry and this one did not.
    P("What it costs", "cost");
    // only when lumi has an FTE band to compute against — no band, no unit rates, no
    // section, rather than a page of dashes
    if (((money.unit_rates || {}).points || []).length) P("What a point is worth", "worth");
    // seven derivable risks at ~4 lines each overrun a sheet; four to a page, and the
    // first also carries the lede
    Prun("Risks and exposures", "risks", risks, () => 2, 6);
    // the not-taken record grows with every decision an author makes — unbounded by
    // nature, so it chunks like every other run in this document
    if (decidedRows.length) Prun("Decisions taken and not taken", "decided", decidedRows, () => 1, 5);
  }
  PART("D");
  if (wantsIntent) P("Governance and approval", "gov");
  P("Method and basis", "method");

  // A divider announcing a single section is padding, not structure — so a part that
  // came out one section long loses its divider and keeps its sections. This happens
  // for real: a fresh org's Part B is the one honest "Where you'll stand" page.
  const _ptCount = {};
  pages.forEach(p => { if (!p.divider && p.pt) _ptCount[p.pt] = (_ptCount[p.pt] || 0) + 1; });
  const spine = pages.filter(p => !(p.divider && (_ptCount[p.pt] || 0) < 2));
  pages.length = 0;
  spine.forEach(p => pages.push(p));
  // the parts that survived, in document order — the contents groups by these
  const LIVE_PARTS = [];
  pages.forEach(p => { if (p.divider && LIVE_PARTS.indexOf(p.pt) < 0) LIVE_PARTS.push(p.pt); });

  const TOTAL = pages.length;
  // Jump to a sheet. Screen-only behaviour — the printed document keeps its page
  // numbers and needs no help; on screen a contents you cannot click is a tease.
  // Section numbers derive from the page list rather than being written into each body:
  // once the two spines merge into one document, hardcoded "02"s collide and skip.
  const SEC_NO = {};
  let _sn = 0;
  // A section that spans two sheets is still ONE section. story2 shares story1's key,
  // or it burns a section number on a continuation sheet the contents hides — which
  // printed a list running 03, 05, 06 with no 04 anywhere in the document.
  const secKey = (p) => p.body === "domain" ? "domain:" + (p.block || {}).name
    : (p.body === "story2" ? "story1" : p.body);
  pages.forEach(p => { const k = secKey(p);
    if (p.body !== "cover" && p.body !== "divider" && !(k in SEC_NO)) SEC_NO[k] = ("0" + (++_sn)).slice(-2); });

  // ---- EXHIBITS -------------------------------------------------------------------
  // Numbered by a walk of the FINISHED page list, in the order the sheets render, so a
  // section added anywhere renumbers everything after it automatically. A number
  // written into a caption by hand is wrong the first time someone inserts a
  // section above it. (No literal exhibit number appears in this file — gated.)
  const EXH = {};
  let _exn = 0;
  const exReg = (k, cap) => { if (!(k in EXH)) EXH[k] = { n: ++_exn, cap: cap }; };
  pages.forEach(p => {
    const b = p.block || {};
    switch (p.body) {
      case "dials": exReg("dials", "Stated reward positions, and what each one changes in how the benchmark is read"); break;
      case "pops": exReg("pops", "Stated positions by employee population"); break;
      case "position": exReg("position", "Market position by area, against the position the strategy sets"); break;
      case "trend": if (trend.available) exReg("trend", "Movement by area since the previous collection window"); break;
      case "sched": exReg("sched:" + p.part, "Planned actions by horizon" + (p.parts > 1 ? " (" + (p.part + 1) + " of " + p.parts + ")" : "")); break;
      case "cost": if ((money.items || []).length) exReg("cost", "Metrics lumi can price, and the cost of moving each to the peer median"); break;
      case "worth": exReg("worth", "What one percentage point of movement is worth, and the arithmetic behind each"); break;
      case "decided": exReg("decided:" + p.part, "Each option, the area it belongs to, the decision recorded and the reason given" + (p.parts > 1 ? " (" + (p.part + 1) + " of " + p.parts + ")" : "")); break;
      case "gov": exReg("gov", "Approval record for this strategy"); break;
      case "domain":
        if (p.half === "read" && (b.signals || []).length)
          exReg("dom-sig:" + b.name, "Signals in " + domainLabel(b.name) + ", with your value and how each one reads against " + cutLabel);
        if (p.half === "follow")
          exReg("dom-opt:" + b.name + ":" + p.levPart,
                "Options against the " + domainLabel(b.name) + " gaps, and the decision on each"
                + ((p.levParts || 1) > 1 ? " (" + ((p.levPart || 0) + 1) + " of " + p.levParts + ")" : ""));
        break;
    }
  });

  // a flat, cheap description of the spine for the navigator — it must not need
  // SEC_NO, secKey or the page objects themselves
  const navItems = pages.map((p, i) => ({
    i: i, cover: !!p.cover, divider: !!p.divider, pt: p.pt,
    partTitle: (RR_PART[p.pt] || {}).title,
    title: p.title, no: SEC_NO[secKey(p)],
    cont: !!(p.title && /\(cont\.\)$/.test(p.title)),
  }));
  const goSheet = (i) => {
    const el = document.getElementById("rr-sheet-" + (i + 1));
    if (!el) return;
    // Smooth is delightful across two sheets and disorienting across thirty — jumping
    // from the contents to sheet 36 is a 38,000px ride past everything the reader
    // deliberately skipped. Smooth when it is near, instant when it is not, and never
    // animated for a reader who has asked the system not to.
    const near = Math.abs(el.getBoundingClientRect().top) < window.innerHeight * 3;
    const still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollIntoView({ behavior: (near && !still) ? "smooth" : "auto", block: "start" });
    // and a brief cue on the sheet you landed on, so the eye knows where it arrived
    el.classList.remove("rr-landed");
    void el.offsetWidth;                       // restart the animation, not queue it
    el.classList.add("rr-landed");
  };

  // ---- deterministic defaults for the board-paper sections ------------------
  // Composed from the document's own figures, so they are instant, always grounded
  // and never wrong when AI is off — and every one of them is the EDITABLE default:
  // a director who wants different words replaces them in place.
  const askProse = () => {
    const n = theAsk.actions_this_cycle || 0;
    const areas = (theAsk.areas || []).map(domainLabel);
    if (!hasPosition) {
      return "The board is asked to approve the reward strategy set out in this document as the "
        + "organisation's stated position on pay, benefits and the wider package. It commits lumi to "
        + "reading every benchmark through it. No spending decision is being sought here: the position "
        + "against the market is not yet measured, and the plan that follows from it comes back to the "
        + "board once it is.";
    }
    if (!n) {
      return nGaps
        ? ("The board is asked to agree how the " + nGaps + " outstanding gap" + (nGaps === 1 ? "" : "s")
           + " in this review " + (nGaps === 1 ? "is" : "are") + " to be addressed. No action has yet "
           + "been scheduled for the current cycle, so this paper seeks a direction rather than an "
           + "approval: which of the options set out under each area are to be taken forward, and when.")
        : ("The board is asked to note this review and reaffirm the reward strategy as stated. The "
           + "organisation's own data currently sits in line with the position it has set, so no "
           + "corrective action is being sought.");
    }
    const cost = money.investment_to_p50_gbp
      ? ("Where lumi can price a change, the indicative cost of moving to the peer median is "
         + gbp(money.investment_to_p50_gbp) + " a year on the assumptions published in this document"
         + (nPriced < nGaps ? "; that figure covers " + nPriced + " of the " + nGaps + " gaps, and the "
            + "rest are changes lumi does not put a number against." : "."))
      : ("None of the actions below carries an indicative cost from lumi's model: their effect is on "
         + "retention, fairness and how the package reads rather than on a figure this document can state.");
    return "The board is asked to approve " + n + " action" + (n === 1 ? "" : "s")
      + " scheduled for this cycle" + (areas.length ? ", covering " + rrList(areas) : "")
      + ". " + (nGaps ? ("They are the first cycle of a response to " + nGaps + " gap"
        + (nGaps === 1 ? "" : "s") + " this review found between the strategy as stated and the "
        + "organisation's own benchmarked position. ") : "") + cost;
  };
  const costProse = () => {
    if (!nPriced) {
      return "lumi puts an indicative figure against a change only where its cost model has one for the "
        + "metric in question — employer pension contribution, attrition and agency spend. None of the "
        + (nGaps ? nGaps + " gaps in this review falls" : "gaps in this review fall") + " into that set, "
        + "so no aggregate cost is stated here. That is not the same as saying they are free: it means "
        + "their cost has to come from your own modelling rather than from a benchmark. "
        + ((money.unit_rates && (money.unit_rates.points || []).length)
           ? "The table below gives what a single percentage point of movement is worth on your "
             + "headcount, which is the multiplier that modelling needs."
           : "");
    }
    const parts = [];
    parts.push("Closing the gaps lumi can price to the peer median is an indicative "
      + gbp(money.investment_to_p50_gbp) + " a year"
      + (money.savings_to_p50_gbp ? ", against " + gbp(money.savings_to_p50_gbp)
         + " a year of indicative saving where you currently sit above the median" : "") + ".");
    parts.push("That envelope covers " + nPriced + " of the " + nGaps + " gap"
      + (nGaps === 1 ? "" : "s") + " in this review"
      + (nPriced < nGaps ? ": the remainder are changes lumi does not price, and their cost has to be "
         + "modelled by you rather than read off a benchmark." : "."));
    parts.push(money.fte_known
      ? "Figures use the midpoint of your stated FTE band and lumi's published salary and level-mix "
        + "assumptions. They are an order of magnitude for a board discussion, not a budget."
      : "Your FTE band is not recorded, so these figures rest on lumi's default headcount assumption. "
        + "Setting the band in your company details will sharpen them materially.");
    return parts.join(" ");
  };
  const worthProse = () => {
    const pts = (money.unit_rates || {}).points || [];
    const n = nGaps - nPriced;
    return (n > 0
      ? n + " of the " + nGaps + " gap" + (nGaps === 1 ? "" : "s") + " in this review "
        + (n === 1 ? "carries" : "carry") + " no price lumi can model — their effect is on "
        + "retention, fairness and how the package reads. "
      : "Where an action carries no price lumi can model, its effect is on retention, "
        + "fairness and how the package reads. ")
      + "That is true and, on its own, useless to a board weighing one against another. "
      + "lumi cannot say how much of that effect an action buys. It can say what a single "
      + "percentage point is worth on your own headcount" + (pts.length === 2 ? ", in the two "
      + "currencies those actions trade in" : "") + " — so the board weighs a change against a "
      + "number it already recognises.";
  };
  const risksProse = () => (risks.length
    ? "The exposures below are restatements of what this review found, not forecasts. Each names a "
      + "condition that is true of the organisation today and says what it bears on; none of them is a "
      + "recommendation, and how binding each one is stays a judgement for the board."
    : "This review found no condition in your data or your stated strategy that reads as a live exposure. "
      + "That is a statement about what lumi can see — affordability, delivery capacity and anything "
      + "outside the benchmark are not in its view.");
  const schedProse = () => {
    if (!schedule.length) return "No actions are scheduled yet.";
    const n = schedule.reduce((a, s) => a + s.actions.length, 0);
    const now = (schedule.find(s => s.horizon === "this cycle") || {}).actions || [];
    return n + " action" + (n === 1 ? "" : "s") + " across " + schedule.length + " horizon"
      + (schedule.length === 1 ? "" : "s") + ", sequenced by how quickly each one can realistically land. "
      + (now.length ? now.length + " " + (now.length === 1 ? "sits" : "sit") + " in the current cycle; "
         + "the rest are held deliberately, not deferred by omission."
         : "Nothing sits in the current cycle — every action here needs a longer runway than the "
           + "current review allows.");
  };
  const decProse = () => (decidedRows.length
    ? "Every option lumi offered against a gap is set out under its own area. The ones below carry a "
      + "recorded decision, so a reader a year from now can tell an option that was weighed and turned "
      + "down from one that was never considered."
    : "No decision has been recorded against any of the options in this document yet. Recording what was "
      + "turned down, and why, is what lets a future reader tell a considered rejection from an oversight.");
  const trendProse = () => (trend.available
    ? "Movement is measured against the previous collection window. A change in position can come from "
      + "your own package moving, from the peer group moving, or from both — the areas below say which."
    : "This is lumi's first aggregated collection window, so every figure in this document is a baseline "
      + "rather than a direction of travel. Whether a position is improving or slipping cannot be "
      + "evidenced until a second window closes, and nothing here should be read as a trend.");

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
      + ", on " + cnt.metrics + " benchmarked " + (cnt.metrics === 1 ? "metric" : "metrics")
      + (cnt.peer_n ? " with a median of " + cnt.peer_n.median + " peers behind each" : "") + ".");
    const parts = [];
    if (p.below) parts.push(p.below + " " + (p.below === 1 ? "sits" : "sit") + " below market");
    if (p.at) parts.push(p.at + " " + (p.at === 1 ? "sits" : "sit") + " on it");
    if (p.above) parts.push(p.above + " " + (p.above === 1 ? "sits" : "sit") + " above");
    if (parts.length) bits.push("Of those, " + rrList(parts) + ".");
    if (cnt.strict === false) {
      bits.push("That read is indicative rather than methodology-grade: it rests on "
        + cnt.metrics + " comparable " + (cnt.metrics === 1 ? "metric" : "metrics")
        + ", below the " + (cnt.domain_min || 3) + " this engine requires before it will call a domain verdict firm. "
        + "Treat the direction as a pointer and the position as provisional.");
    }
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
  const Body = ({ kindOf, items, part, parts, start, num, block, half, levSlice, levPart, levParts, ptId }) => {
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
        ${/* the metadata block a consultancy cover carries: who produced it, when, on
             what basis, and what may be done with it. No "Prepared for" row — the
             organisation's name is the hero line directly above, and naming it twice
             on one sheet reads as a mail-merge rather than a deliverable. */ ""}
        <div class="rr-cover-meta">
          <div><span>Prepared by</span>lumi${" "}·${" "}reward benchmarking</div>
          <div><span>Date of issue</span>${today}</div>
          <div><span>Document status</span>${ver
            ? "Version " + ver.version + ", approved" + (ver.approval_date ? " " + ver.approval_date : "")
            : "Draft — not yet approved"}</div>
          <div><span>Benchmark basis</span>${cutLabel}</div>
          <div><span>Data collection</span>${(al.snapshot || {}).window || "Current window"}${
            (al.snapshot || {}).date ? " · " + al.snapshot.date : ""}</div>
          ${doc.comparator_label && doc.comparator_label !== cutLabel
            ? html`<div><span>Stated comparator</span>${doc.comparator_label}</div>` : null}
          ${al.objective ? html`<div><span>Primary objective</span>${al.objective}</div>` : null}
          <div><span>Classification</span>Private ${"&"} confidential</div>
        </div>
      </div>`;

    // ---- PART DIVIDER -----------------------------------------------------------
    // Announces the part, says what it is for, and lists the sections inside it with
    // their page numbers — so a reader landing here knows what they are about to read
    // and can skip to the one section they came for.
    if (kindOf === "divider") {
      const P_ = RR_PART[ptId] || {};
      const inside = pages.map((p, i) => ({ p: p, n: i + 1 }))
        .filter(x => x.p.pt === ptId && !x.p.divider && x.p.title && !/\(cont\.\)$/.test(x.p.title));
      return html`
        <div class="rr-div-in">
          <div class="rr-div-k">Part ${ptId}</div>
          <h2 class="rr-div-t">${P_.title}</h2>
          <div class="rr-accent"></div>
          <p class="rr-div-lead">${P_.lead}</p>
          <div class="rr-div-list">
            ${inside.map(x => html`
              <button key=${x.n} type="button" class="rr-toc-row rr-jump"
                onClick=${() => goSheet(x.n - 1)}>
                <span><i>${SEC_NO[secKey(x.p)]}</i>${rrType(x.p.title)}</span><b>${x.n}</b>
              </button>`)}
          </div>
        </div>`;
    }

    if (kindOf === "exec") return html`
      <${RrH} n=${num} sub=${"The position, the ask and the basis, in one page. Everything asserted here is "
        + "set out in full and evidenced in the parts that follow."}>Executive summary<//>
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
      ${/* two columns: a per-domain report runs to ~25 sections and a single-column
           contents pushed this sheet past A4 (2026-08-16). Continuation sheets are
           dropped — a reader wants the section, not every sheet it spans. Grouped by
           part, because an ungrouped run of 25 lines is a list, not a map. */ ""}
      <div class="rr-toc">
        <div class="rr-toc-h">Contents</div>
        <div class="rr-toc-cols">
          ${/* the page number IS the sheet index (cover is sheet 1) — an extra +1 here
               once made every contents line point one page late, and the last entry
               point past the end of the document. */ ""}
          ${(() => {
            const rows = [];
            let curPt = null;
            pages.forEach((p, i) => {
              // Group on the PART BOUNDARY, not on the divider page. A part whose divider
              // was suppressed (one section long) still needs its heading here, or its
              // section renders nested under the previous part and reads as belonging to it.
              if (p.pt && p.pt !== curPt) {
                curPt = p.pt;
                rows.push({ kind: "part", id: p.pt, title: (RR_PART[p.pt] || {}).title, n: i + 1 });
              }
              if (p.divider) return;
              if (!p.title || /\(cont\.\)$/.test(p.title)) return;
              rows.push({ kind: "sec", no: SEC_NO[secKey(p)], title: p.title, n: i + 1, inPart: !!p.pt });
            });
            // buttons, not divs: a 41-sheet contents you cannot click is a tease on
            // screen. Styled as plain rows so the printed page is unchanged. (A plain
            // JS comment — this block is an arrow body, NOT a template literal, and an
            // htm-style ${/* … */} here is a syntax error that kills the whole file.)
            return rows.map((r, i) => r.kind === "part"
              ? html`<button key=${i} type="button" class="rr-toc-part rr-jump"
                  onClick=${() => goSheet(r.n - 1)}>
                  <span>Part ${r.id} — ${r.title}</span><b>${r.n}</b></button>`
              : html`<button key=${i} type="button" class=${"rr-toc-row rr-jump" + (r.inPart ? " is-in" : "")}
                  onClick=${() => goSheet(r.n - 1)}>
                  <span><i>${r.no}</i>${rrType(r.title)}</span><b>${r.n}</b></button>`);
          })()}
        </div>
      </div>`;

    // ---- THE STRATEGY, as narrative --------------------------------------------
    // Six sections across two sheets, each individually editable. This replaced four
    // template stubs ("The focus this year is winning talent.") that David rightly
    // called broken sentences — a strategy paper opens with purpose and philosophy,
    // not with captions.
    if (kindOf === "story1" || kindOf === "story2") {
      const P6 = (stm && stm.parts) || {};
      const S = [
        { k: "context", t: "Purpose and context" },
        { k: "philosophy", t: "Our reward philosophy" },
        { k: "positioning", t: "How we position against the market" },
        { k: "mix", t: "The shape of the package" },
        { k: "performance", t: "Performance and differentiation" },
        { k: "governance", t: "Transparency and governance" },
      ].slice(kindOf === "story1" ? 0 : 3, kindOf === "story1" ? 3 : 6);
      return html`
        <${RrH} n=${num} edit=${EditAt("phil", "Change the dials")}
          sub=${kindOf === "story1"
            ? "The strategy as the organisation states it. Every position here is a choice; nothing on these two pages is a measurement."
            : "Continued: how the package is shaped, how performance is differentiated, and how reward is governed and communicated."}>The strategy${kindOf === "story2" ? " (cont.)" : ""}<//>
        ${stm === null ? html`<p class="rr-p rr-muted">Writing the strategy narrative…</p>`
          : S.map(sec => html`
            <div key=${sec.k} class="rr-story">
              <h3 class="rr-sh">${sec.t}</h3>
              <${Prose} k=${sec.k} generated=${rrCase(P6[sec.k] || "")} />
            </div>`)}`;
    }

    if (kindOf === "dials") return html`
      <${RrH} n=${num} edit=${EditAt("phil", "Change the dials")} sub="Each dial below is a stated choice, not a measurement. The third column is what that choice changes in how every benchmark in this document is read.">How we position reward<//>
      <${RrEx} ex=${EXH["dials"]} />
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
              <td class="rr-sm">${v ? (RR_DRIVES[f] || SD_DRIVES[f] || "") : "Read neutrally."}</td>
            </tr>`; })}
        </tbody>
      </table>`;

    if (kindOf === "prin") {
      const cons = doc.constraints || {};
      return html`
        <${RrH} n=${num} edit=${EditAt("principles", "Edit principles")} sub="The statements this organisation holds itself to, the market it measures itself against, and the limits it has recorded on what it can change.">Principles, peers and constraints<//>
        <h3 class="rr-sh">Our reward principles</h3>
        ${(doc.principles || []).length
          ? html`<ol class="rr-ol">${(doc.principles || []).map((p, i) => html`<li key=${i}>${p}</li>`)}</ol>`
          : html`<p class="rr-p rr-muted">No separate set of reward principles has been written down.
              The positions stated in this document carry the philosophy in their place.</p>`}
        <h3 class="rr-sh">Who we compare ourselves to</h3>
        <p class="rr-p">${orgCompareWords(null, doc)}</p>
        <h3 class="rr-sh">What constrains us</h3>
        ${(cons.selected || []).length || cons.notes
          ? html`<p class="rr-p">${rrList((cons.selected || []).map(c => CONSTRAINT_LABEL[c] || c))}${cons.notes ? (((cons.selected || []).length ? ". " : "") + cons.notes) : ""}</p>`
          : html`<p class="rr-p rr-muted">No constraints have been recorded against this strategy.</p>`}`;
    }

    if (kindOf === "pops") return html`
      <${RrH} n=${num} edit=${EditAt("populations", "Edit levels")} sub="Stated positions for named groups. lumi holds no executive pay data, so these are never scored against the benchmark.">Position by employee population<//>
      <${RrEx} ex=${EXH["pops"]} />
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
      ${/* pointed at a "companion document" that this document became (2026-08-16) */ ""}
      ${wantsPlan ? null : html`
        <div class="rr-callout quiet">
          <div class="rr-callout-h">Where you stand against this</div>
          <p class="rr-p">Your live position against this strategy, the gaps it opens and the plan to
          close them are set out in the companion <b>Reward Position ${"&"} Plan</b> document.</p>
        </div>`}`;

    if (kindOf === "gov") return html`
      <${RrH} n=${num} sub="Who approved this strategy, when it takes effect, when it is next reviewed — and what was left unstated at the point of approval.">Governance and approval<//>
      <${RrEx} ex=${EXH["gov"]} />
      <table class="rr-table">
        <tbody>
          <tr><td>Status</td><td><b>${ver ? "Approved" : "Draft — not yet approved"}</b>${ver && ver.dirty ? html` <span class="rr-sm">(edits since approval)</span>` : ""}</td></tr>
          ${ver ? html`<tr><td>Version</td><td><b>${ver.version}</b></td></tr>` : null}
          ${/* a raw login email as "approved by" in a board paper reads as unfinished —
               prefer the recorded body, and mark a bare account as what it is */ ""}
          ${ver ? html`<tr><td>Approved by</td><td>${ver.approver_body
            || (ver.approved_by ? html`<span class="rr-sm">Recorded against the account ${ver.approved_by} — no approving body was named</span>` : "—")}</td></tr>` : null}
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
      const cntStrictFalse = (b.count || {}).strict === false;
      // computed OUTSIDE the template: htm's tokenizer cannot parse a spread inside ${}
      const _allLev = (b.options || []).reduce((a, o) => a.concat(o.levers || []), []);
      const levShown = levSlice ? _allLev.slice(levSlice[0], levSlice[1]) : _allLev;
      // a bare ">" inside ${} makes htm think the tag closed — compare outside the template
      const followSuffix = (!isRead && (levParts || 1) > 1)
        ? " (" + ((levPart || 0) + 1) + " of " + levParts + ")" : "";
      // a sheet carrying the read AND the follow explanation has room for one signal:
      // measured at two it ran 41px past A4 on Time off & family
      // an indicative domain also carries the thin-evidence caveat, which is prose and
      // cannot be trimmed — the signals table is what yields on a crowded sheet
      // three, not four: a signal row with wrapped detail runs ~80px, and a read sheet
      // also carries the stats, the split, the commentary and sometimes a caveat
      const _room = (inlineFollow ? 1 : 3) - (cntStrictFalse ? 1 : 0);
      const sigShown = (b.signals || []).slice(0, Math.max(1, _room));
      const pos = b.position || {};
      const aim = b.aim || {};
      const cnt = b.count || {};
      const total = (pos.below || 0) + (pos.at || 0) + (pos.above || 0);
      const pctOf = (v) => total ? Math.round((100 * (v || 0)) / total) : 0;
      const readWord = RR_ALIGN_WORD[aim.alignment];
      return html`
        ${/* every other content sheet in the document carries a deck; the eight
             "what follows" sheets carried none, which made them read as an overflow of
             the previous page rather than a section (2026-08-16 polish pass). Only the
             first sheet of a split run gets it, like every other run here. */ ""}
        <${RrH} n=${num} sub=${isRead
          ? "How " + domainLabel(b.name) + " sits against " + cutLabel + ", and what your strategy asks of it."
          : ((levPart || 0) > 0 ? null
             : (levShown.length
                ? "The gaps " + domainLabel(b.name) + " opens against your stated position, and the "
                  + "options the market commonly uses to close them — each with what it costs you elsewhere."
                : "The gaps " + domainLabel(b.name) + " opens against your stated position, and why lumi "
                  + "is not putting options against them here."))
          }>${domainLabel(b.name)}${isRead ? "" : " — what follows"}${followSuffix}<//>

        ${!isRead ? null : html`
        ${/* count + market position, side by side — the two facts a reader wants first */ ""}
        <div class="rr-dom-head">
          <div class="rr-dom-stat">
            <span class="rr-dom-k">Metrics benchmarked</span>
            <b>${cnt.metrics || 0}</b>
            ${/* the peer SAMPLE, not the org's own metric count — see the server note */ ""}
            <span class="rr-sm">${cnt.peer_n
              ? "typically " + cnt.peer_n.median + " peers per metric (" + cnt.peer_n.min + "–" + cnt.peer_n.max + ")"
              : "on your own data"}</span>
          </div>
          <div class="rr-dom-stat">
            <span class="rr-dom-k">Market position</span>
            <b class=${"rr-verdict v-" + (pos.verdict || "none")}>${RR_POS_WORD[pos.verdict] || "no read yet"}${
              cnt.strict === false ? html`<span class="rr-indic"> indicative</span>` : ""}</b>
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
          <${RrEx} ex=${EXH["dom-sig:" + b.name]} />
          <table class="rr-table tight">
            <thead><tr><th>Signal</th><th>Yours</th><th>Reads</th></tr></thead>
            <tbody>${sigShown.map(sg => html`
              <tr key=${sg.question_id || sg.title}>
                <td><b>${sg.title}</b>${sg.detail ? html`<br /><span class="rr-sm">${sg.detail}</span>` : ""}</td>
                <td class="rr-sm">${sg.value || "—"}</td>
                <td class="rr-sm">${RR_POS_WORD[sg.position] || sg.position || "—"}</td>
              </tr>`)}</tbody>
          </table>
          ${/* a below-market area whose only flagged signal reads above market looks, on a
               board page, like the evidence refuting the verdict. Say why it doesn't. */ ""}
          ${pos.verdict && sigShown.length && !sigShown.some(x => x.position === pos.verdict) ? html`
            <p class="rr-p rr-sm rr-muted">${"The signals above are the most material in "
              + domainLabel(b.name) + ", which is not the same as the most representative: none of "
              + "them happens to read " + RR_POS_WORD[pos.verdict] + ", while the area overall does. "
              + "The split at the top of this page is the fuller picture."}</p>` : null}` : null}`}

        ${isRead ? null : html`
          ${/* the sheet heading already names the domain and says "what follows";
               repeating it as an h3 underneath said the same thing twice */ ""}
          ${b.gaps.map(c => html`<p key=${c.id} class="rr-p">${rrCase(c.statement)}</p>`)}
          ${levShown.length ? html`
            <${RrEx} ex=${EXH["dom-opt:" + b.name + ":" + (levPart || 0)]} />
            <table class="rr-table tight">
              <thead><tr><th>Option</th><th>Cost</th><th>Speed</th><th>Trade-off</th></tr></thead>
              <tbody>${levShown.map(l => html`
                <tr key=${l.lever_id}><td><b>${l.name}</b><br /><span class="rr-sm">${l.what_it_is}</span>
                  ${/* the decision against this option, recorded in place — the table was a
                       menu with no record of what was chosen or turned down (2026-08-16) */ ""}
                  <${RrDecCell} cur=${decisions[decKey(b.name, l.lever_id)]} states=${DEC_STATES}
                    canEdit=${!!canEditDoc} onSave=${(s, w) => saveDecision(b.name, l.lever_id, s, w)} /></td>
                  <td class="rr-sm">${l.cost_character}</td><td class="rr-sm">${l.speed}</td>
                  <td class="rr-sm">${l.trade_off}</td></tr>`)}</tbody>
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
      <${RrEx} ex=${EXH["position"]} />
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
      ${/* the table above counts AREAS; this counts COMMITMENTS, and one area can carry
           several (its position plus any coherence rule that applies to it). Unlabelled,
           the two looked like the same arithmetic disagreeing with itself. */ ""}
      <div class="rr-stats">
        <div><b>${gaps.length}</b><span>commitments off strategy</span></div>
        <div><b>${holding.length}</b><span>commitments holding</span></div>
        <div><b>${unevid.length}</b><span>not yet evidenced</span></div>
      </div>
      <p class="rr-p rr-sm">The table counts the ${domains.length} areas lumi benchmarks. The figures
      beneath count commitments: an area carries one for the position your strategy sets, plus one for
      each coherence check that applies to it, so the two totals are different measures of the same
      picture.</p>`;

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
        ${part === parts - 1 ? html`<p class="rr-p rr-sm">${rrType(plan.basis)}${plan.built_at ? " Built " + fmtDate(plan.built_at) + "." : ""}</p>` : null}`
      : html`<p class="rr-p rr-muted">${planBusy
          ? "Sequencing your gaps into a plan…"
          : "No plan is stored yet. Use Rebuild plan above to sequence these gaps into actions with their indicative return."}</p>`}`;

    // ---- THE ASK ---------------------------------------------------------------
    // The structural difference between a report and a board paper: this one describes
    // a position, names a cost and requests a decision. Everything on it is derived
    // from the plan and the envelope; only the wording is the author's.
    if (kindOf === "ask") {
      const nowTitles = theAsk.titles || [];
      const rest = Math.max(0, (theAsk.gaps_total || 0) - nowTitles.length);
      return html`
        <${RrH} n=${num} sub="The decision this paper seeks, what it would cost, and what it deliberately leaves open.">What we're asking the board to approve<//>
        <div class="rr-ask">
          <div class="rr-ask-k">Decision sought</div>
          <div class="rr-ask-v">${rrCap(rrCase(theAsk.decision || "note this review"))}</div>
        </div>
        <${Prose} k="the_ask" className="rr-lede" generated=${askProse()} />
        ${hasPosition ? html`
          <div class="rr-stats">
            <div><b>${theAsk.actions_this_cycle || 0}</b><span>${(theAsk.actions_this_cycle === 1) ? "action this cycle" : "actions this cycle"}</span></div>
            <div><b>${money.investment_to_p50_gbp ? gbp(money.investment_to_p50_gbp) : "—"}</b><span>${money.investment_to_p50_gbp ? "indicative, a year" : "no priced cost"}</span></div>
            <div><b>${theAsk.gaps_total || 0}</b><span>${(theAsk.gaps_total === 1) ? "gap in scope" : "gaps in scope"}</span></div>
          </div>` : null}
        ${nowTitles.length ? html`
          <h3 class="rr-sh">What approval covers</h3>
          <ul class="rr-ul">${nowTitles.map((t, i) => html`<li key=${i}>${t}</li>`)}</ul>` : null}
        ${rest ? html`
          <h3 class="rr-sh">What it does not cover</h3>
          <p class="rr-p">${"The remaining " + rest + " gap" + (rest === 1 ? "" : "s")
            + " in this review " + (rest === 1 ? "is" : "are") + " set out under "
            + (rest === 1 ? "its own area" : "their own areas") + " with the options against "
            + (rest === 1 ? "it" : "them") + ", and " + (rest === 1 ? "is" : "are")
            + " not part of this approval. They are held deliberately, not overlooked — the "
            + "schedule says when each one is expected to come back."}</p>` : null}`;
    }

    // ---- MOVEMENT ---------------------------------------------------------------
    // Not buildable until a second collection window closes. The section exists so the
    // document is honest about that now, and fills itself the moment one lands, rather
    // than the gap being discovered by whoever asks whether things are improving.
    if (kindOf === "trend") return html`
      <${RrH} n=${num} sub=${trend.available
        ? "How each area has moved since the previous collection window."
        : "Whether these positions are improving or slipping, and why that cannot yet be answered."}>Movement since the last review<//>
      ${/* its OWN key: "watch" belongs to the Tensions section, and sharing it meant
           editing one section silently rewrote the other */ ""}
      <${Prose} k="movement" className="rr-lede" generated=${trendProse()} />
      ${trend.available ? html`
        <${RrEx} ex=${EXH["trend"]} />
        <table class="rr-table">
          <thead><tr><th>Area</th><th>Then</th><th>Now</th><th>Movement</th></tr></thead>
          <tbody>${domains.map(d => html`
            <tr key=${d.name}><td>${domainLabel(d.name)}</td>
              <td>—</td><td>${RR_POS_WORD[(d.position || {}).verdict] || "no read"}</td>
              <td class="rr-sm">first comparable window</td></tr>`)}</tbody>
        </table>`
      : html`
        <div class="rr-empty-note">
          <h3 class="rr-sh">What will appear here</h3>
          <p class="rr-p">${"Once a second collection window is aggregated, this page carries each area’s "
            + "position then and now, and separates the two reasons a position can change: your own "
            + "package moving, or the peer group moving around you. Both matter to a board and they "
            + "are routinely confused."}</p>
          ${al.snapshot ? html`<p class="rr-p rr-sm">${"The current window is "
            + (al.snapshot.window || "the latest collection")
            + (al.snapshot.date ? ", dated " + al.snapshot.date : "")
            + ". Everything in this document is measured against it."}</p>` : null}
        </div>`}`;

    // ---- THE SCHEDULE ----------------------------------------------------------
    if (kindOf === "sched") return html`
      <${RrH} n=${num} sub=${first ? "The same actions as the section that follows, grouped by when each one can realistically land." : null}>The schedule${contd}<//>
      ${first ? html`<${Prose} k="schedule" className="rr-lede" generated=${schedProse()} />` : null}
      ${/* ONE table with horizon row-groups, not one table per horizon: three stacked
           tables with three headers repeated the column names three times and read as
           three exhibits rather than one schedule (2026-08-16 polish pass). */ ""}
      <${RrEx} ex=${EXH["sched:" + part]} />
      <table class="rr-table tight rr-sched-tbl">
        <thead><tr><th>Action</th><th>Area</th><th>Return</th></tr></thead>
        ${(items || []).map(s => html`
          <tbody key=${s.horizon}>
            <tr class="rr-hz-row"><th colSpan="3">
              <span class=${"rr-hz h-" + s.horizon.replace(/[^a-z]/g, "")}>${rrCap(s.horizon)}</span>
              <i>${s.actions.length} ${s.actions.length === 1 ? "action" : "actions"}</i></th></tr>
            ${s.actions.map((a, i) => html`
              <tr key=${i}><td><b>${a.title}</b></td>
                <td class="rr-sm">${domainLabel(a.category || "")}${SEC_NO["domain:" + a.category]
                  ? " (§" + SEC_NO["domain:" + a.category] + ")" : ""}</td>
                <td class="rr-sm">${a.roi}</td></tr>`)}
          </tbody>`)}
      </table>
      ${(items || []).find(s => s.horizon === "unscheduled") ? html`
        <p class="rr-p rr-sm rr-muted">${"Actions shown as unscheduled carry a timing lumi could not "
          + "place against a cycle. They are listed rather than dropped — an action missing from a "
          + "schedule is worse than one the schedule admits it cannot place."}</p>` : null}`;

    // ---- WHAT IT COSTS ---------------------------------------------------------
    // The aggregate has existed in the engine since the board pack was built and never
    // appeared on the document that goes to a board — so the first question a finance
    // director asks of it had no answer on the page (2026-08-16).
    if (kindOf === "cost") return html`
      <${RrH} n=${num} sub=${"What closing these gaps costs, as far as lumi can price it on " + cutLabel + "."}>What it costs<//>
      <div class="rr-stats">
        <div><b>${money.investment_to_p50_gbp ? gbp(money.investment_to_p50_gbp) : "—"}</b><span>indicative investment, a year</span></div>
        <div><b>${money.savings_to_p50_gbp ? gbp(money.savings_to_p50_gbp) : "—"}</b><span>indicative saving, a year</span></div>
        <div><b>${nPriced} of ${nGaps}</b><span>${nGaps === 1 ? "gap priced" : "gaps priced"}</span></div>
      </div>
      <${Prose} k="cost" generated=${costProse()} />
      ${(money.items || []).length ? html`
        <h3 class="rr-sh">Where the figure comes from</h3>
        <${RrEx} ex=${EXH["cost"]} />
        <table class="rr-table tight">
          <thead><tr><th>Metric</th><th>Area</th><th class="num">To median</th><th class="num">To upper quartile</th></tr></thead>
          <tbody>${(money.items || []).map(it => html`
            <tr key=${it.label}><td><b>${it.label}</b><br /><span class="rr-sm">${it.formula}</span></td>
              <td class="rr-sm">${domainLabel(it.category || "")}</td>
              <td class="num">${gbp(it.to_p50_gbp)}${it.direction === "saving" ? html` <span class="rr-sm">saving</span>` : ""}</td>
              <td class="num rr-sm">${gbp(it.to_p75_gbp)}</td></tr>`)}</tbody>
        </table>` : null}
      ${(money.assumptions && Object.keys(money.assumptions).length) ? html`
        <h3 class="rr-sh">The assumptions behind it</h3>
        <p class="rr-p rr-sm">${"Median salary " + gbp((money.assumptions || {}).median_salary_gbp)
          + " · cost per leaver " + ((money.assumptions || {}).cost_per_leaver_pct_salary || 0)
          + "% of salary · agency premium " + ((money.assumptions || {}).agency_premium_pct || 0)
          + "% · headcount from your stated FTE band. Change any of these in your company details and "
          + "every figure above moves with it."}</p>` : null}`;

    // ---- WHAT A POINT IS WORTH -------------------------------------------------
    // Its own section, not a block under "What it costs": it is a different idea
    // (sensitivity, not cost), it earns a contents entry, and together the two ran
    // 41px past A4 on one sheet.
    if (kindOf === "worth") return html`
      <${RrH} n=${num} sub="What a single percentage point of movement is worth on your headcount — the multiplier for the actions lumi cannot price.">What a point is worth<//>
      <${Prose} k="worth" className="rr-lede" generated=${worthProse()} />
      <${RrEx} ex=${EXH["worth"]} />
      <table class="rr-table tight">
        <thead><tr><th>Move</th><th class="num">Worth, a year</th><th>How it is worked out</th></tr></thead>
        <tbody>${((money.unit_rates || {}).points || []).map(pt => html`
          <tr key=${pt.key}><td><b>${pt.label}</b></td>
            <td class="num">${gbp(pt.gbp)}</td>
            <td class="rr-sm">${pt.formula}</td></tr>`)}</tbody>
      </table>
      ${(money.unit_rates || {}).basis ? html`<p class="rr-p rr-sm rr-muted">${"These rates are "
        + money.unit_rates.basis + "."}</p>` : null}
      <p class="rr-p rr-sm">${"lumi does not say how many points any action buys — that would be a "
        + "prediction about your organisation it has no basis for. It states the arithmetic of one "
        + "point; the judgement about how many an action is worth stays with the board."}</p>`;

    // ---- RISKS -----------------------------------------------------------------
    // Exposures restated from what the engine found, never predictions and never advice
    // — a risk section is the easiest place in a non-directive document to start giving
    // instructions by accident.
    if (kindOf === "risks") return html`
      <${RrH} n=${num} sub=${first ? "What this review found that bears on delivery, affordability or the strength of the evidence." : null}>Risks and exposures${contd}<//>
      ${first ? html`<${Prose} k="risks" className="rr-lede" generated=${risksProse()} />` : null}
      ${(items || []).map(r => html`
        <div key=${r.id} class="rr-risk">
          ${/* engine strings carry raw category names ("Incentives & Recognition");
               every other line on the sheet uses the house sentence case */ ""}
          <div class="rr-risk-h"><span class="rr-risk-c">${r.class}</span>${rrCase(r.title)}</div>
          <p class="rr-p">${rrCase(r.detail)}</p>
        </div>`)}
      ${/* the caveat belongs once, on the last sheet of the run — not under every chunk */ ""}
      ${part !== parts - 1 ? null : html`
        <p class="rr-p rr-sm rr-muted">${"lumi can only name exposures its own data shows. Anything outside "
          + "the benchmark — delivery capacity, employee relations, what a competitor is about to do — is "
          + "not in view here and its absence is not evidence of its absence."}</p>`}`;

    // ---- DECISIONS NOT TAKEN ---------------------------------------------------
    if (kindOf === "decided") return html`
      <${RrH} n=${num} sub=${first ? "The record of what was weighed and what was turned down, so a later reader can tell a considered rejection from an oversight." : null}>Decisions taken and not taken${contd}<//>
      ${first ? html`<${Prose} k="decisions" className="rr-lede" generated=${decProse()} />` : null}
      <${RrEx} ex=${EXH["decided:" + part]} />
      <table class="rr-table">
        <thead><tr><th>Option</th><th>Area</th><th>Decision</th><th>Reason given</th></tr></thead>
        <tbody>${(items || []).map(r => html`
          <tr key=${r.k}>
            <td><b>${r.lever.name}</b></td>
            <td class="rr-sm">${domainLabel(r.cat)}</td>
            <td><span class=${"rr-dec d-" + r.dec.state}>${DEC_STATES[r.dec.state] || r.dec.state}</span>
              <br /><span class="rr-sm">${r.dec.at || ""}${r.dec.by ? " · " + r.dec.by : ""}</span></td>
            <td class="rr-sm">${r.dec.reason || "No reason recorded."}</td>
          </tr>`)}</tbody>
      </table>`;

    if (kindOf === "method") return html`
      <${RrH} n=${num} sub="How every figure in this document was produced, what it rests on, and what it deliberately does not claim.">Method and basis<//>
      ${/* keep the ${} on the SAME line as the words before it — htm collapses a newline
           before an expression and printed "rests on55 of the 77 questions" */ ""}
      ${al.completeness ? html`<p class="rr-p"><b>How complete this is.</b>
      ${"This document rests on " + al.completeness.answered + " of the " + al.completeness.of
        + " questions lumi treats as the core set (" + al.completeness.pct + "%). Areas answered thinly "
        + "carry an indicative read, marked as such in their own section; unanswered ones say so "
        + "rather than being estimated."}</p>` : null}
      ${al.snapshot ? html`<p class="rr-p"><b>Data vintage.</b>
      ${"Peer figures are the " + (al.snapshot.window || "current") + " collection"
        + (al.snapshot.date ? ", dated " + al.snapshot.date : "")
        + ". Your own answers are as you last saved them; where any are due a refresh, Your data says so."}</p>` : null}
      <p class="rr-p">Positions are computed from your own submitted data against <b>${cutLabel}</b>, on the
      same engine and the same suppression rules that govern every figure in lumi. Alignment is reported as
      counts against the commitments your strategy makes — never as a score, index or grade.</p>
      <p class="rr-p">Where a commitment’s evidence is unanswered, this document says so rather than
      estimating: ${unevid.length} commitment${unevid.length === 1 ? " sits" : "s sit"} unevidenced today.
      Indicative figures come from lumi’s cost model on its published assumptions, and appear only where that
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
          ${/* reading position + jump — its own component, so scrolling never
               re-renders the document behind it */ ""}
          <${RrNav} items=${navItems} total=${TOTAL} onGo=${goSheet} />
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
          divider=${p.divider}
          head=${p.cover || p.divider ? null : {
            left: K.title + " · " + orgName,
            right: p.pt ? "Part " + p.pt + " · " + (RR_PART[p.pt] || {}).title : rrType(p.title || "") }}
          prov=${i === TOTAL - 1 ? prov : null}>
          <${Body} kindOf=${p.body} items=${p.items} part=${p.part} parts=${p.parts} start=${p.start} num=${SEC_NO[secKey(p)]} block=${p.block} half=${p.half} levSlice=${p.levSlice} levPart=${p.levPart} levParts=${p.levParts} ptId=${p.pt} />
        <//>`)}
    </div>`;
};
