# Contributing

Issues and pull requests are welcome.

- **Ids are frozen.** The tokenizer files and the transform tables in `src/indic_shift/data/` never
  change within a major version. Changes that would alter any id for any input are out of scope for
  1.x.
- **Development setup.**

  ```bash
  python -m venv .venv && . .venv/bin/activate
  pip install -e ".[dev,transformers]"
  pytest
  ruff check . && ruff format --check . && mypy
  ```

- **Golden vectors.** `tests/golden/golden.jsonl` holds texts written for this repository with their
  exact ids. Add texts there (with `"ids_262k": [], "ids_131k": []`) and run
  `python tools/make_golden.py`; never add text you do not have the right to publish.
- **Regenerating the transform tables** needs CPython 3.12 (Unicode 15.0):
  `python tools/build_transform.py --check` must report the file as up to date.
