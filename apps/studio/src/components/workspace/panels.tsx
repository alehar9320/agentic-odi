import type { ReactNode } from "react";

import type { WorkspacePanelId } from "../../types";
import { DirectCapture } from "../canvas/DirectCapture";
import { EvidenceStream } from "../canvas/EvidenceStream";
import { JobMap } from "../canvas/JobMap";
import { MemoryPanel } from "../canvas/MemoryPanel";
import { OpportunityLandscape } from "../canvas/OpportunityLandscape";
import { SchedulePanel } from "../canvas/SchedulePanel";
import { SegmentBoard } from "../canvas/SegmentBoard";
import { CatchUpFeed } from "../notifications/CatchUpFeed";
import { SettingsPanel } from "../SettingsPanel";
import {
  BellIcon,
  BoltIcon,
  CaptureIcon,
  ClusterIcon,
  CompassIcon,
  RouteIcon,
  SettingsIcon,
  SignalIcon,
  SparkIcon,
} from "../icons";

export interface PanelTalk {
  label: string;
  /** Sent to the agent when the user leaves the lens. */
  intent: string;
}

export interface PanelDefinition {
  id: WorkspacePanelId;
  /** Short label used by the rail and the lens header. */
  label: string;
  title: string;
  blurb: string;
  icon: ReactNode;
  render: () => ReactNode;
  /** The one sentence that takes the user back into the thread. */
  talk?: PanelTalk;
}

/**
 * Every entry is a lens on what the conversation has already produced. None of
 * them owns an input the agent could take more naturally as a message.
 */
export const WORKSPACE_PANELS: PanelDefinition[] = [
  {
    id: "catchup",
    label: "Catch up",
    title: "Catch up",
    blurb: "What moved while you were away, and what each signal asks of you.",
    icon: <BellIcon />,
    render: () => <CatchUpFeed />,
    talk: {
      label: "Talk through what changed",
      intent: "What changed since I was last here, and what should I do about it?",
    },
  },
  {
    id: "landscape",
    label: "Landscape",
    title: "Opportunity landscape",
    blurb: "Every outcome scored. Anything above 10 is underserved.",
    icon: <CompassIcon />,
    render: () => <OpportunityLandscape />,
    talk: {
      label: "Ask which to chase",
      intent: "Looking at my landscape, which opportunity should I chase first, and why?",
    },
  },
  {
    id: "jobmap",
    label: "Job map",
    title: "Universal job map",
    blurb: "The eight phases of the job, in the order customers live them.",
    icon: <RouteIcon />,
    render: () => <JobMap />,
    talk: {
      label: "Walk me through the job",
      intent:
        "Walk me through the job step by step, and show me where the work breaks down today.",
    },
  },
  {
    id: "segments",
    label: "Segments",
    title: "Segments and the bet",
    blurb: "Who the scored outcomes point at, and the strategy that follows from it.",
    icon: <ClusterIcon />,
    render: () => <SegmentBoard />,
    talk: {
      label: "Ask who this is for",
      intent:
        "Who is this for, according to the outcomes I have scored? Then tell me what to do about it, and name the paths you rejected.",
    },
  },
  {
    id: "evidence",
    label: "Evidence",
    title: "Customer evidence",
    blurb: "What customers actually said, and what it does and does not prove.",
    icon: <SignalIcon />,
    render: () => <EvidenceStream />,
    talk: {
      label: "Weigh the evidence",
      intent:
        "What does the evidence I have actually support, and what is still a guess? Tell me what to go find next.",
    },
  },
  {
    id: "memory",
    label: "What I know",
    title: "What I've learned",
    blurb: "What I've picked up about you and the work, and what I'm still guessing.",
    icon: <SparkIcon />,
    render: () => <MemoryPanel />,
    talk: {
      label: "Correct what you know",
      intent:
        "Here's what you've learned about me and the work so far. Ask me what's wrong or missing, and update your notes.",
    },
  },
  {
    id: "schedule",
    label: "Schedule",
    title: "Cloud Agent Scheduling",
    blurb: "Schedule, trigger, and inspect background cloud agent tasks.",
    icon: <BoltIcon />,
    render: () => <SchedulePanel />,
  },
  {
    id: "capture",
    label: "Capture",
    title: "Capture by hand",
    blurb: "The offline path. With a model, just tell the studio what you heard.",
    icon: <CaptureIcon />,
    render: () => <DirectCapture />,
    talk: {
      label: "Capture it in conversation",
      intent:
        "I heard something from a customer that I want to capture as an outcome. Ask me what they said.",
    },
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
