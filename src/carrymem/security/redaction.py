"""Auto-redaction — Automatically detect and block sensitive content from memory storage.

Inspired by claude-mem's <private> tag that lets users mark sensitive content
to be excluded from the memory store. CarryMem takes this further by
automatically detecting common sensitive patterns (API keys, passwords, tokens,
connection strings) and blocking them from being stored.

This module provides a non-critical safety net: if detection fails, the worst
case is that sensitive content gets stored (same as before this module existed).
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Sensitive patterns
# ---------------------------------------------------------------------------

# Each pattern is (name, regex, description)
SENSITIVE_PATTERNS: List[Tuple[str, re.Pattern, str]] = [
    # API keys
    ("openai_api_key", re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"), "OpenAI API key"),
    ("github_token", re.compile(r"\bghp_[a-zA-Z0-9]{36}\b"), "GitHub personal access token"),
    ("github_oauth", re.compile(r"\bgho_[a-zA-Z0-9]{36}\b"), "GitHub OAuth token"),
    ("github_app", re.compile(r"\bghs_[a-zA-Z0-9]{36}\b"), "GitHub app token"),
    ("github_refresh", re.compile(r"\bghr_[a-zA-Z0-9]{36}\b"), "GitHub refresh token"),
    ("anthropic_key", re.compile(r"\bsk-ant-[a-zA-Z0-9\-]{20,}\b"), "Anthropic API key"),
    ("aws_access_key", re.compile(r"\bAKIA[A-Z0-9]{16}\b"), "AWS access key ID"),
    ("aws_secret_key", re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*\S+"), "AWS secret key"),
    ("google_api_key", re.compile(r"\bAIza[a-zA-Z0-9\-_]{35}\b"), "Google API key"),
    ("stripe_secret_key", re.compile(r"\bsk_live_[a-zA-Z0-9]{24,}\b"), "Stripe secret key"),
    ("stripe_publishable_key", re.compile(r"\bpk_live_[a-zA-Z0-9]{24,}\b"), "Stripe publishable key"),
    ("slack_bot_token", re.compile(r"\bxoxb-[a-zA-Z0-9\-]{10,}\b"), "Slack bot token"),
    ("slack_user_token", re.compile(r"\bxoxp-[a-zA-Z0-9\-]{10,}\b"), "Slack user token"),
    ("sendgrid_key", re.compile(r"\bSG\.[a-zA-Z0-9\-_]{22,}\.[a-zA-Z0-9\-_]{43,}\b"), "SendGrid API key"),
    (
        "generic_api_key",
        re.compile(r'(?i)(?:api[_-]?key|apikey)\s*[=:]\s*["\']?[a-zA-Z0-9\-_]{20,}["\']?'),
        "Generic API key",
    ),
    # Passwords
    (
        "password_assignment",
        re.compile(r'(?i)(?:password|passwd|pwd)\s*(?:=|:)\s*["\']?[^\s"\']{4,}["\']?'),
        "Password assignment",
    ),
    ("password_in_url", re.compile(r"://[^/\s:]+:[^/\s@]+@"), "Credentials in URL"),
    # Tokens
    ("bearer_token", re.compile(r"(?i)bearer\s+[a-zA-Z0-9\-_.~+/]+=*"), "Bearer token"),
    (
        "jwt_token",
        re.compile(r"\beyJ[a-zA-Z0-9\-_.~+/]+=*\.eyJ[a-zA-Z0-9\-_.~+/]+=*\." r"[a-zA-Z0-9\-_.~+/]+=*"),
        "JWT token",
    ),
    (
        "generic_token",
        re.compile(
            r"(?i)(?:token|access_token|refresh_token|auth_token)\s*[=:]\s*" r'["\']?[a-zA-Z0-9\-_.~+/]{20,}["\']?'
        ),
        "Generic token",
    ),
    # Private keys
    ("private_key", re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"), "Private key"),
    # Connection strings
    (
        "db_connection_string",
        re.compile(r"(?i)(?:mongodb|postgres(?:ql)?|mysql|redis|amqp)://[^\s]+"),
        "Database connection string",
    ),
    (
        "db_connection_string_with_creds",
        re.compile(r"(?i)(?:mongodb|postgres(?:ql)?|mysql|redis|amqp)://" r"[^/\s:]+:[^/\s@]+@[^\s]+"),
        "Database connection string with credentials",
    ),
    # Secrets
    (
        "generic_secret",
        re.compile(r"(?i)(?:secret|credential|private_key)\s*[=:]\s*" r'["\']?[a-zA-Z0-9\-_.~+/]{20,}["\']?'),
        "Generic secret",
    ),
    # .env patterns
    (
        "env_sensitive",
        re.compile(r"(?i)(?:SECRET_KEY|PRIVATE_KEY|ENCRYPTION_KEY|AUTH_SECRET)\s*=\s*" r'["\']?[^\s"\']{8,}["\']?'),
        "Sensitive env variable",
    ),
]


def detect_sensitive_content(text: str, mask_matches: bool = True) -> List[Tuple[str, str, str]]:
    """Detect sensitive content in text.

    Args:
        text: The text to check for sensitive content.
        mask_matches: If True, truncate matched text to first 8 chars + '...'.
                     Set to False for internal redaction logic that needs full matches.

    Returns:
        List of (pattern_name, matched_text_or_mask, description) tuples.
        Empty list means no sensitive content detected.
    """
    if not text:
        return []

    findings = []
    for name, pattern, description in SENSITIVE_PATTERNS:
        for match in pattern.finditer(text):
            matched = match.group(0)
            if mask_matches and len(matched) > 12:
                matched = matched[:8] + "..."
            findings.append((name, matched, description))

    return findings


def should_redact(text: str) -> Tuple[bool, Optional[str]]:
    """Check if text should be redacted (blocked from memory storage).

    Args:
        text: The text to check.

    Returns:
        Tuple of (should_redact, reason).
        If should_redact is True, reason contains a human-readable explanation.
    """
    findings = detect_sensitive_content(text)
    if not findings:
        return False, None

    # Build reason string
    descriptions = set(f[2] for f in findings)
    reason = f"Sensitive content detected: {', '.join(descriptions)}"
    return True, reason


def redact_content(text: str, replacement: str = "[REDACTED]") -> str:
    """Redact sensitive content in text by replacing it with a placeholder.

    Collects all match spans first, then replaces from end to start
    to avoid overlapping replacements from sequential pattern application.

    Args:
        text: The text to redact.
        replacement: The string to replace sensitive content with.

    Returns:
        The text with sensitive content replaced.
    """
    spans = []
    for _name, pattern, _description in SENSITIVE_PATTERNS:
        for match in pattern.finditer(text):
            spans.append((match.start(), match.end()))

    if not spans:
        return text

    spans.sort(key=lambda s: s[0])

    merged: List[Tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    result = text
    for start, end in reversed(merged):
        result = result[:start] + replacement + result[end:]

    return result
