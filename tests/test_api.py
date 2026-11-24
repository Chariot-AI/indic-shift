"""Public API surface."""

from __future__ import annotations

import json

import pytest

import indic_shift
from indic_shift.__main__ import main


@pytest.mark.parametrize("name", ["262k", "262K", "indic-shift-262k", "INDIC-SHIFT-262K"])
def test_load_aliases(name):
    tok = indic_shift.load(name)
    assert tok.name == "indic-shift-262k"
    assert tok is indic_shift.load("indic-shift-262k")


def test_load_default_and_unknown():
    assert indic_shift.load().name == "indic-shift-262k"
    with pytest.raises(ValueError, match="unknown tokenizer"):
        indic_shift.load("64k")


def test_data_paths_exist():
    for name in ("262k", "131k", "transform"):
        assert indic_shift.data_path(name).is_file()


def test_basic_api(tok262):
    text = "भारत एक विशाल देश है। আমি বাংলায় কথা বলি।"
    ids = tok262.encode(text)
    assert isinstance(ids, list) and all(isinstance(i, int) for i in ids)
    assert tok262.decode(ids) == text
    assert tok262.count(text) == len(ids)
    assert tok262.encode_batch([text, ""]) == [ids, []]
    assert tok262.decode_batch([ids, []]) == [text, ""]
    assert tok262.decode(iter(ids)) == text
    assert "indic-shift-262k" in repr(tok262)
    with pytest.raises(ValueError):
        tok262.decode(ids, errors="ignore")


def test_reference_examples(tok262):
    assert tok262.encode("नमस्ते दुनिया") == [182427, 15851]
    assert tok262.encode("नमस्ते") + tok262.encode(" दुनिया") == [182427, 476, 15851]
    assert len(tok262.encode("আমি বাংলায় কথা বলি")) == 4
    assert len(tok262.encode("We counted 682 birds")) == 4


def test_describe(tok262):
    labels = tok262.transform.describe("আমি 12")
    assert labels[0] == " " and labels[1] == "<indic:Beng>"
    assert "<digit:1>" in labels and "<digit:2>" in labels
    assert tok262.transform.describe("\ue000") == ["<escape:U+E000>"]


def test_cli(capsys):
    assert main(["encode", "नमस्ते दुनिया"]) == 0
    ids = json.loads(capsys.readouterr().out)
    assert ids == [182427, 15851]
    assert main(["decode", "182427", "15851"]) == 0
    assert capsys.readouterr().out == "नमस्ते दुनिया\n"
    assert main(["-t", "131k", "inspect", "নমস্কার"]) == 0
    assert "indic-shift-131k" in capsys.readouterr().out
