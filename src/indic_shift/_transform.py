"""The Indic Shift text transform: text <-> wire (see SPEC.md).

Every table comes from ``data/transform.json``; nothing here consults :mod:`unicodedata`, so the
transform is identical on every Python version.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Iterable
from typing import Any

__all__ = ["Transform"]

_REPLACEMENT = "\ufffd"
_MARKER, _ATOM, _NEUTRAL, _ESCAPE, _NIBBLE, _RESERVED = range(6)
_ERRORS = ("strict", "replace")


def _cp(s: str) -> int:
    if not s.startswith("U+"):
        raise ValueError(f"bad code point {s!r}")
    return int(s[2:], 16)


def _char_class(chars: Iterable[str]) -> str:
    """A regex character class matching exactly ``chars`` (collapsed into ranges)."""
    cps = sorted({ord(c) for c in chars})
    parts: list[str] = []
    i = 0
    while i < len(cps):
        j = i
        while j + 1 < len(cps) and cps[j + 1] == cps[j] + 1:
            j += 1
        lo, hi = re.escape(chr(cps[i])), re.escape(chr(cps[j]))
        parts.append(lo if i == j else f"{lo}-{hi}")
        i = j + 1
    return "[" + "".join(parts) + "]"


class Transform:
    """The reversible text transform that runs before byte-level BPE and after decoding.

    ``encode(text)`` returns the *wire* string that the BPE model sees: Brahmic letters become shared
    letter symbols preceded by a script marker whenever the script changes, decimal digits become
    shared digit symbols, and so on. ``decode(wire)`` restores the exact original text. Each call is
    one text run: it starts from the initial script state and applies the leading-space rule.
    """

    def __init__(self, data: dict) -> None:
        if data.get("format") != "indic-shift-transform" or data.get("spec_version") != 1:
            raise ValueError("not an Indic Shift transform table (spec_version 1)")
        wire = data["wire"]
        self._escape = chr(_cp(wire["escape"]))
        n0, n1 = (_cp(x) for x in wire["nibbles"])
        if n1 - n0 != 15:
            raise ValueError("expected 16 nibble symbols")
        self._nibble_chars = tuple(chr(n0 + v) for v in range(16))
        self._nibble_value = {c: v for v, c in enumerate(self._nibble_chars)}
        self._escaped_lo, self._escaped_hi = (_cp(x) for x in wire["escaped_input"])
        self._escape_re = re.compile(f"[{chr(self._escaped_lo)}-{chr(self._escaped_hi)}]")

        # encoder: source char -> (family index, marker char or None for neutral, atom char)
        enc: dict[str, tuple[int, str | None, str]] = {}
        # decoder: wire symbol -> (kind, family index, payload)
        dec: dict[str, tuple[int, int, Any]] = {self._escape: (_ESCAPE, -1, None)}
        for c in self._nibble_chars:
            dec[c] = (_NIBBLE, -1, None)
        for name, cp in wire["reserved"].items():
            dec[chr(_cp(cp))] = (_RESERVED, -1, name)

        self._families: list[str] = []
        enc_initial: list[str | None] = []
        dec_initial: list[str | None] = []
        self._symbol_names: dict[str, str] = {}
        for fi, fam in enumerate(data["families"]):
            fname = fam["name"]
            self._families.append(fname)
            marker_of = {r: chr(_cp(cp)) for r, cp in fam["markers"].items()}
            atom_of = {a: chr(_cp(cp)) for a, cp in fam["atoms"].items()}
            initial = fam["initial"]
            if initial is not None and initial not in marker_of:
                raise ValueError(f"{fname}: unknown initial realization {initial!r}")
            enc_initial.append(None if initial is None else marker_of[initial])
            dec_initial.append(initial)
            for r, m in marker_of.items():
                self._add_symbol(dec, m, (_MARKER, fi, r))
                self._symbol_names[m] = f"{fname}:{r}"
            renders: dict[str, dict[str, str]] = {a: {} for a in atom_of}
            for r, a, cp in fam["render"]:
                if r not in marker_of or a not in atom_of:
                    raise ValueError(f"{fname}: render entry uses an unknown symbol")
                renders[a][r] = chr(_cp(cp))
            neutral = {a: chr(_cp(cp)) for cp, a in fam["neutral"]}
            for a, ch in atom_of.items():
                if a in neutral:
                    self._add_symbol(dec, ch, (_NEUTRAL, fi, neutral[a]))
                else:
                    self._add_symbol(dec, ch, (_ATOM, fi, renders[a]))
                self._symbol_names[ch] = f"{fname}:{a}"
            for cp, r, a in fam["encode"]:
                src = chr(_cp(cp))
                if src in enc or renders[a].get(r) != src:
                    raise ValueError(f"{fname}: inconsistent encode entry {cp}")
                enc[src] = (fi, marker_of[r], atom_of[a])
            for a, src in neutral.items():
                if src in enc:
                    raise ValueError(f"{fname}: neutral source mapped twice")
                enc[src] = (fi, None, atom_of[a])
        for ch in dec:
            if not self._escaped_lo <= ord(ch) <= self._escaped_hi:
                raise ValueError("wire symbols must lie in the escaped range")
        self._enc = enc
        self._dec = dec
        self._enc_initial = tuple(enc_initial)
        self._dec_initial = tuple(dec_initial)
        self._enc_re = re.compile(_char_class(enc) + "+")
        self._dec_re = re.compile(_char_class(dec))

        ls = data["leading_space"]
        ranges = [(_cp(a), _cp(b)) for a, b in ls["letter_mark_ranges"]]
        self._lm_starts = [a for a, _ in ranges]
        self._lm_ends = [b for _, b in ranges]
        self._nospace = tuple((_cp(a), _cp(b)) for a, b, _ in ls["nospace_ranges"])

    @staticmethod
    def _add_symbol(dec: dict, ch: str, entry: tuple) -> None:
        if ch in dec:
            raise ValueError(f"wire symbol U+{ord(ch):04X} assigned twice")
        dec[ch] = entry

    # ---- leading space -------------------------------------------------------------------------
    def is_letter_or_mark(self, ch: str) -> bool:
        """Whether ``ch`` has General_Category L* or M* in Unicode 15.0 (frozen table)."""
        cp = ord(ch)
        i = bisect_right(self._lm_starts, cp) - 1
        return i >= 0 and cp <= self._lm_ends[i]

    def leading_space(self, text: str) -> bool:
        """Whether encoding ``text`` as one run adds a leading U+0020 (the leading-space rule)."""
        if not text:
            return False
        ch = text[0]
        if ch == " ":
            return True
        if not self.is_letter_or_mark(ch):
            return False
        cp = ord(ch)
        return not any(lo <= cp <= hi for lo, hi in self._nospace)

    # ---- encode --------------------------------------------------------------------------------
    def _escape_one(self, m: re.Match[str]) -> str:
        nib = self._nibble_chars
        return self._escape + "".join(nib[int(d, 16)] for d in f"{ord(m.group()):06X}")

    def encode(self, text: str) -> str:
        """Text -> wire for one text run (leading-space rule included)."""
        body = self._escape_re.sub(self._escape_one, text) if self._escape_re.search(text) else text
        out: list[str] = [" "] if self.leading_space(text) else []
        append = out.append
        enc = self._enc
        initial = self._enc_initial
        state = list(initial)
        pos = 0
        for m in self._enc_re.finditer(body):
            start, end = m.span()
            if start > pos:
                append(body[pos:start])
            for ch in m.group():
                fi, marker, atom = enc[ch]
                if marker is None:  # script-neutral atom: no marker, resets the family
                    state[fi] = initial[fi]
                elif state[fi] != marker:
                    append(marker)
                    state[fi] = marker
                append(atom)
            pos = end
        if pos < len(body):
            append(body[pos:])
        return "".join(out)

    # ---- decode --------------------------------------------------------------------------------
    def decode(self, wire: str, errors: str = "strict") -> str:
        """Wire -> text for one text run: drop one leading U+0020, then invert the transform."""
        if wire.startswith(" "):
            wire = wire[1:]
        dec = _WireDecoder(self, errors)
        return dec.feed(wire, final=True)

    def describe(self, text: str) -> list[str]:
        """The wire of ``text`` as readable labels (symbols as ``<family:name>``), for debugging."""
        wire = self.encode(text)
        out: list[str] = []
        i = 0
        while i < len(wire):
            ch = wire[i]
            if ch == self._escape:
                value = 0
                for c in wire[i + 1 : i + 7]:
                    value = value * 16 + self._nibble_value[c]
                out.append(f"<escape:U+{value:04X}>")
                i += 7
                continue
            name = self._symbol_names.get(ch)
            out.append(f"<{name}>" if name else ch)
            i += 1
        return out


class _WireDecoder:
    """Incremental wire decoder for one text run (the leading space is handled by the caller).

    ``feed(chunk)`` returns the text that is final; an escape sequence cut at the end of a chunk is
    held back until the next chunk (or ``final=True``). Feeding a wire in any number of chunks gives
    the same text as feeding it at once.
    """

    __slots__ = ("_pending", "_state", "_strict", "_t")

    def __init__(self, transform: Transform, errors: str = "strict") -> None:
        if errors not in _ERRORS:
            raise ValueError(f"errors must be one of {_ERRORS}, not {errors!r}")
        self._t = transform
        self._state = list(transform._dec_initial)
        self._pending = ""
        self._strict = errors == "strict"

    def _bad(self, what: str) -> str:
        if self._strict:
            raise ValueError(f"malformed Indic Shift wire: {what}")
        return _REPLACEMENT

    def feed(self, text: str, final: bool = False) -> str:
        t = self._t
        if self._pending:
            text = self._pending + text
            self._pending = ""
        dec = t._dec
        state = self._state
        nibble_value = t._nibble_value
        search = t._dec_re.search
        out: list[str] = []
        append = out.append
        n = len(text)
        pos = 0
        while pos < n:
            m = search(text, pos)
            if m is None:
                append(text[pos:])
                break
            i = m.start()
            if i > pos:
                append(text[pos:i])
            kind, fi, payload = dec[text[i]]
            pos = i + 1
            if kind == _ATOM:
                rendered = payload.get(state[fi])
                if rendered is None:
                    rendered = self._bad(f"symbol U+{ord(text[i]):04X} has no rendering in this state")
                append(rendered)
            elif kind == _MARKER:
                state[fi] = payload
            elif kind == _NEUTRAL:
                append(payload)
                state[fi] = t._dec_initial[fi]
            elif kind == _ESCAPE:
                payload_chars = text[i + 1 : i + 7]
                k = 0
                while k < len(payload_chars) and payload_chars[k] in nibble_value:
                    k += 1
                if k == 6:
                    value = 0
                    for c in payload_chars:
                        value = value * 16 + nibble_value[c]
                    if t._escaped_lo <= value <= t._escaped_hi:
                        append(chr(value))
                    else:
                        append(self._bad("escaped value outside the private-use range"))
                    pos = i + 7
                elif k == len(payload_chars) and not final:
                    self._pending = text[i:]
                    break
                else:
                    append(self._bad("truncated escape sequence"))
            else:
                append(self._bad(f"unexpected symbol U+{ord(text[i]):04X}"))
        if final and self._pending:  # pragma: no cover - cannot happen: final never defers
            raise AssertionError("pending data after final chunk")
        return "".join(out)
