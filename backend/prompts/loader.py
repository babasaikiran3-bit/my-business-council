"""Load prompt templates from markdown files."""

from pathlib import Path
from typing import Dict


# Cache loaded prompts
_loaded_prompts: Dict[str, str] = {}


def _get_prompts_dir() -> Path:
    """Get the directory containing prompt markdown files."""
    return Path(__file__).parent


def load_prompt(name: str) -> str:
    """
    Load a prompt template from a markdown file.
    
    Args:
        name: Name of the prompt file (without .md extension)
        
    Returns:
        The prompt template as a string
        
    Raises:
        FileNotFoundError: If the prompt file doesn't exist
    """
    if name in _loaded_prompts:
        return _loaded_prompts[name]
    
    prompts_dir = _get_prompts_dir()
    prompt_path = prompts_dir / f"{name}.md"
    
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    content = prompt_path.read_text(encoding="utf-8")
    _loaded_prompts[name] = content
    return content


# Pre-load all prompts at module import time
STAGE2_RANKING_TEMPLATE = load_prompt("stage2_ranking")
STAGE3_CHAIRMAN_TEMPLATE = load_prompt("stage3_chairman")
TITLE_GENERATION_TEMPLATE = load_prompt("title_generation")

