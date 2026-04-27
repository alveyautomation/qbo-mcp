#!/usr/bin/env python3
"""Pre-commit hook: refuse to commit files that mention an internal-only tenant.

This is a safety net for forks and downstream deployments. Extend
`FORBIDDEN_PATTERNS` with your own realm-specific tokens (vendor names,
customer names, account numbers, realm IDs) before installing the hook in
a private fork. Out of the box the list is empty for the public repository
— every contributor should add their own unmergeable identifiers locally
and never push that change.

Usage:
    python scripts/check_tenant_fingerprints.py <files...>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Add internal-only tokens here in private forks. Keep this list empty on
# the public main branch.
FORBIDDEN_PATTERNS: list[str] = []


def main(argv: list[str]) -> int:
    if not FORBIDDEN_PATTERNS:
        return 0

    pattern = re.compile("|".join(FORBIDDEN_PATTERNS), re.IGNORECASE)
    failed = False
    for arg in argv[1:]:
        path = Path(arg)
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in pattern.finditer(text):
            print(
                f"{path}: forbidden tenant fingerprint "
                f"{match.group(0)!r} at offset {match.start()}",
                file=sys.stderr,
            )
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
