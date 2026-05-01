"""Lock in the post-Phase-4 doc identity."""

from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

FORBIDDEN_IN_CURRENT_DOCS = [
    "SpacetimeDB",
    "manuslocal",
    "LocalManus",
    "relay-room",
    "swarm_delegator",
    "Pipeline-Stages",
]

CURRENT_DOC_PATHS = [
    REPO / "README.md",
    REPO / "docs" / "ARCHITECTURE.md",
]

REQUIRED_PRESENT_IN_README = [
    "safe-mini",
    "control-plane",
]


def test_no_legacy_terms_in_current_docs():
    for path in CURRENT_DOC_PATHS:
        text = path.read_text(encoding="utf-8")
        for term in FORBIDDEN_IN_CURRENT_DOCS:
            assert term not in text, f"{path.name} still contains legacy term '{term}'"


def test_required_terms_present_in_readme():
    text = (REPO / "README.md").read_text(encoding="utf-8")
    for term in REQUIRED_PRESENT_IN_README:
        assert term in text, f"README.md missing required term '{term}'"
