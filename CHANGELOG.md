# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the package uses
[Semantic Versioning](https://semver.org/). Token ids never change within a major version.

## [1.0.0] - unreleased

### Added

- Tokenizers `indic-shift-262k` (262,144 ids) and `indic-shift-131k` (131,072 ids), bundled in the
  package with pinned sha256 values.
- Python API: `indic_shift.load`, `Tokenizer.encode` / `encode_batch` / `decode` / `decode_batch`,
  `StreamDecoder` for incremental decoding, `Transform`, `data_path`, `available`.
- Hugging Face `transformers` integration: `indic_shift.hf.IndicShiftTokenizer`.
- Command line tool `indic-shift encode | decode | inspect`.
- `SPEC.md` for ports, golden test vectors, and verification tools under `tools/`.
