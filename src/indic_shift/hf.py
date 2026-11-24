"""Hugging Face ``transformers`` integration (optional; needs ``pip install 'indic-shift[transformers]'``).

    from indic_shift.hf import IndicShiftTokenizer

    tok = IndicShiftTokenizer.from_name("262k")
    batch = tok(["नमस्ते दुनिया", "Hello"])
    tok.save_pretrained("my-tokenizer")          # reload with IndicShiftTokenizer.from_pretrained

This is a Python ("slow") tokenizer. ``transformers`` splits text at added tokens and tokenizes each
piece separately, and :meth:`IndicShiftTokenizer.decode` decodes each run between added tokens
separately, which is exactly the per-run semantics of Indic Shift. The tokenizer defines no special
tokens and adds none; models add their own with ``add_special_tokens``. Offsets are not supported.
"""

from __future__ import annotations

import json
import os
from typing import Any

try:
    from transformers import PreTrainedTokenizer
except ImportError as exc:  # pragma: no cover - exercised only without transformers
    raise ImportError("indic_shift.hf needs transformers: pip install 'indic-shift[transformers]'") from exc

from . import __version__
from ._tokenizer import load

__all__ = ["IndicShiftTokenizer"]

VOCAB_FILE = "indic_shift.json"


class IndicShiftTokenizer(PreTrainedTokenizer):  # type: ignore[misc]
    """``transformers`` tokenizer backed by the bundled Indic Shift tokenizer."""

    vocab_files_names = {"vocab_file": VOCAB_FILE}
    model_input_names = ["input_ids", "attention_mask"]

    def __init__(self, vocab_file: str | None = None, name: str = "indic-shift-262k", **kwargs: Any) -> None:
        if vocab_file is not None:
            with open(vocab_file, encoding="utf-8") as f:
                name = json.load(f)["name"]
        self._ist = load(name)
        self._vocab: dict[str, int] = self._ist._bpe.get_vocab(with_added_tokens=False)
        self._inv: dict[int, str] = {i: t for t, i in self._vocab.items()}
        kwargs.setdefault("clean_up_tokenization_spaces", False)
        super().__init__(**kwargs)

    @classmethod
    def from_name(cls, name: str = "262k", **kwargs: Any) -> IndicShiftTokenizer:
        """Tokenizer for a bundled name: ``"262k"`` or ``"131k"`` (or the full names)."""
        return cls(name=name, **kwargs)

    @property
    def indic_shift(self):
        """The underlying :class:`indic_shift.Tokenizer`."""
        return self._ist

    @property
    def vocab_size(self) -> int:
        return self._ist.vocab_size

    def __len__(self) -> int:
        return self._ist.vocab_size + sum(1 for i in self.added_tokens_decoder if i >= self._ist.vocab_size)

    def get_vocab(self) -> dict[str, int]:
        vocab = dict(self._vocab)
        vocab.update(self.added_tokens_encoder)
        return vocab

    def _tokenize(self, text: str, **kwargs: Any) -> list[str]:
        inv = self._inv
        return [inv[i] for i in self._ist.encode(text)]

    def _convert_token_to_id(self, token: str) -> int | None:
        return self._vocab.get(token)

    def _convert_id_to_token(self, index: int) -> str | None:
        return self._inv.get(index)

    def convert_tokens_to_string(self, tokens: list[str]) -> str:
        return self._ist.decode([self._vocab[t] for t in tokens])

    def _decode(
        self,
        token_ids: int | list[int],
        skip_special_tokens: bool = False,
        clean_up_tokenization_spaces: bool | None = None,
        **kwargs: Any,
    ) -> str:
        if isinstance(token_ids, int):
            token_ids = [token_ids]
        added = self.added_tokens_decoder
        special = set(self.all_special_ids)
        out: list[str] = []
        run: list[int] = []
        for i in token_ids:
            i = int(i)
            if i in added:
                if run:
                    out.append(self._ist.decode(run))
                    run = []
                if not (skip_special_tokens and i in special):
                    out.append(added[i].content)
            else:
                run.append(i)
        if run:
            out.append(self._ist.decode(run))
        text = "".join(out)
        if clean_up_tokenization_spaces is None:
            clean_up_tokenization_spaces = bool(self.clean_up_tokenization_spaces)
        return self.clean_up_tokenization(text) if clean_up_tokenization_spaces else text

    def save_vocabulary(self, save_directory: str, filename_prefix: str | None = None) -> tuple[str]:
        path = os.path.join(save_directory, (filename_prefix + "-" if filename_prefix else "") + VOCAB_FILE)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": self._ist.name, "indic_shift_version": __version__}, f, indent=1)
            f.write("\n")
        return (path,)
