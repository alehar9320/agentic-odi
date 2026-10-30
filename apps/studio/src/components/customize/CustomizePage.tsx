import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { useStudio } from "../../state/StudioContext";
import type { CustomizeTab, MarketplaceListing } from "../../types";
import { FailurePanel } from "../FailurePanel";
import { ArrowLeftIcon, CheckIcon, CompassIcon, SearchIcon } from "../icons";
import { AppearanceSection } from "../settings/sections/AppearanceSection";
import { ConnectionsSection } from "../settings/sections/ConnectionsSection";
import { DataSection } from "../settings/sections/DataSection";
import { ModelSection } from "../settings/sections/ModelSection";
import { ShortcutsSection } from "../settings/sections/ShortcutsSection";

const CUSTOMIZE_TABS: { id: CustomizeTab; label: string }[] = [
  { id: "model", label: "Model" },
  { id: "appearance", label: "Appearance" },
  { id: "data", label: "Data" },
  { id: "connectors", label: "Connectors" },
  { id: "shortcuts", label: "Shortcuts" },
];

function listingKey(listing: MarketplaceListing): string {
  return listing.connector_name || listing.name;
}

function listingNameFromId(id: string): string {
  return id.split(/[/:]/).filter(Boolean).at(-1) ?? id;
}

/** Customize keeps local preferences local and loads connector discovery only on its own section. */
export function CustomizePage() {
  const {
    settings,
    saveSettings,
    displayName,
    setDisplayName,
    brief,
    openSetup,
    canvasState,
    models,
    modelsLoading,
    modelsMessage,
    refreshModels,
    llmHealth,
    capabilities,
    mcpReachable,
    sidecarReachable,
    connectors,
    connectorsError,
    refreshConnectors,
    addConnector,
    deleteConnector,
    openCustomize,
    customizeTarget,
    closeCustomize,
    marketplace,
    marketplaceError,
    marketplaceLoading,
    searchMarketplace,
    featured,
    featuredError,
    refreshFeatured,
    installFromMarketplace,
  } = useStudio();

  const [activeTab, setActiveTab] = useState<CustomizeTab>(customizeTarget?.tab ?? "connectors");
  const [query, setQuery] = useState(customizeTarget?.query ?? "");
  const [area, setArea] = useState("");
  const [transport, setTransport] = useState("mcp");
  const [installing, setInstalling] = useState<string | null>(null);
  const tabRefs = useRef<Partial<Record<CustomizeTab, HTMLButtonElement>>>({});
  const listingRefs = useRef<Record<string, HTMLElement | null>>({});
  const searchSeq = useRef(0);
  const listingSearchAttempted = useRef(false);
  const focusedListing = useRef<string | null>(null);

  const installedNames = useMemo(() => new Set(connectors.map((item) => item.name)), [connectors]);
  const featuredNames = useMemo(() => new Set(featured.map(listingKey)), [featured]);
  const listingId = customizeTarget?.listingId;
  const marketplaceOnly = useMemo(
    () =>
      (marketplace?.listings ?? []).filter(
        (item) =>
          !featuredNames.has(listingKey(item)) ||
          (item.id === listingId && !featured.some((pick) => pick.id === listingId)),
      ),
    [marketplace, featured, featuredNames, listingId],
  );
  const listingName = listingId ? listingNameFromId(listingId) : "";
  const activeListings = [...featured, ...marketplaceOnly];
  const marketplaceTypes = marketplace?.types ?? [];
  const types = marketplaceTypes.length
    ? marketplaceTypes
    : [
        { id: "mcp", label: "MCP servers", available: true },
        { id: "a2a", label: "A2A agents", available: false, note: "Coming soon" },
      ];
  const activeType = types.find((type) => type.id === transport);
  const listingAvailable = activeListings.some((item) => item.id === listingId);

  const connectorsUnavailable = sidecarReachable === false || Boolean(connectorsError);
  const lastCustomizeTarget = useRef(customizeTarget);

  useEffect(() => {
    if (activeTab !== "connectors") return;
    void refreshConnectors();
    void refreshFeatured();
  }, [activeTab, refreshConnectors, refreshFeatured]);

  useEffect(() => {
    if (lastCustomizeTarget.current === customizeTarget) return;
    lastCustomizeTarget.current = customizeTarget;
    setActiveTab(customizeTarget?.tab ?? "connectors");
    setQuery(customizeTarget?.query ?? "");
    listingSearchAttempted.current = false;
    focusedListing.current = null;
  }, [customizeTarget]);

  useEffect(() => {
    if (activeTab !== "connectors") return;
    if (listingId) {
      if (listingAvailable) {
        listingSearchAttempted.current = true;
        return;
      }
      if (marketplaceLoading || listingSearchAttempted.current) return;
      listingSearchAttempted.current = true;
      void searchMarketplace({ q: listingName, area });
      return;
    }
    const seq = ++searchSeq.current;
    const timer = window.setTimeout(() => {
      if (seq === searchSeq.current) void searchMarketplace({ q: query, area });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [activeTab, listingId, listingAvailable, listingName, marketplaceLoading, query, area, searchMarketplace]);

  useEffect(() => {
    if (activeTab !== "connectors" || !listingId || !listingAvailable) return;
    if (focusedListing.current === listingId) return;
    focusedListing.current = listingId;
    const card = listingRefs.current[listingId];
    card?.scrollIntoView?.({ block: "center" });
    card?.focus();
  }, [activeTab, listingId, listingAvailable]);

  async function install(listing: MarketplaceListing) {
    setInstalling(listing.id);
    await installFromMarketplace(listing);
    setInstalling(null);
  }

  function selectTab(id: CustomizeTab, focus = false) {
    setActiveTab(id);
    if (focus) tabRefs.current[id]?.focus();
  }

  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    const current = CUSTOMIZE_TABS.findIndex((tab) => tab.id === activeTab);
    let next: number;
    if (event.key === "ArrowRight") next = (current + 1) % CUSTOMIZE_TABS.length;
    else if (event.key === "ArrowLeft") next = (current - 1 + CUSTOMIZE_TABS.length) % CUSTOMIZE_TABS.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = CUSTOMIZE_TABS.length - 1;
    else return;
    event.preventDefault();
    selectTab(CUSTOMIZE_TABS[next].id, true);
  }

  const areas = marketplace?.areas ?? {};

  return (
    <section className="customize" aria-label="Customize">
      <header className="customize__head">
        <button type="button" className="button button--ghost customize__back" onClick={closeCustomize}>
          <ArrowLeftIcon size={15} /> Back to conversation
        </button>
        <h2 className="customize__title">Customize</h2>
        <p className="customize__subtitle">
          Choose how the studio looks, what it reads, and which systems it can reach.
        </p>
        <div className="customize__types" role="tablist" aria-label="Customize sections">
          {CUSTOMIZE_TABS.map(({ id, label }) => (
            <button
              key={id}
              ref={(node) => { if (node) tabRefs.current[id] = node; }}
              id={`customize-tab-${id}`}
              type="button"
              role="tab"
              aria-selected={activeTab === id}
              aria-controls={`customize-panel-${id}`}
              tabIndex={activeTab === id ? 0 : -1}
              className={`customize__type${activeTab === id ? " is-active" : ""}`}
              onClick={() => selectTab(id)}
              onKeyDown={onTabKeyDown}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      <div className="customize__panels">
        {CUSTOMIZE_TABS.map(({ id }) => (
          <div
            key={id}
            className="customize__panel"
            role="tabpanel"
            id={`customize-panel-${id}`}
            aria-labelledby={`customize-tab-${id}`}
            tabIndex={0}
            hidden={activeTab !== id}
          >
            {activeTab === id && id === "model" ? (
              <ModelSection
                settings={settings}
                saveSettings={saveSettings}
                models={models}
                modelsLoading={modelsLoading}
                modelsMessage={modelsMessage}
                refreshModels={() => refreshModels()}
                llmHealth={llmHealth}
                capabilities={capabilities}
                headingId="customize-model-heading"
                idPrefix="customize"
              />
            ) : activeTab === id && id === "appearance" ? (
              <AppearanceSection
                settings={settings}
                saveSettings={saveSettings}
                displayName={displayName}
                setDisplayName={setDisplayName}
                headingId="customize-appearance-heading"
                idPrefix="customize"
              />
            ) : activeTab === id && id === "data" ? (
              <DataSection
                brief={brief}
                openSetup={openSetup}
                canvas={canvasState.data}
                headingId="customize-data-heading"
              />
            ) : activeTab === id && id === "shortcuts" ? (
              <ShortcutsSection />
            ) : activeTab === id && id === "connectors" ? (
              <>
                <ConnectionsSection
                  connectors={connectors}
                  connectorsError={connectorsError}
                  refreshConnectors={refreshConnectors}
                  deleteConnector={deleteConnector}
                  addConnector={addConnector}
                  openCustomize={() => openCustomize({ tab: "connectors" })}
                  sidecarReachable={sidecarReachable}
                  mcpReachable={mcpReachable}
                  llmHealth={llmHealth}
                  capabilities={capabilities}
                  settings={settings}
                  saveSettings={saveSettings}
                  headingId="customize-connectors-heading"
                  heading="Installed"
                  showConnectionStatus={false}
                  showModelStatus={false}
                  showManageButton={false}
                  allowManualAdd
                  manualAddDisabledReason="Connectors need the sidecar"
                />
                <div className="customize__connector-tools">
                  <div className="customize__search">
                    <SearchIcon size={15} />
                    <input
                      type="search"
                      value={listingId && !query ? listingName : query}
                      placeholder="Search the marketplace…"
                      aria-label="Search the marketplace"
                      onChange={(event) => setQuery(event.target.value)}
                    />
                  </div>
                  <div className="customize__areas" aria-label="Capability areas">
                    <button type="button" className={`customize__chip${area === "" ? " is-active" : ""}`} onClick={() => setArea("")}>All</button>
                    {Object.entries(areas).map(([id, label]) => (
                      <button key={id} type="button" className={`customize__chip${area === id ? " is-active" : ""}`} onClick={() => setArea(id)}>{label}</button>
                    ))}
                  </div>
                  <div className="customize__transports" role="group" aria-label="Connector types">
                    {types.map((type) => (
                      <button
                        key={type.id}
                        type="button"
                        className={`customize__chip${transport === type.id ? " is-active" : ""}`}
                        aria-pressed={transport === type.id}
                        onClick={() => setTransport(type.id)}
                        title={type.note}
                      >
                        {type.label}
                        {!type.available ? <span className="customize__type-note">Coming soon</span> : null}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="customize__body">
                  {connectorsUnavailable ? null : activeType?.available ? (
                    <>
                      <section className="customize__section" aria-label="Editor's picks">
                        <h3 className="customize__section-title">Editor's picks</h3>
                        <p className="customize__section-note">Curated connectors from trusted sources, grouped by what they let the studio do.</p>
                        {featuredError ? (
                          <FailurePanel error={featuredError} onRetry={() => void refreshFeatured()} />
                        ) : featured.length === 0 ? (
                          <p className="customize__empty">No picks available right now.</p>
                        ) : (
                          <ul className="customize__cards">
                            {featured.map((item) => (
                              <li key={item.id}>
                                <ListingCard refCallback={(node) => { listingRefs.current[item.id] = node; }} current={item.id === listingId} listing={item} installed={installedNames.has(listingKey(item))} installing={installing === item.id} onInstall={() => void install(item)} />
                              </li>
                            ))}
                          </ul>
                        )}
                      </section>
                      <section className="customize__section" aria-label="Marketplace">
                        <h3 className="customize__section-title">Marketplace {marketplace?.cached ? <span className="customize__badge is-muted">offline copy</span> : null}</h3>
                        <p className="customize__section-note">Live listings from the official MCP registry. A verified badge means Docker reviewed the server.</p>
                        {marketplaceError ? (
                          <FailurePanel error={marketplaceError} onRetry={() => void searchMarketplace({ q: query, area })} />
                        ) : marketplaceLoading && !marketplace ? (
                          <p className="customize__empty">Searching…</p>
                        ) : marketplaceOnly.length === 0 ? (
                          <p className="customize__empty">{query ? `Nothing matched “${query}”. Try a different term.` : "No listings right now."}</p>
                        ) : (
                          <ul className="customize__cards">
                            {marketplaceOnly.map((item) => (
                              <li key={item.id}>
                                <ListingCard refCallback={(node) => { listingRefs.current[item.id] = node; }} current={item.id === listingId} listing={item} installed={installedNames.has(listingKey(item))} installing={installing === item.id} onInstall={() => void install(item)} />
                              </li>
                            ))}
                          </ul>
                        )}
                      </section>
                    </>
                  ) : (
                    <section className="customize__section" aria-label="A2A agents">
                      <h3 className="customize__section-title">A2A agents</h3>
                      <p className="customize__empty">A2A connector support is coming soon.</p>
                    </section>
                  )}
                </div>
              </>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

function ListingCard({
  listing,
  installed,
  installing,
  onInstall,
  current,
  refCallback,
}: {
  listing: MarketplaceListing;
  installed: boolean;
  installing: boolean;
  onInstall: () => void;
  current: boolean;
  refCallback: (node: HTMLElement | null) => void;
}) {
  const name = listing.title ?? listing.name;

  return (
    <article ref={refCallback} className={`connector-card${current ? " is-targeted" : ""}`} aria-current={current ? "true" : undefined} tabIndex={current ? -1 : undefined}>
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
          <a className="connector-card__link" href={listing.docs} target="_blank" rel="noreferrer noopener">
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
