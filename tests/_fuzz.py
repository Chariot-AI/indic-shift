"""Seeded random strings that stress the transform (shared by several tests)."""

from __future__ import annotations

import random


def _r(a: int, b: int) -> list[str]:
    return [chr(c) for c in range(a, b)]


POOLS = [
    _r(0x0900, 0x0D80),  # Devanagari .. Malayalam
    _r(0x0D80, 0x0E00),  # Sinhala
    _r(0xA8E0, 0xA900) + _r(0x11FC0, 0x12000),
    _r(0xAAE0, 0xAB00) + _r(0xABC0, 0xAC00),  # Meetei Mayek
    _r(0x1C50, 0x1C80),  # Ol Chiki
    _r(0x0600, 0x0700) + _r(0x0750, 0x0780) + _r(0x0870, 0x0900),  # Arabic
    _r(0x3040, 0x3100) + _r(0x1B000, 0x1B170),  # kana
    _r(0x30, 0x3A) + ["०", "০", "௦", "٠", "۰", "\U0001d7ce"],
    _r(0xE000, 0xE012) + _r(0xE020, 0xE080) + _r(0xE100, 0xE3E0) + ["\uf8ff", "\U000f0000"],
    [" ", "  ", "\t", "\n", "\r", "\u00a0", "\u200c", "\u200d", "\u3000", "।", "॥", ".", "?"],
    list("abcXYZ_-+=*/\\()[]{}<>|'\",.;:@#$%^&~`"),
    ["<pad>", "<|im_start|>", "<|im_end|>", "<reserved 001>", "<unk>", "</s>"],
    _r(0x0300, 0x0370),
    ["😀", "👍🏽", "👨\u200d👩\u200d👧", "🇮🇳", "₹"],
    ["\U00011f04", "\U0001e4d0", "\U00011380", "\U0001e5d0", "\U00010d4a", "\U0002ebf0"],
]


def texts(seed: int, n: int) -> list[str]:
    rng = random.Random(seed)
    out = []
    for i in range(n):
        if i % 5 == 0:
            cps = [rng.randrange(0x110000) for _ in range(rng.randint(1, 12))]
            out.append("".join(chr(c) if not 0xD800 <= c <= 0xDFFF else "x" for c in cps))
            continue
        pools = rng.sample(POOLS, k=rng.randint(1, 4))
        k = rng.choice([1, 2, 3, 5, 8, 20, 60])
        out.append("".join(rng.choice(rng.choice(pools)) for _ in range(k)))
    return out
