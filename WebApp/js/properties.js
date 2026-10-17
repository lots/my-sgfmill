/**
 * SGF property values: interpretation and serialisation.
 *
 * This mirrors sgfmill.sgf_properties for the property types the web app
 * needs. Points are held the way sgfmill holds them -- [row, col] with
 * (0, 0) at the bottom left, the GTP convention -- so that a board diagram
 * comes out the same way round as the Python library's.
 */

/** Largest board this library supports (sgfmill supports up to 26x26). */
export const MAX_SIZE = 26;

export class SgfError extends Error {}

/**
 * SGF point -> [row, col]. A pass is null.
 *
 * As in FF[4] after this project's change, a pass is the empty value. The
 * older 'tt' spelling is still accepted as a pass on boards of 19 or less.
 */
export function interpretGoPoint(value, size) {
  if (value === "" || value == null) return null;
  if (value.length !== 2) {
    throw new SgfError(`invalid point: ${JSON.stringify(value)}`);
  }
  const col = value.charCodeAt(0) - 97;
  const row = size - 1 - (value.charCodeAt(1) - 97);
  if (col < 0 || col >= size || row < 0 || row >= size) {
    if (value === "tt" && size <= 19) return null;
    throw new SgfError(`point off the board: ${JSON.stringify(value)}`);
  }
  return [row, col];
}

/** [row, col] -> SGF point. null (a pass) becomes the empty value. */
export function serialiseGoPoint(point, size) {
  if (point == null) return "";
  const [row, col] = point;
  return String.fromCharCode(97 + col) + String.fromCharCode(97 + size - 1 - row);
}

/** Text of a point in GTP style, eg "D4"; passes read as "pass". */
export function formatVertex(point) {
  if (point == null) return "pass";
  const [row, col] = point;
  // Column letters skip 'I', as SGF and GTP both do.
  const letter = col < 8
    ? String.fromCharCode(65 + col)
    : String.fromCharCode(66 + col);
  return letter + (row + 1);
}

/** Interpret a raw value according to a property's type. */
export function interpretValue(identifier, raw, size) {
  const type = PROPERTY_TYPES[identifier] || "raw";
  switch (type) {
    case "number":
      return Number(raw);
    case "real":
    case "double":
      return Number(raw);
    case "colour":
      return raw[0].toLowerCase();
    case "point":
      return interpretGoPoint(raw, size);
    case "pointList":
      return interpretPointList([raw], size);
    case "label":
      return interpretLabel(raw, size);
    case "text":
      return unescapeText(raw);
    default:
      return raw;
  }
}

/**
 * Interpret a point list: the raw values of a property, as a list of points.
 *
 * FF[4] allows a *compressed* value: "aa:cc" means the whole rectangle with
 * those corners. The list is a set, so overlapping values are merged and
 * duplicates disappear -- which is what sgfmill's interpret_point_list does,
 * and what the differential tests compare.
 */
export function interpretPointList(values, size) {
  const seen = new Set();
  const points = [];
  const add = (point) => {
    const key = point[0] * MAX_SIZE + point[1];
    if (seen.has(key)) return;
    seen.add(key);
    points.push(point);
  };
  for (const value of values) {
    // An empty value is the FF[4] way of writing "no points" (an elist such as
    // DD[]); it contributes nothing.
    if (value === "") continue;
    const colon = value.indexOf(":");
    if (colon === -1) {
      add(interpretGoPoint(value, size));
      continue;
    }
    const topLeft = interpretGoPoint(value.slice(0, colon), size);
    const bottomRight = interpretGoPoint(value.slice(colon + 1), size);
    const [top, left] = topLeft;
    const [bottom, right] = bottomRight;
    if (!(bottom <= top && left <= right)) throw new SgfError("bad rectangle");
    for (let row = bottom; row <= top; row++) {
      for (let col = left; col <= right; col++) add([row, col]);
    }
  }
  return points;
}

/** A label value is "point:text". */
function interpretLabel(raw, size) {
  const index = raw.indexOf(":");
  if (index === -1) return [];
  const point = interpretGoPoint(raw.slice(0, index), size);
  return [[point, raw.slice(index + 1)]];
}

/** FF[4] text: only backslash and closing bracket are escaped. */
export function unescapeText(raw) {
  let out = "";
  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i];
    if (ch === "\\" && i + 1 < raw.length) {
      const next = raw[++i];
      // A backslash before a newline is a soft line break: it vanishes.
      if (next !== "\n" && next !== "\r") out += next;
    } else {
      out += ch;
    }
  }
  return out;
}

export function escapeText(text) {
  return String(text).replace(/\\/g, "\\\\").replace(/\]/g, "\\]");
}

/**
 * Property types, by identifier, for the properties that matter here.
 * Anything not listed is treated as raw, which is what serialisation needs.
 */
export const PROPERTY_TYPES = {
  // Move
  B: "point", W: "point", KO: "raw", MN: "number",
  // Setup
  AB: "pointList", AW: "pointList", AE: "pointList", PL: "colour",
  // Node annotation
  C: "text", DM: "double", GB: "double", GW: "double", HO: "double",
  N: "simpletext", UC: "double", V: "real",
  // Move annotation
  BM: "double", DO: "raw", IT: "raw", TE: "double",
  // Markup
  AR: "raw", CR: "pointList", DD: "raw", LB: "label", LN: "raw",
  MA: "pointList", SL: "pointList", SQ: "pointList", TR: "pointList",
  // Root
  AP: "simpletext", CA: "simpletext", FF: "number", GM: "number",
  ST: "number", SZ: "raw",
  // Game info
  AN: "simpletext", BR: "simpletext", BT: "simpletext", CP: "simpletext",
  DT: "simpletext", EV: "simpletext", GN: "simpletext", GC: "text",
  ON: "simpletext", OT: "simpletext", PB: "simpletext", PC: "simpletext",
  PW: "simpletext", RE: "simpletext", RO: "simpletext", RU: "simpletext",
  SO: "simpletext", TM: "real", US: "simpletext", WR: "simpletext",
  WT: "simpletext", HA: "number", KM: "real",
  // Timing
  BL: "real", WL: "real", OB: "number", OW: "number",
  // Misc
  FG: "raw", PM: "number", VW: "raw",
  // Territory
  TB: "pointList", TW: "pointList",
  // Go-specific
  TC: "number",
};

/** Is this a text property, so its value needs escaping when written? */
export function isTextProperty(identifier) {
  const type = PROPERTY_TYPES[identifier];
  return type === "text" || type === "simpletext";
}

/** Does a value of this property hold points, so a transformation moves it? */
export function isPointProperty(identifier) {
  const type = PROPERTY_TYPES[identifier];
  return type === "point" || type === "pointList" || type === "label";
}
