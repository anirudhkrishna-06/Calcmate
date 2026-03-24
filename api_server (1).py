from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import os
import tempfile
import asyncio
import logging
import time
import uuid
import re
from contextlib import asynccontextmanager
from typing import Optional, Dict, List, Any
from openai import AsyncOpenAI
from adaptive_quiz import QuestionBank, ThompsonBandit, PracticeForum


# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("MathMendAPI")

# ---------------------------------------------------------------
# CONFIG — local Ollama model
# Run first: ollama pull qwen2.5:3b
# ---------------------------------------------------------------
MODEL_NAME = "qwen2.5:3b"

llm_client = AsyncOpenAI(
    api_key="ollama",
    base_url="http://localhost:11434/v1",
)

# ---------------------------------------------------------------
# OCR — lazy import
# ---------------------------------------------------------------
try:
    from hybrid_ocr_monopoly import process_image, get_easyocr_reader
    OCR_AVAILABLE = True
except Exception as exc:
    OCR_AVAILABLE = False
    logger.warning(f"OCR module not available — /ocr endpoint will be disabled. Reason: {exc}")

# ---------------------------------------------------------------
# Quiz — initialize once at module level
# ---------------------------------------------------------------
quiz_sessions: Dict[str, Any] = {}
_question_bank = QuestionBank()
_bandit = ThompsonBandit(_question_bank.all_topics)
_bandit.load_profile("bayes_model.json")   # loads saved progress if it exists
_forum = PracticeForum()

# ---------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------
SYSTEM_PROMPT = """You are MathMend, an expert math tutor and solver.

When given a math problem:
1. Identify all variables and what they represent.
2. Write out the equations that model the problem.
3. Solve the equations step-by-step.
4. State the final answer clearly.

Format your response EXACTLY like this example — no markdown, no bullet points:

A photo is 8 inches by 6 inches. If you enlarge it by a scale factor of 1.5, what are the new dimensions?
The original height is 6 inches. The original width is 8 inches. After enlargement, the height is h inches. After enlargement, the width is w inches.  Scale factor relates old and new heights: h = 6 * 1.5 Scale factor relates old and new widths: w = 8 * 1.5  Output: h = 6 * 1.5 w = 8 * 1.5  Solution: h = 9.0, w = 12.0

Key rules:
- Always end with "Solution: variable = value, variable = value"
- Use plain text only, no markdown headers or bullet points
- Keep the explanation concise but complete
- If the problem is simple arithmetic, still show the equation then the answer
"""

# ---------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 MathMend API starting up...")
    if OCR_AVAILABLE:
        try:
            await asyncio.to_thread(get_easyocr_reader)
            logger.info("✅ OCR engine ready.")
        except Exception as e:
            logger.warning(f"⚠️ OCR warmup failed: {e}")
    logger.info("✅ MathMend API ready!")
    yield
    logger.info("🛑 MathMend API shutting down.")

# ---------------------------------------------------------------
# App
# ---------------------------------------------------------------
app = FastAPI(
    title="MathMend API",
    description="Math solver + Adaptive Quiz API",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------
# Pydantic models — Chat
# ---------------------------------------------------------------
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)

class ChatResponse(BaseModel):
    answer: str
    solution: Dict[str, Any] = {}
    reasoning: Optional[str] = None
    equations: List[str] = []
    latency_ms: float
    result_type: str = "llm"

class OCRResponse(BaseModel):
    extracted_text: str
    latency_ms: float

# ---------------------------------------------------------------
# Pydantic models — Quiz
# ---------------------------------------------------------------
class QuizStartRequest(BaseModel):
    batch_size: int = Field(default=5, ge=1, le=20)

class QuizAnswerRequest(BaseModel):
    session_id: str
    question_index: int
    answer: str
    topic: str
    ground_truth: float

class QuizQuestion(BaseModel):
    topic: str
    question: str
    solution: str
    ground_truth: float

class QuizStartResponse(BaseModel):
    session_id: str
    questions: List[QuizQuestion]

class QuizAnswerResponse(BaseModel):
    correct: bool
    solution: str

class TopicStats(BaseModel):
    mean: float
    certainty: float

class QuizStatsResponse(BaseModel):
    topics: Dict[str, TopicStats]

# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
def _parse_solution_from_text(text: str) -> Dict[str, Any]:
    solution = {}
    match = re.search(r"Solution:\s*(.+)", text, re.IGNORECASE)
    if not match:
        return solution
    pairs_str = match.group(1)
    for pair in re.finditer(r"(\w+)\s*=\s*([\d.]+)", pairs_str):
        key = pair.group(1)
        try:
            solution[key] = float(pair.group(2))
        except ValueError:
            solution[key] = pair.group(2)
    return solution

def _parse_equations_from_text(text: str) -> List[str]:
    equations = []
    for line in text.split("\n"):
        line = line.strip()
        if re.search(r"[\w\s]+[+\-*/^][\w\s]+=\s*[\d\w]", line):
            if len(line) < 120:
                equations.append(line)
    return equations[:6]

# ---------------------------------------------------------------
# Routes — General
# ---------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "ocr_available": OCR_AVAILABLE,
    }

# ---------------------------------------------------------------
# Routes — Chat
# ---------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    start_time = time.time()
    question = req.question.strip()
    logger.info(f"Chat request: {question[:80]}...")

    try:
        response = await llm_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": question},
            ],
            temperature=0.2,
            max_tokens=800,
        )
        answer_text = response.choices[0].message.content.strip()
        solution    = _parse_solution_from_text(answer_text)
        equations   = _parse_equations_from_text(answer_text)
        latency     = (time.time() - start_time) * 1000
        logger.info(f"Answered in {latency:.1f}ms | solution keys: {list(solution.keys())}")
        return ChatResponse(
            answer=answer_text,
            solution=solution,
            reasoning=answer_text,
            equations=equations,
            latency_ms=latency,
            result_type="llm",
        )
    except Exception as e:
        logger.error(f"LLM call failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")

# ---------------------------------------------------------------
# Routes — OCR
# ---------------------------------------------------------------
@app.post("/ocr", response_model=OCRResponse)
async def ocr_endpoint(image: UploadFile = File(...)):
    if not OCR_AVAILABLE:
        raise HTTPException(status_code=503, detail="OCR module not available on this server.")
    if not image:
        raise HTTPException(status_code=400, detail="No image provided")

    start_time = time.time()
    suffix = os.path.splitext(image.filename or "upload.png")[1] or ".png"
    tmp_path = ""

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await image.read()
            tmp.write(content)
            tmp_path = tmp.name
        extracted_text = await asyncio.to_thread(process_image, tmp_path)
        latency = (time.time() - start_time) * 1000
        logger.info(f"OCR completed in {latency:.1f}ms")
        return OCRResponse(extracted_text=extracted_text, latency_ms=latency)
    except Exception as e:
        logger.error(f"OCR error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR error: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

# ---------------------------------------------------------------
# Routes — Quiz
# ---------------------------------------------------------------
@app.post("/quiz/start", response_model=QuizStartResponse)
async def quiz_start(req: QuizStartRequest):
    topics = _bandit.select_topics(k=req.batch_size)
    questions_out = []
    raw_questions = []

    for topic in topics:
        q_data = _question_bank.get_question(topic)
        if not q_data:
            continue
        questions_out.append(QuizQuestion(
            topic=topic,
            question=q_data["q"],
            solution=q_data["solution_text"],
            ground_truth=float(q_data["ground_truth_numeric"]),
        ))
        raw_questions.append(q_data)

    session_id = str(uuid.uuid4())
    quiz_sessions[session_id] = {
        "topics": topics,
        "raw_questions": raw_questions,
    }
    logger.info(f"Quiz session started: {session_id} | {len(questions_out)} questions")
    return QuizStartResponse(session_id=session_id, questions=questions_out)


@app.post("/quiz/answer", response_model=QuizAnswerResponse)
async def quiz_answer(req: QuizAnswerRequest):
    if req.session_id not in quiz_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = quiz_sessions[req.session_id]
    is_correct = await asyncio.to_thread(
        _forum.grade_submission,
        req.answer,
        req.ground_truth,
    )
    _bandit.update(req.topic, is_correct)

    idx = req.question_index
    raw_questions = session.get("raw_questions", [])
    solution_text = (
        raw_questions[idx]["solution_text"]
        if idx < len(raw_questions)
        else "See solution above."
    )
    logger.info(f"Answer graded | correct={is_correct} | topic={req.topic}")
    return QuizAnswerResponse(correct=is_correct, solution=solution_text)


@app.get("/quiz/stats", response_model=QuizStatsResponse)
async def quiz_stats():
    result = {}
    for topic in _question_bank.all_topics:
        mean, certainty = _bandit.get_stats(topic)
        result[topic] = TopicStats(mean=mean, certainty=certainty)
    return QuizStatsResponse(topics=result)


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
