#!/usr/bin/env python3
"""
Patch TruClaw policy for customer_service_agent:
  1. Add modify_cart + access_cart_information to safeTools
  2. Add approve_discount toolThreshold (field=value, safeBelow=10)

Run from the truclaw_adk_final directory:
  python3 scripts/update_policy_customer_service.py
"""

import json
from google.cloud import storage

BUCKET = "truclaw-medical-reports"
BLOB   = "truclaw/policies/customer_service_agent/TruClaw-Policies.json"

# Tools that need no auth — pure cart reads/writes with no financial side-effect
CART_SAFE_TOOLS = ["access_cart_information", "modify_cart"]

# Threshold rule: approve_discount is safe when value < 10 (MAX_DISCOUNT_RATE)
APPROVE_DISCOUNT_THRESHOLD = {
    "field": "value",          # the arg name in approve_discount(discount_type, value, reason)
    "safeBelow": 10,           # matches MAX_DISCOUNT_RATE in tools.py
    "dailyLimit": None,        # no cumulative cap yet
    "weeklyLimit": None,
}


def main():
    client = storage.Client()
    blob = client.bucket(BUCKET).blob(BLOB)

    policy = json.loads(blob.download_as_text())
    print(f"Loaded policy version={policy.get('version')} agentId={policy.get('agentId')}")

    # 1. Add cart tools to safeTools (idempotent)
    safe_set = set(policy.get("safeTools", []))
    added = []
    for t in CART_SAFE_TOOLS:
        if t not in safe_set:
            safe_set.add(t)
            added.append(t)
    policy["safeTools"] = sorted(safe_set)

    # 2. Remove cart tools from alwaysDangerousTools / unclassified if present
    policy["alwaysDangerousTools"] = [
        t for t in policy.get("alwaysDangerousTools", [])
        if t not in safe_set
    ]
    policy["unclassified"] = [
        t for t in policy.get("unclassified", [])
        if t not in safe_set
    ]

    # 3. Add approve_discount threshold
    thresholds = policy.setdefault("toolThresholds", {})
    thresholds["approve_discount"] = APPROVE_DISCOUNT_THRESHOLD

    print(f"Added to safeTools: {added or '(already present)'}")
    print(f"toolThresholds[approve_discount] = {APPROVE_DISCOUNT_THRESHOLD}")

    updated = json.dumps(policy, indent=2, sort_keys=True)
    blob.upload_from_string(updated, content_type="application/json")
    print(f"Uploaded gs://{BUCKET}/{BLOB}")
    print("Done. Restart/redeploy customer-service to pick up new policy.")


if __name__ == "__main__":
    main()
