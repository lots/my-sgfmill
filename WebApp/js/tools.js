/**
 * The library operations the app exposes: normalise, transform, encoding and
 * splitting a collection.
 *
 * These mirror sgfmill.sgf_normalise, sgfmill.sgf_transform and
 * sgfmill.sgf_encoding; tests/generate_expected.py produces the answers from
 * the Python library itself and tests compare the two.
 */

import { Board } from "./board.js";
import {
  formatVertex, interpretGoPoint, interpretPointList, serialiseGoPoint,
  SgfError, MAX_SIZE,
} from "./properties.js";
import { SgfNode, SgfGame, parseSgfCollection, setText } from "./sgf.js";

// -- normalise -------------------------------------------------------------

/** Every property FF[4] defines for Go, plus the general ones we keep. */
export const STANDARD_PROPERTIES = new Set([
  "AB", "AE", "AN", "AP", "AR", "AW", "B", "BL", "BM", "BR", "BT", "C",
  "CA", "CP", "CR", "DD", "DM", "DO", "DT", "EV", "FF", "FG", "GB", "GC",
  "GM", "GN", "GW", "HA", "HO", "ID", "IT", "KM", "KO", "L", "LB", "LN",
  "LT", "MA", "MN", "N", "OB", "ON", "OT", "OW", "PB", "PC", "PL", "PM",
  "PW", "RE", "RO", "RU", "SL", "SO", "SQ", "ST", "SZ", "TB", "TE", "TM",
  "TR", "TW", "UC", "US", "V", "VW", "W", "WL", "WR", "WT",
]);

/** The properties a usable FF[4] game must carry. */
export const MINIMUM_STANDARD_PROPERTIES = new Set(["FF", "GM", "SZ"]);

/** Walk a node and all its descendants, depth first, in tree order. */
export function* walkNodes(node) {
  yield node;
  for (const child of node.children) yield* walkNodes(child);
}

/** A report of what is, or was, non-standard. */
export class GameReport {
  constructor(findings, removed) {
    this.findings = findings;      // identifier -> [nodes]
    this.removed = removed;
  }

  /** The offending identifiers, sorted. */
  properties() {
    return [...this.findings.keys()].sort();
  }

  /** How many properties were found. */
  count() {
    return this.properties().length;
  }

  /** The nodes carrying at least one of them. */
  nodes() {
    const seen = new Set();
    const nodes = [];
    for (const list of this.findings.values()) {
      for (const node of list) {
        if (!seen.has(node)) {
          seen.add(node);
          nodes.push(node);
        }
      }
    }
    return nodes;
  }

  /** How many nodes carry at least one of them. */
  nodeCount() {
    return this.nodes().length;
  }

  get ok() {
    return this.findings.size === 0;
  }
}

export function checkGame(game, standard = STANDARD_PROPERTIES) {
  const findings = new Map();
  for (const node of walkNodes(game.getRoot())) {
    for (const identifier of node.identifiers().sort()) {
      if (!standard.has(identifier)) {
        if (!findings.has(identifier)) findings.set(identifier, []);
        findings.get(identifier).push(node);
      }
    }
  }
  return new GameReport(findings, false);
}

export function cleanGame(game, standard = STANDARD_PROPERTIES) {
  const findings = new Map();
  for (const node of walkNodes(game.getRoot())) {
    for (const identifier of node.identifiers().sort()) {
      if (!standard.has(identifier)) {
        if (!findings.has(identifier)) findings.set(identifier, []);
        findings.get(identifier).push(node);
        node.getRawMap().delete(identifier);
      }
    }
  }
  return new GameReport(findings, true);
}

// -- transform -------------------------------------------------------------

export const FLIP_VERTICAL = "flip_vertical";
export const FLIP_HORIZONTAL = "flip_horizontal";
export const ROTATE_CW = "rotate_cw";
export const ROTATE_ACW = "rotate_acw";
export const TRANSFORMATIONS = [
  FLIP_VERTICAL, FLIP_HORIZONTAL, ROTATE_CW, ROTATE_ACW,
];

const POINT_FUNCTIONS = {
  [FLIP_VERTICAL]: (row, col, side) => [side - 1 - row, col],
  [FLIP_HORIZONTAL]: (row, col, side) => [row, side - 1 - col],
  // Turning the board 90 degrees clockwise takes the top-left corner to the
  // top-right, as FF[4] specifies ('a' becomes 'i').
  [ROTATE_CW]: (row, col, side) => [side - 1 - col, row],
  [ROTATE_ACW]: (row, col, side) => [col, side - 1 - row],
};

export function transformPoint(point, transformation, side) {
  if (point == null) return null;
  const fn = POINT_FUNCTIONS[transformation];
  if (!fn) throw new SgfError(`unknown transformation: ${transformation}`);
  return fn(point[0], point[1], side);
}

// Properties holding a single point, and those holding lists of points.
const POINT_PROPERTIES = new Set(["B", "W"]);
const POINT_LIST_PROPERTIES = new Set([
  "AB", "AW", "AE", "CR", "MA", "SL", "SQ", "TR", "TB", "TW",
]);
// Elists: the same as a point list, but an empty value is meaningful.
const ELIST_PROPERTIES = new Set(["DD", "VW"]);
const PAIR_PROPERTIES = new Set(["AR", "LN"]);
const LABEL_PROPERTIES = new Set(["LB"]);

/** Transform a game in place. */
export function transformGame(game, transformation) {
  if (!TRANSFORMATIONS.includes(transformation)) {
    throw new SgfError(`unknown transformation: ${transformation}`);
  }
  const side = game.getSize();
  for (const node of walkNodes(game.getRoot())) {
    transformNode(node, transformation, side);
  }
  return game;
}

function transformNode(node, transformation, side) {
  for (const identifier of node.identifiers()) {
    const values = node.getRaw(identifier);
    if (POINT_PROPERTIES.has(identifier)) {
      node.setRaw(identifier, values.map((value) => {
        if (value === "") return value;                 // a pass stays a pass
        const point = interpretGoPoint(value, side);
        return serialiseGoPoint(transformPoint(point, transformation, side),
                                side);
      }));
    } else if (POINT_LIST_PROPERTIES.has(identifier) ||
               ELIST_PROPERTIES.has(identifier)) {
      // sgfmill interprets a point list (expanding any compressed "aa:cc"
      // rectangles and merging duplicates) and re-serialises it one value per
      // point, sorted. Matching that keeps the output byte for byte identical
      // to the library's.
      const points = interpretPointList(values, side);
      const serialised = points
        .map((point) => serialiseGoPoint(
          transformPoint(point, transformation, side), side))
        .sort();
      node.setRaw(identifier, serialised.length === 0 ? [""] : serialised);
    } else if (PAIR_PROPERTIES.has(identifier)) {
      // Two points, in order: an arrow keeps pointing the same way.
      node.setRaw(identifier, values.map((value) => {
        if (value.length !== 5 || value[2] !== ":") return value;
        const a = interpretGoPoint(value.slice(0, 2), side);
        const b = interpretGoPoint(value.slice(3, 5), side);
        return serialiseGoPoint(transformPoint(a, transformation, side), side) +
               ":" + serialiseGoPoint(transformPoint(b, transformation, side),
                                      side);
      }));
    } else if (LABEL_PROPERTIES.has(identifier)) {
      // A label's point moves; its text does not. Their order is kept.
      node.setRaw(identifier, values.map((value) => {
        if (value.length < 3 || value[2] !== ":") return value;
        const point = interpretGoPoint(value.slice(0, 2), side);
        return serialiseGoPoint(transformPoint(point, transformation, side),
                                side) + value.slice(2);
      }));
    }
  }
}

/** A point list as text, eg "D4 Q16"; a compressed list is expanded. */
export function formatPointList(value, side) {
  if (value === "") return "(empty)";
  try {
    return interpretPointList([value], side).map(formatVertex).join(" ");
  } catch (error) {
    return "?";
  }
}

// -- character encoding ----------------------------------------------------

export const UTF8 = "UTF-8";

/** TextDecoder labels, and the name FF[4] files generally use for them. */
const CHARSET_ALIASES = {
  "utf-8": "utf-8", "utf8": "utf-8",
  "iso-8859-1": "iso-8859-1", "iso8859-1": "iso-8859-1",
  "latin1": "iso-8859-1", "latin-1": "iso-8859-1",
  "us-ascii": "utf-8", "ascii": "utf-8",
  "shift-jis": "shift_jis", "shiftjis": "shift_jis", "sjis": "shift_jis",
  "euc-jp": "euc-jp", "eucjp": "euc-jp",
  "gb2312": "gbk", "gbk": "gbk", "gb18030": "gb18030",
  "big5": "big5", "euc-kr": "euc-kr",
  "utf-16": "utf-16le", "utf-16le": "utf-16le", "utf-16be": "utf-16be",
};

const DISPLAY_NAMES = {
  "utf-8": "UTF-8",
  "iso-8859-1": "ISO-8859-1",
  "shift_jis": "Shift_JIS",
  "euc-jp": "EUC-JP",
  "gbk": "GBK",
  "gb18030": "GB18030",
  "big5": "BIG5",
  "euc-kr": "EUC-KR",
  "utf-16le": "UTF-16LE",
  "utf-16be": "UTF-16BE",
};

/** A charset name from a CA property, mapped to a TextDecoder label. */
export function normaliseCharsetName(name) {
  const cleaned = String(name).trim().toLowerCase().replace(/[_ ]/g, "-");
  const label = CHARSET_ALIASES[cleaned];
  if (!label) return null;
  try {
    new TextDecoder(label, { fatal: true });   // is this label supported?
    return label;
  } catch (error) {
    return null;
  }
}

/** The name to show a user for a TextDecoder label. */
export function displayCharsetName(label) {
  return DISPLAY_NAMES[label] || label;
}

/** Read the CA property as text, without needing to know the encoding yet. */
export function declaredCharset(bytes) {
  // CA's value is ASCII, so decoding the whole file as Latin-1 to read it is
  // safe whatever the file really is.
  const text = new TextDecoder("iso-8859-1").decode(bytes);
  const match = /(?:^|[^A-Za-z])CA\[((?:\\.|[^\]\\])*)\]/.exec(text);
  if (!match) return null;
  return match[1].replace(/\\(.)/g, "$1");
}

/**
 * Work out the encoding of some SGF bytes.
 *
 * Follows sgfmill.sgf_encoding.detect_bytes: a byte order mark wins, then the
 * declared CA, then UTF-8, then ISO-8859-1 (which decodes anything).
 */
export function detectEncoding(bytes) {
  const hasBom = bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb &&
                 bytes[2] === 0xbf;
  const asciiOnly = bytes.every((byte) => byte < 0x80);
  let declared = hasBom ? UTF8 : declaredCharset(bytes);
  const declaredCodec = declared == null ? null : normaliseCharsetName(declared);

  if (hasBom) {
    return { encoding: UTF8, declared: UTF8, mismatch: false, asciiOnly: false,
             hasBom: true };
  }
  if (asciiOnly && declared != null) {
    // Every ASCII-compatible encoding agrees on these bytes, so there is
    // nothing to detect and nothing that would need converting.
    const name = declaredCodec == null
      ? declared
      : displayCharsetName(declaredCodec);
    return { encoding: name, declared: name, mismatch: false, asciiOnly: true,
             hasBom: false };
  }

  const order = declaredCodec == null
    ? ["utf-8", "iso-8859-1"]
    : [declaredCodec, "utf-8", "iso-8859-1"];
  const tried = [];
  for (const candidate of order) {
    if (tried.includes(candidate)) continue;
    tried.push(candidate);
    if (canDecode(bytes, candidate)) {
      const encoding = displayCharsetName(candidate);
      // As in sgfmill, the declared name is compared as written: a file that
      // says something other than what it turned out to be is a mismatch.
      return {
        encoding,
        declared,
        mismatch: declared !== encoding,
        asciiOnly,
        hasBom: false,
      };
    }
  }
  throw new SgfError(`can't determine the encoding of the SGF data (tried ${
    tried.join(", ")})`);
}

function canDecode(bytes, label) {
  try {
    new TextDecoder(label, { fatal: true }).decode(bytes);
    return true;
  } catch (error) {
    return false;
  }
}

/** Decode SGF bytes using a name from detectEncoding(). */
export function decodeBytes(bytes, label) {
  const decoder = new TextDecoder(label === UTF8 ? "utf-8" : label,
                                  { fatal: false });
  return decoder.decode(bytes);
}

/** Set CA[UTF-8] so a written file says what it is. */
export function convertGameToUtf8(game) {
  game.getRoot().setRaw("CA", [UTF8]);
  return game;
}

/** Describe an encoding result the way the app's report shows it. */
export function describeEncoding(result) {
  const parts = [result.encoding];
  if (result.encoding === UTF8 && !result.mismatch) {
    parts.push("UTF-8, as files should be");
  }
  if (result.asciiOnly) parts.push("ASCII only");
  return parts.join("; ");
}

// -- splitting a collection ------------------------------------------------

/** Split a collection of games into separate serialised records. */
export function splitCollection(text) {
  return parseSgfCollection(text);
}

export { Board, SgfGame, SgfNode, setText, MAX_SIZE };
