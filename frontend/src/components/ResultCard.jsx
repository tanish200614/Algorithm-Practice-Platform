import { LANGUAGE_LABELS } from "../starters.js";

export default function ResultCard({ name, isYou, isWinner, data }) {
  const valid = (data.results ?? []).filter((r) => r.ms !== null && r.ok);
  const last = valid[valid.length - 1];
  const complexity = data.complexity;
  const approach = data.approach;
  const risk = data.timeout_risk;

  return (
    <div className={`result-card${isWinner ? " winner" : ""}`}>
      <div className="result-card-name">
        {name}
        {isYou ? " (you)" : ""}
        <span className="result-card-lang">
          {LANGUAGE_LABELS[data.language] ?? data.language}
        </span>
      </div>

      <div className="result-card-stats">
        Solved up to n={last?.n ?? 0} &nbsp;|&nbsp; Last:{" "}
        {last ? `${last.ms.toFixed(1)}ms` : "—"}
        {data.error && !risk && (
          <>
            <br />
            <span className="result-card-stopped">Stopped: {data.error}</span>
          </>
        )}
      </div>

      {approach && (
        <div className="approach-row">
          <span className="approach-badge">{approach.label}</span>
          {approach.similar_count > 0 ? (
            <span className="approach-similar">{approach.similar_count} similar</span>
          ) : (
            approach.total_seen >= 6 && <span className="approach-similar">unique</span>
          )}
        </div>
      )}

      {risk && (
        <div className="timeout-warning">
          ⚠ Skipped n={risk.at_n} — predicted ~{risk.predicted_ms.toLocaleString()}ms
        </div>
      )}

      {complexity && (
        <>
          <div className="complexity-verdict">
            <span className="complexity-best">{complexity.best}</span>
          </div>
          <div className="complexity-fits">
            {complexity.fits.map((fit, i) => (
              <div className={`complexity-fit-row${i === 0 ? " is-best" : ""}`} key={fit.label}>
                <span>{fit.label}</span>
                <span className="fit-bar">
                  <span
                    className="fit-bar-fill"
                    style={{ width: `${Math.max(4, Math.round(fit.score * 100))}%` }}
                  />
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
