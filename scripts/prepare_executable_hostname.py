#!/usr/bin/env python3
import json
import sys

sys.path.insert(0, "/home/rlopez/inneros/inneros_core/platform")
from inneros_core_runtime.agents import ag44_cloud_deployer as ag44

HOST = "executable.creatorcore.ai"
TUNNEL = "6fb8ceab-a17e-41b3-872d-e26ef2d1383f.cfargotunnel.com"

result = ag44.cloudflare_prepare_hostname(
    HOST,
    dns_type="CNAME",
    dns_content=TUNNEL,
    proxied=True,
    ensure_waf_skip=False,
    health_path="/healthz",
    dry_run=False,
)
print(json.dumps(result, indent=2))
