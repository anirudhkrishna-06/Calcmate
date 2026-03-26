from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cognitive_engine.app.deepgram_client import DeepgramTranscriptionClient


def test_nova3_uses_keyterm_parameter() -> None:
    client = DeepgramTranscriptionClient()
    client.settings.model = "nova-3"

    assert client._keyword_param_name() == "keyterm"


def test_legacy_models_keep_keywords_parameter() -> None:
    client = DeepgramTranscriptionClient()
    client.settings.model = "enhanced"

    assert client._keyword_param_name() == "keywords"
