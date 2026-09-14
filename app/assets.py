"""Content-address frontend assets so a fresh page never loads a prior release's UI."""

import hashlib
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"


def version():
    digest = hashlib.sha256()
    for name in ("app.js", "styles.css", "typography.css"):
        digest.update((STATIC / name).read_bytes())
    return digest.hexdigest()[:16]
