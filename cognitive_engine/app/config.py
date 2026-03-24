from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


class DeepgramSettings(BaseModel):
    api_key: str | None = None
    base_url: str = "https://api.deepgram.com/v1/listen"
    model: str = "nova-3"
    language: str = "en"
    smart_format: bool = True
    punctuate: bool = True
    utterances: bool = True
    filler_words: bool = True
    diarize: bool = False
    keywords: list[str] = Field(default_factory=list)
    use_keywords: bool = False
    store_audio_locally: bool = False
    audio_storage_dir: Path = ROOT_DIR / "cognitive_engine" / "data" / "audio"
    request_timeout_seconds: float = 15.0


class LLMRefinementSettings(BaseModel):
    enabled: bool = False
    api_key: str | None = None
    base_url: str = "https://api.openai.com/v1/responses"
    model: str = "gpt-5"
    timeout_seconds: float = 0.8
    confidence_threshold: float = 0.6
    ambiguity_threshold: float = 0.55
    window_size: int = 3


class GeminiSettings(BaseModel):
    enabled: bool = False
    api_key: str | None = None
    model: str = "gemini-2.0-flash"
    base_url_template: str = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    timeout_seconds: float = 1.4
    graph_enhancement_enabled: bool = False
    graph_enhancement_timeout_seconds: float = 8.0


class Gemini2Settings(BaseModel):
    api_key: str | None = None
    model: str = "gemini-2.0-flash"
    timeout_seconds: float = 10.0


class Gemini3Settings(BaseModel):
    api_key: str | None = None
    model: str = "gemini-2.0-flash"
    timeout_seconds: float = 10.0


class OllamaSettings(BaseModel):
    enabled: bool = False
    base_url: str = "http://localhost:11434/v1"
    model: str = "qwen2.5:7b"
    timeout_seconds: float = 20.0


class PredictiveAnalyticsSettings(BaseModel):
    enabled: bool = True
    models_dir: Path = ROOT_DIR / "data_models"
    regression_model_filename: str = "regression_model.pkl"
    classification_model_filename: str = "classification_model.pkl"
    early_chunk_count: int = 5


class EngineSettings(BaseModel):
    deepgram: DeepgramSettings
    llm: LLMRefinementSettings
    gemini: GeminiSettings
    gemini2: Gemini2Settings
    gemini3: Gemini3Settings
    ollama: OllamaSettings
    predictive_analytics: PredictiveAnalyticsSettings


@lru_cache(maxsize=1)
def get_settings() -> EngineSettings:
    raw_keywords = os.getenv("DEEPGRAM_KEYWORDS", "")
    keywords = [keyword.strip() for keyword in raw_keywords.split(",") if keyword.strip()]

    deepgram = DeepgramSettings(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        base_url=os.getenv("DEEPGRAM_LISTEN_URL", "https://api.deepgram.com/v1/listen"),
        model=os.getenv("DEEPGRAM_MODEL", "nova-3"),
        language=os.getenv("DEEPGRAM_LANGUAGE", "en"),
        smart_format=os.getenv("DEEPGRAM_SMART_FORMAT", "true").lower() == "true",
        punctuate=os.getenv("DEEPGRAM_PUNCTUATE", "true").lower() == "true",
        utterances=os.getenv("DEEPGRAM_UTTERANCES", "true").lower() == "true",
        filler_words=os.getenv("DEEPGRAM_FILLER_WORDS", "true").lower() == "true",
        diarize=os.getenv("DEEPGRAM_DIARIZE", "false").lower() == "true",
        keywords=keywords,
        use_keywords=os.getenv("DEEPGRAM_USE_KEYWORDS", "false").lower() == "true",
        store_audio_locally=os.getenv("COGNITIVE_STORE_AUDIO", "false").lower() == "true",
        request_timeout_seconds=float(os.getenv("DEEPGRAM_TIMEOUT_SECONDS", "15")),
    )
    llm = LLMRefinementSettings(
        enabled=os.getenv("LLM_REFINEMENT_ENABLED", "false").lower() == "true",
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses"),
        model=os.getenv("LLM_REFINEMENT_MODEL", "gpt-5"),
        timeout_seconds=float(os.getenv("LLM_REFINEMENT_TIMEOUT_SECONDS", "0.8")),
        confidence_threshold=float(os.getenv("LLM_REFINEMENT_CONFIDENCE_THRESHOLD", "0.6")),
        ambiguity_threshold=float(os.getenv("LLM_REFINEMENT_AMBIGUITY_THRESHOLD", "0.55")),
        window_size=int(os.getenv("LLM_REFINEMENT_WINDOW_SIZE", "3")),
    )
    gemini = GeminiSettings(
        enabled=os.getenv("GEMINI_PARSER_ENABLED", "false").lower() == "true",
        api_key=os.getenv("GEMINI_API_KEY"),
        model=os.getenv("GEMINI_PARSER_MODEL", "gemini-2.0-flash"),
        timeout_seconds=float(os.getenv("GEMINI_PARSER_TIMEOUT_SECONDS", "1.4")),
        graph_enhancement_enabled=os.getenv("GEMINI_GRAPH_ENHANCEMENT_ENABLED", "false").lower() == "true",
        graph_enhancement_timeout_seconds=float(os.getenv("GEMINI_GRAPH_ENHANCEMENT_TIMEOUT_SECONDS", "8.0")),
    )
    gemini2 = Gemini2Settings(
        api_key=os.getenv("GEMINI2_API_KEY"),
        model=os.getenv("GEMINI2_MODEL", "gemini-2.0-flash"),
        timeout_seconds=float(os.getenv("GEMINI2_TIMEOUT_SECONDS", "10.0")),
    )
    gemini3 = Gemini3Settings(
        api_key=os.getenv("GEMINI3_API_KEY"),
        model=os.getenv("GEMINI3_MODEL", os.getenv("GEMINI2_MODEL", "gemini-2.0-flash")),
        timeout_seconds=float(os.getenv("GEMINI3_TIMEOUT_SECONDS", "10.0")),
    )
    ollama = OllamaSettings(
        enabled=os.getenv("OLLAMA_ENABLED", "true").lower() == "true",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        model=os.getenv("OLLAMA_MODEL", "qwen3.5:397b-cloud"),
        timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20.0")),
    )
    predictive_analytics = PredictiveAnalyticsSettings(
        enabled=os.getenv("PREDICTIVE_ANALYTICS_ENABLED", "true").lower() == "true",
        models_dir=Path(os.getenv("PREDICTIVE_MODELS_DIR", str(ROOT_DIR / "data_models"))),
        regression_model_filename=os.getenv(
            "PREDICTIVE_REGRESSION_MODEL_FILENAME",
            "regression_model.pkl",
        ),
        classification_model_filename=os.getenv(
            "PREDICTIVE_CLASSIFICATION_MODEL_FILENAME",
            "classification_model.pkl",
        ),
        early_chunk_count=int(os.getenv("PREDICTIVE_EARLY_CHUNK_COUNT", "5")),
    )

    return EngineSettings(
        deepgram=deepgram,
        llm=llm,
        gemini=gemini,
        gemini2=gemini2,
        gemini3=gemini3,
        ollama=ollama,
        predictive_analytics=predictive_analytics,
    )
