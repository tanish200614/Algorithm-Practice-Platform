import { useState } from "react";

export default function WaitingScreen({ roomCode, problem, players, you }) {
  const [copied, setCopied] = useState(false);

  const opponent = players.find((p) => p !== you);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(roomCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard is blocked in some contexts; the code is on screen anyway */
    }
  };

  return (
    <div className="screen active">
      <div className="waiting-inner">
        <div className="waiting-header">
          <span className="tag">Waiting for opponent</span>
          <div className="room-code-display">
            <span className="room-code-label">Room Code</span>
            <span className="room-code-value">{roomCode}</span>
            <button className="btn-copy" onClick={copy} title="Copy">
              {copied ? "✓" : "⎘"}
            </button>
          </div>
        </div>

        <div className="problem-preview">
          <strong>{problem?.title}</strong>
          {problem?.description}
        </div>

        <div className="player-slots">
          <div className="player-slot">
            <div className="slot-dot active" />
            <span>{you}</span>
            <span className="slot-status">Connected</span>
          </div>
          <div className="vs-badge">VS</div>
          <div className="player-slot">
            <div className={`slot-dot ${opponent ? "active" : "waiting-pulse"}`} />
            <span>{opponent ?? "Waiting..."}</span>
            <span className="slot-status">{opponent ? "Connected" : "Not connected"}</span>
          </div>
        </div>

        <div className="waiting-hint">
          Share your room code — battle starts automatically when both players submit.
        </div>
      </div>
    </div>
  );
}
