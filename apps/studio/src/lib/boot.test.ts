import { describe, expect, it } from "vitest";

import { removeBootShell } from "./boot";

describe("removeBootShell", () => {
  it("removes the bootstrap shell so it cannot outlive the first commit", () => {
    document.body.innerHTML = '<div id="root"><div id="boot">shell</div></div>';
    removeBootShell();
    expect(document.getElementById("boot")).toBeNull();
  });

  it("is a no-op when there is no shell to remove", () => {
    document.body.innerHTML = '<div id="root"></div>';
    expect(() => removeBootShell()).not.toThrow();
  });
});
