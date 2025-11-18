"""Wiki generation command."""

import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, cast

import click
from pydantic import ValidationError

from deepwiki_cli.application.repository.change_detection import (
    build_snapshot_from_local,
    build_snapshot_from_tree,
    detect_repo_changes,
    find_affected_pages,
    load_existing_cache,
)
from deepwiki_cli.application.repository.scan import collect_repository_files
from deepwiki_cli.application.wiki.context import WikiGenerationContext
from deepwiki_cli.cli.config import get_provider_models, load_config
from deepwiki_cli.cli.progress import ProgressManager
from deepwiki_cli.cli.utils import (
    confirm_action,
    ensure_cache_dir,
    get_cache_path,
    parse_repository_input,
    prompt_text_input,
    select_from_list,
    select_multiple_from_list,
)
from deepwiki_cli.domain.models import (
    RepoInfo,
    RepoSnapshot,
    WikiCacheData,
    WikiPage,
    WikiStructureModel,
)
from deepwiki_cli.domain.schemas import WikiPageSchema, WikiStructureSchema
from deepwiki_cli.infrastructure.clients.github.client import (
    get_github_repo_structure_standalone as get_github_repo_structure,
)
from deepwiki_cli.infrastructure.config import get_model_config
from deepwiki_cli.infrastructure.config.settings import CLIENT_CLASSES, GITHUB_TOKEN
from deepwiki_cli.infrastructure.prompts.builders import (
    build_wiki_page_prompt,
    build_wiki_structure_prompt,
)
from deepwiki_cli.infrastructure.storage.cache import (
    DEFAULT_LANGUAGE,
    CacheFileInfo,
    get_cache_filename,
    list_existing_wikis,
)

logger = logging.getLogger(__name__)

try:
    WIKI_STRUCTURE_MAX_ATTEMPTS = int(os.environ.get("DEEPWIKI_STRUCTURE_RETRIES", "3"))
except ValueError:
    WIKI_STRUCTURE_MAX_ATTEMPTS = 3

try:
    WIKI_STRUCTURE_RETRY_DELAY = float(
        os.environ.get("DEEPWIKI_STRUCTURE_RETRY_DELAY", "2.0"),
    )
except ValueError:
    WIKI_STRUCTURE_RETRY_DELAY = 2.0


class WikiStructureParseError(ValueError):
    """Raised when the structured wiki response cannot be parsed."""


class WikiPageParseError(ValueError):
    """Raised when a generated wiki page cannot be parsed."""


@dataclass
class RepositoryState:
    file_tree: str
    readme: str
    snapshot: RepoSnapshot


def prompt_repository() -> tuple:
    """Prompt user for repository input.

    Returns:
        Tuple of (repo_type, repo_url_or_path, owner, repo_name)
    """
    click.echo("\n" + "=" * 60)
    click.echo("Repository Selection")
    click.echo("=" * 60)

    while True:
        repo_input = prompt_text_input(
            "\nEnter repository",
            default="",
            show_default=False,
        )

        try:
            repo_type, repo_url_or_path, owner, repo_name = parse_repository_input(
                repo_input,
            )
            click.echo(f"✓ Repository: {repo_name} (type: {repo_type})")
            return repo_type, repo_url_or_path, owner, repo_name
        except ValueError as e:
            click.echo(f"✗ {e}", err=True)
            if not confirm_action("Try again?", default=True):
                raise click.Abort


def prompt_model_config(config: dict) -> tuple:
    """Prompt user for model configuration.

    Returns:
        Tuple of (provider, model)
    """
    click.echo("\n" + "=" * 60)
    click.echo("Model Configuration")
    click.echo("=" * 60)

    # Get available providers and models
    provider_models = get_provider_models()

    if not provider_models:
        click.echo("✗ No model providers configured.", err=True)
        raise click.Abort

    # Prompt for provider
    default_provider = config.get("default_provider", "google")
    providers = list(provider_models.keys())

    provider = select_from_list(
        "Select provider",
        providers,
        default=default_provider,
    )

    # Prompt for model
    available_models = provider_models.get(provider, [])

    default_model = config.get("default_model")
    if default_model and default_model in available_models:
        default_value = default_model
    elif available_models:
        default_value = available_models[0]
    else:
        default_value = None

    if available_models:
        # Use interactive selection with custom option
        model = select_from_list(
            f"Select model for {provider}",
            available_models,
            default=default_value,
            allow_custom=True,
        )
    else:
        # No predefined models, must enter custom
        click.echo(f"\nNo predefined models configured for {provider}.")
        model = prompt_text_input("Enter model name", default="", show_default=False)

    if not model:
        click.echo("✗ Model name is required.", err=True)
        raise click.Abort

    # Warn if custom model is used
    if (
        available_models
        and model not in available_models
        and not confirm_action(
            f"⚠ '{model}' is not in the predefined list. Continue anyway?",
            default=True,
        )
    ):
        raise click.Abort

    click.echo(f"✓ Using {provider}/{model}")
    return provider, model


def prompt_wiki_type(config: dict) -> bool:
    """Prompt user for wiki type.

    Returns:
        True for comprehensive, False for concise
    """
    default_type = config.get("wiki_type", "comprehensive")
    default_comprehensive = default_type == "comprehensive"

    click.echo("\n" + "=" * 60)
    click.echo("Wiki Type")
    click.echo("=" * 60)
    click.echo("\n  • Comprehensive: More pages with detailed sections (recommended)")
    click.echo("  • Concise: Fewer pages with essential information")

    wiki_type_choice = select_from_list(
        "\nSelect wiki type",
        ["Comprehensive", "Concise"],
        default="Comprehensive" if default_comprehensive else "Concise",
    )

    is_comprehensive = wiki_type_choice == "Comprehensive"
    wiki_type = "comprehensive" if is_comprehensive else "concise"
    click.echo(f"✓ Wiki type: {wiki_type}")
    return is_comprehensive


def prompt_file_filters() -> tuple:
    """Prompt user for optional file filters.

    Returns:
        Tuple of (excluded_dirs, excluded_files, included_dirs, included_files)
    """
    click.echo("\n" + "=" * 60)
    click.echo("File Filters (Optional)")
    click.echo("=" * 60)

    use_filters = confirm_action("\nConfigure file filters?", default=False)

    if not use_filters:
        return None, None, None, None

    click.echo("\nEnter patterns (comma-separated) or leave empty:")

    excluded_dirs_input = prompt_text_input(
        "Exclude directories",
        default="",
        show_default=False,
    )
    excluded_files_input = prompt_text_input(
        "Exclude files",
        default="",
        show_default=False,
    )
    included_dirs_input = prompt_text_input(
        "Include only directories",
        default="",
        show_default=False,
    )
    included_files_input = prompt_text_input(
        "Include only files",
        default="",
        show_default=False,
    )

    # Parse comma-separated values
    excluded_dirs = (
        [d.strip() for d in excluded_dirs_input.split(",") if d.strip()]
        if excluded_dirs_input
        else None
    )
    excluded_files = (
        [f.strip() for f in excluded_files_input.split(",") if f.strip()]
        if excluded_files_input
        else None
    )
    included_dirs = (
        [d.strip() for d in included_dirs_input.split(",") if d.strip()]
        if included_dirs_input
        else None
    )
    included_files = (
        [f.strip() for f in included_files_input.split(",") if f.strip()]
        if included_files_input
        else None
    )

    return excluded_dirs, excluded_files, included_dirs, included_files


def _format_cache_choice(entry: CacheFileInfo) -> str:
    timestamp = entry.modified.strftime("%Y-%m-%d %H:%M:%S")
    return f"v{entry.version} • {timestamp} • {entry.path.name}"


def _select_cache_entry(entries: list[CacheFileInfo]) -> CacheFileInfo:
    if len(entries) == 1:
        return entries[0]

    options = [_format_cache_choice(entry) for entry in entries]
    selection = select_from_list(
        "Select existing wiki version",
        options,
        default=options[0],
    )
    selected_index = options.index(selection)
    return entries[selected_index]


def _display_change_summary(
    repo_name: str,
    cache_entry: CacheFileInfo,
    summary: dict[str, list[str]] | None,
    wiki_structure: WikiStructureModel | None,
    affected_page_ids: list[str],
) -> None:
    click.echo(
        f"\n⚠️  Wiki already exists for {repo_name} (v{cache_entry.version})",
    )

    if not summary:
        click.echo("No change information available. Proceed with caution.")
        return

    changed = len(summary.get("changed_files", []))
    new_files = len(summary.get("new_files", []))
    deleted_files = len(summary.get("deleted_files", []))
    unchanged = summary.get("unchanged_count", 0)

    click.echo("Repository changes detected:")
    click.echo(f"  • {changed} files changed")
    click.echo(f"  • {new_files} new files")
    click.echo(f"  • {deleted_files} files deleted")
    click.echo(f"  • {unchanged} files unchanged")

    if not affected_page_ids or not wiki_structure:
        click.echo(
            "Affected pages: none (you can still choose 'Update only affected pages' to pick pages manually)",
        )
        return

    changed_set = set(summary.get("changed_files", []))
    page_lookup = {page.id: page for page in wiki_structure.pages}

    click.echo("Affected pages:")
    for page_id in affected_page_ids:
        page = page_lookup.get(page_id)
        if not page:
            continue
        page_changes = len(set(page.filePaths) & changed_set)
        click.echo(f"  • {page.title} ({page_changes} files changed)")


def _has_repo_changes(change_summary: dict[str, list[str]] | None) -> bool:
    """Return True when snapshot comparison detected any file-level change."""
    if not change_summary:
        return True
    return any(
        change_summary.get(key)
        for key in ("changed_files", "new_files", "deleted_files")
    )


def _prompt_generation_action(
    allow_new: bool,
    can_update_pages: bool,
) -> str:
    actions = []
    action_map = {}

    if allow_new:
        label = "Overwrite existing wiki (regenerate all pages)"
        actions.append(label)
        action_map[label] = "overwrite"
        if can_update_pages:
            label = "Update only affected pages"
            actions.append(label)
            action_map[label] = "update"
        label = "Create new version"
        actions.append(label)
        action_map[label] = "new_version"
        label = "Cancel"
        actions.append(label)
        action_map[label] = "cancel"
    else:
        return "overwrite"

    choice = select_from_list("What would you like to do?", actions)
    return action_map[choice]


def _prompt_pages_to_regenerate(
    wiki_structure: WikiStructureModel,
    affected_page_ids: list[str],
) -> list[str]:
    page_lookup = {page.id: page for page in wiki_structure.pages}

    options = []
    mapping = {}
    for page_id in affected_page_ids:
        page = page_lookup.get(page_id)
        if not page:
            continue
        label = f"{page.title} [{page.id}]"
        options.append(label)
        mapping[label] = page_id

    if not options:
        return []

    selected_labels = select_multiple_from_list(
        "Select pages to regenerate (space to toggle)",
        options,
    )

    if not selected_labels:
        return affected_page_ids

    return [mapping[label] for label in selected_labels if label in mapping]


def _collect_page_feedback(
    page_ids: list[str],
    wiki_structure: WikiStructureModel,
) -> dict[str, str]:
    if not page_ids:
        return {}

    if not confirm_action(
        "Would you like to provide feedback for any selected pages?",
        default=False,
    ):
        return {}

    feedback: dict[str, str] = {}
    page_lookup = {page.id: page for page in wiki_structure.pages}
    for page_id in page_ids:
        page = page_lookup.get(page_id)
        if not page:
            continue
        note = prompt_text_input(
            f"Feedback for '{page.title}' (leave blank to skip)",
            default="",
            show_default=False,
        )
        if note and note.strip():
            feedback[page_id] = note.strip()

    return feedback


def generate_page_content_sync(
    page: WikiPage,
    generation_context: WikiGenerationContext,
    repo_url: str,
    progress_manager: ProgressManager,
    extra_feedback: str | None = None,
) -> WikiPage | None:
    """Generate content for a single page (synchronous wrapper).

    Returns:
        Updated WikiPage with generated content or None on error
    """
    page_id = page.id
    page_title = page.title

    try:
        # Add progress bar for this page
        page_bar = progress_manager.add_page_progress(page_id, page_title)
        page_bar.update(10)  # Starting

        # Import required modules

        # Create the prompt (matching web UI exactly for quality)
        file_paths_list = "\n".join([f"- [{path}]" for path in page.filePaths])

        prompt = build_wiki_page_prompt(
            page_title,
            file_paths_list,
            page_id=page_id,
            importance=page.importance,
            related_pages=page.relatedPages,
        )

        if extra_feedback:
            prompt += "\nUser feedback and guidance:\n" + extra_feedback.strip() + "\n"

        page_bar.update(30)  # Prompt ready

        # Prepare request
        messages = [{"role": "user", "content": prompt}]

        page_bar.update(50)  # Request sent

        # Collect streamed content with incremental progress updates
        raw_response = ""
        chunk_count = 0
        start_time = time.time()
        last_update_time = start_time
        last_progress = 50

        try:
            stream = generation_context.stream_completion(
                messages=messages,
                structured_schema=WikiPageSchema,
            )
            for chunk in stream:
                if chunk:
                    raw_response += chunk if isinstance(chunk, str) else str(chunk)
                chunk_count += 1
                current_time = time.time()
                elapsed = current_time - start_time

                # Update progress smoothly based on time and content received
                # Gradually move from 50% to 90% over time as we receive chunks
                # Use a combination of time-based and content-based progress
                if elapsed > 0:
                    # Time-based progress: assume it takes ~30 seconds to stream
                    # This ensures progress moves even if chunks arrive slowly
                    time_progress = min(50 + (elapsed / 30.0) * 40, 90)

                    # Content-based progress: move faster if we're receiving chunks
                    content_progress = min(50 + (chunk_count / 50.0) * 40, 90)

                    # Use the maximum of both to ensure progress moves
                    target_progress = max(
                        time_progress,
                        content_progress,
                        last_progress,
                    )
                    target_progress = min(target_progress, 90)

                    # Update every 0.2 seconds or when we've made significant progress
                    if (current_time - last_update_time >= 0.2) or (
                        target_progress - last_progress >= 1
                    ):
                        progress_delta = int(target_progress - last_progress)
                        if progress_delta > 0:
                            page_bar.update(progress_delta)
                            last_progress = page_bar.count
                            last_update_time = current_time

            # Ensure we're at 90% when content is fully received
            if page_bar.count < 90:
                page_bar.update(90 - page_bar.count)

            try:
                schema_response = _parse_wiki_page_json(raw_response)
            except WikiPageParseError as parse_exc:
                logger.error(
                    "Failed to parse wiki page %s: %s",
                    page_id,
                    parse_exc,
                )
                _dump_failed_page_response(raw_response)
                raise

            content = schema_response.content.strip()
            if content.startswith("```markdown"):
                content = content[len("```markdown") :].strip()
            if content.endswith("```"):
                content = content[:-3].strip()

            # Update page with parsed data
            page.content = content
            page.metadata = schema_response.metadata.model_dump()
            if schema_response.metadata.related_page_ids:
                page.relatedPages = schema_response.metadata.related_page_ids
            if schema_response.metadata.referenced_files:
                page.filePaths = schema_response.metadata.referenced_files

            page_bar.update(100)  # Complete
            progress_manager.complete_page(page_id)
        except Exception as e:
            logger.exception(f"Error generating page {page_title}: {e}")
            return None

        if not page.content:
            logger.warning(f"No content generated for page {page_title}")
            return None

        return page

    except Exception as e:
        logger.exception(f"Error generating page {page_title}: {e}")
        progress_manager.complete_page(page_id)
        return None


def _dump_failed_structure_response(raw_content: str) -> None:
    """Persist raw structured output to a temp file for debugging."""
    import tempfile

    debug_file = os.path.join(
        tempfile.gettempdir(),
        f"deepwiki_debug_response_{os.getpid()}.txt",
    )
    try:
        with open(debug_file, "w", encoding="utf-8") as handle:
            handle.write(raw_content)
        logger.error("Full response saved to: %s", debug_file)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to save debug file: %s", exc)


def _strip_code_fence(raw_content: str) -> str:
    """Remove common markdown fences from model output."""
    stripped = raw_content.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        stripped = stripped.strip()
        if stripped.endswith("```"):
            stripped = stripped[: stripped.rfind("```")].strip()
    return stripped


def _schema_to_model(structure_schema: WikiStructureSchema) -> WikiStructureModel:
    """Convert schema response to the runtime wiki structure model."""
    pages = [
        WikiPage(
            id=page.page_id,
            title=page.title,
            content="",
            filePaths=page.relevant_files,
            importance=page.importance,
            relatedPages=page.related_page_ids,
        )
        for page in structure_schema.pages
    ]
    if not pages:
        raise WikiStructureParseError("No pages found in wiki structure")

    return WikiStructureModel(
        id="wiki",
        title=structure_schema.title,
        description=structure_schema.description,
        pages=pages,
        sections=[],
        rootSections=[],
    )


def _parse_wiki_structure_json(raw_content: str) -> WikiStructureSchema:
    """Parse JSON returned by the LLM into a WikiStructureSchema."""
    stripped = _strip_code_fence(raw_content)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or start >= end:
        raise WikiStructureParseError("Structured JSON block not found in response")
    json_payload = stripped[start : end + 1]
    logger.debug("Structured JSON candidate: %s", json_payload[:500])
    try:
        return WikiStructureSchema.model_validate_json(json_payload)
    except ValidationError as exc:
        raise WikiStructureParseError(f"JSON parsing failed: {exc}") from exc


def _dump_failed_page_response(raw_content: str) -> None:
    """Persist raw wiki page output to disk for debugging."""
    import tempfile

    debug_file = os.path.join(
        tempfile.gettempdir(),
        f"deepwiki_page_debug_{os.getpid()}.txt",
    )
    try:
        with open(debug_file, "w", encoding="utf-8") as handle:
            handle.write(raw_content)
        logger.error("Full page response saved to: %s", debug_file)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Failed to save page debug file: %s", exc)


def _parse_wiki_page_json(raw_content: str) -> WikiPageSchema:
    """Parse JSON returned by the LLM into a WikiPageSchema."""
    stripped = _strip_code_fence(raw_content)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or start >= end:
        raise WikiPageParseError("Structured JSON block not found in response")
    json_payload = stripped[start : end + 1]
    try:
        return WikiPageSchema.model_validate_json(json_payload)
    except ValidationError as exc:
        sanitized = _sanitize_page_json(json_payload)
        if sanitized is None:
            raise WikiPageParseError(f"Page JSON parsing failed: {exc}") from exc
        logger.warning(
            "Recovered malformed JSON content by escaping embedded quotes.",
            extra={"problem_field": "content"},
        )
        try:
            return WikiPageSchema.model_validate_json(sanitized)
        except ValidationError as sanitized_exc:  # pragma: no cover - defensive
            raise WikiPageParseError(
                f"Page JSON parsing failed: {sanitized_exc}",
            ) from sanitized_exc


def _sanitize_page_json(json_payload: str) -> str | None:
    """Escape embedded quotes inside the content field when providers omit escaping."""
    try:
        import json

        json.loads(json_payload)
        return json_payload
    except Exception:  # pragma: no cover - only triggered on invalid JSON
        pass

    marker = '"content": "'
    if marker not in json_payload:
        return None
    try:
        prefix, remainder = json_payload.split(marker, 1)
        content_raw, suffix = remainder.rsplit('"\n}', 1)
    except ValueError:
        return None
    import json as _json

    escaped = _json.dumps(content_raw)
    return prefix + '"content": ' + escaped + "\n}" + suffix


def _structured_client_for(provider: str, model: str):
    """Instantiate a provider client when structured calls are supported."""
    model_config = get_model_config(provider, model)
    client_name = model_config.get("model_client")
    client_cls = CLIENT_CLASSES.get(client_name)
    if not client_cls:
        return None, model_config
    client = client_cls()
    if not hasattr(client, "call_structured"):
        return None, model_config
    return client, model_config


def _call_structured_wiki_schema(
    provider: str,
    model: str,
    messages: list[dict[str, Any]],
) -> WikiStructureSchema | None:
    """Call provider-specific structured output if supported."""
    client, model_config = _structured_client_for(provider, model)
    if client is None:
        return None
    call_fn: Callable[..., WikiStructureSchema] = getattr(client, "call_structured")
    return call_fn(
        schema=WikiStructureSchema,
        messages=messages,
        model_kwargs=model_config.get("model_kwargs"),
    )


def _stream_structure_response(
    prompt: str,
    repo_url: str,
    provider: str,
    model: str,
    repo_type: str,
    generation_context: WikiGenerationContext | None,
) -> str:
    """Fallback streaming request for providers lacking structured APIs."""
    if generation_context:
        stream = generation_context.stream_completion(
            messages=[{"role": "user", "content": prompt}],
        )
    else:
        from deepwiki_cli.application.wiki.generate_content import generate_wiki_content

        stream = generate_wiki_content(
            repo_url=repo_url,
            messages=[{"role": "user", "content": prompt}],
            provider=provider,
            model=model,
            repo_type=repo_type,
            structured_schema=None,
        )

    aggregated = ""
    for chunk in stream:
        if chunk:
            aggregated += chunk if isinstance(chunk, str) else str(chunk)
    return aggregated


def generate_wiki_structure(
    repo_url: str,
    repo_type: str,
    file_tree: str,
    readme: str,
    provider: str,
    model: str,
    is_comprehensive: bool,
    generation_context: WikiGenerationContext | None = None,
) -> WikiStructureModel | None:
    """Generate wiki structure from repository.

    Returns:
        WikiStructureModel or None on error
    """
    # Calculate file count for page estimation
    file_count = len([line for line in file_tree.split("\n") if line.strip()])

    # Determine page count ranges
    if file_count < 50:
        min_pages = 6 if is_comprehensive else 4
        max_pages = 8 if is_comprehensive else 6
    elif file_count < 200:
        min_pages = 8 if is_comprehensive else 5
        max_pages = 12 if is_comprehensive else 7
    elif file_count < 500:
        min_pages = 10 if is_comprehensive else 6
        max_pages = 15 if is_comprehensive else 9
    else:
        min_pages = 12 if is_comprehensive else 7
        max_pages = 18 if is_comprehensive else 11

    target_pages = (min_pages + max_pages) // 2

    # Create structure prompt (matching frontend for quality)
    prompt = build_wiki_structure_prompt(
        file_tree=file_tree,
        readme=readme,
        is_comprehensive=is_comprehensive,
        min_pages=min_pages,
        max_pages=max_pages,
        target_pages=target_pages,
        file_count=file_count,
    )

    max_attempts = max(1, WIKI_STRUCTURE_MAX_ATTEMPTS)
    messages = [{"role": "user", "content": prompt}]
    for attempt in range(1, max_attempts + 1):
        raw_content = ""
        try:
            schema_response = _call_structured_wiki_schema(
                provider=provider,
                model=model,
                messages=messages,
            )
            if schema_response is None:
                raw_content = _stream_structure_response(
                    prompt=prompt,
                    repo_url=repo_url,
                    provider=provider,
                    model=model,
                    repo_type=repo_type,
                    generation_context=generation_context,
                )
                schema_response = _parse_wiki_structure_json(raw_content)
            return _schema_to_model(schema_response)
        except (WikiStructureParseError, ValidationError) as parse_error:
            is_last = attempt >= max_attempts
            log_fn = logger.error if is_last else logger.warning
            log_fn(
                "Wiki structure parsing failed on attempt %s/%s: %s",
                attempt,
                max_attempts,
                parse_error,
            )
            if is_last:
                _dump_failed_structure_response(raw_content)
                return None
        except Exception as exc:
            is_last = attempt >= max_attempts
            logger.exception(
                "Error generating wiki structure on attempt %s/%s: %s",
                attempt,
                max_attempts,
                exc,
            )
            if is_last:
                return None

        if attempt < max_attempts:
            time.sleep(WIKI_STRUCTURE_RETRY_DELAY)
            logger.info(
                "Retrying wiki structure generation (%s/%s)",
                attempt + 1,
                max_attempts,
            )


def _read_local_readme(repo_path: str) -> str:
    for readme_name in ["README.md", "readme.md", "README.txt"]:
        readme_path = os.path.join(repo_path, readme_name)
        if os.path.exists(readme_path):
            try:
                with open(readme_path, encoding="utf-8", errors="ignore") as handle:
                    return handle.read()
            except Exception as exc:
                logger.debug(f"Failed to read {readme_path}: {exc}")
    return ""


def prepare_repository_state(
    repo_type: str,
    repo_url_or_path: str,
    owner: str | None,
    repo_name: str,
) -> RepositoryState:
    if repo_type == "github":
        data = get_github_repo_structure(
            owner=owner or "",
            repo=repo_name,
            repo_url=repo_url_or_path,
        )
        file_tree = data.get("file_tree", "")
        readme = data.get("readme", "")
        from typing import cast

        tree_files = cast("list[dict[str, Any]] | None", data.get("tree_files")) or []
        snapshot = build_snapshot_from_tree(
            cast("list[dict[str, str]] | None", tree_files),
            reference=f"{owner}/{repo_name}",
        )
        return RepositoryState(file_tree=file_tree, readme=readme, snapshot=snapshot)

    files = collect_repository_files(repo_url_or_path)
    relative_files = [os.path.relpath(f, repo_url_or_path) for f in files]
    file_tree = "\n".join(relative_files)
    readme = _read_local_readme(repo_url_or_path)
    snapshot = build_snapshot_from_local(repo_url_or_path, files)
    return RepositoryState(file_tree=file_tree, readme=readme, snapshot=snapshot)


@click.command(name="generate")
@click.option(
    "--force",
    is_flag=True,
    help="Skip prompts when regenerating and overwrite the latest cache automatically.",
)
def generate(force: bool) -> None:
    """Generate a new wiki or refresh an existing cache."""
    click.echo("\n" + "=" * 60)
    click.echo("DeepWiki Generator")
    click.echo("=" * 60)

    config = load_config()
    progress: ProgressManager | None = None

    try:
        repo_type, repo_url_or_path, owner, repo_name = prompt_repository()
        provider, model = prompt_model_config(config)
        is_comprehensive = prompt_wiki_type(config)
        excluded_dirs, excluded_files, included_dirs, included_files = (
            prompt_file_filters()
        )

        ensure_cache_dir()
        cache_path = get_cache_path()
        owner_key = owner or "local"
        existing_entries = list_existing_wikis(
            cache_path,
            repo_type,
            owner_key,
            repo_name,
        )

        selected_cache_entry: CacheFileInfo | None = None
        existing_cache: WikiCacheData | None = None
        if existing_entries:
            selected_cache_entry = (
                existing_entries[0] if force else _select_cache_entry(existing_entries)
            )
            existing_cache = load_existing_cache(selected_cache_entry.path)
            if existing_cache is None:
                click.echo(
                    f"⚠️  Existing cache '{selected_cache_entry.path.name}' is unreadable and will be ignored.",
                    err=True,
                )
                selected_cache_entry = None
                existing_entries = []

        progress = ProgressManager()
        progress.set_status("Inspecting repository")
        click.echo("\nInspecting repository state...")

        try:
            repo_state = prepare_repository_state(
                repo_type,
                repo_url_or_path,
                owner,
                repo_name,
            )
            click.echo("✓ Repository inspected")
        except Exception as e:
            click.echo(f"✗ Error inspecting repository: {e}", err=True)
            progress.close()
            raise click.Abort

        if not repo_state.file_tree.strip():
            click.echo("✗ No files found in repository", err=True)
            progress.close()

            def _abort() -> None:
                raise click.Abort  # noqa: TRY301

            _abort()

        change_summary = None
        affected_pages: list[str] = []
        update_candidate_page_ids: list[str] = []
        action = "overwrite"

        if existing_cache and selected_cache_entry:
            if force:
                action = "overwrite"
            else:
                change_summary = detect_repo_changes(
                    repo_url_or_path,
                    existing_cache,
                    repo_state.snapshot,
                )
                affected_pages = find_affected_pages(
                    change_summary.get("changed_files", []) if change_summary else [],
                    existing_cache.wiki_structure,
                )
                if existing_cache and existing_cache.wiki_structure:
                    update_candidate_page_ids = (
                        affected_pages
                        if affected_pages
                        else [page.id for page in existing_cache.wiki_structure.pages]
                    )
                _display_change_summary(
                    repo_name,
                    selected_cache_entry,
                    cast("dict[str, list[str]] | None", change_summary),
                    existing_cache.wiki_structure,
                    affected_pages,
                )
                if not force and not _has_repo_changes(
                    cast("dict[str, list[str]] | None", change_summary),
                ):
                    click.echo(
                        "\nNo repository changes detected since the last wiki build.",
                    )
                    regenerate_anyway = confirm_action(
                        "Regenerate anyway?",
                        default=False,
                    )
                    if not regenerate_anyway:
                        click.echo(
                            "✓ Wiki is already up to date. Skipping regeneration.",
                        )
                        progress.close()
                        return
                can_update = bool(update_candidate_page_ids)
                action = _prompt_generation_action(
                    allow_new=True,
                    can_update_pages=can_update,
                )
                if action == "cancel":
                    progress.close()
                    click.echo("Operation cancelled.")
                    return
        else:
            action = "overwrite"

        selected_page_ids: list[str] = []
        page_feedback: dict[str, str] = {}

        if action == "update":
            if not (existing_cache and update_candidate_page_ids):
                click.echo(
                    "No pages available to update; regenerating the entire wiki instead.",
                )
                action = "overwrite"
            else:
                selected_page_ids = _prompt_pages_to_regenerate(
                    existing_cache.wiki_structure,
                    update_candidate_page_ids,
                )
                if not selected_page_ids:
                    progress.close()
                    click.echo("No pages selected. Operation cancelled.")
                    return
                click.echo("\nPages selected for regeneration:")
                for pid in selected_page_ids:
                    page = next(
                        (p for p in existing_cache.wiki_structure.pages if p.id == pid),
                        None,
                    )
                    title = page.title if page else pid
                    click.echo(f"  • {title}")
                page_feedback = _collect_page_feedback(
                    selected_page_ids,
                    existing_cache.wiki_structure,
                )

        target_version = 1
        if action == "new_version":
            highest = max((entry.version for entry in existing_entries), default=0)
            base_version = selected_cache_entry.version if selected_cache_entry else 1
            target_version = max(highest, base_version) + 1
        elif selected_cache_entry:
            target_version = selected_cache_entry.version

        language = DEFAULT_LANGUAGE

        progress.set_status("Preparing repository context")
        click.echo("Preparing repository analysis...")
        force_embedding_rebuild = (
            action in {"overwrite", "new_version"} or not existing_cache
        )
        try:
            generation_context = WikiGenerationContext.prepare(
                repo_url=repo_url_or_path,
                repo_type=repo_type,
                provider=provider,
                model=model,
                token=GITHUB_TOKEN,
                excluded_dirs=excluded_dirs,
                excluded_files=excluded_files,
                included_dirs=included_dirs,
                included_files=included_files,
                force_rebuild_embeddings=force_embedding_rebuild,
            )
            click.echo("✓ Repository prepared")
        except Exception as e:
            click.echo(f"✗ Error preparing repository: {e}", err=True)
            progress.close()
            raise click.Abort

        wiki_structure: WikiStructureModel | None = None
        generated_pages: dict[str, WikiPage] = {}
        regenerated_ids: list[str] = []
        reused_count = 0

        if action == "update" and existing_cache:
            wiki_structure = existing_cache.wiki_structure
            if wiki_structure is None:
                raise ValueError("Existing cache has no wiki_structure")  # noqa: TRY301
            generated_pages = dict(existing_cache.generated_pages)
            pages_to_generate = [
                page for page in wiki_structure.pages if page.id in selected_page_ids
            ]
            progress.set_status("Regenerating selected pages")
            progress.init_overall_progress(len(pages_to_generate), "Updating Pages")

            for page in pages_to_generate:
                updated_page = generate_page_content_sync(
                    page,
                    generation_context,
                    repo_url_or_path,
                    progress,
                    extra_feedback=page_feedback.get(page.id),
                )
                if updated_page:
                    generated_pages[page.id] = updated_page
                    regenerated_ids.append(page.id)

            reused_count = len(wiki_structure.pages) - len(regenerated_ids)
        else:
            progress.set_status("Determining wiki structure")
            click.echo("Determining wiki structure...")

            wiki_structure = generate_wiki_structure(
                repo_url_or_path,
                repo_type,
                repo_state.file_tree,
                repo_state.readme,
                provider,
                model,
                is_comprehensive,
                generation_context,
            )

            if wiki_structure is None:
                click.echo("✗ Failed to generate wiki structure", err=True)
                progress.close()

                def _abort() -> None:
                    raise click.Abort  # noqa: TRY301

                _abort()

            # At this point wiki_structure is guaranteed to be non-None
            if wiki_structure is None:
                raise ValueError("wiki_structure is None")  # noqa: TRY301
            click.echo(f"✓ Structure created: {len(wiki_structure.pages)} pages")

            progress.set_status("Generating pages")
            progress.init_overall_progress(
                len(wiki_structure.pages),
                "Generating Pages",
            )
            click.echo(f"\nGenerating {len(wiki_structure.pages)} pages...\n")

            for page in wiki_structure.pages:
                updated_page = generate_page_content_sync(
                    page,
                    generation_context,
                    repo_url_or_path,
                    progress,
                )
                if updated_page:
                    generated_pages[page.id] = updated_page
                    regenerated_ids.append(page.id)

            reused_count = len(wiki_structure.pages) - len(regenerated_ids)

        progress.set_status("Saving cache")
        click.echo("\n\nSaving to cache...")

        repo_info = RepoInfo(
            owner=owner or "",
            repo=repo_name,
            type=repo_type,
            repoUrl=repo_url_or_path if repo_type == "github" else None,
            localPath=repo_url_or_path if repo_type == "local" else None,
        )

        cache_filename = get_cache_filename(
            repo_type=repo_type,
            owner=owner_key,
            repo_name=repo_name,
            language=language,
            version=target_version,
        )
        cache_file = cache_path / cache_filename

        now_iso = datetime.now(UTC).isoformat()
        created_at = (
            now_iso
            if action == "new_version" or not existing_cache
            else existing_cache.created_at or now_iso
        )

        if wiki_structure is None:
            raise ValueError("wiki_structure must be set before creating cache")  # noqa: TRY301

        # Convert pages to WikiPage objects if they're dicts (from cache)
        pages_dict: dict[str, WikiPage] = {}
        for pid, page in generated_pages.items():
            if isinstance(page, WikiPage):
                pages_dict[pid] = page
            else:
                # Reconstruct WikiPage from dict (e.g., from cache)
                # When loading from cache, pages may be dicts instead of WikiPage objects
                pages_dict[pid] = WikiPage(**page) if isinstance(page, dict) else page  # type: ignore[unreachable]

        if wiki_structure is None:
            raise ValueError("wiki_structure is None")  # noqa: TRY301
        cache_payload = WikiCacheData(
            wiki_structure=wiki_structure,
            generated_pages=pages_dict,
            repo=repo_info,
            provider=provider,
            model=model,
            version=target_version,
            created_at=created_at,
            updated_at=now_iso,
            repo_snapshot=repo_state.snapshot,
            comprehensive=is_comprehensive,
        )

        with open(cache_file, "w") as f:
            json.dump(cache_payload.model_dump(), f, indent=2)

        progress.close()

        click.echo(f"✓ Cache saved to: {cache_file}")

        click.echo("\n" + "=" * 60)
        click.echo("Generation Complete!")
        click.echo("=" * 60)
        click.echo(f"\nRepository: {repo_name}")
        click.echo(f"Version: v{target_version}")
        click.echo(
            "Action: "
            + ("Update affected pages" if action == "update" else "Full regeneration"),
        )
        click.echo(f"Pages regenerated: {len(regenerated_ids)}")
        if regenerated_ids and wiki_structure is not None:
            page_lookup = {page.id: page for page in wiki_structure.pages}
            click.echo("Regenerated pages:")
            for pid in regenerated_ids:
                page = page_lookup.get(pid)
                title = page.title if page is not None else pid
                click.echo(f"  • {title}")
        if reused_count:
            click.echo(f"Pages reused: {reused_count}")
        click.echo(f"Cache file: {cache_file}")
        if change_summary:
            click.echo(
                f"Files processed: {len(change_summary.get('changed_files', []))} changed, "
                f"{len(change_summary.get('new_files', []))} new, "
                f"{len(change_summary.get('deleted_files', []))} deleted",
            )
        click.echo("\nUse 'deepwiki export' to export the wiki to Markdown or JSON.")
        click.echo("=" * 60 + "\n")

    except click.Abort:
        if progress:
            progress.close()
        click.echo("\nOperation cancelled.")
        sys.exit(1)
    except KeyboardInterrupt:
        if progress:
            progress.close()
        click.echo("\n\nOperation interrupted.")
        sys.exit(1)
    except Exception as e:
        if progress:
            progress.close()
        logger.exception("Unexpected error")
        click.echo(f"\n✗ Unexpected error: {e}", err=True)
        sys.exit(1)
