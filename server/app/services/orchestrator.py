"""Orchestrator for aggregating transcripts and triggering LLM hints."""

import asyncio
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import structlog

from app.config import (
    AGGREGATION_TIMEOUT_MS,
    AGGREGATION_WORD_THRESHOLD,
    HINT_RATE_LIMIT_MS,
)
from app.models.session import Session, SessionState, SessionMode
from app.models.events import (
    Speaker,
    TranscriptDelta,
    TranscriptCompleted,
    TextChunk,
)
from app.utils.event_bus import EventBus, EventType

logger = structlog.get_logger()

# Question detection patterns
QUESTION_WORDS = [
    r"^what\b",
    r"^why\b",
    r"^how\b",
    r"^when\b",
    r"^where\b",
    r"^who\b",
    r"^which\b",
    r"^can you\b",
    r"^could you\b",
    r"^would you\b",
    r"^tell me\b",
    r"^explain\b",
    r"^describe\b",
    r"^walk me through\b",
    r"^give me an example\b",
]

QUESTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in QUESTION_WORDS]


def is_question(text: str) -> bool:
    """Detect if text is a question or invitation to speak."""
    text = text.strip()

    # Check for question mark
    if "?" in text:
        return True

    # Check for question words at start
    for pattern in QUESTION_PATTERNS:
        if pattern.search(text):
            return True

    return False


@dataclass
class TranscriptSegment:
    """A transcript segment with metadata."""
    speaker: Speaker
    text: str
    segment_id: str
    timestamp: float
    is_complete: bool = False


@dataclass
class TextAggregator:
    """Aggregates transcript deltas into stable chunks."""

    # Current segments being built (by segment_id)
    current_segments: dict = field(default_factory=dict)

    # History of completed segments
    history: deque = field(default_factory=lambda: deque(maxlen=20))

    # Accumulated text for current speaker
    pending_text: str = ""
    pending_speaker: Optional[Speaker] = None
    pending_segment_id: Optional[str] = None
    last_delta_time: float = 0

    def add_delta(self, event: TranscriptDelta) -> None:
        """Add a transcript delta."""
        segment_id = event.segment_id

        if segment_id not in self.current_segments:
            self.current_segments[segment_id] = TranscriptSegment(
                speaker=event.speaker,
                text="",
                segment_id=segment_id,
                timestamp=event.timestamp,
            )

        segment = self.current_segments[segment_id]
        segment.text += event.text
        self.last_delta_time = time.time()

        # Update pending
        self.pending_text = segment.text
        self.pending_speaker = segment.speaker
        self.pending_segment_id = segment_id

    def complete_segment(self, event: TranscriptCompleted) -> Optional[TranscriptSegment]:
        """Complete a segment and return it."""
        segment_id = event.segment_id

        # Create or update segment
        if segment_id in self.current_segments:
            segment = self.current_segments.pop(segment_id)
            segment.text = event.text
            segment.is_complete = True
        else:
            segment = TranscriptSegment(
                speaker=event.speaker,
                text=event.text,
                segment_id=segment_id,
                timestamp=event.timestamp,
                is_complete=True,
            )

        # Add to history
        self.history.append(segment)

        # Clear pending if this was the pending segment
        if self.pending_segment_id == segment_id:
            self.pending_text = ""
            self.pending_speaker = None
            self.pending_segment_id = None

        return segment

    def get_last_context(self, speaker: Speaker, sentences: int = 2) -> str:
        """Get last N sentences from speaker."""
        texts = []
        for segment in reversed(self.history):
            if segment.speaker == speaker:
                texts.append(segment.text)
                if len(texts) >= sentences:
                    break
        return " ".join(reversed(texts))

    def get_global_context(self, max_chars: int = 500) -> str:
        """Get recent conversation context."""
        texts = []
        total_chars = 0

        for segment in reversed(self.history):
            prefix = "[ME]" if segment.speaker == Speaker.ME else "[THEM]"
            text = f"{prefix} {segment.text}"

            if total_chars + len(text) > max_chars:
                break

            texts.append(text)
            total_chars += len(text)

        return "\n".join(reversed(texts))

    def should_trigger_timeout(self) -> bool:
        """Check if we should trigger due to timeout."""
        if not self.pending_text:
            return False

        elapsed_ms = (time.time() - self.last_delta_time) * 1000
        return elapsed_ms >= AGGREGATION_TIMEOUT_MS

    def should_trigger_word_count(self) -> bool:
        """Check if we should trigger due to word count."""
        if not self.pending_text:
            return False

        word_count = len(self.pending_text.split())
        return word_count >= AGGREGATION_WORD_THRESHOLD

    def get_pending_chunk(self) -> Optional[TextChunk]:
        """Get pending text as a chunk if available."""
        if not self.pending_text or not self.pending_speaker:
            return None

        return TextChunk(
            speaker=self.pending_speaker,
            text=self.pending_text,
            last_context=self.get_last_context(self.pending_speaker),
            global_context=self.get_global_context(),
            is_question=is_question(self.pending_text),
        )

    def clear_pending(self) -> None:
        """Clear pending state."""
        self.pending_text = ""
        self.pending_speaker = None
        self.pending_segment_id = None


class Orchestrator:
    """Orchestrates transcript aggregation and LLM trigger logic."""

    def __init__(self, session: Session, event_bus: EventBus):
        self.session = session
        self.event_bus = event_bus
        self.aggregator = TextAggregator()

        self._running = False
        self._last_hint_time: float = 0

    async def run(self) -> None:
        """Run the orchestrator."""
        logger.info("Orchestrator starting", session_id=self.session.session_id)

        try:
            # Subscribe to transcript events
            await self.event_bus.subscribe(EventType.TRANSCRIPT_DELTA, self._on_delta)
            await self.event_bus.subscribe(EventType.TRANSCRIPT_COMPLETED, self._on_completed)

            self._running = True

            # Run timeout check loop
            while self._running and self.session.state == SessionState.ACTIVE:
                await asyncio.sleep(0.1)

                # Check for timeout trigger
                if self.aggregator.should_trigger_timeout():
                    await self._trigger_from_pending()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Orchestrator error", error=str(e))
        finally:
            await self._cleanup()

    async def _on_delta(self, event: TranscriptDelta) -> None:
        """Handle transcript delta."""
        self.aggregator.add_delta(event)

        # Check for word count trigger
        if self.aggregator.should_trigger_word_count():
            await self._trigger_from_pending()

    async def _on_completed(self, event: TranscriptCompleted) -> None:
        """Handle transcript completed."""
        segment = self.aggregator.complete_segment(event)

        if segment:
            await self._maybe_trigger(segment)

    async def _trigger_from_pending(self) -> None:
        """Trigger from pending text."""
        chunk = self.aggregator.get_pending_chunk()
        if chunk:
            await self._process_chunk(chunk)
            self.aggregator.clear_pending()

    async def _maybe_trigger(self, segment: TranscriptSegment) -> None:
        """Decide whether to trigger LLM for this segment."""
        # Build chunk
        chunk = TextChunk(
            speaker=segment.speaker,
            text=segment.text,
            last_context=self.aggregator.get_last_context(segment.speaker),
            global_context=self.aggregator.get_global_context(),
            is_question=is_question(segment.text),
        )

        await self._process_chunk(chunk)

    async def _process_chunk(self, chunk: TextChunk) -> None:
        """Process a text chunk according to mode."""
        # Check if hints are enabled
        if not self.session.hints_enabled:
            return

        mode = self.session.mode

        if mode == SessionMode.INTERVIEW_ASSISTANT:
            await self._process_interview(chunk)
        elif mode == SessionMode.MEETING_ASSISTANT:
            await self._process_meeting(chunk)

    async def _process_interview(self, chunk: TextChunk) -> None:
        """Process chunk in Interview Assistant mode."""
        # Only respond to questions from THEM
        if chunk.speaker != Speaker.THEM:
            return

        if not chunk.is_question:
            return

        logger.info("Interview question detected",
                   text=chunk.text[:50],
                   session_id=self.session.session_id)

        await self.event_bus.publish(EventType.TEXT_CHUNK_READY, chunk)

    async def _process_meeting(self, chunk: TextChunk) -> None:
        """Process chunk in Meeting Assistant mode."""
        # Only respond to THEM
        if chunk.speaker != Speaker.THEM:
            return

        # Rate limiting
        now = time.time()
        elapsed_ms = (now - self._last_hint_time) * 1000

        if elapsed_ms < HINT_RATE_LIMIT_MS:
            logger.debug("Rate limited",
                        elapsed_ms=elapsed_ms,
                        limit_ms=HINT_RATE_LIMIT_MS)
            return

        self._last_hint_time = now

        logger.info("Meeting chunk processed",
                   text=chunk.text[:50],
                   session_id=self.session.session_id)

        await self.event_bus.publish(EventType.TEXT_CHUNK_READY, chunk)

    async def _cleanup(self) -> None:
        """Cleanup orchestrator."""
        self._running = False

        await self.event_bus.unsubscribe(EventType.TRANSCRIPT_DELTA, self._on_delta)
        await self.event_bus.unsubscribe(EventType.TRANSCRIPT_COMPLETED, self._on_completed)

        logger.info("Orchestrator stopped", session_id=self.session.session_id)
