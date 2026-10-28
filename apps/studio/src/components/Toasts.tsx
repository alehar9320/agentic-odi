import { useStudio } from "../state/StudioContext";

export function Toasts() {
  const { toasts, dismissToast } = useStudio();

  if (!toasts.length) {
    return null;
  }

  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div className={} key={toast.id}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
            <span style={{ whiteSpace: "pre-wrap", flex: 1 }}>{toast.message}</span>
            <button
              type="button"
              className="studio-button studio-button--ghost"
              aria-label="Dismiss notification"
              onClick={() => dismissToast(toast.id)}
              style={{ minHeight: 44, minWidth: 44, padding: 0, fontSize: "1.2rem", lineHeight: 1 }}
            >
              ×
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
