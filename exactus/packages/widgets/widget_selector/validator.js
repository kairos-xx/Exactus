/** Debounced validation with states, counts and problem stepping. */
/** @typedef {{code:string, message:string, offset:number, length:number, line:number, column:number, severity:"error"|"warning", suggestion?:{offset:number,length:number,text:string}, role?:string}} Diagnostic */
/** @typedef {{state:"idle"|"checking"|"valid"|"warning"|"error", diagnostics:Diagnostic[], errors:number, warnings:number, index:number}} ValidationResult */
/**
 * Create a debounced validator around an engine.
 * @returns {{flush:Function, schedule:Function, current:()=>ValidationResult, step:Function, destroy:()=>void}} The validator API.
 */
export const createValidator = (/** @type {{engine:any, delayMs?:number, multiple?:boolean, onResult:(r:ValidationResult)=>void}} */ { engine, delayMs = 120, multiple = false, onResult }) => {
  /** @type {ValidationResult} */
  let current = { state: "idle", diagnostics: [], errors: 0, warnings: 0, index: 0 };
  /** @type {ReturnType<typeof setTimeout>|undefined} */
  let timer;
  /**
   * Lint the text synchronously and derive the result state.
   * @param {string} text Expression text.
   * @returns {ValidationResult} The validation result.
   */
  const run = text => {
    if (!text.trim()) return { state: "idle", diagnostics: [], errors: 0, warnings: 0, index: 0 };
    /** @type {Diagnostic[]} */
    let found = [];
    if (!engine) found = [];
    else if (multiple) {
      let offset = 0;
      text.split("\n").forEach((line, row) => {
        if (line.trim())
          found.push(...engine.lint(line, { warnings: true }).map((/** @type {Diagnostic} */ d) => ({ ...d, offset: d.offset + offset, line: row + 1, ...(d.suggestion ? { suggestion: { ...d.suggestion, offset: d.suggestion.offset + offset } } : {}) })));
        offset += line.length + 1;
      });
    } else found = engine.lint(text, { warnings: true });
    const errors = found.filter(d => d.severity === "error").length;
    const warnings = found.length - errors;
    return { state: errors ? "error" : warnings ? "warning" : "valid", diagnostics: found, errors, warnings, index: 0 };
  };
  /**
   * Validate immediately, cancelling any pending debounce.
   * @param {string} text Expression text.
   * @returns {ValidationResult} The validation result.
   */
  const flush = text => {
    clearTimeout(timer);
    current = run(text);
    onResult(current);
    return current;
  };
  return {
    flush,
    /** @param {string} text */
    schedule: text => {
      clearTimeout(timer);
      current = { ...current, state: "checking" };
      onResult(current);
      timer = setTimeout(() => flush(text), delayMs);
    },
    current: () => current,
    /** @param {1|-1} direction */
    step: direction => {
      if (!current.diagnostics.length) return null;
      current.index = (current.index + direction + current.diagnostics.length) % current.diagnostics.length;
      onResult(current);
      return current.diagnostics[current.index] ?? null;
    },
    destroy: () => clearTimeout(timer),
  };
};
