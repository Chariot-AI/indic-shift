"""Check built distributions: python tools/check_dist.py dist/

* the wheel is pure Python (py3-none-any), below 20 MB, and contains exactly the package files;
* every bundled data file in the wheel matches the sha256 pinned in ``_registry.py``;
* the sdist contains the sources, tests, tools, docs and license files.
"""

from __future__ import annotations

import hashlib
import re
import sys
import tarfile
import zipfile
from pathlib import Path

MAX_WHEEL_BYTES = 20 * 1024 * 1024
WHEEL_FILES = {
    "indic_shift/__init__.py",
    "indic_shift/__main__.py",
    "indic_shift/_registry.py",
    "indic_shift/_tokenizer.py",
    "indic_shift/_transform.py",
    "indic_shift/hf.py",
    "indic_shift/py.typed",
    "indic_shift/data/indic-shift-262k.tokenizer.json",
    "indic_shift/data/indic-shift-131k.tokenizer.json",
    "indic_shift/data/transform.json",
}
SDIST_REQUIRED = {
    "README.md",
    "SPEC.md",
    "CHANGELOG.md",
    "LICENSE",
    "LICENSE-UNICODE",
    "NOTICE",
    "pyproject.toml",
    "src/indic_shift/_transform.py",
    "tests/golden/golden.jsonl",
    "tools/build_transform.py",
}


def fail(msg: str) -> None:
    raise SystemExit(f"check_dist: {msg}")


def main() -> None:
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        fail(f"expected one wheel and one sdist in {dist}")
    wheel, sdist = wheels[0], sdists[0]
    if not wheel.name.endswith("-py3-none-any.whl"):
        fail(f"not a pure-Python wheel: {wheel.name}")
    if wheel.stat().st_size > MAX_WHEEL_BYTES:
        fail(f"wheel is {wheel.stat().st_size:,} bytes")
    with zipfile.ZipFile(wheel) as zf:
        names = {n for n in zf.namelist() if not n.split("/")[0].endswith(".dist-info")}
        if names != WHEEL_FILES:
            extra, missing = sorted(names - WHEEL_FILES), sorted(WHEEL_FILES - names)
            fail(f"unexpected wheel contents: extra {extra}, missing {missing}")
        registry = zf.read("indic_shift/_registry.py").decode()
        pins = dict(re.findall(r"\(\s*['\"]([\w.-]+\.json)['\"],\s*['\"]([0-9a-f]{64})['\"]", registry))
        if len(pins) != 3:
            fail(f"could not read the pinned sha256 values: {pins}")
        for fname, digest in pins.items():
            actual = hashlib.sha256(zf.read(f"indic_shift/data/{fname}")).hexdigest()
            if actual != digest:
                fail(f"{fname}: sha256 {actual} != pinned {digest}")
            print(f"{fname}: {digest}")
    with tarfile.open(sdist) as tf:
        root = tf.getnames()[0].split("/")[0]
        members = {n.removeprefix(root + "/") for n in tf.getnames()}
        missing = SDIST_REQUIRED - members
        if missing:
            fail(f"sdist is missing {sorted(missing)}")
    print(f"{wheel.name}: {wheel.stat().st_size:,} bytes; {sdist.name}: {sdist.stat().st_size:,} bytes; ok")


if __name__ == "__main__":
    main()
