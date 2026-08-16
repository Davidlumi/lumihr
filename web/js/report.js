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
// The signal builder renders a percentile as "P14" — lumi's own shorthand, fine in the
// app and not English anywhere near a board table. Everything else in that column is a
// real value ("1×", "£2,400"), so only the shorthand is translated (2026-08-16).
function rrSignalValue(v) {
  const m = /^P(\d{1,3})$/.exec(String(v || "").trim());
  return m ? rrOrdinal(Number(m[1])) + " percentile" : (v || "—");
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
          ${/* neutral page mark — the vendor's name ran in every footer of the
               member's own board paper (external review 2026-08-16). The print
               verifier's FOOT_RE matches this exact form; change them together. */ ""}
          <span class="pack-pageno">Page ${page} of ${total}</span>
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

// ---- CARDS ---------------------------------------------------------------------
// The reference (LUMI_Future_of_Reward_2035_Report_V3) builds every page out of cards
// on a tinted ground: white cards carry evidence, a cream card carries the "so what",
// and a small-caps pill labels each one. This document was a white paper — single
// column, prose and tables — which is why charts alone did not make it read as a
// consultancy deliverable (2026-08-16).
function RrCard({ label, head, tone, children, className }) {
  return html`
    <div class=${"rr-card" + (tone ? " t-" + tone : "") + (className ? " " + className : "")}>
      ${label ? html`<div class="rr-card-k">${label}</div>` : null}
      ${head ? html`<div class="rr-card-h">${rrTypeAny(head)}</div>` : null}
      ${children}
    </div>`;
}

// A figure, what it is, and where it came from — the reference cites a source under
// every number, which is most of why its stats read as evidence rather than decoration.
function RrStats({ items }) {
  return html`
    <div class="rr-statgrid">
      ${items.filter(Boolean).map((x, i) => html`
        <div key=${i} class="rr-statcard">
          <b class=${x.tone ? "rrst-" + x.tone : ""}>${x.v}</b><span>${x.k}</span>${x.note ? html`<i>${x.note}</i>` : null}
        </div>`)}
    </div>`;
}

// The reference's mechanism device: a navy band of chevron steps. Used once, on the
// ask page, to show what approval sets in motion — the loop is lumi's actual model,
// so this is the one diagram the document can draw without inventing anything.
function RrFlow({ steps }) {
  return html`
    <div class="rr-flowband">
      ${steps.map((st, i) => html`
        <div key=${i} class="rr-flowstep">
          <b>${st.t}</b><span>${st.d}</span>
        </div>`)}
    </div>`;
}

// ---- CHARTS ------------------------------------------------------------------
// David, 2026-08-16: "I still do not think this is big 4 consultancy standard." He was
// right, and the largest single reason was that forty-one pages of benchmarking carried
// no chart at all — the document ASSERTED "around the 30th percentile" in prose and
// never showed it. A reward report from WTW or Mercer is chart-led, because a position
// against the market is a picture before it is a sentence.
//
// Pure SVG from data already on the payload; nothing here computes a new fact. The
// shaded band is the engine's OWN market band, passed through, so the picture cannot
// disagree with the verdict printed beside it.
const RR_SCALE = { w: 640, pad: 26 };

function rrX(pct) {
  const inner = RR_SCALE.w - RR_SCALE.pad * 2;
  return RR_SCALE.pad + (Math.max(0, Math.min(100, pct)) / 100) * inner;
}

// The axis furniture every percentile chart in the document shares — quartile ticks,
// the "on market" band, and the baseline. Drawn once per chart, identical every time,
// so two charts on different pages are read on the same ruler.
function RrAxis({ band, y, h, ticks }) {
  const lo = (band && band[0]) || 40, hi = (band && band[1]) || 60;
  return html`
    <g>
      <rect x=${rrX(lo)} y=${y} width=${rrX(hi) - rrX(lo)} height=${h}
        class="rrc-band" />
      ${(ticks === false ? [] : [10, 25, 50, 75, 90]).map(t => html`
        <line key=${t} x1=${rrX(t)} x2=${rrX(t)} y1=${y} y2=${y + h} class="rrc-tick" />`)}
      <line x1=${rrX(0)} x2=${rrX(100)} y1=${y + h} y2=${y + h} class="rrc-base" />
    </g>`;
}

function RrAxisLabels({ y }) {
  return html`
    <g class="rrc-lab">
      ${[[10, "10th"], [25, "25th"], [50, "median"], [75, "75th"], [90, "90th"]].map(([t, l]) => html`
        <text key=${t} x=${rrX(t)} y=${y} text-anchor="middle">${l}</text>`)}
    </g>`;
}

// ONE DOMAIN: where this area sits on the percentile scale, with the split behind it.
function RrDomainChart({ pctl, verdict, band, stance, label }) {
  // top 26, not 16: the marker's own label sits ABOVE the bar and was being clipped
  // by the viewBox at "30th" (2026-08-16)
  const H = 100, top = 26, barH = 30;
  const has = pctl != null;
  return html`
    <svg class="rrc" viewBox=${"0 0 " + RR_SCALE.w + " " + H} role="img"
      aria-label=${has ? label + " sits around the " + Math.round(pctl) + "th percentile of the peer group"
                       : label + " has no market position yet"}>
      <${RrAxis} band=${band} y=${top} h=${barH} />
      ${has ? html`
        <g>
          <rect x=${rrX(0)} y=${top} width=${rrX(pctl) - rrX(0)} height=${barH}
            class=${"rrc-fill v-" + (verdict || "none")} />
          <line x1=${rrX(pctl)} x2=${rrX(pctl)} y1=${top - 6} y2=${top + barH + 6}
            class="rrc-you" />
          <text x=${rrX(pctl)} y=${top - 10} text-anchor="middle" class="rrc-youlab"
            >${rrOrdinal(pctl)}</text>
        </g>`
      : html`<text x=${RR_SCALE.w / 2} y=${top + barH / 2 + 4} text-anchor="middle"
          class="rrc-none">not enough comparable data to place this area</text>`}
      <${RrAxisLabels} y=${top + barH + 20} />
    </svg>`;
}

// THE PORTFOLIO: every area on one ruler. This is the page a reward director turns to
// first and the one the document did not have — eight verdicts in prose across fifteen
// sheets, and no way to see them together.
// A label gutter, so the chart names its own rows. The first version left them
// unlabelled and relied on a table beneath being in the same order — which a reader
// cannot verify and an edit could silently break. Naming them here let the table go
// entirely, which is also what stopped this sheet overflowing in print.
const RR_PORT = { w: 640, lab: 196, pad: 18 };
function rrPX(pct) {
  const inner = RR_PORT.w - RR_PORT.lab - RR_PORT.pad;
  return RR_PORT.lab + (Math.max(0, Math.min(100, pct)) / 100) * inner;
}

function RrPortfolioChart({ rows, band }) {
  const rowH = 38, top = 18;
  const H = top + rows.length * rowH + 28;
  const lo = (band && band[0]) || 40, hi = (band && band[1]) || 60;
  const bodyH = rows.length * rowH;
  return html`
    <svg class="rrc rrc-port" viewBox=${"0 0 " + RR_PORT.w + " " + H} role="img"
      aria-label="Market position of every area on one percentile scale">
      <rect x=${rrPX(lo)} y=${top} width=${rrPX(hi) - rrPX(lo)} height=${bodyH} class="rrc-band" />
      ${[10, 25, 50, 75, 90].map(t => html`
        <line key=${t} x1=${rrPX(t)} x2=${rrPX(t)} y1=${top} y2=${top + bodyH} class="rrc-tick" />`)}
      <line x1=${rrPX(0)} x2=${rrPX(100)} y1=${top + bodyH} y2=${top + bodyH} class="rrc-base" />
      ${rows.map((r, i) => {
        const cy = top + i * rowH + rowH / 2;
        return html`
          <g key=${r.name}>
            <text x=${RR_PORT.lab - 12} y=${cy + 4} text-anchor="end" class="rrc-rowlab">${r.label}</text>
            <line x1=${rrPX(0)} x2=${rrPX(100)} y1=${cy} y2=${cy} class="rrc-rowline" />
            ${r.aim != null ? html`
              <path d=${"M " + (rrPX(r.aim) - 4.5) + " " + (cy - 9) + " L " + (rrPX(r.aim) + 4.5) + " " + (cy - 9)
                        + " L " + rrPX(r.aim) + " " + (cy - 2.5) + " Z"} class="rrc-aim" />` : null}
            ${r.pctl != null ? html`
              <circle cx=${rrPX(r.pctl)} cy=${cy} r="6" class=${"rrc-dot v-" + (r.verdict || "none")} />`
            : html`<text x=${rrPX(50)} y=${cy + 3.5} text-anchor="middle" class="rrc-none">no read yet</text>`}
          </g>`;
      })}
      <g class="rrc-lab">
        ${[[10, "10th"], [25, "25th"], [50, "median"], [75, "75th"], [90, "90th"]].map(([t, l]) => html`
          <text key=${t} x=${rrPX(t)} y=${top + bodyH + 18} text-anchor="middle">${l}</text>`)}
      </g>
    </svg>`;
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

// the model's per-finding caveat, stripped at render and stated once per page
const RR_FRAMING_RE = /Organisations in this position often size up[^.]*\.\s*(A starting point, not advice\.)?\s*/gi;
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
  // one commitment's levers are ALTERNATIVES — the panel caught both pension options
  // scheduled and counted as two actions. Map lever name -> commitment so the render
  // can say so wherever the plan lists them.
  const altOf = {}, costOf = {}, descOf = {};
  (al.options || []).forEach(o => (o.levers || []).forEach(l => {
    if (l.name && !(l.name in altOf)) altOf[l.name] = o.commitment_id;
    if (l.name && !(l.name in costOf)) costOf[l.name] = l.cost_character;
    // D032 (v3.1): the LIVE description, so the plan can never render reward content
    // the library has since corrected. A stored plan built before the 2026-08-16
    // salary-sacrifice repair still carried the pre-OpRA wording — "pension, cars,
    // technology" — three pages after the section that says those lost the advantage.
    // Stored prose about reward facts is the defect class; this closes it.
    if (l.name && !(l.name in descOf)) descOf[l.name] = l.what_it_is;
  }));
  // Alternative SETS, computed ONCE over the whole schedule (2026-08-16 ship gate):
  // the intro counted set-mates across horizons while the table flagged only within
  // one, so the document said "7 are alternatives" over rows carrying 3 flags. Both
  // surfaces now read this one title-keyed map.
  const altInfo = (() => {
    const src = [];
    schedule.forEach(s => (s.actions || []).forEach(a2 => src.push({ title: a2.title, hz: s.horizon, idx: src.length })));
    if (!src.length) (((plan || {}).actions) || []).forEach(a2 => src.push({ title: a2.title, hz: a2.horizon_bucket, idx: src.length }));
    const byG = {};
    src.forEach(x => { const g = altOf[x.title]; if (g) (byG[g] = byG[g] || []).push(x); });
    const m = {};
    Object.values(byG).forEach(list => {
      if (list.length < 2) return;
      list.forEach(x => {
        m[x.title] = { size: list.length,
                       now: list.filter(y => y.title !== x.title && y.hz === x.hz).map(y => y.title),
                       // mates ABOVE this row in the same cycle — the flag rides the
                       // later row only, as the table always has (flagging both members
                       // doubled the sub-lines and spilled the next-cycle sheet)
                       nowPrior: list.filter(y => y.hz === x.hz && y.idx < x.idx).map(y => y.title) };
      });
    });
    return m;
  })();
  // the row-level flag names the SAME-CYCLE either/or — the un-minutable case; the
  // cross-cycle membership is stated once under the schedule, not on every row
  const altNote = (title) => {
    const i = altInfo[title];
    if (!i || !i.nowPrior.length) return null;
    // terse on purpose: the long form ("alternative to X — one of the two, not both")
    // wrapped twice in the schedule's action column and spilled the next-cycle sheet
    return "either/or with " + rrList(i.nowPrior) + " — one of the "
      + (i.nowPrior.length === 1 ? "two" : String(i.nowPrior.length + 1));
  };
  // this cycle's actions grouped into DECISION UNITS: options against the same gap
  // are one choice, not separate approvals. The server sends the grouping; the
  // fallback derives it so an older cached payload cannot regress the ask.
  const askUnits = (theAsk.decision_units && theAsk.decision_units.length)
    ? theAsk.decision_units
    : (() => { const g = {}, u = []; (theAsk.titles || []).forEach(t => {
        const k = altOf[t] || ("t:" + t);
        if (g[k]) g[k].titles.push(t); else { g[k] = { titles: [t] }; u.push(g[k]); }
      }); return u; })();
  const askChoices = askUnits.filter(u => (u.titles || []).length > 1).length;
  // ONE shape for the ask, read by the banner, both stat cards, the lede and the
  // flow strip. They had drifted: the banner said "re-approve … then approve the 3
  // actions", the stat cards counted 4 (option ROWS, not decisions) and the lede
  // mentioned no re-approval at all (QA v2, D014). A decision unit resolves to one
  // action; the extra rows are alternatives inside it.
  const askActs = askUnits.length || theAsk.actions_this_cycle || 0;
  const askRows = (theAsk.titles || []).length || theAsk.actions_this_cycle || 0;
  // askTwoPart lives with hasPosition, further down — a const referenced above its
  // own declaration is a temporal-dead-zone throw that blanks the whole document.
  const askNote = ((theAsk.areas || []).map(domainLabel).join(", ") || "none scheduled")
    + (askRows > askActs ? " — from " + askRows + " options, "
       + (askChoices === 1 ? "one either/or" : askChoices + " either/ors") : "");
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

  const mband = al.market_band || [40, 60];
  // A stated aim is a WORD ("lead"); the chart needs a point on the ruler. These are
  // the midpoints of what each word means against the engine's own market band — a
  // marker, not a target lumi is asserting.
  const RR_AIM_PCT = { lag: (mband[0] / 2), match: (mband[0] + mband[1]) / 2,
                       lead: mband[1] + (100 - mband[1]) / 2 };

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
  // TWO short sections on one sheet. Only ever called for a named, adjacent pair in the
  // SAME part — so the running head is unambiguous — and never for a continuation. Both
  // keep their own number and their own contents line, both pointing at this sheet.
  // This is the one place the one-section-per-sheet model bends, and it bends by hand:
  // an automatic packer would have to guess print heights, which is how the page count
  // came to lie in the first place.
  const P2 = (t1, b1, t2, b2) => pages.push({
    title: t1, body: b1, title2: t2, body2: b2, pt: curPt, paired: true });
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
    const _hasPrin = (doc.principles || []).length || doc.comparator_cut != null
      || ((doc.constraints || {}).selected || []).length || (doc.constraints || {}).notes;
    if ((doc.population_targets || []).length) {
      if (_hasPrin) P("Principles, peers and constraints", "prin");
      P("Position by employee population", "pops");
      P("Tensions and what to watch", "tension");
    } else if (_hasPrin && !commitments.some(c => c.status === "contradicted")) {
      // measured at 40% and 34% full on their own sheets — together they make one page.
      // NOT when §06 carries contradiction rows (D048, v3.1): routing the register's
      // contradictions into Tensions is what finally gives that section a tension, and
      // it is more content than the shared sheet holds. The pairing is an emptiness
      // optimisation, so it yields the moment either section has something to say.
      P2("Principles, peers and constraints", "prin", "Tensions and what to watch", "tension");
    } else {
      if (_hasPrin) P("Principles, peers and constraints", "prin");
      P("Tensions and what to watch", "tension");
    }
  }
  // No position read yet (a new org states its strategy BEFORE its data): the whole
  // position half collapses to one honest page rather than drawing an empty table,
  // tiles that say "0 off strategy", and a plan CTA the lock would refuse.
  const dstate = al.data_state || {};
  const hasPosition = (dstate.positioned || domains.length) > 0 && dstate.unlocked !== false;
  // the ask is two-part when the strategy has been amended since approval: the
  // board re-approves the strategy the gaps are measured against, THEN approves the
  // actions. Declared here because it reads hasPosition (QA v2, D014).
  const askTwoPart = !!(ver && ver.dirty && hasPosition && askActs);
  if (wantsPlan && !hasPosition) {
    PART("B");
    P("Where you'll stand", "awaiting");
  } else if (wantsPlan) {
    PART("B");
    P("Position at a glance", "position");
    // THE REGISTER (external review 2026-08-16): the whole paper rests on "13
    // commitments, 10 off, 3 holding" and no page enumerated them — a board cannot
    // reconcile a headline count it is never shown. One row per commitment.
    if (commitments.length) Prun("The commitments in full", "register", commitments, () => 1, 9);
    // Movement only earns its own page once a second collection window exists. Until
    // then it is one honest card on the Position page — a full page of "what will
    // appear here" was dead weight in a client paper (2026-08-16 panel, 3 reviewers).
    if (trend.available) P("Movement since the last review", "trend");
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
      // deduped: one lever offered against two commitments is ONE option to a reader,
      // and printing it twice cost the document its credibility (2026-08-16 panel)
      const _seenLev = new Set();
      const allLev = (b.options || []).flatMap(o => (o.levers || []))
        .filter(l => !_seenLev.has(l.lever_id) && _seenLev.add(l.lever_id));
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
    // splits at a sheet boundary instead of running past A4.
    // Groups pre-split at FOUR actions (2026-08-16 ship gate): a RETURN cell is model
    // prose whose length moves between plan rebuilds, and a five-action group weighed
    // by row count alone overran its sheet when the rebuilt plan wrote longer return
    // lines. Four rows always fit; a continued group re-prints its horizon header.
    const schedItems = [];
    schedule.forEach(s => {
      for (let k = 0; k < s.actions.length; k += 4)
        schedItems.push({ horizon: s.horizon, actions: s.actions.slice(k, k + 4),
                          contPart: k / 4, totalN: s.actions.length });
    });
    if (schedItems.length) Prun("The schedule", "sched", schedItems, (s) => 1 + s.actions.length, 6);
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
    Prun("Risks and exposures", "risks", risks, () => 2, 8);
    // the not-taken record grows with every decision an author makes — unbounded by
    // nature, so it chunks like every other run in this document
    if (decidedRows.length) Prun("Decisions taken and not taken", "decided", decidedRows, () => 1, 8);
  }
  PART("D");

  // ONE sheet again. It was split in two while chasing the last-page spill, on the
  // theory that the provenance line made it too tall — but the actual cause was
  // .rr-wrap's padding printing after the final sheet. With that fixed the split was a
  // workaround for a bug that no longer exists, and it was costing two half-empty
  // pages at the back of the document (2026-08-16).
  // NOT paired. Governance (36% full) and Method (38%) look like an obvious pair and
  // are not: Method is the last sheet, so it also carries the provenance line, and the
  // three together run past A4. The verifier caught it on the first render — which is
  // the whole point of measuring the PDF instead of guessing (2026-08-16).
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
  const _num = (k) => { if (!(k in SEC_NO)) SEC_NO[k] = ("0" + (++_sn)).slice(-2); };
  pages.forEach(p => {
    if (p.body === "cover" || p.body === "divider") return;
    _num(secKey(p));
    if (p.body2) _num(p.body2);          // a paired sheet numbers BOTH its sections
  });

  // ---- EXHIBITS -------------------------------------------------------------------
  // Numbered by a walk of the FINISHED page list, in the order the sheets render, so a
  // section added anywhere renumbers everything after it automatically. A number
  // written into a caption by hand is wrong the first time someone inserts a
  // section above it. (No literal exhibit number appears in this file — gated.)
  const EXH = {};
  let _exn = 0;
  const exReg = (k, cap) => { if (!(k in EXH)) EXH[k] = { n: ++_exn, cap: cap }; };
  const exWalk = (p, body) => {
    const b = p.block || {};
    switch (body) {
      case "dials": exReg("dials", "Stated reward positions, and what each one changes in how the benchmark is read"); break;
      case "pops": exReg("pops", "Stated positions by employee population"); break;
      case "position":
        exReg("portfolio", "Market position of every area on one percentile scale, ranked by depth percentile, with the position the strategy sets for each");
        break;
      case "trend": if (trend.available) exReg("trend", "Movement by area since the previous collection window"); break;
      case "register": exReg("register:" + p.part, "Every commitment, its status and its evidence" + (p.parts > 1 ? " (" + (p.part + 1) + " of " + p.parts + ")" : "")); break;
      case "sched": exReg("sched:" + p.part, "Planned actions by horizon" + (p.parts > 1 ? " (" + (p.part + 1) + " of " + p.parts + ")" : "")); break;
      case "cost": if ((money.items || []).length) exReg("cost", "Metrics lumi can price, and the cost of moving each to the peer median"); break;
      case "worth": exReg("worth", "What one percentage point of movement is worth, and the arithmetic behind each"); break;
      case "decided": exReg("decided:" + p.part, "Each option, the area it belongs to, the decision recorded and the reason given" + (p.parts > 1 ? " (" + (p.part + 1) + " of " + p.parts + ")" : "")); break;
      case "gov": exReg("gov", "Approval record for this strategy"); break;
      case "domain":
        // The condition must MATCH the render, or a number is allocated to a table that
        // never prints and the sequence gains a hole — it skipped 5 and 10. (Plain JS
        // here: this is a switch body, not a template literal.)
        if (p.half === "read" && (b.signals || []).length
            && !((b.gaps || []).length && (p.parts || 1) === 1))
          exReg("dom-sig:" + b.name, "Signals in " + domainLabel(b.name) + ", with your value and how each one reads against " + cutLabel);
        if (p.half === "follow") {
          // three reviewers: seven captions promised "the decision on each" over tables
          // with no decision column — the clause now appears only when one is recorded
          const _hasDec = (b.options || []).some(o => (o.levers || [])
            .some(l => decisions[decKey(b.name, l.lever_id)]));
          exReg("dom-opt:" + b.name + ":" + p.levPart,
                "Options against the " + domainLabel(b.name) + " gaps"
                + (_hasDec ? ", and the decision recorded on each" : "")
                + ((p.levParts || 1) > 1 ? " (" + ((p.levPart || 0) + 1) + " of " + p.levParts + ")" : ""));
        }
        break;
    }
  };
  pages.forEach(p => { exWalk(p, p.body); if (p.body2) exWalk(p, p.body2); });

  // a flat, cheap description of the spine for the navigator — it must not need
  // SEC_NO, secKey or the page objects themselves
  const navItems = [];
  pages.forEach((p, i) => { navItems.push(_navItem(p, i));
    if (p.body2) navItems.push({ i: i, cover: false, divider: false, pt: p.pt,
      partTitle: (RR_PART[p.pt] || {}).title, title: p.title2, no: SEC_NO[p.body2], cont: false }); });
  function _navItem(p, i) { return ({
    i: i, cover: !!p.cover, divider: !!p.divider, pt: p.pt,
    partTitle: (RR_PART[p.pt] || {}).title,
    title: p.title, no: SEC_NO[secKey(p)],
    cont: !!(p.title && /\(cont\.\)$/.test(p.title)),
  }); }
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
    // the shared ask shape, never the raw row count (QA v2, D014 / gate A1.5)
    const n = askActs;
    const areas = (theAsk.areas || []).map(domainLabel);
    if (!hasPosition) {
      // the ask must AGREE with the approval record two pages away: "approve the
      // strategy as stated" printed against a record reading Approved asked the board
      // for a decision the same document says was taken (2026-08-16 ship gate). And
      // the board commits the ORGANISATION — lumi reading benchmarks through it is
      // product behaviour, not what is being resolved.
      return (ver && ver.dirty
        ? "The board is asked to re-approve the reward strategy as amended — the approval record "
          + "in Governance and approval shows it approved and since amended, and this document "
          + "reads through the amended statement. "
        : ver
          ? "The strategy stands approved — the record is in Governance and approval — so no "
            + "strategy decision is sought here. The board is asked to note this document as the "
            + "current record of it. "
          : "The board is asked to approve the reward strategy set out in this document as the "
            + "organisation's stated position on pay, benefits and the wider package. ")
        + "It commits the organisation to that stated position; lumi reads every benchmark "
        + "through it. No spending decision is being sought: the position against the market is "
        + "not yet measured, and the plan that follows from it comes back to the board once it is.";
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
    // DECISION UNITS, not rows: approving both members of a declared either/or cannot
    // be minuted, so the ask counts choices (2026-08-16 ship gate). Recurring spend is
    // counted per unit — a pair whose two options both recur is ONE recurring spend.
    const nU = askUnits.length || n;
    const unitCosts = askUnits.map(u => (u.titles || []).map(t => costOf[t]));
    const recCertain = unitCosts.filter(cs => cs.length && cs.every(c => c === "recurring")).length;
    const recMaybe = unitCosts.filter(cs => cs.some(c => c === "recurring") && !cs.every(c => c === "recurring")).length;
    const choiceBit = askChoices
      ? (nU === 1
         ? " It is a single decision offered in two alternative forms — one of the two, not both."
         : askChoices === 1
         ? " One of the " + nU + " is a choice between two alternative forms — one of the two, not both."
         : " " + askChoices + " of the " + nU + " are choices between alternatives — one option from each, not all.")
      : "";
    const ownCost = !nU ? ""
      : (recCertain === 0 && recMaybe === 0)
        // D066 (v3.1): "cost-neutral or self-funding" claimed a tag the lever library
        // does not carry — a hedge that adds a claim the data cannot support. Render
        // the stored cost character, nothing wider.
        ? (nU === 1 ? "The action itself carries no new recurring spend. "
                    : "The actions themselves carry no new recurring spend. ")
        : (nU === 1 && recCertain
            ? "The action carries recurring spend"
            : recCertain ? recCertain + " of the " + nU + (recCertain === 1 ? " carries" : " carry") + " recurring spend"
                         : "None of the " + nU + " necessarily carries recurring spend")
          + (recMaybe ? (recCertain ? ", and up to " : ", though up to ") + recMaybe + " more may, depending on which alternative is chosen" : "")
          + " — the figure is in What it costs where lumi can price it, and yours to set where it cannot. ";
    const cost = money.investment_to_p50_gbp
      ? ("Separately, the indicative cost of closing every gap lumi can price is "
         + gbp(money.investment_to_p50_gbp) + " a year"
         + (nPriced < nGaps ? " — that envelope covers " + nPriced + " of the " + nGaps
            + " gaps and is not the cost of this approval." : "."))
      : "None of the gaps in this review carries a price from lumi's model.";
    // the DECISION itself now leads with "re-approve the strategy as amended, then …"
    // (server-side, external review 2026-08-16), so the lede no longer repeats the
    // sequencing sentence; the Governance page carries the measured-against line.
    const verBit = "";
    return "The board — or the remuneration committee, where reward is delegated to it — "
      + (askTwoPart
         ? "is asked for two decisions. First, re-approve the strategy as amended — the gaps below "
           + "are measured against it. Second, approve the " + nU + " action" + (nU === 1 ? "" : "s")
           + " scheduled for this cycle" + (areas.length ? ", covering " + rrList(areas) : "") + "."
         : "is asked to approve the " + nU + " action" + (nU === 1 ? "" : "s")
           + " scheduled for this cycle" + (areas.length ? ", covering " + rrList(areas) : "") + ".")
      + choiceBit + " " + ownCost
      + (nGaps ? ((nU === 1 ? "It is the first step of a response to the " : "They are the first cycle of a response to the ")
        + nGaps + " gap" + (nGaps === 1 ? "" : "s") + " this review found between the strategy as stated "
        + "and the organisation's own data"
        + (askUnits.length && nGaps ? ", of which " + (askUnits.length === 1 ? "one is" : askUnits.length + " are") + " acted on now" : "")
        + ". ") : "") + verBit + cost;
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
      // Q10 (v3.1): the rounding convention was applied and never stated, and the hedge
      // ("about £27,000" once, unhedged five times) was inconsistent. It belongs where
      // the £ are, not on the method page.
      ? "Aggregate £ figures round to the nearest thousand and per-person figures to the "
        + "pound; every £ here is indicative on these assumptions, whether or not the word "
        + "sits beside it. Figures use the midpoint of your stated FTE band ("
        + (money.fte_band ? money.fte_band.replace(/-/g, "–") + " FTE, midpoint " : "")
        + ((money.unit_rates || {}).fte || "—") + ") and lumi's published salary and level-mix "
        + "assumptions. Peer rates are medians of " + cutLabel + ", which spans organisations of "
        + "every size — the £ scales on your headcount while the rates reflect that sample. "
        + "They are an order of magnitude for a board discussion, not a budget."
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
    // options against the same gap are one DECISION STREAM, not separate commitments —
    // the old count ("7 are alternatives ... one of each pair") was arithmetically
    // impossible against the 3 flags the table carried (2026-08-16 ship gate)
    const inSets = schedule.reduce((a, s2) => a.concat(s2.actions), [])
      .filter(a2 => altInfo[a2.title]).length;
    const gapsInSets = new Set();
    schedule.forEach(s2 => s2.actions.forEach(a2 => { if (altInfo[a2.title]) gapsInSets.add(altOf[a2.title]); }));
    return n + " action" + (n === 1 ? "" : "s") + " across " + schedule.length + " horizon"
      + (schedule.length === 1 ? "" : "s") + ", sequenced by how quickly each one can realistically land. "
      // D033 (v3.1): "an option against one of 1 gap" — the plural template ran at one
      // and produced a grammar leak on a board page. (Plain JS comment: this is a
      // return expression, not an htm template.)
      + (inSets ? ((gapsInSets.size === 1
                    ? (inSets === n ? "They are not " + n + " separate commitments: every one is an option against a single gap"
                       : inSets + " of them are options against a single gap")
                    : (inSets === n ? "They are not " + n + " separate commitments: every one is an option against one of "
                       : inSets + " of them are options against ") + gapsInSets.size + " gaps")
         + " — one option per gap in any one cycle; where two sit in the same cycle they are "
         + "alternatives, one of them, not both. ") : "")
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
        + ", below the " + (cnt.domain_min || 3) + " this engine requires before it will call an area verdict firm. "
        + "Treat the direction as a pointer and the position as provisional.");
    }
    if (aim.stance) {
      // two clauses, two subjects: "you aim on market here, which sits short of the
      // position your strategy sets" hung the shortfall on the AIM — and on an
      // on-market aim read as self-contradictory (2026-08-16 ship gate, six pages)
      const w = { on_target: "the live read matches that aim",
                  behind: "the live read sits short of that aim",
                  ahead: "the live read sits past that aim" }[aim.alignment];
      bits.push("You aim " + RR_STANCE_WORD[aim.stance] + " here" + (w ? "; " + w : "") + ".");
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
  // PRE-DATA tensions are deterministic and intent-only (2026-08-16 ship gate): the
  // cached model commentary describes a measured position, and rendering it on a
  // fresh org put the FULL variant's verdicts above a stat card reading "awaiting
  // your data". Before the read unlocks, only what the strategy itself states can
  // honestly be printed here.
  const tensionPre = () => {
    const dt = strat.domain_targets || {};
    const overall = strat.market_position;
    const diff = Object.keys(dt).filter(k => dt[k] && overall && dt[k] !== overall);
    const bits = ["A tension is a stated choice pulling against another stated choice, or "
      + "against what your data later shows — only the first is testable now."];
    if (overall && diff.length) {
      bits.push("From the strategy alone: the overall dial says "
        + (RR_STANCE_WORD[overall] || overall) + ", while "
        + rrList(diff.map(domainLabel)) + " " + (diff.length === 1 ? "states" : "state")
        + " a different aim — a deliberate spread is legitimate, and stating it makes it "
        + "visible here rather than discovered later.");
    } else if (overall) {
      bits.push("From the strategy alone: every stated area aim sits with the overall dial — "
        + "no internal pull is visible in what has been stated so far.");
    }
    return bits.join(" ");
  };
  const watchPre = () => "Coverage itself: " + commitments.length
    + " commitment" + (commitments.length === 1 ? " is" : "s are") + " stated and every one "
    + "waits on evidence. Once your data is in, this page names the areas where position and "
    + "aim disagree; until then a stated aim stays a stated aim, not a finding.";
  // ------------------------------------------------------------------ bodies ----
  const Body = ({ kindOf, items, part, parts, start, num, block, half, levSlice, levPart, levParts, ptId }) => {
    const first = !part;                       // only sheet 1 of a run carries the intro
    const contd = parts > 1 ? " (" + (part + 1) + " of " + parts + ")" : "";
    if (kindOf === "cover") return html`
      <div class="rr-cover-in">
        ${/* NO vendor mark (external review 2026-08-16): this is the member's own
             reward strategy, and a lumi-authored cover fails the standalone-shareable
             test — worse, it read as the benchmarking vendor asserting figures about
             itself. The organisation's name is the cover's identity; lumi lives in
             Method and basis and the provenance line. */ ""}
        <div class="rr-eyebrow">${K.eyebrow}</div>
        <div class="rr-accent"></div>
        <h1 class="rr-title">${orgName}</h1>
        <div class="rr-subtitle">${K.title}</div>
        <p class="rr-lead">${K.lead}</p>
        ${/* the reference cover leads with a stat wall — white cards on the navy field.
             Position, gaps and the priced envelope, each with its basis, so the cover
             answers "where do we stand" before the reader opens the paper. */ ""}
        ${hasPosition && wantsPlan ? html`
          <${RrStats} items=${[
            { v: domains.length, k: "areas benchmarked", note: "against " + cutLabel },
            // the off-strategy count declares its mix — "10" bundled areas short of
            // their aim with areas PAST a deliberately lower aim, which inflated the
            // alarm on page 1 (external review 2026-08-16). Plain JS comments only:
            // this is an array literal, not a template.
            { v: gaps.length, k: gaps.length === 1 ? "commitment off strategy" : "commitments off strategy",
              note: (() => {
                const aheadN = domains.filter(d => (d.target || {}).alignment === "ahead").length;
                return aheadN
                  ? (gaps.length - aheadN) + " short or contradicted · " + aheadN + " past a deliberately lower aim"
                  : "your data vs your stated strategy";
              })() },
            // NOT the £27k envelope: it prices 1 of 10 gaps and needed two disclaimers
            // on its own page — a number that needs disclaiming is not a cover number
            // (external review 2026-08-16). The envelope lives in What it costs.
            { v: askActs,
              k: (askActs === 1) ? "action proposed this cycle" : "actions proposed this cycle",
              note: askChoices ? "incl. one either/or — see What we're asking" : "see What we're asking" },
          ]} />` : null}
        ${/* the metadata block a consultancy cover carries: who produced it, when, on
             what basis, and what may be done with it. No "Prepared for" row — the
             organisation's name is the hero line directly above, and naming it twice
             on one sheet reads as a mail-merge rather than a deliverable. */ ""}
        <div class="rr-cover-meta">
          ${/* no "Prepared by lumi" row — the member's identity carries the cover;
               the platform is named in Method and basis and the provenance line
               (external review 2026-08-16). "Prepared for" names the body the paper
               is written to, from the approval record where one is named (QA v2,
               D024). A named human AUTHOR needs a captured field that does not
               exist — held for David rather than guessed from the login. */ ""}
          ${/* D037 (v3.1): the "The Board" fallback asserted on page 1 what the approval
               record on page 39 says is unknown — "no board or committee was named at
               approval". The v2 fix for cover dead space created a cross-surface
               contradiction 36 sheets away, which is the argument for the gate rather
               than for careful reading. The row renders ONLY from a captured body. */ ""}
          ${wantsPlan && ver && ver.approver_body
            ? html`<div><span>Prepared for</span>${ver.approver_body}</div>` : null}
          ${/* Q5 (v3.1): the entity block, beside the peer block, so the two can be
               compared where they are asserted rather than 34 pages apart. */ ""}
          ${(al.entity || {}).fte_band || (al.entity || {}).sector ? html`
            <div><span>Organisation</span>${[(al.entity.sector || ""),
              al.entity.fte_band ? al.entity.fte_band.replace(/-/g, "–") + " FTE" : ""]
              .filter(Boolean).join(" · ")}</div>` : null}
          <div><span>Date of issue</span>${today}</div>
          <div><span>Document status</span>${ver
            ? (ver.dirty ? "Version " + ver.version + " — amended" + (ver.amended_at ? " " + fmtDate(ver.amended_at) : "") + "; re-approval pending"
                         : "Version " + ver.version + ", approved" + (ver.approval_date ? " " + ver.approval_date : ""))
            : "Draft — not yet approved"}</div>
          <div><span>Benchmark basis</span>${cutLabel}</div>
          ${/* the ruled R-P2 provenance fact at the FRONT of the artefact as well as in
               the footer line — a durable PDF outlives the conversation that sold the
               membership (2026-08-16) */ ""}
          ${/* strip the sentence terminal with the sentence — the naive replace left
               "…profiles. — lumihr.co.uk" on the cover (QA v2, D025) */ ""}
          ${al.pool_footer ? html`<div><span>Comparison pool</span>${al.pool_footer
            .replace("Comparison pool: ", "")
            .replace(/\.\s*See lumihr\.co\.uk methodology for sources\.\s*$/, " — lumihr.co.uk methodology")}</div>` : null}
          <div><span>Data collection</span>${(al.snapshot || {}).window || "Current window"}${
            (al.snapshot || {}).date ? " · " + al.snapshot.date : ""}</div>
          ${/* the two labels sit adjacent, so the cover itself points at the page
               that reconciles them (2026-08-16 ship gate) */ ""}
          ${/* D052 (v3.1): the cover asserted both labels side by side and left the
               reader to discover on p40 that NO read uses the stated group. The
               divergence is stated where it is asserted. */ ""}
          ${doc.comparator_label && doc.comparator_label !== cutLabel
            ? html`<div><span>Stated peer group</span>${doc.comparator_label
                + " — not the basis for the reads in this document; see Method and basis"}</div>` : null}
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
          ${/* the letter as a typographic device, the way a consultancy divider carries
               its part — reversed out of the colour field (2026-08-16) */ ""}
          <div class="rr-div-mark" aria-hidden="true">${ptId}</div>
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
      ${/* the old sub promised "everything asserted here is set out in full and
           evidenced" — an over-claim the review caught (some area verdicts defer
           their metric evidence to the app), and the line the TOC's new register
           row needed back (2026-08-16) */ ""}
      <${RrH} n=${num} sub="The position, the ask and the basis, in one page.">Executive summary<//>
      ${/* PRE-DATA the lede is deterministic: the model reads (diagnosis/commentary)
           are locked until data unlocks, so on a genuinely fresh org they are empty —
           and a cached read would describe a position this page's own stat card says
           is awaiting data (2026-08-16 ship gate, caught on the fresh variant). */ ""}
      ${!hasPosition ? html`<${Prose} k="exec_summary" className="rr-lede" generated=${
          "This document records the reward strategy as stated, and the commitments it makes. "
          + "Your position against " + cutLabel + " fills in as your data arrives — "
          + Math.round((al.data_state || {}).core_pct || 0) + "% of the core set is in — and Part B "
          + "becomes the measured read, the gaps and the plan at that point."} />`
      : aiWaiting ? html`<p class="rr-p rr-muted">Writing the commentary…</p>`
        : html`<${Prose} k="exec_summary" className="rr-lede" generated=${
            rrCase((wantsPlan ? (dg && dg.parts && dg.parts.summary) : null)
            || (cm && cm.parts && cm.parts.reading) || "")} />`}
      ${/* the stat wall lives on the COVER now — repeating it here was the "stat
           readout" the Mercer reviewer failed the page for. Pre-data, the wall is
           not on the cover, so the three what-IS-known counters stay. */ ""}
      ${hasPosition ? null : html`<${RrStats} items=${[
        { v: commitments.length, k: "commitments stated", note: "from your reward strategy" },
        { v: Math.round((al.data_state || {}).core_pct || 0) + "%", k: "of your data in",
          note: (al.data_state || {}).answered + " of " + (al.data_state || {}).basis_total + " core questions" },
        { v: "—", k: "position", note: "awaiting your data" },
      ]} />`}
      ${/* two columns: a per-domain report runs to ~20 sections and a single-column
           contents list pushed this sheet past A4 (2026-08-16). Continuation pages
           are dropped — a reader wants the section, not every sheet it spans. */ ""}
      ${hasPosition && wantsPlan ? html`
        <${RrCard} tone="navy" label="What this paper concludes">
          <p class="rr-p">${rrType((() => {
            // COUNT THE REGISTER'S OWN OBJECTS (QA v2, D001). This counted the eight
            // domains' engine alignments — but the strategy states a position for only
            // six of them (Wellbeing and Governance carry coherence commitments
            // instead, ruling R3b), so "5 sit below" could not be reconciled against a
            // register holding six position rows. Commitments are the countable thing;
            // areas are coverage. The buckets are exhaustive by construction, so the
            // tally always closes both ways.
            const posC = commitments.filter(c => c.kind === "position");
            const cohC = commitments.filter(c => c.kind === "coherence");
            const shortN = commitments.filter(c => c.direction === "short").length;
            const pastN = commitments.filter(c => c.direction === "past").length;
            const contraN = commitments.filter(c => c.status === "contradicted").length;
            const otherN = Math.max(0, gaps.length - shortN - pastN - contraN);
            // the FRAME and the TOTALS here; the split by status is the register's
            // job one page-turn away, and carrying it twice cost the exec sheet its
            // last two lines. The reconciliation the reviewer wanted is the frame:
            // what is being counted, and how many there are.
            return "Your strategy sets a position for " + posC.length + " of the " + domains.length
              + " benchmarked areas and makes " + cohC.length + " coherence commitment"
              + (cohC.length === 1 ? "" : "s") + " besides — " + commitments.length
              + " in all, listed with their status in The commitments in full. "
              // D058 (v3.1): "3 of them also below market" was reachable only through an
              // unstated sub-rule (off-strategy POSITION rows whose area reads below),
              // and the same sentence carried a second, different 3. The register's
              // status column carries the split; the exec states the totals.
              + gaps.length + (gaps.length === 1 ? " is" : " are") + " off strategy"
              + "; " + holding.length + " hold"
              + (unevid.length ? " and " + unevid.length + " await evidence" : "") + ". ";
          })()
            + "The board is asked to " + rrCase(theAsk.decision || "note this review") + ". "
            + (money.investment_to_p50_gbp
               ? "The one envelope lumi can price — closing every priced gap to the peer median — is "
                 + gbp(money.investment_to_p50_gbp) + " a year; it is not the cost of this approval."
               : "No gap in this review carries a price from lumi's model."))}</p>
        <//>` : null}

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
              if (p.body2) rows.push({ kind: "sec", no: SEC_NO[p.body2], title: p.title2,
                                       n: i + 1, inPart: !!p.pt });
            });
            // PRE-DATA the lettering ran A → B → D: Part C needs data to exist at all,
            // and the silent gap read as a rendering bug while wasting the one moment
            // the contents could say what the data unlocks (2026-08-16 ship gate).
            if (!hasPosition && RR_PART.C && !rows.some(r => r.kind === "part" && r.id === "C")) {
              const di = rows.findIndex(r => r.kind === "part" && r.id === "D");
              const lockRow = { kind: "locked", id: "C", title: RR_PART.C.title };
              if (di >= 0) rows.splice(di, 0, lockRow); else rows.push(lockRow);
            }
            // buttons, not divs: a 41-sheet contents you cannot click is a tease on
            // screen. Styled as plain rows so the printed page is unchanged. (A plain
            // JS comment — this block is an arrow body, NOT a template literal, and an
            // htm-style ${/* … */} here is a syntax error that kills the whole file.)
            return rows.map((r, i) => r.kind === "locked"
              ? html`<div key=${i} class="rr-toc-part rr-toc-locked" aria-disabled="true">
                  <span>Part ${r.id} — ${r.title}</span><b>unlocks with your data</b></div>`
              : r.kind === "part"
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
          : html`
            ${/* one full-width card, then a pair — the reference varies its rhythm and
                 fifteen identical stacks was the creative director's chief complaint */ ""}
            <${RrCard} head=${S[0].t}>
              <${Prose} k=${S[0].k} generated=${rrCase(P6[S[0].k] || "")} />
            <//>
            <div class="rr-grid2">
              ${S.slice(1).map(sec => html`
                <${RrCard} key=${sec.k} head=${sec.t}>
                  <${Prose} k=${sec.k} generated=${rrCase(P6[sec.k] || "")} />
                <//>`)}
            </div>`}`;
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
              ${/* D059 (v3.1): "6 areas set differently" read as "6 differ from the
                   overall stance" (five do) when it meant "6 carry their own aim".
                   The two readings are not equivalent, which is the defect. */ ""}
              <td><b>${v || "Not stated"}</b>${f === "market_position" && n ? html`<br /><span class="rr-sm">${n} area${n === 1 ? "" : "s"} carr${n === 1 ? "ies" : "y"} their own aim</span>` : ""}</td>
              <td class="rr-sm">${v ? (RR_DRIVES[f] || SD_DRIVES[f] || "") : "Read neutrally."}</td>
            </tr>`; })}
        </tbody>
      </table>`;

    if (kindOf === "prin") {
      const cons = doc.constraints || {};
      return html`
        <${RrH} n=${num} edit=${EditAt("principles", "Edit principles")} sub="The statements this organisation holds itself to, the market it measures itself against, and the limits it has recorded on what it can change.">Principles, peers and constraints<//>
        ${/* D047 (v3.1): with principles AND constraints both empty this page said
             nothing twice — two "nothing recorded" boxes plus a restatement of the
             sentence §03 already carries. The empty boxes are suppressed; the
             comparator card, which carries real content, stays. */ ""}
        ${(doc.principles || []).length ? html`
        <${RrCard} head="Our reward principles">
          <ol class="rr-ol">${(doc.principles || []).map((p, i) => html`<li key=${i}>${p}</li>`)}</ol>
        <//>` : null}
        <div class=${(cons.selected || []).length || cons.notes ? "rr-grid2" : ""}>
          <${RrCard} head="Who we compare ourselves to">
            <p class="rr-p">${orgCompareWords(null, doc)}</p>
            ${/* the reconciliation lives here too — this card is the only comparator
                 statement with any detail, and the first place a reader asks which
                 basis actually governs the figures (2026-08-16 ship gate) */ ""}
            ${doc.comparator_label && doc.comparator_label !== cutLabel ? html`
              <p class="rr-p rr-sm rr-muted">${"No read in this document uses that group — the reads run on "
                + cutLabel + ", and Method and basis explains why."}</p>` : null}
          <//>
          ${(cons.selected || []).length || cons.notes ? html`
            <${RrCard} tone="cream" head="What constrains us">
              <p class="rr-p">${rrList((cons.selected || []).map(c => CONSTRAINT_LABEL[c] || c))}${cons.notes ? (((cons.selected || []).length ? ". " : "") + cons.notes) : ""}</p>
            <//>` : null}
        </div>
        ${/* the absences are stated once, in a line, rather than as two empty cards */ ""}
        ${!((doc.principles || []).length) || !((cons.selected || []).length || cons.notes) ? html`
          <p class="rr-src">${rrList([].concat(
              (doc.principles || []).length ? [] : ["no separate set of reward principles"],
              ((cons.selected || []).length || cons.notes) ? [] : ["no recorded constraints"]))
            + " has been written down against this strategy; the positions stated in Part A carry "
            + "the philosophy in their place."}</p>` : null}`;
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
      <${RrH} n=${num} sub=${hasPosition
        ? "Where the stated strategy pulls against itself, or against what the data shows."
        : "Where the stated strategy pulls against itself — what can be tested before your data is in."}>Tensions and what to watch<//>
      ${/* PRE-DATA this section is deterministic and intent-only: the model commentary
           describes a measured position, and a cached or stale read printed the FULL
           org's verdicts on a document whose own pages say the position is awaiting
           data (2026-08-16 ship gate, all five reviewers). */ ""}
      ${!hasPosition ? html`
        <div class="rr-grid2">
          <${RrCard} label="Tensions">
            <${Prose} k="tensions" generated=${tensionPre()} />
          <//>
          <${RrCard} tone="cream" label="What to watch">
            <${Prose} k="watch" generated=${watchPre()} />
          <//>
        </div>`
      : cm && cm.parts ? html`
        ${/* D048 (v3.1): the section built for tensions contained none — the document's
             actual contradictions (a stated intent its own answers run against) sat in
             register rows on p12 and in area sections, and never here. They are routed
             to the section named after them, verbatim from the register. */ ""}
        ${(() => {
          const contra = commitments.filter(c => c.status === "contradicted");
          if (!contra.length) return null;
          return html`
            <${RrCard} tone="navy" label=${contra.length === 1 ? "The contradiction on the register"
              : "The contradictions on the register"}>
              ${contra.map(c => html`<p key=${c.id} class="rr-p rr-sm">${rrCase(c.statement)}</p>`)}
              <p class="rr-p rr-sm rr-muted">${"Each is a stated intent your own answers run against — "
                + "not a shortfall in delivery — and is carried with its evidence in The commitments in full."}</p>
            <//>`;
        })()}
        <div class="rr-grid2">
          <${RrCard} label="Tensions">
            <${Prose} k="tensions" generated=${rrCase(cm.parts.tensions)} />
          <//>
          <${RrCard} tone="cream" label="What to watch">
            <${Prose} k="watch" generated=${rrCase(cm.parts.watch)} />
          <//>
        </div>`
        : html`<p class="rr-p rr-muted">${aiWaiting ? "Writing the commentary…" : "Commentary is unavailable for this document."}</p>`}
      ${/* pointed at a "companion document" that this document became (2026-08-16) */ ""}
      ${wantsPlan ? null : html`
        <div class="rr-callout quiet">
          <div class="rr-callout-h">Where you stand against this</div>
          <p class="rr-p">Your live position against this strategy, the gaps it opens and the plan to
          close them are set out in the companion <b>Reward Position ${"&"} Plan</b> document.</p>
        </div>`}`;

    if (kindOf === "gov") return html`
      ${/* D035 (v3.1): the subtitle promised "when it takes effect, when it is next
           reviewed" and the exhibit carried neither — both are optional fields and are
           unset here. A subtitle names only what the record actually holds. */ ""}
      <${RrH} n=${num} sub=${"Who approved this strategy"
        + (ver && ver.effective_date ? ", when it takes effect" : "")
        + (ver && ver.next_review ? ", when it is next reviewed" : "")
        + " — and what was left unstated at the point of approval."}>Governance and approval<//>
      <${RrCard} label="Approval record">
      <${RrEx} ex=${EXH["gov"]} />
      <table class="rr-table">
        <tbody>
          <tr><td>Status</td><td><b>${ver ? "Approved" : "Draft — not yet approved"}</b>${ver && ver.dirty ? html` <span class="rr-sm">${"— amended" + (ver.amended_at ? " " + fmtDate(ver.amended_at) : " since") + "; the amendments await re-approval"}</span>` : ""}</td></tr>
          ${ver ? html`<tr><td>Version</td><td><b>${ver.version}</b></td></tr>` : null}
          ${/* every value cell in this record is bold — the print review caught the
               column mixing weights (2026-08-16) */ ""}
          ${/* a raw login email as "approved by" in a board paper reads as unfinished —
               prefer the recorded body, and mark a bare account as what it is */ ""}
          ${ver ? html`<tr><td>Approved by</td><td><b>${ver.approver_body
            || (ver.approved_by ? ver.approved_by : "—")}</b>${!ver.approver_body && ver.approved_by
            ? html`<br /><span class="rr-sm">the approving account; no board or committee was named at approval</span>` : ""}</td></tr>` : null}
          ${ver && ver.approval_date ? html`<tr><td>Date of approval</td><td><b>${ver.approval_date}</b></td></tr>` : null}
          ${ver && ver.effective_date ? html`<tr><td>Effective from</td><td><b>${ver.effective_date}</b></td></tr>` : null}
          ${ver && ver.next_review ? html`<tr><td>Next review</td><td><b>${ver.next_review}</b></td></tr>` : null}
          ${st.completed_at ? html`<tr><td>Strategy captured</td><td><b>${fmtDate(st.completed_at)}</b></td></tr>` : null}
        </tbody>
      </table>
      <//>
      ${/* which strategy the document's reads run against — a paper stamped "amended;
           re-approval pending" that asks for decisions owes the reader this line
           (2026-08-16 ship gate) */ ""}
      ${ver && ver.dirty ? html`
        <p class="rr-p rr-sm rr-muted">${"Every read in this document is taken against the strategy "
          + "as it stands today — the amended statement, not the earlier approved version. "
          + "Re-approval of the amendments is recorded here when it happens."}</p>` : null}
      ${(ver && (ver.unstated || []).length) ? html`
        <${RrCard} tone="cream" head="What was unstated at approval">
          <p class="rr-p rr-sm">${ver.unstated.length + " section" + (ver.unstated.length === 1 ? " was" : "s were")
            + " unstated when this was approved: " + ver.unstated.join(", ")
            + ". The version record carries exactly what was and was not stated, so a later reader can tell "
            + "a deliberate silence from an omission."}</p>
        <//>` : null}`;

    // ---- ONE DOMAIN, in full: count, position, signals, commentary, what follows ----
    if (kindOf === "domain") {
      const b = block || {};
      const isRead = (half || "read") === "read";
      const inlineFollow = isRead && (b.gaps || []).length && (parts || 1) === 1;
      const cntStrictFalse = (b.count || {}).strict === false;
      // computed OUTSIDE the template: htm's tokenizer cannot parse a spread inside ${}
      const _seen2 = new Set();
      const _allLev = (b.options || []).reduce((a, o) => a.concat(o.levers || []), [])
        .filter(l => !_seen2.has(l.lever_id) && _seen2.add(l.lever_id));
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
      // Measured in PRINT (10.5pt type), not on screen — the screen render paginates
      // differently and reporting it was how the last section came to split.
      // 2, not 3: the percentile chart sits above this table now and is worth more than
      // a third row. ZERO where the sheet also carries the section's follow-up inline
      // (a domain with gaps but no levers) — that sheet holds a read, a chart, the
      // commentary AND the gap statements, and Time off & family ran past A4 trying to
      // fit a signal table as well. The count is still named in the heading, so the
      // reader is told what is not shown rather than it quietly vanishing.
      const _room = inlineFollow ? 0 : 2 - (cntStrictFalse ? 1 : 0);
      const sigShown = (b.signals || []).slice(0, Math.max(0, _room));
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
        <${RrStats} items=${[
          { v: cnt.metrics || 0, k: "metrics benchmarked",
            // D061 (v3.1): one count-noun wherever a number is doing work. The body
            // said "peers" here and "comparable organisations" elsewhere for the same
            // object; "peer" survives only as the comparison vocabulary (peer median,
            // peer group), never as the thing being counted.
            note: cnt.peer_n ? "typically " + cnt.peer_n.median + " comparable organisations each ("
                               + cnt.peer_n.min + "–" + cnt.peer_n.max + ")"
                             : "on your own data" },
          { v: (RR_POS_WORD[pos.verdict] || "no read yet") + (cnt.strict === false ? " *" : ""),
            k: "market position", tone: pos.verdict ? "v-" + pos.verdict : null,
            note: pos.pctl != null ? "around the " + rrOrdinal(pos.pctl) + " percentile"
                                   : "not enough comparable data" },
          // sentence-case parity with "below market" beside it (copy editor)
          { v: readWord ? readWord.charAt(0).toLowerCase() + readWord.slice(1) : "No aim set", k: "against your aim",
            tone: aim.alignment ? "a-" + aim.alignment : null,
            note: aim.stance ? "you aim " + RR_STANCE_WORD[aim.stance] : "read neutrally" },
        ]} />
        ${cnt.strict === false ? html`<p class="rr-src">${"* indicative — fewer than "
          + cnt.domain_min + " benchmarked metrics stand behind this read."}</p>` : null}

        ${/* the position as a picture, before the counts that produce it */ ""}
        <${RrCard} label="Where you sit">
          <${RrDomainChart} band=${mband} label=${domainLabel(b.name)}
            pctl=${pos.pctl} verdict=${pos.verdict} stance=${aim.stance} />
        <//>

        ${/* the split bar is GONE (2026-08-16): it and the chart above both draw "where
             you sit", and two bars saying the same thing pushed Pay and Time off past
             the sheet in print. The counts it carried are stated in the prose below —
             "18 sit below market, 17 on it and 2 above" — where they read as a
             sentence rather than needing a legend. */ ""}`}

        ${!isRead ? null : html`
        ${/* commentary on alignment to market — the analytic heart of the section */ ""}
        <${RrCard} tone="cream" head="How this reads">
          <${Prose} k=${"domain:" + b.name} generated=${domProse(b)} />
        <//>

        ${/* a sheet that ALSO carries the follow content has room for fewer signals —
             sized so the combined sheet still lands inside A4 */ ""}
        ${/* D027 (v3.1): the tail promised "the options against them follow below" on a
             section whose follow branch correctly DECLINES to offer levers (an area past
             its own aim). The clause now reads the same branch the options block does. */ ""}
        ${(!sigShown.length && b.signal_count) ? html`
          <p class="rr-p rr-sm">${domainLabel(b.name) + " is flagging " + b.signal_count + " signal"
            + (b.signal_count === 1 ? "" : "s") + "; they are set out in full under "
            + domainLabel(b.name) + " in the app"
            + (_allLev.length ? ", and the options against them follow below." : ".")}</p>` : null}
        ${(sigShown || []).length ? html`
          <${RrCard} head=${"What " + domainLabel(b.name) + " is flagging"
            + (b.signal_count > sigShown.length ? " (" + sigShown.length + " of " + b.signal_count + ")" : "")}>
          <${RrEx} ex=${EXH["dom-sig:" + b.name]} />
          <table class="rr-table tight">
            <thead><tr><th>Signal</th><th>Yours</th><th>Reads</th></tr></thead>
            <tbody>${sigShown.map(sg => html`
              <tr key=${sg.question_id || sg.title}>
                <td><b>${sg.title}</b>${sg.detail ? html`<br /><span class="rr-sm">${sg.detail}</span>` : ""}</td>
                <td class="rr-sm">${rrSignalValue(sg.value)}</td>
                <td class="rr-sm">${RR_POS_WORD[sg.position] || sg.position || "—"}</td>
              </tr>`)}</tbody>
          </table>
          ${/* a below-market area whose only flagged signal reads above market looks, on a
               board page, like the evidence refuting the verdict. Say why it doesn't. */ ""}
          <//>
          ${pos.verdict && sigShown.length && !sigShown.some(x => x.position === pos.verdict) ? html`
            <p class="rr-p rr-sm rr-muted">${"The signals above are the most material in "
              + domainLabel(b.name) + ", which is not the same as the most representative: none of "
              + "them happens to read " + RR_POS_WORD[pos.verdict] + ", while the area overall does. "
              + "The split at the top of this page is the fuller picture."}</p>` : null}
          ${/* "(2 of 5)" told the reader something was withheld and not where it lives —
               the Time off sentence was the correct handling, applied everywhere a
               header truncates (2026-08-16 ship gate) */ ""}
          ${b.signal_count > sigShown.length ? html`
            <p class="rr-src">${"The remaining " + (b.signal_count - sigShown.length) + " signal"
              + (b.signal_count - sigShown.length === 1 ? " is" : "s are") + " set out in full under "
              + domainLabel(b.name) + " in the app."}</p>` : null}` : null}`}

        ${isRead ? null : html`
          ${/* the gap statements in a sky card, the options in a white one — the follow
               sheets were the last bare tables once everything else was carded */ ""}
          ${(levPart || 0) === 0 ? html`
            <${RrCard} tone="sky" label=${(b.gaps || []).length === 1 ? "The gap" : "The gaps"}>
              ${b.gaps.map(c => html`<p key=${c.id} class="rr-p rr-sm">${rrCase(c.statement)}</p>`)}
            <//>` : null}
          ${levShown.length ? html`
            <${RrCard}>
            <${RrEx} ex=${EXH["dom-opt:" + b.name + ":" + (levPart || 0)]} />
            <table class="rr-table tight">
              <thead><tr><th>Option</th><th>Cost</th><th>Speed</th><th>Trade-off</th></tr></thead>
              <tbody>${levShown.map(l => html`
                <tr key=${l.lever_id}><td><b>${l.name}</b><br /><span class="rr-sm">${l.what_it_is}</span>
                  ${/* the decision against this option, recorded in place — the table was a
                       menu with no record of what was chosen or turned down (2026-08-16) */ ""}
                  <${RrDecCell} cur=${decisions[decKey(b.name, l.lever_id)]} states=${DEC_STATES}
                    canEdit=${!!canEditDoc} onSave=${(s, w) => saveDecision(b.name, l.lever_id, s, w)} /></td>
                  <td class="rr-sm">${l.cost_character}</td>
                  <td class="rr-sm">${l.speed}${l.reversibility === "hard" ? html`<br /><span class="rr-muted">hard to reverse</span>` : ""}</td>
                  <td class="rr-sm">${l.trade_off}</td></tr>`)}</tbody>
            </table><//>`
          : html`<p class="rr-p rr-sm rr-muted">${rrCase((b.options.find(o => o.coverage_note) || {}).coverage_note || "")}</p>`}`}

        ${isRead && !(b.gaps || []).length ? html`
          <p class="rr-p rr-sm">Nothing in ${domainLabel(b.name)} currently runs against your stated aim.</p>` : null}
        ${/* not split (no options table): the short explanation rides on the read sheet */ ""}
        ${isRead && (b.gaps || []).length && (parts || 1) === 1 ? html`
          <h3 class="rr-sh">What follows for ${domainLabel(b.name)}</h3>
          ${b.gaps.map(c => html`<p key=${c.id} class="rr-p">${rrCase(c.statement)}</p>`)}
          <p class="rr-p rr-sm rr-muted">${rrCase((b.options.find(o => o.coverage_note) || {}).coverage_note || "")}</p>` : null}

        <div class="rr-gap-foot no-print">
          <button class="rp-go" onClick=${() => toSignals(b.name, aim.alignment)}>
            <${Icon} name="zap" size=${13} /> ${domainLabel(b.name)} signals</button>
          <a class="rp-go" href=${"#/category/" + encodeURIComponent(b.name)}>
            <${Icon} name="bar-chart" size=${13} /> The data behind it</a>
        </div>`;
    }

    // ---- THE COMMITMENTS REGISTER ----------------------------------------------
    // The enumeration behind the headline count (external review 2026-08-16): the
    // paper asserted "13 commitments, 10 off, 3 holding" with no register a board
    // could reconcile it against. One row per commitment: what was stated, its
    // status in the document's own vocabulary, and what evidences it. "Past the
    // stated aim" is named as its own state — being better than you said is not
    // the same defect as being short, and bundling them inflated page 1.
    if (kindOf === "register") {
      const regStatus = (c) => c.status === "evidenced" ? "Holding"
        : c.status === "contradicted" ? "Contradicted"
        : c.status === "not_evidenced" ? "Awaiting evidence"
        : c.direction === "past" ? "Past the stated aim" : "Short of the stated aim";
      const regBasis = (c) => (c.evidence || {}).source === "category market read"
        ? "Market read on " + ((c.evidence || {}).cut || cutLabel)
        : "Your stated answers";
      return html`
        <${RrH} n=${num} sub=${first
          ? "One row per commitment — the register behind every count in this paper: "
            + commitments.length + " stated, " + gaps.length + " off strategy, "
            + holding.length + " holding" + (unevid.length ? ", " + unevid.length + " awaiting evidence" : "") + "."
          : null}>The commitments in full${contd}<//>
        <${RrCard}>
        <${RrEx} ex=${EXH["register:" + part]} />
        <table class="rr-table tight">
          <thead><tr><th>Area</th><th>Commitment</th><th>Status</th><th>Read from</th></tr></thead>
          <tbody>${(items || []).map(c => html`
            <tr key=${c.id}>
              <td class="rr-sm">${domainLabel(c.category || "")}</td>
              <td class="rr-sm">${rrCase(c.statement)}</td>
              <td class="rr-sm"><b>${regStatus(c)}</b></td>
              <td class="rr-sm">${regBasis(c)}</td>
            </tr>`)}</tbody>
        </table><//>
        ${/* WHAT HELD. The register carries "Holding" rows and nothing said what they
             mean: a claim the member made, tested against their own answers, and
             confirmed. A reader who watches a claim get tested and stand trusts the
             rest of the document more — and no vendor volunteers this. (QA v2
             delight 3; category (b), work done for them.) */ ""}
        ${/* D031 (v3.1): this claimed three commitments "tested against your own
             answers" when one of the three is a MARKET read, and it printed a template
             fallback with no antecedent — "aim on market (set for this area)" — on a
             circulated page. It now counts only answer-sourced rows and names the area
             for a position row, so the card and the register agree. */ ""}
        ${(() => {
          if (part !== (parts || 1) - 1) return null;
          const tested = holding.filter(c => c.kind === "coherence");
          if (!tested.length) return null;
          const named = tested.map(c => rrCase(c.intent_label || "")).filter(Boolean);
          const alsoRead = holding.length - tested.length;
          return html`
            <${RrCard} tone="sky" label="What we tested and it held">
              <p class="rr-p rr-sm">${tested.length + " of your " + commitments.length
                + " commitments were tested against your own answers and stand"
                + (named.length ? ": " + rrList(named) : "") + ". "
                + (alsoRead ? "A further " + alsoRead + " hold" + (alsoRead === 1 ? "s" : "")
                   + " on the market read rather than on your answers, and " + (alsoRead === 1 ? "is" : "are")
                   + " marked as such in the register. " : "")
                + "Nothing here needs a decision — a commitment that was checked and held is "
                + "evidence too, and only the register shows the difference between that and "
                + "one nobody has looked at."}</p>
            <//>`;
        })()}
        ${part === (parts || 1) - 1 ? html`
          <p class="rr-src">${"“Off strategy” counts the short, the contradicted and the past-aim rows together; "
            + "the status column is the split. A commitment is one stated position or one coherence "
            + "check — the same measure the cover, the executive summary and Part B count."
            // the questions-vs-readings reconciliation (external review: 263 vs 74
            // read as two different documents until the relationship was stated)
            + (() => {
              const readings = (al.domain_blocks || []).reduce((a, b) => a + (((b.count || {}).metrics) || 0), 0);
              return readings ? " Separately, the sections count " + readings + " benchmarked readings "
                + "from the core set’s answered questions — a matrix question contributes one reading "
                + "per role level." : "";
            })()}</p>` : null}`;
    }

    if (kindOf === "awaiting") {
      const need = Math.max(0, Math.ceil(((dstate.basis_total || 0) * (dstate.target_pct || 0)) / 100) - (dstate.answered || 0));
      return html`
        <${RrH} n=${num} sub="This half of the document is written from your own submitted data, read against your peer group. It fills in as your data arrives — nothing here is estimated in the meantime.">Where you'll stand<//>
        <p class="rr-lede">Your strategy above is stated and in force: lumi is already reading every
        benchmark through it. What it cannot yet do is tell you where you actually sit against it.</p>
        <${RrStats} items=${[
          { v: Math.round(dstate.core_pct || 0) + "%", k: "of your core questions answered",
            note: (dstate.answered || 0) + " of " + (dstate.basis_total || 0) },
          { v: need, k: need === 1 ? "answer to unlock" : "answers to unlock",
            note: "to reach the " + (dstate.target_pct || 0) + "% threshold" },
          { v: commitments.length, k: "commitments waiting on evidence",
            note: "from your stated strategy" },
        ]} />
        <p class="rr-p">Once your data is in, these pages complete the document: your position against
        each stated aim, the gaps that opens, what the market does about each one, and a sequenced plan
        with what each action returns.</p>
        ${/* the new customer's first question is "what happens next" — answer it with
             the same flow device the ask page uses (2026-08-16 ship gate) */ ""}
        <${RrCard} tone="navy" label="What happens next">
          <${RrFlow} steps=${[
            { t: "Enter your data", d: (dstate.target_pct || 60) + "% unlocks the read" },
            { t: "Position unlocks", d: "every area placed against peers" },
            { t: "Gaps price", d: "where lumi has a cost model" },
            { t: "The plan builds", d: "options sequenced across cycles" },
            { t: "This document completes", d: "ready for your board" },
          ]} />
        <//>
        ${canEditDoc ? html`
          <div class="rr-cta no-print">
            <button class="btn primary" onClick=${() => nav("/your-data")}>Add your data</button>
            <span class="rr-sm">Roughly ${need > 40 ? "an hour" : need > 15 ? "half an hour" : "a few minutes"} of work, and it only has to be done once.</span>
          </div>` : null}`;
    }

    if (kindOf === "position") return html`
      <${RrH} n=${num} sub=${"Each area's live benchmark on " + cutLabel + ", read against the position the strategy states for it."}>Position at a glance<//>
      ${/* the picture first, the table under it — eight verdicts across fifteen sheets
           had no view that showed them together (2026-08-16) */ ""}
      <${RrCard}>
      <${RrEx} ex=${EXH["portfolio"]} />
      ${/* D041 (v3.1): the chart's only job is rank, and it was rendering areas in
           payload order — neither percentile, verdict, metric count nor alphabetical.
           Sorted highest-first; the sort is stated in the exhibit line. */ ""}
      <${RrPortfolioChart} band=${mband} rows=${domains.map(d => ({
        name: d.name,
        label: domainLabel(d.name),
        pctl: (d.position || {}).depth_pctl,
        verdict: (d.position || {}).verdict,
        aim: RR_AIM_PCT[(d.target || {}).stance],
      })).sort((a, b) => (b.pctl == null ? -1 : b.pctl) - (a.pctl == null ? -1 : a.pctl))} />
      ${/* the key must show the colours the chart actually uses — a single blue dot
           labelled "where you sit" appeared nowhere on the chart, whose dots are
           coloured by verdict (2026-08-16) */ ""}
      ${(() => {
        const present = new Set(domains.map(d => (d.position || {}).verdict).filter(Boolean));
        const SW = [["below", "verdict: below market"], ["at", "verdict: on market"], ["above", "verdict: above market"]];
        return html`
          <div class="rrc-key">
            <span><i class="rrc-k-band"></i>the range lumi reads as on market</span>
            ${SW.filter(([k]) => present.has(k)).map(([k, l]) => html`
              <span key=${k}><i class=${"rrc-k-dot v-" + k}></i>${l}</span>`)}
            <span><i class="rrc-k-aim"></i>where your strategy aims</span>
          </div>
          <p class="rr-src">${"A dot's place is its depth percentile; its colour is lumi's overall "
            + "verdict, which weighs every metric in the area — so two areas near the band's edge can "
            + "share a percentile and read differently."}</p>`;
      })()}
      <//>
      ${/* the first-window baseline caveat ran three times (here, and twice on the
           Movement page) — the external review asked for two, and the Movement page
           is where a reader looking for movement will meet it (2026-08-16) */ ""}
      <p class="rr-p rr-sm">${"The chart above covers the " + domains.length + " areas lumi "
        + "benchmarks. Elsewhere this document counts COMMITMENTS — an area carries one for the "
        + "position your strategy sets, plus one for each coherence check that applies to it — so "
        + gaps.length + " off strategy, " + holding.length + " holding and " + unevid.length
        + " not yet evidenced are a different measure of the same picture, not a disagreement."}</p>`;

    if (kindOf === "findings") return html`
      <${RrH} n=${num} sub=${first ? "Where the declared strategy and the live position diverge, and what organisations in this position commonly consider." : null}>Findings${contd}<//>
      ${(items || []).map((f, i) => {
        // the generic sizing-up caveat printed VERBATIM under every finding — template
        // output, not judgement (5 of 7 reviewers). Said once, at the foot of the run.
        const opt = rrProse(f.option || "").replace(RR_FRAMING_RE, "").trim();
        return html`
        <${RrCard} key=${i} head=${rrCase(f.headline)}>
          <p class="rr-p rr-sm">${rrCase(rrProse(f.detail))}</p>
          ${opt ? html`<p class="rr-p rr-sm rr-opt"><span>Options</span>${rrCase(opt)}</p>` : null}
        <//>`; })}
      ${part === parts - 1 ? html`
        ${(() => {
          // NOT dg.on_plan: that list means "not flagged by the diagnosis", and it filed
          // Governance as tracking while the domain pages read it Below strategy — the
          // WTW reviewer caught the contradiction. The alignment payload is this
          // document's authority, so the sentence derives from it.
          const onT = domains.filter(d => (d.target || {}).alignment === "on_target").map(d => d.name);
          const past = domains.filter(d => (d.target || {}).alignment === "ahead").map(d => d.name);
          return html`
            ${onT.length ? html`<p class="rr-p rr-sm">${rrList(onT.map(domainLabel))
              + (onT.length === 1 ? " is" : " are") + " tracking with the stated intent."}</p>` : null}
            ${past.length ? html`<p class="rr-p rr-sm">${rrList(past.map(domainLabel))
              + (past.length === 1 ? " sits" : " sit") + " above a deliberately lower aim — an "
              + "aim-setting question rather than a delivery gap, taken up in "
              + (past.length === 1 ? "its" : "their") + " own section" + (past.length === 1 ? "" : "s") + "."}</p>` : null}`;
        })()}
        ${/* WHAT IS AHEAD. The findings ran entirely on divergence, so a document
             built to be honest read as deficit-only — and the above-market reads
             appeared solely as confusing contrast under a below-market verdict. Every
             reward lead needs the true things they can say on Monday. Evidenced, with
             the sample behind each one; no adjectives. (QA v2 delight 1, category (a).) */ ""}
        ${(() => {
          const ups = (al.domain_blocks || [])
            .reduce((a, b) => a.concat((b.signals || [])
              .filter(s => s.position === "above")
              .map(s => ({ ...s, area: b.name }))), [])
            .slice(0, 3);
          const upAreas = domains.filter(d => ((d.position || {}).verdict) === "above").map(d => d.name);
          if (!ups.length && !upAreas.length) return null;
          return html`
            <${RrCard} tone="cream" label="What sits above market">
              ${upAreas.length ? html`<p class="rr-p rr-sm">${rrList(upAreas.map(domainLabel))
                + (upAreas.length === 1 ? " reads" : " read") + " above " + cutLabel
                + " overall."}</p>` : null}
              ${ups.length ? html`<ul class="rr-ul">${ups.map((s, i) => html`
                <li key=${i} class="rr-sm">${rrCase(s.title) + " — " + rrSignalValue(s.value)
                  + (s.detail ? " (" + rrCase(s.detail) + ")" : "")
                  + (s.n ? ", on the " + s.n + " organisations that answered it" : "")}</li>`)}</ul>` : null}
              <p class="rr-p rr-sm rr-muted">${"These are reads, not recommendations: an area above "
                + "market may be exactly where the strategy wants it, or may be spend the strategy "
                + "never asked for. Where it is past your own stated aim, its section says so."}</p>
            <//>`;
        })()}
        ${/* D026 (v3.1): dangling boilerplate — the caption described options the
             section had not rendered. It reads the WHOLE findings run (not this chunk),
             because the caption sits on the last sheet of a split run. */ ""}
        ${(((dg || {}).parts || {}).findings || []).some(f =>
            rrProse(f.option || "").replace(RR_FRAMING_RE, "").trim())
          ? html`<p class="rr-src">Options above are what organisations in this position commonly weigh — a starting
          point sized against budget and the roles affected, never a recommendation.</p>` : null}` : null}`;

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
              : ob && ob.coverage_note ? html`<p class="rr-p rr-sm rr-muted">${rrCase(ob.coverage_note)}</p>` : null}
            </div>`; })}
          <div class="rr-gap-foot no-print">
            <button class="rp-go" onClick=${() => toSignals(g.cat, g.align)}>
              <${Icon} name="zap" size=${13} /> ${domainLabel(g.cat)} signals</button>
            <a class="rp-go" href=${"#/category/" + encodeURIComponent(g.cat)}>
              <${Icon} name="bar-chart" size=${13} /> The data behind it</a>
          </div>
        </div>`)}`;

    if (kindOf === "planp") return html`
      ${/* "domain" is engine vocabulary; the document says AREA everywhere else and
           one leak reads as a different document (QA v2, D020) */ ""}
      <${RrH} n=${num} sub=${first ? "This is the roll-up of the sections above: every action below is one of the options already set out under its own area, sequenced across all of them." : null}>The plan${contd}<//>
      ${plan ? html`
        ${first ? html`<${Prose} k="plan_summary" className="rr-lede" generated=${rrCase(plan.summary)} />` : null}
        ${/* the one section still sitting bare on the ground once everything else was
             carded (2026-08-16 panel pass) */ ""}
        <${RrCard}>
        <ol class="rr-plan" start=${start || 1}>
          ${(items || []).map((a, i) => html`
            <li key=${i}>
              <div class="rr-plan-t">${a.title}${altNote(a.title) ? html` <span class="rr-sm rr-muted">· ${altNote(a.title)}</span>` : altInfo[a.title] ? html` <span class="rr-sm rr-muted">· ${"one of " + altInfo[a.title].size + " options against this gap"}</span>` : ""}
                <span class="rr-sm"> · from ${domainLabel(a.category || "")}${
                  SEC_NO["domain:" + a.category] ? " (§" + SEC_NO["domain:" + a.category] + ")" : ""} · ${a.horizon}</span></div>
              ${/* D032 (v3.1): what a lever IS comes from the LIVE library, never from
                   the stored plan — a plan built before a library repair carried the
                   superseded reward content into a board paper and contradicted the
                   section three pages earlier. The stored why supplies the reasoning
                   only where it adds something the description does not. */ ""}
              ${descOf[a.title] ? html`<p class="rr-p">${rrCase(descOf[a.title])}</p>` : null}
              ${(() => {
                const why = rrProse(a.why || "");
                if (!why) return null;
                const desc = (descOf[a.title] || "").trim();
                // drop a stored restatement of the description, however it was worded:
                // if the why is mostly that sentence, the live one above has said it
                const stripped = desc ? why.split(desc).join(" ").trim() : why;
                const rest = stripped.replace(/\s{2,}/g, " ").trim();
                return (!descOf[a.title] || (rest && rest.length > 40))
                  ? html`<p class="rr-p">${rrCase(rest || why)}</p>` : null;
              })()}
              <div class="rr-roi"><span>Return</span>${a.roi}</div>
            </li>`)}
        </ol>
        <//>
        ${part === parts - 1 ? html`<p class="rr-src">${rrType(plan.basis)}${plan.built_at ? " Built " + fmtDate(plan.built_at) + "." : ""}</p>` : null}`
      : html`<p class="rr-p rr-muted">${planBusy
          ? "Sequencing your gaps into a plan…"
          : "No plan is stored yet. Use Rebuild plan above to sequence these gaps into actions with their indicative return."}</p>`}`;

    // ---- THE ASK ---------------------------------------------------------------
    // The structural difference between a report and a board paper: this one describes
    // a position, names a cost and requests a decision. Everything on it is derived
    // from the plan and the envelope; only the wording is the author's.
    if (kindOf === "ask") {
      const nowTitles = theAsk.titles || [];
      // the remainder counts GAPS, and this cycle's actions cover one gap per decision
      // unit — "remaining 6" (10 − 4 rows) overstated coverage when two rows were an
      // either/or against one gap (2026-08-16 ship gate)
      const covered = askUnits.length || nowTitles.length;
      const rest = Math.max(0, (theAsk.gaps_total || 0) - covered);
      return html`
        <${RrH} n=${num} sub="The decision this paper seeks, what it would cost, and what it deliberately leaves open.">What we're asking the board to approve<//>
        <${RrCard} tone="navy" label="Decision sought">
          <div class="rr-ask-v">${rrCap(rrCase(theAsk.decision || "note this review"))}</div>
        <//>
        <${Prose} k="the_ask" className="rr-lede" generated=${askProse()} />
        ${hasPosition ? html`<${RrStats} items=${[
          { v: askActs, k: (askActs === 1) ? "action this cycle" : "actions this cycle", note: askNote },
          // four reviewers read this card as the PRICE OF THE APPROVAL — it is the
          // envelope of every priced gap, which may not even be in this cycle.
          // (Plain JS comment: this is an array literal, not a template.)
          { v: money.investment_to_p50_gbp ? gbp(money.investment_to_p50_gbp) : "—",
            k: money.investment_to_p50_gbp ? "all priced gaps, a year" : "no priced cost",
            note: "the envelope, not this approval's cost — see What it costs" },
          { v: theAsk.gaps_total || 0,
            k: (theAsk.gaps_total === 1) ? "gap in scope" : "gaps in scope",
            note: "strategy vs your own data" },
        ]} />` : null}
        <div class="rr-grid2">
        ${nowTitles.length ? html`
          <${RrCard} head="What approval covers">
            ${/* grouped by decision unit: an either/or renders as ONE item naming the
                 choice — flat bullets asked the board to approve both members of a
                 pair the schedule declares exclusive (2026-08-16 ship gate) */ ""}
            <ul class="rr-ul">${(askUnits.length ? askUnits : nowTitles.map(t => ({ titles: [t] }))).map((u, i) =>
              (u.titles || []).length > 1
                ? html`<li key=${i}><b>One of:</b> ${u.titles.join(", or ")}<br />
                    <span class="rr-sm rr-muted">alternatives against the same gap — approval is for one of the ${u.titles.length === 2 ? "two" : String(u.titles.length)}, not ${u.titles.length === 2 ? "both" : "all"}</span></li>`
                : html`<li key=${i}>${(u.titles || [])[0]}</li>`)}</ul>
          <//>` : null}
        ${rest ? html`
          <${RrCard} tone="cream" head="What it does not cover">
            ${/* D057 (v3.1): "the remaining N gaps" implied the ones acted on were
                 closed. Approving one option against a gap does not close it — the
                 body was careful ("acted on"), the box was not. */ ""}
            <p class="rr-p rr-sm">${"The " + rest + " gap" + (rest === 1 ? "" : "s")
            + " no action is proposed against "
            + (rest === 1 ? "is" : "are") + " set out under "
            + (rest === 1 ? "its own area" : "their own areas") + " with the options against "
            + (rest === 1 ? "it" : "them") + ", and " + (rest === 1 ? "is" : "are")
            + " not part of this approval. Where an option is already planned it appears in "
            + "The schedule; the rest fall to the next review."}</p>
          <//>` : null}
        </div>
        ${hasPosition ? html`
          <${RrCard} tone="navy" label="What approval sets in motion">
            ${/* the strip is the third face of the ask and must carry both parts of a
                 two-part decision, or it contradicts the banner above it (QA v2, D014) */ ""}
            <${RrFlow} steps=${(askTwoPart ? [{ t: "Re-approve", d: "the strategy as amended" }] : [])
              .concat([
                { t: "Approve", d: "the actions for this cycle" },
                { t: "Deliver", d: "changes land in the package" },
                { t: "Re-measure", d: "the next collection window" },
                { t: "Movement", d: "reported against this baseline" },
              ]).concat(askTwoPart ? [] : [{ t: "Next review", d: "the strategy re-tested" }])} />
          <//>` : html`
          ${/* the pre-data decision page was ~85% whitespace and never said what the
               approval sets in motion — the same flow device, measured steps held
               back until they are real (2026-08-16 ship gate) */ ""}
          <${RrCard} tone="navy" label="What this approval sets in motion">
            <${RrFlow} steps=${[
              { t: "Approve", d: "the strategy as the stated position" },
              { t: "Evidence", d: "your data arrives against it" },
              { t: "Position", d: "measured once the core set is in" },
              { t: "The plan", d: "returns to this board, priced" },
            ]} />
          <//>`}`;
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
      <${RrCard}>
      <${RrEx} ex=${EXH["sched:" + part]} />
      <table class="rr-table tight rr-sched-tbl">
        <thead><tr><th>Action</th><th>Area</th><th>Return</th></tr></thead>
        ${(items || []).map(s => html`
          <tbody key=${s.horizon + ":" + (s.contPart || 0)}>
            <tr class="rr-hz-row"><th colSpan="3">
              <span class=${"rr-hz h-" + s.horizon.replace(/[^a-z]/g, "")}>${rrCap(s.horizon)}${s.contPart ? " (cont.)" : ""}</span>
              ${s.contPart ? "" : html`<i>${(s.totalN || s.actions.length)} ${(s.totalN || s.actions.length) === 1 ? "action" : "actions"}</i>`}</th></tr>
            ${s.actions.map((a, i) => html`
              <tr key=${i}><td><b>${a.title}</b>${altNote(a.title) ? html`<br /><span class="rr-sm rr-muted">${altNote(a.title)}</span>` : ""}</td>
                <td class="rr-sm">${domainLabel(a.category || "")}${SEC_NO["domain:" + a.category]
                  ? " (§" + SEC_NO["domain:" + a.category] + ")" : ""}</td>
                <td class="rr-sm">${a.roi}</td></tr>`)}
          </tbody>`)}
      </table><//>
      ${/* set membership ONCE, under the table — flagging all ten rows would drown the
           schedule, and flagging only same-cycle pairs hid the cross-cycle sets whose
           count the intro states (2026-08-16 ship gate) */ ""}
      ${part === (parts || 1) - 1 && Object.keys(altInfo).length ? html`
        <p class="rr-p rr-sm rr-muted">${(() => {
          const byG = {};
          schedule.forEach(s2 => (s2.actions || []).forEach(a2 => {
            const g = altOf[a2.title];
            if (g && altInfo[a2.title]) (byG[g] = byG[g] || { area: a2.category, n: 0 }).n += 1;
          }));
          const sets = Object.values(byG);
          return "Options against one gap are one decision stream — "
            + rrList(sets.map(x => domainLabel(x.area) + " carries " + x.n))
            + ". A later option returns to the board in its own cycle, read against what the "
            + "earlier change moved; approving one never pre-commits the rest.";
        })()}</p>` : null}
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
      <${RrStats} items=${[
        { v: money.investment_to_p50_gbp ? gbp(money.investment_to_p50_gbp) : "—",
          k: "indicative investment, a year", note: "to reach the peer median" },
        { v: money.savings_to_p50_gbp ? gbp(money.savings_to_p50_gbp) : "—",
          k: "indicative saving, a year", note: "where you sit above it" },
        { v: nPriced + " of " + nGaps, k: nGaps === 1 ? "gap priced" : "gaps priced",
          note: "lumi's cost model, published assumptions" },
      ]} />
      <${Prose} k="cost" generated=${costProse()} />
      ${(money.items || []).length ? html`
        <${RrCard} head="Where the figure comes from">
        <${RrEx} ex=${EXH["cost"]} />
        <table class="rr-table tight">
          <thead><tr><th>Metric</th><th>Area</th><th class="num">To median</th><th class="num">To upper quartile</th></tr></thead>
          <tbody>${(money.items || []).map(it => html`
            <tr key=${it.label}><td><b>${it.label}</b><br /><span class="rr-sm">${it.formula}${
              it.levels_covered != null && it.levels_total != null && it.levels_covered < it.levels_total
                ? " — on the " + it.levels_covered + " of " + it.levels_total + " levels you have entered"
                : ""}</span></td>
              <td class="rr-sm">${domainLabel(it.category || "")}</td>
              <td class="num">${gbp(it.to_p50_gbp)}${it.direction === "saving" ? html` <span class="rr-sm">saving</span>` : ""}</td>
              <td class="num rr-sm">${gbp(it.to_p75_gbp)}</td></tr>`)}</tbody>
        </table><//>` : null}
      ${(money.assumptions && Object.keys(money.assumptions).length) ? html`
        <h3 class="rr-sh">The assumptions behind it</h3>
        <p class="rr-p rr-sm">${"Median salary " + gbp((money.assumptions || {}).median_salary_gbp)
          + " and your headcount" + ((money.unit_rates || {}).fte
            ? " (" + money.unit_rates.fte + " FTE, the midpoint of your stated "
              + (money.fte_band ? money.fte_band.replace(/-/g, "–") + " " : "") + "band)"
            : " (from your stated FTE band)")
          + " drive every figure above. Cost per leaver ("
          + ((money.assumptions || {}).cost_per_leaver_pct_salary || 0) + "% of salary) and the agency premium ("
          + ((money.assumptions || {}).agency_premium_pct || 0) + "%) apply only where attrition or agency metrics "
          + "are priced. Contribution gaps are priced on full salary; where contributions are set on "
          + "qualifying earnings the true cost is lower, so the envelope reads as an upper indication "
          + "rather than a like-for-like cost. "
          + "Change any input in your company details and the figures move with it."}</p>` : null}`;

    // ---- WHAT A POINT IS WORTH -------------------------------------------------
    // Its own section, not a block under "What it costs": it is a different idea
    // (sensitivity, not cost), it earns a contents entry, and together the two ran
    // 41px past A4 on one sheet.
    if (kindOf === "worth") return html`
      <${RrH} n=${num} sub=${"What a single percentage point of movement is worth on your own headcount — "
        + ((money.unit_rates || {}).fte ? "{n} FTE, the midpoint of your stated band. ".replace("{n}", String(money.unit_rates.fte)) : "")
        + "The multiplier for the actions lumi cannot price."}>What a point is worth<//>
      <${Prose} k="worth" className="rr-lede" generated=${worthProse()} />
      <${RrCard}>
      <${RrEx} ex=${EXH["worth"]} />
      <table class="rr-table tight">
        <thead><tr><th>Move</th><th class="num">Worth, a year</th><th>How it is worked out</th></tr></thead>
        <tbody>${((money.unit_rates || {}).points || []).map(pt => html`
          <tr key=${pt.key}><td><b>${pt.label}</b></td>
            <td class="num">${gbp(pt.gbp)}</td>
            <td class="rr-sm">${pt.formula}</td></tr>`)}</tbody>
      </table>
      <//>
      ${(money.unit_rates || {}).basis ? html`<p class="rr-src">${"These rates are "
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
      ${/* This conversion was in a batch that ABORTED on a later assertion, so it was
           silently never written — the fragment-dropping failure mode again: the page
           shipped in the old bare style while every neighbour was carded (2026-08-16).
           rrCase because engine strings carry raw category names. */ ""}
      <div class="rr-grid2">
        ${(items || []).map(r => html`
          <${RrCard} key=${r.id} label=${r.class} head=${rrCase(r.title)}>
            <p class="rr-p rr-sm">${rrCase(r.detail)}</p>
          <//>`)}
      </div>
      ${/* the caveat belongs once, on the last sheet of the run — not under every chunk */ ""}
      ${part !== parts - 1 ? null : html`
        <p class="rr-p rr-sm rr-muted">${"lumi can only name exposures its own data shows. Anything outside "
          + "the benchmark — delivery capacity, employee relations, what a competitor is about to do — is "
          + "not in view here and its absence is not evidence of its absence."}</p>`}`;

    // ---- DECISIONS NOT TAKEN ---------------------------------------------------
    if (kindOf === "decided") return html`
      <${RrH} n=${num} sub=${first ? "The record of what was weighed and what was turned down, so a later reader can tell a considered rejection from an oversight." : null}>Decisions taken and not taken${contd}<//>
      ${first ? html`<${Prose} k="decisions" className="rr-lede" generated=${decProse()} />` : null}
      <${RrCard} label="The record">
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
      </table><//>`;

    if (kindOf === "method") return html`
      <${RrH} n=${num} sub="How every figure in this document was produced, what it rests on, and what it deliberately does not claim.">Method and basis<//>
      ${/* keep the ${} on the SAME line as the words before it — htm collapses a newline
           before an expression and printed "rests on55 of the 77 questions" */ ""}
      ${/* SINGLE COLUMN, not rr-grid2 (2026-08-16): half-width cards double every
           sentence's line count and the sheet sits at print capacity — pairing four
           long cards wasted ~40mm and the provline+comparator additions spilled the
           footer. Full-width cards halve the lines; the sheet fits with room. */ ""}
      <div>
      ${/* SINGLE-SOURCED from data_state, the same counters the pre-data pages print —
           a separate completeness block let this page claim 96% while page 9 of the
           same document said 12% (2026-08-16 ship gate, all five reviewers). The
           fallback keeps an older cached payload rendering rather than blank. */ ""}
      ${(al.data_state || al.completeness) ? html`<${RrCard} label="Completeness"><p class="rr-p rr-sm">
      ${(() => {
        const ds = al.data_state || {};
        const answered = ds.answered != null ? ds.answered : (al.completeness || {}).answered;
        const of = ds.basis_total != null ? ds.basis_total : (al.completeness || {}).of;
        const pct = ds.core_pct != null ? Math.round(ds.core_pct) : (al.completeness || {}).pct;
        // (the questions-vs-readings reconciliation lives on the register's closing
        // note — this sheet is at print capacity and the register is where a reader
        // meets both counts)
        return "This document rests on " + answered + " of the " + of
          + " core-set questions (" + pct + "%). "
          + (hasPosition
             // D038 (v3.1): this promised a mark for "thinly answered" areas, which
             // reads as a sample-size threshold that does not exist. The mechanism that
             // DOES exist marks an area with fewer benchmarked metrics than the engine
             // requires — so the sentence now describes that, and points at where the
             // per-signal sample is actually shown.
             ? "An area with too few benchmarked metrics for a firm verdict carries an "
               + "indicative read, marked in its own section; unanswered areas say so rather "
               + "than being estimated."
             : "Until that set reaches " + Math.round(ds.target_pct || 60) + "%, the position "
               + "pages state what is missing rather than estimating anything.");
      })()}</p><//>` : null}
      ${al.snapshot ? html`<${RrCard} label="Data vintage"><p class="rr-p rr-sm">
      ${"Peer figures are the " + (al.snapshot.window || "current") + " collection"
        + (al.snapshot.date ? ", dated " + al.snapshot.date : "")
        + ". Your own answers are as you last saved them."
      // the stated peer group vs the benchmark basis, reconciled where a reader can
      // find it — the cover carries both labels side by side, and no page said why
      // they differ or that the stated group's SIZE BANDS are not the org's own
      // (external review 2026-08-16). Lives on this card to balance the method
      // grid: the positions card had grown past its column partner.
      + (doc.comparator_label && doc.comparator_label !== cutLabel
         ? " The strategy names " + doc.comparator_label + " as its stated peer group; no read here "
           + "uses it — they run on " + cutLabel
           + (money.fte_band && /FTE/i.test(doc.comparator_label)
              && doc.comparator_label.indexOf(money.fte_band) === -1
              ? ", and its size bands are not your own (" + money.fte_band.replace(/-/g, "–") + " FTE)."
              : ".")
         : "")}</p><//>` : null}
      <${RrCard} label="How positions are computed"><p class="rr-p rr-sm">${"Positions come from your own "
      + "submitted data against " + cutLabel + ", on the engine and suppression rules that govern every "
      + "figure in lumi — no figure rests on fewer than " + (al.suppression_floor || 5) + " organisations. "
      + "An area's verdict weighs every metric's position; its percentile is depth alone — "
      + "near the band's edge the two can differ. Alignment is a count against your commitments — never a "
      + "score, index or grade."}</p><//>
      <${RrCard} tone="cream" label="What it will not do"><p class="rr-p rr-sm">${"Positions blend "
      + "your whole workforce, so a blended percentile can mask offsetting gaps between populations "
      + "(hourly store against salaried office); this document does not split them."}</p>
      <p class="rr-p rr-sm">Where a commitment’s evidence is unanswered, this document says so rather than
      estimating: ${hasPosition
        ? (unevid.length + " commitment" + (unevid.length === 1 ? " sits" : "s sit") + " unevidenced today.")
        : (commitments.length + " commitment" + (commitments.length === 1 ? " awaits" : "s await")
           + " evidence until your data is in.")}
      ${/* D039 (v3.1): this described generation-then-validation while the provenance
           foot on the SAME PAGE said all commentary uses standard wording — read
           together, either every generation failed validation or none ran. Both now
           hang off the one flag the foot uses. Keep the ${} on the SAME LINE as the
           words before it: htm collapses the newline and printed "the area.Written". */ ""}
      Indicative figures come from lumi’s cost model on its published assumptions, only where it has
      one for the area. ${_modeled === 0
        ? "Every written passage here is lumi’s standard wording, composed from the figures on the "
          + "page — no model output was used."
        : "Written commentary is generated from those figures and validated before it is shown: it "
          + "cannot introduce a number that is not on the page, direct you to act, or make a legal "
          + "determination; where validation fails, lumi’s standard wording is used."}</p><//>
      </div>
      ${/* the last beat belonged to a caveat about lumi's wording, under a leftover
           settings caption. A member's own strategy should end by returning to them
           — restraint, not a flourish (QA v2 delight 7, category (c)). */ ""}
      <p class="rr-close">${"The strategy in this document is yours as you stated it; the position is "
        + "your own data read against the comparison pool; the options are what the market commonly "
        + "does, and every decision among them stays with you. Where lumi could not see something, "
        + "it has said so rather than filled it in."}</p>`;

    return null;
  };

  // three reviewers: the old line printed raw engine vocabulary ("commentary
  // deterministic, findings model") and collided with the running footer
  const _modeled = sources.filter(x => / model$/.test(x)).length;
  const prov = "Produced with lumi · reward benchmarking. "
    // the ruled R-P2 durable-artefact line, verbatim — the board pack, both CSVs and
    // the share views already carry it; this document was the sibling missing it.
    // ("Benchmarked on X" dropped from this line: the cover and the method card both
    // state the basis, and the third repeat pushed the provline to two lines.)
    + (al.pool_footer ? al.pool_footer + " " : "")
    + (_modeled === 0
       ? "All written commentary uses lumi's standard wording."
       : _modeled === sources.length
         ? "Written commentary was generated by lumi's model and validated before display."
         : "Written commentary was generated by lumi's model where available, validated before display, with standard wording elsewhere.");

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
          ${/* a paired sheet: the second section under a rule, so the join reads as a
               section break and not as more of the section above it */ ""}
          ${p.body2 ? html`
            <div class="rr-pairsplit"></div>
            <${Body} kindOf=${p.body2} num=${SEC_NO[p.body2]} ptId=${p.pt} part=${0} parts=${1} />` : null}
        <//>`)}
    </div>`;
};
