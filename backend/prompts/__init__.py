"""LLM prompt templates for the Copilot system.

This module provides centralized prompt templates for all LLM interactions.
Templates use Python string formatting with named placeholders.
"""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def _load_template(filename: str) -> str:
    """Load a prompt template from file."""
    template_path = _PROMPTS_DIR / filename
    return template_path.read_text(encoding="utf-8")


# Lazy-loaded prompt templates
_templates: dict[str, str] = {}


def get_prompt(name: str) -> str:
    """
    Get a prompt template by name.

    Available prompts:
        - prompt_improver: System prompt for improving user prompts
        - stage2_ranking: Template for peer evaluation/ranking
        - stage3_chairman: Template for final synthesis
        - title_generation: Template for generating conversation titles

    Args:
        name: The prompt template name (without .txt extension)

    Returns:
        The prompt template string with placeholders
    """
    if name not in _templates:
        _templates[name] = _load_template(f"{name}.txt")
    return _templates[name]


def format_prompt(name: str, **kwargs) -> str:
    """
    Get and format a prompt template with the given values.

    Args:
        name: The prompt template name
        **kwargs: Values to substitute into the template

    Returns:
        The formatted prompt string
    """
    template = get_prompt(name)
    return template.format(**kwargs)

