/** Pure rules for projects: names, tags, filtering, sorting and dates.
 *
 * The dialogs, the top bar and the Project tab all read the same rules from
 * here, so a name that is refused in one place is refused in all of them. No
 * DOM, so these can be tested without a browser.
 */
/** The filter that shows everything, newest change first.
 * @returns {GalleryFilter}
 */
export const emptyFilter = () => ({
  query: "",
  tags: [],
  tagMatch: "all",
  author: "",
  modifiedWithin: 0,
  runs: "any",
  sort: "modified",
});
/** Whether a filter narrows the list.
 * @param {GalleryFilter} filter
 * @returns {boolean}
 */
export const isFiltered = filter =>
  Boolean(
    filter.query.trim() ||
    filter.tags.length ||
    filter.author.trim() ||
    filter.modifiedWithin ||
    filter.runs !== "any",
  );
/** What is wrong with a project name, if anything.
 * @param {string} name
 * @param {ProjectSummaryData[]} projects Every project of the library.
 * @param {string} [ignore] A project that may keep its own name.
 * @returns {string} A sentence for the person, or "" when the name is fine.
 */
export const nameIssue = (name, projects, ignore = "") => {
  const wanted = name.trim().toLowerCase();
  if (!wanted) return "Give the project a name.";
  if (wanted.length > 80) return "Use at most 80 characters.";
  const taken = projects.some(
    project =>
      project.slug !== ignore && project.name.trim().toLowerCase() === wanted,
  );
  return taken ? "A project with this name already exists." : "";
};
/** Split tags typed by a person, dropping blanks and repeats.
 * @param {string} text Comma-separated tags.
 * @returns {string[]}
 */
export const parseTags = text => {
  /** @type {string[]} */
  const tags = [];
  for (const part of text.split(",")) {
    const tag = part.trim();
    if (tag && !tags.some(item => item.toLowerCase() === tag.toLowerCase()))
      tags.push(tag);
  }
  return tags;
};
/** Everything a project says about itself, in one lowercase string to search.
 * @param {ProjectSummaryData} project
 * @returns {string}
 */
const haystack = project =>
  [
    project.name,
    project.description,
    project.author,
    project.version,
    project.base_url,
    ...project.tags,
  ]
    .join("\n")
    .toLowerCase();
/** Filter and sort the library for the gallery.
 * @param {ProjectSummaryData[]} projects
 * @param {GalleryFilter} filter
 * @param {number} [now] Current time in milliseconds, for "modified within".
 * @returns {ProjectSummaryData[]}
 */
export const filterProjects = (projects, filter, now = Date.now()) => {
  const words = filter.query.toLowerCase().split(/\s+/).filter(Boolean);
  const author = filter.author.trim().toLowerCase();
  const wanted = filter.tags.map(tag => tag.toLowerCase());
  const cutoff = filter.modifiedWithin
    ? now - filter.modifiedWithin * 86_400_000
    : 0;
  const kept = projects.filter(project => {
    const text = haystack(project);
    if (!words.every(word => text.includes(word))) return false;
    if (author && !project.author.toLowerCase().includes(author)) return false;
    if (wanted.length) {
      const own = project.tags.map(tag => tag.toLowerCase());
      const matches =
        filter.tagMatch === "all"
          ? wanted.every(tag => own.includes(tag))
          : wanted.some(tag => own.includes(tag));
      if (!matches) return false;
    }
    if (cutoff && Date.parse(project.modified_at) < cutoff) return false;
    if (filter.runs === "yes" && !project.last_run_at) return false;
    if (filter.runs === "no" && project.last_run_at) return false;
    return true;
  });
  /** @type {Record<GalleryFilter["sort"], (a:ProjectSummaryData,b:ProjectSummaryData)=>number>} */
  const order = {
    modified: (a, b) => b.modified_at.localeCompare(a.modified_at),
    created: (a, b) => b.created_at.localeCompare(a.created_at),
    run: (a, b) => b.last_run_at.localeCompare(a.last_run_at),
    name: (a, b) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: "base" }),
  };
  return kept.sort(order[filter.sort]);
};
/** Say how long ago a time was, in the units a person would use.
 * @param {string} iso An ISO 8601 time, or "".
 * @param {number} [now] Current time in milliseconds.
 * @returns {string} For example "3 hours ago", or "never" for an empty time.
 */
export const ago = (iso, now = Date.now()) => {
  const then = Date.parse(iso);
  if (!iso || Number.isNaN(then)) return "never";
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  /** @type {[number,string][]} */
  const units = [
    [31_536_000, "year"],
    [2_592_000, "month"],
    [86_400, "day"],
    [3600, "hour"],
    [60, "minute"],
  ];
  for (const [size, unit] of units) {
    if (seconds >= size) {
      const count = Math.floor(seconds / size);
      return `${count} ${unit}${count === 1 ? "" : "s"} ago`;
    }
  }
  return "just now";
};
/** A date and time for a details list.
 * @param {string} iso
 * @returns {string} A local date and time, or "—" when there is none.
 */
export const when = iso => {
  const time = Date.parse(iso);
  if (!iso || Number.isNaN(time)) return "—";
  return new Date(time).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
};
/** The recently opened projects, in order, that still exist.
 * @param {LibraryData} library
 * @returns {ProjectSummaryData[]}
 */
export const recentProjects = library =>
  library.recents
    .map(slug => library.projects.find(project => project.slug === slug))
    .filter(project => project !== undefined)
    .slice(0, 5);
