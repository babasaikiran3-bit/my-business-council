import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { fixNestedCodeBlocks } from '../utils/markdown';

/**
 * Markdown component with support for:
 * - GitHub Flavored Markdown (tables, strikethrough, etc.)
 * - LaTeX math expressions ($...$ for inline, $$...$$ for block)
 * - Nested code blocks (automatically fixed)
 */
export default function Markdown({ children, className = 'markdown-content' }) {
  const processedContent = fixNestedCodeBlocks(children);

  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
}
