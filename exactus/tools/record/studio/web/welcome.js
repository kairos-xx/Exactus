/** The first-run screen: what a new person sees before any project exists.
 *
 * It covers the editor until there is a project, or until the person chooses to
 * go on without one. It says what the Studio does in one sentence, offers the
 * three ways to begin, and shows a flow as what it is: steps on a timeline.
 */
import { h, icon } from "./project-dialogs.js";
/** Where "go on without a project" is remembered for this browser session. */
export const DISMISSED_KEY = "studio.welcome.dismissed";
/** Whether the first-run screen should cover the editor.
 * @param {{library?:LibraryData,project?:ProjectState,workspace?:{flows?:{events?:unknown[]}[]}}|null} snapshot
 * @param {string} view The workspace tab that is showing.
 * @param {boolean} dismissed Whether the person already chose to go on without one.
 * @returns {boolean}
 */
export const shouldWelcome = (snapshot, view, dismissed) => {
  if (dismissed || view !== "edit" || !snapshot?.library || !snapshot.project)
    return false;
  const empty = snapshot.library.projects.length === 0;
  const unsaved = !snapshot.project.saved;
  const worked = (snapshot.workspace?.flows ?? []).some(
    flow => (flow.events ?? []).length > 0,
  );
  return empty && unsaved && !worked;
};
/** The steps the sample timeline plays, in order.
 * @type {readonly {icon:string,label:string,start:number,length:number}[]}
 */
const SAMPLE = Object.freeze([
  { icon: "world", label: "Open the app", start: 0, length: 1 },
  { icon: "mouse", label: "Click Save order", start: 1.2, length: 1.2 },
  {
    icon: "circle-check",
    label: "Check the text is Saved",
    start: 2.6,
    length: 1.4,
  },
]);
/** The sample timeline: a ruler, three steps and a playhead that sweeps once.
 * It is explanation, not controls, so assistive technology skips it.
 * @returns {HTMLElement}
 */
const timeline = () => {
  const seconds = 4;
  const ticks = Array.from({ length: seconds + 1 }, (_, index) =>
    h("span", {
      class: "welcome-tick",
      style: `--dynamic-at: ${(index / seconds) * 100}%`,
      text: `${index}s`,
    }),
  );
  const clips = SAMPLE.map(step => {
    const clip = h(
      "span",
      {
        class: "welcome-clip",
        style: `--dynamic-from: ${(step.start / seconds) * 100}%; --dynamic-span: ${(step.length / seconds) * 100}%; --dynamic-played-at: ${0.4 + step.start}s`,
      },
      [icon(step.icon), h("span", { text: step.label })],
    );
    return clip;
  });
  return h("div", { class: "welcome-timeline", "aria-hidden": "true" }, [
    h("div", { class: "welcome-ruler" }, ticks),
    h("div", { class: "welcome-track" }, clips),
    h("span", { class: "welcome-playhead" }),
  ]);
};
/** Draw the first-run screen.
 * @param {HTMLElement} root The section that holds it.
 * @param {{create:() => unknown,openDemo:() => unknown,importFile:() => unknown,dismiss:() => void}} actions
 * @returns {void}
 */
export const renderWelcome = (root, actions) => {
  if (root.firstChild) return;
  /** A welcome action button wired to its callback.
   * @param {string} label Button text.
   * @param {string} iconName Icon from the shared set.
   * @param {() => unknown} run Click callback.
   * @param {boolean} accent Whether to use the accent style.
   * @returns {HTMLButtonElement}
   */
  const make = (label, iconName, run, accent = false) => {
    const button = /** @type {HTMLButtonElement} */ (
      h("button", { type: "button", ...(accent ? { class: "accent" } : {}) }, [
        icon(iconName),
        h("span", { text: label }),
      ])
    );
    button.addEventListener("click", () => run());
    return button;
  };
  const skip = /** @type {HTMLButtonElement} */ (
    h("button", {
      type: "button",
      class: "welcome-skip",
      text: "Skip and open the empty editor",
    })
  );
  skip.addEventListener("click", actions.dismiss);
  root.append(
    h("div", { class: "welcome-body" }, [
      h("h2", {
        id: "welcome-title",
        text: "Record a flow once. Replay it on every build.",
      }),
      h("p", {
        class: "welcome-lede",
        text: "Flow Studio watches you use your app in a test browser and turns each click, key press and check into a step you can edit.",
      }),
      h("div", { class: "welcome-actions" }, [
        make("New project", "plus", actions.create, true),
        make("Open demo flow", "world", actions.openDemo),
        make("Import project", "upload", actions.importFile),
      ]),
      h("p", {
        class: "welcome-note",
        text: "Each project is a folder of its own, so flows, selectors and results stay together.",
      }),
      timeline(),
      h("p", {
        class: "welcome-caption",
        text: "A flow is a row of steps on a timeline. Reorder them, retime them, and add a check after any step.",
      }),
      skip,
    ]),
  );
};
