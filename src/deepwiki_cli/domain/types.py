"""Type aliases and constants for the domain layer."""

from typing import Literal

# Wiki importance levels
WikiImportance = Literal["high", "medium", "low"]

# Repository types
RepoType = Literal["github", "local"]

# Export formats
ExportFormat = Literal["markdown", "json"]


