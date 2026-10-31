import { mountPointerStudio } from "../../index.js";
const form = document.querySelector("#pointer-demo");
const host = document.querySelector("#pointer-host");
const preview = document.querySelector("#preview");
const reset = document.querySelector("#reset");
const activity = document.querySelector("#activity");
if (!(form instanceof HTMLFormElement) || !(host instanceof HTMLElement) || !(preview instanceof HTMLElement) || !(reset instanceof HTMLButtonElement) || !(activity instanceof HTMLOutputElement)) throw new Error("The pointer demo markup is incomplete.");
const seed = Object.freeze({ pointer_action: "click", selector: "#primary-target" });
mountPointerStudio(host, seed);
/** Show the form values exactly as the Studio adapter receives them. */
const renderPreview = () => {
  const values = Object.fromEntries(new FormData(form).entries());
  preview.textContent = JSON.stringify(values, null, 2);
};
form.addEventListener("submit", event => {
  event.preventDefault();
  renderPreview();
});
form.addEventListener("input", renderPreview);
form.addEventListener("change", renderPreview);
reset.addEventListener("click", () => {
  mountPointerStudio(host, seed);
  renderPreview();
});
for (const target of document.querySelectorAll("#primary-target, #drag-source, #drop-zone, #scroll-target")) {
  target.addEventListener("pointerenter", () => {
    activity.value = `Pointer entered ${target.id}.`;
  });
  target.addEventListener("click", () => {
    activity.value = `Clicked ${target.id}.`;
  });
}
const source = document.querySelector("#drag-source");
const destination = document.querySelector("#drop-zone");
source?.addEventListener("dragstart", event => {
  if (event instanceof DragEvent) event.dataTransfer?.setData("text/plain", "drag-source");
});
destination?.addEventListener("dragover", event => event.preventDefault());
destination?.addEventListener("drop", event => {
  event.preventDefault();
  activity.value = "Dropped drag-source on drop-zone.";
});
renderPreview();
