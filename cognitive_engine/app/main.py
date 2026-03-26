from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect

from .contracts import (
    EndSessionRequest,
    GenerateReportRequest,
    InterventionEventRequest,
    InterventionEventResponse,
    StartTutoringSessionRequest,
    StartTutoringSessionResponse,
    StartSessionRequest,
    StreamAudioChunkRequest,
    ValidateAnswerRequest,
    ValidateAnswerResponse,
    TutoringChatRequest,
    TutoringChatResponse,
)
from .orchestrator import orchestrator
from .report_tutoring import tutoring_service
from .ws_manager import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("cognitive_engine.main")

app = FastAPI(
    title="TCMTE Cognitive Engine",
    version="0.9.0-phase9",
    description="Phase 9 cognitive runtime with enhanced interventions, answer validation, and Gemini-powered reports.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok", "phase": "phase_7a_strategy_validation_engine"}


@app.post("/start_session")
async def start_session(payload: StartSessionRequest):
    response = await orchestrator.start_session(payload)
    logger.info("Session started | session=%s", response.session_id)
    return response


@app.post("/stream_audio_chunk")
async def stream_audio_chunk(payload: StreamAudioChunkRequest):
    try:
        response = await orchestrator.stream_audio_chunk(payload)
        logger.info(
            "Chunk processed | session=%s chunk=%s intent=%s confidence=%.2f phase=%s intervention=%s transcript=%s",
            response.session_id,
            response.chunk_id,
            response.detected_intent.value,
            response.confidence,
            response.current_phase.value,
            response.intervention_recommended,
            response.transcript_excerpt if response.transcript_excerpt else "<none>",
        )
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/intervention_event")
async def intervention_event(payload: InterventionEventRequest):
    try:
        _, count = await orchestrator.manual_intervention(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    logger.info("Manual intervention logged | session=%s intervention=%s count=%s", payload.session_id, payload.intervention_id, count)
    return InterventionEventResponse(
        session_id=payload.session_id,
        intervention_id=payload.intervention_id,
        logged=True,
        intervention_count=count,
    )


@app.post("/end_session")
async def end_session(payload: EndSessionRequest):
    try:
        response = await orchestrator.end_session(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    logger.info("Session ended | session=%s chunks=%s interventions=%s lifecycle=%s", response.session_id, response.total_chunks, response.total_interventions, response.lifecycle_state.value)
    return response


@app.post("/generate_report")
async def generate_report(payload: GenerateReportRequest):
    try:
        return await orchestrator.generate_report(payload.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/validate_answer")
async def validate_answer(payload: ValidateAnswerRequest):
    import base64
    from .answer_validator import validate_answer as run_validation
    from .session_store import store as _store

    state = _store.get(payload.session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        raw_image_b64 = payload.image_b64 or ""
        normalized_image_b64 = raw_image_b64.split(",", 1)[1] if "," in raw_image_b64 else raw_image_b64
        image_bytes = base64.b64decode(normalized_image_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data.")

    logger.info(
        "Validate answer request received | session=%s image_b64_length=%d image_bytes=%d",
        payload.session_id,
        len(payload.image_b64 or ""),
        len(image_bytes),
    )

    problem_text = state.problem_payload.raw_text if state.problem_payload else ""
    if not problem_text:
        raise HTTPException(status_code=400, detail="No problem text available for this session.")

    result = await run_validation(image_bytes, problem_text, session_id=payload.session_id)
    async with _store.get_lock(payload.session_id):
        refreshed_state = _store.get(payload.session_id)
        if refreshed_state is not None:
            refreshed_state.answer_result = result
            refreshed_state.cached_report = None
            _store.save(refreshed_state)
    logger.info(
        "Answer validated | session=%s correct=%s extracted=%s expected=%s",
        payload.session_id, result.get("correct"), result.get("extracted_answer"), result.get("expected_answer"),
    )
    return ValidateAnswerResponse(
        session_id=payload.session_id,
        correct=result.get("correct", False),
        extracted_answer=result.get("extracted_answer", ""),
        expected_answer=result.get("expected_answer", ""),
        ocr_text=result.get("ocr_text", ""),
        explanation=result.get("explanation", ""),
    )


@app.post("/start_tutoring_session", response_model=StartTutoringSessionResponse)
async def start_tutoring_session(payload: StartTutoringSessionRequest):
    logger.info(
        "Tutoring session request received | report_keys=%s",
        ",".join(sorted((payload.report or {}).keys())) if isinstance(payload.report, dict) else "<invalid>",
    )
    response = await tutoring_service.start_session(payload.report)
    logger.info(
        "Tutoring session started | tutoring_session_id=%s available=%s",
        response.tutoring_session_id,
        response.available,
    )
    return response


@app.post("/tutoring_chat", response_model=TutoringChatResponse)
async def tutoring_chat(payload: TutoringChatRequest):
    try:
        logger.info(
            "Tutoring chat request received | tutoring_session_id=%s chars=%d",
            payload.tutoring_session_id,
            len(payload.message),
        )
        response = await tutoring_service.send_message(payload.tutoring_session_id, payload.message)
        logger.info(
            "Tutoring chat responded | tutoring_session_id=%s completed=%s understanding_status=%s",
            payload.tutoring_session_id,
            response.completed,
            response.understanding_status,
        )
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.websocket("/ws/session/{session_id}")
async def session_socket(websocket: WebSocket, session_id: str) -> None:
    await ws_manager.connect(session_id, websocket)
    logger.info("WebSocket connected | session=%s", session_id)
    await orchestrator.send_snapshot(session_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)
        logger.info("WebSocket disconnected | session=%s", session_id)


# Phase 7A debug endpoint
@app.get("/session/{session_id}/validation_state")
def get_validation_state(session_id: str):
    from .session_store import store as _store
    state = _store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "session_id": session_id,
        "validation_state": state.validation_state.model_dump(mode="json"),
        "cognitive_path": {
            "node_count": len(state.cognitive_path.nodes),
            "on_graph": state.cognitive_path.on_graph_count(),
            "off_graph": state.cognitive_path.off_graph_count(),
            "labels": state.cognitive_path.node_labels()[-10:],
        },
        "solution_graph_summary": {
            "node_count": len(state.solution_graph.nodes) if state.solution_graph else 0,
            "optimal_paths": len(state.solution_graph.optimal_paths) if state.solution_graph else 0,
            "alternative_paths": len(state.solution_graph.alternative_paths) if state.solution_graph else 0,
        } if state.solution_graph else None,
    }
