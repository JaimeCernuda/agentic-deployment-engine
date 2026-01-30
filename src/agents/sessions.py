"""Session management for multi-turn conversations.

Provides session storage and conversation history tracking for A2A agents.
Sessions enable context persistence across multiple queries.
"""

import logging
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single message in a conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    """A conversation session with history."""

    session_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **metadata: Any) -> None:
        """Add a message to the session history."""
        self.messages.append(Message(role=role, content=content, metadata=metadata))
        self.last_accessed = time.time()

    def get_history_for_prompt(self, max_messages: int = 20) -> str:
        """Format conversation history for inclusion in prompt.

        Args:
            max_messages: Maximum number of recent messages to include.

        Returns:
            Formatted conversation history string.
        """
        if not self.messages:
            return ""

        # Take most recent messages
        recent = self.messages[-max_messages:]

        lines = ["<conversation_history>"]
        for msg in recent:
            role_label = "User" if msg.role == "user" else "Assistant"
            lines.append(f"[{role_label}]: {msg.content}")
        lines.append("</conversation_history>")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp,
                    "metadata": m.metadata,
                }
                for m in self.messages
            ],
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "metadata": self.metadata,
        }


class SessionManager:
    """Manages conversation sessions with LRU eviction."""

    def __init__(
        self,
        max_sessions: int = 100,
        session_ttl_seconds: int = 3600,
    ):
        """Initialize session manager.

        Args:
            max_sessions: Maximum number of sessions to keep in memory.
            session_ttl_seconds: Time-to-live for inactive sessions.
        """
        self.max_sessions = max_sessions
        self.session_ttl = session_ttl_seconds
        self._sessions: OrderedDict[str, Session] = OrderedDict()

    def create_session(self, session_id: str | None = None) -> Session:
        """Create a new session.

        Args:
            session_id: Optional session ID. If None, generates a UUID.

        Returns:
            New Session instance.
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        # Evict old sessions if at capacity
        self._evict_if_needed()

        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        logger.debug(f"Created session: {session_id}")
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get a session by ID.

        Args:
            session_id: Session identifier.

        Returns:
            Session if found and not expired, None otherwise.
        """
        session = self._sessions.get(session_id)
        if session is None:
            return None

        # Check if expired
        if time.time() - session.last_accessed > self.session_ttl:
            self.delete_session(session_id)
            logger.debug(f"Session expired: {session_id}")
            return None

        # Move to end (most recently used)
        self._sessions.move_to_end(session_id)
        session.last_accessed = time.time()
        return session

    def get_or_create_session(self, session_id: str | None) -> Session:
        """Get existing session or create new one.

        Args:
            session_id: Optional session ID. If None or not found, creates new.

        Returns:
            Session instance.
        """
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session

        return self.create_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session identifier.

        Returns:
            True if session was deleted, False if not found.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(f"Deleted session: {session_id}")
            return True
        return False

    def _evict_if_needed(self) -> None:
        """Evict oldest sessions if at capacity."""
        # First, remove expired sessions
        now = time.time()
        expired = [
            sid
            for sid, session in self._sessions.items()
            if now - session.last_accessed > self.session_ttl
        ]
        for sid in expired:
            del self._sessions[sid]
            logger.debug(f"Evicted expired session: {sid}")

        # Then evict oldest if still at capacity
        while len(self._sessions) >= self.max_sessions:
            oldest_id = next(iter(self._sessions))
            del self._sessions[oldest_id]
            logger.debug(f"Evicted oldest session: {oldest_id}")

    def cleanup_expired(self) -> int:
        """Remove all expired sessions.

        Returns:
            Number of sessions removed.
        """
        now = time.time()
        expired = [
            sid
            for sid, session in self._sessions.items()
            if now - session.last_accessed > self.session_ttl
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    @property
    def session_count(self) -> int:
        """Get current number of sessions."""
        return len(self._sessions)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all active sessions.

        Returns:
            List of session info dictionaries.
        """
        return [
            {
                "session_id": s.session_id,
                "message_count": len(s.messages),
                "created_at": s.created_at,
                "last_accessed": s.last_accessed,
            }
            for s in self._sessions.values()
        ]
