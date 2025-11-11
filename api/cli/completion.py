"""
Shell completion helpers for DeepWiki CLI.
"""

import os
from typing import List
from click.shell_completion import CompletionItem

from api.cli.config import get_provider_models
from api.cli.utils import get_cache_path
from api.utils.wiki_cache import parse_cache_filename


def complete_providers(ctx, param, incomplete: str) -> List[CompletionItem]:
    """Complete provider names from configuration."""
    try:
        provider_models = get_provider_models()
        providers = list(provider_models.keys())
        return [
            CompletionItem(provider)
            for provider in providers
            if provider.startswith(incomplete)
        ]
    except Exception:
        return []


def complete_models(ctx, param, incomplete: str) -> List[CompletionItem]:
    """Complete model names, optionally filtered by provider."""
    try:
        provider_models = get_provider_models()

        # Try to get provider from context if available
        provider = None
        if ctx.params and "provider" in ctx.params:
            provider = ctx.params["provider"]
        elif ctx.parent and ctx.parent.params and "provider" in ctx.parent.params:
            provider = ctx.parent.params["provider"]

        if provider and provider in provider_models:
            models = provider_models[provider]
        else:
            # Return all models from all providers
            models = []
            for provider_models_list in provider_models.values():
                models.extend(provider_models_list)

        return [
            CompletionItem(model) for model in models if model.startswith(incomplete)
        ]
    except Exception:
        return []


def complete_wiki_names(ctx, param, incomplete: str) -> List[CompletionItem]:
    """Complete wiki names from cache files."""
    try:
        cache_dir = get_cache_path()
        if not cache_dir.exists():
            return []

        cache_files = list(cache_dir.glob("deepwiki_cache_*.json"))
        wiki_names = []

        for cache_file in cache_files:
            try:
                meta = parse_cache_filename(cache_file)
                if not meta:
                    continue
                owner = meta["owner"]
                repo = meta["repo"]
                name = f"{owner}/{repo}" if owner and owner != "local" else repo
                wiki_names.append(name)
            except Exception:
                continue

        return [
            CompletionItem(name) for name in wiki_names if name.startswith(incomplete)
        ]
    except Exception:
        return []


def complete_config_keys(ctx, param, incomplete: str) -> List[CompletionItem]:
    """Complete configuration keys."""
    common_keys = [
        "default_provider",
        "default_model",
        "wiki_type",
        "file_filters.excluded_dirs",
        "file_filters.excluded_files",
        "file_filters.included_dirs",
        "file_filters.included_files",
        "use_server",
        "server_url",
        "server_timeout",
        "auto_fallback",
    ]

    return [CompletionItem(key) for key in common_keys if key.startswith(incomplete)]


def complete_file_paths(ctx, param, incomplete: str) -> List[CompletionItem]:
    """Complete file paths."""
    if not incomplete:
        incomplete = "."

    # Expand user home directory
    incomplete = os.path.expanduser(incomplete)

    # Get directory and filename parts
    dir_path = os.path.dirname(incomplete) or "."
    filename_part = os.path.basename(incomplete)

    try:
        if not os.path.isabs(dir_path):
            # Relative path - use current directory
            dir_path = os.path.abspath(dir_path)

        if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
            return []

        completions = []
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)

            # Filter by incomplete filename
            if not item.startswith(filename_part):
                continue

            # Add trailing slash for directories
            if os.path.isdir(item_path):
                completion_value = (
                    os.path.join(os.path.dirname(incomplete), item) + os.sep
                )
            else:
                completion_value = os.path.join(os.path.dirname(incomplete), item)

            completions.append(CompletionItem(completion_value))

        return completions
    except Exception:
        return []
