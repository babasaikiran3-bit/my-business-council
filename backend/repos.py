"""Autodetección y validación de repositorios para el selector de la web."""

import os
from typing import List, Dict

HOME = os.path.expanduser("~")

# Roots donde buscar repos (1 nivel de profundidad). Extensible por env.
_DEFAULT_ROOTS = [HOME, f"{HOME}/GitHub", "/mnt/Datos"]


def _roots() -> List[str]:
    extra = os.environ.get("COUNCIL_REPO_ROOTS", "")
    roots = list(_DEFAULT_ROOTS)
    if extra:
        roots += [r.strip() for r in extra.split(",") if r.strip()]
    # normalizar + dedup preservando orden
    seen, out = set(), []
    for r in roots:
        rp = os.path.realpath(os.path.expanduser(r))
        if rp not in seen and os.path.isdir(rp):
            seen.add(rp)
            out.append(rp)
    return out


def _is_git_repo(path: str) -> bool:
    return os.path.isdir(os.path.join(path, ".git"))


def list_repos() -> List[Dict[str, str]]:
    """Lista carpetas con .git/ en los roots (1 nivel). Ordenadas, deduplicadas."""
    found: Dict[str, str] = {}  # path -> name
    for root in _roots():
        # el root mismo puede ser un repo
        if _is_git_repo(root):
            found.setdefault(os.path.realpath(root), os.path.basename(root))
        try:
            entries = os.scandir(root)
        except OSError:
            continue
        for entry in entries:
            if not entry.is_dir(follow_symlinks=False):
                continue
            if entry.name.startswith("."):
                continue
            if _is_git_repo(entry.path):
                found.setdefault(os.path.realpath(entry.path), entry.name)
    repos = [{"name": name, "path": path} for path, name in found.items()]
    repos.sort(key=lambda r: r["name"].lower())
    return repos


def is_allowed(path: str) -> bool:
    """Valida un path de repo: existe, es dir, y está bajo un root permitido (anti traversal)."""
    if not path:
        return False
    real = os.path.realpath(os.path.expanduser(path))
    if not os.path.isdir(real):
        return False
    for root in _roots():
        if real == root or real.startswith(root + os.sep):
            return True
    return False
