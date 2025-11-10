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
