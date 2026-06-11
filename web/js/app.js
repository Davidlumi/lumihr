/* lumi root app: shell, navigation, global peer filter, search, routing. */
/* global html, useState, useEffect, useMemo, useRef, api, useRoute, nav, Chip, Spinner, AuthScreen,
   OverviewPage, SuperpowerPage, MyViewPage, MyDataPage, MethodologyPage, GapRegisterPage,
   BoardPackPage, BoardPackView, AnalystPane, PeerTwinPanel, SharesPage, TeamPage, SettingsPage,
   UpgradePage, SubmissionPage, BenchmarkCard, SUPERPOWERS, SP_ICONS, EmptyState, cutLabelOf, cutKeyOf */

function App() {
  const route = useRoute();
  const [me, setMe] = useState(undefined);          // undefined=loading, null=unauth
  const [cut, setCut] = useState({ dim: "all", value: null });
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
  else if (route.startsWith("/upgrade")) page = html`<${UpgradePage} />`;
  else page = html`<${OverviewPage} ...${pageProps} />`;

  const benchRoute = route.startsWith("/overview") || route.startsWith("/superpower") ||
    route.startsWith("/myview") || route.startsWith("/metric") || route.startsWith("/gap-register") || route === "" || route === "/";

  return html`
    <div class="shell">
      <nav class="sidebar no-print">
        <a class="logo" href="#/overview">lumi<span>.benchmark</span></a>
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
          ${me.user.role === "admin" && html`<button class=${navCls(route, "/submission")} onClick=${() => nav("/submission")}><${Icon} name="pencil" size=${15} /> Submit data</button>`}
          <button class=${navCls(route, "/team")} onClick=${() => nav("/team")}><${Icon} name="users" size=${15} /> Team</button>
          ${me.user.role === "admin" && html`<button class=${navCls(route, "/shares")} onClick=${() => nav("/shares")}><${Icon} name="link" size=${15} /> Manage shares</button>`}
          <button class=${navCls(route, "/settings")} onClick=${() => nav("/settings")}><${Icon} name="sliders-v" size=${15} /> Settings</button>
          <button class=${navCls(route, "/methodology")} onClick=${() => nav("/methodology")}><${Icon} name="book-open" size=${15} /> Methodology</button>
        </div>
        <div class="nav-group nav-id" style=${{ marginTop: "auto" }}>
          <div class="who">${me.user.display_name || me.user.email}</div>
          <div class="org">${me.org.name}</div>
          ${me.user.preview_as_core && html`<div style=${{ marginBottom: "4px" }}><span class="chip warn">Previewing as Core</span></div>`}
          <button class="nav-item" onClick=${async () => { await api("/api/auth/logout", { method: "POST" }); setMe(null); }}><${Icon} name="log-out" size=${15} /> Sign out</button>
        </div>
      </nav>
      <div class="main">
        <div class="topbar no-print">
          <div class="ctlgroup">
            <select class=${"ctl peer-ctl" + (cut.dim !== "all" ? " narrowed" : "")}
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
                value=${search} onInput=${e => setSearch(e.target.value)} />
              ${search.length > 1 && qIndex && html`<${SearchPop} qIndex=${qIndex} search=${search} onGo=${(q) => { setSearch(""); nav("/superpower/" + q.superpower + "?focus=" + q.id); }} />`}
            </div>
          </div>
          <div class="ctlgroup" style=${{ marginLeft: "auto", alignItems: "flex-end" }}>
            <div class="row" style=${{ gap: "var(--s2)", flexWrap: "nowrap" }}>
              ${contrib && !contrib.insights_unlocked && html`<${ClockChip} contrib=${contrib} />`}
              <button class="btn quiet" title="Ask us to benchmark something new" onClick=${() => setMetricReq({ prefill: "", source: "button" })}>
                <${Icon} name="user-plus" size=${13} /> Request a metric</button>
              <button class="btn feature" onClick=${() => setAnalystOpen(true)}><${Icon} name="sparkle" size=${14} /> Ask lumi</button>
            </div>
            <div class="hint" style=${{ textAlign: "right" }}>Ask in plain English.</div>
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
    : `Reward data ${pct}% · ${contrib.days_left} day${contrib.days_left === 1 ? "" : "s"} to unlock insights`;
  return html`
    <button class=${"clock-chip" + (contrib.reduced ? " paused" : "")} title="Complete 90% of your Core reward questions to unlock your insights — the £ opportunity, board pack and biggest gaps." onClick=${() => nav("/submission")}>
      <span class="clock-ring"><svg viewBox="0 0 20 20" width="14" height="14">
        <circle cx="10" cy="10" r="8" fill="none" stroke="var(--plum-tint-2)" stroke-width="3"/>
        <circle cx="10" cy="10" r="8" fill="none" stroke="var(--plum)" stroke-width="3" stroke-linecap="round"
          stroke-dasharray=${Math.max(2, Math.min(100, pct / 90 * 100)) * 0.503 + " 100"} transform="rotate(-90 10 10)"/>
      </svg></span>
      ${label}
    </button>`;
};

/* Gentle reminders as the deadline nears (7 days / 1 day), and the fair,
   forewarned day-30 message. Quiet banners, never modals. */
window.ContributionBanner = function ({ contrib }) {
  if (contrib.insights_unlocked) return null;
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
        <div class="caption">You're at ${pct}% of your Core reward questions — reach 90% and the £ opportunity,
          board pack and biggest gaps open up with your real position.</div>
      </div>
      <button class="btn primary small" onClick=${() => nav("/submission")}>Continue your submission</button>
    </div>`;
};

/* The warm first-run welcome on the overview — confident and light, one
   obvious next step. Founding members contribute data, never payment. */
window.WelcomeHero = function ({ contrib, pool }) {
  const pct = Math.round(contrib.core_pct || 0);
  return html`
    <div class="card welcome-hero">
      <div style=${{ flex: "1.6 1 320px", minWidth: "280px" }}>
        <div class="row" style=${{ gap: "var(--s2)", marginBottom: "4px" }}>
          <span style=${{ color: "var(--plum)" }}><${Icon} name="sparkle" size=${18} /></span>
          <b style=${{ fontFamily: "var(--font-head)", fontSize: "var(--fs-h3)" }}>
            ${pct < 1 ? "Welcome to lumi" : "You're on your way"}</b>
        </div>
        <p style=${{ margin: "2px 0 0" }}>${pct < 1
          ? html`Explore your reward benchmark below — every metric and all ${pool.responding_orgs} peer organisations are open to you from day one. Complete your reward data within 30 days to unlock your insights: the £ opportunity, your board pack, and your biggest gaps to peers.`
          : html`Keep going — at 90% your insights unlock immediately: the £ opportunity, your board pack, and your biggest gaps to peers. You see the pool because you're part of it.`}</p>
      </div>
      <div style=${{ flex: "1 1 240px", minWidth: "220px" }}>
        <div class="row spread" style=${{ marginBottom: "4px" }}>
          <span class="caption"><b class="num">${pct}%</b> of Core reward questions</span>
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
  const [card, setCard] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => {
    setCard(null);
    api(`/api/benchmark/${qid}?` + cutQS(cut)).then(setCard).catch(e => setErr(e.message));
  }, [qid, cutKeyOf(cut)]);
  if (err) return html`<${EmptyState} title="Couldn't load this metric" body=${err} />`;
  if (!card) return html`<div class="row" style=${{ justifyContent: "center", padding: "60px" }}><${Spinner} /></div>`;
  return html`
    <div style=${{ maxWidth: "560px" }}>
      <button class="btn quiet" onClick=${() => window.history.back()}>← Back</button>
      <div style=${{ marginTop: "10px" }}>
        <${BenchmarkCard} card=${card} prefs=${prefs} onPref=${onPref} onPin=${onPin}
          pinned=${pinnedIds.has(card.id)} cuts=${cuts} globalCut=${cutKeyOf(cut)} />
      </div>
      <div class="caption" style=${{ marginTop: "10px" }}>
        From <a href=${"#/superpower/" + card.superpower}>${card.superpower}</a>${card.subpower ? " · " + card.subpower : ""}.
      </div>
    </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
