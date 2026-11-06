import { useState, type FormEvent } from "react";

import { useStudio } from "../../state/StudioContext";

/**
 * The visit that follows the visit.
 *
 * Two halves of one loop, in the dock where the composer is: after a turn that
 * put something on the screen, it asks what came back for; and while the store
 * still holds a promise, it asks whether it happened. Answering is a sentence
 * that becomes evidence. Not answering is a date, or silence — never a claim.
 *
 * It is an aside in the thread, not a modal: it can never block the next turn.
 */
export function NextStepPrompt() {
  const {
    openNextStep,
    lastTurnProducedSurface,
    nextStepDismissed,
    dismissNextStep,
    setNextStep,
    answerNextStep,
  } = useStudio();
  const [promise, setPromise] = useState("");
  const [answer, setAnswer] = useState<"yes" | "later" | "not-yet" | null>(null);
  const [sentence, setSentence] = useState("");
  const [day, setDay] = useState("");

  // A step the studio cannot read back as a sentence is not a promise it may
  // ask about, so the greeting and this aside fall silent together.
  const step = openNextStep?.text.trim() ? openNextStep : null;

  if (nextStepDismissed) {
    return null;
  }
  if (!step && !lastTurnProducedSurface) {
    return null;
  }

  function remember(event: FormEvent) {
    event.preventDefault();
    const text = promise.trim();
    if (!text) {
      return;
    }
    setPromise("");
    void setNextStep(text);
  }

  function keepAsEvidence(event: FormEvent) {
    event.preventDefault();
    const said = sentence.trim();
    if (!said || !step) {
      return;
    }
    setAnswer(null);
    setSentence("");
    void answerNextStep(step.id, { done: true, sentence: said });
  }

  function move(event: FormEvent) {
    event.preventDefault();
    if (!step || !day) {
      return;
    }
    // The store refuses a reminder with no zone, so the date picked here is
    // taken at midnight in the zone this browser is standing in.
    const dueAt = new Date(`${day}T00:00:00`).toISOString();
    setAnswer(null);
    setDay("");
    void answerNextStep(step.id, { action: "reschedule", dueAt });
  }

  function drop() {
    if (!step) {
      return;
    }
    setAnswer(null);
    void answerNextStep(step.id, { action: "drop" });
  }

  function keepAsking() {
    // The one answer that changes nothing: the step stays open and the question
    // waits for the next visit.
    setAnswer(null);
    dismissNextStep();
  }

  return (
    <aside
      className="guidance guidance--step"
      aria-label={step ? "What you said you would do" : "Something to come back for"}
      aria-live="polite"
    >
      {step ? (
        <>
          <p className="guidance__line">
            {/* Quoted, not restated: on the first screen the greeting already said
                the sentence, and two copies of it would be one too many. */}
            “{step.text.trim()}” — did it happen?
          </p>
          {answer === null ? (
            <div className="guidance__row">
              <button type="button" className="guidance__action" onClick={() => setAnswer("yes")}>
                Yes
              </button>
              <button
                type="button"
                className="guidance__action"
                onClick={() => setAnswer("not-yet")}
              >
                Not yet
              </button>
            </div>
          ) : answer === "yes" ? (
            <form className="guidance__row" onSubmit={keepAsEvidence}>
              <label className="guidance__label" htmlFor="next-step-sentence">
                What happened?
              </label>
              <input
                className="guidance__input"
                id="next-step-sentence"
                value={sentence}
                maxLength={500}
                onChange={(event) => setSentence(event.target.value)}
              />
              <button type="submit" className="guidance__action">
                Keep it as evidence
              </button>
            </form>
          ) : answer === "later" ? (
            <form className="guidance__row" onSubmit={move}>
              <label className="guidance__label" htmlFor="next-step-when">
                Ask again on
              </label>
              <input
                className="guidance__input"
                id="next-step-when"
                type="date"
                value={day}
                onChange={(event) => setDay(event.target.value)}
              />
              <button type="submit" className="guidance__action">
                Set the date
              </button>
            </form>
          ) : (
            <div className="guidance__row">
              <button type="button" className="guidance__action" onClick={keepAsking}>
                Keep asking
              </button>
              <button type="button" className="guidance__action" onClick={() => setAnswer("later")}>
                Later
              </button>
              <button type="button" className="guidance__action" onClick={drop}>
                Drop it
              </button>
            </div>
          )}
        </>
      ) : (
        <>
          <p className="guidance__line">Want this remembered for next time?</p>
          <form className="guidance__row" onSubmit={remember}>
            <label className="guidance__label" htmlFor="next-step-promise">
              What will you come back for?
            </label>
            <input
              className="guidance__input"
              id="next-step-promise"
              value={promise}
              maxLength={500}
              placeholder="One thing, in your own words"
              onChange={(event) => setPromise(event.target.value)}
            />
            <button type="submit" className="guidance__action">
              Remember it
            </button>
          </form>
        </>
      )}
      <button
        type="button"
        className="guidance__dismiss"
        aria-label="Don't ask again this visit"
        title="Quiet for this visit only"
        onClick={dismissNextStep}
      >
        ✕
      </button>
    </aside>
  );
}
