# MathMend

MathMend is a full-stack math learning platform that combines tutoring, adaptive practice, teacher-driven contests, and a cognitive reasoning engine for structure-aware problem solving.

At a high level, the project has three cores:

- A main FastAPI backend for chat, OCR, adaptive quiz, and contest evaluation
- A dedicated Cognitive Engine backend for live reasoning-session analysis
- A React + Vite frontend with student, teacher, contest, quiz, and thinking-session experiences

## What The Project Does

MathMend is designed to do more than return answers. It tries to understand how a learner is approaching a problem, whether their path matches a valid solution structure, and where interventions should happen.

The platform supports:

- Math tutoring through an LLM-backed chat API
- OCR-based answer extraction from uploaded work
- Adaptive quiz generation and mastery tracking
- Teacher-created olympiad-style contests with leaderboard and rating updates
- Structure-oriented retrieval and problem similarity search
- Live cognitive monitoring during think-aloud solving sessions
- Post-session reports, wrong-step analysis, and answer validation

## Core Systems Explained

### 1. Cognitive Engine

The Cognitive Engine is the reasoning-analysis backend in [`cognitive_engine/app/main.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/main.py). It powers live "thinking sessions" where the system listens to a student solving a problem, structures the problem, tracks the student's reasoning path, and produces interventions and reports.

Its flow is:

1. Start a session with the raw problem text.
2. Build a structured representation of the problem.
3. Stream audio chunks from the frontend.
4. Transcribe and refine each chunk.
5. Map each chunk to reasoning intent.
6. Compare the observed reasoning path against an expected solution graph.
7. Estimate confusion, inefficiency, and deviation risk.
8. Generate a final report and validate the submitted answer image.

Main capabilities:

- Session orchestration and lifecycle management
- WebSocket updates for live UI feedback
- Deepgram-based audio transcription
- Optional LLM refinement for ambiguous chunks
- Problem structuring into concepts, parameters, constraints, methods, and equations
- Cognitive path tracking over time
- Graph-based strategy validation
- Predictive analytics using trained regression and classification models
- Final report generation and answer validation

Key files:

- [`cognitive_engine/app/orchestrator.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/orchestrator.py)
- [`cognitive_engine/app/context_engine.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/context_engine.py)
- [`cognitive_engine/app/problem_intelligence/pipeline.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/problem_intelligence/pipeline.py)
- [`cognitive_engine/app/strategy_validation/cognitive_path.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/strategy_validation/cognitive_path.py)
- [`cognitive_engine/app/strategy_validation/graph_alignment.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/strategy_validation/graph_alignment.py)

### 2. Agentic AI Perspective In The Cognitive Engine

The Cognitive Engine is best understood as an event-driven multi-agent system rather than a single LLM call.

Why it is agentic:

- It decomposes cognition analysis into specialized agents with narrow responsibilities.
- Each agent consumes a typed event and emits a new typed event.
- The orchestrator decides execution order and routes outputs to the next relevant agent.
- The system mixes deterministic rules, structured state, external tools, and optional LLM calls.
- Expensive model calls are only used when uncertainty is high, so the fast path stays lightweight.

In other words, the engine behaves like a practical agent pipeline:

- perceive the student signal
- interpret it
- refine it using context
- validate it against a structured plan
- intervene when needed
- summarize the session afterward

This agent graph is explicitly exposed by `build_agent_graph()` in [`cognitive_engine/app/agents.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/agents.py), and returned at session start by the orchestrator in [`cognitive_engine/app/orchestrator.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/orchestrator.py).

#### Agent By Agent

**Problem Structuring Agent**

- Runs at session start.
- Converts raw problem text into `ProblemStructure`.
- Identifies domain, concepts, methods, constraints, equations, and optimal path.
- Creates the foundation that every downstream agent depends on.

**Acoustic Feature Agent**

- Receives raw audio chunks from the frontend.
- Normalizes frontend audio features.
- Builds an acoustic profile such as speech density, silence ratio, hesitation score, and energy features.
- Optionally stores audio locally for debugging or analysis.

**Transcription Agent**

- Calls Deepgram through [`cognitive_engine/app/deepgram_client.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/deepgram_client.py).
- Uses keyword-aware transcription based on the active problem structure.
- Skips low-value chunks when needed.
- Segments transcript output into sentence-level units with timestamps.

**Semantic Intent Agent**

- Interprets what the student is doing cognitively.
- Uses semantic rules plus problem keywords to classify signals like understanding, parameter recognition, strategy selection, deviation, verification, or stuck state.
- Produces an initial semantic intent score.

**Rule Classification Agent**

- Converts semantic output into a normalized `CognitiveChunk`.
- Packages confidence, certainty, timestamps, transcript, and acoustic context into a single structured unit.
- This is the first stable internal reasoning object for the chunk.

**Context Refinement Agent**

- Uses recent chunk history to reinterpret the current chunk.
- Detects trajectories such as stable progress, confusion building, exploration, or execution commitment.
- Helps the engine reason over local sequences instead of isolated sentences.

**LLM Refinement Agent**

- Handles only ambiguous or high-uncertainty cases.
- Calls the refinement client in [`cognitive_engine/app/llm_refiner.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/llm_refiner.py).
- Uses recent chunk context and the active problem to upgrade or confirm intent classification.
- Keeps the system agentic without turning every step into an expensive model call.

**Final Intent Agent**

- Publishes the final refined chunk.
- Acts as the handoff point from interpretation to downstream action systems.

**Timeline Engine**

- Converts technical chunk analysis into student-friendly and UI-friendly timeline updates.
- Emits readable events like "Understanding the problem" or "Strategy identified".
- Also suggests lifecycle transitions, such as moving from thinking into solving.

**Strategy Validator Agent**

- This is one of the most important agentic pieces in the engine.
- Maps each chunk to nodes in the solution graph.
- Updates the live cognitive path.
- Measures path alignment, progress, deviation, delay, inefficiency, and oscillation.
- Produces graph-aware validation instead of plain text similarity scoring.

**Intervention Agent**

- Acts like the real-time coach.
- Consumes deviation, delay, and inefficiency events.
- Delivers minimal Socratic prompts rather than long explanations.
- Uses cooldowns, intervention caps, and domain-aware prompts so the system stays helpful without becoming noisy.

**Report Generator Agent**

- Runs after the session ends.
- Builds final time analysis, thinking graph, validation summary, predictive analytics summary, and wrong-step analysis.
- Can use Grok or Gemini providers when configured, with rule-based fallbacks when not.

#### Orchestration Model

The orchestrator in [`cognitive_engine/app/orchestrator.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/orchestrator.py) is the runtime coordinator for the agent graph.

Its job is to:

- create and lock session state
- emit the initial `SESSION_STARTED` event
- run problem structuring before live chunk processing
- build the enriched solution graph
- push audio chunks through the full agent chain
- route validation signals into intervention logic
- broadcast updates over WebSockets
- cache reports and final session outputs

The chunk pipeline is effectively:

`AUDIO_CHUNK_RECEIVED -> ACOUSTIC_PROFILE_COMPUTED -> TRANSCRIPTION_COMPLETED -> SEMANTIC_INTENT_INFERRED -> RULE_INTENT_CLASSIFIED -> CONTEXT_REFINED -> LLM_REFINEMENT_COMPLETED -> INTENT_CLASSIFIED -> validation/timeline/intervention`

This means the engine is orchestrated as a typed event system, not as a single monolithic prompt.

#### Tools And Frameworks Used By The Agents

The agentic layer uses a mix of deterministic tools and model-backed tools:

- FastAPI for API routing and runtime entrypoints
- Pydantic contracts for typed agent inputs, outputs, events, and state
- WebSockets for live timeline and intervention streaming
- Deepgram as the speech-to-text tool
- Gemini as an optional problem parser and graph enhancer
- OpenAI-compatible responses API for LLM refinement
- Ollama for local model-backed reasoning and answer judgment
- Grok/Gemini fallback stack for final report insight generation
- scikit-learn and XGBoost for predictive analytics
- Rule-based semantic analysis and graph-based validation for deterministic control

This combination is important: the system does not treat LLMs as the whole architecture. LLMs are only one class of tool inside a broader agentic runtime.

#### Future Agentic AI Prospect

The Cognitive Engine already has the right shape for deeper agentic expansion.

Strong future directions include:

- planner agents that choose tutoring strategy based on live validation state
- memory agents that compare a learner's current reasoning to past sessions
- retrieval agents that fetch structurally similar solved problems during intervention
- teacher-facing recommendation agents that convert reports into action plans
- policy agents that decide when to stay silent versus when to intervene
- simulation agents that test multiple possible solution paths before giving a hint

Because the engine already has typed events, explicit state, graph structure, and specialized agent roles, it can evolve from a guided cognitive runtime into a more autonomous educational reasoning system without changing its core architecture.

### 3. Problem Intelligence And Structure-Oriented Solving

This is the layer that converts a raw word problem into a structured object the rest of the system can reason over.

Inside [`cognitive_engine/app/problem_intelligence/pipeline.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/problem_intelligence/pipeline.py), the engine:

- Extracts entities, numbers, variables, goals, and constraints
- Detects concepts from the text
- Enumerates valid methods from a method library
- Selects an optimal path
- Builds symbolic equations and WL-style subtrees
- Builds a solution graph that represents valid reasoning flow
- Produces a keyword bank for retrieval and alignment

This matters because the system is not just storing plain text. It creates a problem structure that can be compared, validated, and reused downstream.

### 4. Structure-Oriented RAG

MathMend includes a retrieval pipeline that is closer to structure-aware RAG than plain semantic search.

The indexing side in [`src/indexing_pipeline.py`](/e:/Projects/MathMend-Project-/src/indexing_pipeline.py):

- Reads a dataset of math problems
- Extracts final equations from reasoning text
- Converts them into a symbolic fingerprint
- Generates embeddings for "problem + symbolic fingerprint"
- Stores both metadata and vectors in PostgreSQL with `pgvector`

The retrieval side in [`src/retrieval_pipeline.py`](/e:/Projects/MathMend-Project-/src/retrieval_pipeline.py):

- Processes the query with the same equation-extraction logic
- Builds a symbolic fingerprint for the query
- Retrieves vector-nearest candidates
- Re-ranks them by exact symbolic match before semantic similarity

So the RAG logic is structure-oriented because it uses:

- Semantic retrieval for broad similarity
- Symbolic fingerprints for mathematical equivalence
- Re-ranking so exact structural matches are preferred

This makes the system better for math than a text-only retriever.

### 5. Contests

The contest system gives teachers a way to run olympiad-style timed rounds from the frontend and evaluate them through the backend.

Backend support lives in [`api_server.py`](/e:/Projects/MathMend-Project-/api_server.py):

- `GET /contest/problems`
- `GET /contest/server-time`
- `POST /contest/evaluate`

Frontend contest logic lives in:

- [`math-chatbot-frontend/src/pages/ContestsPage.jsx`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/pages/ContestsPage.jsx)
- [`math-chatbot-frontend/src/services/contestData.js`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/services/contestData.js)

How contests work:

1. Teachers load the olympiad problem bank from `olympiad.xlsx`.
2. They choose problems and create a timed public or private contest.
3. Private contests notify invited students through Firebase.
4. Students join when the contest becomes live.
5. Submissions are evaluated on the server.
6. Leaderboards, ratings, contest history, and streak signals are updated.

This is not just a static quiz page. It is a contest workflow with scheduling, participant visibility, server-time anchoring, persistence, evaluation, and leaderboard logic.

### 6. Adaptive Quiz

The adaptive quiz system is exposed from [`api_server.py`](/e:/Projects/MathMend-Project-/api_server.py) through:

- `POST /quiz/start`
- `POST /quiz/answer`
- `GET /quiz/stats`

The backend uses the quiz modules in [`adaptive_quiz.py`](/e:/Projects/MathMend-Project-/adaptive_quiz.py), including:

- `QuestionBank`
- `ThompsonBandit`
- `PracticeForum`

What it does:

- Starts a quiz session with a selected batch size
- Adapts question selection by topic
- Grades answers
- Updates mastery statistics
- Sends results into the frontend analytics layer

The student experience is implemented in [`math-chatbot-frontend/src/pages/QuizPage.jsx`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/pages/QuizPage.jsx), and teacher-side assignment/analytics support is in [`math-chatbot-frontend/src/pages/TeacherDashboardPage.jsx`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/pages/TeacherDashboardPage.jsx).

### 7. Main Tutoring API

The primary application backend is [`api_server.py`](/e:/Projects/MathMend-Project-/api_server.py). It handles:

- `/chat` for math tutoring with Ollama/Qwen-style local LLM routing
- `/ocr` for answer extraction from uploaded work
- `/quiz/*` for adaptive practice
- `/contest/*` for olympiad contest evaluation
- `/health` for service status

The chat system uses a structured tutoring prompt so the model explains variables, equations, and solutions in a predictable format.

### 8. Frontend Product Surface

The frontend in [`math-chatbot-frontend/src/App.jsx`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/App.jsx) brings everything together with protected routes for:

- Landing and login
- Student dashboard
- Teacher dashboard
- Chatbot
- Profile
- Quiz
- Contests
- Streak tracking
- Thinking setup
- Thinking session
- Thinking report

Important UI pages:

- [`math-chatbot-frontend/src/pages/ChatbotPage.jsx`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/pages/ChatbotPage.jsx)
- [`math-chatbot-frontend/src/pages/QuizPage.jsx`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/pages/QuizPage.jsx)
- [`math-chatbot-frontend/src/pages/ContestsPage.jsx`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/pages/ContestsPage.jsx)
- [`math-chatbot-frontend/src/pages/ThinkingSessionPage.jsx`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/pages/ThinkingSessionPage.jsx)
- [`math-chatbot-frontend/src/pages/ThinkingReportPage.jsx`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/pages/ThinkingReportPage.jsx)
- [`math-chatbot-frontend/src/pages/TeacherDashboardPage.jsx`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/pages/TeacherDashboardPage.jsx)

## Architecture Summary

### Backend 1: Main API

File:

- [`api_server.py`](/e:/Projects/MathMend-Project-/api_server.py)

Responsibilities:

- Chat tutoring
- OCR
- Adaptive quiz
- Contest problem bank and evaluation

Default port:

- `8000`

### Backend 2: Cognitive Engine

Entry point:

- [`cognitive_engine/app/main.py`](/e:/Projects/MathMend-Project-/cognitive_engine/app/main.py)

Responsibilities:

- Problem structuring
- Audio chunk processing
- Reasoning alignment
- Live interventions
- Reports and answer validation

Recommended frontend port target:

- `8001`

### Frontend

Path:

- [`math-chatbot-frontend`](/e:/Projects/MathMend-Project-/math-chatbot-frontend)

Responsibilities:

- Student and teacher UI
- Firebase auth and Firestore persistence
- Contest and classroom workflows
- Live thinking-session interface

## Tech Stack

- FastAPI
- React + Vite
- Firebase Auth + Firestore
- Ollama-backed local LLM access
- Deepgram for transcription
- Gemini/OpenAI/Grok optional integrations in the cognitive engine
- SymPy
- PostgreSQL + `pgvector`
- Sentence Transformers
- scikit-learn + XGBoost for predictive analytics

## Important Data And Models

- Contest bank: [`olympiad.xlsx`](/e:/Projects/MathMend-Project-/olympiad.xlsx)
- Predictive models:
  - [`data_models/regression_model.pkl`](/e:/Projects/MathMend-Project-/data_models/regression_model.pkl)
  - [`data_models/classification_model.pkl`](/e:/Projects/MathMend-Project-/data_models/classification_model.pkl)
- Retrieval dataset:
  - [`data/dataset.csv`](/e:/Projects/MathMend-Project-/data/dataset.csv)
  - [`data/raw/word_problems.csv`](/e:/Projects/MathMend-Project-/data/raw/word_problems.csv)

## Environment Configuration

The root env template is in [`.env.example`](/e:/Projects/MathMend-Project-/.env.example).

Important groups:

- Deepgram settings for audio transcription
- Ollama settings for local model access
- Gemini/OpenAI/Grok settings for optional cognitive-engine enhancements
- Predictive analytics model paths

Frontend API base URLs are configured in [`math-chatbot-frontend/src/config/api.js`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/src/config/api.js):

- `VITE_API_BASE_URL`, default `http://localhost:8000`
- `VITE_COGNITIVE_API_BASE_URL`, default `http://127.0.0.1:8001`

Firebase is initialized in [`math-chatbot-frontend/firebase.js`](/e:/Projects/MathMend-Project-/math-chatbot-frontend/firebase.js).

## How To Run

### 1. Install Python dependencies

Main backend:

```powershell
pip install -r requirements.txt
```

Cognitive engine:

```powershell
pip install -r cognitive_engine\requirements.txt
```

### 2. Start the main API

```powershell
python api_server.py
```

This serves the main API on `http://localhost:8000`.

### 3. Start the cognitive engine

```powershell
python -m uvicorn cognitive_engine.app.main:app --host 127.0.0.1 --port 8001 --reload
```

### 4. Start the frontend

```powershell
cd math-chatbot-frontend
npm install
npm run dev
```

### 5. Open the app

Frontend default:

- `http://localhost:5173`

Main API health:

- `http://localhost:8000/health`

Cognitive engine health:

- `http://127.0.0.1:8001/health`

## Selected API Surface

Main API:

- `POST /chat`
- `POST /ocr`
- `POST /quiz/start`
- `POST /quiz/answer`
- `GET /quiz/stats`
- `GET /contest/problems`
- `GET /contest/server-time`
- `POST /contest/evaluate`

Cognitive engine:

- `POST /start_session`
- `POST /stream_audio_chunk`
- `POST /intervention_event`
- `POST /end_session`
- `POST /generate_report`
- `POST /validate_answer`
- `POST /start_tutoring_session`
- `POST /tutoring_chat`
- `WS /ws/session/{session_id}`

## Why This Project Is Different

MathMend is not only a chatbot and not only a quiz app.

It combines:

- tutoring
- adaptive assessment
- contest infrastructure
- symbolic and semantic retrieval
- graph-aware reasoning validation
- live cognitive-session analysis

That combination is the real project outcome: a math learning platform that tries to understand both the answer and the path taken to reach it.

## Project Structure

```text
MathMend-Project-/
|-- api_server.py
|-- adaptive_quiz.py
|-- cognitive_engine/
|   |-- app/
|   |   |-- main.py
|   |   |-- orchestrator.py
|   |   |-- context_engine.py
|   |   |-- problem_intelligence/
|   |   `-- strategy_validation/
|-- math-chatbot-frontend/
|   `-- src/
|       |-- pages/
|       |-- components/
|       `-- services/
|-- src/
|   |-- indexing_pipeline.py
|   `-- retrieval_pipeline.py
|-- data_models/
|-- data/
`-- olympiad.xlsx
```

## Final Summary

This repository now represents a complete MathMend platform:

- The Cognitive Engine handles live reasoning analysis and report generation.
- The contest system supports timed olympiad-style competition and rating updates.
- The structure-oriented RAG pipeline retrieves problems by both semantic similarity and mathematical structure.
- The quiz layer supports adaptive practice and mastery tracking.
- The frontend ties all of it into a student-and-teacher learning product.
