export default function AsmPanel({ state, onClose }) {
  // .cfi_ directives are exception-handling metadata — pure noise when the
  // point is to read what the optimiser produced.
  const cleaned = state.asm
    ? state.asm
        .split("\n")
        .filter((line) => !line.trim().startsWith(".cfi_"))
        .join("\n")
        .replace(/\n{3,}/g, "\n\n")
    : null;

  let badge = "";
  if (state.speedup) badge = `${state.speedup}× faster with -O2`;
  else if (state.o0_ms && state.o2_ms) badge = `-O0: ${state.o0_ms}ms  -O2: ${state.o2_ms}ms`;

  return (
    <div className="asm-panel">
      <div className="asm-panel-header">
        <span className="asm-panel-title">Assembly · g++ -O2</span>
        <span className="asm-speedup">{badge}</span>
        <button className="btn-asm-close" onClick={onClose}>
          ✕
        </button>
      </div>
      <pre className="asm-code">
        {state.loading ? "Compiling…" : state.error ? `Error: ${state.error}` : cleaned}
      </pre>
    </div>
  );
}
