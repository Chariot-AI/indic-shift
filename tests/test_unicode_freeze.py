"""Ids do not depend on the Python version: no runtime use of unicodedata, frozen Unicode 15.0 tables."""

from __future__ import annotations

from pathlib import Path

import indic_shift

PKG = Path(indic_shift.__file__).parent


def test_package_never_imports_unicodedata():
    for path in PKG.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "import unicodedata" not in source and "from unicodedata" not in source, path


def test_characters_newer_than_unicode_15(tok262):
    tr = tok262.transform
    # Unicode 15.0 letters get a leading space on every Python (3.10 has Unicode 13.0) ...
    assert tr.leading_space("\U00011f04")  # KAWI LETTER A (15.0)
    assert tr.leading_space("\U0001e4d0")  # NAG MUNDARI LETTER O (15.0)
    # ... and code points assigned after 15.0 do not (3.14 has Unicode 16.0).
    assert not tr.leading_space("\U00010d4a")  # GARAY (16.0)
    assert not tr.leading_space("\U0001e5d0")  # OL ONAL (16.0)
    for text in ["\U00011f04\U00011f05", "\U00010d4a\U00010d4b", "\U0001e5d0 x"]:
        assert tok262.decode(tok262.encode(text)) == text


def test_regex_engine_unicode_classes(tok262):
    """tokenizers >= 0.22 evaluates the split regex with Unicode 16.0 classes (the reference)."""
    split = tok262._bpe.pre_tokenizer.pre_tokenize_str
    for ch in ("\U00011f04", "\U0001e030", "\U00010d4a", "\U0001e5d0"):
        assert len(split("ab" + ch + "cd")) == 1, hex(ord(ch))
