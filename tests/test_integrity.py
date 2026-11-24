"""Bundled data files match their pinned sha256 and are refused when modified."""

from __future__ import annotations

import hashlib
import json

import pytest

import indic_shift
from indic_shift import _registry, _tokenizer


def test_sha256_pins():
    for name, (_, digest, _) in _registry.TOKENIZERS.items():
        assert hashlib.sha256(indic_shift.data_path(name).read_bytes()).hexdigest() == digest
    assert hashlib.sha256(indic_shift.data_path("transform").read_bytes()).hexdigest() == _registry.TRANSFORM[1]


def test_tampered_file_is_refused(monkeypatch):
    name, (fname, _digest, size) = next(iter(_registry.TOKENIZERS.items()))
    monkeypatch.setitem(_registry.TOKENIZERS, name, (fname, "0" * 64, size))
    with pytest.raises(indic_shift.IntegrityError):
        _tokenizer._read_verified(fname, "0" * 64)


def test_transform_table_metadata():
    data = json.loads(indic_shift.data_path("transform").read_text(encoding="utf-8"))
    assert data["format"] == "indic-shift-transform"
    assert data["spec_version"] == 1
    assert data["unicode_version"] == "15.0.0"
    assert [f["name"] for f in data["families"]] == ["digit", "indic", "kana", "arabic_variant"]
    assert len(data["leading_space"]["nospace_ranges"]) == 21


def test_vocab_sizes(tok262, tok131):
    assert (tok262.vocab_size, tok131.vocab_size) == (262_144, 131_072)
    assert indic_shift.available() == ["indic-shift-131k", "indic-shift-262k"]
