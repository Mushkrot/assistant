import { cn } from '@/lib/utils';
import type { SessionMode } from '@/types';
import { Play, Square, Pause, Play as Resume } from 'lucide-react';

interface ControlBarProps {
  isSessionActive: boolean;
  hintsEnabled: boolean;
  currentMode: SessionMode;
  onStartSession: () => void;
  onStopSession: () => void;
  onToggleHints: () => void;
  onModeChange: (mode: SessionMode) => void;
  disabled?: boolean;
}

export function ControlBar({
  isSessionActive,
  hintsEnabled,
  currentMode,
  onStartSession,
  onStopSession,
  onToggleHints,
  onModeChange,
  disabled = false,
}: ControlBarProps) {
  return (
    <div className="flex items-center gap-4 px-4 py-3 bg-gray-800 border-t border-gray-700">
      {/* Start/Stop button */}
      {!isSessionActive ? (
        <button
          onClick={onStartSession}
          disabled={disabled}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
            'bg-green-600 hover:bg-green-500 text-white',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <Play className="w-4 h-4" />
          Start Session
        </button>
      ) : (
        <button
          onClick={onStopSession}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
            'bg-red-600 hover:bg-red-500 text-white'
          )}
        >
          <Square className="w-4 h-4" />
          Stop Session
        </button>
      )}

      {/* Pause/Resume hints button */}
      {isSessionActive && (
        <button
          onClick={onToggleHints}
          className={cn(
            'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
            hintsEnabled
              ? 'bg-yellow-600 hover:bg-yellow-500 text-white'
              : 'bg-gray-600 hover:bg-gray-500 text-white'
          )}
        >
          {hintsEnabled ? (
            <>
              <Pause className="w-4 h-4" />
              Pause Hints
            </>
          ) : (
            <>
              <Resume className="w-4 h-4" />
              Resume Hints
            </>
          )}
        </button>
      )}

      <div className="flex-1" />

      {/* Mode selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-400">Mode:</span>
        <select
          value={currentMode}
          onChange={(e) => onModeChange(e.target.value as SessionMode)}
          disabled={!isSessionActive}
          className={cn(
            'px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg',
            'text-gray-200 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <option value="interview_assistant">Interview Assistant</option>
          <option value="meeting_assistant">Meeting Assistant</option>
        </select>
      </div>
    </div>
  );
}
