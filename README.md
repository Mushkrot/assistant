# Realtime Interview and Meeting Copilot

AI-powered real-time assistant that listens to your interviews and meetings, transcribes conversations, and provides intelligent hints.

## Features

- **Dual Audio Capture**: Captures both your microphone (ME) and system audio (THEM) separately
- **Real-time Transcription**: Uses OpenAI Realtime API for streaming speech-to-text
- **AI Hints**: Generates contextual hints using local Ollama LLM
- **Two Modes**:
  - **Interview Assistant**: Detects questions and suggests answer structures
  - **Meeting Assistant**: Provides context and term explanations
- **Knowledge Base**: Upload .md files to enhance hints with your own materials

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Mac (Chrome Browser)                          │
│  ┌─────────────┐  ┌─────────────┐                               │
│  │  Microphone │  │  BlackHole  │ ← System audio via Multi-Output│
│  └──────┬──────┘  └──────┬──────┘                               │
│         │                │                                       │
│         └────────┬───────┘                                       │
│                  │ WebSocket (PCM audio)                         │
└──────────────────┼───────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Linux Server (Ubuntu)                         │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                     FastAPI + Pipecat                        ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       ││
│  │  │ STT Service  │  │ Orchestrator │  │ LLM Service  │       ││
│  │  │ (OpenAI RT)  │→ │              │→ │  (Ollama)    │       ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘       ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Requirements

### Server (Linux)
- Python 3.10+
- Ollama with llama3.1:8b model
- OpenAI API key (for Realtime STT)

### Client (Mac)
- macOS with Chrome browser
- BlackHole 2ch (for system audio capture)

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
cd /path/to/project

# Run setup script
./scripts/setup.sh
```

### 2. Configure Environment

Create/update `/opt/secure-configs/.env` on the server:
```env
OPENAI_API_KEY=sk-your-key-here
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

### 3. Start Development Server

```bash
./scripts/dev.sh
```

This starts:
- Python server at http://localhost:8000
- React client at http://localhost:3000

### 4. Configure Mac Audio (First Time)

1. **Install BlackHole**:
   ```bash
   brew install blackhole-2ch
   ```

2. **Create Multi-Output Device**:
   - Open **Audio MIDI Setup** (Spotlight → "Audio MIDI Setup")
   - Click **"+"** → **Create Multi-Output Device**
   - Check both your headphones/speakers AND BlackHole 2ch
   - Rename to "Meeting Output" (optional)

3. **Before Meeting**:
   - Set system output to "Meeting Output" in System Settings → Sound
   - Open Chrome and navigate to http://localhost:3000
   - Select your microphone and BlackHole in the app

## Usage

1. Open the app in Chrome
2. Grant microphone permission
3. Select your microphone and BlackHole as system audio
4. Choose mode (Interview or Meeting Assistant)
5. Click "Start Session"
6. Start your meeting/interview in Zoom/Teams/etc.

The app will:
- Show real-time transcription with ME/THEM labels
- Generate AI hints in the right panel
- Allow pausing hints while keeping transcription running

## Project Structure

```
├── server/
│   ├── app/
│   │   ├── main.py           # FastAPI app
│   │   ├── config.py         # Configuration
│   │   ├── routes/
│   │   │   ├── websocket.py  # WebSocket handler
│   │   │   └── api.py        # REST API
│   │   ├── services/
│   │   │   ├── stt_service.py      # OpenAI Realtime STT
│   │   │   ├── orchestrator.py     # Hint triggering logic
│   │   │   ├── llm_service.py      # Ollama integration
│   │   │   └── knowledge_service.py # Knowledge base
│   │   ├── models/
│   │   └── utils/
│   └── requirements.txt
├── client/
│   ├── src/
│   │   ├── App.tsx           # Main app component
│   │   ├── components/       # UI components
│   │   ├── hooks/            # React hooks
│   │   └── types/            # TypeScript types
│   └── package.json
├── scripts/
│   ├── setup.sh              # Initial setup
│   ├── dev.sh                # Development server
│   └── build.sh              # Production build
├── workspaces/               # Knowledge base files
└── Docs/
    ├── PRD.md                # Product requirements
    └── todo.md               # Implementation tasks
```

## API Reference

### WebSocket `/ws`

**Client → Server (Binary):**
- First byte: channel ID (0=mic, 1=system)
- Remaining bytes: PCM s16le mono 16kHz audio

**Client → Server (JSON):**
```json
{"type": "start_session"}
{"type": "stop_session"}
{"type": "pause_hints"}
{"type": "resume_hints"}
{"type": "set_mode", "mode": "interview_assistant"}
```

**Server → Client (JSON):**
```json
{"type": "transcript_delta", "speaker": "THEM", "text": "...", "segment_id": "..."}
{"type": "transcript_completed", "speaker": "THEM", "text": "...", "segment_id": "..."}
{"type": "hint_token", "hint_id": "...", "token": "..."}
{"type": "hint_completed", "hint_id": "...", "final_text": "...", "mode": "..."}
{"type": "status", "connected": true, "stt_mic_state": "active", ...}
```

### REST API

- `GET /health` - Health check
- `GET /api/config` - Get configuration
- `GET /api/workspaces` - List workspaces
- `POST /api/workspaces` - Create workspace
- `POST /api/workspaces/{name}/files` - Upload file
- `GET /api/workspaces/{name}/files` - List files

## License

MIT License. See `LICENSE`.
