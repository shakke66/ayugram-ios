from __future__ import annotations

import argparse
from pathlib import Path


def _suppressed_branch(source: str) -> str:
    marker = "if AyuGramHooks.shouldSuppressReadReceipts?() == true {"
    start = source.find(marker)
    if start < 0:
        return ""
    end = source.find("} else {", start)
    return source[start:end] if end >= 0 else source[start:]


def validate_suppressed_push(source: str) -> list[str]:
    branch = _suppressed_branch(source)
    errors: list[str] = []
    if not branch:
        return ["suppressed read-receipt branch is missing"]
    if "signal = .complete()" in branch:
        errors.append("bare .complete() leaves the Push operation pending")
    if "confirmSynchronizedIncomingReadState(peerId)" not in branch:
        errors.append("suppressed Push is not confirmed locally")
    if "postbox.transaction" not in branch:
        errors.append("suppressed Push completion is not transaction-backed")
    if "synchronizePeerReadState(" in branch:
        errors.append("suppressed Push still calls the network synchronizer")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    errors = validate_suppressed_push(args.path.read_text(encoding="utf-8"))
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
