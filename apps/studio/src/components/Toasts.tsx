import { useStudio } from "../state/StudioContext";

export function Toasts() {
  const { toasts, dismissToast } = useStudio();

  if (!toasts.length) {
    return null;
  }

  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map((toast) => (
        <div className={`toast toast--${toast.kind}`} key={toast.id}>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span style={{ whiteSpace: "pre-wrap" }}>{toast.message}</span>
            <button
              type="button"
              className="studio-button studio-button--ghost"
              aria-label="Dismiss notification"
              onClick={() => dismissToast(toast.id)}
              style={{ padding: "0 6px" }}
            >
              ×
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
