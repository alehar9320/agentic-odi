"""Backend abstraction for CLI."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

from core import ODIService
from core.repository import Repository
from core.sqlite_repository import SQLiteRepository


class Backend(ABC):
    @abstractmethod
    def call(self, tool_name: str, args: dict) -> str:
        raise NotImplementedError


class LocalBackend(Backend):
    def __init__(self, db_path: str | None = None) -> None:
        repo: Repository = SQLiteRepository(db_path=db_path)
        self.service = ODIService(repo)

    def call(self, tool_name: str, args: dict) -> str:
        # Delegate to service and format
        if tool_name == "add_customer_outcome":
            co = self.service.add_customer_outcome(
                job_id=args["job_id"],
                customer_value=args["customer_value"],
                business_value=args["business_value"],
                step_id=args.get("step_id"),
            )
            return f"Customer outcome created successfully: {co.model_dump_json()}"
        if tool_name == "get_customer_outcome":
            try:
                co = self.service.get_customer_outcome(args["outcome_id"])
                return co.model_dump_json()
            except Exception as e:
                return str(e)
        if tool_name == "list_customer_outcomes":
            cos = self.service.list_customer_outcomes(args.get("job_id"))
            import json

            return json.dumps([c.model_dump() for c in cos])
        if tool_name == "update_customer_outcome":
            try:
                co = self.service.update_customer_outcome(args["outcome_id"], args)
                return f"Customer outcome updated successfully: {co.model_dump_json()}"
            except Exception as e:
                return str(e)
        if tool_name == "delete_customer_outcome":
            try:
                self.service.delete_customer_outcome(args["outcome_id"])
                return f"Customer outcome deleted successfully: {args['outcome_id']}"
            except Exception as e:
                return str(e)
        if tool_name == "compute_opportunity":
            score = self.service.compute_opportunity(args["importance"], args["satisfaction"])
            return f"Opportunity score: {score:.2f}"
        raise NotImplementedError(f"Unknown tool: {tool_name}")


class MCPBackend(Backend):
    def __init__(self, mcp_url: str) -> None:
        self.mcp_url = mcp_url

    def call(self, tool_name: str, args: dict) -> str:
        from cli.outcomes import _call_mcp

        return _call_mcp(tool_name, args, self.mcp_url)


def get_backend(
    backend: str | None = None, db_path: str | None = None, mcp_url: str | None = None
) -> Backend:
    if backend is None:
        backend = os.environ.get("AGENTIC_ODI_BACKEND", "local")
    if backend == "local":
        return LocalBackend(db_path=db_path)
    if backend == "mcp":
        return MCPBackend(mcp_url or os.environ.get("AGENTIC_ODI_MCP_URL", "http://localhost:8000/mcp"))
    raise ValueError(f"Unknown backend: {backend}")
