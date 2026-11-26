// Where the backend lives.
//
// In dev this points at uvicorn. The container build sets VITE_API_URL to an
// empty string so every request is same-origin and nginx proxies it. That way
// the same image works behind any hostname without a rebuild.
const RAW = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";

export const API = RAW.replace(/\/+$/, "");

// The Spring Boot GitHub login service. Same-origin "/auth" in the container
// build; in a split deployment (frontend on Vercel) it's the API host's /auth.
const RAW_AUTH = import.meta.env.VITE_AUTH_URL ?? "http://127.0.0.1:8081/auth";
export const AUTH_URL = RAW_AUTH.replace(/\/+$/, "");
export const GITHUB_LOGIN_URL = `${AUTH_URL}/oauth2/authorization/github`;

// Reads a JWT's claims without verifying it. Only for display (username,
// roles); the servers verify the signature on every request.
export function tokenClaims(token) {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(part)
        .split("")
        .map((c) => "%" + c.charCodeAt(0).toString(16).padStart(2, "0"))
        .join("")
    );
    return JSON.parse(json);
  } catch {
    return {};
  }
}

export function tokenRoles(token) {
  const roles = tokenClaims(token).roles;
  return Array.isArray(roles) ? roles : ["USER"];
}

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

  githubLoginAvailable: () =>
    fetch(`${AUTH_URL}/actuator/health`)
      .then((r) => r.ok)
      .catch(() => false),

  interview: (message, history, token) =>
    request("/ai/interview", { method: "POST", body: { message, history }, token }),
  generateProblem: (topic, difficulty, token) =>
    request("/ai/generate-problem", { method: "POST", body: { topic, difficulty }, token }),
  aiCache: (token) => request("/ai/cache", { token }),

  createTournament: (username, token) =>
    request("/tournament/create", { method: "POST", body: { username }, token }),
};
