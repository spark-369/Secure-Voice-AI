"""Unit tests for the dependency-free text helpers.

Run from ``backend/``:  python -m pytest -q
These tests intentionally avoid the ML stack (torch/transformers/chromadb).
"""
from app.utils.text import (
    build_chat_messages,
    chunk_text,
    estimate_severity,
    heuristic_classify,
    sanitize_user_text,
)


# ---------------------------------------------------------------------------
# sanitize_user_text
# ---------------------------------------------------------------------------


def test_sanitize_strips_control_characters_and_collapses_whitespace():
    assert sanitize_user_text("  a\t b  \n\n\n c\x00 ") == "a b \n\n c"


def test_sanitize_truncates_to_max_chars():
    assert sanitize_user_text("x" * 50, max_chars=10) == "x" * 10


def test_sanitize_rejects_non_string_input():
    assert sanitize_user_text(None) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# chunk_text
# ---------------------------------------------------------------------------


def test_chunk_text_short_input_is_single_chunk():
    assert chunk_text("Short sentence.", 700, 120) == ["Short sentence."]


def test_chunk_text_empty_input_returns_empty_list():
    assert chunk_text("", 700, 120) == []
    assert chunk_text("   ", 700, 120) == []


def test_chunk_text_respects_chunk_size():
    text = " ".join(f"Sentence number {i} explains something useful." for i in range(120))
    chunks = chunk_text(text, chunk_size=120, overlap=20)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 120 for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)


def test_chunk_text_preserves_content():
    text = " ".join(f"Point {i} about the policy." for i in range(60))
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert "Point 0 about" in chunks[0]
    assert "Point 59" in chunks[-1]


# ---------------------------------------------------------------------------
# estimate_severity / heuristic_classify
# ---------------------------------------------------------------------------


def test_severity_high_for_legal_threats():
    severity = estimate_severity("I will call my lawyer about this", "complaint", 0.9)
    assert severity >= 0.8


def test_severity_low_for_polite_inquiry():
    severity = estimate_severity("Hi, I have a small question please", "general inquiry", 0.9)
    assert severity <= 0.3


def test_severity_medium_for_refund_complaint():
    severity = estimate_severity("I want a refund, this product is broken", "technical issue", 0.9)
    assert 0.5 <= severity < 0.8


def test_heuristic_classify_detects_billing():
    result = heuristic_classify("I was charged twice on my card, this is unacceptable")
    assert result["provider"] == "heuristic"
    assert result["category"] in ("billing", "complaint")
    assert result["severity"] >= 0.5
    assert result["scores"]


# ---------------------------------------------------------------------------
# build_chat_messages
# ---------------------------------------------------------------------------


def test_build_chat_messages_includes_system_context_and_history():
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "tool", "content": "should be dropped"},
    ]
    messages = build_chat_messages(history, "help me", context_block="CONTEXT BLOCK")
    assert messages[0]["role"] == "system"
    assert "CONTEXT BLOCK" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "help me"}
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]


def test_build_chat_messages_without_context():
    messages = build_chat_messages([], "question only")
    assert len(messages) == 2
    assert "Relevant knowledge-base excerpts" not in messages[0]["content"]
