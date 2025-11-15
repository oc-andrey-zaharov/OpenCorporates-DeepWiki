"""CLI package for OpenCorporates DeepWiki."""

from importlib import metadata

try:
    __version__ = metadata.version("opencorporates-deepwiki-cli")
except metadata.PackageNotFoundError:  # pragma: no cover - fallback during dev
    from .__version__ import __version__

__all__ = ["__version__"]
