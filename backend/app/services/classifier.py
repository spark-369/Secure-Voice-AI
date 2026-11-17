"""Zero-shot alert classification with facebook/bart-large-mnli.

The pipeline is loaded lazily and used from the Celery worker, so the API
process never pays the model-loading cost.
"""
from __future__ import annotations

import logging
import threading

from app.core.config import get_settings
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


class ClassifierNotReadyError(RuntimeError):
    """Raised when the zero-shot pipeline cannot be loaded."""


class ZeroShotClassifier:
    """Thread-safe lazy singleton around the BART-large-MNLI pipeline."""

    _instance: "ZeroShotClassifier | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "ZeroShotClassifier":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._pipeline = None
                    instance._load_lock = threading.Lock()
                    cls._instance = instance
        return cls._instance

    @property
    def is_ready(self) -> bool:
        return self._pipeline is not None

    @staticmethod
    def _resolve_device() -> int:
        settings = get_settings()
        if settings.DEVICE == "cpu":
            return -1
        try:
            import torch

            if settings.DEVICE == "cuda" or (
                settings.DEVICE == "auto" and torch.cuda.is_available()
            ):
                return 0
        except Exception:  # noqa: BLE001
            pass
        return -1

    def load(self) -> None:
        """Download (once) and instantiate the zero-shot pipeline."""
        if self._pipeline is not None:
            return
        with self._load_lock:
            if self._pipeline is not None:
                return
            try:
                from transformers import pipeline
            except Exception as exc:  # noqa: BLE001
                raise ClassifierNotReadyError(
                    "transformers is not installed or failed to import"
                ) from exc

            settings = get_settings()
            device = self._resolve_device()
            logger.info(
                "Loading zero-shot classifier %s (device=%s) …",
                settings.CLASSIFIER_MODEL_NAME,
                device,
            )
            try:
                self._pipeline = pipeline(
                    "zero-shot-classification",
                    model=settings.CLASSIFIER_MODEL_NAME,
                    device=device,
                )
            except Exception as exc:  # noqa: BLE001
                raise ClassifierNotReadyError(
                    f"Failed to load {settings.CLASSIFIER_MODEL_NAME}: {exc}"
                ) from exc
            logger.info("Zero-shot classifier ready")

    def classify(self, text: str) -> dict:
        """Classify a customer utterance into an alert category + severity."""
        if self._pipeline is None:
            self.load()
        result = self._pipeline(
            text, candidate_labels=list(CANDIDATE_LABELS), multi_label=False
        )
        top_label = result["labels"][0]
        top_score = float(result["scores"][0])
        scores = {
            label: round(float(score), 4)
            for label, score in zip(result["labels"], result["scores"])
        }
        return {
            "category": top_label,
            "confidence": round(top_score, 4),
            "scores": scores,
            "severity": estimate_severity(text, top_label, top_score),
            "provider": "zero-shot",
        }


zero_shot_classifier = ZeroShotClassifier()
