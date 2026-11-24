# Indic Shift

An Indic-first byte-level BPE tokenizer with exact, reversible script sharing. Two vocabulary sizes:
262K and 131K.

```python
import indic_shift

tok = indic_shift.load("262k")  # or "131k"
ids = tok.encode("भारत एक विशाल देश है। আমি বাংলায় কথা বলি।")
assert tok.decode(ids) == "भारत एक विशाल देश है। আমি বাংলায় কথা বলি।"
```

## What it is

Indic Shift is byte-level BPE plus a small reversible text transform that runs before BPE and after
decoding:

- The Brahmic scripts share one set of letter symbols, and a script marker records which script is
  active. `क`, `ক`, `ਕ`, `ક`, `କ`, `க`, `క`, `ಕ` and `ക` all become the same letter symbol, so BPE
  can learn word pieces once for several scripts.
- Decimal digits of every script share ten digit symbols, with a marker for the digit set.
- Decoding restores the exact original text, for every Unicode string.

It covers all of Unicode (byte-level, so there are no unknown tokens) and is built for the scheduled
languages of India, English and code. Scripts that share letter symbols: Devanagari,
Bengali-Assamese, Gurmukhi, Gujarati, Odia, Tamil, Telugu, Kannada, Malayalam and Meetei Mayek.

## Install

```bash
pip install indic-shift                      # Python 3.10+, depends only on tokenizers
pip install "indic-shift[transformers]"      # optional Hugging Face transformers integration
```

The tokenizer files ship inside the package. They are checked against pinned sha256 values when they
load, and loading needs no network access. Token ids are the same on every supported Python version
and platform.

## Quick start

```python
import indic_shift

tok = indic_shift.load("262k")
ids = tok.encode("আমি বাংলায় কথা বলি")  # [26162, 211090, 5103, 20496]; no BOS/EOS is added
text = tok.decode(ids)  # "আমি বাংলায় কথা বলি"
tok.vocab_size  # 262144

batch = tok.encode_batch(["नमस्ते", "வணக்கம்", "Hello, world", "سلام"])
tok.decode_batch(batch)  # ["नमस्ते", "வணக்கம்", "Hello, world", "سلام"]
```

`indic_shift.available()` lists the bundled tokenizers (`indic-shift-131k`, `indic-shift-262k`).
There is also a small command line tool:

```bash
indic-shift encode "नमस्ते दुनिया"                    # [182427, 15851]
indic-shift decode 182427 15851                       # नमस्ते दुनिया
indic-shift -t 131k inspect "আমি বাংলায় কথা বলি"     # transformed text and tokens
```

## The leading-space rule

Read this before you build datasets or serve a model.

Every `encode()` call is one **text run**. The tokenizer adds **one** space in front of the run if
the text starts with a space, or with a letter or mark of a script that separates words with spaces
(Latin, Indic, Arabic, Cyrillic, Hangul, Myanmar, ...). It adds none if the text starts with a
digit, punctuation, a symbol or emoji, a line break or a tab, or with Thai, Lao, Khmer, Chinese or
Japanese characters. `decode()` removes exactly that one space, so the round trip is exact.

| text | space added | BPE sees (◌ = Indic Shift symbol) | tokens (262K) |
|---|---|---|---|
| `Hello` | yes | `␠Hello` | `␠Hello` |
| `␠Hello` | yes | `␠␠Hello` | `␠` `␠Hello` |
| `hello world` | yes | `␠hello␠world` | `␠hello` `␠world` |
| `日本語` | no | `日本語` | `日本語` |
| `ภาษาไทย` | no | `ภาษาไทย` | `ภาษาไทย` |
| `한국어` | yes | `␠한국어` | `␠한국어` |
| `தமிழ்` | yes | `␠◌◌◌◌◌◌` | `␠◌◌◌◌◌◌` |
| `{"a": 1}` | no | `{"a":␠◌}` | `{"` `a` `":` `␠◌` `}` |
| `\nx` | no | `\nx` | `\n` `x` |
| (empty) | no | (empty) | (none) |

What follows from the rule:

- **Encode a document whole.** Encoding chunks separately and joining their ids gives different ids,
  because each chunk gets its own leading space and starts from the initial script state.
  `encode("नमस्ते दुनिया")` is `[182427, 15851]`, but `encode("नमस्ते") + encode(" दुनिया")` is
  `[182427, 476, 15851]`.
- **Encode each piece of a prompt on its own.** If your model's prompt format puts control tokens
  between pieces of text (roles, tool calls, ...), encode each piece of text between two control
  tokens with its own `encode()` call and put your control-token ids between them. Decode each piece
  on its own too (or call `StreamDecoder.flush()` at each control token).
- **Continue a run with all of its text.** When a prompt ends inside a run (an assistant prefill, a
  resumed generation), encode that run once with all of its text so far. Never encode the
  continuation separately and append its ids.

## Streaming decode

Decoding is stateful: the active script and the leading space are carried from the start of the
run. Slices of ids decoded separately do not join up to the right text:

```python
ids = tok.encode("আমি বাংলায় কথা বলি")
tok.decode(ids[:2]) + tok.decode(ids[2:])  # "আমি বাংলায়कथा बलि"  (wrong: script and space lost)
```

For incremental output use a `StreamDecoder`. It carries the state and holds back incomplete
characters:

```python
dec = tok.stream_decoder()
for token_id in generated_ids:  # e.g. from a model, one id at a time
    print(dec.step(token_id), end="", flush=True)
print(dec.flush())  # end of the run; ready for the next run
```

Everything returned by `step` / `feed` plus `flush` equals `tok.decode(ids)`. Serving stacks with
their own incremental detokenizer (for example the sliding-window detokenizers of vLLM, SGLang or
TGI) must decode with these semantics; see [SPEC.md](https://github.com/Chariot-AI/indic-shift/blob/main/SPEC.md).

## Hugging Face transformers

```python
from indic_shift.hf import IndicShiftTokenizer

hf_tok = IndicShiftTokenizer.from_name("262k")
batch = hf_tok(["नमस्ते दुनिया", "Hello"])
hf_tok.save_pretrained("my-tokenizer")  # IndicShiftTokenizer.from_pretrained("my-tokenizer")
```

Tokens you add with `add_special_tokens` get new ids after the vocabulary, and the text between them
is encoded and decoded run by run, as described above. Offsets (`return_offsets_mapping`) are not
supported.

## Using `tokenizer.json` directly

`tokenizer.json` on its own gives the wrong ids: text must go through the transform first, and the
decoded text must go back through it.

```python
import indic_shift
from tokenizers import Tokenizer

transform = indic_shift.load("262k").transform
raw = Tokenizer.from_file(str(indic_shift.data_path("262k")))
wire = transform.encode("আমি বাংলায় কথা বলি")  # the transform (includes the leading space)
ids = raw.encode(wire, add_special_tokens=False).ids
assert transform.decode(raw.decode(ids)) == "আমি বাংলায় কথা বলি"
```

To port Indic Shift to another language or serving stack, see [SPEC.md](https://github.com/Chariot-AI/indic-shift/blob/main/SPEC.md). It describes the
transform, the data files and the decoding rules, and `tests/golden/golden.jsonl` has test vectors
with exact ids.

## Two sizes

| | `indic-shift-262k` | `indic-shift-131k` |
|---|---|---|
| vocabulary | 262,144 ids | 131,072 ids |
| suited to | larger models | small or latency-bound models |

The 131K tokenizer is the first part of the 262K: its 131,072 ids are the same tokens in both, its
merges are the first merges of the 262K, and both use the same transform and split rule. Any 131K id
sequence decodes to the same text with either tokenizer. The two encode a text identically whenever
the 262K encoding uses only ids below 131,072.

## How it works

1. **Escape.** Private-use characters U+E000..U+F8FF in the input are escaped, because the transform
   uses that range for its own symbols.
2. **Map.** Four passes replace characters with symbols: decimal digits (ten shared digit symbols plus
   a digit-set marker), Brahmic letters and signs (shared letter symbols plus a script marker), kana
   (shared symbols for hiragana/katakana pairs) and Arabic-script letters. A marker is written only
   when the script changes. Each pass starts in a default state (Devanagari, ASCII digits, Arabic),
   so text in the default scripts carries no markers. The danda `।` and double danda `॥` belong to
   every Brahmic script and return the pass to its default state.
3. **Leading space** (see above), then byte-level BPE. The split rule keeps each Indic word together
   and cuts long numbers into groups of three digits, aligned from the right.

Decoding inverts each step. Each step is lossless, so `decode(encode(text)) == text` for every
string. The tests check this on every Unicode code point and on random text.

## Versioning

Token ids never change within a major version: `indic-shift` 1.x always gives the same ids for the
same text. The sha256 of every bundled file is pinned in the package and listed in the release notes.

## License

Apache License 2.0, for the code and the tokenizer files. See [LICENSE](https://github.com/Chariot-AI/indic-shift/blob/main/LICENSE) and [NOTICE](https://github.com/Chariot-AI/indic-shift/blob/main/NOTICE).
The transform tables are derived from the Unicode Character Database and are also covered by the
Unicode License V3 ([LICENSE-UNICODE](https://github.com/Chariot-AI/indic-shift/blob/main/LICENSE-UNICODE)).
