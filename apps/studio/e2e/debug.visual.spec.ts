import { test, expect } from "@playwright/test";
import { seedSampleCanvas, setTheme } from "./visual/fixtures";

test("debug 390 brief", async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setTheme(page, "dark");
  await seedSampleCanvas(page, request);

  const composer = page.getByRole("textbox", { name: "Message the studio" });
  await composer.click();
  await composer.fill("/brief");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "/tmp/debug-390-brief.png", fullPage: true });

  const lens = page.getByRole("complementary", { name: "Decision brief" });
  console.log("brief lens count:", await lens.count());
  if (await lens.count() > 0) {
    console.log("brief lens visible:", await lens.isVisible());
  }
});