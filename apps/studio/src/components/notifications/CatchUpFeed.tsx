import { useState } from "react";

import { useStudio } from "../../state/StudioContext";
import type { NotificationCategory, StudioNotification, WorkspacePanelId } from "../../types";
import { BoltIcon, CheckIcon, CompassIcon, RouteIcon, SignalIcon, SparkIcon } from "../icons";

type FilterType = "all" | "unread" | "outcome" | "signals";

function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  } catch {
    return "Recently";
  }
}

function getCategoryIcon(category: NotificationCategory) {
  switch (category) {
    case "outcome":
      return <CompassIcon size={16} />;
    case "simulation":
      return <BoltIcon size={16} />;
    case "evidence":
      return <SignalIcon size={16} />;
    case "job":
      return <RouteIcon size={16} />;
    case "insight":
    default:
      return <SparkIcon size={16} />;
  }
}

function getCategoryBadgeClass(category: NotificationCategory): string {
  switch (category) {
    case "outcome":
      return "badge--blue";
    case "simulation":
      return "badge--amber";
    case "evidence":
      return "badge--green";
    case "job":
    case "insight":
    default:
      return "badge--blue";
  }
}

export function CatchUpFeed() {
  const {
    notifications,
    unreadNotificationCount,
    markNotificationAsRead,
    markAllNotificationsAsRead,
    dismissNotification,
    openPanel,
    closePanel,
    sendMessage,
    simulateBackgroundEvent,
  } = useStudio();

  const [activeFilter, setActiveFilter] = useState<FilterType>("all");

  const filteredNotifications = notifications.filter((item) => {
    if (activeFilter === "unread") return !item.read;
    if (activeFilter === "outcome") return item.category === "outcome";
    if (activeFilter === "signals")
      return item.category === "simulation" || item.category === "evidence";
    return true;
  });

  function handleAction(notif: StudioNotification) {
    markNotificationAsRead(notif.id);
    if (notif.targetPanel) {
      openPanel(notif.targetPanel as WorkspacePanelId);
    } else if (notif.chatPrompt) {
      closePanel();
      void sendMessage(notif.chatPrompt);
    }
  }

  function handleAskAssistant(notif: StudioNotification, e: React.MouseEvent) {
    e.stopPropagation();
    markNotificationAsRead(notif.id);
    if (notif.chatPrompt) {
      closePanel();
      void sendMessage(notif.chatPrompt);
    }
  }

  const outcomeCount = notifications.filter((n) => n.category === "outcome").length;
  const signalCount = notifications.filter(
    (n) => n.category === "simulation" || n.category === "evidence",
  ).length;

  return (
    <div className="stack catchup-feed" aria-label="Catch up activity feed">
      {/* Executive Summary Header */}
      <section className="catchup-summary card" aria-label="Summary while you were away">
        <div className="card__head">
          <div>
            <span className="hero__eyebrow">Intent & Outcome Feed</span>
            <h2 className="catchup-title">
              While you were away
            </h2>
          </div>
          <div className="catchup-summary__actions">
            {unreadNotificationCount > 0 && (
              <button
                type="button"
                className="button button--ghost"
                onClick={markAllNotificationsAsRead}
                title="Mark all notifications as read"
              >
                Mark all as read
              </button>
            )}
            <button
              type="button"
              className="button button--ghost"
              onClick={simulateBackgroundEvent}
              title="Simulate a background system update while away"
            >
              + Simulate update
            </button>
          </div>
        </div>

        <div className="metrics catchup-metrics">
          <div className="metric">
            <span className="metric__label">Unread Signals</span>
            <span className="metric__value metric__value--accent">
              {unreadNotificationCount}
            </span>
          </div>
          <div className="metric">
            <span className="metric__label">Outcome Shifts</span>
            <span className="metric__value">{outcomeCount}</span>
          </div>
          <div className="metric">
            <span className="metric__label">Simulations & Evidence</span>
            <span className="metric__value">{signalCount}</span>
          </div>
        </div>
      </section>

      {/* Filter Chips */}
      <div className="chips" role="tablist" aria-label="Filter notifications">
        <button
          type="button"
          role="tab"
          aria-selected={activeFilter === "all"}
          className={`chip${activeFilter === "all" ? " is-on" : ""}`}
          onClick={() => setActiveFilter("all")}
        >
          All ({notifications.length})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeFilter === "unread"}
          className={`chip${activeFilter === "unread" ? " is-on" : ""}`}
          onClick={() => setActiveFilter("unread")}
        >
          Unread ({unreadNotificationCount})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeFilter === "outcome"}
          className={`chip${activeFilter === "outcome" ? " is-on" : ""}`}
          onClick={() => setActiveFilter("outcome")}
        >
          Outcome Shifts ({outcomeCount})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeFilter === "signals"}
          className={`chip${activeFilter === "signals" ? " is-on" : ""}`}
          onClick={() => setActiveFilter("signals")}
        >
          Simulations & Telemetry ({signalCount})
        </button>
      </div>

      {/* Notifications List */}
      {filteredNotifications.length === 0 ? (
        <div className="card empty-note catchup-empty">
          <span className="catchup-empty__icon">✨</span>
          <p className="catchup-empty__title">You're all caught up!</p>
          <p className="catchup-empty__hint">
            No updates found for this filter.
          </p>
        </div>
      ) : (
        <div className="cards">
          {filteredNotifications.map((item) => (
            <article
              key={item.id}
              className={`card catchup-card${!item.read ? " is-unread" : ""}`}
              onClick={() => handleAction(item)}
            >
              <div className="card__head">
                <div className="catchup-card__meta">
                  {!item.read && <span className="status-dot" title="Unread signal" />}
                  <span className={`badge ${getCategoryBadgeClass(item.category)}`}>
                    <span className="catchup-card__badge">
                      {getCategoryIcon(item.category)}
                      {item.category.toUpperCase()}
                    </span>
                  </span>
                  <span className="card__id">{formatRelativeTime(item.timestamp)}</span>
                </div>

                <div className="catchup-card__controls">
                  {!item.read && (
                    <button
                      type="button"
                      className="quiet-action"
                      title="Mark as read"
                      onClick={(e) => {
                        e.stopPropagation();
                        markNotificationAsRead(item.id);
                      }}
                    >
                      <CheckIcon size={14} />
                      Read
                    </button>
                  )}
                  <button
                    type="button"
                    className="quiet-action quiet-action--danger"
                    title="Dismiss"
                    onClick={(e) => {
                      e.stopPropagation();
                      dismissNotification(item.id);
                    }}
                  >
                    Dismiss
                  </button>
                </div>
              </div>

              <h3 className="catchup-card__title">{item.title}</h3>
              <p className="card__statement catchup-card__body">
                {item.message}
              </p>

              <div className="card__actions">
                {item.actionText && (
                  <button
                    type="button"
                    className="button button--ghost catchup-card__action"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleAction(item);
                    }}
                  >
                    {item.actionText} →
                  </button>
                )}
                {item.chatPrompt && (
                  <button
                    type="button"
                    className="button catchup-card__action"
                    onClick={(e) => handleAskAssistant(item, e)}
                  >
                    <SparkIcon size={14} className="catchup-card__action-icon" />
                    Ask Assistant
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
