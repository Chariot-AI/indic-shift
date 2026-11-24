"""Encode and decode text, one string and a batch."""

import indic_shift

tok = indic_shift.load("262k")  # or "131k"

text = "भारत एक विशाल देश है। আমি বাংলায় কথা বলি।"
ids = tok.encode(text)
print(len(ids), "tokens:", ids)
assert tok.decode(ids) == text

texts = ["नमस्ते", "வணக்கம்", "Hello, world", "سلام", "ನಮಸ್ಕಾರ"]
batch = tok.encode_batch(texts)
assert tok.decode_batch(batch) == texts
for t, b in zip(texts, batch):
    print(f"{t!r}: {b}")
