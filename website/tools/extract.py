"""Read the product's own sources so the site can be rendered from them.

Every function here reads a file in the repository and returns plain data. This
module knows nothing about HTML: rendering belongs to ``build_site.py``.

The point of these readers is anti-drift. The site's tool reference, connector
catalog, CLI tree, and opportunity formula are not written by hand — they are
read from the same files the product runs on, so a change upstream shows up as
a change on the site on the next build.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

# The custom property syntax used by the Studio theme.
_TOKEN = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")


def _root_block(css: str, index: int) -> str:
    """The body of the ``index``-th top-level ``:root { ... }`` block."""
    blocks = re.findall(r":root\s*\{([^}]*)\}", css)
    if len(blocks) <= index:
        raise ValueError(f"no :root block at index {index}")
    return blocks[index]


def read_tokens(studio_theme: Path) -> dict[str, str]:
    """The Studio theme's first ``:root`` block: the canonical palette.

    The Studio declares its palette first and its easings in a second ``:root``
    block appended much later. This returns the palette; use
    :func:`read_easings` for the motion curves.
    """
    css = studio_theme.read_text(encoding="utf-8")
    return {name: value.strip() for name, value in _TOKEN.findall(_root_block(css, 0))}


def read_easings(studio_theme: Path) -> dict[str, str]:
    """The Studio theme's second ``:root`` block: the motion easings."""
    css = studio_theme.read_text(encoding="utf-8")
    return {name: value.strip() for name, value in _TOKEN.findall(_root_block(css, 1))}


def read_odi_formula(core_models: Path) -> str:
    """The opportunity formula, exactly as the core module computes it.

    The expression appears twice in ``models.py`` — in the docstring and in
    the return statement. Both are matched, so the site quotes the code
    rather than a transcription of it.
    """
    source = core_models.read_text(encoding="utf-8")
    pattern = re.compile(
        r"importance\s*\+\s*max\(\s*importance\s*-\s*satisfaction\s*,\s*0(?:\.0)?\s*\)"
    )
    for line in source.splitlines():
        match = pattern.search(line)
        if match:
            return match.group(0)
    raise ValueError("the opportunity formula was not found in the core models")


def read_odi_schema(schema_py: Path) -> dict[str, Any]:
    """The canonical ODI entity schema.

    The module is a pure data module with no import-time side effects, so
    importing it is both accurate and cheap.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("odi_schema_module", schema_py)
    if spec is None or spec.loader is None:
        raise ValueError(f"could not load the ODI schema from {schema_py}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.odi_schema()


def read_connectors(catalog_py: Path) -> list[dict[str, Any]]:
    """The connector presets, in source order, with their capability area.

    The catalog is the single source of truth for which connectors ship.
    """
    source = catalog_py.read_text(encoding="utf-8")
    tree = ast.parse(source)

    area_labels = _read_area_labels(tree)
    presets: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_connector_preset(node):
            continue
        fields = {kw.arg: _literal(kw.value) for kw in node.keywords if kw.arg}
        env_vars = list(fields.get("env_vars", []))
        presets.append(
            {
                "id": fields.get("id", ""),
                "label": fields.get("label", ""),
                "area": fields.get("area", ""),
                "area_label": area_labels.get(fields.get("area", ""), ""),
                "summary": fields.get("summary", ""),
                "url": fields.get("url", ""),
                "auth": _auth_label(fields.get("auth", "none"), env_vars),
                "env_vars": env_vars,
                "recommended": bool(fields.get("is_recommended", False)),
                "docs": fields.get("docs", ""),
            }
        )
    if not presets:
        raise ValueError("no connector presets were found in the catalog")
    return presets


def _auth_label(auth: str, env_vars: list[str]) -> str:
    """How a preset authenticates, in the CLI's own words.

    Mirrors ``agentic-odi connectors catalog`` so the site and the terminal
    say the same thing.
    """
    if auth == "oauth":
        return "oauth"
    if env_vars:
        return "api key"
    return "none"


def read_catalog_cards(catalog_ts: Path) -> list[dict[str, str]]:
    """The ODI cards the agent may compose, with their descriptions.

    The catalog is TypeScript, so it is read as text rather than imported.
    The file separates primitives from cards with a marker comment; only the
    top-level ``entry(...)`` calls after that marker are the shapes worth
    naming. Nested entries — the job stages, for instance — are not cards.
    """
    source = catalog_ts.read_text(encoding="utf-8")
    marker = re.search(r"//\s*-+\s*cards\s*$", source, re.MULTILINE)
    if marker is None:
        raise ValueError("the cards section was not found in the UI catalog")
    body = source[marker.end() :]

    cards: list[dict[str, str]] = []
    for call in _balanced_calls(body, "entry"):
        arguments = _string_arguments(call)
        if len(arguments) >= 3:
            cards.append(
                {
                    "type": arguments[0],
                    "kind": arguments[1],
                    "description": arguments[2],
                }
            )
    if not cards:
        raise ValueError("no ODI cards were found in the UI catalog")
    return cards


def _balanced_calls(body: str, name: str) -> list[str]:
    """The bodies of every top-level ``name(...)`` call in a block of source."""
    calls: list[str] = []
    for match in re.finditer(rf"\b{name}\s*\(", body):
        start = match.end()
        depth = 1
        index = start
        while index < len(body) and depth:
            char = body[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        if depth == 0:
            calls.append(body[start : index - 1])
    return calls


def _string_arguments(call: str) -> list[str]:
    """The leading string arguments of a call body."""
    arguments: list[str] = []
    for match in re.finditer(r'"((?:[^"\\]|\\.)*)"', call):
        arguments.append(match.group(1))
        if len(arguments) == 3:
            break
    return arguments


def read_roadmap_pending(roadmap_md: Path) -> list[str]:
    """The roadmap items that are not yet done.

    An empty list means nothing is queued — the site says so rather than
    inventing something to look forward to.
    """
    source = roadmap_md.read_text(encoding="utf-8")
    pending = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            pending.append(stripped[5:].strip())
    return pending


def group_connectors_by_area(presets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group the presets by capability area, in the catalog's own order."""
    areas: dict[str, dict[str, Any]] = {}
    for preset in presets:
        area = areas.setdefault(
            preset["area"],
            {"area": preset["area"], "label": preset["area_label"], "connectors": []},
        )
        area["connectors"].append(preset)
    return list(areas.values())


def _is_connector_preset(node: ast.Call) -> bool:
    func = node.func
    return isinstance(func, ast.Name) and func.id == "ConnectorPreset"


def _read_area_labels(tree: ast.Module) -> dict[str, str]:
    """The ``AREA_LABELS`` mapping: capability area -> human label."""
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "AREA_LABELS":
            mapping = node.value
            if not isinstance(mapping, ast.Dict):
                break
            labels: dict[str, str] = {}
            for key, value in zip(mapping.keys, mapping.values, strict=True):
                if isinstance(key, ast.Constant) and isinstance(value, ast.Constant):
                    labels[str(key.value)] = str(value.value)
            if labels:
                return labels
    raise ValueError("AREA_LABELS was not found in the connector catalog")


def _literal(node: ast.AST) -> Any:
    """Evaluate a literal node, tolerating the few non-literal forms used."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_literal(item) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal(item) for item in node.elts)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        # e.g. Field(default_factory=list) — not interesting for the site.
        return None
    return None


def read_tool_names(contract_py: Path) -> list[str]:
    """The MCP tool names, from the contract's ``ToolName`` enum."""
    tree = ast.parse(contract_py.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "ToolName":
            names = []
            for item in node.body:
                if isinstance(item, ast.Assign) and isinstance(item.value, ast.Constant):
                    names.append(str(item.value.value))
            if names:
                return names
    raise ValueError("the ToolName enum was not found in the contract")


def read_tools(mcp_server_py: Path, contract_py: Path) -> list[dict[str, Any]]:
    """Every MCP tool: its name, purpose, and typed parameters.

    The tools are read from the source rather than the live registry so the
    build has no side effects and no dependency on FastMCP internals. The
    names are cross-checked against the contract, which is itself
    contract-tested against the live registry.
    """
    declared = read_tool_names(contract_py)
    found: dict[str, dict[str, Any]] = {}

    tree = ast.parse(mcp_server_py.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not any(_is_mcp_tool(dec) for dec in node.decorator_list):
            continue
        found[node.name] = {
            "name": node.name,
            "purpose": TOOL_PURPOSES.get(node.name, "See the MCP server source for details."),
            "params": _read_params(node),
        }

    missing = [name for name in declared if name not in found]
    if missing:
        raise ValueError(f"tools declared in the contract but not implemented: {missing}")
    extra = [name for name in found if name not in declared]
    if extra:
        raise ValueError(f"tools implemented but not declared in the contract: {extra}")

    return [found[name] for name in declared]


def _is_mcp_tool(decorator: ast.AST) -> bool:
    """Whether a decorator is the ``@mcp.tool`` marker.

    The server writes it bare (``@mcp.tool``); the call form
    (``@mcp.tool()``) is accepted too.
    """
    if isinstance(decorator, ast.Call):
        decorator = decorator.func
    return (
        isinstance(decorator, ast.Attribute)
        and decorator.attr == "tool"
        and isinstance(decorator.value, ast.Name)
        and decorator.value.id == "mcp"
    )


def _read_params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[dict[str, Any]]:
    """A function's parameters, with annotations and defaults."""
    args = node.args
    positional = list(args.posonlyargs) + list(args.args)
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(args.defaults))
    defaults.extend(args.defaults)

    params: list[dict[str, Any]] = []
    for arg, default in zip(positional, defaults, strict=True):
        if arg.arg in {"self", "cls"}:
            continue
        params.append(
            {
                "name": arg.arg,
                "annotation": ast.unparse(arg.annotation) if arg.annotation else "",
                "default": ast.unparse(default) if default is not None else None,
                "required": default is None,
            }
        )

    for arg, default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
        params.append(
            {
                "name": arg.arg,
                "annotation": ast.unparse(arg.annotation) if arg.annotation else "",
                "default": ast.unparse(default) if default is not None else None,
                "required": default is None,
            }
        )
    return params


def read_cli(cli_py: Path) -> list[dict[str, Any]]:
    """The CLI command tree: top-level commands and their sub-commands."""
    tree = ast.parse(cli_py.read_text(encoding="utf-8"))
    commands: list[dict[str, Any]] = []
    subapps: dict[str, list[dict[str, Any]]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute):
            continue

        if func.attr == "command" and isinstance(func.value, ast.Name):
            name = _kwarg(node, "name")
            if not name:
                continue
            commands.append({"name": name, "help": _kwarg(node, "help") or ""})
        elif func.attr == "add_typer" and isinstance(func.value, ast.Name):
            name = _kwarg(node, "name")
            if not name:
                continue
            subapps.setdefault(name, [])

    # Sub-commands hang off the typer objects registered with add_typer.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Attribute) or call.func.attr != "command":
            continue
        if not isinstance(call.func.value, ast.Name):
            continue
        parent = call.func.value.id
        if parent not in subapps:
            continue
        name = _kwarg(call, "name")
        if not name:
            continue
        subapps[parent].append({"name": name, "help": _kwarg(call, "help") or ""})

    for command in commands:
        command["subcommands"] = subapps.get(command["name"], [])
    return sorted(commands, key=lambda item: item["name"])


def _kwarg(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == name and isinstance(keyword.value, ast.Constant):
            return str(keyword.value.value)
    return None


# A one-line purpose for every tool the MCP server exposes. Kept here, next to
# the reader, so the reference page reads like documentation rather than a
# signature dump.
TOOL_PURPOSES: dict[str, str] = {
    "add_job": "Create a Job-to-be-Done.",
    "get_jobs": "List Jobs, one page at a time.",
    "get_job": "Fetch one Job by id.",
    "update_job": "Rename a Job or change its description.",
    "delete_job": "Delete a Job and everything under it.",
    "add_step": "Add a step to a Job's map.",
    "get_job_map": "Return a Job's ordered steps, one page at a time.",
    "get_step": "Fetch one step by id.",
    "update_step": "Rename a step or move it in the order.",
    "delete_step": "Delete a step.",
    "add_outcome": "Record a desired outcome with importance and satisfaction.",
    "get_outcomes": "List the desired outcomes of a Job or step, one page at a time.",
    "get_outcome": "Fetch one desired outcome by id.",
    "update_outcome": "Edit an outcome's statement or scores.",
    "delete_outcome": "Delete a desired outcome.",
    "add_customer_outcome": "Record a customer outcome with customer and business value.",
    "get_customer_outcome": "Fetch one customer outcome by id.",
    "list_customer_outcomes": "List customer outcomes, optionally for one Job, one page at a time.",
    "update_customer_outcome": "Edit a customer outcome's values.",
    "delete_customer_outcome": "Delete a customer outcome.",
    "add_evidence": "Attach a research record as evidence.",
    "get_evidence": "Fetch one evidence record by id.",
    "list_evidence": "List evidence, optionally for one Job, one page at a time.",
    "delete_evidence": "Delete an evidence record.",
    "promote_evidence": "Promote a record into a Job, outcome, or customer outcome.",
    "evaluate_outcome": "Check a statement against the ODI format before saving it.",
    "get_odi_schema": "Return the canonical JSON schema for every ODI entity.",
    "compute_opportunity": "Score an importance and satisfaction pair.",
    "get_odi_framework_guidelines": "Say which tool to use at each stage of ODI.",
    "get_capabilities": "Describe what the assistant can help with.",
    "get_capabilities_manifest": "Return the whole tool surface as machine-readable JSON.",
    "extract_candidates": "Propose outcomes from one quote; proposes, accepts nothing.",
    "list_candidates": "List proposed outcomes, optionally by quote, Job, or status, one page at a time.",
    "get_candidate": "Fetch one proposed outcome by id.",
    "accept_candidate": "Accept a proposed outcome, creating exactly one Outcome.",
    "reject_candidate": "Reject a proposed outcome; the reason is required and kept.",
    "merge_candidate": "Fold a proposed outcome into an existing Outcome; creates none.",
    "get_outcome_score": "Read an outcome's scores as a sample; an unscored outcome reports nothing yet.",
    "get_brief": "Render the brief for a subject; every figure carries its basis.",
    "record_decision": "Record a decision about a subject, with its rationale.",
    "track_bet": "Track a bet under a decision, with the metric that would move.",
    "get_measurement": "Read what a bet measured; an unmeasured bet reports nothing yet.",
}
