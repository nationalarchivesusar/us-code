#!/usr/bin/env python3
"""Compatibility entry point for the Roblox criminal-law API hardener.

Runs the balanced charge-preserving hardener first, then applies the narrow
section-level exclusions required for the Roblox booking catalog. In --check
mode, both layers are audited without modifying generated output.
"""
from harden_roblox_criminal_api_v2 import main as harden_main
from apply_roblox_api_exclusions import main as exclusions_main


def main() -> int:
    result = harden_main()
    if result not in (None, 0):
        return int(result)
    result = exclusions_main()
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main())
