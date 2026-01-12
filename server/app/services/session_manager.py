"""Session manager for handling active sessions."""

import asyncio
from typing import Optional

import structlog

from app.models.session import Session, SessionState, SessionMode
from app.utils.event_bus import EventBus

logger = structlog.get_logger()


class SessionManager:
    """Manages active sessions (single session for POC)."""

    def __init__(self):
        self.current_session: Optional[Session] = None
        self.event_bus = EventBus()
        self._lock = asyncio.Lock()

    async def create_session(self, mode: SessionMode = SessionMode.INTERVIEW_ASSISTANT) -> Session:
        """Create a new session."""
        async with self._lock:
            # For POC: only one session at a time
            if self.current_session and self.current_session.state == SessionState.ACTIVE:
                logger.warning("Session already active, stopping previous session")
                await self._stop_session(self.current_session)

            session = Session(mode=mode)
            self.current_session = session

            logger.info("Session created",
                       session_id=session.session_id,
                       mode=mode.value)

            return session

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        if self.current_session and self.current_session.session_id == session_id:
            return self.current_session
        return None

    async def start_session(self, session: Session) -> None:
        """Start a session."""
        async with self._lock:
            if session.state != SessionState.CREATED:
                logger.warning("Cannot start session in state", state=session.state.value)
                return

            session.state = SessionState.ACTIVE
            logger.info("Session started", session_id=session.session_id)

    async def stop_session(self, session: Session) -> None:
        """Stop a session."""
        async with self._lock:
            await self._stop_session(session)

    async def _stop_session(self, session: Session) -> None:
        """Internal stop session (must be called with lock held)."""
        if session.state == SessionState.STOPPED:
            return

        session.state = SessionState.STOPPED
        await session.cancel_tasks()

        logger.info("Session stopped",
                   session_id=session.session_id,
                   stats={
                       "dropped_frames": session.stats.dropped_frames_count,
                       "transcript_segments": session.stats.transcript_segments,
                       "hints_generated": session.stats.hints_generated,
                   })

    async def destroy_session(self, session_id: str) -> None:
        """Destroy a session."""
        async with self._lock:
            if self.current_session and self.current_session.session_id == session_id:
                await self._stop_session(self.current_session)
                self.current_session = None
                logger.info("Session destroyed", session_id=session_id)

    def set_mode(self, session: Session, mode: SessionMode) -> None:
        """Set session mode."""
        session.mode = mode
        logger.info("Session mode changed",
                   session_id=session.session_id,
                   mode=mode.value)

    def set_hints_enabled(self, session: Session, enabled: bool) -> None:
        """Enable or disable hints."""
        session.hints_enabled = enabled
        logger.info("Hints enabled changed",
                   session_id=session.session_id,
                   hints_enabled=enabled)

    def set_custom_prompt(self, session: Session, prompt: str) -> None:
        """Set custom prompt."""
        session.custom_prompt = prompt
        logger.info("Custom prompt set", session_id=session.session_id)

    def set_knowledge_workspace(self, session: Session, workspace: str) -> None:
        """Set knowledge workspace."""
        session.knowledge_workspace = workspace
        logger.info("Knowledge workspace set",
                   session_id=session.session_id,
                   workspace=workspace)

    async def shutdown(self) -> None:
        """Shutdown manager and cleanup."""
        if self.current_session:
            await self.stop_session(self.current_session)
            self.current_session = None
        self.event_bus.clear()
        logger.info("Session manager shutdown complete")
