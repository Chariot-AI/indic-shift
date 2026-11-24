"""Incremental decoding, as a server would do with generated ids."""

import indic_shift

tok = indic_shift.load("262k")
ids = tok.encode("আমি বাংলায় কথা বলি")

# Wrong: decoding slices on their own loses the script and the leading space.
half = len(ids) // 2
print("slices:", tok.decode(ids[:half]) + tok.decode(ids[half:]))  # আমি বাংলায়कथा बलि

# Right: one StreamDecoder per run carries the state.
dec = tok.stream_decoder()
pieces = [dec.step(token_id) for token_id in ids]
pieces.append(dec.flush())
print("stream:", "".join(pieces))
assert "".join(pieces) == tok.decode(ids)
