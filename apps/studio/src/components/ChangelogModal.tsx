import { useEffect, useMemo, useState } from "react";

import { fetchChangelog } from "../api/studioApi";
import { markReleasesRead, readReleaseVersions, unreadReleases } from "../lib/changelogRead";
import type { ChangelogData } from "../types";

interface ChangelogModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ChangelogModal({ isOpen, onClose }: ChangelogModalProps) {
  const [changelog, setChangelog] = useState<ChangelogData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [readVersions, setReadVersions] = useState<string[]>(() => readReleaseVersions());

  const unread = useMemo(
    () => unreadReleases(changelog?.releases ?? [], readVersions),
    [changelog, readVersions],
  );
  const unreadVersions = useMemo(
    () => new Set(unread.map((release) => release.version)),
    [unread],
  );

  function markAllRead() {
    setReadVersions(markReleasesRead((changelog?.releases ?? []).map((r) => r.version)));
  }

  useEffect(() => {
    if (!isOpen) return;

    let mounted = true;

    fetchChangelog()
      .then((data) => {
        if (mounted) {
          setChangelog(data);
          setError(null);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (mounted) {
          setError(err.message || "Failed to load release notes");
          setLoading(false);
        }
      });

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      mounted = false;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="changelog-overlay fade-in"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="changelog-modal-title"
    >
      <div
        className="changelog-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="changelog-modal__header">
          <div>
            <div className="changelog-modal__badge">WHAT'S NEW</div>
            <h2 id="changelog-modal-title" className="changelog-modal__title">
              Release Notes & Progress
            </h2>
            {unread.length > 0 && (
              <p className="changelog-modal__unread" role="status">
                {unread.length} new
              </p>
            )}
          </div>
          <button
            type="button"
            className="changelog-modal__close"
            onClick={onClose}
            aria-label="Close changelog modal"
          >
            ✕
          </button>
        </header>

        <div className="changelog-modal__body">
          {loading && (
            <div className="changelog-modal__loading">
              <div className="skeleton skeleton-title" style={{ width: "40%" }} />
              <div className="skeleton skeleton-line" style={{ width: "80%" }} />
              <div className="skeleton skeleton-line" style={{ width: "60%" }} />
            </div>
          )}

          {error && (
            <div className="changelog-modal__error">
              <p>⚠️ Unable to fetch release notes: {error}</p>
            </div>
          )}

          {!loading && !error && changelog && changelog.releases.length === 0 && (
            <p className="changelog-modal__empty">
              Release notes come from the studio service. Start it to see what changed.
            </p>
          )}

          {!loading && !error && changelog && changelog.releases.length > 0 && (
            <div className="changelog-timeline">
              {changelog.releases.map((release) => (
                <article
                  key={release.version}
                  className={
                    unreadVersions.has(release.version)
                      ? "changelog-release changelog-release--unread"
                      : "changelog-release"
                  }
                >
                  <div className="changelog-release__meta">
                    <span className="changelog-release__version">
                      v{release.version}
                    </span>
                    <time className="changelog-release__date">{release.date}</time>
                    {unreadVersions.has(release.version) && (
                      <span className="changelog-release__new">New</span>
                    )}
                  </div>

                  <div className="changelog-release__content">
                    {release.categories.map((cat) => (
                      <div key={cat.name} className="changelog-category">
                        <h3 className="changelog-category__title">{cat.name}</h3>
                        <ul className="changelog-category__list">
                          {cat.items.map((item, idx) => (
                            <li key={idx} className="changelog-category__item">
                              {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <footer className="changelog-modal__footer">
          <span className="changelog-modal__quote">
            "Design is not just what it looks like and feels like. Design is how it works."
          </span>
          <div className="changelog-modal__actions">
            <button
              type="button"
              className="studio-button"
              onClick={markAllRead}
              disabled={unread.length === 0}
            >
              Mark all read
            </button>
            <button
              type="button"
              className="studio-button"
              onClick={onClose}
            >
              Done
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
