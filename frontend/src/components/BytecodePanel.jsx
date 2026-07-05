export default function BytecodePanel({ state, onClose }) {
  // Constant-pool refs (#7, #21) are indirection the reader can't resolve
  // without the pool itself; javap already prints the resolved name in the
  // trailing comment, so the number is noise.
  const cleaned = state.bytecode
    ? state.bytecode
        .split("\n")
        .map((line) => line.replace(/\s+#\d+\s{2,}/, "  "))
        .join("\n")
    : null;

  const totalInstructions = (state.methods ?? []).reduce(
    (sum, m) => sum + m.instructions,
    0,
  );

  return (
    <div className="asm-panel">
      <div className="asm-panel-header">
        <span className="asm-panel-title">JVM bytecode · javap -c</span>
        <span className="asm-speedup">
          {totalInstructions > 0 ? `${totalInstructions} instructions` : ""}
        </span>
        <button className="btn-asm-close" onClick={onClose}>
          ✕
        </button>
      </div>

      {state.insights?.length > 0 && (
        <ul className="bytecode-insights">
          {state.insights.map((insight) => (
            <li key={insight.label}>
              <strong>{insight.label}</strong>
              <span>{insight.detail}</span>
            </li>
          ))}
        </ul>
      )}

      {state.methods?.length > 1 && (
        <div className="bytecode-methods">
          {state.methods.map((m) => (
            <span key={m.signature} className="bytecode-method">
              {m.signature} <em>{m.instructions}</em>
            </span>
          ))}
        </div>
      )}

      <pre className="asm-code">
        {state.loading
          ? "Compiling…"
          : state.error
            ? `Error: ${state.error}`
            : cleaned}
      </pre>
    </div>
  );
}
