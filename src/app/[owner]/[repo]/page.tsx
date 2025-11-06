/* eslint-disable @typescript-eslint/no-unused-vars */
'use client';

import Markdown from '@/components/Markdown';
import ModelSelectionModal from '@/components/ModelSelectionModal';
import ThemeToggle from '@/components/theme-toggle';
import WikiTreeView from '@/components/WikiTreeView';
import { RepoInfo } from '@/types/repoinfo';
import getRepoUrl from '@/utils/getRepoUrl';
import { extractUrlDomain, extractUrlPath } from '@/utils/urlDecoder';
import { validateMermaidMarkdown, MermaidIssue } from '@/utils/mermaidValidation';
import { MERMAID_EXAMPLE_1, MERMAID_EXAMPLE_2, MERMAID_EXAMPLE_3 } from '@/utils/wikiPrompts';
import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FaBookOpen, FaDownload, FaExclamationTriangle, FaFileExport, FaFolder, FaGithub, FaHome, FaSync } from 'react-icons/fa';
// Define the WikiSection and WikiStructure types directly in this file
// since the imported types don't have the sections and rootSections properties
interface WikiSection {
  id: string;
  title: string;
  pages: string[];
  subsections?: string[];
}

interface WikiPage {
  id: string;
  title: string;
  content: string;
  filePaths: string[];
  importance: 'high' | 'medium' | 'low';
  relatedPages: string[];
  parentId?: string;
  isSection?: boolean;
  children?: string[];
}

interface WikiStructure {
  id: string;
  title: string;
  description: string;
  pages: WikiPage[];
  sections: WikiSection[];
  rootSections: string[];
}


// Add CSS styles for wiki
const wikiStyles = `
  .prose code {
    @apply bg-[var(--background)]/70 px-1.5 py-0.5 rounded font-mono text-xs border border-[var(--border-color)];
  }

  .prose pre {
    @apply bg-[var(--background)]/80 text-[var(--foreground)] rounded-md p-4 overflow-x-auto border border-[var(--border-color)] shadow-sm;
  }

  .prose h1, .prose h2, .prose h3, .prose h4 {
    @apply font-serif text-[var(--foreground)];
  }

  .prose p {
    @apply text-[var(--foreground)] leading-relaxed;
  }

  .prose a {
    @apply text-[var(--accent-primary)] hover:text-[var(--highlight)] transition-colors no-underline border-b border-[var(--border-color)] hover:border-[var(--accent-primary)];
  }

  .prose blockquote {
    @apply border-l-4 border-[var(--accent-primary)]/30 bg-[var(--background)]/30 pl-4 py-1 italic;
  }

  .prose ul, .prose ol {
    @apply text-[var(--foreground)];
  }

  .prose table {
    @apply border-collapse border border-[var(--border-color)];
  }

  .prose th {
    @apply bg-[var(--background)]/70 text-[var(--foreground)] p-2 border border-[var(--border-color)];
  }

  .prose td {
    @apply p-2 border border-[var(--border-color)];
  }
  `;

// Helper function to generate cache key for localStorage
const getCacheKey = (owner: string, repo: string, repoType: string, language: string, isComprehensive: boolean = true): string => {
  return `deepwiki_cache_${repoType}_${owner}_${repo}_${language}_${isComprehensive ? 'comprehensive' : 'concise'}`;
};

// Helper function to add tokens and other parameters to request body
const addTokensToRequestBody = (
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  requestBody: Record<string, any>,
  token: string,
  repoType: string,
  provider: string = '',
  model: string = '',
  isCustomModel: boolean = false,
  customModel: string = '',
  language: string = 'en',
  excludedDirs?: string,
  excludedFiles?: string,
  includedDirs?: string,
  includedFiles?: string
): void => {
  if (token !== '') {
    requestBody.token = token;
  }

  // Add provider-based model selection parameters
  requestBody.provider = provider;
  requestBody.model = model;
  if (isCustomModel && customModel) {
    requestBody.custom_model = customModel;
  }

  requestBody.language = language;

  // Add file filter parameters if provided
  if (excludedDirs) {
    requestBody.excluded_dirs = excludedDirs;
  }
  if (excludedFiles) {
    requestBody.excluded_files = excludedFiles;
  }
  if (includedDirs) {
    requestBody.included_dirs = includedDirs;
  }
  if (includedFiles) {
    requestBody.included_files = includedFiles;
  }

};

const createGithubHeaders = (githubToken: string): HeadersInit => {
  const headers: HeadersInit = {
    'Accept': 'application/vnd.github.v3+json'
  };

  if (githubToken) {
    headers['Authorization'] = `Bearer ${githubToken}`;
  }

  return headers;
};




export default function RepoWikiPage() {
  const clone = <T,>(value: T): T => {
    if (typeof structuredClone === 'function') {
      return structuredClone(value);
    }
    return JSON.parse(JSON.stringify(value)) as T;
  };

  // Get route parameters and search params
  const params = useParams();
  const searchParams = useSearchParams();

  // Extract owner and repo from route params
  const owner = params.owner as string;
  const repo = params.repo as string;

  // Extract tokens from search params
  const token = searchParams.get('token') || '';
  const localPath = searchParams.get('local_path') ? decodeURIComponent(searchParams.get('local_path') || '') : undefined;
  const repoUrl = searchParams.get('repo_url') ? decodeURIComponent(searchParams.get('repo_url') || '') : undefined;
  const providerParam = searchParams.get('provider') || '';
  const modelParam = searchParams.get('model') || '';
  const isCustomModelParam = searchParams.get('is_custom_model') === 'true';
  const customModelParam = searchParams.get('custom_model') || '';
  const language = searchParams.get('language') || 'en';
  const repoHost = (() => {
    if (!repoUrl) return '';
    try {
      return new URL(repoUrl).hostname.toLowerCase();
    } catch (e) {
      console.warn(`Invalid repoUrl provided: ${repoUrl}`);
      return '';
    }
  })();
  const repoType = 'github'; // We only support GitHub repositories now

  // Initialize repo info
  const repoInfo = useMemo<RepoInfo>(() => ({
    owner,
    repo,
    type: repoType,
    token: token || null,
    localPath: localPath || null,
    repoUrl: repoUrl || null
  }), [owner, repo, repoType, localPath, repoUrl, token]);

  // State variables
  const [isLoading, setIsLoading] = useState(true);
  const [loadingMessage, setLoadingMessage] = useState<string | undefined>(
    'Initializing wiki generation...'
  );
  const [error, setError] = useState<string | null>(null);
  const [wikiStructure, setWikiStructure] = useState<WikiStructure | undefined>();
  const [currentPageId, setCurrentPageId] = useState<string | undefined>();
  const [generatedPages, setGeneratedPages] = useState<Record<string, WikiPage>>({});
  const [pagesInProgress, setPagesInProgress] = useState(new Set<string>());
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [originalMarkdown, setOriginalMarkdown] = useState<Record<string, string>>({});
  const [pageFeedbackDrafts, setPageFeedbackDrafts] = useState<Record<string, string>>({});
  const [pageRefreshMessages, setPageRefreshMessages] = useState<Record<string, { type: 'success' | 'error'; text: string }>>({});
  const [, setMermaidValidationIssues] = useState<Record<string, MermaidIssue[]>>({});
  const [requestInProgress, setRequestInProgress] = useState(false);
  const [currentToken, setCurrentToken] = useState(token); // Track current effective token
  const [effectiveRepoInfo, setEffectiveRepoInfo] = useState(repoInfo); // Track effective repo info with cached data
  const [embeddingError, setEmbeddingError] = useState(false);

  // Model selection state variables
  const [selectedProviderState, setSelectedProviderState] = useState(providerParam);
  const [selectedModelState, setSelectedModelState] = useState(modelParam);
  const [isCustomSelectedModelState, setIsCustomSelectedModelState] = useState(isCustomModelParam);
  const [customSelectedModelState, setCustomSelectedModelState] = useState(customModelParam);
  const [showModelOptions, setShowModelOptions] = useState(false); // Controls whether to show model options
  const excludedDirs = searchParams.get('excluded_dirs') || '';
  const excludedFiles = searchParams.get('excluded_files') || '';
  const [modelExcludedDirs, setModelExcludedDirs] = useState(excludedDirs);
  const [modelExcludedFiles, setModelExcludedFiles] = useState(excludedFiles);
  const includedDirs = searchParams.get('included_dirs') || '';
  const includedFiles = searchParams.get('included_files') || '';
  const [modelIncludedDirs, setModelIncludedDirs] = useState(includedDirs);
  const [modelIncludedFiles, setModelIncludedFiles] = useState(includedFiles);


  // Wiki type state - default to comprehensive view
  const isComprehensiveParam = searchParams.get('comprehensive') !== 'false';
  const [isComprehensiveView, setIsComprehensiveView] = useState(isComprehensiveParam);
  // Using useRef for activeContentRequests to maintain a single instance across renders
  // This map tracks which pages are currently being processed to prevent duplicate requests
  // Note: In a multi-threaded environment, additional synchronization would be needed,
  // but in React's single-threaded model, this is safe as long as we set the flag before any async operations
  const activeContentRequests = useRef(new Map<string, boolean>()).current;
  const [structureRequestInProgress, setStructureRequestInProgress] = useState(false);
  // Create a flag to track if data was loaded from cache to prevent immediate re-save
  const cacheLoadedSuccessfully = useRef(false);

  const persistWikiCache = useCallback(async (pagesOverride?: Record<string, WikiPage>) => {
    if (!wikiStructure || wikiStructure.pages.length === 0) {
      return;
    }

    const pagesMap = pagesOverride ?? generatedPages;

    const allPagesHaveContent = wikiStructure.pages.every(page => {
      const content = pagesMap[page.id]?.content;
      return content && content !== 'Loading...';
    });

    if (!allPagesHaveContent) {
      return;
    }

    const structureToCache = {
      ...wikiStructure,
      sections: wikiStructure.sections || [],
      rootSections: wikiStructure.rootSections || []
    };

    const dataToCache = {
      repo: effectiveRepoInfo,
      language,
      comprehensive: isComprehensiveView,
      wiki_structure: structureToCache,
      generated_pages: pagesMap,
      provider: selectedProviderState,
      model: selectedModelState
    };

    try {
      const response = await fetch(`/api/wiki_cache`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(dataToCache),
      });

      if (response.ok) {
        console.log('Wiki data successfully saved to server cache');
        cacheLoadedSuccessfully.current = true;
      } else {
        console.error('Error saving wiki data to server cache:', response.status, await response.text());
      }
    } catch (error) {
      console.error('Error saving to server cache:', error);
    }
  }, [wikiStructure, generatedPages, effectiveRepoInfo, language, isComprehensiveView, selectedProviderState, selectedModelState]);

  // Create a flag to ensure the effect only runs once
  const effectRan = React.useRef(false);

  // Default branch state
  const [defaultBranch, setDefaultBranch] = useState<string>('main');

  // Helper function to generate proper repository file URLs
  const generateFileUrl = useCallback((filePath: string): string => {
    if (effectiveRepoInfo.type === 'local') {
      // For local repositories, we can't generate web URLs
      return filePath;
    }

    const repoUrl = effectiveRepoInfo.repoUrl;
    if (!repoUrl) {
      return filePath;
    }

    try {
      const url = new URL(repoUrl);
      const hostname = url.hostname;

      if (hostname === 'github.com' || hostname.includes('github')) {
        // GitHub URL format: https://github.com/owner/repo/blob/branch/path
        return `${repoUrl}/blob/${defaultBranch}/${filePath}`;
      }
    } catch (error) {
      console.warn('Error generating file URL:', error);
    }

    // Fallback to just the file path
    return filePath;
  }, [effectiveRepoInfo, defaultBranch]);

  // Memoize repo info to avoid triggering updates in callbacks

  // Add useEffect to handle scroll reset
  useEffect(() => {
    // Scroll to top when currentPageId changes
    const wikiContent = document.getElementById('wiki-content');
    if (wikiContent) {
      wikiContent.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [currentPageId]);

  // Generate content for a wiki page
  const generatePageContent = useCallback(async (page: WikiPage, owner: string, repo: string, options?: { force?: boolean; feedback?: string }) => {
    return new Promise<boolean>(async (resolve) => {
      const forceRegeneration = options?.force ?? false;
      const feedbackNote = options?.feedback?.trim();
      const previousContent = generatedPages[page.id]?.content;

      try {
        // Skip if content already exists and we're not forcing a refresh
        if (!forceRegeneration && previousContent) {
          resolve(true);
          return;
        }

        // Skip if this page is already being processed
        // Use a synchronized pattern to avoid race conditions
        if (activeContentRequests.get(page.id)) {
          console.log(`Page ${page.id} (${page.title}) is already being processed, skipping duplicate call`);
          resolve(false);
          return;
        }

        // Mark this page as being processed immediately to prevent race conditions
        // This ensures that if multiple calls happen nearly simultaneously, only one proceeds
        activeContentRequests.set(page.id, true);

        // Validate repo info
        if (!owner || !repo) {
          throw new Error('Invalid repository information. Owner and repo name are required.');
        }

        // Mark page as in progress
        setPagesInProgress(prev => new Set(prev).add(page.id));

        const filePaths = page.filePaths;

        // Show a placeholder only when no previous content exists (initial generation)
        if (!forceRegeneration || !previousContent) {
          setGeneratedPages(prev => ({
            ...prev,
            [page.id]: { ...page, content: 'Loading...' }
          }));
        }
        setOriginalMarkdown(prev => ({ ...prev, [page.id]: '' })); // Clear previous original

        // Make API call to generate page content
        console.log(`Starting content generation for page: ${page.title}${forceRegeneration ? ' (forced refresh)' : ''}`);

        // Get repository URL
        const repoUrl = getRepoUrl(effectiveRepoInfo);

        const previousContentSection = forceRegeneration && previousContent
          ? `
                PREVIOUS WIKI CONTENT FOR REFERENCE:
                <previous_markdown>
                ${previousContent}
                </previous_markdown>

                Use the previous content as a baseline and revise it according to the feedback and updated understanding.`
          : '';

        const feedbackSection = feedbackNote
          ? `
                ADDITIONAL CORRECTIONS FROM USER FEEDBACK:
                ${feedbackNote}

                Incorporate every correction from the feedback when composing the page.`
          : '';

        // Create the prompt content - simplified to avoid message dialogs
        const promptContent =
          `You are an expert technical writer and software architect.
                Your task is to generate a comprehensive and accurate technical wiki page in Markdown format about a specific feature, system, or module within a given software project.

                You will be given:
                1. The "[WIKI_PAGE_TOPIC]" for the page you need to create.
                2. A list of "[RELEVANT_SOURCE_FILES]" from the project that you MUST use as the sole basis for the content. You have access to the full content of these files. You MUST use AT LEAST 5 relevant source files for comprehensive coverage - if fewer are provided, search for additional related files in the codebase.
${previousContentSection}${feedbackSection}

                CRITICAL STARTING INSTRUCTION:
                The very first thing on the page MUST be a \`<details>\` block listing ALL the \`[RELEVANT_SOURCE_FILES]\` you used to generate the content. There MUST be AT LEAST 5 source files listed - if fewer were provided, you MUST find additional related files to include.
                  Format it exactly like this:
                  <details>
                    <summary>Relevant source files</summary>

                    Remember, do not provide any acknowledgements, disclaimers, apologies, or any other preface before the \`<details>\` block. JUST START with the \`<details>\` block.
                      The following files were used as context for generating this wiki page:

                      ${filePaths.map(path => `- [${path}](${generateFileUrl(path)})`).join('\n')}
                      <!-- Add additional relevant files if fewer than 5 were provided -->
                    </details>

                      Immediately after the \`<details>\` block, the main title of the page should be a H1 Markdown heading: \`# ${page.title}\`.

                        Based ONLY on the content of the \`[RELEVANT_SOURCE_FILES]\`:

                        1.  **Introduction:** Start with a concise introduction (1-2 paragraphs) explaining the purpose, scope, and high-level overview of "${page.title}" within the context of the overall project. If relevant, and if information is available in the provided files, link to other potential wiki pages using the format \`[Link Text](#page-anchor-or-id)\`.

                        2.  **Detailed Sections:** Break down "${page.title}" into logical sections using H2 (\`##\`) and H3 (\`###\`) Markdown headings. For each section:
                        *   Explain the architecture, components, data flow, or logic relevant to the section's focus, as evidenced in the source files.
                        *   Identify key functions, classes, data structures, API endpoints, or configuration elements pertinent to that section.

                        3.  **Mermaid Diagrams:**
                        *   EXTENSIVELY use Mermaid diagrams (e.g., \`flowchart TD\`, \`sequenceDiagram\`, \`classDiagram\`, \`erDiagram\`, \`graph TD\`) to visually represent architectures, flows, relationships, and schemas found in the source files.
                        *   Ensure diagrams are accurate and directly derived from information in the \`[RELEVANT_SOURCE_FILES]\`.
                        *   Provide a brief explanation before or after each diagram to give context.
                        
                        **CRITICAL SYNTAX RULES FOR MERMAID DIAGRAMS:**
                        
                        **FLOWCHART REQUIREMENTS:**
                        - ALWAYS use "flowchart TD" (never "graph TD") as the first directive
                        - Place the directive on its own line, followed by a blank line
                        - Use simple alphanumeric node IDs (e.g., A, B, C, node1, start)
                        - Node labels MUST be enclosed in quotes: A["Label text"]
                        - Labels should be 3-4 words maximum per line
                        - Use &lt;br/&gt; for line breaks inside labels: A["First<br/>Second"]
                        - Use simple arrow syntax: --> for simple flow, -. -> for dotted, -->|label| for labeled edges
                        - Keep node text SHORT to prevent rendering issues
                        - Avoid special characters in node IDs (use only letters, numbers, underscore)
                        - Avoid complex patterns: NO A--|label|B syntax (Mermaid doesn't support this)
                        - For subgraphs: Use subgraph id["Name"] ... end syntax
                        
                        **SEQUENCE DIAGRAM REQUIREMENTS:**
                        - Start with "sequenceDiagram" as the first directive
                        - Declare ALL participants at the beginning: participant id as Name
                        - Use descriptive names but keep them concise (max 15 characters)
                        - Simple participant IDs: A, B, C, or meaningful short names
                        - Use correct arrow syntax:
                          * ->> for solid line with arrowhead (most common)
                          * -->> for dotted line with arrowhead
                          * -> for solid line without arrow
                          * --> for dotted line without arrow
                        - Message syntax: A->>B: Message text (colon required, no special formatting needed)
                        - Use "Note over" or "Note right of" for comments
                        - Avoid nested structures unless necessary
                        - Use alt/else for conditional flows, NOT complex nested structures
                        
                        **COMMON ERRORS TO AVOID:**
                        - ❌ Do NOT use unquoted node labels: A[Label] (WRONG - quotes required)
                        - ❌ Do NOT use multiple lines per line: A->>B: Message\nMore (WRONG - one message per line)
                        - ❌ Do NOT use special escape sequences: A["Text\\n"] (WRONG - use &lt;br/&gt; instead)
                        - ❌ Do NOT mix participant definition with messages: participant A in sequenceDiagram (WRONG - define all at top)
                        - ❌ Do NOT use undefined participants in messages
                        - ❌ Do NOT use flowchart syntax in sequenceDiagrams or vice versa
                        - ❌ Do NOT create circular dependencies without explicit loops
                        - ❌ Do NOT use HTML entities like &amp; in labels (use regular & instead)

                        **HIGH-QUALITY MERMAID DIAGRAM EXAMPLES:**

                        **Example 1: Architecture Flowchart with Subgraphs**
                        \`\`\`mermaid
                        ${MERMAID_EXAMPLE_1}
                        \`\`\`

                        **Example 2: Sequence Diagram with Structural Elements**
                        \`\`\`mermaid
                        ${MERMAID_EXAMPLE_2}
                        \`\`\`

                        **Example 3: Decision Tree Flowchart**
                        \`\`\`mermaid
                        ${MERMAID_EXAMPLE_3}
                        \`\`\`

                        4.  **Tables:**
                        *   Use Markdown tables to summarize information such as:
                        *   Key features or components and their descriptions.
                        *   API endpoint parameters, types, and descriptions.
                        *   Configuration options, their types, and default values.
                        *   Data model fields, types, constraints, and descriptions.

                        5.  **Code Snippets (ENTIRELY OPTIONAL):**
                        *   Include short, relevant code snippets (e.g., Python, Java, JavaScript, SQL, JSON, YAML) directly from the \`[RELEVANT_SOURCE_FILES]\` to illustrate key implementation details, data structures, or configurations.
                        *   Ensure snippets are well-formatted within Markdown code blocks with appropriate language identifiers.

                        6.  **Source Citations (EXTREMELY IMPORTANT):**
                        *   For EVERY piece of significant information, explanation, diagram, table entry, or code snippet, you MUST cite the specific source file(s) and relevant line numbers from which the information was derived.
                        *   Place citations at the end of the paragraph, under the diagram/table, or after the code snippet.
                        *   Use the exact format: \`Sources: [filename.ext:start_line-end_line]()\` for a range, or \`Sources: [filename.ext:line_number]()\` for a single line. Multiple files can be cited: \`Sources: [file1.ext:1-10](), [file2.ext:5](), [dir/file3.ext]()\` (if the whole file is relevant and line numbers are not applicable or too broad).
                        *   If an entire section is overwhelmingly based on one or two files, you can cite them under the section heading in addition to more specific citations within the section.
                        *   IMPORTANT: You MUST cite AT LEAST 5 different source files throughout the wiki page to ensure comprehensive coverage.

                        7.  **Technical Accuracy:** All information must be derived SOLELY from the \`[RELEVANT_SOURCE_FILES]\`. Do not infer, invent, or use external knowledge about similar systems or common practices unless it's directly supported by the provided code. If information is not present in the provided files, do not include it or explicitly state its absence if crucial to the topic.

                        8.  **Clarity and Conciseness:** Use clear, professional, and concise technical language suitable for other developers working on or learning about the project. Avoid unnecessary jargon, but use correct technical terms where appropriate.

                        9.  **Conclusion/Summary:** End with a brief summary paragraph if appropriate for "${page.title}", reiterating the key aspects covered and their significance within the project.

                        IMPORTANT: Generate the content in English language.

                        Remember:
                        - Ground every claim in the provided source files.
                        - Prioritize accuracy and direct representation of the code's functionality and structure.
                        - Structure the document logically for easy understanding by other developers.
                        `;

        // Prepare request body
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const requestBody: Record<string, any> = {
          repo_url: repoUrl,
          type: effectiveRepoInfo.type,
          messages: [{
            role: 'user',
            content: promptContent
          }]
        };

        // Add tokens if available
        addTokensToRequestBody(requestBody, currentToken, effectiveRepoInfo.type, selectedProviderState, selectedModelState, isCustomSelectedModelState, customSelectedModelState, language, modelExcludedDirs, modelExcludedFiles, modelIncludedDirs, modelIncludedFiles);

        const sanitizeMarkdown = (input: string) =>
          input.replace(/^```markdown\s*/i, '').replace(/```\s*$/i, '').trim();

        const fetchPageContent = async (body: Record<string, unknown>, label: string) => {
          let rawContent = '';

          try {
            const serverBaseUrl = process.env.SERVER_BASE_URL || 'http://localhost:8001';
            const response = await fetch(`${serverBaseUrl}/chat/completions/stream`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
              },
              body: JSON.stringify(body)
            });

            if (!response.ok) {
              const errorText = await response.text().catch(() => 'No error details available');
              console.error(`API error (${response.status}): ${errorText}`);
              throw new Error(`Error generating page content: ${response.status} - ${response.statusText}`);
            }

            rawContent = '';
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();

            if (!reader) {
              throw new Error('Failed to get response reader');
            }

            try {
              while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                rawContent += decoder.decode(value, { stream: true });
              }
              rawContent += decoder.decode();
            } catch (readError) {
              console.error('Error reading stream:', readError);
              throw new Error('Error processing response stream');
            }
          } catch (httpError) {
            console.error(`HTTP error while generating ${label}:`, httpError);
            throw httpError instanceof Error ? httpError : new Error(String(httpError));
          }

          return sanitizeMarkdown(rawContent);
        };

        const baseRequestBody = clone(requestBody);
        const baseMessages = clone(baseRequestBody.messages ?? []);

        const content = await fetchPageContent(baseRequestBody, page.title);

        console.log(`Received content for ${page.title}, length: ${content.length} characters`);

        const runMermaidRepairLoop = async (initialContent: string) => {
          const safeValidate = async (contentToValidate: string) => {
            try {
              return await validateMermaidMarkdown(contentToValidate);
            } catch (validateError) {
              console.error('Mermaid validation failed unexpectedly:', validateError);
              return [{
                index: -1,
                code: '',
                error: validateError instanceof Error ? validateError.message : String(validateError)
              }];
            }
          };

          let attempts = 0;
          let latestContent = initialContent;
          let issues = await safeValidate(latestContent);

          while (issues.length > 0 && attempts < 3) {
            attempts += 1;
            console.warn(`Mermaid validation failed for ${page.title} (attempt ${attempts})`, issues);

            const errorReport = issues.map((issue, idx) => {
              const diagramIndex = issue.index >= 0 ? issue.index + 1 : idx + 1;
              const codeSnippet = issue.code ? `\n<diagram>\n${issue.code}\n</diagram>` : '';
              return `Diagram ${diagramIndex} error: ${issue.error}${codeSnippet}`;
            }).join('\n\n');

            const repairPrompt = `You previously generated the following markdown for the wiki page "${page.title}":\n\n<original_markdown>\n${latestContent}\n</original_markdown>\n\nThe Mermaid diagrams in that markdown failed to render with these parser errors:\n\n<parser_errors>\n${errorReport}\n</parser_errors>\n\nPlease return the FULL wiki page markdown again with every diagram corrected so that Mermaid can parse it successfully. Preserve the structure, content, and citations from the original response. Do not include any commentary or explanations—only return the corrected markdown content.`;

            const repairBody = clone(baseRequestBody);
            repairBody.messages = [
              ...baseMessages,
              { role: 'assistant', content: latestContent },
              { role: 'user', content: repairPrompt }
            ];

            try {
              const repairedContent = await fetchPageContent(repairBody, `${page.title} (repair ${attempts})`);
              if (!repairedContent || repairedContent.trim().length === 0) {
                console.warn(`Mermaid repair attempt ${attempts} returned empty content for ${page.title}, keeping previous content.`);
                break;
              }
              latestContent = repairedContent;
            } catch (repairError) {
              console.error(`Mermaid repair attempt ${attempts} failed for ${page.title}:`, repairError);
              break;
            }

            issues = await safeValidate(latestContent);
          }

          if (issues.length) {
            console.error(`Mermaid diagrams still failing after ${attempts} attempts for ${page.title}. Using original content.`, issues);
            return { content: initialContent, issues };
          }

          if (attempts > 0) {
            console.log(`Mermaid diagrams validated successfully for ${page.title} after ${attempts} repair attempt(s).`);
          }

          return { content: latestContent, issues };
        };

        const { content: finalContent, issues: remainingIssues } = await runMermaidRepairLoop(content);

        const updatedPage = { ...page, content: finalContent };
        setGeneratedPages(prev => {
          const next = { ...prev, [page.id]: updatedPage };
          cacheLoadedSuccessfully.current = false;
          void persistWikiCache(next);
          return next;
        });
        setOriginalMarkdown(prev => ({ ...prev, [page.id]: finalContent }));
        setMermaidValidationIssues(prev => {
          const next = { ...prev };
          if (remainingIssues.length) {
            next[page.id] = remainingIssues;
          } else {
            delete next[page.id];
          }
          return next;
        });

        resolve(true);
      } catch (err) {
        console.error(`Error generating content for page ${page.id}:`, err);
        const errorMessage = err instanceof Error ? err.message : 'Unknown error';
        // Update page state to show error
        setGeneratedPages(prev => ({
          ...prev,
          [page.id]: { ...page, content: `Error generating content: ${errorMessage}` }
        }));
        setError(`Failed to generate content for ${page.title}.`);
        resolve(false);
      } finally {
        // Clear the processing flag for this page
        // This must happen in the finally block to ensure the flag is cleared
        // even if an error occurs during processing
        activeContentRequests.delete(page.id);

        // Mark page as done
        setPagesInProgress(prev => {
          const next = new Set(prev);
          next.delete(page.id);
          return next;
        });
        setLoadingMessage(undefined); // Clear specific loading message
      }
    });
  }, [generatedPages, currentToken, effectiveRepoInfo, selectedProviderState, selectedModelState, isCustomSelectedModelState, customSelectedModelState, modelExcludedDirs, modelExcludedFiles, modelIncludedDirs, modelIncludedFiles, language, activeContentRequests, generateFileUrl, persistWikiCache]);

  // Determine the wiki structure from repository data
  const determineWikiStructure = useCallback(async (fileTree: string, readme: string, owner: string, repo: string) => {
    if (!owner || !repo) {
      setError('Invalid repository information. Owner and repo name are required.');
      setIsLoading(false);
      setEmbeddingError(false); // Reset embedding error state
      return;
    }

    // Skip if structure request is already in progress
    if (structureRequestInProgress) {
      console.log('Wiki structure determination already in progress, skipping duplicate call');
      return;
    }

    try {
      setStructureRequestInProgress(true);
      setLoadingMessage('Determining wiki structure...');

      // Get repository URL
      const repoUrl = getRepoUrl(effectiveRepoInfo);

      // Prepare request body
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const requestBody: Record<string, any> = {
        repo_url: repoUrl,
        type: effectiveRepoInfo.type,
        messages: [{
          role: 'user',
          content: `Analyze this GitHub repository ${owner}/${repo} and create a wiki structure for it.

                            1. The complete file tree of the project:
                            <file_tree>
                              ${fileTree}
                            </file_tree>

                            2. The README file of the project:
                            <readme>
                              ${readme}
                            </readme>

                            I want to create a wiki for this repository. Determine the most logical structure for a wiki based on the repository's content.

                            IMPORTANT: The wiki content will be generated in English language.

                            When designing the wiki structure, include pages that would benefit from visual diagrams, such as:
                            - Architecture overviews
                            - Data flow descriptions
                            - Component relationships
                            - Process workflows
                            - State machines
                            - Class hierarchies

                            ${isComprehensiveView ? `
Create a structured wiki with the following main sections:
- Overview (general information about the project)
- System Architecture (how the system is designed)
- Core Features (key functionality)
- Data Management/Flow: If applicable, how data is stored, processed, accessed, and managed (e.g., database schema, data pipelines, state management).
- Frontend Components (UI elements, if applicable.)
- Backend Systems (server-side components)
- Model Integration (AI model connections)
- Deployment/Infrastructure (how to deploy, what's the infrastructure like)
- Extensibility and Customization: If the project architecture supports it, explain how to extend or customize its functionality (e.g., plugins, theming, custom modules, hooks).

Each section should contain relevant pages. For example, the "Frontend Components" section might include pages for "Home Page", "Repository Wiki Page", "Configuration Modal", etc.

Return your analysis in the following XML format:

<wiki_structure>
  <title>[Overall title for the wiki]</title>
  <description>[Brief description of the repository]</description>
  <sections>
    <section id="section-1">
      <title>[Section title]</title>
      <pages>
        <page_ref>page-1</page_ref>
        <page_ref>page-2</page_ref>
      </pages>
      <subsections>
        <section_ref>section-2</section_ref>
      </subsections>
    </section>
    <!-- More sections as needed -->
  </sections>
  <pages>
    <page id="page-1">
      <title>[Page title]</title>
      <description>[Brief description of what this page will cover]</description>
      <importance>high|medium|low</importance>
      <relevant_files>
        <file_path>[Path to a relevant file]</file_path>
        <!-- More file paths as needed -->
      </relevant_files>
      <related_pages>
        <related>page-2</related>
        <!-- More related page IDs as needed -->
      </related_pages>
      <parent_section>section-1</parent_section>
    </page>
    <!-- More pages as needed -->
  </pages>
</wiki_structure>
` : `
Return your analysis in the following XML format:

<wiki_structure>
  <title>[Overall title for the wiki]</title>
  <description>[Brief description of the repository]</description>
  <pages>
    <page id="page-1">
      <title>[Page title]</title>
      <description>[Brief description of what this page will cover]</description>
      <importance>high|medium|low</importance>
      <relevant_files>
        <file_path>[Path to a relevant file]</file_path>
        <!-- More file paths as needed -->
      </relevant_files>
      <related_pages>
        <related>page-2</related>
        <!-- More related page IDs as needed -->
      </related_pages>
    </page>
    <!-- More pages as needed -->
  </pages>
</wiki_structure>
`}

                            IMPORTANT FORMATTING INSTRUCTIONS:
                            - Return ONLY the valid XML structure specified above
                            - DO NOT wrap the XML in markdown code blocks (no \`\`\` or \`\`\`xml)
                            - DO NOT include any explanation text before or after the XML
                            - Ensure the XML is properly formatted and valid
                            - Start directly with <wiki_structure> and end with </wiki_structure>

                            IMPORTANT:
                            1. Create ${isComprehensiveView ? '8-12' : '4-6'} pages that would make a ${isComprehensiveView ? 'comprehensive' : 'concise'} wiki for this repository
                            2. Each page should focus on a specific aspect of the codebase (e.g., architecture, key features, setup)
                            3. The relevant_files should be actual files from the repository that would be used to generate that page
                            4. Return ONLY valid XML with the structure specified above, with no markdown code block delimiters`
        }]
      };

      // Add tokens if available
      addTokensToRequestBody(requestBody, currentToken, effectiveRepoInfo.type, selectedProviderState, selectedModelState, isCustomSelectedModelState, customSelectedModelState, language, modelExcludedDirs, modelExcludedFiles, modelIncludedDirs, modelIncludedFiles);

      const serverBaseUrl = process.env.SERVER_BASE_URL || 'http://localhost:8001';
      const structureResponse = await fetch(`${serverBaseUrl}/chat/completions/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(requestBody)
      });

      if (!structureResponse.ok) {
        const errorText = await structureResponse.text().catch(() => '');
        throw new Error(`Error determining wiki structure: ${structureResponse.status} ${errorText}`);
      }

      const reader = structureResponse.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Failed to read wiki structure response stream');
      }

      let responseText = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        responseText += decoder.decode(value, { stream: true });
      }

      if (responseText.includes('Error preparing retriever: Environment variable OPENAI_API_KEY must be set')) {
        setEmbeddingError(true);
        throw new Error('OPENAI_API_KEY environment variable is not set. Please configure your OpenAI API key.');
      }

      if (responseText.includes('Ollama model') && responseText.includes('not found')) {
        setEmbeddingError(true);
        throw new Error('The specified Ollama embedding model was not found. Please ensure the model is installed locally or select a different embedding model in the configuration.');
      }

      // Log the raw response for debugging
      console.log('Raw response from API (first 500 chars):', responseText.substring(0, 500));

      // Check if response is empty or too short
      if (!responseText || responseText.trim().length === 0) {
        throw new Error('Backend API returned an empty response. Please ensure the backend server is running at ' + (process.env.SERVER_BASE_URL || 'http://localhost:8001'));
      }

      // Check for common error patterns in the response
      if (responseText.includes('Connection refused') || responseText.includes('ECONNREFUSED')) {
        throw new Error('Cannot connect to backend API server. Please ensure it is running at ' + (process.env.SERVER_BASE_URL || 'http://localhost:8001'));
      }

      if (responseText.includes('Internal Server Error') || responseText.includes('500')) {
        throw new Error('Backend API server encountered an error: ' + responseText.substring(0, 200));
      }

      // Check for API authentication errors based on content
      if (responseText.includes('401') || responseText.includes('No cookie auth credentials') || responseText.includes('invalid_api_key') || responseText.includes('Incorrect API key provided')) {
        // Provider-specific error messages based on response content
        if (responseText.includes('api.openai.com') || responseText.includes('sk-proj-') || responseText.includes('platform.openai.com')) {
          throw new Error('OpenAI API authentication failed. Please check that your OPENAI_API_KEY is correct and valid. You can find your API key at https://platform.openai.com/account/api-keys.');
        } else if (responseText.includes('openrouter.ai') || responseText.includes('OPENROUTER_API_KEY not configured')) {
          throw new Error('OpenRouter API authentication failed. Please set the OPENROUTER_API_KEY environment variable in your .env file with a valid API key from https://openrouter.ai/keys');
        } else {
          // Generic auth error for other providers
          throw new Error('API authentication failed. Please check that your API key is correctly configured for the selected provider.');
        }
      }

      if (responseText.includes('OPENAI_API_KEY not configured')) {
        setEmbeddingError(true);
        throw new Error('OpenAI API key not configured. Please set the OPENAI_API_KEY environment variable in your .env file.');
      }

      if (responseText.includes('OPENROUTER_API_KEY not configured')) {
        throw new Error('OpenRouter API key not configured. Please set the OPENROUTER_API_KEY environment variable in your .env file with a valid API key from https://openrouter.ai/keys');
      }

      if (responseText.includes('GOOGLE_API_KEY') || responseText.includes('Google API')) {
        throw new Error('Google API authentication failed. Please set the GOOGLE_API_KEY environment variable in your .env file.');
      }

      // Clean up markdown delimiters
      responseText = responseText.replace(/^```(?:xml)?\s*/i, '').replace(/```\s*$/i, '');

      // Extract wiki structure from response
      const xmlMatch = responseText.match(/<wiki_structure>[\s\S]*?<\/wiki_structure>/m);
      if (!xmlMatch) {
        console.error('Failed to find XML structure in response. Response length:', responseText.length);
        console.error('Response preview:', responseText.substring(0, 1000));
        throw new Error('No valid XML found in response. The LLM may have returned an unexpected format. Please check the console for details or try again.');
      }

      let xmlText = xmlMatch[0];
      xmlText = xmlText.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '');
      // Try parsing with DOMParser
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(xmlText, "text/xml");

      // Check for parsing errors
      const parseError = xmlDoc.querySelector('parsererror');
      if (parseError) {
        // Log the first few elements to see what was parsed
        const elements = xmlDoc.querySelectorAll('*');
        if (elements.length > 0) {
          console.log('First 5 element names:',
            Array.from(elements).slice(0, 5).map(el => el.nodeName).join(', '));
        }

        // We'll continue anyway since the XML might still be usable
      }

      // Extract wiki structure
      let title = '';
      let description = '';
      let pages: WikiPage[] = [];

      // Try using DOM parsing first
      const titleEl = xmlDoc.querySelector('title');
      const descriptionEl = xmlDoc.querySelector('description');
      const pagesEls = xmlDoc.querySelectorAll('page');

      title = titleEl ? titleEl.textContent || '' : '';
      description = descriptionEl ? descriptionEl.textContent || '' : '';

      // Parse pages using DOM
      pages = [];

      if (parseError && (!pagesEls || pagesEls.length === 0)) {
        console.warn('DOM parsing failed, trying regex fallback');
      }

      pagesEls.forEach(pageEl => {
        const id = pageEl.getAttribute('id') || `page-${pages.length + 1}`;
        const titleEl = pageEl.querySelector('title');
        const importanceEl = pageEl.querySelector('importance');
        const filePathEls = pageEl.querySelectorAll('file_path');
        const relatedEls = pageEl.querySelectorAll('related');

        const title = titleEl ? titleEl.textContent || '' : '';
        const importance = importanceEl ?
          (importanceEl.textContent === 'high' ? 'high' :
            importanceEl.textContent === 'medium' ? 'medium' : 'low') : 'medium';

        const filePaths: string[] = [];
        filePathEls.forEach(el => {
          if (el.textContent) filePaths.push(el.textContent.trim());
        });

        const relatedPages: string[] = [];
        relatedEls.forEach(el => {
          if (el.textContent) relatedPages.push(el.textContent.trim());
        });

        pages.push({
          id,
          title,
          content: '', // Will be generated later
          filePaths,
          importance,
          relatedPages
        });
      });

      // Fallback: if DOM parsing failed to yield any <page> elements, try a manual regex parser
      if (pages.length === 0) {
        console.warn('DOM parser returned no <page> elements; attempting regex fallback parsing');
        const pageRegex = /<page\b([^>]*)>([\s\S]*?)<\/page>/gi;
        let match: RegExpExecArray | null;
        while ((match = pageRegex.exec(xmlText)) !== null) {
          const [, rawAttributes = '', pageContent = ''] = match;
          const idMatch = rawAttributes.match(/id=["']([^"']+)["']/i);
          const pageId = idMatch ? idMatch[1] : `page-${pages.length + 1}`;

          const titleMatch = pageContent.match(/<title>([\s\S]*?)<\/title>/i);
          const importanceMatch = pageContent.match(/<importance>([\s\S]*?)<\/importance>/i);
          const filePathMatches = [...pageContent.matchAll(/<file_path>([\s\S]*?)<\/file_path>/gi)];
          const relatedMatches = [...pageContent.matchAll(/<related>([\s\S]*?)<\/related>/gi)];

          const titleText = titleMatch ? titleMatch[1].trim() : '';
          const importanceText = importanceMatch ? importanceMatch[1].trim().toLowerCase() : 'medium';
          const importanceValue: 'high' | 'medium' | 'low' =
            importanceText === 'high' ? 'high' :
            importanceText === 'low' ? 'low' : 'medium';

          const filePaths = filePathMatches
            .map(([, path]) => path?.trim())
            .filter((path): path is string => Boolean(path && path.length > 0));

          const relatedPages = relatedMatches
            .map(([, rel]) => rel?.trim())
            .filter((rel): rel is string => Boolean(rel && rel.length > 0));

          pages.push({
            id: pageId,
            title: titleText,
            content: '',
            filePaths,
            importance: importanceValue,
            relatedPages
          });
        }
      }

      if (pages.length === 0) {
        throw new Error('Wiki structure response did not contain any <page> entries. Please try generating the wiki again.');
      }

      // Extract sections if they exist in the XML
      const sections: WikiSection[] = [];
      const rootSections: string[] = [];

      // Try to parse sections if we're in comprehensive view
      if (isComprehensiveView) {
        const sectionsEls = xmlDoc.querySelectorAll('section');

        if (sectionsEls && sectionsEls.length > 0) {
          // Process sections
          sectionsEls.forEach(sectionEl => {
            const id = sectionEl.getAttribute('id') || `section-${sections.length + 1}`;
            const titleEl = sectionEl.querySelector('title');
            const pageRefEls = sectionEl.querySelectorAll('page_ref');
            const sectionRefEls = sectionEl.querySelectorAll('section_ref');

            const title = titleEl ? titleEl.textContent || '' : '';
            const pages: string[] = [];
            const subsections: string[] = [];

            pageRefEls.forEach(el => {
              if (el.textContent) pages.push(el.textContent);
            });

            sectionRefEls.forEach(el => {
              if (el.textContent) subsections.push(el.textContent);
            });

            sections.push({
              id,
              title,
              pages,
              subsections: subsections.length > 0 ? subsections : undefined
            });

            // Check if this is a root section (not referenced by any other section)
            let isReferenced = false;
            sectionsEls.forEach(otherSection => {
              const otherSectionRefs = otherSection.querySelectorAll('section_ref');
              otherSectionRefs.forEach(ref => {
                if (ref.textContent === id) {
                  isReferenced = true;
                }
              });
            });

            if (!isReferenced) {
              rootSections.push(id);
            }
          });
        }
      }

      // Create wiki structure
      const wikiStructure: WikiStructure = {
        id: 'wiki',
        title,
        description,
        pages,
        sections,
        rootSections
      };

      setWikiStructure(wikiStructure);
      setCurrentPageId(pages.length > 0 ? pages[0].id : undefined);

      // Start generating content for all pages with controlled concurrency
      if (pages.length > 0) {
        // Mark all pages as in progress
        const initialInProgress = new Set(pages.map(p => p.id));
        setPagesInProgress(initialInProgress);

        console.log(`Starting generation for ${pages.length} pages with controlled concurrency`);

        // Maximum concurrent requests
        const MAX_CONCURRENT = 1;

        // Create a queue of pages
        const queue = [...pages];
        let activeRequests = 0;

        // Function to process next items in queue
        const processQueue = () => {
          // Process as many items as we can up to our concurrency limit
          while (queue.length > 0 && activeRequests < MAX_CONCURRENT) {
            const page = queue.shift();
            if (page) {
              activeRequests++;
              console.log(`Starting page ${page.title} (${activeRequests} active, ${queue.length} remaining)`);

              // Start generating content for this page
              generatePageContent(page, owner, repo)
                .finally(() => {
                  // When done (success or error), decrement active count and process more
                  activeRequests--;
                  console.log(`Finished page ${page.title} (${activeRequests} active, ${queue.length} remaining)`);

                  // Check if all work is done (queue empty and no active requests)
                  if (queue.length === 0 && activeRequests === 0) {
                    console.log("All page generation tasks completed.");
                    setIsLoading(false);
                    setLoadingMessage(undefined);
                  } else {
                    // Only process more if there are items remaining and we're under capacity
                    if (queue.length > 0 && activeRequests < MAX_CONCURRENT) {
                      processQueue();
                    }
                  }
                });
            }
          }

          // Additional check: If the queue started empty or becomes empty and no requests were started/active
          if (queue.length === 0 && activeRequests === 0 && pages.length > 0 && pagesInProgress.size === 0) {
            // This handles the case where the queue might finish before the finally blocks fully update activeRequests
            // or if the initial queue was processed very quickly
            console.log("Queue empty and no active requests after loop, ensuring loading is false.");
            setIsLoading(false);
            setLoadingMessage(undefined);
          } else if (pages.length === 0) {
            // Handle case where there were no pages to begin with
            setIsLoading(false);
            setLoadingMessage(undefined);
          }
        };

        // Start processing the queue
        processQueue();
      } else {
        // Set loading to false if there were no pages found
        setIsLoading(false);
        setLoadingMessage(undefined);
      }

    } catch (error) {
      console.error('Error determining wiki structure:', error);
      setIsLoading(false);
      setError(error instanceof Error ? error.message : 'An unknown error occurred');
      setLoadingMessage(undefined);
    } finally {
      setStructureRequestInProgress(false);
    }
  }, [generatePageContent, currentToken, effectiveRepoInfo, pagesInProgress.size, structureRequestInProgress, selectedProviderState, selectedModelState, isCustomSelectedModelState, customSelectedModelState, modelExcludedDirs, modelExcludedFiles, modelIncludedDirs, modelIncludedFiles, language, isComprehensiveView]);

  // Fetch repository structure using GitHub
  const fetchRepositoryStructure = useCallback(async () => {
    // If a request is already in progress, don't start another one
    if (requestInProgress) {
      console.log('Repository fetch already in progress, skipping duplicate call');
      return;
    }

    // Reset previous state
    cacheLoadedSuccessfully.current = false;
    setWikiStructure(undefined);
    setCurrentPageId(undefined);
    setGeneratedPages({});
    setPagesInProgress(new Set());
    setError(null);
    setEmbeddingError(false); // Reset embedding error state

    try {
      // Set the request in progress flag
      setRequestInProgress(true);

      // Update loading state
      setIsLoading(true);
      setLoadingMessage('Fetching repository structure...');

      let fileTreeData = '';
      let readmeContent = '';

      if (effectiveRepoInfo.type === 'local' && effectiveRepoInfo.localPath) {
        try {
          const response = await fetch(`/local_repo/structure?path=${encodeURIComponent(effectiveRepoInfo.localPath)}`);

          if (!response.ok) {
            const errorData = await response.text();
            throw new Error(`Local repository API error (${response.status}): ${errorData}`);
          }

          const data = await response.json();
          fileTreeData = data.file_tree;
          readmeContent = data.readme;
          // For local repos, we can't determine the actual branch, so use 'main' as default
          setDefaultBranch('main');
        } catch (err) {
          throw err;
        }
      } else if (effectiveRepoInfo.type === 'github') {
        // Use backend endpoint which uses GITHUB_TOKEN from environment
        try {
          const params = new URLSearchParams({
            owner: owner,
            repo: repo,
          });

          if (effectiveRepoInfo.repoUrl) {
            params.append('repo_url', effectiveRepoInfo.repoUrl);
          }

          const response = await fetch(`/api/github/repo/structure?${params.toString()}`);

          if (!response.ok) {
            const errorData = await response.text();
            throw new Error(`Repository structure API error (${response.status}): ${errorData}`);
          }

          const data = await response.json();
          fileTreeData = data.file_tree;
          readmeContent = data.readme;
          setDefaultBranch(data.default_branch || 'main');
          console.log(`Successfully fetched repository structure from backend`);
        } catch (err) {
          throw err;
        }
      }



      // Now determine the wiki structure
      await determineWikiStructure(fileTreeData, readmeContent, owner, repo);

    } catch (error) {
      console.error('Error fetching repository structure:', error);
      setIsLoading(false);
      setError(error instanceof Error ? error.message : 'An unknown error occurred');
      setLoadingMessage(undefined);
    } finally {
      // Reset the request in progress flag
      setRequestInProgress(false);
    }
  }, [owner, repo, determineWikiStructure, effectiveRepoInfo, requestInProgress]);

  // Function to export wiki content
  const exportWiki = useCallback(async (format: 'markdown' | 'json') => {
    if (!wikiStructure || Object.keys(generatedPages).length === 0) {
      setExportError('No wiki content to export');
      return;
    }

    try {
      setIsExporting(true);
      setExportError(null);
      setLoadingMessage(`Exporting wiki as ${format}...`);

      // Prepare the pages for export
      const pagesToExport = wikiStructure.pages.map(page => {
        // Use the generated content if available, otherwise use an empty string
        const content = generatedPages[page.id]?.content || 'Content not generated';
        return {
          ...page,
          content
        };
      });

      // Get repository URL
      const repoUrl = getRepoUrl(effectiveRepoInfo);

      // Make API call to export wiki
      const response = await fetch(`/export/wiki`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repo_url: repoUrl,
          type: effectiveRepoInfo.type,
          pages: pagesToExport,
          format
        })
      });

      if (!response.ok) {
        const errorText = await response.text().catch(() => 'No error details available');
        throw new Error(`Error exporting wiki: ${response.status} - ${errorText}`);
      }

      // Get the filename from the Content-Disposition header if available
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `${effectiveRepoInfo.repo}_wiki.${format === 'markdown' ? 'md' : 'json'}`;

      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename=(.+)/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1].replace(/"/g, '');
        }
      }

      // Convert the response to a blob and download it
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

    } catch (err) {
      console.error('Error exporting wiki:', err);
      const errorMessage = err instanceof Error ? err.message : 'Unknown error during export';
      setExportError(errorMessage);
    } finally {
      setIsExporting(false);
      setLoadingMessage(undefined);
    }
  }, [wikiStructure, generatedPages, effectiveRepoInfo]);

  // No longer needed as we use the modal directly

  const handleFeedbackChange = useCallback((pageId: string, value: string) => {
    setPageFeedbackDrafts(prev => ({ ...prev, [pageId]: value }));
  }, []);

  const handleClearPageFeedback = useCallback((pageId: string) => {
    setPageFeedbackDrafts(prev => {
      const next = { ...prev };
      delete next[pageId];
      return next;
    });
    setPageRefreshMessages(prev => {
      const next = { ...prev };
      delete next[pageId];
      return next;
    });
  }, []);

  const handleRefreshPage = useCallback(async (pageId: string) => {
    if (!wikiStructure) {
      return;
    }

    const page = wikiStructure.pages.find(p => p.id === pageId);
    if (!page) {
      return;
    }

    const feedback = pageFeedbackDrafts[pageId]?.trim() || '';

    setPageRefreshMessages(prev => {
      const next = { ...prev };
      delete next[pageId];
      return next;
    });

    cacheLoadedSuccessfully.current = false;
    setLoadingMessage(`Refreshing "${page.title}"...`);
    const success = await generatePageContent(page, owner, repo, { force: true, feedback });
    setLoadingMessage(undefined);

    setPageRefreshMessages(prev => ({
      ...prev,
      [pageId]: success
        ? { type: 'success', text: 'Page refreshed successfully.' }
        : { type: 'error', text: 'Failed to refresh page. Please review the logs and try again.' }
    }));
  }, [wikiStructure, pageFeedbackDrafts, generatePageContent, owner, repo]);

  const confirmRefresh = useCallback(async (newToken?: string) => {
    setShowModelOptions(false);
    setLoadingMessage('Clearing server cache...');
    setIsLoading(true); // Show loading indicator immediately

    try {
      const params = new URLSearchParams({
        owner: effectiveRepoInfo.owner,
        repo: effectiveRepoInfo.repo,
        repo_type: effectiveRepoInfo.type,
        language: language,
        provider: selectedProviderState,
        model: selectedModelState,
        is_custom_model: isCustomSelectedModelState.toString(),
        custom_model: customSelectedModelState,
        comprehensive: isComprehensiveView.toString(),
      });

      // Add file filters configuration
      if (modelExcludedDirs) {
        params.append('excluded_dirs', modelExcludedDirs);
      }
      if (modelExcludedFiles) {
        params.append('excluded_files', modelExcludedFiles);
      }

      const response = await fetch(`/api/wiki_cache?${params.toString()}`, {
        method: 'DELETE',
        headers: {
          'Accept': 'application/json',
        }
      });

      if (response.ok) {
        console.log('Server-side wiki cache cleared successfully.');
        // Optionally, show a success message for cache clearing if desired
        // setLoadingMessage('Cache cleared. Refreshing wiki...');
      } else {
        const errorText = await response.text();
        console.warn(`Failed to clear server-side wiki cache (status: ${response.status}): ${errorText}. Proceeding with refresh anyway.`);
        // Optionally, inform the user about the cache clear failure but that refresh will still attempt
        // setError(\`Cache clear failed: ${errorText}. Trying to refresh...\`);
        if (response.status == 401) {
          setIsLoading(false);
          setLoadingMessage(undefined);
          setError('Failed to validate the authorization code');
          console.error('Failed to validate the authorization code')
          return;
        }
      }
    } catch (err) {
      console.warn('Error calling DELETE /api/wiki_cache:', err);
      setIsLoading(false);
      setEmbeddingError(false); // Reset embedding error state
      // Optionally, inform the user about the cache clear error
      // setError(\`Error clearing cache: ${err instanceof Error ? err.message : String(err)}. Trying to refresh...\`);
      throw err;
    }

    // Update token if provided
    if (newToken) {
      // Update current token state
      setCurrentToken(newToken);
      // Update the URL parameters to include the new token
      const currentUrl = new URL(window.location.href);
      currentUrl.searchParams.set('token', newToken);
      window.history.replaceState({}, '', currentUrl.toString());
    }

    // Proceed with the rest of the refresh logic
    console.log('Refreshing wiki. Server cache will be overwritten upon new generation if not cleared.');

    // Clear the localStorage cache (if any remnants or if it was used before this change)
    if (typeof window !== 'undefined' && typeof localStorage !== 'undefined' && typeof localStorage.removeItem === 'function') {
      const localStorageCacheKey = getCacheKey(effectiveRepoInfo.owner, effectiveRepoInfo.repo, effectiveRepoInfo.type, language, isComprehensiveView);
      localStorage.removeItem(localStorageCacheKey);
    }

    // Reset cache loaded flag
    cacheLoadedSuccessfully.current = false;
    effectRan.current = false; // Allow the main data loading useEffect to run again

    // Reset all state
    setWikiStructure(undefined);
    setCurrentPageId(undefined);
    setGeneratedPages({});
    setPagesInProgress(new Set());
    setError(null);
    setEmbeddingError(false); // Reset embedding error state
    setIsLoading(true); // Set loading state for refresh
    setLoadingMessage('Initializing wiki generation...');

    // Clear any in-progress requests for page content
    activeContentRequests.clear();
    // Reset flags related to request processing if they are component-wide
    setStructureRequestInProgress(false); // Assuming this flag should be reset
    setRequestInProgress(false); // Assuming this flag should be reset

    // Explicitly trigger the data loading process again by re-invoking what the main useEffect does.
    // This will first attempt to load from (now hopefully non-existent or soon-to-be-overwritten) server cache,
    // then proceed to fetchRepositoryStructure if needed.
    // To ensure fetchRepositoryStructure is called if cache is somehow still there or to force a full refresh:
    // One option is to directly call fetchRepositoryStructure() if force refresh means bypassing cache check.
    // For now, we rely on the standard loadData flow initiated by resetting effectRan and dependencies.
    // This will re-trigger the main data loading useEffect.
    // No direct call to fetchRepositoryStructure here, let the useEffect handle it based on effectRan.current = false.
  }, [effectiveRepoInfo, language, activeContentRequests, selectedProviderState, selectedModelState, isCustomSelectedModelState, customSelectedModelState, modelExcludedDirs, modelExcludedFiles, isComprehensiveView]);

  // Start wiki generation when component mounts
  useEffect(() => {
    if (effectRan.current === false) {
      effectRan.current = true; // Set to true immediately to prevent re-entry due to StrictMode

      const loadData = async () => {
        // Try loading from server-side cache first
        setLoadingMessage('Checking for cached wiki...');
        try {
          const params = new URLSearchParams({
            owner: effectiveRepoInfo.owner,
            repo: effectiveRepoInfo.repo,
            repo_type: effectiveRepoInfo.type,
            language: language,
            comprehensive: isComprehensiveView.toString(),
          });
          const response = await fetch(`/api/wiki_cache?${params.toString()}`);

          if (response.ok) {
            const cachedData = await response.json(); // Returns null if no cache
            if (cachedData && cachedData.wiki_structure && cachedData.generated_pages && Object.keys(cachedData.generated_pages).length > 0) {
              console.log('Using server-cached wiki data');
              if (cachedData.model) {
                setSelectedModelState(cachedData.model);
              }
              if (cachedData.provider) {
                setSelectedProviderState(cachedData.provider);
              }

              // Update repoInfo
              if (cachedData.repo) {
                setEffectiveRepoInfo(cachedData.repo);
              } else if (cachedData.repo_url && !effectiveRepoInfo.repoUrl) {
                const updatedRepoInfo = { ...effectiveRepoInfo, repoUrl: cachedData.repo_url };
                setEffectiveRepoInfo(updatedRepoInfo); // Update effective repo info state
                console.log('Using cached repo_url:', cachedData.repo_url);
              }

              // Ensure the cached structure has sections and rootSections
              const cachedStructure = {
                ...cachedData.wiki_structure,
                sections: cachedData.wiki_structure.sections || [],
                rootSections: cachedData.wiki_structure.rootSections || []
              };

              // If sections or rootSections are missing, create intelligent ones based on page titles
              if (!cachedStructure.sections.length || !cachedStructure.rootSections.length) {
                const pages = cachedStructure.pages;
                const sections: WikiSection[] = [];
                const rootSections: string[] = [];

                // Group pages by common prefixes or categories
                const pageClusters = new Map<string, WikiPage[]>();

                // Define common categories that might appear in page titles
                const categories = [
                  { id: 'overview', title: 'Overview', keywords: ['overview', 'introduction', 'about'] },
                  { id: 'architecture', title: 'Architecture', keywords: ['architecture', 'structure', 'design', 'system'] },
                  { id: 'features', title: 'Core Features', keywords: ['feature', 'functionality', 'core'] },
                  { id: 'components', title: 'Components', keywords: ['component', 'module', 'widget'] },
                  { id: 'api', title: 'API', keywords: ['api', 'endpoint', 'service', 'server'] },
                  { id: 'data', title: 'Data Flow', keywords: ['data', 'flow', 'pipeline', 'storage'] },
                  { id: 'models', title: 'Models', keywords: ['model', 'ai', 'ml', 'integration'] },
                  { id: 'ui', title: 'User Interface', keywords: ['ui', 'interface', 'frontend', 'page'] },
                  { id: 'setup', title: 'Setup & Configuration', keywords: ['setup', 'config', 'installation', 'deploy'] }
                ];

                // Initialize clusters with empty arrays
                categories.forEach(category => {
                  pageClusters.set(category.id, []);
                });

                // Add an "Other" category for pages that don't match any category
                pageClusters.set('other', []);

                // Assign pages to categories based on title keywords
                pages.forEach((page: WikiPage) => {
                  const title = page.title.toLowerCase();
                  let assigned = false;

                  // Try to find a matching category
                  for (const category of categories) {
                    if (category.keywords.some(keyword => title.includes(keyword))) {
                      pageClusters.get(category.id)?.push(page);
                      assigned = true;
                      break;
                    }
                  }

                  // If no category matched, put in "Other"
                  if (!assigned) {
                    pageClusters.get('other')?.push(page);
                  }
                });

                // Create sections for non-empty categories
                for (const [categoryId, categoryPages] of pageClusters.entries()) {
                  if (categoryPages.length > 0) {
                    const category = categories.find(c => c.id === categoryId) ||
                      { id: categoryId, title: categoryId === 'other' ? 'Other' : categoryId.charAt(0).toUpperCase() + categoryId.slice(1) };

                    const sectionId = `section-${categoryId}`;
                    sections.push({
                      id: sectionId,
                      title: category.title,
                      pages: categoryPages.map((p: WikiPage) => p.id)
                    });
                    rootSections.push(sectionId);

                    // Update page parentId
                    categoryPages.forEach((page: WikiPage) => {
                      page.parentId = sectionId;
                    });
                  }
                }

                // If we still have no sections (unlikely), fall back to importance-based grouping
                if (sections.length === 0) {
                  const highImportancePages = pages.filter((p: WikiPage) => p.importance === 'high').map((p: WikiPage) => p.id);
                  const mediumImportancePages = pages.filter((p: WikiPage) => p.importance === 'medium').map((p: WikiPage) => p.id);
                  const lowImportancePages = pages.filter((p: WikiPage) => p.importance === 'low').map((p: WikiPage) => p.id);

                  if (highImportancePages.length > 0) {
                    sections.push({
                      id: 'section-high',
                      title: 'Core Components',
                      pages: highImportancePages
                    });
                    rootSections.push('section-high');
                  }

                  if (mediumImportancePages.length > 0) {
                    sections.push({
                      id: 'section-medium',
                      title: 'Key Features',
                      pages: mediumImportancePages
                    });
                    rootSections.push('section-medium');
                  }

                  if (lowImportancePages.length > 0) {
                    sections.push({
                      id: 'section-low',
                      title: 'Additional Information',
                      pages: lowImportancePages
                    });
                    rootSections.push('section-low');
                  }
                }

                cachedStructure.sections = sections;
                cachedStructure.rootSections = rootSections;
              }

              setWikiStructure(cachedStructure);
              setGeneratedPages(cachedData.generated_pages);
              setCurrentPageId(cachedStructure.pages.length > 0 ? cachedStructure.pages[0].id : undefined);
              setIsLoading(false);
              setEmbeddingError(false);
              setLoadingMessage(undefined);
              cacheLoadedSuccessfully.current = true;
              return; // Exit if cache is successfully loaded
            } else {
              console.log('No valid wiki data in server cache or cache is empty.');
            }
          } else {
            // Log error but proceed to fetch structure, as cache is optional
            console.error('Error fetching wiki cache from server:', response.status, await response.text());
          }
        } catch (error) {
          console.error('Error loading from server cache:', error);
          // Proceed to fetch structure if cache loading fails
        }

        // If we reached here, either there was no cache, it was invalid, or an error occurred
        // Proceed to fetch repository structure
        fetchRepositoryStructure();
      };

      loadData();

    } else {
      console.log('Skipping duplicate repository fetch/cache check');
    }

    // Clean up function for this effect is not strictly necessary for loadData,
    // but keeping the main unmount cleanup in the other useEffect
  }, [effectiveRepoInfo, effectiveRepoInfo.owner, effectiveRepoInfo.repo, effectiveRepoInfo.type, language, fetchRepositoryStructure, isComprehensiveView]);

  // Save wiki to server-side cache when generation is complete
  useEffect(() => {
    if (!isLoading && !error && !cacheLoadedSuccessfully.current) {
      void persistWikiCache();
    }
  }, [isLoading, error, generatedPages, persistWikiCache]);

const handlePageSelect = (pageId: string) => {
  if (currentPageId != pageId) {
    setCurrentPageId(pageId)
  }
};

const totalPages = wikiStructure?.pages.length ?? 0;
const completedPages = wikiStructure ? wikiStructure.pages.length - pagesInProgress.size : 0;
const progressPercent = totalPages > 0
  ? Math.min(100, Math.max(0, Math.round((completedPages / totalPages) * 100)))
  : 0;

const [isModelSelectionModalOpen, setIsModelSelectionModalOpen] = useState(false);

  return (
    <div className="h-screen paper-texture p-4 md:p-8 flex flex-col">
      <style>{wikiStyles}</style>

      <header className="max-w-[90%] xl:max-w-[1400px] mx-auto mb-8 h-fit w-full">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="text-[var(--accent-primary)] hover:text-[var(--highlight)] flex items-center gap-1.5 transition-colors border-b border-[var(--border-color)] hover:border-[var(--accent-primary)] pb-0.5">
              <FaHome /> Home
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-[90%] xl:max-w-[1400px] mx-auto overflow-y-auto">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center p-8 bg-[var(--card-bg)] rounded-lg shadow-custom border border-[var(--border-color)]/60">
            <div className="relative w-20 h-20 mb-6 flex items-center justify-center">
              <div className="absolute inset-0 rounded-full border-2 border-[var(--accent-primary)]/15"></div>
              <div
                className="absolute inset-3 rounded-full border-t-2 border-[var(--accent-primary)]/70 border-l-transparent border-r-transparent border-b-transparent animate-spin"
                style={{ animationDuration: '1.4s' }}
              ></div>
              <div className="relative w-4 h-4 rounded-full bg-[var(--accent-primary)] animate-[floatPulse_1.6s_ease-in-out_infinite]"></div>
            </div>
            <p className="text-[var(--foreground)] text-center mb-1 font-serif text-sm md:text-base transition-opacity duration-300">
              {loadingMessage || 'Preparing your wiki...'}
            </p>
            {isExporting && (
              <p className="text-xs text-[var(--muted)] mb-2">Packaging export files…</p>
            )}

            {/* Progress bar for page generation */}
            {wikiStructure && totalPages > 0 ? (
              <div className="w-full max-w-md mt-4">
                <div className="relative h-2 rounded-full bg-[var(--background)]/70 border border-[var(--border-color)] overflow-hidden">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full bg-[var(--accent-primary)]/85 transition-all duration-500 ease-out"
                    style={{ width: `${Math.max(8, progressPercent)}%` }}
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/70 to-transparent opacity-70 animate-[shimmer_1.4s_linear_infinite]" />
                  </div>
                </div>
                <div className="flex justify-between text-xs text-[var(--muted)] mt-3">
                  <span>{completedPages} of {totalPages} pages ready</span>
                  <span>{progressPercent}%</span>
                </div>

                {/* Show list of in-progress pages */}
                {pagesInProgress.size > 0 && (
                  <div className="mt-4 text-xs">
                    <p className="text-[var(--muted)] mb-2">
                      Currently processing:
                    </p>
                    <ul className="text-[var(--foreground)] space-y-1">
                      {Array.from(pagesInProgress).slice(0, 4).map(pageId => {
                        const page = wikiStructure.pages.find(p => p.id === pageId);
                        return page ? (
                          <li key={pageId} className="flex items-center gap-2 truncate">
                            <span className="h-2.5 w-2.5 rounded-full bg-[var(--accent-primary)]/80 animate-[floatPulse_1.8s_ease-in-out_infinite]" />
                            <span className="truncate">{page.title}</span>
                          </li>
                        ) : null;
                      })}
                      {pagesInProgress.size > 4 && (
                        <li className="text-[var(--muted)]">
                          {`...and ${pagesInProgress.size - 4} more`}
                        </li>
                      )}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-[var(--muted)] mt-4 animate-pulse">Discovering wiki structure…</p>
            )}
          </div>
        ) : error ? (
          <div className="bg-[var(--highlight)]/5 border border-[var(--highlight)]/30 rounded-lg p-5 mb-4 shadow-sm">
            <div className="flex items-center text-[var(--highlight)] mb-3">
              <FaExclamationTriangle className="mr-2" />
              <span className="font-bold font-serif">Error</span>
            </div>
            <p className="text-[var(--foreground)] text-sm mb-3">{error}</p>
            <p className="text-[var(--muted)] text-xs">
              {embeddingError ? (
                'This error is related to the document embedding system used for analyzing your repository. Please verify your embedding model configuration, API keys, and try again. If the issue persists, consider switching to a different embedding provider in the model settings.'
              ) : (
                'Please check that your repository exists and is public. Valid formats are "owner/repo", "https://github.com/owner/repo", or local folder paths like "C:\\path\\to\\folder" or "/path/to/folder".'
              )}
            </p>
            <div className="mt-5">
              <Link
                href="/"
                className="px-5 py-2 inline-flex items-center gap-1.5 bg-[var(--accent-primary)] text-white rounded-md hover:bg-[var(--highlight)] transition-colors"
              >
                <FaHome className="text-sm" />
                Back to Home
              </Link>
            </div>
          </div>
        ) : wikiStructure ? (
          <div className="h-full overflow-y-auto flex flex-col lg:flex-row gap-4 w-full overflow-hidden bg-[var(--card-bg)] rounded-lg shadow-custom">
            {/* Wiki Navigation */}
            <div className="h-full w-full lg:w-[280px] xl:w-[320px] flex-shrink-0 bg-[var(--background)]/50 rounded-lg rounded-r-none p-5 border-b lg:border-b-0 lg:border-r border-[var(--border-color)] overflow-y-auto">
              <h3 className="text-lg font-bold text-[var(--foreground)] mb-3 font-serif">{wikiStructure.title}</h3>
              <p className="text-[var(--muted)] text-sm mb-5 leading-relaxed">{wikiStructure.description}</p>

              {/* Display repository info */}
              <div className="text-xs text-[var(--muted)] mb-5 flex items-center">
                {effectiveRepoInfo.type === 'local' ? (
                  <div className="flex items-center">
                    <FaFolder className="mr-2" />
                    <span className="break-all">{effectiveRepoInfo.localPath}</span>
                  </div>
                ) : (
                  <>
                    <FaGithub className="mr-2" />
                    <a
                      href={effectiveRepoInfo.repoUrl ?? ''}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-[var(--accent-primary)] transition-colors border-b border-[var(--border-color)] hover:border-[var(--accent-primary)]"
                    >
                      {effectiveRepoInfo.owner}/{effectiveRepoInfo.repo}
                    </a>
                  </>
                )}
              </div>

              {/* Wiki Type Indicator */}
              <div className="mb-3 flex items-center text-xs text-[var(--muted)]">
                <span className="mr-2">Wiki Type:</span>
                <span className={`px-2 py-0.5 rounded-full ${isComprehensiveView
                  ? 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border border-[var(--accent-primary)]/30'
                  : 'bg-[var(--background)] text-[var(--foreground)] border border-[var(--border-color)]'}`}>
                  {isComprehensiveView
                    ? 'Comprehensive'
                    : 'Concise'}
                </span>
              </div>

              {/* Refresh Wiki button */}
              <div className="mb-5">
                <button
                  onClick={() => setIsModelSelectionModalOpen(true)}
                  disabled={isLoading}
                  className="flex items-center w-full text-xs px-3 py-2 bg-[var(--background)] text-[var(--foreground)] rounded-md hover:bg-[var(--background)]/80 disabled:opacity-50 disabled:cursor-not-allowed border border-[var(--border-color)] transition-colors hover:cursor-pointer"
                >
                  <FaSync className={`mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                  Refresh Wiki
                </button>
              </div>

              {/* Export buttons */}
              {Object.keys(generatedPages).length > 0 && (
                <div className="mb-5">
                  <h4 className="text-sm font-semibold text-[var(--foreground)] mb-3 font-serif">
                    Export Wiki
                  </h4>
                  <div className="flex flex-col gap-2">
                    <button
                      onClick={() => exportWiki('markdown')}
                      disabled={isExporting}
                      className="flex items-center text-xs px-3 py-2 rounded-md disabled:opacity-50 disabled:cursor-not-allowed bg-[var(--accent-primary)] text-white hover:bg-[var(--highlight)] transition-colors"
                    >
                      <FaDownload className="mr-2" />
                      Export as Markdown
                    </button>
                    <button
                      onClick={() => exportWiki('json')}
                      disabled={isExporting}
                      className="flex items-center text-xs px-3 py-2 bg-[var(--background)] text-[var(--foreground)] rounded-md hover:bg-[var(--background)]/80 disabled:opacity-50 disabled:cursor-not-allowed border border-[var(--border-color)] transition-colors"
                    >
                      <FaFileExport className="mr-2" />
                      Export as JSON
                    </button>
                  </div>
                  {exportError && (
                    <div className="mt-2 text-xs text-[var(--highlight)]">
                      {exportError}
                    </div>
                  )}
                </div>
              )}

              <h4 className="text-md font-semibold text-[var(--foreground)] mb-3 font-serif">
                Pages
              </h4>
              <WikiTreeView
                wikiStructure={wikiStructure}
                currentPageId={currentPageId}
                onPageSelect={handlePageSelect}
              />
            </div>

            {/* Wiki Content */}
            <div id="wiki-content" className="w-full flex-grow p-6 lg:p-8 overflow-y-auto">
              {currentPageId && generatedPages[currentPageId] ? (
                <div className="max-w-[900px] xl:max-w-[1000px] mx-auto">
                  <h3 className="text-xl font-bold text-[var(--foreground)] mb-4 break-words font-serif">
                    {generatedPages[currentPageId].title}
                  </h3>

                  <details className="mb-6 border border-[var(--border-color)] bg-[var(--background)]/50 rounded-lg shadow-sm">
                    <summary className="p-4 cursor-pointer hover:bg-[var(--background)]/70 transition-colors rounded-lg">
                      <h4 className="text-sm font-semibold text-[var(--foreground)] font-serif inline-block">
                        Refresh this page
                      </h4>
                      <span className="text-xs text-[var(--muted)] ml-2">
                        (Add notes about what needs to change, then regenerate)
                      </span>
                    </summary>
                    <div className="px-4 pb-4">
                      <p className="text-xs text-[var(--muted)] mb-3 mt-2">
                        Add notes about what needs to change, then regenerate the page with those fixes.
                      </p>
                      <textarea
                        className="w-full h-24 text-sm rounded-md border border-[var(--border-color)] bg-[var(--card-bg)] p-2 focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/30 focus:border-[var(--accent-primary)] transition-colors resize-y"
                        placeholder="Describe corrections, missing details, or updates you'd like to see..."
                      value={pageFeedbackDrafts[currentPageId] ?? ''}
                      onChange={(event) => handleFeedbackChange(currentPageId, event.target.value)}
                    />
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        onClick={() => handleRefreshPage(currentPageId)}
                        disabled={pagesInProgress.has(currentPageId)}
                        className="px-4 py-2 text-xs font-medium rounded-md border border-transparent bg-[var(--accent-primary)] text-white hover:bg-[var(--highlight)] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
                      >
                        {pagesInProgress.has(currentPageId) ? (
                          <span className="flex items-center gap-2">
                            <span className="h-3 w-3 rounded-full border-2 border-white/40 border-t-transparent animate-spin"></span>
                            Refreshing…
                          </span>
                        ) : (
                          'Refresh Page'
                        )}
                      </button>
                      <button
                        onClick={() => handleClearPageFeedback(currentPageId)}
                        className="px-4 py-2 text-xs font-medium rounded-md border border-[var(--border-color)] text-[var(--muted)] hover:bg-[var(--background)] transition-colors"
                      >
                          Clear Feedback
                        </button>
                      </div>
                      {pageRefreshMessages[currentPageId] && (
                        <div
                          className={`mt-2 text-xs ${
                            pageRefreshMessages[currentPageId]?.type === 'error'
                              ? 'text-[var(--highlight)]'
                              : 'text-green-600 dark:text-green-400'
                          }`}
                        >
                          {pageRefreshMessages[currentPageId]?.text}
                        </div>
                      )}
                    </div>
                  </details>

                  <div className="prose prose-sm md:prose-base lg:prose-lg max-w-none">
                    <Markdown
                      content={generatedPages[currentPageId].content}
                    />
                  </div>

                  {generatedPages[currentPageId].relatedPages.length > 0 && (
                    <div className="mt-8 pt-4 border-t border-[var(--border-color)]">
                      <h4 className="text-sm font-semibold text-[var(--muted)] mb-3">
                        Related Pages:
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {generatedPages[currentPageId].relatedPages.map(relatedId => {
                          const relatedPage = wikiStructure.pages.find(p => p.id === relatedId);
                          return relatedPage ? (
                            <button
                              key={relatedId}
                              className="bg-[var(--accent-primary)]/10 hover:bg-[var(--accent-primary)]/20 text-xs text-[var(--accent-primary)] px-3 py-1.5 rounded-md transition-colors truncate max-w-full border border-[var(--accent-primary)]/20"
                              onClick={() => handlePageSelect(relatedId)}
                            >
                              {relatedPage.title}
                            </button>
                          ) : null;
                        })}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center p-8 text-[var(--muted)] h-full">
                  <div className="relative mb-4">
                    <div className="absolute -inset-2 bg-[var(--accent-primary)]/5 rounded-full blur-md"></div>
                    <FaBookOpen className="text-4xl relative z-10" />
                  </div>
                  <p className="font-serif">
                    Select a page from the navigation to view its content
                  </p>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </main>

      <footer className="max-w-[90%] xl:max-w-[1400px] mx-auto mt-8 flex flex-col gap-4 w-full">
        <div className="flex justify-between items-center gap-4 text-center text-[var(--muted)] text-sm h-fit w-full bg-[var(--card-bg)] rounded-lg p-3 shadow-sm border border-[var(--border-color)]">
          <p className="flex-1 font-serif">
            OpenCorporates DeepWiki - Generate Wiki from GitHub repositories
          </p>
          <ThemeToggle />
        </div>
      </footer>

      <ModelSelectionModal
        isOpen={isModelSelectionModalOpen}
        onClose={() => setIsModelSelectionModalOpen(false)}
        provider={selectedProviderState}
        setProvider={setSelectedProviderState}
        model={selectedModelState}
        setModel={setSelectedModelState}
        isCustomModel={isCustomSelectedModelState}
        setIsCustomModel={setIsCustomSelectedModelState}
        customModel={customSelectedModelState}
        setCustomModel={setCustomSelectedModelState}
        isComprehensiveView={isComprehensiveView}
        setIsComprehensiveView={setIsComprehensiveView}
        showFileFilters={true}
        excludedDirs={modelExcludedDirs}
        setExcludedDirs={setModelExcludedDirs}
        excludedFiles={modelExcludedFiles}
        setExcludedFiles={setModelExcludedFiles}
        includedDirs={modelIncludedDirs}
        setIncludedDirs={setModelIncludedDirs}
        includedFiles={modelIncludedFiles}
        setIncludedFiles={setModelIncludedFiles}
        onApply={confirmRefresh}
        showWikiType={true}
        repositoryType="github"
      />
    </div>
  );
}
