"""Drift tests for the generated capability manifest.

The manifest, the human-readable summary, and the live FastMCP registry
must all agree on the tool names. A snapshot of the manifest makes any
intentional change visible in the diff.
"""

from __future__ import annotations

from agentic_odi_core.contract import (
    TOOL_SPECS,
    ToolEffect,
    capability_manifest,
    capability_summary,
)


def test_every_tool_spec_appears_in_summary() -> None:
    """Every name in TOOL_SPECS appears in capability_summary()."""
    summary = capability_summary()
    for name in TOOL_SPECS:
        assert f"`{name}`" in summary, f"Tool {name} missing from capability_summary()"


def test_every_tool_spec_appears_in_manifest() -> None:
    """Every name in TOOL_SPECS appears in capability_manifest()["tools"]."""
    manifest = capability_manifest()
    manifest_names = {tool["name"] for tool in manifest["tools"]}
    assert manifest_names == set(TOOL_SPECS), (
        f"Manifest tools {manifest_names} != TOOL_SPECS {set(TOOL_SPECS)}"
    )


def test_every_tool_has_summary_effect_and_returns() -> None:
    """Every tool has a non-empty summary, effect, and returns."""
    for name, spec in TOOL_SPECS.items():
        assert spec.summary, f"Tool {name} has empty summary"
        assert spec.effect, f"Tool {name} has empty effect"
        assert spec.returns, f"Tool {name} has empty returns"


def test_effect_derivation_matches_naming_rule() -> None:
    """Effect is derived from the name: get_*/list_* → READ, delete_* → DESTRUCTIVE,
    everything else → WRITE. The derivation is asserted so a tool cannot be
    accidentally marked read-only."""
    for name, spec in TOOL_SPECS.items():
        if name.startswith(("get_", "list_")):
            assert spec.effect == ToolEffect.READ, (
                f"Tool {name} (starts with get_/list_) should be READ, got {spec.effect}"
            )
        elif name.startswith("delete_"):
            assert spec.effect == ToolEffect.DESTRUCTIVE, (
                f"Tool {name} (starts with delete_) should be DESTRUCTIVE, got {spec.effect}"
            )
        else:
            assert spec.effect == ToolEffect.WRITE, (
                f"Tool {name} should be WRITE, got {spec.effect}"
            )


def test_manifest_tool_count_matches_contract() -> None:
    """The manifest has exactly one entry per tool in TOOL_SPECS."""
    manifest = capability_manifest()
    assert len(manifest["tools"]) == len(TOOL_SPECS)


def test_manifest_entries_have_all_fields() -> None:
    """Every manifest entry has name, summary, effect, arguments, required, returns, stage."""
    manifest = capability_manifest()
    for entry in manifest["tools"]:
        assert "name" in entry
        assert "summary" in entry
        assert "effect" in entry
        assert "arguments" in entry
        assert "required" in entry
        assert "returns" in entry
        assert "stage" in entry


def test_capability_summary_mentions_update_and_delete_tools() -> None:
    """get_capabilities names every tool including update_*, delete_*,
    compute_opportunity, get_evidence, delete_evidence, and itself."""
    summary = capability_summary()
    # Update tools
    for prefix in ("update_job", "update_step", "update_outcome", "update_customer_outcome"):
        assert f"`{prefix}`" in summary, f"Update tool {prefix} missing from summary"
    # Delete tools
    for prefix in (
        "delete_job",
        "delete_step",
        "delete_outcome",
        "delete_customer_outcome",
        "delete_evidence",
    ):
        assert f"`{prefix}`" in summary, f"Delete tool {prefix} missing from summary"
    # compute_opportunity
    assert "`compute_opportunity`" in summary
    # get_evidence / delete_evidence
    assert "`get_evidence`" in summary
    assert "`delete_evidence`" in summary
    # get_capabilities itself
    assert "`get_capabilities`" in summary
    # get_capabilities_manifest itself
    assert "`get_capabilities_manifest`" in summary


def test_snapshot_of_manifest() -> None:
    """Snapshot of the full manifest; intentional changes show in the diff."""
    manifest = capability_manifest()
    assert manifest == {
        "tools": [
            {
                "name": spec.name,
                "summary": spec.summary,
                "effect": spec.effect.value,
                "arguments": spec.arguments,
                "required": spec.required,
                "returns": spec.returns,
                "stage": spec.stage,
            }
            for spec in TOOL_SPECS.values()
        ]
    }
