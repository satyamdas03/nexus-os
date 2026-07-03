"""Native tool adapters for NEXUS OS."""

from nexus_os.tools.filesystem import safe_write
from nexus_os.tools.git import is_git_repo

__all__ = ["is_git_repo", "safe_write"]
