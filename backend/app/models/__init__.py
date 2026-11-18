"""ORM models. Importing this package registers every table on ``Base.metadata``."""
from app.models.alert import Alert  # noqa: F401
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.session import ConversationSession  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "Alert",
    "ConversationSession",
    "KnowledgeChunk",
    "KnowledgeDocument",
    "Message",
    "User",
]
