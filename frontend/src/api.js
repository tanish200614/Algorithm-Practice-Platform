// Where the backend lives.
//
// In dev this points at uvicorn. The container build sets VITE_API_URL to an
// empty string so every request is same-origin and nginx proxies it. That way
// the same image works behind any hostname without a rebuild.
const RAW = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";

export const API = RAW.replace(/\/+$/, "");

export function wsUrl(path, token) {
  // API is either absolute (dev, uvicorn) or a same-origin path like "/api"
  // (container build). Turn both into an absolute ws:// URL and keep the
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
  bytecode: (code, token) =>
    request("/bytecode", { method: "POST", body: { code }, token }),

  createRoom: (problemId, token) =>
    request("/room/create", { method: "POST", body: { problem_id: problemId }, token }),
  room: (code) => request(`/room/${code}`),

  createTournament: (username, token) =>
    request("/tournament/create", { method: "POST", body: { username }, token }),
};
