import { dismissInstall, isDismissed, isInstalled, offerInstall } from "../../../install";

/**
 * Offer to open the studio in its own window.
 *
 * The install prompt is browser-owned and local, so this section has nothing to
 * load and nothing to fail on its own. It renders nothing once the app is
 * installed or the offer has been dismissed.
 */
export function InstallSection() {
  const canInstall = !isInstalled() && !isDismissed();

  return (
    <section className="settings__install" aria-labelledby="settings-install-heading">
      <h3 className="settings__title" id="settings-install-heading">
        Install
      </h3>
      <p className="muted">
        Open the Studio in its own window. The site works offline and the window keeps your place
        when you reopen it.
      </p>
      {canInstall ? (
        <button
          type="button"
          className="button button--ghost"
          onClick={() => {
            const offered = offerInstall();
            if (!offered) {
              dismissInstall();
            }
          }}
        >
          Install app
        </button>
      ) : null}
    </section>
  );
}
