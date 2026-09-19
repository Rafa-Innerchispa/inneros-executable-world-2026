#!/usr/bin/env python3
"""Provision executable.creatorcore.ai using InnerOS AG-44 Cloudflare integration."""
from __future__ import annotations

import json
import sys

PLATFORM = "/home/rlopez/inneros/inneros_core/platform"
sys.path.insert(0, PLATFORM)

from inneros_core_runtime.agents import ag44_cloud_deployer as ag44  # noqa: E402

HOSTNAME = "executable.creatorcore.ai"
ZONE = "creatorcore.ai"
TUNNEL_CNAME = "6fb8ceab-a17e-41b3-872d-e26ef2d1383f.cfargotunnel.com"
SERVICE = "http://192.168.1.4:8769"


def main() -> int:
    ref = ag44.cloudflare_dns_upsert(
        "fieldops.creatorcore.ai",
        "A",
        "172.67.212.1",
        proxied=True,
        zone_name=ZONE,
        dry_run=True,
    )
    print("reference_dry_run_fieldops:", json.dumps(ref, indent=2))

    dns = ag44.cloudflare_dns_upsert(
        HOSTNAME,
        "CNAME",
        TUNNEL_CNAME,
        proxied=True,
        zone_name=ZONE,
        dry_run=False,
    )
    print("dns_result:", json.dumps(dns, indent=2))
    if not dns.get("ok"):
        return 1

    health = ag44.cloudflare_hostname_health_check(HOSTNAME)
    print("health:", json.dumps(health, indent=2))
    return 0 if health.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
