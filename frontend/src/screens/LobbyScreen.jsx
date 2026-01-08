import { useEffect, useState } from "react";

import { api } from "../api.js";

function Leaderboard({ entries }) {
  return (
    <div className="leaderboard-panel">
      <div className="leaderboard-title">Top Players</div>
      <div className="leaderboard-list">
        {entries.length === 0 ? (
          <div className="leaderboard-empty">No battles yet</div>
        ) : (
          entries.slice(0, 8).map((e, i) => (
            <div className="lb-row" key={e.name}>
              <span className="lb-rank">{i + 1}</span>
              <span className="lb-name">{e.name}</span>
              <span className={`lb-tier tier-${e.tier.toLowerCase()}`}>{e.tier}</span>
              <span className="lb-skill">{e.skill}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function LobbyScreen({
  username,
  onLogout,
  onCreateRoom,
  onJoinRoom,
  onSolo,
  onFindMatch,
  onHostTournament,
  onJoinTournament,
}) {
  const [problems, setProblems] = useState([]);
  const [leaderboard, setLeaderboard] = useState([]);
  const [problemId, setProblemId] = useState("two_sum");
  const [joinCode, setJoinCode] = useState("");
  const [tournamentCode, setTournamentCode] = useState("");
  const [error, setError] = useState(null);
  const [sandbox, setSandbox] = useState(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.problems(), api.leaderboard(), api.sandbox().catch(() => null)])
      .then(([probs, board, sb]) => {
        if (cancelled) return;
        setProblems(probs);
        setLeaderboard(board);
        setSandbox(sb);
        if (probs.length && !probs.some((p) => p.id === problemId)) {
          setProblemId(probs[0].id);
        }
      })
      .catch(() => {
        /* the lobby is still usable without the extras */
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const guard = (fn) => async (...args) => {
    setError(null);
    try {
      await fn(...args);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="screen active">
      <div className="lobby-bg">
        <div className="grid-lines" />
        <div className="scanline" />
      </div>
      <div className="lobby-content">
        <div className="lobby-topbar">
          <span className="lobby-user-info">{username}</span>
          <button className="btn-ghost small" onClick={onLogout}>
            Logout
          </button>
        </div>

        <div className="logo-block">
          <span className="logo-tag">// v2.0</span>
          <h1 className="logo">
            ALGO
            <br />
            <span className="logo-accent">BATTLE</span>
          </h1>
          <p className="logo-sub">
            Head-to-head algorithm warfare. Submit your solution. Watch runtimes diverge.
          </p>
        </div>

        {error && <div className="auth-error auth-error--fail">{error}</div>}

        <div className="lobby-actions">
          <div className="action-card">
            <div className="card-number">01</div>
            <h2>Create Room</h2>
            <p>Start a battle, get a 6-digit code, share it with your opponent.</p>
            <div className="problem-select-wrap">
              <label>Choose problem</label>
              <select value={problemId} onChange={(e) => setProblemId(e.target.value)}>
                {problems.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title} [{p.tier}]
                  </option>
                ))}
              </select>
            </div>
            <button className="btn-primary" onClick={guard(() => onCreateRoom(problemId))}>
              Create Room →
            </button>
          </div>

          <div className="divider-or">
            <span>OR</span>
          </div>

          <div className="action-card">
            <div className="card-number">02</div>
            <h2>Join Room</h2>
            <p>Enter the code your opponent shared to drop into the battle.</p>
            <input
              type="text"
              placeholder="Room code (e.g. AB12CD)"
              maxLength={6}
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
            />
            <button
              className="btn-primary"
              disabled={joinCode.length < 6}
              onClick={guard(() => onJoinRoom(joinCode))}
            >
              Join Battle →
            </button>
          </div>
        </div>

        <div className="lobby-bottom-row">
          <div className="matchmaking-card">
            <div className="card-number">03</div>
            <h2>Find Match</h2>
            <p>Get paired with a player at similar rating automatically — no room code needed.</p>
            <button className="btn-primary" onClick={onFindMatch}>
              Find Opponent →
            </button>
          </div>

          <div className="tournament-card">
            <div className="card-number">04</div>
            <h2>Tournament</h2>
            <p>4-8 players, single-elimination bracket. Host one or join with a code.</p>
            <div className="tournament-lobby-actions">
              <button className="btn-primary" onClick={guard(onHostTournament)}>
                Host Tournament →
              </button>
              <div className="tournament-join-row">
                <input
                  type="text"
                  placeholder="Tournament code"
                  maxLength={6}
                  value={tournamentCode}
                  onChange={(e) => setTournamentCode(e.target.value.toUpperCase())}
                />
                <button
                  className="btn-ghost"
                  disabled={!tournamentCode}
                  onClick={guard(() => onJoinTournament(tournamentCode))}
                >
                  Join
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="solo-bar">
          <span>Just want to practice solo?</span>
          <button className="btn-ghost" onClick={onSolo}>
            Open Solo Editor →
          </button>
        </div>

        <Leaderboard entries={leaderboard} />

        {sandbox && !sandbox.isolated && (
          <div className="sandbox-warning">
            Submissions are running <strong>unisolated</strong> ({sandbox.mode})
            {sandbox.detail ? ` — ${sandbox.detail}` : ""}. Build the sandbox images to
            isolate them.
          </div>
        )}
      </div>
    </div>
  );
}
