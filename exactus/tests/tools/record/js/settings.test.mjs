/** Exercise the pure rules behind the Settings page: commands, ports, ratios, IDs and validation. */
import assert from "node:assert/strict";
import test from "node:test";
import {
  describeCheck,
  describeService,
  gcd,
  heightForRatio,
  issuesFor,
  joinCommand,
  parseNumber,
  parsePort,
  reduceRatio,
  slugify,
  splitCommand,
  summary,
} from "../../../../tools/record/studio/web/settings.js";
/** The catalog fields the validator needs, shaped like the backend's. */
const fields = [
  {
    id: "width",
    label: "Width",
    kind: "length",
    unit: "px",
    min: 160,
    max: 8192,
  },
  {
    id: "height",
    label: "Height",
    kind: "length",
    unit: "px",
    min: 160,
    max: 8192,
  },
  {
    id: "scale",
    label: "Resolution",
    kind: "number",
    unit: "dppx",
    min: 0.5,
    max: 4,
  },
  {
    id: "screen_width",
    label: "Device width",
    kind: "length",
    unit: "px",
    min: 160,
    max: 8192,
    optional: true,
  },
  {
    id: "screen_height",
    label: "Device height",
    kind: "length",
    unit: "px",
    min: 160,
    max: 8192,
    optional: true,
  },
];
/** A valid profile to change one field of at a time. */
const profile = () => ({
  id: "phone",
  name: "Phone",
  width: 390,
  height: 844,
  scale: 3,
  screen_width: null,
  screen_height: null,
  touch: true,
  mobile: true,
  media: { "prefers-color-scheme": "dark" },
});
test("commands split like a shell and survive a round trip", () => {
  assert.deepEqual(splitCommand("npm run dev"), ["npm", "run", "dev"]);
  assert.deepEqual(splitCommand('node "my app/server.js" --name="a b"'), [
    "node",
    "my app/server.js",
    "--name=a b",
  ]);
  assert.deepEqual(splitCommand("echo it\\'s"), ["echo", "it's"]);
  assert.deepEqual(splitCommand("a   b"), ["a", "b"]);
  assert.deepEqual(splitCommand(""), []);
  assert.deepEqual(splitCommand('x ""'), ["x", ""]);
  assert.throws(() => splitCommand('echo "oops'), /not closed/);
  for (const args of [
    ["a b", "c"],
    ['q"uote', "x"],
    ["", "y"],
    ["back\\slash"],
  ])
    assert.deepEqual(splitCommand(joinCommand(args)), args);
});
test("ports are whole numbers from 1 to 65535, and empty means unset", () => {
  assert.equal(parsePort(""), null);
  assert.equal(parsePort(" 8080 "), 8080);
  assert.equal(parsePort("65535"), 65535);
  for (const bad of ["0", "65536", "80.5", "abc", "-1"])
    assert.throws(() => parsePort(bad), /1 to 65535/, bad);
});
test("aspect ratio and height stay linked", () => {
  assert.equal(gcd(1440, 900), 180);
  assert.deepEqual(reduceRatio(1440, 900), [8, 5]);
  assert.deepEqual(reduceRatio(390, 844), [195, 422]);
  assert.deepEqual(reduceRatio(0, 5), [1, 1]);
  assert.deepEqual(reduceRatio(1.5, 2), [1, 1]);
  assert.equal(heightForRatio(1440, 16, 9), 810);
  assert.equal(heightForRatio(390, 9, 19), 823);
  assert.equal(heightForRatio(100, 0, 9), 0);
});
test("profile IDs come from the name and never collide or shadow 'shared'", () => {
  assert.equal(slugify("Dark Desktop", []), "dark-desktop");
  assert.equal(slugify("Dark Desktop", ["dark-desktop"]), "dark-desktop-2");
  assert.equal(slugify("  Café  ", []), "cafe");
  assert.equal(slugify("***", []), "profile");
  assert.equal(slugify("shared", []), "shared-2");
  assert.ok(slugify("x".repeat(80), []).length <= 28);
});
test("typed numbers are read without blocking what the user typed", () => {
  assert.equal(parseNumber(" 12 "), 12);
  assert.ok(Number.isNaN(parseNumber("")));
  assert.ok(Number.isNaN(parseNumber("12px")));
});
test("a profile is validated against the catalog, one message per field", () => {
  assert.deepEqual(issuesFor(profile(), fields), {});
  assert.match(
    issuesFor({ ...profile(), name: " " }, fields).name ?? "",
    /name/,
  );
  assert.match(
    issuesFor({ ...profile(), width: 10 }, fields).width ?? "",
    /160 to 8192 px/,
  );
  assert.match(
    issuesFor({ ...profile(), height: Number.NaN }, fields).height ?? "",
    /must be a number/,
  );
  assert.match(
    issuesFor({ ...profile(), width: 400.5 }, fields).width ?? "",
    /whole number/,
  );
  assert.match(
    issuesFor({ ...profile(), scale: 9 }, fields).scale ?? "",
    /0.5 to 4 dppx/,
  );
  // The device screen is both sizes or neither.
  assert.match(
    issuesFor({ ...profile(), screen_width: 800 }, fields).screen_height ?? "",
    /both/,
  );
  assert.deepEqual(
    issuesFor({ ...profile(), screen_width: 800, screen_height: 600 }, fields),
    {},
  );
});
test("summaries and status sentences say what matters", () => {
  assert.equal(summary(profile()), "390 × 844 · 3× · touch · dark");
  assert.equal(
    summary({ ...profile(), scale: 1, touch: false, media: {} }),
    "390 × 844",
  );
  assert.match(
    describeCheck({
      state: "reachable",
      status: 200,
      reason: "OK",
      process: { pid: 7, name: "python" },
    }),
    /Reachable.*200 OK.*python \(process 7\)/,
  );
  assert.match(describeCheck({ state: "unreachable" }), /Nothing is listening/);
  assert.match(
    describeCheck({ state: "unresolved", error: "No host x." }),
    /No host x/,
  );
  assert.equal(describeCheck(null), "");
  assert.equal(describeService(undefined), "Not started.");
  assert.match(describeService({ state: "starting" }), /Starting/);
  assert.match(
    describeService({
      state: "running",
      url: "http://127.0.0.1:5173",
      port: 5173,
      pid: 9,
      candidates: [
        { url: "a", port: 5173, status: 200 },
        { url: "b", port: 24678, status: 200 },
      ],
    }),
    /Running at http:\/\/127\.0\.0\.1:5173 \(process 9\)\. Also listening on 24678/,
  );
  assert.equal(
    describeService({ state: "failed", error: "No such program." }),
    "No such program.",
  );
});
