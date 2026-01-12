# PRD: Realtime Interview and Meeting Copilot (Pipecat POC)

Дата: 2026-01-11  
Владелец продукта: Пользователь  
Цель документа: описать POC и следующие фазы разработки системы, которая в реальном времени слушает аудио встречи, потоково транскрибирует речь, помечает источник (я или собеседник), затем автоматически генерирует короткие подсказки по выбранному режиму, используя LLM и локальные файлы знаний.

## 1. Контекст и проблема
Нужна система, которая:

1. Постоянно слушает аудио во время встречи.
2. Выделяет человеческую речь и потоково транскрибирует без ожидания длинных пауз.
3. Разделяет поток на два источника:
   1) микрофон пользователя – это "Я" (сам пользователь)  
   2) системный звук – это собеседник
4. По мере поступления текста автоматически запускает обработку в LLM по выбранному режиму и показывает подсказки с минимальной задержкой.
5. Дает возможность подключать локальные файлы знаний, чтобы подсказки опирались на пользовательские материалы.

Основные режимы POC:
1) Interview Assistant  
2) Meeting Assistant
3) Как пример расширяемости, предполагается режим синхронного перевода на другой язык

## 2. Цели

### POC цели
1. Захват двух аудио каналов на Mac:
   1) микрофон пользователя  
   2) системный звук через виртуальное устройство BlackHole
2. Потоковая транскрипция каждого канала в реальном времени.
3. Единая лента событий с маркерами источника: ME, THEM.
4. Автоматическая генерация коротких подсказок 1–3 пункта.
5. Пауза подсказок: транскрипция продолжает работать, LLM подсказки временно не генерируются.
6. Веб интерфейс хостится на Linux сервере в LAN, открывается в локальном барузере на компьютере (как частный случай для POC - Chrome на macOS.
7. Загрузка файлов знаний на сервер перед началом сессии, формат .md.
8. Современный, интуитивно понятный, красивый интерфейс пользователя.

### Дальнейшие цели
1. Режим одного аудио канала и диаризация спикеров.
2. Удержание идентичности спикеров по всей сессии.
3. RAG по большим базам знаний и поддержка pdf, docx, txt.
4. Производственный транспорт медиа (WebRTC), авторизация, TLS, многопользовательский режим.

## 3. Не цели POC
1. Голосовой вывод (TTS) перевода или подсказок.
2. Мультисессии и параллельные встречи.
3. Полная приватность и on prem STT.
4. Сложные правила автоматизации типа if then без UI редактора.
5. Универсальная поддержка всех браузеров, фокус на Chrome.

## 4. Пользовательские сценарии

### 4.1 Interview Assistant
Пользователь проходит интервью. Система слушает интервьюера, транскрибирует, распознает вопросы и показывает краткий план ответа, термины, подсказки по структуре.

### 4.2 Meeting Assistant
Пользователь на рабочей встрече. Система слушает собеседника, транскрибирует, подсвечивает термины, дает краткие объяснения и вытаскивает релевантные фрагменты из загруженных заметок.

### 4.3 Single channel режим
Встреча в окружении, где невозможно разделить микрофон и системный звук. Тогда требуется диаризация и правила обработки по спикерам. Это не входит в POC, но входит в Phase 2.

## 5. Окружение и ограничения

### Клиент
MacBook Pro 2020 Intel, macOS 15.7.2  
Браузер: Chrome  
Разрешены зависимости: BlackHole, Multi Output Device.

### Сервер
Ubuntu 22.04.5, Ryzen 5 3600, RAM 46 GB  
GPU RTX 3090 24 GB  
Docker доступен  
Внутри LAN нет ограничений на порты  
TLS и авторизация не требуются для POC.

### Модели

POC:
1) STT: OpenAI Realtime Transcription Sessions (streaming STT).  
2) LLM: Ollama на сервере через OpenAI compatible API.

Дальше:
1) альтернативные STT провайдеры  
2) прямой запуск LLM на сервере через vLLM, llama cpp, TensorRT LLM.

## 6. Высокоуровневая архитектура

Компоненты:

1) Web Client (Chrome)
   1) захват аудио двух источников  
   2) ресемплинг и упаковка PCM  
   3) WebSocket связь с сервером  
   4) UI: лента транскрипта, подсказки, режимы, промпты, пауза, загрузка знаний
2) Server Gateway (FastAPI)
   1) хостинг веб приложения  
   2) WebSocket endpoint для аудио и событий  
   3) менеджер сессий
3) Audio Stream Router
   1) прием двух аудио потоков  
   2) нормализация, уровни, optional noise suppression  
   3) отправка в STT
4) STT Service
   1) 2 параллельные Realtime transcription сессии OpenAI  
   2) получение delta и completed событий  
   3) выдача потока текстовых событий
5) Orchestrator
   1) агрегатор фрагментов речи  
   2) триггеры подсказок  
   3) политика очередей и backpressure
6) LLM Service
   1) вызов Ollama API, streaming ответов  
   2) post processing в 1–3 пункта
7) Knowledge Service
   1) хранение и чтение .md  
   2) простое извлечение релевантных фрагментов без RAG
8) Event Bus
   1) внутренняя шина событий и очереди на asyncio  
   2) формат сообщений для клиента

## 7. POC Pipeline подробно

### 7.1 Захват аудио на Mac

Цель: получить два независимых источника в Chrome.

1) Mic stream  
   navigator.mediaDevices.getUserMedia(audio: true)

2) System stream  
   1) пользователь ставит BlackHole  
   2) создается Multi Output Device: наушники плюс BlackHole  
   3) Zoom или Teams выводят звук в Multi Output  
   4) Chrome получает System stream как микрофон, выбранный Input device: BlackHole 2ch

Результат: два MediaStream, каждый содержит один audio track.

### 7.2 Преобразование и отправка аудио

Стандарт POC по сети:
1) PCM s16le mono  
2) sample rate 16000 Hz по требованию POC  
3) frame size 20 ms

Примечание: OpenAI Realtime transcription требует 24000 Hz для pcm16, поэтому сервер будет ресемплить 16k → 24k перед отправкой в OpenAI. В Phase 1 будет опция сразу держать 24k end to end.

Формат WebSocket сообщений client → server:

1) control сообщения JSON
   type: start_session, stop_session, pause_hints, resume_hints, set_mode, set_prompt, set_speaker_policy

2) audio frames binary
   заголовок 1 byte channel_id (0 mic, 1 system)  
   далее raw PCM bytes за 20 ms.

### 7.3 Серверная приемка и очереди

При получении аудио frames сервер:

1) определяет канал по channel_id  
2) кладет PCM в asyncio.Queue на этот канал, maxsize фиксирован, например 200 фреймов
3) если очередь переполнена, применяется политика:
   1) drop oldest для audio, чтобы сохранить свежесть  
   2) метрика dropped_audio_frames увеличивается

### 7.4 STT: OpenAI Realtime transcription sessions

На сервере открываются две независимые websocket сессии OpenAI Realtime, тип transcription, одна на канал.

Конфигурация STT POC:
1) transcription model: gpt-4o-mini-transcribe или gpt-4o-transcribe  
2) turn_detection: server_vad с малым silence_duration_ms, например 250–400 ms  
3) noise_reduction: near_field

Реализация:
1) аудио фреймы из очереди ресемплить в 24 kHz mono pcm16  
2) отправлять как input_audio_buffer.append, периодически commit по server_vad событиям  
3) слушать events:
   1) conversation.item.input_audio_transcription.delta  
   2) conversation.item.input_audio_transcription.completed

На выходе STT генерируется поток событий TranscriptEvent:
1) speaker: ME или THEM  
2) text_delta: строка или пусто  
3) text_completed: строка или пусто  
4) timestamps: server time

### 7.5 Aggregation и триггеры подсказок

Проблема: транскрипция идет дельтами, LLM нельзя дергать на каждый символ.

Нужно два уровня агрегации:

1) Live text для UI  
   UI получает delta и обновляет текущую строку спикера без вызова LLM.

2) Stable chunk для LLM  
   триггерится, когда:
   1) пришел completed от STT  
   2) либо таймер, например каждые 800 ms, если completed долго не приходит  
   3) либо накопилось N слов, например 12 слов

Формируется TextChunk:
1) speaker  
2) text  
3) last_context: последние 1–2 предложения по этому speaker  
4) global_context: короткая выжимка последних 30 секунд диалога, если нужно

### 7.6 Режимы POC

#### Interview Assistant
Триггеры:
1) собеседник сказал вопрос  
2) признак вопроса: знак вопроса в тексте, или вопросительные слова, или rising intonation недоступно в POC. Вопросм также является приглашение к рассказу или пояснению из контекста.

Действие:
1) сформировать запрос к LLM:
   1) system prompt режима  
   2) последние реплики  
   3) текущий вопрос  
   4) опционально релевантные заметки из Knowledge Service
2) ответ LLM форматировать строго 1–3 пункта.

#### Meeting Assistant
Триггеры:
1) новая завершенная реплика собеседника
2) frequency limiter: не чаще 1 раза в 2 секунды
3) optional detection:
   1) термин  
   2) упоминание конкретного проекта
   3) вопрос, приглашение по контексту к рассказу или продолжению беседы

Действие:
1) извлечь top K фрагментов из knowledge путем простого поиска по ключевым словам
2) сформировать подсказку 1–3 пункта:
   1) объяснить термин  
   2) дать контекст  
   3) подсказать вопрос уточнения

#### Translator пример
Не обязателен в POC, но режим должен быть создаваемым:
1) свой system prompt  
2) свои триггеры, например always translate THEM.

### 7.7 Пауза подсказок
Состояние session:
hints_enabled: true or false

При hints_enabled=false:
1) STT и лента транскрипта продолжают работать  
2) Orchestrator не отправляет TextChunk в LLM  
3) UI показывает статус Paused

### 7.8 LLM: Ollama streaming
LLM сервис общается с Ollama на сервере.

Требования:
1) OpenAI compatible endpoint или /api/chat  
2) streaming токенов включен
3) строгий формат ответа:
   1) 1–3 пункта  
   2) без длинных объяснений  
   3) без повторов текста вопроса

Политика параллельности:
1) одновременно активен максимум 1 запрос в LLM  
2) если приходит новый TextChunk пока LLM занят:
   1) если Interview Assistant и это новый вопрос, то отменить предыдущую генерацию и начать новый
   2) если Meeting Assistant, то пропустить или поставить в очередь только последний, policy latest wins.

### 7.9 Отправка событий в UI
Единый WebSocket server → client, события JSON:

1) transcript_delta
   speaker, text, segment_id
2) transcript_completed
   speaker, text, segment_id
3) hint_token
   hint_id, token
4) hint_completed
   hint_id, final_text, mode
5) status
   connected, stt_state, llm_state, dropped_frames_count

## 8. Стек и выбор технологий

### POC
Server:
1) Python 3.10+  
2) FastAPI для web и websocket  
3) Pipecat для каркаса real time пайплайна и utilities  
4) OpenAI Realtime websocket client на Python
5) Ollama для LLM
6) Хранение файлов: файловая система сервера, per workspace folder

Client:
1) React + Vite
2) Web Audio API для ресемплинга
3) WebSocket для отправки аудио и получения событий
4) UI библиотека по выбору команды, минимализм

DevOps:
1) docker compose опционально
2) .env для ключей OpenAI и настроек Ollama

### Почему Pipecat
1) Есть готовые транспорты и client SDK для WebSocket прототипов.
2) Есть серверные utilities для аудио фильтров, VAD, frame pipeline.
3) Легко мигрировать на WebRTC transport в следующих фазах.

## 9. UX и экраны POC

### 9.1 Setup

1) Проверка устройств: Mic, BlackHole input  
2) Инструкция подключения BlackHole и Multi Output  
3) Кнопка Test: показать уровни двух каналов

### 9.2 Knowledge Upload
1) Upload .md files  
2) Workspace name  
3) Summary: количество файлов, общий размер  
4) Обработка: извлечение текста, индекс для keyword search

### 9.3 Modes и Prompts
1) список режимов  
2) создание режима  
3) редактирование system prompt  
4) выбор активного режима

### 9.4 Session
1) Start, Stop  
2) Pause hints, Resume hints  
3) Лента транскрипта с маркерами ME и THEM  
4) Панель подсказок, streaming вывод  
5) Статус STT и LLM, dropped frames

## 10. Knowledge Service POC
Цель POC: дать LLM контекст из пользовательских .md без полноценного RAG.

Подход:
1) при загрузке сохраняем файл и строим простую карту:
   1) title  
   2) plain text  
   3) список ключевых слов, например top N по частоте
2) retrieval:
   1) взять текст chunk  
   2) извлечь keywords  
   3) найти совпадения по файлам  
   4) вернуть 1–3 коротких фрагмента по 500–1200 символов

Ограничение:
1) max_tokens контекста фиксирован, чтобы не увеличивать задержку  
2) если контекста нет, LLM работает без него.

## 11. Нефункциональные требования

### Задержка
POC целевое: до 1.5 секунды от произнесенной фразы до подсказки.

Разбиение:
1) STT partial: 200–800 ms  
2) STT commit: до 1.2 s в зависимости от VAD  
3) LLM: 300–900 ms до первых токенов в streaming

### Надежность
1) reconnect WebSocket клиента  
2) watchdog на STT, если Realtime соединение упало, автопереподключение  
3) graceful stop сессии

### Наблюдаемость
1) метрики:
   1) audio frames in, dropped  
   2) STT latency per channel  
   3) LLM time to first token, total time  
   4) hints per minute
2) structured logs JSON
3) debug mode: сохранять короткие фрагменты аудио локально на сервере, опция.

## 12. Безопасность POC
POC в LAN:
1) без TLS  
2) без авторизации

В будущих фазах:
1) TLS  
2) auth token  
3) хранение ключей OpenAI только на сервере  
4) rate limiting per user

## 13. План разработки

### Фаза POC
Цель: end to end работа в LAN с BlackHole, двумя каналами, streaming STT, hints 1–3 пункта.

Этапы:
1) Репозиторий и базовый сервер
   1) FastAPI статик сайт и ws endpoint
   2) session manager
2) Web клиент
   1) захват mic
   2) выбор input device BlackHole
   3) ресемплинг 48k → 16k, PCM frames 20 ms
   4) отправка frames на сервер
3) STT service
   1) OpenAI Realtime transcription websocket клиент
   2) ресемплинг 16k → 24k
   3) delta и completed события в event bus
4) Orchestrator
   1) TextChunk aggregation
   2) режим Interview Assistant с question detection
   3) режим Meeting Assistant с limiter
5) LLM service
   1) Ollama streaming
   2) форматирование 1–3 пункта
6) Knowledge upload
   1) upload .md
   2) naive retrieval
7) UI session
   1) лента транскрипта
   2) подсказки streaming
   3) pause hints
8) Тесты
   1) unit тесты на aggregation и policy очередей
   2) e2e тест с записанным аудио

Критерии приемки:
1) mic и system каналы отображаются как ME и THEM в одной ленте  
2) подсказки появляются автоматически и стримятся  
3) кнопка pause останавливает генерацию подсказок, но транскрипция продолжается  
4) загрузка .md влияет на подсказки в Meeting Assistant и в Interview Assistant

### Фаза 1: Ускорение и упаковка
1) Аудио транспорт:
   1) опция 24k end to end  
   2) улучшенный ресемплинг в браузере
2) Переход на WebRTC транспорт как основной
3) Server side VAD тюнинг, target 700 ms
4) Политика отмены LLM для новых вопросов
5) Packaging:
   1) docker compose для сервера  
   2) скрипт установки зависимостей BlackHole и настройки Multi Output как пошаговая инструкция
6) Улучшение UX:
   1) hotkeys в браузере через shortcuts  
   2) компактный режим UI.

### Фаза 2: Диаризация и устойчивые спикеры
1) Single channel режим:
   1) захват одного источника  
   2) diarization на сервере
2) Удержание идентичности:
   1) voice embedding per speaker  
   2) mapping speaker A to THEM, speaker B to ME
3) Настройка speaker policy в UI
4) Улучшение knowledge retrieval:
   1) keyword search плюс tf idf  
   2) подготовка к RAG.

### Фаза 3: RAG и продакшен характеристики
1) Хранилище знаний:
   1) поддержка pdf, docx, txt, md  
   2) парсинг пайплайн, включая optional интеграцию внешних парсеров  
   3) vector store, например Qdrant
2) RAG:
   1) chunking  
   2) embeddings модель локально или через API  
   3) retrieval top K  
   4) citations в подсказках
3) Безопасность:
   1) TLS  
   2) auth  
   3) multi user
4) Сохранение данных:
   1) опции записи аудио и текста  
   2) retention policy

## 14. Риски и способы снижения
1) Захват системного звука на macOS
   риск: пользователь неправильно настроил Multi Output  
   снижение: wizard и тест уровней, сохранение выбранных устройств

2) Латентность STT
   риск: VAD делает большие куски  
   снижение: тюнинг server_vad, переход на 24k, WebRTC

3) Перегруз LLM
   риск: слишком много триггеров  
   снижение: limiter, latest wins, отмена генерации

4) Качество подсказок без RAG
   риск: knowledge слишком большой  
   снижение: строгие лимиты контекста, затем Phase 3 RAG

## 15. Открытые решения
1) Точный формат websocket протокола и сериализация frames  
2) Выбор конкретной Ollama модели для POC  
3) Выбор стратегии question detection, heuristics vs small classifier  
4) UI дизайн и компоненты, минимальный набор
