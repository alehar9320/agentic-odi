import { configure } from "@chromatic-com/vitest";
import { expect, it } from "vitest";
import { render } from "vitest-browser-react";

import "../../styles/theme.css";
import { IntroSummary } from "./IntroConversation";

// The build table would otherwise name this `IntroConversation.visual` after
// the test file rather than the surface it covers.
configure({ title: "IntroConversation" });

// One snapshot per build: the accepted state of the brief is the card a person
// reads before saying "looks like me".
it("shows the brief as five editable lines", async () => {
  const screen = await render(
    <div style={{ width: 720, padding: 24 }}>
      <IntroSummary
        answers={{
          role: "I'm the PM for the deploy tool; the team is four engineers and a designer.",
          customer: "The on-call platform engineer at 2am.",
          win: "Ship a service without hand-copying config.",
          friction: "A missed key costs a deploy day.",
          evidence: "Nine onboarding calls and a very angry ticket.",
        }}
        team="four engineers and a designer"
        editing={null}
        editValue=""
        onBeginEdit={() => {}}
        onEditChange={() => {}}
        onCommit={() => {}}
        onCancel={() => {}}
        onAccept={() => {}}
        onSkip={() => {}}
      />
    </div>,
  );

  await expect
    .element(screen.getByRole("heading", { name: "Does this look like you?" }))
    .toBeVisible();
  await expect.element(screen.getByRole("button", { name: "Looks like me" })).toBeVisible();
  await expect.element(screen.getByText(/Nine onboarding calls/)).toBeVisible();
});
