import { expect, test, type Page } from "@playwright/test";

import { COMPOSER, CONVERSATION, dismissConnectorSuggestion, openStudio } from "./helpers";
import { installEdgeDevice } from "./edgeDevice";

/**
 * The browser tier, end to end.
 *
 * What this proves: that the seams are wired — a first visit with no key gets
 * asked once, the yes starts a fetch the dock narrates, the answer that lands
 * is labelled as coming from this browser, a refusal is remembered, and a key
 * appearing later takes the turns back. It drives the real manager, scheduler,
 * IndexedDB state, notice bus, banner dock, composer routing and transcript
 * labelling in a real Chromium against a real sidecar.
 *
 * What it does NOT prove: WebLLM. CI has no GPU and no model weights, so the
 * engine is the fake in `edgeDevice.ts`. The real-GPU path — a 1.3 GB download
 * actually landing, prefill jank, `navigator.locks` across two real tabs, the
 * memory ceiling on iOS — is the handoff list in
 * `docs/superpowers/plans/2026-11-01-edge-llm-ladder-remaining-work.md`, not
 * something this file can assert.
 */

/** Record every `/api/chat` this page tries to send, so "who answered" is a fact. */
function watchRemoteTurns(page: Page): string[] {
  const sent: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/chat")) {
      sent.push(request.url());
    }
  });
  return sent;
}

const dock = (page: Page) => page.locator(".banner");

const offerStrip = (page: Page) => dock(page).filter({ hasText: "This browser can answer" });

const reply = (page: Page) =>
  page.getByRole("log", { name: CONVERSATION }).locator(".message--assistant").last();

test.describe("answering in the browser", () => {
  test("offers once, fetches with a strip, then answers in the tab", async ({ page }) => {
    await installEdgeDevice(page);
    const sent = watchRemoteTurns(page);
    await openStudio(page);

    // The ask: one sentence, the size, two buttons, above the composer.
    const offer = offerStrip(page);
    await expect(offer).toBeVisible();
    await expect(offer.getByText(/about 1.3 GB, once/)).toBeVisible();
    await expect(offer.getByRole("button", { name: "Not now" })).toBeVisible();

    await offer.getByRole("button", { name: "Answer in this browser" }).click();

    // The same dock slot narrates the fetch instead of a second strip appearing.
    await expect(dock(page).filter({ hasText: /Fetching Llama 3.2 1B/ })).toBeVisible();
    await expect(dock(page).filter({ hasText: "answering in this tab now" })).toBeVisible();
    await expect(offer).toHaveCount(0);

    await dismissConnectorSuggestion(page);
    const composer = page.getByRole("textbox", { name: COMPOSER });
    await composer.fill("Where do I start?");
    await page.getByRole("button", { name: "Send message" }).click();

    await expect(reply(page)).toContainText("Start with the job, then the outcome.");
    // The reply names its own brain, and it is the only provenance line on it.
    await expect(reply(page).getByRole("button", { name: "Answered in this browser" })).toBeVisible();
    await expect(reply(page).getByText(/Local draft/i)).toHaveCount(0);
    // Nothing left this tab: the turn was never posted to the sidecar.
    expect(sent).toEqual([]);

    // Durable: reload, and the answer is still yes — no second ask, still local.
    await page.reload();
    await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
    await expect(offerStrip(page)).toHaveCount(0);
  });

  test("\"Not now\" is an answer the studio respects across reloads", async ({ page }) => {
    await installEdgeDevice(page);
    await openStudio(page);

    const offer = offerStrip(page);
    await expect(offer).toBeVisible();
    await offer.getByRole("button", { name: "Not now" }).click();
    // Going quiet is the studio claiming it believes the answer, and nothing
    // else may make it quiet — so the reload below is not racing the write.
    await expect(offer).toHaveCount(0);

    await page.reload();
    await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
    await expect(offerStrip(page)).toHaveCount(0);
  });

  test("a key appearing later takes the turns back", async ({ page }) => {
    await installEdgeDevice(page);
    const sent = watchRemoteTurns(page);
    await openStudio(page);

    await offerStrip(page)
      .getByRole("button", { name: "Answer in this browser" })
      .click();
    await expect(dock(page).filter({ hasText: "answering in this tab now" })).toBeVisible();

    // The person pastes a key and reloads. Consent is still granted and a tier
    // is still on disk — and that is exactly what must *not* keep the turns
    // here: routing follows the endpoint, not the flag.
    await page.evaluate(() => {
      window.localStorage.setItem(
        "studio.settings",
        JSON.stringify({
          base_url: "http://127.0.0.1:9999/v1",
          api_key: "sk-test",
          model_name: "some-paid-model",
          mcp_url: "http://127.0.0.1:8000/mcp",
        }),
      );
    });
    await page.reload();

    const composer = page.getByRole("textbox", { name: COMPOSER });
    await expect(composer).toBeVisible();
    await dismissConnectorSuggestion(page);
    await composer.fill("Where do I start?");
    await page.getByRole("button", { name: "Send message" }).click();

    await expect.poll(() => sent.length, { timeout: 15_000 }).toBeGreaterThan(0);
    // The reply came back from the server path, and it does not claim this tab.
    await expect(reply(page).getByRole("button", { name: "Copy reply" })).toBeVisible();
    await expect(reply(page).getByRole("button", { name: "Answered in this browser" })).toHaveCount(
      0,
    );
  });
});
