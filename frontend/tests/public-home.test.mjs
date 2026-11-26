import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Module from "node:module";
import path from "node:path";
import { test } from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

function load(file, stubs) {
  const filename = path.resolve(file);
  const component = new Module(filename);
  component.filename = filename;
  component.paths = Module._nodeModulePaths(path.dirname(filename));
  const original = component.require.bind(component);
  component.require = name => Object.hasOwn(stubs, name) ? stubs[name] : original(name);
  component._compile(ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
  }).outputText, filename);
  return component.exports;
}

test("anonymous home renders public clinic content without private route children", () => {
  let status = "anon";
  const shell = load("components/AppShell.tsx", {
    "next/link": ({ children }) => React.createElement("a", null, children),
    "next/navigation": { usePathname: () => "/", useRouter: () => ({ replace() {} }) },
    "@/lib/auth": { useAuth: () => ({ state: { status, user: { name: "Account", role: "patient" } } }) },
    "@/lib/api": {}, "@/components/ui": {},
    "@/components/ClinicHome": { ClinicHome: () => React.createElement("div", null, "PUBLIC CLINIC") },
  });
  const render = () => renderToStaticMarkup(React.createElement(shell.AppShell, null, "PRIVATE DASHBOARD"));
  assert.match(render(), /PUBLIC CLINIC/);
  assert.doesNotMatch(render(), /PRIVATE DASHBOARD/);
  status = "authed";
  assert.match(render(), /PRIVATE DASHBOARD/);
  assert.doesNotMatch(render(), /PUBLIC CLINIC/);
});

test("login offers three email shortcuts with an empty required password", () => {
  const panel = load("components/LoginPanel.tsx", {
    "next/navigation": { useRouter: () => ({ replace() {} }) },
    "@/lib/auth": { useAuth: () => ({ state: { status: "anon" } }) },
    "@/lib/api": {}, "@/components/ui": {},
  });
  assert.deepEqual(panel.LOGIN_ACCOUNTS.map(a => a.email), ["patient@terra.test", "receptionist@terra.test", "owner@terra.test"]);
  const html = renderToStaticMarkup(React.createElement(panel.LoginPanel));
  for (const label of ["Patient", "Receptionist", "Owner"]) assert.ok(html.includes(`>${label}</button>`));
  assert.match(html, /type="password"[^>]*required=""[^>]*value=""/);
  assert.doesNotMatch(html, /Create an account|Create account/);
});
