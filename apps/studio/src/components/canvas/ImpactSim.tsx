import { useMemo, useState } from "react";

import { useStudio } from "../../state/StudioContext";

export function ImpactSim() {
  const { canvas, sendMessage, pushToast, pendingSimOutcome, clearPendingSimOutcome } = useStudio();

  const outcomes = useMemo(() => canvas?.outcomes ?? [], [canvas]);
  const options = useMemo(
    () =>
      outcomes.map(
        (outcome) => `${outcome.id ?? "O"}: ${outcome.statement ?? "Untitled Outcome"}`,
      ),
    [outcomes],
  );

  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [bet, setBet] = useState("Automated Secret Sync Daemon (Zero-Touch Ambient Sync)");

  const pendingOption = useMemo(
    () =>
      pendingSimOutcome
        ? options.find((option) => option.startsWith(`${pendingSimOutcome}:`))
        : undefined,
    [pendingSimOutcome, options],
  );
  const selected =
    pendingOption ?? (selectedOption && options.includes(selectedOption) ? selectedOption : options[0] ?? "");

  function onSelect(value: string) {
    setSelectedOption(value);
    if (pendingSimOutcome) {
      clearPendingSimOutcome();
    }
  }

  async function declare() {
    await sendMessage(
      `Draft a Product Decision Record (PDR) for approved bet: '${bet}' target outcome '${selected}'.`,
    );
    pushToast("success", "Product Decision Record drafted by the agent!");
  }

  return (
    <section className="fade-in">
      <h2 className="section-title">WYSIWYG of Human Impact</h2>
      <p className="caption">
        What You See Is What They Experience. Simulate the collapse of human friction before writing code.
      </p>

      <div className="studio-field">
        <label htmlFor="sim-outcome">Target Desired Outcome</label>
        <select
          id="sim-outcome"
          className="studio-select"
          value={selected}
          onChange={(event) => onSelect(event.target.value)}
        >
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>

      <div className="studio-field">
        <label htmlFor="sim-bet">Feature Bet / Concept</label>
        <input
          id="sim-bet"
          className="studio-input"
          value={bet}
          onChange={(event) => setBet(event.target.value)}
        />
      </div>

      <h3 className="section-title" style={{ fontSize: "0.95rem", marginTop: 16 }}>
        Reality Simulation Preview
      </h3>
      <div className="studio-form-grid">
        <div
          className="fade-in"
          style={{
            background: "rgba(239, 68, 68, 0.08)",
            border: "1px solid rgba(239, 68, 68, 0.25)",
            padding: 14,
            borderRadius: "var(--studio-radius-sm)",
          }}
        >
          <span
            className="studio-pill"
            style={{ background: "rgba(239,68,68,0.2)", color: "#f87171" }}
          >
            BEFORE (Current Reality)
          </span>
          <ul style={{ marginTop: 10, paddingLeft: 18, fontSize: "0.88rem", color: "#cbd5e1" }}>
            <li><b>45 min</b> manual copy-paste across environments.</li>
            <li><b>14% deploy failure</b> caused by configuration drift.</li>
            <li>400 engineering teams suffer daily friction.</li>
          </ul>
        </div>
        <div
          className="fade-in"
          style={{
            background: "rgba(16, 185, 129, 0.08)",
            border: "1px solid rgba(16, 185, 129, 0.25)",
            padding: 14,
            borderRadius: "var(--studio-radius-sm)",
          }}
        >
          <span className="studio-pill pill-green">AFTER (Simulated Value)</span>
          <ul style={{ marginTop: 10, paddingLeft: 18, fontSize: "0.88rem", color: "#cbd5e1" }}>
            <li><b>&lt; 30 seconds</b> automated propagation.</li>
            <li><b>Zero human steps</b>. Ambient synchronization.</li>
            <li><b>3,000 hours</b> eliminated per month.</li>
          </ul>
        </div>
      </div>

      <div className="metric-grid" style={{ marginTop: 16 }}>
        <div className="studio-metric">
          <div className="studio-metric__label">Time-to-Value Shift</div>
          <div className="studio-metric__value">-90%</div>
          <div className="studio-metric__delta">Friction Eliminated</div>
        </div>
        <div className="studio-metric">
          <div className="studio-metric__label">Satisfaction Projection</div>
          <div className="studio-metric__value">8.9 / 10</div>
          <div className="studio-metric__delta">+5.8 pts</div>
        </div>
        <div className="studio-metric">
          <div className="studio-metric__label">Implementation Risk</div>
          <div className="studio-metric__value">Low</div>
          <div className="studio-metric__delta">Non-breaking</div>
        </div>
      </div>

      <button
        type="button"
        className="studio-button"
        style={{ width: "100%", marginTop: 16 }}
        onClick={() => void declare()}
      >
        🚀 Declare Intent ➔ Approve Bet &amp; Draft PDR
      </button>
    </section>
  );
}
