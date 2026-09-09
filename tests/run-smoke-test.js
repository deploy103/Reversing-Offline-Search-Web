#!/usr/bin/env node
/*
 * file:// smoke test runner for Reversing-Offline-Search-Web.
 *
 * Loads the ACTUAL built dist/assets/search-index.js and the search engine
 * (assets/js/search.js) into a Node vm sandbox that stubs just enough of
 * `window`/`document` for the script to execute without a real browser, then
 * runs every query in tests/search-smoke-queries.txt and reports whether each
 * one returned a top result.
 *
 * This exercises the same code path a real double-clicked dist/index.html
 * would use (no fetch/XHR, no build-time-only shortcuts) -- it is not a
 * simulation of the search logic, it is the search logic.
 *
 * Usage (from repo root):
 *   node tests/run-smoke-test.js
 *
 * Exit code 0 if every query returns at least one result, 1 otherwise.
 */
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");

function loadSandbox() {
  const sandbox = {
    window: {},
    console: console,
    document: {
      addEventListener: function () {},
      getElementById: function () { return null; },
      querySelector: function () { return null; },
      querySelectorAll: function () { return []; },
      createElement: function () {
        return {
          setAttribute: function () {},
          appendChild: function () {},
          style: {},
          classList: { add: function () {}, remove: function () {} },
        };
      },
    },
  };
  sandbox.window = sandbox;
  sandbox.window.location = { search: "" };
  vm.createContext(sandbox);

  const indexPath = path.join(ROOT, "dist", "assets", "search-index.js");
  if (!fs.existsSync(indexPath)) {
    console.error("dist/assets/search-index.js not found -- run `python3 scripts/build.py` first.");
    process.exit(1);
  }
  const indexSrc = fs.readFileSync(indexPath, "utf8");
  const searchSrc = fs.readFileSync(path.join(ROOT, "assets", "js", "search.js"), "utf8");

  vm.runInContext(indexSrc, sandbox);
  vm.runInContext(searchSrc, sandbox);
  return sandbox;
}

function main() {
  const sandbox = loadSandbox();
  const queriesPath = path.join(ROOT, "tests", "search-smoke-queries.txt");
  const queries = fs
    .readFileSync(queriesPath, "utf8")
    .split("\n")
    .map((s) => s.trim())
    .filter(Boolean);

  let failCount = 0;
  const rows = [];
  for (const q of queries) {
    const results = sandbox.RevSearch.search(q, { limit: 5 });
    const top = results && results.length ? results[0] : null;
    rows.push({
      query: q,
      id: top ? top.id : null,
      title: top ? top.title : null,
    });
    if (!top) failCount++;
  }

  for (const r of rows) {
    const label = r.id ? `${r.id}  ${r.title}` : "(NO RESULT)";
    console.log(`${r.query.padEnd(22)} -> ${label}`);
  }
  console.log("---");
  console.log(`total queries: ${queries.length}, no-result: ${failCount}`);
  process.exit(failCount > 0 ? 1 : 0);
}

main();
