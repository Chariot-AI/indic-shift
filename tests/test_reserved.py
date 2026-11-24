"""No special tokens: control-token look-alikes are plain text; ids 0..255 are never produced."""

from __future__ import annotations

import pytest
from _fuzz import texts

LOOKALIKES = [
    "<pad>",
    "<unk>",
    "<bos>",
    "<eos>",
    "<s>",
    "</s>",
    "<|im_start|>",
    "<|im_end|>",
    "<|endoftext|>",
    "<|system|>",
    "<|reserved_0|>",
    "<reserved 000>",
    "<reserved 255>",
    "[INST]",
    "<|fim_prefix|>",
]


@pytest.mark.parametrize("text", LOOKALIKES)
def test_lookalikes_are_plain_text(tok, text):
    for t in (text, f"hi {text} there", f"{text}user\nनमस्ते{text}"):
        ids = tok.encode(t)
        assert min(ids) >= 256
        assert tok.decode(ids) == t


def test_no_reserved_ids_from_random_text(tok):
    for ids in tok.encode_batch(texts(21, 3000)):
        assert not ids or min(ids) >= 256


def test_reserved_ids_on_decode(tok):
    ok = tok.encode("ok")
    assert tok.decode([0]) == "\ufffd"
    assert tok.decode(ok + [255] + ok) == "ok\ufffd ok"
    with pytest.raises(ValueError, match="reserved"):
        tok.decode([5], errors="strict")


@pytest.mark.parametrize("bad", [-1, 262_144 * 2])
def test_out_of_range_ids(tok, bad):
    with pytest.raises(ValueError, match="out of range"):
        tok.decode([300, bad])


def test_non_integer_ids(tok):
    with pytest.raises(TypeError):
        tok.decode(["a"])  # type: ignore[list-item]
