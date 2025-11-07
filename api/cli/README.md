# DeepWiki CLI

Command-line interface for generating comprehensive wikis from code repositories.

## Installation

The CLI is automatically installed when you install the DeepWiki API package:

```bash
cd api
poetry install
```

The `deepwiki` command will be available in your terminal.

## Prerequisites

1. **Environment Variables**: Ensure your `.env` file in the project root contains necessary API keys:

   ```
   GOOGLE_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here
   OPENROUTER_API_KEY=your_key_here
   GITHUB_TOKEN=your_token_here  # Optional, for private repos
   ```

2. **Backend Server**: The CLI requires the DeepWiki API server to be running:

   ```bash
   cd api
   poetry run python -m api.main
   ```

   The server should be running on `http://localhost:8001`.

## Commands

### Generate Wiki

Interactive wiki generation from a repository:

```bash
deepwiki generate
```

You'll be prompted for:

- Repository (GitHub URL, owner/repo shorthand, or local path)
- Model provider (google, openai, openrouter, ollama, etc.)
- Model selection
- Wiki type (comprehensive or concise)
- Optional file filters

**Example workflow:**

```
Repository: https://github.com/owner/repo
Provider: google
Model: gemini-2.0-flash-exp
Wiki type: comprehensive
File filters: No
```

The CLI will:

1. Clone/analyze the repository
2. Generate wiki structure
3. Generate content for all pages (with progress bars)
4. Save to cache at `~/.adalflow/wikicache/`

### List Cached Wikis

Display all cached wikis:

```bash
deepwiki list
```

Shows:

- Repository name
- Type (github/local)
- Language
- Wiki type (comprehensive/concise)
- Number of pages
- File size
- Last modified date
- Cache file path

### Export Wiki

Export a cached wiki to Markdown or JSON:

```bash
deepwiki export
```

You'll be prompted to:

1. Select a wiki from the list
2. Choose format (markdown or json)
3. Specify output path (optional)

**Example:**

```
Select wiki: 1
Format: markdown
Output: (leave empty for auto-generated name)
```

Exports to a timestamped file like `owner_repo_wiki_20240107_143022.md`

### Delete Wiki

Delete a cached wiki from the cache:

```bash
deepwiki delete
```

You'll be prompted to:

1. Select a wiki from the list
2. Confirm deletion (unless `--yes` flag is used)

**Example:**

```
Select wiki to delete (enter number): 1
Are you sure you want to delete 'owner/repo' (github, en)? [y/N]: y
✓ Wiki cache for owner/repo (en) deleted successfully
```

**Skip confirmation:**

```bash
deepwiki delete --yes
# or
deepwiki delete -y
```

### Configuration Management

#### Show Current Config

```bash
deepwiki config show
```

Displays the current configuration from `~/.deepwiki/config.json`.

#### Set Config Value

```bash
deepwiki config set <key> <value>
```

**Examples:**

```bash
# Set default provider
deepwiki config set default_provider google

# Set default model
deepwiki config set default_model gemini-2.0-flash-exp

# Set wiki type
deepwiki config set wiki_type comprehensive

# Set nested values (use JSON)
deepwiki config set file_filters.excluded_dirs '["node_modules", "dist"]'
```

### Help

```bash
deepwiki --help
deepwiki generate --help
deepwiki list --help
deepwiki export --help
deepwiki delete --help
deepwiki config --help
```

## Configuration

The CLI stores user preferences in `~/.deepwiki/config.json`:

```json
{
  "default_provider": "google",
  "default_model": "gemini-2.0-flash-exp",
  "wiki_type": "comprehensive",
  "file_filters": {
    "excluded_dirs": [],
    "excluded_files": []
  }
}
```

These values are used as defaults during interactive prompts but can be overridden.

## Cache Location

Generated wikis are cached at:

```
~/.adalflow/wikicache/deepwiki_cache_{type}_{owner}_{repo}_{language}.json
```

**Example:**

```
~/.adalflow/wikicache/deepwiki_cache_github_openai_gpt-4_en.json
```

## Progress Display

The CLI uses the Enlighten library to display:

- Overall progress bar (pages completed/total)
- Individual page generation progress
- Real-time status updates
- Clean, multi-line progress bars

## Examples

### Generate Wiki for Public GitHub Repo

```bash
deepwiki generate
# Enter: https://github.com/fastapi/fastapi
# Select: google / gemini-2.0-flash-exp
# Choose: comprehensive
# Skip file filters
```

### Generate Wiki for Local Project

```bash
deepwiki generate
# Enter: /path/to/my/project
# Select: openai / gpt-4-turbo
# Choose: concise
# Skip file filters
```

### Export to Markdown

```bash
deepwiki export
# Select wiki: 1
# Format: markdown
# Output: my-docs.md
```

### Check Configuration

```bash
deepwiki config show
```

## Troubleshooting

### "No cached wikis found"

Generate a wiki first using `deepwiki generate`.

### "Backend API server error"

Ensure the API server is running:

```bash
cd api
poetry run python -m api.main
```

### "API key not configured"

Check your `.env` file in the project root contains the necessary API keys.

### "Module not found"

Reinstall the package:

```bash
cd api
poetry install
```

## Features

- ✅ Interactive prompts for easy use
- ✅ Multi-progress bars for visual feedback
- ✅ Comprehensive or concise wiki generation
- ✅ Support for GitHub and local repositories
- ✅ Multiple model providers (Google, OpenAI, OpenRouter, Ollama, etc.)
- ✅ Automatic caching for fast re-access
- ✅ Export to Markdown or JSON
- ✅ Delete cached wikis
- ✅ Configuration management
- ✅ File filtering options

## Architecture

The CLI reuses the DeepWiki backend:

- `api.rag.RAG` - Repository analysis and retrieval
- `api.data_pipeline` - Document processing and embedding
- `api.api` - Data models and export functions
- Backend API server - Wiki structure and content generation

All generation logic from the web UI is available in the CLI with the same quality and features.
