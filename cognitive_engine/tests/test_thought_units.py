from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cognitive_engine.app.contracts import TranscriptSegment
from cognitive_engine.app.sentence_segmenter import merge_segments_into_thought_units


def test_merges_fragments_into_thought_unit() -> None:
    segments = [
        TranscriptSegment(segment_id="s1", transcript="On looking at", start=0.0, end=0.5, confidence=0.8, words=[]),
        TranscriptSegment(segment_id="s2", transcript="um the values given", start=0.55, end=1.2, confidence=0.8, words=[]),
        TranscriptSegment(segment_id="s3", transcript="2000", start=1.25, end=1.5, confidence=0.9, words=[]),
    ]

    merged = merge_segments_into_thought_units(segments)

    assert len(merged) == 1
    assert "2000" in (merged[0].transcript or "")
