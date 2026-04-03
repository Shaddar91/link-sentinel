"""Tests for GitHub URL parser."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.github_parser import (
    extract_github_urls,
    parse_github_url,
    is_github_url,
    GitHubRepo,
)


def test_parse_https_url():
    """Test parsing standard HTTPS GitHub URL."""
    repo = parse_github_url("https://github.com/anthropics/anthropic-cookbook")
    assert repo is not None
    assert repo.owner == "anthropics"
    assert repo.repo == "anthropic-cookbook"
    assert repo.full_name == "anthropics/anthropic-cookbook"


def test_parse_https_url_with_git_suffix():
    """Test parsing HTTPS URL with .git suffix."""
    repo = parse_github_url("https://github.com/owner/repo.git")
    assert repo is not None
    assert repo.owner == "owner"
    assert repo.repo == "repo"


def test_parse_git_ssh_url():
    """Test parsing SSH git URL."""
    repo = parse_github_url("git@github.com:owner/repo.git")
    assert repo is not None
    assert repo.owner == "owner"
    assert repo.repo == "repo"


def test_parse_url_without_protocol():
    """Test parsing URL without protocol."""
    repo = parse_github_url("github.com/owner/repo")
    assert repo is not None
    assert repo.owner == "owner"
    assert repo.repo == "repo"


def test_extract_multiple_urls():
    """Test extracting multiple URLs from text."""
    text = """
    Check out these repos:
    https://github.com/owner1/repo1
    And also this one: https://github.com/owner2/repo2
    """
    repos = extract_github_urls(text)
    assert len(repos) == 2
    assert repos[0].full_name == "owner1/repo1"
    assert repos[1].full_name == "owner2/repo2"


def test_is_github_url_true():
    """Test is_github_url returns True for valid URL."""
    assert is_github_url("https://github.com/owner/repo")


def test_is_github_url_false():
    """Test is_github_url returns False for non-GitHub URL."""
    assert not is_github_url("https://gitlab.com/owner/repo")


def test_clone_url():
    """Test clone URL generation."""
    repo = parse_github_url("https://github.com/owner/repo")
    assert repo.clone_url == "https://github.com/owner/repo.git"


def test_folder_name():
    """Test folder name generation."""
    repo = parse_github_url("https://github.com/owner/repo")
    assert repo.folder_name == "owner_repo"


def test_deduplicate_same_repo():
    """Test that duplicate URLs are deduplicated."""
    text = """
    https://github.com/owner/repo
    github.com/owner/repo
    """
    repos = extract_github_urls(text)
    assert len(repos) == 1


if __name__ == "__main__":
    test_parse_https_url()
    test_parse_https_url_with_git_suffix()
    test_parse_git_ssh_url()
    test_parse_url_without_protocol()
    test_extract_multiple_urls()
    test_is_github_url_true()
    test_is_github_url_false()
    test_clone_url()
    test_folder_name()
    test_deduplicate_same_repo()
    print("All tests passed!")
