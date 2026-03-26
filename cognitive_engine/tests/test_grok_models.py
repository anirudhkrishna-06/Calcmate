from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cognitive_engine.app.agents import ReportGeneratorAgent


def test_grok_model_candidates_normalize_old_model_name() -> None:
    agent = ReportGeneratorAgent()

    candidates = agent._grok_model_candidates("grok-4.20-reasoning")

    assert candidates[0] == "grok-4-1-fast-reasoning"
    assert "grok-4" in candidates
