from __future__ import annotations

from app.script_llm import _looks_too_similar


def test_similarity_detects_verbatim_copy() -> None:
    source = "Team A defeated Team B 3 to 1 in the final and secured the title after a late goal."
    narration = "Team A defeated Team B 3 to 1 in the final and secured the title after a late goal."
    assert _looks_too_similar(narration, source) is True


def test_similarity_allows_clear_paraphrase() -> None:
    source = "Team A defeated Team B 3 to 1 in the final and secured the title after a late goal."
    narration = (
        "In the championship matchup, Team A came out on top with a 3-1 result over Team B, "
        "clinching the crown thanks to a score that came near the end."
    )
    assert _looks_too_similar(narration, source) is False

