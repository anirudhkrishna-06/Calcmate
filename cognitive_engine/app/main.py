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
    StartSessionRequest,
    StreamAudioChunkRequest,
)
from .orchestrator import orchestrator
from .ws_manager import ws_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("cognitive_engine.main")

app = FastAPI(
    title="TCMTE Cognitive Engine",
    version="0.6.0-phase6",
    description="Phase 6 cognitive runtime with problem structuring, method graph generation, symbolic representation, contextual cognition, and live session orchestration.",
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
    return {"status": "ok", "phase": "phase_6_problem_structuring_engine"}


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
def generate_report(payload: GenerateReportRequest):
    try:
        return orchestrator.generate_report(payload.session_id)
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
