/**
 * Smart truncation utility for creating placeholders with snipped content.
 * Shows the first and last N characters with a summary of skipped content.
 */

/**
 * Format a number with commas for readability (e.g., 12345 -> "12,345")
 * @param {number} num - The number to format
 * @returns {string} - Formatted number string
 */
export function formatNumberWithCommas(num) {
  return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Create a smart placeholder for truncated content.
 * Shows the first and last N characters with a snip indicator in between.
 *
 * @param {string} text - The full text to truncate
 * @param {number} headChars - Number of characters to show at the start (default: 100)
 * @param {number} tailChars - Number of characters to show at the end (default: 100)
 * @returns {string} - The truncated text with snip placeholder, or original text if short enough
 */
export function createSnipPlaceholder(text, headChars = 100, tailChars = 100) {
  if (!text || typeof text !== 'string') {
    return text || '';
  }

  const minLength = headChars + tailChars + 50; // Need some content to snip

  if (text.length <= minLength) {
    return text;
  }

  const head = text.slice(0, headChars);
  const tail = text.slice(-tailChars);
  const snippedChars = text.length - headChars - tailChars;

  return `${head}\n\n... snip ${formatNumberWithCommas(snippedChars)} characters ...\n\n${tail}`;
}

/**
 * Create a snip placeholder with custom prefix text (e.g., for labeling excluded content)
 *
 * @param {string} text - The full text to truncate
 * @param {string} prefix - Optional prefix to add before the placeholder (e.g., "[Excluded Message]")
 * @param {number} headChars - Number of characters to show at the start (default: 100)
 * @param {number} tailChars - Number of characters to show at the end (default: 100)
 * @returns {string} - The truncated text with prefix and snip placeholder
 */
export function createLabeledSnipPlaceholder(text, prefix = '', headChars = 100, tailChars = 100) {
  const placeholder = createSnipPlaceholder(text, headChars, tailChars);
  return prefix ? `${prefix}\n\n${placeholder}` : placeholder;
}
