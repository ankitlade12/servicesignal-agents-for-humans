"""Provision an empty organization with a single-use owner setup link; no email is sent."""

import argparse
import os
import secrets
import time
from pathlib import Path

from app import accounts, db
from app.domain import PROGRAM


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    email = accounts.normalize_email(args.email)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        db.init()
        token = secrets.token_urlsafe(32)
        with db.connect(write=True) as c:
            if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                raise ValueError("This email already has an account. Use account recovery instead.")
            org = secrets.token_urlsafe(16)
            c.execute("INSERT INTO organizations VALUES(?,?,?)", (org, args.organization, time.time()))
            accounts.create_workspace(
                c,
                org,
                {**PROGRAM, "name": "New program", "organization": args.organization, "configured": False},
            )
            c.execute(
                "INSERT INTO invitations VALUES(?,?,?,?,?,0)",
                (accounts.token_hash(token), org, email, "owner", time.time() + 86400),
            )
            accounts.record(
                c, org, None, "OWNER_SETUP_ISSUED", "Operator issued a single-use initial-owner setup link."
            )
        with os.fdopen(descriptor, "w") as handle:
            handle.write(
                "ServiceSignal initial owner setup\n\nOpen this private link within 24 hours:\n"
                + args.origin.rstrip("/")
                + "/#join="
                + token
                + "\n\nUse this email: "
                + email
                + "\nChoose your own password. No message has been sent.\n"
            )
        print("Owner setup instructions saved to the requested restricted file.")
    except BaseException:
        output.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
