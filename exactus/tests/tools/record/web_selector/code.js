/** Position every element that declares its box through data attributes. */
const placeBoxes = () => {
  const boxes = /** @type {NodeListOf<HTMLElement>} */ (
    document.querySelectorAll("[data-left]")
  );
  for (const element of boxes) {
    const { left, top, width, height } = element.dataset;
    Object.assign(element.style, {
      left: `${left}px`,
      top: `${top}px`,
      width: `${width}px`,
      height: `${height}px`,
    });
  }
};
/** Attach an open shadow root with one button to each host element. */
const attachHosts = () => {
  for (const id of ["host", "host2"]) {
    const host = /** @type {HTMLElement} */ (document.getElementById(id));
    host.attachShadow({
      mode: "open",
    }).innerHTML = '<section><button class="inner">Go</button></section>';
  }
};
placeBoxes();
attachHosts();
