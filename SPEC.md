# Indic Shift specification

This document specifies Indic Shift precisely enough to port it to another language or serving stack
and get identical ids. The Python package in this repository is the reference implementation;
`tests/golden/golden.jsonl` and the digests in [Acceptance tests](#acceptance-tests) are the
acceptance criteria.

Notation: code points are written `U+XXXX`; `␠` is U+0020 SPACE.

## 1. Overview

```
encode(text) = BPE(wire(text))
wire(text)   = lead(text) + map(escape(text))
decode(ids)  = unmap(strip(utf8(bytes(ids))))
```

- `escape` protects literal private-use input (section 3).
- `map` replaces characters with transform symbols (section 4).
- `lead` adds one leading `␠` by the leading-space rule (section 5).
- `BPE` is the byte-level BPE in `tokenizer.json` (section 6).
- `bytes`, `utf8`, `strip` and `unmap` invert these steps (section 7).

One call of `encode` or `decode` handles one **text run**. Every run starts from the initial state of
section 4 and gets its own leading-space decision. Sections 8 and 9 cover streaming and serving.

## 2. Data files

| file | contents |
|---|---|
| `indic-shift-262k.tokenizer.json` | Hugging Face `tokenizers` JSON: byte-level BPE, 262,144 ids, 261,632 merges |
| `indic-shift-131k.tokenizer.json` | the same format, 131,072 ids, 130,560 merges (the first part of the 262K) |
| `transform.json` | every table of the transform (sections 3 to 5), `spec_version` 1 |

The package pins the sha256 of each file in `src/indic_shift/_registry.py`.

**Reserved ids.** Ids 0..255 are reserved. In `tokenizer.json` they hold placeholder strings
`"<reserved 000>"` .. `"<reserved 255>"`. These contain U+0020, which never occurs in a byte-level
token, so BPE cannot produce them. `added_tokens` is empty. A port must never emit these ids and
should treat them as invalid on decode (the reference decodes each one as U+FFFD, or rejects it in
strict mode).

**`transform.json`** has these fields:

- `wire`: `escape` (U+E000), `nibbles` (first and last nibble symbol, U+E001..U+E010),
  `escaped_input` (U+E000..U+F8FF) and `reserved` (four reserved symbol code points U+E024..U+E027).
- `families`: the four map families in **encode order**: `digit`, `indic`, `kana`,
  `arabic_variant`. Each family has these fields:
  - `initial`: the realization active at the start of a run, or `null`.
  - `markers`: realization name → marker code point.
  - `atoms`: atom name → atom code point.
  - `encode`: `[source, realization, atom]` triples used by the encoder.
  - `render`: `[realization, atom, output]` triples used by the decoder. This is a superset of the
    inverted `encode` table (see 4.3).
  - `neutral`: `[source, atom]` pairs for script-neutral atoms (indic only).
- `leading_space`: `rule` (prose), `nospace_ranges` (21 ranges) and `letter_mark_ranges` (the code
  points whose General_Category is L* or M* in Unicode 15.0, as inclusive ranges).

`unicode_version` ("15.0.0") records the Unicode database the tables were generated from
(`tools/build_transform.py`, CPython 3.12). Implementations read the tables and never consult their
own Unicode database for the transform.

## 3. Wire alphabet and escaping

The transform writes its symbols as code points in the Basic Multilingual Plane private-use area:

| code points | use |
|---|---|
| U+E000 | escape |
| U+E001..U+E010 | 16 nibble symbols (values 0..15) |
| U+E020..U+E023 | Arabic-script markers |
| U+E024..U+E027 | reserved: never written, invalid on decode |
| U+E028..U+E06B | 68 digit-set markers |
| U+E06C..U+E078 | 13 Brahmic markers |
| U+E079..U+E07A | 2 kana markers |
| U+E100..U+E3D5 | 726 atoms (all families; digit atoms are U+E200..U+E209) |

**Escape.** Before mapping, every input character in U+E000..U+F8FF is replaced by U+E000 followed
by six nibble symbols: the code point in hexadecimal, most significant digit first, zero-padded to
six digits. For example U+F8FF becomes U+E000 U+E001 U+E001 U+E010 U+E009 U+E010 U+E010. Other
private-use planes (U+F0000 and up) are not escaped. After escaping, the only BMP private-use code
points in the stream are transform symbols, so a user can never forge one.

## 4. The map passes

### 4.1 Encoding

Each family keeps an **active realization** (its state), initialised from `initial`:

| family | initial | covers |
|---|---|---|
| `digit` | `U+0030` (ASCII digits) | every General_Category Nd character, atom = its decimal value, realization = its digit set (named by the set's zero) |
| `indic` | `Deva` | Brahmic letters and signs, Meetei Mayek, the two dandas (neutral) |
| `kana` | none | hiragana/katakana pairs with the same name |
| `arabic_variant` | `ARAB` | Arabic-script letters |

The reference applies the four passes one after another, in encode order, each over the output of
the previous one. The families have disjoint source characters and every pass copies the other
passes' symbols and escape sequences unchanged, so a single left-to-right scan is equivalent. For
each character `c` of the escaped text:

```
if c is a neutral source of family F:            # U+0964 DANDA, U+0965 DOUBLE DANDA
    output atom(F, c); state[F] = initial[F]
elif c is an encode source of family F with (r, a):
    if state[F] != r: output marker(F, r); state[F] = r
    output atom(F, a)
else:
    output c
```

Examples (markers in angle brackets, atoms shown as the original letters):

```
"नमस्ते"          -> नमस्ते                     (Devanagari is the initial state: no marker)
"আমি যাই। তুমি"   -> <Beng>আমি যাই। <Beng>তুমি   (the danda resets the state to Devanagari)
"in 2024 ২০২৪"    -> in 2024 <U+09E6>২০২৪        (ASCII digits are the initial digit set)
```

### 4.2 Details of the families

- **Brahmic.** The `indic` atoms come from Unicode character names: a character named
  `<SCRIPT> <REST>` (Devanagari, Bengali, Gurmukhi, Gujarati, Oriya, Tamil, Telugu, Kannada,
  Malayalam, Sinhala) maps to atom `<REST>` in realization `<Script>`. Names that would map two
  characters to one (realization, atom) pair are left unmapped. Decimal digits belong to the digit
  family. The tables in `transform.json` are authoritative; the rule only explains them.
- **Meetei Mayek.** Letters share Brahmic atoms where the Unicode names list gives a clear phonetic
  value. The eight lonsum (final) letters have their own atoms (`LONSUM KA`, ...) in the `Mtei`
  realization.
- **Dandas.** U+0964 and U+0965 are script-neutral atoms: they are written without a marker, decode
  to themselves in every state, and reset the `indic` state to `Deva` in the encoder and the decoder.
- **Ol Chiki.** Ol Chiki letters and signs (U+1C5A..U+1C7F) are not mapped and pass through as
  plain text. Ol Chiki digits (U+1C50..U+1C59) are in the digit family like all other digits.
- **Arabic script.** Every letter named `ARABIC LETTER ...` in U+0600..U+06FF, U+0750..U+077F and
  U+0870..U+08FF has its own atom in the `ARAB` realization. This includes the eight canonical
  hamza/madda composites `آ أ ؤ إ ئ ۀ ۂ ۓ`. Decomposed sequences (letter + combining hamza) are not
  changed.
- **Kana.** A hiragana and a katakana character with the same name after the script word (e.g.
  `LETTER A`) share an atom; `Hira` and `Kana` are the realizations. Kana without a counterpart are
  not mapped.

### 4.3 Decoding (`unmap`)

The decoder scans the wire left to right with the same per-family state, initialised as above:

```
U+E000 followed by six nibble symbols:  output chr(value) if value is in U+E000..U+F8FF, else error
marker of family F for realization r:   state[F] = r; output nothing
neutral atom of family F:               output its source; state[F] = initial[F]
other atom a of family F:               output render(F, state[F], a), error if there is none
nibble or reserved symbol:              error
anything else:                          output it unchanged
```

`render` also contains spellings the encoder never writes. The decoder accepts them so that every
wire of the format decodes: Ol Chiki atoms under `Olck`, the lonsum letters as Brahmic atoms under
`MteiFinal`, and the Arabic composites as a base letter under `HAMZA_ABOVE`, `HAMZA_BELOW` or
`MADDAH_ABOVE`. Private-use code points that are not symbols (for example U+E3D6..U+F8FF, which the
encoder always escapes) are output unchanged.

**Errors.** An escape not followed by six nibbles, a nibble or reserved symbol outside an escape,
and an atom with no rendering in the current state (for example a kana atom before any kana marker)
are malformed wires. A malformed wire cannot come from `encode`; it can come from arbitrary model
output. In strict mode the reference raises an error. In replace mode it outputs U+FFFD:

- one U+FFFD for an escape character that does not start a valid escape (scanning resumes at the
  next character);
- one U+FFFD for a complete escape whose value lies outside U+E000..U+F8FF;
- one U+FFFD for each offending nibble, reserved symbol or atom.

## 5. Leading-space rule

```
lead(text) = "␠" if text != "" and (text[0] == U+0020
                                     or (LM(text[0]) and not NOSPACE(text[0])))
             else ""
strip(wire) = wire[1:] if wire starts with U+0020 else wire
```

- `LM(c)`: `c` is in `leading_space.letter_mark_ranges`, i.e. its General_Category is L* or M* in
  **Unicode 15.0** (frozen; a newer Unicode database must not be used).
- `NOSPACE(c)`: `c` is in one of the 21 `leading_space.nospace_ranges`: the blocks of Thai, Lao,
  Khmer (and Khmer Symbols), Hiragana, Katakana (and its extensions, halfwidth forms and the kana
  supplements), the CJK ideograph blocks and planes 2 and 3, and the letters of CJK Symbols and
  Punctuation. Myanmar and Hangul are not in the list: they get the space.
- `lead` is evaluated on the original text (before escaping). `strip` runs on the decoded wire,
  before `unmap`.

**Why this is lossless.** No pass maps any character to U+0020, and U+0020 is never part of an escape
or an atom, so the mapped text starts with U+0020 exactly when the input does. If the input starts
with U+0020, `lead` always adds one, and `strip` removes exactly that one. If it does not, the wire
starts with U+0020 exactly when `lead` added one, and `strip` removes it. In every case
`unmap(strip(wire(text))) == text`. The decoder never evaluates `LM` or `NOSPACE`.

## 6. Byte-level BPE

`tokenizer.json` is standard `tokenizers` JSON and can be loaded by `tokenizers` 0.22 or later:

1. **Split.** The `Split` pre-tokenizer regex (`behavior: Isolated`). It is the familiar o200k-style
   pattern extended with code-point classes for the wire alphabet: letter-like symbols
   U+E000..U+E027, U+E06C..U+E1FF and U+E20A..U+F8FF; digit-set markers U+E028..U+E06B; digit atoms
   U+E200..U+E209. It also keeps ZWNJ/ZWJ (U+200C/U+200D) inside words that consist of symbols and
   marks, and cuts runs of digits into groups of three, aligned from the right. Its `\p{L}`, `\p{N}`,
   `\p{M}` and `\s` classes are evaluated by the regex engine (Oniguruma in `tokenizers`). The
   reference ids were produced with **Unicode 16.0** classes (`tokenizers` 0.22 and 0.23). Older
   engines with older Unicode tables can split characters added in Unicode 15.0 and 16.0 differently.
2. **ByteLevel** mapping of each piece's UTF-8 bytes to the 256-symbol byte alphabet (no prefix
   space, no regex).
3. **BPE** with the merges in rank order; no dropout, no unknown token, no byte fallback.

No normalizer, no post-processor, and nothing is added at the start or end.

## 7. Decoding ids

1. Map each id to its token's bytes (inverse ByteLevel). Reserved ids give U+FFFD's UTF-8 bytes in
   replace mode and an error in strict mode. Ids outside the vocabulary are always an error.
2. Decode the concatenated bytes as UTF-8. Replace mode substitutes U+FFFD per maximal invalid
   subsequence; this is what both Python's `"replace"` handler and `tokenizers`' lossy decoding do.
3. `strip` one leading U+0020, then `unmap` (section 4.3).

## 8. Streaming

A streaming decoder for one run keeps:

1. the incomplete UTF-8 bytes at the end of the input so far;
2. whether the run's first character has been seen (for `strip`);
3. the per-family states;
4. an escape sequence cut at the end of the input (at most six characters after U+E000).

It emits each character as soon as it is final. A character is held back only while it is an
incomplete UTF-8 sequence or part of an escape that may still be completed. The leading space is
dropped when the run's first character arrives. At the end of the run, everything held back is flushed (in strict mode an
incomplete sequence is an error), and the decoder resets to the initial state. For every split of a
run's ids, the concatenated output equals the full decode. The reference is
`indic_shift.StreamDecoder`.

## 9. Serving contract

- **One run per piece of text.** Encode each piece of text between two of a model's control tokens
  with its own `encode`, from the initial state and with its own leading space. Decode each piece of
  generated text the same way: strip one leading U+0020 at the start of the piece and carry the state
  from the start of the piece.
- **Continuations.** If a prompt ends inside a run (assistant prefill, resumed generation), encode
  that run once with all of its text so far. Never encode a continuation separately and append its
  ids.
- **Incremental detokenizers.** A detokenizer that decodes a sliding window of recent ids on its
  own (common in serving stacks) loses the script state and the leading space. It must decode with
  the semantics of section 8, for example by keeping one `StreamDecoder` per sequence and resetting
  it at control tokens.
- **Reserved ids.** Mask ids 0..255 when sampling (a model trained on Indic Shift never sees them).

## 10. Acceptance tests

- `tests/golden/golden.jsonl`: 257 hand-written texts (all 22 scheduled languages of India,
  Sinhala, English, code, mixed and edge cases) with their exact ids. The sha256 over the JSON id
  lists, one list per line in file order (`json.dumps(ids) + "\n"`, Python's default separators):
  - 262K: `1a1a430b7881d274bc74b647dfd2297da8b487ba35bf100c4fafe2f962afcdac`
  - 131K: `0663b5af8ff16aa3ef644386f8f92ca13e6809dcef4c4a0c3fa0f5a41311db73`
- Every code point, alone and in context, must round-trip (`tests/test_lead_space.py`).
- `tools/verify/compare.py` compares a port with this package on any JSON Lines corpus, on every
  code point in three contexts, and on adversarial strings and id sequences (decode only). A port is
  plugged in as a small adapter file.

## 11. Reproducing the data

- `python tools/build_transform.py --check` (on CPython 3.12, whose `unicodedata` is Unicode 15.0.0)
  regenerates `transform.json` from the rules above and checks that it is byte-identical.
- `python tools/make_golden.py --check` recomputes the golden ids.
