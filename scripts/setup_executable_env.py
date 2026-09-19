#!/usr/bin/env python3
"""Bootstrap ~/.config/inneros/executable.env on deploy host. Run on .4 only."""
from __future__ import annotations

import os
import pathlib
import sys


def upsert(lines: list[str], key: str, val: str) -> list[str]:
    for i, line in enumerate(lines):
        if line.startswith(key + "="):
            lines[i] = f"{key}={val}"
            return lines
    lines.append(f"{key}={val}")
    return lines


def main() -> int:
    api_key = os.environ.get("ASSEMBLYAI_API_KEY", "").strip()
    if not api_key:
        print("ERROR: set ASSEMBLYAI_API_KEY in environment before running", file=sys.stderr)
        return 1

    p = pathlib.Path.home() / ".config/inneros/executable.env"
    voiceops = pathlib.Path.home() / ".config/inneros/voiceops.env"
    if p.exists():
        lines = p.read_text(encoding="utf-8").splitlines()
    elif voiceops.exists():
        lines = voiceops.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    lines = upsert(lines, "ASSEMBLYAI_API_KEY", api_key)
    lines = upsert(lines, "VOICEOPS_ENABLE_LIVE_ASSEMBLYAI", "true")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    p.chmod(0o600)
    print("executable.env ready (AssemblyAI enabled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
