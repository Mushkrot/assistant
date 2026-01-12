"""Audio processing utilities."""

import numpy as np
from scipy import signal

from app.config import SAMPLE_RATE_CLIENT, SAMPLE_RATE_STT


def resample_16k_to_24k(pcm_bytes: bytes) -> bytes:
    """
    Resample PCM audio from 16kHz to 24kHz.

    Args:
        pcm_bytes: PCM s16le mono audio at 16kHz

    Returns:
        PCM s16le mono audio at 24kHz
    """
    # Convert bytes to numpy array
    samples_16k = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)

    # Calculate resampling ratio
    ratio = SAMPLE_RATE_STT / SAMPLE_RATE_CLIENT  # 24000 / 16000 = 1.5

    # Calculate output length
    output_length = int(len(samples_16k) * ratio)

    # Resample using scipy
    samples_24k = signal.resample(samples_16k, output_length)

    # Clip and convert back to int16
    samples_24k = np.clip(samples_24k, -32768, 32767).astype(np.int16)

    return samples_24k.tobytes()


def normalize_audio(pcm_bytes: bytes, target_db: float = -20.0) -> bytes:
    """
    Normalize audio to target dB level.

    Args:
        pcm_bytes: PCM s16le mono audio
        target_db: Target dB level (default -20dB)

    Returns:
        Normalized PCM audio
    """
    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)

    # Calculate current RMS
    rms = np.sqrt(np.mean(samples ** 2))
    if rms < 1e-6:
        return pcm_bytes  # Silence, no normalization needed

    # Calculate current dB
    current_db = 20 * np.log10(rms / 32768)

    # Calculate gain
    gain_db = target_db - current_db
    gain = 10 ** (gain_db / 20)

    # Apply gain with clipping
    normalized = np.clip(samples * gain, -32768, 32767).astype(np.int16)

    return normalized.tobytes()


def calculate_level(pcm_bytes: bytes) -> float:
    """
    Calculate audio level in dB.

    Args:
        pcm_bytes: PCM s16le mono audio

    Returns:
        Audio level in dB (0 to -60, where 0 is max)
    """
    if len(pcm_bytes) == 0:
        return -60.0

    samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)

    # Calculate RMS
    rms = np.sqrt(np.mean(samples ** 2))
    if rms < 1e-6:
        return -60.0

    # Convert to dB
    db = 20 * np.log10(rms / 32768)

    # Clamp to reasonable range
    return max(-60.0, min(0.0, db))


def pcm_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """Convert PCM s16le to float32 array normalized to [-1, 1]."""
    samples = np.frombuffer(pcm_bytes, dtype=np.int16)
    return samples.astype(np.float32) / 32768.0


def float32_to_pcm(samples: np.ndarray) -> bytes:
    """Convert float32 array [-1, 1] to PCM s16le bytes."""
    samples = np.clip(samples * 32768, -32768, 32767).astype(np.int16)
    return samples.tobytes()
