/** Types shared by the page scripts `selector_resolve.js` and
 * `selector_sandbox.js`. Those files are evaluated as single expressions, so
 * their types live here instead of in typedef comments.
 */

/** One resolve request sent to the page. */
interface ResolveArgs {
  expression: string;
  definitions: Record<string, string>;
  checks: string[];
  compile: boolean;
}

/** One element a resolve request found. */
interface ResolveMatch {
  index: number;
  css: string | null;
  cssError: string | null;
  rect: { x: number; y: number; width: number; height: number };
  evidence: Record<string, unknown>;
  failed: string[];
}

/** What a resolve request returns. */
interface ResolveResult {
  count: number;
  matches: ResolveMatch[];
  error: string | null;
  definitionErrors: string[];
}

/** One console line a sandboxed snippet wrote. */
interface SandboxLogEntry {
  level: string;
  message: string;
  at: number;
}

/** The console channels of the flow object. */
type SandboxLevel = "log" | "warn" | "error";

/** One sandbox run request sent to the page. */
interface SandboxContext {
  script: string;
  definitions: Record<string, string>;
  vars: Record<string, unknown>;
  logs: SandboxLogEntry[];
  warnings: SandboxLogEntry[];
  errors: SandboxLogEntry[];
  flowId: string;
  actionId: string;
  runId: string;
  targets: string[];
  indices: number[];
  count: number;
  flowName: string;
  actionKind: string;
  actionLabel: string;
  project: { id: string; name: string; revision: string };
  context: { id: string; name: string; baseUrl: string; origin: string };
}
