"""Typed failures returned to MCP clients as the PRD error object."""

from investigator_shared.errors import ToolFailure, error_body

__all__ = ["ToolFailure", "error_body"]
