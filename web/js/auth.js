/* Auth screens: sign in, register, reset, accept invite. */
/* global html, useState, useEffect, api, Spinner, LegalDocModal */

/* Minimal markdown-ish renderer for the terms documents (headings, bullets,
   bold) — enough to read them comfortably without a library. */
window.TermsText = function ({ text }) {
  const lines = (text || "").split("\n");
  const strong = (t) => {
    const parts = t.split(/\*\*/);
    return parts.map((p, i) => i % 2 ? html`<b key=${i}>${p}</b>` : p);
  };
  return html`<div class="terms-text">${lines.map((l, i) => {
    if (l.startsWith("# ")) return html`<h2 key=${i}>${l.slice(2)}</h2>`;
    if (l.startsWith("## ")) return html`<h3 key=${i}>${l.slice(3)}</h3>`;
    if (l.startsWith("- ")) return html`<div key=${i} class="terms-li">• ${strong(l.slice(2))}</div>`;
    if (!l.trim()) return html`<div key=${i} style=${{ height: "8px" }}></div>`;
    return html`<p key=${i}>${strong(l)}</p>`;
  })}</div>`;
};

window.TermsModal = function ({ kind, onClose }) {
  const [terms, setTerms] = useState(null);
  useEffect(() => { api("/api/terms").then(setTerms).catch(() => {}); }, []);
  const doc = terms && terms[kind];
  return html`
    <div class="modal-back" onClick=${onClose}>
      <div class="card" style=${{ maxWidth: "640px", width: "92%", maxHeight: "80vh", overflow: "auto", padding: "var(--s5)" }}
        onClick=${e => e.stopPropagation()}>
        ${!doc ? html`<${Spinner} />` : html`
          <${TermsText} text=${doc.text} />
          <div class="row spread" style=${{ marginTop: "var(--s4)" }}>
            <span class="chip">Current version · v${doc.version}</span>
            <button class="btn" onClick=${onClose}>Close</button>
          </div>`}
      </div>
    </div>`;
};

function TermsTick({ checked, onChange, children }) {
  return html`
    <label class="terms-tick">
      <input type="checkbox" checked=${checked} onChange=${e => onChange(e.target.checked)} />
      <span>${children}</span>
    </label>`;
}

window.AuthScreen = function ({ onAuthed, route }) {
  if (route.startsWith("/reset/")) return html`<${ResetForm} token=${route.split("/")[2]} onAuthed=${onAuthed} />`;
  if (route.startsWith("/invite/")) return html`<${InviteForm} token=${route.split("/")[2]} onAuthed=${onAuthed} />`;
  return html`<${LoginForm} onAuthed=${onAuthed} />`;
};

function Shell({ children, sub }) {
  const [doc, setDoc] = useState(null);
  return html`
    <div class="auth-wrap">
      <div class="card auth-card">
        <div class="logo" style=${{ padding: 0, marginBottom: "var(--s1)" }}>lumi<span>.benchmark</span></div>
        <div class="caption" style=${{ marginBottom: "var(--s5)" }}>${sub || "People analytics benchmarking for UK HR teams"}</div>
        ${children}
      </div>
      <div class="auth-footer">
        <button class="auth-foot-link" onClick=${() => setDoc("platform")}>Terms of Use</button>
        <span aria-hidden="true">·</span>
        <button class="auth-foot-link" onClick=${() => setDoc("privacy")}>Privacy Notice</button>
      </div>
      ${doc && html`<${LegalDocModal} docKey=${doc} onClose=${() => setDoc(null)} />`}
    </div>`;
}

function Field({ label, type, value, onInput, placeholder, autoFocus }) {
  return html`
    <div class="field">
      <label>${label}</label>
      <input type=${type || "text"} value=${value} placeholder=${placeholder || ""} autoFocus=${autoFocus}
        onInput=${e => onInput(e.target.value)} onKeyDown=${e => { if (e.key === "Enter") { const f = e.target.closest("form"); f && f.requestSubmit(); } }} />
    </div>`;
}

function LoginForm({ onAuthed }) {
  const [mode, setMode] = useState("login"); // login | register | forgot
  const [legalDoc, setLegalDoc] = useState(null);
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [orgName, setOrgName] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const go = async (e) => {
    e.preventDefault();
    setErr(null); setMsg(null); setBusy(true);
    try {
      if (mode === "login") { await api("/api/auth/login", { method: "POST", body: { email, password: pw } }); onAuthed(); }
      else if (mode === "register") { await api("/api/auth/register", { method: "POST", body: { org_name: orgName, email, password: pw, display_name: name, accept_platform_terms: tick } }); onAuthed(); }
      else { const r = await api("/api/auth/request-reset", { method: "POST", body: { email } }); setMsg(r.message); }
    } catch (ex) { setErr(ex.message); }
    setBusy(false);
  };
  return html`
    <${Shell} sub=${mode === "register" ? "Join the co-operative — benchmark against 220 UK organisations" : undefined}>
      <form onSubmit=${go}>
        ${mode === "register" && html`<${Field} label="Organisation name" value=${orgName} onInput=${setOrgName} placeholder="Acme Retail Ltd" autoFocus=${true} />`}
        ${mode === "register" && html`<${Field} label="Your name" value=${name} onInput=${setName} />`}
        <${Field} label="Work email" type="email" value=${email} onInput=${setEmail} placeholder="you@yourorg.co.uk" autoFocus=${mode === "login"} />
        ${mode !== "forgot" && html`<${Field} label="Password" type="password" value=${pw} onInput=${setPw} />`}
        ${mode === "register" && html`
          <${TermsTick} checked=${tick} onChange=${setTick}>
            I accept the lumi <a onClick=${e => { e.preventDefault(); setShowTerms(true); }} style=${{ cursor: "pointer" }}>Platform Terms of Use</a>.
          <//>`}
        ${mode === "register" && html`
          <div class="caption" style=${{ marginBottom: "var(--s3)" }}>
            lumi generates <a onClick=${e => { e.preventDefault(); setLegalDoc("ai_insights"); }} style=${{ cursor: "pointer" }}>AI Insights</a> — plain-language summaries of your benchmark figures (a description of your data, not advice). They're on by default; you can turn them off any time in Settings.
          </div>`}
        ${mode === "register" && html`<div class="caption" style=${{ marginBottom: "var(--s3)" }}>
          By continuing you agree to our <a onClick=${e => { e.preventDefault(); setLegalDoc("platform"); }} style=${{ cursor: "pointer" }}>Terms of Use</a>
          ${" "}and <a onClick=${e => { e.preventDefault(); setLegalDoc("privacy"); }} style=${{ cursor: "pointer" }}>Privacy Notice</a>.</div>`}
        ${err && html`<div class="error-text" style=${{ marginBottom: "var(--s3)" }}>${err}</div>`}
        ${msg && html`<div class="ok-text" style=${{ marginBottom: "var(--s3)" }}>${msg}</div>`}
        <button class="btn primary" style=${{ width: "100%", justifyContent: "center" }} disabled=${busy || (mode === "register" && !tick)}>
          ${busy ? html`<${Spinner} />` : mode === "login" ? "Sign in" : mode === "register" ? "Create organisation account" : "Send reset link"}
        </button>
        ${mode === "register" && html`<div class="caption" style=${{ marginTop: "var(--s2)" }}>
          You'll be your organisation's Admin. Before your team first submits data, you'll also review
          the Data Contribution Terms — your 30 days to contribute start then, not now.</div>`}
        ${showTerms && html`<${TermsModal} kind="platform" onClose=${() => setShowTerms(false)} />`}
        ${legalDoc && html`<${LegalDocModal} docKey=${legalDoc} onClose=${() => setLegalDoc(null)} />`}
      </form>
      <div class="row spread" style=${{ marginTop: "var(--s4)" }}>
        ${mode !== "login" ? html`<a onClick=${() => setMode("login")} style=${{ cursor: "pointer" }}>Sign in</a>` : html`<a onClick=${() => setMode("register")} style=${{ cursor: "pointer" }}>New organisation</a>`}
        ${mode !== "forgot" && html`<a onClick=${() => setMode("forgot")} style=${{ cursor: "pointer" }}>Forgotten password?</a>`}
      </div>
    <//>`;
}

function ResetForm({ token, onAuthed }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState(null);
  const [done, setDone] = useState(false);
  const go = async (e) => {
    e.preventDefault(); setErr(null);
    try { await api("/api/auth/reset", { method: "POST", body: { token, password: pw } }); setDone(true); }
    catch (ex) { setErr(ex.message); }
  };
  return html`
    <${Shell} sub="Choose a new password">
      ${done ? html`<div class="ok-text">Password updated.</div>
        <button class="btn primary" style=${{ marginTop: "var(--s3)" }} onClick=${() => { window.location.hash = "/"; window.location.reload(); }}>Sign in</button>` :
      html`<form onSubmit=${go}>
        <${Field} label="New password (8+ characters)" type="password" value=${pw} onInput=${setPw} autoFocus=${true} />
        ${err && html`<div class="error-text" style=${{ marginBottom: "var(--s3)" }}>${err}</div>`}
        <button class="btn primary" style=${{ width: "100%", justifyContent: "center" }}>Set password</button>
      </form>`}
    <//>`;
}

function InviteForm({ token, onAuthed }) {
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState(null);
  const [pw, setPw] = useState("");
  const [name, setName] = useState("");
  const [tick, setTick] = useState(false);
  const [showTerms, setShowTerms] = useState(false);
  const [aiDoc, setAiDoc] = useState(false);
  useEffect(() => { api("/api/invite/" + token).then(setInfo).catch(e => setErr(e.message)); }, [token]);
  const go = async (e) => {
    e.preventDefault(); setErr(null);
    try { await api("/api/auth/accept-invite", { method: "POST", body: { token, password: pw, display_name: name, accept_platform_terms: tick } }); onAuthed(); }
    catch (ex) { setErr(ex.message); }
  };
  return html`
    <${Shell} sub=${info ? `Join ${info.org_name} on lumi as ${ROLE_LABEL[info.role] || info.role}` : "Team invite"}>
      ${err && !info ? html`<div class="error-text">${err}</div>` :
      !info ? html`<${Spinner} />` :
      html`<form onSubmit=${go}>
        <div class="field"><label>Email</label><input value=${info.email} disabled /></div>
        <${Field} label="Your name" value=${name} onInput=${setName} autoFocus=${true} />
        <${Field} label="Choose a password (8+ characters)" type="password" value=${pw} onInput=${setPw} />
        <${TermsTick} checked=${tick} onChange=${setTick}>
          I accept the lumi <a onClick=${e => { e.preventDefault(); setShowTerms(true); }} style=${{ cursor: "pointer" }}>Platform Terms of Use</a>.
        <//>
        <div class="caption" style=${{ marginBottom: "var(--s3)" }}>
          lumi generates <a onClick=${e => { e.preventDefault(); setAiDoc(true); }} style=${{ cursor: "pointer" }}>AI Insights</a> — plain-language summaries of your benchmark figures (a description of your data, not advice). They're on by default; you can turn them off any time in Settings.
        </div>
        ${aiDoc && html`<${LegalDocModal} docKey="ai_insights" onClose=${() => setAiDoc(false)} />`}
        ${err && html`<div class="error-text" style=${{ marginBottom: "var(--s3)" }}>${err}</div>`}
        <button class="btn primary" style=${{ width: "100%", justifyContent: "center" }} disabled=${!tick}>Join ${info.org_name}</button>
        <div class="caption" style=${{ marginTop: "var(--s2)" }}>Your organisation's Data Contribution Terms were
          already accepted by your Admin — you don't accept those again.</div>
      </form>`}
      ${showTerms && html`<${TermsModal} kind="platform" onClose=${() => setShowTerms(false)} />`}
    <//>`;
}

window.ROLE_LABEL = { admin: "Admin", contributor: "Contributor", viewer: "Viewer" };
