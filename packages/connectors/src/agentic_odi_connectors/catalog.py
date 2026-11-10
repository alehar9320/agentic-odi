"""Ready-to-use MCP connector presets for common ODI workflows.

Each preset captures everything needed to register a connector for a well-known
MCP server: the endpoint, how it authenticates, and where its documentation
lives. Presets are grouped by the five capability areas an outcome-driven
innovation process needs, so a new workspace can be wired up with
``agentic-odi connectors add mcp --preset <id>`` instead of hunting for URLs.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from agentic_odi_connectors.models import ConnectorConfig

CapabilityArea = Literal[
    "voice-of-customer",
    "quantitative-data",
    "market-intelligence",
    "strategy-alignment",
    "knowledge-output",
]

AREA_LABELS: dict[CapabilityArea, str] = {
    "voice-of-customer": "Voice of customer & qualitative research",
    "quantitative-data": "Quantitative data & opportunity scoring",
    "market-intelligence": "Market & competitive intelligence",
    "strategy-alignment": "Product strategy & backlog alignment",
    "knowledge-output": "Strategy & knowledge management output",
}

ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class UnknownPresetError(ValueError):
    def __init__(self, preset_id: str) -> None:
        self.preset_id = preset_id
        super().__init__(f"Unknown preset: {preset_id} (try 'agentic-odi connectors catalog')")


class UnknownAreaError(ValueError):
    def __init__(self, area: str) -> None:
        self.area = area
        valid = ", ".join(AREA_LABELS)
        super().__init__(f"Unknown capability area: {area} (expected one of: {valid})")


class ConnectorPreset(BaseModel):
    """A known MCP server plus the credentials it needs."""

    id: str
    label: str
    area: CapabilityArea
    summary: str
    url: str
    auth: Literal["none", "oauth"] = "none"
    env_vars: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    docs: str
    tools: list[str] = Field(default_factory=list)
    is_recommended: bool = False

    def referenced_env_vars(self) -> set[str]:
        """Environment variables the URL or headers interpolate with ``${VAR}``."""
        found: set[str] = set()
        for value in [self.url, *self.headers.values()]:
            found.update(ENV_VAR_PATTERN.findall(value))
        return found


PRESETS: tuple[ConnectorPreset, ...] = (
    # 1. Voice of customer & qualitative research
    ConnectorPreset(
        id="notion",
        label="Notion",
        is_recommended=True,
        area="voice-of-customer",
        summary="Interview notes, feedback logs, and PRDs from Notion pages.",
        url="https://mcp.notion.com/mcp",
        auth="oauth",
        docs="https://developers.notion.com/docs/mcp",
    ),
    ConnectorPreset(
        id="gong",
        label="Gong",
        area="voice-of-customer",
        summary="Sales and success call transcripts with direct customer quotes.",
        url="https://mcp.gong.io/mcp",
        auth="oauth",
        docs="https://help.gong.io/",
    ),
    ConnectorPreset(
        id="fireflies",
        label="Fireflies.ai",
        area="voice-of-customer",
        summary="Meeting transcripts and summaries for unmet-need mining.",
        url="https://mcp.fireflies.ai/mcp",
        auth="oauth",
        docs="https://docs.fireflies.ai/",
    ),
    ConnectorPreset(
        id="intercom",
        label="Intercom",
        area="voice-of-customer",
        summary="Support conversations and recurring customer frustrations.",
        url="https://mcp.intercom.com/mcp",
        auth="oauth",
        docs="https://developers.intercom.com/docs/guides/mcp",
    ),
    ConnectorPreset(
        id="confluence",
        label="Atlassian Confluence",
        area="voice-of-customer",
        summary="Existing PRDs, research write-ups, and product documentation.",
        url="https://mcp.atlassian.com/v1/mcp",
        auth="oauth",
        docs="https://www.atlassian.com/platform/remote-mcp-server",
    ),
    # 2. Quantitative data & opportunity scoring
    ConnectorPreset(
        id="posthog",
        label="PostHog",
        is_recommended=True,
        area="quantitative-data",
        summary="Feature usage, funnels, and drop-off rates for outcome scoring.",
        url="https://mcp.posthog.com/mcp",
        auth="oauth",
        docs="https://posthog.com/docs/model-context-protocol",
    ),
    ConnectorPreset(
        id="amplitude",
        label="Amplitude",
        area="quantitative-data",
        summary="Behavioral cohorts and adoption metrics behind each outcome.",
        url="https://mcp.amplitude.com/mcp",
        auth="oauth",
        docs="https://amplitude.com/docs/amplitude-ai/amplitude-mcp",
    ),
    ConnectorPreset(
        id="mixpanel",
        label="Mixpanel",
        area="quantitative-data",
        summary="Event analytics for importance and satisfaction evidence.",
        url="https://mcp.mixpanel.com/mcp",
        auth="oauth",
        docs="https://docs.mixpanel.com/docs/mcp",
    ),
    # 3. Market & competitive intelligence
    ConnectorPreset(
        id="exa",
        label="Exa",
        is_recommended=True,
        area="market-intelligence",
        summary="Semantic web search for competitor launches and market gaps.",
        url="https://mcp.exa.ai/mcp?exaApiKey=${EXA_API_KEY}",
        env_vars=["EXA_API_KEY"],
        docs="https://docs.exa.ai/reference/exa-mcp",
    ),
    ConnectorPreset(
        id="tavily",
        label="Tavily",
        area="market-intelligence",
        summary="Research-focused web search for pricing and industry trends.",
        url="https://mcp.tavily.com/mcp/?tavilyApiKey=${TAVILY_API_KEY}",
        env_vars=["TAVILY_API_KEY"],
        docs="https://docs.tavily.com/documentation/mcp",
    ),
    # 4. Product strategy & backlog alignment
    ConnectorPreset(
        id="linear",
        label="Linear",
        is_recommended=True,
        area="strategy-alignment",
        summary="Cross-reference prioritized outcomes with the existing backlog.",
        url="https://mcp.linear.app/mcp",
        auth="oauth",
        docs="https://linear.app/docs/mcp",
    ),
    ConnectorPreset(
        id="github",
        label="GitHub",
        is_recommended=True,
        area="strategy-alignment",
        summary="Issues, projects, and PRs to draft tickets from outcomes.",
        url="https://api.githubcopilot.com/mcp/",
        env_vars=["GITHUB_PERSONAL_ACCESS_TOKEN"],
        headers={"Authorization": "Bearer ${GITHUB_PERSONAL_ACCESS_TOKEN}"},
        docs=(
            "https://docs.github.com/en/copilot/customizing-copilot/"
            "using-model-context-protocol/extending-copilot-chat-with-mcp"
        ),
    ),
    ConnectorPreset(
        id="jira",
        label="Atlassian Jira",
        area="strategy-alignment",
        summary="Epics and issues to align delivery work with desired outcomes.",
        url="https://mcp.atlassian.com/v1/mcp",
        auth="oauth",
        docs="https://www.atlassian.com/platform/remote-mcp-server",
    ),
    ConnectorPreset(
        id="miro",
        label="Miro",
        area="strategy-alignment",
        summary="Outcome matrices and customer journey maps on a shared board.",
        url="https://mcp.miro.com/",
        auth="oauth",
        docs="https://developers.miro.com/docs/miro-mcp",
    ),
    ConnectorPreset(
        id="figma",
        label="Figma",
        area="strategy-alignment",
        summary="FigJam maps and design context for outcome workshops.",
        url="https://mcp.figma.com/mcp",
        auth="oauth",
        docs="https://developers.figma.com/docs/figma-mcp-server/",
    ),
    # 5. Strategy & knowledge management output
    ConnectorPreset(
        id="slack",
        label="Slack",
        area="knowledge-output",
        summary="Post opportunity-score digests and JTBD insights to channels.",
        url="https://mcp.slack.com/mcp",
        auth="oauth",
        docs="https://docs.slack.dev/ai/",
    ),
)


def list_presets(area: str | None = None, recommended: bool = False) -> list[ConnectorPreset]:
    """Return presets, optionally filtered by capability area or recommendation."""
    presets = list(PRESETS)
    if area is not None:
        if area not in AREA_LABELS:
            raise UnknownAreaError(area)
        presets = [preset for preset in presets if preset.area == area]
    if recommended:
        presets = [preset for preset in presets if preset.is_recommended]
    return presets


def get_preset(preset_id: str) -> ConnectorPreset:
    for preset in PRESETS:
        if preset.id == preset_id:
            return preset
    raise UnknownPresetError(preset_id)


def connector_config_from_preset(
    preset: ConnectorPreset,
    *,
    name: str | None = None,
    url: str | None = None,
    tools: list[str] | None = None,
    enabled: bool = True,
) -> ConnectorConfig:
    """Build a registry entry from a preset, allowing local overrides."""
    settings: dict[str, Any] = {
        "url": url or preset.url,
        "auth": preset.auth,
        "headers": dict(preset.headers),
        "env_vars": list(preset.env_vars),
        "tools": list(tools if tools is not None else preset.tools),
    }
    return ConnectorConfig(
        name=name or preset.id,
        kind="mcp",
        enabled=enabled,
        settings=settings,
    )


__all__ = [
    "AREA_LABELS",
    "ENV_VAR_PATTERN",
    "PRESETS",
    "CapabilityArea",
    "ConnectorPreset",
    "UnknownAreaError",
    "UnknownPresetError",
    "connector_config_from_preset",
    "get_preset",
    "list_presets",
]
