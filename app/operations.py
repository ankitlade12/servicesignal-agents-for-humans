"""Scheduled backups and optional retention in a separate supervised process."""

import json
import logging
import os
import secrets
import shutil
import time
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from . import db
from .account_security import cipher

log = logging.getLogger("servicesignal.operations")


def encrypted_backup(source, target):
    key, iv = secrets.token_bytes(32), secrets.token_bytes(12)
    encrypted_key = cipher().encrypt(key)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(iv)).encryptor()
    with open(source, "rb") as incoming, open(target, "xb") as outgoing:
        os.chmod(target, 0o600)
        outgoing.write(b"SIGNALBACKUP1\n" + encrypted_key + b"\n" + iv)
        for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
            outgoing.write(encryptor.update(chunk))
        outgoing.write(encryptor.finalize())
        outgoing.write(encryptor.tag)


def decrypt_backup(source, target):
    target = Path(target)
    try:
        with open(source, "rb") as incoming:
            if incoming.readline() != b"SIGNALBACKUP1\n":
                raise ValueError("Unsupported backup format.")
            key = cipher().decrypt(incoming.readline().strip())
            iv = incoming.read(12)
            start = incoming.tell()
            incoming.seek(-16, 2)
            end = incoming.tell()
            tag = incoming.read(16)
            incoming.seek(start)
            decryptor = Cipher(algorithms.AES(key), modes.GCM(iv, tag)).decryptor()
            with open(target, "xb") as outgoing:
                os.chmod(target, 0o600)
                remaining = end - start
                while remaining:
                    chunk = incoming.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise ValueError("Truncated backup.")
                    remaining -= len(chunk)
                    outgoing.write(decryptor.update(chunk))
                outgoing.write(decryptor.finalize())
    except FileExistsError:
        raise
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def maintenance():
    directory = os.getenv("BACKUP_DIRECTORY")
    if not directory:
        return
    from scripts.data_ops import copy_database, retention

    interval = max(3600, int(os.getenv("BACKUP_INTERVAL_SECONDS", "86400")))
    with db.connect() as c:
        previous = c.execute("SELECT value FROM settings WHERE key='backup_status'").fetchone()
    status = json.loads(previous[0]) if previous else {}
    if time.time() - status.get("attempted_at", 0) < interval:
        return
    status = {"attempted_at": time.time(), "state": "RUNNING", "off_host": False}
    with db.connect(write=True) as c:
        c.execute("INSERT OR REPLACE INTO settings VALUES('backup_status',?)", (json.dumps(status),))
    temporary = None
    try:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        name = "servicesignal-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + secrets.token_hex(4)
        temporary = directory / (name + ".sqlite")
        copy_database(db.path(), temporary)
        target = directory / (name + ".signal-backup")
        encrypted_backup(temporary, target)
        temporary.unlink()
        if os.getenv("BACKUP_S3_BUCKET"):
            import boto3

            client = boto3.client("s3", endpoint_url=os.getenv("BACKUP_S3_ENDPOINT") or None)
            client.upload_file(
                str(target),
                os.environ["BACKUP_S3_BUCKET"],
                os.getenv("BACKUP_S3_PREFIX", "servicesignal/").rstrip("/") + "/" + target.name,
            )
            status["off_host"] = True
        keep = max(2, int(os.getenv("BACKUP_KEEP_COUNT", "7")))
        for old in sorted(directory.glob("servicesignal-*.signal-backup"), reverse=True)[keep:]:
            old.unlink()
        days = int(os.getenv("SOURCE_RETENTION_DAYS", "0"))
        if days >= 7:
            status["retention"] = retention(days, apply=True)
        status.update(state="OK", completed_at=time.time(), bytes=target.stat().st_size)
    except Exception as error:
        status.update(state="FAILED", category=type(error).__name__)
        log.warning("Scheduled backup failed: %s", type(error).__name__)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
        with db.connect(write=True) as c:
            c.execute("INSERT OR REPLACE INTO settings VALUES('backup_status',?)", (json.dumps(status),))


def snapshot():
    with db.connect() as c:
        backup = c.execute("SELECT value FROM settings WHERE key='backup_status'").fetchone()
        pending = c.execute("SELECT count(*) FROM jobs WHERE state='QUEUED'").fetchone()[0]
        failed = c.execute("SELECT count(*) FROM jobs WHERE state='FAILED'").fetchone()[0]
    disk = shutil.disk_usage(Path(db.path()).parent)
    return {
        "queued_jobs": pending,
        "failed_jobs": failed,
        "disk_free_bytes": disk.free,
        "database_bytes": Path(db.path()).stat().st_size,
        "backup": json.loads(backup[0])
        if backup
        else {"state": "NOT_CONFIGURED" if not os.getenv("BACKUP_DIRECTORY") else "PENDING"},
    }


def run():
    db.init()
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            maintenance()
        except Exception as error:
            log.warning("Maintenance failed: %s", type(error).__name__)
        time.sleep(60)


if __name__ == "__main__":
    run()
