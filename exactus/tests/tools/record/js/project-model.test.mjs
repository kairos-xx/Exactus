/** Project names, tags, filtering and dates. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  ago,
  emptyFilter,
  filterProjects,
  nameIssue,
  parseTags,
} from "../../../../tools/record/studio/web/project-model.js";
const now = Date.parse("2026-10-09T12:00:00Z");
/** A project summary with any field overridden.
 * @param {Partial<ProjectSummaryData>} extra Fields to override.
 * @returns {ProjectSummaryData}
 */
const project = extra => ({
  slug: "x",
  name: "X",
  description: "",
  tags: [],
  author: "",
  version: "",
  created_at: "2026-10-01T00:00:00",
  modified_at: "2026-10-08T00:00:00",
  last_run_at: "",
  flows: 1,
  runs: 0,
  base_url: "",
  legacy: false,
  ...extra,
});
const projects = [
  project({
    slug: "a",
    name: "Checkout",
    tags: ["web", "smoke"],
    author: "Ana",
    last_run_at: "2026-10-08T10:00:00",
    modified_at: "2026-10-08T10:00:00",
  }),
  project({
    slug: "b",
    name: "Admin panel",
    tags: ["web"],
    base_url: "http://localhost:3000",
    modified_at: "2026-09-01T00:00:00",
  }),
  project({
    slug: "c",
    name: "Demo",
    tags: ["demo"],
    modified_at: "2026-10-09T09:00:00",
  }),
];
test("names must be present and unique, ignoring case and the project's own name", () => {
  assert.match(nameIssue("  ", projects), /name/);
  assert.match(nameIssue("checkout", projects), /already exists/);
  assert.equal(nameIssue("checkout", projects, "a"), "");
  assert.equal(nameIssue("Fresh", projects), "");
});
test("tags are trimmed and de-duplicated without regard to case", () => {
  assert.deepEqual(parseTags(" web, Smoke ,web,, SMOKE "), ["web", "Smoke"]);
});
test("search matches any field; advanced criteria narrow it", () => {
  /** Assert the slugs a filter change selects.
   * @param {Partial<GalleryFilter>} change Fields merged into the empty filter.
   * @param {string[]} slugs Expected selected slugs in order.
   * @returns {void}
   */
  const check = (change, slugs) =>
    assert.deepEqual(
      filterProjects(projects, { ...emptyFilter(), ...change }, now).map(
        item => item.slug,
      ),
      slugs,
    );
  check({}, ["c", "a", "b"]);
  check({ query: "localhost" }, ["b"]);
  check({ query: "ana smoke" }, ["a"]);
  check({ tags: ["web"] }, ["a", "b"]);
  check({ tags: ["web", "smoke"], tagMatch: "all" }, ["a"]);
  check({ tags: ["demo", "smoke"], tagMatch: "any" }, ["c", "a"]);
  check({ modifiedWithin: 7 }, ["c", "a"]);
  check({ runs: "yes" }, ["a"]);
  check({ runs: "no", sort: "name" }, ["b", "c"]);
});
test("times read the way a person says them", () => {
  assert.equal(ago("", now), "never");
  assert.equal(ago("2026-10-09T11:59:40Z", now), "just now");
  assert.equal(ago("2026-10-09T09:00:00Z", now), "3 hours ago");
  assert.equal(ago("2026-10-08T12:00:00Z", now), "1 day ago");
});
