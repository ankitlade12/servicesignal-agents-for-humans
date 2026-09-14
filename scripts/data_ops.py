"""Operator backup, isolated restore, and explicit private-source retention."""

import argparse
import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path

from app import db


def copy_database(source, destination):
    """SQLite online backup includes committed WAL data; never overwrites a file."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with sqlite3.connect(Path(source).resolve().as_uri() + "?mode=ro", uri=True) as origin:
            with sqlite3.connect(destination) as target:
                origin.backup(target)
                if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("Database integrity check failed.")
        return {
            "path": str(destination),
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "integrity": "ok",
        }
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


def retention(days, apply=False):
    cutoff = time.time() - days * 86400
    with db.connect(write=True) as c:
        changes = c.execute(
            "SELECT id,workspace_id,metrics FROM changes WHERE created_at<? AND state IN ('ENDED','SUPERSEDED') AND source!='[Source removed under retention policy]'",
            (cutoff,),
        ).fetchall()
        active_documents = set()
        for row in c.execute("SELECT metrics FROM changes WHERE state NOT IN ('ENDED','SUPERSEDED')"):
            document = json.loads(row[0]).get("document_id")
            if document:
                active_documents.add(document)
        documents = [
            row["id"]
            for row in c.execute("SELECT id FROM documents WHERE created_at<?", (cutoff,))
            if row["id"] not in active_documents
        ]
        if apply:
            for row in changes:
                metrics = json.loads(row["metrics"])
                metrics.pop("evidence_locations", None)
                metrics.pop("document_id", None)
                metrics["source_removed"] = True
                c.execute(
                    "UPDATE changes SET source='[Source removed under retention policy]',proposal='{}',metrics=? WHERE id=?",
                    (json.dumps(metrics), row["id"]),
                )
                db.event(
                    c,
                    row["workspace_id"],
                    row["id"],
                    "SOURCE_REMOVED",
                    "Operator retention removed private source text and quotations; approved facts and source hash retained.",
                )
            for document in documents:
                c.execute("DELETE FROM documents WHERE id=?", (document,))
        return {
            "applied": apply,
            "older_than_days": days,
            "sources": len(changes),
            "documents": len(documents),
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    backup = sub.add_parser("backup")
    backup.add_argument("--output", required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--input", required=True)
    restore.add_argument("--output", required=True)
    decrypt = sub.add_parser("decrypt-backup")
    decrypt.add_argument("--input", required=True)
    decrypt.add_argument("--output", required=True)
    prune = sub.add_parser("retention")
    prune.add_argument("--days", type=int, default=90)
    prune.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.command == "backup":
        result = copy_database(db.path(), args.output)
    elif args.command == "restore":
        result = copy_database(args.input, args.output)
        result["next_step"] = "Verify this isolated copy before pointing a stopped API/worker pair at it."
    elif args.command == "decrypt-backup":
        from app.operations import decrypt_backup

        decrypt_backup(args.input, args.output)
        result = {"path": args.output, "next_step": "Verify integrity and restore to an isolated service."}
    else:
        if args.days < 7:
            parser.error("Retention must be at least seven days.")
        db.init()
        result = retention(args.days, args.apply)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
