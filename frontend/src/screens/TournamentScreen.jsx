import { useState } from "react";

const MIN_PLAYERS = 4;

function Bracket({ rounds }) {
  if (!rounds?.length) {
    return <div className="bracket-empty">Bracket appears when tournament starts</div>;
  }

  return rounds.map((round) => (
    <div className="bracket-round" key={round.round}>
      <div className="bracket-round-header">
        <span className="bracket-round-num">Round {round.round}</span>
        <span className="bracket-round-problem">{round.problem_title}</span>
      </div>
      <div className="bracket-matches">
        {round.matches.map((m, i) => {
          const p1Win = m.winner && m.winner === m.p1;
          const p2Win = m.winner && m.winner === m.p2;
          const live = !m.winner && m.p1 && m.p2;
          return (
            <div
              className={`bracket-match${live ? " bracket-live" : m.winner ? " bracket-settled" : ""}`}
              key={`${round.round}-${i}`}
            >
              <div
                className={`bracket-player${p1Win ? " bracket-winner" : p2Win ? " bracket-loser" : ""}`}
              >
                {m.p1 ?? <em>BYE</em>}
              </div>
              <div className="bracket-vs">{live ? "vs" : "→"}</div>
              <div
                className={`bracket-player${p2Win ? " bracket-winner" : p1Win ? " bracket-loser" : ""}`}
              >
                {m.p2 ?? <em>BYE</em>}
              </div>
              {m.winner && <div className="bracket-winner-chip">🏆 {m.winner}</div>}
              {live && <div className="bracket-live-chip">live</div>}
            </div>
          );
        })}
      </div>
    </div>
  ));
}

export default function TournamentScreen({ code, you, state, onStart, onLeave }) {
  const [copied, setCopied] = useState(false);
  const { players, bracket, status, host, winner, roundLabel } = state;

  const isHost = host === you;
  const ready = players.length >= MIN_PLAYERS;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* the code is visible on screen regardless */
    }
  };

  let badge = "Lobby";
  if (winner) badge = `🏆 ${winner} wins!`;
  else if (roundLabel) badge = roundLabel;
  else if (status === "active") badge = "Active";

  return (
    <div className="screen active">
      <div className="tournament-layout">
        <div className="tournament-topbar">
          <button className="btn-ghost small" onClick={onLeave}>
            ← Leave
          </button>
          <div className="tournament-code-block">
            <span className="room-code-label">Tournament</span>
            <span className="room-code-value">{code}</span>
            <button className="btn-copy" onClick={copy} title="Copy">
              {copied ? "✓" : "⎘"}
            </button>
          </div>
          <div className="tournament-status-badge">{badge}</div>
        </div>

        <div className="tournament-main">
          <div className="tournament-players-panel">
            <div className="t-panel-header">
              <h3>
                Players <span>({players.length})</span>
              </h3>
            </div>
            <div className="tournament-player-list">
              {players.map((p) => (
                <div
                  className={`t-player-row ${p.alive === false ? "t-eliminated" : ""}`}
                  key={p.name}
                >
                  <span className="t-player-name">
                    {p.name}
                    {p.name === host && <span className="t-host-badge">host</span>}
                    {p.name === you && <span className="t-you-badge">you</span>}
                  </span>
                  <span className="t-player-elo">{p.elo}</span>
                  {p.alive === false && <span className="t-elim-label">out</span>}
                </div>
              ))}
            </div>

            {isHost && status === "lobby" && (
              <div className="tournament-host-controls">
                <button className="btn-primary" disabled={!ready} onClick={onStart}>
                  Start Tournament →
                </button>
                <div className="t-min-note">
                  {ready
                    ? `${players.length} players ready — start when you want`
                    : `Need ${MIN_PLAYERS - players.length} more player${
                        MIN_PLAYERS - players.length === 1 ? "" : "s"
                      } (${players.length}/${MIN_PLAYERS} minimum)`}
                </div>
              </div>
            )}
          </div>

          <div className="tournament-bracket-panel">
            <h3>Bracket</h3>
            <div className="bracket-view">
              <Bracket rounds={bracket} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
