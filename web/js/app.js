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
  }, [me && me.org && me.org.name]);

  if (me === undefined) return html`<div class="auth-wrap"><${Spinner} /></div>`;
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
  const gated = !me.benchmark_unlocked;

  let page = null, m;
  if (route.startsWith("/superpower/")) {
    const [sp, qs] = route.slice("/superpower/".length).split("?");
    const focusQ = qs && new URLSearchParams(qs).get("focus");
    page = html`<${SuperpowerPage} ...${pageProps} sp=${decodeURIComponent(sp)} focusQ=${focusQ} />`;
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
          <div class="nav-label">Superpowers</div>
          ${SUPERPOWERS.map(sp => html`
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
          <span class="caption" style=${{ fontWeight: 600 }}>Compare with</span>
          <select class="ctl" value=${cut.dim === "all" ? "all" : cut.dim === "twin" ? "twin" : cut.dim + "::" + cut.value}
            onChange=${e => { if (e.target.value === "twin-info") { setTwinOpen(true); } else setGlobalCut(e.target.value); }}>
            <option value="all">All peers (${(me.peer_pool || {}).responding_orgs || "—"})</option>
            ${cuts && cuts.org_industry && html`<option value=${"industry::" + cuts.org_industry}>${cuts.org_industry} (${cuts.industries[cuts.org_industry] || "?"})</option>`}
            ${cuts && Object.keys(cuts.industries || {}).filter(i => i !== (cuts || {}).org_industry).map(i =>
              html`<option key=${i} value=${"industry::" + i}>${i} (${cuts.industries[i]})</option>`)}
            ${cuts && Object.keys(cuts.fte_bands || {}).map(b =>
              html`<option key=${b} value=${"fte_band::" + b}>${b} FTE (${cuts.fte_bands[b]})</option>`)}
            ${cuts && cuts.twin_available && html`<option value="twin">Organisations like you</option>`}
          </select>
          ${cut.dim === "twin" && html`<button class="btn small" onClick=${() => setTwinOpen(true)}>Why these peers?</button>`}
          <div style=${{ position: "relative", flex: 1, maxWidth: "380px" }}>
            <span style=${{ position: "absolute", left: "10px", top: "9px", color: "var(--ink-3)", pointerEvents: "none" }}><${Icon} name="search" size=${14} /></span>
            <input class="ctl" style=${{ width: "100%", maxWidth: "none", paddingLeft: "32px" }} placeholder="Search 778 benchmarks…"
              value=${search} onInput=${e => setSearch(e.target.value)} />
            ${search.length > 1 && qIndex && html`<${SearchPop} qIndex=${qIndex} search=${search} onGo=${(q) => { setSearch(""); nav("/superpower/" + q.superpower + "?focus=" + q.id); }} />`}
          </div>
          <button class="btn feature" onClick=${() => setAnalystOpen(true)}><${Icon} name="sparkle" size=${14} /> Ask lumi</button>
        </div>
        <main class="content">
          ${gated && benchRoute ?
            html`<div class="watermark" style=${{ minHeight: "70vh" }} aria-hidden="false">
              <div style=${{ filter: "blur(2px)", opacity: 0.45, pointerEvents: "none" }}>${page}</div>
            </div>
            <div class="row" style=${{ justifyContent: "center", marginTop: "-46vh", position: "relative", zIndex: 31 }}>
              <button class="btn primary" onClick=${() => nav("/submission")}>Complete your submission (${me.core_completion_pct}% of Core done)</button>
            </div>` :
            page}
        </main>
      </div>
      ${analystOpen && html`<${AnalystPane} onClose=${() => setAnalystOpen(false)} />`}
      ${twinOpen && html`<${PeerTwinPanel} onClose=${() => setTwinOpen(false)} onUse=${() => setGlobalCut("twin")} />`}
    </div>`;
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
      ${hits.length === 0 && html`<div class="search-hit caption">No benchmarks match “${search}”.</div>`}
      ${hits.map(q => html`
        <div key=${q.id} class="search-hit" onClick=${() => onGo(q)}>
          <b style=${{ fontSize: "13px" }}>${q.title}</b> ${q.locked && html`<${Icon} name="lock" size=${11} style=${{ verticalAlign: "-1px", color: "var(--ink-3)" }} />`}
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
