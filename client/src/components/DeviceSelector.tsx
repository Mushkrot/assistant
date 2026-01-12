import { cn } from '@/lib/utils';
import type { AudioDevice } from '@/types';
import { Mic, Volume2 } from 'lucide-react';

interface DeviceSelectorProps {
  devices: AudioDevice[];
  micDeviceId: string | null;
  systemDeviceId: string | null;
  onMicChange: (deviceId: string) => void;
  onSystemChange: (deviceId: string) => void;
  micLevel: number;
  systemLevel: number;
  disabled?: boolean;
}

function LevelMeter({ level, className }: { level: number; className?: string }) {
  // Normalize level from -60..0 to 0..100
  const normalized = Math.max(0, Math.min(100, ((level + 60) / 60) * 100));

  return (
    <div className={cn('h-2 bg-gray-700 rounded-full overflow-hidden', className)}>
      <div
        className={cn(
          'h-full transition-all duration-75 rounded-full',
          normalized > 80 ? 'bg-red-500' : normalized > 60 ? 'bg-yellow-500' : 'bg-green-500'
        )}
        style={{ width: `${normalized}%` }}
      />
    </div>
  );
}

export function DeviceSelector({
  devices,
  micDeviceId,
  systemDeviceId,
  onMicChange,
  onSystemChange,
  micLevel,
  systemLevel,
  disabled = false,
}: DeviceSelectorProps) {
  // Find BlackHole devices for system audio
  const blackHoleDevices = devices.filter((d) =>
    d.label.toLowerCase().includes('blackhole')
  );

  // Regular mic devices (exclude BlackHole)
  const micDevices = devices.filter(
    (d) => !d.label.toLowerCase().includes('blackhole')
  );

  return (
    <div className="space-y-6">
      {/* Microphone selection */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <Mic className="w-4 h-4" />
          Microphone (Your voice)
        </label>
        <select
          value={micDeviceId || ''}
          onChange={(e) => onMicChange(e.target.value)}
          disabled={disabled}
          className={cn(
            'w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg',
            'text-gray-200 text-sm',
            'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <option value="">Select microphone...</option>
          {micDevices.map((device) => (
            <option key={device.deviceId} value={device.deviceId}>
              {device.label}
            </option>
          ))}
        </select>
        {micDeviceId && (
          <LevelMeter level={micLevel} className="mt-2" />
        )}
      </div>

      {/* System audio selection */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <Volume2 className="w-4 h-4" />
          System Audio (Other person's voice)
        </label>
        {blackHoleDevices.length > 0 ? (
          <>
            <select
              value={systemDeviceId || ''}
              onChange={(e) => onSystemChange(e.target.value)}
              disabled={disabled}
              className={cn(
                'w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg',
                'text-gray-200 text-sm',
                'focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              <option value="">Select BlackHole device...</option>
              {blackHoleDevices.map((device) => (
                <option key={device.deviceId} value={device.deviceId}>
                  {device.label}
                </option>
              ))}
            </select>
            {systemDeviceId && (
              <LevelMeter level={systemLevel} className="mt-2" />
            )}
          </>
        ) : (
          <div className="p-4 bg-yellow-900/30 border border-yellow-700/50 rounded-lg">
            <p className="text-sm text-yellow-300">
              BlackHole not detected. Please install BlackHole and configure Multi-Output Device.
            </p>
            <a
              href="https://existential.audio/blackhole/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-primary-400 hover:underline mt-2 inline-block"
            >
              Download BlackHole →
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
