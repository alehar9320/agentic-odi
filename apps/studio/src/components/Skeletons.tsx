export function GhostMetrics() {
  return (
    <div className="metric-grid" aria-hidden="true">
      <div className="skeleton skeleton-metric" />
      <div className="skeleton skeleton-metric" />
      <div className="skeleton skeleton-metric" />
    </div>
  );
}

export function GhostOpportunityCards({ count = 3 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <div className="skeleton-card" key={index} aria-hidden="true">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="skeleton skeleton-line" style={{ width: 60, height: 16 }} />
            <div className="skeleton skeleton-badge" />
          </div>
          <div className="skeleton skeleton-title" style={{ marginTop: 10 }} />
          <div className="skeleton skeleton-line" style={{ width: "45%" }} />
        </div>
      ))}
    </>
  );
}

export function GhostJobSteps({ count = 4 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <div
          className="skeleton skeleton-line"
          key={index}
          style={{ height: 38, borderRadius: 8, marginBottom: 8 }}
          aria-hidden="true"
        />
      ))}
    </>
  );
}
