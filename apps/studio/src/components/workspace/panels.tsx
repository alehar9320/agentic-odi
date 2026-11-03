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
import { RecordsPanel } from "../records/RecordsPanel";
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
  TableIcon,
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
    id: "records",
    label: "Records",
    title: "Records",
    blurb: "Everything the store holds, with the ids and the values it returned.",
    icon: <TableIcon />,
    render: () => <RecordsPanel />,
    talk: {
      label: "Ask what's missing here",
      intent:
        "Here are the records I have stored. What is missing, duplicated, or inconsistent? Ask me before you change anything.",
    },
  },
  {
    id: "catchup",
    label: "What changed",
    title: "What changed",
    blurb: "New updates and actions you need to take.",
    icon: <BellIcon />,
    render: () => <CatchUpFeed />,
    talk: {
      label: "Walk through what's new",
      intent: "What changed since I was last here, and what should I do about it?",
    },
  },
  {
    id: "landscape",
    label: "Where to play",
    title: "Where to play",
    blurb: "Gaps worth chasing. Focus here where customers struggle most.",
    icon: <CompassIcon />,
    render: () => <OpportunityLandscape />,
    talk: {
      label: "Ask which gap to chase",
      intent: "Looking at my landscape, which opportunity should I chase first, and why?",
    },
  },
  {
    id: "jobmap",
    label: "The job",
    title: "The job",
    blurb: "The steps customers go through to get something done.",
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
    label: "Who this is for",
    title: "Who this is for",
    blurb: "The people who feel the gap, and what they're trying to do.",
    icon: <ClusterIcon />,
    render: () => <SegmentBoard />,
    talk: {
      label: "Ask who this is for",
      intent:
        "Who is this for, based on what I know? Then tell me what to do about it, and name the paths I should avoid.",
    },
  },
  {
    id: "evidence",
    label: "What customers said",
    title: "What customers said",
    blurb: "Direct quotes from customers and what they reveal.",
    icon: <SignalIcon />,
    render: () => <EvidenceStream />,
    talk: {
      label: "Weigh what they said",
      intent:
        "What does the evidence I have actually support, and what is still a guess? Tell me what to look for next.",
    },
  },
  {
    id: "memory",
    label: "What I know",
    title: "What I know",
    blurb: "Insights I've gathered and what I'm still figuring out.",
    icon: <SparkIcon />,
    render: () => <MemoryPanel />,
    talk: {
      label: "Correct what I know",
      intent:
        "Here's what I've learned so far. Ask what's wrong or missing, and update my notes.",
    },
  },
  {
    id: "schedule",
    label: "Schedule",
    title: "Background tasks",
    blurb: "Set up tasks that run on their own.",
    icon: <BoltIcon />,
    render: () => <SchedulePanel />,
  },
  {
    id: "capture",
    label: "Capture",
    title: "Capture insights",
    blurb: "Add what you heard from customers.",
    icon: <CaptureIcon />,
    render: () => <DirectCapture />,
    talk: {
      label: "Add what I heard",
      intent:
        "I heard something from a customer that I want to add. Ask me what they said.",
    },
  },
];

export const SETTINGS_PANEL: PanelDefinition = {
  id: "settings",
  label: "Settings",
  title: "Settings",
  blurb: "Connect your model and tools.",
  icon: <SettingsIcon />,
  render: () => <SettingsPanel />,
};

export function findPanel(id: WorkspacePanelId): PanelDefinition {
  if (id === "settings") {
    return SETTINGS_PANEL;
  }
  return WORKSPACE_PANELS.find((panel) => panel.id === id) ?? SETTINGS_PANEL;
}
