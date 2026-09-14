"""Server-operator account provisioning and recovery; passwords never travel in CLI arguments."""

import argparse
import getpass

from app import accounts, db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-organization")
    create.add_argument("--organization", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    reset = commands.add_parser("reset-password")
    reset.add_argument("--email", required=True)
    args = parser.parse_args()
    db.init()
    password = getpass.getpass("New password (12–128 characters): ")
    if password != getpass.getpass("Repeat password: "):
        parser.error("Passwords did not match.")
    if args.command == "create-organization":
        accounts.bootstrap(args.organization, args.email, args.name, password)
        print("Organization and owner created. Sign in through the pilot application.")
    else:
        hashed = accounts.password_hash(password)
        with db.connect(write=True) as c:
            user = c.execute(
                "SELECT * FROM users WHERE email=?", (accounts.normalize_email(args.email),)
            ).fetchone()
            if not user:
                parser.error("Account not found.")
            c.execute("UPDATE users SET password_hash=? WHERE id=?", (hashed, user["id"]))
            c.execute("DELETE FROM sessions WHERE user_id=?", (user["id"],))
            accounts.record(
                c,
                user["org_id"],
                None,
                "OPERATOR_PASSWORD_RESET",
                "Server operator reset account password and revoked sessions.",
            )
        print("Password reset; all existing sessions revoked.")


if __name__ == "__main__":
    main()
