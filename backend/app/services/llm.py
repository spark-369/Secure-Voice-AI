"""Conversational LLM engine: Qwen/Qwen2.5-0.5B-Instruct via Transformers.

Heavy imports (torch/transformers) happen lazily inside ``load`` so that the
API can boot — and answer health checks — even before models are downloaded.
"""
from __future__ import annotations

import logging
import threading

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMNotReadyError(RuntimeError):
    """Raised when the model cannot be loaded or used."""


class QwenChatEngine:
    """Thread-safe lazy singleton around the Qwen2.5 instruct model."""

    _instance: "QwenChatEngine | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "QwenChatEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._model = None
                    instance._tokenizer = None
                    instance._device = "cpu"
                    instance._load_lock = threading.Lock()
                    cls._instance = instance
        return cls._instance

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str:
        return self._device

    @staticmethod
    def _resolve_device() -> str:
        settings = get_settings()
        if settings.DEVICE in ("cpu", "cuda"):
            return settings.DEVICE
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:  # noqa: BLE001
            return "cpu"

    def load(self) -> None:
        """Download (once) and load the model onto the target device."""
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except Exception as exc:  # noqa: BLE001
                raise LLMNotReadyError(
                    "torch/transformers are not installed or failed to import"
                ) from exc

            settings = get_settings()
            device = self._resolve_device()
            dtype = torch.float16 if device == "cuda" else torch.float32
            logger.info("Loading LLM %s on %s …", settings.LLM_MODEL_NAME, device)
            try:
                tokenizer = AutoTokenizer.from_pretrained(settings.LLM_MODEL_NAME)
                model = AutoModelForCausalLM.from_pretrained(
                    settings.LLM_MODEL_NAME, torch_dtype=dtype
                )
                model.to(device)
                model.eval()
            except Exception as exc:  # noqa: BLE001
                raise LLMNotReadyError(
                    f"Failed to load {settings.LLM_MODEL_NAME}: {exc}"
                ) from exc
            self._model, self._tokenizer, self._device = model, tokenizer, device
            logger.info("LLM ready (device=%s)", device)

    def generate(
        self,
        messages: list[dict[str, str]],
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Generate a reply for a chat-template message list."""
        settings = get_settings()
        if self._model is None:
            self.load()
        import torch

        max_new_tokens = max_new_tokens or settings.LLM_MAX_NEW_TOKENS
        temperature = (
            max(settings.LLM_TEMPERATURE, 0.05)
            if temperature is None
            else max(temperature, 0.05)
        )
        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        with torch.inference_mode():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=float(temperature),
                top_p=0.9,
                repetition_penalty=1.1,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        completion = output_ids[0][inputs["input_ids"].shape[-1] :]
        return self._tokenizer.decode(completion, skip_special_tokens=True).strip()


llm_engine = QwenChatEngine()
