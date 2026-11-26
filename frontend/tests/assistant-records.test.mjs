import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Module from "node:module";
import path from "node:path";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const filename = path.resolve("components/PatientRecords.tsx");
const component = new Module(filename);
component.filename = filename;
component.paths = Module._nodeModulePaths(path.dirname(filename));
const original = component.require.bind(component);
const stubs = {
  "@/components/ui": {},
  "@/lib/api": {},
  "@/lib/use-loader": { useLoader: () => ({ state: { status: "ready", data: {
    documents: [], summary: { patient: { name: "Patient" }, appointments: [], access: "private" },
  } } }) },
};
component.require = name => Object.hasOwn(stubs, name) ? stubs[name] : original(name);
component._compile(ts.transpileModule(readFileSync(filename, "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
}).outputText, filename);

function render(canUpload, disabled = false) {
  return renderToStaticMarkup(React.createElement(component.exports.PatientRecords, {
    selected: null, onSelect() {}, onUploadStateChange() {}, disabled, canUpload,
  }));
}

test("patient composer retains upload and collapses record details", () => {
  const html = render(true);
  assert.match(html, /Upload document/);
  assert.match(html, /accept="\.pdf,\.png,\.jpg,\.jpeg,\.txt"/);
  assert.match(html, /Records &amp; appointments/);
  assert.doesNotMatch(html, /<aside|<details[^>]*open=/);
});

test("staff record control does not grant upload access; busy patient uploads are disabled", () => {
  assert.doesNotMatch(render(false), /Upload document|type="file"/);
  assert.match(render(true, true), /<button[^>]*disabled=""/);
});
