/* Read-only share viewer — no login; the API enforces what a link can see. */
/* global html, useState, useEffect, useRef, api, Chip, Spinner, EmptyState, BenchmarkCard, BoardPackView, Term */

/* The board-pack is laid out at a fixed A4 width (210mm ≈ 794px). On a phone that
   overflows and scrolls sideways. Wrap it in a viewport-fitting shell: when the
   available width is narrower than the page, scale the whole A4 page down to fit
   (transform-origin top-centre) and collapse the wrapper to the scaled height so
   there's no dead space below. Wide screens render 1:1 (scale never exceeds 1).
   Print is untouched — the wrapper sets --pack-scale:1 and screen-only transform
   is dropped under @media print (see app.css .pack-fit). */
function PackFit({ children }) {
  const wrapRef = useRef(null);
  const innerRef = useRef(null);
  const [scale, setScale] = useState(1);
  const [innerH, setInnerH] = useState(null);
  useEffect(() => {
    const measure = () => {
      const wrap = wrapRef.current, inner = innerRef.current;
      if (!wrap || !inner) return;
      const avail = wrap.clientWidth;
      const natural = inner.scrollWidth || inner.offsetWidth;
      const s = natural > 0 ? Math.min(1, avail / natural) : 1;
      setScale(s);
      setInnerH(inner.offsetHeight * s);
    };
    measure();
    window.addEventListener("resize", measure);
    // pages render asynchronously (charts, async pack fetch already resolved here);
    // a couple of deferred passes catch late layout without a heavy observer.
    const t1 = setTimeout(measure, 60), t2 = setTimeout(measure, 400);
    let ro = null;
    if (window.ResizeObserver && innerRef.current) {
      ro = new ResizeObserver(measure);
      ro.observe(innerRef.current);
    }
    return () => {
      window.removeEventListener("resize", measure);
      clearTimeout(t1); clearTimeout(t2);
      if (ro) ro.disconnect();
    };
  }, []);
  return html`
    <div ref=${wrapRef} class="pack-fit" style=${{ height: innerH != null && scale < 1 ? innerH + "px" : undefined }}>
      <div ref=${innerRef} class="pack-fit-inner" style=${{ "--pack-scale": String(scale) }}>
        ${children}
      </div>
    </div>`;
}

function ShareApp() {
  const token = window.location.pathname.split("/").pop();
  const [data, setData] = useState(undefined);
  useEffect(() => {
    api(`/api/share/${token}/data`).then(setData).catch(e => setData({ error: e.message }));
  }, [token]);
  if (data === undefined) return html`<div class="auth-wrap"><${Spinner} /></div>`;
  if (data.error) return html`
    <div class="auth-wrap"><div class="card auth-card" style=${{ textAlign: "center" }}>
      <div class="logo" style=${{ padding: 0 }}>lumi<span>.benchmark</span></div>
      <div style=${{ fontSize: "var(--fs-display)", margin: "var(--s4) 0 var(--s2)" }}>⏳</div>
      <b>This share link is no longer available</b>
      <p class="caption">It may have expired or been revoked by the organisation that created it.</p>
    </div></div>`;
  if (data.kind === "boardpack") {
    return html`
      <div class="share-boardpack" style=${{ padding: "var(--s5) var(--s3)" }}>
        <div class="row spread no-print" style=${{ maxWidth: "210mm", margin: "0 auto var(--s4)" }}>
          <span class="caption">Shared read-only by ${data.org_name} · powered by lumi</span>
          <button class="btn primary" onClick=${() => window.print()}>Download PDF</button>
        </div>
        <${PackFit}>
          <${BoardPackView} packId=${null} shared=${true} sharedData=${data} />
        <//>
      </div>`;
  }
  const h = data.headline;
  return html`
    <div class="share-dashboard" style=${{ maxWidth: "1180px", margin: "0 auto", padding: "var(--s5) var(--s4)" }}>
      <div class="row spread" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <div class="logo" style=${{ padding: 0 }}>lumi<span>.benchmark</span></div>
          <h1 class="display-title" style=${{ marginTop: "var(--s2)" }}>${data.org_name}</h1>
          <div class="caption">Shared read-only benchmark view · peer group: ${data.cut.dim === "all" ? "All peers" : data.cut.value} (${(data.peer_pool || {}).responding_orgs} organisations)</div>
        </div>
        <${Chip} kind="accent">Read-only<//>
      </div>
      <div class="card banner" style=${{ marginBottom: "var(--s4)" }}>
        <div>
          <div class="section-title" style=${{ marginBottom: "2px" }}>Above the market median on ${h.above_median} of ${h.comparable_metrics} comparable metrics</div>
          <div class="caption">${h.below_median} below · ${h.broadly_in_line} broadly in line · figures resting on fewer than 5 organisations are never shown</div>
        </div>
      </div>
      <div class="grid2" style=${{ marginBottom: "var(--s4)" }}>
        <div><h2 class="section-title">Where they lead</h2>
          ${data.callouts.strengths.map((t, i) => html`<div key=${i} class="callout good">${t}</div>`)}</div>
        <div><h2 class="section-title">Biggest gaps to the market</h2>
          ${data.callouts.gaps.map((t, i) => html`<div key=${i} class="callout bad">${t}</div>`)}</div>
      </div>
      <div class="bench-grid">
        ${data.cards.map(c => html`<${BenchmarkCard} key=${c.id} card=${c} prefs=${{}} />`)}
      </div>
      <div class="caption" style=${{ margin: "var(--s5) 0", textAlign: "center" }}>
        Generated by lumi people analytics benchmarking · percentiles use linear interpolation · n &lt; 5 suppressed throughout
      </div>
    </div>`;
}

ReactDOM.createRoot(document.getElementById("root")).render(html`<${ShareApp} />`);
