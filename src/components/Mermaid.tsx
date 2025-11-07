import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';
// We'll use dynamic import for svg-pan-zoom

// Initialize mermaid with defaults
mermaid.initialize({
  startOnLoad: true,
  theme: 'neutral',
  securityLevel: 'loose',
  suppressErrorRendering: true,
  logLevel: 'error',
  maxTextSize: 100000, // Increase text size limit
  htmlLabels: true,
  flowchart: {
    htmlLabels: true,
    curve: 'basis',
    nodeSpacing: 60,
    rankSpacing: 60,
    padding: 20,
    useMaxWidth: true,
  },
  themeCSS: `
    /* Ensure SVG and all containers have transparent backgrounds */
    svg {
      background: transparent !important;
      background-color: transparent !important;
    }
    
    /* Custom styles for all diagrams */
    .node rect, .node circle, .node ellipse, .node polygon, .node path {
      fill: #f8f4e6;
      stroke: #d7c4bb;
      stroke-width: 1px;
    }
    .edgePath .path {
      stroke: #B8605D;
      stroke-width: 1.5px;
    }
    .edgeLabel {
      background-color: transparent;
      color: var(--foreground, #333333);
      p {
        background-color: transparent !important;
      }
    }
    .label {
      color: var(--foreground, #333333);
    }
    .cluster rect {
      fill: #f8f4e6;
      stroke: #d7c4bb;
      stroke-width: 1px;
    }

    /* Sequence diagram specific styles */
    .actor {
      fill: #f8f4e6;
      stroke: #d7c4bb;
      stroke-width: 1px;
    }
    text.actor {
      fill: var(--foreground, #333333);
      stroke: none;
    }
    .messageText {
      fill: var(--foreground, #333333);
      stroke: none;
    }
    .messageLine0, .messageLine1 {
      stroke: #B8605D;
    }
    .noteText {
      fill: var(--foreground, #333333);
    }

    /* Dark mode overrides - will be applied with data-theme="dark" */
    [data-theme="dark"] .node rect,
    [data-theme="dark"] .node circle,
    [data-theme="dark"] .node ellipse,
    [data-theme="dark"] .node polygon,
    [data-theme="dark"] .node path {
      fill: #222222;
      stroke: #5d4037;
    }
    [data-theme="dark"] .edgePath .path {
      stroke: #C87370;
    }
    [data-theme="dark"] .edgeLabel {
      background-color: transparent;
      color: var(--foreground, #f0f0f0);
    }
    [data-theme="dark"] .label {
      color: var(--foreground, #f0f0f0);
    }
    [data-theme="dark"] .cluster rect {
      fill: #222222;
      stroke: #5d4037;
    }
    [data-theme="dark"] .flowchart-link {
      stroke: #C87370;
    }

    /* Dark mode sequence diagram overrides */
    [data-theme="dark"] .actor {
      fill: #222222;
      stroke: #5d4037;
    }
    [data-theme="dark"] text.actor {
      fill: var(--foreground, #f0f0f0);
      stroke: none;
    }
    [data-theme="dark"] .messageText {
      fill: var(--foreground, #f0f0f0);
      stroke: none;
      font-weight: 500;
    }
    [data-theme="dark"] .messageLine0, [data-theme="dark"] .messageLine1 {
      stroke: #C87370;
      stroke-width: 1.5px;
    }
    [data-theme="dark"] .noteText {
      fill: var(--foreground, #f0f0f0);
    }
    /* Additional styles for sequence diagram text */
    [data-theme="dark"] #sequenceNumber {
      fill: var(--foreground, #f0f0f0);
    }
    [data-theme="dark"] text.sequenceText {
      fill: var(--foreground, #f0f0f0);
      font-weight: 500;
    }
    [data-theme="dark"] text.loopText, [data-theme="dark"] text.loopText tspan {
      fill: var(--foreground, #f0f0f0);
    }
    /* Add a subtle background to message text for better readability */
    [data-theme="dark"] .messageText, [data-theme="dark"] text.sequenceText {
      paint-order: stroke;
      stroke: #1a1a1a;
      stroke-width: 2px;
      stroke-linecap: round;
      stroke-linejoin: round;
    }

    /* Force text elements to be properly colored - use CSS variables for theme consistency */
    text[text-anchor][dominant-baseline],
    text[text-anchor][alignment-baseline],
    .nodeLabel,
    .edgeLabel,
    .label,
    text {
      fill: var(--foreground, #333333) !important;
      font-family: var(--font-geist-sans), sans-serif !important;
    }

    [data-theme="dark"] text[text-anchor][dominant-baseline],
    [data-theme="dark"] text[text-anchor][alignment-baseline],
    [data-theme="dark"] .nodeLabel,
    [data-theme="dark"] .edgeLabel,
    [data-theme="dark"] .label,
    [data-theme="dark"] text {
      fill: var(--foreground, #f0f0f0) !important;
      font-family: var(--font-geist-sans), sans-serif !important;
    }

    /* Add clickable element styles with subtle transitions */
    .clickable {
      transition: all 0.3s ease;
    }
    .clickable:hover {
      transform: scale(1.03);
      cursor: pointer;
    }
    .clickable:hover > * {
      filter: brightness(0.95);
    }
    
    /* Prevent text cutoff in nodes */
    .nodeLabel,
    .edgeLabel,
    .label text,
    text {
      overflow: visible !important;
      text-overflow: clip !important;
      white-space: pre-wrap !important;
    }
    
    /* Ensure foreignObject elements don't clip content and center text */
    foreignObject {
      overflow: visible !important;
      text-align: center !important;
    }
    
    /* Ensure proper text rendering in HTML labels */
    .nodeLabel div,
    .edgeLabel div {
      overflow: visible !important;
      word-wrap: break-word !important;
      white-space: pre-wrap !important;
      text-align: center !important;
      color: var(--foreground, #333333) !important;
      font-family: var(--font-geist-sans), sans-serif !important;
      background: transparent !important;
      background-color: transparent !important;
    }
    
    [data-theme="dark"] .nodeLabel div,
    [data-theme="dark"] .edgeLabel div {
      color: var(--foreground, #f0f0f0) !important;
      background: transparent !important;
      background-color: transparent !important;
    }
    
    /* Remove any black backgrounds from text containers */
    .nodeLabel,
    .edgeLabel,
    foreignObject {
      background: transparent !important;
      background-color: transparent !important;
    }
    
    /* Ensure text elements don't have blue or black colors */
    text {
      fill: var(--foreground, #333333) !important;
    }
    
    [data-theme="dark"] text {
      fill: var(--foreground, #f0f0f0) !important;
    }
    
    /* Center text in SVG text elements */
    .nodeLabel text,
    .label text {
      text-anchor: middle !important;
    }
    
    /* Center content in divs within foreignObject (HTML labels) */
    foreignObject div {
      text-align: center !important;
    }
  `,
  fontFamily: 'var(--font-geist-sans), var(--font-serif-jp), sans-serif',
  fontSize: 12,
});

interface MermaidProps {
  chart: string;
  className?: string;
  zoomingEnabled?: boolean;
}

// Full screen modal component for the diagram
const FullScreenModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
}> = ({ isOpen, onClose, children }) => {
  const modalRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  // Handle click outside to close
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, [isOpen, onClose]);

  // Reset zoom when modal opens
  useEffect(() => {
    if (isOpen) {
      setZoom(1);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-75 p-4">
      <div
        ref={modalRef}
        className="bg-[var(--card-bg)] rounded-lg shadow-custom max-w-5xl max-h-[90vh] w-full overflow-hidden flex flex-col"
      >
        {/* Modal header with controls */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--border-color)]">
          <div className="font-medium text-[var(--foreground)] font-serif">Diagram View</div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setZoom(1)}
              className="text-[var(--foreground)] hover:bg-[var(--accent-primary)]/10 p-2 rounded-md border border-[var(--border-color)] transition-colors"
              aria-label="Reset zoom"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"></path>
                <path d="M21 3v5h-5"></path>
              </svg>
            </button>
            <button
              onClick={onClose}
              className="text-[var(--foreground)] hover:bg-[var(--accent-primary)]/10 p-2 rounded-md border border-[var(--border-color)] transition-colors"
              aria-label="Close"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>

        {/* Modal content with zoom */}
        <div className="overflow-auto p-6 flex-1 flex items-center justify-center bg-[var(--background)]/50">
          <div
            style={{
              transform: `scale(${zoom})`,
              transformOrigin: 'center center',
              transition: 'transform 0.3s ease-out',
              background: 'transparent'
            }}
          >
            {children}
          </div>
        </div>
      </div>
    </div>
  );
};

const normalizeLabel = (label: string): string => {
  return label
    .replace(/<\s*br\s*\/?\s*>/gi, '<br/>')
    .replace(/\s+/g, ' ')
    .trim();
};

const sanitizeFlowchart = (source: string): string => {
  let output = source;

  // Wrap node labels with quotes for [], (), {}, <>
  const wrappers: Array<{ open: string; close: string }> = [
    { open: '[', close: ']' },
    { open: '(', close: ')' },
    { open: '{', close: '}' },
    { open: '<', close: '>' },
  ];

  wrappers.forEach(({ open, close }) => {
    const pattern = new RegExp(
      `([A-Za-z0-9_]+)\\${open}(?!")([\\s\\S]*?)(?<!")\\${close}`,
      'g'
    );
    output = output.replace(pattern, (_, id: string, label: string) => {
      const normalized = normalizeLabel(label);
      const escaped = normalized.replace(/"/g, '\\"');
      return `${id}${open}"${escaped}"${close}`;
    });
  });

  // Convert colon-labelled edges to Mermaid format (A -->|Label| B)
  const arrowPattern = /([A-Za-z0-9_]+)\s*-->\s*([A-Za-z0-9_]+)\s*:\s*([^\n]+)/g;
  output = output.replace(arrowPattern, (_, from: string, to: string, label: string) => {
    return `${from} -->|${label.trim()}| ${to}`;
  });

  return output;
};

const Mermaid: React.FC<MermaidProps> = ({ chart, className = '', zoomingEnabled = false }) => {
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isPanZoomReady, setIsPanZoomReady] = useState(false);
  const mermaidRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const panZoomRef = useRef<any>(null); // Store pan-zoom instance
  const idRef = useRef(`mermaid-${Math.random().toString(36).substring(2, 9)}`);
  const normalizedChartRef = useRef(chart);
  const isDarkModeRef = useRef(
    typeof window !== 'undefined' &&
    window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: dark)').matches
  );

  useEffect(() => {
    normalizedChartRef.current = chart;
  }, [chart]);

  // Initialize pan-zoom functionality when SVG is rendered
  useEffect(() => {
    if (svg && zoomingEnabled && containerRef.current) {
      const initializePanZoom = async () => {
        const svgElement = containerRef.current?.querySelector("svg");
        if (svgElement) {
          // Remove any max-width constraints and ensure proper sizing
          svgElement.style.maxWidth = "none";
          svgElement.style.width = "100%";
          svgElement.style.height = "auto";

          // Fix text overflow by ensuring proper viewBox
          const viewBox = svgElement.getAttribute('viewBox');
          if (viewBox) {
            const [x, y, width, height] = viewBox.split(' ').map(Number);
            // Add padding to viewBox to prevent text cutoff
            const padding = 50;
            svgElement.setAttribute('viewBox', `${x - padding} ${y - padding} ${width + padding * 2} ${height + padding * 2}`);
          }

          try {
            // Dynamically import svg-pan-zoom only when needed in the browser
            const svgPanZoom = (await import("svg-pan-zoom")).default;

            panZoomRef.current = svgPanZoom(svgElement, {
              zoomEnabled: true,
              controlIconsEnabled: false, // Disable default controls
              fit: true,
              center: true,
              minZoom: 0.1,
              maxZoom: 10,
              zoomScaleSensitivity: 0.3,
            });
            setIsPanZoomReady(true);
          } catch (error) {
            console.error("Failed to load svg-pan-zoom:", error);
          }
        }
      };

      // Wait for the SVG to be rendered
      setTimeout(() => {
        void initializePanZoom();
      }, 100);
    }

    // Cleanup
    return () => {
      if (panZoomRef.current && typeof panZoomRef.current.destroy === 'function') {
        panZoomRef.current.destroy();
        panZoomRef.current = null;
      }
      setIsPanZoomReady(false);
    };
  }, [svg, zoomingEnabled]);

  const handleReset = () => {
    if (panZoomRef.current) {
      panZoomRef.current.resetZoom();
      panZoomRef.current.resetPan();
    }
  };

  useEffect(() => {
    if (!chart) return;

    let isMounted = true;

    const renderChart = async () => {
      if (!isMounted) return;

      try {
        const normalizedChart = chart && /^\s*flowchart/i.test(chart)
          ? sanitizeFlowchart(chart)
          : chart;
        normalizedChartRef.current = normalizedChart;

        setError(null);
        setSvg('');

        // Ensure custom fonts are loaded before measuring text for nodes
        if (typeof document !== 'undefined' && 'fonts' in document) {
          try {
            await document.fonts.ready;
          } catch (fontError) {
            console.warn('Mermaid fonts failed to load before render:', fontError);
          }
        }

        // Render the chart directly without preprocessing
        const { svg: renderedSvg } = await mermaid.render(idRef.current, normalizedChart);

        if (!isMounted) return;

        let processedSvg = renderedSvg;
        if (isDarkModeRef.current) {
          processedSvg = processedSvg.replace('<svg ', '<svg data-theme="dark" ');
        }

        // Remove black background from SVG root element first
        processedSvg = processedSvg.replace(
          /<svg([^>]*)>/i,
          (match, attrs) => {
            // Remove any black background from SVG element
            let newAttrs = attrs;
            // Remove black background-color from style attribute
            newAttrs = newAttrs.replace(
              /style="([^"]*)"/i,
              (styleMatch: string, styleContent: string) => {
                let newStyle = styleContent
                  .replace(/background(?:-color)?:\s*(?:black|#000|#000000|rgb\(0,\s*0,\s*0\)|rgba\(0,\s*0,\s*0[^)]*\))[^;]*;?/gi, '')
                  .replace(/;;+/g, ';')
                  .replace(/^;|;$/g, '');
                // Add transparent background if no background is set
                if (!newStyle.includes('background')) {
                  newStyle = `background: transparent; ${newStyle}`;
                }
                return `style="${newStyle}"`;
              }
            );
            // If no style attribute exists, add one with transparent background
            if (!newAttrs.includes('style=')) {
              newAttrs += ' style="background: transparent;"';
            }
            return `<svg${newAttrs}>`;
          }
        );

        // Remove black background rect elements (common in Mermaid diagrams)
        processedSvg = processedSvg.replace(
          /<rect([^>]*fill="(?:black|#000|#000000|rgb\(0,\s*0,\s*0\)|rgba\(0,\s*0,\s*0[^)]*\))"[^>]*)>/gi,
          (match, attrs) => {
            // Remove fill attribute or make it transparent
            let newAttrs = attrs.replace(/fill="(?:black|#000|#000000|rgb\(0,\s*0,\s*0\)|rgba\(0,\s*0,\s*0[^)]*\))"/gi, 'fill="transparent"');
            return `<rect${newAttrs}>`;
          }
        );

        // Also check for black backgrounds in rect style attributes
        processedSvg = processedSvg.replace(
          /<rect([^>]*)>/gi,
          (match, attrs) => {
            if (attrs.includes('style=')) {
              return match.replace(
                /style="([^"]*)"/i,
                (styleMatch, styleContent) => {
                  let newStyle = styleContent
                    .replace(/fill:\s*(?:black|#000|#000000|rgb\(0,\s*0,\s*0\)|rgba\(0,\s*0,\s*0[^)]*\))[^;]*;?/gi, 'fill: transparent;')
                    .replace(/background(?:-color)?:\s*(?:black|#000|#000000|rgb\(0,\s*0,\s*0\)|rgba\(0,\s*0,\s*0[^)]*\))[^;]*;?/gi, '')
                    .replace(/;;+/g, ';')
                    .replace(/^;|;$/g, '');
                  return `style="${newStyle}"`;
                }
              );
            }
            return match;
          }
        );

        // Inject CSS variables for text colors to match page theme
        // Since SVG can't directly use CSS variables, we read them and apply the values
        if (typeof window !== 'undefined') {
          const root = document.documentElement;
          const foregroundColor = getComputedStyle(root).getPropertyValue('--foreground').trim() ||
            (isDarkModeRef.current ? '#f0f0f0' : '#333333');
          const fontFamily = getComputedStyle(root).getPropertyValue('--font-geist-sans').trim() ||
            getComputedStyle(document.body).fontFamily ||
            'sans-serif';

          // Replace ALL text fill colors with theme color (more comprehensive)
          // Match any fill color including blue, black, and other colors
          processedSvg = processedSvg.replace(
            /fill="(#[0-9a-fA-F]{3,6}|rgb\([^)]+\)|rgba\([^)]+\)|blue|black|#000|#333|#777|#333333|#000000|#212529|#343a40|#0066cc|#0066FF|#0000ff)"/gi,
            `fill="${foregroundColor}"`
          );

          // Also replace fill colors in style attributes (including blue)
          processedSvg = processedSvg.replace(
            /style="([^"]*fill:\s*)(?:#[0-9a-fA-F]{3,6}|rgb\([^)]+\)|rgba\([^)]+\)|blue|black|#000|#333|#777|#333333|#000000|#212529|#343a40|#0066cc|#0066FF|#0000ff)([^"]*)"/gi,
            `style="$1${foregroundColor}$2"`
          );

          // Remove black backgrounds from ANY element (fix the black box issue)
          processedSvg = processedSvg.replace(
            /style="([^"]*)(?:background|bg-color|background-color):\s*(?:black|#000|#000000|rgb\(0,\s*0,\s*0\)|rgba\(0,\s*0,\s*0[^)]*\))([^"]*)"/gi,
            (match, before, after) => {
              // Remove the background property entirely
              let cleaned = before + after;
              // Clean up double semicolons
              cleaned = cleaned.replace(/;;+/g, ';');
              // Clean up leading/trailing semicolons
              cleaned = cleaned.replace(/^;|;$/g, '');
              return `style="${cleaned}"`;
            }
          );

          // Also remove black backgrounds from div elements specifically
          processedSvg = processedSvg.replace(
            /<div([^>]*)style="([^"]*)"/g,
            (match, attrs, style) => {
              let newStyle = style;
              // Remove black backgrounds
              newStyle = newStyle.replace(/background(?:-color)?:\s*(?:black|#000|#000000|rgb\(0,\s*0,\s*0\)|rgba\(0,\s*0,\s*0[^)]*\))[^;]*;?/gi, '');
              // Replace blue colors with theme color
              newStyle = newStyle.replace(/color:\s*(?:blue|#0066cc|#0066FF|#0000ff|rgb\(0,\s*102,\s*204\))/gi, `color: ${foregroundColor}`);
              // Clean up double semicolons
              newStyle = newStyle.replace(/;;+/g, ';');
              newStyle = newStyle.replace(/^;|;$/g, '');
              return `<div${attrs}style="${newStyle}"`;
            }
          );

          // Inject font family into foreignObject divs (HTML labels)
          processedSvg = processedSvg.replace(
            /<div([^>]*class="[^"]*nodeLabel[^"]*"[^>]*)>/g,
            (match, attrs) => {
              if (attrs.includes('style=')) {
                return match.replace(/style="([^"]*)"/, (_, existingStyle) => {
                  // Add font-family and color if not already present
                  let newStyle = existingStyle;
                  if (!newStyle.includes('font-family')) {
                    newStyle += `; font-family: ${fontFamily}`;
                  }
                  if (!newStyle.includes('color:')) {
                    newStyle += `; color: ${foregroundColor}`;
                  }
                  // Remove black backgrounds
                  newStyle = newStyle.replace(/background(?:-color)?:\s*(?:black|#000|#000000)[^;]*;?/gi, '');
                  return `style="${newStyle}"`;
                });
              }
              return `<div${attrs} style="font-family: ${fontFamily}; color: ${foregroundColor};">`;
            }
          );
        }

        // Fix text overflow issues - minimal safe changes
        processedSvg = processedSvg.replace(
          /<text([^>]*)>/g,
          (match, attrs) => {
            // Only add text-anchor if not already present and add overflow fix
            if (!attrs.includes('text-anchor')) {
              return `<text${attrs} text-anchor="middle">`;
            }
            return match;
          }
        );

        // Ensure foreignObject elements have proper overflow handling
        processedSvg = processedSvg.replace(
          /<foreignObject([^>]*)>/g,
          (match, attrs) => {
            // Only add style if not already present
            if (!attrs.includes('style=')) {
              return `<foreignObject${attrs} style="overflow: visible;">`;
            }
            return match;
          }
        );

        setSvg(processedSvg);

        // Call mermaid.contentLoaded to ensure proper initialization
        setTimeout(() => {
          mermaid.contentLoaded();
        }, 50);
      } catch (err) {
        console.error('Mermaid rendering error:', err);

        const errorMessage = err instanceof Error ? err.message : String(err);

        if (isMounted) {
          setError(`Failed to render diagram: ${errorMessage}`);

          if (mermaidRef.current) {
            mermaidRef.current.innerHTML = `
              <div class="text-red-500 dark:text-red-400 text-xs mb-1">Syntax error in diagram</div>
              <pre class="text-xs overflow-auto p-2 bg-gray-100 dark:bg-gray-800 rounded">${normalizedChartRef.current}</pre>
            `;
          }
        }
      }
    };

    renderChart();

    return () => {
      isMounted = false;
    };
  }, [chart]);

  const handleDiagramClick = () => {
    if (!error && svg) {
      setIsFullscreen(true);
    }
  };

  if (error) {
    return (
      <div className={`border border-[var(--highlight)]/30 rounded-md p-4 bg-[var(--highlight)]/5 ${className}`}>
        <div className="flex items-center mb-3">
          <div className="text-[var(--highlight)] text-xs font-medium flex items-center">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Diagram Rendering Error
          </div>
        </div>
        <div ref={mermaidRef} className="text-xs overflow-auto"></div>
        <div className="mt-3 text-xs text-[var(--muted)] font-serif">
          The diagram contains syntax errors and cannot be rendered.
        </div>
      </div>
    );
  }

  if (!svg) {
    return (
      <div className={`flex justify-center items-center p-4 ${className}`}>
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-[var(--accent-primary)]/70 rounded-full animate-pulse"></div>
          <div className="w-2 h-2 bg-[var(--accent-primary)]/70 rounded-full animate-pulse delay-75"></div>
          <div className="w-2 h-2 bg-[var(--accent-primary)]/70 rounded-full animate-pulse delay-150"></div>
          <span className="text-[var(--muted)] text-xs ml-2 font-serif">Rendering diagram...</span>
        </div>
      </div>
    );
  }

  return (
    <>
      <div
        ref={containerRef}
        className={`w-full max-w-full ${zoomingEnabled ? "h-[600px] p-4" : ""}`}
      >
        <div
          className={`relative group ${zoomingEnabled ? "h-full rounded-lg border-2 border-[var(--border-color)]" : ""}`}
        >
          <div
            className={`flex justify-center overflow-auto text-center my-2 cursor-pointer hover:shadow-md transition-shadow duration-200 rounded-md ${className} ${zoomingEnabled ? "h-full" : ""}`}
            style={{ background: 'transparent' }}
            dangerouslySetInnerHTML={{ __html: svg }}
            onClick={zoomingEnabled ? undefined : handleDiagramClick}
            title={zoomingEnabled ? undefined : "Click to view fullscreen"}
          />

          {zoomingEnabled && (
            <button
              onClick={handleReset}
              disabled={!isPanZoomReady}
              className="absolute top-2 right-2 bg-[var(--card-bg)]/90 hover:bg-[var(--card-bg)] text-[var(--foreground)] p-2 rounded-md border border-[var(--border-color)] transition-colors shadow-md z-10 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Reset zoom"
              title="Reset zoom"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"></path>
                <path d="M21 3v5h-5"></path>
              </svg>
            </button>
          )}

          {!zoomingEnabled && (
            <div className="absolute top-2 right-2 bg-gray-700/70 dark:bg-gray-900/70 text-white p-1.5 rounded-md opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center gap-1.5 text-xs shadow-md pointer-events-none">
              <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                <line x1="11" y1="8" x2="11" y2="14"></line>
                <line x1="8" y1="11" x2="14" y2="11"></line>
              </svg>
              <span>Click to zoom</span>
            </div>
          )}
        </div>
      </div>

      {!zoomingEnabled && (
        <FullScreenModal
          isOpen={isFullscreen}
          onClose={() => setIsFullscreen(false)}
        >
          <div style={{ background: 'transparent' }} dangerouslySetInnerHTML={{ __html: svg }} />
        </FullScreenModal>
      )}
    </>
  );
};



export default Mermaid;
