import { useState, useEffect, useCallback } from 'react';
import type { AudioDevice } from '@/types';

interface UseAudioDevicesReturn {
  devices: AudioDevice[];
  loading: boolean;
  error: string | null;
  hasPermission: boolean;
  requestPermission: () => Promise<boolean>;
  refresh: () => Promise<void>;
}

export function useAudioDevices(): UseAudioDevicesReturn {
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasPermission, setHasPermission] = useState(false);

  const getDevices = useCallback(async () => {
    try {
      const allDevices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = allDevices
        .filter((d) => d.kind === 'audioinput')
        .map((d) => ({
          deviceId: d.deviceId,
          label: d.label || `Microphone ${d.deviceId.slice(0, 8)}`,
          kind: d.kind as 'audioinput',
        }));

      setDevices(audioInputs);
      setHasPermission(audioInputs.some((d) => d.label !== ''));
    } catch (err) {
      console.error('Failed to enumerate devices:', err);
      setError('Failed to get audio devices');
    }
  }, []);

  const requestPermission = useCallback(async (): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);

      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Stop the stream immediately, we just needed permission
      stream.getTracks().forEach((track) => track.stop());

      setHasPermission(true);

      // Now get the full device list with labels
      await getDevices();

      return true;
    } catch (err) {
      console.error('Failed to get microphone permission:', err);
      setError('Microphone permission denied');
      setHasPermission(false);
      return false;
    } finally {
      setLoading(false);
    }
  }, [getDevices]);

  const refresh = useCallback(async () => {
    setLoading(true);
    await getDevices();
    setLoading(false);
  }, [getDevices]);

  // Initial load
  useEffect(() => {
    getDevices().finally(() => setLoading(false));

    // Listen for device changes
    const handleDeviceChange = () => {
      getDevices();
    };

    navigator.mediaDevices.addEventListener('devicechange', handleDeviceChange);

    return () => {
      navigator.mediaDevices.removeEventListener('devicechange', handleDeviceChange);
    };
  }, [getDevices]);

  return {
    devices,
    loading,
    error,
    hasPermission,
    requestPermission,
    refresh,
  };
}
