import { useState } from "react";

import { api } from "../api.js";
import CodeEditor from "../components/CodeEditor.jsx";

const LANGUAGES = [
  { id: "python", label: "Python" },
  { id: "cpp", label: "C++" },
  { id: "java", label: "Java" },
];

export default function SoloScreen({ token, onBack }) {
  const [language, setLanguage] = useState("python");
  const [code, setCode] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    setBusy(true);
    setResult(null);
    try {
      setResult(await api.run(code, language, token));
    } catch (err) {
      setResult({ stdout: "", stderr: err.message, time_ms: 0 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="screen active">
      <div className="solo-layout">
        <div className="solo-top-bar">
          <button className="btn-ghost small" onClick={onBack}>
            ← Lobby
          </button>
          <h2>Solo Practice</h2>
          <div className="lang-selector">
            {LANGUAGES.map((l) => (
              <button
                key={l.id}
                className={`lang-btn${language === l.id ? " active" : ""}`}
                onClick={() => setLanguage(l.id)}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>

        <CodeEditor
          value={code}
          onChange={setCode}
          placeholder="Write your code here..."
        />

        <button className="btn-primary" onClick={run} disabled={busy}>
          {busy ? "Running…" : "▶ Run Code"}
        </button>

        <div className="solo-output">
          <div className="output-section">
            <label>Output</label>
            <pre>{result?.stdout ?? ""}</pre>
          </div>
          <div className="output-section">
            <label>{result?.compile_error ? "Compile error" : "Errors"}</label>
            <pre className="err">{result?.stderr ?? ""}</pre>
          </div>
          <div className="output-section">
            <label>Sandbox</label>
            <pre>
              {result
                ? [
                    `Time:   ${result.time_ms ?? "?"} ms`,
                    `Limits: ${result.memory_limit_mb} MB / ${result.time_limit_s}s`,
                    `Mode:   ${result.isolated ? "isolated container" : "host (unisolated)"}`,
                  ].join("\n")
                : ""}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
