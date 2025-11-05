# Mermaid Diagram Validation

When wiki pages are generated, the LLM is asked to create multiple Mermaid diagrams. In practice some of those diagrams contain syntax errors, which causes rendering failures in the UI. To make the output more reliable we added an automated validation-and-repair loop that runs **during** page generation.

## During-Generation Repair Loop

1. Generate the wiki page as usual.
2. Extract every ```mermaid``` code fence from the markdown.
3. Validate each diagram using `@mermaid-js/parser.parse`.
4. If all diagrams parse successfully, the page is accepted.
5. If any diagram fails to parse, send the original markdown, the failing snippets, and the parser error messages back to the LLM with explicit “fix these diagrams” instructions.
6. Regenerate the full wiki page and validate again.
7. Repeat this process up to **three** times. After the third attempt we keep the latest markdown even if diagrams still fail, but surface the parser errors so we can address them post-generation.

This loop currently lives in `src/app/[owner]/[repo]/page.tsx`. The helper utilities are defined in `src/utils/mermaidValidation.ts`.

## Planned Post-Generation Enhancements

While the generation-time check catches most issues, we plan to add the following safeguards:

1. **Automated validation pipeline** – keep a record of failed diagrams along with parser errors so we can iterate on prompt quality or model selection.
2. **User-facing editor** – give readers an inline editor to tweak Mermaid code, see live previews, and submit fixes without regenerating an entire wiki page.
3. **Template-based diagram synthesis** – for common diagram shapes, derive the Mermaid graph from structured data instead of free-form LLM text.

These enhancements build on top of the current validation loop and will be implemented next.
