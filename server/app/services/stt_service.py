"""STT Service using OpenAI Realtime API for transcription."""

import asyncio
import base64
import json
import time
import uuid
from typing import Optional, Callable, Any

import aiohttp
import structlog

from app.config import get_settings, SAMPLE_RATE_STT
from app.models.session import Session, SessionState
from app.models.events import Speaker, TranscriptDelta, TranscriptCompleted
from app.utils.event_bus import EventBus, EventType
from app.utils.audio import resample_16k_to_24k

logger = structlog.get_logger()


class RealtimeSTTClient:
    """Client for OpenAI Realtime API transcription."""

    REALTIME_URL = "wss://api.openai.com/v1/realtime"
    MODEL = "gpt-4o-mini-transcribe"

    def __init__(
        self,
        speaker: Speaker,
        on_delta: Callable[[str, str], Any],
        on_completed: Callable[[str, str], Any],
    ):
        self.speaker = speaker
        self.on_delta = on_delta
        self.on_completed = on_completed

        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        self._current_segment_id: Optional[str] = None
        self._receive_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Connect to OpenAI Realtime API."""
        settings = get_settings()

        try:
            self._session = aiohttp.ClientSession()

            headers = {
                "Authorization": f"Bearer {settings.openai_api_key}",
                "OpenAI-Beta": "realtime=v1",
            }

            url = f"{self.REALTIME_URL}?model={self.MODEL}"
            self._ws = await self._session.ws_connect(url, headers=headers)

            # Configure session for transcription
            await self._configure_session()

            self._connected = True
            self._receive_task = asyncio.create_task(self._receive_loop())

            logger.info("STT client connected", speaker=self.speaker.value)
            return True

        except Exception as e:
            logger.error("STT connection failed", speaker=self.speaker.value, error=str(e))
            await self.disconnect()
            return False

    async def _configure_session(self) -> None:
        """Configure the Realtime session for transcription."""
        config = {
            "type": "session.update",
            "session": {
                "input_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "gpt-4o-mini-transcribe",
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 300,
                },
            }
        }
        await self._send(config)

    async def disconnect(self) -> None:
        """Disconnect from OpenAI Realtime API."""
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._session:
            await self._session.close()
            self._session = None

        logger.info("STT client disconnected", speaker=self.speaker.value)

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """Send audio data to OpenAI."""
        if not self._connected or not self._ws:
            return

        # Encode to base64
        audio_b64 = base64.b64encode(pcm_bytes).decode("utf-8")

        message = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        }
        await self._send(message)

    async def _send(self, data: dict) -> None:
        """Send JSON message to WebSocket."""
        if self._ws and not self._ws.closed:
            try:
                await self._ws.send_json(data)
            except Exception as e:
                logger.error("Failed to send to STT", error=str(e))

    async def _receive_loop(self) -> None:
        """Receive and process messages from OpenAI."""
        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._handle_message(json.loads(msg.data))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("STT WebSocket error", error=str(self._ws.exception()))
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("STT receive error", error=str(e))

    async def _handle_message(self, data: dict) -> None:
        """Handle incoming message from OpenAI."""
        msg_type = data.get("type", "")

        if msg_type == "session.created":
            logger.debug("STT session created", speaker=self.speaker.value)

        elif msg_type == "session.updated":
            logger.debug("STT session updated", speaker=self.speaker.value)

        elif msg_type == "input_audio_buffer.speech_started":
            # New speech segment started
            self._current_segment_id = str(uuid.uuid4())
            logger.debug("Speech started",
                        speaker=self.speaker.value,
                        segment_id=self._current_segment_id)

        elif msg_type == "input_audio_buffer.speech_stopped":
            logger.debug("Speech stopped", speaker=self.speaker.value)

        elif msg_type == "conversation.item.input_audio_transcription.delta":
            # Partial transcription
            delta = data.get("delta", "")
            if delta and self._current_segment_id:
                await self.on_delta(delta, self._current_segment_id)

        elif msg_type == "conversation.item.input_audio_transcription.completed":
            # Completed transcription
            transcript = data.get("transcript", "")
            if transcript:
                segment_id = self._current_segment_id or str(uuid.uuid4())
                await self.on_completed(transcript, segment_id)
                self._current_segment_id = None

        elif msg_type == "error":
            error = data.get("error", {})
            logger.error("STT API error",
                        speaker=self.speaker.value,
                        error=error)


class STTService:
    """Service managing STT for both audio channels."""

    def __init__(self, session: Session, event_bus: EventBus):
        self.session = session
        self.event_bus = event_bus

        self._mic_client: Optional[RealtimeSTTClient] = None
        self._system_client: Optional[RealtimeSTTClient] = None
        self._running = False

    async def run(self) -> None:
        """Run the STT service."""
        logger.info("STT service starting", session_id=self.session.session_id)

        try:
            # Create STT clients
            self._mic_client = RealtimeSTTClient(
                speaker=Speaker.ME,
                on_delta=self._on_mic_delta,
                on_completed=self._on_mic_completed,
            )
            self._system_client = RealtimeSTTClient(
                speaker=Speaker.THEM,
                on_delta=self._on_system_delta,
                on_completed=self._on_system_completed,
            )

            # Connect both clients
            mic_connected = await self._mic_client.connect()
            system_connected = await self._system_client.connect()

            if not mic_connected or not system_connected:
                logger.error("Failed to connect STT clients")
                await self.event_bus.publish(EventType.STT_ERROR, "Failed to connect to STT")
                return

            self._running = True

            # Start audio processing tasks
            mic_task = asyncio.create_task(self._process_mic_audio())
            system_task = asyncio.create_task(self._process_system_audio())

            # Wait for session to stop
            while self._running and self.session.state == SessionState.ACTIVE:
                await asyncio.sleep(0.1)

            # Cancel tasks
            mic_task.cancel()
            system_task.cancel()

            try:
                await asyncio.gather(mic_task, system_task, return_exceptions=True)
            except asyncio.CancelledError:
                pass

        except Exception as e:
            logger.error("STT service error", error=str(e))
            await self.event_bus.publish(EventType.STT_ERROR, str(e))
        finally:
            await self._cleanup()

    async def _process_mic_audio(self) -> None:
        """Process audio from mic queue."""
        while self._running:
            try:
                pcm_16k = await asyncio.wait_for(
                    self.session.mic_queue.get(),
                    timeout=0.1
                )
                pcm_24k = resample_16k_to_24k(pcm_16k)
                await self._mic_client.send_audio(pcm_24k)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Mic audio processing error", error=str(e))

    async def _process_system_audio(self) -> None:
        """Process audio from system queue."""
        while self._running:
            try:
                pcm_16k = await asyncio.wait_for(
                    self.session.system_queue.get(),
                    timeout=0.1
                )
                pcm_24k = resample_16k_to_24k(pcm_16k)
                await self._system_client.send_audio(pcm_24k)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("System audio processing error", error=str(e))

    async def _on_mic_delta(self, text: str, segment_id: str) -> None:
        """Handle mic transcript delta."""
        event = TranscriptDelta(
            speaker=Speaker.ME,
            text=text,
            segment_id=segment_id,
            timestamp=time.time(),
        )
        await self.event_bus.publish(EventType.TRANSCRIPT_DELTA, event)

    async def _on_mic_completed(self, text: str, segment_id: str) -> None:
        """Handle mic transcript completed."""
        self.session.stats.transcript_segments += 1
        event = TranscriptCompleted(
            speaker=Speaker.ME,
            text=text,
            segment_id=segment_id,
            timestamp=time.time(),
        )
        await self.event_bus.publish(EventType.TRANSCRIPT_COMPLETED, event)

    async def _on_system_delta(self, text: str, segment_id: str) -> None:
        """Handle system transcript delta."""
        event = TranscriptDelta(
            speaker=Speaker.THEM,
            text=text,
            segment_id=segment_id,
            timestamp=time.time(),
        )
        await self.event_bus.publish(EventType.TRANSCRIPT_DELTA, event)

    async def _on_system_completed(self, text: str, segment_id: str) -> None:
        """Handle system transcript completed."""
        self.session.stats.transcript_segments += 1
        event = TranscriptCompleted(
            speaker=Speaker.THEM,
            text=text,
            segment_id=segment_id,
            timestamp=time.time(),
        )
        await self.event_bus.publish(EventType.TRANSCRIPT_COMPLETED, event)

    async def _cleanup(self) -> None:
        """Cleanup STT clients."""
        self._running = False

        if self._mic_client:
            await self._mic_client.disconnect()
        if self._system_client:
            await self._system_client.disconnect()

        logger.info("STT service stopped", session_id=self.session.session_id)
