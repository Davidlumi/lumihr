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
  // rendered through the house Modal so keyboard users get the same focus
  // trap/restore + Escape as every other overlay — terms are the one document
  // a member MUST be able to read before accepting
  return html`
    <${Modal} onClose=${onClose} width="640px" label="Terms of Use">
      ${!doc ? html`<${Spinner} />` : html`
        <${TermsText} text=${doc.text} />
        <div class="row spread" style=${{ marginTop: "var(--s4)" }}>
          <span class="chip">Current version · v${doc.version}</span>
          <button class="btn" onClick=${onClose}>Close</button>
        </div>`}
    <//>`;
};

function TermsTick({ checked, onChange, children }) {
  return html`
    <label class="terms-tick">
      <input type="checkbox" checked=${checked} onChange=${e => onChange(e.target.checked)} />
      <span>${children}</span>
    </label>`;
}

/* Opening an invite link while already signed in (2026-08-04): the app used to
   swallow the link into the current session's Overview — the mechanism behind
   "I try to sign in as thornbridge but it keeps jumping to tester" once a test
   invite URL lived in the browser's autocomplete. This interstitial names the
   session, explains what an invite does, and offers both exits. */
window.InviteWhileAuthed = function ({ me, token }) {
  const signOutToInvite = async () => {
    try { await api("/api/auth/logout", { method: "POST", body: {} }); } catch (e) { /* signed out anyway */ }
    window.location.hash = "/invite/" + token;
    window.location.reload();
  };
  return html`
    <div class="card" style=${{ maxWidth: "560px", margin: "var(--s6) auto", padding: "var(--s5)" }}>
      <h2 class="section-title" style=${{ marginTop: 0 }}>This is an invite link</h2>
      <p>You're signed in as <b>${me.user.email}</b>${me.org && me.org.org_id ? "" : ""}.
        Accepting an invite creates and signs in a <b>separate account</b>, so it isn't
        opened automatically while you're signed in.</p>
      <p class="caption">Delivering this link to someone else? Just send it — nothing has
        been used. Testing it yourself? A private window leaves your session untouched.</p>
      <div class="row" style=${{ gap: "var(--s2)", marginTop: "var(--s3)" }}>
        <button class="btn primary" onClick=${() => { window.location.hash = "/overview"; }}>Stay signed in</button>
        <button class="btn" onClick=${signOutToInvite}>Sign out & open the invite</button>
      </div>
    </div>`;
};

window.AuthScreen = function ({ onAuthed, route }) {
  if (route.startsWith("/reset/")) return html`<${ResetForm} token=${route.split("/")[2]} onAuthed=${onAuthed} />`;
  if (route.startsWith("/invite/")) return html`<${InviteForm} token=${route.split("/")[2]} onAuthed=${onAuthed} />`;
  // /app#/register lands register-intent traffic ("Get your benchmark") on the
  // register form directly instead of behind the small "New organisation" link
  return html`<${LoginForm} onAuthed=${onAuthed} initialMode=${route.startsWith("/register") ? "register" : "login"} />`;
};

function Shell({ children, sub }) {
  const [doc, setDoc] = useState(null);
  return html`
    <div class="auth-wrap">
      <div class="card auth-card">
        <div class="logo" style=${{ padding: 0, marginBottom: "var(--s1)" }}>lumi<span>.benchmark</span></div>
        <div class="caption" style=${{ marginBottom: "var(--s5)" }}>${sub || (window.__resumeRoute
          ? "Sign in to continue where you left off." : "Reward benchmarking for UK HR teams")}</div>
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

function Field({ label, type, value, onInput, placeholder, autoFocus, autoComplete }) {
  // programmatic label association (screen readers announced these inputs
  // nameless) + autocomplete hints + show/hide on passwords
  const id = "auth-" + (label || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
  const [show, setShow] = useState(false);
  const isPw = type === "password";
  return html`
    <div class="field">
      <div class="row spread">
        <label htmlFor=${id}>${label}</label>
        ${isPw && html`<button type="button" class="auth-foot-link" aria-pressed=${show ? "true" : "false"}
          onClick=${() => setShow(s => !s)}>${show ? "Hide" : "Show"}</button>`}
      </div>
      <input id=${id} type=${isPw && show ? "text" : (type || "text")} value=${value} placeholder=${placeholder || ""}
        autoFocus=${autoFocus} autocomplete=${autoComplete || null}
        onInput=${e => onInput(e.target.value)} onKeyDown=${e => { if (e.key === "Enter") { const f = e.target.closest("form"); f && f.requestSubmit(); } }} />
    </div>`;
}

function LoginForm({ onAuthed, initialMode }) {
  const [mode, setMode] = useState(initialMode || "login"); // login | register | forgot
  const [legalDoc, setLegalDoc] = useState(null);
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [orgName, setOrgName] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [tick, setTick] = useState(false);
  const [regOpen, setRegOpen] = useState(null);   // null = unknown; false shows the set-up-for-you panel
  useEffect(() => {
    if (mode === "register" && regOpen === null)
      api("/api/auth/registration").then(d => setRegOpen(!!d.open)).catch(() => setRegOpen(true));
  }, [mode]);
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
    <${Shell} sub=${mode === "register" ? "Join the co-operative — benchmark against UK peers" : undefined}>
      <form onSubmit=${go}>
        ${mode === "register" && regOpen === false && html`
        <div class="card" style=${{ padding: "var(--s4)", marginBottom: "var(--s3)", textAlign: "left" }}>
          <b>Membership is set up for you.</b>
          <div class="caption" style=${{ marginTop: "var(--s1)" }}>lumi memberships are provisioned by our team so your
            organisation starts with the right profile and peers. Email
            ${" "}<a href="mailto:hello@lumihr.co.uk">hello@lumihr.co.uk</a> and we'll set you up — usually same day.</div>
        </div>`}
        ${mode === "register" && regOpen !== false && html`<${Field} label="Organisation name" value=${orgName} onInput=${setOrgName} placeholder="Acme Retail Ltd" autoFocus=${true} autoComplete="organization" />`}
        ${mode === "register" && regOpen !== false && html`<${Field} label="Your name" value=${name} onInput=${setName} autoComplete="name" />`}
        ${!(mode === "register" && regOpen === false) && html`<${Field} label="Work email" type="email" value=${email} onInput=${setEmail} placeholder="you@yourorg.co.uk" autoFocus=${mode === "login"} autoComplete="email" />`}
        ${!(mode === "register" && regOpen === false) && mode !== "forgot" && html`<${Field} label=${mode === "register" ? "Password (8+ characters)" : "Password"} type="password" value=${pw} onInput=${setPw}
          autoComplete=${mode === "register" ? "new-password" : "current-password"} />`}
        ${mode === "register" && regOpen !== false && html`
          <${TermsTick} checked=${tick} onChange=${setTick}>
            I accept the lumi <a href="#" onClick=${e => { e.preventDefault(); setShowTerms(true); }}>Platform Terms of Use</a>.
          <//>`}
        ${mode === "register" && regOpen !== false && html`
          <div class="caption" style=${{ marginBottom: "var(--s3)" }}>
            lumi generates <a href="#" onClick=${e => { e.preventDefault(); setLegalDoc("ai_insights"); }}>AI Insights</a> — plain-language summaries of your figures, not advice. On by default; turn off any time in Settings.
          </div>`}
        ${mode === "register" && regOpen !== false && html`<div class="caption" style=${{ marginBottom: "var(--s3)" }}>
          By continuing you agree to our <a href="#" onClick=${e => { e.preventDefault(); setLegalDoc("platform"); }}>Terms of Use</a>
          ${" "}and <a href="#" onClick=${e => { e.preventDefault(); setLegalDoc("privacy"); }}>Privacy Notice</a>.</div>`}
        ${err && html`<div class="error-text" role="alert" style=${{ marginBottom: "var(--s3)" }}>${err}</div>`}
        ${msg && html`<div class="ok-text" role="status" style=${{ marginBottom: "var(--s3)" }}>${msg}</div>`}
        ${!(mode === "register" && regOpen === false) && html`
        <button class="btn primary block" disabled=${busy || (mode === "register" && !tick)}
          title=${mode === "register" && !tick ? "Accept the Platform Terms of Use above to continue" : null}>
          ${busy ? html`<${Spinner} />` : mode === "login" ? "Sign in" : mode === "register" ? "Create organisation account" : "Send reset link"}
        </button>`}
        ${mode === "register" && regOpen !== false && html`<div class="caption" style=${{ marginTop: "var(--s2)" }}>
          You'll be your organisation's Admin. Before your team first submits data, you'll also review
          the Data Contribution Terms — your 30 days to contribute start then, not now.</div>`}
        ${showTerms && html`<${TermsModal} kind="platform" onClose=${() => setShowTerms(false)} />`}
        ${legalDoc && html`<${LegalDocModal} docKey=${legalDoc} onClose=${() => setLegalDoc(null)} />`}
      </form>
      <div class="row spread" style=${{ marginTop: "var(--s4)" }}>
        ${mode !== "login" ? html`<a href="#" onClick=${e => { e.preventDefault(); setMode("login"); }}>Sign in</a>` : html`<a href="#" onClick=${e => { e.preventDefault(); setMode("register"); }}>New organisation</a>`}
        ${!(mode === "register" && regOpen === false) && mode !== "forgot" && html`<a href="#" onClick=${e => { e.preventDefault(); setMode("forgot"); }}>Forgotten password?</a>`}
      </div>
    <//>`;
}

function ResetForm({ token, onAuthed }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const go = async (e) => {
    e.preventDefault(); setErr(null); setBusy(true);
    try { await api("/api/auth/reset", { method: "POST", body: { token, password: pw } }); setDone(true); }
    catch (ex) { setErr(ex.message); }
    setBusy(false);
  };
  return html`
    <${Shell} sub="Choose a new password">
      ${done ? html`<div class="ok-text">Password updated.</div>
        <button class="btn primary" style=${{ marginTop: "var(--s3)" }} onClick=${() => { window.location.hash = "/"; window.location.reload(); }}>Sign in</button>` :
      html`<form onSubmit=${go}>
        <${Field} label="New password (8+ characters)" type="password" value=${pw} onInput=${setPw} autoFocus=${true} autoComplete="new-password" />
        ${err && html`<div class="error-text" role="alert" style=${{ marginBottom: "var(--s3)" }}>${err}
          ${/expired|used/i.test(err) ? html` <a href="#/" onClick=${() => { window.location.hash = "/"; window.location.reload(); }}>Request a new link →</a>` : ""}</div>`}
        <button class="btn primary block" disabled=${busy}>${busy ? html`<${Spinner} />` : "Set password"}</button>
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
  const toSignIn = (e) => { e.preventDefault(); window.location.hash = "/"; };
  return html`
    <${Shell} sub=${info ? `Join ${info.org_name} on lumi as ${ROLE_LABEL[info.role] || info.role}` : "Team invite"}>
      ${err && !info ? html`
        <div class="error-text" role="alert">${err}</div>
        <p class="caption" style=${{ margin: "var(--s3) 0" }}>This link has expired or already been used. If you already have an account, sign in.</p>
        <button class="btn primary block" onClick=${toSignIn}>Go to sign in</button>` :
      !info ? html`<${Spinner} />` :
      html`<form onSubmit=${go}>
        <div class="field"><label>Email</label><input value=${info.email} disabled /></div>
        <${Field} label="Your name" value=${name} onInput=${setName} autoFocus=${true} autoComplete="name" />
        <${Field} label="Choose a password (8+ characters)" type="password" value=${pw} onInput=${setPw} autoComplete="new-password" />
        <${TermsTick} checked=${tick} onChange=${setTick}>
          I accept the lumi <a href="#" onClick=${e => { e.preventDefault(); setShowTerms(true); }}>Platform Terms of Use</a>.
        <//>
        <div class="caption" style=${{ marginBottom: "var(--s3)" }}>
          lumi generates <a href="#" onClick=${e => { e.preventDefault(); setAiDoc(true); }}>AI Insights</a> — plain-language summaries of your benchmark figures (a description of your data, not advice). They're on by default; you can turn them off any time in Settings.
        </div>
        ${aiDoc && html`<${LegalDocModal} docKey="ai_insights" onClose=${() => setAiDoc(false)} />`}
        ${err && html`<div class="error-text" role="alert" style=${{ marginBottom: "var(--s3)" }}>${err}</div>`}
        <button class="btn primary block" disabled=${!tick}>Join ${info.org_name}</button>
        <div class="caption" style=${{ marginTop: "var(--s2)" }}>Your organisation's Data Contribution Terms were
          already accepted by your Admin — you don't accept those again.</div>
        <div class="caption" style=${{ marginTop: "var(--s3)" }}>Not ${info.email}?
          <a href="#" onClick=${toSignIn}> Sign in to your own account instead</a>.</div>
      </form>`}
      ${showTerms && html`<${TermsModal} kind="platform" onClose=${() => setShowTerms(false)} />`}
    <//>`;
}

window.ROLE_LABEL = { admin: "Admin", contributor: "Contributor", viewer: "Viewer" };
