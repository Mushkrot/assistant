"""WebSocket endpoint for real-time audio and events."""

import asyncio
import json
from typing import Optional

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import AUDIO_QUEUE_MAX_SIZE
from app.models.session import Session, SessionState, SessionMode
from app.models.events import (
    SessionStatus,
    TranscriptDelta,
    TranscriptCompleted,
    HintToken,
    HintCompleted,
    ErrorMessage,
)
from app.services.session_manager import SessionManager
from app.utils.event_bus import EventType

logger = structlog.get_logger()

router = APIRouter()


class ConnectionHandler:
    """Handles a single WebSocket connection."""

    def __init__(self, websocket: WebSocket, session_manager: SessionManager):
        self.websocket = websocket
        self.session_manager = session_manager
        self.session: Optional[Session] = None
        self.event_bus = session_manager.event_bus
        self._send_lock = asyncio.Lock()

    async def handle(self) -> None:
        """Main handler for the WebSocket connection."""
        await self.websocket.accept()
        logger.info("WebSocket connected")

        try:
            # Create session
            self.session = await self.session_manager.create_session()

            # Subscribe to events
            await self._subscribe_events()

            # Send initial status
            await self._send_status()

            # Handle messages
            await self._message_loop()

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error("WebSocket error", error=str(e))
            await self._send_error(str(e))
        finally:
            await self._cleanup()

    async def _message_loop(self) -> None:
        """Process incoming WebSocket messages."""
        while True:
            message = await self.websocket.receive()

            if message["type"] == "websocket.disconnect":
                break

            if "bytes" in message:
                await self._handle_audio(message["bytes"])
            elif "text" in message:
                await self._handle_control(message["text"])

    async def _handle_audio(self, data: bytes) -> None:
        """Handle incoming audio frame."""
        if not self.session or self.session.state != SessionState.ACTIVE:
            return

        if len(data) < 2:
            return

        # First byte is channel ID
        channel_id = data[0]
        pcm_data = data[1:]

        # Route to appropriate queue
        if channel_id == 0:  # Mic
            queue = self.session.mic_queue
            self.session.stats.total_frames_mic += 1
        elif channel_id == 1:  # System
            queue = self.session.system_queue
            self.session.stats.total_frames_system += 1
        else:
            return

        # Try to add to queue, drop oldest if full
        try:
            queue.put_nowait(pcm_data)
        except asyncio.QueueFull:
            # Drop oldest frame
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(pcm_data)
            except asyncio.QueueFull:
                pass

            if channel_id == 0:
                self.session.stats.dropped_frames_mic += 1
            else:
                self.session.stats.dropped_frames_system += 1

    async def _handle_control(self, text: str) -> None:
        """Handle control message."""
        try:
            data = json.loads(text)
            msg_type = data.get("type")

            if msg_type == "start_session":
                await self._start_session()
            elif msg_type == "stop_session":
                await self._stop_session()
            elif msg_type == "pause_hints":
                self._set_hints_enabled(False)
            elif msg_type == "resume_hints":
                self._set_hints_enabled(True)
            elif msg_type == "set_mode":
                self._set_mode(data.get("mode", "interview_assistant"))
            elif msg_type == "set_prompt":
                self._set_prompt(data.get("prompt", ""))
            elif msg_type == "set_knowledge":
                self._set_knowledge(data.get("workspace", ""))
            else:
                logger.warning("Unknown message type", msg_type=msg_type)

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON message", error=str(e))
            await self._send_error("Invalid JSON")

    async def _start_session(self) -> None:
        """Start the session and processing pipeline."""
        if not self.session:
            return

        await self.session_manager.start_session(self.session)

        # Import here to avoid circular imports
        from app.services.stt_service import STTService
        from app.services.orchestrator import Orchestrator
        from app.services.llm_service import LLMService

        # Start STT service
        stt_service = STTService(self.session, self.event_bus)
        task = asyncio.create_task(stt_service.run())
        self.session.add_task(task)

        # Start Orchestrator
        orchestrator = Orchestrator(self.session, self.event_bus)
        task = asyncio.create_task(orchestrator.run())
        self.session.add_task(task)

        # Start LLM service
        llm_service = LLMService(self.session, self.event_bus)
        task = asyncio.create_task(llm_service.run())
        self.session.add_task(task)

        await self._send_status()
        logger.info("Session pipeline started", session_id=self.session.session_id)

    async def _stop_session(self) -> None:
        """Stop the session."""
        if not self.session:
            return

        await self.session_manager.stop_session(self.session)
        await self._send_status()

    def _set_hints_enabled(self, enabled: bool) -> None:
        """Set hints enabled state."""
        if self.session:
            self.session_manager.set_hints_enabled(self.session, enabled)
            asyncio.create_task(self._send_status())

    def _set_mode(self, mode: str) -> None:
        """Set session mode."""
        if self.session:
            try:
                session_mode = SessionMode(mode)
                self.session_manager.set_mode(self.session, session_mode)
                asyncio.create_task(self._send_status())
            except ValueError:
                logger.warning("Invalid mode", mode=mode)

    def _set_prompt(self, prompt: str) -> None:
        """Set custom prompt."""
        if self.session:
            self.session_manager.set_custom_prompt(self.session, prompt)

    def _set_knowledge(self, workspace: str) -> None:
        """Set knowledge workspace."""
        if self.session:
            self.session_manager.set_knowledge_workspace(self.session, workspace)

    async def _subscribe_events(self) -> None:
        """Subscribe to event bus events."""
        await self.event_bus.subscribe(EventType.TRANSCRIPT_DELTA, self._on_transcript_delta)
        await self.event_bus.subscribe(EventType.TRANSCRIPT_COMPLETED, self._on_transcript_completed)
        await self.event_bus.subscribe(EventType.HINT_TOKEN, self._on_hint_token)
        await self.event_bus.subscribe(EventType.HINT_COMPLETED, self._on_hint_completed)

    async def _on_transcript_delta(self, event: TranscriptDelta) -> None:
        """Handle transcript delta event."""
        await self._send_json(event.model_dump())

    async def _on_transcript_completed(self, event: TranscriptCompleted) -> None:
        """Handle transcript completed event."""
        await self._send_json(event.model_dump())

    async def _on_hint_token(self, event: HintToken) -> None:
        """Handle hint token event."""
        await self._send_json(event.model_dump())

    async def _on_hint_completed(self, event: HintCompleted) -> None:
        """Handle hint completed event."""
        await self._send_json(event.model_dump())

    async def _send_status(self) -> None:
        """Send session status."""
        if not self.session:
            return

        status = SessionStatus(
            connected=True,
            stt_mic_state="active" if self.session.state == SessionState.ACTIVE else "idle",
            stt_system_state="active" if self.session.state == SessionState.ACTIVE else "idle",
            llm_state="idle",
            dropped_frames_count=self.session.stats.dropped_frames_count,
            hints_enabled=self.session.hints_enabled,
        )
        await self._send_json(status.model_dump())

    async def _send_error(self, message: str) -> None:
        """Send error message."""
        error = ErrorMessage(message=message)
        await self._send_json(error.model_dump())

    async def _send_json(self, data: dict) -> None:
        """Send JSON message with lock."""
        async with self._send_lock:
            try:
                await self.websocket.send_json(data)
            except Exception as e:
                logger.error("Failed to send message", error=str(e))

    async def _cleanup(self) -> None:
        """Cleanup on disconnect."""
        # Unsubscribe from events
        await self.event_bus.unsubscribe(EventType.TRANSCRIPT_DELTA, self._on_transcript_delta)
        await self.event_bus.unsubscribe(EventType.TRANSCRIPT_COMPLETED, self._on_transcript_completed)
        await self.event_bus.unsubscribe(EventType.HINT_TOKEN, self._on_hint_token)
        await self.event_bus.unsubscribe(EventType.HINT_COMPLETED, self._on_hint_completed)

        # Destroy session
        if self.session:
            await self.session_manager.destroy_session(self.session.session_id)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication."""
    session_manager = websocket.app.state.session_manager
    handler = ConnectionHandler(websocket, session_manager)
    await handler.handle()
