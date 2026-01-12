# TODO: Realtime Interview and Meeting Copilot — POC Phase

## Обзор
Этот документ содержит детальный план реализации POC фазы проекта.
Цель POC: end-to-end работа в LAN с BlackHole, двумя аудиоканалами, streaming STT, подсказки 1–3 пункта.

**Референс:** [PRD.md](./PRD.md)

---

## Этап 1: Инфраструктура и базовый сервер

### 1.1 Инициализация репозитория

- [ ] Создать структуру директорий проекта:
  ```
  /
  ├── server/
  │   ├── app/
  │   │   ├── __init__.py
  │   │   ├── main.py              # FastAPI приложение
  │   │   ├── config.py            # Конфигурация из .env
  │   │   ├── routes/
  │   │   │   ├── __init__.py
  │   │   │   ├── websocket.py     # WebSocket endpoint
  │   │   │   └── api.py           # REST endpoints
  │   │   ├── services/
  │   │   │   ├── __init__.py
  │   │   │   ├── session_manager.py
  │   │   │   ├── stt_service.py
  │   │   │   ├── llm_service.py
  │   │   │   ├── knowledge_service.py
  │   │   │   └── orchestrator.py
  │   │   ├── models/
  │   │   │   ├── __init__.py
  │   │   │   ├── events.py        # Pydantic модели событий
  │   │   │   └── session.py       # Модель сессии
  │   │   └── utils/
  │   │       ├── __init__.py
  │   │       ├── audio.py         # Утилиты обработки аудио
  │   │       └── event_bus.py     # Внутренняя шина событий
  │   ├── tests/
  │   ├── requirements.txt
  │   └── Dockerfile
  ├── client/
  │   ├── src/
  │   ├── public/
  │   ├── package.json
  │   └── vite.config.ts
  ├── docs/
  ├── docker-compose.yml
  └── README.md
  ```
- [ ] Создать `requirements.txt`:
  ```
  fastapi>=0.109.0
  uvicorn[standard]>=0.27.0
  websockets>=12.0
  pipecat-ai>=0.0.30
  python-dotenv>=1.0.0
  pydantic>=2.5.0
  numpy>=1.26.0
  scipy>=1.12.0
  aiofiles>=23.2.0
  httpx>=0.26.0
  ```
- [ ] Создать базовый `README.md` с инструкциями запуска

### 1.2 FastAPI сервер

- [ ] Реализовать `server/app/main.py`:
  - Инициализация FastAPI приложения
  - Подключение роутеров
  - Middleware для CORS (разрешить все origins для POC)
  - Статическая раздача клиентского билда из `/static`
  - Lifespan events для инициализации/очистки сервисов
- [ ] Реализовать `server/app/config.py`:
  - Загрузка переменных из `/opt/secure-configs/.env`
  - Pydantic Settings класс с валидацией
  - Константы: SAMPLE_RATE_CLIENT=16000, SAMPLE_RATE_STT=24000, FRAME_DURATION_MS=20

### 1.3 Session Manager

- [ ] Реализовать `server/app/services/session_manager.py`:
  - Класс `Session` с полями:
    - `session_id: str`
    - `created_at: datetime`
    - `mode: str` (interview_assistant | meeting_assistant)
    - `hints_enabled: bool`
    - `custom_prompt: Optional[str]`
    - `knowledge_workspace: Optional[str]`
    - `mic_queue: asyncio.Queue` (maxsize=200)
    - `system_queue: asyncio.Queue` (maxsize=200)
    - `stats: SessionStats` (dropped_frames, stt_latency, etc.)
  - Класс `SessionManager`:
    - `create_session() -> Session`
    - `get_session(session_id) -> Optional[Session]`
    - `destroy_session(session_id)`
    - `list_sessions() -> List[Session]`
  - Для POC: хранение в памяти (dict), один активный сессион

### 1.4 Event Bus

- [ ] Реализовать `server/app/utils/event_bus.py`:
  - Класс `EventBus` на основе asyncio:
    - `subscribe(event_type, callback)`
    - `unsubscribe(event_type, callback)`
    - `publish(event_type, payload)`
  - Типы событий (enum):
    - `AUDIO_FRAME_MIC`
    - `AUDIO_FRAME_SYSTEM`
    - `TRANSCRIPT_DELTA`
    - `TRANSCRIPT_COMPLETED`
    - `TEXT_CHUNK_READY`
    - `HINT_TOKEN`
    - `HINT_COMPLETED`
    - `SESSION_STATUS`

### 1.5 Модели событий

- [ ] Реализовать `server/app/models/events.py`:
  ```python
  class Speaker(str, Enum):
      ME = "ME"
      THEM = "THEM"

  class TranscriptDelta(BaseModel):
      speaker: Speaker
      text: str
      segment_id: str
      timestamp: float

  class TranscriptCompleted(BaseModel):
      speaker: Speaker
      text: str
      segment_id: str
      timestamp: float

  class TextChunk(BaseModel):
      speaker: Speaker
      text: str
      last_context: str
      global_context: Optional[str]

  class HintToken(BaseModel):
      hint_id: str
      token: str

  class HintCompleted(BaseModel):
      hint_id: str
      final_text: str
      mode: str

  class SessionStatus(BaseModel):
      connected: bool
      stt_mic_state: str
      stt_system_state: str
      llm_state: str
      dropped_frames_count: int
  ```

---

## Этап 2: WebSocket endpoint и протокол

### 2.1 WebSocket роутер
- [ ] Реализовать `server/app/routes/websocket.py`:
  - Endpoint: `GET /ws`
  - При подключении:
    - Создать сессию через SessionManager
    - Запустить задачи обработки аудио
    - Запустить задачи STT для обоих каналов
    - Подписаться на события для отправки клиенту
  - При отключении:
    - Graceful остановка задач
    - Уничтожение сессии

### 2.2 Протокол сообщений client → server
- [ ] Реализовать парсинг входящих сообщений:
  - **Binary сообщения (аудио):**
    - Первый байт: `channel_id` (0 = mic, 1 = system)
    - Остальные байты: raw PCM s16le mono 16kHz
  - **JSON сообщения (control):**
    ```json
    {"type": "start_session"}
    {"type": "stop_session"}
    {"type": "pause_hints"}
    {"type": "resume_hints"}
    {"type": "set_mode", "mode": "interview_assistant"}
    {"type": "set_prompt", "prompt": "..."}
    {"type": "set_knowledge", "workspace": "my_workspace"}
    ```

### 2.3 Протокол сообщений server → client
- [ ] Реализовать отправку событий клиенту:
  ```json
  {"type": "transcript_delta", "speaker": "THEM", "text": "...", "segment_id": "..."}
  {"type": "transcript_completed", "speaker": "THEM", "text": "...", "segment_id": "..."}
  {"type": "hint_token", "hint_id": "...", "token": "..."}
  {"type": "hint_completed", "hint_id": "...", "final_text": "...", "mode": "..."}
  {"type": "status", "connected": true, "stt_mic_state": "active", ...}
  {"type": "error", "message": "..."}
  ```

### 2.4 Обработка аудио очередей
- [ ] Реализовать воркеры для каждого канала:
  - Читать фреймы из WebSocket
  - Класть в соответствующую asyncio.Queue
  - При переполнении: drop oldest, инкремент счётчика dropped_frames
  - Публиковать AUDIO_FRAME_* события

---

## Этап 3: Web Client — захват аудио

### 3.1 Инициализация React проекта
- [ ] Создать Vite + React + TypeScript проект:
  ```bash
  npm create vite@latest client -- --template react-ts
  ```
- [ ] Установить зависимости:
  ```bash
  npm install
  ```
- [ ] Настроить `vite.config.ts`:
  - Proxy для `/ws` и `/api` на сервер в dev режиме
  - Build output в `../server/static`

### 3.2 Выбор аудио устройств
- [ ] Создать хук `useAudioDevices()`:
  - Запросить разрешение на микрофон
  - Получить список устройств: `navigator.mediaDevices.enumerateDevices()`
  - Фильтровать только `audioinput`
  - Вернуть список устройств с labels
- [ ] Создать компонент `DeviceSelector`:
  - Dropdown для выбора микрофона (default: системный микрофон)
  - Dropdown для выбора системного звука (искать "BlackHole" в названии)
  - Кнопка "Test" для проверки уровней
  - Визуализация уровней (VU meter) для обоих каналов

### 3.3 Захват двух аудиопотоков
- [ ] Создать хук `useAudioCapture(micDeviceId, systemDeviceId)`:
  - Захват микрофона:
    ```javascript
    navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: { exact: micDeviceId },
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false
      }
    })
    ```
  - Захват системного звука (BlackHole):
    ```javascript
    navigator.mediaDevices.getUserMedia({
      audio: {
        deviceId: { exact: systemDeviceId },
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false
      }
    })
    ```
  - Вернуть два MediaStream объекта

### 3.4 Ресемплинг и PCM конвертация

- [ ] Создать класс `AudioProcessor`:
  - Использовать AudioWorklet для обработки в реальном времени
  - Создать `pcm-processor.worklet.js`:
    ```javascript
    class PCMProcessor extends AudioWorkletProcessor {
      constructor() {
        super();
        this.buffer = [];
        this.samplesPerFrame = 320; // 20ms @ 16kHz
      }

      process(inputs, outputs, parameters) {
        const input = inputs[0][0]; // mono
        if (input) {
          // Accumulate samples
          // When buffer >= samplesPerFrame, convert to Int16 and post
        }
        return true;
      }
    }
    ```
  - Ресемплинг 48kHz → 16kHz через OfflineAudioContext или Web Audio API
  - Конвертация Float32 → Int16 (PCM s16le)
  - Упаковка фреймов по 20ms (320 samples @ 16kHz = 640 bytes)

### 3.5 WebSocket клиент
- [ ] Создать хук `useWebSocket(url)`:
  - Подключение с автоматическим reconnect
  - Отправка binary и JSON сообщений
  - Получение и парсинг событий
  - Состояния: connecting, connected, disconnected, error
- [ ] Создать функцию отправки аудио:
  ```javascript
  function sendAudioFrame(channelId: number, pcmData: ArrayBuffer) {
    const header = new Uint8Array([channelId]);
    const frame = new Uint8Array(header.length + pcmData.byteLength);
    frame.set(header, 0);
    frame.set(new Uint8Array(pcmData), header.length);
    ws.send(frame.buffer);
  }
  ```

---

## Этап 4: STT Service — OpenAI Realtime

### 4.1 OpenAI Realtime клиент
- [ ] Реализовать `server/app/services/stt_service.py`:
  - Класс `RealtimeSTTClient`:
    - Подключение к `wss://api.openai.com/v1/realtime`
    - Конфигурация сессии:
      ```json
      {
        "type": "session.update",
        "session": {
          "input_audio_format": "pcm16",
          "input_audio_transcription": {
            "model": "gpt-4o-mini-transcribe"
          },
          "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 300
          }
        }
      }
      ```
    - Методы:
      - `connect()`
      - `disconnect()`
      - `send_audio(pcm_bytes)`
      - `on_transcript_delta(callback)`
      - `on_transcript_completed(callback)`

### 4.2 Ресемплинг на сервере
- [ ] Реализовать `server/app/utils/audio.py`:
  - Функция `resample_16k_to_24k(pcm_bytes) -> bytes`:
    - Использовать scipy.signal.resample или numpy
    - Input: PCM s16le mono 16kHz
    - Output: PCM s16le mono 24kHz
  - Функция `normalize_audio(pcm_bytes, target_db=-20) -> bytes`
  - Функция `calculate_level(pcm_bytes) -> float` (для метрик)

### 4.3 Dual-channel STT Manager
- [ ] Реализовать класс `STTManager`:
  - Создание двух RealtimeSTTClient (mic и system)
  - Воркер для каждого канала:
    ```python
    async def process_channel(channel: str, queue: asyncio.Queue):
        while True:
            pcm_16k = await queue.get()
            pcm_24k = resample_16k_to_24k(pcm_16k)
            await stt_client.send_audio(pcm_24k)
    ```
  - Маппинг каналов на Speaker enum:
    - channel 0 (mic) → Speaker.ME
    - channel 1 (system) → Speaker.THEM
  - Публикация событий TRANSCRIPT_DELTA и TRANSCRIPT_COMPLETED

### 4.4 Обработка событий OpenAI Realtime
- [ ] Парсить события от OpenAI:
  - `conversation.item.input_audio_transcription.delta`:
    ```json
    {"delta": "Hello, how are"}
    ```
  - `conversation.item.input_audio_transcription.completed`:
    ```json
    {"transcript": "Hello, how are you today?"}
    ```
  - `input_audio_buffer.speech_started`
  - `input_audio_buffer.speech_stopped`
- [ ] Генерировать уникальные segment_id для каждого utterance
- [ ] Обрабатывать reconnect при разрыве соединения

---

## Этап 5: Orchestrator — агрегация и триггеры

### 5.1 Text Aggregator
- [ ] Реализовать `server/app/services/orchestrator.py`:
  - Класс `TextAggregator`:
    - Накопление delta текста по segment_id
    - Хранение истории последних N сегментов (для контекста)
    - Формирование `last_context` — последние 1-2 предложения спикера
    - Формирование `global_context` — краткая выжимка последних 30 сек

### 5.2 Trigger Manager
- [ ] Реализовать класс `TriggerManager`:
  - Триггер TextChunk при:
    1. Получен TRANSCRIPT_COMPLETED
    2. ИЛИ прошло 800ms с последнего delta без completed
    3. ИЛИ накоплено >= 12 слов
  - Rate limiter: не чаще 1 раза в 2 секунды для Meeting Assistant
  - При срабатывании: публикация TEXT_CHUNK_READY

### 5.3 Question Detection (Interview Assistant)
- [ ] Реализовать эвристики определения вопроса:
  - Наличие `?` в тексте
  - Начало с вопросительных слов: "what", "why", "how", "when", "where", "who", "can you", "could you", "tell me", "explain", "describe"
  - Приглашение к рассказу: "tell me about", "walk me through", "describe your experience"
- [ ] Функция `is_question(text: str) -> bool`

### 5.4 Mode Router
- [ ] Реализовать класс `ModeRouter`:
  - Подписка на TEXT_CHUNK_READY
  - В зависимости от session.mode:
    - **interview_assistant:**
      - Триггер только если `is_question(text)` и speaker == THEM
      - Формирование запроса к LLM
    - **meeting_assistant:**
      - Триггер на любую реплику THEM
      - Rate limiting
      - Формирование запроса к LLM
  - Проверка `session.hints_enabled` перед отправкой в LLM

---

## Этап 6: LLM Service — Ollama

### 6.1 Ollama клиент
- [ ] Реализовать `server/app/services/llm_service.py`:
  - Класс `OllamaClient`:
    - Использовать OpenAI-compatible endpoint: `{OLLAMA_BASE_URL}/v1/chat/completions`
    - Streaming через `stream=True`
    - Методы:
      - `async generate_stream(messages, on_token)`
      - `cancel_current()`

### 6.2 Prompt Templates
- [ ] Создать промпты для режимов:
  - **Interview Assistant:**
    ```
    You are an interview assistant. The interviewer just asked a question.
    Based on the question and context, provide 1-3 bullet points to help
    the candidate structure their answer.

    Be concise. Each point should be 5-15 words.
    Focus on: key points to mention, structure suggestion, relevant terms.

    Do NOT repeat the question. Do NOT write full answers.

    Context from knowledge base (if available):
    {knowledge_context}

    Recent conversation:
    {conversation_context}

    Question: {question}

    Your hints (1-3 bullet points):
    ```
  - **Meeting Assistant:**
    ```
    You are a meeting assistant. Analyze what was just said and provide
    helpful context or clarification in 1-3 bullet points.

    Be concise. Each point should be 5-15 words.
    Focus on: term explanations, relevant context, follow-up suggestions.

    Context from knowledge base (if available):
    {knowledge_context}

    Recent conversation:
    {conversation_context}

    Latest statement: {statement}

    Your hints (1-3 bullet points):
    ```

### 6.3 Response Formatter
- [ ] Реализовать форматирование ответа:
  - Парсинг streaming токенов
  - Извлечение bullet points (строки начинающиеся с `-`, `•`, `1.`)
  - Ограничение до 3 пунктов
  - Публикация HINT_TOKEN для каждого токена
  - Публикация HINT_COMPLETED по завершении

### 6.4 Concurrency Policy
- [ ] Реализовать политику параллельности:
  - Максимум 1 активный запрос к LLM
  - Флаг `is_generating: bool`
  - При новом запросе во время генерации:
    - **Interview Assistant:** отменить текущий, начать новый (новый вопрос важнее)
    - **Meeting Assistant:** пропустить или заменить в очереди (latest wins)
  - Использовать `asyncio.Event` для отмены

---

## Этап 7: Knowledge Service

### 7.1 File Storage
- [ ] Реализовать `server/app/services/knowledge_service.py`:
  - Директория хранения: `./workspaces/{workspace_name}/`
  - Класс `KnowledgeService`:
    - `create_workspace(name) -> str`
    - `upload_file(workspace, filename, content)`
    - `list_files(workspace) -> List[FileInfo]`
    - `delete_file(workspace, filename)`
    - `get_workspace_stats(workspace) -> WorkspaceStats`

### 7.2 File Processing
- [ ] Реализовать обработку .md файлов:
  - Парсинг markdown → plain text
  - Извлечение заголовков (для структуры)
  - Извлечение ключевых слов:
    - Удаление stop words
    - Top N слов по частоте (N=50)
  - Сохранение индекса в JSON:
    ```json
    {
      "filename": "notes.md",
      "title": "Interview Prep",
      "keywords": ["algorithm", "complexity", "design"],
      "chunks": [
        {"text": "...", "keywords": [...]}
      ]
    }
    ```

### 7.3 Naive Retrieval
- [ ] Реализовать поиск по ключевым словам:
  - Функция `retrieve(workspace, query_text, top_k=3) -> List[str]`:
    - Извлечь ключевые слова из query_text
    - Найти файлы/chunks с максимальным пересечением keywords
    - Вернуть top_k фрагментов по 500-1200 символов
  - Ограничение общего контекста: max 2000 токенов

### 7.4 REST API для Knowledge
- [ ] Добавить endpoints в `server/app/routes/api.py`:
  ```
  POST /api/workspaces                    - создать workspace
  GET  /api/workspaces                    - список workspaces
  POST /api/workspaces/{name}/files       - загрузить файл
  GET  /api/workspaces/{name}/files       - список файлов
  DELETE /api/workspaces/{name}/files/{filename}
  GET  /api/workspaces/{name}/stats       - статистика
  ```

---

## Этап 8: Web Client — UI

### 8.1 Компоненты Layout
- [ ] Создать основной layout:
  ```
  ┌─────────────────────────────────────────────────┐
  │  Header: Logo, Status indicators, Settings      │
  ├─────────────────────────────────────────────────┤
  │                    │                            │
  │   Transcript       │   Hints Panel              │
  │   Feed             │                            │
  │                    │   • Hint 1                 │
  │   [ME] Hello...    │   • Hint 2                 │
  │   [THEM] Can you   │   • Hint 3                 │
  │   tell me about... │                            │
  │                    │                            │
  │                    │                            │
  ├─────────────────────────────────────────────────┤
  │  Controls: Start/Stop, Pause Hints, Mode Select │
  └─────────────────────────────────────────────────┘
  ```

### 8.2 Setup Screen
- [ ] Создать компонент `SetupScreen`:
  - Проверка и выбор устройств (mic, BlackHole)
  - Инструкция по настройке BlackHole + Multi-Output Device
  - Тест уровней с визуализацией
  - Кнопка "Continue to Session"

### 8.3 Knowledge Upload Screen
- [ ] Создать компонент `KnowledgeScreen`:
  - Выбор или создание workspace
  - Drag & drop зона для .md файлов
  - Список загруженных файлов с размером
  - Кнопка удаления файла
  - Summary: количество файлов, общий размер

### 8.4 Mode & Prompt Screen
- [ ] Создать компонент `ModeScreen`:
  - Список режимов: Interview Assistant, Meeting Assistant
  - Карточки с описанием каждого режима
  - Поле для кастомного промпта (textarea)
  - Кнопка "Start Session"

### 8.5 Session Screen
- [ ] Создать компонент `SessionScreen`:
  - **TranscriptFeed:**
    - Лента сообщений с автоскроллом
    - Каждое сообщение: маркер [ME]/[THEM], текст, timestamp
    - Streaming обновление текущего сегмента
    - Визуальное различие ME (справа/синий) и THEM (слева/серый)
  - **HintsPanel:**
    - Текущие подсказки с streaming отображением
    - История последних 3-5 подсказок (collapsed)
    - Индикатор генерации (typing indicator)
  - **ControlBar:**
    - Кнопка Start/Stop сессии
    - Кнопка Pause/Resume hints
    - Dropdown выбора режима
    - Индикаторы статуса: STT (mic), STT (system), LLM
    - Счётчик dropped frames (если > 0)

### 8.6 Status Indicators
- [ ] Создать компонент `StatusBar`:
  - Индикатор подключения WebSocket
  - Индикатор STT mic: idle/active/error
  - Индикатор STT system: idle/active/error
  - Индикатор LLM: idle/generating/error
  - Dropped frames counter

### 8.7 Стилизация
- [ ] Выбрать и настроить UI библиотеку (рекомендация: Tailwind CSS + shadcn/ui)
- [ ] Создать тему:
  - Тёмная тема по умолчанию (меньше отвлекает на встрече)
  - Контрастные цвета для ME/THEM
  - Читаемые шрифты для транскрипта
- [ ] Адаптивность: работа на экранах от 1280px

---

## Этап 9: Интеграция и End-to-End

### 9.1 Полный flow
- [ ] Проверить и отладить полный pipeline:
  1. Клиент захватывает mic и system audio
  2. Клиент ресемплирует и отправляет PCM фреймы
  3. Сервер получает фреймы и кладёт в очереди
  4. STT Service читает очереди, ресемплирует 16k→24k, отправляет в OpenAI
  5. OpenAI возвращает delta/completed
  6. Orchestrator агрегирует и триггерит TextChunk
  7. LLM Service генерирует подсказки
  8. События отправляются клиенту
  9. UI отображает транскрипт и подсказки

### 9.2 Пауза подсказок
- [ ] Реализовать pause/resume:
  - Клиент отправляет `{"type": "pause_hints"}` / `{"type": "resume_hints"}`
  - Сервер устанавливает `session.hints_enabled`
  - Orchestrator проверяет флаг перед отправкой в LLM
  - UI показывает статус "Hints Paused"
  - Транскрипция продолжает работать

### 9.3 Смена режима на лету
- [ ] Реализовать смену режима:
  - Клиент отправляет `{"type": "set_mode", "mode": "..."}`
  - Сервер обновляет `session.mode`
  - Следующий триггер использует новый режим
  - UI обновляет выбранный режим

---

## Этап 10: Тестирование

### 10.1 Unit тесты
- [ ] Тесты для `audio.py`:
  - `test_resample_16k_to_24k`
  - `test_normalize_audio`
- [ ] Тесты для `orchestrator.py`:
  - `test_text_aggregation`
  - `test_trigger_on_completed`
  - `test_trigger_on_timeout`
  - `test_trigger_on_word_count`
  - `test_rate_limiter`
- [ ] Тесты для `knowledge_service.py`:
  - `test_keyword_extraction`
  - `test_retrieval_ranking`
- [ ] Тесты для question detection:
  - `test_question_mark_detection`
  - `test_question_words_detection`
  - `test_invitation_detection`

### 10.2 Integration тесты
- [ ] Тест WebSocket протокола:
  - Подключение и handshake
  - Отправка аудио фреймов
  - Получение событий транскрипции
- [ ] Тест STT Service с mock OpenAI:
  - Отправка аудио
  - Получение delta/completed

### 10.3 E2E тест
- [ ] Создать тест с записанным аудио:
  - Подготовить тестовый аудиофайл (диалог интервью)
  - Разделить на mic и system каналы
  - Отправить через WebSocket
  - Проверить получение транскрипции
  - Проверить генерацию подсказок

---

## Этап 11: DevOps и документация

### 11.1 Docker
- [ ] Создать `server/Dockerfile`:
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```
- [ ] Создать `docker-compose.yml`:
  ```yaml
  services:
    server:
      build: ./server
      ports:
        - "8000:8000"
      environment:
        - OPENAI_API_KEY=${OPENAI_API_KEY}
        - OLLAMA_BASE_URL=http://ollama:11434
      depends_on:
        - ollama
      volumes:
        - ./workspaces:/app/workspaces

    ollama:
      image: ollama/ollama
      ports:
        - "11434:11434"
      volumes:
        - ollama_data:/root/.ollama
      deploy:
        resources:
          reservations:
            devices:
              - capabilities: [gpu]

  volumes:
    ollama_data:
  ```

### 11.2 Скрипты запуска
- [ ] Создать `scripts/setup.sh`:
  - Проверка Python версии
  - Создание venv
  - Установка зависимостей
  - Проверка наличия `/opt/secure-configs/.env` и вывод инструкции по настройке
- [ ] Создать `scripts/dev.sh`:
  - Запуск сервера в dev режиме
  - Запуск клиента в dev режиме
- [ ] Создать `scripts/build.sh`:
  - Сборка клиента
  - Копирование в server/static

### 11.3 Документация
- [ ] Обновить `README.md`:
  - Описание проекта
  - Требования (Python, Node.js, BlackHole)
  - Инструкция по настройке BlackHole на Mac
  - Инструкция по запуску в dev режиме
  - Инструкция по запуску через Docker
  - Переменные окружения

---

## Критерии приёмки POC
- [ ] Mic и system каналы отображаются как ME и THEM в одной ленте
- [ ] Подсказки появляются автоматически и стримятся
- [ ] Кнопка pause останавливает генерацию подсказок, но транскрипция продолжается
- [ ] Загрузка .md файлов влияет на подсказки
- [ ] Задержка от фразы до подсказки не превышает 2 секунд в типичном случае
- [ ] UI интуитивно понятен и работает в Chrome на macOS

---

## Примечания

### Зависимости между этапами

```
Этап 1 (инфраструктура)
    ↓
Этап 2 (WebSocket) ←──────────────────┐
    ↓                                 │
Этап 3 (Client audio) ────────────────┤
    ↓                                 │
Этап 4 (STT) ─────────────────────────┤
    ↓                                 │
Этап 5 (Orchestrator) ────────────────┤
    ↓                                 │
Этап 6 (LLM) ─────────────────────────┤
    ↓                                 │
Этап 7 (Knowledge) ───────────────────┘
    ↓
Этап 8 (UI)
    ↓
Этап 9 (Integration)
    ↓
Этап 10 (Testing)
    ↓
Этап 11 (DevOps)
```

### Приоритеты при нехватке времени
1. **Must have:** Этапы 1-6, 8.5, 9.1 — минимальный работающий прототип
2. **Should have:** Этапы 7, 8.1-8.4, 9.2-9.3 — полноценный POC
3. **Nice to have:** Этапы 10, 11 — качество и удобство

### Риски и mitigation
| Риск | Вероятность | Mitigation |
|------|-------------|------------|
| Сложность захвата системного звука | Средняя | Подробная инструкция по настройке BlackHole |
| Высокая латентность STT | Средняя | Тюнинг VAD параметров, мониторинг метрик |
| Перегрузка LLM запросами | Высокая | Строгий rate limiting, политика latest wins |
| Качество keyword retrieval | Средняя | Fallback: LLM работает без контекста |
