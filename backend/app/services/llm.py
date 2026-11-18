"""Conversational LLM engine: Qwen2.5-0.5B-Instruct GGUF served by Ollama.

All inference happens in the local Ollama server (model
``hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M``); this process only talks to
it through the ``ollama`` client. Replies use **structured output** — the
model's response is constrained to a JSON schema and parsed here, so callers
always receive clean text.
"""
from __future__ import annotations

import json
import logging
import re
import threading

from app.core.config import get_settings
from app.services.ollama_client import get_ollama_client

logger = logging.getLogger(__name__)


class LLMNotReadyError(RuntimeError):
    """Raised when the Ollama server is unreachable or the model is missing."""


# Structured-output schema for conversational replies and summaries.
# ``additionalProperties: false`` keeps the grammar tight so the model can
# only ever emit the single ``reply`` field.
REPLY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "reply": {
            "type": "string",
            "description": "The assistant's answer, in plain conversational text.",
        }
    },
    "required": ["reply"],
    "additionalProperties": False,
}


class QwenChatEngine:
    """Thread-safe lazy singleton around the Ollama-served Qwen chat model."""

    _instance: "QwenChatEngine | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "QwenChatEngine":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._verified = False
                    instance._load_lock = threading.Lock()
                    cls._instance = instance
        return cls._instance

    @property
    def is_ready(self) -> bool:
        return self._verified

    def load(self) -> None:
        """Ping Ollama and make sure the chat model is pulled locally."""
        if self._verified:
            return
        with self._load_lock:
            if self._verified:
                return
            from app.services.ollama_client import ensure_model

            settings = get_settings()
            try:
                ensure_model(settings.LLM_MODEL_NAME)
            except Exception as exc:  # noqa: BLE001
                raise LLMNotReadyError(
                    f"Ollama server at {settings.OLLAMA_BASE_URL} could not provide "
                    f"{settings.LLM_MODEL_NAME!r} ({exc}). Start it with `ollama serve` "
                    "and pull the model with `ollama pull`."
                ) from exc
            self._verified = True
            logger.info("Ollama chat model ready: %s", settings.LLM_MODEL_NAME)

    def chat_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict,
        *,
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> dict:
        """Chat with a JSON-schema-constrained response; returns the parsed object."""
        self.load()
        settings = get_settings()
        max_new_tokens = max_new_tokens or settings.LLM_MAX_NEW_TOKENS
        temperature = (
            max(settings.LLM_TEMPERATURE, 0.05)
            if temperature is None
            else max(temperature, 0.05)
        )
        response = get_ollama_client().chat(
            model=settings.LLM_MODEL_NAME,
            messages=messages,
            format=schema,  # structured output constrains the response to the schema
            options={
                "temperature": float(temperature),
                "top_p": 0.9,
                "repeat_penalty": 1.1,
                "num_predict": max_new_tokens,
            },
        )
        content = self._extract_content(response)
        return self._parse_structured(content)  # defensive parse — never leaks raw JSON

    def generate(
        self,
        messages: list[dict[str, str]],
        max_new_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        """Generate a reply for a chat-template message list (schema-constrained)."""
        data = self.chat_structured(
            messages,
            REPLY_SCHEMA,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
        )
        return self._clean_reply(data.get("reply"))

    @staticmethod
    def _extract_content(response) -> str:
        """Read ``response.message.content`` from dict or pydantic responses."""
        try:
            message = response["message"]  # works for dicts and ollama models
            content = message["content"]
        except (KeyError, TypeError, AttributeError):
            return ""
        return content or ""

    @classmethod
    def _parse_structured(cls, content: str) -> dict:
        """Parse a structured response into a dict without ever leaking raw JSON.

        Tolerates the real-world failure modes of small models: markdown fences
        around the JSON, stray prose before/after the object, and responses
        truncated at ``num_predict`` (unclosed string or braces).
        """
        text = cls._strip_fences(content)
        for candidate in (text, cls._json_slice(text)):
            data = cls._try_json(candidate)
            if data is not None:
                return data
        # Truncated or malformed: pull the "reply" value out of the raw text.
        extracted = cls._extract_reply_value(text)
        if extracted is not None:
            return {"reply": extracted}
        return {"reply": cls._plain_text_fallback(text)}

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Remove markdown code fences if the model wrapped its output in them."""
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```[A-Za-z]*\s*", "", stripped)
        if stripped.endswith("```"):
            stripped = re.sub(r"\s*```$", "", stripped)
        return stripped.strip()

    @staticmethod
    def _json_slice(text: str) -> str:
        """Isolate the outermost ``{...}`` block (drops stray prose around it)."""
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return text[start : end + 1]
        return text

    @staticmethod
    def _try_json(candidate: str) -> dict | None:
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    # Matches the value of "reply" up to its closing quote — or up to the end
    # of the text when the response was truncated mid-string.
    _REPLY_VALUE_RE = re.compile(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)')

    @classmethod
    def _extract_reply_value(cls, text: str) -> str | None:
        """Truncation-tolerant extraction of the ``reply`` string value."""
        match = cls._REPLY_VALUE_RE.search(text)
        if match is None:
            return None
        fragment = match.group(1)
        # Drop a dangling (incomplete) escape sequence at the cut point.
        while fragment.endswith("\\") and not fragment.endswith("\\\\"):
            fragment = fragment[:-1]
        try:
            value = json.loads(f'"{fragment}"')
        except (json.JSONDecodeError, ValueError):
            return None
        return value.strip() if isinstance(value, str) else None

    @classmethod
    def _plain_text_fallback(cls, text: str) -> str:
        """Last resort: strip JSON scaffolding from the raw text and unescape it."""
        cleaned = cls._strip_fences(text)
        cleaned = re.sub(r'^\s*\{\s*"[^"]*"\s*:\s*"?', "", cleaned)
        cleaned = cleaned.rstrip()
        if cleaned.endswith("}"):
            cleaned = cleaned[:-1].rstrip().rstrip(",").rstrip()
        if cleaned.endswith('"'):
            cleaned = cleaned[:-1].rstrip()
        return cls._unescape(cleaned).strip()

    _ESCAPES_RE = re.compile(r"\\(u[0-9a-fA-F]{4}|.)")
    _ESCAPE_MAP = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/"}

    @classmethod
    def _unescape(cls, text: str) -> str:
        """Single-pass replacement of JSON string escapes (left-to-right)."""

        def _replace(match: re.Match[str]) -> str:
            token = match.group(1)
            if token[0] == "u" and len(token) == 5:
                try:
                    return chr(int(token[1:], 16))
                except ValueError:
                    return match.group(0)
            return cls._ESCAPE_MAP.get(token, match.group(0))

        return cls._ESCAPES_RE.sub(_replace, text)

    @staticmethod
    def _clean_reply(value) -> str:
        """Normalise the reply into clean plain text (chat UI / TTS friendly)."""
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
        # Small models sometimes wrap the whole reply in stray quotes.
        if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'“”":
            text = text[1:-1].strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


llm_engine = QwenChatEngine()