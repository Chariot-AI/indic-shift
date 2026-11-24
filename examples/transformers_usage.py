"""Using Indic Shift through Hugging Face transformers (pip install "indic-shift[transformers]")."""

from indic_shift.hf import IndicShiftTokenizer

tok = IndicShiftTokenizer.from_name("131k")
enc = tok(["नमस्ते दुनिया", "Hello"])
print(enc["input_ids"])
print(tok.batch_decode(enc["input_ids"]))

# Add your model's control tokens; text between them is encoded run by run.
tok.add_special_tokens({"additional_special_tokens": ["<|user|>", "<|end|>"]})
ids = tok("<|user|>নমস্কার<|end|>")["input_ids"]
print(ids, tok.decode(ids))
