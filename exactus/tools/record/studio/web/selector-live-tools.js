/** Page-aware controls shared by every ExtendedSelector editing surface. */
import { iconElement } from "./icons.js";
/** Describe a match count in words.
 * @param {number|null|undefined} count
 * @returns {string}
 */
const countCopy = count => {
  if (count === null || count === undefined) return "Not checked";
  return `${count} ${count === 1 ? "match" : "matches"}`;
};
/**
 * Build the page picker, generated-strategy chooser and live highlighter.
 * @param {object} options
 * @param {()=>string} options.getValue Current selector expression.
 * @param {(value:string)=>void} options.setValue Replace the expression.
 * @param {((apply:(element:{selector:string,matches?:number,alternatives?:Array<{strategy:string,selector:string,matches:number}>})=>void)=>void)|undefined} [options.onPick]
 * @param {((value:string,done:(result:{count?:number})=>void)=>void)|undefined} [options.onHighlight]
 * @param {(()=>void)|undefined} [options.onClear] Remove the page highlight.
 * @param {number|null|undefined} [options.matchCount]
 * @returns {{element:HTMLElement,setCount:(count:number|null|undefined)=>void}}
 */
export const selectorLiveTools = options => {
  const element = document.createElement("section");
  element.className = "selector-live-tools";
  element.setAttribute("aria-label", "Page selector tools");
  const actions = document.createElement("div");
  actions.className = "selector-live-actions";
  const strategy = document.createElement("select");
  strategy.className = "selector-live-strategy";
  strategy.setAttribute("aria-label", "Generated selector strategy");
  strategy.hidden = true;
  const count = document.createElement("output");
  count.className = "selector-live-count";
  count.setAttribute("aria-live", "polite");
  /** Show a match count, or the unchecked state.
   * @param {number|null|undefined} value
   * @returns {void}
   */
  const setCount = value => {
    count.value = countCopy(value);
    count.textContent = count.value;
    count.toggleAttribute("data-empty", value === null || value === undefined);
  };
  setCount(options.matchCount);
  /** Build one labelled tool button.
   * @param {string} label
   * @param {string} icon
   * @returns {HTMLButtonElement}
   */
  const button = (label, icon) => {
    const control = document.createElement("button");
    control.type = "button";
    control.append(iconElement(icon), document.createTextNode(label));
    return control;
  };
  const pick = button("Pick on page", "crosshair");
  const highlight = button("Highlight on page", "eye");
  pick.disabled = !options.onPick;
  highlight.disabled = !options.onHighlight;
  pick.addEventListener("click", () => options.onPick?.(picked => {
    const choices = picked.alternatives?.length
      ? picked.alternatives
      : [{
          strategy: "css",
          selector: picked.selector,
          matches: picked.matches ?? 1,
        }];
    const preferred = Math.max(0, choices.findIndex(item => item.matches === 1));
    strategy.replaceChildren(...choices.map((item, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = `${item.strategy} — ${countCopy(item.matches)}`;
      return option;
    }));
    strategy.value = String(preferred);
    strategy.hidden = choices.length < 2;
    /** Apply the chosen generated strategy to the expression.
     * @returns {void}
     */
    const apply = () => {
      const selected = choices[Number(strategy.value)];
      if (!selected) return;
      options.setValue(selected.selector);
      setCount(selected.matches);
    };
    strategy.onchange = apply;
    apply();
  }));
  highlight.addEventListener("click", () => {
    const value = options.getValue().trim();
    if (!value) {
      setCount(0);
      options.onClear?.();
      return;
    }
    count.value = "Checking…";
    count.textContent = count.value;
    options.onHighlight?.(value, result => setCount(result.count));
  });
  actions.append(pick, highlight, count);
  element.append(actions, strategy);
  return { element, setCount };
};
