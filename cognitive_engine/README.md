# Cognitive Engine Phase 1

Phase 1 defines the contract backbone for the Time Cognitive Math Tracing Engine (TCMTE).

This folder contains:

- A FastAPI + Uvicorn backend scaffold
- Immutable request/response contracts for session lifecycle APIs
- Internal schemas for cognitive chunks and session state
- An MCP-style agent graph definition for backend coordination
- A lightweight in-memory runtime store for local development

## Phase 1 scope

This phase focuses on definition, not full cognitive implementation.

Implemented here:

- `POST /start_session`
- `POST /stream_audio_chunk`
- `POST /intervention_event`
- `POST /end_session`
- `POST /generate_report`
- Structured schemas for chunks, timeline events, reports, and session state
- Session lifecycle orchestration
- Agent registry and graph metadata

Not implemented yet:

- Real ASR / speech-to-text
- Real-time DSP feature extraction
- CalcMate structural problem parsing
- Production message bus / Redis / persistent storage
- Real intervention policies

## Run in the `voice` venv

Install dependencies:

```powershell
voice\Scripts\pip install -r cognitive_engine\requirements.txt
```

Start the server:

```powershell
voice\Scripts\python -m uvicorn cognitive_engine.app.main:app --reload
```

Open the API docs:

- `http://127.0.0.1:8000/docs`

## Suggested Phase 2 direction

- Replace the in-memory store with Redis
- Add WebSocket or event-stream delivery for interventions and live timeline updates
- Connect Problem Structuring Agent to CalcMate canonicalization
- Replace placeholder classification with audio + transcript models
