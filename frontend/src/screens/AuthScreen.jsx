import { useEffect, useState } from "react";

import { api, GITHUB_LOGIN_URL } from "../api.js";
import { loginRedirectError } from "../hooks/useAuth.js";

export default function AuthScreen({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [notice, setNotice] = useState(() =>
    loginRedirectError ? { text: loginRedirectError, kind: "fail" } : null
  ); // {text, kind}
  const [busy, setBusy] = useState(false);
  const [github, setGithub] = useState(false);

  // Only offer GitHub login when the auth service is actually up.
  useEffect(() => {
    let cancelled = false;
    api.githubLoginAvailable().then((ok) => !cancelled && setGithub(ok));
    return () => {
      cancelled = true;
    };
  }, []);

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

        {github && (
          <>
            <div className="auth-divider">
              <span>or</span>
            </div>
            <a className="btn-github" href={GITHUB_LOGIN_URL}>
              <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true">
                <path
                  fill="currentColor"
                  d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"
                />
              </svg>
              Continue with GitHub
            </a>
          </>
        )}
      </div>
    </div>
  );
}
