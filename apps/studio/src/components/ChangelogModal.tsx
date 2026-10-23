import { useEffect, useState } from "react";

import { fetchChangelog } from "../api/studioApi";
import type { ChangelogData } from "../types";

interface ChangelogModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const SEEN_KEY = "studio.changelog.seen";

/** Versions the reader has already opened the changelog for. */
function readSeenVersions(): Set<string> {
  try {
    const raw = window.localStorage.getItem(SEEN_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return new Set(
      Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [],
    );
  } catch {
    return new Set();
  }
}

function rememberVersions(versions: string[]): void {
  try {
    const merged = new Set([...readSeenVersions(), ...versions]);
    window.localStorage.setItem(SEEN_KEY, JSON.stringify([...merged]));
  } catch {
    // Storage can be full or blocked; the badge is a nicety, not state to lose.
  }
}

export function ChangelogModal({ isOpen, onClose }: ChangelogModalProps) {
  const [changelog, setChangelog] = useState<ChangelogData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Re-read on every render so a reopen in the same session reflects the close.
  const seenVersions = readSeenVersions();

  // Closing the drawer counts as reading: the badge is for releases the reader
  // has not seen yet.
  useEffect(() => {
    if (isOpen || !changelog) {
      return;
    }
    rememberVersions(changelog.releases.map((release) => release.version));
  }, [isOpen, changelog]);

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

          {!loading && !error && changelog && (
            <div className="changelog-timeline">
              {changelog.releases.map((release) => (
                <article key={release.version} className="changelog-release">
                  <div className="changelog-release__meta">
                    <span className="changelog-release__version">
                      v{release.version}
                    </span>
                    {!seenVersions.has(release.version) && (
                      <span
                        className="changelog-release__new"
                        aria-label={`New in ${release.version}`}
                      >
                        New
                      </span>
                    )}
                    <time className="changelog-release__date">{release.date}</time>
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
          <button
            type="button"
            className="studio-button"
            onClick={onClose}
          >
            Done
          </button>
        </footer>
      </div>
    </div>
  );
}
