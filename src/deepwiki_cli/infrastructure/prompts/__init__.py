"""Prompt management infrastructure."""

from deepwiki_cli.infrastructure.prompts.builders import (
    PAGE_PROMPT_TEMPLATE,
    RAG_SYSTEM_PROMPT,
    RAG_TEMPLATE,
    SIMPLE_CHAT_SYSTEM_PROMPT,
    STRUCTURE_PROMPT_TEMPLATE,
    build_wiki_page_prompt,
    build_wiki_structure_prompt,
)

__all__ = [
    "PAGE_PROMPT_TEMPLATE",
    "RAG_SYSTEM_PROMPT",
    "RAG_TEMPLATE",
    "SIMPLE_CHAT_SYSTEM_PROMPT",
    "STRUCTURE_PROMPT_TEMPLATE",
    "build_wiki_page_prompt",
    "build_wiki_structure_prompt",
]

