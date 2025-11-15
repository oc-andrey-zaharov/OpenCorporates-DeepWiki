# OpenCorporates-DeepWiki

Automatically create beautiful, interactive wikis for any GitHub repository. Analyze code structure, generate comprehensive documentation, and create visual diagrams with AI.

## Features

- **Instant Documentation**: Turn any repo into a wiki in seconds
- **Private Repository Support**: Securely access private repositories with tokens
- **Smart Analysis**: AI-powered code understanding
- **Beautiful Diagrams**: Automatic Mermaid diagrams for architecture and data flow
- **DeepResearch**: Multi-turn research process for complex topics
- **Incremental Regeneration**: Detects repo changes, updates only affected pages, and preserves untouched content
- **Versioned Cache Management**: Maintain multiple wiki snapshots per repo with clear version numbering and summaries
- **Multiple Model Providers**: Google Gemini, OpenAI, OpenRouter, AWS Bedrock, and local Ollama
- **Standalone CLI**: Works completely offline with a clean Python/Poetry toolchain
- **Editable Workspaces**: Export markdown wikis into `docs/wiki`, edit locally, and sync back to the cache

## Quick Start

### Using Makefile (Recommended)

```bash
# Install dependencies
make install

# Use the CLI directly
make cli ARGS="wiki generate"
```

### Manual Installation

#### Prerequisites

- [Poetry v2](https://python-poetry.org/) for Python dependencies
- Python 3.11+

#### Step 1: Setup Environment

Create a `.env` file (copy from `.env.example` if available):

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```bash
GOOGLE_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key

# GitHub Personal Access Token for private repositories
# See instructions below on how to create one
GITHUB_TOKEN=your_github_personal_access_token

# Optional
OPENROUTER_API_KEY=your_openrouter_api_key
DEEPWIKI_EMBEDDER_TYPE=google  # or 'openai' (default), 'ollama'
OLLAMA_HOST=http://localhost:11434
```

### Getting a GitHub Personal Access Token

To access private GitHub repositories, you need to create a GitHub Personal Access Token:

1. **Go to GitHub Settings**: Navigate to [GitHub Settings > Developer settings > Personal access tokens > Tokens (classic)](https://github.com/settings/tokens)
2. **Generate New Token**: Click "Generate new token" > "Generate new token (classic)"
3. **Configure Token**:
   - Give it a descriptive name (e.g., "OpenCorporates DeepWiki")
   - Set an expiration date (or no expiration for internal use)
   - Select the following scopes:
     - `repo` - Full control of private repositories (required for private repos)
     - `read:org` - Read org membership (optional, if accessing org repos)
4. **Generate and Copy**: Click "Generate token" and copy the token immediately (you won't be able to see it again)
5. **Add to .env**: Add the token to your `.env` file:

   ```bash
   GITHUB_TOKEN=ghp_your_token_here
   ```

**Security Note**: Never commit your `.env` file or share your token. The token is stored in your `.env` file only and is used automatically by the CLI when accessing private repositories.

#### Step 2: Install Dependencies

```bash
# From project root
poetry install
```

#### Step 3: Use CLI

```bash
# Generate a wiki (standalone mode - default)
./deepwiki wiki generate

# List available commands
./deepwiki --help
```

## Usage

### CLI Commands

The DeepWiki CLI provides several commands:

- `deepwiki wiki generate` - Generate or refresh a wiki for a repository
- `deepwiki wiki export` - Export a cached wiki to markdown or JSON (version aware)
- `deepwiki wiki delete` - Delete a specific cached wiki version
- `deepwiki wiki list` - List all cached wikis with version, size, and metadata
- `deepwiki config` - Manage configuration settings
- `deepwiki sync` - Apply edits from `docs/wiki` workspaces back to the cache (optionally watch)

#### Generate Wiki

Interactive wiki generation from a repository:

```bash
deepwiki wiki generate
```

You'll be prompted for:

- Repository (GitHub URL, owner/repo shorthand, or local path)
- Model provider (google, openai, openrouter, ollama, etc.)
- Model selection
- Wiki type (comprehensive or concise)
- Optional file filters

When a cache already exists, the CLI now performs change detection against the last snapshot and shows a concise summary (changed/new/deleted counts plus affected pages). You can then choose to:

1. **Overwrite existing wiki** – regenerate everything (default for `--force`)
2. **Update only affected pages** – multi-select individual pages (space to toggle) and optionally provide per-page feedback before regeneration
3. **Create new version** – keep the existing cache intact and write a new `_vN` snapshot
4. **Cancel** – exit without changes

Use `--force` to skip all prompts and overwrite the latest version in CI or scripted workflows.

#### List Cached Wikis

Display all cached wikis:

```bash
deepwiki wiki list
```

Shows repository name, type, language, wiki type, number of pages, cache version, file size, last modified date, and cache file path.

#### Export Wiki

Export a cached wiki to Markdown or JSON:

```bash
deepwiki wiki export
```

You'll be prompted to select a wiki/version combo from the list, choose format (markdown or json), and specify output path (optional). The generated filename automatically includes the version suffix (e.g., `_v3`).

### Editable Wiki Workspaces

Running `deepwiki wiki export` in **markdown** mode now creates an editable workspace under `docs/wiki/<owner-repo>_vN`. Two layouts are available:

- `--layout single` – a single Markdown file that contains markers for each page.
- `--layout multi` – one Markdown file per page, grouped into nested folders that mirror the wiki structure with automatic page linking.

Each export drops a `.deepwiki-manifest.json` file alongside the Markdown. You can:

1. Enable `--watch` (or accept the interactive prompt) to monitor files for changes; edits are synced back to the cache immediately.
2. Use any editor (Cursor, VS Code, etc.) to update the Markdown inside `docs/wiki`.
3. Run `deepwiki sync` later if you exported without watching or want to apply changes in batch.

The `deepwiki sync` command accepts `--workspace /path/to/docs/wiki/<workspace>` and also supports `--watch` to keep syncing after the first run.

#### Delete Wiki

Delete a cached wiki from the cache:

```bash
deepwiki wiki delete
```

You'll be prompted to select a wiki/version and confirm deletion (use `--yes` flag to skip confirmation). Server mode requests include the version so you can prune specific snapshots without touching others.

### Cache Versions & Change Detection

- Cache files follow the pattern `deepwiki_cache_{type}_{owner}_{repo}_{language}_vN.json`. Version `v1` is implicit (no suffix), while higher versions append `_vN`.
- Each cache stores a light-weight repository snapshot (paths, sizes, hashes, mtimes). When you re-run `generate`, the CLI compares the new snapshot against the stored one to avoid unnecessary work.
- Change summaries include counts for changed/new/deleted files plus a list of wiki pages impacted by those files. Only the selected pages are regenerated; the rest of the cache is reused byte-for-byte.
- Multi-select prompts leverage `simple-term-menu` when available. Use the arrow keys + space to toggle multiple entries; press enter to accept the selection. In fallback mode, enter comma-separated numbers.
- Optional per-page feedback is injected directly into the LLM prompt so you can nudge wording or highlight new requirements before regeneration.

#### Configuration Management

```bash
deepwiki config show                    # Show current configuration
deepwiki config set <key> <value>      # Set a configuration value
```

Examples:

```bash
deepwiki config set default_provider google
deepwiki config set default_model gemini-2.0-flash-exp
deepwiki config set wiki_type comprehensive
```

### Shell Completion

DeepWiki CLI supports shell completion for Bash, Zsh, and Fish shells, providing autocomplete for commands, options, and arguments.

#### Setup Instructions

First, find the correct completion variable name by running:

```bash
deepwiki --help | head -1
```

The completion variable is typically `_<COMMAND>_COMPLETE` where `<COMMAND>` is your command name in uppercase. For `deepwiki`, it should be `_DEEPWIKI_COMPLETE`.

**Bash (>= 4.4):**

Add to your `~/.bashrc`:

```bash
eval "$(_DEEPWIKI_COMPLETE=bash_source deepwiki)"
```

Then reload your shell:

```bash
source ~/.bashrc
```

**Zsh:**

Add to your `~/.zshrc`:

```zsh
eval "$(_DEEPWIKI_COMPLETE=zsh_source deepwiki)"
```

Then reload your shell:

```zsh
source ~/.zshrc
```

**Fish:**

Add to your `~/.config/fish/config.fish`:

```fish
_DEEPWIKI_COMPLETE=fish_source deepwiki | source
```

Or save to a file for automatic loading:

```fish
_DEEPWIKI_COMPLETE=fish_source deepwiki > ~/.config/fish/completions/deepwiki.fish
```

**Note:** If `_DEEPWIKI_COMPLETE` doesn't work, try checking what Click generates by running:

```bash
_DEEPWIKI_COMPLETE=bash_source deepwiki
```

This will show you the completion script. The variable name format may vary slightly depending on your Click version.

#### Completion Features

- **Commands**: Autocomplete for `generate`, `export`, `list`, `delete`, `config`, etc.
- **Options**: Autocomplete for flags like `--format`, `--output`, `--verbose`
- **Config Keys**: Autocomplete for configuration keys in `config set` command
- **File Paths**: File path completion for `--output` and other path options
- **Choices**: Autocomplete for predefined choices (e.g., `--format` with `markdown`/`json`)

After setup, restart your shell or reload your configuration file. Then try typing `deepwiki` and press Tab to see completion in action!

### Standalone Mode

DeepWiki now runs exclusively as a CLI tool. All caching, wiki generation, and editing flows happen locally—no FastAPI layer required.

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_API_KEY` | Google Gemini API key | For Google models |
| `OPENAI_API_KEY` | OpenAI API key | For OpenAI models |
| `OPENROUTER_API_KEY` | OpenRouter API key | For OpenRouter models |
| `GITHUB_TOKEN` | GitHub Personal Access Token for private repositories | For private repos |
| `DEEPWIKI_EMBEDDER_TYPE` | Embedder type: `openai`, `google`, or `ollama` | No (default: `openai`) |
| `OLLAMA_HOST` | Ollama host URL | No (default: `http://localhost:11434`) |

### Configuration Files

Located in `src/deepwiki_cli/config/`:

- `generator.json` - Text generation model settings
- `embedder.json` - Embedding model and RAG settings
- `repo.json` - Repository handling rules

### CLI Configuration

The CLI stores configuration in `~/.deepwiki/config.json`. You can manage it with:

```bash
deepwiki config show          # Show current configuration
deepwiki config set key value  # Set a configuration value
```

Editable workspace settings:

- `wiki_workspace` - Base directory for markdown exports (default: `docs/wiki`)
- `export.layout` - Default markdown layout (`single` or `multi`)
- `export.watch` - Whether to auto-watch exports for edits (default: `false`)

## Makefile Commands

```bash
make help              # Show all commands
make install           # Install dependencies
make format            # Format code
make lint              # Run lint checks
make test              # Run full test suite
make cli ARGS="..."    # Run CLI with arguments
make clean             # Clean caches/artifacts
```

## Project Structure

```
opencorporates-deepwiki/
├── src/deepwiki_cli/    # Pure Python CLI package
│   ├── cli/             # CLI commands and entry point
│   ├── clients/         # Model client implementations (OpenAI, Bedrock, etc.)
│   ├── core/            # Core completion helpers
│   ├── services/        # RAG + data pipeline logic
│   ├── utils/           # Shared utilities
│   ├── templates/       # Prompt templates
│   ├── config/          # JSON configuration (models, embedders)
│   ├── config.py        # Configuration management
│   ├── models.py        # Pydantic models
│   ├── prompts.py       # Prompt builders
│   └── logging_config.py # Logging + structlog setup
├── docs/                # Documentation
│   └── wiki/            # Editable wiki exports
├── tests/               # Test suite
├── pyproject.toml      # Poetry project configuration
├── Makefile            # Build and run commands
└── .env                # Environment variables
```

## Architecture Overview

See [docs/architecture.md](docs/architecture.md) for a deeper look at the technology stack, component interactions, and Mermaid diagrams that explain the wiki generation flow.  
See [docs/diagram-validation.md](docs/diagram-validation.md) for details on how Mermaid diagrams are validated and automatically repaired during generation.

## API Keys

- **Google AI**: [Google AI Studio](https://makersuite.google.com/app/apikey)
- **OpenAI**: [OpenAI Platform](https://platform.openai.com/api-keys)
- **OpenRouter**: [OpenRouter](https://openrouter.ai/)

## Troubleshooting

**API Key Issues**: Check your `.env` file has valid keys without extra spaces

**Generation Issues**: Try a smaller repository first, ensure tokens have correct permissions

**Workspace Sync Issues**: Ensure you're editing files inside `docs/wiki/...` and that `.deepwiki-manifest.json` exists. Re-run `deepwiki export` if the workspace was deleted.

## Logging

Logs are written to `src/deepwiki_cli/logs/application.log` by default (JSON via structlog). You can configure logging via environment variables:

- `LOG_LEVEL` - Log level (default: `INFO`)
- `LOG_FILE_PATH` - Path to log file (default: `src/deepwiki_cli/logs/application.log`)

## Testing

### Running Tests

#### All Tests

```bash
# From project root
poetry run pytest tests -v
```

#### Unit Tests Only

```bash
poetry run pytest tests/unit -v
```

#### Integration Tests Only

```bash
poetry run pytest tests/integration -v
```

### Test Structure

```
tests/
├── unit/                 # Unit tests - test individual components in isolation
└── integration/          # Integration tests - test component interactions
```

Integration tests require valid API keys in `.env`:

- `GOOGLE_API_KEY`
- `OPENAI_API_KEY`
- `DEEPWIKI_EMBEDDER_TYPE` (set to `google` for Google embedder tests)

## API Endpoints

The optional FastAPI server exposes light-weight utilities that complement the CLI:

- `GET /` — Basic server info + health.
- `GET /models/config` — Returns configured model providers/models.
- `GET /local_repo/structure` — Builds a file tree + README for a local path.
- `GET /github/repo/structure` — Same as above but fetches directly from GitHub using the configured token.
- `GET /api/wiki_cache` — Retrieve cached wiki metadata.
- `POST /api/wiki_cache` — Persist wiki cache entries.
- `DELETE /api/wiki_cache` — Remove a cache entry.
- `GET /api/processed_projects` — List cached projects for dashboards.
- `POST /export/wiki` — Convert cached pages to Markdown or JSON for download.
