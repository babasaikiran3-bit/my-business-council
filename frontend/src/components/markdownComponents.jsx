/**
 * Safe markdown renderers for model-authored text.
 *
 * The Sources panels are rendered deterministically from real, annotation-derived
 * citations. But a council/chairman answer is free text, so if we let ReactMarkdown
 * turn every [label](http://...) into a live link, a model could surface a
 * fabricated or mis-cited URL as a clickable "source" inside the answer body.
 *
 * makeSafeMarkdownComponents(sources) returns a ReactMarkdown `components` map whose
 * link renderer only keeps a link clickable when its href exactly matches one of the
 * verified source URLs (the allowlist). Any other link is rendered as plain text, so
 * a hallucinated URL is structurally impossible to click.
 */
export function makeSafeMarkdownComponents(sources) {
  const allow = new Set(
    (sources || [])
      .map((s) => (s && s.url ? String(s.url).trim() : null))
      .filter(Boolean)
  );

  return {
    a({ href, children }) {
      const target = href ? String(href).trim() : '';
      if (target && allow.has(target)) {
        return (
          <a href={target} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        );
      }
      // Not a verified source — keep the text, drop the (possibly fabricated) link.
      return (
        <span className="blocked-link" title="Unverified link removed">
          {children}
        </span>
      );
    },
  };
}
