"""Deterministic checks on the reference data behind the agent's tools.

`agent/tools.py` is the agent's ground truth: whatever a tool returns is
relayed to the user as fact, and the agent has no way to validate it. These
checks pin the two values that have drifted before - LangGraph's minimum
Python and the canonical documentation domain - so a stale edit fails CI
instead of reaching users.

The response-level counterparts are `version_accuracy_evaluator` and
`citation_hygiene_evaluator` in `evals/evaluators.py`; those grade an answer,
these grade the data it is grounded in.

Runs standalone, and is collected by pytest if it is installed:

    python evals/test_reference_data.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.tools import (  # noqa: E402
    CONCEPTS_DB,
    SAFE_PATTERNS,
    get_security_advice,
    lookup_concept,
)

# Ground truth for the version floors the tools advertise.
MINIMUM_PYTHON = {
    "langchain": "3.10+",
    "langgraph": "3.10+",
    "langsmith": "3.9+",
    "deep agents": "3.10+",
}

CANONICAL_DOMAIN = "docs.langchain.com"
LEGACY_DOMAINS = ("python.langchain.com", "js.langchain.com")
# Wording that frames a legacy domain as a redirect or a warning rather than a
# recommendation. Mirrors the cue list in `citation_hygiene_evaluator`.
LEGACY_CUES = (
    "legacy",
    "stale",
    "outdated",
    "deprecated",
    "redirect",
    "superseded",
    "no longer",
    "instead of",
    "not canonical",
)


def test_concepts_db_minimum_python_matches_ground_truth() -> None:
    for concept, expected in MINIMUM_PYTHON.items():
        actual = CONCEPTS_DB[concept]["min_python"]
        assert actual == expected, (
            f"CONCEPTS_DB['{concept}']['min_python'] is {actual!r}, expected {expected!r}"
        )


def test_lookup_concept_reports_langgraph_minimum_python() -> None:
    rendered = lookup_concept.invoke({"concept_name": "LangGraph"})
    assert "Minimum Python: 3.10+" in rendered, rendered
    for stale in ("3.6", "3.7", "3.8", "3.9"):
        assert stale not in rendered, f"lookup_concept('LangGraph') still reports {stale}"


def test_lookup_concept_agrees_with_installation_guide() -> None:
    # `get_setup_guide("installation")` states 3.10 for langchain/langgraph. Two
    # tools disagreeing lets the answer depend on which one the agent picks.
    for concept in ("langchain", "langgraph"):
        assert "3.10" in lookup_concept.invoke({"concept_name": concept})


def test_security_advice_names_canonical_documentation_domain() -> None:
    advice = get_security_advice.invoke({"query": "documentation conventions"})
    assert CANONICAL_DOMAIN in advice, advice


def test_security_advice_does_not_recommend_legacy_domains() -> None:
    advice = get_security_advice.invoke({"query": "documentation conventions"})
    recommended = []
    for domain in LEGACY_DOMAINS:
        for sentence in re.split(r"(?<=[.!?\n])\s+|\n", advice):
            lowered = sentence.lower()
            if domain in lowered and not any(cue in lowered for cue in LEGACY_CUES):
                recommended.append(domain)
                break
    assert not recommended, (
        f"get_security_advice recommends legacy domain(s): {', '.join(recommended)}"
    )


def test_safe_patterns_do_not_call_legacy_domains_canonical() -> None:
    for pattern in SAFE_PATTERNS:
        lowered = pattern.lower()
        if "canonical" in lowered:
            assert CANONICAL_DOMAIN in lowered, pattern
            for domain in LEGACY_DOMAINS:
                if domain in lowered:
                    assert any(cue in lowered for cue in LEGACY_CUES), pattern


def main() -> int:
    checks = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    failures = 0
    for check in checks:
        try:
            check()
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {check.__name__}: {exc}")
        else:
            print(f"ok   {check.__name__}")
    print(f"\n{len(checks) - failures}/{len(checks)} reference-data checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
