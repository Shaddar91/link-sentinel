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


#Path segments that are github.com platform features, not user/org accounts.
#Guards against false positives when a URL points to a github.com feature page
#(e.g. /settings/profile, /marketplace/actions/checkout).
RESERVED_OWNERS = frozenset({
    'about', 'account', 'apps', 'codespaces', 'collections', 'contact',
    'dashboard', 'enterprise', 'events', 'explore', 'features', 'gist',
    'issues', 'login', 'logout', 'marketplace', 'mobile', 'new',
    'notifications', 'orgs', 'pricing', 'pulls', 'search', 'security',
    'settings', 'signup', 'site', 'sponsors', 'stars', 'topics',
    'trending', 'watching',
})


#Regex patterns for GitHub URLs.
#Matches the canonical owner/repo even when the full URL carries extra path
#segments (/blob/..., /tree/..., /pull/..., /share) or tracking query params
#(?utm_source=share, ?tab=readme-ov-file) -- the shapes produced by GitHub's
#Share button and mobile/desktop share flows. Without this tolerance, shared
#links were silently dropped because the previous regex was anchored at $.
GITHUB_PATTERNS = [
    #https(s)://[www.]github.com/owner/repo[.git][/extra/path][?query][#frag]
    re.compile(
        r'https?://(?:www\.)?github\.com/'
        r'([a-zA-Z0-9][a-zA-Z0-9_-]*)/'
        r'([a-zA-Z0-9][a-zA-Z0-9_.-]*?)'
        r'(?:\.git)?'
        r'(?:[/#?][^\s]*)?'
        r'(?=\s|$)'
    ),
    #git@github.com:owner/repo.git (SSH)
    re.compile(
        r'git@github\.com:'
        r'([a-zA-Z0-9][a-zA-Z0-9_-]*)/'
        r'([a-zA-Z0-9][a-zA-Z0-9_.-]*?)'
        r'(?:\.git)?'
        r'(?=\s|$)'
    ),
    #Bare github.com/owner/repo[/extra/path]... (no protocol)
    re.compile(
        r'(?<![a-zA-Z0-9./])github\.com/'
        r'([a-zA-Z0-9][a-zA-Z0-9_-]*)/'
        r'([a-zA-Z0-9][a-zA-Z0-9_.-]*?)'
        r'(?:\.git)?'
        r'(?:[/#?][^\s]*)?'
        r'(?=\s|$)'
    ),
]


def _clean_repo_name(repo: str) -> str:
    """Strip a trailing .git suffix and trailing dots from a repo slug."""
    if repo.endswith('.git'):
        repo = repo[:-4]
    return repo.rstrip('.')


def extract_github_urls(text: str) -> list[GitHubRepo]:
    """
    Extract all GitHub repository URLs from text.

    Tolerates "shared"-style URLs produced by GitHub's Share button,
    mobile app, and deep-link flows: URLs that carry extra path segments
    (/blob/..., /tree/..., /pull/..., /share) or tracking query params
    (?utm_source=share, ?tab=readme-ov-file). Every match is normalized
    back to the canonical https://github.com/<owner>/<repo> form so the
    downstream clone/PDF stage receives a clean repo URL.

    Args:
        text: Text that may contain GitHub URLs

    Returns:
        List of parsed GitHubRepo objects (deduplicated by owner/repo)
    """
    repos = []
    seen = set()

    for pattern in GITHUB_PATTERNS:
        for match in pattern.finditer(text):
            owner = match.group(1)
            repo = _clean_repo_name(match.group(2))

            if not repo:
                continue
            if owner.lower() in RESERVED_OWNERS:
                continue

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
