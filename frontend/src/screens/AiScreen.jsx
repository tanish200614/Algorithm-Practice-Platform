import { useEffect, useRef, useState } from "react";

import { api, tokenRoles } from "../api.js";

function Interview({ token }) {
  // The server is stateless: the client holds the transcript and sends it
  // back each turn, so a restart never loses an interview.
  const [history, setHistory] = useState([]);
  const [turns, setTurns] = useState([]); // [{role, content, toolRuns?}]
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  async function send() {
    const message = draft.trim();
    if (!message || busy) return;
    setDraft("");
    setError(null);
    setBusy(true);
    setTurns((t) => [...t, { role: "user", content: message }]);
    try {
      const res = await api.interview(message, history, token);
      setHistory(res.history);
      setTurns((t) => [
        ...t,
        { role: "assistant", content: res.reply, toolRuns: res.tool_runs || [] },
      ]);
    } catch (err) {
      setError(err.message);
      setTurns((t) => t.slice(0, -1));
      setDraft(message);
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setHistory([]);
    setTurns([]);
    setError(null);
  }

  return (
    <div className="ai-panel">
      <div className="ai-chat">
        {turns.length === 0 && (
          <div className="ai-empty">
            Say hi to start a mock interview. Paste code any time — the interviewer runs it in
            the sandbox before judging it.
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`ai-msg ai-msg--${t.role}`}>
            <div className="ai-msg-who">{t.role === "user" ? "You" : "Interviewer"}</div>
            <div className="ai-msg-body">{t.content}</div>
            {t.toolRuns?.map((run, j) => (
              <details key={j} className="ai-toolrun">
                <summary>
                  Ran your {run.language} code —{" "}
                  {run.result.compile_error
                    ? "compile error"
                    : run.result.timed_out
                    ? "timed out"
                    : `exit ${run.result.exit_code}`}
                </summary>
                <pre>{run.result.stdout || run.result.stderr || "(no output)"}</pre>
              </details>
            ))}
          </div>
        ))}
        {busy && <div className="ai-msg ai-msg--assistant ai-typing">Interviewer is thinking…</div>}
        <div ref={endRef} />
      </div>

      {error && <div className="auth-error auth-error--fail">{error}</div>}

      <div className="ai-compose">
        <textarea
          value={draft}
          placeholder="Your answer, or paste code… (Ctrl/⌘+Enter to send)"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
          }}
        />
        <div className="ai-compose-actions">
          <button className="btn-primary" onClick={send} disabled={busy || !draft.trim()}>
            Send →
          </button>
          <button className="btn-ghost small" onClick={reset} disabled={busy}>
            New interview
          </button>
        </div>
      </div>
    </div>
  );
}

function Generator({ token, isAdmin }) {
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("medium");
  const [problem, setProblem] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  if (!isAdmin) {
    return (
      <div className="ai-panel">
        <div className="ai-empty">
          Problem generation calls the model up to three times and runs every candidate in the
          sandbox, so it's limited to accounts with the <strong>ADMIN</strong> role. Admins are
          granted through the GitHub login service.
        </div>
      </div>
    );
  }

  async function generate() {
    if (!topic.trim() || busy) return;
    setBusy(true);
    setError(null);
    setProblem(null);
    try {
      setProblem(await api.generateProblem(topic, difficulty, token));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ai-panel">
      <div className="ai-gen-form">
        <input
          type="text"
          placeholder="Topic, e.g. sliding window, graphs, intervals"
          maxLength={80}
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && generate()}
        />
        <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
        <button className="btn-primary" onClick={generate} disabled={busy || !topic.trim()}>
          {busy ? "Generating + validating…" : "Generate →"}
        </button>
      </div>

      {error && <div className="auth-error auth-error--fail">{error}</div>}

      {problem && (
        <div className="ai-problem">
          <h3>{problem.title}</h3>
          <div className="ai-badge">
            ✓ Reference solution passed {problem._validation?.cases_passed} test cases in the
            sandbox
          </div>
          <p>{problem.description}</p>
          <label>Signature</label>
          <pre>{problem.signature}</pre>
          <label>Test cases</label>
          <pre>
            {problem.test_cases
              .map((c) => `${problem.function_name}(*${c.args}) -> ${c.expected}`)
              .join("\n")}
          </pre>
          <details>
            <summary>Reference solution</summary>
            <pre>{problem.reference_solution}</pre>
          </details>
        </div>
      )}
    </div>
  );
}

export default function AiScreen({ token, onBack }) {
  const [tab, setTab] = useState("interview");
  const [cache, setCache] = useState(null);
  const isAdmin = tokenRoles(token).includes("ADMIN");

  useEffect(() => {
    api
      .aiCache(token)
      .then(setCache)
      .catch(() => setCache(null));
  }, [token, tab]);

  return (
    <div className="screen active">
      <div className="ai-layout">
        <div className="solo-top-bar">
          <button className="btn-ghost small" onClick={onBack}>
            ← Lobby
          </button>
          <h2>AI Practice</h2>
          <div className="lang-selector">
            <button
              className={`lang-btn${tab === "interview" ? " active" : ""}`}
              onClick={() => setTab("interview")}
            >
              Mock Interview
            </button>
            <button
              className={`lang-btn${tab === "generate" ? " active" : ""}`}
              onClick={() => setTab("generate")}
            >
              Problem Generator
            </button>
          </div>
        </div>

        {tab === "interview" ? (
          <Interview token={token} />
        ) : (
          <Generator token={token} isAdmin={isAdmin} />
        )}

        {cache && (
          <div className="ai-cache">
            Response cache ({cache.backend}): {cache.entries} entries
            {cache.hit_rate != null &&
              ` · ${Math.round(cache.hit_rate * 100)}% of requests served without an API call`}
          </div>
        )}
      </div>
    </div>
  );
}
