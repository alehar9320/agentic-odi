import { expect, test, type Page } from "@playwright/test";

import { COMPOSER, CONVERSATION, dismissConnectorSuggestion, openStudio } from "./helpers";
import { failNextFetch, holdNextFetch, installEdgeDevice, releaseNextFetch } from "./edgeDevice";

/**
 * The browser tier, end to end.
 *
 * What this proves: that the seams are wired — a first visit with no key gets
 * asked once, the yes starts a fetch the dock narrates, a fetch that throws says
 * so and hands the same download back, the answer that lands is labelled as
 * coming from this browser, a refusal is remembered, and a key appearing later
 * takes the turns back. It drives the real manager, scheduler, IndexedDB state,
 * notice bus, banner dock, composer routing and transcript labelling in a real
 * Chromium against a real sidecar.
 *
 * What it does NOT prove: WebLLM. CI has no GPU and no model weights, so the
 * engine is the fake in `edgeDevice.ts`. The real-GPU path — a 1.3 GB download
 * actually landing, prefill jank, two tabs competing for a *loaded* model
 * rather than for the fetch, the memory ceiling on iOS — is the handoff list in
 * `docs/superpowers/plans/2026-11-01-edge-llm-ladder-remaining-work.md`, not
 * something this file can assert. What the last scenario does prove, in a real
 * browser, is the two seams that used to be argued from a process-level test:
 * `BroadcastChannel` between two live tabs, and `navigator.locks` refusing a
 * second tab that asked for the engine while the first held it.
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

  test("an answer the tab produced is still there after a reload, still labelled", async ({
    page,
  }) => {
    await installEdgeDevice(page);
    await openStudio(page);

    await offerStrip(page)
      .getByRole("button", { name: "Answer in this browser" })
      .click();
    await expect(dock(page).filter({ hasText: "answering in this tab now" })).toBeVisible();

    await dismissConnectorSuggestion(page);
    await page.getByRole("textbox", { name: COMPOSER }).fill("Where do I start?");
    await page.getByRole("button", { name: "Send message" }).click();

    const asked = reply(page);
    await expect(asked).toContainText("Start with the job, then the outcome.");

    // The person closes the tab and comes back. What the browser answered is
    // the only copy of that work there is: no key was configured, so no server
    // ever saw the turn. Losing it here loses their research.
    await page.reload();
    await expect(page.getByRole("textbox", { name: COMPOSER })).toBeVisible();
    // The newest exchange, not "the only copy of that question": a reload merges
    // this browser's rows into whatever the server holds, and an earlier visit
    // against the same sidecar asked this same question remotely. Both are on
    // screen because both happened — and this browser's answer is last, which is
    // the ordering claim the merge has to keep.
    await expect(
      page.getByRole("log", { name: CONVERSATION }).locator(".message--user").last(),
    ).toContainText("Where do I start?");
    const remembered = reply(page);
    await expect(remembered).toContainText("Start with the job, then the outcome.");
    await expect(
      remembered.getByRole("button", { name: "Answered in this browser" }),
    ).toBeVisible();
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

  test("a download that did not land says so, and the retry it offers works", async ({ page }) => {
    // Weights fail for ordinary reasons — the network drops, a CDN refuses, the
    // browser rejects the cache. What the studio must not do is keep narrating a
    // download that stopped, or retire the one ask and leave no way back.
    await installEdgeDevice(page);
    const sent = watchRemoteTurns(page);
    await openStudio(page);

    await failNextFetch(page);
    await offerStrip(page)
      .getByRole("button", { name: "Answer in this browser" })
      .click();
    await expect(dock(page).filter({ hasText: /Fetching Llama 3.2 1B/ })).toBeVisible();

    // The fetch strip stops claiming, and the failure names itself once.
    await expect(dock(page).filter({ hasText: /didn't finish/i })).toBeVisible();
    await expect(dock(page).filter({ hasText: /Fetching Llama 3.2 1B/ })).toHaveCount(0);
    // And the ask does not come back: the consent question is answered, whatever
    // the download did.
    await expect(offerStrip(page)).toHaveCount(0);

    await dock(page)
      .filter({ hasText: /didn't finish/i })
      .getByRole("button", { name: "Try the download again" })
      .click();
    await expect(dock(page).filter({ hasText: "answering in this tab now" })).toBeVisible();

    await dismissConnectorSuggestion(page);
    await page.getByRole("textbox", { name: COMPOSER }).fill("Where do I start?");
    await page.getByRole("button", { name: "Send message" }).click();

    const answered = reply(page);
    await expect(answered).toContainText("Start with the job, then the outcome.");
    await expect(
      answered.getByRole("button", { name: "Answered in this browser" }),
    ).toBeVisible();
    expect(sent).toEqual([]);
  });

  test("two tabs, one browser: one ask, one fetch, both answering", async ({ context }) => {
    // Two pages in ONE context share an origin's storage and its
    // `navigator.locks`, which is the whole reason this scenario exists: the
    // cross-tab bus and the engine lock could previously only be exercised as
    // two objects in one process. Here they are two pages in one Chromium.
    const first = await context.newPage();
    const second = await context.newPage();
    await installEdgeDevice(first);
    await installEdgeDevice(second);
    const sentFromSecond = watchRemoteTurns(second);
    await openStudio(first);
    await openStudio(second);

    // One consent question per browser, and both tabs are asking it, because
    // both are reading the same unanswered record.
    await expect(offerStrip(first)).toBeVisible();
    await expect(offerStrip(second)).toBeVisible();

    // The fetch is held open on purpose. The lock is only held while a model is
    // loading, so without this the second tab would arrive after the download
    // was over and meet no contention at all.
    await holdNextFetch(first);
    await offerStrip(first)
      .getByRole("button", { name: "Answer in this browser" })
      .click();
    await expect(dock(first).filter({ hasText: /Fetching Llama 3.2 1B/ })).toBeVisible();

    // The other tab is corrected with no reload, no turn and nothing typed: the
    // yes travelled over a real BroadcastChannel between two real pages.
    await expect(offerStrip(second)).toHaveCount(0);

    // Now say yes a second time, in the second tab, while the first still holds
    // the lock. The refusal is Chromium's own `navigator.locks` saying the name
    // is taken — not a stubbed `acquired: false`.
    //
    // The connector suggestion is real product behavior and it is a modal, and
    // this tab has been sitting idle through the other one's download, which is
    // long enough for it to arrive. It intercepts clicks, so it gets dismissed
    // the way a person would before anything else is pressed.
    await dismissConnectorSuggestion(second);
    await second.getByRole("button", { name: "Open settings" }).click();
    const browserSection = second.getByRole("region", { name: "Answers in this browser" });
    await browserSection
      .getByRole("button", { name: "Download Llama 3.2 1B — about 1.3 GB, once" })
      .click();
    await expect(browserSection.getByText(/nothing started in this tab/i)).toBeVisible();

    // Exactly one download for the pair: narrated where it is happening, and
    // silent where it was refused.
    await expect(dock(first).filter({ hasText: /Fetching Llama 3.2 1B/ })).toBeVisible();
    await expect(dock(second).filter({ hasText: /Fetching Llama/ })).toHaveCount(0);

    await releaseNextFetch(first);
    await expect(dock(first).filter({ hasText: "answering in this tab now" })).toBeVisible();

    // The second tab gets the state, not the celebration. It did not fetch
    // anything, so a toast saying "answering in this tab" would be a lie; the
    // tier row is the honest correction.
    await expect(browserSection.getByText(/answering · about 1.3 GB/)).toBeVisible();
    await expect(dock(second).filter({ hasText: "answering in this tab now" })).toHaveCount(0);

    // And the point of the ladder: the weights one tab pulled answer in the
    // other, without a byte leaving it.
    await dismissConnectorSuggestion(second);
    await second.getByRole("textbox", { name: COMPOSER }).fill("Where do I start?");
    await second.getByRole("button", { name: "Send message" }).click();

    const answered = reply(second);
    await expect(answered).toContainText("Start with the job, then the outcome.");
    await expect(
      answered.getByRole("button", { name: "Answered in this browser" }),
    ).toBeVisible();
    expect(sentFromSecond).toEqual([]);
  });
});
