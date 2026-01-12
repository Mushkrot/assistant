"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with validation."""

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key for Realtime STT")

    # Ollama
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL"
    )
    ollama_model: str = Field(
        default="llama3.1:8b",
        description="Ollama model to use for hints"
    )

    # Server
    server_host: str = Field(default="0.0.0.0")
    server_port: int = Field(default=8010)

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # Debug
    debug_save_audio: bool = Field(default=False)
    debug_audio_path: str = Field(default="./debug_audio")

    model_config = {
        "env_file": "/opt/secure-configs/.env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


# Audio constants
SAMPLE_RATE_CLIENT = 16000  # Sample rate from browser
SAMPLE_RATE_STT = 24000     # Sample rate for OpenAI Realtime
FRAME_DURATION_MS = 20      # Frame duration in milliseconds
FRAME_SAMPLES_CLIENT = int(SAMPLE_RATE_CLIENT * FRAME_DURATION_MS / 1000)  # 320 samples
FRAME_SAMPLES_STT = int(SAMPLE_RATE_STT * FRAME_DURATION_MS / 1000)        # 480 samples
BYTES_PER_SAMPLE = 2        # 16-bit PCM

# Queue settings
AUDIO_QUEUE_MAX_SIZE = 200  # Max frames in queue (~4 seconds at 20ms/frame)

# Orchestrator settings
AGGREGATION_TIMEOUT_MS = 800    # Trigger after this many ms without completed
AGGREGATION_WORD_THRESHOLD = 12  # Trigger after this many words
HINT_RATE_LIMIT_MS = 2000       # Min time between hints for Meeting Assistant

# LLM settings
MAX_HINT_POINTS = 3             # Maximum bullet points in hint
MAX_CONTEXT_TOKENS = 2000       # Max tokens for knowledge context


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
