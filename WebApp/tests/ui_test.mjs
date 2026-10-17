/**
 * Interface tests: load the real page in a DOM and drive it.
 *
 *     node WebApp/tests/ui_test.mjs
 *
 * jsdom is a development dependency only; the app itself ships with no
 * dependencies. If jsdom is not installed these tests report that and stop.
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
  console.log("jsdom is not installed; skipping the interface tests.");
  console.log("  npm install --cache .tmp/npm-cache jsdom");
  process.exit(0);
}

// -- set up the page -------------------------------------------------------

const html = readFileSync(join(ROOT, "index.html"), "utf8");
const dom = new JSDOM(html, { runScripts: "outside-only", url: "http://localhost/" });

// The app expects a browser; give it the pieces it uses. URL.createObjectURL
// is deliberately absent, which is how the app knows not to try a download.
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLInputElement = dom.window.HTMLInputElement;
globalThis.KeyboardEvent = dom.window.KeyboardEvent;
globalThis.Blob = dom.window.Blob;
globalThis.URL = dom.window.URL;

const app = await import("../js/app.js");
const ui = dom.window.sgfToolkit;

// -- tiny test harness -----------------------------------------------------

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
        `${JSON.stringify(needle)} not found in ${JSON.stringify(String(haystack).slice(0, 300))}`);
}

const $ = (selector) => dom.window.document.querySelector(selector);
const $$ = (selector) => [...dom.window.document.querySelectorAll(selector)];
const text = (selector) => $(selector)?.textContent ?? "";

function fixture(name) {
  return new Uint8Array(readFileSync(join(HERE, "fixtures", name)));
}

function click(selector) {
  const node = $(selector);
  if (!node) throw new Error(`no such element: ${selector}`);
  node.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
}

// -- the page is wired up --------------------------------------------------

equal("all fourteen actions are listed", $$("#operations li").length, 14);
equal("four tabs", $$("#tabs button").length, 4);
equal("four panels plus three resizers", $$(".pane").length, 4);
equal("three resizers", $$(".resizer").length, 3);
contains("message bar describes the first action", text("#message"),
         "Show the position");
equal("board tab is showing", $("#panel-board").classList.contains("active"), true);

// -- loading a file --------------------------------------------------------

ui.loadBytes("simple.sgf", fixture("simple.sgf"));
const record = ui.state.current;
equal("the file loaded without error", record.error, null);
equal("board size read", record.game.getSize(), 9);
contains("target bar describes the file", text("#target-bar"), "simple.sgf");
contains("target bar shows the encoding", text("#target-bar"), "UTF-8");

// The three stones of simple.sgf: B C3, W G7, B G3.
const board = text("#board-view");
contains("board shows black at C3", board, "3  .  .  #  .  .  .  #  .  .");
contains("board shows white at G7", board, "7  .  .  .  .  .  .  o  .  .");
equal("three stones on the board", (board.match(/[#o]/g) || []).length, 3);
contains("the caption counts the moves", text("#board-caption"), "3 moves");
contains("the caption says it is the final position", text("#board-caption"),
         "final position");
equal("the file list has one entry", $$(".file-list li").length, 1);

// -- the board at a move ---------------------------------------------------

ui.chooseOperation(0);            // Show board position
$("#param-input").value = "1";    // before move 1: nothing played yet
ui.runOperation();
contains("before move 1 shows an empty board", text("#board-view"),
         "3  .  .  .  .  .  .  .  .  .");
contains("the caption says which move", text("#board-caption"), "before move 1");

$("#param-input").value = "3";    // before move 3: only the first two played
ui.runOperation();
contains("before move 3 shows the first two stones", text("#board-view"),
         "3  .  .  #  .  .  .  .  .  .");
contains("and the white stone of move 2", text("#board-view"),
         "7  .  .  .  .  .  .  o  .  .");
equal("but not the third move's stone", 
      (text("#board-view").match(/[#o]/g) || []).length, 2);

$("#param-input").value = "99";
ui.runOperation();
contains("an out-of-range move is refused", text("#notes-view"), "Not a move number");

// -- the game tree ---------------------------------------------------------

ui.state.files = [];
ui.loadBytes("variations.sgf", fixture("variations.sgf"));
ui.chooseOperation(1);            // Show tree
ui.runOperation();
const treeRows = $$("#tree .node");
// variations.sgf: root, B C3, W G7, B G3, then the second variation's
// W C7 and B G3, then W E6 -- seven nodes in all.
equal("tree lists every node", treeRows.length, 7);
contains("tree labels the first move", treeRows[1].textContent, "B C3");

// Clicking a node shows that position. Entry 4 is the W C7 move that begins
// the second variation.
treeRows[4].dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
contains("clicking a node captions its position", text("#board-caption"),
         "at W C7");

// A variation's position is not the main line's: after B C3 and W C7 there are
// two stones, and no white stone at G7 as the main line would have.
const variationBoard = text("#board-view");
const stones = (variationBoard.match(/[#o]/g) || []).length;
equal("two stones in that variation", stones, 2);
contains("the variation's white stone is at C7", variationBoard,
         "7  .  .  o  .  .  .  .  .  .");

// -- non-standard properties ----------------------------------------------

ui.loadBytes("nonstandard.sgf", fixture("nonstandard.sgf"));
ui.chooseOperation(5);            // Check for non-standard props
ui.runOperation();
const checkText = text("#info-view");
contains("the check names MULTIGOGM", checkText, "MULTIGOGM");
contains("the check names XX", checkText, "XX");
contains("the check counts them", checkText, "4 non-standard properties");

// -- cleaning and writing --------------------------------------------------

ui.chooseOperation(6);            // Clean non-standard -> file
equal("the clean action has a parameter", $("#param-input").disabled, false);
contains("it suggests a name", $("#param-input").value, "nonstandard-clean.sgf");
ui.runOperation();
const written = ui.downloads().at(-1);
equal("a file was written", written.name, "nonstandard-clean.sgf");
check("the cleaned file keeps FF[4]", written.text.includes("FF[4]"));
check("the cleaned file drops MULTIGOGM", !written.text.includes("MULTIGOGM"));
check("the cleaned file drops XX", !written.text.includes("XX"));
check("the cleaned file keeps the moves", written.text.includes(";B[cg]"));

// -- transformations -------------------------------------------------------

ui.state.downloads.length = 0;
ui.loadBytes("simple.sgf", fixture("simple.sgf"));
const finalBoard = text("#board-view");

ui.chooseOperation(10);           // Flip board vertically
contains("choosing a flip previews it", text("#board-caption"), "PREVIEW");
contains("the preview says how many", text("#board-caption"), "1 applied");
equal("one flip pending", ui.state.pending.length, 1);
check("the flipped board differs", text("#board-view") !== finalBoard);

ui.chooseOperation(10);           // again: flip back
equal("choosing it again applies again", ui.state.pending.length, 2);
equal("two flips return to the original board", text("#board-view"), finalBoard);

ui.chooseOperation(10);           // a third time
equal("a third choice applies again", ui.state.pending.length, 3);
check("three flips differ again", text("#board-view") !== finalBoard);

ui.resetPreview();
equal("Escape resets the preview", ui.state.pending.length, 0);
equal("and the board is back", text("#board-view"), finalBoard);

// Turning four times comes round.
ui.chooseOperation(8);            // Turn board 90 clockwise
ui.applyAgain();
ui.applyAgain();
ui.applyAgain();
equal("four turns pending", ui.state.pending.length, 4);
equal("four turns return to the original", text("#board-view"), finalBoard);

// Run writes what is on screen and clears the preview.
ui.runOperation();
const turned = ui.downloads().at(-1);
equal("the turn wrote a file", turned.name, "simple-rotate_cw.sgf");
equal("the preview is cleared after writing", ui.state.pending.length, 0);
equal("a full cycle saves the original", turned.text.includes(";B[cg]"), true);

// -- splitting a collection ------------------------------------------------

ui.state.downloads.length = 0;
ui.loadBytes("collection.sgf", fixture("collection.sgf"));
ui.chooseOperation(12);           // Split collection
ui.runOperation();
const parts = ui.downloads();
equal("one file per game", parts.length, 2);
contains("the first part is named", parts[0].name, "-1.sgf");
contains("the second part holds the second game", parts[1].text, "GN[second]");

// -- encoding --------------------------------------------------------------

ui.loadBytes("enc-mismatch.sgf", fixture("enc-mismatch.sgf"));
contains("the mismatch is reported in the target bar", text("#target-bar"), "ISO-8859-1");
ui.chooseOperation(7);            // Convert to UTF-8
ui.runOperation();
const converted = ui.downloads().at(-1);
contains("the conversion declares UTF-8", converted.text, "CA[UTF-8]");
contains("and keeps the name suggestion", converted.name, "enc-mismatch-utf8.sgf");

// -- the notes log ---------------------------------------------------------

check("the log recorded what happened", $$("#notes-view li").length > 5);
equal("no failures were logged", $$("#notes-view li.error").length, 0);

// -- report ----------------------------------------------------------------

for (const failure of failures) console.log(`FAIL ${failure}`);
console.log(`\n${passed} interface checks passed, ${failures.length} failed`);
if (failures.length > 0) process.exitCode = 1;
