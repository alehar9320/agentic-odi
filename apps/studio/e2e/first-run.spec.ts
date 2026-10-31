import { expect, test } from "@playwright/test";

const COMPOSER = "Message the studio";

/**
 * The first run, driven the way a person meets it: the stage offers a door, the
 * agent asks five questions, and the answers become a brief that survives in
 * local storage. No model is reachable during the run, which is the point: the
 * introduction finishes without one.
 */
test.describe("the first-run introduction", () => {
  test.beforeEach(async ({ request }) => {
    // The sidecar is shared by the whole run, and the Studio restores its most
    // recent conversation on boot. A previous spec's thread would open in place
    // of the first-run hero, so the memory is emptied the way a first visit is.
    await request.delete("/api/memory");
  });

  test("asks five questions and saves the brief in the person's words", async ({ page }) => {
    await page.goto("/?flags=firstRunWizard:off");

    // A fresh studio with no connectors offers one in a modal. That is real
    // product behavior, so it is dismissed the way a person would.
    const suggestion = page.getByRole("dialog", { name: "Connector suggestion" });
    await suggestion.waitFor({ state: "visible", timeout: 2_000 }).catch(() => {});
    if (await suggestion.isVisible()) {
      await suggestion.getByRole("button", { name: "Not now" }).click();
      await expect(suggestion).toBeHidden();
    }

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
