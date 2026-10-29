"""Validation and tool schema generation for agent-composed UI.

The sidecar is deliberately catalog-agnostic: the client sends the manifest of
what it can render with each turn, and this module derives both the ``render_ui``
tool schema and the validator from it. There is exactly one source of truth for
the catalog, and it lives with the renderer that has to honour it.

Errors returned by :meth:`UiCatalog.validate` are fed straight back to the model
as the tool result, so a fumbled prop becomes a same-turn correction rather than
a silent blank space in the conversation.
"""

from __future__ import annotations

from typing import Any

MAX_DEPTH = 12
MAX_NODES = 200
MAX_STRING_LENGTH = 2000
MAX_CHILDREN = 32

RENDER_UI_TOOL = "render_ui"

# Surfaces whose content can be mistaken for a measurement must say whether
# they describe live data or a demonstration. The client's catalog carries the
# same rule; this is the server-side backstop for an older or edited manifest.
REQUIRED_PROVENANCE: dict[str, tuple[str, ...]] = {
    # #95 adds a real computation; until then a simulation can only be a label,
    # never a measurement.
    "impact-simulation": ("simulated",),
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class UiCatalog:
    """The client's renderable catalog, as a tool schema and a validator."""

    def __init__(self, components: list[dict[str, Any]]) -> None:
        self._order: list[str] = []
        self._components: dict[str, dict[str, Any]] = {}
        for component in components:
            if not isinstance(component, dict):
                continue
            name = component.get("type")
            if not isinstance(name, str) or not name or name in self._components:
                continue
            self._order.append(name)
            self._components[name] = component

    @classmethod
    def from_manifest(cls, manifest: Any) -> UiCatalog | None:
        """Build a catalog from a request manifest, or ``None`` if unusable."""
        if not isinstance(manifest, dict):
            return None
        components = manifest.get("components")
        if not isinstance(components, list):
            return None
        catalog = cls(components)
        return catalog if catalog.types else None

    @property
    def types(self) -> list[str]:
        return list(self._order)

    # ------------------------------------------------------------------ schema

    def tool_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "description": (
                "One UI node. Put the content in `props` and nest layouts with "
                "`children`. The component catalog is in the tool description."
            ),
            "properties": {
                "type": {
                    "type": "string",
                    "enum": self.types,
                    "description": "Which surface to render.",
                },
                "props": {
                    "type": "object",
                    "description": "Props for the chosen type, as described in the catalog.",
                },
                "children": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Child nodes. Only layout types accept them.",
                },
            },
            "required": ["type"],
        }

    def describe(self) -> str:
        """Compact catalogue the model reads, one line per component."""
        lines = []
        for name in self._order:
            component = self._components[name]
            props_schema = component.get("props") or {}
            required = set(props_schema.get("required") or [])
            properties = props_schema.get("properties") or {}
            props = ", ".join(
                f"{prop}*" if prop in required else prop for prop in properties if prop != "actions"
            )
            description = component.get("description") or ""
            children = " Children allowed." if component.get("acceptsChildren") else ""
            actions = " Optional actions." if "actions" in properties else ""
            lines.append(f"- {name}({props}) — {description}{children}{actions}")
        return "\n".join(lines)

    # -------------------------------------------------------------- validation

    def validate(self, spec: Any) -> str | None:
        """Return a human-readable problem, or ``None`` when the spec is valid."""
        return self._validate_node(spec, 0, {"nodes": 0})

    def _validate_node(self, node: Any, depth: int, state: dict[str, int]) -> str | None:
        if depth > MAX_DEPTH:
            return f"the UI tree is deeper than {MAX_DEPTH} levels"
        state["nodes"] += 1
        if state["nodes"] > MAX_NODES:
            return f"the UI tree has more than {MAX_NODES} nodes"

        if not isinstance(node, dict):
            return "a UI node must be an object"

        name = node.get("type")
        if not isinstance(name, str) or not name:
            return "a UI node needs a `type`"

        component = self._components.get(name)
        if component is None:
            allowed = ", ".join(self.types)
            return f"`{name}` is not a renderable type. Use one of: {allowed}"

        props = node.get("props")
        if props is None:
            props = {}
        if not isinstance(props, dict):
            return f"`{name}.props` must be an object"

        props_schema = component.get("props") or {}
        problem = self._validate_props(props, props_schema, f"{name}.props")
        if problem:
            return problem

        allowed_labels = REQUIRED_PROVENANCE.get(name)
        if allowed_labels is not None:
            label = props.get("provenance")
            if label not in allowed_labels:
                allowed = ", ".join(allowed_labels)
                return f"`{name}.props.provenance` must be one of: {allowed}"

        children = node.get("children")
        if children is not None and not isinstance(children, list):
            return f"`{name}.children` must be an array"
        if children and not component.get("acceptsChildren"):
            # Same tolerance as the client: stray children are dropped, not fatal.
            return None
        if children and len(children) > MAX_CHILDREN:
            # The client rejects the whole tree past this ceiling, so reject here
            # rather than let a surface that never renders look like a success.
            return f"`{name}` accepts at most {MAX_CHILDREN} children"
        for index, child in enumerate(children or []):
            problem = self._validate_node(child, depth + 1, state)
            if problem:
                return f"child {index}: {problem}"

        return None

    def _validate_props(
        self, props: dict[str, Any], schema: dict[str, Any], path: str
    ) -> str | None:
        properties = schema.get("properties") or {}
        required = schema.get("required") or []

        for name in required:
            if name not in props:
                return f"`{path}.{name}` is required"

        for name, value in props.items():
            prop_schema = properties.get(name)
            if not isinstance(prop_schema, dict):
                continue  # unknown props are stripped, matching the renderer
            problem = self._validate_value(value, prop_schema, f"{path}.{name}")
            if problem and name in required:
                return problem

        return None

    def _validate_value(self, value: Any, schema: dict[str, Any], path: str) -> str | None:
        enum = schema.get("enum")
        if isinstance(enum, list):
            if value not in enum:
                return f"`{path}` must be one of: {', '.join(str(item) for item in enum)}"
            return None

        kind = schema.get("type")

        if kind == "string":
            if not isinstance(value, str):
                return f"`{path}` must be a string"
            if len(value) > MAX_STRING_LENGTH:
                return f"`{path}` is longer than {MAX_STRING_LENGTH} characters"
            return None

        if kind in ("number", "integer"):
            if not _is_number(value):
                return f"`{path}` must be a number"
            if kind == "integer" and float(value) != int(value):
                return f"`{path}` must be an integer"
            minimum = schema.get("minimum")
            maximum = schema.get("maximum")
            if minimum is not None and value < minimum:
                return f"`{path}` must be at least {minimum}"
            if maximum is not None and value > maximum:
                return f"`{path}` must be at most {maximum}"
            return None

        if kind == "boolean":
            return None if isinstance(value, bool) else f"`{path}` must be a boolean"

        if kind == "array":
            if not isinstance(value, list):
                return f"`{path}` must be an array"
            minimum_items = schema.get("minItems")
            maximum_items = schema.get("maxItems")
            if isinstance(minimum_items, int) and len(value) < minimum_items:
                return f"`{path}` needs at least {minimum_items} items"
            if isinstance(maximum_items, int) and len(value) > maximum_items:
                return f"`{path}` allows at most {maximum_items} items"
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    problem = self._validate_value(item, item_schema, f"{path}[{index}]")
                    if problem:
                        return problem
            return None

        if kind == "object":
            if not isinstance(value, dict):
                return f"`{path}` must be an object"
            return self._validate_props(value, schema, path)

        return None


__all__ = [
    "MAX_CHILDREN",
    "MAX_DEPTH",
    "MAX_NODES",
    "RENDER_UI_TOOL",
    "REQUIRED_PROVENANCE",
    "UiCatalog",
]
