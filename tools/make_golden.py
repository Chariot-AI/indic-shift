"""Fill in (or check) the golden token ids in ``tests/golden/golden.jsonl``.

Each line holds ``lang``, ``text`` and the ids of both tokenizers. The texts were written for this
repository (no third-party data). Run after adding texts:

    python tools/make_golden.py            # rewrite the ids from the installed/importable package
    python tools/make_golden.py --check    # fail if any stored id differs

The printed digests (sha256 over the JSON ids, one line per text) are the acceptance values that
ports can compare against (see SPEC.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import indic_shift

GOLDEN = Path(__file__).resolve().parent.parent / "tests" / "golden" / "golden.jsonl"
SIZES = ("262k", "131k")


# Invisible and private-use characters are written as JSON escapes so that the file stays readable.
_INVISIBLE = re.compile(
    "[\\x00-\\x08\\x0b-\\x1f\\x7f-\\x9f\\u00a0\\u00ad\\u200b-\\u200f\\u2028-\\u202e\\u2060-\\u206f"
    "\\u3000\\ue000-\\uf8ff\\ufeff\\ufff0-\\uffff\\U000f0000-\\U0010ffff]"
)


def dumps(obj: dict) -> str:
    return _INVISIBLE.sub(lambda m: json.dumps(m.group())[1:-1], json.dumps(obj, ensure_ascii=False))


def digest(rows: list[dict], size: str) -> str:
    h = hashlib.sha256()
    for r in rows:
        h.update((json.dumps(r[f"ids_{size}"]) + "\n").encode())
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines() if line.strip()]
    bad = 0
    for size in SIZES:
        tok = indic_shift.load(size)
        for r in rows:
            ids = tok.encode(r["text"])
            if args.check and r.get(f"ids_{size}") != ids:
                bad += 1
                print(f"{size} differs: {r['lang']} {r['text'][:40]!r}")
            r[f"ids_{size}"] = ids
    if args.check:
        if bad:
            raise SystemExit(f"{bad} golden entries differ")
    else:
        with GOLDEN.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(
                    dumps({"lang": r["lang"], "text": r["text"], "ids_262k": r["ids_262k"], "ids_131k": r["ids_131k"]})
                    + "\n"
                )
    print(f"{len(rows)} texts; " + "; ".join(f"{s}: sha256 {digest(rows, s)}" for s in SIZES))


if __name__ == "__main__":
    main()
