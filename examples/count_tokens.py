"""Count tokens and tokens per word for a UTF-8 text file: python examples/count_tokens.py FILE [131k]"""

import sys

import indic_shift

path = sys.argv[1]
tok = indic_shift.load(sys.argv[2] if len(sys.argv) > 2 else "262k")
with open(path, encoding="utf-8") as f:
    lines = [line.rstrip("\n") for line in f if line.strip()]
tokens = sum(len(ids) for ids in tok.encode_batch(lines))
words = sum(len(line.split()) for line in lines)
print(f"{tok.name}: {len(lines)} lines, {words} words, {tokens} tokens, {tokens / max(words, 1):.3f} tokens/word")
