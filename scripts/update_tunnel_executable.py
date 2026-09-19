#!/usr/bin/env python3
from pathlib import Path

CONFIG = Path.home() / ".cloudflared" / "opportunityops.yml"
HOST = "executable.creatorcore.ai"
SERVICE = "http://192.168.1.4:8769"
MARKER = "  - hostname: voiceops.creatorcore.ai"
ENTRY = f"  - hostname: {HOST}\n    service: {SERVICE}\n"

text = CONFIG.read_text(encoding="utf-8")
if HOST in text:
    print("already present")
else:
    if MARKER not in text:
        raise SystemExit("marker not found")
    CONFIG.write_text(text.replace(MARKER, ENTRY + MARKER, 1), encoding="utf-8")
    print("tunnel updated")
