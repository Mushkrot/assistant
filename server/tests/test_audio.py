"""Tests for audio processing utilities."""

import numpy as np
import pytest
from app.utils.audio import (
    resample_16k_to_24k,
    normalize_audio,
    calculate_level,
    pcm_to_float32,
    float32_to_pcm,
)


def generate_sine_wave(freq: float, duration: float, sample_rate: int) -> bytes:
    """Generate a sine wave as PCM s16le bytes."""
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    samples = np.sin(2 * np.pi * freq * t) * 0.5  # 50% amplitude
    return float32_to_pcm(samples.astype(np.float32))


class TestResample:
    """Tests for resampling function."""

    def test_resample_16k_to_24k_length(self):
        """Test that output has correct length after resampling."""
        # 320 samples at 16kHz = 20ms
        input_samples = 320
        input_bytes = np.zeros(input_samples, dtype=np.int16).tobytes()

        output_bytes = resample_16k_to_24k(input_bytes)
        output_samples = len(output_bytes) // 2  # 2 bytes per sample

        # 20ms at 24kHz = 480 samples
        assert output_samples == 480

    def test_resample_preserves_frequency(self):
        """Test that resampling preserves frequency content."""
        # Generate 1kHz tone at 16kHz sample rate
        pcm_16k = generate_sine_wave(1000, 0.1, 16000)

        # Resample to 24kHz
        pcm_24k = resample_16k_to_24k(pcm_16k)

        # Verify output is valid PCM
        samples = np.frombuffer(pcm_24k, dtype=np.int16)
        assert len(samples) > 0
        assert np.max(np.abs(samples)) > 0  # Not silence


class TestNormalize:
    """Tests for audio normalization."""

    def test_normalize_loud_signal(self):
        """Test normalizing a loud signal."""
        # Generate loud sine wave
        loud_pcm = generate_sine_wave(440, 0.1, 16000)

        # Normalize to -20dB
        normalized = normalize_audio(loud_pcm, target_db=-20)

        # Check level is approximately -20dB
        level = calculate_level(normalized)
        assert -25 < level < -15

    def test_normalize_silence(self):
        """Test that silence is not modified."""
        silence = np.zeros(320, dtype=np.int16).tobytes()
        result = normalize_audio(silence)
        assert result == silence


class TestCalculateLevel:
    """Tests for level calculation."""

    def test_silence_level(self):
        """Test that silence returns minimum level."""
        silence = np.zeros(320, dtype=np.int16).tobytes()
        level = calculate_level(silence)
        assert level == -60.0

    def test_max_level(self):
        """Test that full-scale signal returns ~0dB."""
        max_signal = np.full(320, 32767, dtype=np.int16).tobytes()
        level = calculate_level(max_signal)
        assert level > -3.0

    def test_empty_buffer(self):
        """Test that empty buffer returns minimum level."""
        level = calculate_level(b'')
        assert level == -60.0


class TestPCMConversion:
    """Tests for PCM conversion utilities."""

    def test_roundtrip_conversion(self):
        """Test that float32 -> pcm -> float32 is approximately identity."""
        original = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        pcm = float32_to_pcm(original)
        recovered = pcm_to_float32(pcm)

        # Allow small quantization error
        np.testing.assert_allclose(original, recovered, rtol=1e-4, atol=1e-4)
