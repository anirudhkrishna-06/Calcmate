"""Answer validator with deterministic math solving and OCR-aware extraction."""

from __future__ import annotations

import io
import json
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

import httpx

from .config import get_settings
from .local_llm import call_ollama

logger = logging.getLogger("cognitive_engine.answer_validator")


def resolve_tesseract_cmd() -> str | None:
    env_candidates = [
        os.getenv("TESSERACT_CMD"),
        os.getenv("TESSERACT_PATH"),
    ]
    for candidate in env_candidates:
        if candidate and Path(candidate).exists():
            return candidate

    which_cmd = shutil.which("tesseract")
    if which_cmd:
        return which_cmd

    windows_candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in windows_candidates:
        if Path(candidate).exists():
            return candidate

    return None


def preprocess_for_ocr(image):
    try:
        from PIL import ImageFilter, ImageOps
    except ImportError:
        return image

    processed = image.convert("L")
    processed = ImageOps.autocontrast(processed)
    processed = processed.filter(ImageFilter.SHARPEN)
    processed = processed.point(lambda pixel: 0 if pixel < 160 else 255, mode="1")
    return processed


def extract_text_from_image(image_bytes: bytes) -> str:
    try:
        from PIL import Image
    except ImportError:
        Image = None

    tesseract_cmd = resolve_tesseract_cmd()
    if not tesseract_cmd:
        logger.error("Tesseract executable was not found. Set TESSERACT_CMD or install Tesseract on PATH.")
        return ""

    try:
        with tempfile.TemporaryDirectory(prefix="mathmend_ocr_") as temp_dir:
            input_path = Path(temp_dir) / "input.png"
            output_base = Path(temp_dir) / "output"

            if Image is not None:
                try:
                    image = Image.open(io.BytesIO(image_bytes))
                    image = preprocess_for_ocr(image)
                    image.save(input_path)
                except Exception:
                    input_path.write_bytes(image_bytes)
            else:
                input_path.write_bytes(image_bytes)

            subprocess.run(
                [tesseract_cmd, str(input_path), str(output_base), "--oem", "3", "--psm", "6"],
                check=True,
                capture_output=True,
                text=True,
            )
            output_text_path = output_base.with_suffix(".txt")
            text = output_text_path.read_text(encoding="utf-8", errors="ignore").strip() if output_text_path.exists() else ""
            logger.info("OCR extraction complete | length=%d", len(text))
            return text
    except Exception as exc:
        logger.exception("OCR extraction failed | error=%s", exc)
        return ""


def extract_numbers(text: str) -> list[float]:
    return [float(match) for match in re.findall(r"[-+]?\d*\.?\d+", text)]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def simplify_number(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def build_expected(*, answer: str, numeric: float | None = None, numeric_set: list[float] | None = None, explanation: str, symbolic: str | None = None, provider: str = "local") -> dict:
    return {
        "answer": answer,
        "numeric": numeric,
        "numeric_set": numeric_set or [],
        "symbolic": symbolic,
        "explanation": explanation,
        "provider": provider,
    }


def solve_problem_locally(problem_text: str) -> dict | None:
    text = normalize_text(problem_text)

    match = re.search(r"rectangle has length (\d+(?:\.\d+)?) cm and width (\d+(?:\.\d+)?) cm", text)
    if match:
        length = float(match.group(1))
        width = float(match.group(2))
        area = length * width
        return build_expected(
            answer=simplify_number(area),
            numeric=area,
            explanation=f"Rectangle area = {simplify_number(length)} * {simplify_number(width)} = {simplify_number(area)}.",
        )

    match = re.search(r"triangle has base (\d+(?:\.\d+)?) cm and height (\d+(?:\.\d+)?) cm", text)
    if match:
        base = float(match.group(1))
        height = float(match.group(2))
        area = 0.5 * base * height
        return build_expected(
            answer=simplify_number(area),
            numeric=area,
            explanation=f"Triangle area = 1/2 * {simplify_number(base)} * {simplify_number(height)} = {simplify_number(area)}.",
        )

    match = re.search(r"triangle has side lengths (\d+(?:\.\d+)?) cm, (\d+(?:\.\d+)?) cm, and (\d+(?:\.\d+)?) cm", text)
    if match:
        a, b, c = (float(match.group(index)) for index in range(1, 4))
        s = (a + b + c) / 2
        area = math.sqrt(max(s * (s - a) * (s - b) * (s - c), 0.0))
        return build_expected(
            answer=simplify_number(area),
            numeric=area,
            explanation=f"Using Heron's formula gives area {simplify_number(area)}.",
        )

    match = re.search(r"circle has diameter (\d+(?:\.\d+)?) cm", text)
    if match:
        diameter = float(match.group(1))
        radius = diameter / 2
        coeff = radius * radius
        return build_expected(
            answer=f"{simplify_number(coeff)}pi",
            numeric=coeff * math.pi,
            symbolic=f"{simplify_number(coeff)}pi",
            explanation=f"Area = pi * {simplify_number(radius)}^2 = {simplify_number(coeff)}pi.",
        )

    match = re.search(r"solve for x:\s*([+-]?\d+(?:\.\d+)?)x\s*([+-]\s*\d+(?:\.\d+)?)\s*=\s*([+-]?\d+(?:\.\d+)?)", text)
    if match:
        a = float(match.group(1))
        b = float(match.group(2).replace(" ", ""))
        c = float(match.group(3))
        x = (c - b) / a
        return build_expected(
            answer=simplify_number(x),
            numeric=x,
            explanation=f"x = ({simplify_number(c)} - ({simplify_number(b)})) / {simplify_number(a)} = {simplify_number(x)}.",
        )

    match = re.search(r"solve the system of equations:\s*([+-]?\d+)x\s*([+-])\s*y\s*=\s*([+-]?\d+)\s*and\s*x\s*([+-])\s*y\s*=\s*([+-]?\d+)", text)
    if match:
        a = float(match.group(1))
        b = 1.0 if match.group(2) == "+" else -1.0
        c = float(match.group(3))
        d = 1.0
        e = 1.0 if match.group(4) == "+" else -1.0
        f = float(match.group(5))
        determinant = (a * e) - (b * d)
        if determinant != 0:
            x = ((c * e) - (b * f)) / determinant
            y = ((a * f) - (c * d)) / determinant
            return build_expected(
                answer=f"x={simplify_number(x)}, y={simplify_number(y)}",
                numeric_set=[x, y],
                explanation=f"Solving the 2x2 system gives x={simplify_number(x)}, y={simplify_number(y)}.",
            )

    match = re.search(r"quadratic equation x\^2\s*([+-]\s*\d+)x\s*([+-]\s*\d+)\s*=\s*0", text)
    if match:
        b = float(match.group(1).replace(" ", ""))
        c = float(match.group(2).replace(" ", ""))
        discriminant = (b * b) - (4 * c)
        if discriminant >= 0:
            root_disc = math.sqrt(discriminant)
            roots = sorted([(-b - root_disc) / 2, (-b + root_disc) / 2])
            return build_expected(
                answer=", ".join(simplify_number(root) for root in roots),
                numeric_set=roots,
                explanation=f"The roots are {', '.join(simplify_number(root) for root in roots)}.",
            )

    match = re.search(r"what is (\d+(?:\.\d+)?)% of (\d+(?:\.\d+)?)", text)
    if match:
        percent = float(match.group(1))
        total = float(match.group(2))
        value = (percent / 100.0) * total
        return build_expected(answer=simplify_number(value), numeric=value, explanation=f"{simplify_number(percent)}% of {simplify_number(total)} is {simplify_number(value)}.")

    match = re.search(r"ratio of boys to girls.*?(\d+):(\d+).*?(\d+) students.*?how many are girls", text)
    if match:
        boys = float(match.group(1))
        girls = float(match.group(2))
        total = float(match.group(3))
        value = (girls / (boys + girls)) * total
        return build_expected(answer=simplify_number(value), numeric=value, explanation=f"Girls = {simplify_number(girls)}/{simplify_number(boys + girls)} * {simplify_number(total)} = {simplify_number(value)}.")

    match = re.search(r"travels (\d+(?:\.\d+)?) km in (\d+(?:\.\d+)?) hours", text)
    if match:
        distance = float(match.group(1))
        time_taken = float(match.group(2))
        speed = distance / time_taken
        return build_expected(answer=simplify_number(speed), numeric=speed, explanation=f"Speed = {simplify_number(distance)} / {simplify_number(time_taken)} = {simplify_number(speed)}.")

    match = re.search(r"contains (\d+) red balls and (\d+) blue balls.*probability of drawing a red ball", text)
    if match:
        red = int(match.group(1))
        blue = int(match.group(2))
        frac = Fraction(red, red + blue)
        numeric = red / (red + blue)
        return build_expected(
            answer=f"{frac.numerator}/{frac.denominator}",
            numeric=numeric,
            symbolic=f"{frac.numerator}/{frac.denominator}",
            explanation=f"Probability = favorable/total = {red}/{red + blue}.",
        )

    match = re.search(r"scores ([\d,\sand]+)\. find the mean score", text)
    if match:
        values = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", match.group(1))]
        if values:
            mean = sum(values) / len(values)
            return build_expected(answer=simplify_number(mean), numeric=mean, explanation=f"Mean = {simplify_number(sum(values))} / {len(values)} = {simplify_number(mean)}.")

    match = re.search(r"simple interest on rs\.?\s*(\d+(?:\.\d+)?) at (\d+(?:\.\d+)?)% per annum for (\d+(?:\.\d+)?) years", text)
    if match:
        principal = float(match.group(1))
        rate = float(match.group(2))
        years = float(match.group(3))
        interest = (principal * rate * years) / 100.0
        return build_expected(answer=simplify_number(interest), numeric=interest, explanation=f"SI = PRT/100 = {simplify_number(interest)}.")

    return None


def extract_candidate_answer(ocr_text: str) -> dict:
    lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
    candidate_lines: list[str] = []

    for line in lines:
        lowered = line.lower()
        if any(token in lowered for token in ["answer", "ans", "final", "="]) and re.search(r"\d", line):
            candidate_lines.append(line)
            continue
        if len(line) <= 24 and re.search(r"\d", line):
            candidate_lines.append(line)
            continue
        if "pi" in lowered and len(line) <= 24:
            candidate_lines.append(line)

    if not candidate_lines and len(extract_numbers(ocr_text)) <= 4:
        candidate_lines = lines[-3:]

    best_text = candidate_lines[-1] if candidate_lines else ""
    if ":" in best_text:
        best_text = best_text.split(":")[-1].strip()
    if "=" in best_text:
        best_text = best_text.split("=")[-1].strip()

    return {
        "text": best_text,
        "numbers": extract_numbers(best_text),
        "all_numbers": extract_numbers(" ".join(candidate_lines)),
        "full_numbers": extract_numbers(ocr_text),
        "contains_pi": "pi" in best_text.lower() or "π" in best_text,
        "candidate_lines": candidate_lines,
    }


def build_gemini_candidates() -> list[tuple[str, str | None, str, float]]:
    settings = get_settings()
    return [
        ("GEMINI3", settings.gemini3.api_key, settings.gemini3.model, settings.gemini3.timeout_seconds),
        ("GEMINI2", settings.gemini2.api_key, settings.gemini2.model, settings.gemini2.timeout_seconds),
    ]


async def call_gemini(prompt: str, *, max_output_tokens: int, temperature: float, response_mime_type: str | None = None) -> tuple[str | None, str | None, str | None]:
    last_error: str | None = None
    for label, api_key, model, timeout_seconds in build_gemini_candidates():
        if not api_key:
            continue
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
            },
        }
        if response_mime_type:
            payload["generationConfig"]["responseMimeType"] = response_mime_type

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
            text = "".join(part.get("text", "") for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []))
            if text.strip():
                return text, label, None
            last_error = f"{label} returned an empty response."
        except httpx.HTTPStatusError as exc:
            last_error = f"{label} HTTP {exc.response.status_code}"
            logger.warning("%s request failed | status=%s", label, exc.response.status_code)
            if exc.response.status_code not in {429, 500, 502, 503, 504}:
                break
        except Exception as exc:
            last_error = f"{label}: {exc}"
            logger.exception("%s request failed | error=%s", label, exc)

    return None, None, last_error


def parse_json_object(raw_text: str) -> dict | None:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw_text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


async def compute_expected_answer(problem_text: str) -> dict:
    local_result = solve_problem_locally(problem_text)
    if local_result is not None:
        logger.info("Expected answer computed locally | answer=%s", local_result.get("answer"))
        return local_result

    prompt = (
        "Solve this math problem carefully. Return valid JSON only with keys "
        "\"final_answer\", \"numeric_answer\", and \"solution_summary\".\n\n"
        f"Problem: {problem_text}"
    )
    answer_text, provider, gemini_error = await call_gemini(
        prompt,
        max_output_tokens=512,
        temperature=0.1,
        response_mime_type="application/json",
    )
    if answer_text:
        parsed = parse_json_object(answer_text)
        if parsed:
            numeric_answer = parsed.get("numeric_answer")
            try:
                numeric_value = float(numeric_answer) if numeric_answer is not None else None
            except (TypeError, ValueError):
                numeric_value = None
            return build_expected(
                answer=str(parsed.get("final_answer", "")).strip(),
                numeric=numeric_value,
                explanation=str(parsed.get("solution_summary", "")).strip()[:500],
                provider=provider or "gemini",
            )
    return build_expected(
        answer="",
        explanation=f"Validation unavailable: {gemini_error or 'no solving provider configured'}",
        provider="unavailable",
    )


async def judge_answer_with_gemini(problem_text: str, ocr_text: str, expected: dict, candidate: dict) -> dict | None:
    prompt = (
        "You are validating a student's math answer from OCR text. Ignore website chrome, menu labels, and unrelated UI text. "
        "Focus only on the student's final submitted answer if present.\n\n"
        "Return valid JSON only with keys: "
        "\"extracted_student_answer\", \"correct\", \"where_wrong\".\n\n"
        f"Problem: {problem_text}\n"
        f"Actual solution answer: {expected.get('answer', '')}\n"
        f"Actual solution summary: {expected.get('explanation', '')}\n"
        f"Best OCR candidate answer: {candidate.get('text', '')}\n"
        f"Candidate OCR lines: {candidate.get('candidate_lines', [])}\n"
        f"Full OCR text: {ocr_text}\n"
    )

    raw_text, ollama_error = await call_ollama(
        prompt,
        temperature=0.0,
        max_tokens=300,
        system_prompt="You are a strict math answer validator. Return strict JSON only.",
    )
    if not raw_text:
        logger.info("LLM answer judgement unavailable | ollama_error=%s", ollama_error)
        return None

    parsed = parse_json_object(raw_text)
    if not parsed:
        return None

    extracted_answer = str(parsed.get("extracted_student_answer", "")).strip()
    where_wrong = str(parsed.get("where_wrong", "")).strip()
    correct_value = parsed.get("correct")
    is_correct = correct_value is True or str(correct_value).strip().lower() == "true"
    return {
        "correct": is_correct,
        "extracted_answer": extracted_answer or candidate.get("text", ""),
        "expected_answer": str(expected.get("answer", "")).strip(),
        "method": "llm_judge_ollama",
        "where_wrong": where_wrong,
    }


def compare_answers(extracted_text: str, expected: dict, tolerance: float = 0.01) -> dict:
    candidate = extract_candidate_answer(extracted_text)
    expected_numeric = expected.get("numeric")
    expected_numeric_set = [float(value) for value in expected.get("numeric_set", [])]
    expected_symbolic = normalize_text(str(expected.get("symbolic", "")))
    expected_answer = str(expected.get("answer", "")).strip()

    if expected_numeric is None and not expected_numeric_set and not expected_answer:
        return {
            "correct": False,
            "extracted_answer": candidate["text"] or extracted_text.strip()[:100],
            "expected_answer": "",
            "method": "validation_unavailable",
        }

    candidate_numbers = candidate["numbers"] or candidate["all_numbers"]
    if not candidate_numbers and len(candidate["full_numbers"]) <= 4:
        candidate_numbers = candidate["full_numbers"]

    if expected_numeric is not None:
        if not candidate_numbers:
            return {
                "correct": False,
                "extracted_answer": candidate["text"] or extracted_text.strip()[:100],
                "expected_answer": simplify_number(expected_numeric),
                "method": "numeric_missing",
            }
        closest = min(candidate_numbers, key=lambda value: abs(value - expected_numeric))
        is_correct = abs(closest - expected_numeric) <= tolerance * max(abs(expected_numeric), 1.0)
        return {
            "correct": is_correct,
            "extracted_answer": simplify_number(closest),
            "expected_answer": simplify_number(expected_numeric),
            "method": "numeric_tolerance",
        }

    if expected_numeric_set:
        rounded_expected = sorted(round(value, 4) for value in expected_numeric_set)
        rounded_actual = sorted(round(value, 4) for value in candidate_numbers)
        is_correct = len(rounded_actual) >= len(rounded_expected) and rounded_actual[: len(rounded_expected)] == rounded_expected
        return {
            "correct": is_correct,
            "extracted_answer": ", ".join(simplify_number(value) for value in candidate_numbers[: len(rounded_expected)]) or candidate["text"],
            "expected_answer": ", ".join(simplify_number(value) for value in expected_numeric_set),
            "method": "numeric_set",
        }

    normalized_candidate = normalize_text(candidate["text"] or extracted_text)
    if expected_symbolic:
        compact_expected = expected_symbolic.replace(" ", "")
        compact_candidate = normalized_candidate.replace(" ", "")
        symbolic_match = compact_expected in compact_candidate
        if "pi" in compact_expected and candidate_numbers:
            leading_number = simplify_number(candidate_numbers[0])
            symbolic_match = symbolic_match or compact_expected == f"{leading_number}pi"
        return {
            "correct": symbolic_match,
            "extracted_answer": candidate["text"] or extracted_text.strip()[:100],
            "expected_answer": expected_answer,
            "method": "symbolic_match",
        }

    return {
        "correct": expected_answer.lower() == normalized_candidate,
        "extracted_answer": candidate["text"] or extracted_text.strip()[:100],
        "expected_answer": expected_answer,
        "method": "string_match",
    }


async def validate_answer(image_bytes: bytes, problem_text: str, tolerance: float = 0.01) -> dict:
    ocr_text = extract_text_from_image(image_bytes)
    if not ocr_text:
        return {
            "correct": False,
            "extracted_answer": "",
            "expected_answer": "",
            "ocr_text": "",
            "explanation": "OCR could not run because Tesseract is missing, or no text could be extracted from the image.",
        }

    expected = await compute_expected_answer(problem_text)
    candidate = extract_candidate_answer(ocr_text)
    result = await judge_answer_with_gemini(problem_text, ocr_text, expected, candidate)
    if result is None:
        result = compare_answers(ocr_text, expected, tolerance)
    explanation = expected.get("explanation", "")
    provider = expected.get("provider")
    if provider:
        explanation = f"[{provider}] {explanation}".strip()
    if result.get("where_wrong"):
        explanation = f"{explanation}\nWhere wrong: {result['where_wrong']}".strip()

    return {
        **result,
        "ocr_text": ocr_text,
        "explanation": explanation,
    }
