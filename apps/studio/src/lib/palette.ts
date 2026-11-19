/**
 * Deterministic command palette item registry.
 *
 * Builds a flat, typed list of palette items from the slash-command registry
 * (`STUDIO_COMMANDS`) and the workspace panel definitions, then ranks matches
 * purely by text: exact > prefix > substring, ties broken by group order then
 * registry order. No UI, no network, no artifact search, no recents, no model.
 */

import type { StudioCommand } from "./commands";
import { STUDIO_COMMANDS } from "./commands";
import { SETTINGS_PANEL, WORKSPACE_PANELS, type PanelDefinition } from "../components/workspace/panels";

export type PaletteGroup = "commands" | "panels";

export const GROUP_ORDER: Record<PaletteGroup, number> = {
  commands: 0,
  panels: 1,
};

export interface PaletteItem {
  id: string;
  /** The typed form, including the slash for commands. */
  name: string;
  label: string;
  description: string;
  /** The heading the item is listed under. */
  category: string;
  group: PaletteGroup;
  /** Stable position within its group's registry. */
  index: number;
  disabled?: boolean;
  disabledReason?: string;
  keywords?: string[];
}

function commandToItem(command: StudioCommand, index: number): PaletteItem {
  return {
    id: command.id,
    name: command.name,
    label: command.label,
    description: command.description,
    category: command.category,
    group: "commands",
    index,
    keywords: command.keywords,
  };
}

function panelToItem(panel: PanelDefinition, index: number): PaletteItem {
  return {
    id: panel.id,
    name: panel.id,
    label: panel.label,
    description: panel.blurb,
    category: "Panels",
    group: "panels",
    index,
  };
}

/**
 * The full, deterministic registry: every slash command in declared order,
 * then every workspace panel in declared order. Pure: no side effects.
 */
export function buildPaletteItems(): PaletteItem[] {
  const items: PaletteItem[] = [];
  STUDIO_COMMANDS.forEach((command, index) => {
    items.push(commandToItem(command, index));
  });
  [...WORKSPACE_PANELS, SETTINGS_PANEL].forEach((panel, index) => {
    items.push(panelToItem(panel, index));
  });
  return items;
}

function normalize(value: string): string {
  return value.trim().toLowerCase();
}

function stripSlash(name: string): string {
  return name.replace(/^\//, "");
}

function scoreItem(item: PaletteItem, query: string): number | null {
  const name = stripSlash(item.name).toLowerCase();
  const haystack = [name, item.label, item.description, ...(item.keywords ?? [])]
    .join(" ")
    .toLowerCase();
  if (name === query) {
    return 0;
  }
  if (name.startsWith(query)) {
    return 1;
  }
  if (haystack.includes(query)) {
    return 2;
  }
  return null;
}

/**
 * Rank `items` against `query`: exact > prefix > substring; ties broken by
 * group order then registry order. An empty query returns no items. Disabled
 * items are kept, tagged with their reason, never dropped.
 */
export function matchPaletteItems(items: PaletteItem[], query: string): PaletteItem[] {
  const trimmed = normalize(query);
  if (!trimmed) {
    return [];
  }

  return items
    .map((item, index) => ({ item, index, score: scoreItem(item, trimmed) }))
    .filter((entry) => entry.score !== null)
    .sort((a, b) => {
      if (a.score !== b.score) {
        return a.score! - b.score!;
      }
      const groupA = GROUP_ORDER[a.item.group];
      const groupB = GROUP_ORDER[b.item.group];
      if (groupA !== groupB) {
        return groupA - groupB;
      }
      return a.item.index - b.item.index;
    })
    .map((entry) => entry.item);
}

/**
 * Convenience: match the built registry against `query`.
 */
export function paletteItemsFor(query: string): PaletteItem[] {
  return matchPaletteItems(buildPaletteItems(), query);
}
