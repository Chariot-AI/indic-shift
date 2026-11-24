"""Command line: ``indic-shift encode|decode|inspect`` (or ``python -m indic_shift``)."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__, load


def _read_text(args: argparse.Namespace) -> str:
    if args.text is not None:
        return args.text
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="indic-shift", description="Indic Shift tokenizer")
    ap.add_argument("--version", action="version", version=f"indic-shift {__version__}")
    ap.add_argument("-t", "--tokenizer", default="262k", help="262k (default) or 131k")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("encode", help="print the ids of TEXT (or stdin) as a JSON list")
    p.add_argument("text", nargs="?")
    p = sub.add_parser("decode", help="print the text of ids (JSON list or integers)")
    p.add_argument("ids", nargs="*")
    p = sub.add_parser("inspect", help="show the transformed text and the tokens of TEXT (or stdin)")
    p.add_argument("text", nargs="?")
    args = ap.parse_args(argv)

    tok = load(args.tokenizer)
    if args.command == "encode":
        print(json.dumps(tok.encode(_read_text(args))))
    elif args.command == "decode":
        raw = " ".join(args.ids) if args.ids else sys.stdin.read()
        raw = raw.strip()
        ids = json.loads(raw) if raw.startswith("[") else [int(x) for x in raw.replace(",", " ").split()]
        sys.stdout.write(tok.decode(ids))
        sys.stdout.write("\n")
    else:
        text = _read_text(args)
        ids = tok.encode(text)
        print(f"{tok.name}: {len(ids)} tokens, {len(text)} characters")
        print("wire: " + " ".join(tok.transform.describe(text)))
        names = tok.transform._symbol_names
        for i in ids:
            piece = tok._table()[i].decode("utf-8", "replace")
            shown = "".join(f"<{names[c]}>" if c in names else c for c in piece)
            print(f"{i:>8}  {shown!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
