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


def test_shared_link_with_blob_path():
    """Shared link pointing at a specific file is normalized to owner/repo."""
    repo = parse_github_url("https://github.com/owner/repo/blob/main/README.md")
    assert repo is not None
    assert repo.full_name == "owner/repo"
    assert repo.url == "https://github.com/owner/repo"


def test_shared_link_with_tree_path():
    """Shared link pointing at a branch/tree view."""
    repo = parse_github_url("https://github.com/owner/repo/tree/main/src")
    assert repo is not None
    assert repo.full_name == "owner/repo"


def test_shared_link_with_pull_request():
    """Shared link pointing at a pull request."""
    repo = parse_github_url("https://github.com/owner/repo/pull/123")
    assert repo is not None
    assert repo.full_name == "owner/repo"


def test_shared_link_with_issue():
    """Shared link pointing at an issue."""
    repo = parse_github_url("https://github.com/owner/repo/issues/42")
    assert repo is not None
    assert repo.full_name == "owner/repo"


def test_shared_link_with_share_suffix():
    """URL with literal /share path segment (GitHub share flow)."""
    repo = parse_github_url("https://github.com/owner/repo/share")
    assert repo is not None
    assert repo.full_name == "owner/repo"


def test_shared_link_with_utm_share_param():
    """Share-flow URL from GitHub mobile app with utm tracking."""
    repo = parse_github_url("https://github.com/owner/repo?utm_source=share")
    assert repo is not None
    assert repo.full_name == "owner/repo"


def test_shared_link_with_readme_tab_ref():
    """Modern GitHub Share button includes ?tab=readme-ov-file."""
    repo = parse_github_url("https://github.com/owner/repo?tab=readme-ov-file")
    assert repo is not None
    assert repo.full_name == "owner/repo"


def test_shared_link_embedded_in_message():
    """Shared URL surrounded by sentence text still triggers detection."""
    text = (
        "hey man check this out: https://github.com/owner/repo/blob/main/src/bot.py "
        "-- love the structure"
    )
    repos = extract_github_urls(text)
    assert len(repos) == 1
    assert repos[0].full_name == "owner/repo"


def test_shared_link_normalized_to_clone_url():
    """Normalized shared URL must round-trip to the canonical clone URL."""
    repo = parse_github_url("https://github.com/Shaddar91/link-sentinel/tree/main?utm_source=share")
    assert repo is not None
    assert repo.full_name == "Shaddar91/link-sentinel"
    assert repo.clone_url == "https://github.com/Shaddar91/link-sentinel.git"


def test_reserved_owner_settings_skipped():
    """github.com/settings/... is a platform page, not a repo."""
    assert parse_github_url("https://github.com/settings/profile") is None


def test_reserved_owner_marketplace_skipped():
    """github.com/marketplace/... is a platform page, not a repo."""
    assert parse_github_url("https://github.com/marketplace/actions/checkout") is None


def test_www_subdomain_supported():
    """www.github.com/owner/repo should parse just like github.com."""
    repo = parse_github_url("https://www.github.com/owner/repo")
    assert repo is not None
    assert repo.full_name == "owner/repo"


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
    test_shared_link_with_blob_path()
    test_shared_link_with_tree_path()
    test_shared_link_with_pull_request()
    test_shared_link_with_issue()
    test_shared_link_with_share_suffix()
    test_shared_link_with_utm_share_param()
    test_shared_link_with_readme_tab_ref()
    test_shared_link_embedded_in_message()
    test_shared_link_normalized_to_clone_url()
    test_reserved_owner_settings_skipped()
    test_reserved_owner_marketplace_skipped()
    test_www_subdomain_supported()
    print("All tests passed!")
