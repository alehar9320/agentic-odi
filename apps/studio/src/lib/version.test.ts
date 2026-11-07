import { readFileSync } from "node:fs";
import { STUDIO_VERSION } from "./version";

const pkg = JSON.parse(readFileSync("package.json", "utf-8"));
const release = JSON.parse(readFileSync("../../.release-please-manifest.json", "utf-8"));

test("STUDIO_VERSION matches package.json and release manifest", () => {
  expect(STUDIO_VERSION).toBe(pkg.version);
  expect(STUDIO_VERSION).toBe(release["."]);
});