export default function MatchmakingOverlay({ status, elo, queueSize, onCancel }) {
  return (
    <div className="fullscreen-overlay">
      <div className="overlay-card">
        <div className="searching-rings">
          <div className="ring ring-1" />
          <div className="ring ring-2" />
          <div className="ring ring-3" />
          <div className="search-icon-inner">⚔</div>
        </div>
        <h2 className="overlay-title">Finding Opponent</h2>
        <div className="overlay-status">{status}</div>
        {elo != null && <div className="overlay-sub">Your rating: {elo}</div>}
        {queueSize != null && (
          <div className="overlay-sub">
            {queueSize === 0
              ? "You're the first in queue"
              : `${queueSize} player${queueSize === 1 ? "" : "s"} also searching`}
          </div>
        )}
        <button className="btn-ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
