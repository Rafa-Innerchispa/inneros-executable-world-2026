#!/usr/bin/env python3
"""Fix executable.creatorcore.ai DNS via AG-44 (InnerOS platform integration on .4)."""
from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.parse

sys.path.insert(0, "/home/rlopez/inneros/inneros_core/platform")
from inneros_core_runtime.agents import ag44_cloud_deployer as ag44

HOST = "executable.creatorcore.ai"
ZONE = "creatorcore.ai"
TUNNEL = "6fb8ceab-a17e-41b3-872d-e26ef2d1383f.cfargotunnel.com"


def list_records() -> list[dict]:
    creds = ag44._cloudflare_credentials(ZONE)
    zone = ag44._get_zone(ZONE, creds=creds)
    qs = urllib.parse.urlencode({"per_page": "100", "search": "executable"})
    data = ag44._cf_request("GET", f"/zones/{zone['id']}/dns_records?{qs}", creds=creds)
    return list(data.get("result") or [])


def dig_check() -> str:
    proc = subprocess.run(
        ["dig", "+short", HOST, "@1.1.1.1"],
        capture_output=True,
        text=True,
        check=False,
    )
    return (proc.stdout or proc.stderr or "").strip()


def main() -> int:
    print("before_records:", json.dumps(list_records(), indent=2))

    # Ensure single proxied CNAME like fieldops/voiceops
    ag44.cloudflare_dns_delete(HOST, record_type="", zone_name=ZONE, dry_run=False)
    upsert = ag44.cloudflare_dns_upsert(
        HOST,
        "CNAME",
        TUNNEL,
        proxied=True,
        zone_name=ZONE,
        dry_run=False,
    )
    print("upsert:", json.dumps(upsert, indent=2))

    ingress = ag44.cloudflare_tunnel_ingress_status(HOST)
    print("ingress:", json.dumps(ingress, indent=2))

    for attempt in range(6):
        time.sleep(10)
        answer = dig_check()
        print(f"dig_attempt_{attempt + 1}:", answer or "NXDOMAIN/empty")
        if answer:
            health = ag44.cloudflare_hostname_health_check(HOST, path="/healthz")
            print("health:", json.dumps(health, indent=2))
            return 0 if health.get("ok") else 2

    print("DNS still not visible from 1.1.1.1 after retries")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
