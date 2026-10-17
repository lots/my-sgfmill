/**
 * Test standalone.html: the whole app in one file, which is what a browser
 * loads when it is opened from disk.
 *
 *     node WebApp/tests/standalone_test.mjs
 *
 * Two things are checked: that the generated file is up to date with the
 * modular sources, and that it actually runs -- loaded from the filesystem with
 * no server, exactly as a double-click would.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");

let JSDOM;
try {
  ({ JSDOM } = await import("jsdom"));
} catch (error) {
  console.log("jsdom is not installed; skipping the standalone tests.");
  process.exit(0);
}

let passed = 0;
const failures = [];
function check(name, condition, detail = "") {
  if (condition) {
    passed++;
    return;
  }
  failures.push(`${name}${detail ? `\n    ${detail}` : ""}`);
}
function equal(name, actual, expected) {
  check(name, actual === expected,
        `expected ${JSON.stringify(expected)}\n    actual   ${JSON.stringify(actual)}`);
}
function contains(name, haystack, needle) {
  check(name, String(haystack).includes(needle),
        `${JSON.stringify(needle)} not found in ${JSON.stringify(String(haystack).slice(0, 200))}`);
}

// -- the file is up to date ------------------------------------------------

const { buildPage } = await import("../build_standalone.mjs");
const onDisk = readFileSync(join(ROOT, "standalone.html"), "utf8");
const rebuilt = buildPage();
check("standalone.html is up to date with js/", onDisk === rebuilt,
      "rebuild it with: node WebApp/build_standalone.mjs");

// -- it loads and runs, with no server ------------------------------------

const dom = new JSDOM(onDisk, {
  runScripts: "dangerously",       // a normal page, as opened from disk
  url: "file:///C:/WebApp/standalone.html",
  pretendToBeVisual: true,
  // jsdom does not provide TextDecoder, which every browser has had for years;
  // the app decodes files with it, so hand it Node's copy before the page's
  // own script runs.
  beforeParse(window) {
    window.TextDecoder = TextDecoder;
    window.TextEncoder = TextEncoder;
  },
});
const w = dom.window;

// The app registers window.sgfToolkit when its start-up succeeds.
await new Promise((resolve) => setTimeout(resolve, 600));
check("the app started", Boolean(w.sgfToolkit),
      w.document.getElementById("boot-error-detail")?.textContent || "");
equal("the could-not-start banner is hidden",
      w.document.getElementById("boot-error").hidden, true);

const ui = w.sgfToolkit;
equal("all fourteen actions are listed",
      w.document.querySelectorAll("#operations li").length, 14);
equal("four panels", w.document.querySelectorAll(".pane").length, 4);

// Load a file through the app and check the board it draws.
const bytes = new Uint8Array(readFileSync(join(HERE, "fixtures", "simple.sgf")));
ui.loadBytes("simple.sgf", bytes);
equal("the file loaded without error", ui.state.current.error, null);
equal("board size read", ui.state.current.game.getSize(), 9);
const board = w.document.querySelector("#board-view").textContent;
contains("board shows black at C3", board, "3  .  .  #  .  .  .  #  .  .");
contains("board shows white at G7", board, "7  .  .  .  .  .  .  o  .  .");
contains("the caption counts the moves",
         w.document.querySelector("#board-caption").textContent, "3 moves");

// A transformation, chosen twice, returns to the original.
const original = board;
ui.chooseOperation(10);           // Flip board vertically
contains("a flip previews", w.document.querySelector("#board-caption").textContent,
         "PREVIEW");
ui.chooseOperation(10);
equal("two flips return to the original board",
      w.document.querySelector("#board-view").textContent, original);

// The tree, and writing a file.
ui.chooseOperation(1);            // Show tree
ui.runOperation();
const rows = w.document.querySelectorAll("#tree .node").length;
check("the tree is built", rows >= 3, `rows: ${rows}`);

ui.loadBytes("nonstandard.sgf",
             new Uint8Array(readFileSync(join(HERE, "fixtures", "nonstandard.sgf"))));
ui.chooseOperation(6);            // Clean non-standard
ui.runOperation();
const written = ui.downloads().at(-1);
check("cleaning wrote a file", Boolean(written), "nothing was written");
check("the cleaned text drops MULTIGOGM", !written.text.includes("MULTIGOGM"));
check("and keeps the moves", written.text.includes(";B[cg]"));

// -- report ----------------------------------------------------------------

for (const failure of failures) console.log(`FAIL ${failure}`);
console.log(`\n${passed} standalone checks passed, ${failures.length} failed`);
if (failures.length > 0) process.exitCode = 1;
