"""
Wiki generation command.
"""

import os
import sys
import json
import time
from datetime import datetime
import click
import logging
import subprocess
import fnmatch
from dataclasses import dataclass
from typing import Dict, Optional, List

from api.cli.config import load_config, get_provider_models
from api.cli.utils import (
    parse_repository_input,
    get_cache_path,
    ensure_cache_dir,
    select_from_list,
    select_multiple_from_list,
    confirm_action,
    prompt_text_input,
)
from api.cli.progress import ProgressManager
from api.services.wiki_context import WikiGenerationContext
from api.models import (
    RepoInfo,
    RepoSnapshot,
    WikiStructureModel,
    WikiPage,
    WikiCacheData,
)
from api.config import GITHUB_TOKEN
from api.utils.change_detection import (
    build_snapshot_from_local,
    build_snapshot_from_tree,
    detect_repo_changes,
    find_affected_pages,
    load_existing_cache,
)
from api.utils.wiki_cache import (
    CacheFileInfo,
    DEFAULT_LANGUAGE,
    get_cache_filename,
    list_existing_wikis,
)
from api.utils.github import get_github_repo_structure

logger = logging.getLogger(__name__)


@dataclass
class RepositoryState:
    file_tree: str
    readme: str
    snapshot: RepoSnapshot


def prompt_repository() -> tuple:
    """
    Prompt user for repository input.

    Returns:
        Tuple of (repo_type, repo_url_or_path, owner, repo_name)
    """
    click.echo("\n" + "=" * 60)
    click.echo("Repository Selection")
    click.echo("=" * 60)
    click.echo("\nYou can provide:")
    click.echo("  • GitHub URL: https://github.com/owner/repo")
    click.echo("  • GitHub shorthand: owner/repo")
    click.echo("  • Local directory path: /path/to/repo")

    while True:
        repo_input = prompt_text_input(
            "\nEnter repository", default="", show_default=False
        )

        try:
            repo_type, repo_url_or_path, owner, repo_name = parse_repository_input(
                repo_input
            )
            click.echo(f"✓ Repository: {repo_name} (type: {repo_type})")
            return repo_type, repo_url_or_path, owner, repo_name
        except ValueError as e:
            click.echo(f"✗ {e}", err=True)
            if not confirm_action("Try again?", default=True):
                raise click.Abort()


def prompt_model_config(config: Dict) -> tuple:
    """
    Prompt user for model configuration.

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
        raise click.Abort()

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
        raise click.Abort()

    # Warn if custom model is used
    if available_models and model not in available_models:
        if not confirm_action(
            f"⚠ '{model}' is not in the predefined list. Continue anyway?",
            default=True,
        ):
            raise click.Abort()

    click.echo(f"✓ Using {provider}/{model}")
    return provider, model


def prompt_wiki_type(config: Dict) -> bool:
    """
    Prompt user for wiki type.

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
    """
    Prompt user for optional file filters.

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
        "Exclude directories", default="", show_default=False
    )
    excluded_files_input = prompt_text_input(
        "Exclude files", default="", show_default=False
    )
    included_dirs_input = prompt_text_input(
        "Include only directories", default="", show_default=False
    )
    included_files_input = prompt_text_input(
        "Include only files", default="", show_default=False
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


def _select_cache_entry(entries: List[CacheFileInfo]) -> CacheFileInfo:
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
    summary: Optional[Dict[str, List[str]]],
    wiki_structure: Optional[WikiStructureModel],
    affected_page_ids: List[str],
):
    click.echo(
        f"\n⚠️  Wiki already exists for {repo_name} (v{cache_entry.version})"
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
        click.echo("Affected pages: none")
        return

    changed_set = set(summary.get("changed_files", []))
    page_lookup = {page.id: page for page in wiki_structure.pages}

    click.echo("Affected pages:")
    for page_id in affected_page_ids:
        page = page_lookup.get(page_id)
        if not page:
            continue
        page_changes = len({fp for fp in page.filePaths} & changed_set)
        click.echo(f"  • {page.title} ({page_changes} files changed)")


def _prompt_generation_action(
    has_existing: bool,
    affected_page_ids: List[str],
) -> str:
    actions = []
    action_map = {}

    if has_existing:
        label = "Overwrite existing wiki (regenerate all pages)"
        actions.append(label)
        action_map[label] = "overwrite"
        if affected_page_ids:
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
    affected_page_ids: List[str],
) -> List[str]:
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
        "Select pages to regenerate (space to toggle)", options
    )

    if not selected_labels:
        return affected_page_ids

    return [mapping[label] for label in selected_labels if label in mapping]


def _collect_page_feedback(
    page_ids: List[str],
    wiki_structure: WikiStructureModel,
) -> Dict[str, str]:
    if not page_ids:
        return {}

    if not confirm_action(
        "Would you like to provide feedback for any selected pages?", default=False
    ):
        return {}

    feedback: Dict[str, str] = {}
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
    extra_feedback: Optional[str] = None,
) -> Optional[WikiPage]:
    """
    Generate content for a single page (synchronous wrapper).

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

        prompt = f"""You are an expert technical writer and software architect.
Your task is to generate a comprehensive and accurate technical wiki page in Markdown format about a specific feature, system, or module within a given software project.

You will be given:
1. The "{page_title}" for the page you need to create.
2. A list of RELEVANT_SOURCE_FILES from the project that you MUST use as the sole basis for the content. You have access to the full content of these files. You MUST use AT LEAST 5 relevant source files for comprehensive coverage - if fewer are provided, search for additional related files in the codebase.

CRITICAL STARTING INSTRUCTION:
The very first thing on the page MUST be a `<details>` block listing ALL the RELEVANT_SOURCE_FILES you used to generate the content. There MUST be AT LEAST 5 source files listed - if fewer were provided, you MUST find additional related files to include.
Format it exactly like this:
<details>
  <summary>Relevant source files</summary>

  The following files were used as context for generating this wiki page:

  {file_paths_list}
  <!-- Add additional relevant files if fewer than 5 were provided -->
</details>

Immediately after the `<details>` block, the main title of the page should be a H1 Markdown heading: `# {page_title}`.

Based ONLY on the content of the RELEVANT_SOURCE_FILES:

1.  **Introduction:** Start with a concise introduction (1-2 paragraphs) explaining the purpose, scope, and high-level overview of "{page_title}" within the context of the overall project. If relevant, and if information is available in the provided files, link to other potential wiki pages using the format `[Link Text](#page-anchor-or-id)`.

2.  **Detailed Sections:** Break down "{page_title}" into logical sections using H2 (`##`) and H3 (`###`) Markdown headings. For each section:
*   Explain the architecture, components, data flow, or logic relevant to the section's focus, as evidenced in the source files.
*   Identify key functions, classes, data structures, API endpoints, or configuration elements pertinent to that section.

3.  **Mermaid Diagrams:**
*   EXTENSIVELY use Mermaid diagrams (e.g., `flowchart TD`, `sequenceDiagram`, `classDiagram`, `erDiagram`, `graph TD`) to visually represent architectures, flows, relationships, and schemas found in the source files.
*   Ensure diagrams are accurate and directly derived from information in the RELEVANT_SOURCE_FILES.
*   Provide a brief explanation before or after each diagram to give context.

**CRITICAL SYNTAX RULES FOR MERMAID DIAGRAMS:**

**FLOWCHART REQUIREMENTS:**
- ALWAYS use "flowchart TD" (never "graph TD") as the first directive
- Place the directive on its own line, followed by a blank line
- Use simple alphanumeric node IDs (e.g., A, B, C, node1, start)
- Node labels MUST be enclosed in quotes: A["Label text"]
- Labels should be 3-4 words maximum per line
- Use <br/> for line breaks inside labels: A["First<br/>Second"]
- Use simple arrow syntax: --> for simple flow, -. -> for dotted, -->|label| for labeled edges
- **CRITICAL: Always use quotes around node labels that contain ANY of these: spaces, special characters (< > & " '), HTML tags (<br/>), parentheses ( ), slashes (/), colons (:), or multi-word text**
- Examples: A["Start Process"], B["End<br/>Here"], C["API Call (v2.1)"], D["File/Directory"]
- Keep node text SHORT to prevent rendering issues
- Avoid special characters in node IDs (use only letters, numbers, underscore)
- For subgraphs: Use subgraph id["Name"] ... end syntax

**SEQUENCE DIAGRAM REQUIREMENTS:**
- Start with "sequenceDiagram" as the first directive
- Declare ALL participants at the beginning: participant id as Name
- Use descriptive names but keep them concise (max 15 characters)
- Simple participant IDs: A, B, C, or meaningful short names
- Use correct arrow syntax:
  * ->> for solid line with arrowhead (most common)
  * -->> for dotted line with arrowhead
  * -> for solid line without arrow
  * --> for dotted line without arrow
- Message syntax: A->>B: Message text (colon required, no special formatting needed)
- Use "Note over participant1,participant2: Note text" for notes spanning multiple participants
- Use "Note right of participant: Note text" for notes on the right side
- Use "Note left of participant: Note text" for notes on the left side
- Always put note text in quotes if it contains special characters
- Notes cannot overlap with message arrows - place them between message exchanges
- Use alt/else for conditional flows, NOT complex nested structures

**COMMON ERRORS TO AVOID:**
- NO complex edge labels with special syntax like A--|label|B (use A-->|label|B instead)
- NO undefined participants in sequence diagrams
- NO special characters (#, @, $, %, &) in node IDs
- NO extremely long labels (break them with <br/>)
- NO mixed quote styles (always use ")
- NO missing end statements for subgraphs

**MERMAID EXAMPLES:**

Example 1 - Flowchart with subgraphs:
```mermaid
flowchart TD
    subgraph datasources["Data Sources"]
        lambda["AWS Lambda"]
        spark["Spark Jobs"]
        python["Python Apps"]
    end

    subgraph processing["Processing"]
        client["OC Lineage<br/>Client"]
        manifest["Manifest<br/>Generator"]
    end

    subgraph storage["Storage"]
        console["Console"]
        file["Local File"]
        s3["AWS S3"]
    end

    lambda --> client
    spark --> client
    python --> client

    client --> console
    client --> file
    client --> s3
    manifest -.-> s3
```

Example 1.1 - Flowchart with subgraphs:
```mermaid
flowchart TD
    A[Developer Modifies Code] --> B{"Pre-commit Hook<br/>Triggered"}
    B -- Calls --> C["Cursor Agent<br/>(LLM)"]
    C -- Proposes --> D["Doc Updates<br/>(docs/_suggested.patch)"]
    D --> E{"Developer Reviews<br/>and Commits"}
    E --> F[Push to Git Repository]
    F --> G{"CI Pipeline<br/>Triggered"}
    G -- Runs --> H[Staleness Check]
    G -- Runs --> I["Doc Validation<br/>(validate_docs.py)"]
    I -- On Merge to main --> J["Confluence Publishing<br/>(GitHub Action)"]
    J --> K["Confluence Central Docs<br/>(Locked)"]
    K -- Secure, Versioned --> L[Stakeholders]
    H -. Comments if stale .-> E
```
Example 1.2 - Flowchart with subgraphs:
```mermaid
flowchart TD

    A[LLM Agent] --> B{"Consult Documentation"}
    B -- Rule 1 --> C["Reference Docs Before Assumptions"]
    B -- Rule 2 --> D["Combine Doc Context + Code Comments"]
    B -- Rule 3 --> E["Use Mermaid for Flows"]
    B -- Rule 4 --> F["Follow DOCS_STANDARDS.md for Updates"]

    subgraph "Documentation System"
        G["/docs/ (Primary Location)"]
        H["docs-central (Central Source)"]
        I["Confluence (Publishing Target)"]
    end

    C --> G
    D --> G
    E --> G
    F --> G
```

Example 2 - Sequence diagram:
```mermaid
sequenceDiagram
    autonumber
    participant pipeline as Pipeline
    participant client as OC Client
    participant transport as Transport
    participant storage as Storage

    pipeline->>client: Job START/COMPLETE
    client->>transport: Emit events

    alt S3 Transport
        transport->>storage: Write to S3
    else File Transport
        transport->>client: Write to file
    end

    Note over storage: Partitioned by date
```

Example 3 - Class diagram:
```mermaid
classDiagram
    class Repository {{
        +String name
        +String url
        +getStructure(): RepoStructure
        +analyze(): AnalysisResult
    }}

    class WikiGenerator {{
        +Repository repo
        +Model model
        +generateWiki(): Wiki
        +generatePage(): WikiPage
    }}

    class WikiPage {{
        +String id
        +String title
        +String content
        +String[] filePaths
        +generateContent(): String
    }}

    Repository --> WikiGenerator : generates
    WikiGenerator --> WikiPage : creates
    WikiPage --> Repository : analyzes
```

Example 4 - Entity-Relationship diagram:
```mermaid
erDiagram
    PROJECT ||--o{{ WIKI : has
    PROJECT ||--o{{ FILE : stores
    WIKI ||--o{{ PAGE : contains
    PAGE ||--o{{ PAGE_VERSION : versions
    PAGE ||--o{{ PAGE_FILE : references
    FILE ||--o{{ PAGE_FILE : referenced_by
    PAGE ||--o{{ PAGE_LINK : links_from
    PAGE ||--o{{ PAGE_LINK : links_to

    PROJECT {{
        uuid id PK
        string name
        string url
        datetime created_at
        datetime updated_at
        string created_by
        string updated_by
    }}

    WIKI {{
        uuid id PK
        uuid project_id FK
        string title
        string description
        string type  "enum or label"
        datetime created_at
        datetime updated_at
        string created_by
        string updated_by
    }}

    PAGE {{
        uuid id PK
        uuid wiki_id FK
        string title
        string slug        "unique within wiki"
        string content     "latest version/body"
        string importance  "enum: low|medium|high or 1-5"
        datetime created_at
        datetime updated_at
        string created_by
        string updated_by
    }}

    FILE {{
        uuid id PK
        uuid project_id FK
        string repo        "e.g. org/repo"
        string ref_sha     "git commit SHA"
        string path        "repo-relative path"
        string mime_type
        string type        "logical type, e.g. markdown/image"
        datetime created_at
        datetime updated_at
        string created_by
        string updated_by
    }}

    PAGE_FILE {{
        uuid id PK
        uuid page_id FK
        uuid file_id FK
        string role        "e.g. embedded|reference|attachment"
        datetime created_at
    }}

    PAGE_LINK {{
        uuid id PK
        uuid src_page_id FK
        uuid dst_page_id FK
        string link_type   "e.g. sees|includes|related"
        datetime created_at
    }}

    PAGE_VERSION {{
        uuid id PK
        uuid page_id FK
        int version
        string content
        string editor
        datetime created_at
    }}
```

4.  **Code Examples:** Where appropriate, include brief code snippets (properly formatted in Markdown code blocks with language identifiers like ```python, ```javascript, etc.) extracted directly from the RELEVANT_SOURCE_FILES to illustrate key concepts, implementations, or usage patterns. Do not invent code; only use what is present in the source files.

5.  **Technical Accuracy:** All information MUST be derived SOLELY from the source files. Do not invent, assume, or supplement with external knowledge. If a specific aspect is not covered in the provided files, either omit it or clearly state that the information is not available in the provided context.

6.  **Clarity and Conciseness:** Use clear, professional, and concise technical language appropriate for developers and technical stakeholders. Avoid jargon unless it's standard within the project's context.

7.  **Consistency:** Maintain consistent formatting, terminology, and style throughout the page.

Generate the content in English. Do NOT wrap your response in markdown code fences. Do NOT provide any acknowledgements, disclaimers, apologies, or any other preface. JUST START with the `<details>` block as the very first line of your response."""

        if extra_feedback:
            prompt += (
                "\nUser feedback and guidance:\n"
                + extra_feedback.strip()
                + "\n"
            )


        page_bar.update(30)  # Prompt ready

        # Prepare request
        messages = [{"role": "user", "content": prompt}]

        page_bar.update(50)  # Request sent

        # Collect streamed content with incremental progress updates
        content = ""
        chunk_count = 0
        start_time = time.time()
        last_update_time = start_time
        last_progress = 50

        try:
            stream = generation_context.stream_completion(messages=messages)
            for chunk in stream:
                if chunk:
                    content += chunk if isinstance(chunk, str) else str(chunk)
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
                        time_progress, content_progress, last_progress
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

            # Clean up content
            content = content.strip()
            if content.startswith("```markdown"):
                content = content[len("```markdown") :].strip()
            if content.endswith("```"):
                content = content[:-3].strip()

            # Update page
            page.content = content

            page_bar.update(100)  # Complete
            progress_manager.complete_page(page_id)
        except Exception as e:
            logger.error(f"Error generating page {page_title}: {e}")
            return None

        if not content:
            logger.warning(f"No content generated for page {page_title}")
            return None

        return page

    except Exception as e:
        logger.error(f"Error generating page {page_title}: {e}")
        progress_manager.complete_page(page_id)
        return None


def generate_wiki_structure(
    repo_url: str,
    repo_type: str,
    file_tree: str,
    readme: str,
    provider: str,
    model: str,
    is_comprehensive: bool,
    generation_context: Optional[WikiGenerationContext] = None,
) -> Optional[WikiStructureModel]:
    """
    Generate wiki structure from repository.

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
    prompt = f"""Analyze this repository and create a wiki structure for it.

1. The complete file tree of the project:
<file_tree>
{file_tree}
</file_tree>

2. The README file of the project:
<readme>
{readme}
</readme>

I want to create a wiki for this repository. Determine the most logical structure for a wiki based on the repository's content.

IMPORTANT: The wiki content will be generated in English.

When designing the wiki structure, include pages that would benefit from visual diagrams, such as:
- Architecture overviews
- Data flow descriptions
- Component relationships
- Process workflows
- State machines
- Class hierarchies

{"Create a structured wiki with the following main sections:" if is_comprehensive else "Create a concise wiki with essential pages covering:"}
{"- Overview (general information about the project)" if is_comprehensive else ""}
{"- System Architecture (how the system is designed)" if is_comprehensive else ""}
{"- Core Features (key functionality)" if is_comprehensive else ""}
{"- Data Management/Flow: If applicable, how data is stored, processed, accessed, and managed (e.g., database schema, data pipelines, state management)." if is_comprehensive else ""}
{"- Frontend Components (UI elements, if applicable.)" if is_comprehensive else ""}
{"- Backend Systems (server-side components)" if is_comprehensive else ""}
{"- Model Integration (AI model connections)" if is_comprehensive else ""}
{"- Deployment/Infrastructure (how to deploy, what's the infrastructure like)" if is_comprehensive else ""}
{"- Extensibility and Customization: If the project architecture supports it, explain how to extend or customize its functionality (e.g., plugins, theming, custom modules, hooks)." if is_comprehensive else ""}

{"Each section should contain relevant pages. For example, the 'Frontend Components' section might include pages for 'Home Page', 'Repository Wiki Page', 'Configuration Modal', etc." if is_comprehensive else ""}

Return your analysis in the following XML format:

<wiki_structure>
  <title>[Overall title for the wiki]</title>
  <description>[Brief description of the repository]</description>
  <pages>
    <page id="page-1">
      <title>[Page title]</title>
      <description>[Brief description of what this page will cover]</description>
      <importance>high|medium|low</importance>
      <relevant_files>
        <file_path>[Path to a relevant file]</file_path>
        <!-- More file paths as needed -->
      </relevant_files>
      <related_pages>
        <related>page-2</related>
        <!-- More related page IDs as needed -->
      </related_pages>
    </page>
    <!-- More pages as needed -->
  </pages>
</wiki_structure>

IMPORTANT FORMATTING INSTRUCTIONS:
- Return ONLY the valid XML structure specified above
- DO NOT wrap the XML in markdown code blocks (no ``` or ```xml)
- DO NOT include any explanation text before or after the XML
- Ensure the XML is properly formatted and valid
- Start directly with <wiki_structure> and end with </wiki_structure>

IMPORTANT:
1. Create {min_pages}-{max_pages} pages (aim for {target_pages} pages) that would make a {"comprehensive" if is_comprehensive else "concise"} wiki for this repository. The repository contains {file_count} files, so adjust the number of pages accordingly - larger repositories may need more pages to cover all important aspects.
2. Each page should focus on a specific aspect of the codebase (e.g., architecture, key features, setup)
3. The relevant_files should be actual files from the repository that would be used to generate that page
4. Return ONLY valid XML with the structure specified above, with no markdown code block delimiters"""

    try:
        # Collect response from streaming generator
        xml_content = ""
        if generation_context:
            stream = generation_context.stream_completion(
                messages=[{"role": "user", "content": prompt}]
            )
        else:
            from api.utils.chat import generate_chat_completion_streaming

            stream = generate_chat_completion_streaming(
                repo_url=repo_url,
                messages=[{"role": "user", "content": prompt}],
                provider=provider,
                model=model,
                repo_type=repo_type,
            )

        for chunk in stream:
            if chunk:
                xml_content += chunk if isinstance(chunk, str) else str(chunk)

        # Parse XML
        import xml.etree.ElementTree as ET

        # Clean up response
        xml_content = xml_content.strip()
        if xml_content.startswith("```xml") or xml_content.startswith("```"):
            xml_content = (
                xml_content.split("\n", 1)[1] if "\n" in xml_content else xml_content
            )
        if xml_content.endswith("```"):
            xml_content = (
                xml_content.rsplit("\n", 1)[0] if "\n" in xml_content else xml_content
            )

        # Extract XML
        import re

        xml_match = re.search(
            r"<wiki_structure>.*</wiki_structure>", xml_content, re.DOTALL
        )
        if not xml_match:
            logger.error("No valid XML structure found in response")
            return None

        xml_text = xml_match.group(0)

        # Clean XML: escape common problematic characters
        import html

        # First unescape any HTML entities
        xml_text = html.unescape(xml_text)

        # Escape ampersands that aren't part of entities
        xml_text = re.sub(r"&(?!(?:amp|lt|gt|quot|apos);)", "&amp;", xml_text)

        # Parse XML
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.error(f"XML parsing failed: {e}")
            logger.debug(f"Failed XML content:\n{xml_text[:500]}...")
            return None

        title_el = root.find("title")
        title = title_el.text if title_el is not None and title_el.text else "Wiki"
        description_el = root.find("description")
        description = (
            description_el.text
            if description_el is not None and description_el.text
            else ""
        )

        # Parse pages
        pages: List[WikiPage] = []
        pages_el = root.find("pages")
        if pages_el is not None:
            for page_el in pages_el.findall("page"):
                page_id = page_el.get("id", f"page-{len(pages) + 1}")
                page_title_el = page_el.find("title")
                page_title = (
                    page_title_el.text
                    if page_title_el is not None and page_title_el.text
                    else "Untitled"
                )
                importance_el = page_el.find("importance")
                importance_text = (
                    importance_el.text
                    if importance_el is not None and importance_el.text
                    else "medium"
                )
                importance_lower = (
                    importance_text.lower() if importance_text else "medium"
                )
                importance = (
                    importance_lower
                    if importance_lower in ["high", "medium", "low"]
                    else "medium"
                )

                # File paths
                file_paths = []
                relevant_files_el = page_el.find("relevant_files")
                if relevant_files_el is not None:
                    for fp in relevant_files_el.findall("file_path"):
                        if fp.text:
                            file_paths.append(fp.text.strip())

                # Related pages
                related_pages = []
                related_pages_el = page_el.find("related_pages")
                if related_pages_el is not None:
                    for rel in related_pages_el.findall("related"):
                        if rel.text:
                            related_pages.append(rel.text.strip())

                pages.append(
                    WikiPage(
                        id=page_id,
                        title=page_title,
                        content="",
                        filePaths=file_paths,
                        importance=importance,
                        relatedPages=related_pages,
                    )
                )

        if not pages:
            logger.error("No pages found in wiki structure")
            return None

        return WikiStructureModel(
            id="wiki",
            title=title,
            description=description,
            pages=pages,
            sections=[],
            rootSections=[],
        )

    except Exception as e:
        logger.error(f"Error parsing wiki structure: {e}")
        return None


def _is_git_repo(path: str) -> bool:
    """Check if a path is a git repository."""
    git_dir = os.path.join(path, ".git")
    return os.path.exists(git_dir) or os.path.isdir(git_dir)


def _load_gitignore_patterns(repo_path: str) -> List[str]:
    """Load .gitignore patterns from repository root."""
    patterns = []
    gitignore_path = os.path.join(repo_path, ".gitignore")

    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        patterns.append(line)
        except Exception as e:
            logger.warning(f"Error reading .gitignore: {e}")

    return patterns


def _matches_gitignore_pattern(
    file_path: str, patterns: List[str], repo_path: str
) -> bool:
    """Check if a file path matches any .gitignore pattern."""
    # Normalize path relative to repo root
    rel_path = os.path.relpath(file_path, repo_path)
    rel_path_parts = rel_path.split(os.sep)

    for pattern in patterns:
        # Skip negated patterns (starting with !) for now
        if pattern.startswith("!"):
            continue

        # Handle patterns anchored to root (starting with /)
        if pattern.startswith("/"):
            pattern = pattern[1:]
            # Match from repo root only
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
                rel_path_parts[0], pattern
            ):
                return True
            continue

        # Handle directory patterns (ending with /)
        if pattern.endswith("/"):
            pattern = pattern[:-1]
            # Check if any directory in the path matches
            for part in rel_path_parts[:-1]:  # Exclude filename for directory patterns
                # Support ** for matching any number of directories
                if "**" in pattern:
                    pattern_normalized = pattern.replace("**", "*")
                    if fnmatch.fnmatch(part, pattern_normalized):
                        return True
                elif fnmatch.fnmatch(part, pattern):
                    return True
            continue

        # Handle ** patterns for files
        if "**" in pattern:
            # Replace ** with * for fnmatch compatibility
            pattern_normalized = pattern.replace("**", "*")
            if fnmatch.fnmatch(rel_path, pattern_normalized):
                return True
            continue

        # Check full path or filename
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(
            os.path.basename(rel_path), pattern
        ):
            return True

    return False


def _collect_files_with_git(repo_path: str) -> Optional[List[str]]:
    """Collect tracked files using git ls-files."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        files = []
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                full_path = os.path.join(repo_path, line.strip())
                if os.path.isfile(full_path):
                    files.append(full_path)
        return files
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ) as e:
        logger.warning(f"git ls-files failed: {e}, falling back to directory walk")
        return None


def _collect_files_with_walk(repo_path: str) -> List[str]:
    """Collect files by walking the directory tree with .gitignore filtering."""
    files = []
    gitignore_patterns = _load_gitignore_patterns(repo_path)

    # Always exclude .git and vendor directories
    excluded_dirs = {".git", "vendor"}

    for root, dirs, filenames in os.walk(repo_path):
        # Filter out excluded directories from dirs list to prevent traversal
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        # Check if current directory should be excluded
        rel_root = os.path.relpath(root, repo_path)
        root_parts = rel_root.split(os.sep) if rel_root != "." else []

        # Skip if any part of the path matches excluded directories
        if any(part in excluded_dirs for part in root_parts):
            continue

        for filename in filenames:
            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, repo_path)

            # Skip if matches .gitignore patterns
            if gitignore_patterns and _matches_gitignore_pattern(
                file_path, gitignore_patterns, repo_path
            ):
                continue

            # Skip if in excluded directories
            if any(part in excluded_dirs for part in rel_path.split(os.sep)):
                continue

            files.append(file_path)

    return files


def collect_repository_files(repo_path: str) -> List[str]:
    """
    Collect all relevant files from a repository using repository-aware discovery.

    Prefers using git ls-files for tracked files, falls back to walking the tree
    with .gitignore filtering. Excludes .git and vendor directories.

    Args:
        repo_path: Path to the local repository

    Returns:
        List of absolute file paths
    """
    if not os.path.isdir(repo_path):
        raise ValueError(f"Repository path does not exist: {repo_path}")

    # Try git ls-files first if it's a git repository
    if _is_git_repo(repo_path):
        files = _collect_files_with_git(repo_path)
        if files is not None:
            logger.info(f"Collected {len(files)} files using git ls-files")
            return files

    # Fall back to directory walk with .gitignore filtering
    files = _collect_files_with_walk(repo_path)
    logger.info(f"Collected {len(files)} files using directory walk")
    return files


def _read_local_readme(repo_path: str) -> str:
    for readme_name in ["README.md", "readme.md", "README.txt"]:
        readme_path = os.path.join(repo_path, readme_name)
        if os.path.exists(readme_path):
            try:
                with open(readme_path, "r", encoding="utf-8", errors="ignore") as handle:
                    return handle.read()
            except Exception as exc:
                logger.debug(f"Failed to read {readme_path}: {exc}")
    return ""


def prepare_repository_state(
    repo_type: str,
    repo_url_or_path: str,
    owner: Optional[str],
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
        snapshot = build_snapshot_from_tree(
            data.get("tree_files"), reference=f"{owner}/{repo_name}"
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
def generate(force: bool):
    """Generate a new wiki or refresh an existing cache."""

    click.echo("\n" + "=" * 60)
    click.echo("DeepWiki Generator")
    click.echo("=" * 60)

    config = load_config()
    progress: Optional[ProgressManager] = None

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
            cache_path, repo_type, owner_key, repo_name
        )

        selected_cache_entry: Optional[CacheFileInfo] = None
        existing_cache: Optional[WikiCacheData] = None
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
                repo_type, repo_url_or_path, owner, repo_name
            )
            click.echo("✓ Repository inspected")
        except Exception as e:
            click.echo(f"✗ Error inspecting repository: {e}", err=True)
            progress.close()
            raise click.Abort()

        if not repo_state.file_tree.strip():
            click.echo("✗ No files found in repository", err=True)
            progress.close()
            raise click.Abort()

        change_summary = None
        affected_pages: List[str] = []
        action = "overwrite"

        if existing_cache and selected_cache_entry:
            if force:
                action = "overwrite"
            else:
                change_summary = detect_repo_changes(
                    repo_url_or_path, existing_cache, repo_state.snapshot
                )
                affected_pages = find_affected_pages(
                    change_summary.get("changed_files", [])
                    if change_summary
                    else [],
                    existing_cache.wiki_structure,
                )
                _display_change_summary(
                    repo_name,
                    selected_cache_entry,
                    change_summary,
                    existing_cache.wiki_structure,
                    affected_pages,
                )
                action = _prompt_generation_action(True, affected_pages)
                if action == "cancel":
                    progress.close()
                    click.echo("Operation cancelled.")
                    return
        else:
            action = "overwrite"

        selected_page_ids: List[str] = []
        page_feedback: Dict[str, str] = {}

        if action == "update":
            if not (existing_cache and affected_pages):
                click.echo(
                    "No affected pages detected; regenerating the entire wiki instead."
                )
                action = "overwrite"
            else:
                selected_page_ids = _prompt_pages_to_regenerate(
                    existing_cache.wiki_structure, affected_pages
                )
                if not selected_page_ids:
                    progress.close()
                    click.echo("No pages selected. Operation cancelled.")
                    return
                page_feedback = _collect_page_feedback(
                    selected_page_ids, existing_cache.wiki_structure
                )

        target_version = 1
        if action == "new_version":
            highest = max((entry.version for entry in existing_entries), default=0)
            base_version = (
                selected_cache_entry.version if selected_cache_entry else 1
            )
            target_version = max(highest, base_version) + 1
        elif selected_cache_entry:
            target_version = selected_cache_entry.version

        language = DEFAULT_LANGUAGE

        progress.set_status("Preparing repository context")
        click.echo("Preparing repository analysis...")
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
            )
            click.echo("✓ Repository prepared")
        except Exception as e:
            click.echo(f"✗ Error preparing repository: {e}", err=True)
            progress.close()
            raise click.Abort()

        wiki_structure: Optional[WikiStructureModel] = None
        generated_pages: Dict[str, WikiPage] = {}
        regenerated_ids: List[str] = []
        reused_count = 0

        if action == "update" and existing_cache:
            wiki_structure = existing_cache.wiki_structure
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

            if not wiki_structure:
                click.echo("✗ Failed to generate wiki structure", err=True)
                progress.close()
                raise click.Abort()

            click.echo(f"✓ Structure created: {len(wiki_structure.pages)} pages")

            progress.set_status("Generating pages")
            progress.init_overall_progress(len(wiki_structure.pages), "Generating Pages")
            click.echo(f"\nGenerating {len(wiki_structure.pages)} pages...\n")

            for page in wiki_structure.pages:
                updated_page = generate_page_content_sync(
                    page, generation_context, repo_url_or_path, progress
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

        now_iso = datetime.utcnow().isoformat()
        created_at = (
            now_iso
            if action == "new_version" or not existing_cache
            else existing_cache.created_at or now_iso
        )

        cache_payload = WikiCacheData(
            wiki_structure=wiki_structure,
            generated_pages={
                pid: page.model_dump() if isinstance(page, WikiPage) else page
                for pid, page in generated_pages.items()
            },
            repo=repo_info,
            provider=provider,
            model=model,
            version=target_version,
            created_at=created_at,
            updated_at=now_iso,
            repo_snapshot=repo_state.snapshot,
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
            + (
                "Update affected pages" if action == "update" else "Full regeneration"
            )
        )
        click.echo(f"Pages regenerated: {len(regenerated_ids)}")
        if reused_count:
            click.echo(f"Pages reused: {reused_count}")
        click.echo(f"Cache file: {cache_file}")
        if change_summary:
            click.echo(
                f"Files processed: {len(change_summary.get('changed_files', []))} changed, "
                f"{len(change_summary.get('new_files', []))} new, "
                f"{len(change_summary.get('deleted_files', []))} deleted"
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
        logger.error(f"Unexpected error: {e}", exc_info=True)
        click.echo(f"\n✗ Unexpected error: {e}", err=True)
        sys.exit(1)
