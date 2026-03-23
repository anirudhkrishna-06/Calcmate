# Cognitive Engine

The `cognitive_engine` folder now contains the live backend runtime for TCMTE through Phase 6.

Implemented now:

- FastAPI + Uvicorn backend entrypoints
- Session orchestrator with event-driven lifecycle control
- WebSocket session channels for live UI updates
- Multi-stage audio pipeline:
  - acoustic feature normalization
  - Deepgram transcription
  - semantic intent parsing
  - contextual refinement
  - optional edge-case LLM refinement
  - fused cognitive chunks
- Problem Intelligence Layer:
  - problem parsing
  - curriculum concept mapping
  - method enumeration
  - optimal strategy selection
  - symbolic equation structuring
  - solution graph construction
- In-memory session registry for local development
- Rule-based semantic mapper in `app/semantic_rules.py`
- Rebuilt CalcMate-style problem intelligence modules in `app/problem_intelligence/`

## Phase 6 flow

Each session now begins with:

1. `SESSION_STARTED`
2. `PROBLEM_STRUCTURED`
3. problem graph stored on `session_state.problem_structure`
4. live audio cognition pipeline begins

Each chunk then moves through:

1. `AUDIO_CHUNK_RECEIVED`
2. `ACOUSTIC_PROFILE_COMPUTED`
3. `TRANSCRIPTION_COMPLETED`
4. `SEMANTIC_INTENT_INFERRED`
5. `RULE_INTENT_CLASSIFIED`
6. `CONTEXT_REFINED`
7. `LLM_REFINEMENT_COMPLETED`
8. `INTENT_CLASSIFIED`
9. timeline / deviation / intervention processing

## Problem Intelligence Layer

The rebuilt problem structuring code lives in:

- `cognitive_engine/app/problem_intelligence/gemini_parser.py`
- `cognitive_engine/app/problem_intelligence/concept_mapper.py`
- `cognitive_engine/app/problem_intelligence/method_library.py`
- `cognitive_engine/app/problem_intelligence/symbolic_builder.py`
- `cognitive_engine/app/problem_intelligence/graph_builder.py`
- `cognitive_engine/app/problem_intelligence/pipeline.py`

The pipeline produces a stable `problem_structure` object containing:

- concepts
- parameters
- constraints
- valid methods
- optimal path
- symbolic equations
- WL-style subtrees
- dependency graph nodes and edges

## Deepgram setup

Add a root-level `.env` file in the project root with at least:

```env
DEEPGRAM_API_KEY=your_key_here
DEEPGRAM_MODEL=nova-3
DEEPGRAM_LANGUAGE=en
COGNITIVE_STORE_AUDIO=false
```

Optional behavior:

- `COGNITIVE_STORE_AUDIO=true` stores chunk audio under `cognitive_engine/data/audio/`
- near-silent chunks are skipped before Deepgram calls to reduce API usage
- repeated identical audio blobs are cached by hash to avoid duplicate transcription calls

## Gemini parser setup

Gemini is optional and only used during problem structuring when enabled.
If Gemini is unavailable, the system falls back to the internal rule-based parser.

```env
GEMINI_PARSER_ENABLED=false
GEMINI_API_KEY=
GEMINI_PARSER_MODEL=gemini-2.0-flash
GEMINI_PARSER_TIMEOUT_SECONDS=1.4
```

## Semantic rules

Customize rule-based intent mapping in:

- `cognitive_engine/app/semantic_rules.py`

Recommended extension points there:

- `RULEBOOK`
- `UNCERTAINTY_MARKERS`
- `DECISION_MARKERS`
- `FORMULA_REFERENCES`
- `extract_semantic_signals()`
- `classify_semantic_intent()`

## Run in the `voice` venv

Install dependencies:

```powershell
voice\Scripts\pip install -r cognitive_engine\requirements.txt
```

Start the server:

```powershell
voice\Scripts\python -m uvicorn cognitive_engine.app.main:app --reload
```

Health check:

- `http://127.0.0.1:8000/health`

API docs:

- `http://127.0.0.1:8000/docs`
