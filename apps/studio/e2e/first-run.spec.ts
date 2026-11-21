import { expect, test } from "./fixtures";

import { dismissConnectorSuggestion } from "./helpers";

const COMPOSER = "Message the studio";

/**
 * The first run, driven the way a person meets it: the stage offers a door, the
 * agent asks five questions, and the answers become a brief that survives in
 * local storage. No model is reachable during the run, which is the point: the
 * introduction finishes without one.
 *
 * The Studio restores its most recent conversation on boot, so a previous
 * spec's thread would open in place of the first-run hero. `e2e/fixtures.ts`
 * clears that memory before every test — this spec used to be the only one that
 * did, which made every other spec depend on it having run.
 */
test.describe("the first-run introduction", () => {
  test("asks five questions and saves the brief in the person's words", { tag: "@smoke" }, async ({
    page,
  }) => {
    await page.goto("/?flags=firstRunWizard:off");

    // A fresh studio with no connectors offers one in a modal. That is real
    // product behavior, so it is dismissed the way a person would.
    await dismissConnectorSuggestion(page);

    await page.getByRole("button", { name: "Start with you and your team" }).click();

    const composer = page.getByRole("textbox", { name: COMPOSER });
    const answers = [
      "I'm the PM for the deploy tool; the team is four engineers and a designer.",
      "The on-call platform engineer at 2am",
      "Ship a service without hand-copying config",
      "A missed key costs a deploy day",
      "Nine onboarding calls, a very angry ticket, and a Slack thread",
    ];

    for (const answer of answers) {
      await composer.fill(answer);
      await composer.press("Enter");
    }

    await expect(
      page.getByRole("heading", { name: "Does this look like you?" }),
    ).toBeVisible();
    await expect(page.getByText("Team: four engineers and a designer")).toBeVisible();

    await page.getByRole("button", { name: "Looks like me" }).click();

    // The introduction is gone and the brief is already in the conversation.
    await expect(page.getByRole("button", { name: "Edit context" })).toBeVisible();
    await expect(page.getByText(/on-call platform engineer/)).toBeVisible();

    const saved = await page.evaluate(() => {
      const raw = window.localStorage.getItem("studio.brief");
      return raw ? JSON.parse(raw) : null;
    });

    expect(saved).toMatchObject({
      role: answers[0],
      team: "four engineers and a designer",
      target_user: answers[1],
      job_statement: answers[2],
      core_problem: answers[3],
      evidence_at_hand: [
        "Nine onboarding calls",
        "a very angry ticket",
        "a Slack thread",
      ],
    });
    expect(saved.job_id).toBeTruthy();
  });
});
