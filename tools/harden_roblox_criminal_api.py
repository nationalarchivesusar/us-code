#!/usr/bin/env python3
"""Compatibility entry point for the Roblox criminal-law API hardener.

Runs the balanced charge-preserving hardener first, then applies the narrow
section-level exclusions required for the Roblox booking catalog, and finally
applies the Roblox-specific 20-minute booking cap while preserving the enacted
30-minute statutory ceiling in the legal sentencing data. In --check mode, all
layers are audited without modifying generated output.
"""
from harden_roblox_criminal_api_v2 import KNOWN_TITLE18_CHARGES, main as harden_main
from apply_roblox_api_exclusions import main as exclusions_main
from set_roblox_booking_cap import main as booking_cap_main

# Section 751 is an unambiguous criminal escape offense, but its operative
# penalty syntax is conditional ("shall, if ..., be fined") and therefore does
# not match the strict generic "shall be fined" classifier. Explicitly retain
# the charge so the normal content-safety pass can withhold its restricted body
# text instead of incorrectly deleting the safely named charge from booking.
KNOWN_TITLE18_CHARGES.add("751")


def main() -> int:
    result = harden_main()
    if result not in (None, 0):
        return int(result)
    result = exclusions_main()
    if result not in (None, 0):
        return int(result)
    result = booking_cap_main()
    return 0 if result is None else int(result)


if __name__ == "__main__":
    raise SystemExit(main())
