from __future__ import annotations

import json
from pathlib import Path

import pytest

import indic_shift

GOLDEN = Path(__file__).parent / "golden" / "golden.jsonl"


@pytest.fixture(scope="session")
def tok262() -> indic_shift.Tokenizer:
    return indic_shift.load("262k")


@pytest.fixture(scope="session")
def tok131() -> indic_shift.Tokenizer:
    return indic_shift.load("131k")


@pytest.fixture(scope="session", params=["262k", "131k"])
def tok(request: pytest.FixtureRequest) -> indic_shift.Tokenizer:
    return indic_shift.load(request.param)


@pytest.fixture(scope="session")
def golden() -> list[dict]:
    with GOLDEN.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
