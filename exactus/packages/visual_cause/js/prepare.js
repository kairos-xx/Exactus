() => {
  document.querySelectorAll('link[rel="stylesheet"], style').forEach(node => {
    if (node.id !== "__css_cause_style__") node.remove();
  });
  document.querySelectorAll("video").forEach(video => {
    video.pause();
  });
  const style = document.createElement("style");
  style.id = "__css_cause_style__";
  document.head.append(style);
  return "ok";
};
