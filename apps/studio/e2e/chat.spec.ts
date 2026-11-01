import { expect, test } from "@playwright/test";

import { CONVERSATION, lastReply, openStudio, sendMessage } from "./helpers";

/**
 * The conversation is the Studio's main surface. These tests cover the path
 * every user takes: say something, get an answer.
 *
 * No model is reachable during the test run, so the assistant answers with the
 * sidecar's deterministic reply, labelled on the reply as a local draft. That
 * is the behaviour a user with no LLM configured actually sees, and it is
 * stable enough to assert on.
 */
test.describe("the conversation", () => {
  test("answers a question in the transcript", async ({ page }) => {
    await openStudio(page);

    await sendMessage(page, "Walk me through the ODI stage-by-stage guidelines.");

    const reply = await lastReply(page);
    expect(reply).toContain("ODI, stage by stage");
    expect(reply).toContain("Define the job");
  });

  test("shows the user's message alongside the reply", async ({ page }) => {
    await openStudio(page);

    await sendMessage(page, "Show me the framework.");

    const log = page.getByRole("log", { name: CONVERSATION });
    await expect(log).toContainText("Show me the framework.");
    await expect(log.locator(".message--assistant").last()).toContainText(
      "ODI, stage by stage",
    );
  });

  test("says a reply is a local draft when no model can answer it", async ({ page }) => {
    await openStudio(page);

    await sendMessage(page, "What is the weather tomorrow?");

    const reply = await lastReply(page);
    expect(reply).toContain("Local draft, no model connected");
    expect(reply).toContain("/capture — record an outcome");
  });

  test("offers a copy button on the reply", async ({ page }) => {
    await openStudio(page);

    await sendMessage(page, "Give me the guidelines.");
    await lastReply(page);

    const reply = page
      .getByRole("log", { name: CONVERSATION })
      .locator(".message--assistant")
      .last();
    await expect(reply.getByRole("button", { name: "Copy reply" })).toBeVisible();
  });
});
