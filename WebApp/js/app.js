/**
 * SGF Toolkit (web): the interface.
 *
 * The work is split the same way as the desktop app in App/: the panels run
 * explorer -> actions -> tree -> results, and the message bar describes the
 * highlighted action. Everything the app does is done by the library port in
 * the other modules; this file only wires it to the page.
 */

import {
  parseSgfCollection, serialiseGame, nodeMoveLabel, setText,
} from "./sgf.js";
import { renderBoard } from "./board.js";
import {
  getSetupAndMoves, positionAfter, positionForNode, treeNodes,
} from "./moves.js";
import {
  checkGame, cleanGame, convertGameToUtf8, decodeBytes, describeEncoding,
  detectEncoding, formatPointList, transformGame, FLIP_VERTICAL,
  FLIP_HORIZONTAL, ROTATE_CW, ROTATE_ACW,
} from "./tools.js";
import {
  formatVertex, interpretValue, PROPERTY_TYPES,
} from "./properties.js";

// -- what the app can do ---------------------------------------------------

const OPERATIONS = [
  {
    id: "board",
    label: "Show board position",
    prompt: "Move number (blank = final position)",
    help: ["Show the position after a given number of moves.",
           "A move number, or blank for the final position.",
           "Board tab."],
  },
  {
    id: "tree",
    label: "Show tree (click a move)",
    prompt: null,
    help: ["Show the whole game as a tree, variations and all.",
           "Click (or press Enter on) a move to see its position.",
           "Board tab; the tree is on the left."],
  },
  {
    id: "info",
    label: "Show game information",
    prompt: null,
    help: ["Summarise the game: players, result, komi, size.",
           "Info tab."],
  },
  {
    id: "properties",
    label: "List properties in the tree",
    prompt: null,
    help: ["List every node of the tree with its properties.",
           "Info tab."],
  },
  {
    id: "moves",
    label: "List moves",
    prompt: null,
    help: ["List the moves of the main line.",
           "Info tab."],
  },
  {
    id: "check",
    label: "Check for non-standard props",
    prompt: null,
    help: ["Report properties FF[4] does not define for Go.",
           "Info tab."],
  },
  {
    id: "clean",
    label: "Clean non-standard → file",
    prompt: "Output file",
    suffix: "-clean",
    help: ["Remove the properties FF[4] does not define for Go.",
           "A file name to write.", "A download; the file you opened is left alone."],
  },
  {
    id: "to_utf8",
    label: "Convert to UTF-8 → file",
    prompt: "Output file",
    suffix: "-utf8",
    help: ["Rewrite the file as UTF-8, declaring CA[UTF-8].",
           "A file name to write.", "A download."],
  },
  {
    id: "rotate_cw", label: "Turn board 90 clockwise",
    prompt: "Output file", suffix: "-rotate_cw", transform: ROTATE_CW,
    help: ["Turn the board a quarter-turn clockwise.",
           "Choosing it again turns it again, so four times returns to the start.",
           "A preview; Run writes it."],
  },
  {
    id: "rotate_acw", label: "Turn board 90 anticlockwise",
    prompt: "Output file", suffix: "-rotate_acw", transform: ROTATE_ACW,
    help: ["Turn the board a quarter-turn anticlockwise.",
           "Choosing it again turns it again, so four times returns to the start.",
           "A preview; Run writes it."],
  },
  {
    id: "flip_v", label: "Flip board vertically",
    prompt: "Output file", suffix: "-flip_v", transform: FLIP_VERTICAL,
    help: ["Mirror the board left to right.",
           "Choosing it twice returns the board to where it started.",
           "A preview; Run writes it."],
  },
  {
    id: "flip_h", label: "Flip board horizontally",
    prompt: "Output file", suffix: "-flip_h", transform: FLIP_HORIZONTAL,
    help: ["Mirror the board top to bottom.",
           "Choosing it twice returns the board to where it started.",
           "A preview; Run writes it."],
  },
  {
    id: "split",
    label: "Split collection → files",
    prompt: "Base name for the parts",
    suffix: "",
    help: ["Write one file for each game in a collection.",
           "The name to build the parts from.", "Several downloads."],
  },
  {
    id: "save",
    label: "Save back to a file",
    prompt: null,
    help: ["Write the game out again, as UTF-8.",
           "A download of the file you opened."],
  },
];

const TABS = ["board", "info", "moves", "notes"];

// -- state -----------------------------------------------------------------

const state = {
  files: [],              // {name, bytes, detection, text, game, error}
  current: null,
  operation: 0,
  pending: [],            // transformations awaiting Run
  previewAction: null,
  notes: [],
  downloads: [],          // {name, text} for everything written
};

// -- small helpers ---------------------------------------------------------

const $ = (selector) => document.querySelector(selector);

function element(tag, options = {}, children = []) {
  const node = document.createElement(tag);
  if (options.className) node.className = options.className;
  if (options.text != null) node.textContent = options.text;
  if (options.attrs) {
    for (const [key, value] of Object.entries(options.attrs)) {
      node.setAttribute(key, value);
    }
  }
  for (const child of children) {
    node.append(typeof child === "string" ? document.createTextNode(child)
                                         : child);
  }
  return node;
}

function baseName(name) {
  return name.replace(/\.sgf$/i, "");
}

/** The last part of a path, for showing a file that was dragged in. */
function leafName(name) {
  return String(name).split(/[\\/]/).pop();
}

// -- loading files ---------------------------------------------------------

async function loadFiles(fileList) {
  for (const file of fileList) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    loadOne(file.name, bytes);
  }
  renderFileList();
  if (state.files.length > 0) selectFile(state.files.length - 1);
}

function loadOne(name, bytes) {
  const record = { name: leafName(name), bytes, game: null, games: [], error: null };
  try {
    record.detection = detectEncoding(bytes);
    const label = record.detection.encoding === "UTF-8"
      ? "utf-8"
      : record.detection.encoding.toLowerCase();
    record.text = decodeBytes(bytes, label).replace(/^\uFEFF/, "");
    record.games = parseSgfCollection(record.text);
    record.game = record.games[0];
  } catch (error) {
    record.error = error.message;
  }
  state.files.push(record);
  note(`${record.error ? "Could not read" : "Opened"} ${record.name}${
    record.error ? ": " + record.error : ""}`,
  record.error ? "error" : "ok");
}

function renderFileList() {
  const list = $("#files");
  list.replaceChildren();
  for (const [index, record] of state.files.entries()) {
    const item = element("li", {
      text: record.name + (record.error ? "  (unreadable)" : ""),
      attrs: { "aria-selected": record === state.current ? "true" : "false" },
    });
    if (record.error) item.classList.add("bad");
    item.title = record.error || record.name;
    item.addEventListener("click", () => selectFile(index));
    list.append(item);
  }
  if (state.files.length === 0) {
    list.append(element("li", { className: "hint", text: "No files yet" }));
  }
}

function selectFile(index) {
  const record = state.files[index];
  if (!record) return;
  state.current = record;
  state.pending = [];
  state.previewAction = null;
  renderFileList();
  if (record.error) {
    setTargetBar(`${record.name}: ${record.error}`);
    $("#board-view").textContent = "";
    $("#board-caption").textContent = "";
    return;
  }
  setTargetBar(targetDescription(record));
  drawFinalPosition();
  renderFileList();
  note(`Opened ${record.name}`, "ok");
}

function targetDescription(record) {
  const parts = [record.name, `${record.bytes.length} bytes`];
  if (record.detection) {
    parts.push(`SZ ${record.game.getSize()}`);
    parts.push(`${record.games.length} game${record.games.length === 1 ? "" : "s"}`);
    parts.push(record.detection.encoding);
  }
  return parts.join("   ");
}

function setTargetBar(text) {
  $("#target-bar").textContent = text;
  const record = state.current;
  $("#target-summary").textContent = record ? record.name : "";
}

// -- the board -------------------------------------------------------------

function drawFinalPosition() {
  drawPosition(() => positionAfter(state.current.game), captionForFinal());
}

/** The caption above the board: the file, then the position it shows. */
function captionForFinal() {
  const record = state.current;
  const [black, white] = record.game.getRoot().getSetupStones();
  const [, plays] = getSetupAndMoves(record.game);
  const passes = plays.filter(([, point]) => point == null).length;
  const moves = plays.length - passes;
  const stones = black.length + white.length;
  const parts = [`${plays.length} move${plays.length === 1 ? "" : "s"}`];
  if (passes) parts.push(`${passes} pass${passes === 1 ? "" : "es"}`);
  if (moves) parts.push(`${moves} stone${moves === 1 ? "" : "s"} by the moves`);
  if (stones) parts.push(`${stones} setup stone${stones === 1 ? "" : "s"}`);
  return {
    text: `final position: ${parts.join(", ")}`,
    classes: [],
  };
}

/**
 * Draw whatever the given function returns.
 *
 * The function returns {board, stopped, } so the caller decides which position
 * is wanted; the caption says what is being shown.
 */
function drawPosition(getPosition, caption) {
  let result;
  try {
    result = getPosition();
  } catch (error) {
    $("#board-view").textContent = String(error.message || error);
    return;
  }
  if (result.stopped) {
    note("Stopped early: the file contains an illegal move.", "warn");
  }
  $("#board-view").textContent = renderBoard(result.board);
  const captionNode = $("#board-caption");
  captionNode.replaceChildren();
  if (state.current) {
    captionNode.append(element("span", { text: state.current.name }), "   ");
  }
  const span = element("span", { text: caption.text });
  for (const className of caption.classes) span.classList.add(className);
  captionNode.append(span);
  if (caption.note) {
    captionNode.append("   ", element("span", { className: "dim",
                                                text: caption.note }));
  }
  showTab("board");
}

function drawPreview() {
  const pending = state.pending;
  drawPosition(() => {
    const copy = parseSgfCollection(serialiseGame(state.current.game))[0];
    for (const transformation of pending) transformGame(copy, transformation);
    return positionAfter(copy);
  }, {
    text: `PREVIEW: ${describeTransforms(pending)}`,
    classes: ["preview"],
    note: `${pending.length} applied, Run writes it`,
  });
}

/** Describe a run of transformations, collapsing repeats. */
function describeTransforms(pending) {
  const words = pending.map((transformation) => {
    const operation = OPERATIONS.find((o) => o.transform === transformation);
    return operation ? operation.label.replace(/^Flip board /, "")
      .replace(/^Turn board /, "").toLowerCase() : transformation;
  });
  if (words.length === 1) return words[0];
  if (new Set(words).size === 1) return `${words.length} x ${words[0]}`;
  return words.join(" then ");
}

// -- the action list -------------------------------------------------------

function renderOperations() {
  const list = $("#operations");
  list.replaceChildren();
  for (const [index, operation] of OPERATIONS.entries()) {
    const item = element("li", {
      text: operation.label,
      attrs: {
        role: "option",
        "aria-selected": index === state.operation ? "true" : "false",
        "data-index": String(index),
      },
    });
    item.addEventListener("click", () => chooseOperation(index));
    item.addEventListener("mouseenter", () => highlightOperation(index));
    list.append(item);
  }
}

let highlighted = 0;

function highlightOperation(index) {
  highlighted = index;
  for (const item of $("#operations").children) {
    const isThis = Number(item.dataset.index) === index;
    item.setAttribute("aria-selected", isThis ? "true" : "false");
  }
  const operation = OPERATIONS[index];
  updateParameterBox(operation);
  updateMessage(operation);
}

/** Choosing an action is what runs it, and what applies a transformation. */
function chooseOperation(index) {
  highlightOperation(index);
  state.operation = index;
  const operation = OPERATIONS[index];
  if (operation.transform) {
    applyTransform(operation.transform);
    return;
  }
  if (!requireFile()) return;
  if (operation.prompt) {
    $("#param-input").focus();
    return;
  }
  runOperation();
}

function applyTransform(transformation) {
  if (!requireFile()) return;
  if (state.previewAction !== transformation) {
    // A different transformation starts again from the file's board.
    state.pending = [];
    state.previewAction = transformation;
  }
  state.pending.push(transformation);
  drawPreview();
  updateMessage(OPERATIONS.find((o) => o.transform === transformation));
}

function applyAgain() {
  const operation = OPERATIONS[state.operation];
  if (!operation || !operation.transform) {
    note("Choose a flip or a turn first; there is nothing to apply.", "warn");
    return;
  }
  applyTransform(operation.transform);
}

function resetPreview() {
  if (state.pending.length === 0) return;
  state.pending = [];
  state.previewAction = null;
  if (state.current) {
    drawFinalPosition();
    note("Preview reset to the file's position.");
  }
}

function updateParameterBox(operation) {
  const input = $("#param-input");
  const label = $("#param-label");
  if (!operation.prompt || !state.current) {
    label.textContent = "no parameters";
    input.value = "";
    input.disabled = true;
    return;
  }
  label.textContent = `${state.current.name}  ${operation.prompt}`;
  input.disabled = false;
  input.value = suggestedOutput(operation);
}

function suggestedOutput(operation) {
  const entry = state.current || state.files[0];
  const stem = baseName(entry ? entry.name : "game");
  const suffix = operation.suffix || "";
  return `${stem}${suffix}.sgf`;
}

function updateMessage(operation) {
  const target = state.current ? `   [${state.current.name}]` : "";
  const lines = operation.help;
  const text = lines.length > 1
    ? `${lines[0]}   ${lines[1]}${target}   → ${lines[2]}`
    : `${lines[0]}${target}`;
  $("#message").textContent = text;
}

// -- running an action -----------------------------------------------------

function requireFile() {
  if (state.current && !state.current.error) return true;
  note("Choose an .sgf file in the explorer first.", "warn");
  return false;
}

function runOperation() {
  const operation = OPERATIONS[state.operation];
  if (!operation) return;
  if (!requireFile()) return;
  try {
    if (operation.transform) {
      if (state.pending.length === 0) {
        note("Choose this action first, so there is a transformation to save.",
             "warn");
        return;
      }
      writeTransformed();
      return;
    }
    const handlers = {
      board: showBoardAtMove,
      tree: showTree,
      info: showGameInformation,
      properties: showProperties,
      moves: showMoves,
      check: showCheck,
      clean: writeCleaned,
      to_utf8: writeUtf8,
      split: writeSplit,
      save: writeSelf,
    };
    const handler = handlers[operation.id];
    if (handler) handler();
    else note(`Not implemented: ${operation.id}`, "error");
  } catch (error) {
    note(`${operation.label} failed: ${error.message}`, "error");
    showTab("notes");
  }
}

function outputName(operation) {
  const value = $("#param-input").value.trim();
  if (value) return value;
  return suggestedOutput(operation);
}

function currentOperation() {
  return OPERATIONS[state.operation];
}

// -- read-only actions -----------------------------------------------------

function showBoardAtMove() {
  const value = $("#param-input").value.trim();
  const record = state.current;
  const [, plays] = getSetupAndMoves(record.game);
  if (value === "") {
    drawFinalPosition();
    return;
  }
  const index = Number(value);
  if (!Number.isInteger(index) || index < 1 || index > plays.length + 1) {
    note(`Not a move number: ${value} (the game has ${plays.length}).`,
         "warn");
    return;
  }
  // "Before move N" is the position with the first N-1 moves played.
  drawPosition(() => positionAfter(record.game, index - 1), {
    text: `before move ${index}`,
    classes: [],
  });
}

function showTree() {
  const record = state.current;
  const container = $("#tree");
  container.replaceChildren();
  const side = record.game.getSize();

  const addNode = (node, depth, parentElement) => {
    const row = element("div", {
      className: "node" + (nodeLabel(node, side).startsWith("B ") ||
                          nodeLabel(node, side).startsWith("W ") ? "" : " setup"),
      attrs: { role: "treeitem" },
    });
    row.append(element("span", { className: "guide",
                                text: "  ".repeat(depth) + (depth ? "└ " : "") }));
    row.append(element("span", { className: "label", text: nodeLabel(node, side) }));
    row.dataset.index = String(nodeIndex.get(node));
    row.addEventListener("click", () => selectTreeNode(node, row));
    parentElement.append(row);
    for (const child of node.children) addNode(child, depth + 1, parentElement);
  };

  const nodes = treeNodes(record.game.getRoot());
  const nodeIndex = new Map(nodes.map((node, index) => [node, index]));
  addNode(record.game.getRoot(), 0, container);
  note(`Tree: ${nodes.length} nodes. Click a move to see its position.`, "ok");
  showTab("board");
}

function nodeLabel(node, side) {
  const move = nodeMoveLabel(node);
  if (move) return move;
  const identifiers = node.identifiers().sort();
  if (identifiers.length === 0) return "(empty)";
  const interesting = identifiers.filter((id) =>
    !["FF", "GM", "SZ", "CA", "AP", "ST"].includes(id));
  if (interesting.length === 0) {
    return `${identifiers.length} propert${identifiers.length === 1 ? "y" : "ies"}`;
  }
  const shown = interesting.slice(0, 4).join(" ");
  return interesting.length > 4
    ? `${shown} +${interesting.length - 4}` : shown;
}

function selectTreeNode(node, row) {
  for (const other of $("#tree").children) {
    other.setAttribute("aria-selected", other === row ? "true" : "false");
  }
  const side = state.current.game.getSize();
  const { board } = positionForNode(state.current.game, node);
  $("#board-view").textContent = renderBoard(board);
  const label = nodeLabel(node, side);
  const captionNode = $("#board-caption");
  captionNode.replaceChildren();
  captionNode.append(element("span", { text: state.current.name }), "   ",
                     element("span", { className: "preview", text: `at ${label}` }));
  showTab("board");
  note(`Showing the position at ${label}.`);
}

function showGameInformation() {
  const game = state.current.game;
  const root = game.getRoot();
  const rows = [
    ["File", state.current.name],
    ["Encoding", state.current.detection.encoding],
    ["Board size", `${game.getSize()} x ${game.getSize()}`],
    ["Games in file", String(state.current.games.length)],
  ];
  for (const identifier of ["PB", "PW", "BR", "WR", "RE", "KM", "HA", "RU",
                            "DT", "EV", "GN", "OT", "TM", "PC"]) {
    const raw = root.getRaw(identifier);
    if (!raw) continue;
    rows.push([identifier, raw.join(", ")]);
  }
  const nodes = treeNodes(root);
  rows.push(["Nodes", String(nodes.length)]);
  rows.push(["Moves (main line)", String(game.mainLine().length - 1)]);
  $("#info-view").replaceChildren(buildTable(rows, "Game information"));
  showTab("info");
}

function showProperties() {
  const game = state.current.game;
  const side = game.getSize();
  const container = element("div");
  container.append(element("h3", { text: "Properties in the tree" }));
  for (const [index, node] of treeNodes(game.getRoot()).entries()) {
    const heading = nodeMoveLabel(node) || `node ${index}`;
    container.append(element("p", { className: "hint",
                                    text: `${index}. ${heading}` }));
    const rows = node.identifiers().sort().map((identifier) => [
      identifier, describeProperty(identifier, node.getRaw(identifier), side),
    ]);
    if (rows.length === 0) {
      container.append(element("p", { className: "hint", text: "   (no properties)" }));
    } else {
      container.append(buildTable(rows));
    }
  }
  $("#info-view").replaceChildren(container);
  showTab("info");
}

function describeProperty(identifier, values, side) {
  const type = PROPERTY_TYPES[identifier];
  if (type === "pointList" || type === "label" || type === "point") {
    return values.map((value) => {
      if (type === "point") {
        try {
          return formatVertex(interpretValue(identifier, value, side));
        } catch (error) {
          return value;
        }
      }
      return formatPointList(value.replace(/:[^:]*$/, ""), side) +
             (type === "label" ? value.slice(2) : "");
    }).join(", ");
  }
  return values.join(", ");
}

function showMoves() {
  const game = state.current.game;
  const [, plays] = getSetupAndMoves(game);
  const list = element("ol", { className: "list" });
  for (const [colour, point] of plays) {
    list.append(element("li", {
      text: `${colour === "b" ? "Black" : "White"} ${formatVertex(point)}`,
    }));
  }
  const container = element("div");
  container.append(element("h3", { text: `Moves (${plays.length})` }));
  if (plays.length === 0) {
    container.append(element("p", { className: "hint", text: "No moves." }));
  } else {
    container.append(list);
  }
  $("#info-view").replaceChildren(container);
  showTab("info");
}

function showCheck() {
  const report = checkGame(state.current.game);
  const container = element("div");
  if (report.ok) {
    container.append(element("h3", { text: "All properties are standard" }));
    container.append(element("p", {
      className: "hint",
      text: `${report.count()} non-standard properties: none. The file uses only properties FF[4] defines for Go.`,
    }));
  } else {
    container.append(element("h3", {
      text: `${report.count()} non-standard propert${report.count() === 1 ? "y" : "ies"}`,
    }));
    const rows = report.properties().map((identifier) => [
      identifier, `${report.findings.get(identifier).length} node(s)`,
    ]);
    container.append(buildTable(rows, "Not defined by FF[4] for Go"));
    container.append(element("p", {
      className: "hint",
      text: `On ${report.nodeCount()} of ${treeNodes(state.current.game.getRoot()).length} nodes. Clean the file to remove them.`,
    }));
  }
  $("#info-view").replaceChildren(container);
  showTab("info");
  note(report.ok ? "No non-standard properties."
                 : `${report.count()} non-standard properties found.`,
       report.ok ? "ok" : "warn");
}

// -- writing actions -------------------------------------------------------

function writeTransformed() {
  const operation = currentOperation();
  const copy = parseSgfCollection(serialiseGame(state.current.game))[0];
  for (const transformation of state.pending) transformGame(copy, transformation);
  download(outputName(operation), serialiseGame(copy));
  state.pending = [];
  state.previewAction = null;
  drawFinalPosition();
}

function writeCleaned() {
  const operation = currentOperation();
  const copy = parseSgfCollection(serialiseGame(state.current.game))[0];
  const report = cleanGame(copy);
  download(outputName(operation), serialiseGame(copy));
  note(`Cleaned ${state.current.name}: removed ${report.count()} propert${
    report.count() === 1 ? "y" : "ies"}.`, "ok");
}

function writeUtf8() {
  const operation = currentOperation();
  const copy = parseSgfCollection(serialiseGame(state.current.game))[0];
  convertGameToUtf8(copy);
  download(outputName(operation), serialiseGame(copy));
  note(`Wrote ${outputName(operation)} as UTF-8 (CA[UTF-8]).`, "ok");
}

function writeSplit() {
  const operation = currentOperation();
  const games = state.current.games;
  const base = baseName(outputName(operation)) || baseName(state.current.name);
  for (const [index, game] of games.entries()) {
    download(`${base}-${index + 1}.sgf`, serialiseGame(game));
  }
  note(`Split ${state.current.name} into ${games.length} file(s).`, "ok");
}

function writeSelf() {
  download(state.current.name, serialiseGame(state.current.game));
  note(`Wrote ${state.current.name}.`, "ok");
}

/** Hand a file to the browser. In a test there is no DOM download, so only log. */
function download(name, text) {
  state.downloads.push({ name, text });
  note(`Wrote ${name} (${text.length} characters)`, "ok");
  if (typeof URL === "undefined" || !URL.createObjectURL) return;
  const blob = new Blob([text], { type: "application/x-go-sgf;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = element("a", { attrs: { href: url, download: name } });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

// -- the log and tabs ------------------------------------------------------

function note(message, kind = "") {
  state.notes.push({ message, kind });
  const list = $("#notes-view");
  if (!list) return;
  const item = element("li", { text: message });
  if (kind) item.classList.add(kind);
  list.append(item);
  list.scrollTop = list.scrollHeight;
}

function showTab(name) {
  if (!TABS.includes(name)) return;
  for (const button of $("#tabs").children) {
    button.setAttribute("aria-selected",
                        button.dataset.tab === name ? "true" : "false");
  }
  for (const tab of TABS) {
    $(`#panel-${tab}`).classList.toggle("active", tab === name);
  }
}

function buildTable(rows, section = null) {
  const table = element("table", { className: "grid" });
  if (section) {
    const head = element("tr", { className: "section" });
    const th = element("th", { attrs: { colspan: "2" } });
    th.textContent = section;
    head.append(th);
    table.append(head);
  }
  for (const [name, value] of rows) {
    const tr = element("tr");
    tr.append(element("th", { text: name }), element("td", { text: value }));
    table.append(tr);
  }
  return table;
}

// -- resizable panels ------------------------------------------------------

function setUpResizers() {
  for (const handle of document.querySelectorAll(".resizer")) {
    const pane = document.getElementById(handle.dataset.pane);
    handle.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = pane.getBoundingClientRect().width;
      handle.classList.add("dragging");
      document.body.classList.add("dragging");
      const move = (moveEvent) => {
        const width = Math.max(150, Math.min(900,
          startWidth + (moveEvent.clientX - startX)));
        pane.style.setProperty("--pane-width", `${width}px`);
      };
      const up = () => {
        handle.classList.remove("dragging");
        document.body.classList.remove("dragging");
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    });
  }
}

// -- wiring ----------------------------------------------------------------

function bindEvents() {
  $("#file-input").addEventListener("change", (event) => {
    loadFiles(event.target.files);
    event.target.value = "";
  });

  const explorer = $("#explorer");
  for (const type of ["dragenter", "dragover"]) {
    explorer.addEventListener(type, (event) => {
      event.preventDefault();
      explorer.classList.add("drop-target");
    });
  }
  for (const type of ["dragleave", "drop"]) {
    explorer.addEventListener(type, (event) => {
      event.preventDefault();
      explorer.classList.remove("drop-target");
    });
  }
  explorer.addEventListener("drop", (event) => {
    if (event.dataTransfer && event.dataTransfer.files) {
      loadFiles(event.dataTransfer.files);
    }
  });

  $("#run").addEventListener("click", runOperation);
  $("#apply-again").addEventListener("click", applyAgain);
  $("#param-input").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runOperation();
    }
  });

  const list = $("#operations");
  list.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      highlightOperation(Math.min(OPERATIONS.length - 1, highlighted + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      highlightOperation(Math.max(0, highlighted - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      chooseOperation(highlighted);
    }
  });

  for (const button of $("#tabs").children) {
    button.addEventListener("click", () => showTab(button.dataset.tab));
  }

  document.addEventListener("keydown", (event) => {
    if (event.target instanceof HTMLInputElement) return;
    if (event.ctrlKey && event.key.toLowerCase() === "j") {
      event.preventDefault();
      runOperation();
    } else if (event.ctrlKey && event.key.toLowerCase() === "a") {
      event.preventDefault();
      applyAgain();
    } else if (event.key === "Escape") {
      event.preventDefault();
      resetPreview();
    } else if (event.key === "e") {
      $("#explorer").scrollIntoView?.();
      document.querySelector(".file-list li")?.focus?.();
    } else if (event.key === "a") {
      $("#operations").focus();
    } else if (event.key === "t") {
      $("#tree").focus();
    }
  });
}

function start() {
  renderOperations();
  renderFileList();
  setUpResizers();
  bindEvents();
  highlightOperation(0);
  updateMessage(OPERATIONS[0]);
  updateParameterBox(OPERATIONS[0]);
  showTab("board");
}

/**
 * A small hook for the tests, and for embedding the app in another page.
 *
 * The interface never uses it; it exists so that a test (or a host page) can
 * hand the app bytes without going through a file input.
 */
function exposeTestHook() {
  if (typeof window === "undefined") return;
  window.sgfToolkit = {
    state,
    operations: OPERATIONS,
    loadBytes(name, bytes) {
      loadOne(name, bytes instanceof Uint8Array ? bytes
                                                : new Uint8Array(bytes));
      renderFileList();
      selectFile(state.files.length - 1);
      return state.current;
    },
    chooseOperation,
    runOperation,
    applyAgain,
    resetPreview,
    showTab,
    // The text of every file written so far, newest last.
    downloads: () => state.downloads,
  };
}

start();
exposeTestHook();
