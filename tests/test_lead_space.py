"""The leading-space rule, checked on every code point (frozen Unicode 15.0 table)."""

from __future__ import annotations

import json
import unicodedata

import pytest

import indic_shift

NO_SPACE_EXAMPLES = [
    "日本語",
    "ภาษาไทย",
    "ພາສາລາວ",
    "ភាសាខ្មែរ",
    "ひらがな",
    "カタカナ",
    "1250000",
    '{"a": 1}',
    "\nx",
    "\tx",
    "\u00a0x",
    "😀",
    "(x)",
    "",
    "々",
    "\U00020000",
]
SPACE_EXAMPLES = [
    "Hello",
    " Hello",
    "  ",
    "hello world",
    "မြန်မာ",
    "한국어",
    "தமிழ்",
    "नमस्ते",
    "سلام",
    "Ωμέγα",
    "\u0301x",
    "\U00011f04",
    "ꯃꯅꯤꯄꯨꯔ",
    "ᱥᱟᱱᱛᱟᱲᱤ",
]


@pytest.fixture(scope="module")
def table():
    with indic_shift.data_path("transform").open(encoding="utf-8") as f:
        return json.load(f)["leading_space"]


@pytest.mark.parametrize("text", SPACE_EXAMPLES)
def test_space_added(tok262, text):
    assert tok262.transform.leading_space(text)
    assert tok262.transform.encode(text).startswith(" ")
    assert tok262.decode(tok262.encode(text)) == text


@pytest.mark.parametrize("text", NO_SPACE_EXAMPLES)
def test_no_space_added(tok262, text):
    assert not tok262.transform.leading_space(text)
    assert not tok262.transform.encode(text).startswith(" ")
    assert tok262.decode(tok262.encode(text)) == text


def test_rule_on_every_code_point(tok262, table):
    def cp(s: str) -> int:
        return int(s[2:], 16)

    lm = [(cp(a), cp(b)) for a, b in table["letter_mark_ranges"]]
    nospace = [(cp(a), cp(b)) for a, b, _ in table["nospace_ranges"]]
    is_lm = bytearray(0x110000)
    for a, b in lm:
        is_lm[a : b + 1] = b"\x01" * (b - a + 1)
    blocked = bytearray(0x110000)
    for a, b in nospace:
        blocked[a : b + 1] = b"\x01" * (b - a + 1)
    tr = tok262.transform
    check_unicodedata = unicodedata.unidata_version == "15.0.0"
    for c in range(0x110000):
        if 0xD800 <= c <= 0xDFFF:
            continue
        ch = chr(c)
        expected = c == 0x20 or (is_lm[c] == 1 and blocked[c] == 0)
        assert tr.leading_space(ch) == expected, hex(c)
        if check_unicodedata:
            assert (unicodedata.category(ch)[0] in "LM") == bool(is_lm[c]), hex(c)
        wire = tr.encode(ch)
        assert wire.startswith(" ") == expected
        assert tr.decode(wire) == ch


def test_every_code_point_through_bpe(tok):
    cps = [c for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF]
    texts = [chr(c) for c in cps]
    for text, ids in zip(texts, tok.encode_batch(texts)):
        assert tok.decode(ids) == text


def test_each_run_gets_its_own_space(tok262):
    a, b = "नमस्ते", " दुनिया"
    whole = tok262.encode(a + b)
    parts = tok262.encode(a) + tok262.encode(b)
    assert whole != parts  # the second run gets its own leading space
    assert tok262.decode(whole) == a + b
    assert tok262.decode(tok262.encode(a)) + tok262.decode(tok262.encode(b)) == a + b
