# Backend and CLI Migration Plan: Standalone Python Project

## Executive Summary

This document outlines the migration plan to extract the backend and CLI components from the current monorepo into a standalone Python project, removing all dependencies on the Next.js frontend and JavaScript/TypeScript code.

**Last Updated**: November 7, 2025  
**Status**: Plan reviewed and updated with critical improvements  
**Estimated Timeline**: 10-15 days

## Current Architecture

### Components Overview

1. **Backend API Server** (`api/server.py`, `api/main.py`)
   - FastAPI application providing REST endpoints
   - Serves both CLI and frontend needs
   - Endpoints include: wiki cache management, repository structure fetching, export utilities  
     _(Chat completions now run entirely inside the CLI.)_

2. **CLI** (`api/cli/`)
   - Command-line interface for wiki generation
   - Commands: `generate`, `export`, `delete`, `list`, `config`
   - Currently depends on FastAPI server for some operations

3. **Core Logic** (shared between server and CLI)
   - `api/rag.py` - RAG implementation
   - `api/data_pipeline.py` - Repository processing and embedding
   - `api/config.py` - Configuration management
   - `api/prompts.py` - Prompt templates

4. **Frontend** (`src/`, `package.json`, `next.config.ts`)
   - Next.js application
   - React components
   - TypeScript code
   - **TO BE REMOVED**

### Current Import Structure

The CLI currently imports from `api.server`:

```python
# api/cli/commands/generate.py:24
from api.server import WikiStructureModel, WikiPage, WikiCacheData

# api/cli/commands/export.py:10
from api.server import generate_markdown_export, generate_json_export
```

**Key Observations**:

- CLI already uses `RAG` directly from `api.rag` (no server dependency)
- Model clients are imported directly (standalone-ready)
- Export functions are pure Python (easy to extract)
- Only HTTP endpoint calls require server running

## Dependencies Analysis

### CLI Dependencies on Server

The CLI currently makes HTTP requests to `http://localhost:8001` for:

1. **Wiki Structure Generation** (`generate.py:739-750`)
   - ✅ Now calls `api.core.chat.generate_chat_completion_core()` directly (no HTTP dependency)
   - Streams tokens locally for progress feedback.

2. **Page Content Generation** (`generate.py:543-554`)
   - ✅ Same as above—direct call into core chat logic with streaming.

3. **GitHub Repository Structure** (`generate.py:953-957`)
   - Endpoint: `GET /github/repo/structure`
   - Purpose: Fetch file tree and README from GitHub
   - **Action Required**: Extract GitHub API logic into a reusable function

4. **Wiki Cache Deletion** (`delete.py:80-88`)
   - Endpoint: `DELETE /api/wiki_cache`
   - Purpose: Delete cached wiki files
   - **Action Required**: Replace with direct file system operations

### Shared Code Dependencies

The CLI imports from `api.server`:

1. **Pydantic Models** (`generate.py:24`, `export.py:10`)
   - `WikiPage`, `WikiStructureModel`, `WikiCacheData`, `RepoInfo`
   - **Action Required**: Move to `api/models.py` or `api/schemas.py`

2. **Export Functions** (`export.py:10`)
   - `generate_markdown_export()`, `generate_json_export()`
   - **Action Required**: Move to `api/export.py` or `api/utils/export.py`

### Frontend Dependencies on Backend

The frontend uses Next.js API routes that proxy to Python backend:

1. **Next.js API Routes** (`src/app/api/`)
   - `/api/wiki/projects/route.ts` - Proxies to `/api/processed_projects`
   - `/api/models/config/route.ts` - Proxies to `/models/config`
   - **Action Required**: Remove entirely (not needed for CLI-only)

2. **Next.js Rewrites** (`next.config.ts:36-70`)
   - Proxies various endpoints to Python backend
   - **Action Required**: Remove entirely

3. **Direct Backend Calls** (in React components)
   - Calls to `/github/repo/structure`, `/api/wiki_cache`, etc.
   - **Action Required**: Remove entirely

### Additional Components to Address

1. **WebSocket Server** (`api/websocket_wiki.py`)
   - **Current Status**: Provides real-time wiki generation updates
   - **Decision Required**: Keep as optional service or remove?
   - **Recommendation**: Keep as optional (like FastAPI server), document as advanced feature

2. **Model Client Dependencies**
   - All model clients are already standalone-ready:
     - `api/openai_client.py`
     - `api/bedrock_client.py`
     - `api/openrouter_client.py`
     - `api/google_embedder_client.py`
   - **Action Required**: None - these remain as core dependencies

3. **Cache Management**
   - CLI has its own cache logic via `api/cli/utils.py:get_cache_path()`
   - Server has cache management endpoints
   - **Action Required**: Ensure consistency between CLI and server cache handling

## Migration Strategy

### Phase 0: Pre-Migration Audit (1 day)

**Goal**: Understand exact dependencies and current state before making changes.

**Tasks**:

1. **Audit All CLI Imports**
   - Map all imports in CLI commands from `api.server`
   - Identify which are models vs. functions vs. endpoints
   - Document current working behavior

2. **Test Current Functionality**
   - Run full wiki generation workflow
   - Test export and delete commands
   - Document expected behavior for regression testing

3. **Review Cache Handling**
   - Document cache structure in CLI vs. server
   - Ensure both use consistent paths and formats
   - Identify any discrepancies

### Phase 1: Extract Shared Models and Utilities (2-3 days)

**Goal**: Create common modules for data models and utility functions used by both CLI and server. These are "quick wins" with no behavior changes.

**Tasks**:

1. **Create `api/models.py`**
   - Move Pydantic models from `api/server.py`:
     - `WikiPage`
     - `WikiStructureModel`
     - `WikiSection`
     - `WikiCacheData`
     - `WikiCacheRequest`
     - `RepoInfo`
     - `ProcessedProjectEntry`
   - Update imports in `server.py` and CLI commands
   - **Validation**: Run existing tests to ensure no breakage

2. **Create `api/utils/export.py`**
   - Move export functions from `api/server.py`:
     - `generate_markdown_export()`
     - `generate_json_export()`
   - These are pure Python functions (no FastAPI dependencies)
   - Update imports in `export.py` command
   - **Validation**: Test export command

3. **Standardize Cache Management**
   - Ensure `api/cli/utils.py:get_cache_path()` matches server expectations
   - Document cache format and location
   - Add cache validation utilities if needed

### Phase 2: Implement Core Business Logic Layer (3-4 days)

**Goal**: Create a core layer that both standalone and server modes can use.

**Tasks**:

1. **Create `api/core/` Module Structure**

   ```
   api/core/
   ├── __init__.py
   ├── chat.py          # Chat completion logic (extracted from simple_chat.py)
   ├── github.py        # GitHub API logic
   └── wiki_generator.py # Wiki generation orchestration
   ```

2. **Extract Chat Completion Logic to `api/core/chat.py`**
   - Extract core logic from `api/simple_chat.py:chat_completions_stream()`
   - **Important**: Preserve streaming behavior (not sync-only)
   - Create generator function that yields chunks
   - Support all model providers (OpenAI, Google, Bedrock, etc.)
   - **Validation**: Test with all supported providers

3. **Extract GitHub API Logic to `api/core/github.py`**
   - Extract from `api/server.py:get_github_repo_structure()`
   - Make synchronous (remove async/await)
   - Support GitHub token from: CLI arg > config > env var
   - Add token validation
   - **Validation**: Test with public and private repos

4. **Keep Server as Thin HTTP Wrapper**
   - Update `api/server.py` to import and call core functions
   - No business logic in server endpoints
   - Server just handles HTTP concerns (routing, streaming response, error codes)

### Phase 3: Implement Hybrid Mode (Standalone + Server) (3-4 days)

**Goal**: CLI runs standalone by default, but can optionally connect to server when configured.

**Tasks**:

1. **Add Server Configuration to `api/cli/config.py`**
   - Update `DEFAULT_CONFIG` to add:

     ```python
     DEFAULT_CONFIG = {
         "default_provider": "google",
         "default_model": "gemini-2.0-flash-exp",
         "wiki_type": "comprehensive",
         "file_filters": {"excluded_dirs": [], "excluded_files": []},
         # New server mode settings
         "use_server": False,  # Default to standalone
         "server_url": "http://localhost:8001",
         "server_timeout": 300,
         "auto_fallback": True,  # Fallback to standalone if server unavailable
     }
     ```

   - Add configuration migration function for existing users

2. **Create `api/utils/mode.py`**
   - Mode detection and routing:

     ```python
     def is_server_mode() -> bool
     def get_server_url() -> str
     def check_server_health() -> bool
     def should_fallback() -> bool
     ```

   - Add retry logic with exponential backoff
   - Clear error messages with troubleshooting steps

3. **Expose a Lightweight Wrapper in `api/utils/chat.py`**

   ```python
   def generate_chat_completion_streaming(...):
       """Thin helper that simply yields from generate_chat_completion_core."""
   ```

   This keeps CLI code clean while ensuring all streaming flows are serviced by the core module instead of an HTTP hop.

4. **Create Unified GitHub Function in `api/utils/github.py`**

   ```python
   def get_github_repo_structure(
       owner: str,
       repo: str,
       **kwargs
   ) -> Dict[str, str]:
       """Routes to standalone or server based on config."""
       if is_server_mode():
           return _get_via_server(...)
       else:
           return _get_standalone(...)
   ```

5. **Update CLI Commands**
   - `generate.py`: Use unified functions
   - `delete.py`: Add config-aware cache deletion with fallback
   - All commands: Handle server unavailable gracefully

6. **Add Error Handling and Fallback Logic**
   - If server mode enabled but server down:
     - Check `auto_fallback` config
     - If true: warn and use standalone
     - If false: error with clear message
   - Add health check before operations
   - Provide helpful troubleshooting in errors

7. **Update `api/cli/commands/config_cmd.py`**
   - Add server configuration commands:

     ```bash
     deepwiki config set use_server true
     deepwiki config set server_url http://localhost:8001
     deepwiki config set server_timeout 300
     deepwiki config set auto_fallback true
     ```

   - Show current mode in `deepwiki config show`

### Phase 4: Remove Frontend Dependencies (1 day)

**Goal**: Remove all JavaScript/TypeScript code and dependencies.

**Tasks**:

1. **Remove Frontend Files**
   - Delete `src/` directory
   - Delete `package.json`, `package-lock.json`, `bun.lock`
   - Delete `next.config.ts`, `tsconfig.json`
   - Delete `tailwind.config.js`, `postcss.config.mjs`
   - Delete `eslint.config.mjs`
   - Delete `next-env.d.ts`
   - Delete `public/` directory (if frontend-specific)

2. **Handle WebSocket Server**
   - **Decision**: Keep `api/websocket_wiki.py` as optional service
   - Add documentation:
     - How to start websocket server
     - Use cases (real-time updates for team dashboards)
     - Make it clear it's optional, not required for CLI
   - Consider moving to `api/services/websocket_server.py` for clarity

3. **Update Project Structure**
   - Remove frontend-related directories from `.gitignore` if present
   - Update `README.md` to remove frontend setup instructions
   - Update `Makefile` to remove frontend-related targets
   - Keep Make targets for backend/CLI only

4. **Update Docker Configuration**
   - Update `Dockerfile` to remove Node.js/Bun installation
   - Update `docker-compose.yml` to remove frontend service
   - Keep Python backend service (FastAPI + optional WebSocket)
   - Document how to run services in containers

5. **Update Documentation**
   - Remove frontend architecture documentation
   - Update setup instructions to be CLI-only
   - Document optional services:
     - FastAPI server (for shared cache/resources)
     - WebSocket server (for real-time updates)
   - Add architecture diagram showing CLI, optional server, optional websocket

### Phase 5: Clean Up and Optimize (1-2 days)

**Goal**: Final cleanup, optimization, and comprehensive testing for standalone Python project.

**Tasks**:

1. **Update Dependencies**
   - Review `pyproject.toml` and remove any frontend-related dependencies
   - Ensure all Python dependencies are properly specified
   - Add any new dependencies needed for extracted functions
   - Verify all model client dependencies are included
   - Run dependency audit: `poetry check`

2. **Update Configuration**
   - Remove frontend-related environment variables from `.env.example`
   - Update configuration files to remove frontend-specific settings
   - Add new environment variables for standalone mode if needed
   - Document all required environment variables

3. **Comprehensive Testing**
   - **Unit Tests**:
     - Test all extracted functions independently
     - Test model serialization/deserialization
     - Test configuration management
   - **Integration Tests**:
     - Test full wiki generation in standalone mode
     - Test full wiki generation in server mode
     - Test auto-fallback when server unavailable
     - Test export functionality
     - Test cache management
     - Test all model providers
   - **Regression Tests**:
     - Compare output quality: old vs. new
     - Verify CLI functionality matches previous behavior
     - Test with various repository types (GitHub public/private, local)

4. **Update CI/CD**
   - Remove frontend build steps from workflows
   - Update GitHub Actions to only test Python code
   - Remove Node.js/Bun setup from CI
   - Add matrix testing for different Python versions
   - Add tests for both standalone and server modes
   - Add performance benchmarks

5. **Performance Optimization**
   - Profile standalone mode vs. server mode
   - Identify bottlenecks in RAG preparation
   - Optimize embedding generation if needed
   - Add caching for frequently accessed data
   - Document performance characteristics

6. **Add Monitoring and Logging**
   - Ensure consistent logging between modes
   - Add performance metrics logging
   - Add error tracking
   - Document log locations and formats

## File Changes Summary

### Files to Create

**Phase 1**:

- `api/models.py` - Pydantic models (extracted from server.py)
- `api/utils/export.py` - Export utilities (extracted from server.py)

**Phase 2**:

- `api/core/__init__.py` - Core module initialization
- `api/core/chat.py` - Chat completion logic (extracted from simple_chat.py, preserves streaming)
- `api/core/github.py` - GitHub API logic (extracted from server.py)
- `api/core/wiki_generator.py` - Wiki generation orchestration (optional)

**Phase 3**:

- `api/utils/mode.py` - Mode detection and server health checking
- `api/utils/chat.py` - Thin chat helper that simply proxies to the core generator
- `api/utils/github.py` - Unified GitHub wrapper (routes to core or server)

### Files to Modify

**Phase 1**:

- `api/server.py` - Update imports to use `api.models` and `api.utils.export`
- `api/cli/commands/generate.py` - Update imports to use `api.models`
- `api/cli/commands/export.py` - Update imports to use `api.models` and `api.utils.export`
- `api/cli/commands/delete.py` - Update imports to use `api.models`

**Phase 2**:

- `api/server.py` - Refactor to use core functions, become thin HTTP wrapper
- `api/simple_chat.py` - May be deprecated in favor of core functions

**Phase 3**:

- `api/cli/config.py` - Add server mode configuration defaults
- `api/cli/commands/generate.py` - Use shared helpers for chat + GitHub access
- `api/cli/commands/delete.py` - Add config-aware cache deletion with fallback
- `api/cli/commands/config_cmd.py` - Add server configuration commands
- All CLI commands - Add error handling for server unavailability

**Phase 4**:

- `README.md` - Update for CLI-only usage, document server mode
- `Makefile` - Remove frontend targets
- `.env.example` - Remove frontend variables
- `Dockerfile` - Remove Node.js/Bun installation
- `docker-compose.yml` - Update to remove frontend service
- `.gitignore` - Remove frontend-related entries

**Phase 5**:

- `pyproject.toml` - Remove any frontend dependencies
- `api/config.py` - Remove frontend-related configuration
- Test files - Add comprehensive tests for both modes

### Files to Delete

- `src/` - Entire frontend directory
- `package.json`, `package-lock.json`, `bun.lock`
- `next.config.ts`, `tsconfig.json`
- `tailwind.config.js`, `postcss.config.mjs`
- `eslint.config.mjs`
- `next-env.d.ts`
- `Dockerfile` (if frontend-specific) or update it
- `docker-compose.yml` (update to remove frontend service)

## Implementation Details

### Chat Completion Extraction (Hybrid Mode with Streaming)

The `chat_completions_stream()` function in `api/simple_chat.py` needs to be adapted for both standalone and server modes while **preserving streaming behavior**:

```python
# api/core/chat.py (new file - core implementation)
from typing import Generator, Dict, List, Optional
from api.rag import RAG

def generate_chat_completion_core(
    repo_url: str,
    messages: List[Dict[str, str]],
    provider: str,
    model: str,
    repo_type: str = "github",
    token: Optional[str] = None,
    excluded_dirs: Optional[List[str]] = None,
    excluded_files: Optional[List[str]] = None,
    included_dirs: Optional[List[str]] = None,
    included_files: Optional[List[str]] = None,
) -> Generator[str, None, None]:
    """
    Core chat completion logic with streaming.
    Extracted from api/simple_chat.py.
    Yields chunks as they arrive.
    """
    # Create RAG instance
    rag = RAG(provider=provider, model=model)
    rag.prepare_retriever(
        repo_url, repo_type, token,
        excluded_dirs, excluded_files,
        included_dirs, included_files
    )
    
    # Build prompt and get model client
    # Extract logic from simple_chat.py
    # Yield chunks from model response
    for chunk in model_client.stream_completion(messages):
        yield chunk
```

```python
# api/utils/chat.py (thin wrapper)
from typing import Dict, Generator, List, Optional
from api.core.chat import generate_chat_completion_core

def generate_chat_completion_streaming(
    repo_url: str,
    messages: List[Dict[str, str]],
    provider: str,
    model: str,
    **kwargs,
) -> Generator[str, None, None]:
    """Simple helper so CLI code stays tidy."""
    yield from generate_chat_completion_core(
        repo_url=repo_url,
        messages=messages,
        provider=provider,
        model=model,
        **kwargs,
    )
```

### GitHub Structure Extraction (Hybrid Mode)

Extract the GitHub API logic with support for both modes:

```python
# api/utils/github.py (new file)
from api.cli.config import load_config
from api.utils.mode import is_server_mode, get_server_url

def get_github_repo_structure(
    owner: str,
    repo: str,
    repo_url: Optional[str] = None,
    access_token: Optional[str] = None,
) -> Dict[str, str]:
    """
    Unified function to get GitHub repository structure.
    Routes to standalone or server mode based on config.
    Returns dict with 'file_tree' and 'readme' keys.
    """
    config = load_config()
    
    if config.get("use_server", False):
        return get_github_repo_structure_via_server(
            owner, repo, repo_url, access_token
        )
    else:
        return get_github_repo_structure_standalone(
            owner, repo, repo_url, access_token
        )


def get_github_repo_structure_standalone(...) -> Dict[str, str]:
    """
    Standalone mode: direct GitHub API call.
    No server required.
    """
    # Extract logic from server.py:get_github_repo_structure()
    # Make it synchronous and reusable
    ...


def get_github_repo_structure_via_server(...) -> Dict[str, str]:
    """
    Server mode: HTTP request to FastAPI server.
    Requires server to be running.
    """
    import requests
    config = load_config()
    server_url = config.get("server_url", "http://localhost:8001")
    
    params = {"owner": owner, "repo": repo}
    if repo_url:
        params["repo_url"] = repo_url
    
    response = requests.get(
        f"{server_url}/github/repo/structure",
        params=params,
        timeout=60,
    )
    
    if not response.ok:
        raise Exception(f"Server error: {response.status_code}")
    
    return response.json()
```

### Cache Management (Hybrid Mode)

Use config-aware cache deletion:

```python
# api/cli/commands/delete.py
from api.cli.config import load_config
from api.utils.mode import is_server_mode

def delete(yes: bool):
    # ... existing wiki selection code ...
    
    config = load_config()
    
    if config.get("use_server", False):
        # Server mode: use HTTP DELETE
        import requests
        server_url = config.get("server_url", "http://localhost:8001")
        
        params = {
            "owner": selected_wiki["owner"],
            "repo": selected_wiki["repo"],
            "repo_type": selected_wiki["repo_type"],
            "language": selected_wiki["language"],
        }
        
        try:
            response = requests.delete(
                f"{server_url}/api/wiki_cache",
                params=params,
                timeout=30,
            )
            
            if response.status_code == 200:
                click.echo(f"\n✓ {response.json().get('message', 'Wiki deleted successfully')}")
            elif response.status_code == 404:
                click.echo("\n✗ Wiki cache not found.", err=True)
            else:
                click.echo(f"\n✗ Error: {response.status_code}", err=True)
        except requests.exceptions.ConnectionError:
            click.echo(
                "\n✗ Could not connect to server. "
                "Falling back to standalone mode or check server is running.",
                err=True
            )
            # Fallback to standalone mode
            _delete_standalone(selected_wiki)
    else:
        # Standalone mode: direct file operations
        _delete_standalone(selected_wiki)


def _delete_standalone(selected_wiki):
    """Standalone cache deletion."""
    cache_path = get_cache_path()
    cache_file = cache_path / selected_wiki["path"].name
    
    if cache_file.exists():
        cache_file.unlink()
        click.echo(f"\n✓ Wiki deleted successfully")
    else:
        click.echo("\n✗ Wiki cache not found.", err=True)
```

## Testing Strategy

1. **Unit Tests**
   - Test extracted functions independently
   - Test CLI commands without server running
   - Test model serialization/deserialization

2. **Integration Tests**
   - Test full wiki generation flow via CLI
   - Test export functionality
   - Test cache management

3. **Regression Tests**
   - Ensure CLI functionality matches current behavior
   - Verify wiki output quality remains the same

## Migration Risks and Mitigation

### Risk 1: Breaking Changes During Extraction

- **Risk**: Extracting functions may introduce bugs or break existing functionality
- **Mitigation**:
  - Phase 0: Comprehensive testing before changes
  - Create regression test suite
  - Gradual migration with validation at each step
  - Keep server as fallback during transition

### Risk 2: Code Duplication Between Modes

- **Risk**: Server and CLI may duplicate business logic
- **Mitigation**:
  - Create `api/core/` layer for shared business logic
  - Both modes use same core functions
  - Server is thin HTTP wrapper around core
  - Regular code reviews to catch duplication

### Risk 3: Streaming Behavior Loss

- **Risk**: Converting streaming to synchronous may lose progress feedback
- **Mitigation**:
  - Preserve streaming behavior in standalone mode
  - Use generator functions that yield chunks
  - Maintain same user experience across modes

### Risk 4: Server Unavailability Handling

- **Risk**: Poor error handling when server mode enabled but server down
- **Mitigation**:
  - Implement `auto_fallback` configuration option
  - Health check before operations
  - Clear error messages with troubleshooting steps
  - Retry logic with exponential backoff

### Risk 5: Configuration Migration Issues

- **Risk**: Existing users may have config conflicts after migration
- **Mitigation**:
  - Add configuration migration function
  - Default new options to maintain current behavior
  - Document breaking changes clearly
  - Provide `deepwiki config migrate` command

### Risk 6: Cache Inconsistencies

- **Risk**: CLI and server may use different cache structures
- **Mitigation**:
  - Audit cache handling in Phase 0
  - Standardize cache format and location
  - Add cache validation utilities
  - Document cache structure

### Risk 7: GitHub Token Handling

- **Risk**: Token precedence may cause authentication failures
- **Mitigation**:
  - Clear precedence: CLI arg > config > env var
  - Add token validation before API calls
  - Provide helpful errors for auth failures
  - Document token configuration

### Risk 8: Missing Test Coverage

- **Risk**: Not all edge cases may be covered in testing
- **Mitigation**:
  - Add comprehensive integration tests
  - Test all model providers
  - Test all repository types (public/private/local)
  - Test both modes and fallback scenarios
  - Add performance benchmarks

## Timeline Estimate

- **Phase 0**: 1 day (pre-migration audit)
- **Phase 1**: 2-3 days (extract models and utilities - quick wins)
- **Phase 2**: 3-4 days (implement core business logic layer)
- **Phase 3**: 3-4 days (implement hybrid mode with error handling)
- **Phase 4**: 1 day (remove frontend)
- **Phase 5**: 1-2 days (cleanup, optimization, comprehensive testing)

**Total**: ~10-15 days of focused development

### Revised Phase Priorities

**Week 1** (Days 1-5):

- Phase 0: Audit and document current state
- Phase 1: Extract models and utilities (quick wins)
- Start Phase 2: Begin core layer implementation

**Week 2** (Days 6-10):

- Complete Phase 2: Finish core layer
- Phase 3: Implement hybrid mode with full error handling
- Start Phase 4: Begin frontend removal

**Week 3** (Days 11-15):

- Complete Phase 4: Finish frontend removal
- Phase 5: Testing, optimization, documentation
- Buffer time for unexpected issues

## Post-Migration Benefits

1. **Simplified Architecture**: Pure Python project, easier to understand and maintain
2. **Reduced Dependencies**: No Node.js/Bun/Next.js required
3. **Faster Setup**: Single language stack, simpler installation
4. **Flexible CLI Experience**:
   - **Standalone mode (default)**: No server needed, works out of the box
   - **Server mode (optional)**: Connect to FastAPI server for shared resources/caching
5. **Smaller Footprint**: Reduced disk space and memory usage (no frontend)
6. **Easier Deployment**: Single Python package to deploy
7. **Best of Both Worlds**:
   - Standalone for CI/CD and simple use cases
   - Server mode for teams needing shared cache and resources
8. **Clear Separation**: CLI and server can evolve independently while sharing core logic

## Configuration-Based Server Mode

The FastAPI server is kept as a core component, but CLI defaults to standalone mode:

### Default Behavior (Standalone Mode)

```bash
# CLI works immediately, no server needed
deepwiki generate
```

### Enable Server Mode

```bash
# Configure CLI to use server
deepwiki config set use_server true
deepwiki config set server_url http://localhost:8001

# Now CLI will use server endpoints
deepwiki generate
```

### Configuration Options

The CLI configuration (`~/.deepwiki/config.json`) supports:

```json
{
  "use_server": false,              // Enable server mode (default: false)
  "server_url": "http://localhost:8001",  // Server URL
  "server_timeout": 300,            // Request timeout in seconds
  "default_provider": "google",
  "default_model": "gemini-2.0-flash-exp",
  "wiki_type": "comprehensive"
}
```

### Use Cases

**Standalone Mode (Default)**:

- ✅ CI/CD pipelines (GitHub Actions, etc.)
- ✅ Local development
- ✅ One-off wiki generation
- ✅ No server management needed

**Server Mode (Optional)**:

- ✅ Teams sharing embedding cache
- ✅ Centralized wiki generation service
- ✅ Multiple users accessing same repositories
- ✅ Faster subsequent runs (cached embeddings)

## Success Criteria

The migration will be considered successful when:

### Functional Requirements

- ✅ CLI works in standalone mode without server (default behavior)
- ✅ CLI works in server mode when configured
- ✅ Auto-fallback works when server unavailable
- ✅ All existing CLI commands work (generate, export, delete, list, config)
- ✅ Wiki generation produces same quality output as before
- ✅ All model providers work (OpenAI, Google, Bedrock, OpenRouter, Ollama)
- ✅ All repository types work (GitHub public/private, local)

### Technical Requirements

- ✅ No frontend dependencies in `pyproject.toml`
- ✅ No JavaScript/TypeScript files remaining
- ✅ Clean separation: core logic, utilities, CLI, server
- ✅ Streaming behavior preserved in both modes
- ✅ Comprehensive error handling with clear messages
- ✅ Configuration migration works for existing users
- ✅ Cache management consistent between modes

### Testing Requirements

- ✅ All existing tests pass
- ✅ New tests added for extracted functions
- ✅ Integration tests for standalone mode
- ✅ Integration tests for server mode
- ✅ Integration tests for fallback scenarios
- ✅ Performance benchmarks show no regression

### Documentation Requirements

- ✅ README updated with CLI-only setup
- ✅ Server mode documented as optional
- ✅ Migration guide for existing users
- ✅ Configuration options documented
- ✅ Troubleshooting guide created
- ✅ Architecture diagram updated

## Implementation Best Practices

### During Development

1. **Commit Frequently**
   - Small, atomic commits for each change
   - Use conventional commit format (as per user rules)
   - Test after each commit

2. **Test Early and Often**
   - Run tests after each change
   - Add tests before refactoring
   - Keep regression test suite updated

3. **Document as You Go**
   - Update docstrings for all new functions
   - Add inline comments for complex logic
   - Update README incrementally

4. **Code Review Checkpoints**
   - Review after each phase completion
   - Check for code duplication
   - Verify error handling coverage

### Quality Checks

1. **Before Each Commit**

   ```bash
   # Run linters
   poetry run ruff check api/
   poetry run mypy api/
   
   # Run tests
   poetry run pytest tests/
   
   # Check imports
   poetry run isort --check api/
   ```

2. **Before Each Phase Completion**
   - Full test suite passes
   - No linter warnings
   - Documentation updated
   - Changelog updated

3. **Before Final Release**
   - All success criteria met
   - Performance benchmarks acceptable
   - User acceptance testing complete
   - Migration guide tested by external user

## Conclusion

This migration will transform the project from a full-stack application into a focused Python CLI tool with a hybrid architecture:

- **Default**: CLI runs in standalone mode - no server required, works immediately
- **Optional**: CLI can connect to FastAPI server via configuration for shared resources
- **Flexible**: Users choose the mode that fits their needs (CI/CD = standalone, teams = server mode)
- **No Frontend**: All JavaScript/TypeScript code removed, pure Python project

The FastAPI server remains a core component, providing HTTP API access when needed, but the CLI no longer requires it to function. This gives users the best of both worlds: simplicity for basic use cases and power for advanced scenarios.

## Plan Review Summary

This plan has been reviewed and updated with the following critical improvements:

### Structural Changes

1. **Added Phase 0**: Pre-migration audit to understand exact dependencies
2. **Reorganized Phases**: Separated Phase 2 (core layer) and Phase 3 (hybrid mode) to eliminate overlap
3. **Updated Timeline**: Increased from 8-12 days to 10-15 days to account for additional work
4. **Added Week-by-Week Breakdown**: Clearer planning with weekly milestones

### Technical Improvements

5. **Preserved Streaming**: Clarified that streaming behavior must be maintained (not converted to sync)
6. **Added Error Handling Strategy**: Comprehensive fallback logic with `auto_fallback` config option
7. **Clarified Import Structure**: Documented current imports and dependencies
8. **Added Cache Standardization**: Ensure consistency between CLI and server cache handling
9. **GitHub Token Precedence**: Clear precedence order (CLI arg > config > env var)
10. **WebSocket Server Decision**: Keep as optional service, document clearly

### Risk Management

11. **Expanded Risk Assessment**: From 4 to 8 identified risks with detailed mitigations
12. **Added Configuration Migration**: Handle existing users with migration function
13. **Added Health Checks**: Server availability checking before operations
14. **Added Retry Logic**: Exponential backoff for transient failures

### Quality Assurance

15. **Added Success Criteria**: Clear, measurable criteria for completion
16. **Added Best Practices Section**: Development guidelines and quality checks
17. **Comprehensive Testing Strategy**: Unit, integration, and regression tests for both modes
18. **Performance Benchmarking**: Ensure no performance regression

### Documentation

19. **Added Implementation Examples**: Concrete code examples for streaming hybrid mode
20. **Added Architecture Decisions**: Document WebSocket and optional services
21. **Added Migration Guide Requirement**: Help users transition smoothly

### Key Realizations

- **CLI already uses RAG directly**: No extraction needed for data pipeline
- **Export functions are pure Python**: Easy to extract (quick win)
- **Streaming is essential**: Users need progress feedback during generation
- **Configuration is critical**: Default standalone, optional server mode

This updated plan provides a more realistic, comprehensive, and actionable roadmap for the migration while maintaining the core goal of creating a standalone Python CLI with optional server mode.
