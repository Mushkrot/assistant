"""Session model for managing active sessions."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class SessionState(str, Enum):
    """Session state."""
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class SessionMode(str, Enum):
    """Session mode."""
    INTERVIEW_ASSISTANT = "interview_assistant"
    MEETING_ASSISTANT = "meeting_assistant"


@dataclass
class SessionStats:
    """Session statistics."""
    dropped_frames_mic: int = 0
    dropped_frames_system: int = 0
    total_frames_mic: int = 0
    total_frames_system: int = 0
    transcript_segments: int = 0
    hints_generated: int = 0
    stt_errors: int = 0
    llm_errors: int = 0

    @property
    def dropped_frames_count(self) -> int:
        """Total dropped frames."""
        return self.dropped_frames_mic + self.dropped_frames_system


@dataclass
class Session:
    """Active session state."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)
    state: SessionState = SessionState.CREATED
    mode: SessionMode = SessionMode.INTERVIEW_ASSISTANT
    hints_enabled: bool = True
    custom_prompt: Optional[str] = None
    knowledge_workspace: Optional[str] = None

    # Audio queues
    mic_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=200))
    system_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=200))

    # Statistics
    stats: SessionStats = field(default_factory=SessionStats)

    # Internal state
    _tasks: list = field(default_factory=list)

    def add_task(self, task: asyncio.Task) -> None:
        """Register a background task."""
        self._tasks.append(task)

    async def cancel_tasks(self) -> None:
        """Cancel all background tasks."""
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._tasks.clear()

    def to_status_dict(self) -> dict:
        """Convert to status dictionary for client."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "mode": self.mode.value,
            "hints_enabled": self.hints_enabled,
            "knowledge_workspace": self.knowledge_workspace,
            "stats": {
                "dropped_frames": self.stats.dropped_frames_count,
                "transcript_segments": self.stats.transcript_segments,
                "hints_generated": self.stats.hints_generated,
            }
        }
