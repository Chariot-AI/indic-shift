"""decode(encode(text)) == text for random strings over all of Unicode and the stress pools."""

from __future__ import annotations

import pytest
from _fuzz import texts


@pytest.mark.parametrize("seed", range(4))
def test_roundtrip_fuzz(tok, seed):
    batch = texts(seed, 1500)
    ids_batch = tok.encode_batch(batch)
    for text, ids in zip(batch, ids_batch):
        assert tok.encode(text) == ids
        assert tok.decode(ids) == text, repr(text)
        assert tok.decode(ids, errors="strict") == text
        assert all(256 <= i < tok.vocab_size for i in ids)
    assert tok.decode_batch(ids_batch) == batch


def test_transform_roundtrip_fuzz(tok262):
    tr = tok262.transform
    for text in texts(99, 3000):
        assert tr.decode(tr.encode(text)) == text


@pytest.mark.parametrize(
    "text",
    ["", " ", "\n\n", "\r\n", "x" * 5000, "क्ष" * 2000, "1" * 999, "\ue000" * 50, "\U0010ffff\ufffe\uffff", "\x00"],
)
def test_roundtrip_edges(tok, text):
    assert tok.decode(tok.encode(text)) == text


def test_lone_surrogates_rejected(tok262):
    with pytest.raises((UnicodeEncodeError, ValueError, TypeError)):
        tok262.encode("a\ud800b")
