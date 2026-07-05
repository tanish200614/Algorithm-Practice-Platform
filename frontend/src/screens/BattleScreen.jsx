import { useEffect, useMemo, useState } from "react";

import { api } from "../api.js";
import { starterFor } from "../starters.js";
import AsmPanel from "../components/AsmPanel.jsx";
import BytecodePanel from "../components/BytecodePanel.jsx";
import CodeEditor from "../components/CodeEditor.jsx";
import RaceChart from "../components/RaceChart.jsx";
import ResultCard from "../components/ResultCard.jsx";

const LANGUAGES = [
  { id: "python", label: "Python" },
  { id: "cpp", label: "C++" },
  { id: "java", label: "Java" },
];

function PlayerChip({ name, isYou, className }) {
  const [tier, setTier] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .player(name)
      .then((d) => !cancelled && setTier(d))
      .catch(() => {
        /* the chip still reads fine without a rating */
      });
    return () => {
      cancelled = true;
    };
  }, [name]);

  return (
    <div className={`arena-player-chip ${className}`}>
      {name}
      {isYou ? " (you)" : ""}
      {tier && (
        <span className={`chip-tier tier-${tier.tier.toLowerCase()}`}>
          {tier.tier} · {tier.skill}
        </span>
      )}
    </div>
  );
}

function Insights({ you, info }) {
  const pct = Math.round((info.similarity ?? 0) * 100);
  const simLabel =
    pct >= 70 ? "nearly identical" : pct >= 40 ? "similar" : pct >= 15 ? "different" : "completely different";

  const myPct = info.percentiles?.[you];
  const delta = info.elo_deltas?.[you];
  const skill = info.skills?.[you];
  const solveMs = info.solve_time_ms?.[you];
  const rec = info.recommendations?.[you];

  return (
    <div className="race-insights">
      <div className="insights-grid">
        <div className="insight-cell">
          <div className="insight-label">Code Similarity</div>
          <div className="insight-value">{pct}%</div>
          <div className="insight-sub">{simLabel} approaches</div>
        </div>

        {myPct != null && (
          <div className="insight-cell">
            <div className="insight-label">Your Speed</div>
            <div className="insight-value">{myPct}th pct</div>
            <div className="insight-sub">faster than {myPct}% of solvers</div>
          </div>
        )}

        <div className="insight-cell">
          <div className="insight-label">Your Rating</div>
          <div className="insight-value">
            {skill ?? "—"}{" "}
            {delta != null && (
              <span className={`elo-delta ${delta >= 0 ? "pos" : "neg"}`}>
                {delta >= 0 ? "+" : ""}
                {delta} ELO
              </span>
            )}
          </div>
          <div className="insight-sub">
            {solveMs ? `${(solveMs / 1000).toFixed(0)}s to submit` : ""}
          </div>
        </div>

        {rec && (
          <div className="insight-cell">
            <div className="insight-label">Try Next</div>
            <div className="insight-value insight-rec">{rec}</div>
            <div className="insight-sub">recommended for your level</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function BattleScreen({
  you,
  problem,
  players,
  room,
  token,
  onRematch,
  onLeave,
  rematchLabel = "Rematch",
}) {
  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState(() => starterFor(problem?.id, "python"));
  const [testOutput, setTestOutput] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [asm, setAsm] = useState(null);
  const [bytecode, setBytecode] = useState(null);

  const opponent = players.find((p) => p !== you) ?? "Opponent";

  const switchLanguage = (id) => {
    setLanguage(id);
    setCode(starterFor(problem?.id, id));
    if (id !== "cpp") setAsm(null);
    if (id !== "java") setBytecode(null);
  };

  const series = useMemo(() => {
    const out = {};
    for (const [name, data] of Object.entries(room.results)) {
      out[name] = (data.results ?? [])
        .filter((r) => r.ms !== null)
        .map((r) => ({ x: r.n, y: r.ms }));
    }
    return out;
  }, [room.results]);

  async function testRun() {
    setTestOutput("Running...");
    try {
      const data = await api.run(code, language, token);
      if (data.compile_error) setTestOutput(`Compile error: ${data.stderr.slice(0, 160)}`);
      else if (data.stderr) setTestOutput(`ERR: ${data.stderr.slice(0, 160)}`);
      else setTestOutput(`OK — ${data.stdout.slice(0, 80) || "(no output)"} | ${data.time_ms}ms`);
    } catch (err) {
      setTestOutput(err.message);
    }
  }

  async function showAsm() {
    setAsm({ loading: true });
    try {
      const data = await api.asm(code, problem?.id ?? "two_sum", token);
      setAsm(data.error ? { error: data.error } : data);
    } catch (err) {
      setAsm({ error: err.message });
    }
  }

  async function showBytecode() {
    setBytecode({ loading: true });
    try {
      const data = await api.bytecode(code, token);
      setBytecode(data.error ? { error: data.error } : data);
    } catch (err) {
      setBytecode({ error: err.message });
    }
  }

  function submit() {
    if (!code.trim()) return;
    room.submit(code, language);
    setSubmitted(true);
  }

  const info = room.raceInfo;
  const badge =
    room.status === "done" ? "DONE" : room.status === "racing" ? "RACING" : room.readyNote ?? "CODING";

  return (
    <div className="screen active">
      <div className="arena-layout">
        <div className="arena-left">
          <div className="arena-header">
            <div className="arena-players">
              <PlayerChip name={you} isYou className="you" />
              <PlayerChip name={opponent} className="them" />
            </div>
            <div className={`battle-status-badge ${room.status}`}>{badge}</div>
          </div>

          <div className="problem-panel">
            <strong>{problem?.title} —</strong> {problem?.description}
          </div>

          <div className="editor-wrap">
            <div className="editor-toolbar">
              <div className="lang-selector">
                {LANGUAGES.map((l) => (
                  <button
                    key={l.id}
                    className={`lang-btn${language === l.id ? " active" : ""}`}
                    onClick={() => switchLanguage(l.id)}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
              <div className="toolbar-actions">
                <button className="btn-run-small" onClick={testRun}>
                  Test Run
                </button>
                {language === "cpp" && (
                  <button className="btn-asm" onClick={showAsm}>
                    ⊞ ASM
                  </button>
                )}
                {language === "java" && (
                  <button className="btn-asm" onClick={showBytecode}>
                    ⊞ Bytecode
                  </button>
                )}
              </div>
            </div>
            <CodeEditor
              value={code}
              onChange={setCode}
              placeholder="Write your solution here..."
            />
          </div>

          <div className="arena-bottom-bar">
            <div className="test-output-mini">{testOutput}</div>
            <button
              className="btn-submit"
              onClick={submit}
              disabled={submitted || room.status !== "waiting"}
            >
              <span className="submit-icon">⚡</span>{" "}
              {submitted ? "Waiting for opponent..." : "Submit & Race"}
            </button>
          </div>

          {asm && <AsmPanel state={asm} onClose={() => setAsm(null)} />}
          {bytecode && (
            <BytecodePanel state={bytecode} onClose={() => setBytecode(null)} />
          )}
        </div>

        <div className="arena-right">
          <div className="race-panel">
            <div className="race-header">
              <h3>Runtime Race</h3>
              <span className="race-subtitle">Higher N = harder input</span>
            </div>

            <RaceChart
              players={[you, opponent]}
              series={series}
              placeholder={Object.keys(room.results).length === 0}
            />

            {info && (
              <div className="winner-banner visible">
                <div className="winner-banner-top">
                  <span className="winner-crown">🏆</span>
                  <div>
                    <div className="winner-label">Winner</div>
                    <div className="winner-name">
                      {info.winner === "tie" ? "It's a tie!" : info.winner}
                    </div>
                  </div>
                </div>
                <div className="winner-detail">
                  {info.winner === "tie"
                    ? "Both solutions handled the same input size."
                    : info.winner === you
                      ? "Your solution survived larger inputs. Well played."
                      : "Their solution handled larger inputs. Study the difference."}
                </div>

                <Insights you={you} info={info} />

                <div className="winner-actions">
                  <button className="btn-primary" onClick={onRematch}>
                    {rematchLabel}
                  </button>
                  <button className="btn-ghost" onClick={onLeave}>
                    Back to Lobby
                  </button>
                </div>
              </div>
            )}

            <div className="race-result-cards">
              {Object.entries(room.results).map(([name, data]) => (
                <ResultCard
                  key={name}
                  name={name}
                  data={data}
                  isYou={name === you}
                  isWinner={info?.winner === name}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
