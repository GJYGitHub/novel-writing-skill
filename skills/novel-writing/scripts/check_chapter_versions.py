"""Record or check local chapter file fingerprints without exposing prose."""

import argparse
import hashlib
import json
from pathlib import Path
import re


def fingerprint(root, source):
    relative = Path(source)
    result = {"path": source}
    if relative.anchor or ".." in relative.parts:
        return {**result, "status": "invalid_path"}

    try:
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            return {**result, "status": "invalid_path"}
        digest = hashlib.sha256()
        with path.open("rb") as chapter:
            for block in iter(lambda: chapter.read(65536), b""):
                digest.update(block)
    except FileNotFoundError:
        return {**result, "status": "missing"}
    except (OSError, ValueError, RuntimeError):
        return {**result, "status": "unreadable"}
    return {**result, "status": "recorded", "sha256": digest.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    modes = parser.add_subparsers(dest="mode", required=True)
    snapshot = modes.add_parser("snapshot")
    snapshot.add_argument("paths", nargs="+")
    check = modes.add_parser("check")
    check.add_argument("--expect", nargs=2, action="append", required=True,
                       metavar=("PATH", "SHA256"))
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        parser.error("--root must be an existing project directory")

    if args.mode == "snapshot":
        results = [fingerprint(root, source) for source in args.paths]
    else:
        if any(not re.fullmatch(r"[0-9a-fA-F]{64}", digest)
               for _, digest in args.expect):
            parser.error("each SHA256 must contain exactly 64 hexadecimal digits")
        results = []
        for source, expected in args.expect:
            entry = fingerprint(root, source)
            if entry["status"] == "recorded":
                entry["status"] = (
                    "unchanged" if entry["sha256"] == expected.lower() else "changed"
                )
            results.append(entry)

    print(json.dumps(results))
    return int(any(entry["status"] not in {"recorded", "unchanged"} for entry in results))


if __name__ == "__main__":
    raise SystemExit(main())
