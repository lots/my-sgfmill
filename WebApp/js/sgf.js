/**
 * SGF FF[4] game tree: parsing and serialisation.
 *
 * Mirrors sgfmill.sgf closely enough that the web app and the Python library
 * agree on what a file contains and on the bytes written back out. The
 * differential tests in tests/ compare the two.
 */

import {
  formatVertex, interpretGoPoint, interpretPointList, escapeText, MAX_SIZE,
  SgfError,
} from "./properties.js";

export { SgfError };

/** One node of a game tree. */
export class SgfNode {
  constructor(game) {
    this.game = game;
    // Identifier -> array of raw (still escaped) string values.
    this._properties = new Map();
    this.parent = null;
    this.children = [];
  }

  /** Raw values for an identifier, or undefined. */
  getRaw(identifier) {
    return this._properties.get(identifier);
  }

  getRawMap() {
    return this._properties;
  }

  has(identifier) {
    return this._properties.has(identifier);
  }

  identifiers() {
    return [...this._properties.keys()];
  }

  setRaw(identifier, values) {
    this._properties.set(identifier, values.map(String));
  }

  set(identifier, value) {
    if (value == null) {
      this._properties.delete(identifier);
      return;
    }
    this.setRaw(identifier, Array.isArray(value) ? value : [value]);
  }

  /** The move this node makes, as [colour, rawPoint], or [null, null]. */
  getRawMove() {
    if (this._properties.has("B")) return ["b", this._properties.get("B")[0]];
    if (this._properties.has("W")) return ["w", this._properties.get("W")[0]];
    return [null, null];
  }

  getMove() {
    const [colour, raw] = this.getRawMove();
    if (colour == null) return [null, null];
    return [colour, interpretGoPoint(raw, this.game.getSize())];
  }

  /** Setup stones: [black, white, empty] as arrays of points.
   *
   * Compressed point lists ("aa:cc") and duplicates are handled by
   * interpretPointList, as sgfmill handles them.
   */
  getSetupStones() {
    const size = this.game.getSize();
    const read = (identifier) =>
      interpretPointList(this._properties.get(identifier) || [], size);
    return [read("AB"), read("AW"), read("AE")];
  }

  /** Iterate over the children (the variations from this node). */
  *[Symbol.iterator]() {
    yield* this.children;
  }
}

/** A parsed game: a root node, its tree, and the properties that shape it. */
export class SgfGame {
  constructor(root) {
    this.root = root;
  }

  getRoot() {
    return this.root;
  }

  getSize() {
    const raw = this.root.getRaw("SZ");
    if (!raw) return 19;
    const value = raw[0];
    if (value.includes(":")) throw new SgfError("bad SZ property");
    const size = Number(value);
    if (!Number.isInteger(size) || size < 1 || size > MAX_SIZE) {
      throw new SgfError("bad SZ property");
    }
    return size;
  }

  /** The main line: the leftmost variation, as an array of nodes. */
  mainLine() {
    const nodes = [this.root];
    let node = this.root;
    while (node.children.length > 0) {
      node = node.children[0];
      nodes.push(node);
    }
    return nodes;
  }

  /** Append a node to the end of the main line. */
  extendMainSequence() {
    const line = this.mainLine();
    const node = new SgfNode(this);
    node.parent = line[line.length - 1];
    node.parent.children.push(node);
    return node;
  }

  serialise(wrap = 79) {
    return serialiseGame(this, wrap);
  }
}

// -- parsing ---------------------------------------------------------------

/**
 * Parse one or more games from SGF text.
 *
 * Returns an array of SgfGame. A collection may hold several games.
 */
export function parseSgfCollection(text) {
  const parser = new Parser(text);
  const games = parser.parseCollection();
  if (games.length === 0) throw new SgfError("no games found");
  return games;
}

export function parseSgfGame(text) {
  return parseSgfCollection(text)[0];
}

class Parser {
  constructor(text) {
    this.text = text;
    this.position = 0;
  }

  error(message) {
    throw new SgfError(`${message} at offset ${this.position}`);
  }

  skipWhitespace() {
    while (this.position < this.text.length) {
      if (!/\s/.test(this.text[this.position])) return;
      this.position++;
    }
  }

  parseCollection() {
    const games = [];
    for (;;) {
      this.skipWhitespace();
      if (this.position >= this.text.length) break;
      games.push(this.parseGame());
    }
    return games;
  }

  parseGame() {
    this.expect("(");
    const game = new SgfGame(null);
    const stack = [];       // nodes whose children are being collected
    let current = null;

    for (;;) {
      this.skipWhitespace();
      const ch = this.text[this.position];
      if (ch === undefined) this.error("unterminated game");
      if (ch === ";") {
        this.position++;
        const node = this.parseNode(game);
        if (current === null) {
          if (game.root !== null) this.error("two roots");
          game.root = node;
        } else {
          node.parent = current;
          current.children.push(node);
        }
        current = node;
      } else if (ch === "(") {
        if (current === null) this.error("variation before any node");
        this.position++;
        stack.push(current);
      } else if (ch === ")") {
        this.position++;
        if (stack.length > 0) {
          current = stack.pop();
        } else {
          break;
        }
      } else {
        this.error(`unexpected ${JSON.stringify(ch)}`);
      }
    }
    if (game.root === null) this.error("game has no nodes");
    return game;
  }

  parseNode(game) {
    const node = new SgfNode(game);
    for (;;) {
      this.skipWhitespace();
      const ch = this.text[this.position];
      if (ch === undefined) this.error("unterminated node");
      if (ch === ";" || ch === "(" || ch === ")") break;
      const identifier = this.parseIdentifier();
      const values = [];
      for (;;) {
        this.skipWhitespace();
        if (this.text[this.position] !== "[") break;
        values.push(this.parseValue());
      }
      if (values.length === 0) this.error(`${identifier} has no value`);
      node.setRaw(identifier, values);
    }
    return node;
  }

  parseIdentifier() {
    const start = this.position;
    while (this.position < this.text.length &&
           /[A-Za-z]/.test(this.text[this.position])) {
      this.position++;
    }
    if (this.position === start) this.error("expected a property identifier");
    // FF[4] identifiers are upper case; accept lower case as well, since real
    // files contain both, and normalise so the rest of the code can assume it.
    return this.text.slice(start, this.position).toUpperCase();
  }

  parseValue() {
    this.expect("[");
    let raw = "";
    for (;;) {
      if (this.position >= this.text.length) this.error("unterminated value");
      const ch = this.text[this.position];
      if (ch === "\\") {
        // Keep the escape in the raw value; interpretation removes it.
        raw += ch;
        this.position++;
        if (this.position < this.text.length) {
          raw += this.text[this.position++];
        }
        continue;
      }
      this.position++;
      if (ch === "]") return raw;
      raw += ch;
    }
  }

  expect(ch) {
    this.skipWhitespace();
    if (this.text[this.position] !== ch) {
      this.error(`expected ${JSON.stringify(ch)}`);
    }
    this.position++;
  }
}

// -- serialisation ---------------------------------------------------------

/**
 * Build the "coarse tree" sgfmill serialises from.
 *
 * A run of nodes that each have a single child is one sequence; a node with
 * several children is where the variations start. That is what makes a simple
 * game come out as "(;root;move;move)" and a branching one as
 * "(;root;B(x)(y))".
 */
function coarseTree(node) {
  const sequence = [node];
  let current = node;
  while (current.children.length === 1) {
    current = current.children[0];
    sequence.push(current);
  }
  return { sequence, children: current.children.map(coarseTree) };
}

/** Sorted for serialisation: FF first (as sgfmill does), then alphabetical. */
function compareIdentifiers(a, b) {
  if (a === "FF") return -1;
  if (b === "FF") return 1;
  return a < b ? -1 : a > b ? 1 : 0;
}

function blockFormat(pieces, width = 79) {
  const encoder = new TextEncoder();
  const lines = [];
  let line = "";
  let length = 0;
  for (const piece of pieces) {
    const size = encoder.encode(piece).length;
    if (length + size > width) {
      lines.push(line);
      line = "";
      length = 0;
    }
    line += piece;
    length += size;
  }
  if (line) lines.push(line);
  return lines.join("\n");
}

/**
 * Serialise a game, byte for byte as sgfmill would.
 *
 * Raw values are written back exactly as they were parsed -- sgfmill keeps them
 * verbatim rather than re-interpreting them -- and lines are wrapped at 79
 * bytes, which are both what the differential tests check.
 */
export function serialiseGame(game, wrap = 79) {
  const pieces = [];
  const stack = [coarseTree(game.getRoot())];
  while (stack.length > 0) {
    const tree = stack.pop();
    if (tree === null) {
      pieces.push(")");
      continue;
    }
    pieces.push("(");
    for (const node of tree.sequence) {
      pieces.push(";");
      for (const identifier of node.identifiers().sort(compareIdentifiers)) {
        let piece = identifier;
        for (const value of node.getRaw(identifier)) piece += "[" + value + "]";
        pieces.push(piece);
      }
    }
    stack.push(null);
    for (let i = tree.children.length - 1; i >= 0; i--) {
      stack.push(tree.children[i]);
    }
  }
  pieces.push("\n");
  return wrap == null ? pieces.join("") : blockFormat(pieces, wrap);
}

/** Set a text property, escaping it as FF[4] requires. */
export function setText(node, identifier, text) {
  node.setRaw(identifier, [escapeText(text)]);
}

/** The move at a node as text, eg "B D4"; used by the tree pane. */
export function nodeMoveLabel(node) {
  const [colour, raw] = node.getRawMove();
  if (colour == null) return null;
  let point = null;
  try {
    point = interpretGoPoint(raw, node.game.getSize());
  } catch (error) {
    point = null;
  }
  return `${colour.toUpperCase()} ${formatVertex(point)}`;
}
