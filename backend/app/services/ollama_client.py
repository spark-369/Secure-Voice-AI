"""Shared Ollama client factory.

All AI inference (chat, classification and embeddings) is delegated to a local
Ollama server, so this process stays free of torch/transformers. The client is
a process-wide lazy singleton sharing one HTTP connection pool.
"""
from __future__ import annotations

import logging
import threading

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client_lock = threading.Lock()
_client = None
_probe_lock = threading.Lock()
_probe_client = None


def get_ollama_client():
    """Return the shared Ollama client (created on first use)."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                import ollama

                settings = get_settings()
                _client = ollama.Client(
                    host=settings.OLLAMA_BASE_URL,
                    timeout=settings.OLLAMA_TIMEOUT,
                )
                logger.info("Ollama client ready (%s)", settings.OLLAMA_BASE_URL)
    return _client


def ollama_reachable(timeout: int = 5) -> bool:
    """Cheap connectivity probe with a short timeout (for health checks)."""
    global _probe_client
    try:
        if _probe_client is None:
            with _probe_lock:
                if _probe_client is None:
                    import ollama

                    _probe_client = ollama.Client(
                        host=get_settings().OLLAMA_BASE_URL, timeout=timeout
                    )
        _probe_client.list()
        return True
    except Exception:  # noqa: BLE001
        return False


def ensure_model(model: str) -> None:
    """Verify a model is available locally; pull it once when missing."""
    client = get_ollama_client()
    try:
        client.show(model)
        return
    except Exception:  # noqa: BLE001 - model not present (or server hiccup)
        pass
    logger.info("Pulling Ollama model %s …", model)
    client.pull(model)
