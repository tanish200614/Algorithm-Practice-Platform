import { useCallback, useEffect, useState } from "react";

import { api, tokenClaims } from "../api.js";

const TOKEN_KEY = "ab_token";
const USER_KEY = "ab_username";

// The GitHub login service redirects back with #token=... (or #auth_error=...).
// Take it out of the URL immediately so it isn't left in history or copied
// along with a shared link, and store it like any other login.
function takeRedirect() {
  if (typeof window === "undefined" || !window.location.hash) return null;
  const params = new URLSearchParams(window.location.hash.slice(1));
  const token = params.get("token");
  const error = params.get("auth_error");
  if (!token && !error) return null;
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
  if (token) {
    const sub = tokenClaims(token).sub;
    if (sub) {
      try {
        localStorage.setItem(TOKEN_KEY, token);
        localStorage.setItem(USER_KEY, sub);
      } catch {
        return { token, username: sub };
      }
    }
  }
  return { error };
}

const REDIRECT = takeRedirect();
export const loginRedirectError = REDIRECT?.error ?? null;

function readStored() {
  // Storage blocked: fall back to the token we were just handed.
  if (REDIRECT?.token) return { token: REDIRECT.token, username: REDIRECT.username };
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    const username = localStorage.getItem(USER_KEY);
    return token && username ? { token, username } : null;
  } catch {
    // Private windows and blocked site data throw on access.
    return null;
  }
}

export function useAuth() {
  const [session, setSession] = useState(readStored);
  // Until the saved token is checked we don't know if it's still valid, so
  // render nothing instead of flashing the lobby and bouncing to login.
  const [checking, setChecking] = useState(() => Boolean(readStored()));

  const save = useCallback((token, username) => {
    try {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, username);
    } catch {
      /* a session-only login still beats failing outright */
    }
    setSession({ token, username });
  }, []);

  const clear = useCallback(() => {
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    } catch {
      /* nothing to clean up */
    }
    setSession(null);
  }, []);

  useEffect(() => {
    const stored = readStored();
    if (!stored) return undefined;

    let cancelled = false;
    api
      .me(stored.token)
      .then(() => {
        if (!cancelled) setChecking(false);
      })
      .catch((err) => {
        if (cancelled) return;
        // Don't log out on a network blip, only when the server rejects the token.
        if (err.status === 401) clear();
        setChecking(false);
      });

    return () => {
      cancelled = true;
    };
  }, [clear]);

  return { session, checking, save, clear };
}
