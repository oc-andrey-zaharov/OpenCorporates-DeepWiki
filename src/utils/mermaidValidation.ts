export type MermaidIssue = {
  index: number;
  code: string;
  error: string;
};

let parserPromise: Promise<typeof import('@mermaid-js/parser')> | null = null;

async function loadParser() {
  if (!parserPromise) {
    parserPromise = import('@mermaid-js/parser');
  }
  return parserPromise;
}

function extractMermaidBlocks(markdown: string) {
  const blocks: string[] = [];
  const regex = /```mermaid\s*([\s\S]*?)```/g;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(markdown)) !== null) {
    const code = match[1]?.trim();
    if (code) {
      blocks.push(code);
    }
  }
  return blocks;
}

export async function validateMermaidMarkdown(markdown: string): Promise<MermaidIssue[]> {
  const issues: MermaidIssue[] = [];
  const blocks = extractMermaidBlocks(markdown);

  if (!blocks.length) {
    return issues;
  }

  try {
    const parser = await loadParser();

    await Promise.all(
      blocks.map(async (code, index) => {
        try {
          await parser.parse(code);
        } catch (err) {
          const error = err instanceof Error ? err.message : String(err);
          issues.push({ index, code, error });
        }
      })
    );
  } catch (err) {
    const error = err instanceof Error ? err.message : String(err);
    issues.push({
      index: -1,
      code: '',
      error: `Failed to initialize Mermaid parser: ${error}`
    });
  }

  return issues;
}
