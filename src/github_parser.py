"""GitHub URL parsing and validation."""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class GitHubRepo:
    """Parsed GitHub repository information."""
    owner: str
    repo: str
    url: str

    @property
    def full_name(self) -> str:
        """Return full repository name (owner/repo)."""
        return f"{self.owner}/{self.repo}"

    @property
    def clone_url(self) -> str:
        """Return HTTPS clone URL."""
        return f"https://github.com/{self.owner}/{self.repo}.git"

    @property
    def folder_name(self) -> str:
        """Return folder name for local clone (owner_repo)."""
        return f"{self.owner}_{self.repo}"


#Regex patterns for GitHub URLs
GITHUB_PATTERNS = [
    #https://github.com/owner/repo
    re.compile(r'https?://github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?/?(?:[#?].*)?$'),
    #git@github.com:owner/repo.git
    re.compile(r'git@github\.com:([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?$'),
    #github.com/owner/repo (without protocol)
    re.compile(r'github\.com/([a-zA-Z0-9_-]+)/([a-zA-Z0-9_.-]+)(?:\.git)?/?(?:[#?].*)?'),
]


def extract_github_urls(text: str) -> list[GitHubRepo]:
    """
    Extract all GitHub repository URLs from text.

    Args:
        text: Text that may contain GitHub URLs

    Returns:
        List of parsed GitHubRepo objects
    """
    repos = []
    seen = set()

    for pattern in GITHUB_PATTERNS:
        for match in pattern.finditer(text):
            owner = match.group(1)
            repo = match.group(2).rstrip('.git')

            #Deduplicate
            key = f"{owner}/{repo}"
            if key not in seen:
                seen.add(key)
                repos.append(GitHubRepo(
                    owner=owner,
                    repo=repo,
                    url=f"https://github.com/{owner}/{repo}"
                ))

    return repos


def parse_github_url(url: str) -> Optional[GitHubRepo]:
    """
    Parse a single GitHub URL.

    Args:
        url: GitHub URL to parse

    Returns:
        GitHubRepo if valid, None otherwise
    """
    repos = extract_github_urls(url)
    return repos[0] if repos else None


def is_github_url(text: str) -> bool:
    """
    Check if text contains a GitHub repository URL.

    Args:
        text: Text to check

    Returns:
        True if contains GitHub URL
    """
    return bool(extract_github_urls(text))
