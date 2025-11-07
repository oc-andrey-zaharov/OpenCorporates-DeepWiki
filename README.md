# OpenCorporates-DeepWiki

Automatically create beautiful, interactive wikis for any GitHub repository. Analyze code structure, generate comprehensive documentation, and create visual diagrams with AI.

## Features

- **Instant Documentation**: Turn any repo into a wiki in seconds
- **Private Repository Support**: Securely access private repositories with tokens
- **Smart Analysis**: AI-powered code understanding
- **Beautiful Diagrams**: Automatic Mermaid diagrams for architecture and data flow
- **DeepResearch**: Multi-turn research process for complex topics
- **Multiple Model Providers**: Google Gemini, OpenAI, OpenRouter, Azure OpenAI, and local Ollama
- **Standalone CLI**: Works out of the box without any server required
- **Optional Server Mode**: Connect to FastAPI server for shared resources and caching

## Quick Start

### Using Makefile (Recommended)

```bash
# Install dependencies
make install

# Start backend server (optional, for server mode)
make dev

# Or use CLI directly (standalone mode - default)
make cli -- wiki generate
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

- `deepwiki wiki generate` - Generate a wiki for a repository
- `deepwiki wiki export` - Export a cached wiki to markdown or JSON
- `deepwiki wiki delete` - Delete a cached wiki
- `deepwiki wiki list` - List all cached wikis
- `deepwiki config` - Manage configuration settings

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

#### List Cached Wikis

Display all cached wikis:

```bash
deepwiki wiki list
```

Shows repository name, type, language, wiki type, number of pages, file size, last modified date, and cache file path.

#### Export Wiki

Export a cached wiki to Markdown or JSON:

```bash
deepwiki wiki export
```

You'll be prompted to select a wiki from the list, choose format (markdown or json), and specify output path (optional).

#### Delete Wiki

Delete a cached wiki from the cache:

```bash
deepwiki wiki delete
```

You'll be prompted to select a wiki and confirm deletion (use `--yes` flag to skip confirmation).

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

### Standalone Mode (Default)

The CLI works in standalone mode by default - no server required:

```bash
deepwiki wiki generate
```

### Server Mode (Optional)

To use server mode for shared resources and caching:

1. Start the FastAPI server:
   ```bash
   make dev
   # or
   poetry run python -m api.server.main
   ```

2. Configure CLI to use server:
   ```bash
   deepwiki config set use_server true
   deepwiki config set server_url http://localhost:8001
   ```

3. Now CLI will use server endpoints:
   ```bash
   deepwiki wiki generate
   ```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_API_KEY` | Google Gemini API key | For Google models |
| `OPENAI_API_KEY` | OpenAI API key | For OpenAI models |
| `OPENROUTER_API_KEY` | OpenRouter API key | For OpenRouter models |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key | For Azure models |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | For Azure models |
| `AZURE_OPENAI_VERSION` | Azure OpenAI version | For Azure models |
| `GITHUB_TOKEN` | GitHub Personal Access Token for private repositories | For private repos |
| `DEEPWIKI_EMBEDDER_TYPE` | Embedder type: `openai`, `google`, or `ollama` | No (default: `openai`) |
| `OLLAMA_HOST` | Ollama host URL | No (default: `http://localhost:11434`) |

### Configuration Files

Located in `api/config/`:

- `generator.json` - Text generation model settings
- `embedder.json` - Embedding model and RAG settings
- `repo.json` - Repository handling rules

### CLI Configuration

The CLI stores configuration in `~/.deepwiki/config.json`. You can manage it with:

```bash
deepwiki config show          # Show current configuration
deepwiki config set key value  # Set a configuration value
```

Server mode settings:
- `use_server` - Enable server mode (default: `false`)
- `server_url` - Server URL (default: `http://localhost:8001`)
- `server_timeout` - Request timeout in seconds (default: `300`)
- `auto_fallback` - Fallback to standalone if server unavailable (default: `true`)

## Makefile Commands

```bash
make help              # Show all commands
make install           # Install backend dependencies
make install/backend   # Install backend only
make dev               # Start backend server (optional)
make dev/backend       # Start backend server only
make stop              # Stop backend server
make clean             # Clean build artifacts
make cli               # Run CLI (pass arguments after '--')
```

## Optional Services

### FastAPI Server

The FastAPI server provides HTTP API access and shared caching. It's optional - the CLI works standalone by default.

**Start the server:**
```bash
make dev
# or
poetry run python -m api.server.main
```

**Use cases:**
- Teams sharing embedding cache
- Centralized wiki generation service
- Multiple users accessing same repositories
- Faster subsequent runs (cached embeddings)

### WebSocket Server

The WebSocket server (`api/websocket_wiki.py`) provides real-time wiki generation updates. It's an optional service for advanced use cases.

**Use cases:**
- Real-time progress updates for team dashboards
- WebSocket-based wiki generation monitoring
- Integration with external monitoring systems

See `api/server/websocket_wiki.py` for implementation details.

## Project Structure

```
opencorporates-deepwiki/
├── api/                  # Backend and CLI
│   ├── clients/         # Model client implementations (OpenAI, Bedrock, etc.)
│   ├── cli/             # CLI commands and entry point
│   ├── core/            # Core business logic (chat, github)
│   ├── server/          # Server-related code (FastAPI, WebSocket)
│   ├── services/        # High-level services (RAG, data pipeline)
│   ├── utils/           # Utility functions
│   ├── tools/           # Tools (embedder)
│   ├── config/          # Configuration files (JSON)
│   ├── config.py        # Configuration management
│   ├── models.py        # Pydantic models
│   ├── prompts.py       # Prompt templates
│   └── logging_config.py # Logging setup
├── docs/                # Documentation
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
- **Azure OpenAI**: [Azure Portal](https://portal.azure.com/)

## Troubleshooting

**API Key Issues**: Check your `.env` file has valid keys without extra spaces

**Connection Problems**: Ensure server is running if using server mode (port 8001)

**Generation Issues**: Try a smaller repository first, ensure tokens have correct permissions

**Server Unavailable**: If server mode is enabled but server is down, CLI will automatically fallback to standalone mode (if `auto_fallback` is `true`)

## Logging

Logs are written to `api/logs/application.log` by default. You can configure logging via environment variables:

- `LOG_LEVEL` - Log level (default: `INFO`)
- `LOG_FILE_PATH` - Path to log file (default: `api/logs/application.log`)

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

#### API Tests Only
```bash
poetry run pytest tests/api -v
```

### Test Structure

```
tests/
├── unit/                 # Unit tests - test individual components in isolation
├── integration/          # Integration tests - test component interactions
└── api/                  # API tests - test HTTP endpoints
```

### Test Requirements

For API tests, ensure the FastAPI server is running:

```bash
poetry run python -m api.server.main
```

Some tests require API keys in your `.env` file:
- `GOOGLE_API_KEY` - Required for Google AI embedder tests
- `OPENAI_API_KEY` - Required for some integration tests
- `DEEPWIKI_EMBEDDER_TYPE` - Set to 'google' for Google embedder tests

## API Endpoints

### GET /

Returns basic API information and available endpoints.

### POST /chat/completions/stream

Streams an AI-generated response about a GitHub repository.

**Request Body:**

```json
{
  "repo_url": "https://github.com/username/repo",
  "messages": [
    {
      "role": "user",
      "content": "What does this repository do?"
    }
  ],
  "filePath": "optional/path/to/file.py"
}
```

**Response:**
A streaming response with the generated text.

## License

MIT License - see [LICENSE](LICENSE) file for details.
