import { cn } from '@/lib/utils';
import type { ConnectionState, ServiceState } from '@/types';
import { Wifi, WifiOff, Mic, Volume2, Cpu, AlertTriangle } from 'lucide-react';

interface StatusBarProps {
  connectionState: ConnectionState;
  sttMicState: ServiceState;
  sttSystemState: ServiceState;
  llmState: ServiceState;
  droppedFrames: number;
  hintsEnabled: boolean;
}

function StatusIndicator({
  label,
  state,
  icon: Icon,
}: {
  label: string;
  state: ServiceState | ConnectionState;
  icon: React.ComponentType<{ className?: string }>;
}) {
  const stateColors = {
    idle: 'text-gray-500',
    connecting: 'text-yellow-500',
    connected: 'text-green-500',
    active: 'text-green-500',
    generating: 'text-blue-500',
    error: 'text-red-500',
    disconnected: 'text-gray-500',
  };

  return (
    <div className="flex items-center gap-1.5">
      <Icon className={cn('w-4 h-4', stateColors[state] || 'text-gray-500')} />
      <span className="text-xs text-gray-400">{label}</span>
    </div>
  );
}

export function StatusBar({
  connectionState,
  sttMicState,
  sttSystemState,
  llmState,
  droppedFrames,
  hintsEnabled,
}: StatusBarProps) {
  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-gray-800 border-b border-gray-700">
      {/* Connection status */}
      <StatusIndicator
        label="Server"
        state={connectionState}
        icon={connectionState === 'connected' ? Wifi : WifiOff}
      />

      <div className="w-px h-4 bg-gray-700" />

      {/* STT Mic status */}
      <StatusIndicator
        label="Mic STT"
        state={sttMicState}
        icon={Mic}
      />

      {/* STT System status */}
      <StatusIndicator
        label="System STT"
        state={sttSystemState}
        icon={Volume2}
      />

      <div className="w-px h-4 bg-gray-700" />

      {/* LLM status */}
      <StatusIndicator
        label="LLM"
        state={llmState}
        icon={Cpu}
      />

      {/* Hints status */}
      {!hintsEnabled && (
        <>
          <div className="w-px h-4 bg-gray-700" />
          <div className="flex items-center gap-1.5 text-yellow-500">
            <span className="text-xs font-medium">Hints Paused</span>
          </div>
        </>
      )}

      {/* Dropped frames warning */}
      {droppedFrames > 0 && (
        <>
          <div className="flex-1" />
          <div className="flex items-center gap-1.5 text-yellow-500">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-xs">{droppedFrames} dropped</span>
          </div>
        </>
      )}
    </div>
  );
}
