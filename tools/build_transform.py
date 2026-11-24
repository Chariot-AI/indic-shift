"""Generate ``src/indic_shift/data/transform.json`` from the Unicode 15.0 character database.

The Indic Shift transform is defined by a few rules over Unicode character names, categories and
decompositions (see SPEC.md). Python's ``unicodedata`` changes with every Python release, so the
package never consults it at runtime. Instead, this script evaluates the rules once, on a Python
whose ``unicodedata`` is Unicode 15.0.0 (CPython 3.12), and writes every resulting table to a data
file. The package reads only that file, so it produces identical ids on every Python version.

Usage (CPython 3.12 only):

    python tools/build_transform.py                 # (re)write the data file
    python tools/build_transform.py --check         # fail unless the shipped file is byte-identical
    python tools/build_transform.py --compare-symbols other.json
        # also compare the symbol code points with a {"name": "U+XXXX"} map (an independent build)
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

UNICODE_VERSION = "15.0.0"
REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "src" / "indic_shift" / "data" / "transform.json"

# --- wire alphabet ---------------------------------------------------------------------------------
PUA_START, PUA_END = 0xE000, 0xF8FF  # literal input in this range is escaped
ESCAPE = 0xE000
NIBBLE_START = 0xE001  # 16 nibble symbols U+E001..U+E010
MARKER_START, MARKER_END = 0xE020, 0xE0FF
ATOM_START = 0xE100
# Four marker code points are reserved: never written by the encoder, rejected by the decoder. They
# keep every other symbol (and the code-point classes of the split regex) at a fixed code point.
RESERVED = {"reserved.0": 0xE024, "reserved.1": 0xE025, "reserved.2": 0xE026, "reserved.3": 0xE027}

# --- Brahmic family --------------------------------------------------------------------------------
INDIC_PREFIXES = {
    "DEVANAGARI": "Deva",
    "BENGALI": "Beng",
    "GURMUKHI": "Guru",
    "GUJARATI": "Gujr",
    "ORIYA": "Orya",
    "TAMIL": "Taml",
    "TELUGU": "Telu",
    "KANNADA": "Knda",
    "MALAYALAM": "Mlym",
    "SINHALA": "Sinh",
}
INDIC_RANGES = ((0x0900, 0x0D7F), (0x0D80, 0x0DFF), (0xA8E0, 0xA8FF), (0x11FC0, 0x11FFF))

# Meetei Mayek letters share an atom with the Brahmic letter of the same sound only where the
# Unicode names list (alias) gives a clear phonetic value. Lonsum (final) letters have their own
# atoms; the "MteiFinal" realization is kept for decoding only.
MEETEI_ATOMS: dict[int, tuple[str, str]] = {
    0xAAE0: ("Mtei", "LETTER E"),
    0xAAE1: ("Mtei", "LETTER O"),
    0xAAE2: ("Mtei", "LETTER CHA"),
    0xAAE3: ("Mtei", "LETTER NYA"),
    0xAAE4: ("Mtei", "LETTER TTA"),
    0xAAE5: ("Mtei", "LETTER TTHA"),
    0xAAE6: ("Mtei", "LETTER DDA"),
    0xAAE7: ("Mtei", "LETTER DDHA"),
    0xAAE8: ("Mtei", "LETTER NNA"),
    0xAAE9: ("Mtei", "LETTER SHA"),
    0xAAEA: ("Mtei", "LETTER SSA"),
    0xAAEB: ("Mtei", "VOWEL SIGN II"),
    0xAAEC: ("Mtei", "VOWEL SIGN UU"),
    0xAAF5: ("Mtei", "SIGN VISARGA"),
    0xAAF6: ("Mtei", "SIGN VIRAMA"),
    0xABC0: ("Mtei", "LETTER KA"),
    0xABC1: ("Mtei", "LETTER SA"),
    0xABC2: ("Mtei", "LETTER LA"),
    0xABC3: ("Mtei", "LETTER MA"),
    0xABC4: ("Mtei", "LETTER PA"),
    0xABC5: ("Mtei", "LETTER NA"),
    0xABC6: ("Mtei", "LETTER CA"),
    0xABC7: ("Mtei", "LETTER TA"),
    0xABC8: ("Mtei", "LETTER KHA"),
    0xABC9: ("Mtei", "LETTER NGA"),
    0xABCA: ("Mtei", "LETTER THA"),
    0xABCB: ("Mtei", "LETTER WA"),
    0xABCC: ("Mtei", "LETTER YA"),
    0xABCD: ("Mtei", "LETTER HA"),
    0xABCE: ("Mtei", "LETTER U"),
    0xABCF: ("Mtei", "LETTER I"),
    0xABD0: ("Mtei", "LETTER PHA"),
    0xABD1: ("Mtei", "LETTER A"),
    0xABD2: ("Mtei", "LETTER GA"),
    0xABD3: ("Mtei", "LETTER JHA"),
    0xABD4: ("Mtei", "LETTER RA"),
    0xABD5: ("Mtei", "LETTER BA"),
    0xABD6: ("Mtei", "LETTER JA"),
    0xABD7: ("Mtei", "LETTER DA"),
    0xABD8: ("Mtei", "LETTER GHA"),
    0xABD9: ("Mtei", "LETTER DHA"),
    0xABDA: ("Mtei", "LETTER BHA"),
    0xABDB: ("MteiFinal", "LETTER KA"),
    0xABDC: ("MteiFinal", "LETTER LA"),
    0xABDD: ("MteiFinal", "LETTER MA"),
    0xABDE: ("MteiFinal", "LETTER PA"),
    0xABDF: ("MteiFinal", "LETTER NA"),
    0xABE0: ("MteiFinal", "LETTER TA"),
    0xABE1: ("MteiFinal", "LETTER NGA"),
    0xABE2: ("MteiFinal", "LETTER I"),
    0xABE3: ("Mtei", "VOWEL SIGN O"),
    0xABE4: ("Mtei", "VOWEL SIGN I"),
    0xABE5: ("Mtei", "VOWEL SIGN AA"),
    0xABE6: ("Mtei", "VOWEL SIGN E"),
    0xABE7: ("Mtei", "VOWEL SIGN AU"),
    0xABE8: ("Mtei", "VOWEL SIGN U"),
    0xABE9: ("Mtei", "VOWEL SIGN AI"),
    0xABEA: ("Mtei", "SIGN ANUSVARA"),
}

# Ol Chiki letters (phonetic values from the Unicode encoding proposal). The encoder leaves Ol Chiki
# text unchanged; these renderings exist so that the decoder accepts the "Olck" realization.
OL_CHIKI_ATOMS: dict[int, tuple[str, str]] = {
    0x1C5A: ("Olck", "LETTER SHORT O"),
    0x1C5B: ("Olck", "LETTER TA"),
    0x1C5C: ("Olck", "LETTER GA"),
    0x1C5D: ("Olck", "LETTER NGA"),
    0x1C5E: ("Olck", "LETTER LA"),
    0x1C5F: ("Olck", "LETTER A"),
    0x1C60: ("Olck", "LETTER KA"),
    0x1C61: ("Olck", "LETTER JA"),
    0x1C62: ("Olck", "LETTER MA"),
    0x1C63: ("Olck", "LETTER WA"),
    0x1C64: ("Olck", "LETTER I"),
    0x1C65: ("Olck", "LETTER SA"),
    0x1C66: ("Olck", "LETTER HA"),
    0x1C67: ("Olck", "LETTER NYA"),
    0x1C68: ("Olck", "LETTER RA"),
    0x1C69: ("Olck", "LETTER U"),
    0x1C6A: ("Olck", "LETTER CA"),
    0x1C6B: ("Olck", "LETTER DA"),
    0x1C6C: ("Olck", "LETTER NNA"),
    0x1C6D: ("Olck", "LETTER YA"),
    0x1C6E: ("Olck", "LETTER E"),
    0x1C6F: ("Olck", "LETTER PA"),
    0x1C70: ("Olck", "LETTER DDA"),
    0x1C71: ("Olck", "LETTER NA"),
    0x1C72: ("Olck", "LETTER RRA"),
    0x1C73: ("Olck", "LETTER O"),
    0x1C74: ("Olck", "LETTER TTA"),
    0x1C75: ("Olck", "LETTER BA"),
    0x1C76: ("Olck", "LETTER VA"),
    0x1C78: ("Olck", "SIGN CANDRABINDU"),
    0x1C7B: ("Olck", "LENGTH MARK"),
}
NEUTRAL_INDIC = {0x0964: "DANDA", 0x0965: "DOUBLE DANDA"}

# --- kana family -----------------------------------------------------------------------------------
KANA_PREFIXES = {"HIRAGANA": "Hira", "KATAKANA": "Kana"}
KANA_RANGES = ((0x3040, 0x30FF), (0x31F0, 0x31FF), (0x1B000, 0x1B16F))

# --- Arabic-script family --------------------------------------------------------------------------
ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x0870, 0x089F), (0x08A0, 0x08FF))
ARABIC_COMBINING = {"0653": "MADDAH_ABOVE", "0654": "HAMZA_ABOVE", "0655": "HAMZA_BELOW"}

# --- leading-space rule ----------------------------------------------------------------------------
# Unicode blocks of scripts written without spaces between words. A text run whose first character is
# a letter or mark in one of these ranges gets no leading space.
NOSPACE_RANGES = (
    (0x0E00, 0x0E7F, "Thai"),
    (0x0E80, 0x0EFF, "Lao"),
    (0x1780, 0x17FF, "Khmer"),
    (0x19E0, 0x19FF, "Khmer Symbols"),
    (0x3000, 0x302D, "CJK Symbols and Punctuation (U+3000..U+302D)"),
    (0x3030, 0x303F, "CJK Symbols and Punctuation (U+3030..U+303F)"),
    (0x3040, 0x309F, "Hiragana"),
    (0x30A0, 0x30FF, "Katakana"),
    (0x31F0, 0x31FF, "Katakana Phonetic Extensions"),
    (0x3400, 0x4DBF, "CJK Unified Ideographs Extension A"),
    (0x4E00, 0x9FFF, "CJK Unified Ideographs"),
    (0xF900, 0xFAFF, "CJK Compatibility Ideographs"),
    (0xFF66, 0xFF9F, "Halfwidth Katakana"),
    (0x16FE2, 0x16FE3, "Ideographic Symbols and Punctuation (Han)"),
    (0x16FF0, 0x16FF1, "Ideographic Symbols and Punctuation (Han)"),
    (0x1AFF0, 0x1AFFF, "Kana Extended-B"),
    (0x1B000, 0x1B0FF, "Kana Supplement"),
    (0x1B100, 0x1B12F, "Kana Extended-A"),
    (0x1B130, 0x1B16F, "Small Kana Extension"),
    (0x20000, 0x2FFFF, "Supplementary Ideographic Plane"),
    (0x30000, 0x3FFFF, "Tertiary Ideographic Plane"),
)

LEADING_SPACE_RULE = (
    "encode: prepend one U+0020 to a text run iff the run starts with U+0020, or with a character whose "
    "General_Category (Unicode 15.0) is L* or M* and that lies in none of nospace_ranges; "
    "decode: remove one leading U+0020 of the decoded wire iff present"
)


def u(cp: int) -> str:
    return f"U+{cp:04X}"


class Family:
    """One stateful map: source character -> (realization, atom), and (realization, atom) -> char."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.encode: dict[int, tuple[str, str]] = {}
        self.render: dict[tuple[str, str], int] = {}
        self.realizations: set[str] = set()
        self.atoms: set[str] = set()


def _name_map(
    name: str,
    prefixes: dict[str, str],
    ranges: tuple[tuple[int, int], ...],
    *,
    shared_only: bool,
    skip_categories: frozenset[str] = frozenset(),
) -> Family:
    """Characters whose Unicode name is '<PREFIX> <REST>' map to atom REST in realization PREFIX.

    A (realization, atom) pair claimed by two characters is dropped. With ``shared_only``, atoms that
    occur in a single realization are dropped too.
    """
    candidates: dict[tuple[str, str], list[int]] = {}
    for lo, hi in ranges:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            if unicodedata.category(ch) in skip_categories:
                continue
            uname = unicodedata.name(ch, "")
            for prefix, realization in prefixes.items():
                if uname.startswith(prefix + " "):
                    candidates.setdefault((realization, uname[len(prefix) + 1 :]), []).append(cp)
                    break
    render = {key: cps[0] for key, cps in candidates.items() if len(cps) == 1}
    if shared_only:
        seen: dict[str, set[str]] = {}
        for realization, atom in render:
            seen.setdefault(atom, set()).add(realization)
        render = {k: v for k, v in render.items() if len(seen[k[1]]) >= 2}
    fam = Family(name)
    for (realization, atom), cp in render.items():
        fam.render[(realization, atom)] = cp
        fam.encode[cp] = (realization, atom)
        fam.realizations.add(realization)
        fam.atoms.add(atom)
    return fam


def _add_explicit(fam: Family, mapping: dict[int, tuple[str, str]], name_prefix: str) -> None:
    for cp, (realization, atom) in mapping.items():
        if not unicodedata.name(chr(cp), "").startswith(name_prefix):
            raise RuntimeError(f"U+{cp:04X} is not a {name_prefix} character")
        if atom not in fam.atoms:
            raise RuntimeError(f"atom {atom!r} does not exist in the {fam.name} family")
        key = (realization, atom)
        if fam.render.get(key, cp) != cp:
            raise RuntimeError(f"ambiguous rendering for {key}")
        fam.render[key] = cp
        fam.encode[cp] = key
        fam.realizations.add(realization)


def build_digit() -> Family:
    """Every decimal digit (General_Category Nd): atom = its value, realization = its digit set."""
    fam = Family("digit")
    for cp in range(0x110000):
        ch = chr(cp)
        if unicodedata.category(ch) != "Nd":
            continue
        value = unicodedata.decimal(ch)
        realization = f"U+{cp - value:04X}"
        fam.encode[cp] = (realization, str(value))
        fam.render[(realization, str(value))] = cp
        fam.realizations.add(realization)
    fam.atoms = {str(v) for v in range(10)}
    return fam


def build_indic() -> tuple[Family, dict[int, str], dict[int, str]]:
    """Brahmic letters and signs, Meetei Mayek, Ol Chiki (decode only), the two dandas (neutral)."""
    fam = _name_map("indic", INDIC_PREFIXES, INDIC_RANGES, shared_only=False, skip_categories=frozenset({"Nd"}))
    _add_explicit(fam, MEETEI_ATOMS, "MEETEI MAYEK ")
    _add_explicit(fam, OL_CHIKI_ATOMS, "OL CHIKI ")
    extra: dict[int, str] = {}
    # Lonsum letters: own atoms in the Mtei realization (the MteiFinal rendering stays decodable).
    for cp, (realization, atom) in MEETEI_ATOMS.items():
        if realization == "MteiFinal":
            if not unicodedata.name(chr(cp)).endswith("LONSUM"):
                raise RuntimeError(f"U+{cp:04X} is not a lonsum letter")
            new_atom = "LONSUM " + atom.removeprefix("LETTER ")
            fam.encode[cp] = ("Mtei", new_atom)
            fam.render[("Mtei", new_atom)] = cp
            extra[cp] = new_atom
    # Ol Chiki is never mapped by the encoder (its renderings stay decodable).
    for cp in OL_CHIKI_ATOMS:
        del fam.encode[cp]
    # Dandas are script-neutral: removed from the encode/render tables, handled as neutral atoms.
    neutral: dict[int, str] = {}
    for cp, atom in NEUTRAL_INDIC.items():
        renders = {c for (_, a), c in fam.render.items() if a == atom}
        if renders != {cp}:
            raise RuntimeError(f"neutral atom {atom!r} renders as {renders}")
        del fam.encode[cp]
        for key in [k for k in fam.render if k[1] == atom]:
            del fam.render[key]
        neutral[cp] = atom
    if len(extra) != 8:
        raise RuntimeError("expected 8 lonsum letters")
    return fam, neutral, extra


def build_kana() -> Family:
    return _name_map("kana", KANA_PREFIXES, KANA_RANGES, shared_only=True)


def build_arabic() -> tuple[Family, dict[int, str]]:
    """Arabic-script letters: one atom per letter; canonical hamza/madda composites get own atoms."""
    composed: list[tuple[int, int, str]] = []
    for lo, hi in ARABIC_RANGES:
        for cp in range(lo, hi + 1):
            fields = unicodedata.decomposition(chr(cp)).split()
            if len(fields) != 2 or fields[0].startswith("<"):
                continue
            variant = ARABIC_COMBINING.get(fields[1])
            base = int(fields[0], 16)
            if variant is None or not unicodedata.name(chr(base), "").startswith("ARABIC LETTER "):
                continue
            composed.append((cp, base, variant))
    if len(composed) != 8:
        raise RuntimeError(f"expected 8 canonical Arabic composites, found {len(composed)}")
    composed_cps = {cp for cp, _, _ in composed}
    fam = Family("arabic_variant")
    fam.realizations.add("ARAB")
    for lo, hi in ARABIC_RANGES:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            uname = unicodedata.name(ch, "")
            if cp in composed_cps or not unicodedata.category(ch).startswith("L"):
                continue
            if not uname.startswith("ARABIC LETTER "):
                continue
            atom = uname.removeprefix("ARABIC LETTER ")
            if fam.render.get(("ARAB", atom), cp) != cp:
                raise RuntimeError(f"ambiguous Arabic letter {atom}")
            fam.atoms.add(atom)
            fam.encode[cp] = ("ARAB", atom)
            fam.render[("ARAB", atom)] = cp
    extra: dict[int, str] = {}
    for cp, base, variant in composed:
        atom = unicodedata.name(chr(base)).removeprefix("ARABIC LETTER ")
        fam.atoms.add(atom)
        fam.realizations.add(variant)
        fam.render[(variant, atom)] = cp  # decode-only spelling: base atom in a composite realization
        own = unicodedata.name(chr(cp)).removeprefix("ARABIC LETTER ")
        fam.encode[cp] = ("ARAB", own)
        fam.render[("ARAB", own)] = cp
        extra[cp] = own
    return fam, extra


def letter_mark_ranges() -> list[list[int]]:
    out: list[list[int]] = []
    for cp in range(0x110000):
        if unicodedata.category(chr(cp))[0] in "LM":
            if out and out[-1][1] == cp - 1:
                out[-1][1] = cp
            else:
                out.append([cp, cp])
    return out


def build() -> dict:
    if unicodedata.unidata_version != UNICODE_VERSION:
        sys.exit(
            f"this script needs unicodedata {UNICODE_VERSION} (CPython 3.12); "
            f"this Python has {unicodedata.unidata_version}"
        )
    digit = build_digit()
    indic, neutral, lonsum = build_indic()
    kana = build_kana()
    arabic, composites = build_arabic()
    families = [digit, indic, kana, arabic]  # encode order; decode runs the reverse order

    # Marker and atom names. Markers are numbered in name order from U+E020, skipping the reserved
    # code points; base atoms in name order from U+E100; the 16 extra atoms (lonsum letters, Arabic
    # composites) follow the last base atom, in name order.
    extra_atom_names = {f"indic.atom.{a}" for a in lonsum.values()} | {
        f"arabic_variant.atom.{a}" for a in composites.values()
    }
    markers = sorted({f"{f.name}.realization.{r}" for f in families for r in f.realizations})
    atoms = {f"{f.name}.atom.{a}" for f in families for a in f.atoms}
    for f in families:
        atoms.update(f"{f.name}.atom.{a}" for (_, a) in f.render)
    atoms.update(f"indic.atom.{a}" for a in neutral.values())
    base_atoms = sorted(atoms - extra_atom_names)
    symbol_cp: dict[str, int] = {}
    cp = MARKER_START
    for n in markers:
        while cp in RESERVED.values():
            cp += 1
        symbol_cp[n] = cp
        cp += 1
    if cp - 1 > MARKER_END or min(RESERVED.values()) >= cp:
        raise RuntimeError("marker allocation out of range")
    for i, n in enumerate(base_atoms):
        symbol_cp[n] = ATOM_START + i
    nxt = ATOM_START + len(base_atoms)
    for i, n in enumerate(sorted(extra_atom_names)):
        symbol_cp[n] = nxt + i
    if max(symbol_cp.values()) > PUA_END:
        raise RuntimeError("alphabet exceeds the private-use area")
    sources = [cp for f in families for cp in f.encode] + list(neutral)
    if len(sources) != len(set(sources)):
        raise RuntimeError("a source character belongs to two families")

    fams_out = []
    for f in families:
        initial = {"digit": "U+0030", "indic": "Deva", "kana": None, "arabic_variant": "ARAB"}[f.name]
        fam_atoms = sorted({a for (_, a) in f.render} | ({*neutral.values()} if f.name == "indic" else set()))
        fams_out.append(
            {
                "name": f.name,
                "initial": initial,
                "markers": {r: u(symbol_cp[f"{f.name}.realization.{r}"]) for r in sorted(f.realizations)},
                "atoms": {a: u(symbol_cp[f"{f.name}.atom.{a}"]) for a in fam_atoms},
                "encode": [[u(cp), r, a] for cp, (r, a) in sorted(f.encode.items())],
                "render": [[r, a, u(cp)] for (r, a), cp in sorted(f.render.items(), key=lambda kv: (kv[1], kv[0]))],
                "neutral": [[u(cp), a] for cp, a in sorted(neutral.items())] if f.name == "indic" else [],
            }
        )
    return {
        "format": "indic-shift-transform",
        "spec_version": 1,
        "unicode_version": UNICODE_VERSION,
        "wire": {
            "escape": u(ESCAPE),
            "nibbles": [u(NIBBLE_START), u(NIBBLE_START + 15)],
            "escaped_input": [u(PUA_START), u(PUA_END)],
            "reserved": {n: u(cp) for n, cp in RESERVED.items()},
        },
        "families": fams_out,
        "leading_space": {
            "rule": LEADING_SPACE_RULE,
            "nospace_ranges": [[u(a), u(b), n] for a, b, n in NOSPACE_RANGES],
            "letter_mark_ranges": [[u(a), u(b)] for a, b in letter_mark_ranges()],
        },
    }


def _fmt(obj: object, indent: int) -> str:
    pad = " " * indent
    if isinstance(obj, dict) and obj:
        items = [f"{pad} {json.dumps(k, ensure_ascii=False)}: {_fmt(v, indent + 1)}" for k, v in obj.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(obj, list) and any(isinstance(x, (dict, list)) for x in obj):
        items = [f"{pad} {_fmt(v, indent + 1)}" for v in obj]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    return json.dumps(obj, ensure_ascii=False, separators=(", ", ": "))


def dumps(obj: dict) -> str:
    """Deterministic serialisation: containers one item per line, innermost lists on one line."""
    return _fmt(obj, 0) + "\n"


def symbol_map(obj: dict) -> dict[str, str]:
    """{symbol name: "U+XXXX"} for every marker, atom and reserved code point."""
    out: dict[str, str] = {}
    for f in obj["families"]:
        for r, cp in f["markers"].items():
            out[f"{f['name']}.realization.{r}"] = cp
        for a, cp in f["atoms"].items():
            out[f"{f['name']}.atom.{a}"] = cp
    for n, cp in obj["wire"]["reserved"].items():
        out[n] = cp
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true", help="compare with --out instead of writing it")
    ap.add_argument("--compare-symbols", type=Path, help='JSON {"name": "U+XXXX"} to compare against')
    args = ap.parse_args()
    obj = build()
    text = dumps(obj)
    if json.loads(text) != obj:
        raise RuntimeError("serialisation is not faithful")
    if args.compare_symbols:
        theirs = json.loads(args.compare_symbols.read_text(encoding="utf-8"))
        mine = symbol_map(obj)
        by_cp_mine = {v: k for k, v in mine.items()}
        by_cp_theirs = {v: k for k, v in theirs.items()}
        if set(by_cp_mine) != set(by_cp_theirs):
            sys.exit(f"symbol code points differ: {sorted(set(by_cp_mine) ^ set(by_cp_theirs))[:20]}")
        diff = [
            cp for cp in by_cp_mine if not by_cp_mine[cp].startswith("reserved.") and by_cp_mine[cp] != by_cp_theirs[cp]
        ]
        if diff:
            sys.exit(f"symbol names differ at {diff[:20]}")
        print(f"symbols: {len(mine)} code points identical")
    if args.check:
        current = args.out.read_text(encoding="utf-8")
        if current != text:
            sys.exit(f"{args.out} differs from the generated tables")
        print(f"{args.out}: up to date")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out} ({len(text.encode()):,} bytes)")


if __name__ == "__main__":
    main()
