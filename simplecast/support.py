from __future__ import annotations

import re


_URL_CREDENTIALS = re.compile(
    r"(?P<scheme>\b(?:icecast|https?)://)"
    r"(?P<user>[^:/@\s]+):(?P<secret>[^@\s]+)@",
    re.IGNORECASE,
)
_NAMED_SECRET = re.compile(
    r"(?P<label>\b(?:password|passwd|pwd|secret)\s*[:=]\s*)"
    r"(?P<secret>[^\s,;]+)",
    re.IGNORECASE,
)


def sanitize_support_text(text: str) -> str:
    """Remove common credential forms before logs leave the computer."""
    text = _URL_CREDENTIALS.sub(
        lambda match: (
            f"{match.group('scheme')}{match.group('user')}:***@"
        ),
        text,
    )
    return _NAMED_SECRET.sub(
        lambda match: f"{match.group('label')}***",
        text,
    )
