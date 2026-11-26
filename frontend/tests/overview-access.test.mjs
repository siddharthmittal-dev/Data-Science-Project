import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Module from "node:module";
import path from "node:path";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

test("overview offers patient follow-up only to the owner", () => {
  let role;
  const filename = path.resolve("app/page.tsx");
  const component = new Module(filename);
  component.filename = filename;
  component.paths = Module._nodeModulePaths(path.dirname(filename));
  const originalRequire = component.require.bind(component);
  const stubs = {
    "next/link": ({ href, children }) => React.createElement("a", { href }, children),
    "@/components/CareArt": { CareArt: () => null },
    "@/components/ui": { EmptyState: ({ children }) => React.createElement("div", null, children) },
    "@/lib/api": { getDashboard: () => {} },
    "@/lib/format": {},
    "@/lib/use-loader": { useLoader: () => ({ state: { status: "ready", data: {
      user: { role, name: "Account" }, counts: { upcoming: 0, completed: 0, cancelled: 0 },
      next_appointment: null, recent_activity: [],
      staff_summary: role === "patient" ? null : { today_visits: 0, awaiting_outcome: 0 },
    } } }) },
  };
  component.require = name => Object.hasOwn(stubs, name) ? stubs[name] : originalRequire(name);
  component._compile(ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, filename);
  for (role of ["patient", "receptionist", "admin"]) {
    const html = renderToStaticMarkup(React.createElement(component.exports.default));
    assert.equal(html.includes('href="/retention"'), role === "admin", role);
    if (role === "receptionist") assert.match(html, /Record outcomes/);
  }
});
