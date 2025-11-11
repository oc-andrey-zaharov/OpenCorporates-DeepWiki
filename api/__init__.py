"""API package for OpenCorporates-DeepWiki."""

try:
    from importlib.metadata import version

    __version__ = version("opencorporates-deepwiki-api")
except (ImportError, OSError):
    __version__ = "unknown"
