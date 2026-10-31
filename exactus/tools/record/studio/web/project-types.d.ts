/** Shapes of the project data the Studio's snapshot carries. */

/** One project of the library, as the gallery lists it. */
interface ProjectSummaryData {
  slug: string;
  name: string;
  description: string;
  tags: string[];
  author: string;
  version: string;
  /** ISO 8601 UTC time, or empty when unknown. */
  created_at: string;
  modified_at: string;
  last_run_at: string;
  flows: number;
  runs: number;
  /** The address the project's tests start from, or empty. */
  base_url: string;
  /** Whether this is the Studio folder's own project. */
  legacy: boolean;
}

/** Every project, the recently opened ones and all tags in use. */
interface LibraryData {
  projects: ProjectSummaryData[];
  /** Identifiers of recently opened projects, most recent first. */
  recents: string[];
  tags: string[];
}

/** The project that is open now, including edits not yet saved. */
interface ProjectState {
  slug: string;
  name: string;
  description: string;
  tags: string[];
  author: string;
  version: string;
  created_at: string;
  base_url: string;
  /** Whether the project already has a file on disk. */
  saved: boolean;
}

/** What the gallery's search and advanced search ask for. */
interface GalleryFilter {
  query: string;
  tags: string[];
  /** "all" needs every selected tag, "any" needs at least one. */
  tagMatch: "all" | "any";
  author: string;
  /** Days since the last change; 0 means any time. */
  modifiedWithin: number;
  runs: "any" | "yes" | "no";
  sort: "modified" | "created" | "name" | "run";
}
