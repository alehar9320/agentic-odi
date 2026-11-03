import { useCallback, useEffect, useState } from "react";

import { formatGB, PROGRESSION } from "../edge/ladder";
import { edgeManager, hasModelEndpoint, type EdgePanelState } from "../edge/manager";
import { setFeatureOverride } from "../features/flags";
import { useStudio } from "../state/StudioContext";
import { MeterBar } from "../ui/primitives";

const STATUS_COPY: Record<EdgePanelState["tiers"][number]["status"], string> = {
  empty: "not downloaded",
  cached: "on this device",
  active: "answering",
};

/**
 * The control surface for the browser model: the switch, the consent answer,
 * what is on disk, and what a tier would cost to fetch. It reads one snapshot
 * from `EdgeManager` and never touches WebLLM, the ladder gates, or IndexedDB,
 * so the section stays a view rather than a second owner of the state.
 */
export function EdgeModelSection() {
  const { settings } = useStudio();
  const [panel, setPanel] = useState<EdgePanelState | null>(null);
  const [storage, setStorage] = useState<{ usage: number; quota: number } | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [spokeTooSoon, setSpokeTooSoon] = useState(false);

  const refresh = useCallback(() => {
    // A snapshot of the ladder arrives when the browser's storage answers, never
    // synchronously — so nothing here can cascade a render inside an effect.
    void edgeManager.panelState().then(setPanel);
  }, []);

  useEffect(() => {
    refresh();
    return edgeManager.addNoticeListener((notice) => {
      // Percent ticks change nothing on this panel; a landing or a freeing does.
      if (notice.kind !== "downloading") {
        refresh();
      }
    });
  }, [refresh]);

  useEffect(() => {
    if (!navigator.storage?.estimate) {
      return;
    }
    let cancelled = false;
    void navigator.storage
      .estimate()
      .then((value) => {
        if (!cancelled && typeof value.usage === "number" && typeof value.quota === "number") {
          setStorage({ usage: value.usage, quota: value.quota });
        }
      })
      .catch(() => {
        // A browser that won't say what it is keeping shows no number.
      });
    return () => {
      cancelled = true;
    };
  }, [panel]);

  async function sayYes() {
    setPending("consent");
    setSpokeTooSoon(false);
    try {
      const tier = await edgeManager.grantAndStart();
      setSpokeTooSoon(tier === null && (await edgeManager.servedTier()) === null);
    } finally {
      setPending(null);
      refresh();
    }
  }

  async function free(tier: EdgePanelState["tiers"][number]) {
    setPending(`free:${tier.id}`);
    try {
      await edgeManager.freeTier(tier.id);
    } finally {
      setPending(null);
      refresh();
    }
  }

  const entry = panel?.tiers.find((tier) => tier.eligible) ?? null;
  const offerLabel = entry
    ? `Download ${entry.label} — about ${formatGB(entry.approxBytes)}, once`
    : null;

  return (
    <section className="settings__edge" aria-labelledby="settings-edge-heading">
      <h3 className="settings__title" id="settings-edge-heading">
        Answers in this browser
      </h3>
      <label className="update-settings__toggle">
        <input
          type="checkbox"
          checked={panel?.flagEnabled ?? false}
          disabled={panel === null}
          onChange={(event) => {
            setFeatureOverride("edgeModel", event.target.checked);
            refresh();
          }}
        />
        <span>Let this browser run a model</span>
      </label>
      <p className="muted">
        With no model endpoint answering, replies are generated on this device. Nothing is sent to
        anyone else.
      </p>

      {panel === null ? (
        <p className="muted">Checking this browser…</p>
      ) : (
        <>
          {!panel.flagEnabled ? (
            <p className="muted">
              Switched off — nothing will be downloaded or run until you turn it on.
            </p>
          ) : panel.consent === "granted" ? (
            <div className="settings__edge-consent">
              <p className="muted">
                You said yes. {hasModelEndpoint(settings)
                  ? "Your model endpoint is answering for now; clear it and this takes over."
                  : "Replies run here as soon as a tier is on this device."}
              </p>
              <button
                type="button"
                className="button button--ghost"
                disabled={pending !== null}
                onClick={() => {
                  setPending("consent");
                  void edgeManager.decline().finally(() => {
                    setPending(null);
                    refresh();
                  });
                }}
              >
                Stop answering here
              </button>
              <p className="muted">
                Your downloads stay on this device until you free them below.
              </p>
            </div>
          ) : panel.downloadable ? (
            <div className="settings__edge-consent">
              <p className="muted">
                {panel.consent === "denied"
                  ? "You turned this down earlier. You can change that here."
                  : "This browser has nothing to answer with yet."}
              </p>
              <button
                type="button"
                className="button"
                disabled={pending !== null}
                onClick={() => void sayYes()}
              >
                {offerLabel}
              </button>
              {spokeTooSoon ? (
                <p className="muted">
                  Nothing started in this tab — another tab may already be fetching it, or this
                  browser is waiting for a visible, idle moment off a Save Data connection.
                </p>
              ) : null}
            </div>
          ) : (
            <p className="muted">
              This browser can't host any of these models, so there is nothing to download. The
              reasons are on each tier below.
            </p>
          )}

          <ul className="connection-list">
            {panel.tiers.map((tier) => (
              <li key={tier.id}>
                <span
                  className={`status-dot${
                    tier.status === "active" ? "" : tier.status === "empty" ? " is-unknown" : " is-warn"
                  }`}
                />
                <span>{tier.label}</span>
                <span className="connection-list__value">
                  {tier.eligible
                    ? `${STATUS_COPY[tier.status]} · about ${formatGB(tier.approxBytes)}`
                    : (tier.reason ?? "not for this device")}
                </span>
                {tier.status !== "empty" ? (
                  <button
                    type="button"
                    className="quiet-action"
                    aria-label={`Free the storage ${tier.label} is using`}
                    disabled={pending !== null}
                    onClick={() => void free(tier)}
                  >
                    {pending === `free:${tier.id}` ? "Freeing…" : "Free storage"}
                  </button>
                ) : null}
              </li>
            ))}
          </ul>

          <MeterBar
            label="Answers served here, toward the next tier"
            value={panel.usage.edgeTurns}
            max={PROGRESSION.edgeTurns}
          />
          <p className="muted">
            {panel.usage.edgeTurns >= PROGRESSION.edgeTurns
              ? "Earned. The stronger tier arrives the next time this tab is idle."
              : `${panel.usage.turnsToNext} more answer${
                  panel.usage.turnsToNext === 1 ? "" : "s"
                }, or ${Math.ceil(panel.usage.secondsToNext / 60)} minutes of streamed replies, earns the next tier.`}
          </p>

          {storage !== null && storage.quota > 0 ? (
            <p className="muted">
              This site is keeping {formatGB(storage.usage)} of the {formatGB(storage.quota)} it
              can use.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
