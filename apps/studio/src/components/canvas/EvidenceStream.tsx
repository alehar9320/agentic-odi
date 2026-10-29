export function EvidenceStream() {
  return (
    <section className="stack">
      <p className="notice">
        Sample quotes, shown for orientation. No Gong, Slack, or telemetry connector is wired up in
        this build.
      </p>

      <figure className="evidence">
        <figcaption>Gong call #104 · tech lead, fintech</figcaption>
        <blockquote>
          “We had a junior engineer push code that broke staging because the Stripe secret wasn’t
          copied over. Three senior engineers spent two hours on it. There has to be a better way
          than copy-pasting strings.”
        </blockquote>
        <span className="evidence__meta">Would link to JOB-402 / O-1 · severity high</span>
      </figure>

      <figure className="evidence">
        <figcaption>Slack · #incident-deployments</figcaption>
        <blockquote>
          “Third time this week staging broke after a secret rotation. We need automated
          synchronization.”
        </blockquote>
        <span className="evidence__meta">Would link to JOB-402 / O-2 · severity critical</span>
      </figure>
    </section>
  );
}
