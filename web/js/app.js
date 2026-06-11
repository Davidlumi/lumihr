/* lumi root app: shell, navigation, global peer filter, search, routing. */
/* global html, useState, useEffect, useMemo, useRef, api, useRoute, nav, Chip, Spinner, AuthScreen,
   OverviewPage, SuperpowerPage, MyViewPage, MyDataPage, MethodologyPage, GapRegisterPage,
   BoardPackPage, BoardPackView, AnalystPane, PeerTwinPanel, SharesPage, TeamPage, SettingsPage,
   SubmissionPage, BenchmarkCard, SUPERPOWERS, SP_ICONS, EmptyState, cutLabelOf, cutKeyOf */

/* Deep linking: the peer cut lives in the hash query (?cut=industry::X) so a
   filtered view is shareable and back-button-safe. Section is already in the
   route; this completes the main views. */
function cutFromURL() {
  const m = (window.location.hash || "").match(/[?&]cut=([^&]+)/);
  if (!m) return { dim: "all", value: null };
  const raw = decodeURIComponent(m[1]);
  if (raw === "twin") return { dim: "twin", value: null };
  const [dim, value] = raw.split("::");
  return value ? { dim, value } : { dim: "all", value: null };
}
function cutToURL(cut) {
  const h = window.location.hash || "#/overview";
  const base = h.replace(/[?&]cut=[^&]*/, "").replace(/[?&]$/, "");
  if (cut.dim === "all") { if (base !== h) history.replaceState(null, "", base); return; }
  const enc = encodeURIComponent(cut.dim === "twin" ? "twin" : cut.dim + "::" + cut.value);
  const next = base + (base.includes("?") ? "&" : "?") + "cut=" + enc;
  if (next !== h) history.replaceState(null, "", next);
}

function App() {
  const route = useRoute();
  const [me, setMe] = useState(undefined);          // undefined=loading, null=unauth
  const [cut, setCut] = useState(cutFromURL());
  const [cuts, setCuts] = useState(null);
  const [prefs, setPrefs] = useState({});
  const [layoutIds, setLayoutIds] = useState(new Set());
  const [analystOpen, setAnalystOpen] = useState(false);
  const [metricReq, setMetricReq] = useState(null);   // {prefill, source} | null
  const [gapCue, setGapCue] = useState(null);          // {section, count} — nav priority cue
  const [twinOpen, setTwinOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [qIndex, setQIndex] = useState(null);
  const prefsTimer = useRef(null);

  const refreshMe = () => api("/api/me").then(setMe).catch(() => setMe(null));
  useEffect(() => { refreshMe(); }, []);
  useEffect(() => {
    const f = () => setMe(null);
    window.addEventListener("lumi:unauth", f);
    return () => window.removeEventListener("lumi:unauth", f);
  }, []);
  useEffect(() => {
    if (!me) return;
    api("/api/cuts").then(setCuts);
    api("/api/prefs").then(d => setPrefs(d.prefs || {}));
    api("/api/myview").then(d => setLayoutIds(new Set((d.layout || []).map(s => s.question_id))));
    api("/api/questions").then(setQIndex);
    api("/api/gap-register").then(d => {
      const counts = {};
      (d.rows || []).forEach(r => { if (r.status === "not_in_place") counts[r.subpower] = (counts[r.subpower] || 0) + 1; });
      const top = Object.entries(counts).sort((x, y) => y[1] - x[1])[0];
      setGapCue(top ? { section: top[0], count: top[1] } : null);
    }).catch(() => {});
  }, [me && me.org && me.org.name]);
  useEffect(() => { cutToURL(cut); }, [cutKeyOf(cut)]);
  useEffect(() => {
    const y = consumeReturnScroll(window.location.hash);
    if (y != null) {
      // the page below loads async — keep trying briefly until the height exists
      let tries = 0;
      const t = setInterval(() => {
        window.scrollTo(0, y);
        if (Math.abs(window.scrollY - y) < 4 || ++tries > 20) clearInterval(t);
      }, 150);
      return () => clearInterval(t);
    }
  }, [route]);

  window.openMetricRequest = (prefill, source) => setMetricReq({ prefill: prefill || "", source: source || "button" });
  if (me === undefined) return html`<div class="auth-wrap"><${Spinner} /></div>`;
  const scope = me && me.scope ? me.scope : { superpowers: window.SUPERPOWERS || [], focused: false, question_count: 778 };
  window.SCOPE = scope;
  const activeSupers = scope.superpowers;
  if (me === null) return html`<${AuthScreen} route=${route} onAuthed=${() => { window.location.hash = "/overview"; refreshMe(); }} />`;

  const onPref = (qid, p) => {
    const next = { ...prefs, [qid]: p };
    setPrefs(next);
    clearTimeout(prefsTimer.current);
    prefsTimer.current = setTimeout(() => api("/api/prefs", { method: "PUT", body: { prefs: next } }).catch(() => {}), 800);
  };
  const onPin = async (qid) => {
    const view = await api("/api/myview");
    let layout = view.layout || [];
    if (layout.some(s => s.question_id === qid)) layout = layout.filter(s => s.question_id !== qid);
    else layout = [...layout, { question_id: qid, size: 1 }];
    await api("/api/myview", { method: "PUT", body: { layout } });
    setLayoutIds(new Set(layout.map(s => s.question_id)));
  };
  const setGlobalCut = (key) => {
    if (key === "all") setCut({ dim: "all", value: null });
    else if (key === "twin") setCut({ dim: "twin", value: null });
    else { const [dim, value] = key.split("::"); setCut({ dim, value }); }
  };

  const pageProps = { me, refreshMe, cut, cuts, prefs, onPref, onPin, pinnedIds: layoutIds };
  const contrib = me.contribution || null;

  let page = null, m;
  if (route.startsWith("/superpower/")) {
    const [sp, qs] = route.slice("/superpower/".length).split("?");
    const params = new URLSearchParams(qs || "");
    const focusQ = params.get("focus");
    const subF = params.get("sub");
    if (!activeSupers.includes(decodeURIComponent(sp))) {
      page = html`<${EmptyState} title="That area isn't part of your benchmark"
        body="Your benchmark covers reward." action=${html`<button class="btn small" onClick=${() => nav("/superpower/Reward")}>Go to your reward benchmark</button>`} />`;
    } else {
      page = html`<${SuperpowerPage} ...${pageProps} sp=${decodeURIComponent(sp)} focusQ=${focusQ} subF=${subF} />`;
    }
  } else if ((m = route.match(/^\/metric\/(.+)$/))) {
    page = html`<${MetricPage} ...${pageProps} qid=${m[1]} />`;
  } else if ((m = route.match(/^\/boardpack\/(.+)$/))) {
    page = html`<${BoardPackView} packId=${m[1]} me=${me} />`;
  } else if (route.startsWith("/boardpack")) page = html`<${BoardPackPage} me=${me} cut=${cut} />`;
  else if (route.startsWith("/myview")) page = html`<${MyViewPage} ...${pageProps} />`;
  else if (route.startsWith("/mydata")) page = html`<${MyDataPage} />`;
  else if (route.startsWith("/methodology")) page = html`<${MethodologyPage} />`;
  else if (route.startsWith("/gap-register")) page = html`<${GapRegisterPage} ...${pageProps} />`;
  else if (route.startsWith("/submission")) {
    const section = route.split("/")[2];
    page = html`<${SubmissionPage} me=${me} refreshMe=${refreshMe} section=${section && decodeURIComponent(section)} />`;
  }
  else if (route.startsWith("/shares")) page = html`<${SharesPage} />`;
  else if (route.startsWith("/team")) page = html`<${TeamPage} me=${me} />`;
  else if (route.startsWith("/settings")) page = html`<${SettingsPage} me=${me} refreshMe=${refreshMe} />`;
  else if (route === "" || route === "/" || route.startsWith("/overview") || route.startsWith("/invite/") || route.startsWith("/reset/"))
    page = html`<${OverviewPage} ...${pageProps} />`;
  else page = html`<${NotFoundPage} route=${route} />`;

  const benchRoute = route.startsWith("/overview") || route.startsWith("/superpower") ||
    route.startsWith("/myview") || route.startsWith("/metric") || route.startsWith("/gap-register") || route === "" || route === "/";

  return html`
    <div class="shell">
      <${IdleGuard} onSignOut=${async () => { await api("/api/auth/logout", { method: "POST" }).catch(() => {}); setMe(null); }} />
      <nav class="sidebar no-print" aria-label="Main navigation">
        <a class="logo" href="#/overview" aria-label="lumi benchmark home">lumi<span>.benchmark</span></a>
        <div class="nav-group">
          <button class=${navCls(route, "/overview")} onClick=${() => nav("/overview")}><${Icon} name="home" size=${15} /> Executive overview</button>
          <button class=${navCls(route, "/myview")} onClick=${() => nav("/myview")}><${Icon} name="star" size=${15} /> My view</button>
          <button class=${navCls(route, "/gap-register")} onClick=${() => nav("/gap-register")}><${Icon} name="list-checks" size=${15} /> Gap register</button>
          <button class=${navCls(route, "/boardpack")} onClick=${() => nav("/boardpack")}><${Icon} name="file-text" size=${15} /> Board pack</button>
        </div>
        <div class="nav-group">
          <div class="nav-label">${scope.focused ? "Your reward benchmark" : "Benchmarks"}</div>
          ${scope.focused && html`
            <button class=${"nav-item" + (route.startsWith("/superpower/Reward") && !route.includes("sub=") ? " active" : "")} onClick=${() => nav("/superpower/Reward")}>
              <${SpIcon} sp="Reward" /> All reward
              ${qIndex && html`<span class="nav-count">${qIndex.questions.filter(q => !q.locked).length}</span>`}
            </button>
            <${SectionNav} route=${route} qIndex=${qIndex} gapCue=${gapCue} />`}
          ${!scope.focused && activeSupers.map(sp => html`
            <button key=${sp} class=${navCls(route, "/superpower/" + sp)} onClick=${() => nav("/superpower/" + sp)}>
              <${SpIcon} sp=${sp} /> ${sp}
              ${qIndex && html`<span class="nav-count">${qIndex.questions.filter(q => q.superpower === sp && !q.locked).length}</span>`}
            </button>`)}
        </div>
        <div class="nav-group">
          <div class="nav-label">Your organisation</div>
          <button class=${navCls(route, "/mydata")} onClick=${() => nav("/mydata")}><${Icon} name="table" size=${15} /> My data</button>
          ${(me.user.role === "admin" || me.user.role === "contributor") && html`<button class=${navCls(route, "/submission")} onClick=${() => nav("/submission")}><${Icon} name="pencil" size=${15} /> Submit data</button>`}
          <button class=${navCls(route, "/team")} onClick=${() => nav("/team")}><${Icon} name="users" size=${15} /> Team</button>
          ${me.user.role === "admin" && html`<button class=${navCls(route, "/shares")} onClick=${() => nav("/shares")}><${Icon} name="link" size=${15} /> Manage shares</button>`}
          <button class=${navCls(route, "/settings")} onClick=${() => nav("/settings")}><${Icon} name="sliders-v" size=${15} /> Settings</button>
          <button class=${navCls(route, "/methodology")} onClick=${() => nav("/methodology")}><${Icon} name="book-open" size=${15} /> Methodology</button>
        </div>
        <div class="nav-group nav-id" style=${{ marginTop: "auto" }}>
          <div class="who">${me.user.display_name || me.user.email}</div>
          <div class="org">${me.org.name}</div>
          <button class="nav-item" onClick=${async () => { await api("/api/auth/logout", { method: "POST" }); setMe(null); }}><${Icon} name="log-out" size=${15} /> Sign out</button>
        </div>
      </nav>
      <div class="main">
        <div class="topbar no-print">
          <div class="ctlgroup">
            <select aria-label="Choose your peer group" class=${"ctl peer-ctl" + (cut.dim !== "all" ? " narrowed" : "")}
              value=${cut.dim === "all" ? "all" : cut.dim === "twin" ? "twin" : cut.dim + "::" + cut.value}
              onChange=${e => { if (e.target.value === "twin-info") { setTwinOpen(true); } else setGlobalCut(e.target.value); }}>
              <option value="all">All peers (${(me.peer_pool || {}).responding_orgs || "—"})</option>
              ${cuts && cuts.org_industry && html`<option value=${"industry::" + cuts.org_industry}>${cuts.org_industry} (${cuts.industries[cuts.org_industry] || "?"})</option>`}
              ${cuts && Object.keys(cuts.industries || {}).filter(i => i !== (cuts || {}).org_industry).map(i =>
                html`<option key=${i} value=${"industry::" + i}>${i} (${cuts.industries[i]})</option>`)}
              ${cuts && Object.keys(cuts.fte_bands || {}).map(b =>
                html`<option key=${b} value=${"fte_band::" + b}>${b} FTE (${cuts.fte_bands[b]})</option>`)}
              ${cuts && cuts.twin_available && html`<option value="twin">Organisations like you</option>`}
            </select>
            <div class="hint">${cutHint(cut, cuts, me)}</div>
            ${cut.dim === "twin" && html`<button class="btn small" onClick=${() => setTwinOpen(true)}>Why these peers?</button>`}
          </div>
          <div class="ctlgroup" style=${{ flex: 1, maxWidth: "400px" }}>
            <div style=${{ position: "relative" }}>
              <span style=${{ position: "absolute", left: "10px", top: "11px", color: "var(--ink-faint)", pointerEvents: "none" }}><${Icon} name="search" size=${14} /></span>
              <input class="ctl" style=${{ width: "100%", maxWidth: "none", paddingLeft: "32px" }} placeholder="Search any reward metric, e.g. 'pension' or 'sick pay'"
                aria-label="Search reward metrics" value=${search} onInput=${e => setSearch(e.target.value)}
                onKeyDown=${e => { if (e.key === "Escape") setSearch(""); }} />
              ${search.length > 1 && qIndex && html`<${SearchPop} qIndex=${qIndex} search=${search} onGo=${(q) => { setSearch(""); openMetric(q.id); }} />`}
            </div>
          </div>
          <div class="topbar-right">
            ${contrib && !contrib.insights_unlocked && html`<${ClockChip} contrib=${contrib} />`}
            <button class="link-quiet" title="Ask us to benchmark something new" onClick=${() => setMetricReq({ prefill: "", source: "button" })}>Request a metric</button>
            <button class="btn feature" title="Ask anything about your benchmark, in plain English" onClick=${() => setAnalystOpen(true)}><${Icon} name="sparkle" size=${14} /> Ask lumi</button>
          </div>
        </div>
        <main class="content">
          ${contrib && benchRoute && html`<${ContributionBanner} contrib=${contrib} />`}
          ${page}
        </main>
      </div>
      ${analystOpen && html`<${AnalystPane} onClose=${() => setAnalystOpen(false)} />`}
      ${metricReq && html`<${RequestMetricModal} prefill=${metricReq.prefill} source=${metricReq.source}
        onClose=${() => setMetricReq(null)} />`}
      ${twinOpen && html`<${PeerTwinPanel} onClose=${() => setTwinOpen(false)} onUse=${() => setGlobalCut("twin")} />`}
    </div>`;
}

window.SectionNav = function ({ route, qIndex, gapCue }) {
  if (!qIndex) return null;
  const secs = sectionList(qIndex);
  return html`${secs.map(sec => {
    const active = route.includes("sub=" + encodeURIComponent(sec.name));
    const cued = gapCue && gapCue.section === sec.name;
    return html`
      <button key=${sec.name} class=${"nav-item" + (active ? " active" : "")}
        style=${{ paddingLeft: "var(--s6)" }}
        onClick=${() => nav("/superpower/Reward?sub=" + encodeURIComponent(sec.name))}>
        ${sec.name}
        ${cued && html`<span class="gap-cue" title=${gapCue.count + " practices your peers commonly have that you don't — your biggest opportunity area"}></span>`}
        <span class="nav-count">${sec.count}</span>
      </button>`;
  })}`;
};

window.NotFoundPage = function ({ route }) {
  return html`
    <div style=${{ maxWidth: "480px", margin: "var(--s7) auto", textAlign: "center" }}>
      <div style=${{ color: "var(--ink-faint)", marginBottom: "var(--s3)" }}><${Icon} name="search" size=${26} /></div>
      <h1 class="display-title">That page doesn't exist</h1>
      <p class="caption">There's nothing at <b>${route}</b> — it may be an old or mistyped link.</p>
      <button class="btn primary" onClick=${() => nav("/overview")}>Back to your overview</button>
    </div>`;
};

/* Idle session guard: after IDLE_MIN minutes without input, warn with a
   60-second countdown and a "stay signed in" option; sign out if ignored.
   Client-side policy only — no security logic changed. */
window.IdleGuard = function ({ onSignOut }) {
  const IDLE_MIN = window.LUMI_IDLE_MIN || 30;   // overridable for testing
  const [warn, setWarn] = useState(false);
  const [left, setLeft] = useState(60);
  const last = useRef(Date.now());
  const warnRef = useRef(false);
  useEffect(() => { warnRef.current = warn; }, [warn]);
  useEffect(() => {
    let throttled = 0;
    const touch = () => { const now = Date.now(); if (now - throttled > 2000) { throttled = now; last.current = now; } };
    ["mousemove", "mousedown", "keydown", "scroll", "touchstart"].forEach(ev =>
      window.addEventListener(ev, touch, { passive: true }));
    const iv = setInterval(() => {
      const idleMin = window.LUMI_IDLE_MIN || IDLE_MIN;
      if (!warnRef.current && Date.now() - last.current > idleMin * 60000) { setWarn(true); setLeft(60); }
    }, window.LUMI_IDLE_MIN ? 1000 : 15000);
    return () => { clearInterval(iv); ["mousemove", "mousedown", "keydown", "scroll", "touchstart"].forEach(ev =>
      window.removeEventListener(ev, touch)); };
  }, []);
  useEffect(() => {
    if (!warn) return;
    const iv = setInterval(() => setLeft(l => {
      if (l <= 1) { clearInterval(iv); onSignOut(); return 0; }
      return l - 1;
    }), 1000);
    return () => clearInterval(iv);
  }, [warn]);
  if (!warn) return null;
  const stay = async () => { try { await api("/api/me"); } catch (e) { /* handled globally */ } last.current = Date.now(); setWarn(false); };
  return html`
    <div class="modal-back" role="alertdialog" aria-label="Session timeout warning">
      <div class="modal" style=${{ maxWidth: "420px", textAlign: "center" }}>
        <h2 class="section-title">Still there?</h2>
        <p>You've been inactive for a while. For your organisation's data safety we'll sign you
        out in <span class="idle-count">${left}</span> seconds.</p>
        <div class="row" style=${{ justifyContent: "center" }}>
          <button class="btn primary" autoFocus onClick=${stay}>Stay signed in</button>
          <button class="btn" onClick=${onSignOut}>Sign out now</button>
        </div>
      </div>
    </div>`;
};

window.sectionList = function (qIndex) {
  const m = new Map();
  for (const q of qIndex.questions) {
    if (q.locked || !q.subpower) continue;
    if (!m.has(q.subpower)) m.set(q.subpower, { name: q.subpower, order: q.sub_power_order || 999, count: 0 });
    m.get(q.subpower).count++;
  }
  return Array.from(m.values()).sort((a, b) => a.order - b.order);
};

/* Day-one model: explore everything; insights are the carrot. The chip is the
   persistent, quiet progress indicator — always visible, never nagging. */
window.ClockChip = function ({ contrib }) {
  const pct = Math.round(contrib.core_pct || 0);
  const label = contrib.reduced
    ? "Benchmark paused — complete to restore"
    : !contrib.clock_started
    ? "Next step: accept the data terms"
    : `Reward data ${pct}% · ${contrib.days_left} day${contrib.days_left === 1 ? "" : "s"} to unlock insights`;
  return html`
    <button class=${"clock-chip" + (contrib.reduced ? " paused" : "")} title=${!contrib.clock_started
      ? "Your Admin accepts the Data Contribution Terms once, on the Submit data page — your 30 days to contribute start then."
      : "Complete your key reward questions to unlock your insights — the £ opportunity, board pack and biggest gaps. 'Not applicable' counts as an answer."} onClick=${() => nav("/submission")}>
      <span class="clock-ring"><svg viewBox="0 0 20 20" width="14" height="14">
        <circle cx="10" cy="10" r="8" fill="none" stroke="var(--blue-tint-2)" stroke-width="3"/>
        <circle cx="10" cy="10" r="8" fill="none" stroke="var(--blue)" stroke-width="3" stroke-linecap="round"
          stroke-dasharray=${Math.max(2, Math.min(100, pct / 90 * 100)) * 0.503 + " 100"} transform="rotate(-90 10 10)"/>
      </svg></span>
      ${label}
    </button>`;
};

/* Gentle reminders as the deadline nears (7 days / 1 day), and the fair,
   forewarned day-30 message. Quiet banners, never modals. */
window.ContributionBanner = function ({ contrib }) {
  if (contrib.insights_unlocked || !contrib.clock_started) return null;
  const pct = Math.round(contrib.core_pct || 0);
  if (contrib.reduced) return html`
    <div class="card contrib-banner paused">
      <div>
        <b>Your full benchmark is paused.</b>
        <div class="caption">The 30 days passed before your reward data reached 90% — everything you've explored is still here,
          and a sample stays open below. Complete your reward questions to restore the full benchmark and unlock your insights. You're at ${pct}%.</div>
      </div>
      <button class="btn primary small" onClick=${() => nav("/submission")}>Complete your reward data</button>
    </div>`;
  if (contrib.days_left > 7) return null;
  return html`
    <div class="card contrib-banner">
      <div>
        <b>${contrib.days_left} day${contrib.days_left === 1 ? "" : "s"} left to unlock your insights.</b>
        <div class="caption">You're at ${pct}% of your key reward questions — complete them and the £ opportunity,
          board pack and biggest gaps open up with your real position.</div>
      </div>
      <button class="btn primary small" onClick=${() => nav("/submission")}>Continue your submission</button>
    </div>`;
};

/* The warm first-run welcome on the overview — confident and light, one
   obvious next step. Founding members contribute data, never payment. */
window.WelcomeHero = function ({ contrib, pool, me }) {
  const pct = Math.round(contrib.core_pct || 0);
  const role = me && me.user ? me.user.role : "viewer";
  if (!contrib.terms_accepted) {
    /* First-run "you're set up — next steps": welcoming, not a wizard. */
    const steps = [
      { n: 1, label: "Review and accept the Data Contribution Terms", done: false,
        hint: role === "admin" ? "You accept once, for the whole organisation — your 30 days start then."
                               : "Your Admin does this — nothing is needed from you yet." },
      { n: 2, label: "Complete your reward data", done: false,
        hint: "180 questions by section, autosaved — insights unlock once your key questions are answered." },
      { n: 3, label: "Invite your team", done: false,
        hint: "Contributors fill the questionnaire; Viewers see the benchmark." },
    ];
    return html`
      <div class="card welcome-hero">
        <div style=${{ flex: "1.6 1 320px", minWidth: "280px" }}>
          <div class="row" style=${{ gap: "var(--s2)", marginBottom: "4px" }}>
            <span style=${{ color: "var(--blue)" }}><${Icon} name="sparkle" size=${18} /></span>
            <b style=${{ fontFamily: "var(--font-head)", fontSize: "var(--fs-h3)" }}>You're set up — here's what's next</b>
          </div>
          <p style=${{ margin: "2px 0 0" }}>Explore your reward benchmark below — every metric and all
            ${" "}${pool.responding_orgs} peer organisations are open to you from day one. Your 30 days to
            contribute only start when your Admin accepts the Data Contribution Terms — setup time is never
            counted against you.</p>
        </div>
        <div style=${{ flex: "1.2 1 280px", minWidth: "260px" }}>
          ${steps.map(st => html`
            <div key=${st.n} class="next-step">
              <span class="next-step-n">${st.n}</span>
              <div><b>${st.label}</b><div class="caption">${st.hint}</div></div>
            </div>`)}
          <div class="row" style=${{ marginTop: "var(--s2)" }}>
            ${role === "admin" && html`<button class="btn primary" onClick=${() => nav("/submission")}>Review the data terms</button>`}
            ${role === "admin" && html`<button class="btn" onClick=${() => nav("/team")}>Invite your team</button>`}
            ${role !== "admin" && html`<button class="btn primary" onClick=${() => nav("/superpower/Reward")}>Explore the benchmark</button>`}
          </div>
        </div>
      </div>`;
  }
  return html`
    <div class="card welcome-hero">
      <div style=${{ flex: "1.6 1 320px", minWidth: "280px" }}>
        <div class="row" style=${{ gap: "var(--s2)", marginBottom: "4px" }}>
          <span style=${{ color: "var(--blue)" }}><${Icon} name="sparkle" size=${18} /></span>
          <b style=${{ fontFamily: "var(--font-head)", fontSize: "var(--fs-h3)" }}>
            ${pct < 1 ? "Welcome to lumi" : "You're on your way"}</b>
        </div>
        <p style=${{ margin: "2px 0 0" }}>${pct < 1
          ? html`Explore your reward benchmark below — every metric and all ${pool.responding_orgs} peer organisations are open to you from day one. Complete your reward data within 30 days to unlock your insights: the £ opportunity, your board pack, and your biggest gaps to peers.`
          : html`Keep going — at 90% your insights unlock immediately: the £ opportunity, your board pack, and your biggest gaps to peers. You see the pool because you're part of it.`}</p>
      </div>
      <div style=${{ flex: "1 1 240px", minWidth: "220px" }}>
        <div class="row spread" style=${{ marginBottom: "4px" }}>
          <span class="caption"><b class="num">${pct}%</b> of your key reward questions</span>
          <span class="caption num">${contrib.days_left} days left</span>
        </div>
        <div class="progressbar" style=${{ height: "10px" }}><div style=${{ width: Math.min(100, pct / 90 * 100) + "%" }}></div></div>
        <div class="caption" style=${{ margin: "4px 0 10px" }}>Insights unlock at 90% — everything autosaves.</div>
        <button class="btn primary" onClick=${() => nav("/submission")}>${pct < 1 ? "Submit your data" : "Continue your submission"}</button>
      </div>
    </div>`;
};

function cutHint(cut, cuts, me) {
  const total = (me.peer_pool || {}).responding_orgs || "all";
  if (cut.dim === "industry") return `Comparing against ${cut.value} only — change here.`;
  if (cut.dim === "fte_band") return `Comparing against ${cut.value}-employee organisations — change here.`;
  if (cut.dim === "twin") return "Comparing against organisations most like yours — change here.";
  return `Comparing against all ${total} organisations — change here.`;
}

function navCls(route, path) {
  const active = path === "/overview" ? (route === "/" || route === "" || route.startsWith("/overview")) : route.startsWith(path);
  return "nav-item" + (active ? " active" : "");
}

function SearchPop({ qIndex, search, onGo }) {
  const s = search.toLowerCase();
  const hits = qIndex.questions.filter(q => (q.title || "").toLowerCase().includes(s)).slice(0, 12);
  return html`
    <div class="searchpop">
      ${hits.length === 0 && html`
        <div class="search-hit" style=${{ cursor: "default" }}>
          <div class="caption">We don't benchmark “${search}” yet.</div>
          <button class="btn small" style=${{ marginTop: "var(--s2)" }}
            onClick=${() => window.openMetricRequest(search, "search")}>Request this metric</button>
        </div>`}
      ${hits.map(q => html`
        <div key=${q.id} class="search-hit" onClick=${() => onGo(q)}>
          <b style=${{ fontSize: "13px" }}>${q.title}</b> ${q.locked && html`<${Icon} name="lock" size=${11} style=${{ verticalAlign: "-1px", color: "var(--ink-faint)" }} />`}
          <div class="caption">${q.superpower}${q.subpower ? " · " + q.subpower : ""} · ${q.category} · n=${q.n}</div>
        </div>`)}
    </div>`;
}

// single-metric page (deep links from analyst chips / opportunity tile)
function MetricPage({ qid, me, cut, cuts, prefs, onPref, onPin, pinnedIds }) {
  const [cards, setCards] = useState(null);   // {all, sector, size}
  const [err, setErr] = useState(null);
  const org = me.org;
  const chartRef = useRef(null);
  useEffect(() => {
    setCards(null); setErr(null);
    const want = [["all", "cut=all"]];
    if (org.industry) want.push(["sector", "cut=industry&cut_value=" + encodeURIComponent(org.industry)]);
    if (org.fte_band) want.push(["size", "cut=fte_band&cut_value=" + encodeURIComponent(org.fte_band)]);
    // the same per-cut aggregates the peer-cut selector uses — no new maths
    Promise.all(want.map(([k, qs]) => api(`/api/benchmark/${qid}?` + qs).then(c => [k, c])))
      .then(entries => setCards(Object.fromEntries(entries)))
      .catch(e => setErr(e.message));
  }, [qid, org.industry, org.fte_band]);
  if (err) return html`<${EmptyState} title="Couldn't load this metric"
    body=${err + " — nothing is lost; it usually works on a retry."}
    action=${html`<button class="btn small primary" onClick=${() => window.location.reload()}>Retry</button>`} />`;
  if (!cards) return html`
    <div>
      <div class="skel" style=${{ height: "32px", width: "440px", marginBottom: "10px" }}></div>
      <div class="skel" style=${{ height: "18px", width: "560px", marginBottom: "18px" }}></div>
      <div class="skel" style=${{ height: "220px", marginBottom: "14px", borderRadius: "var(--radius)" }}></div>
      <div class="skel" style=${{ height: "320px", borderRadius: "var(--radius)" }}></div>
    </div>`;

  // active cut for the big chart follows the global peer selector
  const activeKey = cut.dim === "industry" && cards.sector ? "sector" : cut.dim === "fte_band" && cards.size ? "size" : "all";
  const c = cards[activeKey] || cards.all;
  const pos = cardPosition(c);
  const sent = humanSentence(c);
  const chart = normaliseChart(c, prefs[c.id] && prefs[c.id].chart);
  const period = (me.snapshots && me.snapshots[0] && me.snapshots[0].collection_window) || "";
  const backTo = "/superpower/" + c.superpower + (c.subpower ? "?sub=" + encodeURIComponent(c.subpower) : "");
  const goBack = () => {
    let hasReturn = false;
    try { hasReturn = !!sessionStorage.getItem("lumi-return"); } catch (e) {}
    if (hasReturn) window.history.back(); else nav(backTo);
  };
  const doExport = async (mode) => {
    const res = await exportCardPNG(chartRef.current, {
      title: c.title, cutLabel: c.cut.label, n: c.n, window: period,
      suffix: c.you && c.you.percentile != null ? `You: ${c.you.display} (${pLabel(c.you.percentile)})` : null,
    }, mode);
    toast(res === "downloaded" ? "Chart downloaded — includes title, n, peer group and the sample-data caveat" : res === "copied" ? "Chart copied to clipboard" : "Nothing to export yet");
  };
  const share = () => { navigator.clipboard.writeText(window.location.href.split("#")[0] + "#" + ("/metric/" + qid)); toast("Link to this metric copied"); };

  const CUT_ROWS = [
    { key: "all", label: "All peers" },
    { key: "sector", label: org.industry ? "Your sector: " + org.industry : null },
    { key: "size", label: org.fte_band ? "Your size: " + org.fte_band + " FTE" : null },
  ];
  return html`
    <div class="metric-page">
      <button class="btn quiet" onClick=${goBack}>← Back</button>
      <div class="row spread" style=${{ alignItems: "flex-start", marginTop: "8px", gap: "var(--s4)" }}>
        <div style=${{ minWidth: 0 }}>
          <h1 class="display-title" style=${{ marginBottom: "4px" }}>${c.title}</h1>
          <p class="caption" style=${{ margin: "0 0 10px", maxWidth: "640px" }}>${c.question_text}</p>
          <div class="row" style=${{ gap: "var(--s2)" }}>
            <${Chip} kind="accent">${org.name}<//>
            ${org.industry && html`<${Chip}>${org.industry}<//>`}
            ${org.fte_band && html`<${Chip}>${org.fte_band} FTE<//>`}
            ${org.hq_region && html`<${Chip}>${org.hq_region}<//>`}
            ${period && html`<${Chip}>${period}<//>`}
            <span class="chip warn hastip" style=${{ position: "relative", cursor: "help" }}>Illustrative sample data
              <span class="tip">The current peer pool is realistic but synthetic seed data, generated to behave like a UK benchmark while real member submissions build up. It must not be read as real benchmark data.</span></span>
          </div>
        </div>
        ${pos && html`<span class=${"pos-pill lg " + pos.kind} title=${pos.tip}>${pos.arrow} ${pos.label}</span>`}
      </div>

      ${sent.lead && html`<p class="metric-lead">${sent.lead}</p>`}

      <h2 class="section-title" style=${{ marginTop: "var(--s5)" }}>How you compare, peer group by peer group</h2>
      <p class="caption" style=${{ marginTop: "-4px" }}>The same metric through three lenses — the nuance a single number hides.</p>
      <div class="card" style=${{ padding: "var(--s4)" }}>
        ${CUT_ROWS.filter(r => r.label).map(r => {
          const rc = cards[r.key];
          if (!rc) return null;
          const rpos = cardPosition(rc);
          return html`
            <div key=${r.key} class="cut-row">
              <div class="cut-row-label">
                <b>${r.label}</b>
                <div class="caption num">n=${rc.n}</div>
                ${rpos && html`<span class=${"pos-pill " + rpos.kind} title=${rpos.tip}>${rpos.arrow} ${rpos.label}</span>`}
              </div>
              <div class="cut-row-chart">
                ${rc.suppressed ? html`
                  <div class="suppressed-box" style=${{ minHeight: "90px" }}>
                    <b>Not enough organisations to show this safely</b>
                    <div class="caption">Fewer than 5 organisations in this peer group answered — protecting every member's data comes first.</div>
                  </div>` :
                html`<${CardBody} card=${rc} chart=${normaliseChart(rc, null)} showP1090=${false} showValues=${false} fav=${rpos ? rpos.kind : null} />`}
              </div>
            </div>`;
        })}
        ${!org.industry && html`<div class="caption" style=${{ marginTop: "8px" }}>Declare your sector and size in <a href="#/submission">your submission</a> to see those comparisons.</div>`}
      </div>

      <h2 class="section-title" style=${{ marginTop: "var(--s6)" }}>The full picture — ${c.cut.label}</h2>
      <div class="card" style=${{ padding: "var(--s5)" }} ref=${chartRef}>
        ${c.suppressed ? html`
          <${EmptyState} title="Not enough organisations to show this safely"
            body="Fewer than 5 organisations in this peer group answered this question." />` : html`
          <div class="metric-xl">
            <${CardBody} card=${c} chart=${chart} showP1090=${true} showValues=${true} fav=${pos ? pos.kind : null} xl=${true} />
          </div>
          <${ExactFigures} card=${c} />`}
      </div>

      <div class="grid2" style=${{ marginTop: "var(--s5)", gap: "var(--s4)" }}>
        <div class="card" style=${{ padding: "var(--s5)" }}>
          <h2 class="section-title">What this measures</h2>
          ${c.definition && html`<p>${c.definition}</p>`}
          ${c.help_text && html`<p class="caption">${c.help_text}</p>`}
          <p class="caption"><${Term} word="percentile">Percentiles<//> are calculated with linear interpolation across all
          valid peer answers; medians are used rather than averages. Any figure resting on fewer than 5 organisations is
          ${" "}<${Term} word="suppressed">suppressed<//>. Full method in the <a href="#/methodology">methodology</a>.</p>
        </div>
        <div class="card" style=${{ padding: "var(--s5)" }}>
          <h2 class="section-title">What this means for you</h2>
          <${WhatThisMeans} card=${c} pos=${pos} defaultOpen=${true} />
          <div class="row" style=${{ marginTop: "var(--s3)", flexWrap: "wrap" }}>
            <button class="btn" onClick=${() => doExport("download")}><${Icon} name="download" size=${13} /> Download chart (PNG)</button>
            <button class="btn" onClick=${share}><${Icon} name="link" size=${13} /> Copy link to this metric</button>
            <button class="btn quiet" onClick=${() => window.openMetricRequest(c.title, "metric-page")}>Request a related metric</button>
          </div>
        </div>
      </div>
      <div class="caption" style=${{ margin: "var(--s4) 0" }}>
        From <a href=${"#" + backTo}>${c.subpower || c.superpower}</a> in your reward benchmark.
      </div>
    </div>`;
}

/* Exact figures: the analyst's row — your value, percentile, peer quartiles, n. */
function ExactFigures({ card: c }) {
  const cells = [];
  if (c.type === "numeric" && c.block) {
    if (c.you && c.you.display != null) cells.push(["You", c.you.display + (c.you.percentile != null ? " · " + pLabel(c.you.percentile) : "")]);
    for (const [k, lbl] of [["p25", "Peer P25"], ["p50", "Peer median"], ["p75", "Peer P75"]]) {
      if (c.block[k] != null) cells.push([lbl, fmtValue(c.block[k], c.unit)]);
    }
  } else if (c.block && c.block.options) {
    if (c.you && c.you.label) {
      const mine = c.block.options.find(o => o.label === c.you.label);
      cells.push(["Your answer", c.you.label + (mine ? ` (${mine.pct}% of peers)` : "")]);
    }
    const top = [...c.block.options].sort((a, b) => b.pct - a.pct)[0];
    if (top) cells.push(["Most common", `${top.label} (${top.pct}%)`]);
  }
  cells.push(["Organisations", "n=" + c.n]);
  return html`
    <div class="exact-figs">
      ${cells.map(([k, v], i) => html`<div key=${i}><span class="caption">${k}</span><b class="num">${v}</b></div>`)}
    </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${ErrorBoundary}><${App} /><//>`);
