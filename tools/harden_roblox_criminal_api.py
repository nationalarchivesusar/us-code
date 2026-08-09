#!/usr/bin/env python3
"""Compatibility entry point for the Roblox criminal-law API hardener.

Runs the balanced charge-preserving hardener with the audited Title 18 charge
classifier, then applies the narrow section-level exclusions required for the
Roblox booking catalog, and finally applies the Roblox-specific 20-minute
booking cap while preserving the enacted 30-minute statutory ceiling in the
legal sentencing data. In --check mode, all layers are audited without
modifying generated output.
"""
import harden_roblox_criminal_api_v2 as hardener
from apply_roblox_api_exclusions import main as exclusions_main
from set_roblox_booking_cap import main as booking_cap_main
from title18_charge_classifier import (
    KNOWN_TITLE18_CHARGES,
    title18_is_positive_charge,
)

# Keep the existing hardening/safety engine, but replace its brittle inline
# charge detector with the separately audited classifier. Updating the shared
# known-charge set also keeps charge_classification metadata accurate.
hardener.KNOWN_TITLE18_CHARGES.clear()
hardener.KNOWN_TITLE18_CHARGES.update(KNOWN_TITLE18_CHARGES)
hardener.title18_is_positive_charge = title18_is_positive_charge


def main() -> int:
    result = hardener.main()
    if result not in (None, 0):
        return int(result)
    result = exclusions_main()
    if result not in (None, 0):
        return int(result)
    result = booking_cap_main()
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main())
