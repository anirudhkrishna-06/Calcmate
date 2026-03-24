"""Answer Validator — Phase 9.

Validates student answers via:
  1. Tesseract OCR for extracting text from uploaded images
  2. Gemini2 for computing the expected answer from the problem text
  3. Numeric comparison with tolerance
"""

from __future__ import annotations

import io
import logging
import re

import httpx
from PIL import Image

from .config import get_settings

logger = logging.getLogger("cognitive_engine.answer_validator")


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from an image using Tesseract OCR."""
    try:
        import pytesseract
    except ImportError:
        logger.error("pytesseract is not installed")
        return ""

    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image).strip()
        logger.info("OCR extraction complete | length=%d", len(text))
        return text
    except Exception as exc:
        logger.exception("OCR extraction failed | error=%s", exc)
        return ""


def extract_numbers(text: str) -> list[float]:
    """Extract all numeric values from text."""
    pattern = r"[-+]?\d*\.?\d+"
    matches = re.findall(pattern, text)
    return [float(m) for m in matches]


async def compute_expected_answer(problem_text: str) -> dict:
    """Call Gemini2 to solve the problem and extract the expected answer.

    Returns { "answer": <str>, "numeric": <float|None>, "explanation": <str> }
    """
    settings = get_settings()
    api_key = settings.gemini2.api_key
    if not api_key:
        logger.warning("GEMINI2_API_KEY not set — cannot compute expected answer")
        return {"answer": "", "numeric": None, "explanation": "API key not configured"}

    model = settings.gemini2.model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    prompt = (
        f"Solve this math problem step by step and give the final numeric answer. "
        f"At the very end, write EXACTLY: FINAL_ANSWER: <number>\n\n"
        f"Problem: {problem_text}"
    )

    try:
        async with httpx.AsyncClient(timeout=settings.gemini2.timeout_seconds) as client:
            response = await client.post(
                url,
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
                },
            )
            response.raise_for_status()
            data = response.json()

        answer_text = ""
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        for part in parts:
            answer_text += part.get("text", "")

        # Extract FINAL_ANSWER
        match = re.search(r"FINAL_ANSWER:\s*([-+]?\d*\.?\d+)", answer_text)
        numeric_answer = float(match.group(1)) if match else None

        if numeric_answer is None:
            # Fallback: try to get the last number in the response
            numbers = extract_numbers(answer_text)
            numeric_answer = numbers[-1] if numbers else None

        logger.info("Expected answer computed | answer=%s", numeric_answer)
        return {
            "answer": str(numeric_answer) if numeric_answer is not None else answer_text.strip()[-100:],
            "numeric": numeric_answer,
            "explanation": answer_text.strip()[:500],
        }

    except Exception as exc:
        logger.exception("Gemini2 answer computation failed | error=%s", exc)
        return {"answer": "", "numeric": None, "explanation": f"Error: {exc}"}


def compare_answers(
    extracted_text: str,
    expected: dict,
    tolerance: float = 0.01,
) -> dict:
    """Compare extracted answer with expected answer.

    Returns { "correct": bool, "extracted_answer": str, "expected_answer": str, "method": str }
    """
    expected_numeric = expected.get("numeric")
    extracted_numbers = extract_numbers(extracted_text)

    # Numeric comparison
    if expected_numeric is not None and extracted_numbers:
        for extracted_num in extracted_numbers:
            if abs(extracted_num - expected_numeric) <= tolerance * max(abs(expected_numeric), 1.0):
                return {
                    "correct": True,
                    "extracted_answer": str(extracted_num),
                    "expected_answer": str(expected_numeric),
                    "method": "numeric_tolerance",
                }
        # Check the closest one
        closest = min(extracted_numbers, key=lambda x: abs(x - expected_numeric))
        return {
            "correct": False,
            "extracted_answer": str(closest),
            "expected_answer": str(expected_numeric),
            "method": "numeric_tolerance",
        }

    # String comparison fallback
    expected_str = str(expected.get("answer", "")).strip().lower()
    extracted_str = extracted_text.strip().lower()

    return {
        "correct": expected_str in extracted_str or extracted_str in expected_str,
        "extracted_answer": extracted_text.strip()[:100],
        "expected_answer": expected.get("answer", ""),
        "method": "string_match",
    }


async def validate_answer(
    image_bytes: bytes,
    problem_text: str,
    tolerance: float = 0.01,
) -> dict:
    """Full validation pipeline: OCR → Gemini solve → compare.

    Returns { "correct": bool, "extracted_answer": str, "expected_answer": str,
              "ocr_text": str, "explanation": str }
    """
    # Step 1: OCR
    ocr_text = extract_text_from_image(image_bytes)
    if not ocr_text:
        return {
            "correct": False,
            "extracted_answer": "",
            "expected_answer": "",
            "ocr_text": "",
            "explanation": "No text could be extracted from the image.",
        }

    # Step 2: Compute expected answer
    expected = await compute_expected_answer(problem_text)

    # Step 3: Compare
    result = compare_answers(ocr_text, expected, tolerance)

    return {
        **result,
        "ocr_text": ocr_text,
        "explanation": expected.get("explanation", ""),
    }
