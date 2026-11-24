"""Indic Shift: an Indic-first byte-level BPE tokenizer with exact, reversible script sharing.

import indic_shift

tok = indic_shift.load("262k")          # or "131k"
ids = tok.encode("भारत एक विशाल देश है।")
assert tok.decode(ids) == "भारत एक विशाल देश है।"
"""

from __future__ import annotations

from ._tokenizer import IntegrityError, StreamDecoder, Tokenizer, available, data_path, load
from ._transform import Transform

__version__ = "1.0.0"

__all__ = [
    "IntegrityError",
    "StreamDecoder",
    "Tokenizer",
    "Transform",
    "__version__",
    "available",
    "data_path",
    "load",
]
