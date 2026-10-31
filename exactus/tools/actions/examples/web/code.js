const save = document.getElementById("save");
const result = document.getElementById("result");
if (save && result)
  save.addEventListener("click", () => {
    result.textContent = "Saved";
  });
