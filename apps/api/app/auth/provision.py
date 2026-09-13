"""Operator helper: create or rotate an invited user password.

Usage (password read from the environment, never logged):

    PREDICTA_API_BOOTSTRAP_PASSWORD=... python -m app.auth.provision beta@example.com
"""

from __future__ import annotations

import os
import sys

from app.auth.service import provision_user
from app.core.clock import Clock
from app.core.config import get_settings
from app.db.session import session_scope


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: python -m app.auth.provision <email>\n")
        return 2
    password = os.environ.get("PREDICTA_API_BOOTSTRAP_PASSWORD", "")
    if not password:
        sys.stderr.write("PREDICTA_API_BOOTSTRAP_PASSWORD is required.\n")
        return 2
    settings = get_settings()
    email = argv[1]
    with session_scope(settings) as session:
        user = provision_user(session, email=email, password=password, now=Clock().now())
        sys.stdout.write(f"provisioned {user.email}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
