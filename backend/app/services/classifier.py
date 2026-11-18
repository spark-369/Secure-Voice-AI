"""LLM-backed alert classification via the local Ollama server.

The former facebook/bart-large-mnli zero-shot pipeline is replaced by the
lightweight Qwen chat model: the same Ollama server classifies each utterance
with a **structured-output schema** (enum category + confidence), so no local
torch/transformers stack is needed. Runs inside the Celery worker; the API
process never pays the inference cost.
"""
from __future__ import annotations

import logging
import threading

from app.core.config import get_settings
from app.services.llm import llm_engine
from app.utils.text import estimate_severity

logger = logging.getLogger(__name__)

CANDIDATE_LABELS = (
    "billing",
    "technical issue",
    "account access",
    "refund or cancellation",
    "product question",
    "complaint",
    "urgent escalation",
    "general inquiry",
)

CLASSIFIER_SYSTEM_PROMPT = (
    "You are a strict classifier for customer-support messages. Choose the single "
    "best-fitting category for the user message and estimate your confidence "
    "(0.0-1.0). Respond only through the required JSON fields."
)

# Structured-output schema for the classification verdict.
CLASSIFICATION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": list(CANDIDATE_LABELS),
            "description": "The best-fitting support category.",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Classifier confidence between 0 and 1.",
        },
    },
    "required": ["category", "confidence"],
    "additionalProperties": False,
}


class ClassifierNotReadyError(RuntimeError):
    """Raised when the Ollama server cannot serve the classification model."""


class LLMClassifier:
    """Thread-safe lazy singleton that classifies utterances via Ollama."""

    _instance: "LLMClassifier | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "LLMClassifier":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def is_ready(self) -> bool:
        return llm_engine.is_ready

    def load(self) -> None:
        """Verify the shared Ollama chat model (pulled on demand)."""
        llm_engine.load()

    def classify(self, text: str) -> dict:
        """Classify a customer utterance into an alert category + severity."""
        settings = get_settings()
        try:
            verdict = llm_engine.chat_structured(
                [
                    {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                    {"role": "user", "content": (text or "")[: settings.MAX_MESSAGE_CHARS]},
                ],
                schema=CLASSIFICATION_SCHEMA,
                max_new_tokens=80,
                temperature=0.1,
            )
        except Exception as exc:  # noqa: BLE001
            raise ClassifierNotReadyError(f"Ollama classification failed: {exc}") from exc

        category = str(verdict.get("category") or "").strip().lower()
        if category not in CANDIDATE_LABELS:
            # Schema-constrained models rarely leave the enum; guard anyway.
            raise ClassifierNotReadyError(f"Unexpected category {category!r}")
        try:
            confidence = min(max(float(verdict.get("confidence", 0.5)), 0.0), 1.0)
        except (TypeError, ValueError):
            confidence = 0.5

        return {
            "category": category,
            "confidence": round(confidence, 4),
            "scores": {category: round(confidence, 4)},
            "severity": estimate_severity(text, category, confidence),
            "provider": "ollama",
        }


llm_classifier = LLMClassifier()