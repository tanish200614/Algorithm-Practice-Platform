import { useState } from "react";

import { api } from "../api.js";

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [notice, setNotice] = useState(null); // {text, kind}
  const [busy, setBusy] = useState(false);

  const switchMode = (next) => {
    setMode(next);
    setNotice(null);
    setConfirm("");
  };

  async function submit() {
    if (busy) return;
    if (!username || !password) {
      setNotice({ text: "Fill in all fields", kind: "fail" });
      return;
    }
    if (mode === "register" && password !== confirm) {
      setNotice({ text: "Passwords don't match", kind: "fail" });
      return;
    }

    setBusy(true);
    setNotice(null);
    try {
      if (mode === "register") {
        await api.register(username, password);
        // Registration returns a token, but making people log in once checks
        // they remember the password they just picked.
        setMode("login");
        setPassword("");
        setConfirm("");
        setNotice({ text: "Account created — please log in", kind: "ok" });
      } else {
        const data = await api.login(username, password);
        onAuthenticated(data.token, data.username);
      }
    } catch (err) {
      setNotice({ text: err.message, kind: "fail" });
    } finally {
      setBusy(false);
    }
  }

  const onKeyDown = (e) => {
    if (e.key === "Enter") submit();
  };

  const label = mode === "login" ? "Login →" : "Create Account →";

  return (
    <div className="screen active">
      <div className="auth-bg">
        <div className="grid-lines" />
        <div className="scanline" />
      </div>
      <div className="auth-card">
        <div className="auth-logo">
          ALGO<span className="logo-accent">BATTLE</span>
        </div>
        <div className="auth-tabs">
          <button
            className={`auth-tab${mode === "login" ? " active" : ""}`}
            onClick={() => switchMode("login")}
          >
            Login
          </button>
          <button
            className={`auth-tab${mode === "register" ? " active" : ""}`}
            onClick={() => switchMode("register")}
          >
            Register
          </button>
        </div>

        {notice && (
          <div className={`auth-error auth-error--${notice.kind}`}>{notice.text}</div>
        )}

        <input
          type="text"
          placeholder="Username"
          autoComplete="username"
          maxLength={16}
          value={username}
          onChange={(e) => setUsername(e.target.value.trim())}
          onKeyDown={onKeyDown}
        />
        <input
          type="password"
          placeholder="Password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={onKeyDown}
        />
        {mode === "register" && (
          <input
            type="password"
            placeholder="Confirm password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            onKeyDown={onKeyDown}
          />
        )}
        <button className="btn-primary" onClick={submit} disabled={busy}>
          {busy ? "…" : label}
        </button>
      </div>
    </div>
  );
}
