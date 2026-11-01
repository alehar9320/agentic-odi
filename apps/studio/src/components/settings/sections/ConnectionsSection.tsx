import type { ReactNode } from "react";

import type { StudioConfig } from "../../../types";
import { SavedField, SectionSaveLine } from "../SavedField";
import { useSectionSaves } from "../saves";
import { validateMcpUrl } from "../validation";

interface ConnectionsSectionProps {
  settings: StudioConfig;
  saveSettings: (config: StudioConfig) => void;
  /** The read-only status rows and connector controls that follow the URL. */
  children: ReactNode;
}

/**
 * The studio bridge, saved when its field is left.
 *
 * The bridge URL is the only editable value here; the status rows below it are
 * read from the services themselves. A URL that is not an address is refused
 * beside the field, so the working bridge keeps answering.
 */
export function ConnectionsSection({
  settings,
  saveSettings,
  children,
}: ConnectionsSectionProps) {
  const { report, summary } = useSectionSaves();

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
      {children}
    </div>
  );
}
