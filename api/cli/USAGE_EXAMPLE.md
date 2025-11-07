# DeepWiki CLI Usage Examples

## Quick Start

### 1. Install Dependencies

```bash
cd api
poetry install
```

### 2. Start the Backend Server

In one terminal:

```bash
cd api
poetry run python -m api.main
```

The server will start on `http://localhost:8001`.

### 3. Use the CLI

In another terminal:

#### Generate a Wiki Interactively

```bash
poetry run deepwiki generate
```

Follow the prompts:

```
Repository Selection
════════════════════════════════════════════════════════════
You can provide:
  • GitHub URL: https://github.com/owner/repo
  • GitHub shorthand: owner/repo
  • Local directory path: /path/to/repo

Enter repository: fastapi/fastapi
✓ Repository: fastapi (type: github)

Model Configuration
════════════════════════════════════════════════════════════
Available providers: google, openai, openrouter, ollama
Select provider [google]: google
Available models for google: gemini-2.0-flash-exp, gemini-1.5-flash
Select model [gemini-2.0-flash-exp]: gemini-2.0-flash-exp
✓ Using google/gemini-2.0-flash-exp

Wiki Type
════════════════════════════════════════════════════════════
  • Comprehensive: More pages with detailed sections (recommended)
  • Concise: Fewer pages with essential information

Generate comprehensive wiki? [Y/n]: y
✓ Wiki type: comprehensive

File Filters (Optional)
════════════════════════════════════════════════════════════
Configure file filters? [y/N]: n

Generating Wiki
════════════════════════════════════════════════════════════
Preparing repository analysis...
✓ Repository prepared
Fetching repository structure...
✓ Structure fetched
Determining wiki structure...
✓ Structure created: 12 pages

Generating 12 pages...

  Project Overview                         [████████████████████] 100%
  API Architecture                         [████████████████████] 100%
  Core Features                            [████████████████████] 100%
  ...

✓ Cache saved to: ~/.adalflow/wikicache/deepwiki_cache_github_fastapi_fastapi_en.json

Generation Complete!
════════════════════════════════════════════════════════════
Repository: fastapi
Pages generated: 12/12
Cache file: ~/.adalflow/wikicache/deepwiki_cache_github_fastapi_fastapi_en.json

Use 'deepwiki export' to export the wiki to Markdown or JSON.
════════════════════════════════════════════════════════════
```

#### List Cached Wikis

```bash
poetry run deepwiki list
```

Output:

```
════════════════════════════════════════════════════════════════════════════════
Cached Wikis
════════════════════════════════════════════════════════════════════════════════

1. fastapi/fastapi
   Type: github | Language: en | Wiki Type: comprehensive
   Pages: 12 | Size: 156.7 KB
   Modified: 2024-01-07 14:30:22
   Path: ~/.adalflow/wikicache/deepwiki_cache_github_fastapi_fastapi_en.json

2. local/myproject
   Type: local | Language: en | Wiki Type: concise
   Pages: 6 | Size: 45.2 KB
   Modified: 2024-01-06 09:15:10
   Path: ~/.adalflow/wikicache/deepwiki_cache_local_local_myproject_en.json

Total: 2 cached wiki(s)
════════════════════════════════════════════════════════════════════════════════
```

#### Export to Markdown

```bash
poetry run deepwiki export
```

Follow the prompts:

```
Available wikis:

  1. fastapi/fastapi (github, en)
  2. local/myproject (local, en)

Select wiki to export (enter number): 1
Export format (markdown/json) [markdown]: markdown
Output file path []: fastapi_wiki.md

✓ Wiki exported successfully to: fastapi_wiki.md
  File size: 156.45 KB
  Pages exported: 12
```

#### Export to JSON

```bash
poetry run deepwiki export
```

```
Available wikis:

  1. fastapi/fastapi (github, en)
  2. local/myproject (local, en)

Select wiki to export (enter number): 1
Export format (markdown/json) [markdown]: json
Output file path []:

✓ Wiki exported successfully to: fastapi_fastapi_wiki_20240107_143522.json
  File size: 245.12 KB
  Pages exported: 12
```

#### View Configuration

```bash
poetry run deepwiki config show
```

Output:

```
══════════════════════════════════════════════════
DeepWiki CLI Configuration
══════════════════════════════════════════════════

Config file: ~/.deepwiki/config.json

{
  "default_provider": "google",
  "default_model": "gemini-2.0-flash-exp",
  "wiki_type": "comprehensive",
  "file_filters": {
    "excluded_dirs": [],
    "excluded_files": []
  }
}

══════════════════════════════════════════════════
```

#### Update Configuration

```bash
# Set default provider
poetry run deepwiki config set default_provider openai

# Set default model
poetry run deepwiki config set default_model gpt-4-turbo

# Set wiki type preference
poetry run deepwiki config set wiki_type concise
```

## Advanced Examples

### Generate Wiki for Private Repository

```bash
# Ensure GITHUB_TOKEN is in your .env file
poetry run deepwiki generate
# Enter: https://github.com/yourorg/private-repo
# The CLI will use GITHUB_TOKEN from .env automatically
```

### Generate Wiki with File Filters

```bash
poetry run deepwiki generate
```

When prompted for file filters:

```
Configure file filters? [y/N]: y

Enter patterns (comma-separated) or leave empty:
Exclude directories: tests, docs, examples
Exclude files: test_*.py, *_test.py
Include only directories: 
Include only files: 
```

### Generate Concise Wiki for Large Repository

```bash
poetry run deepwiki generate
# Choose: concise (generates fewer pages, faster)
```

### Batch Export Multiple Wikis

```bash
# Export wiki 1
poetry run deepwiki export
# Select: 1
# Format: markdown
# Output: wiki1.md

# Export wiki 2
poetry run deepwiki export
# Select: 2
# Format: json
# Output: wiki2.json
```

## Troubleshooting

### Command Not Found

If `deepwiki` command is not found:

```bash
cd api
poetry install  # Reinstall
poetry run deepwiki --help  # Use with poetry run
```

### Backend Connection Error

Ensure the backend server is running:

```bash
# Terminal 1
cd api
poetry run python -m api.main

# Terminal 2
poetry run deepwiki generate
```

### Missing API Keys

Check your `.env` file in project root:

```
GOOGLE_API_KEY=your_key
OPENAI_API_KEY=your_key
GITHUB_TOKEN=your_token
```

## Tips

1. **Use comprehensive mode** for detailed documentation
2. **Use concise mode** for quick overviews or large repos
3. **Configure defaults** to skip repetitive prompts
4. **Export immediately** after generation to preserve results
5. **Use file filters** to focus on relevant code only

## Next Steps

- Read the full README: `api/cli/README.md`
- Check backend API docs: `api/README.md`
- Explore generated wikis in: `~/.adalflow/wikicache/`
