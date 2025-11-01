const API = "http://127.0.0.1:8000";
const WS_BASE = "ws://127.0.0.1:8000";

// ── Auth state ─────────────────────────────────────────────────────────────
const auth = {
  token: localStorage.getItem("ab_token"),
  username: localStorage.getItem("ab_username"),
  save(token, username) {
    this.token = token; this.username = username;
    localStorage.setItem("ab_token", token);
    localStorage.setItem("ab_username", username);
  },
  clear() {
    this.token = null; this.username = null;
    localStorage.removeItem("ab_token");
    localStorage.removeItem("ab_username");
  },
  headers() {
    return this.token
      ? { "Content-Type": "application/json", "Authorization": `Bearer ${this.token}` }
      : { "Content-Type": "application/json" };
  },
};

// ── Auth screen ────────────────────────────────────────────────────────────
let _authMode = "login";

document.getElementById("tab-login").addEventListener("click", () => setAuthMode("login"));
document.getElementById("tab-register").addEventListener("click", () => setAuthMode("register"));

function setAuthMode(mode) {
  _authMode = mode;
  document.getElementById("tab-login").classList.toggle("active", mode === "login");
  document.getElementById("tab-register").classList.toggle("active", mode === "register");
  document.getElementById("auth-password2").classList.toggle("hidden", mode === "login");
  const btn = document.getElementById("auth-submit");
  btn.textContent = mode === "login" ? "Login →" : "Create Account →";
  btn.disabled = false;
  document.getElementById("auth-error").classList.add("hidden");
}

document.getElementById("auth-submit").addEventListener("click", async () => {
  const btn = document.getElementById("auth-submit");
  if (btn.disabled) return;

  const username = document.getElementById("auth-username").value.trim();
  const password = document.getElementById("auth-password").value;
  const password2 = document.getElementById("auth-password2").value;

  if (!username || !password) return showAuthError("Fill in all fields");
  if (_authMode === "register" && password !== password2)
    return showAuthError("Passwords don't match");

  btn.disabled = true;
  btn.textContent = "...";
  document.getElementById("auth-error").classList.add("hidden");

  const endpoint = _authMode === "login" ? "/login" : "/register";
  let data;
  try {
    const res = await fetch(`${API}${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    data = await res.json();
  } catch {
    showAuthError("Cannot reach server — is the backend running?");
    btn.disabled = false;
    btn.textContent = _authMode === "login" ? "Login →" : "Create Account →";
    return;
  }

  if (!data || !data.token) {
    showAuthError(data?.detail || "Something went wrong");
    btn.disabled = false;
    btn.textContent = _authMode === "login" ? "Login →" : "Create Account →";
    return;
  }

  if (_authMode === "register") {
    // Show success then switch to login tab — user logs in manually
    setAuthMode("login");
    document.getElementById("auth-username").value = username;
    document.getElementById("auth-password").value = "";
    showAuthSuccess("Account created — please log in");
    return;
  }

  // Login success → go to lobby
  auth.save(data.token, data.username);
  try {
    enterLobby();
  } catch (err) {
    console.error("enterLobby failed:", err);
    showAuthError("Login succeeded but failed to load — try refreshing");
    btn.disabled = false;
    btn.textContent = "Login →";
  }
});

// Allow Enter key to submit
["auth-username", "auth-password", "auth-password2"].forEach(id => {
  document.getElementById(id).addEventListener("keydown", e => {
    if (e.key === "Enter") document.getElementById("auth-submit").click();
  });
});

function showAuthError(msg) {
  const el = document.getElementById("auth-error");
  el.textContent = msg;
  el.className = "auth-error auth-error--fail";
  el.classList.remove("hidden");
}

function showAuthSuccess(msg) {
  const el = document.getElementById("auth-error");
  el.textContent = msg;
  el.className = "auth-error auth-error--ok";
  el.classList.remove("hidden");
}

function enterLobby() {
  showScreen("lobby");
  const info = document.getElementById("lobby-user-info");
  if (info) info.textContent = auth.username;
  // Pre-fill name fields with authenticated username
  const createName = document.getElementById("create-name");
  const joinName = document.getElementById("join-name");
  if (createName) createName.value = auth.username || "";
  if (joinName) joinName.value = auth.username || "";
  bootLobby();
}

document.getElementById("btn-logout").addEventListener("click", () => {
  auth.clear();
  showScreen("auth");
});

// On page load: skip auth if token exists
if (auth.token) {
  // Verify token is still valid
  fetch(`${API}/me`, { headers: auth.headers() })
    .then(r => r.ok ? r.json() : Promise.reject())
    .then(() => enterLobby())
    .catch(() => { auth.clear(); showScreen("auth"); });
}

// ── Boot: fetch problems with difficulty + leaderboard ─────────────────────
async function bootLobby() {
  try {
    const [probRes, lbRes] = await Promise.all([
      fetch(`${API}/problems`, { headers: auth.headers() }),
      fetch(`${API}/leaderboard`, { headers: auth.headers() }),
    ]);
    const problems = await probRes.json();
    const leaderboard = await lbRes.json();

    // Enrich problem-select with difficulty badges
    const sel = document.getElementById("problem-select");
    problems.forEach(p => {
      const opt = sel.querySelector(`option[value="${p.id}"]`);
      if (opt) opt.textContent = `${p.title}  [${p.tier}]`;
    });

    renderLeaderboard(leaderboard);
  } catch (_) {}
}

function renderLeaderboard(entries) {
  const el = document.getElementById("leaderboard-list");
  if (!entries || !entries.length) return;
  el.innerHTML = entries.slice(0, 8).map((e, i) => `
    <div class="lb-row">
      <span class="lb-rank">${i + 1}</span>
      <span class="lb-name">${e.name}</span>
      <span class="lb-tier tier-${e.tier.toLowerCase()}">${e.tier}</span>
      <span class="lb-skill">${e.skill}</span>
    </div>
  `).join("");
}

bootLobby();

// ── State ──────────────────────────────────────────────────────────────────
let state = {
  screen: "lobby",
  roomCode: null,
  playerName: null,
  playerId: null,
  problem: null,
  language: "python",
  ws: null,
  raceChart: null,
  myColor: "#00ff88",
  themColor: "#ff3c6e",
  players: [],
  resultsReceived: {},
};

const STARTERS = {
  two_sum: {
    python: `def two_sum(nums: list, target: int) -> list:\n    pass`,
    cpp: `#include <iostream>\n#include <vector>\n#include <unordered_map>\nusing namespace std;\n\nvector<int> two_sum(vector<int>& nums, int target) {\n    // your code here\n    return {};\n}`,
    java: `static int[] twoSum(int[] nums, int target) {\n    // your code here\n    return new int[]{};\n}`,
  },
  max_subarray: {
    python: `def max_subarray(nums: list) -> int:\n    pass`,
    cpp: `#include <iostream>\n#include <vector>\n#include <algorithm>\nusing namespace std;\n\nint max_subarray(vector<int>& nums) {\n    // your code here\n    return 0;\n}`,
    java: `static int maxSubarray(int[] nums) {\n    // your code here\n    return 0;\n}`,
  },
  bubble_sort: {
    python: `def sort_array(nums: list) -> list:\n    pass`,
    cpp: `#include <iostream>\n#include <vector>\n#include <algorithm>\nusing namespace std;\n\nvector<int> sort_array(vector<int> nums) {\n    // your code here\n    return nums;\n}`,
    java: `static int[] sortArray(int[] nums) {\n    // your code here\n    return nums;\n}`,
  },
};

// ── Screen management ──────────────────────────────────────────────────────
function showScreen(name) {
  document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
  document.getElementById(`screen-${name}`).classList.add("active");
  state.screen = name;
}

// ── Lobby ──────────────────────────────────────────────────────────────────
document.getElementById("btn-create").addEventListener("click", async () => {
  const name = document.getElementById("create-name").value.trim();
  const problem_id = document.getElementById("problem-select").value;
  if (!name) return alert("Enter your name first");

  try {
    const res = await fetch(`${API}/room/create`, {
      method: "POST",
      headers: auth.headers(),
      body: JSON.stringify({ problem_id }),
    });
    const data = await res.json();
    state.roomCode = data.room_code;
    state.playerName = name;
    state.problem = data.problem;
    enterWaiting();
  } catch (e) {
    alert("Cannot reach server. Is the backend running?\n\nStart it with:\ncd backend && source venv/bin/activate && uvicorn main:app --reload");
  }
});

document.getElementById("btn-join").addEventListener("click", () => {
  const code = document.getElementById("join-code").value.trim().toUpperCase();
  const name = document.getElementById("join-name").value.trim();
  if (!code || !name) return alert("Enter room code and your name");
  state.roomCode = code;
  state.playerName = name;
  fetchAndEnterBattle();
});

document.getElementById("btn-solo").addEventListener("click", () => showScreen("solo"));
document.getElementById("btn-back-lobby").addEventListener("click", () => showScreen("lobby"));

async function fetchAndEnterBattle() {
  const res = await fetch(`${API}/room/${state.roomCode}`);
  const data = await res.json();
  if (data.error) return alert(data.error);
  state.problem = data.problem;
  enterWaiting();
}

// ── Waiting Room ───────────────────────────────────────────────────────────
function enterWaiting() {
  showScreen("waiting");
  document.getElementById("display-room-code").textContent = state.roomCode;

  const pp = document.getElementById("waiting-problem-preview");
  pp.innerHTML = `<strong>${state.problem.title}</strong>${state.problem.description}`;

  document.getElementById("slot-p1-name").textContent = state.playerName;
  document.getElementById("slot-p2-name").textContent = "Waiting...";
  document.getElementById("slot-p2-status").textContent = "Not connected";
  document.querySelector("#slot-p2 .slot-dot").className = "slot-dot waiting-pulse";

  document.getElementById("btn-copy-code").addEventListener("click", () => {
    navigator.clipboard.writeText(state.roomCode);
    document.getElementById("btn-copy-code").textContent = "✓";
    setTimeout(() => { document.getElementById("btn-copy-code").textContent = "⎘"; }, 1500);
  });

  connectWebSocket();
}

// ── WebSocket ──────────────────────────────────────────────────────────────
function connectWebSocket() {
  const url = `${WS_BASE}/ws/${state.roomCode}?token=${encodeURIComponent(auth.token || "")}`;
  state.ws = new WebSocket(url);

  state.ws.onopen = () => console.log("WS connected");

  state.ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleMessage(msg);
  };

  state.ws.onerror = (e) => console.error("WS error", e);
  state.ws.onclose = () => console.log("WS closed");
}

function handleMessage(msg) {
  console.log("MSG", msg);
  switch (msg.type) {
    case "joined":
      state.playerId = msg.player_id;
      state.problem = msg.problem;
      updatePlayerSlots(msg.players);
      break;

    case "player_joined":
      updatePlayerSlots(msg.players);
      if (msg.count === 2 && state.screen === "waiting") {
        // Small delay so user sees both names before switching
        setTimeout(() => enterBattle(), 800);
      }
      break;

    case "player_ready":
      updateBattleStatus(`${msg.player} submitted (${msg.ready_count}/${msg.total})`);
      break;

    case "race_start":
      document.getElementById("battle-status-badge").textContent = "RACING";
      document.getElementById("battle-status-badge").className = "battle-status-badge racing";
      document.getElementById("arena-submit-btn").disabled = true;
      document.getElementById("chart-placeholder").classList.add("hidden");
      break;

    case "results":
      handleRaceResults(msg.player, msg.data, msg.language);
      break;

    case "race_done":
      showWinner(msg.winner, msg);
      break;

    case "player_left":
      updatePlayerSlots(msg.players);
      break;

    case "error":
      alert("Server: " + msg.msg);
      break;
  }
}

function updatePlayerSlots(players) {
  state.players = players;
  if (state.screen === "waiting") {
    document.getElementById("slot-p1-name").textContent = players[0] || state.playerName;
    if (players[1]) {
      document.getElementById("slot-p2-name").textContent = players[1];
      document.getElementById("slot-p2-status").textContent = "Connected";
      document.querySelector("#slot-p2 .slot-dot").className = "slot-dot active";
    }
  }
}

// ── Battle Arena ───────────────────────────────────────────────────────────
function enterBattle() {
  showScreen("battle");
  buildArena();
}

function buildArena() {
  // Players bar
  const bar = document.getElementById("arena-players-bar");
  const me = state.playerName;
  const them = state.players.find(p => p !== me) || "Opponent";

  async function playerChip(name, classes) {
    let skill = "";
    try {
      const r = await fetch(`${API}/player/${encodeURIComponent(name)}`);
      const d = await r.json();
      skill = `<span class="chip-tier tier-${d.tier.toLowerCase()}">${d.tier} · ${d.skill}</span>`;
    } catch (_) {}
    const chip = bar.querySelector(`.arena-player-chip.${classes.split(" ")[0]}`);
    if (chip) chip.innerHTML = `${name}${name === me ? " (you)" : ""} ${skill}`;
  }

  bar.innerHTML = `
    <div class="arena-player-chip you">${me} (you)</div>
    <div class="arena-player-chip them">${them}</div>
  `;
  playerChip(me, "you");
  playerChip(them, "them");

  // Problem
  const pp = document.getElementById("battle-problem-panel");
  pp.innerHTML = `<strong>${state.problem.title} —</strong> ${state.problem.description}`;

  // Language buttons
  document.querySelectorAll(".lang-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".lang-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.language = btn.dataset.lang;
      setStarterCode();
      const asmBtn = document.getElementById("arena-asm-btn");
      asmBtn.classList.toggle("hidden", state.language !== "cpp");
      if (state.language !== "cpp") {
        document.getElementById("arena-asm-panel").classList.add("hidden");
      }
    });
  });

  // Set initial starter
  state.language = "python";
  document.querySelectorAll(".lang-btn").forEach(b => b.classList.remove("active"));
  document.querySelector(".lang-btn[data-lang='python']").classList.add("active");
  setStarterCode();

  // Init chart
  initRaceChart([me, them]);
}

function setStarterCode() {
  const problemId = state.problem?.id;
  const starters = STARTERS[problemId];
  if (starters) {
    document.getElementById("arena-code").value = starters[state.language] || "";
  }
}

function initRaceChart(playerNames) {
  const ctx = document.getElementById("race-chart").getContext("2d");
  if (state.raceChart) state.raceChart.destroy();

  state.raceChart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        {
          label: playerNames[0],
          data: [],
          borderColor: state.myColor,
          backgroundColor: "transparent",
          pointBackgroundColor: state.myColor,
          tension: 0.3,
        },
        {
          label: playerNames[1] || "Opponent",
          data: [],
          borderColor: state.themColor,
          backgroundColor: "transparent",
          pointBackgroundColor: state.themColor,
          tension: 0.3,
        },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          type: "linear",
          title: { display: true, text: "Input Size (n)", color: "#6b6b8a", font: { family: "'Space Mono'" } },
          grid: { color: "rgba(255,255,255,0.05)" },
          ticks: { color: "#6b6b8a" },
        },
        y: {
          title: { display: true, text: "Time (ms)", color: "#6b6b8a", font: { family: "'Space Mono'" } },
          grid: { color: "rgba(255,255,255,0.05)" },
          ticks: { color: "#6b6b8a" },
        },
      },
    },
  });

  // legend
  const legend = document.getElementById("race-legend");
  legend.innerHTML = playerNames.map((name, i) => `
    <div class="legend-item">
      <div class="legend-dot" style="background:${i === 0 ? state.myColor : state.themColor}"></div>
      <span>${name}${name === state.playerName ? " (you)" : ""}</span>
    </div>
  `).join("");
}

// Test run
document.getElementById("arena-test-btn").addEventListener("click", async () => {
  const code = document.getElementById("arena-code").value;
  const out = document.getElementById("arena-test-output");
  out.textContent = "Running...";
  try {
    const res = await fetch(`${API}/run`, {
      method: "POST",
      headers: auth.headers(),
      body: JSON.stringify({ code, language: state.language }),
    });
    const data = await res.json();
    out.textContent = data.stderr
      ? `ERR: ${data.stderr.slice(0, 120)}`
      : `OK — ${data.stdout.slice(0, 80) || "(no output)"} | ${data.time_ms}ms`;
  } catch (e) {
    out.textContent = "Server error: " + e.message;
  }
});

// Submit
document.getElementById("arena-submit-btn").addEventListener("click", () => {
  const code = document.getElementById("arena-code").value;
  if (!code.trim()) return;
  state.ws.send(JSON.stringify({ type: "submit", code, language: state.language }));
  document.getElementById("arena-submit-btn").textContent = "⏳ Waiting for opponent...";
  document.getElementById("arena-submit-btn").disabled = true;
});

function updateBattleStatus(txt) {
  document.getElementById("battle-status-badge").textContent = txt;
}

function handleRaceResults(playerName, data, language = "python") {
  state.resultsReceived[playerName] = data;

  const me = state.playerName;
  const them = state.players.find(p => p !== me) || "Opponent";
  const idx = playerName === me ? 0 : 1;

  const points = data.results
    .filter(r => r.ms !== null)
    .map(r => ({ x: r.n, y: r.ms }));

  state.raceChart.data.datasets[idx].data = points;
  state.raceChart.update();

  const cards = document.getElementById("race-result-cards");
  const valid = data.results.filter(r => r.ms !== null && r.ok);
  const maxN = valid.length ? valid[valid.length - 1].n : 0;
  const lastMs = valid.length ? valid[valid.length - 1].ms.toFixed(1) : "—";
  const langLabels = { python: "Python", cpp: "C++", java: "Java" };
  const langLabel = langLabels[language] || language;
  const cx = data.complexity;
  const complexityHtml = cx ? `
    <div class="complexity-verdict">
      <span class="complexity-best">${cx.best}</span>
    </div>
    <div class="complexity-fits">
      ${cx.fits.map((f, i) => `
        <div class="complexity-fit-row${i === 0 ? " is-best" : ""}">
          <span>${f.label}</span>
          <span class="fit-bar">
            <span class="fit-bar-fill" style="width:${Math.max(4, Math.round(f.score * 100))}%"></span>
          </span>
        </div>
      `).join("")}
    </div>` : "";

  const ap = data.approach;
  const approachHtml = ap ? (() => {
    const similarText = ap.similar_count > 0
      ? `<span class="approach-similar">${ap.similar_count} similar</span>`
      : (ap.total_seen >= 6 ? `<span class="approach-similar">unique</span>` : "");
    return `<div class="approach-row"><span class="approach-badge">${ap.label}</span>${similarText}</div>`;
  })() : "";

  const tr = data.timeout_risk;
  const timeoutHtml = tr
    ? `<div class="timeout-warning">&#9888; Skipped n=${tr.at_n} — predicted ~${tr.predicted_ms.toLocaleString()}ms</div>`
    : "";

  const existing = document.getElementById(`card-${CSS.escape(playerName)}`);
  const html = `
    <div class="result-card" id="card-${CSS.escape(playerName)}">
      <div class="result-card-name">
        ${playerName}${playerName === me ? " (you)" : ""}
        <span style="color:var(--accent3);margin-left:8px;font-size:10px;">${langLabel}</span>
      </div>
      <div class="result-card-stats">
        Solved up to n=${maxN} &nbsp;|&nbsp; Last: ${lastMs}ms
        ${data.error && !tr ? `<br><span style="color:var(--accent2)">Stopped: ${data.error}</span>` : ""}
      </div>
      ${approachHtml}
      ${timeoutHtml}
      ${complexityHtml}
    </div>
  `;
  if (existing) existing.outerHTML = html;
  else cards.insertAdjacentHTML("beforeend", html);
}

function showWinner(winner, msg = {}) {
  document.getElementById("battle-status-badge").textContent = "DONE";
  document.getElementById("battle-status-badge").className = "battle-status-badge done";

  const banner = document.getElementById("winner-banner");
  banner.classList.add("visible");

  const nameEl = document.getElementById("winner-name-display");
  const detailEl = document.getElementById("winner-detail");

  if (winner === "tie") {
    nameEl.textContent = "It's a tie!";
    detailEl.textContent = "Both solutions handled the same input size.";
  } else {
    nameEl.textContent = winner;
    const isMe = winner === state.playerName;
    detailEl.textContent = isMe
      ? "Your solution survived larger inputs. Well played."
      : "Their solution handled larger inputs. Study the difference.";
  }

  // ── ML insights panel ───────────────────────────────────────────────────
  const insights = document.getElementById("race-insights");
  if (insights && msg.similarity !== undefined) {
    const me = state.playerName;
    const simPct = Math.round(msg.similarity * 100);
    const simLabel = simPct >= 70 ? "nearly identical" : simPct >= 40 ? "similar" : simPct >= 15 ? "different" : "completely different";

    const myPct = msg.percentiles?.[me];
    const myDelta = msg.elo_deltas?.[me];
    const mySkill = msg.skills?.[me];
    const myTime = msg.solve_time_ms?.[me];
    const rec = msg.recommendations?.[me];

    const deltaTxt = myDelta != null
      ? `<span class="elo-delta ${myDelta >= 0 ? "pos" : "neg"}">${myDelta >= 0 ? "+" : ""}${myDelta} ELO</span>`
      : "";

    insights.innerHTML = `
      <div class="insights-grid">
        <div class="insight-cell">
          <div class="insight-label">Code Similarity</div>
          <div class="insight-value">${simPct}%</div>
          <div class="insight-sub">${simLabel} approaches</div>
        </div>
        ${myPct != null ? `
        <div class="insight-cell">
          <div class="insight-label">Your Speed</div>
          <div class="insight-value">${myPct}th pct</div>
          <div class="insight-sub">faster than ${myPct}% of solvers</div>
        </div>` : ""}
        <div class="insight-cell">
          <div class="insight-label">Your Rating</div>
          <div class="insight-value">${mySkill ?? "—"} ${deltaTxt}</div>
          <div class="insight-sub">${myTime ? (myTime / 1000).toFixed(0) + "s to submit" : ""}</div>
        </div>
        ${rec ? `
        <div class="insight-cell">
          <div class="insight-label">Try Next</div>
          <div class="insight-value insight-rec">${rec}</div>
          <div class="insight-sub">recommended for your level</div>
        </div>` : ""}
      </div>
    `;
  }

  // Refresh leaderboard in background
  fetch(`${API}/leaderboard`).then(r => r.json()).then(renderLeaderboard).catch(() => {});

  // highlight winner card
  document.querySelectorAll(".result-card").forEach(card => {
    if (card.querySelector(".result-card-name")?.textContent.startsWith(winner)) {
      card.classList.add("winner");
    }
  });
}

document.getElementById("btn-rematch").addEventListener("click", () => {
  document.getElementById("winner-banner").classList.remove("visible");
  if (_tournamentCode && _tournamentWs) {
    // In tournament mode — go back to bracket view between rounds
    resetState();
    showScreen("tournament");
    renderBracket(_latestBracket);
  } else {
    showScreen("lobby");
    resetState();
  }
});

document.getElementById("btn-lobby").addEventListener("click", () => {
  document.getElementById("winner-banner").classList.remove("visible");
  if (_tournamentCode && _tournamentWs) {
    resetState();
    showScreen("tournament");
    renderBracket(_latestBracket);
  } else {
    showScreen("lobby");
    resetState();
  }
});

function resetState() {
  if (state.ws) { state.ws.close(); state.ws = null; }
  state.roomCode = null;
  state.playerName = null;
  state.problem = null;
  state.resultsReceived = {};
  state.language = "python";
  document.getElementById("winner-banner").classList.remove("visible");
  document.getElementById("arena-submit-btn").disabled = false;
  document.getElementById("race-result-cards").innerHTML = "";
  document.getElementById("arena-test-output").textContent = "";
  document.getElementById("arena-code").value = "";
  document.getElementById("chart-placeholder").classList.remove("hidden");
  if (state.raceChart) { state.raceChart.destroy(); state.raceChart = null; }
}

function leaveTournament() {
  if (_tournamentWs) { try { _tournamentWs.close(); } catch (_) {} _tournamentWs = null; }
  _tournamentCode = null;
  _isHost = false;
  _latestBracket = [];
  _tournamentWinner = null;
}

// ── Solo Mode ──────────────────────────────────────────────────────────────
document.getElementById("solo-run-btn").addEventListener("click", async () => {
  const code = document.getElementById("solo-code").value;
  document.getElementById("solo-stdout").textContent = "";
  document.getElementById("solo-stderr").textContent = "";
  document.getElementById("solo-stats").textContent = "";

  try {
    const res = await fetch(`${API}/run`, {
      method: "POST",
      headers: auth.headers(),
      body: JSON.stringify({ code }),
    });
    if (!res.ok) {
      document.getElementById("solo-stderr").textContent = `Error ${res.status}: ${res.statusText}`;
      return;
    }
    const data = await res.json();
    document.getElementById("solo-stdout").textContent = data.stdout || "";
    document.getElementById("solo-stderr").textContent = data.stderr || "";
    document.getElementById("solo-stats").textContent =
      `Time: ${data.time_ms ?? "?"} ms\nMemory: ${data.memory_kb ?? "?"} KB`;
  } catch (err) {
    document.getElementById("solo-stderr").textContent = "Server error: " + err.message;
  }
});

// ── Assembly viewer ────────────────────────────────────────────────────────
document.getElementById("arena-asm-btn").addEventListener("click", async () => {
  const code = document.getElementById("arena-code").value;
  const panel = document.getElementById("arena-asm-panel");
  const asmCode = document.getElementById("arena-asm-code");
  const speedupEl = document.getElementById("arena-asm-speedup");

  panel.classList.remove("hidden");
  asmCode.textContent = "Compiling…";
  speedupEl.textContent = "";

  try {
    const res = await fetch(`${API}/asm`, {
      method: "POST",
      headers: auth.headers(),
      body: JSON.stringify({ code, problem_id: state.problem?.id || "two_sum" }),
    });
    const data = await res.json();
    if (data.error) {
      asmCode.textContent = "Error: " + data.error;
      return;
    }
    // Strip .cfi_ directives — pure exception-handling metadata, not useful here
    const cleaned = data.asm
      .split("\n")
      .filter(l => !l.trim().startsWith(".cfi_"))
      .join("\n")
      .replace(/\n{3,}/g, "\n\n");
    asmCode.textContent = cleaned;

    if (data.speedup) {
      speedupEl.textContent = `${data.speedup}× faster with -O2`;
    } else if (data.o0_ms && data.o2_ms) {
      speedupEl.textContent = `-O0: ${data.o0_ms}ms  -O2: ${data.o2_ms}ms`;
    }
  } catch (e) {
    asmCode.textContent = "Server error: " + e.message;
  }
});

document.getElementById("arena-asm-close").addEventListener("click", () => {
  document.getElementById("arena-asm-panel").classList.add("hidden");
});

// ── Editor key handling (tab, brackets, indent) ───────────────────────────
const PAIRS = { '(': ')', '[': ']', '{': '}' };
const CLOSERS = new Set([')', ']', '}']);

document.querySelectorAll("textarea").forEach(ta => {
  ta.addEventListener("keydown", e => {
    const s = ta.selectionStart, end = ta.selectionEnd;
    const val = ta.value;
    const selected = val.substring(s, end);

    if (e.key === "Tab") {
      e.preventDefault();
      ta.value = val.substring(0, s) + "    " + val.substring(end);
      ta.selectionStart = ta.selectionEnd = s + 4;
      return;
    }

    // Auto-close brackets; wrap selection if text is highlighted
    if (e.key in PAIRS) {
      e.preventDefault();
      const close = PAIRS[e.key];
      if (selected) {
        ta.value = val.substring(0, s) + e.key + selected + close + val.substring(end);
        ta.selectionStart = s + 1;
        ta.selectionEnd = end + 1;
      } else {
        ta.value = val.substring(0, s) + e.key + close + val.substring(end);
        ta.selectionStart = ta.selectionEnd = s + 1;
      }
      return;
    }

    // Skip over existing closing bracket instead of inserting a duplicate
    if (CLOSERS.has(e.key) && s === end && val[s] === e.key) {
      e.preventDefault();
      ta.selectionStart = ta.selectionEnd = s + 1;
      return;
    }

    // Backspace: delete both brackets if cursor is inside an empty pair
    if (e.key === "Backspace" && s === end && s > 0) {
      if (val[s - 1] in PAIRS && val[s] === PAIRS[val[s - 1]]) {
        e.preventDefault();
        ta.value = val.substring(0, s - 1) + val.substring(s + 1);
        ta.selectionStart = ta.selectionEnd = s - 1;
        return;
      }
    }

    // Auto-indent on Enter: match current line indent, add extra after : or {
    if (e.key === "Enter") {
      e.preventDefault();
      const lineStart = val.lastIndexOf('\n', s - 1) + 1;
      const currentLine = val.substring(lineStart, s);
      const indent = currentLine.match(/^(\s*)/)[1];

      if (val[s - 1] === '{' && val[s] === '}') {
        // Cursor between { } — expand into three lines
        const inner = '\n' + indent + '    ';
        ta.value = val.substring(0, s) + inner + '\n' + indent + val.substring(end);
        ta.selectionStart = ta.selectionEnd = s + inner.length;
      } else {
        const extra = /[:{]\s*$/.test(currentLine) ? '    ' : '';
        const ins = '\n' + indent + extra;
        ta.value = val.substring(0, s) + ins + val.substring(end);
        ta.selectionStart = ta.selectionEnd = s + ins.length;
      }
      return;
    }
  });
});

// ── Matchmaking ────────────────────────────────────────────────────────────────
let _queueWs = null;

document.getElementById("btn-find-match").addEventListener("click", startMatchmaking);
document.getElementById("btn-cancel-matchmaking").addEventListener("click", cancelMatchmaking);

function startMatchmaking() {
  if (!auth.token) return alert("Please log in to use matchmaking");
  const overlay = document.getElementById("matchmaking-overlay");
  overlay.classList.remove("hidden");
  document.getElementById("match-status").textContent = "Connecting...";
  document.getElementById("match-elo").textContent = "";
  document.getElementById("match-queue").textContent = "";

  const url = `${WS_BASE}/ws/queue?token=${encodeURIComponent(auth.token || "")}`;
  _queueWs = new WebSocket(url);

  _queueWs.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "searching") {
      document.getElementById("match-status").textContent = "Searching for opponent...";
      document.getElementById("match-elo").textContent = `Your rating: ${msg.elo}`;
      const qs = msg.queue_size;
      document.getElementById("match-queue").textContent =
        qs ? `${qs} other player${qs !== 1 ? "s" : ""} also searching` : "You're the first in queue";
    } else if (msg.type === "still_searching") {
      const qs = msg.queue_size;
      document.getElementById("match-queue").textContent =
        `${qs} player${qs !== 1 ? "s" : ""} in queue`;
    } else if (msg.type === "matched") {
      document.getElementById("match-status").textContent = `Matched vs ${msg.opponent}!`;
      overlay.classList.add("hidden");
      _queueWs = null;
      state.roomCode = msg.room_code;
      state.playerName = auth.username || "Player";
      fetchAndEnterBattle();
    }
  };

  _queueWs.onerror = () => {
    document.getElementById("match-status").textContent = "Connection error — is the server running?";
  };

  _queueWs.onclose = () => {
    overlay.classList.add("hidden");
    _queueWs = null;
  };
}

function cancelMatchmaking() {
  if (_queueWs) {
    try { _queueWs.send(JSON.stringify({ type: "cancel" })); } catch (_) {}
    _queueWs.close();
    _queueWs = null;
  }
  document.getElementById("matchmaking-overlay").classList.add("hidden");
}

// ── Tournament ─────────────────────────────────────────────────────────────────
let _tournamentWs = null;
let _tournamentCode = null;
let _isHost = false;
let _latestBracket = [];
let _tournamentWinner = null;

document.getElementById("btn-create-tournament").addEventListener("click", async () => {
  if (!auth.token) return alert("Please log in first");
  try {
    const res = await fetch(`${API}/tournament/create`, {
      method: "POST",
      headers: auth.headers(),
      body: JSON.stringify({ username: auth.username }),
    });
    const data = await res.json();
    joinTournamentWs(data.tournament_code, true);
  } catch (e) {
    alert("Cannot reach server");
  }
});

document.getElementById("btn-join-tournament").addEventListener("click", () => {
  const code = document.getElementById("tournament-join-code").value.trim().toUpperCase();
  if (!code) return alert("Enter a tournament code");
  if (!auth.token) return alert("Please log in first");
  joinTournamentWs(code, false);
});

function joinTournamentWs(code, isHost) {
  _tournamentCode = code;
  _isHost = isHost;
  _latestBracket = [];
  _tournamentWinner = null;

  showScreen("tournament");
  document.getElementById("tournament-code-display").textContent = code;
  document.getElementById("tournament-status-badge").textContent = "Lobby";
  document.getElementById("bracket-view").innerHTML =
    '<div class="bracket-empty">Bracket appears when tournament starts</div>';
  document.getElementById("tournament-host-controls").classList.toggle("hidden", !isHost);
  if (isHost) updateTournamentStartBtn(1);

  const url = `${WS_BASE}/ws/tournament/${code}?token=${encodeURIComponent(auth.token || "")}`;
  _tournamentWs = new WebSocket(url);

  _tournamentWs.onmessage = (event) => handleTournamentMessage(JSON.parse(event.data));
  _tournamentWs.onerror = () => alert("Tournament connection error");
  _tournamentWs.onclose = () => { _tournamentWs = null; };
}

function handleTournamentMessage(msg) {
  switch (msg.type) {
    case "lobby_state":
      renderTournamentPlayers(msg.players, msg.host);
      updateTournamentStartBtn(msg.players.length);
      break;

    case "player_joined":
    case "player_left":
      renderTournamentPlayers(msg.players, null);
      updateTournamentStartBtn(msg.count);
      break;

    case "tournament_started":
      document.getElementById("tournament-status-badge").textContent = "Active";
      document.getElementById("tournament-host-controls").classList.add("hidden");
      break;

    case "round_start":
      _latestBracket = msg.bracket;
      document.getElementById("tournament-status-badge").textContent =
        `Round ${msg.round} — ${msg.problem_title}`;
      if (state.screen === "tournament") renderBracket(msg.bracket);
      break;

    case "match_ready":
      state.roomCode = msg.room_code;
      state.playerName = auth.username || "Player";
      fetchAndEnterBattle();
      break;

    case "round_done":
      _latestBracket = msg.bracket;
      document.getElementById("tournament-status-badge").textContent =
        `Round ${msg.round} complete`;
      if (state.screen === "tournament") renderBracket(msg.bracket);
      break;

    case "tournament_done":
      _latestBracket = msg.bracket;
      _tournamentWinner = msg.winner;
      document.getElementById("tournament-status-badge").textContent =
        `\u{1F3C6} ${msg.winner} wins!`;
      if (state.screen === "tournament") {
        renderBracket(msg.bracket);
        document.getElementById("tournament-status-badge").scrollIntoView({ behavior: "smooth" });
      }
      break;

    case "error":
      alert("Tournament error: " + msg.msg);
      if (state.screen === "tournament") { leaveTournament(); showScreen("lobby"); }
      break;
  }
}

function renderTournamentPlayers(players, host) {
  const el = document.getElementById("tournament-player-list");
  const count = document.getElementById("tournament-player-count");
  count.textContent = `(${players.length})`;
  el.innerHTML = players.map(p => `
    <div class="t-player-row ${p.alive === false ? "t-eliminated" : ""}">
      <span class="t-player-name">
        ${p.name}${p.name === host ? " <span class='t-host-badge'>host</span>" : ""}
        ${p.name === auth.username ? " <span class='t-you-badge'>you</span>" : ""}
      </span>
      <span class="t-player-elo">${p.elo}</span>
      ${p.alive === false ? '<span class="t-elim-label">out</span>' : ""}
    </div>
  `).join("");
}

function updateTournamentStartBtn(count) {
  const btn = document.getElementById("tournament-start-btn");
  const note = document.getElementById("t-min-note");
  if (!btn) return;
  const ready = count >= 4;
  btn.disabled = !ready;
  note.textContent = ready
    ? `${count} player${count !== 1 ? "s" : ""} ready — start when you want`
    : `Need ${4 - count} more player${(4 - count) !== 1 ? "s" : ""} (${count}/4 minimum)`;
}

function renderBracket(rounds) {
  const el = document.getElementById("bracket-view");
  if (!rounds || !rounds.length) {
    el.innerHTML = '<div class="bracket-empty">Bracket appears when tournament starts</div>';
    return;
  }
  el.innerHTML = rounds.map(r => `
    <div class="bracket-round">
      <div class="bracket-round-header">
        <span class="bracket-round-num">Round ${r.round}</span>
        <span class="bracket-round-problem">${r.problem_title}</span>
      </div>
      <div class="bracket-matches">
        ${r.matches.map(m => {
          const p1Win = m.winner && m.winner === m.p1;
          const p2Win = m.winner && m.winner === m.p2;
          const live = !m.winner && m.p1 && m.p2;
          return `
          <div class="bracket-match${live ? " bracket-live" : m.winner ? " bracket-settled" : ""}">
            <div class="bracket-player${p1Win ? " bracket-winner" : p2Win ? " bracket-loser" : ""}">
              ${m.p1 || "<em>BYE</em>"}
            </div>
            <div class="bracket-vs">${live ? "vs" : "→"}</div>
            <div class="bracket-player${p2Win ? " bracket-winner" : p1Win ? " bracket-loser" : ""}">
              ${m.p2 || "<em>BYE</em>"}
            </div>
            ${m.winner ? `<div class="bracket-winner-chip">\u{1F3C6} ${m.winner}</div>` : ""}
            ${live ? '<div class="bracket-live-chip">live</div>' : ""}
          </div>`;
        }).join("")}
      </div>
    </div>
  `).join("");
}

document.getElementById("tournament-start-btn").addEventListener("click", () => {
  if (_tournamentWs) _tournamentWs.send(JSON.stringify({ type: "start" }));
});

document.getElementById("btn-leave-tournament").addEventListener("click", () => {
  leaveTournament();
  showScreen("lobby");
  bootLobby();
});

document.getElementById("btn-copy-tournament-code").addEventListener("click", () => {
  navigator.clipboard.writeText(_tournamentCode || "");
  const btn = document.getElementById("btn-copy-tournament-code");
  btn.textContent = "✓";
  setTimeout(() => { btn.textContent = "⎘"; }, 1500);
});

// ── AI Problem Generator ───────────────────────────────────────────────────────
let _generatedProblem = null;

document.getElementById("btn-open-generate").addEventListener("click", () => {
  _generatedProblem = null;
  document.getElementById("generate-description").value = "";
  document.getElementById("generate-status").classList.add("hidden");
  document.getElementById("generate-preview").classList.add("hidden");
  document.getElementById("btn-generate-submit").disabled = false;
  document.getElementById("btn-generate-submit").textContent = "Generate Problem →";
  document.getElementById("generate-modal").classList.remove("hidden");
});

document.getElementById("btn-close-generate").addEventListener("click", () => {
  document.getElementById("generate-modal").classList.add("hidden");
});

document.getElementById("btn-generate-submit").addEventListener("click", runGenerate);
document.getElementById("btn-regenerate").addEventListener("click", runGenerate);

document.getElementById("generate-description").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); runGenerate(); }
});

async function runGenerate() {
  const desc = document.getElementById("generate-description").value.trim();
  if (!desc) return;

  const btn = document.getElementById("btn-generate-submit");
  const status = document.getElementById("generate-status");
  const preview = document.getElementById("generate-preview");

  btn.disabled = true;
  btn.textContent = "Generating...";
  preview.classList.add("hidden");
  status.textContent = "Writing problem, test cases, and validator...";
  status.className = "generate-status";

  try {
    const res = await fetch(`${API}/ai/generate-problem`, {
      method: "POST",
      headers: auth.headers(),
      body: JSON.stringify({ description: desc }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Generation failed");

    _generatedProblem = data.problem;
    document.getElementById("generate-preview-title").textContent = data.problem.title;
    document.getElementById("generate-preview-desc").textContent = data.problem.description;
    status.classList.add("hidden");
    preview.classList.remove("hidden");
  } catch (e) {
    status.textContent = "Error: " + e.message;
    status.className = "generate-status generate-error";
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Problem →";
  }
}

document.getElementById("btn-use-problem").addEventListener("click", () => {
  if (!_generatedProblem) return;

  const sel = document.getElementById("problem-select");
  const existing = sel.querySelector(`option[value="${_generatedProblem.id}"]`);
  if (!existing) {
    const opt = document.createElement("option");
    opt.value = _generatedProblem.id;
    opt.textContent = `${_generatedProblem.title}  [AI]`;
    sel.appendChild(opt);
  }
  sel.value = _generatedProblem.id;

  // Register starter code so the editor knows what to show
  STARTERS[_generatedProblem.id] = {
    python: _generatedProblem.starter,
    cpp: `// ${_generatedProblem.title}\n// Implement in C++`,
    java: `// ${_generatedProblem.title}\n// Implement in Java`,
  };

  document.getElementById("generate-modal").classList.add("hidden");
});

// ── AI Interview Simulator ─────────────────────────────────────────────────────
let _interviewHistory = [];
let _interviewDone = false;

document.getElementById("btn-interview-mode").addEventListener("click", openInterview);
document.getElementById("btn-close-interview").addEventListener("click", () => {
  document.getElementById("interview-overlay").classList.add("hidden");
});

document.getElementById("interview-send").addEventListener("click", sendInterviewMessage);
document.getElementById("interview-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendInterviewMessage(); }
});

function openInterview() {
  _interviewHistory = [];
  _interviewDone = false;

  const code = document.getElementById("arena-code").value || "";
  const myResults = state.resultsReceived?.[state.playerName];
  const complexity = myResults?.complexity?.best || "Unknown";
  const approach = myResults?.approach?.label || "Unknown";

  document.getElementById("interview-problem-title").textContent =
    state.problem?.title || "Algorithm Problem";
  document.getElementById("interview-code").textContent = code;
  document.getElementById("interview-chat").innerHTML = "";
  document.getElementById("interview-input").value = "";
  document.getElementById("interview-meta").textContent =
    `Complexity: ${complexity} · Approach: ${approach}`;

  document.getElementById("interview-overlay").classList.remove("hidden");

  // AI opens with first question automatically
  _sendToInterviewer("I'm ready for the interview.", true);
}

function appendInterviewBubble(text, role) {
  const chat = document.getElementById("interview-chat");
  const div = document.createElement("div");
  div.className = `interview-bubble ${role === "interviewer" ? "bubble-ai" : "bubble-user"}`;
  div.innerHTML = `
    <div class="bubble-label">${role === "interviewer" ? "Interviewer" : "You"}</div>
    <div class="bubble-text">${text.replace(/\n/g, "<br>")}</div>
  `;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

async function sendInterviewMessage() {
  if (_interviewDone) return;
  const input = document.getElementById("interview-input");
  const msg = input.value.trim();
  if (!msg) return;

  input.value = "";
  appendInterviewBubble(msg, "user");
  _sendToInterviewer(msg, false);
}

async function _sendToInterviewer(userMsg, isOpening) {
  const sendBtn = document.getElementById("interview-send");
  sendBtn.disabled = true;

  const code = document.getElementById("arena-code").value || "";
  const myResults = state.resultsReceived?.[state.playerName];
  const complexity = myResults?.complexity?.best || "Unknown";
  const approach = myResults?.approach?.label || "Unknown";

  if (!isOpening) {
    _interviewHistory.push({ role: "user", content: userMsg });
  }

  try {
    const res = await fetch(`${API}/ai/interview`, {
      method: "POST",
      headers: auth.headers(),
      body: JSON.stringify({
        problem_title: state.problem?.title || "Unknown",
        problem_description: state.problem?.description || "",
        code,
        complexity,
        approach,
        history: isOpening ? [] : _interviewHistory.slice(0, -1),
        message: userMsg,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Interview error");

    appendInterviewBubble(data.response, "interviewer");
    _interviewHistory.push({ role: "assistant", content: data.response });

    if (data.done) {
      _interviewDone = true;
      document.getElementById("interview-meta").textContent = "Interview complete.";
      sendBtn.textContent = "Done";
    }
  } catch (e) {
    appendInterviewBubble(`Error: ${e.message}`, "interviewer");
  } finally {
    if (!_interviewDone) sendBtn.disabled = false;
  }
}