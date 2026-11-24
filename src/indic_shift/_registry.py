"""Packaged data files and their sha256 (do not edit)."""

from __future__ import annotations

TRANSFORM = ("transform.json", "59175effab865dc3e9b20c1c1ab530c7d1c72ebc57d4da997c2b4eb162cbaf6c")

# name -> (file, sha256, vocabulary size)
TOKENIZERS: dict[str, tuple[str, str, int]] = {
    "indic-shift-262k": (
        "indic-shift-262k.tokenizer.json",
        "d075a93f2cd1654d7938502136550f429ea2647f54dcd4895331dec75c3582bf",
        262144,
    ),
    "indic-shift-131k": (
        "indic-shift-131k.tokenizer.json",
        "4cd92628f979558311ced0f72b4bbb3f6a18974f4cd761403db6d64fa5566a7c",
        131072,
    ),
}

# ids below this value are reserved slots: never produced by encode(), rejected by decode()
FIRST_TOKEN_ID = 256
