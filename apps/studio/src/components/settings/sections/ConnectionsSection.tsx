import type { Capability } from "../../../bff/capabilities/registry";
import type { ConnectorListItem, ConnectorPreset, StudioConfig, StudioError } from "../../../types";
import { FailurePanel } from "../../FailurePanel";
import { SavedField, SectionSaveLine } from "../SavedField";
import { useSectionSaves } from "../saves";
import { validateMcpUrl } from "../validation";

const PRESET_AREAS: ConnectorPreset["area"][] = [
  "voice-of-customer",
  "quantitative-data",
  "market-intelligence",
  "strategy-alignment",
  "knowledge-output",
];

const AREA_LABELS: Record<ConnectorPreset["area"], string> = {
  "voice-of-customer": "Voice of customer & qualitative research",
  "quantitative-data": "Quantitative data & opportunity scoring",
  "market-intelligence": "Market & competitive intelligence",
  "strategy-alignment": "Product strategy & backlog alignment",
  "knowledge-output": "Strategy & knowledge management output",
};

type Reach = boolean | null;

interface ConnectionsSectionProps {
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
  /** Model reachability for the status row; null means "not checked". */
  modelHealthy: Reach;
  /** Sidecar reachability; null means "unknown". */
  sidecarKnown: Reach;
  /** Local FastMCP reachability. */
  mcpKnown: boolean;
  capabilities: Capability[];
  connectors: ConnectorListItem[];
  connectorsError: StudioError | null;
  connectorsLoading: boolean;
  presets: ConnectorPreset[];
  presetError: StudioError | null;
  presetsLoading: boolean;
  refreshConnectors: () => Promise<void>;
  refreshPresets: () => Promise<void>;
  addConnector: (payload: { preset: string }) => Promise<void>;
  deleteConnector: (name: string) => Promise<void>;
  openCustomize: () => void;
}

/**
 * The studio bridge, the service status rows, and the connector catalog.
 *
 * The bridge URL is the only editable value here; the status rows below it are
 * read from the services themselves. A URL that is not an address is refused
 * beside the field, so the working bridge keeps answering.
 *
 * This section reads its own three sources — the bridge field, the installed
 * connector list, and the preset catalog — and reports each one's failure in
 * place. A connector fetch that fails shows an error here and leaves the Model
 * section, composed beside it, untouched.
 */
export function ConnectionsSection({
  settings,
  saveSettings,
  modelHealthy,
  sidecarKnown,
  mcpKnown,
  capabilities,
  connectors,
  connectorsError,
  connectorsLoading,
  presets,
  presetError,
  presetsLoading,
  refreshConnectors,
  refreshPresets,
  addConnector,
  deleteConnector,
  openCustomize,
}: ConnectionsSectionProps) {
  const { report, summary } = useSectionSaves();

  const presetGroups = PRESET_AREAS.map((area) => ({
    area,
    label: AREA_LABELS[area],
    presets: presets.filter((preset) => preset.area === area),
  })).filter((group) => group.presets.length > 0);

  return (
    <div className="settings__section">
      <h3 className="settings__title" id="settings-connections-heading">
        Studio bridge
      </h3>
      <SavedField
        id="mcp-url"
        label="MCP server URL"
        value={settings.mcp_url}
        spellCheck={false}
        validate={validateMcpUrl}
        onCommit={(value) => saveSettings({ ...settings, mcp_url: value })}
        onStatusChange={(status) => report("mcp_url", status)}
      />
      <SectionSaveLine status={summary} />

      <ul className="connection-list">
        <li>
          <span
            className={`status-dot${modelHealthy === false ? " is-warn" : ""}${
              modelHealthy === null ? " is-unknown" : ""
            }`}
          />
          <span>Model</span>
          <span className="connection-list__value">
            {modelHealthy === false ? "offline" : modelHealthy === null ? "not checked" : "reachable"}
          </span>
        </li>
        <li>
          <span
            className={`status-dot${sidecarKnown === false ? " is-warn" : sidecarKnown === null ? " is-unknown" : ""}`}
          />
          <span>Sidecar</span>
          <span className="connection-list__value">
            {sidecarKnown === false ? "unavailable" : sidecarKnown === null ? "unknown" : "reachable"}
          </span>
        </li>
        <li>
          <span className={`status-dot${mcpKnown ? "" : " is-unknown"}`} />
          <span>Local FastMCP server</span>
          <span className="connection-list__value">{mcpKnown ? "connected" : "offline"}</span>
        </li>
      </ul>
      <p className="muted">
        Only the model and MCP server above are live. No data source is connected yet — add one from
        the presets below.
      </p>

      <h3 className="settings__title">Capabilities</h3>
      <ul className="connection-list">
        {capabilities.map((capability) => (
          <li key={capability.id}>
            <span
              className={`status-dot${capability.status === "available" ? "" : " is-warn"}`}
            />
            <span>{capability.label}</span>
            <span className="connection-list__value">
              {capability.status === "available" ? "available" : "unavailable"}
              {capability.reason ? ` — ${capability.reason}` : ""}
            </span>
          </li>
        ))}
      </ul>

      {sidecarKnown === false ? (
        <p className="muted">
          Connectors require the local sidecar. Data and conversation still work without it;
          connect a sidecar to add MCP or REST data sources.
        </p>
      ) : (
        <>
          <h3 className="settings__title">Connectors</h3>
          <button type="button" className="button settings__manage" onClick={openCustomize}>
            Manage connectors
          </button>
          {connectorsLoading ? (
            <p className="muted">Reading the connector list…</p>
          ) : connectorsError ? (
            <FailurePanel
              error={connectorsError}
              retryText="reload"
              onRetry={() => void refreshConnectors()}
            />
          ) : connectors.length === 0 ? (
            <p className="muted">No connectors registered. Pick a preset to add one.</p>
          ) : (
            <ul className="connection-list">
              {connectors.map((connector) => (
                <li key={connector.name}>
                  <span className="connection-list__value">
                    {connector.name} · {connector.kind}
                    {connector.enabled ? "" : " (disabled)"}
                  </span>
                  <button
                    type="button"
                    className="button button--ghost"
                    aria-label={`Remove ${connector.name}`}
                    onClick={() => void deleteConnector(connector.name)}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
          <h4 className="settings__title">Add a data source</h4>
          {presetsLoading ? (
            <p className="muted">Reading the preset catalog…</p>
          ) : presetError ? (
            <FailurePanel
              error={presetError}
              retryText="reload"
              onRetry={() => void refreshPresets()}
            />
          ) : presetGroups.length === 0 ? (
            <p className="muted">No presets available.</p>
          ) : (
            <div className="settings__presets">
              {presetGroups.map((group) => (
                <section
                  key={group.area}
                  className="settings__preset-group"
                  aria-label={group.label}
                >
                  <h5 className="settings__preset-title">{group.label}</h5>
                  <ul className="connection-list">
                    {group.presets.map((preset) => (
                      <li key={preset.id}>
                        <span className="connection-list__value">
                          {preset.label} <code className="settings__preset-id">{preset.id}</code>
                          {" · "}
                          {preset.auth === "oauth" ? "OAuth" : "No auth"}
                        </span>
                        <button
                          type="button"
                          className="button button--ghost"
                          aria-label={`Connect ${preset.label}`}
                          onClick={() => void addConnector({ preset: preset.id })}
                        >
                          Connect
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
