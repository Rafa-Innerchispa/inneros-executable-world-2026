#!/usr/bin/env python3
import json
import sys

sys.path.insert(0, "/home/rlopez/inneros/inneros_core/platform")
from inneros_core_runtime.agents import ag44_cloud_deployer as ag44

creds = ag44._cloudflare_credentials("creatorcore.ai")
zone = ag44._get_zone("creatorcore.ai", creds=creds)
print("zone_id", zone["id"], "zone", zone["name"])
for host in ["executable", "executable.creatorcore.ai", "fieldops.creatorcore.ai"]:
    recs = ag44._list_dns_records(zone["id"], host if "." in host else f"{host}.creatorcore.ai", None, creds=creds)
    print(host, len(recs), json.dumps(recs, indent=2)[:500])
