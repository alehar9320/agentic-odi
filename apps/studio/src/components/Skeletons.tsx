export function GhostMetrics() {
  return (
    <div className="metrics" aria-hidden="true">
      <div className="skeleton skeleton--tile" />
      <div className="skeleton skeleton--tile" />
      <div className="skeleton skeleton--tile" />
    </div>
  );
}

export function GhostOpportunityCards({ count = 3 }: { count?: number }) {
  return (
    <div className="cards" aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <div className="card" key={index}>
          <div className="skeleton skeleton--line" style={{ width: 56 }} />
          <div className="skeleton skeleton--line" style={{ width: "78%", height: 18 }} />
          <div className="skeleton skeleton--line" style={{ width: "40%" }} />
        </div>
      ))}
    </div>
  );
}

export function GhostJobSteps({ count = 4 }: { count?: number }) {
  return (
    <div aria-hidden="true">
      {Array.from({ length: count }, (_, index) => (
        <div
          className="skeleton"
          key={index}
          style={{ height: 40, borderRadius: 10, marginBottom: 8 }}
        />
      ))}
    </div>
  );
}
