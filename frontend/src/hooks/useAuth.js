import { useCallback, useEffect, useState } from "react";

import { api } from "../api.js";

const TOKEN_KEY = "ab_token";
const USER_KEY = "ab_username";

function readStored() {
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
  // Until the stored token has been checked against the server we don't know
  // whether it is still good, so the app renders nothing rather than flashing
  // the lobby and bouncing back to the login screen.
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
        // A network blip shouldn't discard a valid login — only an outright
        // rejection from the server should.
        if (err.status === 401) clear();
        setChecking(false);
      });

    return () => {
      cancelled = true;
    };
  }, [clear]);

  return { session, checking, save, clear };
}
