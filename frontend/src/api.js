// Where the backend lives.
//
// Dev points at uvicorn directly. The container build sets VITE_API_URL to an
// empty string, which makes every path same-origin so nginx can proxy it —
// that way the image works behind any hostname or load balancer without being
// rebuilt for each environment.
const RAW = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";

export const API = RAW.replace(/\/+$/, "");

export function wsUrl(path, token) {
  // API may be absolute (dev, pointing at uvicorn) or a same-origin path like
  // "/api" (the container build). Resolve both to an absolute ws:// URL, and
  // keep the base's own path — overwriting pathname outright would drop the
  // "/api" prefix.
  const absolute = /^https?:/.test(API) ? API : `${window.location.origin}${API}`;
  const url = new URL(absolute);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = `${url.pathname.replace(/\/+$/, "")}${path}`;
  if (token) url.searchParams.set("token", token);
  return url.toString();
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body, token } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;

  let res;
  try {
    res = await fetch(`${API}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the server — is the backend running?", 0);
  }

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    throw new ApiError(data?.detail || `Request failed (${res.status})`, res.status);
  }
  return data;
}

export const api = {
  register: (username, password) =>
    request("/register", { method: "POST", body: { username, password } }),
  login: (username, password) =>
    request("/login", { method: "POST", body: { username, password } }),
  me: (token) => request("/me", { token }),

  problems: () => request("/problems"),
  languages: () => request("/languages"),
  leaderboard: () => request("/leaderboard"),
  player: (name) => request(`/player/${encodeURIComponent(name)}`),
  sandbox: () => request("/sandbox"),

  run: (code, language, token) =>
    request("/run", { method: "POST", body: { code, language }, token }),
  asm: (code, problemId, token) =>
    request("/asm", { method: "POST", body: { code, problem_id: problemId }, token }),

  createRoom: (problemId, token) =>
    request("/room/create", { method: "POST", body: { problem_id: problemId }, token }),
  room: (code) => request(`/room/${code}`),

  createTournament: (username, token) =>
    request("/tournament/create", { method: "POST", body: { username }, token }),
};
