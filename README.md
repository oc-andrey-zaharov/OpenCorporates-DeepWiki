# OpenCorporates-DeepWiki

Automatically create beautiful, interactive wikis for any GitHub, GitLab, or Bitbucket repository. Analyze code structure, generate comprehensive documentation, and create visual diagrams with AI.

## Features

- **Instant Documentation**: Turn any repo into a wiki in seconds
- **Private Repository Support**: Securely access private repositories with tokens
- **Smart Analysis**: AI-powered code understanding
- **Beautiful Diagrams**: Automatic Mermaid diagrams for architecture and data flow
- **Interactive Chat**: Ask questions about your codebase with RAG-powered AI
- **DeepResearch**: Multi-turn research process for complex topics
- **Multiple Model Providers**: Google Gemini, OpenAI, OpenRouter, Azure OpenAI, and local Ollama

## Quick Start

### Using Makefile (Recommended)

```bash
# Install dependencies
make install

# Start both frontend and backend
make dev

# Or start separately
make dev/backend   # Start backend (port 8001)
make dev/frontend  # Start frontend (port 3000)
```

### Manual Installation

#### Prerequisites

- [Bun](https://bun.sh/) for frontend
- [Poetry v2](https://python-poetry.org/) for Python dependencies
- Python 3.12+

#### Step 1: Setup Environment

Create a `.env` file:

```bash
GOOGLE_API_KEY=your_google_api_key
OPENAI_API_KEY=your_openai_api_key

# Optional
OPENROUTER_API_KEY=your_openrouter_api_key
DEEPWIKI_EMBEDDER_TYPE=google  # or 'openai' (default), 'ollama'
OLLAMA_HOST=http://localhost:11434
```

#### Step 2: Install Dependencies

```bash
# Backend
cd api && poetry install && cd ..

# Frontend
bun install
```

#### Step 3: Start Servers

```bash
# Backend (in one terminal - from project root)
api/.venv/bin/python -m api.main

# Frontend (in another terminal)
bun run dev
```

Open [http://localhost:3000](http://localhost:3000) and start generating wikis!

## Usage

1. Enter a GitHub, GitLab, or Bitbucket repository URL
2. For private repos, click "+ Add access tokens" and enter your personal access token
3. Choose your preferred AI model
4. Click "Generate Wiki"
5. Use the Ask feature to chat with your codebase

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
| `DEEPWIKI_EMBEDDER_TYPE` | Embedder type: `openai`, `google`, or `ollama` | No (default: `openai`) |
| `OLLAMA_HOST` | Ollama host URL | No (default: `http://localhost:11434`) |

### Configuration Files

Located in `api/config/`:

- `generator.json` - Text generation model settings
- `embedder.json` - Embedding model and RAG settings
- `repo.json` - Repository handling rules

## Makefile Commands

```bash
make help              # Show all commands
make install           # Install all dependencies
make install/frontend  # Install frontend only
make install/backend   # Install backend only
make dev               # Start both servers
make dev/frontend      # Start frontend only
make dev/backend       # Start backend only
make dev/bun           # Start frontend with bun
make stop              # Stop all servers
make clean             # Clean build artifacts
```

## Project Structure

```
opencorporates-deepwiki/
├── api/                  # Backend FastAPI server
│   ├── main.py          # API entry point
│   ├── rag.py           # RAG implementation
│   └── config/          # Configuration files
├── src/                 # Frontend Next.js app
│   ├── app/             # Next.js pages
│   └── components/      # React components
├── Makefile            # Build and run commands
└── .env                # Environment variables
```

## API Keys

- **Google AI**: [Google AI Studio](https://makersuite.google.com/app/apikey)
- **OpenAI**: [OpenAI Platform](https://platform.openai.com/api-keys)
- **OpenRouter**: [OpenRouter](https://openrouter.ai/)
- **Azure OpenAI**: [Azure Portal](https://portal.azure.com/)

## Troubleshooting

**API Key Issues**: Check your `.env` file has valid keys without extra spaces

**Connection Problems**: Ensure both servers are running (port 3000 for frontend, 8001 for backend)

**Generation Issues**: Try a smaller repository first, ensure tokens have correct permissions

## License

MIT License - see [LICENSE](LICENSE) file for details.
