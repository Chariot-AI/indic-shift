"""transformers integration (skipped when transformers is not installed)."""

from __future__ import annotations

import pytest

transformers = pytest.importorskip("transformers")

from indic_shift.hf import IndicShiftTokenizer  # noqa: E402

TEXTS = ["नमस्ते दुनिया", "আমি বাংলায় কথা বলি।", "Hello, world", "سلام", ""]


@pytest.fixture(scope="module")
def hf():
    return IndicShiftTokenizer.from_name("262k")


def test_same_ids(hf, tok262):
    for text in TEXTS:
        assert hf(text)["input_ids"] == tok262.encode(text)
        assert hf.decode(tok262.encode(text)) == text
    batch = hf(TEXTS)
    assert batch["input_ids"] == tok262.encode_batch(TEXTS)
    assert hf.batch_decode(batch["input_ids"]) == TEXTS


def test_vocab(hf, tok262):
    assert hf.vocab_size == tok262.vocab_size
    assert len(hf) == tok262.vocab_size
    assert hf.all_special_ids == []


def test_added_special_tokens_split_runs(tok262):
    hf = IndicShiftTokenizer.from_name("262k")
    hf.add_special_tokens({"additional_special_tokens": ["<|user|>", "<|end|>"]})
    user, end = hf.convert_tokens_to_ids(["<|user|>", "<|end|>"])
    assert user == tok262.vocab_size and end == tok262.vocab_size + 1
    ids = hf("<|user|>নমস্কার<|end|>")["input_ids"]
    assert ids == [user, *tok262.encode("নমস্কার"), end]
    assert hf.decode(ids) == "<|user|>নমস্কার<|end|>"
    assert hf.decode(ids, skip_special_tokens=True) == "নমস্কার"
    assert len(hf) == tok262.vocab_size + 2


def test_save_and_reload(tmp_path, hf):
    hf.save_pretrained(tmp_path)
    again = IndicShiftTokenizer.from_pretrained(tmp_path)
    assert again.indic_shift.name == "indic-shift-262k"
    assert again("নমস্কার")["input_ids"] == hf("নমস্কার")["input_ids"]
    small = IndicShiftTokenizer.from_name("131k")
    small.save_pretrained(tmp_path / "small")
    assert IndicShiftTokenizer.from_pretrained(tmp_path / "small").vocab_size == 131_072
