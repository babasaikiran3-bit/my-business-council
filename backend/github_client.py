"""GitHub API client for repository access."""

import os
from typing import List, Dict, Any, Optional
from github import Github, GithubException, Repository as GithubRepo
from .logging_config import get_logger

logger = get_logger(__name__)


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client.

        Args:
            token: GitHub personal access token. If not provided, reads from GITHUB_TOKEN env var.
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            logger.warning("github_token_not_configured", message="GITHUB_TOKEN not set - GitHub features disabled")
            self.client = None
        else:
            self.client = Github(self.token)
            logger.info("github_client_initialized")

    def is_available(self) -> bool:
        """Check if GitHub client is configured and available."""
        return self.client is not None

    def get_user_repos(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get list of repositories for the authenticated user.

        Args:
            limit: Maximum number of repos to fetch

        Returns:
            List of repo metadata dicts
        """
        if not self.is_available():
            logger.warning("github_client_not_available", operation="get_user_repos")
            return []

        try:
            user = self.client.get_user()
            repos = []

            # Get user's own repos
            for repo in user.get_repos()[:limit]:
                repos.append(self._repo_to_dict(repo))

            logger.info("fetched_user_repos", count=len(repos))
            return repos

        except GithubException as e:
            logger.error("github_api_error", operation="get_user_repos", error=str(e), status=e.status)
            return []
        except Exception as e:
            logger.error("github_error", operation="get_user_repos", error=str(e))
            return []

    def get_repo(self, full_name: str) -> Optional[Dict[str, Any]]:
        """
        Get repository metadata by full name (owner/repo).

        Args:
            full_name: Repository full name (e.g., "octocat/Hello-World")

        Returns:
            Repo metadata dict or None if not found
        """
        if not self.is_available():
            logger.warning("github_client_not_available", operation="get_repo")
            return None

        try:
            repo = self.client.get_repo(full_name)
            return self._repo_to_dict(repo)

        except GithubException as e:
            logger.error("github_api_error", operation="get_repo", repo=full_name, error=str(e), status=e.status)
            return None
        except Exception as e:
            logger.error("github_error", operation="get_repo", repo=full_name, error=str(e))
            return None

    def get_repo_tree(self, full_name: str, max_depth: int = 3) -> Optional[Dict[str, Any]]:
        """
        Get repository file tree structure.

        Args:
            full_name: Repository full name
            max_depth: Maximum directory depth to traverse

        Returns:
            Tree structure as nested dict or None
        """
        if not self.is_available():
            return None

        try:
            repo = self.client.get_repo(full_name)
            default_branch = repo.default_branch

            # Get the tree recursively
            tree = repo.get_git_tree(default_branch, recursive=True)

            # Build simplified structure
            structure = {
                "files": [],
                "directories": []
            }

            for item in tree.tree:
                # Skip deep paths
                depth = item.path.count('/')
                if depth > max_depth:
                    continue

                # Skip common excluded directories
                excluded_dirs = {'node_modules', '.git', 'dist', 'build', '__pycache__', '.venv', 'venv'}
                if any(excluded in item.path for excluded in excluded_dirs):
                    continue

                if item.type == "blob":  # file
                    structure["files"].append({
                        "path": item.path,
                        "size": item.size
                    })
                elif item.type == "tree":  # directory
                    structure["directories"].append(item.path)

            logger.info("fetched_repo_tree", repo=full_name, files=len(structure["files"]), dirs=len(structure["directories"]))
            return structure

        except GithubException as e:
            logger.error("github_api_error", operation="get_repo_tree", repo=full_name, error=str(e))
            return None
        except Exception as e:
            logger.error("github_error", operation="get_repo_tree", repo=full_name, error=str(e))
            return None

    def get_key_files(self, full_name: str) -> Dict[str, str]:
        """
        Fetch content of key files from repository.

        Key files include:
        - README.md, README.txt
        - package.json, pyproject.toml, go.mod, Cargo.toml
        - .env.example, config files
        - LICENSE

        Args:
            full_name: Repository full name

        Returns:
            Dict mapping filename to content
        """
        if not self.is_available():
            return {}

        key_file_patterns = [
            "README.md", "README.txt", "README",
            "package.json", "pyproject.toml", "go.mod", "Cargo.toml",
            "requirements.txt", "Gemfile", "pom.xml",
            ".env.example", "config.yaml", "config.json",
            "LICENSE", "LICENSE.md", "LICENSE.txt"
        ]

        files_content = {}

        try:
            repo = self.client.get_repo(full_name)

            for pattern in key_file_patterns:
                try:
                    content_file = repo.get_contents(pattern)
                    if isinstance(content_file, list):  # Skip if it's a directory
                        continue

                    # Decode content (it's base64 encoded)
                    content = content_file.decoded_content.decode('utf-8')

                    # Limit file size to 50KB to avoid huge files
                    if len(content) > 50000:
                        content = content[:50000] + "\n\n... (truncated)"

                    files_content[pattern] = content
                    logger.debug("fetched_file", repo=full_name, file=pattern, size=len(content))

                except GithubException as e:
                    if e.status == 404:
                        # File doesn't exist, skip
                        continue
                    logger.debug("file_fetch_failed", repo=full_name, file=pattern, error=str(e))
                except Exception as e:
                    logger.debug("file_decode_failed", repo=full_name, file=pattern, error=str(e))

            logger.info("fetched_key_files", repo=full_name, count=len(files_content))
            return files_content

        except GithubException as e:
            logger.error("github_api_error", operation="get_key_files", repo=full_name, error=str(e))
            return {}
        except Exception as e:
            logger.error("github_error", operation="get_key_files", repo=full_name, error=str(e))
            return {}

    def generate_repo_summary(self, repo_metadata: Dict[str, Any], key_files: Dict[str, str], tree: Optional[Dict[str, Any]]) -> str:
        """
        Generate a text summary of the repository for LLM context.

        Args:
            repo_metadata: Repository metadata dict
            key_files: Dict of key file contents
            tree: Repository tree structure

        Returns:
            Formatted summary text
        """
        summary_parts = [
            f"# Repository: {repo_metadata['full_name']}",
            f"Description: {repo_metadata.get('description', 'No description')}",
            f"Language: {repo_metadata.get('language', 'Unknown')}",
            f"Stars: {repo_metadata.get('stars', 0)}",
            ""
        ]

        # Add README if available
        readme_keys = [k for k in key_files.keys() if k.upper().startswith('README')]
        if readme_keys:
            readme = key_files[readme_keys[0]]
            # Truncate if too long
            if len(readme) > 2000:
                readme = readme[:2000] + "\n\n... (truncated)"
            summary_parts.append("## README")
            summary_parts.append(readme)
            summary_parts.append("")

        # Add tech stack info from package files
        tech_files = {
            "package.json": "Node.js/JavaScript",
            "pyproject.toml": "Python",
            "requirements.txt": "Python",
            "go.mod": "Go",
            "Cargo.toml": "Rust",
            "Gemfile": "Ruby",
            "pom.xml": "Java/Maven"
        }

        found_tech = []
        for file, tech in tech_files.items():
            if file in key_files:
                found_tech.append(tech)

        if found_tech:
            summary_parts.append(f"## Technology Stack")
            summary_parts.append(", ".join(found_tech))
            summary_parts.append("")

        # Add directory structure summary
        if tree:
            summary_parts.append("## Repository Structure")
            summary_parts.append(f"Files: {len(tree.get('files', []))}")
            summary_parts.append(f"Directories: {len(tree.get('directories', []))}")

            # Show top-level directories
            top_level_dirs = [d for d in tree.get('directories', []) if '/' not in d]
            if top_level_dirs:
                summary_parts.append(f"Top-level directories: {', '.join(top_level_dirs[:10])}")

        return "\n".join(summary_parts)

    def _repo_to_dict(self, repo: GithubRepo) -> Dict[str, Any]:
        """Convert GitHub repository object to dict."""
        return {
            "id": repo.id,
            "full_name": repo.full_name,
            "name": repo.name,
            "description": repo.description,
            "language": repo.language,
            "default_branch": repo.default_branch,
            "stars": repo.stargazers_count,
            "private": repo.private,
            "url": repo.html_url,
        }


# Global client instance
_github_client: Optional[GitHubClient] = None


def get_github_client() -> GitHubClient:
    """Get or create global GitHub client instance."""
    global _github_client
    if _github_client is None:
        _github_client = GitHubClient()
    return _github_client
