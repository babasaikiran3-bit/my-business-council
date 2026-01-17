/**
 * Fix nested code blocks by using more backticks for outer fences.
 * This handles cases where model output contains ``` inside code blocks.
 *
 * Example problem:
 *   ```markdown
 *   ## Code
 *   ```python
 *   print("hello")
 *   ```
 *   ```
 *
 * The parser sees the inner ``` as closing the outer markdown block.
 * We fix this by using ````` for outer blocks that contain inner ```.
 */
export function fixNestedCodeBlocks(text) {
  if (!text) return text;

  const lines = text.split('\n');
  const result = [];

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const fenceMatch = line.match(/^(`{3,})(\w*)\s*$/);

    if (fenceMatch) {
      // Found a code fence - collect the entire block with proper nesting
      const openingFenceLen = fenceMatch[1].length;
      const lang = fenceMatch[2];
      const blockLines = [];
      let depth = 1; // We're inside the outer block
      let maxNestedFence = 0;

      i++; // Move past opening fence

      // Collect lines, tracking nesting depth
      while (i < lines.length && depth > 0) {
        const innerLine = lines[i];

        // Check for opening fence (has language tag or starts a block)
        const openMatch = innerLine.match(/^(`{3,})(\w+)\s*$/);
        // Check for closing fence (just backticks, no language)
        const closeMatch = innerLine.match(/^(`{3,})\s*$/);

        if (openMatch) {
          // Opening a nested block
          depth++;
          maxNestedFence = Math.max(maxNestedFence, openMatch[1].length);
          blockLines.push(innerLine);
        } else if (closeMatch) {
          depth--;
          if (depth > 0) {
            // This closes a nested block, not the outer one
            maxNestedFence = Math.max(maxNestedFence, closeMatch[1].length);
            blockLines.push(innerLine);
          }
          // If depth == 0, this closes the outer block (don't add to blockLines)
        } else {
          blockLines.push(innerLine);
        }
        i++;
      }

      // If we found nested fences, use longer outer fences
      if (maxNestedFence > 0) {
        const outerFence = '`'.repeat(Math.max(openingFenceLen, maxNestedFence + 1));
        result.push(outerFence + lang);
        result.push(...blockLines);
        result.push(outerFence);
      } else {
        // No nested fences, keep original
        result.push('`'.repeat(openingFenceLen) + lang);
        result.push(...blockLines);
        result.push('`'.repeat(openingFenceLen));
      }
    } else {
      result.push(line);
      i++;
    }
  }

  return result.join('\n');
}
