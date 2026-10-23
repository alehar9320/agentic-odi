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
          <span style={{ whiteSpace: "pre-wrap", flex: 1 }}>{toast.message}</span>
          <button
            type="button"
            aria-label="Dismiss notification"
            onClick={() => dismissToast(toast.id)}
            style={{ minHeight: 44, minWidth: 44, padding: 0, fontSize: "1.2rem", lineHeight: 1 }}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
