'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { FaGithub } from 'react-icons/fa';
import Mermaid from './Mermaid';
import terracottaPrismTheme from '@/styles/prismTheme';

interface MarkdownProps {
  content: string;
  repoUrl?: string;
  defaultBranch?: string;
  wikiPages?: Array<{ id: string; title: string }>;
  onPageSelect?: (pageId: string) => void;
}

const Markdown: React.FC<MarkdownProps> = ({ content, repoUrl, defaultBranch = 'main', wikiPages = [], onPageSelect }) => {
  // Helper function to generate GitHub URL for source references
  const generateSourceUrl = (filePath: string, lineRange?: string): string | undefined => {
    if (!repoUrl) return undefined;

    try {
      const url = new URL(repoUrl);
      const hostname = url.hostname.toLowerCase();

      if (hostname === 'github.com' || hostname.includes('github')) {
        // GitHub URL format: https://github.com/owner/repo/blob/branch/path#Lstart-Lend
        let githubUrl = `${repoUrl}/blob/${defaultBranch}/${filePath}`;

        if (lineRange) {
          // Parse line range (e.g., "1-10" or "5")
          const rangeMatch = lineRange.match(/^(\d+)(?:-(\d+))?$/);
          if (rangeMatch) {
            const startLine = rangeMatch[1];
            const endLine = rangeMatch[2] || startLine;
            githubUrl += `#L${startLine}-L${endLine}`;
          }
        }

        return githubUrl;
      }
    } catch (error) {
      console.warn('Error generating source URL:', error);
    }

    return undefined;
  };

  const extractTextContent = (node: React.ReactNode): string => {
    if (typeof node === 'string' || typeof node === 'number') {
      return String(node);
    }

    if (Array.isArray(node)) {
      return node.map(extractTextContent).join('');
    }

    if (React.isValidElement<{ children?: React.ReactNode }>(node)) {
      return extractTextContent(node.props.children);
    }

    return '';
  };

  // Helper function to check if a link is a source reference
  const isSourceReference = (href: string | undefined, children: React.ReactNode): boolean => {
    // Source references have empty href or undefined href
    if (href && href !== '') return false;

    // Check if the link text matches the source reference pattern
    // Matches: file.ext, file.ext:123, file.ext:1-10, dir/file.ext, etc.
    const text = extractTextContent(children).trim();

    // More flexible pattern: file path (with optional directory) with optional line numbers or section names
    // Also handles cases like "file.ext:Section Name" by checking for file extension
    // Pattern: starts with file path (may contain slashes), has extension, optionally followed by colon and anything
    return /^[^\s\[\]]+\.\w+(?::[^\s\[\]]*)?$/.test(text);
  };

  // Preprocess content to ensure "Sources:" appears on a new line and fix source references
  let preprocessedContent = content;

  // Step 1: Normalize "Source:" to "Sources:" for consistency
  preprocessedContent = preprocessedContent.replace(/\bSource:\s*/g, 'Sources: ');

  // Step 2: Ensure "Sources:" appears on a new line
  preprocessedContent = preprocessedContent.replace(/([^\n])\s*Sources:\s*/g, '$1\n\nSources: ');

  // Step 3: Fix malformed source references and convert plain text to markdown links
  // Handle patterns like:
  // - Sources: file.ext (plain text)
  // - Sources: [file.ext:Section] (brackets without link)
  // - Sources: file.ext:Section Name (plain text with section)
  // - Sources: file.ext.file.ext:1-200 (concatenated)
  // - Sources: file.ext, file2.ext (multiple plain text)
  preprocessedContent = preprocessedContent.replace(
    /Sources:\s*([^\n]+)/g,
    (match, sourcesText) => {
      // Split by comma to handle multiple sources, but be careful with commas inside brackets
      const sources: string[] = [];
      let currentSource = '';
      let bracketDepth = 0;

      for (let i = 0; i < sourcesText.length; i++) {
        const char = sourcesText[i];
        if (char === '[') bracketDepth++;
        if (char === ']') bracketDepth--;

        if (char === ',' && bracketDepth === 0) {
          if (currentSource.trim()) {
            sources.push(currentSource.trim());
          }
          currentSource = '';
        } else {
          currentSource += char;
        }
      }
      if (currentSource.trim()) {
        sources.push(currentSource.trim());
      }

      // Process each source
      const convertedSources = sources.map((src: string) => {
        let trimmed = src.trim();

        // Skip if empty
        if (!trimmed) return '';

        // Fix concatenated references like "file.ext.file.ext:1-200"
        // Try to detect and split them
        const concatenatedMatch = trimmed.match(/^([^\s\.]+\.\w+)\.([^\s\.]+\.\w+.*)$/);
        if (concatenatedMatch) {
          // Split into two separate references
          const firstPart = concatenatedMatch[1];
          const secondPart = concatenatedMatch[2];
          return `[${firstPart}](), [${secondPart}]()`;
        }

        // If already a proper markdown link [text](), keep it but fix malformed text
        if (trimmed.match(/^\[.+\]\(\)$/)) {
          // Check if link text contains multiple file references (malformed)
          const linkMatch = trimmed.match(/^\[(.+)\]\(\)$/);
          if (linkMatch) {
            const linkText = linkMatch[1];
            // If it contains multiple file references separated by space or period
            const multipleFiles = linkText.match(/([^\s\.]+\.\w+(?::[^\s]*)?)/g);
            if (multipleFiles && multipleFiles.length > 1) {
              // Split into multiple links
              return multipleFiles.map(f => `[${f}]()`).join(', ');
            }
          }
          return trimmed;
        }

        // If in brackets but missing the link part, add it: [text] -> [text]()
        if (trimmed.match(/^\[.+\]$/)) {
          const bracketMatch = trimmed.match(/^\[(.+)\]$/);
          if (bracketMatch) {
            const innerText = bracketMatch[1];
            // Check if inner text contains multiple references
            const multipleFiles = innerText.match(/([^\s\.]+\.\w+(?::[^\s]*)?)/g);
            if (multipleFiles && multipleFiles.length > 1) {
              return multipleFiles.map(f => `[${f}]()`).join(', ');
            }
          }
          return trimmed + '()';
        }

        // If it's a plain file path (contains .ext), convert to markdown link
        if (trimmed.match(/[^\s\[\]]+\.\w+/)) {
          return `[${trimmed}]()`;
        }

        // Otherwise return as-is
        return trimmed;
      }).filter((s: string) => s.length > 0);

      return `Sources: ${convertedSources.join(', ')}`;
    }
  );

  // Define markdown components
  const MarkdownComponents: React.ComponentProps<typeof ReactMarkdown>['components'] = {
    p({ children, ...props }: { children?: React.ReactNode }) {
      return <p className="mb-3 text-sm leading-relaxed text-[var(--foreground)]" {...props}>{children}</p>;
    },
    h1({ children, ...props }: { children?: React.ReactNode }) {
      return <h1 className="text-xl font-bold mt-6 mb-3 text-[var(--foreground)]" {...props}>{children}</h1>;
    },
    h2({ children, ...props }: { children?: React.ReactNode }) {
      // Special styling for ReAct headings
      if (children && typeof children === 'string') {
        const text = children.toString();
        if (text.includes('Thought') || text.includes('Action') || text.includes('Observation') || text.includes('Answer')) {
          return (
            <h2
              className="text-base font-semibold mt-5 mb-3 px-3 py-2 rounded-md border border-[var(--code-border)] bg-[var(--surface-muted)] text-[var(--foreground)] shadow-custom tracking-wide"
              {...props}
            >
              {children}
            </h2>
          );
        }
      }
      return <h2 className="text-lg font-bold mt-5 mb-3 text-[var(--foreground)]" {...props}>{children}</h2>;
    },
    h3({ children, ...props }: { children?: React.ReactNode }) {
      return <h3 className="text-base font-semibold mt-4 mb-2 text-[var(--foreground)]" {...props}>{children}</h3>;
    },
    h4({ children, ...props }: { children?: React.ReactNode }) {
      return <h4 className="text-sm font-semibold mt-3 mb-2 text-[var(--foreground)]" {...props}>{children}</h4>;
    },
    ul({ children, ...props }: { children?: React.ReactNode }) {
      return <ul className="list-disc pl-6 mb-4 text-sm text-[var(--foreground)] space-y-2" {...props}>{children}</ul>;
    },
    ol({ children, ...props }: { children?: React.ReactNode }) {
      return <ol className="list-decimal pl-6 mb-4 text-sm text-[var(--foreground)] space-y-2" {...props}>{children}</ol>;
    },
    li({ children, ...props }: { children?: React.ReactNode }) {
      return <li className="mb-2 text-sm leading-relaxed text-[var(--foreground)]" {...props}>{children}</li>;
    },
    a({ children, href, ...props }: { children?: React.ReactNode; href?: string }) {
      // Check if this is a source reference link
      if (isSourceReference(href, children)) {
        const linkText = extractTextContent(children).trim();

        // Parse file path and line range from link text
        // Handles: "file.py", "file.py:1-10", "file.py:5", "file.py:Section Name"
        const sourceMatch = linkText.match(/^([^:]+\.\w+)(?::(.+))?$/);
        if (sourceMatch) {
          const filePath = sourceMatch[1];
          const lineRangeOrSection = sourceMatch[2];

          // Try to extract line numbers if present (e.g., "1-10" or "5")
          let lineRange: string | undefined;
          if (lineRangeOrSection) {
            const lineMatch = lineRangeOrSection.match(/^(\d+)(?:-(\d+))?$/);
            if (lineMatch) {
              lineRange = lineMatch[0]; // Use the matched line range
            }
            // If it's not a line number (e.g., "Section Name"), we'll just link to the file
          }

          const githubUrl = generateSourceUrl(filePath, lineRange);

          if (githubUrl) {
            return (
              <a
                href={githubUrl}
                className="inline-flex items-center gap-1.5 text-[var(--link-color)] hover:text-[var(--accent-primary)] font-medium transition-colors"
                target="_blank"
                rel="noopener noreferrer"
                {...props}
              >
                <FaGithub className="w-3.5 h-3.5 flex-shrink-0" />
                <span>{linkText}</span>
              </a>
            );
          }
        }
      }

      // Check if this is a wiki page link (anchor link like #page-id)
      if (href && href.startsWith('#') && wikiPages.length > 0 && onPageSelect) {
        const pageId = href.substring(1); // Remove the #
        const wikiPage = wikiPages.find(p => p.id === pageId);

        if (wikiPage) {
          return (
            <button
              onClick={() => onPageSelect(pageId)}
              className="text-[var(--link-color)] hover:text-[var(--accent-primary)] underline-offset-2 hover:underline font-medium cursor-pointer border-none bg-transparent p-0 transition-colors"
              {...props}
            >
              {children}
            </button>
          );
        }
      }

      return (
        <a
          href={href}
          className="text-[var(--link-color)] hover:text-[var(--accent-primary)] underline-offset-2 hover:underline font-medium transition-colors"
          target={href && (href.startsWith('http') || href.startsWith('//')) ? '_blank' : undefined}
          rel={href && (href.startsWith('http') || href.startsWith('//')) ? 'noopener noreferrer' : undefined}
          {...props}
        >
          {children}
        </a>
      );
    },
    blockquote({ children, ...props }: { children?: React.ReactNode }) {
      return (
        <blockquote
          className="border-l-4 border-[var(--accent-secondary)] pl-4 pr-3 py-2 text-[var(--foreground)] italic my-4 text-sm bg-[var(--surface-muted)] rounded-md shadow-custom"
          {...props}
        >
          {children}
        </blockquote>
      );
    },
    table({ children, ...props }: { children?: React.ReactNode }) {
      return (
        <div className="overflow-x-auto my-6 rounded-md shadow-custom border border-[var(--code-border)] bg-[var(--card-bg)]">
          <table className="min-w-full text-sm border-collapse text-[var(--foreground)]" {...props}>
            {children}
          </table>
        </div>
      );
    },
    thead({ children, ...props }: { children?: React.ReactNode }) {
      return <thead className="bg-[var(--surface-strong)] text-[var(--foreground)]" {...props}>{children}</thead>;
    },
    tbody({ children, ...props }: { children?: React.ReactNode }) {
      return <tbody className="divide-y divide-[var(--code-border)]" {...props}>{children}</tbody>;
    },
    tr({ children, ...props }: { children?: React.ReactNode }) {
      return <tr className="hover:bg-[var(--surface-muted)] transition-colors" {...props}>{children}</tr>;
    },
    th({ children, ...props }: { children?: React.ReactNode }) {
      return (
        <th
          className="px-4 py-3 text-left font-medium text-[var(--foreground)]"
          {...props}
        >
          {children}
        </th>
      );
    },
    td({ children, ...props }: { children?: React.ReactNode }) {
      return <td className="px-4 py-3 border-t border-[var(--code-border)]" {...props}>{children}</td>;
    },
    code(props: {
      inline?: boolean;
      className?: string;
      children?: React.ReactNode;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      [key: string]: any; // Using any here as it's required for ReactMarkdown components
    }) {
      const { inline, className, children, ...otherProps } = props;
      const match = /language-(\w+)/.exec(className || '');
      const codeContent = children ? String(children).replace(/\n$/, '') : '';

      // Handle Mermaid diagrams
      if (!inline && match && match[1] === 'mermaid') {
        return (
          <div className="not-prose my-8 rounded-xl overflow-hidden shadow-custom border border-[var(--diagram-border)] bg-[var(--diagram-bg)]">
            <Mermaid
              chart={codeContent}
              className="w-full max-w-full"
              zoomingEnabled={true}
            />
          </div>
        );
      }

      // Handle code blocks
      if (!inline && match) {
        return (
          <div className="my-6 rounded-xl overflow-hidden text-sm shadow-custom border border-[var(--code-border)] bg-[var(--code-bg)]">
            <div className="flex justify-between items-center px-4 py-2 text-xs font-medium uppercase tracking-wide bg-[var(--code-header-bg)] text-[var(--muted)] border-b border-[var(--code-border)]">
              <span className="font-mono">{match[1]}</span>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(codeContent);
                }}
                className="inline-flex items-center gap-2 text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
                title="Copy code"
                type="button"
                aria-label="Copy code snippet"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-4 w-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                  />
                </svg>
              </button>
            </div>
            <SyntaxHighlighter
              language={match[1]}
              style={terracottaPrismTheme}
              className="!text-sm"
              customStyle={{
                margin: 0,
                borderRadius: '0',
                padding: '1rem 1.25rem',
                background: 'var(--code-bg)',
                color: 'var(--code-text)',
              }}
              codeTagProps={{
                style: {
                  background: 'transparent',
                  color: 'inherit',
                  fontFamily: 'var(--font-geist-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace)',
                  fontSize: '0.9rem',
                },
              }}
              showLineNumbers
              lineNumberStyle={{
                minWidth: '2.25rem',
                paddingRight: '0.75rem',
                color: 'var(--code-comment)',
                fontSize: '0.75rem',
              }}
              wrapLines
              wrapLongLines
              {...otherProps}
            >
              {codeContent}
            </SyntaxHighlighter>
          </div>
        );
      }

      // Handle inline code
      return (
        <code
          className={`${className ?? ''} font-mono bg-[var(--code-inline-bg)] text-[var(--code-inline-text)] px-2 py-0.5 rounded-md text-sm`}
          {...otherProps}
        >
          {children}
        </code>
      );
    },
  };

  return (
    <div className="prose prose-base dark:prose-invert max-w-none px-2 py-4">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={MarkdownComponents}
      >
        {preprocessedContent}
      </ReactMarkdown>
    </div>
  );
};

export default Markdown;
