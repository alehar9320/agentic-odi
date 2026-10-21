import type { ReactNode } from "react";

import type { WorkspacePanelId } from "../../types";
import { DirectCapture } from "../canvas/DirectCapture";
import { EvidenceStream } from "../canvas/EvidenceStream";
import { ImpactSim } from "../canvas/ImpactSim";
import { JobMap } from "../canvas/JobMap";
import { OpportunityLandscape } from "../canvas/OpportunityLandscape";
import { CatchUpFeed } from "../notifications/CatchUpFeed";
import { SettingsPanel } from "../SettingsPanel";
import {
  BellIcon,
  BoltIcon,
  CaptureIcon,
  CompassIcon,
  RouteIcon,
  SettingsIcon,
  SignalIcon,
} from "../icons";

export interface PanelDefinition {
  id: WorkspacePanelId;
  /** Short label used by the drawer and pills. */
  label: string;
  title: string;
  blurb: string;
  icon: ReactNode;
  render: () => ReactNode;
}

export const WORKSPACE_PANELS: PanelDefinition[] = [
  {
    id: "catchup",
    label: "Catch up",
    title: "Activity & Catch Up",
    blurb: "Seamlessly catch up on outcome shifts, simulations, and telemetry signals while you were away.",
    icon: <BellIcon />,
    render: () => <CatchUpFeed />,
  },
  {
    id: "landscape",
    label: "Landscape",
    title: "Opportunity landscape",
    blurb: "Every outcome scored. Anything above 10 is underserved.",
    icon: <CompassIcon />,
    render: () => <OpportunityLandscape />,
  },
  {
    id: "jobmap",
    label: "Job map",
    title: "Universal job map",
    blurb: "The eight phases of the job, in the order customers live them.",
    icon: <RouteIcon />,
    render: () => <JobMap />,
  },
  {
    id: "impact",
    label: "Impact",
    title: "Simulate impact",
    blurb: "What you see is what they experience. Preview the friction collapse.",
    icon: <BoltIcon />,
    render: () => <ImpactSim />,
  },
  {
    id: "evidence",
    label: "Evidence",
    title: "Customer evidence",
    blurb: "Sample signals only — no connectors are wired up yet.",
    icon: <SignalIcon />,
    render: () => <EvidenceStream />,
  },
  {
    id: "capture",
    label: "Capture",
    title: "Capture an outcome",
    blurb: "Prefer typing into a form? This writes to the same MCP repository.",
    icon: <CaptureIcon />,
    render: () => <DirectCapture />,
  },
];

export const SETTINGS_PANEL: PanelDefinition = {
  id: "settings",
  label: "Settings",
  title: "Settings",
  blurb: "Point the studio at your model and your MCP bridge.",
  icon: <SettingsIcon />,
  render: () => <SettingsPanel />,
};

export function findPanel(id: WorkspacePanelId): PanelDefinition {
  if (id === "settings") {
    return SETTINGS_PANEL;
  }
  return WORKSPACE_PANELS.find((panel) => panel.id === id) ?? SETTINGS_PANEL;
}
