import { UpdateSettings } from "../../../updater";

/**
 * Updates: the update row and nothing else.
 *
 * The updater owns its own provider-backed state, so a failure to check for an
 * update never reaches the sections beside it. The tour and the essay about how
 * the studio works live in About, so updater state is not repeated beside it and
 * the tour keeps exactly one entry point (#533).
 */
export function UpdatesSection() {
  return (
    <div className="settings__section">
      <UpdateSettings />
    </div>
  );
}
