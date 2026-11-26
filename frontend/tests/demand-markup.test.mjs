import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Module from "node:module";
import path from "node:path";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Compile the real TSX component in memory; no generated files or browser substitutes.
const filename = path.resolve("components/DemandChart.tsx");
const component = new Module(filename);
component.filename = filename;
component.paths = Module._nodeModulePaths(path.dirname(filename));
component._compile(ts.transpileModule(readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
}).outputText, filename);

test("demand chart renders finite geometry, named controls and exact-value alternative", () => {
  const data = {
    history: Array.from({ length: 14 }, (_, i) => ({ day: `2026-11-${String(i + 1).padStart(2, "0")}`, demand: i * 3 })),
    points: Array.from({ length: 7 }, (_, i) => ({ day: `2026-11-${23 + i}`, capacity: i === 6 ? 0 : i === 5 ? 48 : 120, linear_regression: i === 6 ? 0 : 30 + i, baseline: i === 6 ? 0 : 28 + i })),
  };
  const html = renderToStaticMarkup(React.createElement(component.exports.DemandChart, { data }));
  assert.doesNotMatch(html, /NaN|Infinity|undefined/);
  assert.match(html, /role="img" aria-labelledby=/);
  assert.match(html, /Regression and baseline forecasts/);
  assert.match(html, /Inspect forecast date/);
  assert.match(html, /aria-live="polite" aria-atomic="true"/);
  assert.match(html, /Regression: <strong>30\.0/);
  assert.match(html, /Next 7 days/);
  assert.match(html, /Last 14 days/);
  assert.match(html, /scroll horizontally on narrow screens/);
  assert.match(html, /Closed/);
});
