export function ShortcutsSection({ headingId = "customize-shortcuts-heading" }: { headingId?: string }) {
  return (
    <section className="customize__section" aria-labelledby={headingId}>
      <h3 className="settings__title" id={headingId}>Shortcuts</h3>
      <dl className="customize__shortcuts">
        <div><dt>Enter</dt><dd>Send a message</dd></div>
        <div><dt>Shift + Enter</dt><dd>Add a line</dd></div>
        <div><dt>/</dt><dd>Open the command palette</dd></div>
        <div><dt>Up / Down / Enter / Tab / Escape</dt><dd>Navigate the command palette</dd></div>
        <div><dt>Escape</dt><dd>Stop a running reply before closing a panel</dd></div>
      </dl>
    </section>
  );
}
