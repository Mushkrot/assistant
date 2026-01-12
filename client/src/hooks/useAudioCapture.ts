import { useState, useCallback, useRef, useEffect } from 'react';

// Audio processing constants
const TARGET_SAMPLE_RATE = 16000;
const FRAME_DURATION_MS = 20;
const FRAME_SIZE = (TARGET_SAMPLE_RATE * FRAME_DURATION_MS) / 1000; // 320 samples

interface UseAudioCaptureOptions {
  micDeviceId: string | null;
  systemDeviceId: string | null;
  onMicFrame?: (pcmData: ArrayBuffer) => void;
  onSystemFrame?: (pcmData: ArrayBuffer) => void;
  onMicLevel?: (level: number) => void;
  onSystemLevel?: (level: number) => void;
}

interface UseAudioCaptureReturn {
  isCapturing: boolean;
  start: () => Promise<boolean>;
  stop: () => void;
  micLevel: number;
  systemLevel: number;
}

// Audio Worklet processor code as a string
const WORKLET_CODE = `
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = [];
    this.samplesPerFrame = ${FRAME_SIZE};
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const samples = input[0];

    // Add samples to buffer
    for (let i = 0; i < samples.length; i++) {
      this.buffer.push(samples[i]);
    }

    // When we have enough samples, send a frame
    while (this.buffer.length >= this.samplesPerFrame) {
      const frameData = this.buffer.splice(0, this.samplesPerFrame);

      // Convert Float32 to Int16
      const int16Data = new Int16Array(frameData.length);
      for (let i = 0; i < frameData.length; i++) {
        const s = Math.max(-1, Math.min(1, frameData[i]));
        int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }

      // Calculate level (RMS)
      let sum = 0;
      for (let i = 0; i < frameData.length; i++) {
        sum += frameData[i] * frameData[i];
      }
      const rms = Math.sqrt(sum / frameData.length);
      const level = Math.max(-60, 20 * Math.log10(rms + 0.0001));

      this.port.postMessage({
        pcm: int16Data.buffer,
        level: level
      }, [int16Data.buffer]);
    }

    return true;
  }
}

registerProcessor('pcm-processor', PCMProcessor);
`;

export function useAudioCapture(options: UseAudioCaptureOptions): UseAudioCaptureReturn {
  const {
    micDeviceId,
    systemDeviceId,
    onMicFrame,
    onSystemFrame,
    onMicLevel,
    onSystemLevel,
  } = options;

  const [isCapturing, setIsCapturing] = useState(false);
  const [micLevel, setMicLevel] = useState(-60);
  const [systemLevel, setSystemLevel] = useState(-60);

  const micContextRef = useRef<AudioContext | null>(null);
  const systemContextRef = useRef<AudioContext | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const systemStreamRef = useRef<MediaStream | null>(null);
  const workletModuleLoaded = useRef(false);

  const createWorkletModule = useCallback(async (context: AudioContext) => {
    if (!workletModuleLoaded.current) {
      const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
      const url = URL.createObjectURL(blob);
      try {
        await context.audioWorklet.addModule(url);
        workletModuleLoaded.current = true;
      } finally {
        URL.revokeObjectURL(url);
      }
    }
  }, []);

  const setupAudioPipeline = useCallback(async (
    deviceId: string,
    isMic: boolean
  ): Promise<{ context: AudioContext; stream: MediaStream } | null> => {
    try {
      // Get media stream
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: { exact: deviceId },
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          sampleRate: 48000, // Browser native
        },
      });

      // Create audio context with target sample rate
      const context = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });

      // Load worklet module
      await createWorkletModule(context);

      // Create source from stream
      const source = context.createMediaStreamSource(stream);

      // Create worklet node
      const workletNode = new AudioWorkletNode(context, 'pcm-processor');

      // Handle messages from worklet
      workletNode.port.onmessage = (event) => {
        const { pcm, level } = event.data;

        if (isMic) {
          setMicLevel(level);
          onMicLevel?.(level);
          onMicFrame?.(pcm);
        } else {
          setSystemLevel(level);
          onSystemLevel?.(level);
          onSystemFrame?.(pcm);
        }
      };

      // Connect: source -> worklet
      source.connect(workletNode);

      // Don't connect to destination (we don't want to play back)
      // workletNode.connect(context.destination);

      return { context, stream };
    } catch (err) {
      console.error('Failed to setup audio pipeline:', err);
      return null;
    }
  }, [createWorkletModule, onMicFrame, onSystemFrame, onMicLevel, onSystemLevel]);

  const start = useCallback(async (): Promise<boolean> => {
    if (isCapturing) return true;
    if (!micDeviceId) {
      console.error('No mic device selected');
      return false;
    }

    try {
      // Setup mic pipeline
      const micResult = await setupAudioPipeline(micDeviceId, true);
      if (!micResult) {
        return false;
      }
      micContextRef.current = micResult.context;
      micStreamRef.current = micResult.stream;

      // Setup system audio pipeline if device selected
      if (systemDeviceId) {
        const systemResult = await setupAudioPipeline(systemDeviceId, false);
        if (systemResult) {
          systemContextRef.current = systemResult.context;
          systemStreamRef.current = systemResult.stream;
        }
      }

      setIsCapturing(true);
      return true;
    } catch (err) {
      console.error('Failed to start audio capture:', err);
      return false;
    }
  }, [isCapturing, micDeviceId, systemDeviceId, setupAudioPipeline]);

  const stop = useCallback(() => {
    // Stop mic
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }
    if (micContextRef.current) {
      micContextRef.current.close();
      micContextRef.current = null;
    }

    // Stop system
    if (systemStreamRef.current) {
      systemStreamRef.current.getTracks().forEach((track) => track.stop());
      systemStreamRef.current = null;
    }
    if (systemContextRef.current) {
      systemContextRef.current.close();
      systemContextRef.current = null;
    }

    setIsCapturing(false);
    setMicLevel(-60);
    setSystemLevel(-60);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return {
    isCapturing,
    start,
    stop,
    micLevel,
    systemLevel,
  };
}
