# TODO

## LLM Provider Evaluation

- [x] Check if it's feasible to use cursor-agent as an LLM provider instead of using API calls
  - **Feasibility**: ✅ Yes, it's feasible. Cursor CLI supports headless mode via `cursor-agent -p` or `--print` flags for non-interactive execution.
  - **Implementation Approach**: Would require creating a `CursorAgentClient` class extending `ModelClient` that uses subprocess to call `cursor-agent` CLI, format messages, and parse output.
  - **Considerations**:
    - Subprocess overhead vs direct API calls (higher latency)
    - Streaming support may be limited (CLI typically returns complete output)
    - Requires proper message formatting for CLI input
    - Error handling for CLI failures/timeouts
    - Benefits: Can leverage Cursor's MCP integrations and code understanding capabilities
    - Reference: [Cursor CLI Headless Docs](https://cursor.com/docs/cli/headless)
- [ ] Research better embedding models (local via LM studio)

## Code Organization

- [ ] Migrate prompts to a separate file for clarity and maintainability
- [ ] Address linting debt
- [ ] Review docs and add playbook/runbook docs
- [ ] Port over linting rules as well as best practices for make and pyproject from lineage and loader projects

## Project Improvements

- [ ] Remember the Python project (look up git) to improve the output quality of results

## Evaluation System

- [ ] Evaluate eval system to refine doc generation quality and settle on a model

## Action Plan: Backend/CLI Cleanup

1. Remove leftover frontend/Node build artifacts  
   - [x] Delete or fully rewrite `Dockerfile-ollama-local` so it no longer builds/copies `.next` assets or installs Node.  
   - [x] Remove any other references to `node`, `.next`, `server.js`, or old frontend processes from docs/scripts.

2. Fix chat streaming inconsistencies  
   - [x] Either reintroduce a real `/chat/completions/stream` FastAPI route or, preferably, remove server-mode chat wiring (`api/utils/chat.py`, README endpoint docs, tests/api) and document the new behavior.  
   - [x] Ensure README/API docs describe only the endpoints that actually exist.

3. Consolidate RAG lifecycle so embeddings are prepared once  
   - [x] Introduce a shared `WikiGenerationContext` (or similar) that prepares the retriever a single time per repo.  
   - [x] Update CLI generation and `generate_chat_completion_core()` to reuse that context instead of instantiating new `RAG` objects for every page.

4. DRY up repository scanning and file filtering  
   - [ ] Extract git discovery, `.gitignore` parsing, and file collection into a single module used by both `api/services/data_pipeline.py` and CLI helpers.  
   - [ ] Remove duplicated implementations once the shared module exists.

5. Prune unused dependencies  
   - [ ] Confirm `langid`, `jinja2`, and any other lingering requirements are truly unused; drop them from `pyproject.toml` / lockfiles if so.  
   - [ ] Add regression tests (or grep checks) to prevent reintroduction.

6. Make FastAPI server thin and accurate  
   - [ ] Split `api/server/server.py` into routers that call shared services; ensure there is (or isn’t) a wiki-generation endpoint and keep docs/tests aligned.  
   - [ ] Remove “Streaming API” wording if chat streaming is no longer served here.

7. Deduplicate streaming helpers and prompts  
   - [ ] Move prompt strings and chunk-collection logic into dedicated modules so CLI/server share the same implementations.  
   - [ ] Add unit tests for the new helpers to keep behavior stable.

8. Update architecture/docs/tests  
   - [x] Refresh `README.md`, `docs/architecture.md`, `docs/backend-cli-migration-plan.md`, etc., to match the Python-only architecture (no Next.js, no missing files).  
   - [x] Delete or rewrite tests that reference removed endpoints/features.
