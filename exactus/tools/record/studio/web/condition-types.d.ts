/** One name a condition can use, as the server's vocabulary lists it. */
interface ConditionTerm {
  name: string;
  kind: "system" | "probe" | "output";
  /** What the name evaluates to, so the editor can type-check a condition. */
  value_type: "string" | "integer" | "float" | "boolean" | "json";
  detail: string;
}
