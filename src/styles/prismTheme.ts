import type { PrismTheme } from 'react-syntax-highlighter';

const terracottaPrismTheme: PrismTheme = {
  plain: {
    color: 'var(--code-text)',
    backgroundColor: 'transparent',
    fontFamily:
      'var(--font-geist-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace)',
    fontSize: '0.9rem',
    textShadow: 'none'
  },
  styles: [
    {
      types: ['selection'],
      style: {
        background: 'var(--code-selection)'
      }
    },
    {
      types: ['comment', 'prolog', 'doctype', 'cdata'],
      style: {
        color: 'var(--code-comment)',
        fontStyle: 'italic'
      }
    },
    {
      types: ['punctuation'],
      style: {
        color: 'var(--code-punctuation)'
      }
    },
    {
      types: ['atrule', 'attr-value', 'keyword'],
      style: {
        color: 'var(--code-keyword)',
        fontWeight: 600
      }
    },
    {
      types: ['tag'],
      style: {
        color: 'var(--code-tag)'
      }
    },
    {
      types: ['attr-name', 'property'],
      style: {
        color: 'var(--code-attr)'
      }
    },
    {
      types: ['function', 'class-name', 'selector'],
      style: {
        color: 'var(--code-function)'
      }
    },
    {
      types: ['string', 'char', 'builtin', 'inserted'],
      style: {
        color: 'var(--code-string)'
      }
    },
    {
      types: ['number', 'boolean', 'variable', 'constant', 'symbol'],
      style: {
        color: 'var(--code-number)'
      }
    },
    {
      types: ['operator', 'entity', 'url'],
      style: {
        color: 'var(--code-operator)'
      }
    },
    {
      types: ['deleted'],
      style: {
        color: 'var(--highlight)',
        textDecoration: 'line-through'
      }
    },
    {
      types: ['important', 'bold'],
      style: {
        fontWeight: 700
      }
    },
    {
      types: ['italic'],
      style: {
        fontStyle: 'italic'
      }
    },
    {
      types: ['namespace'],
      style: {
        opacity: 0.8
      }
    }
  ]
};

export default terracottaPrismTheme;

