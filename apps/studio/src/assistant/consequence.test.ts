import { describe, expect, it } from "vitest";

import { describeConsequence } from "./consequence";

describe("describeConsequence", () => {
  it("says a create_ tool creates its noun", () => {
    expect(describeConsequence("create_job")).toBe("creates a job");
  });

  it("says an add_ tool creates its noun", () => {
    expect(describeConsequence("add_outcome")).toBe("creates an outcome");
  });

  it("says an update_ tool changes an existing record", () => {
    expect(describeConsequence("update_outcome")).toBe("changes an existing outcome");
  });

  it("says a delete_ tool removes its noun", () => {
    expect(describeConsequence("delete_step")).toBe("removes a step");
  });

  it("uses 'an' before a vowel, and no article for an uncountable noun", () => {
    expect(describeConsequence("add_evidence")).toBe("creates evidence");
    expect(describeConsequence("create_observation")).toBe("creates an observation");
  });

  it("reads a multi-word noun without underscores", () => {
    expect(describeConsequence("add_customer_outcome")).toBe("creates a customer outcome");
  });

  it("falls back to running the tool rather than inventing an effect", () => {
    expect(describeConsequence("make_coffee")).toBe("runs make_coffee");
    expect(describeConsequence("get_jobs")).toBe("runs get_jobs");
  });
});
