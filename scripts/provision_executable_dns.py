#!/usr/bin/env python3
"""Provision executable.creatorcore.ai DNS (proxied A records) via Cloudflare API."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ZONE = "creatorcore.ai"
HOSTNAME = "executable.creatorcore.ai"
IPS = ("172.67.212.1", "104.21.53.103")


def api(method: str, path: str, payload: dict | None = None) -> dict:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set CLOUDFLARE_API_TOKEN")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if not body.get("success"):
        raise RuntimeError(body)
    return body


def zone_id() -> str:
    body = api("GET", f"/zones?name={ZONE}")
    result = body.get("result") or []
    if not result:
        raise SystemExit(f"Zone not found: {ZONE}")
    return result[0]["id"]


def upsert_a(zid: str, ip: str) -> None:
    existing = api("GET", f"/zones/{zid}/dns_records?type=A&name={HOSTNAME}")
    for rec in existing.get("result") or []:
        if rec.get("content") == ip:
            print(f"exists A {ip}")
            return
    api(
        "POST",
        f"/zones/{zid}/dns_records",
        {
            "type": "A",
            "name": HOSTNAME,
            "content": ip,
            "proxied": True,
            "ttl": 1,
        },
    )
    print(f"created A {ip}")


def main() -> int:
    try:
        zid = zone_id()
        for ip in IPS:
            upsert_a(zid, ip)
        print(f"DNS ready for {HOSTNAME}")
        return 0
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8", errors="replace"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
