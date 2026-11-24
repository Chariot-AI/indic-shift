"""StreamDecoder output equals decode() for every way of feeding the ids."""

from __future__ import annotations

import random

import pytest
from _fuzz import texts

import indic_shift

SAMPLES = [
    "আমি বাংলায় কথা বলি।",
    "தமிழ் மொழி",
    "नमस्ते दुनिया",
    "We counted 682 birds",
    "\ue000\uf8ffx",
    "ꯈꯣꯡꯉꯨꯞ ᱥᱟᱱᱛᱟᱲᱤ",
    "سأل آپ کیسے ہیں؟",
    "",
    " ",
    "👨\u200d👩\u200d👧 ३.१४",
]


def stream(tok, ids, chunks=None):
    dec = tok.stream_decoder()
    if chunks is None:
        return "".join(dec.step(i) for i in ids) + dec.flush()
    out, pos = [], 0
    for n in chunks:
        out.append(dec.feed(ids[pos : pos + n]))
        pos += n
    out.append(dec.feed(ids[pos:]))
    return "".join(out) + dec.flush()


@pytest.mark.parametrize("text", SAMPLES)
def test_stream_equals_decode(tok, text):
    ids = tok.encode(text)
    assert stream(tok, ids) == tok.decode(ids) == text


def test_stream_every_prefix(tok262):
    text = "আমি বাংলায় কথা বলি। தமிழ் 682 \ue000"
    ids = tok262.encode(text)
    for k in range(len(ids) + 1):
        dec = tok262.stream_decoder()
        head = "".join(dec.step(i) for i in ids[:k])
        rest = "".join(dec.step(i) for i in ids[k:]) + dec.flush()
        assert head + rest == text
        assert tok262.decode(ids[:k]).startswith(head)


def test_stream_random_chunks(tok):
    rng = random.Random(7)
    for text in texts(3, 400):
        ids = tok.encode(text)
        chunks = [rng.randint(0, 4) for _ in range(len(ids))]
        assert stream(tok, ids, chunks) == text


def test_stream_garbage_matches_decode(tok):
    rng = random.Random(11)
    for _ in range(300):
        ids = [rng.randrange(256, tok.vocab_size) for _ in range(rng.randint(1, 10))]
        assert stream(tok, ids) == tok.decode(ids)


def test_slices_do_not_join_but_stream_does(tok262):
    """Decoding is stateful: separately decoded halves are wrong, the stream decoder is right."""
    text = "আমি বাংলায় কথা বলি"
    ids = tok262.encode(text)
    half = len(ids) // 2
    assert tok262.decode(ids[:half]) + tok262.decode(ids[half:]) != text
    assert stream(tok262, ids) == text


def test_flush_resets_for_next_run(tok262):
    dec = tok262.stream_decoder()
    first = tok262.encode("তুমি")
    second = tok262.encode("नमस्ते")
    a = dec.feed(first) + dec.flush()
    b = dec.feed(second) + dec.flush()
    assert (a, b) == ("তুমি", "नमस्ते")


def test_reset_discards_state(tok262):
    dec = tok262.stream_decoder()
    dec.feed(tok262.encode("তুমি")[:1])
    dec.reset()
    assert dec.feed(tok262.encode("नमस्ते")) + dec.flush() == "नमस्ते"


def test_strict_stream_raises_on_truncated_character(tok262):
    ids = tok262.encode("\ue000")  # escape sequence spread over several tokens
    dec = indic_shift.StreamDecoder(tok262, errors="strict")
    dec.feed(ids[:-1])
    with pytest.raises(ValueError):
        dec.flush()
