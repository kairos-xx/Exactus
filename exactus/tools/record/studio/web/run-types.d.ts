/** Shapes of the run results the editor shows for a step. */

/** Why an action failed or only warned. */
interface RunCause {
  phase?: string;
  message?: string;
  expression?: string;
  expected_count?: number | null;
  found_count?: number;
  resolved_css?: string;
  target_index?: number | null;
  timeout_ms?: number;
  failed?: { index: number; checks?: string[] }[];
  changes?: { field: string; baseline: unknown; current: unknown }[];
  playwright_error?: string;
}

/** One line the action's snippet wrote to the console. */
interface RunStream {
  level: string;
  source: string;
  message: string;
}

/** The result of running one action, or one match of it. */
interface RunRecord {
  event_id: string;
  status: string;
  error?: string | null;
  cause?: RunCause | null;
  unit?: { index: number; count: number } | null;
  streams?: RunStream[];
  response?: unknown;
}
