/**
 * Differential tests: run the same fixtures through the JavaScript port and
 * compare with the answers generated from the Python library.
 *
 *     node WebApp/tests/engine_test.mjs
 *
 * Regenerate the expectations after changing either side:
 *
 *     python WebApp/tests/generate_expected.py
 */

import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  parseSgfCollection, parseSgfGame, serialiseGame, nodeMoveLabel,
} from "../js/sgf.js";
import { renderBoard } from "../js/board.js";
import { getSetupAndMoves, positionAfter, positionForNode,
         treeNodes } from "../js/moves.js";
import {
  checkGame, cleanGame, detectEncoding, decodeBytes, convertGameToUtf8,
  transformGame, FLIP_VERTICAL, FLIP_HORIZONTAL, ROTATE_CW, ROTATE_ACW,
} from "../js/tools.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURES = join(HERE, "fixtures");

let passed = 0;
const failures = [];

function check(name, actual, expected) {
  const a = canonical(actual);
  const e = canonical(expected);
  if (a === e) {
    passed++;
    return;
  }
  failures.push({ name, actual: a, expected: e });
}

/** JSON with sorted keys, so that object key order cannot cause a mismatch. */
function canonical(value) {
  return JSON.stringify(sortKeys(value));
}

function sortKeys(value) {
  if (Array.isArray(value)) return value.map(sortKeys);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort()
      .map((key) => [key, sortKeys(value[key])]));
  }
  return value;
}

function readBytes(name) {
  return new Uint8Array(readFileSync(join(FIXTURES, name)));
}

/** Points as sorted "row,col" strings, matching the Python generator. */
function pointKeys(points) {
  return points.filter(Boolean)
    .map(([row, col]) => `${row},${col}`).sort();
}

/** Read a file the way the app does: detect, decode, parse. */
function openGame(bytes) {
  const detection = detectEncoding(bytes);
  const text = decodeBytes(bytes, detection.encoding === "UTF-8"
    ? "utf-8" : detection.encoding);
  return { detection, text, game: parseSgfGame(text.replace(/^\uFEFF/, "")) };
}

const TRANSFORMS = {
  flip_vertical: FLIP_VERTICAL,
  flip_horizontal: FLIP_HORIZONTAL,
  rotate_cw: ROTATE_CW,
  rotate_acw: ROTATE_ACW,
};

function main() {
  const expected = JSON.parse(readFileSync(join(HERE, "expected.json"), "utf8"));

  // -- games -------------------------------------------------------------
  for (const [name, want] of Object.entries(expected.games)) {
    const bytes = readBytes(name);
    const { game } = openGame(bytes);

    check(`${name}: size`, game.getSize(), want.size);
    check(`${name}: serialise`, serialiseGame(game), want.serialise);

    let nodeCount = 0;
    const walk = (node) => {
      nodeCount++;
      node.children.forEach(walk);
    };
    walk(game.getRoot());
    check(`${name}: node count`, nodeCount, want.nodeCount);

    const [, plays] = getSetupAndMoves(game);
    check(`${name}: plays`,
          plays.map(([colour, point]) => [colour, point]), want.plays);

    const [black, white, empty] = game.getRoot().getSetupStones();
    check(`${name}: setup`, {
      black: pointKeys(black), white: pointKeys(white), empty: pointKeys(empty),
    }, want.setup);

    // The position after each move, which is what the board pane draws.
    for (let limit = 0; limit <= plays.length; limit++) {
      const { board } = positionAfter(game, limit);
      check(`${name}: position after ${limit}`,
            { black: pointKeys(board.listStones("b")),
              white: pointKeys(board.listStones("w")) },
            want.positions[limit]);
    }

    // Normalising.
    const report = checkGame(game);
    check(`${name}: check properties`, report.properties(),
          want.check.properties);
    check(`${name}: check node count`, report.nodeCount(),
          want.check.nodeCount);

    // Every node's position, which is what clicking in the tree shows.
    for (const [index, node] of treeNodes(game.getRoot()).entries()) {
      const { board: atNode } = positionForNode(game, node);
      check(`${name}: node ${index} position`,
            { black: pointKeys(atNode.listStones("b")),
              white: pointKeys(atNode.listStones("w")) },
            want.nodePositions[index]);
    }

    const cleaned = parseSgfGame(serialiseGame(game));
    cleanGame(cleaned);
    check(`${name}: clean serialise`, serialiseGame(cleaned),
          want.clean.serialise);

    // Transformations, each from a fresh parse.
    for (const [label, transformation] of Object.entries(TRANSFORMS)) {
      const copy = parseSgfGame(serialiseGame(game));
      transformGame(copy, transformation);
      check(`${name}: ${label}`, serialiseGame(copy), want.transforms[label]);
    }

    // The board diagram must match the Python renderer character for
    // character: the two front ends show the same picture.
    const { board: finalBoard } = positionAfter(game);
    check(`${name}: diagram`, renderBoard(finalBoard), want.diagram);
  }

  // -- encodings ---------------------------------------------------------
  for (const [name, want] of Object.entries(expected.encodings)) {
    const detected = detectEncoding(readBytes(name));
    check(`${name}: encoding`, detected.encoding, want.encoding);
    check(`${name}: declared`, detected.declared, want.declared);
    check(`${name}: mismatch`, detected.mismatch, want.mismatch);
    check(`${name}: asciiOnly`, detected.asciiOnly, want.asciiOnly);
  }

  // -- collection splitting ---------------------------------------------
  const collection = parseSgfCollection(
    new TextDecoder("utf-8").decode(readBytes("collection.sgf")));
  check("collection: game count", collection.length, 2);
  check("collection: second is shorter", collection[1].mainLine().length, 3);

  // -- a few things the fixtures do not cover ----------------------------
  // A pass is written as the FF[4] empty value, never as 'tt'.
  const passGame = parseSgfGame("(;FF[4]GM[1]SZ[9];B[];W[tt])");
  const [, passPlays] = getSetupAndMoves(passGame);
  check("passes read as passes", passPlays, [["b", null], ["w", null]]);
  check("passes serialise as empty", serialiseGame(passGame),
        "(;FF[4]GM[1]SZ[9];B[];W[tt])\n");

  // A legacy 'tt' pass becomes an empty value once transformed.
  const ttGame = parseSgfGame("(;FF[4]GM[1]SZ[9];B[tt])");
  transformGame(ttGame, FLIP_VERTICAL);
  check("'tt' pass stays a pass", serialiseGame(ttGame),
        "(;FF[4]GM[1]SZ[9];B[])\n");

  // Tree labels.
  const treeGame = parseSgfGame("(;FF[4]GM[1]SZ[9];B[cg];W[])");
  const labels = treeGame.mainLine().map((node) => nodeMoveLabel(node));
  check("tree labels", labels, [null, "B C3", "W pass"]);

  // Turning a board four times comes back to where it started.
  const spin = parseSgfGame(serialiseGame(treeGame));
  for (let i = 0; i < 4; i++) transformGame(spin, ROTATE_CW);
  check("four turns are the identity", serialiseGame(spin),
        serialiseGame(treeGame));

  // Converting declares UTF-8.
  const latin = openGame(readBytes("enc-latin1-declared.sgf"));
  convertGameToUtf8(latin.game);
  check("convert sets CA[UTF-8]", latin.game.getRoot().getRaw("CA"),
        ["UTF-8"]);

  // Every fixture that is a valid game parses and draws.
  const readable = readdirSync(FIXTURES).filter((f) => f.endsWith(".sgf"));
  check("fixture count", readable.length > 10, true);

  report();
}

function report() {
  for (const failure of failures) {
    console.log(`FAIL ${failure.name}`);
    console.log(`  expected: ${failure.expected}`);
    console.log(`  actual  : ${failure.actual}`);
  }
  console.log(`\n${passed} checks passed, ${failures.length} failed`);
  if (failures.length > 0) process.exitCode = 1;
}

main();
