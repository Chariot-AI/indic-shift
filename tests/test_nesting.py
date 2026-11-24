"""How the 131K tokenizer relates to the 262K tokenizer.

What holds exactly:
1. Same ids for the first 131,072 entries: every 131K id is the same token (same bytes) in the 262K.
2. The 131K merges are the first 130,560 merges of the 262K; transform, split regex and decoder are shared.
3. Hence any 131K id sequence decodes to the same text with either tokenizer.
4. encode_131k(t) == encode_262k(t) whenever every 262K id of t is below 131,072; otherwise the
   262K encoding uses at least one id >= 131,072 and the two encodings differ.
"""

from __future__ import annotations

import json

from _fuzz import texts

import indic_shift

SMALL = 131_072


def _model(name: str) -> dict:
    with indic_shift.data_path(name).open(encoding="utf-8") as f:
        return json.load(f)


def test_vocab_and_merges_are_prefix():
    big, small = _model("262k"), _model("131k")
    bv, sv = big["model"]["vocab"], small["model"]["vocab"]
    assert len(sv) == SMALL and len(bv) == 2 * SMALL
    assert all(bv[t] == i for t, i in sv.items())
    sm = small["model"]["merges"]
    assert big["model"]["merges"][: len(sm)] == sm
    assert {k: v for k, v in big.items() if k != "model"} == {k: v for k, v in small.items() if k != "model"}


def test_small_ids_decode_identically(tok262, tok131):
    for text in texts(5, 500) + ["আমি বাংলায় কথা বলি।", "हिन्दी"]:
        ids = tok131.encode(text)
        assert tok262.decode(ids) == tok131.decode(ids) == text


def test_encodings_agree_exactly_when_262k_stays_below_131072(tok262, tok131, golden):
    agree = differ = 0
    for text in [g["text"] for g in golden] + texts(6, 1500):
        big, small = tok262.encode(text), tok131.encode(text)
        if not big or max(big) < SMALL:
            assert big == small
            agree += 1
        else:
            assert big != small
            differ += 1
    assert agree and differ
