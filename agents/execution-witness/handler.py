"""Minimal EdgeOne witness handler — accepts sanitized execution receipts only.

Deploy under EdgeOne Pages / Edge Functions. Never receives secrets.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WitnessHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({"ok": True, "witness": "inneros-executable-world", "ts": _now_iso()})
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        receipt = payload.get("receipt") or {}
        response = {
            "witnessed": True,
            "received_at": _now_iso(),
            "event_type": payload.get("event_type"),
            "session_id": receipt.get("session_id"),
            "evidence_sha256": receipt.get("evidence_sha256"),
            "pages_project": payload.get("pages_project"),
        }
        body = json.dumps(response, ensure_ascii=False)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))


def main() -> None:
    port = int(__import__("os").environ.get("PORT", "8780"))
    server = HTTPServer(("0.0.0.0", port), WitnessHandler)
    print(f"execution-witness listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
