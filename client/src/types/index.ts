// Speaker types
export type Speaker = 'ME' | 'THEM';

// Session modes
export type SessionMode = 'interview_assistant' | 'meeting_assistant';

// Connection states
export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error';

// Service states
export type ServiceState = 'idle' | 'connecting' | 'active' | 'error';

// Transcript segment
export interface TranscriptSegment {
  id: string;
  speaker: Speaker;
  text: string;
  timestamp: number;
  isComplete: boolean;
}

// Hint
export interface Hint {
  id: string;
  text: string;
  mode: SessionMode;
  isComplete: boolean;
  timestamp: number;
}

// Session status
export interface SessionStatus {
  connected: boolean;
  sttMicState: ServiceState;
  sttSystemState: ServiceState;
  llmState: ServiceState;
  droppedFramesCount: number;
  hintsEnabled: boolean;
}

// Audio device
export interface AudioDevice {
  deviceId: string;
  label: string;
  kind: 'audioinput' | 'audiooutput';
}

// WebSocket messages from server
export interface TranscriptDeltaMessage {
  type: 'transcript_delta';
  speaker: Speaker;
  text: string;
  segment_id: string;
  timestamp: number;
}

export interface TranscriptCompletedMessage {
  type: 'transcript_completed';
  speaker: Speaker;
  text: string;
  segment_id: string;
  timestamp: number;
}

export interface HintTokenMessage {
  type: 'hint_token';
  hint_id: string;
  token: string;
}

export interface HintCompletedMessage {
  type: 'hint_completed';
  hint_id: string;
  final_text: string;
  mode: string;
}

export interface StatusMessage {
  type: 'status';
  connected: boolean;
  stt_mic_state: string;
  stt_system_state: string;
  llm_state: string;
  dropped_frames_count: number;
  hints_enabled: boolean;
}

export interface ErrorMessage {
  type: 'error';
  message: string;
  code?: string;
}

export type ServerMessage =
  | TranscriptDeltaMessage
  | TranscriptCompletedMessage
  | HintTokenMessage
  | HintCompletedMessage
  | StatusMessage
  | ErrorMessage;

// Client messages
export interface StartSessionMessage {
  type: 'start_session';
}

export interface StopSessionMessage {
  type: 'stop_session';
}

export interface PauseHintsMessage {
  type: 'pause_hints';
}

export interface ResumeHintsMessage {
  type: 'resume_hints';
}

export interface SetModeMessage {
  type: 'set_mode';
  mode: SessionMode;
}

export interface SetPromptMessage {
  type: 'set_prompt';
  prompt: string;
}

export interface SetKnowledgeMessage {
  type: 'set_knowledge';
  workspace: string;
}

export type ClientMessage =
  | StartSessionMessage
  | StopSessionMessage
  | PauseHintsMessage
  | ResumeHintsMessage
  | SetModeMessage
  | SetPromptMessage
  | SetKnowledgeMessage;
