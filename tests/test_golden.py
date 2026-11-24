"""Exact ids for hand-written texts in every scheduled language, English, code and edge cases."""

from __future__ import annotations

import hashlib
import json

# sha256 over the JSON id lists, one line per text (also quoted in SPEC.md for ports)
DIGESTS = {
    "262k": "1a1a430b7881d274bc74b647dfd2297da8b487ba35bf100c4fafe2f962afcdac",
    "131k": "0663b5af8ff16aa3ef644386f8f92ca13e6809dcef4c4a0c3fa0f5a41311db73",
}


def test_golden_ids(tok, golden):
    size = tok.name.rsplit("-", 1)[1]
    wrong = [g["text"] for g in golden if tok.encode(g["text"]) != g[f"ids_{size}"]]
    assert not wrong, wrong[:5]


def test_golden_batch(tok, golden):
    size = tok.name.rsplit("-", 1)[1]
    assert tok.encode_batch([g["text"] for g in golden]) == [g[f"ids_{size}"] for g in golden]


def test_golden_decode(tok, golden):
    size = tok.name.rsplit("-", 1)[1]
    for g in golden:
        assert tok.decode(g[f"ids_{size}"]) == g["text"]
        assert tok.decode(g[f"ids_{size}"], errors="strict") == g["text"]


def test_golden_digest(golden):
    for size, expected in DIGESTS.items():
        h = hashlib.sha256()
        for g in golden:
            h.update((json.dumps(g[f"ids_{size}"]) + "\n").encode())
        assert h.hexdigest() == expected


def test_golden_covers_languages(golden):
    langs = {g["lang"] for g in golden}
    scheduled = {
        "asm_Beng",
        "ben_Beng",
        "brx_Deva",
        "doi_Deva",
        "guj_Gujr",
        "hin_Deva",
        "kan_Knda",
        "kas_Arab",
        "gom_Deva",
        "mai_Deva",
        "mal_Mlym",
        "mni_Mtei",
        "mar_Deva",
        "npi_Deva",
        "ory_Orya",
        "pan_Guru",
        "san_Deva",
        "sat_Olck",
        "snd_Arab",
        "tam_Taml",
        "tel_Telu",
        "urd_Arab",
    }
    assert scheduled <= langs
    assert {"eng_Latn", "code", "edge"} <= langs
