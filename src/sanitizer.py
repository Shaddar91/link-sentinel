"""Sanitize user input before writing to task files."""
import re


# Patterns that should never appear in user prompts
DANGEROUS_PATTERNS = [
    re.compile(r'[`$]'),                      # backticks, shell variable expansion
    re.compile(r';\s*\w'),                     # command chaining
    re.compile(r'\|\s*\w'),                    # pipe to command
    re.compile(r'>\s*/'),                      # redirect to absolute path
    re.compile(r'&&\s*\w'),                    # AND chaining
    re.compile(r'\|\|\s*\w'),                  # OR chaining
    re.compile(r'<\('),                        # process substitution
    re.compile(r'\$\('),                       # command substitution
    re.compile(r'\$\{'),                       # variable expansion
    re.compile(r'\\x[0-9a-fA-F]'),            # hex escape
    re.compile(r'(?:sudo|rm|chmod|chown|wget|curl|eval|exec|sh|bash|python|perl|ruby|nc|ncat)\s', re.IGNORECASE),
]


def sanitize_prompt(text: str) -> str:
    """
    Remove potentially dangerous content from user prompts.
    Only allows plain natural language text.

    Args:
        text: Raw user prompt

    Returns:
        Sanitized text safe for inclusion in task files
    """
    if not text:
        return ""

    # Strip control characters
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        text = pattern.sub('', text)

    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()

    # Hard limit length
    return text[:500]
