"""Building a prompt with your own control tokens: encode each text run on its own.

Indic Shift has no special tokens. A model defines its own control tokens (here, two ids after the
vocabulary) and puts them between separately encoded text runs.
"""

import indic_shift

tok = indic_shift.load("262k")
USER, END = tok.vocab_size, tok.vocab_size + 1  # ids your model adds after the vocabulary

messages = ["नमस्ते! आप कैसे हैं?", "আমি ভালো আছি।"]
ids: list[int] = []
for message in messages:
    ids += [USER, *tok.encode(message), END]  # one encode() call per run

# Decoding: split at your control ids and decode each run on its own.
runs, run = [], []
for i in ids:
    if i in (USER, END):
        if run:
            runs.append(tok.decode(run))
        run = []
    else:
        run.append(i)
assert runs == messages
print(runs)
