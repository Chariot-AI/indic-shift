"""Tokenizer: the Indic Shift transform followed by byte-level BPE (``tokenizers``)."""

from __future__ import annotations

import codecs
import hashlib
import json
import threading
from collections.abc import Iterable, Sequence
from functools import cache, lru_cache
from importlib.resources import files
from pathlib import Path

from . import _registry
from ._transform import _ERRORS, Transform, _WireDecoder

__all__ = ["IntegrityError", "StreamDecoder", "Tokenizer", "available", "data_path", "load"]

_ALIASES = {"262k": "indic-shift-262k", "131k": "indic-shift-131k"}
_UTF8_REPLACEMENT = "\ufffd".encode()


class IntegrityError(RuntimeError):
    """A packaged data file does not match its pinned sha256."""


def available() -> list[str]:
    """Names of the bundled tokenizers."""
    return sorted(_registry.TOKENIZERS)


def _canonical(name: str) -> str:
    key = _ALIASES.get(name.lower(), name.lower())
    if key not in _registry.TOKENIZERS:
        raise ValueError(f"unknown tokenizer {name!r}; available: {', '.join(available())} (or 262k / 131k)")
    return key


def _data_file(filename: str):
    return files("indic_shift") / "data" / filename


def data_path(name: str = "262k") -> Path:
    """Filesystem path of a bundled ``tokenizer.json`` (``name``) or of ``"transform"``.

    The ``tokenizer.json`` alone does not give Indic Shift ids: the text must go through
    :attr:`Tokenizer.transform` first (see SPEC.md).
    """
    filename = _registry.TRANSFORM[0] if name == "transform" else _registry.TOKENIZERS[_canonical(name)][0]
    return Path(str(_data_file(filename)))


def _read_verified(filename: str, expected: str) -> bytes:
    raw = _data_file(filename).read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise IntegrityError(f"{filename}: sha256 {actual} does not match the pinned {expected}")
    return raw


@lru_cache(maxsize=1)
def _transform() -> Transform:
    filename, digest = _registry.TRANSFORM
    return Transform(json.loads(_read_verified(filename, digest)))


def load(name: str = "262k") -> Tokenizer:
    """Load a bundled tokenizer: ``"262k"`` / ``"indic-shift-262k"`` or ``"131k"`` / ``"indic-shift-131k"``.

    Files ship inside the package and are checked against pinned sha256 values; no network access.
    The result is cached, so repeated calls are cheap.
    """
    return _load(_canonical(name))


@cache
def _load(key: str) -> Tokenizer:
    filename, digest, size = _registry.TOKENIZERS[key]
    return Tokenizer(key, _read_verified(filename, digest).decode("utf-8"), _transform(), size)


def _byte_decoder() -> dict[int, str]:
    """str.translate table: byte-level BPE alphabet character -> the byte it stands for (as chr)."""
    bs = [*range(0x21, 0x7F), *range(0xA1, 0xAD), *range(0xAE, 0x100)]
    cs = list(bs)
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return {c: chr(b) for b, c in zip(bs, cs)}


class Tokenizer:
    """An Indic Shift tokenizer. Get one with :func:`indic_shift.load`.

    ``encode`` treats its whole input as one text run (see "The leading-space rule" in the README).
    No special tokens exist: any text, including strings that look like control tokens, is encoded
    as plain text. Ids ``0..255`` are reserved and never produced.
    """

    def __init__(self, name: str, tokenizer_json: str, transform: Transform, vocab_size: int) -> None:
        from tokenizers import Tokenizer as _HFTokenizer

        self._name = name
        self._transform = transform
        self._bpe = _HFTokenizer.from_str(tokenizer_json)
        self._vocab_size = vocab_size
        if self._bpe.get_vocab_size(with_added_tokens=True) != vocab_size:
            raise IntegrityError(f"{name}: unexpected vocabulary size")
        self._first = _registry.FIRST_TOKEN_ID
        self._bytes: list[bytes] | None = None
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return f"<indic_shift.Tokenizer {self._name!r} vocab_size={self._vocab_size}>"

    @property
    def name(self) -> str:
        """``"indic-shift-262k"`` or ``"indic-shift-131k"``."""
        return self._name

    @property
    def vocab_size(self) -> int:
        """Number of ids (262,144 or 131,072), reserved ids included. Use it for embedding sizes."""
        return self._vocab_size

    @property
    def transform(self) -> Transform:
        """The text transform (for ports and debugging; :meth:`encode` already applies it)."""
        return self._transform

    # ---- encode --------------------------------------------------------------------------------
    def encode(self, text: str) -> list[int]:
        """Token ids of ``text``, encoded as one text run. No ids are added at the start or end."""
        return self._bpe.encode(self._transform.encode(text), add_special_tokens=False).ids

    def encode_batch(self, texts: Sequence[str]) -> list[list[int]]:
        """``[encode(t) for t in texts]``; the BPE step runs in parallel threads."""
        wires = [self._transform.encode(t) for t in texts]
        fast = getattr(self._bpe, "encode_batch_fast", None)
        encodings = (fast or self._bpe.encode_batch)(wires, add_special_tokens=False)
        return [e.ids for e in encodings]

    def count(self, text: str) -> int:
        """``len(encode(text))``."""
        return len(self.encode(text))

    # ---- decode --------------------------------------------------------------------------------
    def _table(self) -> list[bytes]:
        table = self._bytes
        if table is None:
            with self._lock:
                table = self._bytes
                if table is None:
                    vocab = self._bpe.get_vocab(with_added_tokens=False)
                    tokens = [""] * self._vocab_size
                    for tok, i in vocab.items():
                        tokens[i] = tok
                    trans = _byte_decoder()
                    table = [b""] * self._first + [t.translate(trans).encode("latin-1") for t in tokens[self._first :]]
                    self._bytes = table
        return table

    def _id_bytes(self, ids: Iterable[int], errors: str) -> bytes:
        """Concatenated token bytes; reserved ids -> error or the UTF-8 of U+FFFD."""
        table = self._table()
        ids = list(ids)
        if not ids:
            return b""
        try:
            lo, hi = min(ids), max(ids)
        except TypeError:
            raise TypeError("token ids must be integers") from None
        if lo >= self._first and hi < self._vocab_size:
            return b"".join([table[i] for i in ids])
        parts = []
        for i in ids:
            if not 0 <= i < self._vocab_size:
                raise ValueError(f"token id {i} is out of range for {self._name} (0..{self._vocab_size - 1})")
            if i < self._first:
                if errors == "strict":
                    raise ValueError(f"token id {i} is a reserved id; encode() never produces ids below {self._first}")
                parts.append(_UTF8_REPLACEMENT)
            else:
                parts.append(table[i])
        return b"".join(parts)

    def decode(self, ids: Iterable[int], *, errors: str = "replace") -> str:
        """Text of ``ids``, decoded as one text run (the inverse of :meth:`encode`).

        ``decode(encode(text)) == text`` for every string. For id sequences that no text encodes
        to (e.g. model output cut in the middle of a character), ``errors="replace"`` substitutes
        U+FFFD and ``errors="strict"`` raises ``ValueError``.
        """
        if errors not in _ERRORS:
            raise ValueError(f"errors must be one of {_ERRORS}, not {errors!r}")
        wire = self._id_bytes(ids, errors).decode("utf-8", errors)
        return self._transform.decode(wire, errors)

    def decode_batch(self, batch: Iterable[Iterable[int]], *, errors: str = "replace") -> list[str]:
        """``[decode(ids) for ids in batch]``."""
        return [self.decode(ids, errors=errors) for ids in batch]

    def stream_decoder(self, *, errors: str = "replace") -> StreamDecoder:
        """A :class:`StreamDecoder` for incremental (token by token) decoding."""
        return StreamDecoder(self, errors=errors)


class StreamDecoder:
    """Incremental decoder for one text run at a time.

    Decoding is stateful: the active script and the leading space are carried from the start of the
    run, so separately decoded slices of ids do not join up to the right text. Feed ids in order::

        dec = tok.stream_decoder()
        for token_id in generated:
            print(dec.step(token_id), end="")
        print(dec.flush())

    The concatenation of everything returned by :meth:`step` / :meth:`feed` and :meth:`flush`
    equals ``tok.decode(ids)``. Text is held back only while it is incomplete (a partial UTF-8
    character or a partial escape sequence).
    """

    def __init__(self, tokenizer: Tokenizer, *, errors: str = "replace") -> None:
        if errors not in _ERRORS:
            raise ValueError(f"errors must be one of {_ERRORS}, not {errors!r}")
        self._tok = tokenizer
        self._errors = errors
        self.reset()

    def reset(self) -> None:
        """Discard all state and start a new text run."""
        self._utf8 = codecs.getincrementaldecoder("utf-8")(errors=self._errors)
        self._wire = _WireDecoder(self._tok.transform, self._errors)
        self._started = False

    def _emit(self, piece: str, final: bool) -> str:
        if not self._started:
            if not piece:
                return self._wire.feed("", final) if final else ""
            if piece[0] == " ":  # the run's leading space
                piece = piece[1:]
            self._started = True
        return self._wire.feed(piece, final)

    def step(self, token_id: int) -> str:
        """Add one id; return the text that became final."""
        return self._emit(self._utf8.decode(self._tok._id_bytes((token_id,), self._errors)), False)

    def feed(self, ids: Iterable[int]) -> str:
        """Add several ids; return the text that became final."""
        return self._emit(self._utf8.decode(self._tok._id_bytes(ids, self._errors)), False)

    def flush(self) -> str:
        """End the run: return the remaining text and reset for the next run."""
        out = self._emit(self._utf8.decode(b"", final=True), True)
        self.reset()
        return out
