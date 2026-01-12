import { useState, useCallback, useEffect } from 'react';
import { useWebSocket, useAudioDevices, useAudioCapture } from '@/hooks';
import {
  StatusBar,
  DeviceSelector,
  TranscriptFeed,
  HintsPanel,
  ControlBar,
} from '@/components';
import type {
  TranscriptSegment,
  Hint,
  SessionStatus,
  SessionMode,
  ConnectionState,
  ServiceState,
} from '@/types';
import { Settings, X } from 'lucide-react';
import { cn } from '@/lib/utils';

type AppScreen = 'setup' | 'session';

export default function App() {
  // Screen state
  const [screen, setScreen] = useState<AppScreen>('setup');
  const [showSettings, setShowSettings] = useState(false);

  // Device state
  const { devices, hasPermission, requestPermission, loading: devicesLoading } = useAudioDevices();
  const [micDeviceId, setMicDeviceId] = useState<string | null>(null);
  const [systemDeviceId, setSystemDeviceId] = useState<string | null>(null);

  // Session state
  const [isSessionActive, setIsSessionActive] = useState(false);
  const [currentMode, setCurrentMode] = useState<SessionMode>('interview_assistant');
  const [status, setStatus] = useState<SessionStatus>({
    connected: false,
    sttMicState: 'idle',
    sttSystemState: 'idle',
    llmState: 'idle',
    droppedFramesCount: 0,
    hintsEnabled: true,
  });

  // Transcript state
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);

  // Hints state
  const [currentHint, setCurrentHint] = useState<Hint | null>(null);
  const [previousHints, setPreviousHints] = useState<Hint[]>([]);
  const [isGeneratingHint, setIsGeneratingHint] = useState(false);

  // WebSocket callbacks
  const handleTranscriptDelta = useCallback((segment: TranscriptSegment) => {
    setSegments((prev) => {
      const existing = prev.find((s) => s.id === segment.id);
      if (existing) {
        return prev.map((s) =>
          s.id === segment.id ? { ...s, text: s.text + segment.text } : s
        );
      }
      return [...prev, segment];
    });
  }, []);

  const handleTranscriptCompleted = useCallback((segment: TranscriptSegment) => {
    setSegments((prev) => {
      const existing = prev.find((s) => s.id === segment.id);
      if (existing) {
        return prev.map((s) =>
          s.id === segment.id ? { ...segment, isComplete: true } : s
        );
      }
      return [...prev, { ...segment, isComplete: true }];
    });
  }, []);

  const handleHintToken = useCallback((hintId: string, token: string) => {
    setIsGeneratingHint(true);
    setCurrentHint((prev) => {
      if (prev?.id === hintId) {
        return { ...prev, text: prev.text + token };
      }
      return {
        id: hintId,
        text: token,
        mode: currentMode,
        isComplete: false,
        timestamp: Date.now() / 1000,
      };
    });
  }, [currentMode]);

  const handleHintCompleted = useCallback((hint: Hint) => {
    setIsGeneratingHint(false);
    setCurrentHint((prev) => {
      if (prev) {
        setPreviousHints((prevHints) => [...prevHints, { ...prev, ...hint, isComplete: true }]);
      }
      return null;
    });
  }, []);

  const handleStatusUpdate = useCallback((newStatus: SessionStatus) => {
    setStatus(newStatus);
  }, []);

  const handleError = useCallback((message: string) => {
    console.error('WebSocket error:', message);
  }, []);

  // WebSocket hook
  const { connectionState, connect, disconnect, sendMessage, sendAudioFrame } = useWebSocket({
    onTranscriptDelta: handleTranscriptDelta,
    onTranscriptCompleted: handleTranscriptCompleted,
    onHintToken: handleHintToken,
    onHintCompleted: handleHintCompleted,
    onStatusUpdate: handleStatusUpdate,
    onError: handleError,
  });

  // Audio capture callbacks
  const handleMicFrame = useCallback(
    (pcmData: ArrayBuffer) => {
      sendAudioFrame(0, pcmData);
    },
    [sendAudioFrame]
  );

  const handleSystemFrame = useCallback(
    (pcmData: ArrayBuffer) => {
      sendAudioFrame(1, pcmData);
    },
    [sendAudioFrame]
  );

  // Audio capture hook
  const {
    isCapturing,
    start: startCapture,
    stop: stopCapture,
    micLevel,
    systemLevel,
  } = useAudioCapture({
    micDeviceId,
    systemDeviceId,
    onMicFrame: handleMicFrame,
    onSystemFrame: handleSystemFrame,
  });

  // Auto-select default devices
  useEffect(() => {
    if (devices.length > 0 && !micDeviceId) {
      const defaultMic = devices.find(
        (d) => !d.label.toLowerCase().includes('blackhole')
      );
      if (defaultMic) {
        setMicDeviceId(defaultMic.deviceId);
      }
    }
    if (devices.length > 0 && !systemDeviceId) {
      const blackhole = devices.find((d) =>
        d.label.toLowerCase().includes('blackhole')
      );
      if (blackhole) {
        setSystemDeviceId(blackhole.deviceId);
      }
    }
  }, [devices, micDeviceId, systemDeviceId]);

  // Session handlers
  const handleStartSession = useCallback(async () => {
    if (connectionState !== 'connected') {
      connect();
    }

    const captureStarted = await startCapture();
    if (!captureStarted) {
      console.error('Failed to start audio capture');
      return;
    }

    // Wait for connection if not connected
    await new Promise<void>((resolve) => {
      const checkConnection = setInterval(() => {
        if (connectionState === 'connected') {
          clearInterval(checkConnection);
          resolve();
        }
      }, 100);
    });

    sendMessage({ type: 'set_mode', mode: currentMode });
    sendMessage({ type: 'start_session' });
    setIsSessionActive(true);
    setScreen('session');
  }, [connectionState, connect, startCapture, sendMessage, currentMode]);

  const handleStopSession = useCallback(() => {
    sendMessage({ type: 'stop_session' });
    stopCapture();
    setIsSessionActive(false);
  }, [sendMessage, stopCapture]);

  const handleToggleHints = useCallback(() => {
    if (status.hintsEnabled) {
      sendMessage({ type: 'pause_hints' });
    } else {
      sendMessage({ type: 'resume_hints' });
    }
  }, [sendMessage, status.hintsEnabled]);

  const handleModeChange = useCallback(
    (mode: SessionMode) => {
      setCurrentMode(mode);
      if (isSessionActive) {
        sendMessage({ type: 'set_mode', mode });
      }
    },
    [isSessionActive, sendMessage]
  );

  const handleContinueToSession = useCallback(async () => {
    if (!hasPermission) {
      const granted = await requestPermission();
      if (!granted) return;
    }
    connect();
    setScreen('session');
  }, [hasPermission, requestPermission, connect]);

  // Render setup screen
  if (screen === 'setup') {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-gray-800 rounded-xl shadow-xl p-6 space-y-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-white mb-2">
              Realtime Copilot
            </h1>
            <p className="text-gray-400 text-sm">
              AI-powered interview and meeting assistant
            </p>
          </div>

          {!hasPermission ? (
            <div className="space-y-4">
              <p className="text-gray-300 text-sm">
                This app needs microphone access to capture audio.
              </p>
              <button
                onClick={requestPermission}
                disabled={devicesLoading}
                className={cn(
                  'w-full py-3 rounded-lg font-medium transition-colors',
                  'bg-primary-600 hover:bg-primary-500 text-white',
                  'disabled:opacity-50 disabled:cursor-not-allowed'
                )}
              >
                {devicesLoading ? 'Loading...' : 'Grant Microphone Access'}
              </button>
            </div>
          ) : (
            <>
              <DeviceSelector
                devices={devices}
                micDeviceId={micDeviceId}
                systemDeviceId={systemDeviceId}
                onMicChange={setMicDeviceId}
                onSystemChange={setSystemDeviceId}
                micLevel={micLevel}
                systemLevel={systemLevel}
              />

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Mode
                  </label>
                  <select
                    value={currentMode}
                    onChange={(e) => setCurrentMode(e.target.value as SessionMode)}
                    className={cn(
                      'w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg',
                      'text-gray-200 text-sm',
                      'focus:outline-none focus:ring-2 focus:ring-primary-500'
                    )}
                  >
                    <option value="interview_assistant">Interview Assistant</option>
                    <option value="meeting_assistant">Meeting Assistant</option>
                  </select>
                </div>

                <button
                  onClick={handleContinueToSession}
                  disabled={!micDeviceId}
                  className={cn(
                    'w-full py-3 rounded-lg font-medium transition-colors',
                    'bg-primary-600 hover:bg-primary-500 text-white',
                    'disabled:opacity-50 disabled:cursor-not-allowed'
                  )}
                >
                  Continue to Session
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    );
  }

  // Render session screen
  return (
    <div className="h-screen flex flex-col bg-gray-900">
      {/* Status bar */}
      <StatusBar
        connectionState={connectionState}
        sttMicState={status.sttMicState}
        sttSystemState={status.sttSystemState}
        llmState={status.llmState}
        droppedFrames={status.droppedFramesCount}
        hintsEnabled={status.hintsEnabled}
      />

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Transcript feed */}
        <div className="flex-1 flex flex-col border-r border-gray-700">
          <div className="px-4 py-3 border-b border-gray-700">
            <h2 className="text-sm font-medium text-gray-300">Transcript</h2>
          </div>
          <TranscriptFeed segments={segments} className="flex-1" />
        </div>

        {/* Hints panel */}
        <div className="w-80 flex flex-col">
          <HintsPanel
            currentHint={currentHint}
            previousHints={previousHints}
            isGenerating={isGeneratingHint}
            className="flex-1"
          />
        </div>
      </div>

      {/* Control bar */}
      <ControlBar
        isSessionActive={isSessionActive}
        hintsEnabled={status.hintsEnabled}
        currentMode={currentMode}
        onStartSession={handleStartSession}
        onStopSession={handleStopSession}
        onToggleHints={handleToggleHints}
        onModeChange={handleModeChange}
        disabled={connectionState !== 'connected' && !isSessionActive}
      />

      {/* Settings button */}
      <button
        onClick={() => setShowSettings(true)}
        className="fixed top-4 right-4 p-2 bg-gray-800 rounded-lg hover:bg-gray-700 transition-colors"
      >
        <Settings className="w-5 h-5 text-gray-400" />
      </button>

      {/* Settings modal */}
      {showSettings && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-gray-800 rounded-xl shadow-xl p-6 max-w-md w-full">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-white">Settings</h2>
              <button
                onClick={() => setShowSettings(false)}
                className="p-1 hover:bg-gray-700 rounded"
              >
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>

            <DeviceSelector
              devices={devices}
              micDeviceId={micDeviceId}
              systemDeviceId={systemDeviceId}
              onMicChange={setMicDeviceId}
              onSystemChange={setSystemDeviceId}
              micLevel={micLevel}
              systemLevel={systemLevel}
              disabled={isSessionActive}
            />

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setShowSettings(false)}
                className="px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white rounded-lg font-medium"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
