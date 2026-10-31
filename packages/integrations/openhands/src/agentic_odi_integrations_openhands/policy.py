"""Deterministic confirmation policy for full autopilot.

The LLM's risk estimate is an input, not the decision. This module applies a
fixed allowlist and denylist so the same action always gets the same answer,
and so a prompt-injected agent cannot talk its way past a dangerous command.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from dataclasses import dataclass, field
from typing import Any

from agentic_odi_openhands.models import SecurityRisk

from agentic_odi_integrations_openhands.models import Decision

# Commands that end the run immediately, regardless of risk or allowlist.
_DENY_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f"), "rm -rf is never allowed"),
    (re.compile(r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*r"), "rm -rf is never allowed"),
    (re.compile(r"(^|[;&|]\s*)sudo\b"), "sudo is never allowed"),
    (re.compile(r"git\s+push\b[^\n]*--force"), "force-push is never allowed"),
    (re.compile(r"git\s+push\b[^\n]*(\s-f\b|--force-with-lease)"), "force-push is never allowed"),
    (re.compile(r"git\s+reset\s+--hard"), "git reset --hard discards work"),
    (re.compile(r"git\s+clean\s+-[a-zA-Z]*f"), "git clean -f deletes untracked work"),
    (re.compile(r"git\s+branch\s+-[a-zA-Z]*D"), "branch deletion is never allowed"),
    (re.compile(r"git\s+push\b[^\n]*--delete"), "remote branch deletion is never allowed"),
    (re.compile(r"git\s+merge\b"), "merging is outside the delivery boundary"),
    (re.compile(r"gh\s+pr\s+merge\b"), "merging a PR is never allowed"),
    (re.compile(r"gh\s+repo\s+delete\b"), "repository deletion is never allowed"),
    (re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE), "destructive SQL is never allowed"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE), "destructive SQL is never allowed"),
    (re.compile(r"\b(chmod|chown)\s+.*(/etc|/usr|/bin|/root)"), "system permission changes"),
    (re.compile(r"\b(npm|yarn|pnpm)\s+publish\b"), "package publishing is never allowed"),
    (re.compile(r"\btwine\s+upload\b"), "package publishing is never allowed"),
    (re.compile(r"\bdocker\b"), "docker is outside the sandbox scope"),
    (re.compile(r"\bkubectl\b|\bterraform\b|\baws\b|\bgcloud\b"), "cloud control is out of scope"),
    (re.compile(r"\bssh\b|\bscp\b|\brsync\b"), "remote shell/file transfer is out of scope"),
    (re.compile(r"(curl|wget)\b[^\n|]*\|\s*(sh|bash|zsh|python|node)\b"), "pipe-to-shell"),
    (re.compile(r"(?<![0-9&])>(?!&)\s*(?!/dev/null)"), "shell redirection is not allowed"),
    (re.compile(r"\$\(|`"), "command substitution is not allowed"),
    (re.compile(r"\.ssh(/|\b)"), "SSH material is out of scope"),
    (re.compile(r"(^|[\s/])\.env($|[\s\"'`;])"), "reading or writing .env is not allowed"),
    (re.compile(r"\.github/workflows"), "CI workflow edits require a human"),
    (re.compile(r"\bprintenv\b|(^|\s)env(\s|$)"), "dumping the environment is not allowed"),
    (re.compile(r"~/\.config/agentic-odi|agentic-odi/openhands\.json"), "credential files"),
    (
        re.compile(
            r"(^|[;&|]\s*)history\b|(^|[\s/])\.?(bash|zsh|sh|fish)_history\b"
        ),
        "shell history is out of scope",
    ),
)

_READ_ONLY_PROGRAMS = frozenset(
    {
        "ls",
        "cat",
        "head",
        "tail",
        "wc",
        "pwd",
        "file",
        "which",
        "tree",
        "diff",
        "rg",
        "grep",
        "find",
        "sed",
    }
)

_SAFE_GIT_SUBCOMMANDS = frozenset(
    {"status", "diff", "log", "show", "add", "commit", "branch", "rev-parse", "remote", "ls-files"}
)
_SAFE_GH_PR = frozenset({"create", "view", "list", "checks", "status", "diff", "comment"})
_SAFE_UV = frozenset({"run", "sync", "lock", "pip", "tree", "--version", "python"})
_SAFE_NPM = frozenset({"test", "run", "ci", "--version"})
_SAFE_NPM_RUN = frozenset({"typecheck", "lint", "build", "test"})

_EDITOR_WRITE_COMMANDS = frozenset(
    {"create", "str_replace", "insert", "write", "edit", "append", "mkdir"}
)
_EDITOR_READ_COMMANDS = frozenset({"view", "read", "open", "list", "ls"})

_WRITE_OUTSIDE_DENY = (
    "/etc/",
    "/usr/",
    "/bin/",
    "/sbin/",
    "/root/",
    "/boot/",
    "/proc/",
    "/sys/",
    ".ssh/",
    ".aws/",
    ".github/workflows/",
)

_DEFAULT_BRANCHES = frozenset({"main", "master"})


@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    rule_id: str
    reason: str


@dataclass(frozen=True)
class ActionRequest:
    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    risk: SecurityRisk = SecurityRisk.UNKNOWN
    repository: str | None = None
    default_branch: str | None = None
    workspace_root: str | None = None


def args_digest(arguments: dict[str, Any]) -> str:
    canonical = json.dumps(arguments, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _command(request: ActionRequest) -> str:
    for key in ("command", "cmd", "script"):
        value = request.arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _path(request: ActionRequest) -> str:
    for key in ("path", "file_path", "filename"):
        value = request.arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _denied(command: str) -> PolicyDecision | None:
    for pattern, reason in _DENY_PATTERNS:
        if pattern.search(command):
            return PolicyDecision(Decision.BLOCK, "denylist", reason)
    return None


def _path_decision(path: str, workspace_root: str | None) -> PolicyDecision | None:
    if not path:
        return None
    normalized = path.replace("\\", "/")
    if "/.github/workflows/" in f"/{normalized.lstrip('/')}" or normalized.startswith(
        ".github/workflows/"
    ):
        return PolicyDecision(Decision.BLOCK, "denylist", "CI workflow edits require a human")
    if "/.ssh/" in f"/{normalized.lstrip('/')}" or normalized.endswith(".env"):
        return PolicyDecision(Decision.BLOCK, "denylist", "credential files are out of scope")
    if ".." in normalized.split("/"):
        return PolicyDecision(Decision.BLOCK, "path_escape", "path traversal is not allowed")
    if normalized.startswith("/"):
        if workspace_root and normalized.startswith(workspace_root.rstrip("/") + "/"):
            return None
        if normalized == "/workspace" or normalized.startswith("/workspace/"):
            return None
        for denied in _WRITE_OUTSIDE_DENY:
            if denied in normalized:
                return PolicyDecision(
                    Decision.BLOCK, "denylist", f"writes to {denied} are not allowed"
                )
        return PolicyDecision(
            Decision.REJECT, "path_outside_repo", "write outside the selected repository"
        )
    return None


# Commands that, anywhere in a pipe, read stdin and execute it as code.
_SHELL_INTERPRETERS = frozenset(
    {
        "sh",
        "bash",
        "zsh",
        "dash",
        "ksh",
        "csh",
        "tcsh",
        "python",
        "python3",
        "node",
        "ruby",
        "perl",
        "php",
    }
)

# Tools whose primary use in a pipe is to send stdin off-host.
_EXFILTRATION_TOOLS = frozenset({"nc", "ncat", "netcat"})


def _simple_commands(tokens: list[str]) -> list[list[str]]:
    """Split a token list on pipe boundaries into simple commands."""
    commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token == "|":  # nosec B105 - "|" is a pipe operator, not a secret
            if current:
                commands.append(current)
                current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def _pipe_decision(tokens: list[str]) -> PolicyDecision | None:
    """Block pipes that route into a shell interpreter or exfiltration tool.

    The first command in a pipe may be read-only, but a later command such as
    ``sh`` or ``nc`` receives the piped input and can execute or exfiltrate it.
    Single commands with no pipe are left to the existing allowlist logic.
    """
    commands = _simple_commands(tokens)
    if len(commands) <= 1:
        return None
    for simple in commands:
        if not simple:
            continue
        program = simple[0]
        if program in _SHELL_INTERPRETERS:
            return PolicyDecision(
                Decision.BLOCK, "denylist", "pipe to shell interpreter is not allowed"
            )
        if program in _EXFILTRATION_TOOLS:
            return PolicyDecision(
                Decision.BLOCK, "denylist", "piped exfiltration is not allowed"
            )
    return None


def _split_command(command: str) -> list[list[str]]:
    """Split a shell line into simple commands; shell operators are boundaries."""
    parts = re.split(r"\s*(?:&&|\|\||;|\n)\s*", command)
    segments: list[list[str]] = []
    for part in parts:
        if not part.strip():
            continue
        try:
            segments.append(shlex.split(part))
        except ValueError:
            segments.append(part.split())
    return segments


def _git_push_decision(tokens: list[str]) -> PolicyDecision:
    rest = tokens[2:]
    for token in rest:
        if token in {"--all", "--mirror"}:
            return PolicyDecision(
                Decision.BLOCK, "push_all_branches", "pushing every branch is not allowed"
            )
        if token in {"--delete", "-d"}:
            return PolicyDecision(
                Decision.BLOCK, "push_delete_branch", "remote branch deletion is never allowed"
            )
        if token.startswith("--force") or (
            token.startswith("-") and not token.startswith("--") and "f" in token[1:]
        ):
            return PolicyDecision(Decision.BLOCK, "denylist", "force-push is never allowed")
    positionals = [token for token in rest if not token.startswith("-")]
    if len(positionals) < 2:
        return PolicyDecision(
            Decision.REJECT,
            "git_push_ambiguous",
            "push an explicit non-default branch (git push origin feature/name)",
        )
    for token in positionals:
        if token.startswith("+"):
            return PolicyDecision(Decision.BLOCK, "denylist", "force-push is never allowed")
        if token.startswith(":"):
            return PolicyDecision(
                Decision.BLOCK, "push_delete_branch", "remote branch deletion is never allowed"
            )
    ref = positionals[-1].split(":")[-1]
    if ref in _DEFAULT_BRANCHES:
        return PolicyDecision(
            Decision.BLOCK, "push_default_branch", "pushing to the default branch is not allowed"
        )
    return PolicyDecision(Decision.ACCEPT, "git_push_feature_branch", "non-force feature push")


def _git_decision(tokens: list[str]) -> PolicyDecision:
    if len(tokens) < 2:
        return PolicyDecision(Decision.REJECT, "git_incomplete", "incomplete git command")
    sub = tokens[1]
    if sub == "push":
        return _git_push_decision(tokens)
    if sub == "checkout" and ("-b" in tokens or "--orphan" in tokens):
        return PolicyDecision(Decision.ACCEPT, "git_checkout_branch", "creating a branch")
    if sub == "switch" and ("-c" in tokens or "--create" in tokens):
        return PolicyDecision(Decision.ACCEPT, "git_switch_create", "creating a branch")
    if sub in _SAFE_GIT_SUBCOMMANDS:
        return PolicyDecision(Decision.ACCEPT, "git_read_or_commit", f"git {sub} is allowed")
    return PolicyDecision(Decision.REJECT, "git_unlisted", f"git {sub} is not allowlisted")


def _command_decision(command: str, request: ActionRequest) -> PolicyDecision:
    denied = _denied(command)
    if denied is not None:
        return denied

    for tokens in _split_command(command):
        if not tokens:
            continue
        pipe = _pipe_decision(tokens)
        if pipe is not None:
            return pipe
        program = tokens[0]
        if program == "git":
            decision = _git_decision(tokens)
            if decision.decision != Decision.ACCEPT:
                return decision
            continue
        if program == "gh":
            if len(tokens) >= 3 and tokens[1] == "pr" and tokens[2] in _SAFE_GH_PR:
                continue
            return PolicyDecision(
                Decision.REJECT, "gh_unlisted", "only gh pr read/create/comment is allowed"
            )
        if program in {"pytest", "ruff", "mypy"}:
            continue
        if program == "uv":
            if len(tokens) >= 2 and tokens[1] in _SAFE_UV:
                continue
            return PolicyDecision(Decision.REJECT, "uv_unlisted", "uv subcommand not allowlisted")
        if program in {"npm", "yarn", "pnpm"}:
            if len(tokens) >= 2 and tokens[1] in _SAFE_NPM:
                if tokens[1] == "run" and len(tokens) >= 3 and tokens[2] not in _SAFE_NPM_RUN:
                    return PolicyDecision(
                        Decision.REJECT, "npm_script_unlisted", "npm script not allowlisted"
                    )
                continue
            return PolicyDecision(Decision.REJECT, "npm_unlisted", "npm subcommand not allowlisted")
        if program in {"python", "python3"}:
            if tokens[1:] in (["-V"], ["--version"]):
                continue
            if len(tokens) >= 3 and tokens[1] == "-m" and tokens[2] in {"pytest", "ruff", "mypy"}:
                continue
            return PolicyDecision(
                Decision.REJECT, "python_unlisted", "arbitrary python is not allowlisted"
            )
        if program == "find" and any(token in {"-delete", "-exec", "-execdir"} for token in tokens):
            return PolicyDecision(Decision.BLOCK, "denylist", "find -delete/-exec is not allowed")
        if program in _READ_ONLY_PROGRAMS:
            if program == "sed" and "-i" in tokens:
                return PolicyDecision(Decision.BLOCK, "denylist", "sed -i edits files")
            if program == "cat" and any(token.endswith(".env") for token in tokens):
                return PolicyDecision(Decision.BLOCK, "denylist", "reading .env is not allowed")
            continue
        if program in {"cd", "true", "echo"}:
            continue
        if program == "finish":
            continue
        return PolicyDecision(
            Decision.REJECT, "command_unlisted", f"command {program!r} is not allowlisted"
        )
    return PolicyDecision(Decision.ACCEPT, "command_allowlist", "allowlisted command")


class ApprovalPolicy:
    """Evaluate one pending action against the deterministic rules."""

    def __init__(self, rejection_limit: int = 3) -> None:
        self.rejection_limit = rejection_limit

    def evaluate(self, request: ActionRequest, prior_rejections: int = 0) -> PolicyDecision:
        tool = request.tool_name.lower().strip()

        if request.risk is SecurityRisk.HIGH:
            return PolicyDecision(
                Decision.BLOCK, "risk_high", f"{request.tool_name} was rated HIGH risk"
            )

        if tool in {"finish", "think", "task_tracker", "plan"}:
            return PolicyDecision(Decision.ACCEPT, "no_side_effect", "no side effects")

        if tool in {"glob", "grep"}:
            return PolicyDecision(Decision.ACCEPT, "repo_search", "repository search")

        if tool in {"str_replace_editor", "file_editor", "editor", "files"}:
            return self._editor(request)

        if tool in {"execute_bash", "bash", "terminal", "run_command"}:
            command = _command(request)
            if not command:
                return PolicyDecision(Decision.REJECT, "bash_no_command", "no command was provided")
            return _command_decision(command, request)

        if prior_rejections >= self.rejection_limit:
            return PolicyDecision(
                Decision.BLOCK,
                "rejection_limit",
                "too many unlisted actions; stopping for a human",
            )
        return PolicyDecision(
            Decision.REJECT,
            "tool_unlisted",
            f"tool {request.tool_name!r} is not in the allowlist",
        )

    def _editor(self, request: ActionRequest) -> PolicyDecision:
        command = str(request.arguments.get("command") or "view").lower()
        path = _path(request)
        path_decision = _path_decision(path, request.workspace_root)
        if path_decision is not None:
            return path_decision
        if command in _EDITOR_READ_COMMANDS:
            return PolicyDecision(Decision.ACCEPT, "editor_read", "README/edit read")
        if command in _EDITOR_WRITE_COMMANDS:
            if not path:
                return PolicyDecision(Decision.REJECT, "editor_no_path", "no file path provided")
            return PolicyDecision(
                Decision.ACCEPT, "editor_write_in_repo", "write inside the repository"
            )
        return PolicyDecision(
            Decision.REJECT, "editor_command_unlisted", f"editor command {command!r} not allowed"
        )
