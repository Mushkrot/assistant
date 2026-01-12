"""LLM Service for generating hints using Ollama."""

import asyncio
import uuid
from typing import Optional

import httpx
import structlog

from app.config import get_settings, MAX_HINT_POINTS
from app.models.session import Session, SessionState, SessionMode
from app.models.events import TextChunk, HintToken, HintCompleted
from app.utils.event_bus import EventBus, EventType
from app.services.knowledge_service import KnowledgeService

logger = structlog.get_logger()

# Prompt templates
INTERVIEW_SYSTEM_PROMPT = """You are an interview assistant. The interviewer just asked a question.
Based on the question and context, provide 1-3 bullet points to help the candidate structure their answer.

Be concise. Each point should be 5-15 words.
Focus on: key points to mention, structure suggestion, relevant terms.

Do NOT repeat the question. Do NOT write full answers. Do NOT use numbering.
Output ONLY bullet points starting with "- ".

{knowledge_context}"""

MEETING_SYSTEM_PROMPT = """You are a meeting assistant. Analyze what was just said and provide helpful context in 1-3 bullet points.

Be concise. Each point should be 5-15 words.
Focus on: term explanations, relevant context, follow-up suggestions.

Do NOT repeat what was said. Do NOT use numbering.
Output ONLY bullet points starting with "- ".

{knowledge_context}"""


class LLMService:
    """Service for generating hints using Ollama LLM."""

    def __init__(self, session: Session, event_bus: EventBus):
        self.session = session
        self.event_bus = event_bus
        self.knowledge_service = KnowledgeService()

        self._running = False
        self._generating = False
        self._cancel_event = asyncio.Event()
        self._current_hint_id: Optional[str] = None
        self._pending_chunk: Optional[TextChunk] = None

    async def run(self) -> None:
        """Run the LLM service."""
        logger.info("LLM service starting", session_id=self.session.session_id)

        try:
            await self.event_bus.subscribe(EventType.TEXT_CHUNK_READY, self._on_chunk)

            self._running = True

            while self._running and self.session.state == SessionState.ACTIVE:
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("LLM service error", error=str(e))
        finally:
            await self._cleanup()

    async def _on_chunk(self, chunk: TextChunk) -> None:
        """Handle incoming text chunk."""
        if not self.session.hints_enabled:
            return

        if self._generating:
            # Handle based on mode
            if self.session.mode == SessionMode.INTERVIEW_ASSISTANT:
                # Cancel current and start new (new question is priority)
                self._cancel_event.set()
                self._pending_chunk = chunk
            else:
                # Latest wins - just replace pending
                self._pending_chunk = chunk
            return

        await self._generate_hint(chunk)

    async def _generate_hint(self, chunk: TextChunk) -> None:
        """Generate a hint for the given chunk."""
        self._generating = True
        self._cancel_event.clear()
        self._current_hint_id = str(uuid.uuid4())

        hint_id = self._current_hint_id
        collected_text = ""

        try:
            settings = get_settings()

            # Get knowledge context if workspace is set
            knowledge_context = ""
            if self.session.knowledge_workspace:
                knowledge_context = self.knowledge_service.retrieve(
                    self.session.knowledge_workspace,
                    chunk.text
                )
                if knowledge_context:
                    knowledge_context = f"\nRelevant knowledge:\n{knowledge_context}\n"

            # Build prompt
            if self.session.mode == SessionMode.INTERVIEW_ASSISTANT:
                system_prompt = INTERVIEW_SYSTEM_PROMPT.format(
                    knowledge_context=knowledge_context
                )
            else:
                system_prompt = MEETING_SYSTEM_PROMPT.format(
                    knowledge_context=knowledge_context
                )

            # Add custom prompt if set
            if self.session.custom_prompt:
                system_prompt += f"\n\nAdditional instructions: {self.session.custom_prompt}"

            # Build messages
            messages = [
                {"role": "system", "content": system_prompt},
            ]

            # Add context if available
            if chunk.global_context:
                messages.append({
                    "role": "user",
                    "content": f"Recent conversation:\n{chunk.global_context}"
                })

            # Add the question/statement
            if self.session.mode == SessionMode.INTERVIEW_ASSISTANT:
                messages.append({
                    "role": "user",
                    "content": f"Question: {chunk.text}\n\nProvide 1-3 bullet points:"
                })
            else:
                messages.append({
                    "role": "user",
                    "content": f"Statement: {chunk.text}\n\nProvide 1-3 bullet points:"
                })

            # Stream from Ollama
            url = f"{settings.ollama_base_url}/v1/chat/completions"

            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    url,
                    json={
                        "model": settings.ollama_model,
                        "messages": messages,
                        "stream": True,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9,
                        }
                    }
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error("Ollama error", status=response.status_code, body=error_text)
                        return

                    async for line in response.aiter_lines():
                        # Check for cancellation
                        if self._cancel_event.is_set():
                            logger.info("Hint generation cancelled", hint_id=hint_id)
                            return

                        if not line or not line.startswith("data: "):
                            continue

                        data = line[6:]  # Remove "data: " prefix
                        if data == "[DONE]":
                            break

                        try:
                            import json
                            chunk_data = json.loads(data)
                            delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                            token = delta.get("content", "")

                            if token:
                                collected_text += token

                                # Send token event
                                event = HintToken(hint_id=hint_id, token=token)
                                await self.event_bus.publish(EventType.HINT_TOKEN, event)

                        except Exception as e:
                            logger.debug("Parse error", error=str(e), line=line)

            # Format and send completed hint
            if collected_text and not self._cancel_event.is_set():
                formatted = self._format_hint(collected_text)
                self.session.stats.hints_generated += 1

                event = HintCompleted(
                    hint_id=hint_id,
                    final_text=formatted,
                    mode=self.session.mode.value,
                )
                await self.event_bus.publish(EventType.HINT_COMPLETED, event)

                logger.info("Hint generated",
                           hint_id=hint_id,
                           length=len(formatted),
                           session_id=self.session.session_id)

        except Exception as e:
            logger.error("Hint generation error", error=str(e))
            await self.event_bus.publish(EventType.LLM_ERROR, str(e))
            self.session.stats.llm_errors += 1

        finally:
            self._generating = False
            self._current_hint_id = None

            # Process pending chunk if any
            if self._pending_chunk:
                chunk = self._pending_chunk
                self._pending_chunk = None
                await self._generate_hint(chunk)

    def _format_hint(self, text: str) -> str:
        """Format hint to ensure 1-3 bullet points."""
        lines = text.strip().split("\n")
        bullet_points = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if it's a bullet point
            if line.startswith("- ") or line.startswith("• ") or line.startswith("* "):
                bullet_points.append(line)
            elif line[0].isdigit() and "." in line[:3]:
                # Convert numbered to bullet
                parts = line.split(".", 1)
                if len(parts) > 1:
                    bullet_points.append(f"- {parts[1].strip()}")
            elif bullet_points:
                # Continuation of previous bullet
                bullet_points[-1] += " " + line

        # Limit to MAX_HINT_POINTS
        bullet_points = bullet_points[:MAX_HINT_POINTS]

        return "\n".join(bullet_points)

    async def _cleanup(self) -> None:
        """Cleanup LLM service."""
        self._running = False
        self._cancel_event.set()

        await self.event_bus.unsubscribe(EventType.TEXT_CHUNK_READY, self._on_chunk)

        logger.info("LLM service stopped", session_id=self.session.session_id)
