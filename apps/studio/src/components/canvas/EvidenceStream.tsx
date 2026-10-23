export function EvidenceStream() {
  return (
    <section className="fade-in">
      <h2 className="section-title">Customer Evidence Stream</h2>
      <p className="caption">
        Live customer signals streaming from Gong, Slack, and product telemetry via MCP.
      </p>

      <div className="evidence-box fade-in">
        <span style={{ fontWeight: 700, color: "#fbbf24", display: "block", marginBottom: 4 }}>
          🎙️ Gong Call #104 (Tech Lead - FinTech Corp)
        </span>
        <p style={{ fontStyle: "italic", color: "#e2e8f0", lineHeight: 1.45 }}>
          &quot;We had a junior engineer push code that failed staging because the Stripe secret
          wasn&apos;t copied over. It took 3 senior engineers 2 hours to figure out why the cluster
          wouldn&apos;t spin up.&quot;
        </p>
        <span style={{ fontSize: "0.78rem", color: "#94a3b8", display: "block", marginTop: 8 }}>
          Linked to: <b>JOB-402 / Outcome O-1</b> • Severity: High
        </span>
      </div>

      <div
        className="evidence-box fade-in"
        style={{ borderLeftColor: "#34d399", marginTop: 12 }}
      >
        <span style={{ fontWeight: 700, color: "#34d399", display: "block", marginBottom: 4 }}>
          💬 Customer Slack Friction Alert (#incident-deployments)
        </span>
        <p style={{ fontStyle: "italic", color: "#e2e8f0", lineHeight: 1.45 }}>
          &quot;Third time this week staging broke after secret rotation. We need automated
          synchronization.&quot;
        </p>
        <span style={{ fontSize: "0.78rem", color: "#94a3b8", display: "block", marginTop: 8 }}>
          Linked to: <b>JOB-402 / Outcome O-2</b> • Severity: Critical
        </span>
      </div>

      <p className="caption" style={{ marginTop: 16 }}>
        💡 <i>External MCP connectors continuously sync customer signals directly into the SQLite Intent Store.</i>
      </p>
    </section>
  );
}
