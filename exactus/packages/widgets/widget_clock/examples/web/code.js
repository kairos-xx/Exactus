/** Read the input control that fired an event.
 * @param {Event} event Event whose currentTarget is the control.
 * @returns {HTMLInputElement}
 * @throws {TypeError} When the event did not come from an input or select.
 */
const controlFromEvent = event => {
  if (!(
    event.currentTarget instanceof HTMLInputElement ||
    event.currentTarget instanceof HTMLSelectElement
  ))
    throw new TypeError("Expected an input control");
  return /** @type {HTMLInputElement} */ (event.currentTarget);
};
/* global AnalogClock: readonly */
/** Look up a required control element by id.
 * @param {string} id Element id.
 * @returns {HTMLInputElement}
 * @throws {Error} When the id is absent or not an element.
 */
const getElement = id => {
  const element = document.getElementById(id);
  if (!(element instanceof HTMLElement))
    throw new Error(`Missing clock control: ${id}`);
  return /** @type {HTMLInputElement} */ (element);
};
const target = getElement("analog-clock-target");
const mount = getElement("analog-clock-mount");
const analogClock = new AnalogClock(mount, {
  recording: true,
  recVisible: "visible",
  background: "#080a0c",
});
Object.assign(globalThis, {
  analogClock,
});
const resizeHandle = /** @type {HTMLButtonElement} */ (
  target.querySelector(".target-resize-handle")
);
/** Resize the clock target to a dragged width and height.
 * @param {any} width Requested width in CSS pixels.
 * @param {any} height Requested height in CSS pixels.
 * @returns {void}
 */
const resizeTarget = (width, height) => {
  const style = getComputedStyle(target);
  const container = /** @type {HTMLElement} */ (target.parentElement);
  const containerStyle = getComputedStyle(container);
  const availableWidth =
    container.clientWidth -
    parseFloat(containerStyle.paddingLeft) -
    parseFloat(containerStyle.paddingRight);
  const availableHeight =
    container.clientHeight -
    parseFloat(containerStyle.paddingTop) -
    parseFloat(containerStyle.paddingBottom);
  /** Resolve a CSS max-size limit to pixels; % means a share of available.
   * @returns {number} Pixel limit.
   */
  const resolveLimit = (
    /** @type {string} */ limit,
    /** @type {number} */ available,
  ) =>
    limit.endsWith("%")
      ? (parseFloat(limit) * available) / 100
      : parseFloat(limit) || available;
  const maxWidth = resolveLimit(style.maxWidth, availableWidth);
  const maxHeight = resolveLimit(style.maxHeight, availableHeight);
  target.style.inlineSize = `${Math.min(maxWidth, Math.max(Math.min(parseFloat(style.minWidth) || 0, maxWidth), width))}px`;
  target.style.blockSize = `${Math.min(maxHeight, Math.max(Math.min(parseFloat(style.minHeight) || 0, maxHeight), height))}px`;
};
/** @type {{pointerId:number,startX:number,startY:number,width:number,height:number}|null} */
let resizeState = null;
resizeHandle.addEventListener("pointerdown", event => {
  if (event.button !== 0) return;
  const rect = target.getBoundingClientRect();
  resizeState = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    width: rect.width,
    height: rect.height,
  };
  resizeHandle.setPointerCapture(event.pointerId);
  event.preventDefault();
});
resizeHandle.addEventListener("pointermove", event => {
  if (!resizeState || resizeState.pointerId !== event.pointerId) return;
  resizeTarget(
    resizeState.width + event.clientX - resizeState.startX,
    resizeState.height + event.clientY - resizeState.startY,
  );
});
/** End a resize drag and release the pointer capture.
 * @param {any} event Pointerup event that ends the drag.
 * @returns {void}
 */
const finishResize = event => {
  if (!resizeState || resizeState.pointerId !== event.pointerId) return;
  resizeState = null;
  if (resizeHandle.hasPointerCapture(event.pointerId))
    resizeHandle.releasePointerCapture(event.pointerId);
};
resizeHandle.addEventListener("pointerup", finishResize);
resizeHandle.addEventListener("pointercancel", finishResize);
resizeHandle.addEventListener("lostpointercapture", () => {
  resizeState = null;
});
resizeHandle.addEventListener("keydown", event => {
  if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key))
    return;
  event.preventDefault();
  const rect = target.getBoundingClientRect();
  const step = event.shiftKey ? 32 : 8;
  resizeTarget(
    rect.width +
      (event.key === "ArrowRight"
        ? step
        : event.key === "ArrowLeft"
          ? -step
          : 0),
    rect.height +
      (event.key === "ArrowDown" ? step : event.key === "ArrowUp" ? -step : 0),
  );
});
/** @type {Record<string,[string,string]>} */
const numericControls = Object.freeze({
  fps: ["fps", ""],
  "matrix-rows": ["matrixRows", ""],
  "matrix-columns": ["matrixColumns", ""],
  "separator-width": ["separatorWidth", ""],
  "segment-on-duration": ["segmentOnDuration", " ms"],
  "segment-off-duration": ["segmentOffDuration", " ms"],
  "dot-blink-duration": ["dotBlinkDuration", " ms"],
  "rec-led-size": ["recLedSize", ""],
  "rec-led-glow-size": ["recLedGlowSize", ""],
  "rec-pulse-duration": ["recPulseDuration", " ms"],
  "rec-font-size": ["recFontSize", ""],
  "rec-font-weight": ["recFontWeight", ""],
  "rec-letter-spacing": ["recLetterSpacing", ""],
  "rec-gap": ["recGap", ""],
  padding: ["padding", ""],
});
Object.entries(numericControls).forEach(([id, [property, suffix]]) => {
  const input = getElement(id);
  const output = getElement(`${id}-out`);
  if (!(input instanceof HTMLInputElement)) return;
  input.addEventListener("input", () => {
    const value = Number(input.value);
    if (output instanceof HTMLOutputElement) output.value = `${value}${suffix}`;
    analogClock.set({
      [property]: value,
    });
  });
});
const booleanControls = Object.freeze({
  live: "live",
  "blink-separators": "blinkSeparatorsOnSecond",
  "rec-enabled": "recEnabled",
  recording: "recording",
  "rec-pulse": "recPulse",
});
Object.entries(booleanControls).forEach(([id, property]) => {
  const input = getElement(id);
  if (!(input instanceof HTMLInputElement)) return;
  input.addEventListener("change", () => {
    analogClock.set({
      [property]: input.checked,
    });
  });
});
const textControls = Object.freeze({
  "transition-easing": "transitionEasing",
  "rec-label": "recLabel",
  "rec-font-family": "recFontFamily",
});
Object.entries(textControls).forEach(([id, property]) => {
  const input = getElement(id);
  if (!(input instanceof HTMLInputElement)) return;
  input.addEventListener("input", () => {
    analogClock.set({
      [property]: input.value,
    });
  });
});
const colorControls = Object.freeze({
  "rec-led-on-color": "recLedOnColor",
  "rec-led-off-color": "recLedOffColor",
  "rec-led-glow-color": "recLedGlowColor",
  "rec-text-color": "recTextColor",
  background: "background",
});
Object.entries(colorControls).forEach(([id, property]) => {
  const input = getElement(id);
  if (!(input instanceof HTMLInputElement)) return;
  input.addEventListener("input", () => {
    analogClock.set({
      [property]: input.value,
    });
  });
});
getElement("mode").addEventListener("change", event => {
  analogClock.set({
    mode: controlFromEvent(event).value,
  });
});
getElement("matrix-layout").addEventListener("change", event => {
  analogClock.set({
    matrixLayout: controlFromEvent(event).value,
  });
});
const groupValuesEditor = getElement("group-values");
/** Rebuild the per-group value editor rows.
 * @returns {void}
 */
const renderGroupValues = () => {
  getElement("live").checked = analogClock.live;
  groupValuesEditor.replaceChildren();
  const groups = analogClock.groupItems();
  const values = analogClock.groupValues;
  groups.forEach(
    (/** @type {{digits:number}} */ group, /** @type {number} */ index) => {
      const label = document.createElement("label");
      label.textContent = `Group ${index + 1} (${group.digits} digits)`;
      const input = Object.assign(document.createElement("input"), {
        type: "text",
        inputMode: "numeric",
        maxLength: Number(group.digits),
        placeholder: "-".repeat(Number(group.digits)),
        value: values?.[index] ?? "",
      });
      input.addEventListener("input", () => {
        if (!new RegExp(`^\\d{${group.digits}}$`).test(input.value)) return;
        analogClock.setGroupValue(index, input.value);
        getElement("live").checked = false;
      });
      input.addEventListener("change", () => {
        if (input.value === "") {
          analogClock.clear();
          renderGroupValues();
          return;
        }
        try {
          analogClock.setGroupValue(index, input.value);
        } catch (error) {
          input.setCustomValidity(
            String(error instanceof Error ? error.message : error),
          );
          input.reportValidity();
          input.setCustomValidity("");
        }
      });
      label.append(input);
      groupValuesEditor.append(label);
    },
  );
};
getElement("clear-values").addEventListener("click", () => {
  analogClock.clear();
  renderGroupValues();
});
getElement("resume-live").addEventListener("click", () => {
  analogClock.resume();
  getElement("live").checked = true;
});
const structureEditor = getElement("structure-editor");
/** Apply one edited structure field back to the clock.
 * @param {any} index Structure entry index.
 * @param {any} name Field name being edited.
 * @param {any} value New field value.
 * @returns {void}
 */
const updateStructureItem = (index, name, value) => {
  const structure = analogClock.normalizedStructure();
  structure[index][name] = value;
  analogClock.set({
    structure,
  });
  renderGroupValues();
};
/** Rebuild the structure editor rows from the clock layout.
 * @returns {void}
 */
const renderStructureEditor = () => {
  structureEditor.replaceChildren();
  analogClock
    .normalizedStructure()
    .forEach((/** @type {any} */ item, /** @type {number} */ index) => {
      const row = document.createElement("div");
      row.className = "structure-row";
      const title = document.createElement("strong");
      title.textContent =
        item.type === "group"
          ? `Group ${index + 1} · digit style`
          : `Marker ${index + 1} · marker style`;
      row.append(title);
      const fields =
        item.type === "group"
          ? [
              ["digits", "number", item.digits, 1, 12, 1],
              [
                "digitGap",
                "number",
                item.digitGap ?? analogClock.settings.digitGap,
                0,
                200,
                0.5,
              ],
              [
                "color",
                "color",
                item.color ?? analogClock.settings.segmentOnColor,
                null,
                null,
                null,
              ],
              [
                "offColor",
                "color",
                item.offColor ?? analogClock.settings.segmentOffColor,
                null,
                null,
                null,
              ],
              [
                "glowColor",
                "color",
                item.glowColor ?? analogClock.settings.segmentGlowColor,
                null,
                null,
                null,
              ],
              [
                "glowSize",
                "number",
                item.glowSize ?? analogClock.settings.segmentGlowSize,
                0,
                100,
                0.5,
              ],
              [
                "digitWidth",
                "number",
                item.digitWidth ?? analogClock.settings.digitWidth,
                20,
                300,
                1,
              ],
              [
                "digitHeight",
                "number",
                item.digitHeight ?? analogClock.settings.digitHeight,
                40,
                500,
                1,
              ],
              [
                "segmentLength",
                "number",
                item.segmentLength ?? analogClock.settings.segmentLength,
                20,
                200,
                1,
              ],
              [
                "segmentThickness",
                "number",
                item.segmentThickness ?? analogClock.settings.segmentThickness,
                2,
                50,
                0.5,
              ],
              [
                "segmentGap",
                "number",
                item.segmentGap ?? analogClock.settings.segmentGap,
                0,
                30,
                0.5,
              ],
              [
                "onDuration",
                "number",
                item.onDuration ?? analogClock.settings.segmentOnDuration,
                0,
                2000,
                10,
              ],
              [
                "offDuration",
                "number",
                item.offDuration ?? analogClock.settings.segmentOffDuration,
                0,
                2000,
                10,
              ],
              [
                "easing",
                "text",
                item.easing ?? analogClock.settings.transitionEasing,
                null,
                null,
                null,
              ],
              [
                "matrixColumns",
                "number",
                item.matrixColumns ?? analogClock.settings.matrixColumns,
                3,
                15,
                1,
              ],
              [
                "matrixDotSize",
                "number",
                item.matrixDotSize ?? analogClock.settings.matrixDotSize,
                1,
                30,
                0.5,
              ],
              [
                "matrixDotGap",
                "number",
                item.matrixDotGap ?? analogClock.settings.matrixDotGap,
                0,
                20,
                0.5,
              ],
              [
                "matrixOnColor",
                "color",
                item.matrixOnColor ??
                  item.color ??
                  analogClock.settings.matrixOnColor,
                null,
                null,
                null,
              ],
              [
                "matrixOffColor",
                "color",
                item.matrixOffColor ??
                  item.offColor ??
                  analogClock.settings.matrixOffColor,
                null,
                null,
                null,
              ],
              [
                "matrixGlowColor",
                "color",
                item.matrixGlowColor ??
                  item.glowColor ??
                  analogClock.settings.matrixOnColor,
                null,
                null,
                null,
              ],
              [
                "matrixGlowSize",
                "number",
                item.matrixGlowSize ??
                  item.glowSize ??
                  analogClock.settings.matrixGlowSize,
                0,
                100,
                0.5,
              ],
            ]
          : [
              ["symbol", "text", item.symbol, null, null, null],
              ["size", "number", item.size, 1, 100, 0.5],
              ["color", "color", item.color, null, null, null],
              ["offColor", "color", item.offColor, null, null, null],
              ["glowColor", "color", item.glowColor, null, null, null],
              ["glowSize", "number", item.glowSize, 0, 100, 0.5],
              ["gapBefore", "number", item.gapBefore, 0, 200, 0.5],
              ["gapAfter", "number", item.gapAfter, 0, 200, 0.5],
              [
                "matrixSize",
                "number",
                item.matrixSize ?? analogClock.settings.matrixDotSize,
                1,
                30,
                0.5,
              ],
              [
                "matrixColor",
                "color",
                item.matrixColor ??
                  item.color ??
                  analogClock.settings.matrixOnColor,
                null,
                null,
                null,
              ],
              [
                "matrixOffColor",
                "color",
                item.matrixOffColor ??
                  item.offColor ??
                  analogClock.settings.matrixOffColor,
                null,
                null,
                null,
              ],
              [
                "matrixGlowColor",
                "color",
                item.matrixGlowColor ??
                  item.glowColor ??
                  analogClock.settings.matrixOnColor,
                null,
                null,
                null,
              ],
              [
                "matrixGlowSize",
                "number",
                item.matrixGlowSize ?? item.glowSize ?? 0,
                0,
                100,
                0.5,
              ],
            ];
      fields.forEach(([name, type, value, minimum, maximum, step]) => {
        const label = document.createElement("label");
        label.className = "structure-field";
        const caption = document.createElement("span");
        caption.textContent = name;
        const input = document.createElement("input");
        input.type = type;
        input.value = String(value ?? "");
        if (minimum !== null) input.min = String(minimum);
        if (maximum !== null) input.max = String(maximum);
        if (step !== null) input.step = String(step);
        /** Apply the edited input value to its structure field.
         * @returns {void}
         */
        const commit = () => {
          if (type === "number") {
            const parsed = input.valueAsNumber;
            if (!Number.isFinite(parsed)) return;
            updateStructureItem(index, name, parsed);
            return;
          }
          updateStructureItem(index, name, input.value);
        };
        input.addEventListener("input", commit);
        input.addEventListener("change", commit);
        label.append(caption);
        if (type === "number") {
          const controls = document.createElement("span");
          controls.className = "number-combo";
          const slider = document.createElement("input");
          slider.type = "range";
          slider.min = input.min;
          slider.max = input.max;
          slider.step = input.step;
          slider.value = input.value;
          slider.setAttribute("aria-label", `${name} slider`);
          input.setAttribute("aria-label", `${name} value`);
          slider.addEventListener("input", () => {
            input.value = slider.value;
            commit();
          });
          input.addEventListener("input", () => {
            slider.value = input.value;
          });
          controls.append(slider, input);
          label.append(controls);
        } else label.append(input);
        row.append(label);
      });
      if (item.type === "marker") {
        const blink = document.createElement("label");
        blink.className = "structure-field-checkbox";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = item.blink !== false;
        const caption = document.createElement("span");
        caption.textContent = "Blink on second";
        checkbox.addEventListener("change", () => {
          updateStructureItem(index, "blink", checkbox.checked);
        });
        blink.append(checkbox, caption);
        row.append(blink);
      }
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "structure-remove";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        const structure = analogClock
          .normalizedStructure()
          .filter(
            (/** @type {unknown} */ _, /** @type {number} */ entryIndex) =>
              entryIndex !== index,
          );
        analogClock.set({
          structure,
        });
        renderStructureEditor();
        renderGroupValues();
      });
      row.append(remove);
      structureEditor.append(row);
    });
};
getElement("import-template").addEventListener("click", () => {
  const template = getElement("template").value.trim();
  if (!template.includes("d")) return;
  analogClock.set({
    structure: analogClock.structureFromTemplate(template),
  });
  renderStructureEditor();
  renderGroupValues();
});
getElement("add-group").addEventListener("click", () => {
  const structure = analogClock.normalizedStructure();
  if (structure.length > 0)
    structure.push({
      type: "marker",
      symbol: ":",
      size: analogClock.settings.dotSize,
      color: analogClock.settings.segmentOnColor,
      offColor: analogClock.settings.segmentOffColor,
      glowColor: analogClock.settings.segmentGlowColor,
      glowSize: analogClock.settings.segmentGlowSize,
      gapBefore: analogClock.settings.groupGap,
      gapAfter: analogClock.settings.groupGap,
      blink: true,
    });
  structure.push({
    type: "group",
    digits: 2,
    digitGap: analogClock.settings.digitGap,
    color: analogClock.settings.segmentOnColor,
    offColor: analogClock.settings.segmentOffColor,
    glowColor: analogClock.settings.segmentGlowColor,
    glowSize: analogClock.settings.segmentGlowSize,
    segmentLength: analogClock.settings.segmentLength,
    segmentThickness: analogClock.settings.segmentThickness,
    segmentGap: analogClock.settings.segmentGap,
    onDuration: analogClock.settings.segmentOnDuration,
    offDuration: analogClock.settings.segmentOffDuration,
    easing: analogClock.settings.transitionEasing,
    matrixColumns: analogClock.settings.matrixColumns,
    matrixDotSize: analogClock.settings.matrixDotSize,
    matrixDotGap: analogClock.settings.matrixDotGap,
  });
  analogClock.set({
    structure,
  });
  renderStructureEditor();
  renderGroupValues();
});
renderStructureEditor();
renderGroupValues();
getElement("rec-visible").addEventListener("change", event => {
  analogClock.set({
    recVisible: controlFromEvent(event).value,
  });
});
getElement("align").addEventListener("change", event => {
  analogClock.set({
    align: controlFromEvent(event).value,
  });
});
getElement("blink-now").addEventListener("click", () => {
  analogClock.blink();
});
getElement("reset-settings").addEventListener("click", () => {
  location.reload();
});
