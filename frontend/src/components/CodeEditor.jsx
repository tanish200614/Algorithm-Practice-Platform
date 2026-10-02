import { useCallback } from "react";

const PAIRS = { "(": ")", "[": "]", "{": "}" };
const CLOSERS = new Set([")", "]", "}"]);

/**
 * A textarea that behaves like a basic code editor: tab inserts spaces,
 * brackets auto-close and wrap a selection, typing a closer skips over an
 * existing one, backspace deletes an empty pair, and Enter keeps the indent
 * (adding a level after `:` or `{`).
 *
 * Every branch sets the caret itself because writing `value` through React
 * moves it to the end.
 */
export default function CodeEditor({ value, onChange, ...props }) {
  const handleKeyDown = useCallback(
    (e) => {
      const ta = e.target;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const val = ta.value;
      const selected = val.slice(start, end);

      const apply = (next, caretStart, caretEnd = caretStart) => {
        e.preventDefault();
        // Write the text and caret straight to the DOM, then tell React.
        // Setting the caret later (rAF or an effect) breaks with fast typing:
        // `print(6*7)` turned into `print(*7)6`. React leaves the selection
        // alone because the value it renders matches what's already there.
        ta.value = next;
        ta.setSelectionRange(caretStart, caretEnd);
        onChange(next);
      };

      if (e.key === "Tab") {
        return apply(`${val.slice(0, start)}    ${val.slice(end)}`, start + 4);
      }

      if (e.key in PAIRS) {
        const close = PAIRS[e.key];
        if (selected) {
          return apply(
            `${val.slice(0, start)}${e.key}${selected}${close}${val.slice(end)}`,
            start + 1,
            end + 1
          );
        }
        return apply(
          `${val.slice(0, start)}${e.key}${close}${val.slice(end)}`,
          start + 1
        );
      }

      if (CLOSERS.has(e.key) && start === end && val[start] === e.key) {
        return apply(val, start + 1);
      }

      if (e.key === "Backspace" && start === end && start > 0) {
        if (val[start - 1] in PAIRS && val[start] === PAIRS[val[start - 1]]) {
          return apply(`${val.slice(0, start - 1)}${val.slice(start + 1)}`, start - 1);
        }
      }

      if (e.key === "Enter") {
        const lineStart = val.lastIndexOf("\n", start - 1) + 1;
        const currentLine = val.slice(lineStart, start);
        const indent = currentLine.match(/^(\s*)/)[1];

        // Caret sitting between a brace pair: open it into three lines.
        if (val[start - 1] === "{" && val[start] === "}") {
          const inner = `\n${indent}    `;
          return apply(
            `${val.slice(0, start)}${inner}\n${indent}${val.slice(end)}`,
            start + inner.length
          );
        }

        const extra = /[:{]\s*$/.test(currentLine) ? "    " : "";
        const ins = `\n${indent}${extra}`;
        return apply(`${val.slice(0, start)}${ins}${val.slice(end)}`, start + ins.length);
      }

      return undefined;
    },
    [onChange]
  );

  return (
    <textarea
      spellCheck="false"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={handleKeyDown}
      {...props}
    />
  );
}
