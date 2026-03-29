"""
Improved answer extraction with better regex patterns
Based on analysis of 286 unknown predictions
"""
import sys
import io

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import re

def extract_answer_improved(raw_output: str, dataset: str) -> str:
    """Enhanced answer extraction with more flexible patterns.

    Improvements over original:
    1. Handles "A." format (letter with period)
    2. Better last-line parsing
    3. More flexible regex patterns
    4. Multi-line answer detection
    """
    if not raw_output:
        return "unknown"

    text = raw_output.strip()

    if dataset == "pubmedqa":
        # Check last line first (most common location)
        last_line = text.split("\n")[-1].strip().lower()

        # Exact match on last line
        for label in ["maybe", "yes", "no"]:
            if label == last_line or last_line == f"{label}.":
                return label

        # NEW: Check if last line is just a single letter (format confusion)
        if last_line in ["a.", "a", "b.", "b", "c.", "c", "d.", "d"]:
            # Model confused format - check context for yes/no/maybe
            pass  # Fall through to regex search

        # Search entire text for yes/no/maybe
        # NEW: More flexible word boundaries
        match = re.search(r'\b(yes|no|maybe)\b', text.lower())
        if match:
            return match.group(1)

        # Check first word
        first_word = text.split()[0].lower().rstrip(".,;:!?") if text.split() else ""
        if first_word in ("yes", "no", "maybe"):
            return first_word

        return "unknown"

    else:  # medqa, mmlu
        # NEW: Handle "A." format (letter with period, standalone)
        last_line = text.split("\n")[-1].strip().upper()

        # Check for "A." or "A" at end
        if last_line in ["A.", "B.", "C.", "D.", "A", "B", "C", "D"]:
            return last_line.rstrip(".")

        # Original patterns
        match = re.match(r'^([A-D])\b', last_line)
        if match:
            return match.group(1)

        # NEW: More flexible answer patterns
        # "The answer is B", "Answer: C", "Final answer: D"
        match = re.search(r'(?:final\s+)?(?:answer\s*(?:is|:)\s*)([A-D])\b', text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # "Option B", "Choice C"
        match = re.search(r'(?:option|choice)\s+([A-D])\b', text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Look for "A)", "B)", etc
        match = re.search(r'\b([A-D])\)', text)
        if match:
            return match.group(1).upper()

        # NEW: Check last 100 chars for any A/B/C/D
        last_100 = text[-100:] if len(text) > 100 else text
        match = re.search(r'\b([A-D])\b', last_100.upper())
        if match:
            return match.group(1).upper()

        # Check entire text as last resort
        if text.upper().rstrip(".,;:!?") in ("A", "B", "C", "D"):
            return text.upper().rstrip(".,;:!?")

        # First word
        first_word = text.split()[0].upper().rstrip(".,;:!?") if text.split() else ""
        if first_word in ("A", "B", "C", "D"):
            return first_word

        return "unknown"


# Test function
def test_improved_extraction():
    """Test cases based on actual failures"""

    test_cases = [
        # PubMedQA cases
        ("pubmedqa", "A.", "unknown"),  # Format confusion - no yes/no/maybe
        ("pubmedqa", "yes", "yes"),
        ("pubmedqa", "Yes.", "yes"),
        ("pubmedqa", "Maybe", "maybe"),
        ("pubmedqa", "According to study... no.", "no"),

        # MedQA/MMLU cases
        ("medqa", "A.", "A"),  # NEW: Should extract
        ("medqa", "B", "B"),
        ("medqa", "Maybe", "unknown"),  # Correct: judge confused format
        ("medqa", "The answer is C", "C"),
        ("medqa", "Final answer: D", "D"),
        ("medqa", "Option B is correct", "B"),
        ("medqa", "After consideration... A.", "A"),

        # Edge cases
        ("mmlu", "maybe", "unknown"),  # Correct: wrong format for MCQ
        ("mmlu", "C)", "C"),
        ("mmlu", "The correct choice is A", "A"),
    ]

    print("Testing improved extraction...")
    print("-" * 80)

    passed = 0
    failed = 0

    for dataset, raw, expected in test_cases:
        result = extract_answer_improved(raw, dataset)
        status = "✓" if result == expected else "✗"

        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} {dataset:10s} | '{raw[:30]:30s}' → '{result:7s}' (expected '{expected}')")

    print("-" * 80)
    print(f"Passed: {passed}/{len(test_cases)}, Failed: {failed}/{len(test_cases)}")


if __name__ == "__main__":
    test_improved_extraction()
