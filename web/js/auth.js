/* Auth screens: sign in, register, reset, accept invite. */
/* global html, useState, useEffect, api, Spinner */

window.AuthScreen = function ({ onAuthed, route }) {
  if (route.startsWith("/reset/")) return html`<${ResetForm} token=${route.split("/")[2]} onAuthed=${onAuthed} />`;
  if (route.startsWith("/invite/")) return html`<${InviteForm} token=${route.split("/")[2]} onAuthed=${onAuthed} />`;
  return html`<${LoginForm} onAuthed=${onAuthed} />`;
};

function Shell({ children, sub }) {
  return html`
    <div class="auth-wrap">
      <div class="card auth-card">
        <div class="logo" style=${{ padding: 0, marginBottom: "4px" }}>lumi<span>.benchmark</span></div>
        <div class="caption" style=${{ marginBottom: "20px" }}>${sub || "People analytics benchmarking for UK HR teams"}</div>
        ${children}
      </div>
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
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [orgName, setOrgName] = useState("");
  const [name, setName] = useState("");
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const go = async (e) => {
    e.preventDefault();
    setErr(null); setMsg(null); setBusy(true);
    try {
      if (mode === "login") { await api("/api/auth/login", { method: "POST", body: { email, password: pw } }); onAuthed(); }
      else if (mode === "register") { await api("/api/auth/register", { method: "POST", body: { org_name: orgName, email, password: pw, display_name: name } }); onAuthed(); }
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
        ${err && html`<div class="error-text" style=${{ marginBottom: "10px" }}>${err}</div>`}
        ${msg && html`<div class="ok-text" style=${{ marginBottom: "10px" }}>${msg}</div>`}
        <button class="btn primary" style=${{ width: "100%", justifyContent: "center" }} disabled=${busy}>
          ${busy ? html`<${Spinner} />` : mode === "login" ? "Sign in" : mode === "register" ? "Create organisation account" : "Send reset link"}
        </button>
      </form>
      <div class="row spread" style=${{ marginTop: "16px" }}>
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
        <button class="btn primary" style=${{ marginTop: "12px" }} onClick=${() => { window.location.hash = "/"; window.location.reload(); }}>Sign in</button>` :
      html`<form onSubmit=${go}>
        <${Field} label="New password (8+ characters)" type="password" value=${pw} onInput=${setPw} autoFocus=${true} />
        ${err && html`<div class="error-text" style=${{ marginBottom: "10px" }}>${err}</div>`}
        <button class="btn primary" style=${{ width: "100%", justifyContent: "center" }}>Set password</button>
      </form>`}
    <//>`;
}

function InviteForm({ token, onAuthed }) {
  const [info, setInfo] = useState(null);
  const [err, setErr] = useState(null);
  const [pw, setPw] = useState("");
  const [name, setName] = useState("");
  useEffect(() => { api("/api/invite/" + token).then(setInfo).catch(e => setErr(e.message)); }, [token]);
  const go = async (e) => {
    e.preventDefault(); setErr(null);
    try { await api("/api/auth/accept-invite", { method: "POST", body: { token, password: pw, display_name: name } }); onAuthed(); }
    catch (ex) { setErr(ex.message); }
  };
  return html`
    <${Shell} sub=${info ? `Join ${info.org_name} on lumi as ${info.role}` : "Team invite"}>
      ${err && !info ? html`<div class="error-text">${err}</div>` :
      !info ? html`<${Spinner} />` :
      html`<form onSubmit=${go}>
        <div class="field"><label>Email</label><input value=${info.email} disabled /></div>
        <${Field} label="Your name" value=${name} onInput=${setName} autoFocus=${true} />
        <${Field} label="Choose a password (8+ characters)" type="password" value=${pw} onInput=${setPw} />
        ${err && html`<div class="error-text" style=${{ marginBottom: "10px" }}>${err}</div>`}
        <button class="btn primary" style=${{ width: "100%", justifyContent: "center" }}>Join ${info.org_name}</button>
      </form>`}
    <//>`;
}
