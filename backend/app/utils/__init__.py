"""Pure helper utilities (implementation lives in ``text.py``)."""
from app.utils.text import (  # noqa: F401
    FALLBACK_REPLY,
    SYSTEM_PROMPT,
    build_chat_messages,
    chunk_text,
    estimate_severity,
    format_context_block,
    heuristic_classify,
    sanitize_user_text,
)

__all__ = [
    "FALLBACK_REPLY",
    "SYSTEM_PROMPT",
    "build_chat_messages",
    "chunk_text",
    "estimate_severity",
    "format_context_block",
    "heuristic_classify",
    "sanitize_user_text",
]
