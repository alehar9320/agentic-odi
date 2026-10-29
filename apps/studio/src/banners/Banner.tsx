import * as Toast from "@radix-ui/react-toast";

import type { Banner, BannerActionId } from "./types";

/** Critical and warning interrupt; info and success wait their turn. */
function isUrgent(banner: Banner): boolean {
  return banner.severity === "critical" || banner.severity === "warning";
}

/**
 * One banner, rendered on Radix's toast primitive so focus handling, swipe
 * dismissal, pause-on-hover, and the live region come from the library rather
 * than from hand-rolled timers and guessed ARIA.
 *
 * A persistent banner passes `Infinity` as its duration, which Radix treats as
 * "never expire" — the banner stays until its condition clears or the user
 * dismisses it.
 */
export function BannerRow({
  banner,
  onDismiss,
  onAction,
  onIntent,
}: {
  banner: Banner;
  onDismiss: (id: string) => void;
  onAction: (action: BannerActionId) => void;
  onIntent: (intent: string) => void;
}) {
  const urgent = isUrgent(banner);

  return (
    <Toast.Root
      className={`banner banner--${banner.severity}`}
      role={urgent ? "alert" : "status"}
      type={urgent ? "foreground" : "background"}
      duration={banner.life === "persistent" ? Infinity : banner.durationMs}
      open
      onOpenChange={(open) => {
        if (!open) {
          onDismiss(banner.id);
        }
      }}
    >
      <div className="banner__text">
        {banner.title ? (
          <Toast.Title className="banner__title">{banner.title}</Toast.Title>
        ) : null}
        {banner.body ? (
          <Toast.Description className="banner__body">{banner.body}</Toast.Description>
        ) : null}
      </div>

      {(banner.actions.length > 0 || banner.dismissible) && (
        <div className="banner__actions">
          {banner.actions.map((action) => (
            <Toast.Action
              key={action.label}
              altText={action.label}
              className={`banner__action banner__action--${action.tone}`}
              onClick={() => {
                if (action.action) {
                  onAction(action.action);
                } else if (action.intent) {
                  onIntent(action.intent);
                }
              }}
            >
              {action.label}
            </Toast.Action>
          ))}
          {banner.dismissible ? (
            <Toast.Close className="banner__dismiss" aria-label="Dismiss">
              Dismiss
            </Toast.Close>
          ) : null}
        </div>
      )}
    </Toast.Root>
  );
}
