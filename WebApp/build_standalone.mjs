/**
 * Build standalone.html: the whole app in one file, so it can be opened by
 * double-clicking, with no server at all.
 *
 *     node WebApp/build_standalone.mjs
 *
 * A browser refuses to load ES modules from a file:// URL, which is why the
 * modular version has to be served. This inlines the CSS and the modules into
 * a single classic script, which has no such restriction.
 *
 * The modular sources stay the truth: this file is generated from them, and
 * tests/standalone_test.mjs both runs the result and checks that it is up to
 * date. Regenerate it after changing anything in WebApp/js/.
 */

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "standalone.html");

// Dependencies come before the modules that use them.
const MODULES = ["properties.js", "board.js", "sgf.js", "moves.js", "tools.js",
                 "app.js"];

/**
 * Turn one ES module into plain script text.
 *
 * Only the three forms these modules actually use are handled, each anchored
 * to the start of a line so that the word "import" inside a comment or a
 * string cannot be mistaken for a statement.
 */
export function stripModuleSyntax(source) {
  return source
    // import { ... } from "./x.js";   (may span several lines)
    .replace(/^import\s[\s\S]*?from\s*"[^"]*";?[ \t]*$/gm, "")
    // export { a, b };
    .replace(/^export\s*\{[^}]*\};?[ \t]*$/gm, "")
    // export function / class / const / let / var
    .replace(/^export\s+(?=(async\s+)?(function|class|const|let|var)\b)/gm, "");
}

/** Inline the modules into one classic script. */
export function buildBundle() {
  const parts = MODULES.map((name) => {
    const source = readFileSync(join(HERE, "js", name), "utf8");
    return `// ---- ${name} ${"-".repeat(Math.max(0, 60 - name.length))}\n` +
           stripModuleSyntax(source).trimEnd();
  });
  return `(function () {\n"use strict";\n\n${parts.join("\n\n")}\n})();\n`;
}

/** Produce the standalone page from index.html and the sources. */
export function buildPage() {
  const css = readFileSync(join(HERE, "styles.css"), "utf8");
  let html = readFileSync(join(HERE, "index.html"), "utf8");

  html = html.replace(
    /[ \t]*<link rel="stylesheet" href="styles\.css">\n/,
    () => `<style>\n${css.trimEnd()}\n</style>\n`);
  html = html.replace(
    /[ \t]*<script type="module" src="js\/app\.js"><\/script>/,
    () => `<script>\n${buildBundle()}</script>`);
  html = html.replace(
    /<title>SGF Toolkit \(web\)<\/title>/,
    "<title>SGF Toolkit (web, standalone)</title>");

  return html;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const page = buildPage();
  writeFileSync(OUT, page, "utf8");
  const size = (Buffer.byteLength(page) / 1024).toFixed(1);
  console.log(`wrote ${OUT} (${size} KB)`);
}
