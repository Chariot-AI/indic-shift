"""Adversarial inputs for exactness checks: edge-case strings and id sequences.

``texts(seed, n_random)`` returns hand-written edge cases plus seeded random mixtures drawn from
character pools that stress the transform (every Brahmic script, digits of every digit set,
joiners, private-use code points including the wire alphabet itself, control-token look-alikes,
whitespace, combining marks, kana, Arabic composites, emoji sequences, recently assigned code points).
``id_sequences(...)`` returns id sequences that no text encodes to (random ids, slices of valid
encodings) for decode comparisons.
"""

from __future__ import annotations

import random

EDGE = [
    "",
    " ",
    "  ",
    "\t",
    "\n",
    "\r\n",
    " \n ",
    "\u00a0",
    "\u3000",
    "x",
    " x",
    "  x",
    "x ",
    "Hello",
    " Hello",
    "hello world",
    "日本語",
    " 日本語",
    "ภาษาไทย",
    "ພາສາລາວ",
    "ភាសាខ្មែរ",
    "မြန်မာ",
    "한국어",
    "தமிழ்",
    '{"a": 1}',
    "\nx",
    "1250000",
    "We counted 682 birds",
    "Rs 1,25,682 only",
    "x = foo(a, 027)",
    "३.१४ ৩.১৪ ௩.௧௪ ٣٫١٤ ۳٫۱۴",
    "০১২৩৪৫৬৭৮৯ ੦੧੨੩ ૦૧૨૩ ୦୧୨୩ ౦౧౨౩ ೦೧೨೩ ൦൧൨൩ ෦෧෨෩ ꯰꯱꯲ ᱐᱑᱒",
    "আমি যাই। তুমি",
    "नमस्ते। आप कैसे हैं॥ ठीक",
    "।।॥ ।",
    "। আমি",
    "ক্ষ ক্\u200dষ ক্\u200cষ",  # ZWJ / ZWNJ inside a conjunct
    "\u200d\u200c",
    "\u200dক",
    "क\u200d",
    "ꯃꯅꯤꯄꯨꯔ ꯈꯣꯡꯉꯨꯞ ꯂꯣꯟ",
    "ᱥᱟᱱᱛᱟᱲᱤ ᱑᱒ ᱚᱞ ᱪᱤᱠᱤ",
    "ᱥᱟᱱᱛᱟᱲᱤ தமிழ் ᱥᱟ",
    "سأل إسلام آخر مؤمن شيئ ۂ ۓ ۀ",
    "سأل",  # decomposed hamza stays decomposed
    "ٱلْعَرَبِيَّة",
    "اردو زبان بہت پیاری ہے۔",
    "کشمیری ژ ۆ",
    "ひらがな カタカナ ｶﾀｶﾅ ㇰ 𛀁",
    "\ue000",
    "\ue000\ue001\ue002",
    "\ue024\ue025\ue026\ue027",
    "\ue100\ue3d5\ue3d6\uf8ff",
    "\U000f0000\U0010fffd",
    "\ufffe\uffff\U0010ffff\ufeff",
    "\x00\x01\x7f\x85",
    "<pad>",
    "<unk><bos><eos>",
    "<|im_start|>user\nनमस्ते<|im_end|>",
    "<|endoftext|>",
    "<reserved 000>",
    "<reserved 255><reserved 256>",
    "<s></s>[INST][/INST]",
    "👍🏽 👨\u200d👩\u200d👧\u200d👦 🇮🇳",
    "\u0301x",
    "\u0901़",
    "\U00011f04\U00011f05 \U0001e4d0\U0001e4d1 \U00011380\U00011381 \U0001e5d0\U0001e5d1",
    "ab\U00011f04cd \U00010d4a1",
    "a" * 1000,
    "क" * 500,
    "1" * 100,
    "१२३४५६७८९०" * 10,
]

_POOLS = [
    [chr(c) for c in range(0x0900, 0x0D80)],  # Brahmic blocks
    [chr(c) for c in range(0x0D80, 0x0E00)],  # Sinhala
    [chr(c) for c in range(0xA8E0, 0xA900)] + [chr(c) for c in range(0x11FC0, 0x12000)],
    [chr(c) for c in range(0xAAE0, 0xAB00)] + [chr(c) for c in range(0xABC0, 0xAC00)],  # Meetei
    [chr(c) for c in range(0x1C50, 0x1C80)],  # Ol Chiki
    [chr(c) for c in range(0x0600, 0x0700)] + [chr(c) for c in range(0x0750, 0x0780)],
    [chr(c) for c in range(0x0870, 0x0900)],
    [chr(c) for c in range(0x3040, 0x3100)] + [chr(c) for c in range(0x1B000, 0x1B170)],
    [chr(c) for c in range(0x30, 0x3A)] + [chr(c) for c in (0x0966, 0x09E6, 0x0BE6, 0x0660, 0x06F0, 0x1D7CE)],
    [chr(c) for c in range(0xE000, 0xE012)] + [chr(c) for c in range(0xE020, 0xE080)],
    [chr(c) for c in range(0xE100, 0xE3E0)] + ["\uf8ff", "\uf000", "\U000f0000"],
    [" ", "  ", "\t", "\n", "\r", "\u00a0", "\u200c", "\u200d", "\u3000", "।", "॥", ".", "?", "!"],
    list("abcdefXYZ_-+=*/\\()[]{}<>|'\",.;:@#$%^&~`"),
    ["<pad>", "<|im_start|>", "<|im_end|>", "<reserved 001>", "<unk>", "</s>"],
    [chr(c) for c in range(0x0300, 0x0370)] + ["\u093c", "\u094d", "\u0bcd"],
    ["😀", "👍🏽", "👨\u200d👩\u200d👧", "🇮🇳", "₹", "€"],
    [chr(c) for c in (0x11F04, 0x1E4D0, 0x11380, 0x1E5D0, 0x10D4A, 0x2EBF0, 0x16FE2, 0x1AFF0)],
]


def random_text(rng: random.Random) -> str:
    n = rng.choice([1, 1, 2, 3, 5, 8, 13, 40, 120])
    pools = rng.sample(_POOLS, k=rng.randint(1, 4))
    return "".join(rng.choice(rng.choice(pools)) for _ in range(n))


def random_code_point_text(rng: random.Random) -> str:
    out = []
    for _ in range(rng.randint(1, 20)):
        cp = rng.randrange(0x110000)
        if 0xD800 <= cp <= 0xDFFF:
            cp = 0xFFFD
        out.append(chr(cp))
    return "".join(out)


def texts(seed: int = 0, n_random: int = 20000) -> list[str]:
    rng = random.Random(seed)
    out = list(EDGE)
    for i in range(n_random):
        out.append(random_text(rng) if i % 4 else random_code_point_text(rng))
    return out


def id_sequences(
    encodings: list[list[int]], vocab_size: int, first_id: int, seed: int = 0, n_random: int = 5000
) -> list[list[int]]:
    """Id sequences for decode-only comparisons: random ids and arbitrary slices of encodings."""
    rng = random.Random(seed)
    out: list[list[int]] = []
    for _ in range(n_random):
        out.append([rng.randrange(first_id, vocab_size) for _ in range(rng.randint(1, 12))])
    for ids in encodings:
        if len(ids) >= 2:
            a = rng.randrange(len(ids))
            b = rng.randrange(a + 1, len(ids) + 1)
            out.append(ids[a:b])
    return out
