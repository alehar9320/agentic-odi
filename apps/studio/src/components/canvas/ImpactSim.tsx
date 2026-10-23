import { useMemo, useState } from "react";

import { useStudio } from "../../state/StudioContext";

export function ImpactSim() {
  const { canvas, sendMessage, pushToast, pendingSimOutcome, clearPendingSimOutcome, closePanel } =
    useStudio();

  const outcomes = useMemo(() => canvas?.outcomes ?? [], [canvas]);
  const options = useMemo(
    () =>
      outcomes.map(
        (outcome) => `${outcome.id ?? "O"}: ${outcome.statement ?? "Untitled outcome"}`,
      ),
    [outcomes],
  );

  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [bet, setBet] = useState("Automated secret sync daemon (zero-touch)");

  const pendingOption = useMemo(
    () =>
      pendingSimOutcome
        ? options.find((option) => option.startsWith(`${pendingSimOutcome}:`))
        : undefined,
    [pendingSimOutcome, options],
  );
  const selected =
    pendingOption ??
    (selectedOption && options.includes(selectedOption) ? selectedOption : options[0] ?? "");

  function onSelect(value: string) {
    setSelectedOption(value);
    if (pendingSimOutcome) {
      clearPendingSimOutcome();
    }
  }

  async function declare() {
    // Hand the stage back to the conversation so the reply is visible.
    closePanel();
    await sendMessage(
      `Draft a Product Decision Record (PDR) for approved bet: '${bet}' target outcome '${selected}'.`,
    );
    pushToast("success", "Product Decision Record drafted by the agent!");
  }

  return (
    <section className="stack">
      <div className="field">
        <label htmlFor="sim-outcome">Target outcome</label>
        <select
          id="sim-outcome"
          className="select"
          value={selected}
          onChange={(event) => onSelect(event.target.value)}
        >
          {options.length ? (
            options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))
          ) : (
            <option value="">No outcomes captured yet</option>
          )}
        </select>
      </div>

      <div className="field">
        <label htmlFor="sim-bet">Bet you want to test</label>
        <input
          id="sim-bet"
          className="input"
          value={bet}
          onChange={(event) => setBet(event.target.value)}
        />
      </div>

      <div className="before-after">
        <div className="compare compare--before">
          <span className="compare__label">Before</span>
          <ul>
            <li>
              <b>45 minutes</b> of manual copy-paste across environments.
            </li>
            <li>
              <b>14%</b> of deploys fail from configuration drift.
            </li>
            <li>400 teams feel the friction every week.</li>
          </ul>
        </div>
        <div className="compare compare--after">
          <span className="compare__label">After</span>
          <ul>
            <li>
              <b>&lt; 30 seconds</b>, propagated in the background.
            </li>
            <li>
              <b>Zero</b> human steps. Ambient credentials.
            </li>
            <li>
              <b>3,000 hours</b> of agony removed per month.
            </li>
          </ul>
        </div>
      </div>

      <p className="empty-note">
        Figures are illustrative until evidence is connected — the shape of the story is the point.
      </p>

      <button type="button" className="button button--block" onClick={() => void declare()}>
        Approve bet and draft the PDR
      </button>
    </section>
  );
}
