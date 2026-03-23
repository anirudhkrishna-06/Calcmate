# Phase 1 Specification

## API Contracts

### `POST /start_session`
Initializes a new cognitive session.

Request fields:
- `problem_payload`
- `user_id`
- `session_metadata`

Response fields:
- `session_id`
- `session_token`
- `problem_payload`
- `initial_state`
- `agent_graph`

### `POST /stream_audio_chunk`
Accepts a low-latency audio chunk event.

Request fields:
- `session_id`
- `chunk_id`
- `timestamp.start_time`
- `timestamp.end_time`
- `audio_payload_b64`
- `frontend_features`
- `transcript_hint`

Response fields:
- `session_id`
- `chunk_id`
- `detected_intent`
- `confidence`
- `intervention_recommended`
- `current_phase`

### `POST /intervention_event`
Formal intervention logging contract.

Request fields:
- `session_id`
- `intervention_id`
- `trigger_reason`
- `message`

Response fields:
- `session_id`
- `intervention_id`
- `logged`
- `intervention_count`

### `POST /end_session`
Closes the active session.

Request fields:
- `session_id`
- `final_timestamps`
- `image_reference`

Response fields:
- `session_id`
- `phase`
- `closed_at`
- `total_chunks`
- `total_interventions`

### `POST /generate_report`
Builds the final cognitive report.

Request fields:
- `session_id`

Response fields:
- `timeline_metrics`
- `deviation_analysis`
- `strategy_evaluation`
- `improvement_suggestions`

## Cognitive Chunk Schema

Atomic immutable log record:
- `chunk_id`
- `timestamp`
- `audio_features`
- `intent`
- `confidence`
- `latency_seconds`
- `transcript_excerpt`
- `created_at`

Intent vocabulary:
- `problem_understanding`
- `parameter_recognition`
- `strategy_selection`
- `execution_start`
- `deviation`
- `silence_reflection`

## Agent Graph

Nodes:
- Problem Structuring Agent
- Audio Cognition Agent
- Timeline Engine
- Strategy Validator
- Intervention Agent
- Report Generator

Execution flow:
- Session start boots the Problem Structuring Agent
- Audio chunks flow through Audio Cognition Agent into Timeline Engine
- Timeline Engine feeds Strategy Validator
- Strategy Validator can trigger Intervention Agent
- Timeline Engine and Strategy Validator feed Report Generator after session end

## Session State Model

Single source of truth fields:
- `phase`
- `timeline`
- `chunks`
- `deviation_score`
- `intervention_count`
- `created_at`
- `updated_at`
- `closed_at`

Phase values:
- `understanding`
- `strategy_selection`
- `execution`
- `reflection`
- `completed`

## Runtime Notes

Current storage is in-memory for local development.
Recommended production upgrade path:
- Redis for session state
- event bus or WebSocket channel for interventions and live timeline streaming
- CalcMate integration for structured problem payloads
