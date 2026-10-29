import { useEffect, useMemo, useRef, useState } from "react";

import { useStudio } from "../../state/StudioContext";
import type { MarketplaceListing } from "../../types";
import { FailurePanel } from "../FailurePanel";
import { ArrowLeftIcon, CheckIcon, CompassIcon, SearchIcon } from "../icons";

/** A listing installs under its connector name, which can differ from its display name. */
function listingKey(listing: MarketplaceListing): string {
  return listing.connector_name || listing.name;
}

/**
 * Customize: the one place to see what the studio can already read and to add
 * more. It replaces the conversation for as long as it is open, because this is
 * a management surface, not a lens on the thread — the bar stays, so leaving is
 * always one gesture.
 *
 * Everything installed is a row in the shared `connectors.json`, so the CLI
 * sees the same set. Nothing here stores a credential: a listing that needs a
 * token says which environment variable to set and nothing more.
 */
export function CustomizePage() {
  const {
    connectors,
    connectorsError,
    refreshConnectors,
    deleteConnector,
    closeCustomize,
    customizeTarget,
    marketplace,
    marketplaceError,
    marketplaceLoading,
    searchMarketplace,
    featured,
    featuredError,
    refreshFeatured,
    installFromMarketplace,
  } = useStudio();

  const [query, setQuery] = useState(customizeTarget?.query ?? "");
  const [area, setArea] = useState<string>("");
  const [installing, setInstalling] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  // Responses can arrive out of order; only the newest search may write.
  const searchSeq = useRef(0);

  const installedNames = useMemo(() => new Set(connectors.map((item) => item.name)), [connectors]);

  // A curated pick and its registry entry are the same connector under two
  // ids. Showing it twice would read as two things to install.
  const featuredNames = useMemo(() => new Set(featured.map(listingKey)), [featured]);
  const marketplaceOnly = useMemo(
    () => (marketplace?.listings ?? []).filter((item) => !featuredNames.has(listingKey(item))),
    [marketplace, featuredNames],
  );

  useEffect(() => {
    void refreshFeatured();
    searchRef.current?.focus();
  }, [refreshFeatured]);

  // Debounced so typing does not fire a request per keystroke.
  useEffect(() => {
    const seq = ++searchSeq.current;
    const timer = window.setTimeout(() => {
      if (seq === searchSeq.current) void searchMarketplace({ q: query, area });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query, area, searchMarketplace]);

  async function install(listing: MarketplaceListing) {
    setInstalling(listing.id);
    await installFromMarketplace(listing);
    setInstalling(null);
  }

  const types = marketplace?.types ?? [{ id: "mcp", label: "MCP servers", available: true }];
  const areas = marketplace?.areas ?? {};

  return (
    <section className="customize" aria-label="Customize connectors">
      <header className="customize__head">
        <button
          type="button"
          className="button button--ghost customize__back"
          onClick={closeCustomize}
        >
          <ArrowLeftIcon size={15} />
          Back to conversation
        </button>
        <h2 className="customize__title">Customize</h2>
        <p className="customize__subtitle">
          Connect the systems the studio can read. Everything you add here is available to the
          agent and to the CLI.
        </p>

        <div className="customize__types" role="tablist" aria-label="Connection types">
          {types.map((type) => (
            <button
              key={type.id}
              type="button"
              role="tab"
              aria-selected={type.id === "mcp"}
              disabled={!type.available}
              className={`customize__type${type.id === "mcp" ? " is-active" : ""}${
                type.available ? "" : " is-disabled"
              }`}
              title={type.note}
            >
              {type.label}
              {!type.available && type.note ? (
                <span className="customize__type-note">{type.note}</span>
              ) : null}
            </button>
          ))}
        </div>

        <div className="customize__search">
          <SearchIcon size={15} />
          <input
            ref={searchRef}
            type="search"
            value={query}
            placeholder="Search the marketplace…"
            aria-label="Search the marketplace"
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>

        <div className="customize__areas" aria-label="Capability areas">
          <button
            type="button"
            className={`customize__chip${area === "" ? " is-active" : ""}`}
            onClick={() => setArea("")}
          >
            All
          </button>
          {Object.entries(areas).map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`customize__chip${area === id ? " is-active" : ""}`}
              onClick={() => setArea(id)}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      <div className="customize__body">
        <section className="customize__section" aria-label="Installed connectors">
          <h3 className="customize__section-title">
            Installed
            <span className="customize__count">{connectors.length}</span>
          </h3>
          {connectorsError ? (
            <FailurePanel
              error={connectorsError}
              retryText="reload"
              onRetry={() => void refreshConnectors()}
            />
          ) : connectors.length === 0 ? (
            <p className="customize__empty">
              Nothing connected yet. The studio can only reason about what it can read — add a
              system below.
            </p>
          ) : (
            <ul className="customize__list">
              {connectors.map((connector) => (
                <li key={connector.name} className="customize__row">
                  <span className="customize__row-mark" aria-hidden="true">
                    <CheckIcon size={13} />
                  </span>
                  <span className="customize__row-name">{connector.name}</span>
                  <span className="customize__badge">{connector.kind}</span>
                  {connector.enabled ? null : (
                    <span className="customize__badge is-muted">disabled</span>
                  )}
                  <button
                    type="button"
                    className="button button--ghost customize__remove"
                    aria-label={`Remove ${connector.name}`}
                    onClick={() => void deleteConnector(connector.name)}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="customize__section" aria-label="Editor's picks">
          <h3 className="customize__section-title">Editor's picks</h3>
          <p className="customize__section-note">
            Curated connectors we have checked, grouped by what they let the studio do.
          </p>
          {featuredError ? (
            <FailurePanel
              error={featuredError}
              retryText="reload"
              onRetry={() => void refreshFeatured()}
            />
          ) : featured.length === 0 ? (
            <p className="customize__empty">No picks available right now.</p>
          ) : (
            <ul className="customize__cards">
              {featured.map((listing) => (
                <li key={listing.id}>
                  <ListingCard
                    listing={listing}
                    installed={installedNames.has(listingKey(listing))}
                    installing={installing === listing.id}
                    onInstall={() => void install(listing)}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="customize__section" aria-label="Marketplace">
          <h3 className="customize__section-title">
            Marketplace
            {marketplace?.cached ? (
              <span className="customize__badge is-muted">offline copy</span>
            ) : null}
          </h3>
          <p className="customize__section-note">
            Live listings from the official MCP registry. A verified badge means Docker reviewed
            the server.
          </p>
          {marketplaceError ? (
            <FailurePanel
              error={marketplaceError}
              retryText="reload"
              onRetry={() => void searchMarketplace({ q: query, area })}
            />
          ) : marketplaceLoading && !marketplace ? (
            <p className="customize__empty">Searching…</p>
          ) : marketplaceOnly.length === 0 ? (
            <p className="customize__empty">
              {query
                ? `Nothing matched “${query}”. Try a different term.`
                : "No listings right now."}
            </p>
          ) : (
            <ul className="customize__cards">
              {marketplaceOnly.map((listing) => (
                <li key={listing.id}>
                  <ListingCard
                    listing={listing}
                    installed={installedNames.has(listingKey(listing))}
                    installing={installing === listing.id}
                    onInstall={() => void install(listing)}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </section>
  );
}

function ListingCard({
  listing,
  installed,
  installing,
  onInstall,
}: {
  listing: MarketplaceListing;
  installed: boolean;
  installing: boolean;
  onInstall: () => void;
}) {
  const name = listing.title ?? listing.name;

  return (
    <article className="connector-card">
      <div className="connector-card__head">
        <span className="connector-card__mark" aria-hidden="true">
          <CompassIcon size={15} />
        </span>
        <h4 className="connector-card__name">{name}</h4>
        {listing.verified ? (
          <span className="connector-card__verified" title="Reviewed by Docker">
            Verified
          </span>
        ) : null}
      </div>
      {listing.summary ? <p className="connector-card__summary">{listing.summary}</p> : null}
      <div className="connector-card__meta">
        {listing.area ? (
          <span className="connector-card__tag">{listing.area.replace(/-/g, " ")}</span>
        ) : null}
        <span className="connector-card__tag">
          {listing.source === "official" ? "official registry" : "editor's pick"}
        </span>
        {listing.pull_count > 0 ? (
          <span className="connector-card__tag">{formatPulls(listing.pull_count)} pulls</span>
        ) : null}
        {listing.auth === "oauth" ? <span className="connector-card__tag">sign-in</span> : null}
      </div>
      {listing.env_vars.length > 0 ? (
        <p className="connector-card__creds">
          Needs <code>{listing.env_vars.join(", ")}</code> in your environment.
        </p>
      ) : null}
      <div className="connector-card__actions">
        {installed ? (
          <span className="connector-card__installed">
            <CheckIcon size={13} /> Added
          </span>
        ) : listing.installable ? (
          <button
            type="button"
            className="button connector-card__install"
            disabled={installing}
            onClick={onInstall}
          >
            {installing ? "Adding…" : "Add"}
          </button>
        ) : (
          <span className="connector-card__unavailable">
            {listing.unavailable_reason ?? "Not available for this studio"}
          </span>
        )}
        {listing.docs ? (
          <a
            className="connector-card__link"
            href={listing.docs}
            target="_blank"
            rel="noreferrer noopener"
          >
            Docs
          </a>
        ) : null}
      </div>
    </article>
  );
}

function formatPulls(count: number): string {
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${Math.round(count / 1_000)}k`;
  return String(count);
}
