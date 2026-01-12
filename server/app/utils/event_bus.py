"""Internal event bus for async communication between components."""

import asyncio
from enum import Enum
from typing import Any, Callable, Coroutine
from collections import defaultdict
import structlog

logger = structlog.get_logger()


class EventType(str, Enum):
    """Event types for internal communication."""
    # Audio events
    AUDIO_FRAME_MIC = "audio_frame_mic"
    AUDIO_FRAME_SYSTEM = "audio_frame_system"

    # Transcript events
    TRANSCRIPT_DELTA = "transcript_delta"
    TRANSCRIPT_COMPLETED = "transcript_completed"

    # Orchestrator events
    TEXT_CHUNK_READY = "text_chunk_ready"

    # Hint events
    HINT_TOKEN = "hint_token"
    HINT_COMPLETED = "hint_completed"

    # Session events
    SESSION_STARTED = "session_started"
    SESSION_STOPPED = "session_stopped"
    SESSION_STATUS = "session_status"

    # Error events
    STT_ERROR = "stt_error"
    LLM_ERROR = "llm_error"


# Type alias for event handlers
EventHandler = Callable[[Any], Coroutine[Any, Any, None]]


class EventBus:
    """Async event bus for internal component communication."""

    def __init__(self):
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe to an event type."""
        async with self._lock:
            if handler not in self._handlers[event_type]:
                self._handlers[event_type].append(handler)
                logger.debug("Handler subscribed", event_type=event_type.value)

    async def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Unsubscribe from an event type."""
        async with self._lock:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
                logger.debug("Handler unsubscribed", event_type=event_type.value)

    async def publish(self, event_type: EventType, payload: Any = None) -> None:
        """Publish an event to all subscribers."""
        async with self._lock:
            handlers = list(self._handlers[event_type])

        if not handlers:
            return

        # Execute all handlers concurrently
        tasks = [
            asyncio.create_task(self._safe_call(handler, payload))
            for handler in handlers
        ]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_call(self, handler: EventHandler, payload: Any) -> None:
        """Safely call a handler, catching exceptions."""
        try:
            await handler(payload)
        except Exception as e:
            logger.error("Event handler error",
                        handler=handler.__name__,
                        error=str(e))

    def clear(self) -> None:
        """Clear all handlers."""
        self._handlers.clear()
