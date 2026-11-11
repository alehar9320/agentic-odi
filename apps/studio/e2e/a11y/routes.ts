import { expect, type Page } from "@playwright/test";

import { lens, rail, runCommand } from "../helpers";

/**
 * How the contrast gate reaches each surface, through the shipped UI.
 *
 * The command is the route for most of them: the rail only shows a chip once
 * the thread has produced that artifact, which is a fact about the data rather
 * than about the surface being painted. Where no command exists — the memory
 * count, the catch-up bell, the settings button — the gate clicks what a person
 * clicks, and the seed that makes the chip appear is part of that test.
 */

type Opener = (page: Page) => Promise<void>;

const openLens: Opener = async (page) => {
  await expect(lens(page)).toBeVisible();
};

export const ROUTES: Record<string, Opener> = {
  home: async () => {},
  landscape: (page) => runCommand(page, "/landscape"),
  records: (page) => runCommand(page, "/records"),
  brief: (page) => runCommand(page, "/brief"),
  jobmap: (page) => runCommand(page, "/jobmap"),
  segments: (page) => runCommand(page, "/segments"),
  evidence: (page) => runCommand(page, "/evidence"),
  // The one lens with no command of its own: the rail counts what the agent has
  // learned, so this screen needs seeded memory and a real click.
  memory: async (page) => {
    await rail(page).getByRole("button", { name: /^What I know,/ }).click();
    await openLens(page);
  },
  catchup: async (page) => {
    await page.locator(".bar__bell").click();
    await openLens(page);
  },
  // With no model configured, `/capture` opens the by-hand form instead of
  // starting a sentence with a model — and the form is the surface to measure.
  capture: (page) => runCommand(page, "/capture"),
  settings: async (page) => {
    await page.getByRole("button", { name: "Open settings" }).click();
    await expect(page.getByRole("main")).toBeVisible();
  },
};
