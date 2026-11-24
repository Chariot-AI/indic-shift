"""Exactness checks for indic_shift, optionally against a reference implementation.

Corpus mode (texts from JSON Lines files, split into shards):

    python tools/verify/compare.py --jsonl a.jsonl b.jsonl --shard 3 --num-shards 64 \\
        --reference ref=path/to/adapter.py:make --out shard3.json

Other inputs: ``--all-code-points`` (every scalar value in three contexts, sharded by code point)
and ``--adversarial`` (tools/verify/adversarial.py: edge cases, random mixtures, and id sequences
that no text encodes to, for decode-only comparisons).

A reference adapter is a Python file with a factory ``make(size) -> obj`` where ``obj.encode(text)``
returns ids and ``obj.decode(ids)`` returns text (and may raise ``ValueError`` on malformed input).
Several references can be given (``--reference label=file:factory``).

For every text and size the script checks: ids equal the reference's, ``encode_batch`` equals
``encode``, ``decode(encode(t)) == t`` (both error modes), the StreamDecoder (one id at a time)
equals ``decode``, and the reference decodes our ids to the same text. It also writes a sha256
digest of all ids so that runs on different Python / tokenizers versions can be compared.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adversarial  # noqa: E402

import indic_shift  # noqa: E402


def load_reference(spec: str):
    label, _, target = spec.partition("=")
    path, _, factory = target.rpartition(":")
    mod_spec = importlib.util.spec_from_file_location(f"_ref_{label}", path)
    if mod_spec is None or mod_spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    mod = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(mod)
    return label, getattr(mod, factory)


def corpus(paths: list[str], field: str, shard: int, num_shards: int):
    g = 0
    for p in paths:
        with open(p, encoding="utf-8") as f:
            for line in f:
                if g % num_shards == shard:
                    obj = json.loads(line)
                    yield f"{Path(p).name}:{obj.get('id', g)}", obj[field]
                g += 1


def code_point_texts(shard: int, num_shards: int):
    for cp in range(shard, 0x110000, num_shards):
        if 0xD800 <= cp <= 0xDFFF:
            continue
        c = chr(cp)
        yield f"U+{cp:04X}/1", c
        yield f"U+{cp:04X}/2", c + " x1"
        yield f"U+{cp:04X}/3", "a" + c + "ক" + c


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--jsonl", nargs="+")
    src.add_argument("--all-code-points", action="store_true")
    src.add_argument("--adversarial", action="store_true")
    ap.add_argument("--field", default="text")
    ap.add_argument("--sizes", nargs="+", default=["262k", "131k"])
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--num-shards", type=int, default=1)
    ap.add_argument("--reference", action="append", default=[], help="label=adapter.py:factory")
    ap.add_argument("--no-stream", action="store_true", help="skip the StreamDecoder check")
    ap.add_argument("--max-examples", type=int, default=20)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    refs = [load_reference(s) for s in args.reference]
    if args.jsonl:
        items = list(corpus(args.jsonl, args.field, args.shard, args.num_shards))
    elif args.all_code_points:
        items = list(code_point_texts(args.shard, args.num_shards))
    else:
        items = [(f"adv/{i}", t) for i, t in enumerate(adversarial.texts(seed=args.shard))]

    import tokenizers

    result: dict = {
        "python": platform.python_version(),
        "tokenizers": tokenizers.__version__,
        "indic_shift": indic_shift.__version__,
        "items": len(items),
        "shard": args.shard,
        "num_shards": args.num_shards,
        "sizes": {},
    }
    t0 = time.time()
    for size in args.sizes:
        tok = indic_shift.load(size)
        ref_objs = [(label, factory(size)) for label, factory in refs]
        r: dict = {
            "tokens": 0,
            "roundtrip_fail": 0,
            "strict_roundtrip_fail": 0,
            "batch_mismatch": 0,
            "stream_mismatch": 0,
            "reserved_ids_emitted": 0,
            "reference": {
                label: {"ids_equal": 0, "ids_differ": 0, "ref_decode_equal": 0, "ref_decode_differ": 0, "examples": []}
                for label, _ in ref_objs
            },
            "examples": [],
        }
        digest = hashlib.sha256()
        texts = [t for _, t in items]
        batch_ids: list[list[int]] = []
        for i in range(0, len(texts), 512):
            batch_ids.extend(tok.encode_batch(texts[i : i + 512]))
        encodings = []
        for (key, text), bids in zip(items, batch_ids):
            ids = tok.encode(text)
            encodings.append(ids)
            digest.update(json.dumps(ids).encode())
            r["tokens"] += len(ids)
            if bids != ids:
                r["batch_mismatch"] += 1
            if ids and min(ids) < 256:
                r["reserved_ids_emitted"] += 1
            ok = tok.decode(ids) == text
            if not ok:
                r["roundtrip_fail"] += 1
                if len(r["examples"]) < args.max_examples:
                    r["examples"].append({"key": key, "problem": "roundtrip", "text": text[:200]})
            try:
                strict_ok = tok.decode(ids, errors="strict") == text
            except ValueError:
                strict_ok = False
            if not strict_ok:
                r["strict_roundtrip_fail"] += 1
            if not args.no_stream:
                dec = tok.stream_decoder()
                streamed = "".join(dec.step(t) for t in ids) + dec.flush()
                if streamed != text:
                    r["stream_mismatch"] += 1
                    if len(r["examples"]) < args.max_examples:
                        r["examples"].append({"key": key, "problem": "stream", "text": text[:200]})
            for label, ref in ref_objs:
                rr = r["reference"][label]
                rids = ref.encode(text)
                if list(rids) == ids:
                    rr["ids_equal"] += 1
                else:
                    rr["ids_differ"] += 1
                    if len(rr["examples"]) < args.max_examples:
                        rr["examples"].append(
                            {"key": key, "text": text[:200], "ours": ids[:40], "reference": list(rids)[:40]}
                        )
                try:
                    rdec = ref.decode(ids)
                except Exception:
                    rdec = None
                rr["ref_decode_equal" if rdec == text else "ref_decode_differ"] += 1
        r["ids_sha256"] = digest.hexdigest()

        if args.adversarial:
            seqs = adversarial.id_sequences(encodings, tok.vocab_size, 256, seed=args.shard)
            d = {
                "sequences": len(seqs),
                "stream_mismatch": 0,
                "strict_raised": 0,
                "reference": {
                    label: {"equal": 0, "differ": 0, "ref_raised": 0, "ref_raised_strict_also": 0, "examples": []}
                    for label, _ in ref_objs
                },
            }
            dd = hashlib.sha256()
            for seq in seqs:
                ours = tok.decode(seq)
                dd.update(ours.encode("utf-8", "surrogatepass"))
                try:
                    tok.decode(seq, errors="strict")
                    strict_raised = False
                except ValueError:
                    strict_raised = True
                d["strict_raised"] += strict_raised
                dec = tok.stream_decoder()
                if "".join(dec.step(t) for t in seq) + dec.flush() != ours:
                    d["stream_mismatch"] += 1
                for label, ref in ref_objs:
                    rd = d["reference"][label]
                    try:
                        theirs = ref.decode(seq)
                    except ValueError:
                        rd["ref_raised"] += 1
                        rd["ref_raised_strict_also"] += strict_raised
                        continue
                    if theirs == ours:
                        rd["equal"] += 1
                    else:
                        rd["differ"] += 1
                        if len(rd["examples"]) < args.max_examples:
                            rd["examples"].append({"ids": seq, "ours": ours, "reference": theirs})
            d["decoded_sha256"] = dd.hexdigest()
            r["decode_only"] = d
        result["sizes"][size] = r
    result["seconds"] = round(time.time() - t0, 1)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {
        s: {k: v for k, v in r.items() if k not in ("examples", "reference", "decode_only")}
        for s, r in result["sizes"].items()
    }
    print(json.dumps({"items": len(items), "seconds": result["seconds"], **summary}))


if __name__ == "__main__":
    main()
