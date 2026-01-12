import { useState, useCallback, useRef, useEffect } from 'react';
import type {
  ConnectionState,
  ServerMessage,
  ClientMessage,
  TranscriptSegment,
  Hint,
  SessionStatus,
} from '@/types';

interface UseWebSocketOptions {
  onTranscriptDelta?: (segment: TranscriptSegment) => void;
  onTranscriptCompleted?: (segment: TranscriptSegment) => void;
  onHintToken?: (hintId: string, token: string) => void;
  onHintCompleted?: (hint: Hint) => void;
  onStatusUpdate?: (status: SessionStatus) => void;
  onError?: (message: string) => void;
}

interface UseWebSocketReturn {
  connectionState: ConnectionState;
  connect: () => void;
  disconnect: () => void;
  sendMessage: (message: ClientMessage) => void;
  sendAudioFrame: (channelId: number, pcmData: ArrayBuffer) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}): UseWebSocketReturn {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const {
    onTranscriptDelta,
    onTranscriptCompleted,
    onHintToken,
    onHintCompleted,
    onStatusUpdate,
    onError,
  } = options;

  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data: ServerMessage = JSON.parse(event.data);

      switch (data.type) {
        case 'transcript_delta':
          onTranscriptDelta?.({
            id: data.segment_id,
            speaker: data.speaker,
            text: data.text,
            timestamp: data.timestamp,
            isComplete: false,
          });
          break;

        case 'transcript_completed':
          onTranscriptCompleted?.({
            id: data.segment_id,
            speaker: data.speaker,
            text: data.text,
            timestamp: data.timestamp,
            isComplete: true,
          });
          break;

        case 'hint_token':
          onHintToken?.(data.hint_id, data.token);
          break;

        case 'hint_completed':
          onHintCompleted?.({
            id: data.hint_id,
            text: data.final_text,
            mode: data.mode as 'interview_assistant' | 'meeting_assistant',
            isComplete: true,
            timestamp: Date.now() / 1000,
          });
          break;

        case 'status':
          onStatusUpdate?.({
            connected: data.connected,
            sttMicState: data.stt_mic_state as 'idle' | 'active' | 'error',
            sttSystemState: data.stt_system_state as 'idle' | 'active' | 'error',
            llmState: data.llm_state as 'idle' | 'generating' | 'error',
            droppedFramesCount: data.dropped_frames_count,
            hintsEnabled: data.hints_enabled,
          });
          break;

        case 'error':
          onError?.(data.message);
          break;
      }
    } catch (err) {
      console.error('Failed to parse WebSocket message:', err);
    }
  }, [onTranscriptDelta, onTranscriptCompleted, onHintToken, onHintCompleted, onStatusUpdate, onError]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setConnectionState('connecting');

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionState('connected');
      console.log('WebSocket connected');
    };

    ws.onmessage = handleMessage;

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionState('error');
    };

    ws.onclose = () => {
      setConnectionState('disconnected');
      console.log('WebSocket disconnected');

      // Auto-reconnect after 3 seconds
      reconnectTimeoutRef.current = window.setTimeout(() => {
        if (wsRef.current === ws) {
          console.log('Attempting to reconnect...');
          connect();
        }
      }, 3000);
    };
  }, [handleMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionState('disconnected');
  }, []);

  const sendMessage = useCallback((message: ClientMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const sendAudioFrame = useCallback((channelId: number, pcmData: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Create frame with channel ID header
      const header = new Uint8Array([channelId]);
      const frame = new Uint8Array(header.length + pcmData.byteLength);
      frame.set(header, 0);
      frame.set(new Uint8Array(pcmData), header.length);
      wsRef.current.send(frame.buffer);
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    connectionState,
    connect,
    disconnect,
    sendMessage,
    sendAudioFrame,
  };
}
