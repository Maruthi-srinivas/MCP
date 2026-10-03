"""Build or reuse the analysis file and return counts."""

from analysis_mcp.analysis.artifact import ensure_artifact, summary
from analysis_mcp.logging import observed_tool


@observed_tool
def analyze_code(repository_id: str) -> dict:
    """Return commit, analyzer version, counts, and warnings. Lists stay on the other tools."""
    return summary(repository_id, ensure_artifact(repository_id))
