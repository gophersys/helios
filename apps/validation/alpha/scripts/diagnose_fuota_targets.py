#!/usr/bin/env python3
"""Diagnose CoreCloud FUOTA target handling.

Creates test plans with different flag combinations (B, BM, BD, BMD)
and queries them back to see how CoreCloud stores the targets.
This tells us if CoreCloud strips or modifies any flags.

Usage:
    PYTHONPATH=libs/python:libs/protocols:libs python3 apps/validation/alpha/scripts/diagnose_fuota_targets.py

Requires:
    CORECLOUD_VAL_API_KEY environment variable (or .env with VAL_1_0 config)
"""

import os
import sys
import time

# Ensure libs are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../libs/python"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../libs/protocols"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../libs"))

from corekinect.test.fuota_client import FuotaClient


def main():
    client = FuotaClient(api_env="VAL_1_0")

    # Test cases: different flag combinations
    test_targets = [
        ["108.0.99.1-B", "109.0.99.1-B"],       # Bench only (no debug, no mfg)
        ["108.0.99.2-BM", "109.0.99.2-BM"],      # Bench + Mfg (what works)
        ["108.0.99.3-BD", "109.0.99.3-BD"],       # Bench + Debug (what's failing)
        ["108.0.99.4-BMD", "109.0.99.4-BMD"],     # Bench + Mfg + Debug
    ]

    created_plans = []

    print("=" * 70)
    print("CoreCloud FUOTA Target Flag Diagnosis")
    print("=" * 70)
    print()

    for targets in test_targets:
        flags = targets[0].rsplit("-", 1)[1]
        desc = f"DIAG: flag test -{flags}"

        print(f"--- Testing -{flags} flags ---")
        print(f"  Submitting targets: {targets}")

        try:
            plan_id = client.create_plan(
                stages=[{
                    "targets": targets,
                    "description": desc,
                    "isSkippable": False,
                }],
                description=desc,
                device_type_id=2,
                device_variant_id=3,
            )
            created_plans.append(plan_id)
            print(f"  Plan created: id={plan_id}")
        except Exception as e:
            print(f"  FAILED to create plan: {e}")
            continue

    # Now query all plans back
    print()
    print("=" * 70)
    print("Querying plans back from CoreCloud...")
    print("=" * 70)
    print()

    time.sleep(1)
    plans = client.list_plans()

    for plan_id in created_plans:
        plan = next((p for p in plans if p.get("planId") == plan_id), None)
        if not plan:
            print(f"Plan {plan_id}: NOT FOUND in plan list!")
            continue

        stored_stages = plan.get("stages", [])
        for i, stage in enumerate(stored_stages):
            stored = stage.get("targets", [])
            submitted = test_targets[created_plans.index(plan_id)]

            match = set(stored) == set(submitted)
            status = "MATCH" if match else "MISMATCH"
            print(f"Plan {plan_id} [{status}]:")
            print(f"  Submitted: {submitted}")
            print(f"  Stored:    {stored}")
            if not match:
                print(f"  *** CoreCloud MODIFIED the targets! ***")
                # Identify what changed
                for s, t in zip(sorted(submitted), sorted(stored)):
                    if s != t:
                        print(f"      {s} -> {t}")
            print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    mismatches = []
    for plan_id in created_plans:
        plan = next((p for p in plans if p.get("planId") == plan_id), None)
        if plan:
            stored = plan.get("stages", [{}])[0].get("targets", [])
            submitted = test_targets[created_plans.index(plan_id)]
            if set(stored) != set(submitted):
                flags = submitted[0].rsplit("-", 1)[1]
                stored_flags = stored[0].rsplit("-", 1)[1] if stored else "?"
                mismatches.append(f"-{flags} -> -{stored_flags}")

    if mismatches:
        print(f"CoreCloud MODIFIES these flag combinations:")
        for m in mismatches:
            print(f"  {m}")
        print()
        print("FUOTA plans with modified targets will NOT match uploaded CFW versions!")
        print("The uploaded CFW version string (from binary header) won't match")
        print("what CoreCloud expects, so delivery will never start.")
    else:
        print("CoreCloud stores all flag combinations as-is (no modification).")
        print("The FUOTA delivery issue is NOT caused by flag stripping.")
        print("Root cause is likely stale progress data from back-to-back plans.")

    # Cleanup: note plan IDs for manual deletion if needed
    print()
    print(f"Diagnostic plans created: {created_plans}")
    print("These are harmless (no devices assigned) but can be left for reference.")


if __name__ == "__main__":
    main()
