[Home](Home.md) > [Packages](Packages.md) > scene_description

# scene_description/

Rendered semantic scene descriptions and Visual Cause integration: captures
a semantic scene graph from a rendered page, describes deterministic A/B
differences between two scenes in human-readable language, and enriches an
existing Visual Cause report with those descriptions. Report-independent —
nothing here imports `exactus.tools`.

Run standalone with `python -m exactus.packages.scene_description <report> <scene-a> <scene-b> -o <output>`.

## Boundaries

`SceneDescriptor` talks to the browser only through the narrow `PageLike`
protocol (`add_script_tag`, `evaluate`), so tests drive it with in-memory
fakes and Playwright covers it end to end. `describe()` installs the runtime
on demand and returns the manifest verbatim.

`SceneChangeDescriber` matches elements across scenes by `selector` (or the
`visualCauseSelector` alias) and applies a geometry tolerance so sub-pixel
noise produces no output. All comparisons are deterministic: selector order
is sorted and every detail line is derived from stable fields.

`VisualCauseDescriber.enrich()` never mutates the input report — it returns a
deep copy with a `change_description` block, per-node `visual_description`
entries for matched change trees, and a summary sentence.

---

| Source | Tests | Full reference |
|---|---|---|
| [`exactus/packages/scene_description/`](../exactus/packages/scene_description/) | [`exactus/tests/packages/scene_description/`](../exactus/tests/packages/scene_description/) | [`DOCS.md`](../exactus/docs/packages/scene_description/DOCS.md) |

[< Packages-rename_project](Packages-rename_project.md) · [Packages index](Packages.md) · [Packages-screenshot >](Packages-screenshot.md)
