"""Event models for WebSocket communication."""

from enum import Enum
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field


class Speaker(str, Enum):
    """Speaker identifier."""
    ME = "ME"
    THEM = "THEM"


class TranscriptDelta(BaseModel):
    """Partial transcript update."""
    type: Literal["transcript_delta"] = "transcript_delta"
    speaker: Speaker
    text: str
    segment_id: str
    timestamp: float


class TranscriptCompleted(BaseModel):
    """Completed transcript segment."""
    type: Literal["transcript_completed"] = "transcript_completed"
    speaker: Speaker
    text: str
    segment_id: str
    timestamp: float


class TextChunk(BaseModel):
    """Aggregated text chunk ready for LLM processing."""
    speaker: Speaker
    text: str
    last_context: str = ""
    global_context: Optional[str] = None
    is_question: bool = False


class HintToken(BaseModel):
    """Streaming hint token."""
    type: Literal["hint_token"] = "hint_token"
    hint_id: str
    token: str


class HintCompleted(BaseModel):
    """Completed hint."""
    type: Literal["hint_completed"] = "hint_completed"
    hint_id: str
    final_text: str
    mode: str


class SessionStatus(BaseModel):
    """Session status update."""
    type: Literal["status"] = "status"
    connected: bool
    stt_mic_state: str = "idle"      # idle, connecting, active, error
    stt_system_state: str = "idle"   # idle, connecting, active, error
    llm_state: str = "idle"          # idle, generating, error
    dropped_frames_count: int = 0
    hints_enabled: bool = True


class ErrorMessage(BaseModel):
    """Error message."""
    type: Literal["error"] = "error"
    message: str
    code: Optional[str] = None


# Client -> Server messages

class StartSessionMessage(BaseModel):
    """Start session command."""
    type: Literal["start_session"] = "start_session"


class StopSessionMessage(BaseModel):
    """Stop session command."""
    type: Literal["stop_session"] = "stop_session"


class PauseHintsMessage(BaseModel):
    """Pause hints command."""
    type: Literal["pause_hints"] = "pause_hints"


class ResumeHintsMessage(BaseModel):
    """Resume hints command."""
    type: Literal["resume_hints"] = "resume_hints"


class SetModeMessage(BaseModel):
    """Set session mode command."""
    type: Literal["set_mode"] = "set_mode"
    mode: str  # interview_assistant, meeting_assistant


class SetPromptMessage(BaseModel):
    """Set custom prompt command."""
    type: Literal["set_prompt"] = "set_prompt"
    prompt: str


class SetKnowledgeMessage(BaseModel):
    """Set knowledge workspace command."""
    type: Literal["set_knowledge"] = "set_knowledge"
    workspace: str


# Union types for parsing
ClientMessage = Union[
    StartSessionMessage,
    StopSessionMessage,
    PauseHintsMessage,
    ResumeHintsMessage,
    SetModeMessage,
    SetPromptMessage,
    SetKnowledgeMessage,
]

ServerMessage = Union[
    TranscriptDelta,
    TranscriptCompleted,
    HintToken,
    HintCompleted,
    SessionStatus,
    ErrorMessage,
]
