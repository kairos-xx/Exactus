/** Types for the offline dashboard script `dashboard.js`. */

/** One checklist task as the generated page embeds it. */
interface TodoTask {
  id: string;
  text: string;
  done: boolean;
  ongoing: boolean;
  priority: string;
  category: string;
  /** Line of the task in the source document. */
  line: number;
  /** Titles of the headings the task sits under. */
  wpath: string[];
  /** Source lines of those headings, in the same order. */
  wlines: number[];
  /** Any other facet field, such as workstream or prefix. */
  [field: string]: string | number | boolean | string[] | number[] | undefined;
}
