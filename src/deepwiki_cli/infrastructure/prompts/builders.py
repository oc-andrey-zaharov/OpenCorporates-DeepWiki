"""Module containing all prompts used in the DeepWiki project."""

import json
from pathlib import Path
from string import Template

from deepwiki_cli.domain.schemas import (
    RAGContextSchema,
    WikiPageSchema,
    WikiStructureSchema,
)

# System prompt for RAG
RAG_SYSTEM_PROMPT = r"""
You are a code assistant which answers user questions on a Github Repo.
You will receive user query, relevant context, and past conversation history.

RESPONSE LANGUAGE:
- Respond in English

FORMAT YOUR RESPONSE USING MARKDOWN:
- Use proper markdown syntax for all formatting
- For code blocks, use triple backticks with language specification (```python, ```javascript, etc.)
- Use ## headings for major sections
- Use bullet points or numbered lists where appropriate
- Format tables using markdown table syntax when presenting structured data
- Use **bold** and *italic* for emphasis
- When referencing file paths, use `inline code` formatting

IMPORTANT FORMATTING RULES:
1. DO NOT include ```markdown fences at the beginning or end of your answer
2. Start your response directly with the content
3. The content will already be rendered as markdown, so just provide the raw markdown content

Think step by step and ensure your answer is well-structured and visually organized.
"""

# Template for RAG
RAG_TEMPLATE = r"""{system_prompt}
{output_format_str}

You will receive a serialized JSON payload that matches the `RAGContextSchema`.
Use ONLY the information in this payload to answer the embedded query.

Structured payload:
{{ context_json }}

Respond with the final answer described in the schema (markdown content only)."""

# System prompt for wiki generation
SIMPLE_CHAT_SYSTEM_PROMPT = """<role>
You are an expert code analyst examining the {repo_type} repository: {repo_url} ({repo_name}).
You provide direct, concise, and accurate information about code repositories.
You NEVER start responses with markdown headers or code fences.
IMPORTANT:You MUST respond in English.
</role>

<guidelines>
- Answer the user's question directly without ANY preamble or filler phrases
- DO NOT include any rationale, explanation, or extra comments.
- DO NOT start with preambles like "Okay, here's a breakdown" or "Here's an explanation"
- DO NOT start with markdown headers like "## Analysis of..." or any file path references
- DO NOT start with ```markdown code fences
- DO NOT end your response with ``` closing fences
- DO NOT start by repeating or acknowledging the question
- JUST START with the direct answer to the question

<example_of_what_not_to_do>
```markdown
## Analysis of `adalflow/adalflow/datasets/gsm8k.py`

This file contains...
```
</example_of_what_not_to_do>

- Format your response with proper markdown including headings, lists, and code blocks WITHIN your answer
- For code analysis, organize your response with clear sections
- Think step by step and structure your answer logically
- Start with the most relevant information that directly addresses the user's query
- Be precise and technical when discussing code
- Your response should be in English
</guidelines>

<style>
- Use concise, direct language
- Prioritize accuracy over verbosity
- When showing code, include line numbers and file paths when relevant
- Use markdown formatting to improve readability
</style>"""

_TEMPLATE_DIR = Path(__file__).parent / "templates"
PAGE_PROMPT_TEMPLATE = Template(
    (_TEMPLATE_DIR / "wiki_page_prompt.txt").read_text(encoding="utf-8"),
)
STRUCTURE_PROMPT_TEMPLATE = Template(
    (_TEMPLATE_DIR / "wiki_structure_prompt.txt").read_text(encoding="utf-8"),
)


def build_wiki_page_prompt(
    page_title: str,
    file_paths_list: str,
    *,
    page_id: str,
    importance: str,
    related_pages: list[str],
) -> str:
    """Return the canonical prompt for generating wiki page content."""
    schema_definition = json.dumps(
        WikiPageSchema.model_json_schema(),
        indent=2,
    ).replace("$", "$$")
    example_response = json.dumps(
        {
            "schema_name": "wiki_page",
            "schema_version": "1.0",
            "page_id": page_id,
            "title": page_title,
            "importance": importance,
            "metadata": {
                "summary": f"Concise overview for {page_title}.",
                "keywords": ["architecture", "overview"],
                "related_page_ids": related_pages,
                "referenced_files": ["README.md"],
                "diagram_types": ["flowchart"],
            },
            "content": "<details>...</details>\\n# Title\\n...",
        },
        indent=2,
    )
    related_pages_text = ", ".join(related_pages) if related_pages else "None supplied"

    return PAGE_PROMPT_TEMPLATE.substitute(
        page_id=page_id,
        page_title=page_title,
        file_paths_list=file_paths_list,
        importance=importance,
        related_pages=related_pages_text,
        schema_definition=schema_definition,
        example_response=example_response,
    )


def _section_guidance(is_comprehensive: bool) -> str:
    if is_comprehensive:
        return """Create a structured wiki with the following main sections:
- Overview (general information about the project)
- System Architecture (how the system is designed)
- Core Features (key functionality)
- Data Management/Flow: If applicable, how data is stored, processed, accessed, and managed (e.g., database schema, data pipelines, state management).
- Frontend Components (UI elements, if applicable.)
- Backend Systems (server-side components)
- Model Integration (AI model connections)
- Deployment/Infrastructure (how to deploy, what's the infrastructure like)
- Extensibility and Customization: If the project architecture supports it, explain how to extend or customize its functionality (e.g., plugins, theming, custom modules, hooks).

Each section should contain relevant pages. For example, the 'Frontend Components' section might include pages for 'Home Page', 'Repository Wiki Page', 'Configuration Modal', etc."""
    return "Create a concise wiki with essential pages covering:"


def build_wiki_structure_prompt(
    file_tree: str,
    readme: str,
    is_comprehensive: bool,
    min_pages: int,
    max_pages: int,
    target_pages: int,
    file_count: int,
) -> str:
    """Return the prompt used for structure generation."""
    section_guidance = _section_guidance(is_comprehensive)
    wiki_scope = "comprehensive" if is_comprehensive else "concise"
    schema_definition = json.dumps(
        WikiStructureSchema.model_json_schema(),
        indent=2,
    ).replace("$", "$$")
    example_response = json.dumps(
        {
            "schema_name": "wiki_structure",
            "schema_version": "1.0",
            "title": "Project DeepWiki",
            "description": "Technical reference capturing architecture, workflows, and developer onboarding guidance.",
            "pages": [
                {
                    "page_id": "overview",
                    "title": "System Overview",
                    "summary": "High-level system context, primary capabilities, and deployment footprint.",
                    "importance": "high",
                    "relevant_files": ["README.md", "docs/architecture.md"],
                    "related_page_ids": ["architecture"],
                    "diagram_suggestions": ["flowchart", "sequenceDiagram"],
                },
            ],
        },
        indent=2,
    )

    return STRUCTURE_PROMPT_TEMPLATE.substitute(
        file_tree=file_tree,
        readme=readme,
        section_guidance=section_guidance,
        min_pages=min_pages,
        max_pages=max_pages,
        target_pages=target_pages,
        wiki_scope=wiki_scope,
        file_count=file_count,
        schema_definition=schema_definition,
        example_response=example_response,
    )


